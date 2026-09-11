from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from decimal import Decimal
from typing import Dict, List, Optional, Sequence

from . import cost as cost_mod
from . import deadline as deadline_mod
from . import distance as distance_mod
from . import fuel as fuel_mod
from . import voyage as voyage_mod
from .models import Port, ResourceInventory, Route, Station, Vessel


@dataclass
class VoyageOption:
    """
    A single evaluated resupply-voyage option.

    This represents one vessel + route + departure-date combination.
    """

    vessel: Vessel
    route: Route
    origin_port: Port
    destination_station: Station

    departure: datetime
    arrival: datetime

    distance_km: float
    distance_nm: float
    voyage_duration_days: float

    fuel_required_litres: float
    fuel_cost: Decimal
    operating_cost: Decimal
    total_cost: Decimal
    cost_per_tonne: Decimal

    safety_margin_days: float

    remaining_inventory: Dict[str, float]

    feasible: bool
    rejection_reason: Optional[str] = None


@dataclass
class OptimizationResult:
    """Result returned by the resupply optimizer."""

    best_option: Optional[VoyageOption]
    alternatives: List[VoyageOption]
    infeasible_options: List[VoyageOption]
    all_options: List[VoyageOption]

    status: str
    message: str


def _ensure_utc(value: datetime, name: str) -> datetime:
    """Ensure a datetime is timezone-aware and normalize it to UTC."""

    if value.tzinfo is None:
        raise ValueError(
            f"{name} must be timezone-aware"
        )

    return value.astimezone(timezone.utc)


def _get_route_distance(
    route: Route,
) -> tuple[float, float]:
    """
    Calculate route distance from its waypoint geometry.

    Waypoints are treated as the authoritative route geometry.
    """

    distance_km = distance_mod.calculate_route_distance_km(
        route.waypoints
    )

    distance_nm = distance_km / 1.852

    return distance_km, distance_nm


def _get_station_inventory(
    station_id: str,
    station_inventory: Dict[
        str,
        Dict[str, ResourceInventory],
    ],
) -> Optional[Dict[str, ResourceInventory]]:
    """Return inventory resources for a station."""

    return station_inventory.get(station_id)


def _find_critical_date(
    inventory: Dict[str, ResourceInventory],
    current_datetime: datetime,
) -> Optional[datetime]:
    """
    Find the earliest critical date among all station resources.

    The first resource to reach its safety threshold determines
    the station's resupply deadline.
    """

    critical_dates: List[datetime] = []

    for resource in inventory.values():
        critical_date = inventory_mod_calculate_critical_date(
            resource,
            current_datetime,
        )

        if critical_date is not None:
            critical_dates.append(critical_date)

    if not critical_dates:
        return None

    return min(critical_dates)


def inventory_mod_calculate_critical_date(
    inventory: ResourceInventory,
    current_datetime: datetime,
) -> Optional[datetime]:
    """
    Local wrapper around the inventory engine.

    Kept here so the optimizer has one clear inventory calculation path.
    """

    from . import inventory as inventory_mod

    return inventory_mod.calculate_critical_date(
        inventory,
        current_datetime,
    )


def _calculate_remaining_inventory(
    inventory: Dict[str, ResourceInventory],
    current_datetime: datetime,
    arrival_datetime: datetime,
) -> Dict[str, float]:
    """Calculate projected inventory at arrival."""

    from . import inventory as inventory_mod

    return {
        resource_name: inventory_mod.calculate_inventory_on_date(
            resource,
            current_datetime,
            arrival_datetime,
        )
        for resource_name, resource in inventory.items()
    }


def _check_vessel_availability(
    vessel: Vessel,
    departure: datetime,
    arrival: datetime,
) -> Optional[str]:
    """Return a rejection reason if the vessel is unavailable."""

    departure = _ensure_utc(
        departure,
        "departure",
    )

    arrival = _ensure_utc(
        arrival,
        "arrival",
    )

    availability_start = _ensure_utc(
        vessel.availability_start,
        "vessel.availability_start",
    )

    availability_end = _ensure_utc(
        vessel.availability_end,
        "vessel.availability_end",
    )

    if departure < availability_start:
        return "VESSEL_UNAVAILABLE_AT_DEPARTURE"

    if departure > availability_end:
        return "VESSEL_UNAVAILABLE_AT_DEPARTURE"

    if arrival > availability_end:
        return "VESSEL_UNAVAILABLE_FOR_COMPLETE_VOYAGE"

    return None


def _check_port_availability(
    port: Port,
) -> Optional[str]:
    """Check whether a port is available for simulation."""

    if not port.available_for_simulation:
        return "PORT_UNAVAILABLE"

    return None


def _check_route_match(
    route: Route,
    port: Port,
    station: Station,
) -> Optional[str]:
    """Ensure the route connects the selected port and station."""

    if route.origin_port_id != port.id:
        return "ROUTE_ORIGIN_MISMATCH"

    if route.destination_station_id != station.id:
        return "ROUTE_DESTINATION_MISMATCH"

    return None


def _check_cargo_capacity(
    vessel: Vessel,
    cargo_weight_tonnes: float,
) -> Optional[str]:
    """Check whether the vessel can carry the required cargo."""

    if cargo_weight_tonnes <= 0:
        return "INVALID_CARGO_WEIGHT"

    if cargo_weight_tonnes > vessel.cargo_capacity_tonnes:
        return "INSUFFICIENT_CARGO_CAPACITY"

    return None


def _check_station_receiving_capacity(
    station: Station,
    cargo_weight_tonnes: float,
) -> Optional[str]:
    """Check whether the station can receive the proposed cargo."""

    if cargo_weight_tonnes > station.receiving_capacity_tonnes:
        return "STATION_RECEIVING_CAPACITY_EXCEEDED"

    return None


def _check_fuel_capacity(
    vessel: Vessel,
    fuel_required_litres: float,
) -> Optional[str]:
    """Check whether the vessel carries enough fuel."""

    if fuel_required_litres > vessel.fuel_capacity_litres:
        return "INSUFFICIENT_FUEL"

    return None


def _check_arrival_deadline(
    arrival: datetime,
    latest_safe_arrival: Optional[datetime],
) -> Optional[str]:
    """Check whether the voyage reaches the station before the deadline."""

    if latest_safe_arrival is None:
        return None

    if arrival > latest_safe_arrival:
        return "ARRIVAL_AFTER_DEADLINE"

    return None


def _score_option(
    option: VoyageOption,
) -> tuple:
    """
    Score an option for deterministic optimization.

    Higher safety margin is better.
    Lower cost is better.
    Lower fuel consumption is better.
    Shorter duration is better.
    """

    return (
        1 if option.feasible else 0,
        option.safety_margin_days,
        -float(option.total_cost),
        -option.fuel_required_litres,
        -option.voyage_duration_days,
    )


def _sort_options(
    options: Sequence[VoyageOption],
) -> List[VoyageOption]:
    """Return options sorted from best to worst."""

    return sorted(
        options,
        key=_score_option,
        reverse=True,
    )


def optimize_resupply(
    ports: Sequence[Port],
    stations: Sequence[Station],
    vessels: Sequence[Vessel],
    routes: Sequence[Route],
    departure_dates: Sequence[datetime],
    cargo_weight_tonnes: float,
    station_inventory: Dict[
        str,
        Dict[str, ResourceInventory],
    ],
    safety_buffer_days: float = 3.0,
    current_datetime: Optional[datetime] = None,
    max_alternatives: int = 3,
) -> OptimizationResult:
    """
    Evaluate and rank simulated Antarctic resupply voyages.

    The optimizer considers:

    - route geometry
    - vessel speed
    - vessel fuel consumption
    - fuel capacity
    - cargo capacity
    - port availability
    - vessel availability
    - station receiving capacity
    - inventory depletion
    - safety buffer
    - arrival deadline
    - voyage cost

    Parameters
    ----------
    ports:
        Available simulated Indian departure ports.

    stations:
        Operational Antarctic research stations.

    vessels:
        Simulated resupply vessels.

    routes:
        Simulated maritime corridors.

    departure_dates:
        Candidate UTC departure times.

    cargo_weight_tonnes:
        Cargo planned for the voyage.

    station_inventory:
        Mapping:
            station_id -> resource_name -> ResourceInventory

    safety_buffer_days:
        Required number of days before the actual critical date.

    current_datetime:
        Reference time used for inventory projection.
        Defaults to the earliest departure date.

    max_alternatives:
        Maximum number of alternatives returned in addition
        to the best option.
    """

    if cargo_weight_tonnes <= 0:
        raise ValueError(
            "cargo_weight_tonnes must be positive"
        )

    if safety_buffer_days < 0:
        raise ValueError(
            "safety_buffer_days must be non-negative"
        )

    if max_alternatives < 0:
        raise ValueError(
            "max_alternatives must be non-negative"
        )

    if not ports:
        raise ValueError("At least one port is required")

    if not stations:
        raise ValueError("At least one station is required")

    if not vessels:
        raise ValueError("At least one vessel is required")

    if not routes:
        raise ValueError("At least one route is required")

    if not departure_dates:
        raise ValueError(
            "At least one departure date is required"
        )

    normalized_departures = [
        _ensure_utc(
            departure,
            "departure_date",
        )
        for departure in departure_dates
    ]

    if current_datetime is None:
        current_datetime = min(normalized_departures)
    else:
        current_datetime = _ensure_utc(
            current_datetime,
            "current_datetime",
        )

    all_options: List[VoyageOption] = []

    for station in stations:

        inventory = _get_station_inventory(
            station.id,
            station_inventory,
        )

        if inventory is None:
            continue

        critical_date = _find_critical_date(
            inventory,
            current_datetime,
        )

        latest_safe_arrival: Optional[datetime] = None

        if critical_date is not None:
            latest_safe_arrival = (
                deadline_mod.calculate_latest_safe_arrival(
                    critical_date,
                    safety_buffer_days,
                )
            )

        for route in routes:

            route_match_error = None

            for port in ports:

                route_match_error = _check_route_match(
                    route,
                    port,
                    station,
                )

                if route_match_error is not None:
                    continue

                port_error = _check_port_availability(
                    port,
                )

                for vessel in vessels:

                    cargo_error = _check_cargo_capacity(
                        vessel,
                        cargo_weight_tonnes,
                    )

                    station_capacity_error = (
                        _check_station_receiving_capacity(
                            station,
                            cargo_weight_tonnes,
                        )
                    )

                    route_distance_km, route_distance_nm = (
                        _get_route_distance(route)
                    )

                    voyage_duration_days = (
                        voyage_mod.calculate_voyage_days(
                            route_distance_nm,
                            vessel.cruising_speed_knots,
                        )
                    )

                    fuel_required = (
                        fuel_mod.calculate_fuel_consumption(
                            voyage_duration_days,
                            vessel.fuel_consumption_litres_per_day,
                        )
                    )

                    departure_error = None

                    for departure in normalized_departures:

                        arrival = voyage_mod.calculate_eta(
                            departure,
                            route_distance_nm,
                            vessel.cruising_speed_knots,
                        )

                        vessel_error = (
                            _check_vessel_availability(
                                vessel,
                                departure,
                                arrival,
                            )
                        )

                        fuel_error = _check_fuel_capacity(
                            vessel,
                            fuel_required,
                        )

                        deadline_error = (
                            _check_arrival_deadline(
                                arrival,
                                latest_safe_arrival,
                            )
                        )

                        safety_margin = 0.0

                        if latest_safe_arrival is not None:
                            safety_margin = (
                                deadline_mod.calculate_safety_margin_days(
                                    latest_safe_arrival,
                                    arrival,
                                )
                            )

                        remaining_inventory = (
                            _calculate_remaining_inventory(
                                inventory,
                                current_datetime,
                                arrival,
                            )
                        )

                        fuel_cost = (
                            fuel_mod.calculate_fuel_cost(
                                fuel_required,
                                vessel.fuel_cost_per_litre,
                            )
                        )

                        operating_cost = (
                            cost_mod.calculate_operating_cost(
                                voyage_duration_days,
                                vessel.operating_cost_per_day,
                            )
                        )

                        total_cost = (
                            cost_mod.calculate_total_cost(
                                fuel_cost,
                                operating_cost,
                            )
                        )

                        cost_per_tonne = (
                            cost_mod.calculate_cost_per_tonne(
                                total_cost,
                                cargo_weight_tonnes,
                            )
                        )

                        rejection_reason = (
                            cargo_error
                            or station_capacity_error
                            or port_error
                            or vessel_error
                            or fuel_error
                            or deadline_error
                        )

                        feasible = (
                            rejection_reason is None
                        )

                        option = VoyageOption(
                            vessel=vessel,
                            route=route,
                            origin_port=port,
                            destination_station=station,
                            departure=departure,
                            arrival=arrival,
                            distance_km=route_distance_km,
                            distance_nm=route_distance_nm,
                            voyage_duration_days=voyage_duration_days,
                            fuel_required_litres=fuel_required,
                            fuel_cost=fuel_cost,
                            operating_cost=operating_cost,
                            total_cost=total_cost,
                            cost_per_tonne=cost_per_tonne,
                            safety_margin_days=safety_margin,
                            remaining_inventory=remaining_inventory,
                            feasible=feasible,
                            rejection_reason=rejection_reason,
                        )

                        all_options.append(option)

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

    ranked_feasible = _sort_options(
        feasible_options
    )

    ranked_infeasible = _sort_options(
        infeasible_options
    )

    if not ranked_feasible:
        if ranked_infeasible:
            reasons = sorted(
                {
                    option.rejection_reason
                    for option in ranked_infeasible
                    if option.rejection_reason
                }
            )

            reason_text = ", ".join(reasons)

            message = (
                "No feasible resupply plan was found. "
                f"Candidate rejection reasons: {reason_text}."
            )
        else:
            message = (
                "No valid voyage candidates were generated."
            )

        return OptimizationResult(
            best_option=None,
            alternatives=[],
            infeasible_options=ranked_infeasible,
            all_options=all_options,
            status="NO_FEASIBLE_PLAN",
            message=message,
        )

    best_option = ranked_feasible[0]

    alternatives = ranked_feasible[
        1 : 1 + max_alternatives
    ]

    return OptimizationResult(
        best_option=best_option,
        alternatives=alternatives,
        infeasible_options=ranked_infeasible,
        all_options=all_options,
        status="FEASIBLE_PLAN_FOUND",
        message=(
            "A feasible resupply plan was found and ranked "
            "against all evaluated candidates."
        ),
    )


__all__ = [
    "VoyageOption",
    "OptimizationResult",
    "optimize_resupply",
]