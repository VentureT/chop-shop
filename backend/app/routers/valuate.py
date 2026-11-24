"""Valuation, taxonomy and comparison endpoints."""
from __future__ import annotations

from functools import lru_cache

import httpx
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app.config import get_settings
from app.models import CompareRequest, CompareResponse, PartType, ValuateRequest, ValuateResponse
from app.services.jobs import JobStore
from app.services.taxonomy import applicable_parts, load_part_types
from app.services.valuation import Valuator, compare
from app.services.vpic import decode_vin

router = APIRouter(tags=["valuation"])


@lru_cache
def get_valuator() -> Valuator:
    return Valuator(get_settings())


@lru_cache
def get_jobs() -> JobStore:
    return JobStore()


class ValuationJob(BaseModel):
    job_id: str
    status: str  # running | done | error
    done: int
    total: int
    result: ValuateResponse | None = None
    error: str = ""


def _decode(vin: str):
    try:
        return decode_vin(vin)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except httpx.HTTPError as exc:
        raise HTTPException(status_code=502, detail=f"vPIC unavailable: {exc}") from exc


@router.get("/parts", response_model=list[PartType])
def parts() -> list[PartType]:
    """The full curated taxonomy (before vehicle filtering)."""
    return load_part_types()


@router.post("/valuate", response_model=ValuateResponse)
def valuate(req: ValuateRequest) -> ValuateResponse:
    """Synchronous valuation. Fine for scripts and warm caches; the UI uses the job form."""
    vehicle = _decode(req.vin)
    return get_valuator().valuate(vehicle, req.options, req.zip, req.max_parts)


@router.post("/valuate/start", response_model=ValuationJob)
def valuate_start(req: ValuateRequest) -> ValuationJob:
    """Start a valuation in the background; poll GET /api/valuate/jobs/{job_id}."""
    vehicle = _decode(req.vin)
    parts = applicable_parts(vehicle, req.options)
    total = len(parts[: req.max_parts] if req.max_parts else parts)
    valuator = get_valuator()

    def run(job):
        return valuator.valuate(vehicle, req.options, req.zip, req.max_parts, progress=job.progress)

    job = get_jobs().start(run, total)
    return ValuationJob(job_id=job.id, status=job.status, done=job.done, total=job.total)


@router.get("/valuate/jobs/{job_id}", response_model=ValuationJob)
def valuate_job(job_id: str) -> ValuationJob:
    job = get_jobs().get(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Unknown or expired job")
    return ValuationJob(
        job_id=job.id, status=job.status, done=job.done, total=job.total,
        result=job.result if job.status == "done" else None, error=job.error,
    )


@router.post("/compare", response_model=CompareResponse)
def compare_endpoint(req: CompareRequest) -> CompareResponse:
    return compare(req)


@router.get("/status")
def status() -> dict:
    s = get_settings()
    return {"ebay_configured": s.ebay_configured, "ebay_env": s.ebay_env, "state": s.state}
