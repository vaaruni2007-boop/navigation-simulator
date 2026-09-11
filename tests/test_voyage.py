from datetime import datetime, timezone

import pytest

from engine.voyage import (
    knots_to_kmh,
    voyage_duration_hours,
    voyage_duration_days,
    estimated_arrival,
)


def test_knots_to_kmh():
    assert knots_to_kmh(1.0) == pytest.approx(
        1.852
    )


def test_knots_to_kmh_zero():
    assert knots_to_kmh(0.0) == pytest.approx(
        0.0
    )


def test_voyage_duration_hours():
    # 10 nautical miles at 10 knots = 1 hour.
    assert voyage_duration_hours(
        distance_nm=10.0,
        speed_knots=10.0,
    ) == pytest.approx(1.0)


def test_voyage_duration_days():
    # 240 NM at 10 knots = 24 hours = 1 day.
    assert voyage_duration_days(
        distance_nm=240.0,
        speed_knots=10.0,
    ) == pytest.approx(1.0)


def test_zero_distance_has_zero_duration():
    assert voyage_duration_hours(
        distance_nm=0.0,
        speed_knots=10.0,
    ) == pytest.approx(0.0)


def test_negative_distance_is_rejected():
    with pytest.raises(ValueError):
        voyage_duration_hours(
            distance_nm=-10.0,
            speed_knots=10.0,
        )


def test_zero_speed_is_rejected():
    with pytest.raises(ValueError):
        voyage_duration_hours(
            distance_nm=100.0,
            speed_knots=0.0,
        )


def test_negative_speed_is_rejected():
    with pytest.raises(ValueError):
        voyage_duration_hours(
            distance_nm=100.0,
            speed_knots=-5.0,
        )


def test_estimated_arrival():
    departure = datetime(
        2026,
        12,
        1,
        0,
        0,
        tzinfo=timezone.utc,
    )

    arrival = estimated_arrival(
        departure=departure,
        distance_nm=240.0,
        speed_knots=10.0,
    )

    assert arrival == datetime(
        2026,
        12,
        2,
        0,
        0,
        tzinfo=timezone.utc,
    )
