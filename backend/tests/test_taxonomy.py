from app.models import Options, VehicleProfile
from app.services.taxonomy import applicable_parts, load_part_types, query_for


def test_taxonomy_loads_and_ids_unique():
    parts = load_part_types()
    assert len(parts) >= 90
    ids = [p.id for p in parts]
    assert len(ids) == len(set(ids))


def test_coupe_excludes_rear_doors_and_liftgate(a5_coupe, options):
    ids = {p.id for p in applicable_parts(a5_coupe, options)}
    assert "door_rear" not in ids
    assert "liftgate" not in ids
    assert "decklid" in ids
    assert "quarter_window_regulator" in ids


def test_awd_turbo_auto_parts_present(a5_coupe, options):
    ids = {p.id for p in applicable_parts(a5_coupe, options)}
    assert {"transfer_case", "rear_differential", "driveshaft", "turbocharger", "torque_converter", "tcm"} <= ids
    assert "flywheel_clutch" not in ids


def test_fwd_sedan_drops_driveline(options):
    v = VehicleProfile(vin="X" * 17, year=2016, make="HONDA", model="Accord", body="Sedan", drive="FWD", transmission="Manual")
    ids = {p.id for p in applicable_parts(v, options)}
    assert "transfer_case" not in ids and "rear_differential" not in ids
    assert "door_rear" in ids
    assert "flywheel_clutch" in ids and "torque_converter" not in ids
    assert "turbocharger" not in ids


def test_option_variants_pick_query(a5_coupe):
    parts = {p.id: p for p in load_part_types()}
    assert "xenon" in query_for(parts["headlamp_assembly"], Options(headlights="xenon"))
    assert "led" in query_for(parts["headlamp_assembly"], Options(headlights="led"))
    assert query_for(parts["wheel"], Options(wheel_size=19)).startswith("19 inch")
    assert "mmi" in query_for(parts["infotainment_head_unit"], Options(navigation=True))


def test_sunroof_option_gates_part(a5_coupe):
    with_roof = {p.id for p in applicable_parts(a5_coupe, Options(sunroof=True))}
    without = {p.id for p in applicable_parts(a5_coupe, Options(sunroof=False))}
    assert "sunroof_assembly" in with_roof and "sunroof_assembly" not in without
