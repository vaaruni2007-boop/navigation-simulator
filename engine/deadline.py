from __future__ import annotations

from datetime import datetime, timedelta, timezone


SECONDS_PER_DAY = 86400.0


def _require_aware_utc(
    value: datetime,
    name: str,
) -> datetime:
    if value.tzinfo is None:
        raise ValueError(
            f"{name} must be timezone-aware"
        )

    return value.astimezone(timezone.utc)


def _require_non_negative(
    value: float,
    name: str,
) -> float:
    if value < 0:
        raise ValueError(
            f"{name} must be non-negative"
        )

    return float(value)


def calculate_arrival_deadline(
    critical_date: datetime,
    safety_buffer_days: float,
) -> datetime:
    """
    Calculate the latest safe arrival deadline.

    The safety buffer is subtracted from the critical date.
    """

    critical_date = _require_aware_utc(
        critical_date,
        "critical_date",
    )

    safety_buffer_days = _require_non_negative(
        safety_buffer_days,
        "safety_buffer_days",
    )

    return critical_date - timedelta(
        days=safety_buffer_days
    )


def calculate_latest_safe_arrival(
    critical_date: datetime,
    safety_buffer_days: float,
) -> datetime:
    """Backward-compatible alias for calculate_arrival_deadline."""

    return calculate_arrival_deadline(
        critical_date,
        safety_buffer_days,
    )


def calculate_latest_safe_departure(
    latest_safe_arrival: datetime,
    voyage_duration_days: float,
) -> datetime:
    """Calculate latest departure that reaches the safe-arrival deadline."""

    latest_safe_arrival = _require_aware_utc(
        latest_safe_arrival,
        "latest_safe_arrival",
    )

    if voyage_duration_days <= 0:
        raise ValueError(
            "voyage_duration_days must be positive"
        )

    return latest_safe_arrival - timedelta(
        days=voyage_duration_days
    )


def calculate_safety_margin_days(
    required_arrival: datetime,
    actual_arrival: datetime,
) -> float:
    """Calculate arrival safety margin in days."""

    required_arrival = _require_aware_utc(
        required_arrival,
        "required_arrival",
    )

    actual_arrival = _require_aware_utc(
        actual_arrival,
        "actual_arrival",
    )

    return (
        required_arrival - actual_arrival
    ).total_seconds() / SECONDS_PER_DAY


def is_arrival_feasible(
    actual_arrival: datetime,
    latest_safe_arrival: datetime,
) -> bool:
    """Return whether arrival meets the safe-arrival deadline."""

    actual_arrival = _require_aware_utc(
        actual_arrival,
        "actual_arrival",
    )

    latest_safe_arrival = _require_aware_utc(
        latest_safe_arrival,
        "latest_safe_arrival",
    )

    return actual_arrival <= latest_safe_arrival


# Test-compatible alias.
is_arrival_before_deadline = is_arrival_feasible
has_arrived_before_deadline = is_arrival_feasible


__all__ = [
    "calculate_arrival_deadline",
    "calculate_latest_safe_arrival",
    "calculate_latest_safe_departure",
    "calculate_safety_margin_days",
    "is_arrival_feasible",
    "is_arrival_before_deadline",
    "has_arrived_before_deadline",
]