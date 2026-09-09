"""Auth, verify, enroll, identify, metrics, events."""

from __future__ import annotations

from sqlmodel import select

from app.db import session as db_session
from app.db.models import Organization
from tests.helpers import png_bytes


def _default_slug() -> str:
    with db_session.SessionLocal() as session:
        org = session.exec(select(Organization).order_by(Organization.id)).first()
        assert org is not None and org.slug
        return org.slug


def _login(client, username: str, password: str = "password1", org: str | None = None):
    return client.post(
        "/api/v1/auth/login",
        json={"username": username, "password": password, "org": org or _default_slug()},
    )


def test_login_ok(client):
    res = client.post("/api/v1/auth/login", json={"username": "admin", "password": "admin1234"})
    assert res.status_code == 200
    assert res.json()["access_token"]


def test_login_bad_password(client):
    res = client.post("/api/v1/auth/login", json={"username": "admin", "password": "nope"})
    assert res.status_code == 401


def test_me_requires_auth(client):
    assert client.get("/api/v1/auth/me").status_code == 401


def test_register_and_me(client):
    res = client.post(
        "/api/v1/auth/register",
        json={"username": "alice", "password": "password1", "name": "Alice Liddell"},
    )
    assert res.status_code == 201, res.text
    body = res.json()
    assert body["username"] == "alice"
    assert body["is_admin"] is False
    assert body["person"]["name"] == "Alice Liddell"
    assert body["person"]["face_ready"] is False
    token = _login(client, "alice").json()
    me = client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {token['access_token']}"})
    assert me.json()["username"] == "alice"
    assert me.json()["person"]["n_embeddings"] == 0

    forbidden = client.get("/api/v1/persons", headers={"Authorization": f"Bearer {token['access_token']}"})
    assert forbidden.status_code == 403


def test_health(client):
    res = client.get("/health")
    assert res.status_code == 200
    assert res.json()["encoder"] == "fake"


def test_metrics(client, auth):
    res = client.get("/api/v1/metrics", headers=auth)
    assert res.status_code == 200
    assert res.json()["served_encoder"] == "fake"


def test_verify_same_image_matches(client, auth):
    img = png_bytes((40, 80, 120))
    res = client.post(
        "/api/v1/verify",
        headers=auth,
        files={"image_a": ("a.png", img, "image/png"), "image_b": ("b.png", img, "image/png")},
    )
    assert res.status_code == 200, res.text
    body = res.json()
    assert body["match"] is True
    assert body["similarity"] > 0.99


def test_verify_different_images(client, auth):
    res = client.post(
        "/api/v1/verify",
        headers=auth,
        files={
            "image_a": ("a.png", png_bytes((10, 10, 10)), "image/png"),
            "image_b": ("b.png", png_bytes((240, 10, 10)), "image/png"),
        },
    )
    assert res.status_code == 200
    # Fake encoder still produces somewhat similar unit vectors; just assert a score is returned.
    assert "similarity" in res.json()


def test_enroll_identify_roundtrip(client, auth):
    created = client.post("/api/v1/persons", headers=auth, json={"name": "Ada Lovelace", "employee_id": "E1"})
    assert created.status_code == 201
    pid = created.json()["id"]
    img = png_bytes((12, 34, 56))
    enrolled = client.post(
        f"/api/v1/persons/{pid}/enroll",
        headers=auth,
        files=[("images", ("face.png", img, "image/png"))],
    )
    assert enrolled.status_code == 200
    assert enrolled.json()["n_embeddings"] == 1

    ident = client.post(
        "/api/v1/identify",
        headers=auth,
        files={"image": ("probe.png", img, "image/png")},
    )
    assert ident.status_code == 200, ident.text
    body = ident.json()
    assert body["identified"] is True
    assert body["matches"][0]["person_id"] == pid

    events = client.get("/api/v1/events", headers=auth)
    kinds = {e["kind"] for e in events.json()}
    assert "enroll" in kinds
    assert "identify" in kinds


def test_update_and_delete_person(client, auth):
    created = client.post(
        "/api/v1/persons",
        headers=auth,
        json={"name": "Grace Hopper", "employee_id": "E2", "notes": "navy"},
    )
    assert created.status_code == 201
    pid = created.json()["id"]
    img = png_bytes((9, 9, 9))
    client.post(
        f"/api/v1/persons/{pid}/enroll",
        headers=auth,
        files=[("images", ("face.png", img, "image/png"))],
    )

    patched = client.patch(
        f"/api/v1/persons/{pid}",
        headers=auth,
        json={"name": "Rear Admiral Hopper", "employee_id": "NAVY-1", "notes": "COBOL"},
    )
    assert patched.status_code == 200, patched.text
    body = patched.json()
    assert body["name"] == "Rear Admiral Hopper"
    assert body["employee_id"] == "NAVY-1"
    assert body["notes"] == "COBOL"

    ident = client.post(
        "/api/v1/identify",
        headers=auth,
        files={"image": ("probe.png", img, "image/png")},
    )
    assert ident.json()["matches"][0]["name"] == "Rear Admiral Hopper"

    deleted = client.delete(f"/api/v1/persons/{pid}", headers=auth)
    assert deleted.status_code == 204
    still = client.get(f"/api/v1/persons/{pid}", headers=auth)
    assert still.status_code == 200
    assert still.json()["is_active"] is False
    remaining = client.get("/api/v1/persons", headers=auth).json()
    assert all(p["id"] != pid for p in remaining)
    ghost = client.post(
        "/api/v1/identify",
        headers=auth,
        files={"image": ("probe.png", img, "image/png")},
    )
    assert all(m["person_id"] != pid for m in ghost.json()["matches"])
    events = client.get("/api/v1/events", headers=auth).json()
    kinds = {e["kind"] for e in events}
    decisions = {e["decision"] for e in events}
    assert "person" in kinds
    assert "updated" in decisions
    assert "deactivated" in decisions


def test_admin_can_give_person_a_login(client, auth):
    created = client.post("/api/v1/persons", headers=auth, json={"name": "Rohan"})
    pid = created.json()["id"]
    listed = client.get("/api/v1/persons", headers=auth).json()
    hit = next(p for p in listed if p["id"] == pid)
    assert hit["username"] is None

    given = client.post(
        f"/api/v1/persons/{pid}/login",
        headers=auth,
        json={"username": "rohan", "password": "password1"},
    )
    assert given.status_code == 200, given.text
    assert given.json()["username"] == "rohan"

    token = _login(client, "rohan")
    assert token.status_code == 200
    me = client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {token.json()['access_token']}"})
    assert me.json()["is_admin"] is False
    assert me.json()["person"]["id"] == pid


def test_unauthenticated_verify(client):
    img = png_bytes((1, 2, 3))
    res = client.post(
        "/api/v1/verify",
        files={"image_a": ("a.png", img, "image/png"), "image_b": ("b.png", img, "image/png")},
    )
    assert res.status_code == 401


def test_employee_attendance_requires_enrolled_face(client):
    client.post(
        "/api/v1/auth/register",
        json={"username": "bob", "password": "password1", "name": "Bob Builder", "employee_id": "E-BOB"},
    )
    token = _login(client, "bob").json()["access_token"]
    emp = {"Authorization": f"Bearer {token}"}
    img = png_bytes((12, 34, 56))
    missing = client.post(
        "/api/v1/attendance/check-in",
        headers=emp,
        files={"image": ("face.png", img, "image/png")},
    )
    assert missing.status_code == 400
    assert missing.json()["detail"] == "face_not_enrolled"


def test_employee_check_in_and_once_per_day(client, auth):
    client.post(
        "/api/v1/auth/register",
        json={"username": "carol", "password": "password1", "name": "Carol Danvers"},
    )
    emp_token = _login(client, "carol").json()["access_token"]
    emp = {"Authorization": f"Bearer {emp_token}"}
    me = client.get("/api/v1/auth/me", headers=emp).json()
    pid = me["person"]["id"]
    img = png_bytes((20, 40, 80))
    enrolled = client.post(
        f"/api/v1/persons/{pid}/enroll",
        headers=auth,
        files=[("images", ("face.png", img, "image/png"))],
    )
    assert enrolled.status_code == 200, enrolled.text

    first = client.post(
        "/api/v1/attendance/check-in",
        headers=emp,
        files={"image": ("probe.png", img, "image/png")},
    )
    assert first.status_code == 200, first.text
    assert first.json()["decision"] == "present"
    assert first.json()["already_marked"] is False

    second = client.post(
        "/api/v1/attendance/check-in",
        headers=emp,
        files={"image": ("probe.png", img, "image/png")},
    )
    assert second.status_code == 200
    assert second.json()["already_marked"] is True
    assert second.json()["id"] == first.json()["id"]

    mine = client.get("/api/v1/attendance/me", headers=emp).json()
    assert len([r for r in mine if r["decision"] == "present"]) == 1

    listed = client.get("/api/v1/attendance", headers=auth)
    assert listed.status_code == 200
    assert any(r["person_name"] == "Carol Danvers" for r in listed.json())

    as_emp = client.get("/api/v1/attendance", headers=emp)
    assert as_emp.status_code == 403

    today = client.get("/api/v1/attendance/today", headers=emp)
    assert today.status_code == 200
    assert today.json()["decision"] == "present"

    out = client.post("/api/v1/attendance/check-out", headers=emp)
    assert out.status_code == 200, out.text
    assert out.json()["checked_out_at"] is not None


def test_unique_employee_id(client, auth):
    a = client.post("/api/v1/persons", headers=auth, json={"name": "One", "employee_id": "DUP-1"})
    assert a.status_code == 201
    b = client.post("/api/v1/persons", headers=auth, json={"name": "Two", "employee_id": "DUP-1"})
    assert b.status_code == 409


def test_deactivated_person_cannot_punch(client, auth):
    client.post(
        "/api/v1/auth/register",
        json={"username": "dana", "password": "password1", "name": "Dana Scully"},
    )
    emp_token = _login(client, "dana").json()["access_token"]
    emp = {"Authorization": f"Bearer {emp_token}"}
    pid = client.get("/api/v1/auth/me", headers=emp).json()["person"]["id"]
    img = png_bytes((33, 44, 55))
    assert client.post(
        f"/api/v1/persons/{pid}/enroll",
        headers=auth,
        files=[("images", ("face.png", img, "image/png"))],
    ).status_code == 200
    assert client.delete(f"/api/v1/persons/{pid}", headers=auth).status_code == 204
    denied = client.post(
        "/api/v1/attendance/check-in",
        headers=emp,
        files={"image": ("probe.png", img, "image/png")},
    )
    assert denied.status_code == 403
    assert denied.json()["detail"] == "account_deactivated"


def test_liveness_gated_check_in(client, auth):
    from app.core.config import settings
    from app.liveness.service import liveness_service

    client.post(
        "/api/v1/auth/register",
        json={"username": "eve", "password": "password1", "name": "Eve Polastri"},
    )
    emp_token = _login(client, "eve").json()["access_token"]
    emp = {"Authorization": f"Bearer {emp_token}"}
    me = client.get("/api/v1/auth/me", headers=emp).json()
    pid = me["person"]["id"]
    img = png_bytes((8, 16, 32))
    client.post(
        f"/api/v1/persons/{pid}/enroll",
        headers=auth,
        files=[("images", ("face.png", img, "image/png"))],
    )
    settings.require_liveness = True
    try:
        missing = client.post(
            "/api/v1/attendance/check-in",
            headers=emp,
            files={"image": ("probe.png", img, "image/png")},
        )
        assert missing.status_code == 400
        assert missing.json()["detail"] == "liveness_required"
        challenge_id = liveness_service.grant_for_tests(me["id"])
        ok = client.post(
            "/api/v1/attendance/check-in",
            headers=emp,
            data={"challenge_id": challenge_id},
            files={"image": ("probe.png", img, "image/png")},
        )
        assert ok.status_code == 200, ok.text
        assert ok.json()["decision"] == "present"
    finally:
        settings.require_liveness = False


def test_register_disabled(client, monkeypatch):
    from app.core.config import settings

    monkeypatch.setattr(settings, "allow_public_register", False)
    res = client.post(
        "/api/v1/auth/register",
        json={"username": "blocked", "password": "password1", "name": "Blocked"},
    )
    assert res.status_code == 403


def test_csv_import_and_kiosk(client, auth):
    csv_body = "name,employee_id,email\nImported Person,IMP-1,imp@example.com\n"
    imported = client.post(
        "/api/v1/persons/import",
        headers=auth,
        files={"file": ("people.csv", csv_body, "text/csv")},
    )
    assert imported.status_code == 200, imported.text
    assert imported.json()["created"] == 1
    people = client.get("/api/v1/persons", headers=auth).json()
    person = next(p for p in people if p["employee_id"] == "IMP-1")
    img = png_bytes((70, 80, 90))
    client.post(
        f"/api/v1/persons/{person['id']}/enroll",
        headers=auth,
        files=[("images", ("face.png", img, "image/png"))],
    )
    punch = client.post(
        "/api/v1/attendance/kiosk",
        headers=auth,
        files={"image": ("probe.png", img, "image/png")},
    )
    assert punch.status_code == 200, punch.text
    assert punch.json()["decision"] == "present"
    assert punch.json()["source"] == "kiosk"


def test_ops_summary(client, auth):
    res = client.get("/api/v1/ops/summary", headers=auth)
    assert res.status_code == 200
    body = res.json()
    assert "pending_faces" in body
    assert "present_today" in body


def test_ready(client):
    res = client.get("/ready")
    assert res.status_code == 200
    assert res.json()["database"] == "ok"
    assert res.json()["gallery"] == "ok"


def test_hr_and_operator_roles(client, default_org_id):
    from app.core.security import hash_password
    from app.db import session as db_session
    from app.db.models import User

    with db_session.SessionLocal() as session:
        session.add(
            User(
                username="hr1",
                hashed_password=hash_password("password1"),
                is_admin=False,
                role="hr",
                org_id=default_org_id,
            )
        )
        session.add(
            User(
                username="op1",
                hashed_password=hash_password("password1"),
                is_admin=False,
                role="operator",
                org_id=default_org_id,
            )
        )
        session.commit()
    hr = _login(client, "hr1").json()
    op = _login(client, "op1").json()
    hr_h = {"Authorization": f"Bearer {hr['access_token']}"}
    op_h = {"Authorization": f"Bearer {op['access_token']}"}
    assert client.get("/api/v1/persons", headers=hr_h).status_code == 200
    assert client.get("/api/v1/ops/summary", headers=hr_h).status_code == 200
    assert client.get("/api/v1/metrics", headers=hr_h).status_code == 403
    assert client.get("/api/v1/persons", headers=op_h).status_code == 403
    assert client.get("/api/v1/metrics", headers=op_h).status_code == 200
    assert client.get("/api/v1/attendance", headers=op_h).status_code == 403


def test_staff_admin_timeline_holidays_and_export(client, auth):
    created = client.post(
        "/api/v1/users",
        headers=auth,
        json={"username": "hrdesk", "password": "password1", "role": "hr"},
    )
    assert created.status_code == 201, created.text
    assert created.json()["role"] == "hr"
    listed = client.get("/api/v1/users", headers=auth)
    assert listed.status_code == 200
    assert any(u["username"] == "hrdesk" for u in listed.json())

    person = client.post("/api/v1/persons", headers=auth, json={"name": "Ada", "department": "Eng", "office": "HQ"}).json()
    timeline = client.get(f"/api/v1/persons/{person['id']}/timeline", headers=auth)
    assert timeline.status_code == 200
    assert timeline.json()["person"]["name"] == "Ada"
    assert timeline.json()["person"]["department"] == "Eng"

    holiday = client.post("/api/v1/holidays", headers=auth, json={"day": "2026-12-25", "name": "Christmas"})
    assert holiday.status_code == 201, holiday.text
    holidays = client.get("/api/v1/holidays", headers=auth)
    assert holidays.status_code == 200
    assert holidays.json()[0]["name"] == "Christmas"

    events_csv = client.get("/api/v1/events/export", headers=auth)
    assert events_csv.status_code == 200
    assert "text/csv" in events_csv.headers.get("content-type", "")

    settings = client.get("/api/v1/settings", headers=auth)
    assert settings.status_code == 200
    body = settings.json()
    assert "geo_radius_m" in body
    assert "notify_late" in body
    assert "weekend" in body

    patched = client.patch(
        "/api/v1/settings",
        headers=auth,
        json={"office_name": "Studio", "weekend": "6,7", "notify_late": False},
    )
    assert patched.status_code == 200
    assert patched.json()["office_name"] == "Studio"


def test_kiosk_pin_fallback(client, auth):
    person = client.post(
        "/api/v1/persons",
        headers=auth,
        json={"name": "Pin User", "employee_id": "PIN-9"},
    ).json()
    blocked = client.post("/api/v1/attendance/kiosk", headers=auth, data={"pin": "PIN-9"})
    assert blocked.status_code == 403
    assert blocked.json()["detail"] == "kiosk_pin_disabled"

    enabled = client.patch("/api/v1/settings", headers=auth, json={"allow_kiosk_pin": True})
    assert enabled.status_code == 200
    assert enabled.json()["allow_kiosk_pin"] is True

    punch = client.post("/api/v1/attendance/kiosk", headers=auth, data={"pin": "PIN-9"})
    assert punch.status_code == 200, punch.text
    assert punch.json()["person_id"] == person["id"]
    assert punch.json()["source"] == "pin"


def test_liveness_challenge_includes_timing(client, auth):
    rec = client.post("/api/v1/liveness/challenge", headers=auth)
    assert rec.status_code == 200
    body = rec.json()
    assert body["hold_ms"] >= 900
    assert body["hold_frames"] >= 4
    assert body["blink_frames"] >= 8


def test_check_in_requires_office_geofence(client, auth):
    client.post(
        "/api/v1/auth/register",
        json={"username": "geoemp", "password": "password1", "name": "Geo Person"},
    )
    emp_token = _login(client, "geoemp").json()["access_token"]
    emp = {"Authorization": f"Bearer {emp_token}"}
    pid = client.get("/api/v1/auth/me", headers=emp).json()["person"]["id"]
    img = png_bytes((12, 24, 36))
    assert (
        client.post(
            f"/api/v1/persons/{pid}/enroll",
            headers=auth,
            files=[("images", ("face.png", img, "image/png"))],
        ).status_code
        == 200
    )
    pinned = client.patch(
        "/api/v1/settings",
        headers=auth,
        json={"geo_lat": 28.6139, "geo_lng": 77.2090, "geo_radius_m": 150},
    )
    assert pinned.status_code == 200, pinned.text

    missing = client.post(
        "/api/v1/attendance/check-in",
        headers=emp,
        files={"image": ("probe.png", img, "image/png")},
    )
    assert missing.status_code == 400
    assert missing.json()["detail"] == "location_required"

    far = client.post(
        "/api/v1/attendance/check-in",
        headers=emp,
        data={"latitude": "19.0760", "longitude": "72.8777"},
        files={"image": ("probe.png", img, "image/png")},
    )
    assert far.status_code == 403
    assert far.json()["detail"] == "outside_geofence"

    near = client.post(
        "/api/v1/attendance/check-in",
        headers=emp,
        data={"latitude": "28.6139", "longitude": "77.2090"},
        files={"image": ("probe.png", img, "image/png")},
    )
    assert near.status_code == 200, near.text
    assert near.json()["decision"] == "present"


def test_spoof_alert_captures_photo_for_hr(client, auth):
    client.post(
        "/api/v1/auth/register",
        json={"username": "cheat", "password": "password1", "name": "Cheat Person"},
    )
    emp_token = _login(client, "cheat").json()["access_token"]
    emp = {"Authorization": f"Bearer {emp_token}"}
    img = png_bytes((40, 80, 120))
    challenge = client.post("/api/v1/liveness/challenge", headers=emp)
    assert challenge.status_code == 200
    files = [("frames", (f"f{i}.png", img, "image/png")) for i in range(12)]
    checked = client.post(
        "/api/v1/liveness/check",
        headers=emp,
        data={"challenge_id": challenge.json()["challenge_id"], "source": "attendance"},
        files=files,
    )
    assert checked.status_code == 200, checked.text
    assert checked.json()["live"] is False

    denied = client.get("/api/v1/ops/spoof-alerts", headers=emp)
    assert denied.status_code == 403

    alerts = client.get("/api/v1/ops/spoof-alerts", headers=auth)
    assert alerts.status_code == 200, alerts.text
    rows = alerts.json()
    assert len(rows) >= 1
    row = rows[0]
    assert row["actor_username"] == "cheat"
    assert row["person_name"] == "Cheat Person"
    assert row["source"] == "attendance"
    photo = client.get(f"/api/v1/ops/spoof-alerts/{row['id']}/image", headers=auth)
    assert photo.status_code == 200
    assert photo.headers["content-type"] == "image/jpeg"
    assert len(photo.content) > 50

    lab = client.post("/api/v1/liveness/challenge", headers=emp)
    lab_check = client.post(
        "/api/v1/liveness/check",
        headers=emp,
        data={"challenge_id": lab.json()["challenge_id"], "source": "lab"},
        files=files,
    )
    assert lab_check.status_code == 200
    after = client.get("/api/v1/ops/spoof-alerts", headers=auth).json()
    assert len(after) == len(rows)


def test_missed_blink_on_live_face_is_not_a_spoof_alert():
    """Texture that already says 'looks live' must not file a photo/screen alert."""
    from app.db.models import User
    from app.liveness.alerts import record_spoof

    user = User(username="rohan", hashed_password="x", role="employee")
    out = record_spoof(
        None,  # type: ignore[arg-type]
        user=user,
        frames=[b"unused"],
        result={
            "live": False,
            "blink": {"reason": "no open-closed-open transition"},
            "texture": {"live": True, "reason": "looks live"},
        },
        source="attendance",
    )
    assert out is None


def test_hr_can_edit_attendance_and_reactivate(client, auth):
    person = client.post(
        "/api/v1/persons",
        headers=auth,
        json={"name": "Override Person", "employee_id": "OV-1"},
    ).json()
    marked = client.post(
        "/api/v1/attendance/manual",
        headers=auth,
        json={"person_id": person["id"], "decision": "present", "late": True},
    )
    assert marked.status_code == 200, marked.text
    assert marked.json()["decision"] == "present"
    assert marked.json()["late"] is True
    assert marked.json()["source"] == "hr"
    rid = marked.json()["id"]

    edited = client.patch(
        f"/api/v1/attendance/{rid}",
        headers=auth,
        json={"decision": "excused", "checked_out": False},
    )
    assert edited.status_code == 200, edited.text
    assert edited.json()["decision"] == "excused"
    assert edited.json()["late"] is False

    client.post(
        "/api/v1/auth/register",
        json={"username": "noedit", "password": "password1", "name": "No Edit"},
    )
    emp_token = _login(client, "noedit").json()["access_token"]
    emp = {"Authorization": f"Bearer {emp_token}"}
    denied = client.patch(f"/api/v1/attendance/{rid}", headers=emp, json={"decision": "present"})
    assert denied.status_code == 403

    gone = client.delete(f"/api/v1/persons/{person['id']}", headers=auth)
    assert gone.status_code == 204
    back = client.post(f"/api/v1/persons/{person['id']}/reactivate", headers=auth)
    assert back.status_code == 200, back.text
    assert back.json()["is_active"] is True


def _enroll_employee(client, auth, username, name, color=(11, 22, 33)):
    client.post(
        "/api/v1/auth/register",
        json={"username": username, "password": "password1", "name": name},
    )
    token = _login(client, username).json()["access_token"]
    emp = {"Authorization": f"Bearer {token}"}
    pid = client.get("/api/v1/auth/me", headers=emp).json()["person"]["id"]
    img = png_bytes(color)
    assert (
        client.post(
            f"/api/v1/persons/{pid}/enroll",
            headers=auth,
            files=[("images", ("face.png", img, "image/png"))],
        ).status_code
        == 200
    )
    return emp, pid, img


def test_auth_config_includes_workplace_profile(client):
    cfg = client.get("/api/v1/auth/config").json()
    assert cfg["org_type"] == "workplace"
    assert cfg["kernel"] == "daily_inout"
    assert cfg["allow_checkout"] is True
    assert cfg["subject_label"] == "employee"
    assert cfg.get("org_slug") in (None, "")
    assert cfg.get("org_name") in (None, "")
    assert cfg.get("default_site") in (None, {})


def test_school_daily_hides_checkout_and_keeps_once_per_day(client, auth):
    switched = client.patch("/api/v1/settings", headers=auth, json={"org_type": "school"})
    assert switched.status_code == 200, switched.text
    body = switched.json()
    assert body["kernel"] == "daily_presence"
    assert body["allow_checkout"] is False
    assert body["subject_label"] == "student"
    assert body["id_label"] == "Student ID"

    emp, _pid, img = _enroll_employee(client, auth, "schoolkid", "School Kid", (4, 8, 16))
    first = client.post("/api/v1/attendance/check-in", headers=emp, files={"image": ("p.png", img, "image/png")})
    assert first.status_code == 200, first.text
    assert first.json()["already_marked"] is False
    second = client.post("/api/v1/attendance/check-in", headers=emp, files={"image": ("p.png", img, "image/png")})
    assert second.status_code == 200
    assert second.json()["already_marked"] is True
    denied = client.post("/api/v1/attendance/check-out", headers=emp)
    assert denied.status_code == 400
    assert denied.json()["detail"] == "checkout_disabled"


def test_college_session_allows_two_marks_same_day(client, auth):
    assert client.patch("/api/v1/settings", headers=auth, json={"org_type": "college"}).status_code == 200
    emp, pid, img = _enroll_employee(client, auth, "undergrad", "Under Grad", (9, 18, 27))
    course = client.post(
        "/api/v1/schedule/offerings",
        headers=auth,
        json={"name": "CS101", "code": "CS101", "kind": "course", "default_start": "00:00", "default_end": "23:59"},
    )
    assert course.status_code == 201, course.text
    oid = course.json()["id"]
    enrolled = client.post(
        f"/api/v1/schedule/offerings/{oid}/enrollments",
        headers=auth,
        json={"person_id": pid},
    )
    assert enrolled.status_code == 201, enrolled.text
    from datetime import date as date_cls

    today = date_cls.today().isoformat()
    a = client.post(
        "/api/v1/schedule/occurrences",
        headers=auth,
        json={"offering_id": oid, "title": "Lecture A", "day": today, "start": "00:00", "end": "12:00"},
    )
    b = client.post(
        "/api/v1/schedule/occurrences",
        headers=auth,
        json={"offering_id": oid, "title": "Lab B", "day": today, "start": "12:00", "end": "23:59"},
    )
    assert a.status_code == 201, a.text
    assert b.status_code == 201, b.text
    first = client.post(
        "/api/v1/attendance/check-in",
        headers=emp,
        data={"occurrence_id": str(a.json()["id"])},
        files={"image": ("p.png", img, "image/png")},
    )
    assert first.status_code == 200, first.text
    assert first.json()["already_marked"] is False
    assert first.json()["occurrence_id"] == a.json()["id"]
    repeat = client.post(
        "/api/v1/attendance/check-in",
        headers=emp,
        data={"occurrence_id": str(a.json()["id"])},
        files={"image": ("p.png", img, "image/png")},
    )
    assert repeat.json()["already_marked"] is True
    second = client.post(
        "/api/v1/attendance/check-in",
        headers=emp,
        data={"occurrence_id": str(b.json()["id"])},
        files={"image": ("p.png", img, "image/png")},
    )
    assert second.status_code == 200, second.text
    assert second.json()["already_marked"] is False
    assert second.json()["id"] != first.json()["id"]
    stats = client.get(f"/api/v1/schedule/offerings/{oid}/stats", headers=auth).json()
    assert stats["meetings"] == 2
    assert stats["present_marks"] == 2


def test_visit_kernel_allows_multiple_checkins(client, auth):
    assert client.patch("/api/v1/settings", headers=auth, json={"org_type": "membership"}).status_code == 200
    emp, _pid, img = _enroll_employee(client, auth, "gymgoer", "Gym Goer", (30, 40, 50))
    first = client.post("/api/v1/attendance/check-in", headers=emp, files={"image": ("p.png", img, "image/png")})
    second = client.post("/api/v1/attendance/check-in", headers=emp, files={"image": ("p.png", img, "image/png")})
    assert first.status_code == 200, first.text
    assert second.status_code == 200, second.text
    assert first.json()["id"] != second.json()["id"]
    assert first.json()["already_marked"] is False
    assert second.json()["already_marked"] is False


def test_shift_occurrence_and_site_geofence(client, auth):
    assert client.patch("/api/v1/settings", headers=auth, json={"org_type": "shift_ops"}).status_code == 200
    site = client.post(
        "/api/v1/schedule/sites",
        headers=auth,
        json={"name": "Plant A", "lat": 28.6139, "lng": 77.2090, "radius_m": 200, "is_default": True},
    )
    assert site.status_code == 201, site.text
    offering = client.post(
        "/api/v1/schedule/offerings",
        headers=auth,
        json={"name": "Night", "kind": "shift", "default_start": "22:00", "default_end": "06:00"},
    )
    oid = offering.json()["id"]
    from datetime import date as date_cls

    today = date_cls.today().isoformat()
    occ = client.post(
        "/api/v1/schedule/occurrences",
        headers=auth,
        json={
            "offering_id": oid,
            "kind": "shift",
            "title": "Night shift",
            "day": today,
            "start": "00:00",
            "end": "23:59",
            "overnight": True,
            "site_id": site.json()["id"],
        },
    )
    assert occ.status_code == 201, occ.text
    emp, pid, img = _enroll_employee(client, auth, "shiftworker", "Shift Worker", (1, 2, 3))
    client.post(f"/api/v1/schedule/offerings/{oid}/enrollments", headers=auth, json={"person_id": pid})
    missing = client.post(
        "/api/v1/attendance/check-in",
        headers=emp,
        data={"occurrence_id": str(occ.json()["id"])},
        files={"image": ("p.png", img, "image/png")},
    )
    assert missing.status_code == 400
    assert missing.json()["detail"] == "location_required"
    far = client.post(
        "/api/v1/attendance/check-in",
        headers=emp,
        data={"occurrence_id": str(occ.json()["id"]), "latitude": "19.0760", "longitude": "72.8777"},
        files={"image": ("p.png", img, "image/png")},
    )
    assert far.status_code == 403
    near = client.post(
        "/api/v1/attendance/check-in",
        headers=emp,
        data={"occurrence_id": str(occ.json()["id"]), "latitude": "28.6139", "longitude": "77.2090"},
        files={"image": ("p.png", img, "image/png")},
    )
    assert near.status_code == 200, near.text
    assert near.json()["occurrence_id"] == occ.json()["id"]
    assert near.json()["site_id"] == site.json()["id"]


def test_kiosk_session_requires_occurrence(client, auth):
    assert client.patch("/api/v1/settings", headers=auth, json={"org_type": "college"}).status_code == 200
    person = client.post("/api/v1/persons", headers=auth, json={"name": "Kiosk Student", "employee_id": "KS-1"}).json()
    img = png_bytes((70, 80, 90))
    client.post(
        f"/api/v1/persons/{person['id']}/enroll",
        headers=auth,
        files=[("images", ("face.png", img, "image/png"))],
    )
    blocked = client.post("/api/v1/attendance/kiosk", headers=auth, files={"image": ("probe.png", img, "image/png")})
    assert blocked.status_code == 400
    assert blocked.json()["detail"] == "occurrence_required"


def test_platform_admin_lists_and_creates_orgs(client, auth, default_org_id):
    listed = client.get("/api/v1/orgs", headers=auth)
    assert listed.status_code == 200, listed.text
    ids = {row["id"] for row in listed.json()}
    assert default_org_id in ids
    created = client.post(
        "/api/v1/orgs",
        headers=auth,
        json={"name": "North Campus", "org_type": "school"},
    )
    assert created.status_code == 201, created.text
    body = created.json()
    assert body["name"] == "North Campus"
    assert body["slug"] == "north-campus"
    assert body["org_type"] == "school"
    assert body["kernel"] == "daily_presence"
    assert body["subject_label"] == "student"


def test_hr_cannot_list_orgs(client, auth):
    staff = client.post(
        "/api/v1/users",
        headers=auth,
        json={"username": "hruser", "password": "password1", "role": "hr"},
    )
    assert staff.status_code == 201, staff.text
    token = _login(client, "hruser").json()["access_token"]
    hr = {"Authorization": f"Bearer {token}"}
    blocked = client.get("/api/v1/orgs", headers=hr)
    assert blocked.status_code == 403
    assert blocked.json()["detail"] == "platform_admin_only"


def test_people_are_isolated_per_org(client, auth):
    person_a = client.post("/api/v1/persons", headers=auth, json={"name": "Org A Worker", "employee_id": "A-1"})
    assert person_a.status_code == 201, person_a.text
    other = client.post("/api/v1/orgs", headers=auth, json={"name": "Other Co", "org_type": "workplace"})
    assert other.status_code == 201, other.text
    org_b = other.json()["id"]
    headers_b = {**auth, "X-Org-Id": str(org_b)}
    listed_b = client.get("/api/v1/persons", headers=headers_b)
    assert listed_b.status_code == 200
    assert listed_b.json() == []
    listed_a = client.get("/api/v1/persons", headers=auth)
    names = {p["name"] for p in listed_a.json()}
    assert "Org A Worker" in names
    hidden = client.get(f"/api/v1/persons/{person_a.json()['id']}", headers=headers_b)
    assert hidden.status_code == 404


def test_kiosk_identify_does_not_cross_orgs(client, auth):
    other = client.post("/api/v1/orgs", headers=auth, json={"name": "School B", "org_type": "school"})
    assert other.status_code == 201, other.text
    headers_b = {**auth, "X-Org-Id": str(other.json()["id"])}
    person_b = client.post(
        "/api/v1/persons",
        headers=headers_b,
        json={"name": "Only In B", "employee_id": "B-1"},
    ).json()
    img = png_bytes((12, 24, 48))
    assert (
        client.post(
            f"/api/v1/persons/{person_b['id']}/enroll",
            headers=headers_b,
            files=[("images", ("face.png", img, "image/png"))],
        ).status_code
        == 200
    )
    miss = client.post("/api/v1/attendance/kiosk", headers=auth, files={"image": ("probe.png", img, "image/png")})
    assert miss.status_code == 404
    assert miss.json()["detail"] == "face_not_recognized"
    hit = client.post("/api/v1/attendance/kiosk", headers=headers_b, files={"image": ("probe.png", img, "image/png")})
    assert hit.status_code == 200, hit.text
    assert hit.json()["person_id"] == person_b["id"]


def test_same_username_allowed_in_two_orgs(client, auth):
    first = client.post(
        "/api/v1/auth/register",
        json={"username": "alice", "password": "password1", "name": "Alice HQ"},
    )
    assert first.status_code == 201, first.text
    other = client.post("/api/v1/orgs", headers=auth, json={"name": "South Campus", "org_type": "workplace"})
    assert other.status_code == 201, other.text
    slug_b = other.json()["slug"]
    second = client.post(
        "/api/v1/auth/register",
        json={"username": "alice", "password": "password1", "name": "Alice South", "org": slug_b},
    )
    assert second.status_code == 201, second.text
    assert second.json()["org_id"] == other.json()["id"]

    denied = client.post("/api/v1/auth/login", json={"username": "alice", "password": "password1"})
    assert denied.status_code == 401

    hq = _login(client, "alice")
    assert hq.status_code == 200, hq.text
    south = _login(client, "alice", org=slug_b)
    assert south.status_code == 200, south.text
    me_hq = client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {hq.json()['access_token']}"}).json()
    me_south = client.get(
        "/api/v1/auth/me", headers={"Authorization": f"Bearer {south.json()['access_token']}"}
    ).json()
    assert me_hq["person"]["name"] == "Alice HQ"
    assert me_south["person"]["name"] == "Alice South"


def test_org_admin_username_does_not_shadow_platform_admin(client, auth):
    created = client.post(
        "/api/v1/users",
        headers=auth,
        json={"username": "admin", "password": "password1", "role": "hr"},
    )
    assert created.status_code == 201, created.text
    as_org = _login(client, "admin", password="password1")
    assert as_org.status_code == 200, as_org.text
    me = client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {as_org.json()['access_token']}"}).json()
    assert me["role"] == "hr"
    assert me["org_id"] is not None
    platform = client.post("/api/v1/auth/login", json={"username": "admin", "password": "admin1234"})
    assert platform.status_code == 200
    plat_me = client.get(
        "/api/v1/auth/me", headers={"Authorization": f"Bearer {platform.json()['access_token']}"}
    ).json()
    assert plat_me["org_id"] is None
    assert plat_me["is_admin"] is True


def test_postgres_org_schema_has_no_foreign_people(client, auth, default_org_id):
    import pytest
    from sqlalchemy import text

    from app.core.config import settings
    from app.db.session import SessionLocal
    from app.db.tenancy import schema_name

    if settings.is_sqlite:
        pytest.skip("Postgres schema-per-org only")
    other = client.post("/api/v1/orgs", headers=auth, json={"name": "Isolated Co", "org_type": "workplace"})
    assert other.status_code == 201, other.text
    org_b = other.json()["id"]
    person = client.post("/api/v1/persons", headers=auth, json={"name": "Only A", "employee_id": "A-99"})
    assert person.status_code == 201, person.text
    with SessionLocal() as session:
        n_b = session.connection().execute(text(f'SELECT count(*) FROM "{schema_name(org_b)}".person')).scalar()
        n_a = session.connection().execute(
            text(f'SELECT count(*) FROM "{schema_name(default_org_id)}".person')
        ).scalar()
    assert n_b == 0
    assert int(n_a or 0) >= 1


def test_new_org_has_default_site_for_hr_and_employee(client, auth):
    created = client.post(
        "/api/v1/orgs",
        headers=auth,
        json={"name": "West Campus", "org_type": "workplace"},
    )
    assert created.status_code == 201, created.text
    slug = created.json()["slug"]
    org_id = created.json()["id"]
    headers_b = {**auth, "X-Org-Id": str(org_id)}
    sites = client.get("/api/v1/schedule/sites", headers=headers_b)
    assert sites.status_code == 200, sites.text
    rows = sites.json()
    assert any(s["is_default"] for s in rows)
    assert any(s["name"] == "West Campus" for s in rows)
    cfg_hr = client.get("/api/v1/auth/config", headers=headers_b).json()
    assert cfg_hr["org_slug"] == slug
    assert cfg_hr["org_name"] == "West Campus"
    assert cfg_hr["default_site"]["name"] == "West Campus"

    registered = client.post(
        "/api/v1/auth/register",
        json={"username": "siteemp", "password": "password1", "name": "Site Emp", "org": slug},
    )
    assert registered.status_code == 201, registered.text
    emp = _login(client, "siteemp", org=slug)
    assert emp.status_code == 200, emp.text
    emp_h = {"Authorization": f"Bearer {emp.json()['access_token']}"}
    seen = client.get("/api/v1/schedule/sites", headers=emp_h)
    assert seen.status_code == 200, seen.text
    assert any(s["is_default"] and s["name"] == "West Campus" for s in seen.json())
    cfg = client.get("/api/v1/auth/config", headers=emp_h).json()
    assert cfg["org_slug"] == slug
    me = client.get("/api/v1/auth/me", headers=emp_h).json()
    assert me["org_slug"] == slug
    assert me["org_name"] == "West Campus"


def test_org_user_cannot_switch_org_via_header(client, auth):
    assert client.post(
        "/api/v1/auth/register",
        json={"username": "stayput", "password": "password1", "name": "Stay Put"},
    ).status_code == 201
    other = client.post("/api/v1/orgs", headers=auth, json={"name": "Divert Co", "org_type": "workplace"})
    assert other.status_code == 201, other.text
    token = _login(client, "stayput")
    assert token.status_code == 200, token.text
    emp = {
        "Authorization": f"Bearer {token.json()['access_token']}",
        "X-Org-Id": str(other.json()["id"]),
    }
    me = client.get("/api/v1/auth/me", headers=emp).json()
    assert me["org_id"] != other.json()["id"]
    cfg = client.get("/api/v1/auth/config", headers=emp).json()
    assert cfg["org_slug"] == _default_slug()


def test_hr_cannot_verify_or_patch_other_org_person(client, auth):
    person_a = client.post("/api/v1/persons", headers=auth, json={"name": "Only A", "employee_id": "XA-1"})
    assert person_a.status_code == 201, person_a.text
    pid = person_a.json()["id"]
    img = png_bytes((3, 6, 9))
    assert (
        client.post(
            f"/api/v1/persons/{pid}/enroll",
            headers=auth,
            files=[("images", ("face.png", img, "image/png"))],
        ).status_code
        == 200
    )
    other = client.post("/api/v1/orgs", headers=auth, json={"name": "Other Lab", "org_type": "workplace"})
    assert other.status_code == 201, other.text
    headers_b = {**auth, "X-Org-Id": str(other.json()["id"])}
    staff = client.post(
        "/api/v1/users",
        headers=headers_b,
        json={"username": "otherop", "password": "password1", "role": "operator"},
    )
    assert staff.status_code == 201, staff.text
    op = _login(client, "otherop", org=other.json()["slug"])
    assert op.status_code == 200, op.text
    op_h = {"Authorization": f"Bearer {op.json()['access_token']}"}
    denied = client.post(
        f"/api/v1/verify/person/{pid}",
        headers=op_h,
        files={"image": ("p.png", img, "image/png")},
    )
    assert denied.status_code == 404
    hr = client.post(
        "/api/v1/users",
        headers=headers_b,
        json={"username": "otherhr", "password": "password1", "role": "hr"},
    )
    assert hr.status_code == 201, hr.text
    hr_tok = _login(client, "otherhr", org=other.json()["slug"])
    hr_h = {"Authorization": f"Bearer {hr_tok.json()['access_token']}"}
    listed = client.get("/api/v1/attendance", headers=hr_h)
    assert listed.status_code == 200
    assert listed.json() == []
    patched = client.patch(f"/api/v1/attendance/{pid}", headers=hr_h, json={"decision": "excused"})
    assert patched.status_code == 404

