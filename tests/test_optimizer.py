from datetime import datetime, timezone

import pytest

from engine.models import (
    Port,
    ResourceInventory,
    Route,
    Station,
    Vessel,
    Waypoint,
)
from engine.optimizer import optimize_resupply


def make_port(
    port_id="P001",
    name="Mumbai Port",
):
    return Port(
        id=port_id,
        name=name,
        latitude=18.95,
        longitude=72.95,
        capacity_tonnes=100_000,
        available=True,
    )


def make_station(
    station_id="S001",
    name="Maitri",
):
    return Station(
        id=station_id,
        name=name,
        latitude=-70.76,
        longitude=11.73,
        status="operational",
        inventory_reference="scenario_01",
        receiving_capacity_tonnes=5000,
    )


def make_vessel(
    vessel_id="V001",
    name="Test Vessel",
    cruising_speed_knots=20.0,
    cargo_capacity_tonnes=5000.0,
    fuel_capacity_litres=1_000_000.0,
    fuel_consumption_litres_per_day=10_000.0,
    operating_cost_per_day=20_000.0,
    fuel_cost_per_litre=1.0,
    availability_start=None,
    availability_end=None,
):
    return Vessel(
        id=vessel_id,
        name=name,
        type="container_ship",
        cruising_speed_knots=cruising_speed_knots,
        maximum_speed_knots=cruising_speed_knots + 2,
        cargo_capacity_tonnes=cargo_capacity_tonnes,
        fuel_capacity_litres=fuel_capacity_litres,
        fuel_consumption_litres_per_day=fuel_consumption_litres_per_day,
        operating_cost_per_day=operating_cost_per_day,
        fuel_cost_per_litre=fuel_cost_per_litre,
        availability_start=availability_start,
        availability_end=availability_end,
        status="available",
    )


def make_route(
    route_id="R001",
    name="Mumbai-Maitri",
):
    return Route(
        id=route_id,
        name=name,
        origin_port_id="P001",
        destination_station_id="S001",
        waypoints=[
            Waypoint(
                latitude=18.95,
                longitude=72.95,
            ),
            Waypoint(
                latitude=-20.0,
                longitude=30.0,
            ),
            Waypoint(
                latitude=-70.76,
                longitude=11.73,
            ),
        ],
        distance_km=14_500.0,
        route_type="direct",
        base_risk_factor=0.20,
    )


def make_inventory():
    return {
        "S001": {
            "diesel": ResourceInventory(
                resource_name="diesel",
                current_quantity=100_000.0,
                unit="litres",
                daily_consumption=2_000.0,
                minimum_safety_threshold=20_000.0,
                required_resupply_quantity=50_000.0,
            )
        }
    }


def test_optimizer_finds_feasible_option():
    port = make_port()
    station = make_station()
    vessel = make_vessel()
    route = make_route()

    current = datetime(
        2026,
        10,
        1,
        tzinfo=timezone.utc,
    )

    departure = datetime(
        2026,
        11,
        1,
        tzinfo=timezone.utc,
    )

    result = optimize_resupply(
        ports=[port],
        stations=[station],
        vessels=[vessel],
        routes=[route],
        departure_dates=[departure],
        cargo_weight_tonnes=1000.0,
        station_inventory=make_inventory(),
        safety_buffer_days=3.0,
        current_datetime=current,
    )

    assert result.best_option is not None
    assert result.best_option.feasible is True


def test_optimizer_rejects_overweight_cargo():
    port = make_port()
    station = make_station()

    vessel = make_vessel(
        cargo_capacity_tonnes=1000.0
    )

    route = make_route()

    departure = datetime(
        2026,
        11,
        1,
        tzinfo=timezone.utc,
    )

    result = optimize_resupply(
        ports=[port],
        stations=[station],
        vessels=[vessel],
        routes=[route],
        departure_dates=[departure],
        cargo_weight_tonnes=2000.0,
        station_inventory=make_inventory(),
        current_datetime=datetime(
            2026,
            10,
            1,
            tzinfo=timezone.utc,
        ),
    )

    assert result.best_option is None
    assert len(result.infeasible_options) > 0


def test_optimizer_rejects_insufficient_fuel_capacity():
    port = make_port()
    station = make_station()

    vessel = make_vessel(
        fuel_capacity_litres=1_000.0,
        fuel_consumption_litres_per_day=100_000.0,
    )

    route = make_route()

    departure = datetime(
        2026,
        11,
        1,
        tzinfo=timezone.utc,
    )

    result = optimize_resupply(
        ports=[port],
        stations=[station],
        vessels=[vessel],
        routes=[route],
        departure_dates=[departure],
        cargo_weight_tonnes=1000.0,
        station_inventory=make_inventory(),
        current_datetime=datetime(
            2026,
            10,
            1,
            tzinfo=timezone.utc,
        ),
    )

    assert result.best_option is None

    assert any(
        option.rejection_reason
        and "fuel" in option.rejection_reason.lower()
        for option in result.infeasible_options
    )


def test_optimizer_rejects_unavailable_vessel():
    port = make_port()
    station = make_station()

    vessel = make_vessel(
        availability_start=datetime(
            2027,
            1,
            1,
            tzinfo=timezone.utc,
        ),
        availability_end=datetime(
            2027,
            3,
            1,
            tzinfo=timezone.utc,
        ),
    )

    route = make_route()

    departure = datetime(
        2026,
        11,
        1,
        tzinfo=timezone.utc,
    )

    result = optimize_resupply(
        ports=[port],
        stations=[station],
        vessels=[vessel],
        routes=[route],
        departure_dates=[departure],
        cargo_weight_tonnes=1000.0,
        station_inventory=make_inventory(),
        current_datetime=datetime(
            2026,
            10,
            1,
            tzinfo=timezone.utc,
        ),
    )

    assert result.best_option is None

    assert any(
        option.rejection_reason
        and "availability"
        in option.rejection_reason.lower()
        for option in result.infeasible_options
    )


def test_optimizer_rejects_unavailable_port():
    port = make_port()
    port.available = False

    station = make_station()
    vessel = make_vessel()
    route = make_route()

    departure = datetime(
        2026,
        11,
        1,
        tzinfo=timezone.utc,
    )

    result = optimize_resupply(
        ports=[port],
        stations=[station],
        vessels=[vessel],
        routes=[route],
        departure_dates=[departure],
        cargo_weight_tonnes=1000.0,
        station_inventory=make_inventory(),
        current_datetime=datetime(
            2026,
            10,
            1,
            tzinfo=timezone.utc,
        ),
    )

    assert result.best_option is None


def test_optimizer_prefers_lower_cost_when_other_factors_equal():
    port = make_port()
    station = make_station()
    route = make_route()

    expensive_vessel = make_vessel(
        vessel_id="V001",
        name="Expensive Vessel",
        operating_cost_per_day=100_000.0,
    )

    cheap_vessel = make_vessel(
        vessel_id="V002",
        name="Cheap Vessel",
        operating_cost_per_day=10_000.0,
    )

    departure = datetime(
        2026,
        11,
        1,
        tzinfo=timezone.utc,
    )

    result = optimize_resupply(
        ports=[port],
        stations=[station],
        vessels=[
            expensive_vessel,
            cheap_vessel,
        ],
        routes=[route],
        departure_dates=[departure],
        cargo_weight_tonnes=1000.0,
        station_inventory=make_inventory(),
        current_datetime=datetime(
            2026,
            10,
            1,
            tzinfo=timezone.utc,
        ),
    )

    assert result.best_option is not None

    assert (
        result.best_option.vessel.id
        == "V002"
    )


def test_optimizer_returns_alternatives():
    port = make_port()
    station = make_station()
    route = make_route()

    vessels = [
        make_vessel(
            vessel_id="V001",
            name="Vessel One",
        ),
        make_vessel(
            vessel_id="V002",
            name="Vessel Two",
            operating_cost_per_day=25_000.0,
        ),
        make_vessel(
            vessel_id="V003",
            name="Vessel Three",
            operating_cost_per_day=30_000.0,
        ),
    ]

    departure = datetime(
        2026,
        11,
        1,
        tzinfo=timezone.utc,
    )

    result = optimize_resupply(
        ports=[port],
        stations=[station],
        vessels=vessels,
        routes=[route],
        departure_dates=[departure],
        cargo_weight_tonnes=1000.0,
        station_inventory=make_inventory(),
        current_datetime=datetime(
            2026,
            10,
            1,
            tzinfo=timezone.utc,
        ),
        max_alternatives=2,
    )

    assert result.best_option is not None
    assert len(result.alternatives) <= 2


def test_optimizer_rejects_wrong_route_destination():
    port = make_port()
    station = make_station()

    route = make_route()
    route.destination_station_id = "S999"

    vessel = make_vessel()

    departure = datetime(
        2026,
        11,
        1,
        tzinfo=timezone.utc,
    )

    result = optimize_resupply(
        ports=[port],
        stations=[station],
        vessels=[vessel],
        routes=[route],
        departure_dates=[departure],
        cargo_weight_tonnes=1000.0,
        station_inventory=make_inventory(),
        current_datetime=datetime(
            2026,
            10,
            1,
            tzinfo=timezone.utc,
        ),
    )

    assert result.best_option is None


def test_optimizer_rejects_wrong_route_origin():
    port = make_port()
    station = make_station()

    route = make_route()
    route.origin_port_id = "P999"

    vessel = make_vessel()

    departure = datetime(
        2026,
        11,
        1,
        tzinfo=timezone.utc,
    )

    result = optimize_resupply(
        ports=[port],
        stations=[station],
        vessels=[vessel],
        routes=[route],
        departure_dates=[departure],
        cargo_weight_tonnes=1000.0,
        station_inventory=make_inventory(),
        current_datetime=datetime(
            2026,
            10,
            1,
            tzinfo=timezone.utc,
        ),
    )

    assert result.best_option is None