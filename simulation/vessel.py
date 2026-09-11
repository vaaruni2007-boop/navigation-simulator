from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Optional

from engine import distance as distance_mod
from engine.models import Route, Vessel, Waypoint
from engine import voyage as voyage_mod


@dataclass
class SimulatedVessel:
    """
    Runtime simulation state for a vessel travelling along a route.

    The underlying Vessel and Route remain immutable domain models.
    This class tracks where the vessel currently is.
    """

    vessel: Vessel
    route: Route

    current_position: Waypoint
    progress_fraction: float = 0.0
    travelled_distance_km: float = 0.0
    status: str = "READY"

    _segment_distances_km: Optional[list[float]] = None
    _total_distance_km: Optional[float] = None

    @classmethod
    def create_from_models(
        cls,
        vessel: Vessel,
        route: Route,
    ) -> "SimulatedVessel":
        """Create a simulation vessel from domain models."""

        if len(route.waypoints) < 2:
            raise ValueError(
                "Route must contain at least two waypoints"
            )

        segment_distances = [
            distance_mod.haversine_distance_km(
                route.waypoints[index],
                route.waypoints[index + 1],
            )
            for index in range(
                len(route.waypoints) - 1
            )
        ]

        total_distance = sum(
            segment_distances
        )

        return cls(
            vessel=vessel,
            route=route,
            current_position=route.waypoints[0],
            progress_fraction=0.0,
            travelled_distance_km=0.0,
            status="READY",
            _segment_distances_km=segment_distances,
            _total_distance_km=total_distance,
        )

    @property
    def total_distance_km(self) -> float:
        """Total route distance."""

        if self._total_distance_km is None:
            self._calculate_route_geometry()

        return self._total_distance_km or 0.0

    @property
    def total_distance_nm(self) -> float:
        """Total route distance in nautical miles."""

        return self.total_distance_km / 1.852

    @property
    def is_complete(self) -> bool:
        """Whether the vessel has reached the destination."""

        return self.progress_fraction >= 1.0

    def start_voyage(self) -> None:
        """Begin simulated movement."""

        if self.is_complete:
            return

        self.status = "EN_ROUTE"

    def pause_voyage(self) -> None:
        """Pause simulated movement."""

        if self.status == "EN_ROUTE":
            self.status = "PAUSED"

    def reset(self) -> None:
        """Return the vessel to the route origin."""

        self.current_position = self.route.waypoints[0]
        self.progress_fraction = 0.0
        self.travelled_distance_km = 0.0
        self.status = "READY"

    def update(
        self,
        elapsed_seconds: float,
    ) -> None:
        """
        Advance vessel position by elapsed simulation time.

        Movement uses the vessel's cruising speed.
        """

        if elapsed_seconds < 0:
            raise ValueError(
                "elapsed_seconds must be non-negative"
            )

        if self.status != "EN_ROUTE":
            return

        if self.is_complete:
            self.status = "COMPLETED"
            return

        speed_kmh = voyage_mod.knots_to_kmh(
            self.vessel.cruising_speed_knots
        )

        distance_to_travel = (
            speed_kmh
            * elapsed_seconds
            / 3600.0
        )

        new_distance = min(
            self.total_distance_km,
            self.travelled_distance_km
            + distance_to_travel,
        )

        self.travelled_distance_km = new_distance

        if self.total_distance_km > 0:
            self.progress_fraction = (
                self.travelled_distance_km
                / self.total_distance_km
            )

        self.current_position = (
            self._interpolate_position(
                self.travelled_distance_km
            )
        )

        if self.progress_fraction >= 1.0:
            self.progress_fraction = 1.0
            self.current_position = (
                self.route.waypoints[-1]
            )
            self.status = "COMPLETED"

    def estimated_duration_days(self) -> float:
        """Calculate simulated voyage duration."""

        return voyage_mod.calculate_voyage_days(
            self.total_distance_nm,
            self.vessel.cruising_speed_knots,
        )

    def estimated_arrival(
        self,
        departure_datetime: datetime,
    ) -> datetime:
        """Calculate estimated arrival time."""

        return voyage_mod.calculate_eta(
            departure_datetime,
            self.total_distance_nm,
            self.vessel.cruising_speed_knots,
        )

    def _calculate_route_geometry(self) -> None:
        """Calculate cached segment distances."""

        self._segment_distances_km = [
            distance_mod.haversine_distance_km(
                self.route.waypoints[index],
                self.route.waypoints[index + 1],
            )
            for index in range(
                len(self.route.waypoints) - 1
            )
        ]

        self._total_distance_km = sum(
            self._segment_distances_km
        )

    def _interpolate_position(
        self,
        travelled_distance_km: float,
    ) -> Waypoint:
        """
        Find vessel position along the route
        using linear interpolation within the
        current route segment.
        """

        if self._segment_distances_km is None:
            self._calculate_route_geometry()

        segment_distances = (
            self._segment_distances_km or []
        )

        remaining_distance = travelled_distance_km

        for index, segment_distance in enumerate(
            segment_distances
        ):
            start = self.route.waypoints[index]
            end = self.route.waypoints[index + 1]

            if remaining_distance <= segment_distance:
                if segment_distance == 0:
                    return end

                fraction = (
                    remaining_distance
                    / segment_distance
                )

                latitude = (
                    start.latitude
                    + (
                        end.latitude
                        - start.latitude
                    )
                    * fraction
                )

                longitude = (
                    start.longitude
                    + (
                        end.longitude
                        - start.longitude
                    )
                    * fraction
                )

                return Waypoint(
                    latitude=latitude,
                    longitude=longitude,
                )

            remaining_distance -= segment_distance

        return self.route.waypoints[-1]


__all__ = [
    "SimulatedVessel",
]