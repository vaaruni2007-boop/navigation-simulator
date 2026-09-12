from __future__ import annotations

from fastapi import APIRouter, HTTPException

from api.schemas import (
    MissionCreateRequest,
    MissionUpdateRequest,
)
from api.services.mission_service import MissionService


router = APIRouter(
    prefix="/api/mission",
    tags=["Mission Simulation"],
)

service = MissionService()


@router.post("")
def create_mission(request: MissionCreateRequest):
    try:
        mission_id, mission = service.create_mission(
            station_id=request.station_id,
            vessel_id=request.vessel_id,
            route_id=request.route_id,
            cargo_weight_tonnes=request.cargo_weight_tonnes,
            departure_datetime=request.departure_datetime,
            safety_buffer_days=request.safety_buffer_days,
        )

        return {
            "status": "success",
            "message": "Resupply mission created.",
            "mission_id": mission_id,
            "mission": mission.get_state(),
        }

    except ValueError as exc:
        raise HTTPException(
            status_code=400,
            detail=str(exc),
        )


@router.get("/{mission_id}")
def get_mission(mission_id: str):
    try:
        return {
            "status": "success",
            "mission_id": mission_id,
            "mission": service.get_state(mission_id),
        }

    except ValueError as exc:
        raise HTTPException(
            status_code=404,
            detail=str(exc),
        )


@router.post("/{mission_id}/start")
def start_mission(mission_id: str):
    try:
        mission = service.start_mission(mission_id)

        return {
            "status": "success",
            "message": "Mission started.",
            "mission_id": mission_id,
            "mission": mission.get_state(),
        }

    except ValueError as exc:
        raise HTTPException(
            status_code=400,
            detail=str(exc),
        )


@router.post("/{mission_id}/update")
def update_mission(
    mission_id: str,
    request: MissionUpdateRequest,
):
    try:
        mission = service.update_mission(
            mission_id,
            request.elapsed_seconds,
        )

        return {
            "status": "success",
            "message": "Mission updated.",
            "mission_id": mission_id,
            "mission": mission.get_state(),
        }

    except RuntimeError as exc:
        raise HTTPException(
            status_code=409,
            detail=str(exc),
        )

    except ValueError as exc:
        raise HTTPException(
            status_code=400,
            detail=str(exc),
        )


@router.post("/{mission_id}/pause")
def pause_mission(mission_id: str):
    try:
        mission = service.pause_mission(mission_id)

        return {
            "status": "success",
            "message": "Mission paused.",
            "mission_id": mission_id,
            "mission": mission.get_state(),
        }

    except ValueError as exc:
        raise HTTPException(
            status_code=400,
            detail=str(exc),
        )


@router.post("/{mission_id}/resume")
def resume_mission(mission_id: str):
    try:
        mission = service.resume_mission(mission_id)

        return {
            "status": "success",
            "message": "Mission resumed.",
            "mission_id": mission_id,
            "mission": mission.get_state(),
        }

    except ValueError as exc:
        raise HTTPException(
            status_code=400,
            detail=str(exc),
        )