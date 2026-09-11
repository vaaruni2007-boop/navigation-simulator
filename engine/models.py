from __future__ import annotations

from datetime import datetime
from typing import List, Optional

from pydantic import (
    AliasChoices,
    BaseModel,
    ConfigDict,
    Field,
    field_validator,
    model_validator,
)


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

    latitude: float
    longitude: float

    capacity_tonnes: float = Field(gt=0)

    available: bool = True

    country: str = "India"

    cargo_handling_capacity_tonnes: Optional[float] = None

    @model_validator(mode="after")
    def set_handling_capacity(self) -> "Port":
        """
        If a separate cargo-handling capacity is not provided,
        use the port's general capacity.
        """
        if self.cargo_handling_capacity_tonnes is None:
            self.cargo_handling_capacity_tonnes = self.capacity_tonnes

        return self

    @property
    def available_for_simulation(self) -> bool:
        """Backward-compatible access for optimizer checks."""
        return self.available

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

    latitude: float
    longitude: float

    status: str = "operational"

    inventory_reference: Optional[str] = None
    receiving_capacity_tonnes: float = Field(gt=0)

    country: str = "India"

    @property
    def operational_status(self) -> str:
        """Backward-compatible access to station operational status."""
        return self.status

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

    model_config = ConfigDict(populate_by_name=True)

    id: str
    name: str

    vessel_type: str = Field(
        validation_alias=AliasChoices("vessel_type", "type")
    )

    cruising_speed_knots: float = Field(
        gt=0,
        validation_alias=AliasChoices(
            "cruising_speed_knots",
            "cruise_speed_knots",
        ),
    )

    maximum_speed_knots: float = Field(
        gt=0,
        validation_alias=AliasChoices(
            "maximum_speed_knots",
            "max_speed_knots",
        ),
    )

    cargo_capacity_tonnes: float = Field(gt=0)

    fuel_capacity_litres: float = Field(gt=0)

    fuel_consumption_litres_per_day: float = Field(
        gt=0,
        validation_alias=AliasChoices(
            "fuel_consumption_litres_per_day",
            "fuel_consumption_l_per_day",
        ),
    )

    operating_cost_per_day: float = Field(ge=0)

    fuel_cost_per_litre: float = Field(ge=0)

    # Optional because test/simulation vessels may not have
    # a restricted availability window.
    availability_start: datetime | None = None
    availability_end: datetime | None = None

    status: str = "available"

    @property
    def type(self) -> str:
        """Backward-compatible access to vessel type."""
        return self.vessel_type

    @property
    def cruise_speed_knots(self) -> float:
        """Backward-compatible access to cruising speed."""
        return self.cruising_speed_knots

    @property
    def max_speed_knots(self) -> float:
        """Backward-compatible access to maximum speed."""
        return self.maximum_speed_knots

    @model_validator(mode="after")
    def validate_vessel(self) -> "Vessel":
        """Validate vessel speed and optional availability window."""

        if self.maximum_speed_knots < self.cruising_speed_knots:
            raise ValueError(
                "maximum_speed_knots must be greater than or equal to "
                "cruising_speed_knots"
            )

        # Availability dates are optional.
        # If supplied, however, they must be timezone-aware.
        if (
            self.availability_start is not None
            and self.availability_start.tzinfo is None
        ):
            raise ValueError(
                "availability_start must be timezone-aware"
            )

        if (
            self.availability_end is not None
            and self.availability_end.tzinfo is None
        ):
            raise ValueError(
                "availability_end must be timezone-aware"
            )

        if (
            self.availability_start is not None
            and self.availability_end is not None
            and self.availability_end < self.availability_start
        ):
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

    distance_km: Optional[float] = Field(
        default=None,
        ge=0,
    )

    route_type: str

    base_risk_factor: float = Field(ge=0)

    @field_validator("waypoints")
    @classmethod
    def validate_waypoints(
        cls,
        value: List[Waypoint],
    ) -> List[Waypoint]:
        if len(value) < 2:
            raise ValueError(
                "Route must contain at least two waypoints"
            )

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
        """
        Being below the safety threshold is allowed.
        The optimizer should handle it as a critical condition.
        """
        return self


__all__ = [
    "Waypoint",
    "Port",
    "Station",
    "Vessel",
    "Route",
    "ResourceInventory",
]