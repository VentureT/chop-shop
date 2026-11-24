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


# ---------- clean_listings ----------
from app.models import PartType, VehicleProfile


def _part(**kw):
    base = dict(id="front_seat", name="Front seat", group="Interior", qty=2, ebay_q="front seat",
                reference_asking=300, title_any=["seat"], title_none=["belt", "track"])
    base.update(kw)
    return PartType(**base)


def _veh(body="Coupe"):
    return VehicleProfile(vin="WAUCFAFR5FA000001", year=2015, make="AUDI", model="A5", body=body)


def test_clean_drops_accessories_and_requires_part_noun():
    part = _part()
    listings = [
        _l(498.65, "EXACT", "a"), _l(23.80, "EXACT", "b"), _l(47.49, "EXACT", "c"), _l(42.00, "EXACT", "d"), _l(135.0, "EXACT", "e"),
    ]
    listings[0].title = "2014-2016 Audi A5 Passenger Side Right Front Seat Electric Leather"
    listings[1].title = "2015-2020 AUDI A3 - Front SEAT Lumbar Assembly"
    listings[2].title = "2013-2015 AUDI RS5 - Front Right Outer SEAT Switch TRIM / Panel"
    listings[3].title = "2011-2015 Audi A5 Rear Center Console Storage Pocket Tray"
    listings[4].title = "2008-2017 Audi A5 Front Left Seat Track Rail"
    kept = pricing.clean_listings(listings, part, "front seat", _veh())
    assert [l.item_id for l in kept] == ["a"]


def test_clean_side_and_body_conflicts():
    part = _part()
    rear = _l(300, "EXACT", "r"); rear.title = "2015 Audi A5 Rear Seat Leather"
    both = _l(300, "EXACT", "b"); both.title = "2015 Audi A5 Front Rear Seat Leather"
    cab = _l(300, "EXACT", "c"); cab.title = "2015 Audi A5 Convertible Front Seat"
    coupe = _l(300, "EXACT", "d"); coupe.title = "2015 Audi A5 Coupe Cabrio Front Seat"
    kept = pricing.clean_listings([rear, both, cab, coupe], part, "front seat", _veh("Coupe"))
    assert [l.item_id for l in kept] == ["b", "d"]


def test_clean_splits_pairs_dedupes_and_floors():
    part = PartType(id="headlamp_assembly", name="Headlamp assembly", group="Front end", qty=2,
                    ebay_q="headlight assembly", reference_asking=450, title_any=["headlight", "headlamp"])
    pair = _l(2183.65, "EXACT", "p"); pair.title = "Audi A5 2011-2018 PAIR Headlight Used OEM"
    dup = _l(2183.65, "EXACT", "p2"); dup.title = "Audi A5 2011-2018 PAIR Headlight Used OEM"
    ballast = _l(19.99, "EXACT", "x"); ballast.title = "FOR Audi Xenon Ballast HID Module Control Unit"
    cheap = _l(14.92, "EXACT", "y"); cheap.title = "OEM Audi A5 Headlight Low Beam"
    single = _l(349.5, "EXACT", "s"); single.title = "2013-2017 Audi A5 Right Xenon Headlight OEM"
    kept = pricing.clean_listings([pair, dup, ballast, cheap, single], part, "xenon hid headlight assembly", _veh())
    assert [(l.item_id, l.price) for l in kept] == [("p", 1091.83), ("s", 349.5)]


def test_effective_exclusions_keep_the_parts_own_words():
    pump = PartType(id="water_pump_thermostat", name="Water pump / thermostat housing", group="Engine",
                    ebay_q="water pump thermostat", title_any=["water pump"])
    ex = pricing.effective_exclusions(pump, "water pump thermostat")
    assert "pump" not in ex and "housing" not in ex and "bracket" in ex
    mats = PartType(id="floor_mats", name="Floor mats (set)", group="Interior", ebay_q="floor mats oem", title_allow=["liner"])
    assert "liner" not in pricing.effective_exclusions(mats, "floor mats oem")


def test_clean_rejects_other_vehicles_and_junk_conditions():
    part = PartType(id="turbocharger", name="Turbocharger", group="Engine", ebay_q="turbocharger turbo",
                    reference_asking=300, title_any=["turbo"])
    ok = _l(184.79, "EXACT", "ok"); ok.title = "2013-2016 AUDI A4 A5 2.0L - Turbo / Turbocharger 06H145702R"
    ford = _l(92.99, "EXACT", "ford"); ford.title = "2013-2016 Ford Escape 1.6L Turbo Turbocharger Assembly OEM"
    a4 = _l(150, "EXACT", "a4"); a4.title = "2013-2016 Audi A4 B8 2.0T Turbo Turbocharger OEM"
    old = _l(150, "EXACT", "old"); old.title = "2010-2012 audi a5 quattro 2.0l turbo turbocharger oem"
    near = _l(150, "EXACT", "near"); near.title = "2014 Audi A5 Turbo Turbocharger OEM 90k"
    far = _l(150, "EXACT", "far"); far.title = "2009 Audi A5 Turbo Turbocharger OEM"
    run = _l(150, "EXACT", "run"); run.title = "13 14 15 16 17 AUDI A5 S5 TURBO TURBOCHARGER"
    broken = _l(150, "EXACT", "broken"); broken.condition = "For parts or not working"; broken.title = "2015 Audi A5 Turbo Turbocharger"
    kept = pricing.clean_listings([ok, ford, a4, old, near, far, run, broken], part, "turbocharger turbo", _veh())
    assert [l.item_id for l in kept] == ["ok", "near", "run"]


def test_mentioned_years_and_model_family():
    assert pricing.mentioned_years("2013-2017 Audi A5") == set(range(2013, 2018))
    assert pricing.mentioned_years("13-17 Audi A5 8T0941043E") == set(range(2013, 2018))
    assert pricing.mentioned_years("2013-17 Audi A5") == set(range(2013, 2018))
    assert pricing.mentioned_years("Audi A5 S5 Headlight 8T0 941 043") == set()
    assert pricing.model_family(_veh()) >= {"a5", "s5", "rs5"}


def test_trim_names_do_not_trip_accessory_words():
    part = PartType(id="bumper_cover_front", name="Front bumper cover", group="Front end", ebay_q="front bumper cover",
                    reference_asking=350, title_any=["bumper"], title_allow=["cover"])
    sline = _l(249.95, "EXACT", "s"); sline.title = "13-17 Audi A5 B8.5 S-Line Front Bumper Cover DAYTONA GREY"
    hose = _l(20, "EXACT", "h"); hose.title = "13-17 Audi A5 Front Bumper Washer Line Hose"
    kept = pricing.clean_listings([sline, hose], part, "front bumper cover", _veh())
    assert [l.item_id for l in kept] == ["s"]


def test_remanufactured_dropped_unless_allowed():
    batt = PartType(id="battery", name="Battery", group="Electrical", ebay_q="agm battery", reference_asking=60, title_any=["battery"])
    reman = _l(206, "EXACT", "r"); reman.title = "For 2010-2025 Audi A5 Quattro Battery Deka"; reman.condition = "Remanufactured"
    assert pricing.clean_listings([reman], batt, "agm battery", _veh()) == []
    wheel = PartType(id="wheel", name="Wheel (rim)", group="Wheels", qty=4, ebay_q="wheel rim", reference_asking=180,
                     title_any=["wheel", "rim"], title_allow=["remanufactured"])
    rw = _l(304, "EXACT", "w"); rw.title = "Audi A5 2015 18\" OEM Wheel Rim 8T0601025BM"; rw.condition = "Remanufactured"
    assert [l.item_id for l in pricing.clean_listings([rw], wheel, "18 inch wheel rim", _veh())] == ["w"]
