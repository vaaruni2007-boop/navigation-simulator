# tests/test_inventory.py
"""
Pytest suite for ``engine.inventory`` utilities.

Scenarios covered:
1. Normal consumption – days until safety threshold.
2. Inventory already below threshold – immediate critical state.
3. Zero daily consumption – never depletes.
4. Inventory exactly at safety threshold – critical immediately.
5. Projection of inventory on a future date (including clamping at zero).
6. Required‑resupply calculation and post‑resupply inventory.
"""

import pytest
from datetime import datetime, timezone, timedelta

from engine.inventory import ResourceInventory


# ----------------------------------------------------------------------
# Scenario 1 – standard consumption
# ----------------------------------------------------------------------
def test_days_until_threshold_standard() -> None:
    inv = ResourceInventory(
        resource_name="diesel",
        current_quantity=100_000.0,
        unit="litres",
        daily_consumption=1_800.0,
        minimum_safety_threshold=25_000.0,
        required_resupply_quantity=0.0,
    )
    # (100000 - 25000) / 1800 = 41.666666...
    expected_days = (100_000.0 - 25_000.0) / 1_800.0
    assert inv.calculate_days_until_threshold() == pytest.approx(expected_days)


# ----------------------------------------------------------------------
# Scenario 2 – inventory already below threshold
# ----------------------------------------------------------------------
def test_critical_immediate_below_threshold() -> None:
    now = datetime.now(timezone.utc)
    inv = ResourceInventory(
        resource_name="diesel",
        current_quantity=10_000.0,
        unit="litres",
        daily_consumption=500.0,
        minimum_safety_threshold=20_000.0,
        required_resupply_quantity=0.0,
    )
    # Days until threshold should be zero
    assert inv.calculate_days_until_threshold() == pytest.approx(0.0)

    crit_date = inv.calculate_critical_date(now)
    # Critical date should be exactly 'now' (no offset)
    assert crit_date == now


# ----------------------------------------------------------------------
# Scenario 3 – zero daily consumption (non‑depleting resource)
# ----------------------------------------------------------------------
def test_never_depletes_zero_consumption() -> None:
    now = datetime.now(timezone.utc)
    inv = ResourceInventory(
        resource_name="food",
        current_quantity=5_000.0,
        unit="kg",
        daily_consumption=0.0,
        minimum_safety_threshold=1_000.0,
        required_resupply_quantity=0.0,
    )
    # Days until threshold is infinite
    assert inv.calculate_days_until_threshold() == float("inf")

    # Critical date should be None for non‑depleting resource
    assert inv.calculate_critical_date(now) is None

    # Inventory projection any number of days ahead stays constant
    future = now + timedelta(days=365)
    assert inv.calculate_inventory_on_date(now, future) == pytest.approx(5_000.0)


# ----------------------------------------------------------------------
# Scenario 4 – inventory exactly at safety threshold
# ----------------------------------------------------------------------
def test_critical_exact_threshold() -> None:
    now = datetime.now(timezone.utc)
    inv = ResourceInventory(
        resource_name="diesel",
        current_quantity=25_000.0,
        unit="litres",
        daily_consumption=1_800.0,
        minimum_safety_threshold=25_000.0,
        required_resupply_quantity=0.0,
    )
    # Zero days remaining
    assert inv.calculate_days_until_threshold() == pytest.approx(0.0)

    # Critical datetime should be 'now'
    assert inv.calculate_critical_date(now) == now


# ----------------------------------------------------------------------
# Scenario 5 – future inventory projection with clamping at zero
# ----------------------------------------------------------------------
def test_inventory_projection_clamped_to_zero() -> None:
    now = datetime.now(timezone.utc)
    inv = ResourceInventory(
        resource_name="diesel",
        current_quantity=5_000.0,
        unit="litres",
        daily_consumption=1_000.0,
        minimum_safety_threshold=1_000.0,
        required_resupply_quantity=0.0,
    )
    # 10 days ahead would deplete to negative; expect zero after clamping
    target = now + timedelta(days=10)
    assert inv.calculate_inventory_on_date(now, target) == pytest.approx(0.0)

    # 3 days ahead: 5_000 - 1_000*3 = 2_000
    target_mid = now + timedelta(days=3)
    assert inv.calculate_inventory_on_date(now, target_mid) == pytest.approx(2_000.0)


# ----------------------------------------------------------------------
# Scenario 6 – required resupply quantity and post‑resupply inventory
# ----------------------------------------------------------------------
def test_required_resupply_and_post_inventory() -> None:
    inv = ResourceInventory(
        resource_name="diesel",
        current_quantity=40_000.0,
        unit="litres",
        daily_consumption=1_800.0,
        minimum_safety_threshold=25_000.0,
        required_resupply_quantity=60_000.0,
    )
    # Required resupply should be returned unchanged
    assert inv.calculate_required_resupply() == pytest.approx(60_000.0)

    # After resupply inventory = current + required
    expected_after = 40_000.0 + 60_000.0
    assert inv.calculate_inventory_after_resupply() == pytest.approx(expected_after)
    