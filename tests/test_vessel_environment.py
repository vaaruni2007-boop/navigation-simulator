from datetime import datetime, timezone

import pytest

from simulation.environment import (
    heavy_ice_conditions,
    normal_conditions,
    storm_conditions,
)
from simulation.vessel import SimulatedVessel


def make_vessel():
    return SimulatedVessel(
        vessel_id="V001",
        total_distance_nm=1000.0,
        cruise_speed_knots=20.0,
        fuel_capacity_litres=100000.0,
        fuel_remaining_litres=100000.0,
        fuel_consumption_litres_per_day=10000.0,
    )


def test_normal_environment_keeps_cruise_speed():
    vessel = make_vessel()

    assert vessel.effective_speed_knots == pytest.approx(20.0)


def test_storm_reduces_vessel_speed():
    vessel = make_vessel()
    vessel.set_environment(storm_conditions())

    assert vessel.effective_speed_knots < 20.0


def test_heavy_ice_reduces_vessel_speed():
    vessel = make_vessel()
    vessel.set_environment(heavy_ice_conditions())

    assert vessel.effective_speed_knots < 20.0


def test_storm_increases_fuel_burn():
    vessel = make_vessel()

    normal_burn = vessel.current_fuel_burn_per_day

    vessel.set_environment(storm_conditions())

    assert vessel.current_fuel_burn_per_day > normal_burn


def test_vessel_moves_forward():
    vessel = make_vessel()

    vessel.start_voyage(
        datetime(2026, 12, 1, tzinfo=timezone.utc)
    )

    vessel.advance(1.0)

    assert vessel.distance_travelled_nm == pytest.approx(20.0)
    assert vessel.current_datetime == datetime(
        2026, 12, 1, 1, tzinfo=timezone.utc
    )


def test_vessel_consumes_fuel():
    vessel = make_vessel()

    vessel.start_voyage(
        datetime(2026, 12, 1, tzinfo=timezone.utc)
    )

    vessel.advance(24.0)

    assert vessel.fuel_remaining_litres == pytest.approx(
        90000.0
    )


def test_storm_causes_less_distance_in_same_time():
    vessel = make_vessel()

    vessel.start_voyage(
        datetime(2026, 12, 1, tzinfo=timezone.utc)
    )

    vessel.advance(
        1.0,
        environment=storm_conditions(),
    )

    assert vessel.distance_travelled_nm < 20.0


def test_vessel_completes_when_destination_reached():
    vessel = SimulatedVessel(
        vessel_id="V001",
        total_distance_nm=10.0,
        cruise_speed_knots=20.0,
        fuel_capacity_litres=100000.0,
        fuel_remaining_litres=100000.0,
        fuel_consumption_litres_per_day=10000.0,
    )

    vessel.start_voyage(
        datetime(2026, 12, 1, tzinfo=timezone.utc)
    )

    vessel.advance(1.0)

    assert vessel.is_complete
    assert vessel.status == "COMPLETED"