"""Health and readiness probes."""

from __future__ import annotations

from fastapi import APIRouter
from sqlalchemy import text

from app.api.deps import DbSession
from app.core.redis import get_redis

router = APIRouter(tags=["health"])


@router.get("/health")
async def health() -> dict[str, str]:
    """Liveness probe — process is up."""
    return {"status": "ok"}


@router.get("/ready")
async def ready(db: DbSession) -> dict[str, str]:
    """Readiness probe — dependencies (DB, Redis) are reachable."""
    checks: dict[str, str] = {}
    try:
        await db.execute(text("SELECT 1"))
        checks["database"] = "ok"
    except Exception as exc:  # noqa: BLE001
        checks["database"] = f"error: {exc}"
    try:
        await get_redis().ping()
        checks["redis"] = "ok"
    except Exception as exc:  # noqa: BLE001
        checks["redis"] = f"error: {exc}"
    checks["status"] = "ok" if all(v == "ok" for v in checks.values()) else "degraded"
    return checks
