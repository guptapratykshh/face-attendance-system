"""1:1 verification — two images, or one image against an enrolled person."""

from __future__ import annotations

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from sqlmodel import Session

from app.api.deps import get_runtime, require_lab, require_org
from app.api.routes._common import face_info, log_event, person_out, read_image
from app.api.schemas import VerifyPersonResponse, VerifyResponse
from app.core.org_ctx import belongs_to_org
from app.db.models import Organization, Person, User
from app.db.session import get_session
from app.encoders.base import FaceEncoder
from app.runtime import Runtime

router = APIRouter(tags=["verify"])


@router.post("/verify", response_model=VerifyResponse)
async def verify_pair(
    image_a: UploadFile = File(...),
    image_b: UploadFile = File(...),
    _user: User = Depends(require_lab),
    session: Session = Depends(get_session),
    rt: Runtime = Depends(get_runtime),
) -> VerifyResponse:
    a = rt.pipeline.embed_single(await read_image(image_a))
    b = rt.pipeline.embed_single(await read_image(image_b))
    similarity = float(FaceEncoder.similarity(a.embedding[None], b.embedding[None])[0])
    match = similarity >= rt.verify_threshold
    log_event(
        session,
        kind="verify",
        decision="match" if match else "no_match",
        similarity=similarity,
        encoder=rt.encoder_name,
        detail=f"pair threshold={rt.verify_threshold:.4f}",
    )
    return VerifyResponse(
        match=match,
        similarity=round(similarity, 4),
        threshold=rt.verify_threshold,
        far_target=rt.extra.get("target_far", 1e-3),
        encoder=rt.encoder_name,
        face_a=face_info(a),
        face_b=face_info(b),
    )


@router.post("/verify/person/{person_id}", response_model=VerifyPersonResponse)
async def verify_person(
    person_id: int,
    image: UploadFile = File(...),
    _user: User = Depends(require_lab),
    _org: Organization = Depends(require_org),
    session: Session = Depends(get_session),
    rt: Runtime = Depends(get_runtime),
) -> VerifyPersonResponse:
    person = belongs_to_org(session.get(Person, person_id), detail="person not found")
    probe = rt.gallery.embedding_of(person_id, org_id=person.org_id)
    if probe is None:
        raise HTTPException(404, detail="person has no embeddings for the active encoder")
    face = rt.pipeline.embed_single(await read_image(image))
    similarity = float(FaceEncoder.similarity(face.embedding[None], probe[None])[0])
    match = similarity >= rt.verify_threshold
    log_event(
        session,
        kind="verify",
        decision="match" if match else "no_match",
        person=person,
        similarity=similarity,
        encoder=rt.encoder_name,
    )
    return VerifyPersonResponse(
        match=match,
        similarity=round(similarity, 4),
        threshold=rt.verify_threshold,
        far_target=rt.extra.get("target_far", 1e-3),
        encoder=rt.encoder_name,
        person=person_out(person, session=session),
        face=face_info(face),
    )
