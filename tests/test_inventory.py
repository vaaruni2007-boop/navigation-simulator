from datetime import datetime, timezone

import pytest

from engine.inventory import (
    calculate_critical_date,
    calculate_remaining_inventory,
    calculate_resource_depletion_days,
)
from engine.models import ResourceInventory


def make_inventory(
    current_quantity=1000.0,
    daily_consumption=100.0,
    minimum_safety_threshold=200.0,
):
    return ResourceInventory(
        resource_name="diesel",
        current_quantity=current_quantity,
        unit="litres",
        daily_consumption=daily_consumption,
        minimum_safety_threshold=minimum_safety_threshold,
        required_resupply_quantity=500.0,
    )


def test_resource_depletion_days():
    inventory = make_inventory(
        current_quantity=1000.0,
        daily_consumption=100.0,
    )

    days = calculate_resource_depletion_days(
        inventory
    )

    assert days == pytest.approx(10.0)


def test_zero_consumption_has_no_depletion():
    inventory = make_inventory(
        current_quantity=1000.0,
        daily_consumption=0.0,
    )

    days = calculate_resource_depletion_days(
        inventory
    )

    assert days is None


def test_remaining_inventory():
    inventory = make_inventory(
        current_quantity=1000.0,
        daily_consumption=100.0,
    )

    remaining = calculate_remaining_inventory(
        inventory=inventory,
        days_elapsed=3.0,
    )

    assert remaining == pytest.approx(
        700.0
    )


def test_remaining_inventory_does_not_go_negative():
    inventory = make_inventory(
        current_quantity=1000.0,
        daily_consumption=100.0,
    )

    remaining = calculate_remaining_inventory(
        inventory=inventory,
        days_elapsed=20.0,
    )

    assert remaining == pytest.approx(
        0.0
    )


def test_critical_date():
    inventory = make_inventory(
        current_quantity=1000.0,
        daily_consumption=100.0,
        minimum_safety_threshold=200.0,
    )

    reference = datetime(
        2026,
        12,
        1,
        tzinfo=timezone.utc,
    )

    critical_date = calculate_critical_date(
        inventory=inventory,
        reference_datetime=reference,
    )

    # 1000 -> 200 at 100/day = 8 days.
    assert critical_date == datetime(
        2026,
        12,
        9,
        tzinfo=timezone.utc,
    )


def test_inventory_already_below_threshold():
    inventory = make_inventory(
        current_quantity=100.0,
        daily_consumption=100.0,
        minimum_safety_threshold=200.0,
    )

    reference = datetime(
        2026,
        12,
        1,
        tzinfo=timezone.utc,
    )

    critical_date = calculate_critical_date(
        inventory=inventory,
        reference_datetime=reference,
    )

    assert critical_date == reference


def test_negative_daily_consumption_is_rejected():
    with pytest.raises(ValueError):
        make_inventory(
            daily_consumption=-10.0
        )