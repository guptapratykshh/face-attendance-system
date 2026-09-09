"""Pipeline-level failures that map onto specific HTTP responses.

These are distinct exception types rather than a generic error because the API must tell
callers apart: "no face found" and "several faces found" are user-correctable and are
returned as 422, while a decode failure is a 400.
"""

from __future__ import annotations


class PipelineError(Exception):
    """Base class for recoverable pipeline failures."""

    code = "pipeline_error"


class ImageDecodeError(PipelineError):
    code = "image_decode_failed"


class NoFaceDetected(PipelineError):
    code = "no_face_detected"


class MultipleFacesDetected(PipelineError):
    code = "multiple_faces_detected"

    def __init__(self, count: int):
        super().__init__(f"expected exactly one face, found {count}")
        self.count = count


class FaceQualityTooLow(PipelineError):
    code = "face_quality_too_low"

    def __init__(self, reason: str, **details):
        super().__init__(reason)
        self.details = details
