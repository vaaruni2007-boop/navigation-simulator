from datetime import datetime, timezone

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