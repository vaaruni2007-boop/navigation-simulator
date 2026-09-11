from __future__ import annotations

from dataclasses import dataclass


@dataclass
class EnvironmentConditions:
    """
    Environmental conditions affecting a simulated Antarctic voyage.

    All values are simulation inputs, not live weather or AIS data.
    """

    weather_severity: float = 0.0
    sea_ice_severity: float = 0.0
    current_factor: float = 1.0
    visibility_factor: float = 1.0

    def __post_init__(self):
        self._validate_range(
            self.weather_severity,
            "weather_severity",
        )
        self._validate_range(
            self.sea_ice_severity,
            "sea_ice_severity",
        )

        if self.current_factor <= 0:
            raise ValueError("current_factor must be greater than zero.")

        if not 0 < self.visibility_factor <= 1:
            raise ValueError(
                "visibility_factor must be greater than 0 and at most 1."
            )

    @staticmethod
    def _validate_range(value: float, name: str):
        if not 0 <= value <= 1:
            raise ValueError(
                f"{name} must be between 0 and 1."
            )

    @property
    def overall_severity(self) -> float:
        """
        Combined environmental severity.

        Weather and sea-ice are weighted equally for now.
        """
        return (
            self.weather_severity
            + self.sea_ice_severity
        ) / 2

    def speed_factor(self) -> float:
        """
        Calculate the fraction of normal vessel speed
        available under current environmental conditions.
        """

        weather_penalty = 0.35 * self.weather_severity
        sea_ice_penalty = 0.40 * self.sea_ice_severity
        visibility_penalty = 0.15 * (1 - self.visibility_factor)

        factor = (
            1.0
            - weather_penalty
            - sea_ice_penalty
            - visibility_penalty
        )

        return max(0.25, factor * self.current_factor)

    def effective_speed(self, base_speed_knots: float) -> float:
        """
        Return vessel speed after environmental effects.
        """

        if base_speed_knots <= 0:
            raise ValueError(
                "base_speed_knots must be greater than zero."
            )

        return base_speed_knots * self.speed_factor()

    def fuel_multiplier(self) -> float:
        """
        Environmental increase in fuel consumption.

        Harsh conditions increase fuel requirements.
        """

        multiplier = (
            1.0
            + 0.30 * self.weather_severity
            + 0.40 * self.sea_ice_severity
            + 0.10 * (1 - self.visibility_factor)
        )

        return multiplier

    def risk_score(self, base_route_risk: float = 0.0) -> float:
        """
        Combine route risk with environmental conditions.

        Result is capped at 1.0.
        """

        if not 0 <= base_route_risk <= 1:
            raise ValueError(
                "base_route_risk must be between 0 and 1."
            )

        environmental_risk = (
            0.45 * self.weather_severity
            + 0.45 * self.sea_ice_severity
            + 0.10 * (1 - self.visibility_factor)
        )

        return min(
            1.0,
            base_route_risk * 0.5
            + environmental_risk * 0.5,
        )


def normal_conditions() -> EnvironmentConditions:
    """Return a baseline calm-weather scenario."""

    return EnvironmentConditions(
        weather_severity=0.0,
        sea_ice_severity=0.0,
        current_factor=1.0,
        visibility_factor=1.0,
    )


def storm_conditions() -> EnvironmentConditions:
    """Return a simulated severe-weather scenario."""

    return EnvironmentConditions(
        weather_severity=0.9,
        sea_ice_severity=0.4,
        current_factor=0.85,
        visibility_factor=0.5,
    )


def heavy_ice_conditions() -> EnvironmentConditions:
    """Return a simulated heavy-sea-ice scenario."""

    return EnvironmentConditions(
        weather_severity=0.3,
        sea_ice_severity=0.9,
        current_factor=0.75,
        visibility_factor=0.7,
    )