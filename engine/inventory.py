from __future__ import annotations

from datetime import datetime, timedelta
from math import inf

from .models import ResourceInventory


def calculate_days_until_threshold(
    inventory: ResourceInventory,
) -> float:
    """Calculate days until inventory reaches its safety threshold."""

    if inventory.current_quantity <= inventory.minimum_safety_threshold:
        return 0.0

    if inventory.daily_consumption == 0:
        return inf

    quantity_above_threshold = (
        inventory.current_quantity
        - inventory.minimum_safety_threshold
    )

    return quantity_above_threshold / inventory.daily_consumption


def calculate_critical_date(
    inventory: ResourceInventory,
    current_datetime: datetime,
) -> datetime | None:
    """Calculate when inventory reaches its minimum safety threshold."""

    if current_datetime.tzinfo is None:
        raise ValueError(
            "current_datetime must be timezone-aware"
        )

    days_until_threshold = calculate_days_until_threshold(
        inventory
    )

    if days_until_threshold == inf:
        return None

    return current_datetime + timedelta(
        days=days_until_threshold
    )


def calculate_remaining_inventory(
    inventory: ResourceInventory,
    elapsed_days: float,
) -> float:
    """
    Calculate remaining inventory after a number of elapsed days.

    Inventory is never allowed to fall below zero.
    """

    if elapsed_days < 0:
        raise ValueError(
            "elapsed_days must be non-negative"
        )

    remaining = (
        inventory.current_quantity
        - inventory.daily_consumption * elapsed_days
    )

    return max(0.0, remaining)


def calculate_inventory_on_date(
    inventory: ResourceInventory,
    current_datetime: datetime,
    target_datetime: datetime,
) -> float:
    """Project inventory quantity at a future datetime."""

    if current_datetime.tzinfo is None:
        raise ValueError(
            "current_datetime must be timezone-aware"
        )

    if target_datetime.tzinfo is None:
        raise ValueError(
            "target_datetime must be timezone-aware"
        )

    if target_datetime <= current_datetime:
        return inventory.current_quantity

    elapsed_days = (
        target_datetime - current_datetime
    ).total_seconds() / 86400.0

    return calculate_remaining_inventory(
        inventory,
        elapsed_days,
    )


def calculate_required_resupply(
    inventory: ResourceInventory,
) -> float:
    """Return the configured required resupply quantity."""

    return inventory.required_resupply_quantity


def calculate_inventory_after_resupply(
    inventory: ResourceInventory,
) -> float:
    """Calculate inventory after configured resupply arrives."""

    return (
        inventory.current_quantity
        + inventory.required_resupply_quantity
    )


__all__ = [
    "calculate_days_until_threshold",
    "calculate_remaining_inventory",
    "calculate_critical_date",
    "calculate_inventory_on_date",
    "calculate_required_resupply",
    "calculate_inventory_after_resupply",
    "ResourceInventory",
]