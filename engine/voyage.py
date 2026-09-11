from __future__ import annotations

from datetime import datetime, timedelta


KM_PER_NAUTICAL_MILE = 1.852


def knots_to_kmh(speed_knots: float) -> float:
    """Convert speed from knots to kilometres per hour."""

    if speed_knots <= 0:
        raise ValueError("speed_knots must be positive")

    return speed_knots * KM_PER_NAUTICAL_MILE


def calculate_voyage_hours(
    distance_nm: float,
    speed_knots: float,
) -> float:
    """Calculate voyage duration in hours."""

    if distance_nm <= 0:
        raise ValueError("distance_nm must be positive")

    if speed_knots <= 0:
        raise ValueError("speed_knots must be positive")

    return distance_nm / speed_knots


def calculate_voyage_days(
    distance_nm: float,
    speed_knots: float,
) -> float:
    """Calculate voyage duration in days."""

    return calculate_voyage_hours(
        distance_nm,
        speed_knots,
    ) / 24.0


def calculate_eta(
    departure_datetime: datetime,
    distance_nm: float,
    speed_knots: float,
) -> datetime:
    """Calculate estimated arrival time."""

    if departure_datetime.tzinfo is None:
        raise ValueError(
            "departure_datetime must be timezone-aware"
        )

    voyage_hours = calculate_voyage_hours(
        distance_nm,
        speed_knots,
    )

    return departure_datetime + timedelta(
        hours=voyage_hours
    )


__all__ = [
    "knots_to_kmh",
    "calculate_voyage_hours",
    "calculate_voyage_days",
    "calculate_eta",
]