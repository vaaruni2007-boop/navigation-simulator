from __future__ import annotations

from datetime import datetime, timedelta


class SimulationClock:
    """
    Deterministic simulation clock.

    The clock can be started, paused, reset, and advanced manually.
    A speed multiplier can be used when running a real-time simulation.
    """

    def __init__(
        self,
        initial_datetime: datetime,
        speed_multiplier: float = 1.0,
    ) -> None:

        if initial_datetime.tzinfo is None:
            raise ValueError(
                "initial_datetime must be timezone-aware"
            )

        if speed_multiplier <= 0:
            raise ValueError(
                "speed_multiplier must be greater than zero"
            )

        self._initial_datetime = initial_datetime
        self._simulation_datetime = initial_datetime
        self._speed_multiplier = speed_multiplier
        self._running = False

    # ------------------------------------------------------------------
    # Properties
    # ------------------------------------------------------------------

    @property
    def current_datetime(self) -> datetime:
        """Return the current simulated datetime."""

        return self._simulation_datetime

    @property
    def simulation_datetime(self) -> datetime:
        """
        Backward-compatible alias for current_datetime.

        Some simulation-state code uses the older
        simulation_datetime name.
        """

        return self._simulation_datetime

    @property
    def start_datetime(self) -> datetime:
        """Return the original datetime at which the simulation began."""

        return self._initial_datetime

    @property
    def initial_datetime(self) -> datetime:
        """Alias for start_datetime."""

        return self._initial_datetime

    @property
    def speed_multiplier(self) -> float:
        """Return the current simulation speed multiplier."""

        return self._speed_multiplier

    @property
    def is_running(self) -> bool:
        """Return whether the simulation clock is currently running."""

        return self._running

    # ------------------------------------------------------------------
    # Controls
    # ------------------------------------------------------------------

    def start(self) -> None:
        """Start the simulation clock."""

        self._running = True

    def pause(self) -> None:
        """Pause the simulation clock."""

        self._running = False

    def resume(self) -> None:
        """Resume the simulation clock."""

        self._running = True

    def reset(self) -> None:
        """Return the clock to its initial datetime and pause it."""

        self._simulation_datetime = self._initial_datetime
        self._running = False

    def set_speed(
        self,
        speed_multiplier: float,
    ) -> None:
        """Change the simulation speed multiplier."""

        if speed_multiplier <= 0:
            raise ValueError(
                "speed_multiplier must be greater than zero"
            )

        self._speed_multiplier = speed_multiplier

    # ------------------------------------------------------------------
    # Time advancement
    # ------------------------------------------------------------------

    def advance(
        self,
        seconds: float,
    ) -> datetime:
        """
        Advance simulated time.

        Parameters
        ----------
        seconds:
            Amount of real-time seconds to advance.

        Returns
        -------
        datetime
            Updated simulated datetime.

        Notes
        -----
        The supplied number of seconds is multiplied by the current
        simulation speed.
        """

        if seconds < 0:
            raise ValueError(
                "seconds must be greater than or equal to zero"
            )

        simulated_seconds = (
            seconds * self._speed_multiplier
        )

        self._simulation_datetime += timedelta(
            seconds=simulated_seconds
        )

        return self._simulation_datetime

    def tick(
        self,
        seconds: float,
    ) -> datetime:
        """
        Compatibility alias for advance().
        """

        return self.advance(seconds)

    # ------------------------------------------------------------------
    # Utility methods
    # ------------------------------------------------------------------

    def elapsed_seconds(self) -> float:
        """Return simulated seconds elapsed since the initial datetime."""

        return (
            self._simulation_datetime
            - self._initial_datetime
        ).total_seconds()

    def elapsed_days(self) -> float:
        """Return simulated days elapsed since the initial datetime."""

        return self.elapsed_seconds() / 86400.0

    def __repr__(self) -> str:
        return (
            f"SimulationClock("
            f"current_datetime={self.current_datetime!r}, "
            f"speed_multiplier={self.speed_multiplier}, "
            f"running={self.is_running}"
            f")"
        )


__all__ = [
    "SimulationClock",
]