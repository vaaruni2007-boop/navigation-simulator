from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Any, Callable, Optional

from engine import fuel as fuel_mod
from engine import inventory as inventory_mod
from engine.cost import calculate_operating_cost
from engine.voyage import (
    environment_adjusted_fuel_consumption,
    environment_adjusted_voyage_duration_days,
)
from simulation.environment import EnvironmentConditions
from engine.models import (
    Port,
    Route,
    Station,
    Vessel,
)


EnvironmentProvider = Callable[
    [datetime, Route, Vessel],
    EnvironmentConditions,
]


# ======================================================================
# RESUPPLY OPTION
# ======================================================================


@dataclass
class ResupplyOption:
    vessel: Vessel
    route: Route
    station: Station
    resource: Any
    cargo_weight_tonnes: float

    departure_datetime: datetime
    arrival_datetime: Optional[datetime]

    duration_days: float
    fuel_required_litres: float
    fuel_capacity_litres: float

    fuel_cost: float
    operating_cost: float
    total_cost: float

    risk_score: float
    safety_margin_days: Optional[float]

    feasible: bool

    rejection_reasons: list[str] = field(
        default_factory=list
    )

    warnings: list[str] = field(
        default_factory=list
    )

    environment: Optional[EnvironmentConditions] = None

    # ------------------------------------------------------------------
    # Compatibility / convenience properties
    # ------------------------------------------------------------------

    @property
    def vessel_id(self) -> str:
        return str(
            getattr(
                self.vessel,
                "id",
                getattr(self.vessel, "vessel_id", "unknown"),
            )
        )

    @property
    def route_id(self) -> str:
        return str(
            getattr(
                self.route,
                "id",
                getattr(self.route, "route_id", "unknown"),
            )
        )

    @property
    def option_id(self) -> str:
        return f"{self.vessel_id}:{self.route_id}"

    @property
    def reasons(self) -> list[str]:
        """
        Step 7 explainability compatibility.

        `reasons` is the human-readable explanation list.
        For infeasible options it contains rejection reasons.
        For feasible options it contains the operational factors
        that justified the option.
        """
        return self.rejection_reasons

    @property
    def explanation(self) -> str:
        if self.feasible:
            return (
                f"{self.vessel_id} via {self.route_id}: "
                f"{self.duration_days:.1f} days, "
                f"{self.fuel_required_litres:,.0f} L fuel, "
                f"total cost {self.total_cost:,.0f}, "
                f"risk {self.risk_score:.2f}."
            )

        if self.rejection_reasons:
            return (
                f"{self.vessel_id} via {self.route_id} "
                f"is infeasible. "
                + " ".join(self.rejection_reasons)
            )

        return (
            f"{self.vessel_id} via {self.route_id} "
            f"is infeasible."
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "option_id": self.option_id,
            "vessel_id": self.vessel_id,
            "vessel_name": getattr(
                self.vessel,
                "name",
                self.vessel_id,
            ),
            "route_id": self.route_id,
            "station_id": getattr(
                self.station,
                "id",
                getattr(self.station, "station_id", None),
            ),
            "resource": getattr(
                self.resource,
                "resource_name",
                getattr(
                    self.resource,
                    "id",
                    "unknown",
                ),
            ),
            "cargo_weight_tonnes": self.cargo_weight_tonnes,
            "departure_datetime": (
                self.departure_datetime.isoformat()
            ),
            "arrival_datetime": (
                self.arrival_datetime.isoformat()
                if self.arrival_datetime is not None
                else None
            ),
            "duration_days": self.duration_days,
            "fuel_required_litres": self.fuel_required_litres,
            "fuel_capacity_litres": self.fuel_capacity_litres,
            "fuel_cost": self.fuel_cost,
            "operating_cost": self.operating_cost,
            "total_cost": self.total_cost,
            "risk_score": self.risk_score,
            "safety_margin_days": self.safety_margin_days,
            "feasible": self.feasible,
            "rejection_reasons": list(
                self.rejection_reasons
            ),
            "reasons": list(self.reasons),
            "warnings": list(self.warnings),
            "explanation": self.explanation,
        }


# ======================================================================
# OPTIMIZATION RESULT
# ======================================================================


@dataclass
class ResupplyOptimizationResult:
    selected_option: Optional[ResupplyOption]

    feasible_options: list[ResupplyOption]

    infeasible_options: list[ResupplyOption]

    # ------------------------------------------------------------------
    # Compatibility aliases
    # ------------------------------------------------------------------

    @property
    def best_option(self) -> Optional[ResupplyOption]:
        return self.selected_option

    @property
    def recommended_option(
        self,
    ) -> Optional[ResupplyOption]:
        return self.selected_option

    @property
    def options(self) -> list[ResupplyOption]:
        return self.feasible_options

    # ------------------------------------------------------------------
    # Explainability
    # ------------------------------------------------------------------

    def why_this_option_won(self) -> dict[str, Any]:
        """
        Explain why the selected option was recommended.

        Returns a structured dictionary so it can be directly
        consumed by the frontend.
        """

        if self.selected_option is None:
            return {
                "status": "NO_FEASIBLE_OPTION",
                "winner": None,
                "reasons": [],
                "warnings": [],
            }

        winner = self.selected_option

        reasons = list(winner.reasons)

        # Add explicit comparative reason.
        if len(self.feasible_options) > 1:
            cheaper_than = [
                option
                for option in self.feasible_options
                if option is not winner
                and option.total_cost > winner.total_cost
            ]

            faster_than = [
                option
                for option in self.feasible_options
                if option is not winner
                and option.duration_days > winner.duration_days
            ]

            lower_risk_than = [
                option
                for option in self.feasible_options
                if option is not winner
                and option.risk_score > winner.risk_score
            ]

            if faster_than:
                reasons.append(
                    "Selected because it provides a faster "
                    "arrival than slower feasible alternatives."
                )

            if cheaper_than:
                reasons.append(
                    "Selected because it has lower estimated "
                    "total cost than more expensive feasible "
                    "alternatives."
                )

            if lower_risk_than:
                reasons.append(
                    "Selected because it has lower route/"
                    "environmental risk than higher-risk "
                    "feasible alternatives."
                )

        return {
            "status": "RECOMMENDED",
            "winner": winner.to_dict(),
            "reasons": reasons,
            "warnings": list(winner.warnings),
        }

    def to_dict(self) -> dict[str, Any]:
        """
        Serialize the complete optimization result.

        The top-level fields intentionally preserve the API expected
        by the existing simulator/frontend tests.
        """

        station_id = None
        station_name = None
        resource_name = None

        reference_option = (
            self.selected_option
            or (
                self.feasible_options[0]
                if self.feasible_options
                else (
                    self.infeasible_options[0]
                    if self.infeasible_options
                    else None
                )
            )
        )

        if reference_option is not None:
            station_id = getattr(
                reference_option.station,
                "id",
                getattr(
                    reference_option.station,
                    "station_id",
                    None,
                ),
            )

            station_name = getattr(
                reference_option.station,
                "name",
                station_id,
            )

            resource_name = getattr(
                reference_option.resource,
                "resource_name",
                getattr(
                    reference_option.resource,
                    "name",
                    getattr(
                        reference_option.resource,
                        "id",
                        None,
                    ),
                ),
            )

        return {
            "station_id": station_id,
            "station_name": station_name,
            "resource_name": resource_name,
            "recommended_option": (
                self.selected_option.to_dict()
                if self.selected_option is not None
                else None
            ),
            "selected_option": (
                self.selected_option.to_dict()
                if self.selected_option is not None
                else None
            ),
            "feasible_options": [
                option.to_dict()
                for option in self.feasible_options
            ],
            "infeasible_options": [
                option.to_dict()
                for option in self.infeasible_options
            ],
            "why_this_option_won": (
                self.why_this_option_won()
            ),
        }


# ======================================================================
# RESUPPLY OPTIMIZER
# ======================================================================


class ResupplyOptimizer:
    """
    Optimizes Antarctic resupply voyages.

    Evaluates:
    - vessel cargo capacity
    - vessel availability
    - route validity
    - voyage duration
    - environmental effects
    - fuel consumption
    - fuel capacity
    - fuel cost
    - operating cost
    - inventory deadlines
    - safety margin
    - route/environmental risk

    Maritime routes and vessel data remain simulated unless replaced
    with authoritative operational data.
    """

    def __init__(
        self,
        vessels: Optional[list[Vessel]] = None,
        routes: Optional[list[Route]] = None,
        ports: Optional[list[Port]] = None,
        departure_window_days: int = 0,
        departure_step_days: int = 1,
        environment_provider: Optional[
            EnvironmentProvider
        ] = None,
    ):
        self.vessels = vessels or []
        self.routes = routes or []
        self.ports = ports or []

        self.departure_window_days = max(
            0,
            int(departure_window_days),
        )

        self.departure_step_days = max(
            1,
            int(departure_step_days),
        )

        self.environment_provider = (
            environment_provider
        )

    # ==================================================================
    # Generic helpers
    # ==================================================================

    @staticmethod
    def _get(
        obj: Any,
        *names: str,
        default: Any = None,
    ) -> Any:

        for name in names:
            if hasattr(obj, name):
                return getattr(obj, name)

            if isinstance(obj, dict) and name in obj:
                return obj[name]

        return default

    @staticmethod
    def _route_distance_km(
        route: Route,
    ) -> float:

        value = ResupplyOptimizer._get(
            route,
            "distance_km",
            "distance",
            default=0.0,
        )

        return float(value)

    @staticmethod
    def _route_risk(
        route: Route,
    ) -> float:

        value = ResupplyOptimizer._get(
            route,
            "risk_score",
            "risk",
            default=0.0,
        )

        return float(value)

    @staticmethod
    def _vessel_capacity(
        vessel: Vessel,
    ) -> float:

        return float(
            ResupplyOptimizer._get(
                vessel,
                "cargo_capacity_tonnes",
                "cargo_capacity",
                "capacity_tonnes",
                default=0.0,
            )
        )

    @staticmethod
    def _fuel_capacity(
        vessel: Vessel,
    ) -> float:

        return float(
            ResupplyOptimizer._get(
                vessel,
                "fuel_capacity_litres",
                "fuel_capacity",
                default=0.0,
            )
        )

    @staticmethod
    def _fuel_per_day(
        vessel: Vessel,
    ) -> float:

        return float(
            ResupplyOptimizer._get(
                vessel,
                "fuel_consumption_litres_per_day",
                "fuel_consumption",
                "fuel_burn_litres_per_day",
                default=0.0,
            )
        )

    @staticmethod
    def _fuel_cost_per_litre(
        vessel: Vessel,
    ) -> float:

        return float(
            ResupplyOptimizer._get(
                vessel,
                "fuel_cost_per_litre",
                "fuel_cost",
                default=0.0,
            )
        )

    @staticmethod
    def _operating_cost_per_day(
        vessel: Vessel,
    ) -> float:

        return float(
            ResupplyOptimizer._get(
                vessel,
                "operating_cost_per_day",
                "daily_operating_cost",
                default=0.0,
            )
        )

    @staticmethod
    def _cruise_speed(
        vessel: Vessel,
    ) -> float:

        return float(
            ResupplyOptimizer._get(
                vessel,
                "cruise_speed_knots",
                "cruise_speed",
                "speed_knots",
                default=0.0,
            )
        )

    @staticmethod
    def _vessel_start(
        vessel: Vessel,
    ) -> Optional[datetime]:

        return ResupplyOptimizer._get(
            vessel,
            "availability_start",
            "available_from",
            default=None,
        )

    @staticmethod
    def _vessel_end(
        vessel: Vessel,
    ) -> Optional[datetime]:

        return ResupplyOptimizer._get(
            vessel,
            "availability_end",
            "available_until",
            default=None,
        )

    @staticmethod
    def _resource_daily_consumption(
        resource: Any,
    ) -> Optional[float]:

        value = ResupplyOptimizer._get(
            resource,
            "daily_consumption",
            default=None,
        )

        if value is None:
            return None

        return float(value)

    @staticmethod
    def _resource_current_quantity(
        resource: Any,
    ) -> Optional[float]:

        value = ResupplyOptimizer._get(
            resource,
            "current_quantity",
            default=None,
        )

        if value is None:
            return None

        return float(value)

    @staticmethod
    def _resource_threshold(
        resource: Any,
    ) -> Optional[float]:

        value = ResupplyOptimizer._get(
            resource,
            "safety_threshold",
            default=None,
        )

        if value is None:
            return None

        return float(value)

    # ==================================================================
    # Environment
    # ==================================================================

    def _environment(
        self,
        current_datetime: datetime,
        route: Route,
        vessel: Vessel,
        environment: Optional[
            EnvironmentConditions
        ],
    ) -> EnvironmentConditions:

        if environment is not None:
            return environment

        if self.environment_provider is not None:
            return self.environment_provider(
                current_datetime,
                route,
                vessel,
            )

        return EnvironmentConditions()

    # ==================================================================
    # Inventory deadline
    # ==================================================================

    @staticmethod
    def _calculate_inventory_deadline(
        resource: Any,
        current_datetime: datetime,
    ) -> Optional[datetime]:

        current_quantity = (
            ResupplyOptimizer._resource_current_quantity(
                resource
            )
        )

        daily_consumption = (
            ResupplyOptimizer._resource_daily_consumption(
                resource
            )
        )

        safety_threshold = (
            ResupplyOptimizer._resource_threshold(
                resource
            )
        )

        # SimpleNamespace fixtures and some lightweight resources
        # intentionally do not contain inventory forecasting data.
        if (
            current_quantity is None
            or daily_consumption is None
            or safety_threshold is None
        ):
            return None

        if daily_consumption <= 0:
            return None

        try:
            return inventory_mod.calculate_critical_date(
                current_quantity=current_quantity,
                daily_consumption=daily_consumption,
                safety_threshold=safety_threshold,
                current_datetime=current_datetime,
            )

        except (
            TypeError,
            ValueError,
        ):
            return None

    # ==================================================================
    # Single option evaluation
    # ==================================================================

    def evaluate_option(
        self,
        vessel: Vessel,
        route: Route,
        station: Station,
        resource: Any,
        current_datetime: datetime,
        cargo_weight_tonnes: float,
        latest_safe_arrival: Optional[
            datetime
        ] = None,
        environment: Optional[
            EnvironmentConditions
        ] = None,
    ) -> ResupplyOption:

        rejection_reasons: list[str] = []
        warnings: list[str] = []

        cargo_weight_tonnes = float(
            cargo_weight_tonnes
        )

        # --------------------------------------------------------------
        # Cargo capacity
        # --------------------------------------------------------------

        if cargo_weight_tonnes < 0:
            rejection_reasons.append(
                "Cargo weight cannot be negative."
            )

        vessel_capacity = (
            self._vessel_capacity(vessel)
        )

        if cargo_weight_tonnes > vessel_capacity:
            rejection_reasons.append(
                f"Cargo weight "
                f"{cargo_weight_tonnes:,.1f} tonnes "
                f"exceeds vessel capacity "
                f"{vessel_capacity:,.1f} tonnes."
            )

        # --------------------------------------------------------------
        # Vessel availability
        # --------------------------------------------------------------

        vessel_start = self._vessel_start(
            vessel
        )

        vessel_end = self._vessel_end(
            vessel
        )

        if (
            vessel_start is not None
            and current_datetime < vessel_start
        ):
            rejection_reasons.append(
                "Vessel is unavailable until "
                f"{vessel_start.isoformat()}."
            )

        if (
            vessel_end is not None
            and current_datetime > vessel_end
        ):
            rejection_reasons.append(
                "Vessel availability ended at "
                f"{vessel_end.isoformat()}."
            )

        # --------------------------------------------------------------
        # Route validation
        # --------------------------------------------------------------

        route_origin = self._get(
            route,
            "origin_port_id",
            "origin",
            "origin_id",
            default=None,
        )

        route_destination = self._get(
            route,
            "destination_station_id",
            "destination",
            "destination_id",
            default=None,
        )

        station_id = self._get(
            station,
            "id",
            "station_id",
            default=None,
        )

        if (
            route_destination is not None
            and station_id is not None
            and route_destination != station_id
        ):
            rejection_reasons.append(
                f"Route destination "
                f"{route_destination} does not match "
                f"station {station_id}."
            )

        if (
            self.ports
            and route_origin is not None
        ):

            matching_port = next(
                (
                    port
                    for port in self.ports
                    if self._get(
                        port,
                        "id",
                        "port_id",
                        default=None,
                    ) == route_origin
                ),
                None,
            )

            if matching_port is None:
                rejection_reasons.append(
                    f"Origin port {route_origin} "
                    "was not found."
                )

            elif not self._get(
                matching_port,
                "available",
                "availability",
                default=True,
            ):
                rejection_reasons.append(
                    f"Origin port {route_origin} "
                    "is unavailable."
                )

        # --------------------------------------------------------------
        # Environment
        # --------------------------------------------------------------

        conditions = self._environment(
            current_datetime=current_datetime,
            route=route,
            vessel=vessel,
            environment=environment,
        )

        # --------------------------------------------------------------
        # Voyage calculation
        # --------------------------------------------------------------

        distance_km = (
            self._route_distance_km(route)
        )

        speed_knots = (
            self._cruise_speed(vessel)
        )

        duration_days = 0.0
        arrival_datetime: Optional[
            datetime
        ] = None

        fuel_required = 0.0
        fuel_cost = 0.0
        operating_cost = 0.0

        voyage_calculation_failed = False

        try:

            if distance_km <= 0:
                raise ValueError(
                    "Route distance must be greater than zero."
                )

            if speed_knots <= 0:
                raise ValueError(
                    "Vessel cruise speed must be greater than zero."
                )

            # routes.json stores distance in KM.
            # voyage.py expects nautical miles.
            distance_nm = (
                distance_km / 1.852
            )

            duration_days = (
                environment_adjusted_voyage_duration_days(
                    distance_nm=distance_nm,
                    speed_knots=speed_knots,
                    environment=conditions,
                )
            )

            arrival_datetime = (
                current_datetime
                + timedelta(
                    days=duration_days
                )
            )

            fuel_required = (
                environment_adjusted_fuel_consumption(
                    duration_days=duration_days,
                    base_fuel_per_day=(
                        self._fuel_per_day(vessel)
                    ),
                    environment=conditions,
                )
            )

            fuel_cost = float(
                fuel_mod.calculate_fuel_cost(
                    fuel_required,
                    self._fuel_cost_per_litre(
                        vessel
                    ),
                )
            )

            # calculate_operating_cost returns Decimal
            # in the current cost module. Convert it to float
            # immediately so all ResupplyOption monetary values
            # use one numeric type.
            operating_cost = float(
                calculate_operating_cost(
                    duration_days,
                    self._operating_cost_per_day(
                        vessel
                    ),
                )
            )

        except (
            TypeError,
            ValueError,
            ZeroDivisionError,
        ) as exc:

            voyage_calculation_failed = True

            rejection_reasons.append(
                f"Voyage calculation failed: {exc}"
            )

        # --------------------------------------------------------------
        # Fuel capacity
        # --------------------------------------------------------------

        fuel_capacity = (
            self._fuel_capacity(vessel)
        )

        if not voyage_calculation_failed:

            try:

                has_sufficient_fuel = (
                    fuel_mod.validate_fuel_capacity(
                        fuel_required_litres=(
                            fuel_required
                        ),
                        fuel_capacity_litres=(
                            fuel_capacity
                        ),
                    )
                )

                if not has_sufficient_fuel:
                    rejection_reasons.append(
                        "Insufficient fuel capacity "
                        "for voyage: requires "
                        f"{fuel_required:,.0f} litres, "
                        "but vessel capacity is only "
                        f"{fuel_capacity:,.0f} litres."
                    )

            except (
                TypeError,
                ValueError,
            ) as exc:

                rejection_reasons.append(
                    "Fuel capacity validation failed: "
                    f"{exc}"
                )

        # --------------------------------------------------------------
        # Inventory deadline
        # --------------------------------------------------------------

        inventory_deadline = (
            self._calculate_inventory_deadline(
                resource=resource,
                current_datetime=current_datetime,
            )
        )

        if latest_safe_arrival is None:
            latest_safe_arrival = (
                inventory_deadline
            )

        safety_margin_days: Optional[
            float
        ] = None

        if (
            arrival_datetime is not None
            and latest_safe_arrival is not None
        ):

            safety_margin_days = (
                (
                    latest_safe_arrival
                    - arrival_datetime
                ).total_seconds()
                / 86400.0
            )

            if safety_margin_days < 0:

                rejection_reasons.append(
                    "Arrival occurs after the "
                    "latest safe arrival deadline "
                    "by "
                    f"{-safety_margin_days:.1f} days."
                )

            elif safety_margin_days < 3:

                warnings.append(
                    "Low safety margin: only "
                    f"{safety_margin_days:.1f} days "
                    "remain before the latest "
                    "safe arrival deadline."
                )

        # --------------------------------------------------------------
        # Route/environment risk
        # --------------------------------------------------------------

        base_risk = self._route_risk(
            route
        )

        try:
            risk_score = float(
                conditions.risk_score(
                    base_risk
                )
            )

        except (
            TypeError,
            ValueError,
        ):
            risk_score = float(
                base_risk
            )

        if risk_score >= 0.75:

            warnings.append(
                "High environmental/route risk "
                f"score: {risk_score:.2f}."
            )

        elif risk_score >= 0.5:

            warnings.append(
                "Moderate environmental/route risk "
                f"score: {risk_score:.2f}."
            )

        # --------------------------------------------------------------
        # Explainable reasons
        # --------------------------------------------------------------

        if not rejection_reasons:

            # For feasible options, `reasons` is intentionally
            # operational rather than merely saying "feasible".
            rejection_reasons.extend(
                [
                    (
                        "Cargo requirement of "
                        f"{cargo_weight_tonnes:,.1f} tonnes "
                        "fits within vessel capacity of "
                        f"{vessel_capacity:,.1f} tonnes."
                    ),
                    (
                        "Fuel requirement of "
                        f"{fuel_required:,.0f} litres "
                        "fits within available fuel "
                        f"capacity of "
                        f"{fuel_capacity:,.0f} litres."
                    ),
                    (
                        "Estimated total voyage cost is "
                        f"{fuel_cost + operating_cost:,.0f} "
                        "including fuel and operating costs."
                    ),
                    (
                        "Route/environment risk score is "
                        f"{risk_score:.2f}."
                    ),
                ]
            )

            if arrival_datetime is not None:

                rejection_reasons.append(
                    "Estimated arrival is "
                    f"{arrival_datetime.isoformat()}."
                )

            if safety_margin_days is not None:

                rejection_reasons.append(
                    "Estimated safety margin is "
                    f"{safety_margin_days:.1f} days."
                )

        # --------------------------------------------------------------
        # Final feasibility
        # --------------------------------------------------------------

        feasible = (
            len(
                [
                    reason
                    for reason in rejection_reasons
                    if (
                        reason.startswith(
                            "Cargo weight cannot"
                        )
                        or reason.startswith(
                            "Cargo weight "
                        )
                        or reason.startswith(
                            "Vessel is unavailable"
                        )
                        or reason.startswith(
                            "Vessel availability ended"
                        )
                        or reason.startswith(
                            "Route destination"
                        )
                        or reason.startswith(
                            "Origin port"
                        )
                        or reason.startswith(
                            "Voyage calculation failed"
                        )
                        or reason.startswith(
                            "Insufficient fuel capacity"
                        )
                        or reason.startswith(
                            "Fuel capacity validation failed"
                        )
                        or reason.startswith(
                            "Arrival occurs after"
                        )
                    )
                ]
            )
            == 0
        )

        # The above logic preserves the original rejection behavior
        # while allowing feasible options to have explanatory reasons.
        #
        # If any actual rejection was recorded before the explanatory
        # reasons were added, the option must remain infeasible.
        actual_rejections = []

        for reason in rejection_reasons:

            if (
                reason.startswith(
                    "Cargo weight cannot"
                )
                or reason.startswith(
                    "Cargo weight "
                )
                and "exceeds vessel capacity" in reason
                or reason.startswith(
                    "Vessel is unavailable"
                )
                or reason.startswith(
                    "Vessel availability ended"
                )
                or reason.startswith(
                    "Route destination"
                )
                or reason.startswith(
                    "Origin port"
                )
                or reason.startswith(
                    "Voyage calculation failed"
                )
                or reason.startswith(
                    "Insufficient fuel capacity"
                )
                or reason.startswith(
                    "Fuel capacity validation failed"
                )
                or reason.startswith(
                    "Arrival occurs after"
                )
            ):
                actual_rejections.append(
                    reason
                )

        feasible = len(actual_rejections) == 0

        return ResupplyOption(
            vessel=vessel,
            route=route,
            station=station,
            resource=resource,
            cargo_weight_tonnes=(
                cargo_weight_tonnes
            ),
            departure_datetime=(
                current_datetime
            ),
            arrival_datetime=(
                arrival_datetime
            ),
            duration_days=float(
                duration_days
            ),
            fuel_required_litres=float(
                fuel_required
            ),
            fuel_capacity_litres=float(
                fuel_capacity
            ),
            fuel_cost=float(
                fuel_cost
            ),
            operating_cost=float(
                operating_cost
            ),
            total_cost=float(
                fuel_cost + operating_cost
            ),
            risk_score=float(
                risk_score
            ),
            safety_margin_days=(
                safety_margin_days
            ),
            feasible=feasible,
            rejection_reasons=(
                rejection_reasons
            ),
            warnings=warnings,
            environment=conditions,
        )

    # ==================================================================
    # Optimization
    # ==================================================================

    def optimize(
        self,
        station: Station,
        resource: Any,
        current_datetime: datetime,
        cargo_weight_tonnes: float,
        latest_safe_arrival: Optional[
            datetime
        ] = None,
        environment: Optional[
            EnvironmentConditions
        ] = None,
        vessels: Optional[list[Vessel]] = None,
        routes: Optional[list[Route]] = None,
    ) -> ResupplyOptimizationResult:

        # Explicit arguments override constructor data.
        # This preserves both APIs:
        #
        # ResupplyOptimizer(vessels=..., routes=...)
        #
        # and
        #
        # optimizer.optimize(vessels=..., routes=...)

        candidate_vessels = (
            self.vessels
            if vessels is None
            else vessels
        )

        candidate_routes = (
            self.routes
            if routes is None
            else routes
        )

        all_options: list[
            ResupplyOption
        ] = []

        departure_dates = [
            current_datetime
            + timedelta(days=offset)
            for offset in range(
                0,
                self.departure_window_days + 1,
                self.departure_step_days,
            )
        ]

        for vessel in candidate_vessels:

            for route in candidate_routes:

                for departure_datetime in (
                    departure_dates
                ):

                    option = (
                        self.evaluate_option(
                            vessel=vessel,
                            route=route,
                            station=station,
                            resource=resource,
                            current_datetime=(
                                departure_datetime
                            ),
                            cargo_weight_tonnes=(
                                cargo_weight_tonnes
                            ),
                            latest_safe_arrival=(
                                latest_safe_arrival
                            ),
                            environment=environment,
                        )
                    )

                    all_options.append(
                        option
                    )

        feasible_options = [
            option
            for option in all_options
            if option.feasible
        ]

        infeasible_options = [
            option
            for option in all_options
            if not option.feasible
        ]

        # --------------------------------------------------------------
        # Ranking
        # --------------------------------------------------------------
        #
        # If there is a deadline:
        #
        #   1. Safety margin
        #   2. Cost
        #   3. Fuel
        #   4. Duration
        #   5. Risk
        #
        # If there is NO deadline:
        #
        #   1. Duration
        #   2. Cost
        #   3. Fuel
        #   4. Risk
        #
        # This preserves the expected "FAST" result in the existing
        # test suite while still making deadline-aware optimization
        # prioritize schedule safety.

        if latest_safe_arrival is not None:

            feasible_options.sort(
                key=lambda option: (
                    (
                        option.safety_margin_days
                        if option.safety_margin_days
                        is not None
                        else float("-inf")
                    ),
                    -option.total_cost,
                    -option.fuel_required_litres,
                    -option.duration_days,
                    -option.risk_score,
                ),
                reverse=True,
            )

        else:

            feasible_options.sort(
                key=lambda option: (
                    option.duration_days,
                    option.total_cost,
                    option.fuel_required_litres,
                    option.risk_score,
                )
            )

        selected_option = (
            feasible_options[0]
            if feasible_options
            else None
        )

        return ResupplyOptimizationResult(
            selected_option=selected_option,
            feasible_options=feasible_options,
            infeasible_options=infeasible_options,
        )

    # ==================================================================
    # Convenience API
    # ==================================================================

    def optimize_resupply(
        self,
        station: Station,
        resource: Any,
        current_datetime: datetime,
        cargo_weight_tonnes: Optional[
            float
        ] = None,
        latest_safe_arrival: Optional[
            datetime
        ] = None,
        environment: Optional[
            EnvironmentConditions
        ] = None,
    ) -> ResupplyOptimizationResult:

        if cargo_weight_tonnes is None:

            cargo_weight_tonnes = self._get(
                resource,
                "required_resupply_quantity",
                "resupply_quantity",
                "quantity",
                default=0.0,
            )

        return self.optimize(
            station=station,
            resource=resource,
            current_datetime=current_datetime,
            cargo_weight_tonnes=float(
                cargo_weight_tonnes
            ),
            latest_safe_arrival=(
                latest_safe_arrival
            ),
            environment=environment,
        )


# ======================================================================
# BACKWARDS-COMPATIBLE FUNCTIONAL API
# ======================================================================


def optimize_resupply(
    vessels: list[Vessel],
    routes: list[Route],
    station: Station,
    resource: Any,
    current_datetime: datetime,
    cargo_weight_tonnes: Optional[
        float
    ] = None,
    latest_safe_arrival: Optional[
        datetime
    ] = None,
    ports: Optional[list[Port]] = None,
    departure_window_days: int = 0,
    departure_step_days: int = 1,
    environment_provider: Optional[
        EnvironmentProvider
    ] = None,
    environment: Optional[
        EnvironmentConditions
    ] = None,
) -> ResupplyOptimizationResult:

    optimizer = ResupplyOptimizer(
        vessels=vessels,
        routes=routes,
        ports=ports,
        departure_window_days=(
            departure_window_days
        ),
        departure_step_days=(
            departure_step_days
        ),
        environment_provider=(
            environment_provider
        ),
    )

    return optimizer.optimize_resupply(
        station=station,
        resource=resource,
        current_datetime=current_datetime,
        cargo_weight_tonnes=(
            cargo_weight_tonnes
        ),
        latest_safe_arrival=(
            latest_safe_arrival
        ),
        environment=environment,
    )