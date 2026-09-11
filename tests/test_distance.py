# -*- coding: utf-8 -*-
"""
tests/test_distance.py
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Pytest suite for the geographic utilities in ``engine/distance.py``.
"""

from __future__ import annotations

import math
import pytest

from engine.distance import (
    Waypoint,
    haversine_distance_km,
    haversine_distance_nm,
    calculate_route_distance_km,
)


# ----------------------------------------------------------------------
# Helper constants for deterministic expectations
# ----------------------------------------------------------------------
# Approximate distance (km) between (0°, 0°) and (0°, 1°) at the equator.
# The haversine formula yields about 111.19492664455873 km.
_EQUATOR_1DEG_KM = 111.19492664455873
_EQUATOR_1DEG_NM = _EQUATOR_1DEG_KM / 1.852  # exact nautical‑mile conversion


def test_identical_coordinates_return_zero_distance() -> None:
    """Two identical waypoints must have zero distance in both km and NM."""
    p = Waypoint(latitude=10.0, longitude=20.0)
    assert haversine_distance_km(p, p) == pytest.approx(0.0, abs=1e-9)
    assert haversine_distance_nm(p, p) == pytest.approx(0.0, abs=1e-9)


def test_known_geographic_distance_is_approximately_correct() -> None:
    """
    Verify the haversine distance between two points on the equator
    (0°,0°) and (0°,1°). The expected value is known to high precision.
    """
    p1 = Waypoint(latitude=0.0, longitude=0.0)
    p2 = Waypoint(latitude=0.0, longitude=1.0)
    dist_km = haversine_distance_km(p1, p2)
    assert dist_km == pytest.approx(_EQUATOR_1DEG_KM, rel=1e-6)


def test_nautical_mile_conversion_is_correct() -> None:
    """
    The nautic‑mile conversion uses the exact factor 1 NM = 1.852 km.
    """
    p1 = Waypoint(latitude=0.0, longitude=0.0)
    p2 = Waypoint(latitude=0.0, longitude=1.0)
    dist_nm = haversine_distance_nm(p1, p2)
    assert dist_nm == pytest.approx(_EQUATOR_1DEG_NM, rel=1e-6)


def test_route_distance_equals_sum_of_segment_distances() -> None:
    """
    Create a three‑point route and ensure the total route distance is the
    sum of the two segment distances.
    """
    wp_a = Waypoint(latitude=0.0, longitude=0.0)
    wp_b = Waypoint(latitude=0.0, longitude=1.0)   # ~111.19 km east of wp_a
    wp_c = Waypoint(latitude=1.0, longitude=1.0)   # ~111.19 km north of wp_b

    # Individual segment distances
    seg1 = haversine_distance_km(wp_a, wp_b)
    seg2 = haversine_distance_km(wp_b, wp_c)

    total = calculate_route_distance_km([wp_a, wp_b, wp_c])
    assert total == pytest.approx(seg1 + seg2, rel=1e-6)


def test_invalid_latitude_raises_value_error() -> None:
    """Waypoint latitude outside [-90, 90] must raise a ValueError."""
    with pytest.raises(ValueError, match="Latitude"):
        Waypoint(latitude=120.0, longitude=0.0)


def test_invalid_longitude_raises_value_error() -> None:
    """Waypoint longitude outside [-180, 180] must raise a ValueError."""
    with pytest.raises(ValueError, match="Longitude"):
        Waypoint(latitude=0.0, longitude=250.0)


@pytest.mark.parametrize(
    "waypoints",
    [
        [],                    # empty sequence
        [Waypoint(0, 0)],     # single waypoint
    ],
)
def test_route_distance_invalid_waypoint_sequences(waypoints):
    """
    ``calculate_route_distance_km`` must raise a ValueError when fewer than
    two waypoints are supplied.
    """
    with pytest.raises(ValueError, match="At least two waypoints"):
        calculate_route_distance_km(waypoints)