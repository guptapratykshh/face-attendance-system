"""Register 10 LFW sample identities as a local classroom demo and evaluate probes.

Run download_lfw.py first. Images, embeddings and the composite scan stay in ignored
local data; no real student photos are bundled with the repository.
"""

from __future__ import annotations

import argparse
import json
from datetime import timedelta
from pathlib import Path

import numpy as np
from app.core.attendance_policy import apply_org_type
from app.core.clock import now_local
from app.core.config import settings
from app.core.org_ctx import reset_current_org_id, set_current_org_id
from app.db.models import Enrollment, FaceEmbedding, Occurrence, Offering, Organization, Person
from app.db.session import SessionLocal, init_db
from app.gallery.index import FaceGallery
from app.pipeline.face_pipeline import MIN_FACE_PIXELS, MIN_LAPLACIAN_VAR, get_pipeline
from PIL import Image
from sqlmodel import select

DEMO_SLUG = "classroom-demo"


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--images-dir", type=Path, default=settings.lfw_images_dir)
    parser.add_argument("--encoder", default="arcface")
    parser.add_argument("--threshold", type=float, default=0.2557)
    args = parser.parse_args()
    if not settings.is_sqlite:
        parser.error("This local demo script requires SQLite; use the app UI for other databases.")
    if not args.images_dir.is_dir():
        parser.error(f"Missing {args.images_dir}. Run: python scripts/download_lfw.py")

    init_db()
    pipeline = get_pipeline(args.encoder)
    sample_dirs = sorted(
        (
            folder
            for folder in args.images_dir.iterdir()
            if folder.is_dir() and len(list(folder.glob("*.jpg"))) >= 2
        ),
        key=lambda folder: folder.name,
    )
    selected: list[tuple[str, Path, Path, np.ndarray]] = []
    for folder in sample_dirs:
        photos = sorted(folder.glob("*.jpg"))
        try:
            enrollment = pipeline.embed_single(photos[0].read_bytes())
            pipeline.embed_single(photos[1].read_bytes())
        except Exception:
            continue
        selected.append((folder.name, photos[0], photos[1], enrollment.embedding))
        if len(selected) == 10:
            break
    if len(selected) < 10:
        parser.error("Fewer than 10 sample identities have two usable face photos.")

    with SessionLocal() as session:
        org = session.exec(select(Organization).where(Organization.slug == DEMO_SLUG)).first()
        if org is None:
            org = Organization(name="Classroom Demo (LFW samples)", slug=DEMO_SLUG, tz=settings.tz)
            apply_org_type(org, "college")
            session.add(org)
            session.commit()
            session.refresh(org)
        token = set_current_org_id(int(org.id))
        try:
            course = session.exec(
                select(Offering).where(Offering.org_id == org.id, Offering.code == "CV-DEMO")
            ).first()
            if course is None:
                course = Offering(
                    org_id=int(org.id), name="Computer Vision Demo", code="CV-DEMO", kind="course"
                )
                session.add(course)
                session.commit()
                session.refresh(course)

            people: list[Person] = []
            for number, (source, _enroll_image, _probe_image, embedding) in enumerate(selected, 1):
                student_id = f"DEMO-{number:03d}"
                person = session.exec(
                    select(Person).where(Person.org_id == org.id, Person.employee_id == student_id)
                ).first()
                if person is None:
                    person = Person(
                        org_id=int(org.id),
                        name=f"Demo Student {number:02d}",
                        employee_id=student_id,
                        notes=f"LFW sample identity: {source}. Research demo only.",
                    )
                    session.add(person)
                    session.commit()
                    session.refresh(person)
                face = session.exec(
                    select(FaceEmbedding).where(
                        FaceEmbedding.person_id == person.id,
                        FaceEmbedding.encoder == pipeline.encoder_name,
                    )
                ).first()
                if face is None:
                    session.add(
                        FaceEmbedding(
                            person_id=int(person.id),
                            encoder=pipeline.encoder_name,
                            dim=len(embedding),
                            vector=np.asarray(embedding, dtype=np.float32).tobytes(),
                            quality_json=json.dumps({"source": "LFW sample", "identity": source}),
                        )
                    )
                enrolled = session.exec(
                    select(Enrollment).where(
                        Enrollment.person_id == person.id, Enrollment.offering_id == course.id
                    )
                ).first()
                if enrolled is None:
                    session.add(
                        Enrollment(
                            org_id=int(org.id), person_id=int(person.id), offering_id=int(course.id)
                        )
                    )
                people.append(person)
            session.commit()

            now = now_local(session)
            start, end = now - timedelta(minutes=5), now + timedelta(minutes=55)
            lecture = session.exec(
                select(Occurrence).where(
                    Occurrence.org_id == org.id,
                    Occurrence.offering_id == course.id,
                    Occurrence.day == now.date(),
                )
            ).first()
            if lecture is None:
                lecture = Occurrence(
                    org_id=int(org.id),
                    offering_id=int(course.id),
                    kind="session",
                    title="Classroom Demo",
                    day=now.date(),
                    start=start.strftime("%H:%M"),
                    end=end.strftime("%H:%M"),
                    overnight=end.date() > now.date(),
                )
                session.add(lecture)
                session.commit()
                session.refresh(lecture)
            else:
                lecture.start = start.strftime("%H:%M")
                lecture.end = end.strftime("%H:%M")
                lecture.overnight = end.date() > now.date()
                session.add(lecture)
                session.commit()

            gallery = FaceGallery(dim=pipeline.encoder.dim, encoder=pipeline.encoder_name)
            gallery.rebuild(session)
            ids = {int(person.id) for person in people}
            correct = rejected = wrong = 0
            for person, (_source, _enroll_image, probe_image, _embedding) in zip(
                people, selected, strict=True
            ):
                probe = pipeline.embed_single(probe_image.read_bytes())
                matches = gallery.search(probe.embedding, top_k=1, allowed_ids=ids)
                hit = matches[0] if matches and matches[0].similarity >= args.threshold else None
                if hit is None:
                    rejected += 1
                elif hit.person_id == person.id:
                    correct += 1
                else:
                    wrong += 1
            unknown_sources = [
                folder for folder in sample_dirs if folder.name not in {row[0] for row in selected}
            ][:10]
            unknown_false_accepts = unknown_tested = 0
            for folder in unknown_sources:
                try:
                    probe = pipeline.embed_single(sorted(folder.glob("*.jpg"))[0].read_bytes())
                except Exception:
                    continue
                unknown_tested += 1
                matches = gallery.search(probe.embedding, top_k=1, allowed_ids=ids)
                if matches and matches[0].similarity >= args.threshold:
                    unknown_false_accepts += 1

            canvas = Image.new("RGB", (750, 1000), "#ddd")
            for i, (_source, _enroll_image, probe_image, _embedding) in enumerate(selected):
                with Image.open(probe_image) as photo:
                    canvas.paste(
                        photo.convert("RGB").resize((250, 250)), ((i % 3) * 250, (i // 3) * 250)
                    )
            collage = settings.data_dir / "classroom_demo_scan.jpg"
            canvas.save(collage, quality=92)
            composite_faces = pipeline.process(
                collage.read_bytes(), require_single=False, enforce_quality=False
            )
            seen_tiles: set[int] = set()
            composite_correct = composite_wrong = composite_unknown = composite_low_quality = 0
            composite_extra = 0
            for face in composite_faces:
                x1, y1, x2, y2 = face.detection.bbox
                tile = int((y1 + y2) / 2 // 250) * 3 + int((x1 + x2) / 2 // 250)
                if tile >= len(people) or tile in seen_tiles:
                    composite_extra += 1
                    continue
                seen_tiles.add(tile)
                if (
                    face.quality.get("face_pixels", 0) < MIN_FACE_PIXELS
                    or face.quality.get("blur_var", 0) < MIN_LAPLACIAN_VAR
                ):
                    composite_low_quality += 1
                    continue
                matches = gallery.search(face.embedding, top_k=1, allowed_ids=ids)
                hit = matches[0] if matches and matches[0].similarity >= args.threshold else None
                if hit is None:
                    composite_unknown += 1
                elif hit.person_id == people[tile].id:
                    composite_correct += 1
                else:
                    composite_wrong += 1
            composite_missed = len(people) - len(seen_tiles)
            report = settings.reports_dir / "CLASSROOM_EVALUATION.md"
            false_accept_line = (
                f"- False accept rate on this tiny unregistered set: {unknown_false_accepts / unknown_tested:.1%}.\n\n"
                if unknown_tested
                else "- No usable unregistered probes.\n\n"
            )
            report.write_text(
                "# Classroom attendance demo evaluation\n\n"
                f"Generated: {now.isoformat()}\n\n"
                f"Demo organization: `{DEMO_SLUG}`. Encoder: `{pipeline.encoder_name}`. "
                f"Threshold: {args.threshold:.4f} (LFW-calibrated operating point).\n\n"
                "## Registered sample identities\n\n"
                f"{len(people)} fictional student records each linked to one LFW face image and enrolled in one lecture. "
                "They are **not real students**. Their source images stay local and are not committed.\n\n"
                "## Small probe check\n\n"
                f"- Known held-out photos: {correct}/10 correctly identified, {rejected}/10 rejected, {wrong}/10 assigned to a different registered identity.\n"
                f"- Unregistered photos: {unknown_false_accepts}/{unknown_tested} falsely accepted.\n"
                f"- Known identification accuracy: {correct / 10:.1%}.\n"
                + false_accept_line
                + "## Composite classroom scan\n\n"
                + f"A 3 × 4 grid of the ten held-out photos produced {len(composite_faces)} face detections. "
                + f"Correctly assigned: {composite_correct}/10; assigned to another demo identity: {composite_wrong}; "
                + f"below threshold: {composite_unknown}; low quality: {composite_low_quality}; "
                + f"missed tiles: {composite_missed}; extra detections: {composite_extra}. "
                + f"Detection recall: {len(seen_tiles) / 10:.1%}; correct-assignment recall: {composite_correct / 10:.1%}.\n\n"
                + "These small LFW checks are smoke tests, not an independent classroom accuracy estimate: "
                "the operating threshold was also calibrated on LFW, and a composite photo does not reproduce classroom distance, occlusion, lighting, motion, or camera angle. "
                "A real evaluation needs consented student enrollment images and separately labeled lecture frames. "
                "Measure face detection recall, present-student recall, false matches, missed students, and per-lecture attendance precision. "
                "A still photo can also be replayed or manipulated; this batch route has no liveness check. "
                "Use consented data, restrict access to the attendance log, and manually review unknown and not-seen students. "
                "A single photo cannot establish absence.\n"
            )
            print(
                f"Demo ready: org={DEMO_SLUG} ({org.id}), lecture={lecture.id}, students={len(people)}"
            )
            print(f"Composite: {collage}")
            print(f"Evaluation: {report}")
        finally:
            reset_current_org_id(token)


if __name__ == "__main__":
    main()
