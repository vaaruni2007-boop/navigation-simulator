"""engine.optimizer
===================

Core optimisation routine for the Antarctic Maritime Resupply Navigation Simulator.

The optimiser combines the pure-utility modules:

* ``engine.distance`` – great‑circle distance calculations
* ``engine.voyage``  – duration / ETA helpers
* ``engine.fuel``    – fuel consumption & cost
* ``engine.cost``    – operating‑cost & total‑cost helpers
* ``engine.inventory`` – station inventory forecasts
* ``engine.deadline`` – deadline and feasibility helpers

It **does not** contain any domain‑specific heuristics beyond the scoring
rules described in the docstring of ``optimize_resupply``.  All calculations are
performed by the imported utility modules – no duplicated logic.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone, timedelta
from decimal import Decimal
from typing import List, Optional, Dict, Tuple, Any

# ---------------------------------------------------------------------------
# Imported utility modules
# ---------------------------------------------------------------------------
from .distance import Waypoint, calculate_route_distance_km
from .voyage import calculate_voyage_days, calculate_eta
from .fuel import (
    calculate_fuel_consumption,
    calculate_fuel_cost,
    validate_fuel_capacity,
)
from .cost import (
    calculate_operating_cost,
    calculate_total_cost,
)
from .deadline import (
    calculate_latest_safe_arrival,
    calculate_safety_margin_days,
    is_arrival_feasible,
)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
_KM_TO_NM: float = 1.0 / 1.852  # 1 km = 0.5399568 nautical miles


# ---------------------------------------------------------------------------
# Data models
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class VoyageOption:
    """A single evaluated resupply plan."""

    vessel: Dict[str, Any]                 # raw vessel record (as loaded from JSON)
    route: Dict[str, Any]                  # raw route record
    departure: datetime                    # UTC, timezone‑aware
    arrival: datetime                      # UTC, timezone‑aware
    distance_nm: float                     # nautical miles (derived)
    voyage_duration_days: float            # days (derived)
    fuel_required_l: float                 # litres (derived)
    fuel_cost: Decimal                     # monetary (derived)
    operating_cost: Decimal                # monetary (derived)
    total_cost: Decimal                    # monetary (derived)
    remaining_inventory: Dict[str, float]  # resource name → quantity at arrival
    safety_margin_days: float              # days (positive = early)
    feasible: bool                         # overall feasibility
    rejection_reason: Optional[str] = None # populated when not feasible


@dataclass
class OptimizationResult:
    """Result object returned by the optimiser."""

    status: str                                            # "SUCCESS", "NO_FEASIBLE_PLAN"
    best_option: Optional[VoyageOption] = None
    alternatives: List[VoyageOption] = field(default_factory=list)
    notes: Optional[str] = None                            # human‑readable explanation


# ---------------------------------------------------------------------------
# Helper functions
# ---------------------------------------------------------------------------

def _waypoints_to_objects(wp_dicts: List[Dict[str, float]]) -> List[Waypoint]:
    """Convert a list of ``{'latitude':…, 'longitude':…}`` dicts to ``Waypoint`` objects."""
    return [Waypoint(latitude=w["latitude"], longitude=w["longitude"]) for w in wp_dicts]


def _km_to_nm(km: float) -> float:
    """Convert kilometres to nautical miles."""
    return km * _KM_TO_NM


def _score_option(opt: VoyageOption) -> Tuple[int, float, Decimal, float, float]:
    """
    Produce a sortable score tuple.

    The tuple is ordered to reflect optimisation priority:

    1. feasibility (1 = feasible, 0 = not) – higher is better.
    2. safety margin (larger positive is better).
    3. total cost (lower is better).
    4. fuel required (lower is better).
    5. voyage duration (lower is better).

    ``None`` values are never present for feasible options; infeasible options
    are given a score that pushes them to the end of any sorted list.
    """
    feasible_flag = 1 if opt.feasible else 0
    # For infeasible options we return a tuple that will sort after any feasible
    if not opt.feasible:
        return (0, float("-inf"), Decimal("Infinity"), float("Infinity"), float("Infinity"))
    return (
        feasible_flag,
        opt.safety_margin_days,
        opt.total_cost,
        opt.fuel_required_l,
        opt.voyage_duration_days,
    )


# ---------------------------------------------------------------------------
# Core optimisation routine
# ---------------------------------------------------------------------------

def optimize_resupply(
    *,
    vessels: List[Dict[str, Any]],
    routes: List[Dict[str, Any]],
    departure_dates: List[datetime],
    cargo_weight_tonnes: float,
    station_inventory: Dict[str, Any],
    safety_buffer_days: float,
    current_datetime: Optional[datetime] = None,
) -> OptimizationResult:
    """
    Evaluate all plausible combinations of vessels, routes and departure dates
    and return the optimal feasible plan together with up to three alternative
    feasible plans.

    Parameters
    ----------
    vessels
        List of vessel dictionaries (as defined in ``data/vessels.json``).
    routes
        List of route dictionaries (as defined in ``data/routes.json``).  Each
        route must contain a ``waypoints`` key with a list of ``{'latitude',
        'longitude'}`` dicts.
    departure_dates
        Candidate departure datetimes (UTC, timezone‑aware).  The optimiser will
        treat each as a possible leave‑time.
    cargo_weight_tonnes
        Amount of cargo to be delivered (tonnes).  Must fit within the vessel's
        ``cargo_capacity_tonnes``.
    station_inventory
        Mapping ``station_id -> ResourceInventory`` (already instantiated).
        The optimiser uses the *diesel* resource to compute the critical date.
    safety_buffer_days
        Desired safety buffer before the station reaches its critical inventory
        date.
    current_datetime
        Optional “now” timestamp; defaults to ``datetime.now(timezone.utc)``.
        Used for inventory projection.

    Returns
    -------
    OptimizationResult
        Contains the best feasible plan (if any) and up to three alternative
        feasible plans.
    """
    if current_datetime is None:
        current_datetime = datetime.now(timezone.utc)

    evaluated_options: List[VoyageOption] = []

    # -------------------------------------------------------------------
    # Exhaustive evaluation loop
    # -------------------------------------------------------------------
    for vessel in vessels:
        # Extract vessel parameters once for readability
        max_speed = vessel["maximum_speed_knots"]
        fuel_capacity = vessel["fuel_capacity_litres"]
        fuel_consumption_per_day = vessel["fuel_consumption_litres_per_day"]
        cargo_capacity = vessel["cargo_capacity_tonnes"]
        operating_cost_per_day = vessel["operating_cost_per_day"]
        fuel_cost_per_litre = vessel["fuel_cost_per_litre"]

        for route in routes:
            # Pre‑compute route distance (km → NM) using the waypoint geometry
            try:
                wp_objs = _waypoints_to_objects(route["waypoints"])
                route_distance_km = calculate_route_distance_km(wp_objs)
                route_distance_nm = _km_to_nm(route_distance_km)
            except Exception as exc:
                # If the geometry is malformed we cannot use this route.
                continue

            for dep in departure_dates:
                # ----- Voyage duration & ETA -----
                voyage_days = calculate_voyage_days(route_distance_nm, max_speed)
                arrival = calculate_eta(dep, route_distance_nm, max_speed)

                # ----- Inventory & safety checks -----
                # Determine which station we are heading to
                station_id = route["destination_station_id"]
                inventory_obj = station_inventory.get(station_id)
                if inventory_obj is None:
                    # Missing inventory information – cannot evaluate safely.
                    continue

                # Critical date for the station (when safety threshold is hit)
                critical_dt = inventory_obj.calculate_critical_date(current_datetime)
                if critical_dt is None:
                    # No depletion (zero daily consumption); treat as always safe.
                    latest_safe_arrival = arrival  # any arrival is acceptable
                else:
                    latest_safe_arrival = calculate_latest_safe_arrival(
                        critical_dt, safety_buffer_days
                    )

                # Feasibility flag and rejection reason tracking
                feasible = True
                rejection_reason = None

                # 1. Arrival must be on or before latest safe arrival
                if not is_arrival_feasible(arrival, latest_safe_arrival):
                    feasible = False
                    rejection_reason = "arrival after safety deadline"

                # 2. Vessel must have enough fuel for the voyage
                fuel_needed = calculate_fuel_consumption(voyage_days, fuel_consumption_per_day)
                if not validate_fuel_capacity(fuel_needed, fuel_capacity):
                    feasible = False
                    rejection_reason = (
                        rejection_reason or "insufficient fuel capacity"
                    )
                # 3. Vessel cargo capacity must accommodate the cargo weight
                if cargo_weight_tonnes > cargo_capacity:
                    feasible = False
                    rejection_reason = (
                        rejection_reason or "cargo exceeds vessel capacity"
                    )

                # ----- Cost calculations (performed regardless of feasibility) -----
                fuel_cost = calculate_fuel_cost(Decimal(str(fuel_needed)), Decimal(str(fuel_cost_per_litre)))
                operating_cost = calculate_operating_cost(voyage_days, Decimal(str(operating_cost_per_day)))
                total_cost = calculate_total_cost(fuel_cost, operating_cost)

                # ----- Inventory projection (only meaningful if we have a valid inventory object) -----
                remaining_inventory: Dict[str, float] = {}
                if critical_dt is not None:
                    # Project each resource's quantity at arrival time
                    for res_name, res_obj in inventory_obj.items():  # type: ignore[attr-defined]
                        # ``ResourceInventory`` instances are stored per‑resource.
                        # The caller should provide a mapping of resource name →
                        # ResourceInventory.  Here we handle that generic case.
                        projected_qty = res_obj.calculate_inventory_on_date(
                            current_datetime, arrival
                        )
                        remaining_inventory[res_name] = projected_qty

                # ----- Safety margin -----
                safety_margin = calculate_safety_margin_days(latest_safe_arrival, arrival)

                # Build the option record
                option = VoyageOption(
                    vessel=vessel,
                    route=route,
                    departure=dep,
                    arrival=arrival,
                    distance_nm=route_distance_nm,
                    voyage_duration_days=voyage_days,
                    fuel_required_l=fuel_needed,
                    fuel_cost=fuel_cost,
                    operating_cost=operating_cost,
                    total_cost=total_cost,
                    remaining_inventory=remaining_inventory,
                    safety_margin_days=safety_margin,
                    feasible=feasible,
                    rejection_reason=rejection_reason,
                )
                evaluated_options.append(option)

    # -------------------------------------------------------------------
    # Ranking & selection
    # -------------------------------------------------------------------
    if not evaluated_options:
        return OptimizationResult(
            status="NO_FEASIBLE_PLAN",
            notes="No options could be evaluated (possible data issues).",
        )

    # Sort by the scoring tuple (higher is better for the first three items, lower for costs)
    sorted_opts = sorted(
        evaluated_options,
        key=_score_option,
        reverse=True,  # we want highest feasibility & safety margin first
    )

    # Extract feasible options
    feasible_opts = [opt for opt in sorted_opts if opt.feasible]

    if not feasible_opts:
        # All options were infeasible; return the most informative rejection reason
        # (pick the first infeasible option after sorting)
        reason = feasible_opts[0].rejection_reason if feasible_opts else "unknown"
        return OptimizationResult(
            status="NO_FEASIBLE_PLAN",
            notes=f"All evaluated options are infeasible. Example reason: {reason}",
        )

    best = feasible_opts[0]
    alternatives = feasible_opts[1:4]  # up to three alternatives

    return OptimizationResult(
        status="SUCCESS",
        best_option=best,
        alternatives=alternatives,
        notes=f"{len(feasible_opts)} feasible options evaluated.",
    )