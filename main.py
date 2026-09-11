# -*- coding: utf-8 -*-
"""
main.py
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Command‑line demonstration for the Antarctic maritime resupply simulator.

The script performs a full end‑to‑end run using the pure‑function modules in
``engine/`` and the data files under ``data/``.  It:

1. Loads ports, stations, vessels, and routes from JSON.
2. Sets up a simple diesel inventory scenario for the Maitri station.
3. Calculates the critical inventory date, latest safe arrival, and latest safe
   departure for each candidate voyage.
4. Uses ``engine.optimizer.optimize_resupply`` to evaluate every vessel/route
   combination.
5. Separates feasible and infeasible options, prints them, and highlights the
   best plan together with up to three alternatives.

All calculations are deterministic and rely only on the internal modules – no
external APIs, no Google Maps, no frontend code.
"""

import json
import sys
from datetime import datetime, timezone, timedelta
from decimal import Decimal
from pathlib import Path
from typing import List

# --------------------------------------------------------------------- #
# Engine imports (pure calculation utilities)
# --------------------------------------------------------------------- #
from engine import (
    distance as distance_mod,
    voyage as voyage_mod,
    fuel as fuel_mod,
    cost as cost_mod,
    inventory as inventory_mod,
    deadline as deadline_mod,
    optimizer as optimizer_mod,
    models as models_mod,
)

# --------------------------------------------------------------------- #
# Helper functions
# --------------------------------------------------------------------- #
def _load_json(file_path: Path) -> List[dict]:
    """Read a JSON file and return the decoded list of dictionaries."""
    if not file_path.is_file():
        raise FileNotFoundError(f"Required data file not found: {file_path}")
    with file_path.open("r", encoding="utf-8") as f:
        return json.load(f)


def _pretty_print_header(title: str) -> None:
    line = "=" * 50
    print(f"\n{line}\n{title}\n{line}\n")


def _format_currency(value: Decimal) -> str:
    return f"{value:.2f}"


def _format_number(value: float) -> str:
    return f"{value:,.2f}"


# --------------------------------------------------------------------- #
# Main demonstration logic
# --------------------------------------------------------------------- #
def main() -> int:
    # -----------------------------------------------------------------
    # 1. Load all data files
    # -----------------------------------------------------------------
    data_dir = Path(__file__).parent / "data"
    ports_data = _load_json(data_dir / "ports.json")
    stations_data = _load_json(data_dir / "stations.json")
    vessels_data = _load_json(data_dir / "vessels.json")
    routes_data = _load_json(data_dir / "routes.json")

    ports = [models_mod.Port(**p) for p in ports_data]
    stations = [models_mod.Station(**s) for s in stations_data]
    vessels = [models_mod.Vessel(**v) for v in vessels_data]
    routes = [models_mod.Route(**r) for r in routes_data]

    # -----------------------------------------------------------------
    # 2. Pick the destination station (Maitri) and set up the diesel scenario
    # -----------------------------------------------------------------
    destination_station = next(s for s in stations if s.name.lower() == "maitri")
    simulation_start = datetime(2026, 10, 1, 0, 0, tzinfo=timezone.utc)

    # Diesel resource inventory (simulated values as per the brief)
    diesel_inventory = inventory_mod.ResourceInventory(
        resource_name="Diesel",
        current_quantity=100_000.0,
        unit="L",
        daily_consumption=1_800.0,
        minimum_safety_threshold=25_000.0,
        required_resupply_quantity=60_000.0,
    )

    # -----------------------------------------------------------------
    # 3. Calculate critical date, latest safe arrival, and latest safe departure
    # -----------------------------------------------------------------
    days_until_critical = inventory_mod.calculate_days_until_threshold(
        current_quantity=diesel_inventory.current_quantity,
        daily_consumption=diesel_inventory.daily_consumption,
        safety_threshold=diesel_inventory.minimum_safety_threshold,
    )
    critical_date = simulation_start + timedelta(days=days_until_critical)

    latest_safe_arrival = deadline_mod.calculate_latest_safe_arrival(
        critical_date, safety_buffer_days=2
    )
    # The latest safe departure will be computed per candidate voyage later.

    # -----------------------------------------------------------------
    # 4. Prepare departure candidate datetimes (we try a window of 5 days)
    # -----------------------------------------------------------------
    candidate_departures = [
        simulation_start + timedelta(days=offset) for offset in range(0, 6)
    ]

    # -----------------------------------------------------------------
    # 5. Run the optimiser (it evaluates all vessel/route/departure combos)
    # -----------------------------------------------------------------
    optimisation_result = optimizer_mod.optimize_resupply(
        vessels=vessels,
        routes=routes,
        ports=ports,
        stations=stations,
        departure_dates_utc=candidate_departures,
        cargo_weight_tonnes=diesel_inventory.required_resupply_quantity / 1_000,  # 1t ≈ 1000L
        fuel_cost_per_litre=Decimal("1.0"),  # deterministic price for demo
    )

    # -----------------------------------------------------------------
    # 6. Separate feasible and infeasible options for reporting
    # -----------------------------------------------------------------
    feasible: List[optimizer_mod.VoyageOption] = []
    infeasible: List[optimizer_mod.VoyageOption] = []

    for opt in [optimisation_result.best_option, *optimisation_result.alternatives]:
        if opt is None:
            continue
        if opt.feasible:
            feasible.append(opt)
        else:
            infeasible.append(opt)

    # -----------------------------------------------------------------
    # 7. Output formatted report
    # -----------------------------------------------------------------
    _pretty_print_header("ANTARCTIC RESUPPLY NAVIGATION SIMULATOR")

    # ----- Destination & Resource Summary -----
    print("DESTINATION".ljust(20) + destination_station.name)
    print("RESOURCE".ljust(20) + "Diesel")
    print("\nCURRENT INVENTORY".ljust(20) + f"{_format_number(diesel_inventory.current_quantity)} L")
    print("DAILY CONSUMPTION".ljust(20) + f"{_format_number(diesel_inventory.daily_consumption)} L/day")
    print("SAFETY RESERVE".ljust(20) + f"{_format_number(diesel_inventory.minimum_safety_threshold)} L")
    print("\nCRITICAL DATE".ljust(20) + critical_date.isoformat())
    print("LATEST SAFE ARRIVAL".ljust(20) + latest_safe_arrival.isoformat())
    print("\nNOTE: SIMULATED DATA — NOT LIVE MARITIME DATA\n")

    # ----- Candidate Voyages -----
    print("-" * 50)
    print("CANDIDATE VOYAGES".center(50))
    print("-" * 50)

    if not feasible:
        print("\nNo feasible voyages were found for the given parameters.\n")
    else:
        for idx, opt in enumerate(feasible, start=1):
            print(f"\nOption {idx}:")
            print(f"  Vessel                : {opt.vessel.name} (id={opt.vessel.id})")
            print(f"  Route                 : {opt.route.name} (id={opt.route.id})")
            print(f"  Departure (UTC)       : {opt.departure.isoformat()}")
            print(f"  Arrival (UTC)         : {opt.arrival.isoformat()}")
            print(f"  Voyage duration (days): {_format_number(opt.voyage_duration)}")
            print(f"  Fuel required (L)     : {_format_number(opt.fuel_required)}")
            print(f"  Fuel cost             : {_format_currency(opt.fuel_cost)}")
            print(f"  Operating cost (day)  : {_format_currency(opt.operating_cost)}")
            print(f"  Total cost            : {_format_currency(opt.total_cost)}")
            print(f"  Safety margin (days)  : {_format_number(opt.safety_margin)}")
            print(f"  Status                : {'FEASIBLE' if opt.feasible else 'INFEASIBLE'}")
            if opt.rejection_reason:
                print(f"  Reason                : {opt.rejection_reason}")

    # ----- Infeasible Options -----
    if infeasible:
        print("\n" + "-" * 50)
        print("INFEASIBLE OPTIONS".center(50))
        print("-" * 50)
        for idx, opt in enumerate(infeasible, start=1):
            print(f"\nOption {idx}:")
            print(f"  Vessel                : {opt.vessel.name} (id={opt.vessel.id})")
            print(f"  Route                 : {opt.route.name} (id={opt.route.id})")
            print(f"  Departure (UTC)       : {opt.departure.isoformat()}")
            print(f"  Arrival (UTC)         : {opt.arrival.isoformat()}")
            print(f"  Reason                : {opt.rejection_reason}")

    # ----- Recommended Plan -----
    if optimisation_result.best_option and optimisation_result.best_option.feasible:
        best = optimisation_result.best_option
        print("\n" + "-" * 50)
        print("RECOMMENDED PLAN".center(50))
        print("-" * 50)
        print(f"Vessel               : {best.vessel.name} ({best.vessel.id})")
        print(f"Route                : {best.route.name} ({best.route.id})")
        print(f"Departure            : {best.departure.isoformat()}")
        print(f"Arrival              : {best.arrival.isoformat()}")
        print(f"Voyage duration (days): {_format_number(best.voyage_duration)}")
        print(f"Fuel required (L)    : {_format_number(best.fuel_required)}")
        print(f"Fuel cost            : {_format_currency(best.fuel_cost)}")
        print(f"Operating cost (day) : {_format_currency(best.operating_cost)}")
        print(f"Total cost           : {_format_currency(best.total_cost)}")
        print(f"Safety margin (days) : {_format_number(best.safety_margin)}")
        print("\nReason for selection: Lowest total cost among feasible options with a positive safety margin.")
    else:
        print("\nNo feasible plan could be identified.\n")

    return 0


if __name__ == "__main__":
    sys.exit(main())