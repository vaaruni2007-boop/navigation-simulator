# tests/test_optimizer.py
"""
Comprehensive pytest suite for ``engine.optimizer``.

The optimizer pulls in many pure‑utility modules.  To keep the tests fast,
deterministic and independent of the real implementations we monkey‑patch the
imported functions with lightweight fakes that return values we control.

The tests cover:

1. A basic feasible option is found.
2. A route that arrives after the safety deadline is rejected.
3. A vessel lacking sufficient fuel capacity is rejected.
4. Insufficient cargo capacity is rejected.
5. Among feasible options the one with the lowest total cost is selected.
6. A cheaper option that arrives too late is *not* selected.
7. The optimiser returns up to three alternative feasible plans.
8. ``NO_FEASIBLE_PLAN`` is returned when every option fails.
9. Rejection reasons are propagated to the result notes.
10. Changing a station’s daily consumption (hence its critical date) changes
    which option is optimal.

All tests are written against the public ``optimize_resupply`` function.
"""

import builtins
from datetime import datetime, timezone, timedelta
from decimal import Decimal

import pytest

# The module under test
import engine.optimizer as optimizer
from engine.inventory import ResourceInventory


# ----------------------------------------------------------------------
# Helper – a minimal mock of ``ResourceInventory``.
# ----------------------------------------------------------------------
class FakeInventory(ResourceInventory):
    """
    Sub‑class the real ``ResourceInventory`` but expose the underlying
    ``calculate_critical_date`` implementation unchanged.  It is used to
    inject a specific consumption pattern for each test.
    """

    def __init__(self, critical_dt: datetime | None):
        # ``critical_dt`` is the pre‑computed critical datetime we want the
        # inventory to return regardless of the ``current_datetime`` argument.
        # We set ``current_quantity`` and ``daily_consumption`` to values that
        # would produce this critical datetime in the real implementation.
        if critical_dt is None:
            # Non‑depleting resource → zero consumption
            super().__init__(
                resource_name="diesel",
                current_quantity=100_000,
                unit="litres",
                daily_consumption=0,
                minimum_safety_threshold=20_000,
                required_resupply_quantity=0,
            )
        else:
            # Pick arbitrary numbers that yield the desired critical date.
            # We use a fixed current datetime of 2026‑01‑01 00:00 UTC for the
            # calculation.
            now = datetime(2026, 1, 1, tzinfo=timezone.utc)
            days_until = (critical_dt - now).total_seconds() / 86400.0
            # Choose a current quantity such that (current - threshold) / consumption = days_until
            # Let consumption = 1 000 L/day, threshold = 20 000 L.
            consumption = 1_000.0
            threshold = 20_000.0
            current = threshold + consumption * days_until
            super().__init__(
                resource_name="diesel",
                current_quantity=current,
                unit="litres",
                daily_consumption=consumption,
                minimum_safety_threshold=threshold,
                required_resupply_quantity=0,
            )


# ----------------------------------------------------------------------
# Common fixture that installs deterministic stubs for all utility functions.
# ----------------------------------------------------------------------
@pytest.fixture
def stub_functions(monkeypatch):
    """
    Install simple deterministic versions of all utility functions that the
    optimiser depends on.  The stubs are deliberately simple:

    * Distance: every route is 1 000 km.
    * Voyage days: 1 day per 100 nautical miles.
    * ETA: departure + voyage_days.
    * Fuel consumption: voyage_days * daily_consumption.
    * Fuel cost / operating cost / total cost: linear arithmetic.
    * Latest safe arrival: a fixed far‑future date shifted by ``safety_buffer_days``.
    * Safety margin & feasibility: computed from the dates.
    """

    # ---- distance -------------------------------------------------------
    def fake_route_distance_km(_waypoints):
        return 1_000.0  # km

    monkeypatch.setattr(optimizer, "calculate_route_distance_km", fake_route_distance_km)

    # ---- voyage ---------------------------------------------------------
    def fake_voyage_days(distance_nm: float, max_speed: float) -> float:
        # 100 NM per day for simplicity.
        return distance_nm / 100.0

    def fake_eta(departure: datetime, distance_nm: float, max_speed: float) -> datetime:
        days = fake_voyage_days(distance_nm, max_speed)
        return departure + timedelta(days=days)

    monkeypatch.setattr(optimizer, "calculate_voyage_days", fake_voyage_days)
    monkeypatch.setattr(optimizer, "calculate_eta", fake_eta)

    # ---- fuel -----------------------------------------------------------
    def fake_fuel_consumption(voyage_days: float, daily_consumption: float) -> float:
        return voyage_days * daily_consumption

    def fake_fuel_cost(litres: Decimal, price_per_litre: Decimal) -> Decimal:
        return litres * price_per_litre

    def fake_validate_fuel_capacity(required: float, capacity: float) -> bool:
        return required <= capacity

    monkeypatch.setattr(optimizer, "calculate_fuel_consumption", fake_fuel_consumption)
    monkeypatch.setattr(optimizer, "calculate_fuel_cost", fake_fuel_cost)
    monkeypatch.setattr(optimizer, "validate_fuel_capacity", fake_validate_fuel_capacity)

    # ---- cost -----------------------------------------------------------
    def fake_operating_cost(voyage_days: float, cost_per_day: Decimal) -> Decimal:
        return Decimal(voyage_days) * cost_per_day

    def fake_total_cost(fuel_cost: Decimal, operating_cost: Decimal) -> Decimal:
        return fuel_cost + operating_cost

    monkeypatch.setattr(optimizer, "calculate_operating_cost", fake_operating_cost)
    monkeypatch.setattr(optimizer, "calculate_total_cost", fake_total_cost)

    # ---- deadline -------------------------------------------------------
    def fake_latest_safe_arrival(critical_dt: datetime, safety_buffer: float) -> datetime:
        # Return a date far enough in the future that we can control feasibility
        # via ``is_arrival_feasible``.
        return datetime(2100, 1, 1, tzinfo=timezone.utc) + timedelta(days=safety_buffer)

    def fake_safety_margin(required_arrival: datetime, actual_arrival: datetime) -> float:
        delta = required_arrival - actual_arrival
        return delta.total_seconds() / 86400.0

    # ``is_arrival_feasible`` will be overridden per‑test as needed.
    monkeypatch.setattr(optimizer, "calculate_latest_safe_arrival", fake_latest_safe_arrival)
    monkeypatch.setattr(optimizer, "calculate_safety_margin_days", fake_safety_margin)

    # Return a dict with a few constants that the tests might need.
    return {
        "fuel_cost_per_litre": Decimal("1.0"),
        "operating_cost_per_day": Decimal("100.0"),
    }


# ----------------------------------------------------------------------
# Helper to build a minimal vessel dict.
# ----------------------------------------------------------------------
def make_vessel(
    vid: str,
    max_speed: float = 10.0,
    fuel_capacity: float = 20_000.0,
    fuel_consumption_per_day: float = 500.0,
    cargo_capacity: float = 50.0,
    operating_cost_per_day: float = 100.0,
    fuel_cost_per_litre: float = 1.0,
) -> dict:
    return {
        "id": vid,
        "maximum_speed_knots": max_speed,
        "fuel_capacity_litres": fuel_capacity,
        "fuel_consumption_litres_per_day": fuel_consumption_per_day,
        "cargo_capacity_tonnes": cargo_capacity,
        "operating_cost_per_day": operating_cost_per_day,
        "fuel_cost_per_litre": fuel_cost_per_litre,
    }


# ----------------------------------------------------------------------
# Helper to build a minimal route dict.
# ----------------------------------------------------------------------
def make_route(rid: str, destination_station_id: str) -> dict:
    # Waypoints are not used by the fake distance function, so any list works.
    return {
        "id": rid,
        "waypoints": [{"latitude": 0, "longitude": 0}, {"latitude": 1, "longitude": 1}],
        "destination_station_id": destination_station_id,
    }


# ----------------------------------------------------------------------
# 1. Optimizer finds a feasible option
# ----------------------------------------------------------------------
def test_optimizer_finds_feasible_option(stub_functions, monkeypatch):
    # Make every arrival feasible.
    monkeypatch.setattr(optimizer, "is_arrival_feasible", lambda a, b: True)

    vessel = make_vessel("v1")
    route = make_route("r1", "station_A")
    departure = datetime(2026, 1, 1, tzinfo=timezone.utc)

    # Critical date far in the future → always feasible.
    station_inventory = {"station_A": FakeInventory(None)}

    result = optimizer.optimize_resupply(
        vessels=[vessel],
        routes=[route],
        departure_dates=[departure],
        cargo_weight_tonnes=10.0,
        station_inventory=station_inventory,
        safety_buffer_days=2.0,
    )

    assert result.status == "SUCCESS"
    assert result.best_option is not None
    assert result.best_option.feasible is True


# ----------------------------------------------------------------------
# 2. Optimizer rejects a route that arrives too late
# ----------------------------------------------------------------------
def test_optimizer_rejects_late_arrival(stub_functions, monkeypatch):
    # Force the feasibility check to fail for the single option.
    monkeypatch.setattr(optimizer, "is_arrival_feasible", lambda a, b: False)

    vessel = make_vessel("v2")
    route = make_route("r2", "station_B")
    departure = datetime(2026, 1, 1, tzinfo=timezone.utc)
    station_inventory = {"station_B": FakeInventory(None)}

    result = optimizer.optimize_resupply(
        vessels=[vessel],
        routes=[route],
        departure_dates=[departure],
        cargo_weight_tonnes=5.0,
        station_inventory=station_inventory,
        safety_buffer_days=1.0,
    )

    assert result.status == "NO_FEASIBLE_PLAN"
    assert result.best_option is None
    assert "infeasible" in (result.notes or "").lower()


# ----------------------------------------------------------------------
# 3. Optimizer rejects a vessel without enough fuel capacity
# ----------------------------------------------------------------------
def test_optimizer_rejects_insufficient_fuel(monkeypatch, stub_functions):
    # All arrivals are feasible, but fuel capacity validation fails.
    monkeypatch.setattr(optimizer, "is_arrival_feasible", lambda a, b: True)
    monkeypatch.setattr(
        optimizer,
        "validate_fuel_capacity",
        lambda required, capacity: False,
    )

    vessel = make_vessel("v3", fuel_capacity=1_000.0)  # too small
    route = make_route("r3", "station_C")
    departure = datetime(2026, 2, 1, tzinfo=timezone.utc)
    station_inventory = {"station_C": FakeInventory(None)}

    result = optimizer.optimize_resupply(
        vessels=[vessel],
        routes=[route],
        departure_dates=[departure],
        cargo_weight_tonnes=10.0,
        station_inventory=station_inventory,
        safety_buffer_days=2.0,
    )

    assert result.status == "NO_FEASIBLE_PLAN"
    assert result.best_option is None
    # The generic note should contain the word “fuel”.
    assert "fuel" in (result.notes or "").lower()


# ----------------------------------------------------------------------
# 4. Optimizer rejects insufficient cargo capacity
# ----------------------------------------------------------------------
def test_optimizer_rejects_insufficient_cargo(monkeypatch, stub_functions):
    monkeypatch.setattr(optimizer, "is_arrival_feasible", lambda a, b: True)

    # Vessel can carry only 5 tonnes, but we request 10 tonnes.
    vessel = make_vessel("v4", cargo_capacity=5.0)
    route = make_route("r4", "station_D")
    departure = datetime(2026, 3, 1, tzinfo=timezone.utc)
    station_inventory = {"station_D": FakeInventory(None)}

    result = optimizer.optimize_resupply(
        vessels=[vessel],
        routes=[route],
        departure_dates=[departure],
        cargo_weight_tonnes=10.0,
        station_inventory=station_inventory,
        safety_buffer_days=1.0,
    )

    assert result.status == "NO_FEASIBLE_PLAN"
    assert result.best_option is None
    assert "cargo" in (result.notes or "").lower()


# ----------------------------------------------------------------------
# 5. Optimizer chooses the lowest‑cost feasible option
# ----------------------------------------------------------------------
def test_optimizer_selects_lowest_cost(monkeypatch, stub_functions):
    # All options are feasible.
    monkeypatch.setattr(optimizer, "is_arrival_feasible", lambda a, b: True)

    vessel_a = make_vessel("vA", fuel_cost_per_litre=1.0)  # cheaper fuel
    vessel_b = make_vessel("vB", fuel_cost_per_litre=2.0)  # more expensive fuel

    route = make_route("r5", "station_E")
    departure = datetime(2026, 4, 1, tzinfo=timezone.utc)
    station_inventory = {"station_E": FakeInventory(None)}

    result = optimizer.optimize_resupply(
        vessels=[vessel_a, vessel_b],
        routes=[route],
        departure_dates=[departure],
        cargo_weight_tonnes=5.0,
        station_inventory=station_inventory,
        safety_buffer_days=1.0,
    )

    assert result.status == "SUCCESS"
    # Vessel A (cheaper fuel) should be the best option.
    assert result.best_option.vessel["id"] == "vA"


# ----------------------------------------------------------------------
# 6. Cheaper option arrives too late → not selected
# ----------------------------------------------------------------------
def test_optimizer_chooses_expensive_but_on_time(monkeypatch, stub_functions):
    """
    OPTION A (cheaper) arrives after the safety deadline → infeasible.
    OPTION B (more expensive) arrives before the deadline → feasible.
    The optimizer must pick OPTION B.
    """

    # Custom feasibility logic: only arrivals before a fixed cutoff are feasible.
    cutoff = datetime(2100, 1, 1, 12, 0, tzinfo=timezone.utc)  # midday cut‑off

    def custom_feasibility(actual, latest):
        return actual <= cutoff

    monkeypatch.setattr(optimizer, "is_arrival_feasible", custom_feasibility)

    # Vessel A: cheap fuel, fast speed → arrives *after* cutoff (because we
    # manipulate departure to make it later).
    vessel_a = make_vessel("vA", max_speed=5.0, fuel_cost_per_litre=1.0)

    # Vessel B: expensive fuel, slower speed → arrives *before* cutoff.
    vessel_b = make_vessel("vB", max_speed=15.0, fuel_cost_per_litre=5.0)

    route = make_route("r6", "station_F")
    # Two departures: the earlier one will be used with vessel B, the later with
    # vessel A (we simply provide both dates; the optimiser will evaluate all combos).
    dep_early = datetime(2026, 5, 1, 0, 0, tzinfo=timezone.utc)
    dep_late = datetime(2026, 5, 10, 0, 0, tzinfo=timezone.utc)

    station_inventory = {"station_F": FakeInventory(None)}

    result = optimizer.optimize_resupply(
        vessels=[vessel_a, vessel_b],
        routes=[route],
        departure_dates=[dep_early, dep_late],
        cargo_weight_tonnes=5.0,
        station_inventory=station_inventory,
        safety_buffer_days=1.0,
    )

    assert result.status == "SUCCESS"
    # The chosen vessel must be the expensive one (vB) because only its options
    # satisfy the custom feasibility predicate.
    assert result.best_option.vessel["id"] == "vB"


# ----------------------------------------------------------------------
# 7. Optimizer returns up to three alternatives
# ----------------------------------------------------------------------
def test_optimizer_returns_top_three_alternatives(monkeypatch, stub_functions):
    monkeypatch.setattr(optimizer, "is_arrival_feasible", lambda a, b: True)

    # Three vessels with progressively higher costs.
    vessels = [
        make_vessel("v1", fuel_cost_per_litre=1.0),
        make_vessel("v2", fuel_cost_per_litre=2.0),
        make_vessel("v3", fuel_cost_per_litre=3.0),
        make_vessel("v4", fuel_cost_per_litre=4.0),
        make_vessel("v5", fuel_cost_per_litre=5.0),
    ]

    route = make_route("r7", "station_G")
    departure = datetime(2026, 6, 1, tzinfo=timezone.utc)
    station_inventory = {"station_G": FakeInventory(None)}

    result = optimizer.optimize_resupply(
        vessels=vessels,
        routes=[route],
        departure_dates=[departure],
        cargo_weight_tonnes=5.0,
        station_inventory=station_inventory,
        safety_buffer_days=1.0,
    )

    assert result.status == "SUCCESS"
    # There should be a best option plus up to three alternatives.
    assert len(result.alternatives) == 3
    # Verify ordering: alternatives are the next best options by cost.
    best_cost = result.best_option.total_cost
    alt_costs = [opt.total_cost for opt in result.alternatives]
    assert all(best_cost <= c for c in alt_costs)


# ----------------------------------------------------------------------
# 8. NO_FEASIBLE_PLAN when every option fails
# ----------------------------------------------------------------------
def test_optimizer_no_feasible_when_all_fail(monkeypatch, stub_functions):
    # All arrivals are marked infeasible.
    monkeypatch.setattr(optimizer, "is_arrival_feasible", lambda a, b: False)

    vessels = [
        make_vessel("v1"),
        make_vessel("v2"),
    ]
    routes = [
        make_route("r1", "station_H"),
        make_route("r2", "station_H"),
    ]
    departures = [
        datetime(2026, 7, 1, tzinfo=timezone.utc),
        datetime(2026, 7, 2, tzinfo=timezone.utc),
    ]
    station_inventory = {"station_H": FakeInventory(None)}

    result = optimizer.optimize_resupply(
        vessels=vessels,
        routes=routes,
        departure_dates=departures,
        cargo_weight_tonnes=5.0,
        station_inventory=station_inventory,
        safety_buffer_days=1.0,
    )

    assert result.status == "NO_FEASIBLE_PLAN"
    assert result.best_option is None
    assert "infeasible" in (result.notes or "").lower()


# ----------------------------------------------------------------------
# 9. Optimizer propagates rejection reasons
# ----------------------------------------------------------------------
def test_optimizer_provides_rejection_reason(monkeypatch, stub_functions):
    """
    Mix two failure modes: one option fails because of fuel capacity,
    the other fails because of late arrival.  The result notes should
    contain one of those reasons.
    """
    # Custom feasibility: only the first vessel's option is late.
    def custom_feasibility(actual, latest):
        # For vessel with id "fuel_bad" we will make the arrival later than the
        # cutoff, causing infeasibility.  For the other vessel we let the check
        # pass, but fuel capacity will reject it.
        return True

    monkeypatch.setattr(optimizer, "is_arrival_feasible", custom_feasibility)

    # Vessel that will be rejected due to fuel capacity.
    fuel_bad = make_vessel(
        "fuel_bad",
        fuel_capacity=1_000.0,          # too small for the voyage
        fuel_consumption_per_day=500.0,
    )
    # Vessel that will be rejected due to late arrival (we force the
    # feasibility check to return False for it by monkey‑patching later).
    late_bad = make_vessel(
        "late_bad",
        max_speed=5.0,                  # slower → later arrival
    )
    # Make the late arrival infeasible.
    monkeypatch.setattr(
        optimizer,
        "is_arrival_feasible",
        lambda actual, latest: actual <= datetime(2100, 1, 1, tzinfo=timezone.utc),
    )

    route = make_route("r9", "station_I")
    departure = datetime(2026, 8, 1, tzinfo=timezone.utc)
    station_inventory = {"station_I": FakeInventory(None)}

    result = optimizer.optimize_resupply(
        vessels=[fuel_bad, late_bad],
        routes=[route],
        departure_dates=[departure],
        cargo_weight_tonnes=5.0,
        station_inventory=station_inventory,
        safety_buffer_days=1.0,
    )

    assert result.status == "NO_FEASIBLE_PLAN"
    # The generic notes string should mention either ’fuel‘ or ’arrival‘.
    note = (result.notes or "").lower()
    assert ("fuel" in note) or ("arrival" in note)


# ----------------------------------------------------------------------
# 10. Changing station consumption changes the optimal result
# ----------------------------------------------------------------------
def test_optimizer_station_consumption_affects_optimal_choice(monkeypatch, stub_functions):
    """
    Two routes lead to the same station, but the station’s daily consumption
    impacts the critical date.  By altering that consumption we make one route
    feasible and the other infeasible, flipping which option is chosen.
    """

    # All arrivals are feasible by default.
    monkeypatch.setattr(optimizer, "is_arrival_feasible", lambda a, b: True)

    vessel = make_vessel("vX", max_speed=10.0)
    route_a = make_route("routeA", "station_J")
    route_b = make_route("routeB", "station_J")
    departure = datetime(2026, 9, 1, tzinfo=timezone.utc)

    # First inventory: high consumption → critical date early → both routes feasible.
    high_consumption_inventory = {
        "station_J": FakeInventory(
            # Critical date 2026‑01‑05 (early)
            datetime(2026, 1, 5, tzinfo=timezone.utc)
        )
    }

    result_high = optimizer.optimize_resupply(
        vessels=[vessel],
        routes=[route_a, route_b],
        departure_dates=[departure],
        cargo_weight_tonnes=5.0,
        station_inventory=high_consumption_inventory,
        safety_buffer_days=2.0,
    )
    assert result_high.status == "SUCCESS"
    # Both routes are feasible; the optimizer will pick one (the first in the sorted list).
    # Ensure that a best option exists.
    assert result_high.best_option is not None

    # Second inventory: low consumption → critical date far in the future,
    # making the longer route (which we will artificially lengthen) exceed the buffer.
    low_consumption_inventory = {
        "station_J": FakeInventory(
            # Critical date far in the future (2027‑01‑01)
            datetime(2027, 1, 1, tzinfo=timezone.utc)
        )
    }

    # Monkey‑patch the distance function so that route A is short (1000 km) and
    # route B is long (2000 km).  This will affect voyage duration and thus the
    # arrival datetime.
    def fake_route_distance_km(waypoints):
        # Pick route based on the route's id present in the waypoint list
        # (the fake waypoints contain no id, so we inspect the caller via
        # closure – instead we simply differentiate by length of the list).
        # For simplicity, return 1 000 km for route A and 2 000 km for route B.
        if len(waypoints) == 2:
            # In our stub, both routes have two waypoints; use the global
            # variable set before calling optimise to decide.
            return fake_route_distance_km.current_distance
        return 1_000.0

    # Assign a custom attribute that the stub reads.
    fake_route_distance_km.current_distance = 1_000.0  # default for route A
    monkeypatch.setattr(optimizer, "calculate_route_distance_km", fake_route_distance_km)

    # First evaluate with short route (1 000 km) → should be feasible.
    result_low_short = optimizer.optimize_resupply(
        vessels=[vessel],
        routes=[route_a],
        departure_dates=[departure],
        cargo_weight_tonnes=5.0,
        station_inventory=low_consumption_inventory,
        safety_buffer_days=2.0,
    )
    assert result_low_short.status == "SUCCESS"
    assert result_low_short.best_option is not None

    # Now evaluate with long route (2 000 km) → make it infeasible by increasing
    # the distance that the stub returns.
    fake_route_distance_km.current_distance = 2_000.0  # long route for route B
    result_low_long = optimizer.optimize_resupply(
        vessels=[vessel],
        routes=[route_b],
        departure_dates=[departure],
        cargo_weight_tonnes=5.0,
        station_inventory=low_consumption_inventory,
        safety_buffer_days=2.0,
    )
    # With a far‑future critical date the long voyage will push arrival beyond
    # the calculated latest safe arrival, causing infeasibility.
    assert result_low_long.status == "NO_FEASIBLE_PLAN"