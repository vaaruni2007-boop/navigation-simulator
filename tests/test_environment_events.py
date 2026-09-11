from datetime import datetime, timedelta, timezone

import pytest

from simulation.environment import (
    storm_conditions,
)
from simulation.environment_events import (
    EnvironmentEvent,
    EnvironmentTimeline,
    create_demo_timeline,
)


def make_start():
    return datetime(
        2026,
        12,
        1,
        tzinfo=timezone.utc,
    )


def test_event_requires_positive_duration():
    start = make_start()

    with pytest.raises(ValueError):
        EnvironmentEvent(
            start_datetime=start,
            end_datetime=start,
            conditions=storm_conditions(),
        )


def test_timeline_returns_default_conditions():
    timeline = EnvironmentTimeline()

    conditions = timeline.get_conditions(make_start())

    assert conditions is timeline.default_conditions


def test_timeline_returns_active_event():
    start = make_start()

    event = EnvironmentEvent(
        start_datetime=start,
        end_datetime=start + timedelta(days=1),
        conditions=storm_conditions(),
        name="Storm",
    )

    timeline = EnvironmentTimeline(
        events=[event]
    )

    conditions = timeline.get_conditions(
        start + timedelta(hours=12)
    )

    assert conditions is event.conditions


def test_timeline_returns_default_after_event():
    start = make_start()

    event = EnvironmentEvent(
        start_datetime=start,
        end_datetime=start + timedelta(days=1),
        conditions=storm_conditions(),
    )

    timeline = EnvironmentTimeline(
        events=[event]
    )

    conditions = timeline.get_conditions(
        start + timedelta(days=2)
    )

    assert conditions is timeline.default_conditions


def test_event_is_active():
    start = make_start()

    event = EnvironmentEvent(
        start_datetime=start,
        end_datetime=start + timedelta(days=2),
        conditions=storm_conditions(),
    )

    assert event.is_active(
        start + timedelta(days=1)
    )

    assert not event.is_active(
        start + timedelta(days=2)
    )


def test_demo_timeline_has_heavy_ice():
    start = make_start()

    timeline = create_demo_timeline(start)

    conditions = timeline.get_conditions(
        start + timedelta(days=3)
    )

    assert conditions.sea_ice_severity > 0


def test_demo_timeline_has_storm():
    start = make_start()

    timeline = create_demo_timeline(start)

    conditions = timeline.get_conditions(
        start + timedelta(days=4, hours=12)
    )

    assert conditions.weather_severity > 0


def test_demo_timeline_returns_normal_initially():
    start = make_start()

    timeline = create_demo_timeline(start)

    conditions = timeline.get_conditions(start)

    assert conditions.weather_severity == pytest.approx(0.0)
    assert conditions.sea_ice_severity == pytest.approx(0.0)


def test_next_change_after_returns_event_start():
    start = make_start()

    timeline = create_demo_timeline(start)

    next_change = timeline.next_change_after(
        start + timedelta(days=1)
    )

    assert next_change == start + timedelta(days=2)


def test_next_change_after_returns_event_end():
    start = make_start()

    timeline = create_demo_timeline(start)

    next_change = timeline.next_change_after(
        start + timedelta(days=3)
    )

    assert next_change == start + timedelta(days=4)


def test_next_change_after_returns_none_when_finished():
    start = make_start()

    timeline = create_demo_timeline(start)

    next_change = timeline.next_change_after(
        start + timedelta(days=6)
    )

    assert next_change is None