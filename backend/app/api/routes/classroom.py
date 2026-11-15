"""One classroom photo -> roster-scoped, per-lecture attendance."""

from __future__ import annotations

import csv
import io
from collections import defaultdict

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
from sqlmodel import Session, select

from app.api.deps import get_runtime, require_org, require_staff
from app.api.routes._common import read_image
from app.core.attendance_policy import is_late_for, occurrence_is_open
from app.core.clock import today_local
from app.core.org_ctx import belongs_to_org, gallery_allowed_ids, require_org_id, scoped
from app.db.models import Attendance, Enrollment, Occurrence, Organization, Person, User
from app.db.session import get_session
from app.pipeline.face_pipeline import MIN_FACE_PIXELS, MIN_LAPLACIAN_VAR
from app.runtime import Runtime

router = APIRouter(prefix="/classroom", tags=["classroom"])


class ScanFace(BaseModel):
    bbox: list[float]
    status: str
    person_id: int | None = None
    name: str | None = None
    similarity: float | None = None
    quality: dict = Field(default_factory=dict)


class ScanResult(BaseModel):
    occurrence_id: int
    title: str
    roster_size: int
    face_ready: int
    detected: int
    marked: int
    already_marked: int
    faces: list[ScanFace]


def _lecture(session: Session, occurrence_id: int) -> Occurrence:
    occurrence = belongs_to_org(
        session.get(Occurrence, occurrence_id), detail="occurrence_not_found"
    )
    if occurrence.kind != "session" or occurrence.offering_id is None:
        raise HTTPException(400, detail="classroom_requires_course_session")
    return occurrence


def _roster(session: Session, occurrence: Occurrence) -> dict[int, Person]:
    enrollments = session.exec(
        scoped(
            select(Enrollment).where(Enrollment.offering_id == occurrence.offering_id), Enrollment
        )
    ).all()
    roster: dict[int, Person] = {}
    for enrollment in enrollments:
        person = session.get(Person, enrollment.person_id)
        if person is not None and person.is_active and person.org_id == require_org_id():
            roster[int(person.id)] = person
    return roster


@router.post("/{occurrence_id}/scan", response_model=ScanResult)
async def scan_classroom(
    occurrence_id: int,
    image: UploadFile = File(...),
    _staff: User = Depends(require_staff),
    _org: Organization = Depends(require_org),
    session: Session = Depends(get_session),
    rt: Runtime = Depends(get_runtime),
) -> ScanResult:
    occurrence = _lecture(session, occurrence_id)
    if occurrence.day != today_local(session) or not occurrence_is_open(occurrence, session):
        raise HTTPException(400, detail="lecture_not_open")
    roster = _roster(session, occurrence)
    if not roster:
        raise HTTPException(400, detail="class_roster_empty")
    allowed = set(roster) & set(gallery_allowed_ids(session) or ())
    face_ready = len(
        allowed
        & {
            person_id
            for person_id, org_id in zip(rt.gallery.person_ids, rt.gallery.org_ids, strict=True)
            if org_id == require_org_id()
        }
    )
    if face_ready == 0:
        raise HTTPException(400, detail="class_faces_not_enrolled")

    # Classroom input is intentionally multi-face. Quality is checked for each face,
    # so one blurry student does not discard the whole photo.
    faces = rt.pipeline.process(
        await read_image(image), require_single=False, enforce_quality=False
    )
    output: list[ScanFace] = []
    candidates: dict[int, list[tuple[int, float]]] = defaultdict(list)
    for face in faces:
        bbox = [round(float(v), 2) for v in face.detection.bbox]
        quality = face.quality
        if (
            quality.get("face_pixels", 0) < MIN_FACE_PIXELS
            or quality.get("blur_var", 0) < MIN_LAPLACIAN_VAR
        ):
            output.append(ScanFace(bbox=bbox, status="low_quality", quality=quality))
            continue
        matches = rt.gallery.search(face.embedding, top_k=1, allowed_ids=allowed)
        hit = matches[0] if matches else None
        if hit is None or hit.similarity < rt.identify_threshold:
            output.append(
                ScanFace(
                    bbox=bbox,
                    status="unknown",
                    similarity=round(hit.similarity, 4) if hit else None,
                    quality=quality,
                )
            )
            continue
        index = len(output)
        output.append(
            ScanFace(
                bbox=bbox,
                status="candidate",
                person_id=hit.person_id,
                name=roster[hit.person_id].name,
                similarity=round(hit.similarity, 4),
                quality=quality,
            )
        )
        candidates[hit.person_id].append((index, float(hit.similarity)))

    marked = already_marked = 0
    for person_id, hits in candidates.items():
        best_index, best_similarity = max(hits, key=lambda item: item[1])
        for index, _score in hits:
            if index != best_index:
                output[index].status = "duplicate"
        existing = session.exec(
            scoped(
                select(Attendance).where(
                    Attendance.occurrence_id == occurrence_id,
                    Attendance.person_id == person_id,
                    Attendance.decision == "present",
                ),
                Attendance,
            )
        ).first()
        if existing:
            output[best_index].status = "already_marked"
            already_marked += 1
            continue
        person = roster[person_id]
        linked = session.exec(select(User).where(User.person_id == person_id)).first()
        session.add(
            Attendance(
                org_id=require_org_id(),
                person_id=person_id,
                user_id=int(linked.id) if linked else None,
                occurrence_id=occurrence_id,
                site_id=occurrence.site_id,
                decision="present",
                similarity=best_similarity,
                encoder=rt.encoder_name,
                source="classroom",
                late=is_late_for(session, person=person, occurrence=occurrence),
            )
        )
        output[best_index].status = "marked"
        marked += 1
    session.commit()
    return ScanResult(
        occurrence_id=occurrence_id,
        title=occurrence.title,
        roster_size=len(roster),
        face_ready=face_ready,
        detected=len(faces),
        marked=marked,
        already_marked=already_marked,
        faces=output,
    )


@router.get("/{occurrence_id}/export")
def export_classroom(
    occurrence_id: int,
    _staff: User = Depends(require_staff),
    _org: Organization = Depends(require_org),
    session: Session = Depends(get_session),
) -> StreamingResponse:
    occurrence = _lecture(session, occurrence_id)
    roster = _roster(session, occurrence)
    attendance = session.exec(
        scoped(
            select(Attendance).where(
                Attendance.occurrence_id == occurrence_id, Attendance.decision == "present"
            ),
            Attendance,
        )
    ).all()
    present = {row.person_id: row for row in attendance}
    # Keep a student's historical mark visible even if staff later remove them
    # from the course roster or deactivate their profile.
    for person_id in present:
        if person_id not in roster:
            person = session.get(Person, person_id)
            if person is not None and person.org_id == require_org_id():
                roster[person_id] = person
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(
        [
            "lecture_id",
            "lecture",
            "date",
            "student_id",
            "student_name",
            "status",
            "marked_at",
            "source",
            "similarity",
        ]
    )
    for person_id, person in sorted(
        roster.items(), key=lambda item: (item[1].name.lower(), item[0])
    ):
        row = present.get(person_id)
        writer.writerow(
            [
                occurrence_id,
                occurrence.title,
                occurrence.day.isoformat(),
                person.employee_id or person_id,
                person.name,
                "present" if row else "not_seen",
                row.created_at.isoformat() if row else "",
                row.source if row else "",
                round(float(row.similarity), 4) if row and row.similarity is not None else "",
            ]
        )
    output.seek(0)
    return StreamingResponse(
        iter([output.getvalue()]),
        media_type="text/csv",
        headers={
            "Content-Disposition": f'attachment; filename="lecture-{occurrence_id}-attendance.csv"'
        },
    )
