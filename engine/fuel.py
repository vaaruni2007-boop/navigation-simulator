from __future__ import annotations

from numbers import Real


def _validate_non_negative(value: float, name: str) -> float:
    if not isinstance(value, Real):
        raise TypeError(f"{name} must be a number.")
    if value < 0:
        raise ValueError(f"{name} cannot be negative.")
    return float(value)


def calculate_fuel_consumption(
    duration_days: float,
    consumption_litres_per_day: float | None = None,
    fuel_consumption_litres_per_day: float | None = None,
) -> float:
    """
    Calculate total fuel consumption for a voyage.

    Supports both:
        consumption_litres_per_day
        fuel_consumption_litres_per_day

    The first name is the canonical/test-facing API.
    """

    duration_days = _validate_non_negative(duration_days, "duration_days")

    if consumption_litres_per_day is None:
        consumption_litres_per_day = fuel_consumption_litres_per_day

    if consumption_litres_per_day is None:
        raise TypeError(
            "consumption_litres_per_day must be provided."
        )

    consumption_litres_per_day = _validate_non_negative(
        consumption_litres_per_day,
        "consumption_litres_per_day",
    )

    return duration_days * consumption_litres_per_day


def calculate_fuel_cost(
    fuel_litres: float,
    cost_per_litre: float | None = None,
    fuel_cost_per_litre: float | None = None,
) -> float:
    """
    Calculate fuel cost.

    Supports both cost_per_litre and fuel_cost_per_litre.
    """

    fuel_litres = _validate_non_negative(fuel_litres, "fuel_litres")

    if cost_per_litre is None:
        cost_per_litre = fuel_cost_per_litre

    if cost_per_litre is None:
        raise TypeError("cost_per_litre must be provided.")

    cost_per_litre = _validate_non_negative(
        cost_per_litre,
        "cost_per_litre",
    )

    return fuel_litres * cost_per_litre


def validate_fuel_capacity(
    fuel_required_litres: float,
    fuel_capacity_litres: float,
) -> bool:
    """
    Return True when the vessel has sufficient fuel capacity.
    """

    fuel_required_litres = _validate_non_negative(
        fuel_required_litres,
        "fuel_required_litres",
    )

    fuel_capacity_litres = _validate_non_negative(
        fuel_capacity_litres,
        "fuel_capacity_litres",
    )

    return fuel_required_litres <= fuel_capacity_litres