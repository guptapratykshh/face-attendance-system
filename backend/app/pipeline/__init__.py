"""Face processing pipeline: detection, alignment, embedding."""

from app.pipeline.align import align, align_arcface, align_margin
from app.pipeline.detector import Detection, FaceDetector, get_detector
from app.pipeline.errors import (
    FaceQualityTooLow,
    ImageDecodeError,
    MultipleFacesDetected,
    NoFaceDetected,
    PipelineError,
)
from app.pipeline.face_pipeline import (
    FacePipeline,
    FaceResult,
    clear_pipelines,
    decode_image,
    get_pipeline,
)

__all__ = [
    "Detection",
    "FaceDetector",
    "FacePipeline",
    "FaceQualityTooLow",
    "FaceResult",
    "ImageDecodeError",
    "MultipleFacesDetected",
    "NoFaceDetected",
    "PipelineError",
    "align",
    "align_arcface",
    "align_margin",
    "clear_pipelines",
    "decode_image",
    "get_detector",
    "get_pipeline",
]
