from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import List

from engine import deadline as deadline_mod
from engine import inventory as inventory_mod
from engine.models import ResourceInventory, Station


@dataclass(frozen=True)
class ResourceResupplyRequirement:
    resource_name: str
    unit: str
    current_quantity: float
    daily_consumption: float
    minimum_safety_threshold: float
    predicted_critical_date: datetime | None
    latest_safe_arrival: datetime | None
    required_quantity: float
    days_until_threshold: float
    is_urgent: bool


@dataclass
class ResupplyScenario:
    station_id: str
    station_name: str
    generated_at: datetime
    safety_buffer_days: float = 3.0
    requirements: List[ResourceResupplyRequirement] = field(default_factory=list)

    @property
    def total_resource_types(self) -> int:
        return len(self.requirements)

    @property
    def urgent_resources(self) -> List[ResourceResupplyRequirement]:
        return [
            requirement
            for requirement in self.requirements
            if requirement.is_urgent
        ]

    @property
    def has_urgent_requirements(self) -> bool:
        return len(self.urgent_resources) > 0

    def get_requirement(
        self,
        resource_name: str,
    ) -> ResourceResupplyRequirement | None:
        for requirement in self.requirements:
            if requirement.resource_name == resource_name:
                return requirement
        return None

    def to_dict(self) -> dict:
        return {
            "station_id": self.station_id,
            "station_name": self.station_name,
            "generated_at": self.generated_at.isoformat(),
            "safety_buffer_days": self.safety_buffer_days,
            "requirements": [
                {
                    "resource_name": requirement.resource_name,
                    "unit": requirement.unit,
                    "current_quantity": requirement.current_quantity,
                    "daily_consumption": requirement.daily_consumption,
                    "minimum_safety_threshold": (
                        requirement.minimum_safety_threshold
                    ),
                    "predicted_critical_date": (
                        requirement.predicted_critical_date.isoformat()
                        if requirement.predicted_critical_date
                        else None
                    ),
                    "latest_safe_arrival": (
                        requirement.latest_safe_arrival.isoformat()
                        if requirement.latest_safe_arrival
                        else None
                    ),
                    "required_quantity": requirement.required_quantity,
                    "days_until_threshold": requirement.days_until_threshold,
                    "is_urgent": requirement.is_urgent,
                }
                for requirement in self.requirements
            ],
        }


def calculate_required_resupply_quantity(
    resource: ResourceInventory,
) -> float:
    if resource.current_quantity >= resource.minimum_safety_threshold:
        return 0.0

    return (
        resource.minimum_safety_threshold
        - resource.current_quantity
    )


def build_resource_requirement(
    resource: ResourceInventory,
    current_datetime: datetime,
    safety_buffer_days: float = 3.0,
) -> ResourceResupplyRequirement:
    if safety_buffer_days < 0:
        raise ValueError("safety_buffer_days cannot be negative.")

    days_until_threshold = (
        inventory_mod.calculate_days_until_threshold(resource)
    )

    critical_date = inventory_mod.calculate_critical_date(
        resource,
        current_datetime,
    )

    latest_safe_arrival = None

    if critical_date is not None:
        latest_safe_arrival = (
            deadline_mod.calculate_latest_safe_arrival(
                critical_date,
                safety_buffer_days,
            )
        )

    required_quantity = calculate_required_resupply_quantity(resource)

    is_urgent = days_until_threshold <= safety_buffer_days

    return ResourceResupplyRequirement(
        resource_name=resource.resource_name,
        unit=resource.unit,
        current_quantity=resource.current_quantity,
        daily_consumption=resource.daily_consumption,
        minimum_safety_threshold=resource.minimum_safety_threshold,
        predicted_critical_date=critical_date,
        latest_safe_arrival=latest_safe_arrival,
        required_quantity=required_quantity,
        days_until_threshold=days_until_threshold,
        is_urgent=is_urgent,
    )


def build_resupply_scenario(
    station: Station,
    inventory: List[ResourceInventory],
    current_datetime: datetime,
    safety_buffer_days: float = 3.0,
) -> ResupplyScenario:
    if safety_buffer_days < 0:
        raise ValueError("safety_buffer_days cannot be negative.")

    requirements = [
        build_resource_requirement(
            resource,
            current_datetime,
            safety_buffer_days,
        )
        for resource in inventory
    ]

    requirements.sort(
        key=lambda requirement: requirement.days_until_threshold
    )

    return ResupplyScenario(
        station_id=station.id,
        station_name=station.name,
        generated_at=current_datetime,
        safety_buffer_days=safety_buffer_days,
        requirements=requirements,
    )