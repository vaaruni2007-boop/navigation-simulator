from datetime import datetime, timedelta, timezone

import pytest

from engine.deadline import (
    calculate_arrival_deadline,
    has_arrived_before_deadline,
)


def test_calculate_arrival_deadline():
    critical_date = datetime(
        2026,
        12,
        20,
        tzinfo=timezone.utc,
    )

    deadline = calculate_arrival_deadline(
        critical_date=critical_date,
        safety_buffer_days=3.0,
    )

    assert deadline == datetime(
        2026,
        12,
        17,
        tzinfo=timezone.utc,
    )


def test_zero_safety_buffer():
    critical_date = datetime(
        2026,
        12,
        20,
        tzinfo=timezone.utc,
    )

    deadline = calculate_arrival_deadline(
        critical_date=critical_date,
        safety_buffer_days=0.0,
    )

    assert deadline == critical_date


def test_negative_safety_buffer_is_rejected():
    critical_date = datetime(
        2026,
        12,
        20,
        tzinfo=timezone.utc,
    )

    with pytest.raises(ValueError):
        calculate_arrival_deadline(
            critical_date=critical_date,
            safety_buffer_days=-1.0,
        )


def test_arrival_before_deadline():
    deadline = datetime(
        2026,
        12,
        20,
        tzinfo=timezone.utc,
    )

    arrival = deadline - timedelta(
        days=1
    )

    assert has_arrived_before_deadline(
        arrival,
        deadline,
    ) is True


def test_arrival_exactly_on_deadline():
    deadline = datetime(
        2026,
        12,
        20,
        tzinfo=timezone.utc,
    )

    assert has_arrived_before_deadline(
        deadline,
        deadline,
    ) is True


def test_arrival_after_deadline():
    deadline = datetime(
        2026,
        12,
        20,
        tzinfo=timezone.utc,
    )

    arrival = deadline + timedelta(
        days=1
    )

    assert has_arrived_before_deadline(
        arrival,
        deadline,
    ) is False