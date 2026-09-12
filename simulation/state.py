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
from .environment import (
    EnvironmentConditions,
    normal_conditions,
)
from .environment_events import EnvironmentTimeline
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

    environment_timeline: Optional[
        EnvironmentTimeline
    ] = None

    simulated_vessel: SimulatedVessel = field(
        init=False
    )

    predicted_critical_date: Optional[
        datetime
    ] = field(
        default=None,
        init=False,
    )

    latest_safe_arrival: Optional[
        datetime
    ] = field(
        default=None,
        init=False,
    )

    estimated_arrival: Optional[
        datetime
    ] = field(
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
        return self.clock.simulation_datetime

    @property
    def vessel_position(self):
        return self.simulated_vessel.current_position

    @property
    def vessel_progress(self) -> float:
        return self.simulated_vessel.progress_fraction

    @property
    def estimated_voyage_duration_days(self) -> float:
        return self.simulated_vessel.estimated_duration_days()

    @property
    def environmental_delay_days(
        self,
    ) -> Optional[float]:
        return self.simulated_vessel.delay_days

    @property
    def projected_arrival_datetime(
        self,
    ) -> Optional[datetime]:
        return self.simulated_vessel.projected_arrival_datetime

    # ------------------------------------------------------------------
    # Environment
    # ------------------------------------------------------------------

    def _update_environment(self) -> None:
        if self.environment_timeline is None:
            self.current_environment = normal_conditions()
            self.active_environment_event = None
        else:
            self.current_environment = (
                self.environment_timeline.get_conditions(
                    self.simulation_datetime
                )
            )

            event = (
                self.environment_timeline.active_event(
                    self.simulation_datetime
                )
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
        if self.environment_timeline is None:
            return None

        return (
            self.environment_timeline.next_change_after(
                self.simulation_datetime
            )
        )

    # ------------------------------------------------------------------
    # Controls
    # ------------------------------------------------------------------

    def start(
        self,
        departure_datetime: Optional[
            datetime
        ] = None,
    ) -> None:

        if departure_datetime is None:
            departure_datetime = (
                self.clock.simulation_datetime
            )

        if departure_datetime.tzinfo is None:
            raise ValueError(
                "departure_datetime must be timezone-aware"
            )

        self.simulated_vessel.start_voyage(
            departure_datetime
        )

        self._update_environment()
        self._refresh_dynamic_eta()
        self._calculate_predictions()

        self.clock.start()

        self.status = "running"

    def pause(self) -> None:
        if self.status != "running":
            return

        self.simulated_vessel.pause_voyage()
        self.clock.pause()

        self.status = "paused"

    def resume(self) -> None:
        if self.status != "paused":
            return

        self.simulated_vessel.resume_voyage()
        self._update_environment()
        self._refresh_dynamic_eta()

        self.clock.resume()

        self.status = "running"

    def update(
        self,
        elapsed_seconds: float,
    ) -> None:

        if elapsed_seconds < 0:
            raise ValueError(
                "elapsed_seconds must be non-negative"
            )

        # A paused or completed simulation must not advance.
        if self.status != "running":
            return

        if elapsed_seconds == 0:
            self._update_environment()
            self._refresh_dynamic_eta()
            return

        remaining_real_seconds = float(
            elapsed_seconds
        )

        while remaining_real_seconds > 0:
            self._update_environment()
            self._refresh_dynamic_eta()

            environment = self.current_environment

            # ----------------------------------------------------------
            # Determine how much simulated time can actually pass.
            #
            # elapsed_seconds is real/update time.
            # SimulationClock may accelerate that time using its
            # speed_multiplier.
            # ----------------------------------------------------------

            speed_multiplier = (
                self.clock.speed_multiplier
            )

            if speed_multiplier <= 0:
                raise RuntimeError(
                    "Simulation clock speed multiplier must be greater than zero."
                )

            requested_simulation_seconds = (
                remaining_real_seconds
                * speed_multiplier
            )

            # ----------------------------------------------------------
            # Stop exactly at the next environmental boundary.
            # ----------------------------------------------------------

            environment_boundary_seconds = (
                self._simulation_seconds_until_environment_change()
            )

            if environment_boundary_seconds is not None:
                requested_simulation_seconds = min(
                    requested_simulation_seconds,
                    environment_boundary_seconds,
                )

            # ----------------------------------------------------------
            # Stop exactly when the vessel reaches Antarctica.
            #
            # distance / knots = hours
            # ----------------------------------------------------------

            if (
                self.simulated_vessel.is_active
                and not self.simulated_vessel.is_complete
            ):
                effective_speed = (
                    self.simulated_vessel.effective_speed_knots
                )

                hours_to_destination = (
                    self.simulated_vessel.distance_remaining_nm
                    / effective_speed
                )

                vessel_remaining_seconds = (
                    hours_to_destination
                    * 3600.0
                )

                requested_simulation_seconds = min(
                    requested_simulation_seconds,
                    vessel_remaining_seconds,
                )

            # Nothing meaningful can advance.
            if requested_simulation_seconds <= 0:
                break

            # Convert simulated time back to real update time so
            # SimulationClock applies its speed multiplier exactly once.
            segment_real_seconds = (
                requested_simulation_seconds
                / speed_multiplier
            )

            before_datetime = (
                self.clock.simulation_datetime
            )

            # Advance the authoritative simulation clock.
            self.clock.advance(
                segment_real_seconds
            )

            actual_simulation_seconds = (
                self.clock.simulation_datetime
                - before_datetime
            ).total_seconds()

            # Advance vessel using the SAME simulated duration.
            self.simulated_vessel.update(
                actual_simulation_seconds,
                environment=environment,
            )

            self._update_inventory()

            # Vessel is authoritative for actual fuel usage.
            self.fuel_consumed_litres = (
                self.simulated_vessel.fuel_used_litres()
            )

            self._update_environment()
            self._refresh_dynamic_eta()

            remaining_real_seconds -= (
                segment_real_seconds
            )

            if remaining_real_seconds < 0.000001:
                remaining_real_seconds = 0.0

            # ----------------------------------------------------------
            # If vessel arrived, stop immediately.
            #
            # The clock has already been capped to the exact arrival
            # time, so simulation_datetime == arrival_datetime.
            # ----------------------------------------------------------

            if self.simulated_vessel.is_complete:
                self.status = "completed"

                self.fuel_consumed_litres = (
                    self.simulated_vessel.fuel_used_litres()
                )

                break

        self._update_environment()
        self._refresh_dynamic_eta()

        self.fuel_consumed_litres = (
            self.simulated_vessel.fuel_used_litres()
        )

    def _simulation_seconds_until_environment_change(
        self,
    ) -> Optional[float]:
        """
        Return the number of simulated seconds until the next
        environmental event boundary.

        Returns None when there is no upcoming event.
        """

        next_change = (
            self._next_environment_change()
        )

        if next_change is None:
            return None

        delta = (
            next_change
            - self.simulation_datetime
        )

        seconds_until_change = (
            delta.total_seconds()
        )

        if seconds_until_change <= 0:
            return None

        return seconds_until_change

    def _refresh_dynamic_eta(self) -> None:
        projected_eta = (
            self.simulated_vessel.projected_arrival_datetime
        )

        if projected_eta is not None:
            self.estimated_arrival = projected_eta

    def reset(self) -> None:
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

    def calculate_safety_margin_days(
        self,
    ) -> Optional[float]:

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
    def arrival_feasible(
        self,
    ) -> Optional[bool]:

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

        margin = self.calculate_safety_margin_days()

        if margin is None:
            return "UNKNOWN"

        if margin < 0:
            return "CRITICAL"

        if margin <= self.safety_buffer_days:
            return "AT_RISK"

        return "SAFE"

    def get_resource_risk(
        self,
    ) -> Dict[str, dict]:

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

                if self.estimated_arrival > latest_safe_arrival:
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
                "latest_safe_arrival": latest_safe_arrival.isoformat(),
                "status": resource_status,
                "days_until_critical": days_until_critical,
            }

        return result

    def get_risk_summary(self) -> dict:
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
            "safety_margin_days": self.calculate_safety_margin_days(),
            "delay_days": self.environmental_delay_days,
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
            "fuel_consumed_litres": self.fuel_consumed_litres,
            "fuel_remaining_litres": (
                self.simulated_vessel.fuel_remaining_litres
            ),
            "fuel_remaining_percent": (
                self.simulated_vessel.fuel_remaining_percent()
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
            "delay_days": self.environmental_delay_days,
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
                critical_dates.append(critical_date)

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

        operating_cost = cost_mod.calculate_operating_cost(
            self.estimated_voyage_duration_days,
            self.vessel.operating_cost_per_day,
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

    def _initial_simulation_datetime(
        self,
    ) -> datetime:
        return self.clock.start_datetime

    # ------------------------------------------------------------------
    # Fuel
    # ------------------------------------------------------------------

    def _accumulate_fuel_consumption(
        self,
        elapsed_seconds: float,
        environment: EnvironmentConditions,
    ) -> None:

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