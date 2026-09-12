from __future__ import annotations

from typing import Any

from engine import optimizer
from engine.models import ResourceInventory

from api.schemas import (
    OptimizeRequest,
    OptimizationResponse,
    VoyageOptionResponse,
)
from api.services.data_service import (
    load_ports,
    load_routes,
    load_stations,
    load_vessels,
)


def _option_to_response(option: Any) -> VoyageOptionResponse:
    routes = load_routes()
    ports = load_ports()
    stations = load_stations()
    vessels = load_vessels()

    route = None
    origin_port = None
    destination_station = None
    vessel = None

    if option.route_id:
        route = next(
            (
                item
                for item in routes
                if item.id == option.route_id
            ),
            None,
        )

    if option.origin_port_id:
        origin_port = next(
            (
                item
                for item in ports
                if item.id == option.origin_port_id
            ),
            None,
        )

    if option.destination_station_id:
        destination_station = next(
            (
                item
                for item in stations
                if item.id == option.destination_station_id
            ),
            None,
        )

    if option.vessel_id:
        vessel = next(
            (
                item
                for item in vessels
                if item.id == option.vessel_id
            ),
            None,
        )

    distance_km = float(option.distance_km)
    distance_nm = distance_km / 1.852

    cargo_weight = float(option.cargo_weight_tonnes)

    if cargo_weight > 0:
        cost_per_tonne = (
            float(option.total_cost)
            / cargo_weight
        )
    else:
        cost_per_tonne = 0.0

    return VoyageOptionResponse(
        vessel_id=(
            vessel.id
            if vessel is not None
            else option.vessel_id or None
        ),
        vessel_name=(
            vessel.name
            if vessel is not None
            else None
        ),
        route_id=(
            route.id
            if route is not None
            else option.route_id or None
        ),
        route_name=(
            route.name
            if route is not None
            else None
        ),
        origin_port_id=(
            origin_port.id
            if origin_port is not None
            else option.origin_port_id or None
        ),
        origin_port_name=(
            origin_port.name
            if origin_port is not None
            else None
        ),
        destination_station_id=(
            destination_station.id
            if destination_station is not None
            else option.destination_station_id or None
        ),
        destination_station_name=(
            destination_station.name
            if destination_station is not None
            else None
        ),
        departure=option.departure_datetime,
        arrival=option.arrival_datetime,
        distance_km=distance_km,
        distance_nm=distance_nm,
        voyage_duration_days=float(
            option.duration_days
        ),
        fuel_required_litres=float(
            option.fuel_required_litres
        ),
        fuel_cost=float(option.fuel_cost),
        operating_cost=float(option.operating_cost),
        total_cost=float(option.total_cost),
        cost_per_tonne=cost_per_tonne,
        safety_margin_days=(
            float(option.safety_margin_days)
            if option.safety_margin_days is not None
            else None
        ),
        feasible=option.feasible,
        rejection_reason=option.rejection_reason,
    )


def optimize_resupply_plan(
    request: OptimizeRequest,
) -> OptimizationResponse:

    ports = load_ports()
    stations = load_stations()
    vessels = load_vessels()

    # Load all routes, then keep only routes that actually
    # terminate at the station requested by the user.
    all_routes = load_routes()

    routes = [
        route
        for route in all_routes
        if route.destination_station_id == request.station_id
    ]

    station = next(
        (
            item
            for item in stations
            if item.id == request.station_id
        ),
        None,
    )

    if station is None:
        raise ValueError(
            f"Station not found: {request.station_id}"
        )

    if not routes:
        raise ValueError(
            f"No routes found for station: {request.station_id}"
        )

    inventory = ResourceInventory(
        resource_name=request.inventory.resource_name,
        current_quantity=request.inventory.current_quantity,
        unit=request.inventory.unit,
        daily_consumption=request.inventory.daily_consumption,
        minimum_safety_threshold=(
            request.inventory.minimum_safety_threshold
        ),
        required_resupply_quantity=(
            request.inventory.required_resupply_quantity
        ),
    )

    # Keep the station-specific inventory structure simple:
    #
    # {
    #     "MAITRI": [ResourceInventory(...)]
    # }
    #
    # This allows the optimizer to correctly inspect the resource
    # object and calculate its inventory deadline.
    station_inventory = {
        request.station_id: [inventory]
    }

    result = optimizer.optimize_resupply(
        ports=ports,
        stations=[station],
        vessels=vessels,
        routes=routes,
        departure_dates=request.departure_dates,
        cargo_weight_tonnes=request.cargo_weight_tonnes,
        station_inventory=station_inventory,
        safety_buffer_days=request.safety_buffer_days,
        current_datetime=request.current_datetime,
        max_alternatives=request.max_alternatives,
    )

    if result.best_option is not None:
        status = "success"
        message = "Optimal resupply plan found."

    elif result.infeasible_options:
        status = "infeasible"
        message = (
            "No feasible resupply plan was found for "
            "the supplied constraints."
        )

    else:
        status = "no_solution"
        message = "No resupply options were generated."

    recommended = None

    if result.best_option is not None:
        recommended = _option_to_response(
            result.best_option
        )

    alternatives = [
        _option_to_response(option)
        for option in result.alternatives
    ]

    infeasible = [
        _option_to_response(option)
        for option in result.infeasible_options
    ]

    return OptimizationResponse(
        status=status,
        message=message,
        recommended_option=recommended,
        alternatives=alternatives,
        infeasible_options=infeasible,
    )