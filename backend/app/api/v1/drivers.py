"""Driver catalog endpoint: lists supported device platforms for the UI."""

from __future__ import annotations

from fastapi import APIRouter
from pydantic import BaseModel

from app.api.deps import CurrentUser
from app.drivers import list_drivers

router = APIRouter(prefix="/drivers", tags=["drivers"])


class DriverInfo(BaseModel):
    platform: str
    display_name: str
    vendor: str
    transport_kind: str
    default_port: int
    config_format: str


@router.get("", response_model=list[DriverInfo])
async def list_supported_drivers(current_user: CurrentUser) -> list[DriverInfo]:
    """Return every supported platform so the UI can populate device/config dropdowns."""
    return [DriverInfo(**meta.__dict__) for meta in list_drivers()]
