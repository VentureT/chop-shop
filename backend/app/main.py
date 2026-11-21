"""Chop Shop API — FastAPI application entrypoint."""
from __future__ import annotations

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import get_settings
from app.routers import decode, valuate

settings = get_settings()

app = FastAPI(
    title=settings.app_name,
    description="VIN in, ranked list of sellable used parts with estimated resale value out.",
    version="0.1.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(decode.router, prefix="/api")
app.include_router(valuate.router, prefix="/api")


@app.get("/health", tags=["meta"])
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/", tags=["meta"])
def root() -> dict[str, object]:
    return {
        "name": settings.app_name,
        "links": {
            "health": "/health",
            "docs": "/docs",
            "decode": "/api/decode/{vin}",
            "parts": "/api/parts",
            "valuate": "POST /api/valuate",
            "compare": "POST /api/compare",
            "status": "/api/status",
        },
    }
