from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Optional

from simulation.environment import (
    EnvironmentConditions,
    normal_conditions,
    storm_conditions,
    heavy_ice_conditions,
)


@dataclass(frozen=True)
class EnvironmentEvent:
    """
    A simulated environmental event occurring during a voyage.
    """

    start_datetime: datetime
    end_datetime: datetime
    conditions: EnvironmentConditions
    name: str = "Environmental Event"

    def __post_init__(self):
        if self.end_datetime <= self.start_datetime:
            raise ValueError("end_datetime must be after start_datetime.")

    def is_active(self, current_datetime: datetime) -> bool:
        return (
            self.start_datetime
            <= current_datetime
            < self.end_datetime
        )


class EnvironmentTimeline:
    """
    Provides environmental conditions for a simulated voyage
    based on time-dependent events.
    """

    def __init__(
        self,
        events: Optional[list[EnvironmentEvent]] = None,
        default_conditions: Optional[EnvironmentConditions] = None,
    ):
        self.events = events or []
        self.default_conditions = (
            default_conditions
            if default_conditions is not None
            else normal_conditions()
        )

    def add_event(self, event: EnvironmentEvent):
        self.events.append(event)

    def get_conditions(
        self,
        current_datetime: datetime,
    ) -> EnvironmentConditions:
        """
        Return the active environmental conditions.

        The latest-added active event takes precedence.
        """

        active_event = None

        for event in self.events:
            if event.is_active(current_datetime):
                active_event = event

        if active_event is not None:
            return active_event.conditions

        return self.default_conditions

    def active_event(
        self,
        current_datetime: datetime,
    ) -> Optional[EnvironmentEvent]:
        """
        Return the currently active event, if any.
        """

        for event in reversed(self.events):
            if event.is_active(current_datetime):
                return event

        return None

    def next_change_after(
        self,
        current_datetime: datetime,
    ) -> Optional[datetime]:
        """
        Return the next time at which environmental conditions
        may change.

        Both event starts and event ends are considered.
        """

        boundaries = []

        for event in self.events:
            if event.start_datetime > current_datetime:
                boundaries.append(event.start_datetime)

            if event.end_datetime > current_datetime:
                boundaries.append(event.end_datetime)

        if not boundaries:
            return None

        return min(boundaries)


def create_demo_timeline(
    start_datetime: datetime,
) -> EnvironmentTimeline:
    """
    Create a deterministic demonstration timeline.

    This uses simulated environmental data for development
    and demonstration purposes.
    """

    timeline = EnvironmentTimeline()

    timeline.add_event(
        EnvironmentEvent(
            start_datetime=start_datetime + timedelta(days=2),
            end_datetime=start_datetime + timedelta(days=4),
            conditions=heavy_ice_conditions(),
            name="Heavy Sea Ice",
        )
    )

    timeline.add_event(
        EnvironmentEvent(
            start_datetime=start_datetime + timedelta(days=4),
            end_datetime=start_datetime + timedelta(days=5),
            conditions=storm_conditions(),
            name="Severe Storm",
        )
    )

    return timeline