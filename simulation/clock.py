from __future__ import annotations

from datetime import datetime, timedelta, timezone
import time


class SimulationClock:
    """
    Deterministic simulation clock.

    Simulation time advances according to:

        simulation time =
            start time + elapsed real time * speed multiplier

    The clock can also be manually advanced while paused.
    """

    def __init__(
        self,
        start_datetime: datetime | None = None,
        speed_multiplier: float = 1.0,
    ) -> None:

        if start_datetime is None:
            start_datetime = datetime.now(timezone.utc)

        if start_datetime.tzinfo is None:
            raise ValueError(
                "start_datetime must be timezone-aware"
            )

        if speed_multiplier <= 0:
            raise ValueError(
                "speed_multiplier must be positive"
            )

        self._initial_datetime = start_datetime.astimezone(
            timezone.utc
        )

        self._simulation_datetime = self._initial_datetime

        self._speed_multiplier = float(
            speed_multiplier
        )

        self._running = False

        self._last_real_time: float | None = None

    @property
    def speed_multiplier(self) -> float:
        """Current simulation speed multiplier."""

        return self._speed_multiplier

    @property
    def running(self) -> bool:
        """Whether the clock is currently running."""

        return self._running

    @property
    def simulation_datetime(self) -> datetime:
        """Current simulation datetime in UTC."""

        if self._running:
            self._synchronize()

        return self._simulation_datetime

    @property
    def current_datetime(self) -> datetime:
        """Alias for simulation_datetime."""

        return self.simulation_datetime

    def start(self) -> None:
        """Start or resume the simulation clock."""

        if self._running:
            return

        self._last_real_time = time.monotonic()
        self._running = True

    def pause(self) -> None:
        """Pause the simulation clock."""

        if not self._running:
            return

        self._synchronize()
        self._running = False
        self._last_real_time = None

    def reset(self) -> None:
        """Reset the clock to its original starting datetime."""

        self._running = False
        self._last_real_time = None
        self._simulation_datetime = self._initial_datetime

    def set_speed(
        self,
        speed_multiplier: float,
    ) -> None:
        """
        Change the simulation speed.

        The current simulation time is synchronized before
        changing the multiplier.
        """

        if speed_multiplier <= 0:
            raise ValueError(
                "speed_multiplier must be positive"
            )

        if self._running:
            self._synchronize()

        self._speed_multiplier = float(
            speed_multiplier
        )

        if self._running:
            self._last_real_time = time.monotonic()

    def advance(
        self,
        seconds: float,
    ) -> None:
        """
        Manually advance simulation time.

        Manual advancement is allowed while paused.
        """

        if seconds < 0:
            raise ValueError(
                "seconds must be non-negative"
            )

        if self._running:
            self._synchronize()

        self._simulation_datetime += timedelta(
            seconds=seconds
        )

        if self._running:
            self._last_real_time = time.monotonic()

    def _synchronize(self) -> None:
        """Synchronize simulation time with real elapsed time."""

        if not self._running:
            return

        if self._last_real_time is None:
            self._last_real_time = time.monotonic()
            return

        now = time.monotonic()

        elapsed_real_seconds = (
            now - self._last_real_time
        )

        simulation_seconds = (
            elapsed_real_seconds
            * self._speed_multiplier
        )

        self._simulation_datetime += timedelta(
            seconds=simulation_seconds
        )

        self._last_real_time = now

    def __repr__(self) -> str:
        return (
            "SimulationClock("
            f"simulation_datetime="
            f"{self.simulation_datetime.isoformat()}, "
            f"speed_multiplier="
            f"{self.speed_multiplier}, "
            f"running={self.running}"
            ")"
        )


__all__ = [
    "SimulationClock",
]