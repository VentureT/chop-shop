"""Orchestrates decode -> taxonomy -> pricing -> flags -> comparison."""
from __future__ import annotations

import logging
from datetime import timedelta

from app.config import Settings
from app.models import (
    CompareRequest,
    CompareResponse,
    Options,
    PartType,
    PartValuation,
    ValuateResponse,
    VehicleProfile,
)
from app.services import legal, pricing
from app.services.cache import TTLCache
from app.services.ebay_auth import EbayAuth
from app.services.ebay_browse import EbayBrowse
from app.services.taxonomy import applicable_parts, query_for

log = logging.getLogger(__name__)


class Valuator:
    def __init__(self, settings: Settings) -> None:
        self.s = settings
        self.cache = TTLCache(settings.cache_path, int(timedelta(days=settings.cache_ttl_days).total_seconds()))
        self.auth = EbayAuth(settings)
        self.browse = EbayBrowse(settings, self.auth, self.cache)

    # ---------- single part ----------
    def value_part(self, vehicle: VehicleProfile, part: PartType, options: Options, zip_code: str | None) -> PartValuation:
        query = query_for(part, options)
        flags, sellable, haircut = legal.part_flags(part, vehicle, self.s.state)
        pv = PartValuation(part=part, query=query, price_status="reference", flags=flags, sellable=sellable)

        if not sellable:
            pv.price_status = "reference"
            pv.note = "Not sellable on mainstream marketplaces; valued at $0."
            return pv

        if self.auth.configured:
            try:
                listings, mode = self.browse.search_part(vehicle, part, query, zip_code)
                stats = pricing.summarize(listings)
                if stats["n"] > 0:
                    pv.price_status = "live"
                    pv.sample_size = stats["n"]
                    pv.exact_share = round(stats["exact_share"], 2)
                    pv.asking_median = stats["median"]
                    pv.asking_low = stats["low"]
                    pv.asking_high = stats["high"]
                    pv.confidence = pricing.confidence(stats["n"], stats["exact_share"], mode)  # type: ignore[assignment]
                    pv.sample_listings = sorted(listings, key=lambda l: l.price)[:5]
                    pv.note = f"eBay {mode} search: {stats['n']} used listings."
                else:
                    pv.price_status = "no_results"
                    pv.note = "No used listings found; using reference estimate."
            except Exception as exc:  # network / auth / quota
                log.warning("eBay lookup failed for %s: %s", part.id, exc)
                pv.price_status = "error"
                pv.note = f"eBay lookup failed ({type(exc).__name__}); using reference estimate."
        else:
            pv.price_status = "no_credentials"
            pv.note = "No eBay credentials configured; using built-in reference estimate."

        if pv.asking_median == 0:
            pv.asking_median = part.reference_asking
            pv.asking_low = round(part.reference_asking * 0.6, 2)
            pv.asking_high = round(part.reference_asking * 1.4, 2)
            pv.confidence = "low" if part.reference_asking else "none"

        pv.confidence_reason = pricing.explain_confidence(
            pv.sample_size, pv.exact_share, "compat" if "compat" in pv.note else "keyword", pv.price_status
        )
        pv.est_sold_each = pricing.est_sold(pv.asking_median, haircut)
        pv.est_net_each = pricing.est_net(pv.est_sold_each, part.size_class)
        pv.est_net_total = round(pv.est_net_each * part.qty, 2)
        return pv

    # ---------- whole vehicle ----------
    def valuate(self, vehicle: VehicleProfile, options: Options, zip_code: str | None, max_parts: int | None = None) -> ValuateResponse:
        parts = applicable_parts(vehicle, options)
        if max_parts:
            parts = parts[:max_parts]
        valuations = [self.value_part(vehicle, p, options, zip_code or self.s.default_zip) for p in parts]
        valuations.sort(key=lambda v: v.est_net_total, reverse=True)

        sellable = [v for v in valuations if v.sellable]
        totals = {
            "parts_considered": len(valuations),
            "parts_sellable": len(sellable),
            "gross_asking": round(sum(v.asking_median * v.part.qty for v in sellable), 2),
            "est_sold": round(sum(v.est_sold_each * v.part.qty for v in sellable), 2),
            "est_net": round(sum(v.est_net_total for v in sellable), 2),
            "removal_hours": round(sum(v.part.removal_hours * v.part.qty for v in sellable), 1),
            "top_10_removal_hours": round(sum(v.part.removal_hours * v.part.qty for v in sellable[:10]), 1),
            "live_priced": sum(1 for v in valuations if v.price_status == "live"),
            "top_10_share": 0.0,
        }
        if totals["est_net"]:
            top10 = sum(v.est_net_total for v in sellable[:10])
            totals["top_10_share"] = round(top10 / totals["est_net"], 2)

        return ValuateResponse(
            vehicle=vehicle,
            options=options,
            parts=valuations,
            totals=totals,
            vehicle_flags=legal.vehicle_flags(vehicle, self.s.state),
            ebay_live=self.auth.configured,
        )


def compare(req: CompareRequest) -> CompareResponse:
    t = req.valuation.totals
    gross = float(t.get("gross_asking", 0.0))
    sold = float(t.get("est_sold", 0.0)) * req.sell_through
    net = float(t.get("est_net", 0.0)) * req.sell_through + req.shell_scrap
    hours = float(t.get("removal_hours", 0.0)) + 20.0  # +listing/packing/shipping overhead
    after_labor = net - hours * req.hourly_value

    candidates = {
        "instant_offer": req.instant_offer,
        "private_party": req.private_party,
        "part_out": after_labor,
    }
    winner = max(candidates, key=candidates.get)  # type: ignore[arg-type]

    notes = [
        f"Part-out assumes {int(req.sell_through * 100)}% of parts actually sell; the rest are scrapped with the shell.",
        f"Labor valued at ${req.hourly_value:.0f}/hr over ~{hours:.0f} hours including listing, packing and shipping.",
        "Airbags are excluded (unsellable on major platforms). Catalytic converter requires a licensed buyer.",
        "Prices are asking-price medians with a haircut, not sold prices. Treat as +/-40%.",
    ]
    return CompareResponse(
        instant_offer=req.instant_offer,
        private_party=req.private_party,
        part_out_gross_asking=round(gross, 2),
        part_out_est_sold=round(sold, 2),
        part_out_est_net=round(net, 2),
        part_out_net_after_labor=round(after_labor, 2),
        total_hours=round(hours, 1),
        months_estimate="6-12",
        sell_through=req.sell_through,
        shell_scrap=req.shell_scrap,
        winner=winner,
        notes=notes,
    )
