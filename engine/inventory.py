from __future__ import annotations

from datetime import datetime, timedelta
from math import inf

from .models import ResourceInventory


def calculate_resource_depletion_days(
    inventory: ResourceInventory,
) -> float | None:
    """
    Calculate days until the resource is completely depleted.

    Returns None when daily consumption is zero.
    """

    if inventory.daily_consumption < 0:
        raise ValueError(
            "daily_consumption must be non-negative"
        )

    if inventory.current_quantity <= 0:
        return 0.0

    if inventory.daily_consumption == 0:
        return None

    return (
        inventory.current_quantity
        / inventory.daily_consumption
    )


def calculate_days_until_threshold(
    inventory: ResourceInventory,
) -> float | None:
    """Calculate days until inventory reaches its safety threshold."""

    if inventory.daily_consumption < 0:
        raise ValueError(
            "daily_consumption must be non-negative"
        )

    if inventory.current_quantity <= inventory.minimum_safety_threshold:
        return 0.0

    if inventory.daily_consumption == 0:
        return None

    return (
        inventory.current_quantity
        - inventory.minimum_safety_threshold
    ) / inventory.daily_consumption


def calculate_remaining_inventory(
    inventory: ResourceInventory,
    days_elapsed: float,
) -> float:
    """Calculate inventory remaining after elapsed days."""

    if days_elapsed < 0:
        raise ValueError(
            "days_elapsed must be non-negative"
        )

    remaining = (
        inventory.current_quantity
        - inventory.daily_consumption * days_elapsed
    )

    return max(0.0, remaining)


def calculate_critical_date(
    inventory: ResourceInventory,
    reference_datetime: datetime,
) -> datetime | None:
    """Calculate when inventory reaches its safety threshold."""

    if reference_datetime.tzinfo is None:
        raise ValueError(
            "reference_datetime must be timezone-aware"
        )

    days_until_threshold = calculate_days_until_threshold(
        inventory
    )

    if days_until_threshold is None:
        return None

    return reference_datetime + timedelta(
        days=days_until_threshold
    )


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
    """Return configured required resupply quantity."""

    return inventory.required_resupply_quantity


def calculate_inventory_after_resupply(
    inventory: ResourceInventory,
) -> float:
    """Calculate inventory after configured resupply."""

    return (
        inventory.current_quantity
        + inventory.required_resupply_quantity
    )


# Backward-compatible aliases.
calculate_days_until_depletion = calculate_resource_depletion_days


__all__ = [
    "calculate_resource_depletion_days",
    "calculate_days_until_threshold",
    "calculate_days_until_depletion",
    "calculate_remaining_inventory",
    "calculate_critical_date",
    "calculate_inventory_on_date",
    "calculate_required_resupply",
    "calculate_inventory_after_resupply",
    "ResourceInventory",
]