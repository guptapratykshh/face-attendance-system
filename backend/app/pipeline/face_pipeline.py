"""Detect -> align -> embed, with explicit quality gating.

The pipeline deliberately refuses ambiguous input instead of guessing. For an access
control system, silently embedding the largest of three faces in a frame is a security
bug, so `require_single` surfaces that as an error the caller must handle.
"""

from __future__ import annotations

import io
from dataclasses import dataclass, field

import cv2
import numpy as np

from app.core.config import settings
from app.encoders import FaceEncoder, get_encoder
from app.pipeline.align import align
from app.pipeline.detector import Detection, get_detector
from app.pipeline.errors import (
    FaceQualityTooLow,
    ImageDecodeError,
    MultipleFacesDetected,
    NoFaceDetected,
)

# Encoders were trained on different crops; each declares the geometry it expects.
ALIGN_FOR_ENCODER = {
    "facenet": ("arcface", 160),
    "facenet-finetuned": ("arcface", 160),
    "arcface-w600k_r50": ("arcface", 112),
}

MIN_FACE_PIXELS = 40
MIN_LAPLACIAN_VAR = 12.0


@dataclass
class FaceResult:
    """One detected, aligned and embedded face."""

    embedding: np.ndarray
    detection: Detection
    crop: np.ndarray
    quality: dict = field(default_factory=dict)

    def as_dict(self) -> dict:
        return {**self.detection.as_dict(), "quality": self.quality}


def decode_image(data: bytes) -> np.ndarray:
    """Decode image bytes to an RGB uint8 array."""
    if not data:
        raise ImageDecodeError("empty image payload")
    if len(data) > settings.max_upload_bytes:
        raise ImageDecodeError(
            f"image exceeds {settings.max_upload_bytes // 1024 // 1024} MB limit"
        )
    array = np.frombuffer(data, dtype=np.uint8)
    bgr = cv2.imdecode(array, cv2.IMREAD_COLOR)
    if bgr is None:
        # Fall back to Pillow, which reads some formats OpenCV rejects.
        try:
            from PIL import Image

            with Image.open(io.BytesIO(data)) as im:
                return np.asarray(im.convert("RGB"))
        except Exception as exc:
            raise ImageDecodeError(f"unsupported or corrupt image: {exc}") from exc
    return cv2.cvtColor(bgr, cv2.COLOR_BGR2RGB)


def blur_score(gray_crop: np.ndarray) -> float:
    """Variance of the Laplacian: low values indicate an out-of-focus or upscaled face."""
    return float(cv2.Laplacian(gray_crop, cv2.CV_64F).var())


class FacePipeline:
    """Reusable detect/align/embed pipeline bound to one encoder."""

    def __init__(self, encoder: FaceEncoder | None = None, encoder_name: str | None = None):
        self.encoder = encoder or get_encoder(encoder_name)
        self.detector = get_detector()
        mode, size = ALIGN_FOR_ENCODER.get(self.encoder.name, ("arcface", self.encoder.input_size))
        self.align_mode = mode
        self.align_size = size

    @property
    def encoder_name(self) -> str:
        return self.encoder.name

    def detect(self, image_rgb: np.ndarray) -> list[Detection]:
        return self.detector.detect(image_rgb)

    def align_faces(self, image_rgb: np.ndarray, detections: list[Detection]) -> np.ndarray:
        crops = [
            align(
                image_rgb,
                landmarks=d.landmarks,
                bbox=d.bbox,
                size=self.align_size,
                mode=self.align_mode,
            )
            for d in detections
        ]
        return np.stack(crops) if crops else np.empty((0, self.align_size, self.align_size, 3), np.uint8)

    def _quality(self, detection: Detection, crop: np.ndarray) -> dict:
        gray = cv2.cvtColor(crop, cv2.COLOR_RGB2GRAY)
        return {
            "det_score": round(detection.score, 4),
            "face_pixels": int(min(detection.width, detection.height)),
            "blur_var": round(blur_score(gray), 2),
            "brightness": round(float(gray.mean()), 2),
        }

    def _check_quality(self, quality: dict, enforce: bool) -> None:
        if not enforce:
            return
        if quality["face_pixels"] < MIN_FACE_PIXELS:
            raise FaceQualityTooLow(
                f"face is only {quality['face_pixels']}px across; need >= {MIN_FACE_PIXELS}px",
                **quality,
            )
        if quality["blur_var"] < MIN_LAPLACIAN_VAR:
            raise FaceQualityTooLow(
                f"image is too blurry (laplacian variance {quality['blur_var']})", **quality
            )

    def process(
        self,
        image: bytes | np.ndarray,
        *,
        require_single: bool = True,
        enforce_quality: bool = True,
        max_faces: int | None = None,
    ) -> list[FaceResult]:
        """Run the full pipeline.

        Raises NoFaceDetected, and MultipleFacesDetected when `require_single` is set.
        """
        image_rgb = decode_image(image) if isinstance(image, bytes | bytearray) else image
        detections = self.detect(image_rgb)
        if not detections:
            raise NoFaceDetected("no face detected in the image")
        if require_single and len(detections) > 1:
            raise MultipleFacesDetected(len(detections))
        if max_faces is not None:
            detections = detections[:max_faces]

        crops = self.align_faces(image_rgb, detections)
        qualities = [self._quality(d, c) for d, c in zip(detections, crops, strict=True)]
        if require_single:
            self._check_quality(qualities[0], enforce_quality)

        embeddings = self.encoder.embed(crops)
        return [
            FaceResult(embedding=e, detection=d, crop=c, quality=q)
            for e, d, c, q in zip(embeddings, detections, crops, qualities, strict=True)
        ]

    def embed_single(self, image: bytes | np.ndarray, **kwargs) -> FaceResult:
        """Convenience wrapper for the one-face case used by verify/enroll."""
        return self.process(image, require_single=True, **kwargs)[0]

    def embed_aligned(self, crops: np.ndarray) -> np.ndarray:
        """Embed already-aligned crops, bypassing detection (used by the evaluation scripts)."""
        return self.encoder.embed(crops)


_PIPELINES: dict[str, FacePipeline] = {}


def get_pipeline(encoder_name: str | None = None) -> FacePipeline:
    """Process-wide pipeline cache keyed by encoder name."""
    key = encoder_name or settings.encoder
    if key not in _PIPELINES:
        _PIPELINES[key] = FacePipeline(encoder_name=encoder_name)
    return _PIPELINES[key]


def clear_pipelines() -> None:
    _PIPELINES.clear()
