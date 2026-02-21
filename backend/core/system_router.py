"""System settings router - system configuration and monitoring endpoints."""

from datetime import date
from typing import Literal, Optional

from fastapi import APIRouter, Depends, Query

from backend.auth.dependencies import get_current_user, require_admin

router = APIRouter(prefix="/api/system", tags=["system"])


@router.get("/langfuse")
async def get_langfuse_settings(_admin=Depends(require_admin)) -> dict:
    """Get Langfuse configuration for admin display.

    Returns:
        {
            "enabled": bool,
            "url": str,  # Langfuse UI URL
            "status": "healthy" | "unhealthy" | "disabled"
        }
    """
    from backend.services.langfuse_service import get_langfuse_service

    service = get_langfuse_service()
    health = await service.health_check()

    return {
        "enabled": service.enabled,
        "url": service.base_url,
        "status": health["status"],
    }


@router.get("/usage")
async def get_usage_stats(
    granularity: Literal["day"] = Query(default="day"),
    days: int = Query(default=30, ge=1, le=365),
    start_date: Optional[date] = Query(default=None),
    _user=Depends(get_current_user),
) -> dict:
    """Get system-wide token usage statistics.

    All authenticated users can access this endpoint.

    Args:
        granularity: Time aggregation granularity (fixed to day)
        days: Number of days to query (1-365)
        start_date: Optional start date for the query (YYYY-MM-DD)

    Returns:
        {
            "granularity": str,
            "period_days": int,
            "total_tokens": int,
            "input_tokens": int,
            "output_tokens": int,
            "total_cost_usd": float,
            "total_calls": int,
            "by_time": [...],
            "by_model": [...],
            "by_user": [...]
        }
    """
    from backend.services.langfuse_service import get_langfuse_service

    service = get_langfuse_service()
    return await service.get_usage_stats(
        granularity=granularity, days=days, start_date=start_date
    )
