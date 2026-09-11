"""engine.deadline
===================

Conversion utilities that turn inventory forecasts into hard logistical deadlines
for Antarctic resupply voyages.

All functions operate on timezone‑aware ``datetime`` objects (UTC) and return
typed results.  The module is deliberately pure – it contains no knowledge of
navigation, cost, or optimisation.
"""

from __future__ import annotations

from datetime import datetime, timezone, timedelta
from typing import Final


# ---------------------------------------------------------------------------
# Validation helpers
# ---------------------------------------------------------------------------

def _require_aware_utc(dt: datetime, name: str) -> datetime:
    """Ensure *dt* is timezone‑aware and expressed in UTC."""
    if dt.tzinfo is None:
        raise ValueError(f"{name} must be timezone‑aware")
    # Normalise to UTC for internal calculations
    return dt.astimezone(timezone.utc)


def _require_non_negative(value: float, name: str) -> float:
    """Raise ``ValueError`` if *value* is negative."""
    if value < 0:
        raise ValueError(f"{name} must be non‑negative (got {value!r})")
    return value


# ---------------------------------------------------------------------------
# Core deadline calculations
# ---------------------------------------------------------------------------

def calculate_latest_safe_arrival(
    critical_date: datetime,
    safety_buffer_days: float,
) -> datetime:
    """
    Compute the latest arrival datetime that still leaves a safety buffer.

    Parameters
    ----------
    critical_date : datetime
        UTC, timezone‑aware moment when the inventory falls below the safety
        threshold.
    safety_buffer_days : float
        Desired buffer in days (must be ≥ 0).

    Returns
    -------
    datetime
        Latest safe arrival (UTC).
    """
    crit_utc = _require_aware_utc(critical_date, "critical_date")
    days = _require_non_negative(safety_buffer_days, "safety_buffer_days")
    return crit_utc - timedelta(days=days)


def calculate_latest_safe_departure(
    latest_safe_arrival: datetime,
    voyage_duration_days: float,
) -> datetime:
    """
    Compute the latest departure datetime that still meets the safe arrival.

    Parameters
    ----------
    latest_safe_arrival : datetime
        UTC, timezone‑aware latest acceptable arrival datetime.
    voyage_duration_days : float
        Expected voyage duration in days (must be > 0).

    Returns
    -------
    datetime
        Latest safe departure (UTC).
    """
    arrival_utc = _require_aware_utc(latest_safe_arrival, "latest_safe_arrival")
    duration = _require_non_negative(voyage_duration_days, "voyage_duration_days")
    return arrival_utc - timedelta(days=duration)


def calculate_safety_margin_days(
    required_arrival: datetime,
    actual_arrival: datetime,
) -> float:
    """
    Compute the safety margin (in days) between a required arrival and the
    actual arrival.  Positive values indicate the vessel arrives **before**
    the required time; negative values indicate it is late.

    Parameters
    ----------
    required_arrival : datetime
        UTC, timezone‑aware deadline that must be met.
    actual_arrival : datetime
        UTC, timezone‑aware actual arrival time.

    Returns
    -------
    float
        Margin in days (positive = early, negative = late, zero = on time).
    """
    req = _require_aware_utc(required_arrival, "required_arrival")
    act = _require_aware_utc(actual_arrival, "actual_arrival")
    delta = req - act
    return delta.total_seconds() / 86400.0


def is_arrival_feasible(
    actual_arrival: datetime,
    latest_safe_arrival: datetime,
) -> bool:
    """
    Determine whether an actual arrival meets the logistics feasibility rule.

    A voyage is feasible **only** if ``actual_arrival`` occurs on or before the
    ``latest_safe_arrival`` datetime.

    Parameters
    ----------
    actual_arrival : datetime
        UTC, timezone‑aware actual arrival moment.
    latest_safe_arrival : datetime
        UTC, timezone‑aware latest permissible arrival.

    Returns
    -------
    bool
        ``True`` if the arrival is on time or early, ``False`` otherwise.
    """
    act = _require_aware_utc(actual_arrival, "actual_arrival")
    latest = _require_aware_utc(latest_safe_arrival, "latest_safe_arrival")
    return act <= latest


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

__all__: Final = [
    "calculate_latest_safe_arrival",
    "calculate_latest_safe_departure",
    "calculate_safety_margin_days",
    "is_arrival_feasible",
]