from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

import pytest

from engine.models import ResourceInventory
from simulation.environment import heavy_ice_conditions, storm_conditions
from simulation.environment_events import (
    EnvironmentEvent,
    EnvironmentTimeline,
)
from simulation.mission import ResupplyMission


def make_station():
    return SimpleNamespace(
        id="MAITRI",
        name="Maitri",
    )


def make_vessel():
    return SimpleNamespace(
        id="V001",
        name="Swift Arctic",
        cruising_speed_knots=18.0,
        fuel_capacity_litres=500000.0,
        fuel_consumption_litres_per_day=12000.0,
        fuel_cost_per_litre=1.2,
        operating_cost_per_day=25000.0,
    )


def make_route():
    return SimpleNamespace(
        id="R001",
        name="Mumbai-Maitri Direct",
        distance_km=14500.0,
        waypoints=[
            {"latitude": 18.95, "longitude": 72.95},
            {"latitude": -20.0, "longitude": 30.0},
            {"latitude": -70.77, "longitude": 11.73},
        ],
    )


def make_inventory():
    return {
        "diesel": ResourceInventory(
            resource_name="Diesel",
            unit="litres",
            current_quantity=10000.0,
            daily_consumption=100.0,
            minimum_safety_threshold=3000.0,
            required_resupply_quantity=5000.0,
        )
    }


def make_datetime():
    return datetime(
        2026,
        12,
        1,
        0,
        0,
        tzinfo=timezone.utc,
    )


def make_mission(environment_timeline=None):
    return ResupplyMission.create(
        station=make_station(),
        vessel=make_vessel(),
        route=make_route(),
        cargo_weight_tonnes=2000.0,
        departure_datetime=make_datetime(),
        station_inventory=make_inventory(),
        environment_timeline=environment_timeline,
    )


def make_environment_timeline():
    start = make_datetime()

    timeline = EnvironmentTimeline()

    timeline.add_event(
        EnvironmentEvent(
            start_datetime=start + timedelta(days=2),
            end_datetime=start + timedelta(days=4),
            conditions=heavy_ice_conditions(),
            name="Heavy Sea Ice",
        )
    )

    timeline.add_event(
        EnvironmentEvent(
            start_datetime=start + timedelta(days=4),
            end_datetime=start + timedelta(days=5),
            conditions=storm_conditions(),
            name="Severe Storm",
        )
    )

    return timeline


def test_mission_is_created_as_planned():
    mission = make_mission()

    assert mission.status == "PLANNED"
    assert mission.station.id == "MAITRI"
    assert mission.vessel.id == "V001"
    assert mission.route.id == "R001"
    assert mission.cargo_weight_tonnes == 2000.0
    assert mission.simulation_state is None


def test_mission_rejects_negative_cargo():
    with pytest.raises(ValueError):
        ResupplyMission.create(
            station=make_station(),
            vessel=make_vessel(),
            route=make_route(),
            cargo_weight_tonnes=-1.0,
            departure_datetime=make_datetime(),
            station_inventory=make_inventory(),
        )


def test_mission_requires_timezone_aware_departure():
    naive_datetime = datetime(
        2026,
        12,
        1,
    )

    with pytest.raises(ValueError):
        ResupplyMission.create(
            station=make_station(),
            vessel=make_vessel(),
            route=make_route(),
            cargo_weight_tonnes=2000.0,
            departure_datetime=naive_datetime,
            station_inventory=make_inventory(),
        )


def test_mission_initializes_simulation_state():
    mission = make_mission()

    state = mission.initialize()

    assert mission.simulation_state is state
    assert state.station.id == "MAITRI"
    assert state.vessel.id == "V001"
    assert state.route.id == "R001"


def test_mission_get_state_before_initialization():
    mission = make_mission()

    state = mission.get_state()

    assert state["status"] == "PLANNED"
    assert state["station"]["id"] == "MAITRI"
    assert state["vessel"]["id"] == "V001"
    assert state["route"]["id"] == "R001"
    assert state["cargo_weight_tonnes"] == 2000.0
    assert state["progress_percent"] == 0.0


def test_mission_get_state_after_initialization():
    mission = make_mission()

    mission.initialize()

    state = mission.get_state()

    assert state["station"]["id"] == "MAITRI"
    assert state["vessel"]["id"] == "V001"
    assert state["route"]["id"] == "R001"
    assert state["mission"]["cargo_weight_tonnes"] == 2000.0
    assert state["mission"]["status"] == "PLANNED"


def test_initial_mission_progress_is_zero():
    mission = make_mission()

    mission.initialize()

    assert mission.progress_fraction == 0.0
    assert mission.progress_percent == 0.0


def test_simulation_datetime_starts_at_departure():
    mission = make_mission()

    mission.initialize()

    assert (
        mission.simulation_datetime
        == mission.departure_datetime
    )


def test_start_initializes_and_starts_mission():
    mission = make_mission()

    state = mission.start()

    assert state is mission.simulation_state
    assert mission.status == "RUNNING"
    assert mission.simulation_state.status == "running"


def test_start_starts_vessel_voyage():
    mission = make_mission()

    mission.start()

    assert (
        mission.simulation_state.simulated_vessel.status
        == "EN_ROUTE"
    )


def test_start_does_not_reset_existing_simulation():
    mission = make_mission()

    mission.initialize()
    original_state = mission.simulation_state

    mission.start()

    assert mission.simulation_state is original_state
    assert mission.status == "RUNNING"


def test_start_running_mission_is_idempotent():
    mission = make_mission()

    first_state = mission.start()
    second_state = mission.start()

    assert first_state is second_state
    assert mission.status == "RUNNING"


def test_update_moves_simulation_time_forward():
    mission = make_mission()

    mission.start()

    mission.update(24 * 60 * 60)

    assert (
        mission.simulation_datetime
        == datetime(
            2026,
            12,
            2,
            0,
            0,
            tzinfo=timezone.utc,
        )
    )


def test_update_increases_vessel_progress():
    mission = make_mission()

    mission.start()

    initial_progress = mission.progress_fraction

    mission.update(24 * 60 * 60)

    assert mission.progress_fraction > initial_progress
    assert mission.progress_percent > 0.0


def test_update_changes_vessel_position():
    mission = make_mission()

    mission.start()

    initial_position = mission.vessel_position

    mission.update(24 * 60 * 60)

    updated_position = mission.vessel_position

    assert updated_position != initial_position


def test_update_consumes_fuel():
    mission = make_mission()

    mission.start()

    assert mission.fuel_consumed_litres == 0.0

    mission.update(24 * 60 * 60)

    assert mission.fuel_consumed_litres > 0.0


def test_update_reduces_station_inventory():
    mission = make_mission()

    mission.start()

    initial_inventory = mission.current_inventory["diesel"]

    mission.update(24 * 60 * 60)

    updated_inventory = mission.current_inventory["diesel"]

    assert updated_inventory < initial_inventory


def test_update_requires_started_mission():
    mission = make_mission()

    with pytest.raises(RuntimeError):
        mission.update(3600)


def test_update_rejects_negative_elapsed_seconds():
    mission = make_mission()

    mission.start()

    with pytest.raises(ValueError):
        mission.update(-1)


def test_mission_starts_with_normal_environment():
    mission = make_mission(
        environment_timeline=make_environment_timeline()
    )

    mission.start()

    assert mission.current_environment.weather_severity == 0.0
    assert mission.current_environment.sea_ice_severity == 0.0
    assert mission.active_environment_event is None


def test_heavy_ice_event_becomes_active():
    mission = make_mission(
        environment_timeline=make_environment_timeline()
    )

    mission.start()

    mission.update(2 * 24 * 60 * 60)

    assert mission.active_environment_event == "Heavy Sea Ice"
    assert mission.current_environment.sea_ice_severity == 0.9


def test_storm_event_becomes_active():
    mission = make_mission(
        environment_timeline=make_environment_timeline()
    )

    mission.start()

    mission.update(4 * 24 * 60 * 60)

    assert mission.active_environment_event == "Severe Storm"
    assert mission.current_environment.weather_severity == 0.9


def test_environment_returns_to_normal_after_event():
    mission = make_mission(
        environment_timeline=make_environment_timeline()
    )

    mission.start()

    mission.update(5 * 24 * 60 * 60)

    assert mission.active_environment_event is None
    assert mission.current_environment.weather_severity == 0.0
    assert mission.current_environment.sea_ice_severity == 0.0


def test_heavy_ice_reduces_progress_relative_to_normal():
    normal_mission = make_mission()
    ice_mission = make_mission(
        environment_timeline=make_environment_timeline()
    )

    normal_mission.start()
    ice_mission.start()

    normal_mission.update(3 * 24 * 60 * 60)
    ice_mission.update(3 * 24 * 60 * 60)

    assert (
        ice_mission.progress_fraction
        < normal_mission.progress_fraction
    )


def test_environment_increases_fuel_burn_rate():
    normal_mission = make_mission()
    storm_mission = make_mission(
        environment_timeline=make_environment_timeline()
    )

    normal_mission.start()
    storm_mission.start()

    # Advance both missions to the beginning of the storm.
    normal_mission.update(4 * 24 * 60 * 60)
    storm_mission.update(4 * 24 * 60 * 60)

    normal_fuel_before = normal_mission.fuel_consumed_litres
    storm_fuel_before = storm_mission.fuel_consumed_litres

    # Advance both missions through the same one-hour interval.
    normal_mission.update(60 * 60)
    storm_mission.update(60 * 60)

    normal_fuel_increase = (
        normal_mission.fuel_consumed_litres
        - normal_fuel_before
    )

    storm_fuel_increase = (
        storm_mission.fuel_consumed_litres
        - storm_fuel_before
    )

    assert storm_fuel_increase > normal_fuel_increase


def test_environment_is_exposed_in_mission_state():
    mission = make_mission(
        environment_timeline=make_environment_timeline()
    )

    mission.start()
    mission.update(2 * 24 * 60 * 60)

    state = mission.get_state()

    assert "environment" in state
    assert state["environment"]["active_event"] == "Heavy Sea Ice"
    assert state["environment"]["sea_ice_severity"] == 0.9