"""Pure pricing math: raw eBay listings -> cleaned sample -> estimated sold / net.

eBay's compatibility match is per listing, so a search for "front seat" fitting a
2015 Audi A5 returns the seat's lumbar motor, switch trim and headrest as EXACT
matches next to the actual seat. `clean_listings` removes that noise by title
before any statistics are taken.
"""
from __future__ import annotations

import re
import statistics

from app.models import Listing, PartType, VehicleProfile

EBAY_FEE_RATE = 0.13  # final value fee + payment processing, Parts & Accessories, approx.
ASKING_TO_SOLD = 0.75  # realized price vs. asking median; tune per part class

# Estimated outbound shipping you eat or discount for, by size class.
SHIPPING_BY_SIZE = {"S": 12.0, "M": 30.0, "L": 90.0, "XL": 250.0}

# Listings below this fraction of the part's reference price are accessories or junk.
PRICE_FLOOR_FRACTION = 0.10

# Words that mark a listing as an accessory, sub-component, service or broken item
# rather than the part itself. A word is ignored for a part whose own name, query,
# title_any or title_allow contains it ("water pump" keeps "pump").
GLOBAL_EXCLUDE = [
    "bracket", "cover", "cap", "trim", "molding", "moulding", "bulb", "gasket", "seal", "bolt",
    "screw", "nut", "clip", "sticker", "decal", "emblem", "badge", "repair", "service", "harness",
    "connector", "pigtail", "hose", "line", "pipe", "sensor", "switch", "relay", "fuse", "lumbar",
    "headrest", "cushion", "actuator", "lens", "glass", "motor", "ballast", "igniter", "module",
    "control unit", "pump", "kit", "mount", "grommet", "shim", "retainer", "cable", "wire",
    "wiring", "filter", "belt", "pulley", "tensioner", "pad", "liner", "guard", "shield", "insert",
    "spacer", "adapter", "bushing", "boot", "strap", "hinge", "latch", "handle", "knob", "button",
    "bezel", "sill", "plate", "nozzle", "pan", "lock", "speaker", "airbag", "turn signal",
    "indicator", "adjuster", "tray", "pocket", "solenoid", "valve", "o ring", "oring", "stud",
    "rivet", "fastener", "hardware", "grille", "grill", "tow hook", "reflector", "socket",
    "weatherstrip", "antenna", "camera", "mirror", "wiper", "clamp", "hanger", "diagram", "manual",
    "tool", "lid", "housing", "loom", "jack", "rotor", "cooler", "oil", "support", "foam",
    "insulation", "core", "for parts", "parts only", "not working", "broken", "damaged", "cracked",
    "as is", "universal", "aftermarket", "android", "carplay", "tow", "towing", "tow eye",
]

# Other manufacturers. A title naming one of these and not the vehicle's make is a
# different car, whatever the seller's fitment list says.
OTHER_MAKES = [
    "ford", "chevrolet", "chevy", "gmc", "dodge", "chrysler", "jeep", "toyota", "lexus", "honda",
    "acura", "nissan", "infiniti", "mazda", "subaru", "mitsubishi", "hyundai", "kia", "volkswagen",
    "vw", "bmw", "mercedes", "benz", "porsche", "volvo", "jaguar", "land rover", "range rover",
    "tesla", "buick", "cadillac", "lincoln", "fiat", "alfa romeo", "saab", "scion", "suzuki", "isuzu",
    "pontiac", "saturn", "mercury", "hummer", "bentley", "maserati", "ferrari", "lamborghini",
    "skoda", "audi", "mini cooper",
]

# Tokens that look like a model designation (a5, q7, s4, rs5, x5, e46, tt, r8) ...
_MODEL_TOKEN_RE = re.compile(r"^(?:[a-z]{1,2}\d{1,2}[a-z]?|tt)$")
# ... except chassis codes (b8, c7, w204, f30), engine layouts (v6, l4, i4) and bulbs (d3s, h7).
_NOT_MODEL_RE = re.compile(r"^(?:[bcdefw]\d{1,2}|[vli]\d|[dh]\d[a-z]?)$")
_YEAR4 = r"(?:19|20)\d\d"

# Body-style words. A listing that names a different body style and not the
# vehicle's own is for a different variant (coupe vs. cabriolet doors, seats, glass).
BODY_WORDS = {
    "Coupe": ["coupe"],
    "Convertible": ["convertible", "cabriolet", "cabrio", "roadster", "spyder", "spider"],
    "Sedan": ["sedan", "saloon"],
    "Hatchback": ["hatchback", "sportback", "hatch"],
    "Wagon": ["wagon", "avant", "allroad", "estate", "touring"],
    "SUV": ["suv"],
}

_PAIR_RE = re.compile(r"\b(pair|set of 2|set of two|2 pcs|2pcs|2x|x2|both sides|\(2\))\b")
_SET4_RE = re.compile(r"\b(set of 4|set of four|4 pcs|4pcs|4x|x4|\(4\)|full set|complete set)\b")


# Trim-level names that would otherwise trip accessory words ("S-Line" -> "line").
_TRIM_PHRASES = {" s line ": " sline ", " r line ": " rline ", " f sport ": " fsport ", " m sport ": " msport "}


def normalize(text: str) -> str:
    """Lowercase, punctuation to spaces, single-spaced, padded for whole-word matching."""
    out = " " + re.sub(r"[^a-z0-9&]+", " ", text.lower()).strip() + " "
    for phrase, joined in _TRIM_PHRASES.items():
        out = out.replace(phrase, joined)
    return out


def _has(norm_title: str, phrase: str) -> bool:
    return normalize(phrase) in norm_title


def _tokens(text: str) -> set[str]:
    out: set[str] = set()
    for t in normalize(text).split():
        out.add(t)
        if len(t) > 3 and t.endswith("s"):
            out.add(t[:-1])
    return out


def effective_exclusions(part: PartType, query: str) -> list[str]:
    """Global noise words minus anything this part is actually about, plus its own list."""
    own_text = f"{part.name} {part.ebay_q} {query} {' '.join(part.title_any)} {' '.join(part.title_allow)}"
    own_tokens = _tokens(own_text)
    own_norm = normalize(own_text)
    keep: list[str] = []
    for word in GLOBAL_EXCLUDE:
        if " " in word.strip():
            if normalize(word) in own_norm:
                continue
        elif word in own_tokens or (len(word) > 3 and word + "s" in own_tokens):
            continue
        keep.append(word)
    return keep + list(part.title_none)


def _side_conflict(norm_title: str, query_tokens: set[str]) -> bool:
    for a, b in (("front", "rear"), ("rear", "front"), ("upper", "lower"), ("lower", "upper")):
        if a in query_tokens and b not in query_tokens:
            if _has(norm_title, b) and not _has(norm_title, a):
                return True
    return False


def _make_conflict(norm_title: str, vehicle: VehicleProfile | None) -> bool:
    if vehicle is None or not vehicle.make:
        return False
    own = vehicle.make.lower()
    if _has(norm_title, own):
        return False
    return any(_has(norm_title, m) for m in OTHER_MAKES if m != own)


def model_family(vehicle: VehicleProfile) -> set[str]:
    """Model tokens that mean 'this car': the model, its performance siblings, series/trim."""
    m = vehicle.model.lower().replace(" ", "")
    fam = {m}
    mm = re.match(r"^(a|s|rs|q|sq|rsq)(\d+)$", m)
    if mm:
        n = mm.group(2)
        fam |= {f"a{n}", f"s{n}", f"rs{n}"} if mm.group(1) in ("a", "s", "rs") else {f"q{n}", f"sq{n}", f"rsq{n}"}
    for t in _tokens(f"{vehicle.series} {vehicle.trim}"):
        if _MODEL_TOKEN_RE.match(t):
            fam.add(t)
    return fam


def _model_conflict(norm_title: str, vehicle: VehicleProfile | None) -> bool:
    """True when the title names models and none of them is this car."""
    if vehicle is None or not vehicle.model:
        return False
    mentioned = {t for t in norm_title.split() if _MODEL_TOKEN_RE.match(t) and not _NOT_MODEL_RE.match(t)}
    if not mentioned:
        return False
    return not (mentioned & model_family(vehicle))


def mentioned_years(title: str) -> set[int]:
    """Model years a title claims to fit: ranges (2013-2017, 13-17, 2013-17), runs (13 14 15), singles."""
    t = title.lower()
    years: set[int] = set()
    dash = r"\s*(?:-|–|—|to|thru|through)\s*"
    for a, b in re.findall(rf"\b({_YEAR4}){dash}({_YEAR4})\b", t):
        if int(a) <= int(b):
            years |= set(range(int(a), int(b) + 1))
    for a, b in re.findall(rf"\b({_YEAR4}){dash}(\d\d)\b", t):
        end = int(a[:2] + b)
        if int(a) <= end:
            years |= set(range(int(a), end + 1))
    for a, b in re.findall(r"\b(\d\d)\s*(?:-|–|—)\s*(\d\d)\b", t):
        a2, b2 = int(a), int(b)
        if a2 <= 30 and a2 <= b2 <= 30:
            years |= set(range(2000 + a2, 2000 + b2 + 1))
    for run in re.findall(r"\b(\d\d(?:\s+\d\d){2,})\b", t):
        nums = [int(x) for x in run.split()]
        if all(n <= 30 for n in nums):
            years |= {2000 + n for n in nums}
    for y in re.findall(rf"\b({_YEAR4})\b", t):
        years.add(int(y))
    return years


def _year_conflict(title: str, vehicle: VehicleProfile | None) -> bool:
    """Ranges are strict; a lone year gets +-3 years of slack (same generation)."""
    if vehicle is None or not vehicle.year:
        return False
    years = mentioned_years(title)
    if not years or vehicle.year in years:
        return False
    if len(years) == 1 and abs(next(iter(years)) - vehicle.year) <= 3:
        return False
    return True


def _body_conflict(norm_title: str, vehicle: VehicleProfile | None) -> bool:
    if vehicle is None or vehicle.body not in BODY_WORDS:
        return False
    own = BODY_WORDS[vehicle.body]
    if any(_has(norm_title, w) for w in own):
        return False
    for body, words in BODY_WORDS.items():
        if body != vehicle.body and any(_has(norm_title, w) for w in words):
            return True
    return False


def drop_reason(
    l: Listing, part: PartType, query: str, vehicle: VehicleProfile | None = None,
    exclude: list[str] | None = None, required: list[str] | None = None, qtokens: set[str] | None = None,
) -> str | None:
    """Why a listing is not a comparable for this part, or None if it is."""
    exclude = effective_exclusions(part, query) if exclude is None else exclude
    required = [normalize(a) for a in part.title_any] if required is None else required
    qtokens = _tokens(query) if qtokens is None else qtokens
    if l.price <= 0:
        return "no price"
    cond = l.condition.lower()
    if l.condition_id == "7000" or "for parts" in cond or "not working" in cond:
        return "for parts / not working"
    if ("remanufactured" in cond or "refurbished" in cond or "rebuilt" in cond) and not any(
        w in ("remanufactured", "refurbished", "rebuilt") for w in part.title_allow
    ):
        return "remanufactured / refurbished, not used"
    nt = normalize(l.title)
    if required and not any(r in nt for r in required):
        return f"title lacks {'/'.join(part.title_any[:3])}"
    hit = next((w for w in exclude if _has(nt, w)), None)
    if hit:
        return f"accessory word '{hit}'"
    if _side_conflict(nt, qtokens):
        return "wrong side/position"
    if _body_conflict(nt, vehicle):
        return "different body style"
    if _make_conflict(nt, vehicle):
        return "different make"
    if _model_conflict(nt, vehicle):
        return "different model"
    if _year_conflict(l.title, vehicle):
        return "year range excludes this car"
    return None


def unit_price(l: Listing, part: PartType) -> float:
    """Per-unit price: pairs and sets of 4 are split for multi-quantity parts."""
    nt = normalize(l.title)
    if part.qty >= 4 and _SET4_RE.search(nt):
        return round(l.price / 4, 2)
    if part.qty >= 2 and _PAIR_RE.search(nt):
        return round(l.price / 2, 2)
    return l.price


def clean_listings(
    listings: list[Listing], part: PartType, query: str, vehicle: VehicleProfile | None = None
) -> list[Listing]:
    """Drop accessories, wrong side/body/make/model/year, duplicates and junk prices; split pairs."""
    exclude = effective_exclusions(part, query)
    required = [normalize(a) for a in part.title_any]
    qtokens = _tokens(query)
    floor = part.reference_asking * PRICE_FLOOR_FRACTION if part.reference_asking > 0 else 0.0
    seen: set[tuple[str, float]] = set()
    out: list[Listing] = []
    for l in listings:
        key = (normalize(l.title), l.price)
        if key in seen:
            continue
        seen.add(key)
        if drop_reason(l, part, query, vehicle, exclude, required, qtokens):
            continue
        price = unit_price(l, part)
        if price < floor:
            continue
        out.append(l if price == l.price else l.model_copy(update={"price": price}))
    return out


def trim_outliers(prices: list[float], frac: float = 0.10) -> list[float]:
    if len(prices) < 5:
        return sorted(prices)
    s = sorted(prices)
    k = int(len(s) * frac)
    return s[k : len(s) - k] if k else s


def select_listings(listings: list[Listing]) -> tuple[list[Listing], float]:
    """Prefer EXACT compatibility matches; return (chosen, exact_share)."""
    if not listings:
        return [], 0.0
    exact = [l for l in listings if l.compatibility_match == "EXACT"]
    share = len(exact) / len(listings)
    if len(exact) >= 3:
        return exact, share
    return listings, share


def summarize(listings: list[Listing]) -> dict:
    chosen, exact_share = select_listings(listings)
    prices = trim_outliers([l.price for l in chosen if l.price > 0])
    if not prices:
        return {"n": 0, "exact_share": exact_share, "median": 0.0, "low": 0.0, "high": 0.0}
    return {
        "n": len(prices),
        "exact_share": exact_share,
        "median": round(statistics.median(prices), 2),
        "low": round(prices[0], 2),
        "high": round(prices[-1], 2),
    }


def est_sold(asking_median: float, haircut: float | None = None) -> float:
    return round(asking_median * (haircut if haircut is not None else ASKING_TO_SOLD), 2)


def est_net(sold_each: float, size_class: str) -> float:
    net = sold_each * (1 - EBAY_FEE_RATE) - SHIPPING_BY_SIZE.get(size_class, 30.0)
    return round(max(net, 0.0), 2)


def confidence(n: int, exact_share: float, mode: str) -> str:
    if n == 0:
        return "none"
    if mode == "compat" and n >= 8 and exact_share >= 0.5:
        return "high"
    if n >= 5:
        return "medium"
    return "low"


def explain_confidence(n: int, exact_share: float, mode: str, status: str) -> str:
    """Plain-language reason for the confidence level shown in the UI."""
    if status in ("no_credentials", "reference", "no_results", "error"):
        return (
            "Low: built-in reference estimate, not market data. Connect eBay for live listings."
            if status != "error"
            else "Low: the eBay lookup failed, so this is the built-in reference estimate."
        )
    exact_pct = int(round(exact_share * 100))
    if n == 0:
        return "None: no used listings found."
    if mode == "compat" and n >= 8 and exact_share >= 0.5:
        return f"High: {n} used listings after trimming outliers, and {exact_pct}% are exact fitment matches for this year, make and model."
    if n >= 5:
        why = "fitment was matched by keyword, not eBay's compatibility data" if mode != "compat" else f"only {exact_pct}% are exact fitment matches"
        return f"Medium: {n} used listings, but {why}."
    return f"Low: only {n} used listing{'s' if n != 1 else ''} to price from."
