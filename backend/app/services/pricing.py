"""Pure pricing math: asking listings -> estimated sold / net."""
from __future__ import annotations

import statistics

from app.models import Listing

EBAY_FEE_RATE = 0.13  # final value fee + payment processing, Parts & Accessories, approx.
ASKING_TO_SOLD = 0.75  # realized price vs. asking median; tune per part class

# Estimated outbound shipping you eat or discount for, by size class.
SHIPPING_BY_SIZE = {"S": 12.0, "M": 30.0, "L": 90.0, "XL": 250.0}


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
