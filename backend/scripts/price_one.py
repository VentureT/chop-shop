"""Validate eBay filter syntax and category resolution for one part before running the full loop.

Usage (from backend/):  python -m scripts.price_one <VIN> <part_id> [zip]
Example:                python -m scripts.price_one WAUCFAFR5FA000001 headlamp_assembly 75201
"""
from __future__ import annotations

import json
import sys

from app.config import get_settings
from app.models import Options
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
    cat, compat = v.browse.resolve_category(query)
    print(f"Query: {query!r} -> category {cat} compat={compat}")
    listings, mode = v.browse.search_part(vehicle, part, query, zip_code)
    print(f"Mode: {mode}  listings: {len(listings)}")
    for l in sorted(listings, key=lambda x: x.price)[:10]:
        print(f"  ${l.price:>8.2f}  {l.compatibility_match or '-':8}  {l.condition:10}  {l.title[:70]}")
    pv = v.value_part(vehicle, part, opts, zip_code)
    print(json.dumps({k: pv.model_dump()[k] for k in ["price_status", "sample_size", "asking_median", "est_sold_each", "est_net_each", "confidence"]}, indent=2))


if __name__ == "__main__":
    main()
