"""Curated sellable-parts taxonomy (Hollander-derived) and applicability filtering."""
from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path

from app.models import Options, PartType, VehicleProfile

DATA_PATH = Path(__file__).resolve().parent.parent / "data" / "part_types.json"


@lru_cache
def load_part_types() -> list[PartType]:
    with DATA_PATH.open() as f:
        raw = json.load(f)
    return [PartType(**p) for p in raw]


def _matches(rule: dict, vehicle: VehicleProfile, options: Options) -> bool:
    """Every key in `rule` must match. Supported keys:
    body: [..], drive: [..], transmission: [..], turbo: bool,
    option.<name>: value | [values]
    """
    for key, want in rule.items():
        if key == "body":
            if vehicle.body not in want:
                return False
        elif key == "drive":
            if vehicle.drive not in want:
                return False
        elif key == "transmission":
            if not any(w.lower() in vehicle.transmission.lower() for w in want):
                return False
        elif key == "turbo":
            if vehicle.turbo != want:
                return False
        elif key.startswith("option."):
            name = key.split(".", 1)[1]
            have = getattr(options, name, None)
            if isinstance(want, list):
                if have not in want:
                    return False
            elif have != want:
                return False
    return True


def applicable_parts(vehicle: VehicleProfile, options: Options) -> list[PartType]:
    return [p for p in load_part_types() if _matches(p.applies_if, vehicle, options)]


def query_for(part: PartType, options: Options) -> str:
    """Pick the eBay keyword for this part given the chosen options."""
    for opt_name, mapping in part.option_variants.items():
        val = getattr(options, opt_name, None)
        if val is not None and str(val) in mapping:
            return mapping[str(val)]
    return part.ebay_q
