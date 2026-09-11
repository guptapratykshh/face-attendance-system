"""Record blocked photo/video check-ins and notify HR and admin."""

from __future__ import annotations

import json
import logging

import cv2
from sqlmodel import Session, col, select

from app.api.routes._common import log_event
from app.core.mail import notify_spoof_alert
from app.core.org_ctx import gallery_allowed_ids, get_current_org_id
from app.core.roles import PEOPLE_ROLES
from app.db.models import CaptureProbe, Person, SpoofAlert, User
from app.pipeline.face_pipeline import decode_image
from app.runtime import runtime

log = logging.getLogger(__name__)

ATTENDANCE_SOURCES = frozenset({"attendance", "kiosk"})


def _jpeg(blob: bytes) -> bytes | None:
    try:
        rgb = decode_image(blob)
        bgr = cv2.cvtColor(rgb, cv2.COLOR_RGB2BGR)
        ok, buf = cv2.imencode(".jpg", bgr, [int(cv2.IMWRITE_JPEG_QUALITY), 82])
        if not ok:
            return None
        data = buf.tobytes()
        if not data or len(data) > 2_500_000:
            return None
        return data
    except Exception:
        log.exception("could not encode spoof frame")
        return None


def _reason(result: dict) -> str:
    blink = result.get("blink") if isinstance(result.get("blink"), dict) else {}
    texture = result.get("texture") if isinstance(result.get("texture"), dict) else {}
    parts = [blink.get("reason"), texture.get("reason")]
    return "; ".join(p for p in parts if p) or "photo or video replay"


def _match_person(session: Session, blob: bytes) -> tuple[Person | None, float | None]:
    rt = runtime
    if rt.pipeline is None or rt.gallery is None:
        return None, None
    try:
        face = rt.pipeline.embed_single(blob)
        matches = rt.gallery.search(face.embedding, top_k=1, allowed_ids=gallery_allowed_ids(session))
        if not matches:
            return None, None
        hit = matches[0]
        person = session.get(Person, hit.person_id)
        return person, float(hit.similarity)
    except Exception:
        log.exception("could not identify spoof frame")
        return None, None


def _staff_emails(session: Session) -> list[str]:
    from app.core.config import settings

    emails: list[str] = []
    seen: set[str] = set()
    extra = (settings.alert_email or "").strip()
    for raw in extra.split(","):
        addr = raw.strip()
        if addr and addr not in seen:
            seen.add(addr)
            emails.append(addr)
    staff = session.exec(select(User).where(col(User.role).in_(list(PEOPLE_ROLES)))).all()
    for user in staff:
        if user.person_id is None:
            continue
        person = session.get(Person, user.person_id)
        addr = (person.email or "").strip() if person is not None else ""
        if addr and addr not in seen:
            seen.add(addr)
            emails.append(addr)
    return emails


def record_capture_probe(
    session: Session,
    *,
    user: User,
    challenge_id: str | None,
    source: str,
    report: str | dict | None,
    analysis: dict | None,
    label: str | None = None,
) -> CaptureProbe | None:
    """Persist one probe session. Bonafide traffic is the negative class, so keep it all."""
    if report is None:
        return None
    raw = report if isinstance(report, str) else json.dumps(report)
    if len(raw) > 200_000:
        return None
    row = CaptureProbe(
        org_id=get_current_org_id(),
        user_id=int(user.id) if user.id is not None else None,
        challenge_id=challenge_id,
        source=source,
        score=analysis.get("score") if analysis else None,
        live=analysis.get("live") if analysis else None,
        scored_by=analysis.get("scored_by") if analysis else None,
        reason=analysis.get("reason") if analysis else None,
        features_json=json.dumps(analysis.get("features")) if analysis else None,
        report_json=raw,
        label=(label or None),
    )
    try:
        session.add(row)
        session.commit()
        session.refresh(row)
    except Exception:
        session.rollback()
        log.exception("could not store capture probe")
        return None
    return row


def record_spoof(
    session: Session,
    *,
    user: User,
    frames: list[bytes],
    result: dict,
    source: str,
) -> SpoofAlert | None:
    if source not in ATTENDANCE_SOURCES:
        return None
    texture = result.get("texture") if isinstance(result.get("texture"), dict) else {}
    if result.get("live") or texture.get("live"):
        # Texture already says this is a live face — a missed blink is not a photo.
        return None
    probe = frames[len(frames) // 2] if frames else None
    if not probe:
        probe = frames[0] if frames else None
    if not probe:
        return None
    jpeg = _jpeg(probe)
    if jpeg is None:
        return None

    linked = session.get(Person, user.person_id) if user.person_id is not None else None
    identified, similarity = _match_person(session, probe)
    person = linked or identified
    reason = _reason(result)
    place = "kiosk" if source == "kiosk" else "phone check-in"

    alert = SpoofAlert(
        org_id=get_current_org_id() or (person.org_id if person is not None else None),
        actor_user_id=int(user.id) if user.id is not None else None,
        actor_username=user.username,
        person_id=int(person.id) if person is not None else None,
        person_name=person.name if person is not None else None,
        source=source,
        reason=reason,
        similarity=similarity,
        image=jpeg,
    )
    session.add(alert)
    session.commit()
    session.refresh(alert)

    who = person.name if person is not None else user.username
    log_event(
        session,
        kind="spoof",
        decision="blocked",
        person=person,
        similarity=similarity,
        detail=f"{place}: {reason}",
    )
    try:
        notify_spoof_alert(
            _staff_emails(session),
            who=who,
            actor=user.username,
            place=place,
            reason=reason,
            image=jpeg,
        )
    except Exception:
        log.exception("could not email spoof alert")
    return alert
