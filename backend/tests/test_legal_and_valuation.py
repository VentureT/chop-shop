from app.config import Settings
from app.models import CompareRequest, Options
from app.services import legal
from app.services.taxonomy import load_part_types
from app.services.valuation import Valuator, compare

PARTS = {p.id: p for p in load_part_types()}


def test_airbags_blocked(a5_coupe):
    flags, sellable, _ = legal.part_flags(PARTS["airbag_driver"], a5_coupe, "TX")
    assert not sellable
    assert any(f.code == "AIRBAG_UNSELLABLE" and f.severity == "block" for f in flags)


def test_component_protection_only_for_vag_2011_plus(a5_coupe):
    flags, sellable, haircut = legal.part_flags(PARTS["infotainment_head_unit"], a5_coupe, "TX")
    assert sellable and haircut == 0.6
    assert any(f.code == "COMPONENT_PROTECTION" for f in flags)
    honda = a5_coupe.model_copy(update={"make": "HONDA"})
    flags, _, haircut = legal.part_flags(PARTS["infotainment_head_unit"], honda, "TX")
    assert haircut is None and not flags


def test_cat_converter_texas_vs_generic(a5_coupe):
    tx, _, _ = legal.part_flags(PARTS["catalytic_converter"], a5_coupe, "TX")
    ca, _, _ = legal.part_flags(PARTS["catalytic_converter"], a5_coupe, "CA")
    assert "SB 224" in tx[0].detail
    assert "SB 224" not in ca[0].detail


def test_vehicle_flags_texas(a5_coupe):
    codes = [f.code for f in legal.vehicle_flags(a5_coupe, "TX")]
    assert codes[:2] == ["TITLE_REQUIRED", "LICENSE_IF_COMMERCIAL"]


def test_valuation_without_credentials_uses_reference(tmp_path, a5_coupe):
    settings = Settings(ebay_client_id="", ebay_client_secret="", cache_path=str(tmp_path / "c.db"), state="TX")
    v = Valuator(settings)
    res = v.valuate(a5_coupe, Options(), None)
    assert res.ebay_live is False
    assert res.totals["parts_considered"] > 80
    engine = next(p for p in res.parts if p.part.id == "engine_assembly")
    assert engine.price_status == "no_credentials"
    assert engine.asking_median == 2500
    assert engine.est_sold_each == 1875.0
    airbag = next(p for p in res.parts if p.part.id == "airbag_driver")
    assert airbag.est_net_total == 0 and not airbag.sellable
    # sorted by net value, descending
    nets = [p.est_net_total for p in res.parts]
    assert nets == sorted(nets, reverse=True)
    assert res.totals["est_net"] > 0


def test_compare_picks_winner(tmp_path, a5_coupe):
    settings = Settings(ebay_client_id="", ebay_client_secret="", cache_path=str(tmp_path / "c.db"))
    res = Valuator(settings).valuate(a5_coupe, Options(), None)
    out = compare(CompareRequest(instant_offer=6000, private_party=11000, valuation=res, hourly_value=25))
    assert out.winner in {"instant_offer", "private_party", "part_out"}
    assert out.part_out_net_after_labor < out.part_out_est_net
    assert out.total_hours > 20
