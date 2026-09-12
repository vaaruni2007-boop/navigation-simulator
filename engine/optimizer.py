from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Any, Mapping, Optional, Sequence

from engine.cost import calculate_operating_cost, calculate_total_cost
from engine.fuel import calculate_fuel_consumption, validate_fuel_capacity
from engine.voyage import calculate_voyage_duration


@dataclass
class VoyageOption:
    vessel_id: str
    route_id: str
    origin_port_id: str
    destination_station_id: str
    departure_datetime: datetime
    arrival_datetime: Optional[datetime]
    duration_days: float
    distance_km: float
    fuel_required_litres: float
    fuel_cost: float
    operating_cost: float
    total_cost: float
    cargo_weight_tonnes: float
    feasible: bool
    rejection_reason: Optional[str] = None
    safety_margin_days: Optional[float] = None
    risk_score: float = 0.0

    vessel: Any = None


@dataclass
class OptimizationResult:
    best_option: Optional[VoyageOption]
    alternatives: list[VoyageOption] = field(default_factory=list)
    rejected_options: list[VoyageOption] = field(default_factory=list)

    @property
    def infeasible_options(self) -> list[VoyageOption]:
        return self.rejected_options


def _get(obj: Any, *names: str, default: Any = None) -> Any:
    """Get a value from either an object attribute or mapping key."""
    for name in names:
        if isinstance(obj, Mapping):
            if name in obj:
                return obj[name]
        elif hasattr(obj, name):
            return getattr(obj, name)

    return default


def _as_utc(value: Optional[datetime]) -> Optional[datetime]:
    if value is None:
        return None

    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)

    return value.astimezone(timezone.utc)


def _same_id(obj: Any, expected: Any, *names: str) -> bool:
    value = _get(obj, *names, default=None)

    if value is None or expected is None:
        return False

    return str(value) == str(expected)


def _availability_reason(
    vessel: Any,
    departure: datetime,
) -> Optional[str]:
    """Return a rejection reason if the vessel is unavailable."""

    departure = _as_utc(departure)

    availability_start = _get(
        vessel,
        "availability_start",
        "available_from",
        "start_date",
        default=None,
    )

    availability_end = _get(
        vessel,
        "availability_end",
        "available_until",
        "end_date",
        default=None,
    )

    availability_start = _as_utc(availability_start)
    availability_end = _as_utc(availability_end)

    if (
        availability_start is not None
        and departure < availability_start
    ):
        return (
            f"Vessel availability violation: departure "
            f"{departure.isoformat()} is before availability start "
            f"{availability_start.isoformat()}."
        )

    if (
        availability_end is not None
        and departure > availability_end
    ):
        return (
            f"Vessel availability violation: departure "
            f"{departure.isoformat()} is after availability end "
            f"{availability_end.isoformat()}."
        )

    return None


def _get_inventory_deadline(
    station_inventory: Optional[Mapping[str, Any]],
    station_id: str,
    current_datetime: datetime,
    safety_buffer_days: float,
) -> Optional[datetime]:
    """
    Calculate the earliest safe arrival deadline for a station.

    The deadline is the earliest time at which any tracked resource
    reaches its minimum safety threshold, minus the requested safety
    buffer.

    Supports:
    - ResourceInventory-like objects
    - mappings containing resource data
    - lists/tuples of resources
    - nested station/resource mappings
    """

    if not station_inventory:
        return None

    inventory = station_inventory.get(station_id)

    if inventory is None:
        return None

    if isinstance(inventory, Mapping):
        resources = list(inventory.values())
    elif isinstance(inventory, (list, tuple)):
        resources = list(inventory)
    else:
        resources = [inventory]

    deadlines: list[datetime] = []

    for resource in resources:

        # Handle nested structures defensively.
        if isinstance(resource, Mapping):
            nested_values = list(resource.values())

            # If this mapping itself contains inventory fields,
            # treat it as one resource rather than expanding it.
            if (
                "current_quantity" in resource
                or "daily_consumption" in resource
                or "minimum_safety_threshold" in resource
            ):
                resource_items = [resource]
            else:
                resource_items = nested_values
        else:
            resource_items = [resource]

        for item in resource_items:

            critical_date = None

            # Existing/custom inventory objects may expose their own
            # critical-date calculation.
            if hasattr(item, "calculate_critical_date"):
                critical_date = item.calculate_critical_date(
                    current_datetime
                )

            else:
                current_quantity = _get(
                    item,
                    "current_quantity",
                    default=None,
                )

                daily_consumption = _get(
                    item,
                    "daily_consumption",
                    default=None,
                )

                safety_threshold = _get(
                    item,
                    "minimum_safety_threshold",
                    default=None,
                )

                if (
                    current_quantity is not None
                    and daily_consumption is not None
                    and safety_threshold is not None
                ):
                    current_quantity = float(current_quantity)
                    daily_consumption = float(daily_consumption)
                    safety_threshold = float(safety_threshold)

                    # Already at/below the safety threshold:
                    # the station is already critical.
                    if current_quantity <= safety_threshold:
                        critical_date = current_datetime

                    elif daily_consumption > 0:
                        days_until_threshold = (
                            current_quantity - safety_threshold
                        ) / daily_consumption

                        critical_date = (
                            current_datetime
                            + timedelta(
                                days=days_until_threshold
                            )
                        )

            if critical_date is not None:
                deadlines.append(
                    _as_utc(critical_date)
                )

    if not deadlines:
        return None

    earliest_critical_date = min(deadlines)

    return (
        earliest_critical_date
        - timedelta(days=safety_buffer_days)
    )


def _make_rejected_option(
    *,
    vessel_id: str,
    route_id: str,
    origin_port_id: str,
    destination_station_id: str,
    departure: datetime,
    distance_km: float,
    cargo_weight_tonnes: float,
    reason: str,
    vessel: Any = None,
    duration_days: float = 0.0,
    arrival_datetime: Optional[datetime] = None,
    fuel_required_litres: float = 0.0,
    fuel_cost: float = 0.0,
    operating_cost: float = 0.0,
    total_cost: float = 0.0,
    risk_score: float = 0.0,
    safety_margin_days: Optional[float] = None,
) -> VoyageOption:

    return VoyageOption(
        vessel_id=str(vessel_id),
        route_id=str(route_id),
        origin_port_id=str(origin_port_id),
        destination_station_id=str(
            destination_station_id
        ),
        departure_datetime=departure,
        arrival_datetime=arrival_datetime,
        duration_days=duration_days,
        distance_km=distance_km,
        fuel_required_litres=fuel_required_litres,
        fuel_cost=fuel_cost,
        operating_cost=operating_cost,
        total_cost=total_cost,
        cargo_weight_tonnes=cargo_weight_tonnes,
        feasible=False,
        rejection_reason=reason,
        safety_margin_days=safety_margin_days,
        risk_score=risk_score,
        vessel=vessel,
    )


def optimize_resupply(
    ports,
    stations,
    vessels,
    routes,
    departure_dates: Optional[Sequence[datetime]] = None,
    cargo_weight_tonnes: float = 0.0,
    station_inventory: Optional[Mapping[str, Any]] = None,
    safety_buffer_days: float = 3.0,
    current_datetime: Optional[datetime] = None,
    max_alternatives: int = 2,
    departure_time: Optional[datetime] = None,
) -> OptimizationResult:

    if cargo_weight_tonnes < 0:
        raise ValueError(
            "cargo_weight_tonnes cannot be negative"
        )

    if departure_dates is None:

        if departure_time is not None:
            departure_dates = [departure_time]

        elif current_datetime is not None:
            departure_dates = [current_datetime]

        else:
            departure_dates = [
                datetime.now(timezone.utc)
            ]

    departure_dates = [
        _as_utc(value)
        for value in departure_dates
    ]

    if current_datetime is None:
        current_datetime = min(departure_dates)

    current_datetime = _as_utc(current_datetime)

    feasible_options: list[VoyageOption] = []
    rejected_options: list[VoyageOption] = []

    for route in routes:

        route_id = _get(
            route,
            "id",
            "route_id",
            default="",
        )

        origin_port_id = _get(
            route,
            "origin_port_id",
            "port_id",
            "origin_id",
            default=None,
        )

        destination_station_id = _get(
            route,
            "destination_station_id",
            "station_id",
            "destination_id",
            default=None,
        )

        distance_km = float(
            _get(
                route,
                "distance_km",
                "distance",
                default=0.0,
            )
        )

        risk_score = float(
            _get(
                route,
                "base_risk_factor",
                "risk_score",
                "risk",
                default=0.0,
            )
        )

        for departure in departure_dates:

            departure = _as_utc(departure)

            # ---------------------------------------------------------
            # Validate origin port.
            # ---------------------------------------------------------

            port = next(
                (
                    p
                    for p in ports
                    if _same_id(
                        p,
                        origin_port_id,
                        "id",
                        "port_id",
                    )
                ),
                None,
            )

            if port is None:
                rejected_options.append(
                    _make_rejected_option(
                        vessel_id="",
                        route_id=route_id,
                        origin_port_id=origin_port_id,
                        destination_station_id=destination_station_id,
                        departure=departure,
                        distance_km=distance_km,
                        cargo_weight_tonnes=cargo_weight_tonnes,
                        reason=(
                            f"Port {origin_port_id} not found."
                        ),
                        risk_score=risk_score,
                    )
                )
                continue

            port_available = _get(
                port,
                "available",
                "is_available",
                default=True,
            )

            if not port_available:
                rejected_options.append(
                    _make_rejected_option(
                        vessel_id="",
                        route_id=route_id,
                        origin_port_id=origin_port_id,
                        destination_station_id=destination_station_id,
                        departure=departure,
                        distance_km=distance_km,
                        cargo_weight_tonnes=cargo_weight_tonnes,
                        reason=(
                            f"Port {origin_port_id} unavailable."
                        ),
                        risk_score=risk_score,
                    )
                )
                continue

            # ---------------------------------------------------------
            # Validate destination station.
            # ---------------------------------------------------------

            station = next(
                (
                    s
                    for s in stations
                    if _same_id(
                        s,
                        destination_station_id,
                        "id",
                        "station_id",
                    )
                ),
                None,
            )

            if station is None:
                rejected_options.append(
                    _make_rejected_option(
                        vessel_id="",
                        route_id=route_id,
                        origin_port_id=origin_port_id,
                        destination_station_id=destination_station_id,
                        departure=departure,
                        distance_km=distance_km,
                        cargo_weight_tonnes=cargo_weight_tonnes,
                        reason=(
                            f"Destination station "
                            f"{destination_station_id} not found."
                        ),
                        risk_score=risk_score,
                    )
                )
                continue

            # ---------------------------------------------------------
            # Calculate inventory deadline ONCE per route/departure.
            # ---------------------------------------------------------

            latest_safe_arrival = _get_inventory_deadline(
                station_inventory=station_inventory,
                station_id=str(destination_station_id),
                current_datetime=current_datetime,
                safety_buffer_days=safety_buffer_days,
            )

            # ---------------------------------------------------------
            # Evaluate vessels.
            # ---------------------------------------------------------

            for vessel in vessels:

                vessel_id = _get(
                    vessel,
                    "id",
                    "vessel_id",
                    default="",
                )

                # -----------------------------------------------------
                # Availability.
                # -----------------------------------------------------

                availability_reason = _availability_reason(
                    vessel,
                    departure,
                )

                if availability_reason is not None:
                    rejected_options.append(
                        _make_rejected_option(
                            vessel_id=vessel_id,
                            route_id=route_id,
                            origin_port_id=origin_port_id,
                            destination_station_id=destination_station_id,
                            departure=departure,
                            distance_km=distance_km,
                            cargo_weight_tonnes=cargo_weight_tonnes,
                            reason=availability_reason,
                            vessel=vessel,
                            risk_score=risk_score,
                        )
                    )
                    continue

                # -----------------------------------------------------
                # Cargo capacity.
                # -----------------------------------------------------

                cargo_capacity = float(
                    _get(
                        vessel,
                        "cargo_capacity_tonnes",
                        "cargo_capacity",
                        "capacity_tonnes",
                        default=0.0,
                    )
                )

                if cargo_weight_tonnes > cargo_capacity:
                    rejected_options.append(
                        _make_rejected_option(
                            vessel_id=vessel_id,
                            route_id=route_id,
                            origin_port_id=origin_port_id,
                            destination_station_id=destination_station_id,
                            departure=departure,
                            distance_km=distance_km,
                            cargo_weight_tonnes=cargo_weight_tonnes,
                            reason=(
                                f"Cargo weight "
                                f"{cargo_weight_tonnes} tonnes "
                                f"exceeds vessel capacity "
                                f"{cargo_capacity} tonnes."
                            ),
                            vessel=vessel,
                            risk_score=risk_score,
                        )
                    )
                    continue

                # -----------------------------------------------------
                # Speed.
                # -----------------------------------------------------

                speed_knots = float(
                    _get(
                        vessel,
                        "cruising_speed_knots",
                        "cruise_speed_knots",
                        "cruise_speed",
                        "speed_knots",
                        default=0.0,
                    )
                )

                if speed_knots <= 0:
                    rejected_options.append(
                        _make_rejected_option(
                            vessel_id=vessel_id,
                            route_id=route_id,
                            origin_port_id=origin_port_id,
                            destination_station_id=destination_station_id,
                            departure=departure,
                            distance_km=distance_km,
                            cargo_weight_tonnes=cargo_weight_tonnes,
                            reason=(
                                "Vessel speed must be greater than zero."
                            ),
                            vessel=vessel,
                            risk_score=risk_score,
                        )
                    )
                    continue

                # -----------------------------------------------------
                # Voyage duration.
                # -----------------------------------------------------

                duration_days = float(
                    calculate_voyage_duration(
                        distance_km=distance_km,
                        speed_knots=speed_knots,
                    )
                )

                arrival_datetime = (
                    departure
                    + timedelta(days=duration_days)
                )

                # -----------------------------------------------------
                # Safety deadline check.
                # -----------------------------------------------------

                safety_margin_days = None

                if latest_safe_arrival is not None:
                    safety_margin_days = (
                        (
                            latest_safe_arrival
                            - arrival_datetime
                        ).total_seconds()
                        / 86400.0
                    )

                # -----------------------------------------------------
                # Fuel.
                # -----------------------------------------------------

                fuel_consumption_per_day = float(
                    _get(
                        vessel,
                        "fuel_consumption_litres_per_day",
                        "fuel_consumption_l_per_day",
                        "fuel_consumption",
                        default=0.0,
                    )
                )

                fuel_required = calculate_fuel_consumption(
                    duration_days,
                    fuel_consumption_per_day,
                )

                fuel_capacity = float(
                    _get(
                        vessel,
                        "fuel_capacity_litres",
                        "fuel_capacity",
                        default=0.0,
                    )
                )

                if not validate_fuel_capacity(
                    fuel_required,
                    fuel_capacity,
                ):
                    rejected_options.append(
                        _make_rejected_option(
                            vessel_id=vessel_id,
                            route_id=route_id,
                            origin_port_id=origin_port_id,
                            destination_station_id=destination_station_id,
                            departure=departure,
                            arrival_datetime=arrival_datetime,
                            duration_days=duration_days,
                            distance_km=distance_km,
                            cargo_weight_tonnes=cargo_weight_tonnes,
                            fuel_required_litres=fuel_required,
                            reason=(
                                f"Fuel requirement "
                                f"{fuel_required:.2f} L exceeds "
                                f"fuel capacity "
                                f"{fuel_capacity:.2f} L."
                            ),
                            vessel=vessel,
                            risk_score=risk_score,
                            safety_margin_days=safety_margin_days,
                        )
                    )
                    continue

                # -----------------------------------------------------
                # Inventory deadline is a HARD constraint.
                # -----------------------------------------------------

                if (
                    latest_safe_arrival is not None
                    and arrival_datetime > latest_safe_arrival
                ):
                    delay_days = (
                        arrival_datetime
                        - latest_safe_arrival
                    ).total_seconds() / 86400.0

                    rejected_options.append(
                        _make_rejected_option(
                            vessel_id=vessel_id,
                            route_id=route_id,
                            origin_port_id=origin_port_id,
                            destination_station_id=destination_station_id,
                            departure=departure,
                            arrival_datetime=arrival_datetime,
                            duration_days=duration_days,
                            distance_km=distance_km,
                            cargo_weight_tonnes=cargo_weight_tonnes,
                            fuel_required_litres=fuel_required,
                            reason=(
                                "Arrival misses the station inventory "
                                f"safety deadline by {delay_days:.2f} "
                                "days."
                            ),
                            vessel=vessel,
                            risk_score=risk_score,
                            safety_margin_days=safety_margin_days,
                        )
                    )
                    continue

                # -----------------------------------------------------
                # Costs.
                # -----------------------------------------------------

                fuel_price = float(
                    _get(
                        vessel,
                        "fuel_cost_per_litre",
                        "fuel_price_per_litre",
                        default=0.0,
                    )
                )

                fuel_cost = (
                    fuel_required * fuel_price
                )

                operating_cost_per_day = float(
                    _get(
                        vessel,
                        "operating_cost_per_day",
                        "daily_operating_cost",
                        default=0.0,
                    )
                )

                operating_cost = calculate_operating_cost(
                    duration_days,
                    operating_cost_per_day,
                )

                total_cost = calculate_total_cost(
                    fuel_cost,
                    operating_cost,
                )

                # -----------------------------------------------------
                # Feasible option.
                # -----------------------------------------------------

                option = VoyageOption(
                    vessel_id=str(vessel_id),
                    route_id=str(route_id),
                    origin_port_id=str(origin_port_id),
                    destination_station_id=str(
                        destination_station_id
                    ),
                    departure_datetime=departure,
                    arrival_datetime=arrival_datetime,
                    duration_days=duration_days,
                    distance_km=distance_km,
                    fuel_required_litres=fuel_required,
                    fuel_cost=fuel_cost,
                    operating_cost=operating_cost,
                    total_cost=total_cost,
                    cargo_weight_tonnes=cargo_weight_tonnes,
                    feasible=True,
                    rejection_reason=None,
                    safety_margin_days=safety_margin_days,
                    risk_score=risk_score,
                    vessel=vessel,
                )

                feasible_options.append(option)

    # -----------------------------------------------------------------
    # Rank feasible options.
    #
    # Hard constraints have already been applied above.
    #
    # Among safe options:
    #   1. lowest total cost
    #   2. lowest fuel consumption
    #   3. lowest risk
    #   4. shortest duration
    #   5. larger safety margin as final tie-breaker
    # -----------------------------------------------------------------

    feasible_options.sort(
        key=lambda option: (
            option.total_cost,
            option.fuel_required_litres,
            option.risk_score,
            option.duration_days,
            -(
                option.safety_margin_days
                if option.safety_margin_days is not None
                else float("-inf")
            ),
        )
    )

    best_option = (
        feasible_options[0]
        if feasible_options
        else None
    )

    alternatives = (
        feasible_options[
            1:1 + max_alternatives
        ]
        if best_option is not None
        else []
    )

    return OptimizationResult(
        best_option=best_option,
        alternatives=alternatives,
        rejected_options=rejected_options,
    )