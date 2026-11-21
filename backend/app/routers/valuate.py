"""Valuation, taxonomy and comparison endpoints."""
from __future__ import annotations

from functools import lru_cache

import httpx
from fastapi import APIRouter, HTTPException

from app.config import get_settings
from app.models import CompareRequest, CompareResponse, PartType, ValuateRequest, ValuateResponse
from app.services.taxonomy import load_part_types
from app.services.valuation import Valuator, compare
from app.services.vpic import decode_vin

router = APIRouter(tags=["valuation"])


@lru_cache
def get_valuator() -> Valuator:
    return Valuator(get_settings())


@router.get("/parts", response_model=list[PartType])
def parts() -> list[PartType]:
    """The full curated taxonomy (before vehicle filtering)."""
    return load_part_types()


@router.post("/valuate", response_model=ValuateResponse)
def valuate(req: ValuateRequest) -> ValuateResponse:
    try:
        vehicle = decode_vin(req.vin)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except httpx.HTTPError as exc:
        raise HTTPException(status_code=502, detail=f"vPIC unavailable: {exc}") from exc
    return get_valuator().valuate(vehicle, req.options, req.zip, req.max_parts)


@router.post("/compare", response_model=CompareResponse)
def compare_endpoint(req: CompareRequest) -> CompareResponse:
    return compare(req)


@router.get("/status")
def status() -> dict:
    s = get_settings()
    return {"ebay_configured": s.ebay_configured, "ebay_env": s.ebay_env, "state": s.state}
