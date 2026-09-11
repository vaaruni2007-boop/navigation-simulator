# -*- coding: utf-8 -*-
"""
simulation/vessel.py
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Simulated vessel that physically travels along a predefined maritime route.

The :class:`SimulatedVessel` uses the deterministic ``SimulationClock`` (or any
UTC‐aware datetime) to advance the vessel's position based on its speed,
elapsed simulated time, and the geometry of the route.  Interpolation between
waypoints is performed linearly in latitude/longitude, which is sufficient for
the coarse‑grained simulation required here.

No external services (e.g. Google Maps) are used; all calculations rely on the
pure functions from ``engine.distance``.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import List, Tuple

from ..engine import distance as dist_mod
from ..engine.models import Vessel, Route, Waypoint


@dataclass
class SimulatedVessel:
    """
    Represents a vessel moving along a maritime route in a deterministic simulation.

    Attributes
    ----------
    vessel_id : str
        Identifier of the simulated vessel (matches the ``Vessel.id``).
    route_id : str
        Identifier of the route (matches the ``Route.id``).
    progress : float
        Normalised progress along the route; ``0.0`` = start, ``1.0`` = destination.
    current_latitude : float
        Current latitude of the vessel (degrees).
    current_longitude : float
        Current longitude of the vessel (degrees).
    status : str
        One of ``\"PLANNED\"``, ``\"EN_ROUTE\"``, ``\"PAUSED\"``, ``\"ARRIVED\"``.
    departure_datetime : datetime | None
        UTC timestamp when the vessel started its voyage.
    estimated_arrival_datetime : datetime | None
        UTC timestamp when the vessel is expected to arrive (based on speed).
    """

    vessel_id: str
    route_id: str
    progress: float = 0.0
    current_latitude: float = 0.0
    current_longitude: float = 0.0
    status: str = "PLANNED"
    departure_datetime: datetime | None = None
    estimated_arrival_datetime: datetime | None = None

    # Internal fields (not part of the public API)
    _vessel: Vessel = field(repr=False, init=False)
    _route: Route = field(repr=False, init=False)
    _segment_distances_nm: List[float] = field(default_factory=list, repr=False, init=False)
    _cumulative_distances_nm: List[float] = field(default_factory=list, repr=False, init=False)
    _total_distance_nm: float = field(default=0.0, repr=False, init=False)

    def __post_init__(self):
        raise RuntimeError(
            "SimulatedVessel must be instantiated via the classmethod "
            "`create_from_models(vessel, route)` – direct construction is disabled."
        )

    # --------------------------------------------------------------------- #
    # Construction helpers
    # --------------------------------------------------------------------- #
    @classmethod
    def create_from_models(cls, vessel: Vessel, route: Route) -> "SimulatedVessel":
        """
        Initialise a :class:`SimulatedVessel` from validated ``Vessel`` and ``Route`` models.

        This method extracts the waypoint list, pre‑computes segment distances,
        and seeds the initial position at the route start.

        Parameters
        ----------
        vessel : Vessel
            Vessel definition (must contain a positive ``max_speed_knots``).
        route : Route
            Route definition (must contain at least two waypoints).

        Returns
        -------
        SimulatedVessel
            Fully‑initialised simulated vessel ready for ``start_voyage``.
        """
        if not isinstance(vessel, Vessel):
            raise TypeError("vessel must be an instance of engine.models.Vessel")
        if not isinstance(route, Route):
            raise TypeError("route must be an instance of engine.models.Route")
        if not route.waypoints or len(route.waypoints) < 2:
            raise ValueError("route must contain at least two waypoints")

        # Convert raw dict waypoints (if they are plain dicts) to Waypoint objects
        waypoints = [
            wp if isinstance(wp, Waypoint) else Waypoint(**wp) for wp in route.waypoints
        ]

        # Pre‑compute distances between consecutive waypoints (nautical miles)
        segment_distances_nm = [
            dist_mod.haversine_distance_nm(waypoints[i], waypoints[i + 1])
            for i in range(len(waypoints) - 1)
        ]

        # Cumulative distances starting at 0 for the first waypoint
        cumulative = [0.0]
        for d in segment_distances_nm:
            cumulative.append(cumulative[-1] + d)

        total_distance_nm = cumulative[-1]
        if total_distance_nm <= 0:
            raise ValueError("route distance must be greater than zero")

        # Seed initial position at the start waypoint
        start_wp = waypoints[0]

        # Create the instance without invoking __post_init__
        obj = object.__new__(cls)  # bypass dataclass __init__
        obj.vessel_id = vessel.id
        obj.route_id = route.id
        obj.progress = 0.0
        obj.current_latitude = start_wp.latitude
        obj.current_longitude = start_wp.longitude
        obj.status = "PLANNED"
        obj.departure_datetime = None
        obj.estimated_arrival_datetime = None

        # Store internal helpers
        obj._vessel = vessel
        obj._route = route
        obj._segment_distances_nm = segment_distances_nm
        obj._cumulative_distances_nm = cumulative
        obj._total_distance_nm = total_distance_nm

        return obj

    # --------------------------------------------------------------------- #
    # Public API
    # --------------------------------------------------------------------- #
    def start_voyage(self, departure_datetime: datetime) -> None:
        """
        Begin the voyage at the supplied UTC datetime.

        Parameters
        ----------
        departure_datetime : datetime
            UTC timestamp when the vessel actually departs. Must be timezone‑aware.
        """
        if departure_datetime.tzinfo is None:
            raise ValueError("departure_datetime must be timezone‑aware (UTC)")
        if self.status not in ("PLANNED", "PAUSED"):
            raise RuntimeError(f"Cannot start voyage when status is '{self.status}'")
        self.departure_datetime = departure_datetime
        self.status = "EN_ROUTE"

        # Estimate arrival based on constant speed and total route distance
        hours_needed = self._total_distance_nm / max(self._vessel.max_speed_knots, 1e-6)
        self.estimated_arrival_datetime = departure_datetime + timedelta(hours=hours_needed)

    def pause(self) -> None:
        """Pause the vessel's movement (status becomes ``PAUSED``)."""
        if self.status != "EN_ROUTE":
            raise RuntimeError("Can only pause a vessel that is currently EN_ROUTE")
        self.status = "PAUSED"

    def resume(self) -> None:
        """Resume movement after a pause (status returns to ``EN_ROUTE``)."""
        if self.status != "PAUSED":
            raise RuntimeError("Can only resume a vessel that is PAUSED")
        self.status = "EN_ROUTE"

    def update(self, simulated_datetime: datetime) -> None:
        """
        Advance the vessel's state to ``simulated_datetime``.

        This method computes how far the vessel should have travelled based on
        its speed, the elapsed simulated time, and updates ``progress`` and the
        current latitude/longitude accordingly.

        Parameters
        ----------
        simulated_datetime : datetime
            Current simulated UTC time (must be timezone‑aware).
        """
        if simulated_datetime.tzinfo is None:
            raise ValueError("simulated_datetime must be timezone‑aware (UTC)")

        if self.status not in ("EN_ROUTE", "PAUSED"):
            # No movement required – either not started or already arrived.
            return

        if self.departure_datetime is None:
            raise RuntimeError("Voyage has not been started (departure_datetime is None)")

        if simulated_datetime < self.departure_datetime:
            # Still before departure – nothing to update.
            return

        if self.status == "PAUSED":
            # While paused, progress does not change.
            return

        # Elapsed time in seconds
        elapsed_seconds = (simulated_datetime - self.departure_datetime).total_seconds()
        elapsed_hours = elapsed_seconds / 3600.0

        # Distance travelled (nautical miles) at constant vessel speed
        distance_travelled_nm = elapsed_hours * self._vessel.max_speed_knots

        # Clamp to total route distance
        distance_travelled_nm = min(distance_travelled_nm, self._total_distance_nm)

        # Normalised progress
        self.progress = distance_travelled_nm / self._total_distance_nm

        # Update position via linear interpolation along waypoints
        self._update_position_from_distance(distance_travelled_nm)

        # Determine arrival
        if self.progress >= 1.0 - 1e-9:  # tolerance for floating‑point
            self.progress = 1.0
            self.status = "ARRIVED"
            # Snap to final waypoint for cleanliness
            final_wp = (
                self._route.waypoints[-1]
                if isinstance(self._route.waypoints[-1], Waypoint)
                else Waypoint(**self._route.waypoints[-1])
            )
            self.current_latitude = final_wp.latitude
            self.current_longitude = final_wp.longitude

    def _update_position_from_distance(self, travelled_nm: float) -> None:
        """
        Helper: set ``current_latitude`` / ``current_longitude`` based on travelled distance.

        The method walks the cumulative distance list to find the segment the
        vessel is currently on and then linearly interpolates between the two
        bounding waypoints.
        """
        # Find segment index where cumulative[i] <= travelled < cumulative[i+1]
        cum = self._cumulative_distances_nm
        seg_idx = 0
        while seg_idx < len(cum) - 1 and travelled_nm >= cum[seg_idx + 1]:
            seg_idx += 1

        # Edge cases – at the very start or end
        if seg_idx >= len(cum) - 1:
            wp = self._route.waypoints[-1]
            if not isinstance(wp, Waypoint):
                wp = Waypoint(**wp)
            self.current_latitude = wp.latitude
            self.current_longitude = wp.longitude
            return
        if seg_idx == 0 and travelled_nm <= 0:
            wp = self._route.waypoints[0]
            if not isinstance(wp, Waypoint):
                wp = Waypoint(**wp)
            self.current_latitude = wp.latitude
            self.current_longitude = wp.longitude
            return

        # Interpolate within the segment
        wp_start = self._route.waypoints[seg_idx]
        wp_end = self._route.waypoints[seg_idx + 1]
        if not isinstance(wp_start, Waypoint):
            wp_start = Waypoint(**wp_start)
        if not isinstance(wp_end, Waypoint):
            wp_end = Waypoint(**wp_end)

        segment_start_nm = cum[seg_idx]
        segment_end_nm = cum[seg_idx + 1]
        segment_len = segment_end_nm - segment_start_nm
        if segment_len == 0:
            fraction = 0.0
        else:
            fraction = (travelled_nm - segment_start_nm) / segment_len

        self.current_latitude = wp_start.latitude + fraction * (wp_end.latitude - wp_start.latitude)
        self.current_longitude = wp_start.longitude + fraction * (wp_end.longitude - wp_start.longitude)

    # --------------------------------------------------------------------- #
    # Query helpers
    # --------------------------------------------------------------------- #
    def get_current_position(self) -> Tuple[float, float]:
        """
        Return the vessel's current latitude and longitude as a ``(lat, lon)`` tuple.
        """
        return self.current_latitude, self.current_longitude

    def get_progress(self) -> float:
        """
        Return the normalised progress along the route (0.0 → 1.0).
        """
        return self.progress

    def is_arrived(self) -> bool:
        """
        Return ``True`` if the vessel has reached the end of its route.
        """
        return self.status == "ARRIVED"

    # --------------------------------------------------------------------- #
    # Representation
    # --------------------------------------------------------------------- #
    def __repr__(self) -> str:  # pragma: no cover
        return (
            f"<SimulatedVessel id={self.vessel_id!r} route={self.route_id!r} "
            f"status={self.status} progress={self.progress:.3f}>"
        )