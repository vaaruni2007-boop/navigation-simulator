# -*- coding: utf-8 -*-
"""
simulation/state.py
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Core state container for a single Antarctic resupply simulation.

The :class:`SimulationState` tracks every piece of information that a frontend
might need to render a live view of the simulation:

* simulation time (via :class:`simulation.clock.SimulationClock`)
* the active vessel and its progress/position
* the active route
* the destination station’s inventory (modeled with ``engine.inventory.ResourceInventory``)
* derived dates such as the predicted critical inventory date, the latest safe
  arrival, and the vessel’s estimated arrival
* fuel usage and cost estimates
* a high‑level simulation status (PLANNED, EN_ROUTE, PAUSED, COMPLETED, FAILED)

All fields are kept in plain Python types (or Pydantic models) so that the
state can be trivially serialised to JSON later (e.g. via ``json.dumps(state.
to_dict())``).

The implementation is deliberately *pure* – it does not perform any I/O,
network calls, or UI work.
"""

from __future__ import annotations

import copy
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from typing import Dict, List, Tuple, Optional

import pydantic


# Engine utilities --------------------------------------------------------------
from ..engine import (
    cost as cost_mod,
    deadline as deadline_mod,
    fuel as fuel_mod,
    inventory as inventory_mod,
    distance as dist_mod,
)
from engine import vessels, routes, station, ResourceInventory, Waypoint

# Simulation helpers -------------------------------------------------------------
from .clock import SimulationClock
from .vessel import SimulatedVessel

class SimulationState(pydantic.BaseModel):
    """
    Complete mutable state for one resupply simulation.

    The class is a thin mutable container (not an immutable value object) because
    the simulation progresses step‑by‑step.  All public mutation occurs through
    the dedicated ``initialize`` / ``update`` / ``reset`` methods.
    """

    # --------------------------------------------------------------------- #
    # Core attributes – all are JSON‑serialisable after ``to_dict`` conversion
    # --------------------------------------------------------------------- #
    simulation_datetime: datetime = pydantic.Field(default_factory=lambda: datetime.now(timezone.utc))
    station_inventory: Dict[str, ResourceInventory] = pydantic.Field(default_factory=dict)
    active_vessel: Optional[SimulatedVessel] = None
    active_route: Optional[Route] = None
    vessel_position: Tuple[float, float] = (0.0, 0.0)  # (lat, lon)
    vessel_progress: float = 0.0
    current_inventory: Dict[str, ResourceInventory] = pydantic.Field(default_factory=dict)
    predicted_critical_date: Optional[datetime] = None
    latest_safe_arrival: Optional[datetime] = None
    estimated_arrival: Optional[datetime] = None
    fuel_consumed_l: float = 0.0
    estimated_total_fuel_l: float = 0.0
    estimated_total_cost: Decimal = Decimal("0")
    simulation_status: str = "PLANNED"  # PLANNED, EN_ROUTE, PAUSED, COMPLETED, FAILED

    # --------------------------------------------------------------------- #
    # Internal helpers (not part of the public JSON payload)
    # --------------------------------------------------------------------- #
    _clock: SimulationClock = pydantic.Field(default_factory=SimulationClock, exclude=True)
    _initial_snapshot: Optional["SimulationState"] = pydantic.Field(default=None, exclude=True)

    # --------------------------------------------------------------------- #
    # Public API
    # --------------------------------------------------------------------- #
    def initialize(
        self,
        start_datetime: datetime,
        vessel: Vessel,
        route: Route,
        station: Station,
        inventory_resources: List[ResourceInventory],
        speed_multiplier: float = 1.0,
    ) -> None:
        """
        Populate the state with a fresh simulation configuration.

        Parameters
        ----------
        start_datetime : datetime
            Initial simulation time (must be timezone‑aware, UTC preferred).
        vessel : Vessel
            Vessel definition.
        route : Route
            Maritime corridor the vessel will follow.
        station : Station
            Destination Antarctic station (used only for metadata; inventory
            handling is performed via ``inventory_resources``).
        inventory_resources : List[ResourceInventory]
            One ``ResourceInventory`` per resource the station tracks.
        speed_multiplier : float, optional
            Multiplier for the underlying :class:`SimulationClock`.  ``1.0``
            means real‑time playback.
        """
        if start_datetime.tzinfo is None:
            raise ValueError("start_datetime must be timezone‑aware")

        # Reset the deterministic clock
        self._clock = SimulationClock(start_datetime, speed_multiplier)

        # Build the simulated vessel from the provided models
        self.active_vessel = SimulatedVessel.create_from_models(vessel, route)
        self.active_route = route

        # Store a copy of the inventory – deep‑copy to avoid external mutation
        self.station_inventory = {inv.resource_name: copy.deepcopy(inv) for inv in inventory_resources}
        self.current_inventory = copy.deepcopy(self.station_inventory)

        # Initialise derived fields
        self.simulation_datetime = start_datetime
        self.vessel_position = (
            self.active_vessel.current_latitude,
            self.active_vessel.current_longitude,
        )
        self.vessel_progress = self.active_vessel.get_progress()
        self.fuel_consumed_l = 0.0
        self.estimated_total_fuel_l = float(
            self.active_vessel._total_distance_nm * vessel.fuel_consumption_l_per_nm
        )
        self.estimated_total_cost = Decimal("0")
        self.predicted_critical_date = None
        self.latest_safe_arrival = None
        self.estimated_arrival = None
        self.simulation_status = "PLANNED"

        # Preserve a snapshot for ``reset`` calls
        self._initial_snapshot = copy.deepcopy(self)

    def update(self, new_simulation_datetime: datetime) -> None:
        """
        Advance the simulation to ``new_simulation_datetime`` and recompute all
        derived values.

        The method performs the following steps (in order):

        1. Advance the internal :class:`SimulationClock`.
        2. Update the vessel’s position / progress.
        3. Update the station’s inventory based on consumption.
        4. Record fuel consumption up to the current point.
        5. Compute cost estimates.
        6. Evaluate schedule feasibility (arrival vs. latest safe arrival).
        7. Detect arrival and update the high‑level simulation status.
        """
        if new_simulation_datetime.tzinfo is None:
            raise ValueError("new_simulation_datetime must be timezone‑aware")
        if self.active_vessel is None or self.active_route is None:
            raise RuntimeError("Simulation must be initialised before calling update()")

        # -----------------------------------------------------------------
        # 1. Advance deterministic clock
        # -----------------------------------------------------------------
        self._clock._base_datetime = new_simulation_datetime  # deterministic set
        self.simulation_datetime = self._clock.current_datetime

        # -----------------------------------------------------------------
        # 2. Vessel position / progress
        # -----------------------------------------------------------------
        if self.simulation_status in ("PLANNED", "PAUSED"):
            # Vessel hasn't left yet – nothing to move.
            pass
        else:
            self.active_vessel.update(self.simulation_datetime)
            self.vessel_position = self.active_vessel.get_current_position()
            self.vessel_progress = self.active_vessel.get_progress()
            self.estimated_arrival = self.active_vessel.estimated_arrival_datetime

        # -----------------------------------------------------------------
        # 3. Station inventory consumption
        # -----------------------------------------------------------------
        # For each resource we project the inventory forward to the current time.
        for name, res_inv in self.current_inventory.items():
            projected = inventory_mod.calculate_inventory_on_date(
                current_datetime=self.simulation_datetime,
                target_datetime=self.simulation_datetime,
                current_quantity=res_inv.current_quantity,
                daily_consumption=res_inv.daily_consumption,
                unit=res_inv.unit,
                minimum_safety_threshold=res_inv.minimum_safety_threshold,
            )
            # ``calculate_inventory_on_date`` returns a ``ResourceInventory``.
            # Here we just update the quantity field.
            self.current_inventory[name].current_quantity = projected.current_quantity

        # -----------------------------------------------------------------
        # 4. Fuel consumption so far
        # -----------------------------------------------------------------
        if self.active_vessel and self.active_vessel.departure_datetime:
            elapsed_hours = (
                self.simulation_datetime - self.active_vessel.departure_datetime
            ).total_seconds() / 3600.0
            # Fuel consumption = elapsed_hours * speed_knots * fuel_per_nm
            fuel_used = (
                elapsed_hours
                * self.active_vessel._vessel.max_speed_knots
                * self.active_vessel._vessel.fuel_consumption_l_per_nm
            )
            self.fuel_consumed_l = float(min(fuel_used, self.estimated_total_fuel_l))
        else:
            self.fuel_consumed_l = 0.0

        # -----------------------------------------------------------------
        # 5. Cost estimates
        # -----------------------------------------------------------------
        operating_cost = cost_mod.calculate_operating_cost(
            voyage_mod.calculate_voyage_days(
                self.active_vessel._total_distance_nm,
                self.active_vessel._vessel.max_speed_knots,
            ),
            self.active_vessel._vessel.operating_cost_per_day,
        )
        fuel_cost = fuel_mod.calculate_fuel_cost(
            self.estimated_total_fuel_l, self.active_vessel._vessel.fuel_cost_per_litre
        )
        self.estimated_total_cost = cost_mod.calculate_total_cost(fuel_cost, operating_cost)

        # -----------------------------------------------------------------
        # 6. Schedule feasibility
        # -----------------------------------------------------------------
        # Predict when the station will hit its safety threshold.
        # We pick the first resource that has a non‑zero daily consumption as a
        # representative; in a richer implementation each resource would be
        # handled individually.
        critical_dates = []
        for inv in self.current_inventory.values():
            if inv.daily_consumption > 0:
                days_until = inventory_mod.calculate_days_until_threshold(
                    current_quantity=inv.current_quantity,
                    daily_consumption=inv.daily_consumption,
                    safety_threshold=inv.minimum_safety_threshold,
                )
                critical_date = self.simulation_datetime + timedelta(days=days_until)
                critical_dates.append(critical_date)

        if critical_dates:
            self.predicted_critical_date = min(critical_dates)
            self.latest_safe_arrival = deadline_mod.calculate_latest_safe_arrival(
                self.predicted_critical_date, safety_buffer_days=2
            )
        else:
            self.predicted_critical_date = None
            self.latest_safe_arrival = None

        # Determine if vessel arrival is on schedule (if we have dates)
        if self.latest_safe_arrival and self.estimated_arrival:
            on_schedule = deadline_mod.is_arrival_feasible(
                self.estimated_arrival, self.latest_safe_arrival
            )
        else:
            on_schedule = True  # no schedule constraints yet

        # -----------------------------------------------------------------
        # 7. Arrival detection & high‑level status update
        # -----------------------------------------------------------------
        if self.active_vessel.is_arrived():
            self.simulation_status = "COMPLETED"
        else:
            if self.simulation_status == "PLANNED":
                # If the departure time has passed, transition to EN_ROUTE.
                if (
                    self.active_vessel.departure_datetime
                    and self.simulation_datetime >= self.active_vessel.departure_datetime
                ):
                    self.simulation_status = "EN_ROUTE"
                    self.active_vessel.start_voyage(self.active_vessel.departure_datetime)
            elif self.simulation_status == "EN_ROUTE":
                # If schedule is violated, mark as FAILED.
                if not on_schedule:
                    self.simulation_status = "FAILED"

    def get_state(self) -> Dict:
        """
        Return a JSON‑serialisable representation of the current simulation state.

        ``datetime`` objects are ISO‑8601 strings, ``Decimal`` values are converted
        to strings, and all Pydantic models are represented by their ``dict()``
        output.
        """
        def _to_iso(dt: Optional[datetime]) -> Optional[str]:
            return dt.isoformat() if dt else None

        state = {
            "simulation_datetime": _to_iso(self.simulation_datetime),
            "station_inventory": {
                name: inv.dict()
                for name, inv in self.current_inventory.items()
            },
            "active_vessel": self.active_vessel.dict() if self.active_vessel else None,
            "active_route": self.active_route.dict() if self.active_route else None,
            "vessel_position": {"latitude": self.vessel_position[0],
                                "longitude": self.vessel_position[1]},
            "vessel_progress": self.vessel_progress,
            "predicted_critical_date": _to_iso(self.predicted_critical_date),
            "latest_safe_arrival": _to_iso(self.latest_safe_arrival),
            "estimated_arrival": _to_iso(self.estimated_arrival),
            "fuel_consumed_l": self.fuel_consumed_l,
            "estimated_total_fuel_l": self.estimated_total_fuel_l,
            "estimated_total_cost": str(self.estimated_total_cost),
            "simulation_status": self.simulation_status,
        }
        return state

    def reset(self) -> None:
        """
        Return the simulation to its original state (as captured during
        ``initialize``).  All mutable fields are replaced with a deep copy of the
        snapshot taken at initialisation.
        """
        if self._initial_snapshot is None:
            raise RuntimeError("Simulation has not been initialised; cannot reset.")
        # Deep‑copy the snapshot to avoid sharing mutable sub‑objects.
        restored = copy.deepcopy(self._initial_snapshot)

        # Replace all fields – we cannot simply assign ``self = restored`` because
        # the reference would be lost for callers.
        for field_name, value in restored.__dict__.items():
            setattr(self, field_name, value)