"""Lecture scan writes one present row per identity and exports the whole roster."""

import csv
import io

from app.core.clock import today_local
from app.runtime import runtime

from tests.helpers import png_bytes


def test_classroom_scan_deduplicates_and_exports_roster(client, auth, monkeypatch):
    base = "/api/v1"
    course = client.post(
        f"{base}/schedule/offerings", headers=auth, json={"name": "Computer Vision"}
    )
    assert course.status_code == 201, course.text
    course_id = course.json()["id"]
    lecture = client.post(
        f"{base}/schedule/occurrences",
        headers=auth,
        json={
            "offering_id": course_id,
            "title": "Lecture 1",
            "kind": "session",
            "day": today_local().isoformat(),
            "start": "00:00",
            "end": "23:59",
        },
    )
    assert lecture.status_code == 201, lecture.text
    lecture_id = lecture.json()["id"]
    image = png_bytes((20, 40, 80))
    people = []
    enrollment_ids = []
    for name in ("Student One", "Student Two"):
        person = client.post(f"{base}/persons", headers=auth, json={"name": name})
        assert person.status_code == 201, person.text
        person_id = person.json()["id"]
        people.append(person_id)
        enrolled = client.post(
            f"{base}/schedule/offerings/{course_id}/enrollments",
            headers=auth,
            json={"person_id": person_id},
        )
        assert enrolled.status_code == 201, enrolled.text
        enrollment_ids.append(enrolled.json()["id"])
    enrolled_face = client.post(
        f"{base}/persons/{people[0]}/enroll",
        headers=auth,
        files=[("images", ("face.png", image, "image/png"))],
    )
    assert enrolled_face.status_code == 200, enrolled_face.text
    face = runtime.pipeline.embed_single(image)
    monkeypatch.setattr(
        runtime.pipeline, "process", lambda *_args, **_kwargs: [face, face], raising=False
    )

    def scan():
        return client.post(
            f"{base}/classroom/{lecture_id}/scan",
            headers=auth,
            files={"image": ("class.png", image, "image/png")},
        )

    first = scan()
    assert first.status_code == 200, first.text
    assert first.json()["roster_size"] == 2
    assert first.json()["face_ready"] == 1
    assert first.json()["marked"] == 1
    assert sorted(f["status"] for f in first.json()["faces"]) == ["duplicate", "marked"]
    second = scan()
    assert second.status_code == 200, second.text
    assert second.json()["marked"] == 0
    assert second.json()["already_marked"] == 1

    attendance = client.get(f"{base}/attendance", headers=auth).json()
    assert (
        len(
            [
                r
                for r in attendance
                if r["occurrence_id"] == lecture_id and r["decision"] == "present"
            ]
        )
        == 1
    )
    removed = client.delete(f"{base}/schedule/enrollments/{enrollment_ids[0]}", headers=auth)
    assert removed.status_code == 204, removed.text
    exported = client.get(f"{base}/classroom/{lecture_id}/export", headers=auth)
    assert exported.status_code == 200, exported.text
    rows = list(csv.DictReader(io.StringIO(exported.text)))
    assert len(rows) == 2
    assert {row["student_name"]: row["status"] for row in rows} == {
        "Student One": "present",
        "Student Two": "not_seen",
    }


def test_classroom_requires_auth(client):
    assert client.get("/api/v1/classroom/1/export").status_code == 401
