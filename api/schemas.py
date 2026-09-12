from __future__ import annotations

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field


class StationSummary(BaseModel):
    id: str
    name: str
    country: str
    latitude: float
    longitude: float
    status: str


class PortSummary(BaseModel):
    id: str
    name: str
    country: str
    latitude: float
    longitude: float
    capacity_tonnes: float
    availability: bool


class VesselSummary(BaseModel):
    id: str
    name: str
    vessel_type: str
    cruise_speed_knots: float
    max_speed_knots: float
    cargo_capacity_tonnes: float
    fuel_capacity_litres: float
    fuel_consumption_litres_per_day: float


class RouteSummary(BaseModel):
    id: str
    name: str
    origin_port_id: str
    destination_station_id: str
    distance_km: float


class ResourceInventoryRequest(BaseModel):
    resource_name: str = Field(min_length=1)
    current_quantity: float = Field(ge=0)
    unit: str = Field(min_length=1)
    daily_consumption: float = Field(ge=0)
    minimum_safety_threshold: float = Field(ge=0)
    required_resupply_quantity: float = Field(ge=0)


class OptimizeRequest(BaseModel):
    station_id: str
    resource_name: str
    cargo_weight_tonnes: float = Field(gt=0)
    current_datetime: datetime
    departure_dates: list[datetime] = Field(min_length=1)
    safety_buffer_days: float = Field(default=3.0, ge=0)
    max_alternatives: int = Field(default=3, ge=0)
    inventory: ResourceInventoryRequest


class VoyageOptionResponse(BaseModel):
    vessel_id: Optional[str] = None
    vessel_name: Optional[str] = None

    route_id: Optional[str] = None
    route_name: Optional[str] = None

    origin_port_id: Optional[str] = None
    origin_port_name: Optional[str] = None

    destination_station_id: Optional[str] = None
    destination_station_name: Optional[str] = None

    departure: datetime
    arrival: Optional[datetime] = None

    distance_km: float
    distance_nm: float
    voyage_duration_days: float

    fuel_required_litres: float
    fuel_cost: float
    operating_cost: float
    total_cost: float
    cost_per_tonne: float

    safety_margin_days: Optional[float] = None

    feasible: bool
    rejection_reason: Optional[str] = None


class OptimizationResponse(BaseModel):
    status: str
    message: str
    recommended_option: Optional[VoyageOptionResponse] = None
    alternatives: list[VoyageOptionResponse] = Field(
        default_factory=list
    )
    infeasible_options: list[VoyageOptionResponse] = Field(
        default_factory=list
    )
class MissionCreateRequest(BaseModel):
    station_id: str
    vessel_id: str
    route_id: str
    cargo_weight_tonnes: float = Field(gt=0)
    departure_datetime: datetime
    safety_buffer_days: float = Field(default=3.0, ge=0)


class MissionUpdateRequest(BaseModel):
    elapsed_seconds: float = Field(ge=0)    