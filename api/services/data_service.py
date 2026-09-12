from __future__ import annotations

import json
from pathlib import Path

from engine.models import Port, Route, Station, Vessel


BASE_DIR = Path(__file__).resolve().parents[2]
DATA_DIR = BASE_DIR / "data"


def _load_json(filename: str):
    """Load a JSON file from the project's data directory."""

    path = DATA_DIR / filename

    if not path.exists():
        raise FileNotFoundError(f"Data file not found: {path}")

    with path.open("r", encoding="utf-8") as file:
        return json.load(file)


def _extract_items(data, key: str) -> list[dict]:
    """
    Extract records from either a JSON list or a wrapped JSON object.
    """

    if isinstance(data, list):
        return data

    if isinstance(data, dict):
        items = data.get(key)

        if isinstance(items, list):
            return items

    raise ValueError(
        f"Expected '{key}' to contain a list of records."
    )


def load_ports() -> list[Port]:
    """Load and normalize simulated departure ports."""

    data = _load_json("ports.json")
    raw_ports = _extract_items(data, "ports")

    ports = []

    for item in raw_ports:
        normalized = {
            **item,
            "capacity_tonnes": item[
                "cargo_handling_capacity_tonnes"
            ],
            "availability": item[
                "available_for_simulation"
            ],
        }

        normalized.pop(
            "cargo_handling_capacity_tonnes",
            None,
        )

        normalized.pop(
            "available_for_simulation",
            None,
        )

        ports.append(
            Port.model_validate(normalized)
        )

    return ports


def load_stations() -> list[Station]:
    """Load all Antarctic research stations."""

    data = _load_json("stations.json")

    return [
        Station.model_validate(item)
        for item in _extract_items(data, "stations")
    ]


def load_vessels() -> list[Vessel]:
    """Load all simulated vessel profiles."""

    data = _load_json("vessels.json")

    return [
        Vessel.model_validate(item)
        for item in _extract_items(data, "vessels")
    ]


def load_routes() -> list[Route]:
    """Load all simulated maritime routes."""

    data = _load_json("routes.json")

    return [
        Route.model_validate(item)
        for item in _extract_items(data, "routes")
    ]


def get_port(port_id: str) -> Port:
    """Return a port by ID."""

    for port in load_ports():
        if port.id == port_id:
            return port

    raise ValueError(f"Port not found: {port_id}")


def get_station(station_id: str) -> Station:
    """Return a station by ID."""

    for station in load_stations():
        if station.id == station_id:
            return station

    raise ValueError(f"Station not found: {station_id}")


def get_vessel(vessel_id: str) -> Vessel:
    """Return a vessel by ID."""

    for vessel in load_vessels():
        if vessel.id == vessel_id:
            return vessel

    raise ValueError(f"Vessel not found: {vessel_id}")


def get_route(route_id: str) -> Route:
    """Return a route by ID."""

    for route in load_routes():
        if route.id == route_id:
            return route

    raise ValueError(f"Route not found: {route_id}")