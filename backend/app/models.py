"""Pydantic models shared by routers and services."""
from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

Body = Literal["Coupe", "Convertible", "Sedan", "Hatchback", "Wagon", "SUV", "Pickup", "Van", "Unknown"]


class VehicleProfile(BaseModel):
    vin: str
    year: int
    make: str
    model: str
    trim: str = ""
    series: str = ""
    body: Body = "Unknown"
    doors: int | None = None
    drive: str = ""  # AWD / FWD / RWD / 4WD
    engine_cyl: int | None = None
    displacement_l: float | None = None
    fuel: str = ""
    transmission: str = ""  # Automatic / Manual
    turbo: bool = False
    plant_country: str = ""
    decode_warnings: list[str] = Field(default_factory=list)

    @property
    def search_terms(self) -> str:
        return f"{self.year} {self.make.title()} {self.model}"


class Options(BaseModel):
    """Factory options a VIN can't reveal. Defaults are conservative."""

    headlights: Literal["halogen", "xenon", "led"] = "xenon"
    wheel_size: Literal[16, 17, 18, 19, 20, 21] = 18
    audio: Literal["standard", "premium"] = "standard"
    navigation: bool = True
    seats: Literal["standard", "sport"] = "standard"
    sunroof: bool = True
    sport_package: bool = False
    convertible_top: bool = False


class Flag(BaseModel):
    code: str
    severity: Literal["info", "warn", "block"]
    title: str
    detail: str
    source: str = ""


class PartType(BaseModel):
    id: str
    hollander: str = ""
    name: str
    group: str
    qty: int = 1
    ebay_q: str
    size_class: Literal["S", "M", "L", "XL"] = "M"
    removal_hours: float = 1.0
    reference_asking: float = 0.0  # rough fallback when eBay is unavailable
    applies_if: dict = Field(default_factory=dict)
    option_variants: dict = Field(default_factory=dict)
    flags: list[str] = Field(default_factory=list)
    haircut_override: float | None = None
    # eBay search tuning (see services/pricing.clean_listings):
    ebay_category_id: str | None = None  # leaf category override; else resolved via Taxonomy API
    title_any: list[str] = Field(default_factory=list)  # listing title must contain one of these
    title_none: list[str] = Field(default_factory=list)  # ...and none of these
    title_allow: list[str] = Field(default_factory=list)  # global noise words to permit for this part


class Listing(BaseModel):
    item_id: str
    title: str
    price: float
    condition: str = ""
    condition_id: str = ""
    buying_options: list[str] = Field(default_factory=list)
    compatibility_match: str = ""
    url: str = ""
    shipping: float | None = None


class PartValuation(BaseModel):
    part: PartType
    query: str
    price_status: Literal["live", "cached", "reference", "no_results", "error", "no_credentials"]
    sample_size: int = 0
    exact_share: float = 0.0
    asking_median: float = 0.0
    asking_low: float = 0.0
    asking_high: float = 0.0
    est_sold_each: float = 0.0
    est_net_each: float = 0.0
    est_net_total: float = 0.0
    sellable: bool = True
    confidence: Literal["none", "low", "medium", "high"] = "none"
    confidence_reason: str = ""
    flags: list[Flag] = Field(default_factory=list)
    sample_listings: list[Listing] = Field(default_factory=list)
    note: str = ""


class ValuateRequest(BaseModel):
    vin: str
    options: Options = Field(default_factory=Options)
    zip: str | None = None
    max_parts: int | None = None


class ValuateResponse(BaseModel):
    vehicle: VehicleProfile
    options: Options
    parts: list[PartValuation]
    totals: dict
    vehicle_flags: list[Flag]
    ebay_live: bool


class CompareRequest(BaseModel):
    instant_offer: float = 0.0
    private_party: float = 0.0
    valuation: ValuateResponse
    sell_through: float = 0.70
    hourly_value: float = 25.0
    shell_scrap: float = 400.0


class CompareResponse(BaseModel):
    instant_offer: float
    private_party: float
    part_out_gross_asking: float
    part_out_est_sold: float
    part_out_est_net: float
    part_out_net_after_labor: float
    total_hours: float
    months_estimate: str
    sell_through: float
    shell_scrap: float
    winner: str
    notes: list[str]
