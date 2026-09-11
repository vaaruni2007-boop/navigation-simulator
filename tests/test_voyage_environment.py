from datetime import datetime, timezone

import pytest

from engine.voyage import (
    environment_adjusted_eta,
    environment_adjusted_fuel_consumption,
    environment_adjusted_voyage_duration_days,
    effective_voyage_speed,
)
from simulation.environment import (
    heavy_ice_conditions,
    normal_conditions,
    storm_conditions,
)


def test_normal_environment_preserves_speed():
    speed = effective_voyage_speed(
        18.0,
        normal_conditions(),
    )

    assert speed == pytest.approx(18.0)


def test_heavy_ice_reduces_speed():
    normal_speed = effective_voyage_speed(
        18.0,
        normal_conditions(),
    )

    ice_speed = effective_voyage_speed(
        18.0,
        heavy_ice_conditions(),
    )

    assert ice_speed < normal_speed


def test_storm_reduces_speed():
    normal_speed = effective_voyage_speed(
        18.0,
        normal_conditions(),
    )

    storm_speed = effective_voyage_speed(
        18.0,
        storm_conditions(),
    )

    assert storm_speed < normal_speed


def test_environment_increases_duration():
    normal_duration = (
        environment_adjusted_voyage_duration_days(
            distance_nm=1000,
            speed_knots=18,
            environment=normal_conditions(),
        )
    )

    storm_duration = (
        environment_adjusted_voyage_duration_days(
            distance_nm=1000,
            speed_knots=18,
            environment=storm_conditions(),
        )
    )

    assert storm_duration > normal_duration


def test_environment_increases_fuel_consumption():
    normal_fuel = environment_adjusted_fuel_consumption(
        duration_days=10,
        base_fuel_per_day=10000,
        environment=normal_conditions(),
    )

    storm_fuel = environment_adjusted_fuel_consumption(
        duration_days=10,
        base_fuel_per_day=10000,
        environment=storm_conditions(),
    )

    assert storm_fuel > normal_fuel


def test_environment_adjusted_eta_is_later():
    departure = datetime(
        2026,
        12,
        1,
        tzinfo=timezone.utc,
    )

    normal_eta = environment_adjusted_eta(
        departure=departure,
        distance_nm=5000,
        speed_knots=18,
        environment=normal_conditions(),
    )

    storm_eta = environment_adjusted_eta(
        departure=departure,
        distance_nm=5000,
        speed_knots=18,
        environment=storm_conditions(),
    )

    assert storm_eta > normal_eta


def test_zero_distance_has_zero_duration():
    duration = (
        environment_adjusted_voyage_duration_days(
            distance_nm=0,
            speed_knots=18,
            environment=storm_conditions(),
        )
    )

    assert duration == pytest.approx(0.0)


def test_environmental_speed_rejects_invalid_speed():
    with pytest.raises(ValueError):
        effective_voyage_speed(
            0,
            normal_conditions(),
        )