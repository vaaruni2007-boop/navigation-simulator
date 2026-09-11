from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Dict, Optional

from engine.models import ResourceInventory, Route, Station, Vessel

from .clock import SimulationClock
from .environment_events import EnvironmentTimeline
from .state import SimulationState


@dataclass
class ResupplyMission:
    """
    High-level wrapper for one Antarctic resupply simulation.

    ResupplyMission manages mission-level information while
    SimulationState handles the actual vessel/time/environment simulation.
    """

    station: Station
    vessel: Vessel
    route: Route
    cargo_weight_tonnes: float
    departure_datetime: datetime
    station_inventory: Dict[str, ResourceInventory]

    safety_buffer_days: float = 3.0
    environment_timeline: Optional[EnvironmentTimeline] = None

    status: str = "PLANNED"
    simulation_state: Optional[SimulationState] = None

    def __post_init__(self) -> None:
        if self.cargo_weight_tonnes < 0:
            raise ValueError(
                "cargo_weight_tonnes must be non-negative."
            )

        if self.departure_datetime.tzinfo is None:
            raise ValueError(
                "departure_datetime must be timezone-aware."
            )

        if self.safety_buffer_days < 0:
            raise ValueError(
                "safety_buffer_days must be non-negative."
            )

    @classmethod
    def create(
        cls,
        station: Station,
        vessel: Vessel,
        route: Route,
        cargo_weight_tonnes: float,
        departure_datetime: datetime,
        station_inventory: Dict[str, ResourceInventory],
        safety_buffer_days: float = 3.0,
        environment_timeline: Optional[
            EnvironmentTimeline
        ] = None,
    ) -> "ResupplyMission":
        """Create a new planned resupply mission."""

        return cls(
            station=station,
            vessel=vessel,
            route=route,
            cargo_weight_tonnes=cargo_weight_tonnes,
            departure_datetime=departure_datetime,
            station_inventory=station_inventory,
            safety_buffer_days=safety_buffer_days,
            environment_timeline=environment_timeline,
        )

    def initialize(self) -> SimulationState:
        """
        Create the underlying SimulationState.

        Initialization prepares the simulation but does not start
        the voyage.
        """

        clock = SimulationClock(
            self.departure_datetime
        )

        self.simulation_state = SimulationState(
            clock=clock,
            station=self.station,
            vessel=self.vessel,
            route=self.route,
            station_inventory=self.station_inventory,
            safety_buffer_days=self.safety_buffer_days,
            environment_timeline=self.environment_timeline,
        )

        return self.simulation_state

    def start(self) -> SimulationState:
        """
        Start the resupply mission.

        If the mission has not been initialized yet, initialize it first.
        """

        if self.status == "RUNNING":
            return self.simulation_state

        if self.status == "COMPLETED":
            raise RuntimeError(
                "A completed mission cannot be started again."
            )

        if self.status == "PAUSED":
            return self.resume()

        if self.simulation_state is None:
            self.initialize()

        self.simulation_state.start()

        self.status = "RUNNING"

        return self.simulation_state

    def update(self, elapsed_seconds: float) -> SimulationState:
        """
        Advance the mission simulation.

        SimulationState is responsible for applying environmental
        conditions, vessel movement, fuel consumption and inventory
        depletion.
        """

        if elapsed_seconds < 0:
            raise ValueError(
                "elapsed_seconds must be non-negative."
            )

        if self.simulation_state is None:
            raise RuntimeError(
                "Mission must be started before it can be updated."
            )

        if self.status not in {"RUNNING", "PAUSED"}:
            raise RuntimeError(
                "Only a running or paused mission can be updated."
            )

        self.simulation_state.update(elapsed_seconds)

        simulation_status = self.simulation_state.status.lower()

        if simulation_status == "completed":
            self.status = "COMPLETED"
        elif simulation_status == "paused":
            self.status = "PAUSED"
        elif simulation_status == "running":
            self.status = "RUNNING"

        return self.simulation_state

    def resume(self) -> SimulationState:
        """
        Resume a paused mission.
        """

        if self.simulation_state is None:
            raise RuntimeError(
                "Mission must be initialized before it can be resumed."
            )

        if self.status != "PAUSED":
            raise RuntimeError(
                "Only a paused mission can be resumed."
            )

        self.simulation_state.resume()
        self.status = "RUNNING"

        return self.simulation_state

    @property
    def simulation_datetime(self) -> datetime:
        """Return the current mission simulation time."""

        if self.simulation_state is None:
            return self.departure_datetime

        return self.simulation_state.simulation_datetime

    @property
    def vessel_position(self):
        """Return the current simulated vessel position."""

        if self.simulation_state is None:
            raise RuntimeError(
                "Mission must be initialized before accessing vessel position."
            )

        return self.simulation_state.vessel_position

    @property
    def progress_fraction(self) -> float:
        """Return voyage completion as a fraction from 0 to 1."""

        if self.simulation_state is None:
            return 0.0

        return self.simulation_state.vessel_progress

    @property
    def progress_percent(self) -> float:
        """Return voyage completion as a percentage."""

        return self.progress_fraction * 100.0

    @property
    def fuel_consumed_litres(self) -> float:
        """Return fuel consumed so far."""

        if self.simulation_state is None:
            return 0.0

        return self.simulation_state.fuel_consumed_litres

    @property
    def current_inventory(self) -> Dict[str, float]:
        """Return the current simulated station inventory."""

        if self.simulation_state is None:
            return {
                name: inventory.current_quantity
                for name, inventory in self.station_inventory.items()
            }

        return dict(self.simulation_state.current_inventory)

    @property
    def current_environment(self):
        """Return the environment currently affecting the mission."""

        if self.simulation_state is None:
            return None

        return self.simulation_state.current_environment

    @property
    def active_environment_event(self) -> Optional[str]:
        """Return the name of the active environmental event, if any."""

        if self.simulation_state is None:
            return None

        return self.simulation_state.active_environment_event

    def get_state(self) -> dict:
        """
        Return the current mission state.

        Before initialization, return basic planned-mission information.
        After initialization, include the complete SimulationState.
        """

        if self.simulation_state is None:
            return {
                "status": self.status,
                "station": {
                    "id": self.station.id,
                    "name": self.station.name,
                },
                "vessel": {
                    "id": self.vessel.id,
                    "name": self.vessel.name,
                },
                "route": {
                    "id": self.route.id,
                    "name": self.route.name,
                },
                "cargo_weight_tonnes": self.cargo_weight_tonnes,
                "departure_datetime": (
                    self.departure_datetime.isoformat()
                ),
                "progress_percent": 0.0,
            }

        state = self.simulation_state.get_state()

        state["mission"] = {
            "cargo_weight_tonnes": self.cargo_weight_tonnes,
            "departure_datetime": (
                self.departure_datetime.isoformat()
            ),
            "status": self.status,
        }

        return state


__all__ = ["ResupplyMission"]