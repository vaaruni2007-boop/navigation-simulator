from __future__ import annotations

from decimal import Decimal


def _require_non_negative_decimal(
    value: Decimal | float | int,
    name: str,
) -> Decimal:
    result = Decimal(str(value))

    if result < 0:
        raise ValueError(
            f"{name} must be non-negative"
        )

    return result


def _require_positive_float(
    value: float,
    name: str,
) -> float:
    if value <= 0:
        raise ValueError(
            f"{name} must be positive"
        )

    return float(value)


def calculate_operating_cost(
    voyage_days: float,
    operating_cost_per_day: float,
) -> Decimal:
    """Calculate total operating cost."""

    voyage_days = _require_positive_float(
        voyage_days,
        "voyage_days",
    )

    operating_cost = _require_non_negative_decimal(
        operating_cost_per_day,
        "operating_cost_per_day",
    )

    return (
        Decimal(str(voyage_days))
        * operating_cost
    )


def calculate_total_cost(
    fuel_cost: Decimal | float,
    operating_cost: Decimal | float,
) -> Decimal:
    """Calculate total voyage cost."""

    fuel = _require_non_negative_decimal(
        fuel_cost,
        "fuel_cost",
    )

    operating = _require_non_negative_decimal(
        operating_cost,
        "operating_cost",
    )

    return fuel + operating


def calculate_cost_per_tonne(
    total_cost: Decimal | float,
    cargo_weight_tonnes: float,
) -> Decimal:
    """Calculate voyage cost per tonne of cargo."""

    cost = _require_non_negative_decimal(
        total_cost,
        "total_cost",
    )

    cargo_weight_tonnes = _require_positive_float(
        cargo_weight_tonnes,
        "cargo_weight_tonnes",
    )

    return cost / Decimal(str(cargo_weight_tonnes))


__all__ = [
    "calculate_operating_cost",
    "calculate_total_cost",
    "calculate_cost_per_tonne",
]