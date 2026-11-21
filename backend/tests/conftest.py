import pytest

from app.models import Options, VehicleProfile


@pytest.fixture
def a5_coupe() -> VehicleProfile:
    return VehicleProfile(
        vin="WAUCFAFR5FA000001",
        year=2015,
        make="AUDI",
        model="A5",
        trim="Premium",
        body="Coupe",
        doors=2,
        drive="AWD",
        engine_cyl=4,
        displacement_l=2.0,
        fuel="Gasoline",
        transmission="Automatic",
        turbo=True,
    )


@pytest.fixture
def options() -> Options:
    return Options(headlights="xenon", wheel_size=18, navigation=True, sunroof=True)
