# tests/test_deadline.py
"""
Pytest suite for ``engine.deadline`` utilities.

Covered scenarios:
1. Latest safe arrival calculation.
2. Latest safe departure calculation.
3. Positive safety margin.
4. Zero safety margin.
5. Negative safety margin.
6. Arrival exactly at the deadline (feasible).
7. Arrival after the deadline (infeasible).
"""

import pytest
from datetime import datetime, timezone, timedelta

from engine.deadline import (
    calculate_latest_safe_arrival,
    calculate_latest_safe_departure,
    calculate_safety_margin_days,
    is_arrival_feasible,
)


# ----------------------------------------------------------------------
# 1. Latest safe arrival calculation
# ----------------------------------------------------------------------
def test_latest_safe_arrival_basic() -> None:
    critical = datetime(2027, 1, 15, 12, 0, tzinfo=timezone.utc)
    buffer_days = 3.0
    expected = critical - timedelta(days=buffer_days)
    assert calculate_latest_safe_arrival(critical, buffer_days) == expected


def test_latest_safe_arrival_zero_buffer() -> None:
    critical = datetime(2027, 5, 1, 0, 0, tzinfo=timezone.utc)
    assert calculate_latest_safe_arrival(critical, 0) == critical


# ----------------------------------------------------------------------
# 2. Latest safe departure calculation
# ----------------------------------------------------------------------
def test_latest_safe_departure_basic() -> None:
    latest_arrival = datetime(2027, 2, 20, 18, 0, tzinfo=timezone.utc)
    voyage_days = 4.5
    expected = latest_arrival - timedelta(days=voyage_days)
    assert calculate_latest_safe_departure(latest_arrival, voyage_days) == expected


def test_latest_safe_departure_zero_duration() -> None:
    latest_arrival = datetime(2027, 3, 10, tzinfo=timezone.utc)
    assert calculate_latest_safe_departure(latest_arrival, 0) == latest_arrival


# ----------------------------------------------------------------------
# 3. Positive safety margin
# ----------------------------------------------------------------------
def test_safety_margin_positive() -> None:
    required = datetime(2027, 4, 30, 12, 0, tzinfo=timezone.utc)
    actual = datetime(2027, 4, 29, 0, 0, tzinfo=timezone.utc)
    # required - actual = 1.5 days
    assert calculate_safety_margin_days(required, actual) == pytest.approx(1.5)


# ----------------------------------------------------------------------
# 4. Zero safety margin
# ----------------------------------------------------------------------
def test_safety_margin_zero() -> None:
    dt = datetime(2027, 6, 6, 6, 6, tzinfo=timezone.utc)
    assert calculate_safety_margin_days(dt, dt) == pytest.approx(0.0)


# ----------------------------------------------------------------------
# 5. Negative safety margin
# ----------------------------------------------------------------------
def test_safety_margin_negative() -> None:
    required = datetime(2027, 7, 1, tzinfo=timezone.utc)
    actual = datetime(2027, 7, 3, 12, 0, tzinfo=timezone.utc)
    # required - actual = -2.5 days
    assert calculate_safety_margin_days(required, actual) == pytest.approx(-2.5)


# ----------------------------------------------------------------------
# 6. Arrival exactly at deadline (feasible)
# ----------------------------------------------------------------------
def test_arrival_feasible_exact_deadline() -> None:
    latest = datetime(2027, 8, 15, 0, 0, tzinfo=timezone.utc)
    actual = latest  # identical datetime
    assert is_arrival_feasible(actual, latest) is True


# ----------------------------------------------------------------------
# 7. Arrival after deadline (infeasible)
# ----------------------------------------------------------------------
def test_arrival_infeasible_after_deadline() -> None:
    latest = datetime(2027, 9, 1, 12, 0, tzinfo=timezone.utc)
    actual = latest + timedelta(hours=1)  # one hour late
    assert is_arrival_feasible(actual, latest) is False