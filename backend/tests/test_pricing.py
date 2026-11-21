from app.models import Listing
from app.services import pricing


def _l(price, match="", item="x"):
    return Listing(item_id=item, title="t", price=price, compatibility_match=match)


def test_trim_outliers_drops_extremes():
    assert pricing.trim_outliers([1, 2, 3, 4, 5, 6, 7, 8, 9, 100]) == [2, 3, 4, 5, 6, 7, 8, 9]
    assert pricing.trim_outliers([5, 1, 3]) == [1, 3, 5]


def test_summarize_prefers_exact_matches():
    listings = [_l(50, "POSSIBLE"), _l(60, "POSSIBLE"), _l(400, "EXACT"), _l(420, "EXACT"), _l(440, "EXACT")]
    s = pricing.summarize(listings)
    assert s["median"] == 420
    assert s["n"] == 3
    assert 0.59 < s["exact_share"] < 0.61


def test_summarize_falls_back_when_few_exact():
    listings = [_l(50), _l(60), _l(70), _l(400, "EXACT")]
    s = pricing.summarize(listings)
    assert s["n"] == 4
    assert s["median"] == 65


def test_est_sold_and_net():
    assert pricing.est_sold(100) == 75.0
    assert pricing.est_sold(100, haircut=0.5) == 50.0
    assert pricing.est_net(100, "S") == round(100 * 0.87 - 12, 2)
    assert pricing.est_net(10, "XL") == 0.0  # never negative


def test_confidence_levels():
    assert pricing.confidence(0, 0, "compat") == "none"
    assert pricing.confidence(3, 1.0, "compat") == "low"
    assert pricing.confidence(6, 0.2, "keyword") == "medium"
    assert pricing.confidence(10, 0.8, "compat") == "high"


def test_explain_confidence():
    assert pricing.explain_confidence(0, 0, "keyword", "no_credentials").startswith("Low: built-in")
    assert pricing.explain_confidence(12, 0.8, "compat", "live").startswith("High: 12 used listings")
    assert "keyword" in pricing.explain_confidence(6, 0.0, "keyword", "live")
    assert pricing.explain_confidence(2, 1.0, "compat", "live") == "Low: only 2 used listings to price from."
