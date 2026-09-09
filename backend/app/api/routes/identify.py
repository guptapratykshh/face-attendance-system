"""1:N identification against the enrolled gallery."""

from __future__ import annotations

from fastapi import APIRouter, Depends, File, Query, UploadFile
from sqlmodel import Session

from app.api.deps import get_runtime, require_lab, require_org
from app.api.routes._common import face_info, log_event, read_image
from app.api.schemas import IdentifyResponse, MatchOut
from app.core.org_ctx import gallery_allowed_ids
from app.db.models import Organization, Person, User
from app.db.session import get_session
from app.runtime import Runtime

router = APIRouter(tags=["identify"])


@router.post("/identify", response_model=IdentifyResponse)
async def identify(
    image: UploadFile = File(...),
    top_k: int = Query(default=5, ge=1, le=20),
    _user: User = Depends(require_lab),
    _org: Organization = Depends(require_org),
    session: Session = Depends(get_session),
    rt: Runtime = Depends(get_runtime),
) -> IdentifyResponse:
    face = rt.pipeline.embed_single(await read_image(image))
    allowed = gallery_allowed_ids(session)
    matches = rt.gallery.search(face.embedding, top_k=top_k, allowed_ids=allowed)
    identified = bool(matches) and matches[0].similarity >= rt.identify_threshold
    top = matches[0] if matches else None
    matched_person = session.get(Person, top.person_id) if identified and top else None
    log_event(
        session,
        kind="identify",
        decision="match" if identified else "no_match",
        person=matched_person,
        similarity=top.similarity if top else None,
        encoder=rt.encoder_name,
        detail=(
            top.name
            if top
            else "empty gallery"
            if len(rt.gallery) == 0
            else "below threshold"
        ),
    )
    gallery_size = (
        sum(1 for pid in rt.gallery.person_ids if allowed is None or pid in allowed)
        if allowed is not None
        else len(rt.gallery)
    )
    return IdentifyResponse(
        identified=identified,
        matches=[
            MatchOut(
                person_id=m.person_id,
                name=m.name,
                similarity=round(m.similarity, 4),
                n_embeddings=m.n_embeddings,
            )
            for m in matches
        ],
        threshold=rt.identify_threshold,
        encoder=rt.encoder_name,
        gallery_size=gallery_size,
        face=face_info(face),
    )
