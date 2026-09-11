"""engine.cost
==============

Utility functions for financial cost calculations used by the Antarctic Maritime
Resupply Navigation Simulator.

All monetary values are handled with :class:`decimal.Decimal` to preserve
precision. The module is deliberately free of any optimisation logic – it
simply reports costs based on the inputs supplied by the calling code.
"""

from __future__ import annotations

from decimal import Decimal, InvalidOperation, getcontext
from typing import Final

# Use a reasonable precision for currency calculations (2‑decimal places)
getcontext().prec = 28  # sufficient for large sums; rounding is left to callers


# ---------------------------------------------------------------------------
# Validation helpers
# ---------------------------------------------------------------------------

def _require_positive_decimal(value: float | Decimal, name: str) -> Decimal:
    """
    Convert *value* to ``Decimal`` and ensure it is strictly positive.

    Raises
    ------
    ValueError
        If *value* is not positive or cannot be converted to ``Decimal``.
    """
    try:
        dec_value = Decimal(str(value))
    except (InvalidOperation, TypeError) as exc:
        raise ValueError(f"{name} must be a numeric value") from exc

    if dec_value <= 0:
        raise ValueError(f"{name} must be > 0 (got {value!r})")
    return dec_value


def _require_positive_float(value: float, name: str) -> float:
    """
    Ensure a float is strictly positive.

    Raises
    ------
    ValueError
        If *value* is not positive.
    """
    if value <= 0:
        raise ValueError(f"{name} must be > 0 (got {value!r})")
    return value


# ---------------------------------------------------------------------------
# Core cost calculations
# ---------------------------------------------------------------------------

def calculate_operating_cost(
    voyage_days: float,
    operating_cost_per_day: float,
) -> Decimal:
    """
    Compute the vessel operating cost for a voyage.

    Parameters
    ----------
    voyage_days : float
        Duration of the voyage in days. Must be > 0.
    operating_cost_per_day : float
        Daily operating expense (currency units per day). Must be > 0.

    Returns
    -------
    Decimal
        Total operating cost for the voyage.

    Raises
    ------
    ValueError
        If any argument is non‑positive.
    """
    days = _require_positive_float(voyage_days, "voyage_days")
    daily_cost = _require_positive_decimal(operating_cost_per_day, "operating_cost_per_day")
    return daily_cost * Decimal(str(days))


def calculate_total_cost(
    fuel_cost: Decimal,
    operating_cost: Decimal,
) -> Decimal:
    """
    Sum the fuel cost and vessel operating cost to obtain the total voyage cost.

    Parameters
    ----------
    fuel_cost : Decimal
        Monetary cost of the fuel required for the voyage. Must be > 0.
    operating_cost : Decimal
        Vessel operating cost for the voyage. Must be > 0.

    Returns
    -------
    Decimal
        Combined total cost.

    Raises
    ------
    ValueError
        If any argument is non‑positive.
    """
    fuel = _require_positive_decimal(fuel_cost, "fuel_cost")
    op = _require_positive_decimal(operating_cost, "operating_cost")
    return fuel + op


def calculate_cost_per_tonne(
    total_cost: Decimal,
    cargo_weight_tonnes: float,
) -> Decimal:
    """
    Derive the cost per tonne of cargo delivered.

    Parameters
    ----------
    total_cost : Decimal
        Total monetary cost of the voyage. Must be > 0.
    cargo_weight_tonnes : float
        Cargo mass to be delivered (tonnes). Must be > 0.

    Returns
    -------
    Decimal
        Cost per tonne (currency units per tonne).

    Raises
    ------
    ValueError
        If any argument is non‑positive.
    """
    cost = _require_positive_decimal(total_cost, "total_cost")
    weight = _require_positive_float(cargo_weight_tonnes, "cargo_weight_tonnes")
    return cost / Decimal(str(weight))


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

__all__: Final = [
    "calculate_operating_cost",
    "calculate_total_cost",
    "calculate_cost_per_tonne",
]