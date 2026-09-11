"""engine.voyage
================

Utility functions for maritime voyage calculations.

The module provides three pure‑functions that operate on:
* a distance (nautical miles)
* a vessel speed (knots)
* a departure datetime (timezone‑aware UTC)

All calculations are deterministic and do not depend on external services.
"""

from __future__ import annotations

from datetime import datetime, timezone, timedelta
from typing import Final

# ---------------------------------------------------------------------------
# Validation helpers
# ---------------------------------------------------------------------------

def _validate_positive(value: float, name: str) -> None:
    """Raise ValueError if *value* is not strictly positive."""
    if value <= 0:
        raise ValueError(f"{name} must be > 0 (got {value!r})")


def _validate_utc(dt: datetime) -> None:
    """Raise ValueError if *dt* is not timezone‑aware or not UTC."""
    if dt.tzinfo is None:
        raise ValueError("departure_datetime must be timezone‑aware")
    # Convert to UTC for the check – any aware datetime is acceptable as long as we
    # treat it as UTC for the calculation.
    if dt.utcoffset() != timezone.utc.utcoffset(dt):
        raise ValueError("departure_datetime must be expressed in UTC")


# ---------------------------------------------------------------------------
# Core voyage calculations
# ---------------------------------------------------------------------------

def calculate_voyage_hours(distance_nm: float, speed_knots: float) -> float:
    """
    Compute voyage duration in **hours**.

    Parameters
    ----------
    distance_nm : float
        Distance to travel in nautical miles. Must be > 0.
    speed_knots : float
        Vessel speed in knots (nautical miles per hour). Must be > 0.

    Returns
    -------
    float
        Duration in hours (may be fractional).

    Raises
    ------
    ValueError
        If *distance_nm* or *speed_knots* are not positive.
    """
    _validate_positive(distance_nm, "distance_nm")
    _validate_positive(speed_knots, "speed_knots")
    return distance_nm / speed_knots


def calculate_voyage_days(distance_nm: float, speed_knots: float) -> float:
    """
    Compute voyage duration in **days**.

    The result is a float; callers can round or truncate as needed.

    Parameters
    ----------
    distance_nm : float
        Distance to travel in nautical miles. Must be > 0.
    speed_knots : float
        Vessel speed in knots. Must be > 0.

    Returns
    -------
    float
        Duration in days.
    """
    hours = calculate_voyage_hours(distance_nm, speed_knots)
    return hours / 24.0


def calculate_eta(
    departure_datetime: datetime,
    distance_nm: float,
    speed_knots: float,
) -> datetime:
    """
    Calculate the estimated time of arrival (ETA).

    The ETA is a timezone‑aware ``datetime`` in UTC.

    Parameters
    ----------
    departure_datetime : datetime
        UTC, timezone‑aware departure timestamp.
    distance_nm : float
        Distance to travel in nautical miles. Must be > 0.
    speed_knots : float
        Vessel speed in knots. Must be > 0.

    Returns
    -------
    datetime
        ETA as a UTC ``datetime`` object.

    Raises
    ------
    ValueError
        If any parameter fails validation.
    """
    _validate_utc(departure_datetime)
    voyage_hours = calculate_voyage_hours(distance_nm, speed_knots)
    eta = departure_datetime + timedelta(hours=voyage_hours)
    # Ensure the result retains UTC tzinfo
    return eta.astimezone(timezone.utc)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

__all__: Final = [
    "calculate_voyage_hours",
    "calculate_voyage_days",
    "calculate_eta",
]