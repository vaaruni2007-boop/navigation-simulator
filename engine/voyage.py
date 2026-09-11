from __future__ import annotations

from datetime import datetime, timedelta
from typing import Optional

from simulation.environment import (
    EnvironmentConditions,
    normal_conditions,
)


KNOTS_TO_KMH = 1.852


def knots_to_kmh(knots: float) -> float:
    """Convert knots to kilometres per hour."""
    if knots < 0:
        raise ValueError("Speed cannot be negative.")

    return knots * KNOTS_TO_KMH


def voyage_duration_hours(
    distance_nm: float,
    speed_knots: float,
) -> float:
    """Calculate voyage duration in hours."""
    if distance_nm < 0:
        raise ValueError("Distance cannot be negative.")

    if speed_knots <= 0:
        raise ValueError("Speed must be greater than zero.")

    return distance_nm / speed_knots


def voyage_duration_days(
    distance_nm: float,
    speed_knots: float,
) -> float:
    """Calculate voyage duration in days."""
    return voyage_duration_hours(
        distance_nm=distance_nm,
        speed_knots=speed_knots,
    ) / 24.0


def calculate_voyage_days(
    distance_nm: float,
    speed_knots: float,
) -> float:
    """Compatibility alias used by the simulation engine."""
    return voyage_duration_days(
        distance_nm=distance_nm,
        speed_knots=speed_knots,
    )


def calculate_voyage_duration(
    distance_km: float,
    speed_knots: float,
) -> float:
    """
    Calculate voyage duration in days from distance in kilometres.
    """
    if distance_km < 0:
        raise ValueError("Distance cannot be negative.")

    if speed_knots <= 0:
        raise ValueError("Speed must be greater than zero.")

    speed_kmh = knots_to_kmh(speed_knots)

    return (distance_km / speed_kmh) / 24.0


# ----------------------------------------------------------------------
# Environment-aware voyage calculations
# ----------------------------------------------------------------------

def effective_voyage_speed(
    base_speed_knots: float,
    environment: Optional[EnvironmentConditions] = None,
) -> float:
    """
    Calculate effective vessel speed under environmental conditions.

    Normal conditions preserve the original vessel speed.
    Weather, sea ice, visibility and currents can reduce speed.
    """

    if base_speed_knots <= 0:
        raise ValueError(
            "base_speed_knots must be greater than zero."
        )

    if environment is None:
        environment = normal_conditions()

    return environment.effective_speed(
        base_speed_knots
    )


def environment_adjusted_voyage_duration_hours(
    distance_nm: float,
    speed_knots: float,
    environment: Optional[EnvironmentConditions] = None,
) -> float:
    """
    Calculate voyage duration in hours after environmental
    speed adjustments.
    """

    if distance_nm < 0:
        raise ValueError(
            "Distance cannot be negative."
        )

    effective_speed = effective_voyage_speed(
        speed_knots,
        environment,
    )

    return distance_nm / effective_speed


def environment_adjusted_voyage_duration_days(
    distance_nm: float,
    speed_knots: float,
    environment: Optional[EnvironmentConditions] = None,
) -> float:
    """
    Calculate voyage duration in days after environmental
    speed adjustments.
    """

    return (
        environment_adjusted_voyage_duration_hours(
            distance_nm=distance_nm,
            speed_knots=speed_knots,
            environment=environment,
        )
        / 24.0
    )


def environment_adjusted_fuel_consumption(
    duration_days: float,
    base_fuel_per_day: float,
    environment: Optional[EnvironmentConditions] = None,
) -> float:
    """
    Calculate fuel consumption after applying an environmental
    fuel multiplier.
    """

    if duration_days < 0:
        raise ValueError(
            "duration_days cannot be negative."
        )

    if base_fuel_per_day < 0:
        raise ValueError(
            "base_fuel_per_day cannot be negative."
        )

    if environment is None:
        environment = normal_conditions()

    return (
        duration_days
        * base_fuel_per_day
        * environment.fuel_multiplier()
    )


def environment_adjusted_eta(
    departure: datetime,
    distance_nm: float,
    speed_knots: float,
    environment: Optional[EnvironmentConditions] = None,
) -> datetime:
    """
    Estimate arrival time after environmental speed adjustments.
    """

    duration_days = (
        environment_adjusted_voyage_duration_days(
            distance_nm=distance_nm,
            speed_knots=speed_knots,
            environment=environment,
        )
    )

    return departure + timedelta(
        days=duration_days
    )


# ----------------------------------------------------------------------
# Standard ETA calculations
# ----------------------------------------------------------------------

def estimated_arrival(
    departure: datetime,
    distance_nm: float,
    speed_knots: float,
) -> datetime:
    """Estimate arrival time."""
    duration_days = voyage_duration_days(
        distance_nm=distance_nm,
        speed_knots=speed_knots,
    )

    return departure + timedelta(
        days=duration_days
    )


def calculate_eta(
    departure: datetime,
    distance_nm: float,
    speed_knots: float,
) -> datetime:
    """Calculate estimated arrival time."""
    return estimated_arrival(
        departure=departure,
        distance_nm=distance_nm,
        speed_knots=speed_knots,
    )


class Voyage:
    """Represents a simulated maritime voyage."""

    def __init__(
        self,
        distance_km: float,
        speed_knots: float,
        departure_time: Optional[datetime] = None,
    ):
        self.distance_km = distance_km
        self.speed_knots = speed_knots
        self.departure_time = departure_time

    @property
    def speed_kmh(self) -> float:
        return knots_to_kmh(
            self.speed_knots
        )

    @property
    def duration_days(self) -> float:
        return calculate_voyage_duration(
            self.distance_km,
            self.speed_knots,
        )

    @property
    def duration_hours(self) -> float:
        return self.duration_days * 24.0

    def calculate_arrival_time(self) -> datetime:
        if self.departure_time is None:
            raise ValueError(
                "Departure time is required."
            )

        return self.departure_time + timedelta(
            days=self.duration_days
        )

    def environment_adjusted_duration_days(
        self,
        environment: Optional[EnvironmentConditions] = None,
    ) -> float:
        """
        Calculate voyage duration under environmental conditions.

        Converts the voyage's kilometre distance to nautical miles
        before applying the environment-aware calculation.
        """

        distance_nm = self.distance_km / 1.852

        return environment_adjusted_voyage_duration_days(
            distance_nm=distance_nm,
            speed_knots=self.speed_knots,
            environment=environment,
        )

    def environment_adjusted_arrival_time(
        self,
        environment: Optional[EnvironmentConditions] = None,
    ) -> datetime:
        """
        Calculate arrival time under environmental conditions.
        """

        if self.departure_time is None:
            raise ValueError(
                "Departure time is required."
            )

        duration_days = (
            self.environment_adjusted_duration_days(
                environment
            )
        )

        return self.departure_time + timedelta(
            days=duration_days
        )