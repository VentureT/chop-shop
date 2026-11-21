"""NHTSA vPIC VIN decode (free, public, no key)."""
from __future__ import annotations

import httpx

from app.models import VehicleProfile

VPIC_URL = "https://vpic.nhtsa.dot.gov/api/vehicles/DecodeVinValuesExtended/{vin}?format=json"

_BODY_MAP = {
    "coupe": "Coupe",
    "convertible": "Convertible",
    "cabriolet": "Convertible",
    "sedan": "Sedan",
    "hatchback": "Hatchback",
    "wagon": "Wagon",
    "sport utility": "SUV",
    "suv": "SUV",
    "crossover": "SUV",
    "pickup": "Pickup",
    "van": "Van",
}


def _body(raw: str) -> str:
    low = (raw or "").lower()
    for key, val in _BODY_MAP.items():
        if key in low:
            return val
    return "Unknown"


def _drive(raw: str) -> str:
    low = (raw or "").lower()
    if "awd" in low or "all-wheel" in low:
        return "AWD"
    if "4wd" in low or "4x4" in low or "four-wheel" in low:
        return "4WD"
    if "fwd" in low or "front" in low:
        return "FWD"
    if "rwd" in low or "rear" in low:
        return "RWD"
    return ""


def _int(v: str) -> int | None:
    try:
        return int(float(v))
    except (TypeError, ValueError):
        return None


def _float(v: str) -> float | None:
    try:
        return round(float(v), 1)
    except (TypeError, ValueError):
        return None


def profile_from_vpic(vin: str, r: dict) -> VehicleProfile:
    warnings: list[str] = []
    err = (r.get("ErrorCode") or "0").split(",")[0].strip()
    if err not in ("0", ""):
        warnings.append(r.get("ErrorText") or f"vPIC error code {err}")
    year = _int(r.get("ModelYear") or "")
    if not year or not r.get("Make"):
        raise ValueError("VIN did not decode to a year/make. Check the VIN and try again.")
    turbo = "turbo" in (r.get("Turbo") or "").lower() or "turbo" in (r.get("EngineModel") or "").lower()
    return VehicleProfile(
        vin=vin.upper(),
        year=year,
        make=r.get("Make") or "",
        model=r.get("Model") or "",
        trim=r.get("Trim") or "",
        series=r.get("Series") or "",
        body=_body(r.get("BodyClass") or ""),
        doors=_int(r.get("Doors") or ""),
        drive=_drive(r.get("DriveType") or ""),
        engine_cyl=_int(r.get("EngineCylinders") or ""),
        displacement_l=_float(r.get("DisplacementL") or ""),
        fuel=r.get("FuelTypePrimary") or "",
        transmission=r.get("TransmissionStyle") or "",
        turbo=turbo,
        plant_country=r.get("PlantCountry") or "",
        decode_warnings=warnings,
    )


def decode_vin(vin: str) -> VehicleProfile:
    vin = vin.strip().upper()
    if len(vin) != 17:
        raise ValueError("VIN must be 17 characters.")
    with httpx.Client(timeout=20) as client:
        resp = client.get(VPIC_URL.format(vin=vin))
        resp.raise_for_status()
        results = resp.json().get("Results") or []
    if not results:
        raise ValueError("vPIC returned no results.")
    return profile_from_vpic(vin, results[0])
