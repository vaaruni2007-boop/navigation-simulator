from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

import pytest

from engine.resupply_optimizer import (
    ResupplyOptimizer,
    optimize_resupply,
)
from simulation.environment import (
    heavy_ice_conditions,
    normal_conditions,
    storm_conditions,
)


def make_datetime():
    return datetime(
        2026,
        10,
        1,
        12,
        0,
        tzinfo=timezone.utc,
    )


def make_station():
    return SimpleNamespace(
        id="MAITRI",
        name="Maitri",
    )


def make_resource(
    required_quantity=10000.0,
):
    return SimpleNamespace(
        id="diesel",
        resource_name="Diesel",
        required_resupply_quantity=required_quantity,
    )


def make_vessel(
    vessel_id="V001",
    name="Swift Arctic",
    cargo_capacity_tonnes=2000.0,
    fuel_capacity_litres=500000.0,
    cruise_speed_knots=18.0,
    fuel_consumption_litres_per_day=12000.0,
    operating_cost_per_day=25000.0,
    fuel_cost_per_litre=1.2,
    availability_start=None,
    availability_end=None,
):
    return SimpleNamespace(
        id=vessel_id,
        name=name,
        cargo_capacity_tonnes=cargo_capacity_tonnes,
        fuel_capacity_litres=fuel_capacity_litres,
        cruise_speed_knots=cruise_speed_knots,
        fuel_consumption_litres_per_day=(
            fuel_consumption_litres_per_day
        ),
        operating_cost_per_day=operating_cost_per_day,
        fuel_cost_per_litre=fuel_cost_per_litre,
        availability_start=availability_start,
        availability_end=availability_end,
    )


def make_route(
    route_id="R001",
    origin="MUMBAI",
    destination="MAITRI",
    distance_km=14500.0,
    risk_score=0.25,
):
    return SimpleNamespace(
        id=route_id,
        origin_port_id=origin,
        destination_station_id=destination,
        distance_km=distance_km,
        risk_score=risk_score,
    )


def test_optimizer_evaluates_valid_option():
    optimizer = ResupplyOptimizer()

    option = optimizer.evaluate_option(
        vessel=make_vessel(),
        route=make_route(),
        station=make_station(),
        resource=make_resource(),
        current_datetime=make_datetime(),
        cargo_weight_tonnes=500.0,
    )

    assert option.feasible is True
    assert option.vessel_id == "V001"
    assert option.route_id == "R001"
    assert option.duration_days > 0
    assert option.fuel_required_litres > 0
    assert option.total_cost > 0


def test_optimizer_rejects_insufficient_cargo_capacity():
    optimizer = ResupplyOptimizer()

    option = optimizer.evaluate_option(
        vessel=make_vessel(
            cargo_capacity_tonnes=100.0,
        ),
        route=make_route(),
        station=make_station(),
        resource=make_resource(),
        current_datetime=make_datetime(),
        cargo_weight_tonnes=500.0,
    )

    assert option.feasible is False
    assert any(
        "cargo" in reason.lower()
        for reason in option.rejection_reasons
    )


def test_optimizer_rejects_unavailable_vessel():
    current = make_datetime()

    optimizer = ResupplyOptimizer()

    option = optimizer.evaluate_option(
        vessel=make_vessel(
            availability_start=current + timedelta(days=10),
        ),
        route=make_route(),
        station=make_station(),
        resource=make_resource(),
        current_datetime=current,
        cargo_weight_tonnes=500.0,
    )

    assert option.feasible is False
    assert any(
        "unavailable" in reason.lower()
        for reason in option.rejection_reasons
    )


def test_optimizer_rejects_insufficient_fuel():
    optimizer = ResupplyOptimizer()

    option = optimizer.evaluate_option(
        vessel=make_vessel(
            fuel_capacity_litres=1000.0,
        ),
        route=make_route(),
        station=make_station(),
        resource=make_resource(),
        current_datetime=make_datetime(),
        cargo_weight_tonnes=500.0,
    )

    assert option.feasible is False
    assert any(
        "fuel" in reason.lower()
        for reason in option.rejection_reasons
    )


def test_optimizer_rejects_wrong_destination():
    optimizer = ResupplyOptimizer()

    option = optimizer.evaluate_option(
        vessel=make_vessel(),
        route=make_route(
            destination="BHARATI",
        ),
        station=make_station(),
        resource=make_resource(),
        current_datetime=make_datetime(),
        cargo_weight_tonnes=500.0,
    )

    assert option.feasible is False
    assert any(
        "station" in reason.lower()
        for reason in option.rejection_reasons
    )


def test_optimizer_rejects_missed_deadline():
    current = make_datetime()

    optimizer = ResupplyOptimizer()

    option = optimizer.evaluate_option(
        vessel=make_vessel(),
        route=make_route(),
        station=make_station(),
        resource=make_resource(),
        current_datetime=current,
        cargo_weight_tonnes=500.0,
        latest_safe_arrival=current + timedelta(days=5),
    )

    assert option.feasible is False
    assert any(
        "deadline" in reason.lower()
        or "arrival" in reason.lower()
        for reason in option.rejection_reasons
    )


def test_optimizer_returns_feasible_options():
    optimizer = ResupplyOptimizer()

    result = optimizer.optimize(
        station=make_station(),
        resource=make_resource(),
        vessels=[
            make_vessel(
                vessel_id="V001",
                name="Swift Arctic",
            ),
            make_vessel(
                vessel_id="V002",
                name="Polar Glide",
                cruise_speed_knots=10.0,
                fuel_consumption_litres_per_day=8000.0,
                fuel_capacity_litres=600000.0,
            ),
        ],
        routes=[
            make_route(),
        ],
        current_datetime=make_datetime(),
        cargo_weight_tonnes=500.0,
    )

    assert len(result.feasible_options) == 2
    assert result.recommended_option is not None


def test_optimizer_selects_best_feasible_option():
    current = make_datetime()

    optimizer = ResupplyOptimizer()

    result = optimizer.optimize(
        station=make_station(),
        resource=make_resource(),
        vessels=[
            make_vessel(
                vessel_id="SLOW",
                name="Slow Vessel",
                cruise_speed_knots=10.0,
                fuel_consumption_litres_per_day=8000.0,
            ),
            make_vessel(
                vessel_id="FAST",
                name="Fast Vessel",
                cruise_speed_knots=18.0,
                fuel_consumption_litres_per_day=12000.0,
            ),
        ],
        routes=[
            make_route(),
        ],
        current_datetime=current,
        cargo_weight_tonnes=500.0,
        latest_safe_arrival=current + timedelta(days=100),
    )

    assert result.recommended_option is not None
    assert result.recommended_option.vessel_id == "FAST"


def test_environment_increases_fuel_requirement():
    optimizer = ResupplyOptimizer()

    normal = optimizer.evaluate_option(
        vessel=make_vessel(),
        route=make_route(),
        station=make_station(),
        resource=make_resource(),
        current_datetime=make_datetime(),
        cargo_weight_tonnes=500.0,
        environment=normal_conditions(),
    )

    storm = optimizer.evaluate_option(
        vessel=make_vessel(),
        route=make_route(),
        station=make_station(),
        resource=make_resource(),
        current_datetime=make_datetime(),
        cargo_weight_tonnes=500.0,
        environment=storm_conditions(),
    )

    assert storm.fuel_required_litres > normal.fuel_required_litres


def test_environment_reduces_effective_speed():
    optimizer = ResupplyOptimizer()

    normal = optimizer.evaluate_option(
        vessel=make_vessel(),
        route=make_route(),
        station=make_station(),
        resource=make_resource(),
        current_datetime=make_datetime(),
        cargo_weight_tonnes=500.0,
        environment=normal_conditions(),
    )

    ice = optimizer.evaluate_option(
        vessel=make_vessel(),
        route=make_route(),
        station=make_station(),
        resource=make_resource(),
        current_datetime=make_datetime(),
        cargo_weight_tonnes=500.0,
        environment=heavy_ice_conditions(),
    )

    assert ice.duration_days > normal.duration_days


def test_optimizer_serializes_result():
    result = optimize_resupply(
        station=make_station(),
        resource=make_resource(),
        vessels=[
            make_vessel(),
        ],
        routes=[
            make_route(),
        ],
        current_datetime=make_datetime(),
        cargo_weight_tonnes=500.0,
    )

    data = result.to_dict()

    assert isinstance(data, dict)
    assert data["station_id"] == "MAITRI"
    assert data["station_name"] == "Maitri"
    assert data["resource_name"] == "Diesel"
    assert data["recommended_option"] is not None


def test_optimizer_keeps_infeasible_options():
    result = optimize_resupply(
        station=make_station(),
        resource=make_resource(),
        vessels=[
            make_vessel(
                vessel_id="BAD",
                name="Bad Vessel",
                cargo_capacity_tonnes=100.0,
            ),
            make_vessel(
                vessel_id="GOOD",
                name="Good Vessel",
            ),
        ],
        routes=[
            make_route(),
        ],
        current_datetime=make_datetime(),
        cargo_weight_tonnes=500.0,
    )

    assert len(result.infeasible_options) == 1
    assert result.infeasible_options[0].vessel_id == "BAD"
    assert result.recommended_option is not None


# ============================================================
# STEP 7 — EXPLAINABILITY TESTS
# ============================================================


def test_feasible_option_contains_explanation():
    optimizer = ResupplyOptimizer()

    option = optimizer.evaluate_option(
        vessel=make_vessel(),
        route=make_route(),
        station=make_station(),
        resource=make_resource(),
        current_datetime=make_datetime(),
        cargo_weight_tonnes=500.0,
    )

    assert option.feasible is True
    assert hasattr(option, "reasons")
    assert hasattr(option, "warnings")

    assert isinstance(option.reasons, list)
    assert isinstance(option.warnings, list)

    assert len(option.reasons) > 0


def test_infeasible_option_explains_rejection():
    optimizer = ResupplyOptimizer()

    option = optimizer.evaluate_option(
        vessel=make_vessel(
            cargo_capacity_tonnes=100.0,
        ),
        route=make_route(),
        station=make_station(),
        resource=make_resource(),
        current_datetime=make_datetime(),
        cargo_weight_tonnes=500.0,
    )

    assert option.feasible is False
    assert hasattr(option, "reasons")
    assert isinstance(option.reasons, list)

    assert len(option.reasons) > 0

    assert any(
        "cargo" in reason.lower()
        for reason in option.reasons
    )


def test_recommended_option_has_explanation():
    optimizer = ResupplyOptimizer()

    result = optimizer.optimize(
        station=make_station(),
        resource=make_resource(),
        vessels=[
            make_vessel(
                vessel_id="V001",
            ),
            make_vessel(
                vessel_id="V002",
                name="Polar Glide",
                cruise_speed_knots=10.0,
                fuel_consumption_litres_per_day=8000.0,
                fuel_capacity_litres=600000.0,
            ),
        ],
        routes=[
            make_route(),
        ],
        current_datetime=make_datetime(),
        cargo_weight_tonnes=500.0,
    )

    assert result.recommended_option is not None

    winner = result.recommended_option

    assert len(winner.reasons) > 0
    assert isinstance(winner.warnings, list)


def test_why_this_option_won_returns_explanation():
    optimizer = ResupplyOptimizer()

    result = optimizer.optimize(
        station=make_station(),
        resource=make_resource(),
        vessels=[
            make_vessel(),
        ],
        routes=[
            make_route(),
        ],
        current_datetime=make_datetime(),
        cargo_weight_tonnes=500.0,
    )

    explanation = result.why_this_option_won()

    assert isinstance(explanation, dict)
    assert explanation["status"] == "RECOMMENDED"
    assert explanation["winner"] is not None
    assert explanation["reasons"]


def test_why_this_option_won_handles_no_feasible_option():
    optimizer = ResupplyOptimizer()

    result = optimizer.optimize(
        station=make_station(),
        resource=make_resource(),
        vessels=[
            make_vessel(
                cargo_capacity_tonnes=100.0,
            ),
        ],
        routes=[
            make_route(),
        ],
        current_datetime=make_datetime(),
        cargo_weight_tonnes=500.0,
    )

    explanation = result.why_this_option_won()

    assert isinstance(explanation, dict)
    assert explanation["status"] == "NO_FEASIBLE_OPTION"
    assert explanation["winner"] is None
    assert explanation["reasons"] == []


def test_explanation_contains_operational_factors():
    optimizer = ResupplyOptimizer()

    option = optimizer.evaluate_option(
        vessel=make_vessel(),
        route=make_route(),
        station=make_station(),
        resource=make_resource(),
        current_datetime=make_datetime(),
        cargo_weight_tonnes=500.0,
        environment=normal_conditions(),
    )

    explanation_text = " ".join(option.reasons).lower()

    assert "cargo" in explanation_text
    assert "fuel" in explanation_text
    assert "cost" in explanation_text
    assert "risk" in explanation_text