"""Serve the TAR@FAR evaluation payload the dashboard charts against."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse

from app.api.deps import require_lab
from app.core.config import settings
from app.db.models import User
from app.runtime import runtime

router = APIRouter(prefix="/metrics", tags=["metrics"])


@router.get("")
def metrics(_user: User = Depends(require_lab)) -> dict:
    if runtime.eval_report is None:
        runtime.load_report()
    if runtime.eval_report is None:
        raise HTTPException(404, detail="no evaluation report; run scripts/evaluate.py")
    return runtime.eval_report


@router.get("/report")
def report_file(_user: User = Depends(require_lab)) -> FileResponse:
    path = settings.reports_dir / "TAR_FAR_REPORT.md"
    if not path.exists():
        raise HTTPException(404, detail="TAR_FAR_REPORT.md has not been generated")
    return FileResponse(path, media_type="text/markdown", filename="TAR_FAR_REPORT.md")
