"""Optional SMTP notices for enrollment, late, absent, failed checks, and spoof alerts."""

from __future__ import annotations

import logging
import smtplib
from email.message import EmailMessage

from app.core.config import settings
from app.db.models import Person

log = logging.getLogger(__name__)


def _send(to: str, subject: str, body: str, image: bytes | None = None) -> None:
    if not settings.smtp_host or not to:
        return
    sender = settings.smtp_from or settings.smtp_user
    if not sender:
        return
    msg = EmailMessage()
    msg["Subject"] = subject
    msg["From"] = sender
    msg["To"] = to
    msg.set_content(body)
    if image:
        msg.add_attachment(image, maintype="image", subtype="jpeg", filename="blocked-check-in.jpg")
    try:
        with smtplib.SMTP(settings.smtp_host, settings.smtp_port, timeout=10) as smtp:
            smtp.starttls()
            if settings.smtp_user and settings.smtp_password:
                smtp.login(settings.smtp_user, settings.smtp_password)
            smtp.send_message(msg)
    except Exception:
        log.exception("failed to send email to %s", to)


def notify_face_enrolled(person: Person) -> None:
    if not person.email:
        return
    _send(
        person.email,
        "You can check in now",
        f"Hi {person.name},\n\nYour face has been enrolled. You can mark attendance in Sentinel.\n",
    )


def notify_late_arrival(person: Person) -> None:
    if not person.email:
        return
    _send(
        person.email,
        "Late check-in recorded",
        f"Hi {person.name},\n\nSentinel marked you present after the late grace window.\n",
    )


def notify_fail_streak(person: Person, count: int) -> None:
    if not person.email:
        return
    _send(
        person.email,
        "Face check-in failed several times",
        f"Hi {person.name},\n\nSentinel recorded {count} failed face checks today. "
        "Use even light, face the camera, and try again — or ask HR for a kiosk PIN.\n",
    )


def notify_absence(person: Person) -> None:
    if not person.email:
        return
    _send(
        person.email,
        "You were marked absent",
        f"Hi {person.name},\n\nYou had not checked in after office start plus grace. "
        "If you are on leave, tell HR so this day is not counted as absent.\n",
    )


def notify_spoof_alert(
    recipients: list[str],
    *,
    who: str,
    actor: str,
    place: str,
    reason: str,
    image: bytes,
) -> None:
    if not recipients:
        return
    body = (
        f"Sentinel blocked a check-in that looked like a photo or a video.\n\n"
        f"Who: {who}\n"
        f"Account: {actor}\n"
        f"Where: {place}\n"
        f"Why: {reason}\n\n"
        "The captured camera frame is attached. Open Today in Sentinel to review it.\n"
        "They were not marked present.\n"
    )
    for to in recipients:
        _send(to, f"Cheating alert: {who}", body, image=image)
