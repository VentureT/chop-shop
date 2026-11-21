"""eBay Browse API search for used parts, with category resolution and caching.

Strategy per part type:
  1. Resolve an eBay leaf category for the part keyword via the Taxonomy API
     (get_category_suggestions) and check whether it supports parts compatibility.
  2. If it does: item_summary/search with compatibility_filter=Year:..;Make:..;Model:..
  3. Otherwise (or on a 400 from the compat search): keyword search with the
     vehicle terms folded into `q`, restricted to eBay Motors Parts & Accessories.
All responses are cached (SQLite, TTL) keyed by (year, make, model, part id).
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

PARTS_ROOT_CATEGORY = "6030"  # eBay Motors > Parts & Accessories (L1; requires q)
MARKETPLACE = "EBAY_US"


class EbayBrowse:
    def __init__(self, settings: Settings, auth: EbayAuth, cache: TTLCache) -> None:
        self.s = settings
        self.auth = auth
        self.cache = cache

    # ---------- helpers ----------
    def _headers(self, zip_code: str | None) -> dict[str, str]:
        h = {
            "Authorization": f"Bearer {self.auth.token()}",
            "X-EBAY-C-MARKETPLACE-ID": MARKETPLACE,
            "Accept": "application/json",
        }
        if zip_code:
            h["X-EBAY-C-ENDUSERCTX"] = f"contextualLocation=country%3DUS%2Czip%3D{quote(zip_code)}"
        return h

    def _get(self, path: str, params: dict, zip_code: str | None = None) -> dict:
        with httpx.Client(timeout=30) as client:
            resp = client.get(f"{self.s.ebay_api_base}{path}", params=params, headers=self._headers(zip_code))
            if resp.status_code >= 400:
                raise httpx.HTTPStatusError(
                    f"{resp.status_code} {resp.text[:300]}", request=resp.request, response=resp
                )
            return resp.json()

    # ---------- category resolution ----------
    def resolve_category(self, keyword: str) -> tuple[str | None, bool]:
        """Return (category_id, supports_compatibility) for a part keyword."""
        key = f"cat:{keyword.lower()}"
        cached = self.cache.get(key)
        if cached:
            return cached["id"], cached["compat"]
        cat_id: str | None = None
        compat = False
        try:
            data = self._get(
                "/commerce/taxonomy/v1/category_tree/0/get_category_suggestions",
                {"q": keyword},
            )
            for sug in data.get("categorySuggestions", []):
                anc = sug.get("categoryTreeNodeAncestors", [])
                # keep suggestions under eBay Motors Parts & Accessories
                if any(a.get("categoryId") == PARTS_ROOT_CATEGORY for a in anc):
                    cat_id = sug["category"]["categoryId"]
                    break
            if cat_id:
                try:
                    props = self._get(
                        f"/commerce/taxonomy/v1/category_tree/0/get_compatibility_properties",
                        {"category_id": cat_id},
                    )
                    names = {p.get("name") for p in props.get("compatibilityProperties", [])}
                    compat = {"Year", "Make", "Model"} <= names
                except httpx.HTTPStatusError:
                    compat = False
        except httpx.HTTPStatusError as exc:
            log.warning("taxonomy lookup failed for %s: %s", keyword, exc)
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

    def search_part(self, vehicle: VehicleProfile, part: PartType, query: str, zip_code: str | None) -> tuple[list[Listing], str]:
        """Return (listings, mode) where mode is 'compat' | 'keyword'. Cached."""
        key = f"srch:{vehicle.year}:{vehicle.make.lower()}:{vehicle.model.lower()}:{part.id}:{query.lower()}"
        cached = self.cache.get(key)
        if cached:
            return [Listing(**l) for l in cached["listings"]], cached["mode"]

        base_filter = "conditions:{USED},priceCurrency:USD,deliveryCountry:US,buyingOptions:{FIXED_PRICE|BEST_OFFER}"
        params_common = {"filter": base_filter, "sort": "price", "limit": "100", "fieldgroups": "MATCHING_ITEMS"}

        cat_id, compat = self.resolve_category(query)
        listings: list[Listing] = []
        mode = "keyword"

        if cat_id and compat:
            compat_filter = f"Year:{vehicle.year};Make:{vehicle.make.title()};Model:{vehicle.model}"
            try:
                data = self._get(
                    "/buy/browse/v1/item_summary/search",
                    {"q": query, "category_ids": cat_id, "compatibility_filter": compat_filter, **params_common},
                    zip_code,
                )
                listings = self._parse(data.get("itemSummaries") or [])
                mode = "compat"
            except httpx.HTTPStatusError as exc:
                log.warning("compat search failed for %s (%s); falling back to keyword", part.id, exc)

        if not listings:
            q = f"{vehicle.search_terms} {query}"[:100]
            data = self._get(
                "/buy/browse/v1/item_summary/search",
                {"q": q, "category_ids": cat_id or PARTS_ROOT_CATEGORY, **params_common},
                zip_code,
            )
            listings = self._parse(data.get("itemSummaries") or [])
            mode = "keyword"

        self.cache.set(key, {"listings": [l.model_dump() for l in listings], "mode": mode})
        return listings, mode
