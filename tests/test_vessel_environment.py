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


def make_departure():
    return datetime(
        2026,
        12,
        1,
        tzinfo=timezone.utc,
    )


def test_normal_environment_keeps_cruise_speed():
    vessel = make_vessel()

    assert vessel.effective_speed_knots == pytest.approx(
        20.0
    )


def test_storm_reduces_vessel_speed():
    vessel = make_vessel()
    vessel.set_environment(storm_conditions())

    assert vessel.effective_speed_knots < 20.0


def test_heavy_ice_reduces_vessel_speed():
    vessel = make_vessel()

    vessel.set_environment(
        heavy_ice_conditions()
    )

    assert vessel.effective_speed_knots < 20.0


def test_storm_increases_fuel_burn():
    vessel = make_vessel()

    normal_burn = (
        vessel.current_fuel_burn_per_day
    )

    vessel.set_environment(
        storm_conditions()
    )

    assert (
        vessel.current_fuel_burn_per_day
        > normal_burn
    )


def test_vessel_moves_forward():
    vessel = make_vessel()

    departure = make_departure()

    vessel.start_voyage(departure)

    vessel.advance(1.0)

    assert (
        vessel.distance_travelled_nm
        == pytest.approx(20.0)
    )

    assert (
        vessel.current_datetime
        == datetime(
            2026,
            12,
            1,
            1,
            tzinfo=timezone.utc,
        )
    )


def test_vessel_consumes_fuel():
    vessel = make_vessel()

    vessel.start_voyage(
        make_departure()
    )

    vessel.advance(24.0)

    assert (
        vessel.fuel_remaining_litres
        == pytest.approx(90000.0)
    )


def test_storm_causes_less_distance_in_same_time():
    vessel = make_vessel()

    vessel.start_voyage(
        make_departure()
    )

    vessel.advance(
        1.0,
        environment=storm_conditions(),
    )

    assert (
        vessel.distance_travelled_nm
        < 20.0
    )


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
        make_departure()
    )

    vessel.advance(1.0)

    assert vessel.is_complete
    assert vessel.status == "COMPLETED"


# ------------------------------------------------------------------
# Dynamic ETA
# ------------------------------------------------------------------


def test_projected_arrival_datetime_exists_after_voyage_starts():
    vessel = make_vessel()

    departure = make_departure()

    vessel.start_voyage(departure)

    assert (
        vessel.projected_arrival_datetime
        is not None
    )


def test_projected_eta_recalculates_from_remaining_distance():
    vessel = make_vessel()

    departure = make_departure()

    vessel.start_voyage(departure)

    original_remaining = (
        vessel.distance_remaining_nm
    )

    vessel.advance(24.0)

    assert (
        vessel.distance_remaining_nm
        < original_remaining
    )

    assert (
        vessel.projected_arrival_datetime
        is not None
    )


def test_dynamic_eta_moves_later_under_slower_environment():
    vessel = make_vessel()

    departure = make_departure()

    vessel.start_voyage(
        departure,
        environment=normal_conditions(),
    )

    vessel.advance(24.0)

    normal_eta = (
        vessel.projected_arrival_datetime
    )

    vessel.set_environment(
        heavy_ice_conditions()
    )

    delayed_eta = (
        vessel.projected_arrival_datetime
    )

    assert normal_eta is not None
    assert delayed_eta is not None
    assert delayed_eta > normal_eta


def test_delay_days_is_zero_at_voyage_start():
    vessel = make_vessel()

    departure = make_departure()

    vessel.start_voyage(
        departure,
        environment=normal_conditions(),
    )

    assert vessel.delay_days == pytest.approx(
        0.0
    )


def test_delay_days_becomes_positive_after_environmental_slowdown():
    vessel = make_vessel()

    departure = make_departure()

    vessel.start_voyage(
        departure,
        environment=normal_conditions(),
    )

    vessel.set_environment(
        heavy_ice_conditions()
    )

    vessel.advance(24.0)

    assert vessel.delay_days is not None
    assert vessel.delay_days > 0


def test_dynamic_eta_equals_current_time_when_voyage_completes():
    vessel = make_vessel()

    departure = make_departure()

    vessel.start_voyage(departure)

    vessel.advance(
        vessel.estimated_duration_days() * 24
    )

    assert vessel.is_complete

    assert (
        vessel.projected_arrival_datetime
        == vessel.current_datetime
    )


# ------------------------------------------------------------------
# 8E.3 — Environmental risk propagation
# ------------------------------------------------------------------


def test_environmental_delay_is_exposed_after_slowdown():
    vessel = make_vessel()

    departure = make_departure()

    vessel.start_voyage(
        departure,
        environment=normal_conditions(),
    )

    assert vessel.delay_days == pytest.approx(
        0.0
    )

    vessel.advance(24.0)

    vessel.set_environment(
        heavy_ice_conditions()
    )

    assert vessel.delay_days is not None
    assert vessel.delay_days > 0


def test_set_environment_updates_arrival_projection():
    vessel = make_vessel()

    departure = make_departure()

    vessel.start_voyage(
        departure,
        environment=normal_conditions(),
    )

    vessel.advance(24.0)

    normal_eta = (
        vessel.projected_arrival_datetime
    )

    vessel.set_environment(
        storm_conditions()
    )

    storm_eta = (
        vessel.projected_arrival_datetime
    )

    assert normal_eta is not None
    assert storm_eta is not None
    assert storm_eta > normal_eta


def test_environmental_delay_is_zero_under_normal_conditions():
    vessel = make_vessel()

    departure = make_departure()

    vessel.start_voyage(
        departure,
        environment=normal_conditions(),
    )

    vessel.advance(24.0)

    assert vessel.delay_days == pytest.approx(
        0.0
    )


# ------------------------------------------------------------------
# Pause / Resume
# ------------------------------------------------------------------


def test_pause_voyage_changes_status_to_paused():
    vessel = make_vessel()

    vessel.start_voyage(
        make_departure()
    )

    vessel.pause_voyage()

    assert vessel.status == "PAUSED"
    assert not vessel.is_active


def test_paused_vessel_does_not_advance():
    vessel = make_vessel()

    vessel.start_voyage(
        make_departure()
    )

    vessel.advance(12.0)

    distance_before_pause = (
        vessel.distance_travelled_nm
    )
    datetime_before_pause = (
        vessel.current_datetime
    )
    fuel_before_pause = (
        vessel.fuel_remaining_litres
    )

    vessel.pause_voyage()

    vessel.advance(24.0)

    assert (
        vessel.distance_travelled_nm
        == pytest.approx(
            distance_before_pause
        )
    )

    assert (
        vessel.current_datetime
        == datetime_before_pause
    )

    assert (
        vessel.fuel_remaining_litres
        == pytest.approx(
            fuel_before_pause
        )
    )


def test_resume_voyage_continues_existing_voyage():
    vessel = make_vessel()

    vessel.start_voyage(
        make_departure()
    )

    vessel.advance(12.0)

    distance_before_pause = (
        vessel.distance_travelled_nm
    )
    datetime_before_pause = (
        vessel.current_datetime
    )

    vessel.pause_voyage()
    vessel.resume_voyage()

    assert vessel.status == "EN_ROUTE"

    vessel.advance(12.0)

    assert (
        vessel.distance_travelled_nm
        > distance_before_pause
    )

    assert (
        vessel.current_datetime
        > datetime_before_pause
    )


def test_pause_resume_preserves_departure_datetime():
    vessel = make_vessel()

    departure = make_departure()

    vessel.start_voyage(departure)

    vessel.advance(12.0)

    vessel.pause_voyage()
    vessel.resume_voyage()

    assert (
        vessel.departure_datetime
        == departure
    )


def test_pause_resume_does_not_reset_progress():
    vessel = make_vessel()

    vessel.start_voyage(
        make_departure()
    )

    vessel.advance(10.0)

    progress_before_pause = (
        vessel.progress
    )

    vessel.pause_voyage()
    vessel.resume_voyage()

    assert (
        vessel.progress
        == pytest.approx(
            progress_before_pause
        )
    )


def test_start_voyage_rejects_paused_vessel():
    vessel = make_vessel()

    vessel.start_voyage(
        make_departure()
    )

    vessel.pause_voyage()

    with pytest.raises(ValueError):
        vessel.start_voyage(
            make_departure()
        )


def test_start_voyage_rejects_completed_vessel():
    vessel = SimulatedVessel(
        vessel_id="V001",
        total_distance_nm=10.0,
        cruise_speed_knots=20.0,
        fuel_capacity_litres=100000.0,
        fuel_remaining_litres=100000.0,
        fuel_consumption_litres_per_day=10000.0,
    )

    vessel.start_voyage(
        make_departure()
    )

    vessel.advance(1.0)

    assert vessel.status == "COMPLETED"

    with pytest.raises(ValueError):
        vessel.start_voyage(
            make_departure()
        )


def test_naive_departure_datetime_is_rejected():
    vessel = make_vessel()

    with pytest.raises(ValueError):
        vessel.start_voyage(
            datetime(2026, 12, 1)
        )


def test_pause_when_not_en_route_is_safe():
    vessel = make_vessel()

    vessel.pause_voyage()

    assert vessel.status == "PLANNED"


def test_resume_when_not_paused_is_safe():
    vessel = make_vessel()

    vessel.resume_voyage()

    assert vessel.status == "PLANNED"