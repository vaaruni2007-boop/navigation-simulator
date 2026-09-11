# -*- coding: utf-8 -*-
"""
tests/test_simulation.py
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Pytest suite for the deterministic Antarctic resupply simulation components:

* simulation.clock.SimulationClock
* simulation.vessel.SimulatedVessel
* simulation.state.SimulationState

The tests avoid any real‑time waiting; they manipulate the internal state of the
clock to simulate elapsed time deterministically.
"""

import copy
from datetime import datetime, timezone, timedelta
from decimal import Decimal

import pytest

# --------------------------------------------------------------------- #
# Imports from the project
# --------------------------------------------------------------------- #
from simulator.clock import SimulationClock
from simulator.vessel import SimulatedVessel
from simulator.state import SimulationState

from engine import (
    distance as distance_mod,
    inventory as inventory_mod,
    models as models_mod,
)

# --------------------------------------------------------------------- #
# Helper fixtures
# --------------------------------------------------------------------- #
@pytest.fixture
def start_dt():
    """Base UTC datetime used for deterministic tests."""
    return datetime(2026, 10, 1, 0, 0, tzinfo=timezone.utc)


@pytest.fixture
def simple_route():
    """A route with three way‑points forming a straight line."""
    waypoints = [
        {"latitude": 0.0, "longitude": 0.0},
        {"latitude": 0.0, "longitude": 1.0},
        {"latitude": 0.0, "longitude": 2.0},
    ]
    return models_mod.Route(
        id="R1",
        name="StraightLine",
        origin_port_id="P1",
        destination_port_id="S1",
        distance_km=0.0,  # will be ignored – distance is recomputed from waypoints
        waypoints=waypoints,
    )


@pytest.fixture
def simple_vessel():
    """A vessel with modest speed (10 knots) and reasonable fuel consumption."""
    return models_mod.Vessel(
        id="V1",
        name="TestVessel",
        max_speed_knots=10.0,
        fuel_consumption_l_per_nm=2.0,
        operating_cost_per_day=1000.0,
        capacity_liters=5000.0,
        fuel_cost_per_litre=Decimal("1.0"),
    )


@pytest.fixture
def diesel_inventory():
    """ResourceInventory matching the scenario described in the prompt."""
    return inventory_mod.ResourceInventory(
        resource_name="Diesel",
        current_quantity=100_000.0,
        unit="L",
        daily_consumption=1_800.0,
        minimum_safety_threshold=25_000.0,
        required_resupply_quantity=60_000.0,
    )


# --------------------------------------------------------------------- #
# Clock tests
# --------------------------------------------------------------------- #
def test_clock_starts_correctly(start_dt):
    clock = SimulationClock(start_dt, speed_multiplier=1.0)
    # Initially paused – simulated time equals base time
    assert clock.simulation_datetime == start_dt
    # Start the clock; without any real time elapsed it should still equal start_dt
    clock.start()
    assert clock.simulation_datetime == start_dt
    # Simulate some real time by manually adjusting internal counters
    clock._elapsed_real = 10.0  # 10 real seconds have passed
    expected = start_dt + timedelta(seconds=10.0)