"""In-process sliding-window limiter for login and check-in."""

from __future__ import annotations

import time
from collections import defaultdict

from fastapi import HTTPException, Request, status


class SlidingWindowLimiter:
    def __init__(self, max_calls: int, window_s: float) -> None:
        self.max_calls = max_calls
        self.window_s = window_s
        self._hits: dict[str, list[float]] = defaultdict(list)

    def check(self, key: str) -> None:
        from app.core.config import settings

        if not settings.rate_limit:
            return
        now = time.monotonic()
        recent = [stamp for stamp in self._hits[key] if now - stamp < self.window_s]
        if len(recent) >= self.max_calls:
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail="too many attempts, try again shortly",
            )
        recent.append(now)
        self._hits[key] = recent


login_limiter = SlidingWindowLimiter(max_calls=10, window_s=60.0)
checkin_limiter = SlidingWindowLimiter(max_calls=20, window_s=60.0)


def client_ip(request: Request) -> str:
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:
        return forwarded.split(",")[0].strip()
    if request.client:
        return request.client.host
    return "unknown"
