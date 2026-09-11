import pytest

from simulation.environment import (
    EnvironmentConditions,
    heavy_ice_conditions,
    normal_conditions,
    storm_conditions,
)


def test_normal_conditions_do_not_reduce_speed():
    conditions = normal_conditions()

    assert conditions.effective_speed(18.0) == pytest.approx(18.0)


def test_storm_reduces_speed():
    conditions = storm_conditions()

    assert conditions.effective_speed(18.0) < 18.0


def test_heavy_ice_reduces_speed():
    conditions = heavy_ice_conditions()

    assert conditions.effective_speed(18.0) < 18.0


def test_harsh_conditions_increase_fuel():
    normal = normal_conditions()
    storm = storm_conditions()

    assert storm.fuel_multiplier() > normal.fuel_multiplier()


def test_risk_is_between_zero_and_one():
    conditions = storm_conditions()

    risk = conditions.risk_score(0.5)

    assert 0 <= risk <= 1


def test_invalid_weather_severity():
    with pytest.raises(ValueError):
        EnvironmentConditions(weather_severity=1.5)


def test_invalid_sea_ice_severity():
    with pytest.raises(ValueError):
        EnvironmentConditions(sea_ice_severity=-0.1)


def test_invalid_current_factor():
    with pytest.raises(ValueError):
        EnvironmentConditions(current_factor=0)


def test_invalid_visibility_factor():
    with pytest.raises(ValueError):
        EnvironmentConditions(visibility_factor=1.5)


def test_invalid_base_speed():
    conditions = normal_conditions()

    with pytest.raises(ValueError):
        conditions.effective_speed(0)