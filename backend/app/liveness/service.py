"""Short-lived blink-challenge sessions with a random wait, then 'blink now'."""

from __future__ import annotations

import secrets
import time
from dataclasses import dataclass, field
from random import randint

from app.liveness.blink import ear_from_image, timed_blink
from app.liveness.texture import replay_analysis
from app.pipeline.face_pipeline import decode_image

SESSION_TTL_S = 60.0
HOLD_FRAMES = 8
BLINK_FRAMES = 16
INTERVAL_MS = 70
HOLD_MS_MIN = 900
HOLD_MS_MAX = 2200


@dataclass
class Challenge:
    id: str
    instruction: str
    created_at: float
    expires_at: float
    hold_ms: int = 1200
    hold_frames: int = HOLD_FRAMES
    blink_frames: int = BLINK_FRAMES
    interval_ms: int = INTERVAL_MS
    resolved: bool = False
    result: dict = field(default_factory=dict)
    user_id: int | None = None
    attendance_consumed: bool = False


class LivenessService:
    def __init__(self):
        self._sessions: dict[str, Challenge] = {}

    def issue(self, instruction: str = "blink") -> Challenge:
        self._purge()
        now = time.time()
        challenge = Challenge(
            id=secrets.token_urlsafe(16),
            instruction=instruction,
            created_at=now,
            expires_at=now + SESSION_TTL_S,
            hold_ms=randint(HOLD_MS_MIN, HOLD_MS_MAX),
            hold_frames=HOLD_FRAMES,
            blink_frames=BLINK_FRAMES,
            interval_ms=INTERVAL_MS,
        )
        self._sessions[challenge.id] = challenge
        return challenge

    def check(self, challenge_id: str, frames: list[bytes]) -> dict:
        self._purge()
        challenge = self._sessions.get(challenge_id)
        if challenge is None:
            return {"ok": False, "code": "unknown_challenge", "detail": "challenge expired or unknown"}
        if challenge.resolved:
            return {"ok": False, "code": "already_used", "detail": "challenge already consumed"}
        need = challenge.hold_frames + 3
        if len(frames) < need:
            return {
                "ok": False,
                "code": "too_few_frames",
                "detail": f"send hold frames then blink frames (at least {need})",
            }
        frames = frames[: challenge.hold_frames + challenge.blink_frames]
        images = [decode_image(f) for f in frames]
        split = min(challenge.hold_frames, len(images) - 3)
        hold_imgs = images[:split]
        action_imgs = images[split:]
        hold_ears = [ear_from_image(im) for im in hold_imgs]
        action_ears = [ear_from_image(im) for im in action_imgs]
        blink = timed_blink(hold_ears, action_ears)
        texture = replay_analysis(images)
        blink_ok = bool(blink.get("blink"))
        texture_ok = bool(texture.get("live"))
        live = blink_ok and texture_ok
        challenge.resolved = True
        challenge.result = {
            "ok": True,
            "live": live,
            "blink": blink,
            "texture": texture,
            "instruction": challenge.instruction,
        }
        return challenge.result

    def bind_user(self, challenge_id: str, user_id: int) -> None:
        challenge = self._sessions.get(challenge_id)
        if challenge is not None:
            challenge.user_id = user_id

    def consume_live(self, challenge_id: str, user_id: int) -> bool:
        self._purge()
        challenge = self._sessions.get(challenge_id)
        if challenge is None or challenge.attendance_consumed:
            return False
        if not challenge.result.get("live"):
            return False
        if challenge.user_id is not None and challenge.user_id != user_id:
            return False
        challenge.attendance_consumed = True
        return True

    def grant_for_tests(self, user_id: int) -> str:
        challenge = self.issue("blink")
        challenge.resolved = True
        challenge.user_id = user_id
        challenge.result = {"ok": True, "live": True}
        return challenge.id

    def _purge(self) -> None:
        now = time.time()
        dead = [k for k, v in self._sessions.items() if v.expires_at < now]
        for k in dead:
            del self._sessions[k]


liveness_service = LivenessService()
