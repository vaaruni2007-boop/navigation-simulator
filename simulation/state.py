from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal
from typing import Dict, Optional

from engine import deadline as deadline_mod
from engine import fuel as fuel_mod
from engine import inventory as inventory_mod

from engine.models import (
    ResourceInventory,
    Route,
    Station,
    Vessel,
)

from .clock import SimulationClock
from .environment import EnvironmentConditions, normal_conditions
from .environment_events import EnvironmentTimeline
from .vessel import SimulatedVessel


@dataclass
class SimulationState:
    """
    Complete runtime state of one simulated resupply voyage.

    The state coordinates:
    - simulation time
    - vessel movement
    - station inventory
    - fuel consumption
    - voyage predictions
    - time-dependent environmental conditions
    - resupply risk analysis
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

    environment_timeline: Optional[EnvironmentTimeline] = None

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

    current_environment: EnvironmentConditions = field(
        default_factory=normal_conditions,
        init=False,
    )

    active_environment_event: Optional[str] = field(
        default=None,
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

        if self.environment_timeline is not None:
            self._update_environment()

        self._calculate_predictions()

    # ------------------------------------------------------------------
    # Properties
    # ------------------------------------------------------------------

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

    # ------------------------------------------------------------------
    # Environment
    # ------------------------------------------------------------------

    def _update_environment(self) -> None:
        """
        Update the active environmental conditions based on
        the current simulation datetime.
        """

        if self.environment_timeline is None:
            self.current_environment = normal_conditions()
            self.active_environment_event = None
        else:
            self.current_environment = (
                self.environment_timeline.get_conditions(
                    self.simulation_datetime
                )
            )

            event = self.environment_timeline.active_event(
                self.simulation_datetime
            )

            self.active_environment_event = (
                event.name
                if event is not None
                else None
            )

        self.simulated_vessel.set_environment(
            self.current_environment
        )

    def _next_environment_change(
        self,
    ) -> Optional[datetime]:
        """
        Return the next environmental boundary after
        the current simulation time.
        """

        if self.environment_timeline is None:
            return None

        return self.environment_timeline.next_change_after(
            self.simulation_datetime
        )

    # ------------------------------------------------------------------
    # Controls
    # ------------------------------------------------------------------

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
            departure_datetime = self.clock.simulation_datetime

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

        self.simulated_vessel.start_voyage(
            departure_datetime
        )

        self._update_environment()

        self.clock.start()

        self.status = "running"

    def pause(self) -> None:
        """Pause the simulation."""

        self.clock.pause()
        self.simulated_vessel.pause_voyage()

        if self.status == "running":
            self.status = "paused"

    def resume(self) -> None:
        """Resume a paused simulation."""

        if self.status != "paused":
            return

        self.clock.resume()
        self.simulated_vessel.start_voyage()

        self._update_environment()

        self.status = "running"

    def update(
        self,
        elapsed_seconds: float,
    ) -> None:
        """
        Advance the simulation.

        Environmental boundaries split the timestep so that
        each segment uses the correct environmental conditions.
        """

        if elapsed_seconds < 0:
            raise ValueError(
                "elapsed_seconds must be non-negative"
            )

        if self.status not in {
            "running",
            "paused",
        }:
            return

        if elapsed_seconds == 0:
            self._update_environment()
            return

        remaining_seconds = float(elapsed_seconds)

        while remaining_seconds > 0:
            self._update_environment()

            segment_seconds = (
                self._seconds_until_environment_change(
                    remaining_seconds
                )
            )

            if segment_seconds <= 0:
                segment_seconds = remaining_seconds

            environment = self.current_environment

            self.clock.advance(
                segment_seconds
            )

            self.simulated_vessel.update(
                segment_seconds,
                environment=environment,
            )

            self._update_inventory()

            self._accumulate_fuel_consumption(
                segment_seconds,
                environment,
            )

            remaining_seconds -= segment_seconds

            if remaining_seconds < 0.000001:
                remaining_seconds = 0.0

            if self.simulated_vessel.is_complete:
                self.status = "completed"
                break

        if (
            self.status == "running"
            and not self.simulated_vessel.is_complete
        ):
            self.status = "running"

        self._update_environment()

    def _seconds_until_environment_change(
        self,
        requested_seconds: float,
    ) -> float:
        """
        Determine how many seconds can be simulated before
        the next environmental boundary.
        """

        next_change = self._next_environment_change()

        if next_change is None:
            return requested_seconds

        delta = (
            next_change
            - self.simulation_datetime
        )

        seconds_until_change = delta.total_seconds()

        if seconds_until_change <= 0:
            return requested_seconds

        return min(
            requested_seconds,
            seconds_until_change,
        )

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

        self._update_environment()
        self._calculate_predictions()

    # ------------------------------------------------------------------
    # Risk analysis
    # ------------------------------------------------------------------

    def calculate_safety_margin_days(self) -> Optional[float]:
        """
        Calculate the current arrival safety margin.

        Positive  = arrival is before the safe deadline.
        Zero       = arrival is exactly at the safe deadline.
        Negative   = arrival is after the safe deadline.
        """

        if (
            self.latest_safe_arrival is None
            or self.estimated_arrival is None
        ):
            return None

        return deadline_mod.calculate_safety_margin_days(
            self.latest_safe_arrival,
            self.estimated_arrival,
        )

    @property
    def arrival_feasible(self) -> Optional[bool]:
        """
        Return whether the currently estimated arrival
        meets the safe-arrival deadline.
        """

        if (
            self.latest_safe_arrival is None
            or self.estimated_arrival is None
        ):
            return None

        return deadline_mod.is_arrival_feasible(
            self.estimated_arrival,
            self.latest_safe_arrival,
        )

    @property
    def arrival_risk_status(self) -> str:
        """
        Return a high-level arrival risk classification.

        SAFE:
            ETA is comfortably before the deadline.

        AT_RISK:
            ETA is within the safety deadline but has little
            remaining margin.

        CRITICAL:
            ETA is already beyond the safe-arrival deadline.
        """

        margin = self.calculate_safety_margin_days()

        if margin is None:
            return "UNKNOWN"

        if margin < 0:
            return "CRITICAL"

        if margin <= self.safety_buffer_days:
            return "AT_RISK"

        return "SAFE"

    def get_resource_risk(self) -> Dict[str, dict]:
        """
        Return risk information for every station resource.
        """

        result: Dict[str, dict] = {}

        for resource_name, resource in (
            self.station_inventory.items()
        ):
            critical_date = (
                inventory_mod.calculate_critical_date(
                    resource,
                    self._initial_simulation_datetime(),
                )
            )

            if critical_date is None:
                result[resource_name] = {
                    "resource_name": resource.resource_name,
                    "current_quantity": self.current_inventory.get(
                        resource_name,
                        resource.current_quantity,
                    ),
                    "daily_consumption": resource.daily_consumption,
                    "critical_date": None,
                    "latest_safe_arrival": None,
                    "status": "NO_DEPLETION_RISK",
                    "days_until_critical": None,
                }
                continue

            latest_safe_arrival = (
                deadline_mod.calculate_latest_safe_arrival(
                    critical_date,
                    self.safety_buffer_days,
                )
            )

            days_until_critical = (
                critical_date
                - self.simulation_datetime
            ).total_seconds() / 86400.0

            if days_until_critical < 0:
                resource_status = "CRITICAL"
            elif self.estimated_arrival is not None:
                if (
                    self.estimated_arrival
                    > latest_safe_arrival
                ):
                    resource_status = "CRITICAL"
                elif (
                    (
                        latest_safe_arrival
                        - self.estimated_arrival
                    ).total_seconds()
                    / 86400.0
                    <= self.safety_buffer_days
                ):
                    resource_status = "AT_RISK"
                else:
                    resource_status = "SAFE"
            else:
                resource_status = "SAFE"

            result[resource_name] = {
                "resource_name": resource.resource_name,
                "current_quantity": self.current_inventory.get(
                    resource_name,
                    resource.current_quantity,
                ),
                "daily_consumption": resource.daily_consumption,
                "critical_date": critical_date.isoformat(),
                "latest_safe_arrival": (
                    latest_safe_arrival.isoformat()
                ),
                "status": resource_status,
                "days_until_critical": days_until_critical,
            }

        return result

    def get_risk_summary(self) -> dict:
        """
        Return a complete mission-level risk summary.
        """

        resource_risk = self.get_resource_risk()

        statuses = [
            item["status"]
            for item in resource_risk.values()
        ]

        if "CRITICAL" in statuses:
            overall_status = "CRITICAL"
        elif "AT_RISK" in statuses:
            overall_status = "AT_RISK"
        else:
            overall_status = "SAFE"

        return {
            "overall_status": overall_status,
            "arrival_status": self.arrival_risk_status,
            "arrival_feasible": self.arrival_feasible,
            "safety_margin_days": (
                self.calculate_safety_margin_days()
            ),
            "estimated_arrival": (
                self.estimated_arrival.isoformat()
                if self.estimated_arrival
                else None
            ),
            "latest_safe_arrival": (
                self.latest_safe_arrival.isoformat()
                if self.latest_safe_arrival
                else None
            ),
            "predicted_critical_date": (
                self.predicted_critical_date.isoformat()
                if self.predicted_critical_date
                else None
            ),
            "resources": resource_risk,
        }

    # ------------------------------------------------------------------
    # State export
    # ------------------------------------------------------------------

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
            "environment": {
                "weather_severity": (
                    self.current_environment.weather_severity
                ),
                "sea_ice_severity": (
                    self.current_environment.sea_ice_severity
                ),
                "current_factor": (
                    self.current_environment.current_factor
                ),
                "visibility_factor": (
                    self.current_environment.visibility_factor
                ),
                "overall_severity": (
                    self.current_environment.overall_severity
                ),
                "active_event": (
                    self.active_environment_event
                ),
            },
            "risk": self.get_risk_summary(),
        }

    # ------------------------------------------------------------------
    # Predictions
    # ------------------------------------------------------------------

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

    # ------------------------------------------------------------------
    # Inventory
    # ------------------------------------------------------------------

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
        """Return the original simulation reference datetime."""

        return self.clock.start_datetime

    # ------------------------------------------------------------------
    # Fuel
    # ------------------------------------------------------------------

    def _accumulate_fuel_consumption(
        self,
        elapsed_seconds: float,
        environment: EnvironmentConditions,
    ) -> None:
        """
        Accumulate actual fuel consumed during a simulation segment.
        """

        if elapsed_seconds <= 0:
            return

        elapsed_days = (
            float(elapsed_seconds)
            / (24.0 * 60.0 * 60.0)
        )

        base_fuel = (
            self.vessel.fuel_consumption_litres_per_day
        )

        environmental_multiplier = (
            environment.fuel_multiplier()
        )

        fuel_used = (
            base_fuel
            * elapsed_days
            * environmental_multiplier
        )

        self.fuel_consumed_litres += fuel_used


__all__ = [
    "SimulationState",
]
