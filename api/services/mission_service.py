from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Dict

from engine.models import ResourceInventory, Route, Station, Vessel
from simulation.environment_events import create_demo_timeline
from simulation.mission import ResupplyMission


DATA_DIR = Path(__file__).resolve().parents[2] / "data"


class MissionService:
    def __init__(self) -> None:
        self._missions: Dict[str, ResupplyMission] = {}

    # ------------------------------------------------------------------
    # Data loading
    # ------------------------------------------------------------------

    def _load_json(self, filename: str) -> dict:
        with open(DATA_DIR / filename, "r", encoding="utf-8") as file:
            return json.load(file)

    def _get_station(self, station_id: str) -> Station:
        data = self._load_json("stations.json")

        for item in data["stations"]:
            if item["id"] == station_id:
                return Station(
                    id=item["id"],
                    name=item["name"],
                    latitude=item["latitude"],
                    longitude=item["longitude"],
                    status=item.get("status", "operational"),
                    inventory_reference=item.get(
                        "inventory_reference",
                        "scenario_01",
                    ),
                    receiving_capacity_tonnes=item.get(
                        "receiving_capacity_tonnes",
                        0,
                    ),
                    country=item.get("country", "India"),
                )

        raise ValueError(f"Station not found: {station_id}")

    def _get_vessel(self, vessel_id: str) -> Vessel:
        data = self._load_json("vessels.json")

        for item in data["vessels"]:
            if item["id"] == vessel_id:
                return Vessel(**item)

        raise ValueError(f"Vessel not found: {vessel_id}")

    def _get_route(self, route_id: str) -> Route:
        data = self._load_json("routes.json")

        for item in data["routes"]:
            if item["id"] == route_id:
                return Route(**item)

        raise ValueError(f"Route not found: {route_id}")

    # ------------------------------------------------------------------
    # Demo inventory
    # ------------------------------------------------------------------

    def _default_inventory(self) -> Dict[str, ResourceInventory]:
        return {
            "diesel": ResourceInventory(
                resource_name="diesel",
                current_quantity=300000,
                unit="litres",
                daily_consumption=1800,
                minimum_safety_threshold=25000,
                required_resupply_quantity=60000,
            )
        }

    # ------------------------------------------------------------------
    # Mission lifecycle
    # ------------------------------------------------------------------

    def create_mission(
        self,
        station_id: str,
        vessel_id: str,
        route_id: str,
        cargo_weight_tonnes: float,
        departure_datetime: datetime,
        safety_buffer_days: float = 3.0,
    ) -> tuple[str, ResupplyMission]:

        station = self._get_station(station_id)
        vessel = self._get_vessel(vessel_id)
        route = self._get_route(route_id)

        if route.destination_station_id != station_id:
            raise ValueError(
                f"Route {route_id} does not terminate at station {station_id}."
            )

        if route.origin_port_id not in {
            "MUMBAI",
            "CHENNAI",
        }:
            raise ValueError(
                f"Unsupported origin port: {route.origin_port_id}"
            )

        if vessel.cargo_capacity_tonnes < cargo_weight_tonnes:
            raise ValueError(
                f"Cargo weight {cargo_weight_tonnes} tonnes exceeds "
                f"vessel capacity {vessel.cargo_capacity_tonnes} tonnes."
            )

        if departure_datetime.tzinfo is None:
            raise ValueError(
                "departure_datetime must be timezone-aware."
            )

        mission = ResupplyMission.create(
            station=station,
            vessel=vessel,
            route=route,
            cargo_weight_tonnes=cargo_weight_tonnes,
            departure_datetime=departure_datetime,
            station_inventory=self._default_inventory(),
            safety_buffer_days=safety_buffer_days,
            environment_timeline=create_demo_timeline(
                departure_datetime
            ),
        )

        mission_id = f"MISSION-{len(self._missions) + 1:04d}"

        self._missions[mission_id] = mission

        return mission_id, mission

    def get_mission(self, mission_id: str) -> ResupplyMission:
        try:
            return self._missions[mission_id]
        except KeyError:
            raise ValueError(
                f"Mission not found: {mission_id}"
            )

    def start_mission(self, mission_id: str) -> ResupplyMission:
        mission = self.get_mission(mission_id)
        mission.start()
        return mission

    def update_mission(
        self,
        mission_id: str,
        elapsed_seconds: float,
    ) -> ResupplyMission:

        mission = self.get_mission(mission_id)

        mission.update(elapsed_seconds)

        return mission

    def pause_mission(self, mission_id: str) -> ResupplyMission:
        mission = self.get_mission(mission_id)

        if mission.simulation_state is not None:
            mission.simulation_state.pause()
            mission.status = "PAUSED"

        return mission

    def resume_mission(self, mission_id: str) -> ResupplyMission:
        mission = self.get_mission(mission_id)
        mission.resume()
        return mission

    def get_state(self, mission_id: str) -> dict:
        mission = self.get_mission(mission_id)
        return mission.get_state()