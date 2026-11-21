"""VIN decode endpoint."""
from __future__ import annotations

import httpx
from fastapi import APIRouter, HTTPException

from app.models import VehicleProfile
from app.services.vpic import decode_vin

router = APIRouter(tags=["decode"])


@router.get("/decode/{vin}", response_model=VehicleProfile)
def decode(vin: str) -> VehicleProfile:
    try:
        return decode_vin(vin)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except httpx.HTTPError as exc:
        raise HTTPException(status_code=502, detail=f"vPIC unavailable: {exc}") from exc
