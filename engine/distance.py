from __future__ import annotations

import math
from typing import Sequence

from .models import Waypoint


EARTH_RADIUS_KM = 6371.0088
KM_PER_NAUTICAL_MILE = 1.852


def haversine_distance_km(
    point1: Waypoint,
    point2: Waypoint,
) -> float:
    """
    Calculate great-circle distance between two waypoints in kilometres.
    """

    latitude1 = math.radians(point1.latitude)
    latitude2 = math.radians(point2.latitude)

    delta_latitude = math.radians(
        point2.latitude - point1.latitude
    )
    delta_longitude = math.radians(
        point2.longitude - point1.longitude
    )

    a = (
        math.sin(delta_latitude / 2) ** 2
        + math.cos(latitude1)
        * math.cos(latitude2)
        * math.sin(delta_longitude / 2) ** 2
    )

    c = 2 * math.atan2(
        math.sqrt(a),
        math.sqrt(1 - a),
    )

    return EARTH_RADIUS_KM * c


def haversine_distance_nm(
    point1: Waypoint,
    point2: Waypoint,
) -> float:
    """Calculate great-circle distance between two waypoints in nautical miles."""

    return haversine_distance_km(point1, point2) / KM_PER_NAUTICAL_MILE


def calculate_route_distance_km(
    waypoints: Sequence[Waypoint],
) -> float:
    """Calculate total route distance from consecutive waypoints."""

    if len(waypoints) < 2:
        raise ValueError("At least two waypoints are required")

    return sum(
        haversine_distance_km(
            waypoints[index],
            waypoints[index + 1],
        )
        for index in range(len(waypoints) - 1)
    )


def calculate_route_distance_nm(
    waypoints: Sequence[Waypoint],
) -> float:
    """Calculate total route distance in nautical miles."""

    return calculate_route_distance_km(waypoints) / KM_PER_NAUTICAL_MILE


__all__ = [
    "haversine_distance_km",
    "haversine_distance_nm",
    "calculate_route_distance_km",
    "calculate_route_distance_nm",
]