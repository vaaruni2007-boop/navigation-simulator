from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict

from engine import optimizer
from engine.models import (
    Port,
    ResourceInventory,
    Route,
    Station,
    Vessel,
)


BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR / "data"


def load_json(filename: str):
    """Load a JSON file from the data directory."""

    path = DATA_DIR / filename

    if not path.exists():
        raise FileNotFoundError(
            f"Data file not found: {path}"
        )

    with path.open(
        "r",
        encoding="utf-8",
    ) as file:
        return json.load(file)


def load_ports() -> list[Port]:
    """Load simulated Indian departure ports."""

    data = load_json("ports.json")

    return [
        Port.model_validate(port)
        for port in data
    ]


def load_stations() -> list[Station]:
    """Load Antarctic research stations."""

    data = load_json("stations.json")

    return [
        Station.model_validate(station)
        for station in data
    ]


def load_vessels() -> list[Vessel]:
    """Load simulated vessel profiles."""

    data = load_json("vessels.json")

    return [
        Vessel.model_validate(vessel)
        for vessel in data
    ]


def load_routes() -> list[Route]:
    """Load simulated maritime routes."""

    data = load_json("routes.json")

    return [
        Route.model_validate(route)
        for route in data
    ]


def create_demo_inventory() -> Dict[
    str,
    Dict[str, ResourceInventory],
]:
    """
    Create the demo inventory scenario.

    Inventory is represented as:

        station_id
            -> resource_name
                -> ResourceInventory
    """

    return {
        "S001": {
            "diesel": ResourceInventory(
                resource_name="diesel",
                current_quantity=100_000,
                unit="litres",
                daily_consumption=1_800,
                minimum_safety_threshold=25_000,
                required_resupply_quantity=60_000,
            ),
        },
        "S002": {
            "diesel": ResourceInventory(
                resource_name="diesel",
                current_quantity=90_000,
                unit="litres",
                daily_consumption=1_500,
                minimum_safety_threshold=25_000,
                required_resupply_quantity=50_000,
            ),
        },
    }


def print_option(
    option,
    rank: int | None = None,
) -> None:
    """Print a single voyage option."""

    if rank is not None:
        print(f"\n--- Option {rank} ---")

    print(
        f"Vessel: "
        f"{option.vessel.name} "
        f"({option.vessel.id})"
    )

    print(
        f"Route: "
        f"{option.route.name} "
        f"({option.route.id})"
    )

    print(
        f"Departure port: "
        f"{option.origin_port.name}"
    )

    print(
        f"Destination: "
        f"{option.destination_station.name}"
    )

    print(
        f"Departure: "
        f"{option.departure.isoformat()}"
    )

    print(
        f"Arrival: "
        f"{option.arrival.isoformat()}"
    )

    print(
        f"Distance: "
        f"{option.distance_km:,.1f} km "
        f"({option.distance_nm:,.1f} NM)"
    )

    print(
        f"Voyage duration: "
        f"{option.voyage_duration_days:.2f} days"
    )

    print(
        f"Fuel required: "
        f"{option.fuel_required_litres:,.0f} L"
    )

    print(
        f"Fuel cost: "
        f"{option.fuel_cost:,.2f}"
    )

    print(
        f"Operating cost: "
        f"{option.operating_cost:,.2f}"
    )

    print(
        f"Total cost: "
        f"{option.total_cost:,.2f}"
    )

    print(
        f"Cost per tonne: "
        f"{option.cost_per_tonne:,.2f}"
    )

    print(
        f"Safety margin: "
        f"{option.safety_margin_days:.2f} days"
    )

    print(
        f"Feasible: "
        f"{'YES' if option.feasible else 'NO'}"
    )

    if option.rejection_reason:
        print(
            f"Rejection reason: "
            f"{option.rejection_reason}"
        )


def print_infeasible_summary(
    options,
) -> None:
    """Print a compact summary of rejected candidates."""

    if not options:
        return

    print("\n" + "=" * 60)
    print("INFEASIBLE CANDIDATES")
    print("=" * 60)

    for option in options:
        print(
            f"- {option.vessel.name} | "
            f"{option.route.name} | "
            f"{option.departure.isoformat()} | "
            f"{option.rejection_reason}"
        )


def main() -> None:
    """Run the Antarctic resupply optimization demo."""

    print("=" * 60)
    print("ANTARCTIC MARITIME RESUPPLY OPTIMIZER")
    print("=" * 60)

    # ---------------------------------------------------------
    # Load scenario data
    # ---------------------------------------------------------

    print("\nLoading simulation data...")

    ports = load_ports()
    stations = load_stations()
    vessels = load_vessels()
    routes = load_routes()

    print(f"Ports loaded: {len(ports)}")
    print(f"Stations loaded: {len(stations)}")
    print(f"Vessels loaded: {len(vessels)}")
    print(f"Routes loaded: {len(routes)}")

    # ---------------------------------------------------------
    # Select station
    # ---------------------------------------------------------

    station = next(
        (
            station
            for station in stations
            if station.name.lower() == "maitri"
        ),
        None,
    )

    if station is None:
        raise RuntimeError(
            "Maitri station was not found in stations.json"
        )

    print(
        f"\nTarget station: "
        f"{station.name} ({station.id})"
    )

    # ---------------------------------------------------------
    # Create inventory scenario
    # ---------------------------------------------------------

    station_inventory = create_demo_inventory()

    if station.id not in station_inventory:
        raise RuntimeError(
            f"No inventory scenario configured for "
            f"station {station.id}"
        )

    # ---------------------------------------------------------
    # Simulation dates
    # ---------------------------------------------------------

    current_datetime = datetime(
        2026,
        10,
        1,
        0,
        0,
        0,
        tzinfo=timezone.utc,
    )

    departure_dates = [
        datetime(
            2026,
            11,
            15,
            0,
            0,
            0,
            tzinfo=timezone.utc,
        ),
        datetime(
            2026,
            12,
            1,
            0,
            0,
            0,
            tzinfo=timezone.utc,
        ),
        datetime(
            2026,
            12,
            15,
            0,
            0,
            0,
            tzinfo=timezone.utc,
        ),
        datetime(
            2027,
            1,
            1,
            0,
            0,
            0,
            tzinfo=timezone.utc,
        ),
    ]

    # ---------------------------------------------------------
    # Cargo requirement
    # ---------------------------------------------------------

    cargo_weight_tonnes = 1_500.0

    safety_buffer_days = 3.0

    # ---------------------------------------------------------
    # Run optimizer
    # ---------------------------------------------------------

    print("\nRunning voyage optimization...")

    result = optimizer.optimize_resupply(
        ports=ports,
        stations=[station],
        vessels=vessels,
        routes=routes,
        departure_dates=departure_dates,
        cargo_weight_tonnes=cargo_weight_tonnes,
        station_inventory=station_inventory,
        safety_buffer_days=safety_buffer_days,
        current_datetime=current_datetime,
        max_alternatives=3,
    )

    # ---------------------------------------------------------
    # Result
    # ---------------------------------------------------------

    print("\n" + "=" * 60)
    print("OPTIMIZATION RESULT")
    print("=" * 60)

    print(f"Status: {result.status}")
    print(f"Message: {result.message}")

    if result.best_option is None:
        print(
            "\nNo feasible resupply plan was found."
        )

        print_infeasible_summary(
            result.infeasible_options
        )

        return

    # ---------------------------------------------------------
    # Recommended plan
    # ---------------------------------------------------------

    print("\n" + "=" * 60)
    print("RECOMMENDED RESUPPLY PLAN")
    print("=" * 60)

    print_option(
        result.best_option
    )

    # ---------------------------------------------------------
    # Alternatives
    # ---------------------------------------------------------

    if result.alternatives:
        print("\n" + "=" * 60)
        print("ALTERNATIVE PLANS")
        print("=" * 60)

        for index, option in enumerate(
            result.alternatives,
            start=1,
        ):
            print_option(
                option,
                rank=index,
            )

    # ---------------------------------------------------------
    # Infeasible candidates
    # ---------------------------------------------------------

    print_infeasible_summary(
        result.infeasible_options
    )

    # ---------------------------------------------------------
    # Completion
    # ---------------------------------------------------------

    print("\n" + "=" * 60)
    print("SIMULATION OPTIMIZATION COMPLETE")
    print("=" * 60)


if __name__ == "__main__":
    main()