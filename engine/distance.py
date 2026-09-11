"""engine.distance
===================

Utility functions for geographic distance calculations used by the Antarctic
Maritime Resupply Navigation Simulator.

The module provides:

1. ``haversine_distance_km`` – great‑circle distance between two latitude/longitude
   points expressed in kilometres.
2. ``haversine_distance_nm`` – the same distance expressed in nautical miles.
3. ``calculate_route_distance_km`` – total distance of a route defined by a
   sequence of waypoints.

All functions are deterministic, type‑annotated and include basic validation.
"""

from __future__ import annotations

from dataclasses import dataclass
from math import radians, sin, cos, sqrt, atan2
from typing import Iterable, List

# Earth radius in kilometres – mean radius as defined by the IUGG.
_EARTH_RADIUS_KM = 6371.0088
_NM_TO_KM = 1.852  # 1 nautical mile = 1.852 km


@dataclass(frozen=True)
class Waypoint:
    """Geographic waypoint.

    Attributes
    ----------
    latitude: float
        Latitude in decimal degrees. Must be in the range ``[-90, 90]``.
    longitude: float
        Longitude in decimal degrees. Must be in the range ``[-180, 180]``.
    """

    latitude: float
    longitude: float

    def __post_init__(self) -> None:
        if not -90.0 <= self.latitude <= 90.0:
            raise ValueError(f"Latitude {self.latitude!r} out of range [-90, 90]")
        if not -180.0 <= self.longitude <= 180.0:
            raise ValueError(f"Longitude {self.longitude!r} out of range [-180, 180]")


def _haversine(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Core haversine implementation.

    Parameters
    ----------
    lat1, lon1, lat2, lon2: float
        Coordinates in decimal degrees.

    Returns
    -------
    float
        Great‑circle distance in kilometres.
    """
    # Convert decimal degrees to radians
    φ1, λ1, φ2, λ2 = map(radians, (lat1, lon1, lat2, lon2))

    dφ = φ2 - φ1
    dλ = λ2 - λ1

    a = sin(dφ / 2) ** 2 + cos(φ1) * cos(φ2) * sin(dλ / 2) ** 2
    c = 2 * atan2(sqrt(a), sqrt(1 - a))
    return _EARTH_RADIUS_KM * c


def haversine_distance_km(point1: Waypoint, point2: Waypoint) -> float:
    """Return the great‑circle distance between *point1* and *point2* in kilometres.

    The function validates the coordinate ranges via :class:`Waypoint` and raises
    ``ValueError`` if either point is out of bounds.
    """
    return _haversine(
        point1.latitude,
        point1.longitude,
        point2.latitude,
        point2.longitude,
    )


def haversine_distance_nm(point1: Waypoint, point2: Waypoint) -> float:
    """Return the great‑circle distance between *point1* and *point2* in nautical miles.

    The conversion uses the exact factor ``1 NM = 1.852 km``.
    """
    km = haversine_distance_km(point1, point2)
    return km / _NM_TO_KM


def calculate_route_distance_km(waypoints: Iterable[Waypoint]) -> float:
    """Calculate the total route distance in kilometres.

    The *waypoints* iterable must contain at least two waypoints. The function
    sums the haversine distance between each consecutive pair. If the iterable
    contains fewer than two points a ``ValueError`` is raised.

    Parameters
    ----------
    waypoints: Iterable[Waypoint]
        Ordered collection of geographic points defining the route.

    Returns
    -------
    float
        Total distance of the route in kilometres.
    """
    wp_list: List[Waypoint] = list(waypoints)
    if len(wp_list) < 2:
        raise ValueError(
            "At least two waypoints are required to calculate a route distance"
        )

    total = 0.0
    for start, end in zip(wp_list, wp_list[1:]):
        total += haversine_distance_km(start, end)
    return total


__all__ = [
    "Waypoint",
    "haversine_distance_km",
    "haversine_distance_nm",
    "calculate_route_distance_km",
]