import pytest

from engine.distance import (
    haversine_distance_km,
    km_to_nm,
    nm_to_km,
    route_distance_km,
    route_distance_nm,
)
from engine.models import Waypoint


def test_haversine_distance_zero():
    point = Waypoint(
        latitude=20.0,
        longitude=70.0,
    )

    assert haversine_distance_km(point, point) == pytest.approx(0.0)


def test_haversine_distance_known_points():
    point_a = Waypoint(
        latitude=0.0,
        longitude=0.0,
    )

    point_b = Waypoint(
        latitude=0.0,
        longitude=1.0,
    )

    distance = haversine_distance_km(
        point_a,
        point_b,
    )

    # One degree of longitude at the equator
    # is approximately 111.2 km.
    assert distance == pytest.approx(
        111.2,
        abs=0.5,
    )


def test_km_to_nm():
    assert km_to_nm(1.852) == pytest.approx(1.0)


def test_nm_to_km():
    assert nm_to_km(1.0) == pytest.approx(1.852)


def test_distance_conversions_are_inverse():
    original_km = 15000.0

    converted_nm = km_to_nm(original_km)
    converted_back = nm_to_km(converted_nm)

    assert converted_back == pytest.approx(
        original_km
    )


def test_route_distance_km():
    waypoints = [
        Waypoint(
            latitude=0.0,
            longitude=0.0,
        ),
        Waypoint(
            latitude=0.0,
            longitude=1.0,
        ),
    ]

    distance = route_distance_km(
        waypoints
    )

    assert distance == pytest.approx(
        111.2,
        abs=0.5,
    )


def test_route_distance_nm():
    waypoints = [
        Waypoint(
            latitude=0.0,
            longitude=0.0,
        ),
        Waypoint(
            latitude=0.0,
            longitude=1.0,
        ),
    ]

    distance_nm = route_distance_nm(
        waypoints
    )

    assert distance_nm == pytest.approx(
        60.0,
        abs=0.5,
    )


def test_route_requires_at_least_two_waypoints():
    waypoints = [
        Waypoint(
            latitude=0.0,
            longitude=0.0,
        )
    ]

    with pytest.raises(ValueError):
        route_distance_km(waypoints)