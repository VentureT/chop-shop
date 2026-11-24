"""Price every applicable part for a VIN against live eBay and print a tuning table.

Usage (from backend/):  python -m scripts.price_all <VIN> [zip]
Columns: est net total | asking median | n (cleaned) | raw | mode | confidence | reference | part
"""
from __future__ import annotations

import sys
import time

from app.config import get_settings
from app.models import Options
from app.services.valuation import Valuator
from app.services.vpic import decode_vin


def main() -> None:
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(1)
    vin = sys.argv[1]
    zip_code = sys.argv[2] if len(sys.argv) > 2 else None
    settings = get_settings()
    vehicle = decode_vin(vin)
    print(f"Vehicle: {vehicle.search_terms} {vehicle.body} {vehicle.drive}")
    t0 = time.time()
    res = Valuator(settings).valuate(vehicle, Options(), zip_code)
    print(f"{'net total':>10} {'asking':>8} {'n':>4} {'raw':>4} {'mode':<8} {'conf':<7} {'ref':>6}  part")
    for v in res.parts:
        raw = v.note.split("(")[-1].split(" raw")[0] if " raw" in v.note else "-"
        mode = "compat" if "compat" in v.note else ("keyword" if "keyword" in v.note else v.price_status)
        print(f"{v.est_net_total:>10.2f} {v.asking_median:>8.2f} {v.sample_size:>4} {raw:>4} {mode:<8} {v.confidence:<7} {v.part.reference_asking:>6.0f}  {v.part.id}")
    t = res.totals
    print(f"\ngross asking {t['gross_asking']:.0f} | est sold {t['est_sold']:.0f} | est net {t['est_net']:.0f} | "
          f"live {t['live_priced']}/{t['parts_considered']} | {time.time()-t0:.0f}s")


if __name__ == "__main__":
    main()
