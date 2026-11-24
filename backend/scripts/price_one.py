"""Validate eBay filter syntax and category resolution for one part before running the full loop.

Usage (from backend/):  python -m scripts.price_one <VIN> <part_id> [zip] [drop-reason filter]
Example:                python -m scripts.price_one WAUCFAFR5FA000001 headlamp_assembly 75201
"""
from __future__ import annotations

import json
import sys

from app.config import get_settings
from app.models import Options
from app.services.pricing import drop_reason
from app.services.taxonomy import load_part_types, query_for
from app.services.valuation import Valuator
from app.services.vpic import decode_vin


def main() -> None:
    if len(sys.argv) < 3:
        print(__doc__)
        sys.exit(1)
    vin, part_id = sys.argv[1], sys.argv[2]
    zip_code = sys.argv[3] if len(sys.argv) > 3 else None
    settings = get_settings()
    if not settings.ebay_configured:
        print("EBAY_CLIENT_ID / EBAY_CLIENT_SECRET not set in backend/.env")
        sys.exit(2)
    part = next((p for p in load_part_types() if p.id == part_id), None)
    if not part:
        print(f"unknown part id {part_id}. Known: {', '.join(p.id for p in load_part_types())}")
        sys.exit(1)
    vehicle = decode_vin(vin)
    print(f"Vehicle: {vehicle.search_terms} {vehicle.body} {vehicle.drive} {vehicle.displacement_l}L")
    v = Valuator(settings)
    opts = Options()
    query = query_for(part, opts)
    cat, compat = v.browse.resolve_category(query, part.ebay_category_id)
    print(f"Query: {query!r} -> category {cat} compat={compat}" + (" (pinned)" if part.ebay_category_id else ""))
    raw, listings, mode = v.gather(vehicle, part, query, zip_code)
    print(f"Mode: {mode}  raw: {len(raw)}  after cleaning: {len(listings)}")
    for l in sorted(listings, key=lambda x: x.price)[:10]:
        print(f"  ${l.price:>8.2f}  {l.compatibility_match or '-':8}  {l.condition[:10]:10}  {l.title[:70]}")
    kept = {k.item_id for k in listings}
    dropped = [l for l in raw if l.item_id not in kept]
    if dropped:
        reasons: dict[str, int] = {}
        for l in dropped:
            r = drop_reason(l, part, query, vehicle) or "duplicate / below price floor"
            reasons[r] = reasons.get(r, 0) + 1
        print(f"  -- dropped {len(dropped)}: " + "; ".join(f"{k} x{v}" for k, v in sorted(reasons.items(), key=lambda kv: -kv[1])))
        show = sys.argv[4] if len(sys.argv) > 4 else ""
        for l in [d for d in dropped if show in (drop_reason(d, part, query, vehicle) or "")][: 12 if show else 5]:
            print(f"  x ${l.price:>8.2f}  [{drop_reason(l, part, query, vehicle) or 'dup/floor'}]  {l.title[:70]}")
    pv = v.value_part(vehicle, part, opts, zip_code)
    print(json.dumps({k: pv.model_dump()[k] for k in ["price_status", "sample_size", "asking_median", "est_sold_each", "est_net_each", "confidence"]}, indent=2))


if __name__ == "__main__":
    main()
