from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from engine.models import ResourceInventory, Route, Station, Vessel
from simulation.environment import (
    heavy_ice_conditions,
    normal_conditions,
    storm_conditions,
)
from simulation.environment_events import (
    EnvironmentEvent,
    EnvironmentTimeline,
)
from simulation.mission import ResupplyMission


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

BASE_DIR = Path(__file__).resolve().parents[1]
DATA_DIR = BASE_DIR / "data"


def make_datetime() -> datetime:
    return datetime(
        2026,
        12,
        15,
        12,
        0,
        tzinfo=timezone.utc,
    )


def make_resource(
    name: str = "Diesel",
    current: float = 100000.0,
    consumption: float = 2000.0,
    threshold: float = 20000.0,
) -> ResourceInventory:
    return ResourceInventory(
        resource_name=name,
        current_quantity=current,
        unit="litres",
        daily_consumption=consumption,
        minimum_safety_threshold=threshold,
        required_resupply_quantity=0.0,
    )


def make_station() -> Station:
    return Station(
        id="MAITRI",
        name="Maitri",
        country="Antarctica",
        latitude=-70.7697,
        longitude=11.7367,
        status="operational",
        inventory_reference="scenario_01",
        receiving_capacity_tonnes=5000.0,
    )


def _load_json(filename: str):
    with open(DATA_DIR / filename, "r", encoding="utf-8") as file:
        return json.load(file)


def make_vessel() -> Vessel:
    data = _load_json("vessels.json")

    if isinstance(data, dict):
        records = (
            data.get("vessels")
            or data.get("data")
            or data.get("items")
            or []
        )
    else:
        records = data

    vessel_data = next(
        item for item in records
        if item.get("id") == "V001"
    )

    return Vessel.model_validate(vessel_data)


def make_route() -> Route:
    data = _load_json("routes.json")

    if isinstance(data, dict):
        records = (
            data.get("routes")
            or data.get("data")
            or data.get("items")
            or []
        )
    else:
        records = data

    route_data = next(
        item for item in records
        if item.get("id") == "R001"
    )

    return Route.model_validate(route_data)


def make_mission(
    *,
    departure_datetime: datetime | None = None,
    cargo_weight_tonnes: float = 1000.0,
    inventory: dict[str, ResourceInventory] | None = None,
    safety_buffer_days: float = 3.0,
    environment_timeline: EnvironmentTimeline | None = None,
) -> ResupplyMission:
    return ResupplyMission(
        station=make_station(),
        vessel=make_vessel(),
        route=make_route(),
        cargo_weight_tonnes=cargo_weight_tonnes,
        departure_datetime=(
            departure_datetime
            if departure_datetime is not None
            else make_datetime()
        ),
        station_inventory=(
            inventory
            if inventory is not None
            else {"diesel": make_resource()}
        ),
        safety_buffer_days=safety_buffer_days,
        environment_timeline=environment_timeline,
    )


# ---------------------------------------------------------------------------
# Creation and validation
# ---------------------------------------------------------------------------


def test_mission_can_be_created():
    mission = make_mission()

    assert mission.station.id == "MAITRI"
    assert mission.vessel.id == "V001"
    assert mission.route.id == "R001"


def test_mission_starts_in_planned_status():
    mission = make_mission()

    assert mission.status == "PLANNED"


def test_negative_cargo_weight_is_rejected():
    with pytest.raises(ValueError):
        make_mission(cargo_weight_tonnes=-1.0)


def test_naive_departure_datetime_is_rejected():
    naive_datetime = datetime(2026, 12, 15, 12, 0)

    with pytest.raises(ValueError):
        make_mission(
            departure_datetime=naive_datetime,
        )


def test_negative_safety_buffer_is_rejected():
    with pytest.raises(ValueError):
        make_mission(
            safety_buffer_days=-1.0,
        )


def test_create_classmethod_returns_mission():
    mission = ResupplyMission.create(
        station=make_station(),
        vessel=make_vessel(),
        route=make_route(),
        cargo_weight_tonnes=1000.0,
        departure_datetime=make_datetime(),
        station_inventory={"diesel": make_resource()},
    )

    assert isinstance(mission, ResupplyMission)
    assert mission.status == "PLANNED"


# ---------------------------------------------------------------------------
# Initialization
# ---------------------------------------------------------------------------


def test_mission_initialization_creates_simulation_state():
    mission = make_mission()

    state = mission.initialize()

    assert state is mission.simulation_state
    assert state is not None


def test_initialization_does_not_start_mission():
    mission = make_mission()

    mission.initialize()

    assert mission.status == "PLANNED"
    assert mission.simulation_state.status == "PLANNED"


def test_simulation_datetime_before_start_equals_departure():
    mission = make_mission()

    mission.initialize()

    assert mission.simulation_datetime == make_datetime()


def test_progress_is_zero_before_start():
    mission = make_mission()

    assert mission.progress_fraction == 0.0
    assert mission.progress_percent == 0.0


def test_fuel_consumed_is_zero_before_start():
    mission = make_mission()

    assert mission.fuel_consumed_litres == 0.0


def test_current_inventory_is_available_before_start():
    mission = make_mission()

    inventory = mission.current_inventory

    assert inventory["diesel"] == 100000.0


# ---------------------------------------------------------------------------
# Starting
# ---------------------------------------------------------------------------


def test_mission_start_auto_initializes():
    mission = make_mission()

    state = mission.start()

    assert state is mission.simulation_state
    assert mission.status == "RUNNING"


def test_mission_start_sets_running_state():
    mission = make_mission()

    mission.start()

    assert mission.simulation_state.status == "running"


def test_start_is_idempotent_when_already_running():
    mission = make_mission()

    first_state = mission.start()
    second_state = mission.start()

    assert second_state is first_state
    assert mission.status == "RUNNING"


def test_simulation_datetime_after_start_equals_departure():
    mission = make_mission()

    mission.start()

    assert mission.simulation_datetime == make_datetime()


def test_vessel_position_is_available_after_start():
    mission = make_mission()

    mission.start()

    position = mission.vessel_position

    assert position is not None


# ---------------------------------------------------------------------------
# Simulation updates
# ---------------------------------------------------------------------------


def test_update_advances_simulation_datetime():
    mission = make_mission()

    mission.start()

    original_datetime = mission.simulation_datetime

    mission.update(24 * 60 * 60)

    assert mission.simulation_datetime == (
        original_datetime + timedelta(days=1)
    )


def test_update_advances_vessel_progress():
    mission = make_mission()

    mission.start()

    original_progress = mission.progress_fraction

    mission.update(24 * 60 * 60)

    assert mission.progress_fraction > original_progress


def test_progress_percent_matches_fraction():
    mission = make_mission()

    mission.start()
    mission.update(12 * 60 * 60)

    assert mission.progress_percent == pytest.approx(
        mission.progress_fraction * 100.0
    )


def test_update_consumes_fuel():
    mission = make_mission()

    mission.start()

    mission.update(24 * 60 * 60)

    assert mission.fuel_consumed_litres > 0


def test_update_reduces_inventory():
    mission = make_mission()

    mission.start()

    original_inventory = mission.current_inventory["diesel"]

    mission.update(24 * 60 * 60)

    assert mission.current_inventory["diesel"] < original_inventory


def test_negative_update_time_is_rejected():
    mission = make_mission()

    mission.start()

    with pytest.raises(ValueError):
        mission.update(-1.0)


def test_update_before_start_is_rejected():
    mission = make_mission()

    with pytest.raises(RuntimeError):
        mission.update(3600.0)


# ---------------------------------------------------------------------------
# Environment integration
# ---------------------------------------------------------------------------


def test_mission_exposes_normal_environment():
    mission = make_mission()

    mission.start()

    environment = mission.current_environment

    assert environment is not None
    assert environment.weather_severity == 0.0
    assert environment.sea_ice_severity == 0.0


def test_mission_exposes_environment_timeline_event():
    departure = make_datetime()

    timeline = EnvironmentTimeline()
    timeline.add_event(
        EnvironmentEvent(
            start_datetime=departure + timedelta(days=1),
            end_datetime=departure + timedelta(days=2),
            conditions=heavy_ice_conditions(),
            name="Heavy Sea Ice",
        )
    )

    mission = make_mission(
        environment_timeline=timeline,
    )

    mission.start()
    mission.update(24 * 60 * 60)

    assert mission.active_environment_event == "Heavy Sea Ice"


def test_mission_returns_to_default_environment_after_event():
    departure = make_datetime()

    timeline = EnvironmentTimeline()
    timeline.add_event(
        EnvironmentEvent(
            start_datetime=departure + timedelta(days=1),
            end_datetime=departure + timedelta(days=2),
            conditions=storm_conditions(),
            name="Severe Storm",
        )
    )

    mission = make_mission(
        environment_timeline=timeline,
    )

    mission.start()

    mission.update(24 * 60 * 60)
    assert mission.active_environment_event == "Severe Storm"

    mission.update(24 * 60 * 60)
    assert mission.active_environment_event is None


def test_heavy_ice_slows_mission_progress():
    departure = make_datetime()

    normal_mission = make_mission()
    ice_timeline = EnvironmentTimeline()
    ice_timeline.add_event(
        EnvironmentEvent(
            start_datetime=departure,
            end_datetime=departure + timedelta(days=2),
            conditions=heavy_ice_conditions(),
            name="Heavy Sea Ice",
        )
    )

    ice_mission = make_mission(
        environment_timeline=ice_timeline,
    )

    normal_mission.start()
    ice_mission.start()

    normal_mission.update(24 * 60 * 60)
    ice_mission.update(24 * 60 * 60)

    assert (
        ice_mission.progress_fraction
        < normal_mission.progress_fraction
    )


def test_storm_increases_fuel_consumption():
    departure = make_datetime()

    normal_mission = make_mission()

    storm_timeline = EnvironmentTimeline()
    storm_timeline.add_event(
        EnvironmentEvent(
            start_datetime=departure,
            end_datetime=departure + timedelta(days=2),
            conditions=storm_conditions(),
            name="Severe Storm",
        )
    )

    storm_mission = make_mission(
        environment_timeline=storm_timeline,
    )

    normal_mission.start()
    storm_mission.start()

    normal_mission.update(24 * 60 * 60)
    storm_mission.update(24 * 60 * 60)

    assert (
        storm_mission.fuel_consumed_litres
        > normal_mission.fuel_consumed_litres
    )


# ---------------------------------------------------------------------------
# Risk analysis
# ---------------------------------------------------------------------------


def test_mission_calculates_safety_margin():
    mission = make_mission()

    mission.start()

    margin = (
        mission.simulation_state
        .calculate_safety_margin_days()
    )

    assert margin is not None


def test_mission_reports_arrival_feasibility():
    mission = make_mission()

    mission.start()

    assert (
        mission.simulation_state.arrival_feasible
        is True
    )


def test_mission_has_arrival_risk_status():
    mission = make_mission()

    mission.start()

    assert (
        mission.simulation_state.arrival_risk_status
        in {"SAFE", "AT_RISK", "CRITICAL", "UNKNOWN"}
    )


def test_resource_risk_contains_diesel():
    mission = make_mission()

    mission.start()

    risk = (
        mission.simulation_state
        .get_resource_risk()
    )

    assert "diesel" in risk

    diesel = risk["diesel"]

    assert diesel["resource_name"] == "Diesel"
    assert diesel["current_quantity"] > 0
    assert diesel["daily_consumption"] == 2000.0
    assert diesel["critical_date"] is not None
    assert diesel["latest_safe_arrival"] is not None


def test_resource_risk_detects_critical_arrival():
    mission = make_mission()

    mission.start()

    mission.simulation_state.estimated_arrival = (
        mission.simulation_state.latest_safe_arrival
        + timedelta(days=2)
    )

    risk = (
        mission.simulation_state
        .get_resource_risk()
    )

    assert risk["diesel"]["status"] == "CRITICAL"


def test_resource_risk_detects_safe_arrival():
    mission = make_mission()

    mission.start()

    mission.simulation_state.estimated_arrival = (
        mission.simulation_state.latest_safe_arrival
        - timedelta(days=5)
    )

    risk = (
        mission.simulation_state
        .get_resource_risk()
    )

    assert risk["diesel"]["status"] == "SAFE"


def test_risk_summary_is_exposed_in_state():
    mission = make_mission()

    mission.start()

    state = mission.get_state()

    assert "risk" in state
    assert "overall_status" in state["risk"]
    assert "arrival_status" in state["risk"]
    assert "resources" in state["risk"]
    assert "diesel" in state["risk"]["resources"]


def test_risk_summary_becomes_critical_when_arrival_is_late():
    mission = make_mission()

    mission.start()

    mission.simulation_state.estimated_arrival = (
        mission.simulation_state.latest_safe_arrival
        + timedelta(days=2)
    )

    summary = (
        mission.simulation_state
        .get_risk_summary()
    )

    assert summary["overall_status"] == "CRITICAL"
    assert summary["arrival_status"] == "CRITICAL"
    assert summary["arrival_feasible"] is False


# ---------------------------------------------------------------------------
# State export
# ---------------------------------------------------------------------------


def test_planned_mission_state_is_serializable():
    mission = make_mission()

    state = mission.get_state()

    assert isinstance(state, dict)
    assert state["status"] == "PLANNED"
    assert state["station"]["id"] == "MAITRI"
    assert state["vessel"]["id"] == "V001"
    assert state["route"]["id"] == "R001"


def test_running_mission_state_contains_mission_information():
    mission = make_mission()

    mission.start()

    state = mission.get_state()

    assert "mission" in state
    assert state["mission"]["cargo_weight_tonnes"] == 1000.0
    assert state["mission"]["status"] == "RUNNING"


def test_state_contains_station_information():
    mission = make_mission()

    mission.start()

    state = mission.get_state()

    assert state["station"]["id"] == "MAITRI"
    assert state["station"]["name"] == "Maitri"


def test_state_contains_vessel_information():
    mission = make_mission()

    mission.start()

    state = mission.get_state()

    assert state["vessel"]["id"] == "V001"
    assert state["vessel"]["name"] == "Swift Arctic"


def test_state_contains_route_information():
    mission = make_mission()

    mission.start()

    state = mission.get_state()

    assert state["route"]["id"] == "R001"
    assert state["route"]["name"] == mission.route.name