from __future__ import annotations

from decimal import Decimal


def calculate_fuel_consumption(
    voyage_days: float,
    fuel_consumption_litres_per_day: float,
) -> float:
    """
    Calculate total fuel consumed during a voyage.
    """

    if voyage_days <= 0:
        raise ValueError("voyage_days must be positive")

    if fuel_consumption_litres_per_day <= 0:
        raise ValueError(
            "fuel_consumption_litres_per_day must be positive"
        )

    return (
        voyage_days
        * fuel_consumption_litres_per_day
    )


def calculate_fuel_cost(
    fuel_litres: float,
    fuel_cost_per_litre: Decimal | float,
) -> Decimal:
    """Calculate fuel cost."""

    if fuel_litres <= 0:
        raise ValueError("fuel_litres must be positive")

    fuel_cost = Decimal(str(fuel_cost_per_litre))

    if fuel_cost <= 0:
        raise ValueError(
            "fuel_cost_per_litre must be positive"
        )

    return (
        Decimal(str(fuel_litres))
        * fuel_cost
    )


def validate_fuel_capacity(
    fuel_required: float,
    fuel_capacity: float,
) -> bool:
    """Return whether required fuel fits within vessel capacity."""

    if fuel_required <= 0:
        raise ValueError("fuel_required must be positive")

    if fuel_capacity <= 0:
        raise ValueError("fuel_capacity must be positive")

    return fuel_required <= fuel_capacity


__all__ = [
    "calculate_fuel_consumption",
    "calculate_fuel_cost",
    "validate_fuel_capacity",
]