from __future__ import annotations

from fastapi import APIRouter, HTTPException

from api.schemas import OptimizeRequest, OptimizationResponse
from api.services.optimization_service import optimize_resupply_plan


router = APIRouter(
    prefix="/api",
    tags=["Optimization"],
)


@router.post(
    "/optimize",
    response_model=OptimizationResponse,
)
def optimize(request: OptimizeRequest) -> OptimizationResponse:
    """
    Find the best feasible Antarctic resupply plan
    for the supplied scenario.
    """
    try:
        return optimize_resupply_plan(request)

    except ValueError as exc:
        raise HTTPException(
            status_code=400,
            detail=str(exc),
        ) from exc

    except Exception as exc:
        # Temporary debugging detail.
        # We will replace this with a generic message
        # once the underlying issue is fixed.
        raise HTTPException(
            status_code=500,
            detail=f"{type(exc).__name__}: {exc}",
        ) from exc