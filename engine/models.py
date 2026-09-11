from __future__ import annotations

from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, Field, field_validator, model_validator


class Waypoint(BaseModel):
    """Geographic point used by simulated maritime routes."""

    latitude: float
    longitude: float

    @field_validator("latitude")
    @classmethod
    def validate_latitude(cls, value: float) -> float:
        if not -90 <= value <= 90:
            raise ValueError("Latitude must be between -90 and 90 degrees")
        return value

    @field_validator("longitude")
    @classmethod
    def validate_longitude(cls, value: float) -> float:
        if not -180 <= value <= 180:
            raise ValueError("Longitude must be between -180 and 180 degrees")
        return value


class Port(BaseModel):
    """Indian maritime departure point used by the simulator."""

    id: str
    name: str
    country: str

    latitude: float
    longitude: float

    cargo_handling_capacity_tonnes: float = Field(gt=0)
    available_for_simulation: bool = True

    @field_validator("latitude")
    @classmethod
    def validate_latitude(cls, value: float) -> float:
        if not -90 <= value <= 90:
            raise ValueError("Latitude must be between -90 and 90 degrees")
        return value

    @field_validator("longitude")
    @classmethod
    def validate_longitude(cls, value: float) -> float:
        if not -180 <= value <= 180:
            raise ValueError("Longitude must be between -180 and 180 degrees")
        return value


class Station(BaseModel):
    """Indian Antarctic research station."""

    id: str
    name: str
    country: str

    latitude: float
    longitude: float

    operational_status: str
    inventory_reference: Optional[str] = None
    receiving_capacity_tonnes: float = Field(gt=0)

    @field_validator("latitude")
    @classmethod
    def validate_latitude(cls, value: float) -> float:
        if not -90 <= value <= 90:
            raise ValueError("Latitude must be between -90 and 90 degrees")
        return value

    @field_validator("longitude")
    @classmethod
    def validate_longitude(cls, value: float) -> float:
        if not -180 <= value <= 180:
            raise ValueError("Longitude must be between -180 and 180 degrees")
        return value


class Vessel(BaseModel):
    """Simulated resupply vessel profile."""

    id: str
    name: str
    vessel_type: str

    cruising_speed_knots: float = Field(gt=0)
    maximum_speed_knots: float = Field(gt=0)

    cargo_capacity_tonnes: float = Field(gt=0)

    fuel_capacity_litres: float = Field(gt=0)
    fuel_consumption_litres_per_day: float = Field(gt=0)

    operating_cost_per_day: float = Field(ge=0)
    fuel_cost_per_litre: float = Field(ge=0)

    availability_start: datetime
    availability_end: datetime

    status: str = "available"

    @model_validator(mode="after")
    def validate_vessel(self) -> "Vessel":
        if self.maximum_speed_knots < self.cruising_speed_knots:
            raise ValueError(
                "maximum_speed_knots must be greater than or equal to "
                "cruising_speed_knots"
            )

        if self.availability_start.tzinfo is None:
            raise ValueError("availability_start must be timezone-aware")

        if self.availability_end.tzinfo is None:
            raise ValueError("availability_end must be timezone-aware")

        if self.availability_end < self.availability_start:
            raise ValueError(
                "availability_end must be after availability_start"
            )

        return self


class Route(BaseModel):
    """Simulated maritime corridor between an Indian port and an Antarctic station."""

    id: str
    name: str

    origin_port_id: str
    destination_station_id: str

    waypoints: List[Waypoint]

    distance_km: Optional[float] = Field(default=None, ge=0)

    route_type: str
    base_risk_factor: float = Field(ge=0)

    @field_validator("waypoints")
    @classmethod
    def validate_waypoints(
        cls,
        value: List[Waypoint],
    ) -> List[Waypoint]:
        if len(value) < 2:
            raise ValueError("Route must contain at least two waypoints")
        return value


class ResourceInventory(BaseModel):
    """Inventory state for one station resource."""

    resource_name: str

    current_quantity: float = Field(ge=0)
    unit: str

    daily_consumption: float = Field(ge=0)
    minimum_safety_threshold: float = Field(ge=0)

    required_resupply_quantity: float = Field(ge=0)

    @model_validator(mode="after")
    def validate_inventory(self) -> "ResourceInventory":
        if self.minimum_safety_threshold > self.current_quantity:
            # This is allowed because the resource can already be
            # below its desired safety threshold.
            pass

        return self


__all__ = [
    "Waypoint",
    "Port",
    "Station",
    "Vessel",
    "Route",
    "ResourceInventory",
]