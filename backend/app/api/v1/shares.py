"""Share request endpoints: request access to a config, accept/deny incoming requests."""

from __future__ import annotations

import uuid

from fastapi import APIRouter, HTTPException, status

from app.api.deps import CurrentUser, DbSession
from app.schemas.share import ShareRequestCreate, ShareRequestDecision, ShareRequestRead
from app.services import audit_service, config_service, share_service
from app.services.share_service import ShareError

router = APIRouter(prefix="/shares", tags=["shares"])


@router.post("", response_model=ShareRequestRead, status_code=status.HTTP_201_CREATED)
async def request_share(
    db: DbSession, current_user: CurrentUser, payload: ShareRequestCreate
) -> ShareRequestRead:
    """Ask the owner of a config file for read access."""
    config = await config_service.get(db, payload.config_file_id)
    if not config:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Config file not found")
    try:
        request = await share_service.create_request(db, current_user, config, payload.message)
    except ShareError as exc:
        raise HTTPException(status.HTTP_409_CONFLICT, str(exc)) from exc
    await audit_service.record(
        db, actor_id=current_user.id, action="share.request",
        target_type="config", target_id=config.id,
    )
    return ShareRequestRead.model_validate(request)


@router.get("/incoming", response_model=list[ShareRequestRead])
async def incoming_requests(db: DbSession, current_user: CurrentUser) -> list[ShareRequestRead]:
    """Requests from others for config files you own."""
    requests = await share_service.list_incoming(db, current_user)
    return [ShareRequestRead.model_validate(r) for r in requests]


@router.get("/outgoing", response_model=list[ShareRequestRead])
async def outgoing_requests(db: DbSession, current_user: CurrentUser) -> list[ShareRequestRead]:
    """Requests you have made for other users' config files."""
    requests = await share_service.list_outgoing(db, current_user)
    return [ShareRequestRead.model_validate(r) for r in requests]


@router.post("/{request_id}/decision", response_model=ShareRequestRead)
async def decide_request(
    db: DbSession,
    current_user: CurrentUser,
    request_id: uuid.UUID,
    payload: ShareRequestDecision,
) -> ShareRequestRead:
    """Accept or deny an incoming share request (owner only)."""
    request = await share_service.get(db, request_id)
    if not request:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Share request not found")
    if request.owner_id != current_user.id:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Only the owner can answer this request")
    try:
        request = await share_service.decide(db, request, accept=payload.accept)
    except ShareError as exc:
        raise HTTPException(status.HTTP_409_CONFLICT, str(exc)) from exc
    await audit_service.record(
        db, actor_id=current_user.id,
        action="share.accept" if payload.accept else "share.deny",
        target_type="share", target_id=request.id,
    )
    return ShareRequestRead.model_validate(request)
