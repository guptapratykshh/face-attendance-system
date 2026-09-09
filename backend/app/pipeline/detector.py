"""Face detection with SCRFD-10GF (InsightFace buffalo_l det_10g.onnx).

SCRFD returns a bounding box, a confidence score and five landmarks (both eyes, nose,
both mouth corners) per face. The landmarks are what make canonical alignment possible,
which matters more for embedding quality than the box itself.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from app.core.config import settings
from app.encoders.model_store import detector_path

# SCRFD's ONNX graph declares output shapes for a 640px input, so running it at another
# size emits a VerifyOutputSizes warning per tensor. The values are correct; only the
# static shape hint is stale.
_ORT_LOG_SEVERITY_ERROR = 3


def _quiet_onnxruntime() -> None:
    import onnxruntime as ort

    ort.set_default_logger_severity(_ORT_LOG_SEVERITY_ERROR)


@dataclass(frozen=True)
class Detection:
    """A single detected face in original-image pixel coordinates."""

    bbox: np.ndarray  # (4,) x1, y1, x2, y2
    score: float
    landmarks: np.ndarray  # (5, 2)

    @property
    def width(self) -> float:
        return float(self.bbox[2] - self.bbox[0])

    @property
    def height(self) -> float:
        return float(self.bbox[3] - self.bbox[1])

    @property
    def area(self) -> float:
        return self.width * self.height

    def as_dict(self) -> dict:
        return {
            "bbox": [round(float(v), 2) for v in self.bbox],
            "score": round(self.score, 4),
            "landmarks": [[round(float(x), 2), round(float(y), 2)] for x, y in self.landmarks],
        }


class FaceDetector:
    """Thin wrapper over InsightFace's SCRFD with a stable return type."""

    # SCRFD strides are 8/16/32, so the working size must be a multiple of 32.
    MIN_AUTO_SIZE = 256
    STRIDE = 32

    def __init__(
        self,
        det_size: int | None = None,
        det_thresh: float | None = None,
        auto_size: bool = True,
    ):
        from insightface.model_zoo.scrfd import SCRFD

        _quiet_onnxruntime()
        self.det_size = det_size or settings.det_size
        self.det_thresh = det_thresh if det_thresh is not None else settings.det_thresh
        # Detection cost scales with the working resolution, not the source image, so
        # small inputs (LFW is 250x250) are detected at a smaller size for a ~3.5x
        # speedup with no measured loss in detection rate.
        self.auto_size = auto_size
        self.model = SCRFD(model_file=str(detector_path()))
        # ctx_id < 0 selects CPU. SCRFD is small; CPU keeps memory free for the encoder.
        self.model.prepare(
            ctx_id=-1, det_thresh=self.det_thresh, input_size=(self.det_size, self.det_size)
        )

    def _input_size_for(self, image_rgb: np.ndarray) -> tuple[int, int]:
        if not self.auto_size:
            return (self.det_size, self.det_size)
        longest = max(image_rgb.shape[:2])
        rounded = self.STRIDE * ((longest + self.STRIDE - 1) // self.STRIDE)
        size = max(self.MIN_AUTO_SIZE, min(self.det_size, rounded))
        return (size, size)

    def detect(self, image_rgb: np.ndarray, max_num: int = 0) -> list[Detection]:
        """Detect faces in an RGB uint8 image, ordered by descending box area."""
        if image_rgb.ndim != 3 or image_rgb.shape[2] != 3:
            raise ValueError(f"expected (H, W, 3) RGB image, got {image_rgb.shape}")
        # SCRFD was trained on BGR input, matching OpenCV's channel order.
        bgr = np.ascontiguousarray(image_rgb[:, :, ::-1])
        boxes, kpss = self.model.detect(
            bgr, input_size=self._input_size_for(image_rgb), max_num=max_num, metric="default"
        )
        if boxes is None or len(boxes) == 0:
            return []

        detections = []
        for i, box in enumerate(boxes):
            landmarks = kpss[i] if kpss is not None else None
            if landmarks is None:
                continue
            detections.append(
                Detection(
                    bbox=np.asarray(box[:4], dtype=np.float32),
                    score=float(box[4]),
                    landmarks=np.asarray(landmarks, dtype=np.float32),
                )
            )
        detections.sort(key=lambda d: d.area, reverse=True)
        return detections


_DETECTOR: FaceDetector | None = None


def get_detector() -> FaceDetector:
    """Process-wide detector, loaded on first use."""
    global _DETECTOR
    if _DETECTOR is None:
        _DETECTOR = FaceDetector()
    return _DETECTOR
