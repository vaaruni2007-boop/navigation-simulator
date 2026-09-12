from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any, Optional

from engine.voyage import calculate_voyage_days, calculate_eta
from simulation.environment import (
    EnvironmentConditions,
    normal_conditions,
)


@dataclass
class SimulatedVessel:
    """
    Runtime representation of a vessel travelling along a simulated route.

    The vessel tracks:
    - distance travelled
    - current environment
    - fuel consumption
    - planned ETA
    - dynamically projected ETA
    - pause/resume state
    """

    vessel: Any = None
    route: Any = None

    vessel_id: Optional[str] = None
    total_distance_nm: Optional[float] = None
    cruise_speed_knots: Optional[float] = None
    fuel_capacity_litres: Optional[float] = None
    fuel_remaining_litres: Optional[float] = None
    fuel_consumption_litres_per_day: Optional[float] = None

    distance_travelled_nm: float = 0.0
    current_datetime: Optional[datetime] = None
    departure_datetime: Optional[datetime] = None
    arrival_datetime: Optional[datetime] = None

    status: str = "PLANNED"
    environment: Optional[EnvironmentConditions] = None

    def __post_init__(self):
        if self.vessel is not None:
            self._populate_from_models()

        if self.vessel_id is None:
            raise ValueError("vessel_id is required.")

        if self.total_distance_nm is None:
            raise ValueError("total_distance_nm is required.")

        if self.cruise_speed_knots is None:
            raise ValueError("cruise_speed_knots is required.")

        if self.fuel_capacity_litres is None:
            raise ValueError("fuel_capacity_litres is required.")

        if self.fuel_remaining_litres is None:
            self.fuel_remaining_litres = self.fuel_capacity_litres

        if self.fuel_consumption_litres_per_day is None:
            self.fuel_consumption_litres_per_day = 0.0

        if self.total_distance_nm < 0:
            raise ValueError(
                "total_distance_nm cannot be negative."
            )

        if self.cruise_speed_knots <= 0:
            raise ValueError(
                "cruise_speed_knots must be greater than zero."
            )

        if self.fuel_capacity_litres < 0:
            raise ValueError(
                "fuel_capacity_litres cannot be negative."
            )

        if self.fuel_remaining_litres < 0:
            raise ValueError(
                "fuel_remaining_litres cannot be negative."
            )

        if self.fuel_remaining_litres > self.fuel_capacity_litres:
            raise ValueError(
                "fuel_remaining_litres cannot exceed fuel capacity."
            )

        if self.fuel_consumption_litres_per_day < 0:
            raise ValueError(
                "fuel_consumption_litres_per_day cannot be negative."
            )

        if self.environment is None:
            self.environment = normal_conditions()

    # ------------------------------------------------------------------
    # Model helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _get(obj: Any, *names: str, default: Any = None) -> Any:
        if obj is None:
            return default

        for name in names:
            if isinstance(obj, dict) and name in obj:
                return obj[name]

            if hasattr(obj, name):
                return getattr(obj, name)

        return default

    def _populate_from_models(self):
        """Populate simulation properties from project domain models."""

        if self.vessel_id is None:
            self.vessel_id = self._get(
                self.vessel,
                "id",
                "vessel_id",
            )

        if self.total_distance_nm is None:
            distance_km = self._get(
                self.route,
                "distance_km",
                "distance",
                default=0.0,
            )

            self.total_distance_nm = (
                float(distance_km) * 0.539956803
            )

        if self.cruise_speed_knots is None:
            self.cruise_speed_knots = float(
                self._get(
                    self.vessel,
                    "cruising_speed_knots",
                    "cruise_speed_knots",
                    "cruise_speed",
                    "speed_knots",
                    default=0.0,
                )
            )

        if self.fuel_capacity_litres is None:
            self.fuel_capacity_litres = float(
                self._get(
                    self.vessel,
                    "fuel_capacity_litres",
                    "fuel_capacity",
                    default=0.0,
                )
            )

        if self.fuel_remaining_litres is None:
            self.fuel_remaining_litres = (
                self.fuel_capacity_litres
            )

        if self.fuel_consumption_litres_per_day is None:
            self.fuel_consumption_litres_per_day = float(
                self._get(
                    self.vessel,
                    "fuel_consumption_litres_per_day",
                    "fuel_consumption_l_per_day",
                    "fuel_consumption",
                    default=0.0,
                )
            )

    @classmethod
    def create_from_models(cls, vessel: Any, route: Any):
        return cls(
            vessel=vessel,
            route=route,
        )

    # ------------------------------------------------------------------
    # Progress
    # ------------------------------------------------------------------

    @property
    def progress(self) -> float:
        if self.total_distance_nm == 0:
            return 1.0

        return min(
            1.0,
            self.distance_travelled_nm
            / self.total_distance_nm,
        )

    @property
    def progress_fraction(self) -> float:
        return self.progress

    @property
    def progress_percent(self) -> float:
        return self.progress * 100.0

    @property
    def distance_remaining_nm(self) -> float:
        return max(
            0.0,
            self.total_distance_nm
            - self.distance_travelled_nm,
        )

    @property
    def is_complete(self) -> bool:
        return (
            self.distance_travelled_nm
            >= self.total_distance_nm
        )

    @property
    def is_active(self) -> bool:
        return self.status == "EN_ROUTE"

    # ------------------------------------------------------------------
    # Environment
    # ------------------------------------------------------------------

    @property
    def effective_speed_knots(self) -> float:
        return self.environment.effective_speed(
            self.cruise_speed_knots
        )

    @property
    def current_fuel_burn_per_day(self) -> float:
        return (
            self.fuel_consumption_litres_per_day
            * self.environment.fuel_multiplier()
        )

    # ------------------------------------------------------------------
    # Position
    # ------------------------------------------------------------------

    @property
    def current_position(self):
        """Current interpolated position along the route."""

        if self.route is None:
            return self._position_from_direct_coordinates()

        waypoints = self._get(
            self.route,
            "waypoints",
            default=[],
        )

        if not waypoints:
            return self._position_from_direct_coordinates()

        if self.progress <= 0:
            return self._waypoint_position(waypoints[0])

        if self.progress >= 1:
            return self._waypoint_position(waypoints[-1])

        segment_lengths = []

        for index in range(len(waypoints) - 1):
            first = self._waypoint_coordinates(
                waypoints[index]
            )
            second = self._waypoint_coordinates(
                waypoints[index + 1]
            )

            if first is None or second is None:
                continue

            lat1, lon1 = first
            lat2, lon2 = second

            segment_length = (
                (lat2 - lat1) ** 2
                + (lon2 - lon1) ** 2
            ) ** 0.5

            segment_lengths.append(
                (index, segment_length)
            )

        if not segment_lengths:
            return self._waypoint_position(waypoints[0])

        total_length = sum(
            length
            for _, length in segment_lengths
        )

        target = self.progress * total_length
        travelled = 0.0

        for index, segment_length in segment_lengths:
            first = self._waypoint_coordinates(
                waypoints[index]
            )
            second = self._waypoint_coordinates(
                waypoints[index + 1]
            )

            if target <= travelled + segment_length:
                fraction = 0.0

                if segment_length > 0:
                    fraction = (
                        target - travelled
                    ) / segment_length

                lat = first[0] + (
                    second[0] - first[0]
                ) * fraction

                lon = first[1] + (
                    second[1] - first[1]
                ) * fraction

                return self._make_position(
                    lat,
                    lon,
                )

            travelled += segment_length

        return self._waypoint_position(
            waypoints[-1]
        )

    @staticmethod
    def _make_position(
        latitude: float,
        longitude: float,
    ):
        return type(
            "Position",
            (),
            {
                "latitude": latitude,
                "longitude": longitude,
            },
        )()

    @classmethod
    def _waypoint_coordinates(cls, waypoint):
        if isinstance(waypoint, dict):
            lat = waypoint.get(
                "latitude",
                waypoint.get("lat"),
            )
            lon = waypoint.get(
                "longitude",
                waypoint.get("lon"),
            )

            if lat is not None and lon is not None:
                return float(lat), float(lon)

        if (
            isinstance(waypoint, (list, tuple))
            and len(waypoint) >= 2
        ):
            return (
                float(waypoint[0]),
                float(waypoint[1]),
            )

        lat = getattr(
            waypoint,
            "latitude",
            getattr(waypoint, "lat", None),
        )

        lon = getattr(
            waypoint,
            "longitude",
            getattr(waypoint, "lon", None),
        )

        if lat is not None and lon is not None:
            return float(lat), float(lon)

        return None

    @classmethod
    def _waypoint_position(cls, waypoint):
        coordinates = cls._waypoint_coordinates(
            waypoint
        )

        if coordinates is None:
            return cls._make_position(
                0.0,
                0.0,
            )

        return cls._make_position(
            coordinates[0],
            coordinates[1],
        )

    def _position_from_direct_coordinates(self):
        latitude = self._get(
            self.vessel,
            "latitude",
            "current_latitude",
            default=0.0,
        )

        longitude = self._get(
            self.vessel,
            "longitude",
            "current_longitude",
            default=0.0,
        )

        return self._make_position(
            float(latitude),
            float(longitude),
        )

    # ------------------------------------------------------------------
    # Voyage calculations
    # ------------------------------------------------------------------

    def estimated_duration_days(self) -> float:
        if self.total_distance_nm == 0:
            return 0.0

        return calculate_voyage_days(
            self.total_distance_nm,
            self.effective_speed_knots,
        )

    def estimated_arrival(
        self,
        departure_datetime: Optional[datetime] = None,
    ) -> Optional[datetime]:

        if departure_datetime is None:
            departure_datetime = self.departure_datetime

        if departure_datetime is None:
            return None

        return calculate_eta(
            departure_datetime,
            self.total_distance_nm,
            self.effective_speed_knots,
        )

    # ------------------------------------------------------------------
    # Dynamic ETA
    # ------------------------------------------------------------------

    @property
    def planned_duration_days(self) -> float:
        """Original planned voyage duration using normal conditions."""

        if self.total_distance_nm == 0:
            return 0.0

        normal_speed = (
            normal_conditions().effective_speed(
                self.cruise_speed_knots
            )
        )

        return calculate_voyage_days(
            self.total_distance_nm,
            normal_speed,
        )

    @property
    def planned_arrival_datetime(
        self,
    ) -> Optional[datetime]:
        """Original planned ETA under normal conditions."""

        if self.departure_datetime is None:
            return None

        return self.departure_datetime + timedelta(
            days=self.planned_duration_days
        )

    @property
    def projected_remaining_duration_days(
        self,
    ) -> float:
        """Remaining voyage duration at the current effective speed."""

        if self.is_complete:
            return 0.0

        if self.distance_remaining_nm <= 0:
            return 0.0

        return (
            self.distance_remaining_nm
            / self.effective_speed_knots
            / 24.0
        )

    @property
    def projected_arrival_datetime(
        self,
    ) -> Optional[datetime]:
        """Current dynamic projected arrival."""

        if self.current_datetime is None:
            return self.planned_arrival_datetime

        if self.is_complete:
            return self.current_datetime

        return self.current_datetime + timedelta(
            days=self.projected_remaining_duration_days
        )

    @property
    def dynamic_eta(self) -> Optional[datetime]:
        return self.projected_arrival_datetime

    @property
    def delay_days(self) -> Optional[float]:
        """Projected delay relative to the original normal-condition plan."""

        planned_arrival = self.planned_arrival_datetime
        projected_arrival = self.projected_arrival_datetime

        if (
            planned_arrival is None
            or projected_arrival is None
        ):
            return None

        delay = (
            projected_arrival
            - planned_arrival
        ).total_seconds() / 86400.0

        return max(
            0.0,
            delay,
        )

    # ------------------------------------------------------------------
    # Voyage controls
    # ------------------------------------------------------------------

    def start_voyage(
        self,
        departure_datetime: datetime,
        environment: Optional[
            EnvironmentConditions
        ] = None,
    ):
        if self.status == "EN_ROUTE":
            raise ValueError(
                "Vessel is already en route."
            )

        if self.status == "PAUSED":
            raise ValueError(
                "Use resume_voyage() to resume a paused vessel."
            )

        if self.status == "COMPLETED":
            raise ValueError(
                "Cannot start a completed vessel. Reset it first."
            )

        if departure_datetime.tzinfo is None:
            raise ValueError(
                "departure_datetime must be timezone-aware."
            )

        if environment is not None:
            self.environment = environment

        self.departure_datetime = departure_datetime
        self.current_datetime = departure_datetime

        self.arrival_datetime = self.estimated_arrival(
            departure_datetime
        )

        self.status = "EN_ROUTE"

    def start(
        self,
        departure_datetime: datetime,
    ):
        self.start_voyage(
            departure_datetime
        )

    def pause_voyage(self):
        if self.status != "EN_ROUTE":
            return

        self.status = "PAUSED"

    def resume_voyage(self):
        if self.status != "PAUSED":
            return

        self.status = "EN_ROUTE"

        if not self.is_complete:
            self.arrival_datetime = (
                self.projected_arrival_datetime
            )

    def advance(
        self,
        elapsed_hours: float,
        environment: Optional[
            EnvironmentConditions
        ] = None,
    ):
        if elapsed_hours < 0:
            raise ValueError(
                "elapsed_hours cannot be negative."
            )

        if self.status != "EN_ROUTE":
            return

        if environment is not None:
            self.environment = environment

        if self.current_datetime is None:
            raise RuntimeError(
                "Vessel must have a current datetime before advancing."
            )

        if self.is_complete:
            self.status = "COMPLETED"
            self.arrival_datetime = self.current_datetime
            return

        effective_speed = self.effective_speed_knots

        # Calculate the exact amount of time required to reach
        # the destination. This prevents a large update tick from
        # moving the vessel beyond its true arrival time.
        hours_to_destination = (
            self.distance_remaining_nm
            / effective_speed
        )

        actual_elapsed_hours = min(
            elapsed_hours,
            hours_to_destination,
        )

        distance_moved = (
            effective_speed
            * actual_elapsed_hours
        )

        self.distance_travelled_nm = min(
            self.total_distance_nm,
            self.distance_travelled_nm
            + distance_moved,
        )

        fuel_used = (
            self.current_fuel_burn_per_day
            * actual_elapsed_hours
            / 24.0
        )

        self.fuel_remaining_litres = max(
            0.0,
            self.fuel_remaining_litres
            - fuel_used,
        )

        self.current_datetime += timedelta(
            hours=actual_elapsed_hours
        )

        if self.is_complete:
            self.status = "COMPLETED"
            self.arrival_datetime = self.current_datetime
        else:
            self.arrival_datetime = (
                self.projected_arrival_datetime
            )

    def update(
        self,
        elapsed_seconds: float,
        environment: Optional[
            EnvironmentConditions
        ] = None,
    ):
        """Advance simulation by seconds."""

        if elapsed_seconds < 0:
            raise ValueError(
                "elapsed_seconds cannot be negative."
            )

        self.advance(
            elapsed_seconds / 3600.0,
            environment=environment,
        )

    def set_environment(
        self,
        environment: EnvironmentConditions,
    ):
        self.environment = environment

        if (
            self.status == "EN_ROUTE"
            and not self.is_complete
        ):
            self.arrival_datetime = (
                self.projected_arrival_datetime
            )

    # ------------------------------------------------------------------
    # Reset / fuel
    # ------------------------------------------------------------------

    def reset(self):
        self.distance_travelled_nm = 0.0
        self.current_datetime = None
        self.departure_datetime = None
        self.arrival_datetime = None
        self.fuel_remaining_litres = (
            self.fuel_capacity_litres
        )
        self.status = "PLANNED"

    def fuel_used_litres(self) -> float:
        return (
            self.fuel_capacity_litres
            - self.fuel_remaining_litres
        )

    def fuel_remaining_percent(self) -> float:
        if self.fuel_capacity_litres == 0:
            return 0.0

        return (
            self.fuel_remaining_litres
            / self.fuel_capacity_litres
        ) * 100.0


__all__ = [
    "SimulatedVessel",
]