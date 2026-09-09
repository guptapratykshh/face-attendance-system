"""Map pipeline exceptions onto HTTP responses."""

from __future__ import annotations

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from app.pipeline.errors import (
    FaceQualityTooLow,
    ImageDecodeError,
    MultipleFacesDetected,
    NoFaceDetected,
    PipelineError,
)


def _payload(exc: PipelineError, status_code: int) -> JSONResponse:
    body: dict = {"code": exc.code, "detail": str(exc)}
    if isinstance(exc, MultipleFacesDetected):
        body["count"] = exc.count
    if isinstance(exc, FaceQualityTooLow):
        body["quality"] = exc.details
    return JSONResponse(status_code=status_code, content=body)


def register_exception_handlers(app: FastAPI) -> None:
    @app.exception_handler(ImageDecodeError)
    async def decode_handler(_request: Request, exc: ImageDecodeError) -> JSONResponse:
        return _payload(exc, 400)

    @app.exception_handler(NoFaceDetected)
    async def no_face_handler(_request: Request, exc: NoFaceDetected) -> JSONResponse:
        return _payload(exc, 422)

    @app.exception_handler(MultipleFacesDetected)
    async def multi_handler(_request: Request, exc: MultipleFacesDetected) -> JSONResponse:
        return _payload(exc, 422)

    @app.exception_handler(FaceQualityTooLow)
    async def quality_handler(_request: Request, exc: FaceQualityTooLow) -> JSONResponse:
        return _payload(exc, 422)

    @app.exception_handler(PipelineError)
    async def pipeline_handler(_request: Request, exc: PipelineError) -> JSONResponse:
        return _payload(exc, 400)
