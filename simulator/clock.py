# -*- coding: utf-8 -*-
"""
simulation/clock.py
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Deterministic simulation clock for Antarctic voyage simulations.

The :class:`SimulationClock` provides a controllable notion of simulated time
that can run faster (or slower) than real time.  It is deliberately *pure* –
no background threads, no asyncio, and no external services – so it is fully
testable and reproducible.

Typical usage::

    from datetime import datetime, timezone
    from simulation.clock import SimulationClock

    # Initialise the clock at a known UTC moment.
    start = datetime(2026, 9, 1, 0, 0, tzinfo=timezone.utc)
    clock = SimulationClock(start)

    clock.set_speed(60)   # 60× – 1 real second = 1 simulated minute
    clock.start()
    # … after some real time …
    now = clock.current_datetime

    clock.pause()
    # Manually jump forward, useful for unit tests.
    clock.advance(3600)   # +1 hour simulated time

The implementation tracks:

* ``_base_datetime`` – the simulated time at the moment the clock was last
  paused or reset.
* ``_elapsed_real`` – cumulative *real* seconds that have passed while the
  clock was running.
* ``_start_real`` – timestamp from ``time.monotonic()`` recorded when the
  clock is started.
* ``speed_multiplier`` – how many simulated seconds pass per real second.
* ``running`` – whether the clock is currently advancing automatically.

All public methods validate their inputs and raise ``ValueError`` for illegal
states (e.g., negative speed).  The class is deliberately small and does not
depend on any external libraries beyond the Python standard library.
"""

from __future__ import annotations

import time
from datetime import datetime, timedelta, timezone
from typing import Optional


class SimulationClock:
    """Deterministic clock that can run faster or slower than real time.

    Parameters
    ----------
    start_datetime:
        The initial simulated datetime.  Must be timezone‑aware; UTC is used
        by default.
    speed_multiplier:
        Initial speed factor (simulated seconds per real second).  ``1.0``
        represents real‑time playback.
    """

    def __init__(self, start_datetime: Optional[datetime] = None, speed_multiplier: float = 1.0):
        if start_datetime is None:
            start_datetime = datetime.now(timezone.utc)
        if start_datetime.tzinfo is None:
            raise ValueError("start_datetime must be timezone‑aware")
        if speed_multiplier <= 0:
            raise ValueError("speed_multiplier must be positive")

        self._base_datetime: datetime = start_datetime
        self._elapsed_real: float = 0.0  # seconds of real time accumulated while running
        self._start_real: Optional[float] = None  # time.monotonic() value when started
        self.speed_multiplier: float = speed_multiplier
        self.running: bool = False

    # ---------------------------------------------------------------------
    # Public API
    # ---------------------------------------------------------------------
    def start(self) -> None:
        """Start (or resume) the automatic advancement of simulated time.

        If the clock is already running this call is a no‑op.
        """
        if not self.running:
            self._start_real = time.monotonic()
            self.running = True

    def pause(self) -> None:
        """Pause the clock, freezing the simulated datetime.

        The elapsed real‑time since the last :meth:`start` call is recorded so
        that the simulated time can be reconstructed later.
        """
        if self.running:
            now = time.monotonic()
            assert self._start_real is not None  # for type‑checkers
            self._elapsed_real += now - self._start_real
            self._start_real = None
            self.running = False

    def reset(self, new_start: Optional[datetime] = None) -> None:
        """Reset the clock to a fresh state.

        ``new_start`` replaces the current simulation datetime; if omitted, the
        clock is reset to the original start time used at construction.
        The clock becomes paused after a reset.
        """
        self.pause()
        if new_start is not None:
            if new_start.tzinfo is None:
                raise ValueError("new_start must be timezone‑aware")
            self._base_datetime = new_start
        else:
            # Reset to the construction‑time baseline (which is stored in
            # ``_base_datetime`` already).  No change needed.
            pass
        self._elapsed_real = 0.0
        self.running = False

    def set_speed(self, multiplier: float) -> None:
        """Change the speed multiplier.

        The change takes effect immediately.  If the clock is running, the
        simulated datetime is first updated using the *old* speed before the
        new multiplier is stored, ensuring a seamless transition.
        """
        if multiplier <= 0:
            raise ValueError("speed multiplier must be positive")
        # Synchronise the simulated datetime up to this instant.
        if self.running:
            # Update base datetime with elapsed real time at the old speed.
            now = time.monotonic()
            assert self._start_real is not None
            self._elapsed_real += now - self._start_real
            self._base_datetime = self._base_datetime + timedelta(
                seconds=self._elapsed_real * self.speed_multiplier
            )
            # Reset counters for the new speed.
            self._elapsed_real = 0.0
            self._start_real = now
        self.speed_multiplier = multiplier

    def advance(self, seconds: float) -> None:
        """Manually advance the simulated time by *seconds*.

        This method is useful for unit tests or for deterministic jumps that
        are independent of real‑world time.  It works regardless of the clock's
        running state.
        """
        if seconds < 0:
            raise ValueError("cannot advance by a negative amount")
        self._base_datetime += timedelta(seconds=seconds)
        # If the clock is running we also want the elapsed‑real counter to stay
        # consistent; we therefore *do not* modify ``_elapsed_real`` because the
        # base datetime already absorbed the advancement.

    @property
    def simulation_datetime(self) -> datetime:
        """Current simulated datetime, accounting for real‑time progress.

        The returned value is always timezone‑aware (UTC).
        """
        if self.running:
            now = time.monotonic()
            assert self._start_real is not None
            elapsed = self._elapsed_real + (now - self._start_real)
            return self._base_datetime + timedelta(seconds=elapsed * self.speed_multiplier)
        else:
            return self._base_datetime

    # Alias that mirrors the name used in the request description.
    @property
    def current_datetime(self) -> datetime:
        """Alias for :pyattr:`simulation_datetime` (kept for backward compatibility)."""
        return self.simulation_datetime

    # ---------------------------------------------------------------------
    # Introspection helpers (not required but convenient for debugging)
    # ---------------------------------------------------------------------
    def __repr__(self) -> str:  # pragma: no cover
        state = "running" if self.running else "paused"
        return (
            f"<SimulationClock {state}, speed={self.speed_multiplier}×, "
            f"sim_time={self.simulation_datetime.isoformat()}>"
        )