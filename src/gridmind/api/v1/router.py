from __future__ import annotations

from fastapi import APIRouter

from gridmind.api.v1 import audit, balancing, battery, dispatch, forecasting, grid, operations, optimization, outages

api_router = APIRouter(prefix="/api/v1")
api_router.include_router(forecasting.router)
api_router.include_router(balancing.router)
api_router.include_router(outages.router)
api_router.include_router(dispatch.router)
api_router.include_router(audit.router)
api_router.include_router(grid.router)
api_router.include_router(operations.router)
api_router.include_router(battery.router)
api_router.include_router(optimization.router)
