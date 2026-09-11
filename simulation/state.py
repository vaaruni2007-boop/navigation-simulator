from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal
from typing import Dict, Optional

from engine import deadline as deadline_mod
from engine import fuel as fuel_mod
from engine import inventory as inventory_mod
from engine import voyage as voyage_mod

from engine.models import (
    ResourceInventory,
    Route,
    Station,
    Vessel,
)

from .clock import SimulationClock
from .vessel import SimulatedVessel


@dataclass
class SimulationState:
    """
    Complete runtime state of one simulated resupply voyage.
    """

    clock: SimulationClock

    station: Station
    vessel: Vessel
    route: Route

    station_inventory: Dict[
        str,
        ResourceInventory,
    ]

    safety_buffer_days: float = 3.0

    status: str = "PLANNED"

    simulated_vessel: SimulatedVessel = field(
        init=False
    )

    predicted_critical_date: Optional[datetime] = field(
        default=None,
        init=False,
    )

    latest_safe_arrival: Optional[datetime] = field(
        default=None,
        init=False,
    )

    estimated_arrival: Optional[datetime] = field(
        default=None,
        init=False,
    )

    estimated_total_fuel_litres: float = field(
        default=0.0,
        init=False,
    )

    fuel_consumed_litres: float = field(
        default=0.0,
        init=False,
    )

    estimated_total_cost: Decimal = field(
        default=Decimal("0"),
        init=False,
    )

    current_inventory: Dict[
        str,
        float,
    ] = field(
        default_factory=dict,
        init=False,
    )

    def __post_init__(self) -> None:
        if self.safety_buffer_days < 0:
            raise ValueError(
                "safety_buffer_days must be non-negative"
            )

        self.simulated_vessel = (
            SimulatedVessel.create_from_models(
                self.vessel,
                self.route,
            )
        )

        self.current_inventory = {
            resource_name: resource.current_quantity
            for resource_name, resource
            in self.station_inventory.items()
        }

        self._calculate_predictions()

    @property
    def simulation_datetime(self) -> datetime:
        """Current simulation time."""

        return self.clock.simulation_datetime

    @property
    def vessel_position(self):
        """Current simulated vessel position."""

        return self.simulated_vessel.current_position

    @property
    def vessel_progress(self) -> float:
        """Current voyage completion fraction."""

        return self.simulated_vessel.progress_fraction

    @property
    def estimated_voyage_duration_days(self) -> float:
        """Estimated total voyage duration."""

        return self.simulated_vessel.estimated_duration_days()

    def start(
        self,
        departure_datetime: Optional[datetime] = None,
    ) -> None:
        """
        Start the simulated voyage.

        If no departure time is supplied, the current
        simulation time is used.
        """

        if departure_datetime is None:
            departure_datetime = (
                self.clock.simulation_datetime
            )

        if departure_datetime.tzinfo is None:
            raise ValueError(
                "departure_datetime must be timezone-aware"
            )

        self.estimated_arrival = (
            self.simulated_vessel.estimated_arrival(
                departure_datetime
            )
        )

        self._calculate_predictions()

        self.simulated_vessel.start_voyage()

        self.clock.start()

        self.status = "EN_ROUTE"

    def pause(self) -> None:
        """Pause the simulation."""

        self.clock.pause()
        self.simulated_vessel.pause_voyage()

        if self.status == "EN_ROUTE":
            self.status = "PAUSED"

    def resume(self) -> None:
        """Resume a paused simulation."""

        if self.status != "PAUSED":
            return

        self.clock.start()
        self.simulated_vessel.start_voyage()

        self.status = "EN_ROUTE"

    def update(
        self,
        elapsed_seconds: float,
    ) -> None:
        """
        Advance the simulation.

        The caller supplies elapsed simulation seconds.
        """

        if elapsed_seconds < 0:
            raise ValueError(
                "elapsed_seconds must be non-negative"
            )

        if self.status not in {
            "EN_ROUTE",
            "PAUSED",
        }:
            return

        self.clock.advance(
            elapsed_seconds
        )

        self.simulated_vessel.update(
            elapsed_seconds
        )

        self._update_inventory()
        self._update_fuel_consumption()

        if self.simulated_vessel.is_complete:
            self.status = "COMPLETED"

        elif self.status == "EN_ROUTE":
            self.status = "EN_ROUTE"

    def reset(self) -> None:
        """Reset the entire simulation."""

        self.clock.reset()
        self.simulated_vessel.reset()

        self.status = "PLANNED"

        self.fuel_consumed_litres = 0.0

        self.current_inventory = {
            resource_name: resource.current_quantity
            for resource_name, resource
            in self.station_inventory.items()
        }

        self._calculate_predictions()

    def get_state(self) -> dict:
        """
        Return a JSON-serializable representation
        of the current simulation state.
        """

        return {
            "status": self.status,
            "simulation_datetime": (
                self.simulation_datetime.isoformat()
            ),
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
            "vessel_position": {
                "latitude": self.vessel_position.latitude,
                "longitude": self.vessel_position.longitude,
            },
            "vessel_progress": self.vessel_progress,
            "fuel_consumed_litres": (
                self.fuel_consumed_litres
            ),
            "estimated_total_fuel_litres": (
                self.estimated_total_fuel_litres
            ),
            "estimated_total_cost": str(
                self.estimated_total_cost
            ),
            "predicted_critical_date": (
                self.predicted_critical_date.isoformat()
                if self.predicted_critical_date
                else None
            ),
            "latest_safe_arrival": (
                self.latest_safe_arrival.isoformat()
                if self.latest_safe_arrival
                else None
            ),
            "estimated_arrival": (
                self.estimated_arrival.isoformat()
                if self.estimated_arrival
                else None
            ),
            "inventory": self.current_inventory.copy(),
        }

    def _calculate_predictions(self) -> None:
        """Calculate deadline, ETA, fuel and cost predictions."""

        current_datetime = (
            self.clock.simulation_datetime
        )

        critical_dates = []

        for resource in self.station_inventory.values():
            critical_date = (
                inventory_mod.calculate_critical_date(
                    resource,
                    current_datetime,
                )
            )

            if critical_date is not None:
                critical_dates.append(
                    critical_date
                )

        if critical_dates:
            self.predicted_critical_date = min(
                critical_dates
            )

            self.latest_safe_arrival = (
                deadline_mod.calculate_latest_safe_arrival(
                    self.predicted_critical_date,
                    self.safety_buffer_days,
                )
            )
        else:
            self.predicted_critical_date = None
            self.latest_safe_arrival = None

        self.estimated_total_fuel_litres = (
            fuel_mod.calculate_fuel_consumption(
                self.estimated_voyage_duration_days,
                self.vessel.fuel_consumption_litres_per_day,
            )
        )

        fuel_cost = fuel_mod.calculate_fuel_cost(
            self.estimated_total_fuel_litres,
            self.vessel.fuel_cost_per_litre,
        )

        from engine import cost as cost_mod

        operating_cost = (
            cost_mod.calculate_operating_cost(
                self.estimated_voyage_duration_days,
                self.vessel.operating_cost_per_day,
            )
        )

        self.estimated_total_cost = (
            cost_mod.calculate_total_cost(
                fuel_cost,
                operating_cost,
            )
        )

    def _update_inventory(self) -> None:
        """Update projected inventory at current simulation time."""

        current_datetime = (
            self.clock.simulation_datetime
        )

        for resource_name, resource in (
            self.station_inventory.items()
        ):
            self.current_inventory[
                resource_name
            ] = inventory_mod.calculate_inventory_on_date(
                resource,
                self._initial_simulation_datetime(),
                current_datetime,
            )

    def _initial_simulation_datetime(self) -> datetime:
        """Return the initial simulation datetime."""

        # The clock's reset operation returns to this point.
        # We obtain it without depending on the clock's private
        # implementation details by temporarily relying on its
        # current state only when no voyage has started.
        #
        # In normal operation, inventory projections are based
        # on the original simulation start.
        current = self.clock.simulation_datetime

        if self.status == "PLANNED":
            return current

        # The inventory projection is recalculated from the
        # simulation's original inventory reference time.
        #
        # This is stored lazily the first time it is needed.
        if not hasattr(self, "_inventory_reference_datetime"):
            self._inventory_reference_datetime = current

        return self._inventory_reference_datetime

    def _update_fuel_consumption(self) -> None:
        """Calculate fuel consumed based on voyage progress."""

        self.fuel_consumed_litres = (
            self.estimated_total_fuel_litres
            * self.simulated_vessel.progress_fraction
        )


__all__ = [
    "SimulationState",
]
