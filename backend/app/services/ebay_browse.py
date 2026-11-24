"""eBay Browse API search for used parts, with category resolution and caching.

Strategy per part type:
  1. Resolve an eBay leaf category for the part keyword. The part may pin one
     (`ebay_category_id`); otherwise ask the Taxonomy API's *eBay Motors* tree
     (id 100) for suggestions and keep the first under Car & Truck Parts (6030).
     Tree 0 (plain EBAY_US) suggests heavy-equipment and consumer-electronics
     categories for car parts, so it is not used.
  2. If the category supports parts compatibility: item_summary/search with
     compatibility_filter=Year:..;Make:..;Model:.. sorted by best match.
  3. The valuator cleans the result (pricing.clean_listings) and, if fewer than
     SPARSE_THRESHOLD listings survive, tops up with a keyword search that folds
     the vehicle terms into `q` in the same category.
Raw responses are cached (SQLite, TTL) keyed by (year, make, model, part id, query),
so cached data stays raw and cleaning rules can change without refetching.
"""
from __future__ import annotations

import logging
from urllib.parse import quote

import httpx

from app.config import Settings
from app.models import Listing, PartType, VehicleProfile
from app.services.cache import TTLCache
from app.services.ebay_auth import EbayAuth

log = logging.getLogger(__name__)

CAR_TRUCK_PARTS_CATEGORY = "6030"  # eBay Motors > Parts & Accessories > Car & Truck Parts & Accessories
MOTORS_TREE = "100"  # EBAY_MOTORS_US category tree (get_default_category_tree_id)
MARKETPLACE = "EBAY_US"
SPARSE_THRESHOLD = 5
CACHE_VERSION = "v2"  # bump when request shape changes so stale cache entries are skipped


class EbayBrowse:
    def __init__(self, settings: Settings, auth: EbayAuth, cache: TTLCache) -> None:
        self.s = settings
        self.auth = auth
        self.cache = cache

    # ---------- helpers ----------
    def _headers(self, zip_code: str | None, marketplace: str = MARKETPLACE) -> dict[str, str]:
        h = {
            "Authorization": f"Bearer {self.auth.token()}",
            "X-EBAY-C-MARKETPLACE-ID": marketplace,
            "Accept": "application/json",
        }
        if zip_code:
            h["X-EBAY-C-ENDUSERCTX"] = f"contextualLocation=country%3DUS%2Czip%3D{quote(zip_code)}"
        return h

    def _get(self, path: str, params: dict, zip_code: str | None = None, marketplace: str = MARKETPLACE) -> dict:
        with httpx.Client(timeout=30) as client:
            resp = client.get(
                f"{self.s.ebay_api_base}{path}", params=params, headers=self._headers(zip_code, marketplace)
            )
            if resp.status_code >= 400:
                raise httpx.HTTPStatusError(
                    f"{resp.status_code} {resp.text[:300]}", request=resp.request, response=resp
                )
            return resp.json()

    # ---------- category resolution ----------
    def supports_compatibility(self, cat_id: str) -> bool:
        key = f"{CACHE_VERSION}:compat:{cat_id}"
        cached = self.cache.get(key)
        if cached is not None:
            return bool(cached)
        ok = False
        try:
            props = self._get(
                f"/commerce/taxonomy/v1/category_tree/{MOTORS_TREE}/get_compatibility_properties",
                {"category_id": cat_id},
                marketplace="EBAY_MOTORS_US",
            )
            names = {p.get("name") for p in props.get("compatibilityProperties", [])}
            ok = {"Year", "Make", "Model"} <= names
        except httpx.HTTPStatusError as exc:
            log.info("no compatibility properties for category %s: %s", cat_id, exc)
        self.cache.set(key, ok)
        return ok

    def resolve_category(self, keyword: str, override: str | None = None) -> tuple[str | None, bool]:
        """Return (category_id, supports_compatibility) for a part keyword."""
        if override:
            return override, self.supports_compatibility(override)
        key = f"{CACHE_VERSION}:cat:{keyword.lower()}"
        cached = self.cache.get(key)
        if cached:
            return cached["id"], cached["compat"]
        cat_id: str | None = None
        try:
            data = self._get(
                f"/commerce/taxonomy/v1/category_tree/{MOTORS_TREE}/get_category_suggestions",
                {"q": keyword},
                marketplace="EBAY_MOTORS_US",
            )
            for sug in data.get("categorySuggestions", []):
                anc = sug.get("categoryTreeNodeAncestors", [])
                if any(a.get("categoryId") == CAR_TRUCK_PARTS_CATEGORY for a in anc):
                    cat_id = sug["category"]["categoryId"]
                    break
        except httpx.HTTPStatusError as exc:
            log.warning("taxonomy lookup failed for %s: %s", keyword, exc)
        compat = self.supports_compatibility(cat_id) if cat_id else False
        self.cache.set(key, {"id": cat_id, "compat": compat})
        return cat_id, compat

    # ---------- search ----------
    @staticmethod
    def _parse(items: list[dict]) -> list[Listing]:
        out: list[Listing] = []
        for it in items:
            try:
                price = float(it["price"]["value"])
            except (KeyError, TypeError, ValueError):
                continue
            ship = None
            for opt in it.get("shippingOptions") or []:
                cost = (opt.get("shippingCost") or {}).get("value")
                if cost is not None:
                    try:
                        ship = float(cost)
                    except ValueError:
                        ship = None
                    break
            out.append(
                Listing(
                    item_id=it.get("itemId", ""),
                    title=it.get("title", ""),
                    price=price,
                    condition=it.get("condition", ""),
                    condition_id=str(it.get("conditionId", "")),
                    buying_options=it.get("buyingOptions") or [],
                    compatibility_match=it.get("compatibilityMatch", ""),
                    url=it.get("itemWebUrl", ""),
                    shipping=ship,
                )
            )
        return out

    _FILTER = "conditions:{USED},priceCurrency:USD,deliveryCountry:US,buyingOptions:{FIXED_PRICE|BEST_OFFER}"
    # Best-match order (no `sort`): sorting by price ascending would return the
    # 200 cheapest accessories in the category instead of the part.
    _COMMON = {"filter": _FILTER, "limit": "200", "fieldgroups": "MATCHING_ITEMS"}

    def _key(self, kind: str, vehicle: VehicleProfile, part: PartType, query: str) -> str:
        return f"{CACHE_VERSION}:{kind}:{vehicle.year}:{vehicle.make.lower()}:{vehicle.model.lower()}:{part.id}:{query.lower()}"

    def search_compat(self, vehicle: VehicleProfile, part: PartType, query: str, zip_code: str | None) -> list[Listing]:
        """Compatibility-filtered search in the part's leaf category. [] if unsupported. Cached raw."""
        key = self._key("compat", vehicle, part, query)
        cached = self.cache.get(key)
        if cached is not None:
            return [Listing(**l) for l in cached]
        cat_id, compat = self.resolve_category(query, part.ebay_category_id)
        listings: list[Listing] = []
        if cat_id and compat:
            compat_filter = f"Year:{vehicle.year};Make:{vehicle.make.title()};Model:{vehicle.model}"
            try:
                data = self._get(
                    "/buy/browse/v1/item_summary/search",
                    {"q": query, "category_ids": cat_id, "compatibility_filter": compat_filter, **self._COMMON},
                    zip_code,
                )
                listings = self._parse(data.get("itemSummaries") or [])
            except httpx.HTTPStatusError as exc:
                log.warning("compat search failed for %s (%s)", part.id, exc)
        self.cache.set(key, [l.model_dump() for l in listings])
        return listings

    def search_keyword(self, vehicle: VehicleProfile, part: PartType, query: str, zip_code: str | None) -> list[Listing]:
        """Keyword search with the vehicle terms in `q`, in the leaf category if known. Cached raw."""
        key = self._key("keyword", vehicle, part, query)
        cached = self.cache.get(key)
        if cached is not None:
            return [Listing(**l) for l in cached]
        cat_id, _ = self.resolve_category(query, part.ebay_category_id)
        q = f"{vehicle.search_terms} {query}"[:100]
        data = self._get(
            "/buy/browse/v1/item_summary/search",
            {"q": q, "category_ids": cat_id or CAR_TRUCK_PARTS_CATEGORY, **self._COMMON},
            zip_code,
        )
        listings = self._parse(data.get("itemSummaries") or [])
        self.cache.set(key, [l.model_dump() for l in listings])
        return listings
