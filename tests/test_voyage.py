# -*- coding: utf-8 -*-
"""
tests/test_voyage.py
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Pytest suite for the voyage utilities in ``engine/voyage.py``.
"""

from __future__ import annotations

import pytest
from datetime import datetime, timezone, timedelta

from engine.voyage import (
    knots_to_kmh,
    calculate_voyage_days,
    calculate_eta,
)


# ----------------------------------------------------------------------
# Known reference values (used across multiple tests)
# ----------------------------------------------------------------------
_KNOTS_TO_KMH_FACTOR = 1.852  # exact conversion factor


def test_knots_to_kmh_conversion() -> None:
    """Conversion from knots to kilometres per hour must use the exact factor."""
    speed_knots = 10.0
    expected_kmh = speed_knots * _KNOTS_TO_KMH_FACTOR
    assert knots_to_kmh(speed_knots) == pytest.approx(expected_kmh, rel=1e-9)


def test_knots_to_kmh_negative_speed_raises() -> None:
    """Providing a non‑positive speed to ``knots_to_kmh`` must raise."""
    with pytest.raises(ValueError, match="positive"):
        knots_to_kmh(0)
    with pytest.raises(ValueError, match="positive"):
        knots_to_kmh(-5)


def test_calculate_voyage_days_known_values() -> None:
    """
    Verify voyage duration calculation using a simple example:

    distance = 240 nautical miles
    speed    = 12 knots
    → hours = 20
    → days  = 20 / 24 = 0.833333...
    """
    distance_nm = 240.0
    speed_knots = 12.0
    expected_days = (distance_nm / speed_knots) / 24.0
    assert calculate_voyage_days(distance_nm, speed_knots) == pytest.approx(
        expected_days, rel=1e-9
    )


@pytest.mark.parametrize(
    "distance, speed",
    [
        (0, 10),   # zero distance
        (-50, 10), # negative distance
    ],
)
def test_calculate_voyage_days_invalid_distance(distance, speed):
    """Zero or negative distances must raise a ValueError."""
    with pytest.raises(ValueError, match="distance_nm"):
        calculate_voyage_days(distance, speed)


@pytest.mark.parametrize(
    "distance, speed",
    [
        (100, 0),    # zero speed
        (100, -3),   # negative speed
    ],
)
def test_calculate_voyage_days_invalid_speed(distance, speed):
    """Zero or negative speeds must raise a ValueError."""
    with pytest.raises(ValueError, match="speed_knots"):
        calculate_voyage_days(distance, speed)


def test_calculate_eta_correctness() -> None:
    """
    ETA should be departure + (distance / speed) hours.
    Use a deterministic UTC datetime for reproducibility.
    """
    departure = datetime(2026, 10, 1, 12, 0, tzinfo=timezone.utc)
    distance_nm = 180.0
    speed_knots = 6.0  # 30 hours total travel time
    expected_eta = departure + timedelta(hours=distance_nm / speed_knots)
    assert calculate_eta(departure, distance_nm, speed_knots) == expected_eta


def test_calculate_eta_requires_timezone_aware_datetime() -> None:
    """A naive datetime must cause ``calculate_eta`` to raise."""
    naive_dt = datetime(2026, 10, 1, 12, 0)  # no tzinfo
    with pytest.raises(ValueError, match="timezone‑aware"):
        calculate_eta(naive_dt, 100, 10)


@pytest.mark.parametrize(
    "distance, speed",
    [
        (0, 10),    # zero distance
        (-10, 10),  # negative distance
    ],
)
def test_calculate_eta_invalid_distance(distance, speed):
    """Zero or negative distance arguments raise a ValueError."""
    departure = datetime(2026, 10, 1, 12, 0, tzinfo=timezone.utc)
    with pytest.raises(ValueError, match="distance_nm"):
        calculate_eta(departure, distance, speed)


@pytest.mark.parametrize(
    "distance, speed",
    [
        (100, 0),   # zero speed
        (100, -5),  # negative speed
    ],
)
def test_calculate_eta_invalid_speed(distance, speed):
    """Zero or negative speed arguments raise a ValueError."""
    departure = datetime(2026, 10, 1, 12, 0, tzinfo=timezone.utc)
    with pytest.raises(ValueError, match="speed_knots"):
        calculate_eta(departure, distance, speed)