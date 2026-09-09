"""FastAPI application factory."""

from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from sqlmodel import select

from app.api.errors import register_exception_handlers
from app.api.routes import (
    assist,
    attendance,
    auth,
    events,
    holidays,
    identify,
    liveness,
    metrics,
    ops,
    orgs,
    persons,
    schedule,
    users,
    verify,
)
from app.api.routes import settings as office
from app.api.routes.auth import seed_admin
from app.api.schemas import HealthOut, ReadyOut
from app.core.config import settings
from app.core.org_ctx import reset_current_org_id, set_current_org_id
from app.core.security import decode_access_token
from app.db.models import User
from app.db.session import SessionLocal, init_db, seed_default_org, seed_office_settings
from app.gallery.index import FaceGallery
from app.pipeline.face_pipeline import get_pipeline
from app.runtime import runtime


def assert_boot_config() -> None:
    # Local SQLite keeps the old default secret so `uvicorn` works without a .env.
    # Compose/Postgres must set a real FRS_SECRET_KEY.
    if settings.is_sqlite:
        return
    if settings.secret_is_placeholder:
        raise RuntimeError(
            "FRS_SECRET_KEY is missing, shorter than 32 bytes, or still a placeholder. "
            "Set a production secret before starting the API."
        )


def _weights_ready() -> bool:
    if runtime.pipeline is not None:
        return True
    weights = settings.weights_dir
    if not weights.exists():
        return False
    return any(weights.glob("**/*.onnx")) or any(weights.glob("**/*.pt"))


def _boot() -> None:
    assert_boot_config()
    settings.ensure_dirs()
    init_db()
    with SessionLocal() as session:
        seed_admin(session)
        seed_office_settings(session)
        seed_default_org(session)

    runtime.load_report()
    pipeline = get_pipeline(runtime.encoder_name)
    runtime.pipeline = pipeline
    runtime.encoder_name = pipeline.encoder.name
    runtime.extra["target_far"] = settings.target_far
    runtime.gallery = FaceGallery(dim=pipeline.encoder.dim, encoder=runtime.encoder_name)
    with SessionLocal() as session:
        runtime.gallery.rebuild(session)


@asynccontextmanager
async def lifespan(_app: FastAPI):
    _boot()
    yield


def _org_id_from_request(request: Request) -> int | None:
    auth = request.headers.get("authorization") or ""
    header_org = request.headers.get("x-org-id")
    payload = None
    if auth.lower().startswith("bearer "):
        try:
            payload = decode_access_token(auth.split(" ", 1)[1])
        except Exception:
            payload = None
    if not payload:
        return None
    if payload.get("org") is not None:
        try:
            return int(payload["org"])
        except (TypeError, ValueError):
            return None
    if payload.get("admin") and header_org:
        try:
            return int(header_org)
        except (TypeError, ValueError):
            return None
    return None


def create_app(*, boot: bool = True) -> FastAPI:
    app = FastAPI(
        title="Face Recognition System",
        description="Employee attendance with FaceNet/ArcFace verification",
        version="0.2.0",
        lifespan=lifespan if boot else None,
    )
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.middleware("http")
    async def org_context_middleware(request: Request, call_next):
        token = set_current_org_id(_org_id_from_request(request))
        try:
            return await call_next(request)
        finally:
            reset_current_org_id(token)

    register_exception_handlers(app)

    prefix = settings.api_prefix
    app.include_router(auth.router, prefix=prefix)
    app.include_router(orgs.router, prefix=prefix)
    app.include_router(verify.router, prefix=prefix)
    app.include_router(persons.router, prefix=prefix)
    app.include_router(identify.router, prefix=prefix)
    app.include_router(liveness.router, prefix=prefix)
    app.include_router(metrics.router, prefix=prefix)
    app.include_router(events.router, prefix=prefix)
    app.include_router(attendance.router, prefix=prefix)
    app.include_router(ops.router, prefix=prefix)
    app.include_router(office.router, prefix=prefix)
    app.include_router(users.router, prefix=prefix)
    app.include_router(holidays.router, prefix=prefix)
    app.include_router(schedule.router, prefix=prefix)
    app.include_router(assist.router, prefix=prefix)

    @app.get("/health", response_model=HealthOut, tags=["health"])
    @app.get(f"{prefix}/health", response_model=HealthOut, tags=["health"])
    def health() -> HealthOut:
        rt = runtime
        return HealthOut(
            status="ok" if rt.pipeline is not None else "booting",
            encoder=rt.encoder_name,
            gallery_size=len(rt.gallery) if rt.gallery is not None else 0,
            verify_threshold=rt.verify_threshold,
            identify_threshold=rt.identify_threshold,
            device=settings.device,
        )

    @app.get("/ready", response_model=ReadyOut)
    @app.get(f"{prefix}/ready", response_model=ReadyOut)
    def ready() -> ReadyOut:
        db_status = "fail"
        detail = None
        try:
            with SessionLocal() as session:
                session.exec(select(User).limit(1)).first()
            db_status = "ok"
        except Exception as exc:  # pragma: no cover
            detail = str(exc)
        gallery_status = "ok" if runtime.gallery is not None else "fail"
        weights_status = "ok" if _weights_ready() else "fail"
        ok = db_status == "ok" and gallery_status == "ok" and weights_status == "ok"
        return ReadyOut(
            status="ok" if ok else "fail",
            database=db_status,
            weights=weights_status,
            gallery=gallery_status,
            encoder=runtime.encoder_name,
            detail=detail,
        )

    return app


app = create_app()
