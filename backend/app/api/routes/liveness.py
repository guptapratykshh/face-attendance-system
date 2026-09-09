"""Blink-challenge liveness sessions."""

from __future__ import annotations

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from sqlmodel import Session

from app.api.deps import get_current_user
from app.api.routes._common import log_event, read_image
from app.api.schemas import ChallengeOut, LivenessResponse
from app.db.models import Person, User
from app.db.session import get_session
from app.liveness.alerts import record_spoof
from app.liveness.service import SESSION_TTL_S, liveness_service

router = APIRouter(prefix="/liveness", tags=["liveness"])


@router.post("/challenge", response_model=ChallengeOut)
def issue_challenge(user: User = Depends(get_current_user)) -> ChallengeOut:
    challenge = liveness_service.issue("blink")
    liveness_service.bind_user(challenge.id, int(user.id))
    return ChallengeOut(
        challenge_id=challenge.id,
        instruction=challenge.instruction,
        expires_in_s=int(SESSION_TTL_S),
        hold_ms=challenge.hold_ms,
        hold_frames=challenge.hold_frames,
        blink_frames=challenge.blink_frames,
        interval_ms=challenge.interval_ms,
    )


@router.post("/check", response_model=LivenessResponse)
async def check_challenge(
    challenge_id: str = Form(...),
    frames: list[UploadFile] = File(...),
    source: str = Form(default="lab"),
    user: User = Depends(get_current_user),
    session: Session = Depends(get_session),
) -> LivenessResponse:
    liveness_service.bind_user(challenge_id, int(user.id))
    blobs = [await read_image(f) for f in frames]
    result = liveness_service.check(challenge_id, blobs)
    if not result.get("ok"):
        raise HTTPException(400, detail=result.get("detail") or result.get("code"))
    person = session.get(Person, user.person_id) if user.person_id is not None else None
    texture = result.get("texture") if isinstance(result.get("texture"), dict) else {}
    photo_or_screen = not bool(texture.get("live", True))
    if result["live"]:
        decision = "live"
    elif photo_or_screen:
        decision = "spoof"
    else:
        decision = "failed"
    log_event(
        session,
        kind="liveness",
        decision=decision,
        person=person,
        detail=result["blink"].get("reason") if isinstance(result.get("blink"), dict) else None,
    )
    if photo_or_screen:
        record_spoof(session, user=user, frames=blobs, result=result, source=source)
    return LivenessResponse(
        live=result["live"],
        blink=result["blink"],
        texture=result["texture"],
        instruction=result["instruction"],
    )
