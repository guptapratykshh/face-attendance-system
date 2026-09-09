"""Encoder registry.

Encoders are cached per (name, checkpoint) so the API and the evaluation scripts share
one loaded model instead of paying the load cost per request.
"""

from __future__ import annotations

from pathlib import Path

from app.core.config import settings
from app.encoders.base import FaceEncoder, l2_normalize

_CACHE: dict[tuple[str, str | None], FaceEncoder] = {}

AVAILABLE = ("facenet", "arcface")


def get_encoder(
    name: str | None = None, checkpoint: Path | None = None, **kwargs
) -> FaceEncoder:
    """Return a cached encoder. `name` defaults to the configured encoder."""
    name = (name or settings.encoder).lower()
    if checkpoint is None and name == "facenet":
        checkpoint = settings.facenet_checkpoint
    key = (name, str(checkpoint) if checkpoint else None)
    if key in _CACHE:
        return _CACHE[key]

    if name in ("facenet", "facenet-finetuned"):
        from app.encoders.facenet import FaceNetEncoder

        encoder: FaceEncoder = FaceNetEncoder(checkpoint=checkpoint, device=settings.device, **kwargs)
    elif name in ("arcface", "arcface-w600k_r50", "insightface"):
        from app.encoders.arcface import ArcFaceEncoder

        encoder = ArcFaceEncoder(**kwargs)
    else:
        raise ValueError(f"unknown encoder {name!r}; expected one of {AVAILABLE}")

    _CACHE[key] = encoder
    return encoder


def clear_cache() -> None:
    _CACHE.clear()


__all__ = ["AVAILABLE", "FaceEncoder", "clear_cache", "get_encoder", "l2_normalize"]
