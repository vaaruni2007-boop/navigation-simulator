from datetime import datetime, timedelta, timezone

import pytest

from engine.models import (
    ResourceInventory,
    Route,
    Station,
    Vessel,
    Waypoint,
)
from simulation.clock import SimulationClock
from simulation.vessel import SimulatedVessel
from simulation.state import SimulationState


def make_vessel():
    return Vessel(
        id="V001",
        name="Test Vessel",
        type="container_ship",
        cruising_speed_knots=10.0,
        maximum_speed_knots=12.0,
        cargo_capacity_tonnes=5000.0,
        fuel_capacity_litres=500_000.0,
        fuel_consumption_litres_per_day=10_000.0,
        operating_cost_per_day=20_000.0,
        fuel_cost_per_litre=1.0,
        availability_start=datetime(
            2026,
            1,
            1,
            tzinfo=timezone.utc,
        ),
        availability_end=datetime(
            2027,
            12,
            31,
            tzinfo=timezone.utc,
        ),
        status="available",
    )


def make_route():
    return Route(
        id="R001",
        name="Test Route",
        origin_port_id="P001",
        destination_station_id="S001",
        waypoints=[
            Waypoint(
                latitude=0.0,
                longitude=0.0,
            ),
            Waypoint(
                latitude=0.0,
                longitude=10.0,
            ),
        ],
        distance_km=1112.0,
        route_type="direct",
        base_risk_factor=0.2,
    )


def make_station():
    return Station(
        id="S001",
        name="Maitri",
        latitude=-70.76,
        longitude=11.73,
        status="operational",
        inventory_reference="scenario_01",
        receiving_capacity_tonnes=5000.0,
    )


def make_inventory():
    return {
        "diesel": ResourceInventory(
            resource_name="diesel",
            current_quantity=1000.0,
            unit="litres",
            daily_consumption=100.0,
            minimum_safety_threshold=200.0,
            required_resupply_quantity=500.0,
        )
    }


def make_clock():
    return SimulationClock(
        initial_datetime=datetime(
            2026,
            11,
            1,
            tzinfo=timezone.utc,
        )
    )


def test_clock_initial_datetime():
    initial = datetime(
        2026,
        11,
        1,
        tzinfo=timezone.utc,
    )

    clock = SimulationClock(
        initial_datetime=initial
    )

    assert clock.current_datetime == initial


def test_clock_advance():
    initial = datetime(
        2026,
        11,
        1,
        tzinfo=timezone.utc,
    )

    clock = SimulationClock(
        initial_datetime=initial
    )

    clock.advance(
        86_400
    )

    assert clock.current_datetime == datetime(
        2026,
        11,
        2,
        tzinfo=timezone.utc,
    )


def test_clock_speed_multiplier():
    initial = datetime(
        2026,
        11,
        1,
        tzinfo=timezone.utc,
    )

    clock = SimulationClock(
        initial_datetime=initial
    )

    clock.set_speed(10.0)

    clock.advance(
        3600
    )

    assert clock.current_datetime == datetime(
        2026,
        11,
        1,
        10,
        0,
        tzinfo=timezone.utc,
    )


def test_clock_reset():
    initial = datetime(
        2026,
        11,
        1,
        tzinfo=timezone.utc,
    )

    clock = SimulationClock(
        initial_datetime=initial
    )

    clock.advance(
        86_400
    )

    clock.reset()

    assert clock.current_datetime == initial


def test_simulated_vessel_initial_state():
    vessel = SimulatedVessel(
        vessel=make_vessel(),
        route=make_route(),
    )

    assert vessel.progress == pytest.approx(
        0.0
    )


def test_simulated_vessel_start():
    simulated = SimulatedVessel(
        vessel=make_vessel(),
        route=make_route(),
    )

    departure = datetime(
        2026,
        11,
        1,
        tzinfo=timezone.utc,
    )

    simulated.start_voyage(
        departure
    )

    assert simulated.is_active is True


def test_simulated_vessel_progresses():
    simulated = SimulatedVessel(
        vessel=make_vessel(),
        route=make_route(),
    )

    departure = datetime(
        2026,
        11,
        1,
        tzinfo=timezone.utc,
    )

    simulated.start_voyage(
        departure
    )

    duration_days = simulated.estimated_duration_days()

    simulated.update(
        duration_days * 86_400 / 2
    )

    assert simulated.progress == pytest.approx(
        0.5,
        abs=0.02,
    )


def test_simulated_vessel_completes():
    simulated = SimulatedVessel(
        vessel=make_vessel(),
        route=make_route(),
    )

    departure = datetime(
        2026,
        11,
        1,
        tzinfo=timezone.utc,
    )

    simulated.start_voyage(
        departure
    )

    duration_days = simulated.estimated_duration_days()

    simulated.update(
        duration_days * 86_400 * 2
    )

    assert simulated.progress == pytest.approx(
        1.0
    )


def test_simulated_vessel_reset():
    simulated = SimulatedVessel(
        vessel=make_vessel(),
        route=make_route(),
    )

    departure = datetime(
        2026,
        11,
        1,
        tzinfo=timezone.utc,
    )

    simulated.start_voyage(
        departure
    )

    simulated.update(
        10_000
    )

    simulated.reset()

    assert simulated.progress == pytest.approx(
        0.0
    )


def test_simulation_state_initialization():
    state = SimulationState(
        clock=make_clock(),
        station=make_station(),
        vessel=make_vessel(),
        route=make_route(),
        station_inventory=make_inventory(),
    )

    current_state = state.get_state()

    assert current_state is not None
    assert state.station.id == "S001"
    assert state.vessel.id == "V001"
    assert state.route.id == "R001"


def test_simulation_state_start():
    state = SimulationState(
        clock=make_clock(),
        station=make_station(),
        vessel=make_vessel(),
        route=make_route(),
        station_inventory=make_inventory(),
    )

    state.start()

    assert state.status in {
        "running",
        "active",
        "started",
    }


def test_simulation_state_reset():
    state = SimulationState(
        clock=make_clock(),
        station=make_station(),
        vessel=make_vessel(),
        route=make_route(),
        station_inventory=make_inventory(),
    )

    state.start()

    state.update(
        3600
    )

    state.reset()

    assert state.simulated_vessel.progress == pytest.approx(
        0.0
    )
def test_paused_simulation_does_not_advance():
    state = SimulationState(
        clock=make_clock(),
        station=make_station(),
        vessel=make_vessel(),
        route=make_route(),
        station_inventory=make_inventory(),
    )

    state.start()

    state.update(3600)

    datetime_before_pause = state.simulation_datetime
    progress_before_pause = state.vessel_progress
    fuel_before_pause = state.fuel_consumed_litres
    inventory_before_pause = dict(state.current_inventory)

    state.pause()

    state.update(86_400)

    assert state.simulation_datetime == datetime_before_pause
    assert state.vessel_progress == pytest.approx(
        progress_before_pause
    )
    assert state.fuel_consumed_litres == pytest.approx(
        fuel_before_pause
    )
    assert state.current_inventory == inventory_before_pause


def test_vessel_does_not_overshoot_arrival():
    simulated = SimulatedVessel(
        vessel=make_vessel(),
        route=make_route(),
    )

    departure = datetime(
        2026,
        11,
        1,
        tzinfo=timezone.utc,
    )

    simulated.start_voyage(departure)

    duration_days = simulated.estimated_duration_days()

    simulated.update(
        duration_days * 86_400 * 10
    )

    assert simulated.is_complete is True
    assert simulated.progress == pytest.approx(1.0)

    expected_arrival = departure + timedelta(
        days=simulated.planned_duration_days
    )

    assert simulated.current_datetime == expected_arrival


def test_fuel_consumed_matches_vessel_fuel_remaining():
    state = SimulationState(
        clock=make_clock(),
        station=make_station(),
        vessel=make_vessel(),
        route=make_route(),
        station_inventory=make_inventory(),
    )

    state.start()
    state.update(12 * 3600)

    expected_consumed = (
        state.vessel.fuel_capacity_litres
        - state.simulated_vessel.fuel_remaining_litres
    )

    assert state.fuel_consumed_litres == pytest.approx(
        expected_consumed
    )


def test_environment_event_changes_vessel_speed():
    from simulation.environment_events import (
        create_demo_timeline,
    )

    clock = make_clock()

    timeline = create_demo_timeline(
        clock.start_datetime
    )

    state = SimulationState(
        clock=clock,
        station=make_station(),
        vessel=make_vessel(),
        route=make_route(),
        station_inventory=make_inventory(),
        environment_timeline=timeline,
    )

    state.start()

    normal_speed = state.simulated_vessel.effective_speed_knots

    state.update(
        2 * 86_400
    )

    assert state.active_environment_event == "Heavy Sea Ice"

    ice_speed = state.simulated_vessel.effective_speed_knots

    assert ice_speed < normal_speed


def test_environment_event_increases_fuel_burn():
    from simulation.environment_events import (
        create_demo_timeline,
    )

    clock = make_clock()

    timeline = create_demo_timeline(
        clock.start_datetime
    )

    state = SimulationState(
        clock=clock,
        station=make_station(),
        vessel=make_vessel(),
        route=make_route(),
        station_inventory=make_inventory(),
        environment_timeline=timeline,
    )

    state.start()

    normal_burn = (
        state.simulated_vessel.current_fuel_burn_per_day
    )

    state.update(
        2 * 86_400
    )

    harsh_burn = (
        state.simulated_vessel.current_fuel_burn_per_day
    )

    assert harsh_burn > normal_burn


def test_state_reports_fuel_remaining():
    state = SimulationState(
        clock=make_clock(),
        station=make_station(),
        vessel=make_vessel(),
        route=make_route(),
        station_inventory=make_inventory(),
    )

    state.start()
    state.update(3600)

    result = state.get_state()

    assert "fuel_remaining_litres" in result
    assert "fuel_remaining_percent" in result

    assert result["fuel_remaining_litres"] == pytest.approx(
        state.simulated_vessel.fuel_remaining_litres
    )


def test_simulation_completes_with_exact_arrival():
    state = SimulationState(
        clock=make_clock(),
        station=make_station(),
        vessel=make_vessel(),
        route=make_route(),
        station_inventory=make_inventory(),
    )

    state.start()

    duration_days = (
        state.simulated_vessel.estimated_duration_days()
    )

    state.update(
        duration_days * 86_400 * 2
    )

    assert state.status == "completed"
    assert state.simulated_vessel.status == "COMPLETED"
    assert state.vessel_progress == pytest.approx(1.0)

    assert (
        state.simulation_datetime
        == state.simulated_vessel.arrival_datetime
    )    