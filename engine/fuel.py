"""engine.fuel
==============

Utility functions for fuel consumption, fuel cost, and capacity validation
used by the Antarctic Maritime Resupply Navigation Simulator.

The module is deliberately isolated from inventory, cost, and optimization
logic so that it can be extended later (e.g., with weather or sea‑ice modifiers)
without affecting other parts of the code base.
"""

from __future__ import annotations

from typing import Final


# ---------------------------------------------------------------------------
# Validation helpers
# ---------------------------------------------------------------------------

def _require_positive(value: float, name: str) -> None:
    """Raise ``ValueError`` if *value* is not strictly positive."""
    if value <= 0:
        raise ValueError(f"{name} must be > 0 (got {value!r})")


# ---------------------------------------------------------------------------
# Core fuel calculations
# ---------------------------------------------------------------------------

def calculate_fuel_consumption(
    voyage_days: float,
    fuel_consumption_litres_per_day: float,
) -> float:
    """
    Compute the total fuel required for a voyage.

    Parameters
    ----------
    voyage_days : float
        Duration of the voyage in days. Must be > 0.
    fuel_consumption_litres_per_day : float
        Vessel's daily fuel consumption (litres per day). Must be > 0.

    Returns
    -------
    float
        Total fuel required in litres.

    Raises
    ------
    ValueError
        If any argument is non‑positive.
    """
    _require_positive(voyage_days, "voyage_days")
    _require_positive(fuel_consumption_litres_per_day, "fuel_consumption_litres_per_day")
    return voyage_days * fuel_consumption_litres_per_day


def calculate_fuel_cost(
    fuel_litres: float,
    fuel_cost_per_litre: float,
) -> float:
    """
    Compute the monetary cost of a given amount of fuel.

    Parameters
    ----------
    fuel_litres : float
        Quantity of fuel in litres. Must be > 0.
    fuel_cost_per_litre : float
        Unit price of fuel (currency units per litre). Must be > 0.

    Returns
    -------
    float
        Total fuel cost.

    Raises
    ------
    ValueError
        If any argument is non‑positive.
    """
    _require_positive(fuel_litres, "fuel_litres")
    _require_positive(fuel_cost_per_litre, "fuel_cost_per_litre")
    return fuel_litres * fuel_cost_per_litre


def validate_fuel_capacity(
    fuel_required: float,
    fuel_capacity: float,
) -> bool:
    """
    Verify that a vessel can hold the required amount of fuel.

    Parameters
    ----------
    fuel_required : float
        Fuel needed for the planned voyage (litres). Must be > 0.
    fuel_capacity : float
        Maximum fuel that the vessel can carry (litres). Must be > 0.

    Returns
    -------
    bool
        ``True`` if ``fuel_required`` fits within ``fuel_capacity``;
        ``False`` otherwise.

    Raises
    ------
    ValueError
        If any argument is non‑positive.
    """
    _require_positive(fuel_required, "fuel_required")
    _require_positive(fuel_capacity, "fuel_capacity")
    return fuel_required <= fuel_capacity


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

__all__: Final = [
    "calculate_fuel_consumption",
    "calculate_fuel_cost",
    "validate_fuel_capacity",
]