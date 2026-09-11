from datetime import datetime, timezone

import pytest

from engine.resupply import (
    build_resource_requirement,
    build_resupply_scenario,
    calculate_required_resupply_quantity,
)
from engine.models import (
    ResourceInventory,
    Station,
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


def make_resource(
    name="Diesel",
    current=100000.0,
    consumption=2000.0,
    threshold=20000.0,
):
    return ResourceInventory(
        resource_name=name,
        current_quantity=current,
        unit="litres",
        daily_consumption=consumption,
        minimum_safety_threshold=threshold,
        required_resupply_quantity=0.0,
    )


def make_station():
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


def test_required_quantity_when_above_threshold():
    resource = make_resource()

    result = calculate_required_resupply_quantity(resource)

    assert result == 0.0


def test_required_quantity_when_below_threshold():
    resource = make_resource(
        current=10000.0,
        threshold=20000.0,
    )

    result = calculate_required_resupply_quantity(resource)

    assert result == 10000.0


def test_resource_requirement_calculates_critical_date():
    resource = make_resource()

    result = build_resource_requirement(
        resource,
        make_datetime(),
    )

    assert result.predicted_critical_date is not None
    assert result.days_until_threshold == 40.0


def test_resource_requirement_calculates_safe_arrival():
    resource = make_resource()

    result = build_resource_requirement(
        resource,
        make_datetime(),
        safety_buffer_days=3.0,
    )

    assert result.latest_safe_arrival is not None
    assert (
        result.latest_safe_arrival
        == result.predicted_critical_date
        - __import__("datetime").timedelta(days=3)
    )


def test_resource_is_not_urgent_when_far_from_threshold():
    resource = make_resource(
        current=100000.0,
        consumption=2000.0,
        threshold=20000.0,
    )

    result = build_resource_requirement(
        resource,
        make_datetime(),
        safety_buffer_days=3.0,
    )

    assert result.is_urgent is False


def test_resource_is_urgent_when_near_threshold():
    resource = make_resource(
        current=24000.0,
        consumption=2000.0,
        threshold=20000.0,
    )

    result = build_resource_requirement(
        resource,
        make_datetime(),
        safety_buffer_days=3.0,
    )

    assert result.days_until_threshold == 2.0
    assert result.is_urgent is True


def test_resupply_scenario_contains_all_resources():
    resources = [
        make_resource(
            name="Diesel",
        ),
        make_resource(
            name="Water",
            current=50000,
            consumption=1000,
            threshold=10000,
        ),
    ]

    scenario = build_resupply_scenario(
        make_station(),
        resources,
        make_datetime(),
    )

    assert scenario.total_resource_types == 2
    assert scenario.get_requirement("Diesel") is not None
    assert scenario.get_requirement("Water") is not None


def test_resupply_scenario_sorts_by_urgency():
    resources = [
        make_resource(
            name="Diesel",
            current=100000,
            consumption=2000,
            threshold=20000,
        ),
        make_resource(
            name="Water",
            current=22000,
            consumption=2000,
            threshold=20000,
        ),
    ]

    scenario = build_resupply_scenario(
        make_station(),
        resources,
        make_datetime(),
    )

    assert scenario.requirements[0].resource_name == "Water"
    assert scenario.requirements[1].resource_name == "Diesel"


def test_scenario_identifies_urgent_resources():
    resources = [
        make_resource(
            name="Water",
            current=24000,
            consumption=2000,
            threshold=20000,
        ),
    ]

    scenario = build_resupply_scenario(
        make_station(),
        resources,
        make_datetime(),
        safety_buffer_days=3.0,
    )

    assert scenario.has_urgent_requirements is True
    assert len(scenario.urgent_resources) == 1
    assert scenario.urgent_resources[0].resource_name == "Water"


def test_scenario_to_dict_is_serializable():
    resources = [
        make_resource(),
    ]

    scenario = build_resupply_scenario(
        make_station(),
        resources,
        make_datetime(),
    )

    result = scenario.to_dict()

    assert isinstance(result, dict)
    assert result["station_id"] == "MAITRI"
    assert result["station_name"] == "Maitri"
    assert isinstance(result["generated_at"], str)
    assert len(result["requirements"]) == 1
    assert result["requirements"][0]["resource_name"] == "Diesel"
