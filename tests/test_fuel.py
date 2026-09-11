import pytest

from engine.fuel import (
    calculate_fuel_consumption,
    calculate_fuel_cost,
    validate_fuel_capacity,
)


def test_calculate_fuel_consumption():
    fuel = calculate_fuel_consumption(
        duration_days=10.0,
        consumption_litres_per_day=1000.0,
    )

    assert fuel == pytest.approx(
        10_000.0
    )


def test_zero_duration_requires_zero_fuel():
    fuel = calculate_fuel_consumption(
        duration_days=0.0,
        consumption_litres_per_day=1000.0,
    )

    assert fuel == pytest.approx(0.0)


def test_negative_duration_is_rejected():
    with pytest.raises(ValueError):
        calculate_fuel_consumption(
            duration_days=-1.0,
            consumption_litres_per_day=1000.0,
        )


def test_negative_consumption_is_rejected():
    with pytest.raises(ValueError):
        calculate_fuel_consumption(
            duration_days=10.0,
            consumption_litres_per_day=-100.0,
        )


def test_calculate_fuel_cost():
    cost = calculate_fuel_cost(
        fuel_litres=10_000.0,
        cost_per_litre=2.0,
    )

    assert cost == pytest.approx(
        20_000.0
    )


def test_zero_fuel_cost():
    assert calculate_fuel_cost(
        fuel_litres=0.0,
        cost_per_litre=2.0,
    ) == pytest.approx(0.0)


def test_negative_fuel_cost_is_rejected():
    with pytest.raises(ValueError):
        calculate_fuel_cost(
            fuel_litres=100.0,
            cost_per_litre=-1.0,
        )


def test_validate_fuel_capacity_success():
    assert validate_fuel_capacity(
        fuel_required_litres=50_000.0,
        fuel_capacity_litres=100_000.0,
    ) is True


def test_validate_fuel_capacity_exact_limit():
    assert validate_fuel_capacity(
        fuel_required_litres=100_000.0,
        fuel_capacity_litres=100_000.0,
    ) is True


def test_validate_fuel_capacity_failure():
    assert validate_fuel_capacity(
        fuel_required_litres=150_000.0,
        fuel_capacity_litres=100_000.0,
    ) is False


def test_negative_fuel_requirement_is_rejected():
    with pytest.raises(ValueError):
        validate_fuel_capacity(
            fuel_required_litres=-1.0,
            fuel_capacity_litres=100_000.0,
        )