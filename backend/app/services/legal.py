"""Legal and practical flags. Pure rules; Texas-specific where noted."""
from __future__ import annotations

from app.models import Flag, PartType, VehicleProfile

AIRBAG_BAN = Flag(
    code="AIRBAG_UNSELLABLE",
    severity="block",
    title="Airbags cannot be sold on major marketplaces",
    detail=(
        "eBay prohibits all airbags and inflators (new, used, deployed, rebuilt) effective 2026-09-24. "
        "Amazon, Facebook Marketplace, Alibaba and Temu already prohibit them. Treat as $0."
    ),
    source="eBay Vehicles, parts & accessories policy; eBay announcement Sept 2026",
)

SAFETY_RESTRAINT = Flag(
    code="SAFETY_PART_LOW_DEMAND",
    severity="warn",
    title="Safety restraint part: thin resale market",
    detail="Pretensioner seat belts carry liability concerns; many buyers and platforms avoid used units.",
)

COMPONENT_PROTECTION = Flag(
    code="COMPONENT_PROTECTION",
    severity="warn",
    title="Audi/VW component protection (VIN-locked module)",
    detail=(
        "2011+ Audi MMI units, displays, clusters, ECUs and gateways are locked to the donor VIN. "
        "The buyer needs dealer coding to use it, which depresses used prices. An extra haircut is applied."
    ),
)

CAT_TX = Flag(
    code="CAT_CONVERTER_RESTRICTED",
    severity="warn",
    title="Catalytic converter: Texas seller documentation rules",
    detail=(
        "Texas SB 224 (eff. 2023-07-01) requires sellers to provide identifying information to a metal "
        "recycling entity, which must record and mark each unit. Sell only to a licensed buyer with paperwork; "
        "eBay also has a dedicated converter policy."
    ),
    source="Texas DPS Metals Program; Tex. SB 224 (88R)",
)

CAT_GENERIC = Flag(
    code="CAT_CONVERTER_RESTRICTED",
    severity="warn",
    title="Catalytic converter: documentation usually required",
    detail="Most states restrict sale of detached converters to licensed buyers with proof of ownership.",
)

HAZMAT = Flag(
    code="HAZMAT",
    severity="info",
    title="Refrigerant and fluids need proper recovery",
    detail="A/C refrigerant must be recovered by an EPA 609 certified tech; oil, coolant, fuel and brake fluid need proper disposal.",
)

FUEL_TANK = Flag(
    code="FUEL_TANK_SHIPPING",
    severity="warn",
    title="Fuel-contaminated part: shipping restrictions",
    detail="Carriers restrict parts that held fuel; local sale only in practice.",
)

TITLE_TX = Flag(
    code="TITLE_REQUIRED",
    severity="warn",
    title="Texas: convert the title before dismantling",
    detail=(
        "Tex. Transp. Code 501.09111 lets the holder of a salvage or nonrepairable title dismantle the vehicle and "
        "sell its parts. Apply with form VTR-441 ($8). TxDMV states it will not issue a salvage title for an "
        "undamaged vehicle, so confirm the nonrepairable-title path with TxDMV before you start. Use form VTR-63 "
        "(Component Parts Bill of Sale) for major components."
    ),
    source="Tex. Transp. Code 501.09111; TxDMV VTR-441, VTR-63",
)

LICENSE_TX = Flag(
    code="LICENSE_IF_COMMERCIAL",
    severity="info",
    title="Texas: a parts business needs a TDLR license",
    detail=(
        "Operating a used automotive parts recycling business requires a TDLR Used Automotive Parts Recycler "
        "license (Tex. Occ. Code ch. 2309). A one-time sale of your own car's parts is generally outside that, "
        "but repeated part-outs are not."
    ),
    source="Tex. Occ. Code ch. 2309; 16 TAC ch. 87",
)

TITLE_GENERIC = Flag(
    code="TITLE_REQUIRED",
    severity="warn",
    title="Title must usually be converted before dismantling",
    detail="Most states require a salvage, nonrepairable or junk title before a vehicle is parted out. Check your DMV.",
)

SHELL = Flag(
    code="SHELL_DISPOSAL",
    severity="info",
    title="Plan for the shell",
    detail="A stripped unibody scraps for roughly $300-500 and requires handing the title to a licensed recycler.",
)

AUDI_VW_MAKES = {"AUDI", "VOLKSWAGEN", "PORSCHE", "BENTLEY", "LAMBORGHINI"}


def part_flags(part: PartType, vehicle: VehicleProfile, state: str) -> tuple[list[Flag], bool, float | None]:
    """Return (flags, sellable, haircut_override) for a part on this vehicle."""
    flags: list[Flag] = []
    sellable = True
    haircut: float | None = part.haircut_override
    tags = set(part.flags)

    if "airbag" in tags:
        flags.append(AIRBAG_BAN)
        sellable = False
    if "restraint" in tags:
        flags.append(SAFETY_RESTRAINT)
        haircut = min(haircut or 1.0, 0.5)
    if "vin_locked" in tags and vehicle.make.upper() in AUDI_VW_MAKES and vehicle.year >= 2011:
        flags.append(COMPONENT_PROTECTION)
        haircut = min(haircut or 1.0, 0.6)
    if "catalytic" in tags:
        flags.append(CAT_TX if state.upper() == "TX" else CAT_GENERIC)
    if "refrigerant" in tags:
        flags.append(HAZMAT)
    if "fuel" in tags:
        flags.append(FUEL_TANK)
    return flags, sellable, haircut


def vehicle_flags(vehicle: VehicleProfile, state: str) -> list[Flag]:
    if state.upper() == "TX":
        return [TITLE_TX, LICENSE_TX, HAZMAT, SHELL]
    return [TITLE_GENERIC, HAZMAT, SHELL]
