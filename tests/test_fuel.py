# tests/test_fuel.py
"""
Pytest suite for ``engine.fuel`` utilities.

The tests cover:
1. Fuel consumption = voyage_days × daily consumption.
2. Fuel cost = litres × price_per_litre.
3. Capacity validation (fits / does not fit).
4. Proper handling of zero and negative inputs (ValueError).
"""

import pytest
from engine.fuel import (
    calculate_fuel_consumption,
    calculate_fuel_cost,
    validate_fuel_capacity,
)


# ----------------------------------------------------------------------
# 1. Normal calculations
# ----------------------------------------------------------------------
def test_calculate_fuel_consumption_basic() -> None:
    """Fuel consumption should be voyage_days * consumption_per_day."""
    voyage_days = 10.0
    consumption_per_day = 200.0  # litres/day
    expected = voyage_days * consumption_per_day
    assert calculate_fuel_consumption(voyage_days, consumption_per_day) == pytest.approx(
        expected
    )


def test_calculate_fuel_cost_basic() -> None:
    """Fuel cost should be litres * price_per_litre."""
    fuel_litres = 500.0
    price_per_litre = 1.5  # currency units / litre
    expected = fuel_litres * price_per_litre
    assert calculate_fuel_cost(fuel_litres, price_per_litre) == pytest.approx(expected)


def test_validate_fuel_capacity_true() -> None:
    """validate_fuel_capacity should return True when required ≤ capacity."""
    required = 1000.0
    capacity = 1500.0
    assert validate_fuel_capacity(required, capacity) is True


def test_validate_fuel_capacity_false() -> None:
    """validate_fuel_capacity should return False when required > capacity."""
    required = 2000.0
    capacity = 1500.0
    assert validate_fuel_capacity(required, capacity) is False


# ----------------------------------------------------------------------
# 2. Edge‑case validation (zero / negative inputs)
# ----------------------------------------------------------------------
@pytest.mark.parametrize(
    "func, args",
    [
        (calculate_fuel_consumption, (0.0, 100.0)),   # zero voyage_days
        (calculate_fuel_consumption, (10.0, 0.0)),    # zero consumption per day
        (calculate_fuel_cost, (0.0, 1.0)),            # zero fuel litres
        (calculate_fuel_cost, (100.0, 0.0)),          # zero price per litre
        (validate_fuel_capacity, (0.0, 1000.0)),      # zero required fuel
        (validate_fuel_capacity, (500.0, 0.0)),       # zero capacity
    ],
)
def test_zero_inputs_raise_value_error(func, args) -> None:
    """All public helpers must raise ValueError for zero-valued arguments."""
    with pytest.raises(ValueError):
        func(*args)


@pytest.mark.parametrize(
    "func, args",
    [
        (calculate_fuel_consumption, (-5.0, 100.0)),   # negative voyage_days
        (calculate_fuel_consumption, (10.0, -20.0)),   # negative consumption per day
        (calculate_fuel_cost, (-10.0, 1.0)),           # negative fuel litres
        (calculate_fuel_cost, (100.0, -2.0)),          # negative price per litre
        (validate_fuel_capacity, (-100.0, 1000.0)),    # negative required fuel
        (validate_fuel_capacity, (500.0, -200.0)),     # negative capacity
    ],
)
def test_negative_inputs_raise_value_error(func, args) -> None:
    """All public helpers must raise ValueError for negative arguments."""
    with pytest.raises(ValueError):
        func(*args)