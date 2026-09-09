# Product Requirements Document

**Product:** Sentinel  
**Full name:** Sentinel Face Attendance Platform  
**Document type:** Product Requirements Document (PRD)  
**Version:** 1.0  
**Status:** Current product (implemented)  
**Date:** 26 August 2026  
**Classification:** Internal — product & engineering  

---

## 1. Purpose of this document

This PRD describes **Sentinel** as a workplace product: what it is for, who uses it, what it must do, and how success is judged.

Sentinel started as a face-recognition lab (FaceNet / ArcFace, LFW evaluation). It is now a **face-attendance platform**: employees check in with a live face, HR sees who is in, and the entrance can run as a kiosk. The recognition research stack remains, but the product promise is **reliable workplace attendance**, not a demo of embeddings.

This document is the source of truth for:

- product scope that exists today
- roles and permissions
- user journeys
- functional and non-functional requirements
- what is explicitly out of scope

---

## 2. Product summary

| | |
|---|---|
| **One-line** | Employees mark attendance with a face. HR sees who is in. The door can run as a kiosk. |
| **Category** | Workplace attendance / access control |
| **Primary platform** | Web app (React) + FastAPI backend |
| **Local demo** | `http://localhost:5173` (Vite) → API `http://127.0.0.1:8000` |
| **Default local admin** | `admin` / `admin1234` (SQLite) |

**Tagline (product UI):** *Show up. Check in. Go to work.*

---

## 3. Problem

Most workplace attendance is still:

- a shared PIN or RFID card (easy to share, easy to lose)
- a paper register or spreadsheet (slow, dishonest, hard to audit)
- a mobile “punch” that can be done from home

Face check-in is stronger **if** it is actually a live person at the workplace. Printed photos, phone screens, and remote punches must fail.

HR also needs a live picture of the day: who is in, who is late, who never got a photo enrolled, and a trail they can export.

---

## 4. Goals

### 4.1 Product goals

1. Check-in is a **face moment**, not a form: camera, oval, optional blink, clear success or retry.
2. HR can run the day without opening a lab: Today dashboard, people directory, reports.
3. The entrance can run **unattended** as a fullscreen kiosk, plus a TV “who is in” screen.
4. Phone check-in can be **locked to the office location** that HR or Admin sets.
5. Recognition quality stays measurable (ROC, TAR@FAR, liveness tester) for operators and admins.

### 4.2 Non-goals (do not pretend we do these yet)

- Payroll, tax, or salary calculation
- Full leave / PTO workflow and manager approvals
- Mobile native apps (iOS / Android stores)
- Multi-company SaaS tenancy
- Voice or QR as a primary check-in method

---

## 5. Users and roles

| Role | Who | Home screen | Can do |
|------|-----|-------------|--------|
| **Employee** | Staff member with a linked person record | Check in | Sign in, check in / out, month calendar + CSV, change password |
| **HR** | People operations | Today | People, enroll faces, reports, office hours, office location lock, holidays (view), kiosk, activity, TV board |
| **Operator** | Reception / security / lab | Recognition lab | Kiosk, activity, TV board, verify / identify / liveness, accuracy charts. **Cannot** manage people or attendance reports |
| **Admin** | IT / founder | Today | Everything HR can, plus staff accounts (create HR / operator / admin, reset passwords), holidays edit, office settings |

A person in the directory is not the same as a login. HR must **give a login** and **add a face photo** before that person can check in.

---

## 6. User journeys

### 6.1 New employee

1. Employee creates an account (if public register is on) **or** HR creates the person and login.
2. HR opens **Add faces**, captures a front-facing photo.
3. Employee opens **Check in**. The page waits until a photo exists.
4. Employee looks at the camera, blinks if liveness is required, and is marked present.

### 6.2 Morning at the door

1. Staff opens **Entrance kiosk** (fullscreen, no sidebar).
2. Visitor or employee faces the oval and taps Check in (blink if required).
3. On match: name, time, late badge; screen resets after a few seconds.
4. If the camera fails: staff uses **employee ID** as a supervised PIN.
5. Optional: a TV on **Entrance screen** (`/board`) shows who is in now vs still expected.

### 6.3 HR’s day

1. **Today** auto-refreshes: present, late, not in, failed checks, waiting for photo.
2. Click a name → person timeline (punches and events).
3. **Reports** with Today / This week / This month + CSV.
4. Set **office hours**, **weekends**, **holidays**, and **office location lock**.

### 6.4 Location-locked check-in

1. HR or Admin stands at the workplace.
2. **Today → Office location lock → Use this device as the office**, pick radius (e.g. 150 m), save.
3. Employee check-in requests GPS. Outside the circle, or location denied → **not present**.
4. Physical **kiosk** at the door does **not** require GPS (the device is already on site).

---

## 7. Functional requirements

Priority: **P0** must work for a demo / first workplace; **P1** expected in this build; **P2** later.

### 7.1 Authentication and accounts — P0

| ID | Requirement |
|----|-------------|
| AUTH-1 | JWT login; session on the SPA. |
| AUTH-2 | Roles: `admin`, `hr`, `operator`, `employee`. |
| AUTH-3 | Optional public self-register (can be disabled). After register, employee sees a 3-step “what happens next”. |
| AUTH-4 | Admin can create staff users and reset passwords (**Staff**). |
| AUTH-5 | HR can set or reset an employee username/password from **People**. |
| AUTH-6 | Employee can change their own password. |

### 7.2 Directory and enrollment — P0

| ID | Requirement |
|----|-------------|
| PEO-1 | Add, search, edit, CSV import, soft-deactivate people. |
| PEO-2 | Fields: name, employee ID (unique), email, notes, department, office, shift start/end. |
| PEO-3 | Enroll one or more face photos; quality gates reject no-face / multi-face / poor frames. |
| PEO-4 | Person timeline: attendance + audit events. |
| PEO-5 | Deactivated people cannot check in; history is kept. |

### 7.3 Employee attendance — P0

| ID | Requirement |
|----|-------------|
| ATT-1 | 1:1 verify against the enrolled embedding; threshold from evaluation (TAR@FAR 1e-3 by default). |
| ATT-2 | Optional blink liveness before check-in when `require_liveness` is on. |
| ATT-3 | One present mark per local calendar day; repeat check-in returns already marked. |
| ATT-4 | Late if after work start + grace (person shift overrides office hours). |
| ATT-5 | Check-out with optional second face; early leave if before work end / shift end. |
| ATT-6 | If office geofence is set: employee check-in **must** send GPS and be inside the radius. |
| ATT-7 | Personal month view + CSV export. |

### 7.4 Kiosk and TV board — P0 / P1

| ID | Requirement |
|----|-------------|
| KIO-1 | Staff-only fullscreen kiosk; 1:N identify against the gallery. |
| KIO-2 | Oval + scan overlay; success/fail moment; auto-reset ~5s. |
| KIO-3 | Kiosk liveness when required; PIN = employee ID if camera fails. |
| KIO-4 | Kiosk is **not** GPS-gated. |
| BRD-1 | `/board` entrance screen: in now, not in yet, live clock, % of expected. TV-friendly, no sidebar. |

### 7.5 HR operations — P0 / P1

| ID | Requirement |
|----|-------------|
| OPS-1 | Today dashboard polls ~12s: present, late, absent, failed, pending faces, still out. |
| OPS-2 | Office hours, timezone, grace, weekend days. HR and Admin may edit. |
| OPS-3 | Office location lock (lat/lng/radius). HR and Admin may edit. |
| OPS-4 | Holidays so expected attendance skips those days. |
| OPS-5 | Reports with date presets and CSV. Activity log with CSV. |
| OPS-6 | Optional email: enrolled face, late, 3 failed checks, absent after start+grace. |

### 7.6 Recognition lab — P1

| ID | Requirement |
|----|-------------|
| LAB-1 | Accuracy charts: ROC, TAR@FAR, score histograms (from `reports/evaluation.json`). |
| LAB-2 | Verify two photos; identify 1:N. |
| LAB-3 | Blink liveness tester with Live / Not live + blink meter (not raw JSON). |

### 7.7 Platform — P0

| ID | Requirement |
|----|-------------|
| PLT-1 | SQLite locally; Postgres + Alembic in Docker / production. |
| PLT-2 | Rate limits on login and check-in. |
| PLT-3 | Health / ready endpoints. CI: pytest, frontend tests, build. |
| PLT-4 | Dark-first greyscale UI; status badges keep pass/fail colour. |

---

## 8. Face pipeline (how matching works)

This is the differentiator. Product copy should stay human; this section is for engineering and reviewers.

```
Camera frame
  → detect face (SCRFD)
  → quality gates (one face, size, blur, brightness)
  → 5-point align
  → L2-normalised embedding (FaceNet or ArcFace, 512-D)
  → cosine vs enrolled gallery (FAISS inner product or NumPy)
  → match if score ≥ calibrated threshold
```

| Encoder | Role |
|---------|------|
| FaceNet (Inception-ResNet-v1, VGGFace2) | Default published weights |
| ArcFace (`w600k_r50` ONNX) | Published reference |
| Fine-tuned FaceNet + ArcFace head | Optional; evaluated on LFW |

**Operating point:** TAR at FAR = **0.001** on LFW View 2 (6,000 pairs). The live API uses that threshold unless overridden.

**Liveness:** short blink challenge (eye aspect ratio) plus a texture cue so a printed photo or screen is less likely to pass.

**Gallery:** embeddings stored per person; identify is 1:N search.

---

## 9. Information architecture (screens)

| Route | Audience | Purpose |
|-------|----------|---------|
| `/login` | All | Sign in / register |
| `/` | HR, Admin | Today — who is in |
| `/board` | Staff | TV entrance screen |
| `/people`, `/people/:id` | HR, Admin | Directory and timeline |
| `/enroll` | HR, Admin | Face photos |
| `/reports` | HR, Admin | Attendance export |
| `/kiosk` | Staff | Entrance check-in |
| `/events` | Staff | Audit log |
| `/staff` | Admin | Create HR / operator / admin |
| `/attendance`, `/my-attendance`, `/profile` | Employee | Check in, days, password |
| `/lab`, `/verify`, `/identify`, `/liveness` | Admin, Operator | Recognition lab |

---

## 10. Non-functional requirements

| Area | Requirement |
|------|-------------|
| **Latency** | Check-in should feel interactive on CPU with a single face (typically a few hundred ms plus network). |
| **Accuracy** | Publish LFW accuracy, EER, TAR@FAR; do not silently swap encoders. |
| **Privacy** | Store embeddings and audit events, not a video archive of every frame. Limit who can see people and reports. |
| **Security** | JWT; production must set a real `FRS_SECRET_KEY`; disable public register in production; geofence is **assistive**, not a substitute for a guarded door. |
| **Reliability** | `/ready` reports database, weights, gallery. |
| **Deploy** | Docker Compose + Postgres for a real install; SQLite for local demo. |
| **A11y / UI** | Large kiosk type; camera-denied copy; no raw `play()` errors on the kiosk. |
| **Timezone** | Late / absent / “today” use office timezone (default `Asia/Kolkata`). |

---

## 11. Success metrics

| Metric | Why it matters |
|--------|----------------|
| Time to first successful check-in (new hire) | Enrollment + login friction |
| Present vs expected by 10 minutes after start + grace | Did the office actually fill? |
| False reject rate at the kiosk (qualitative + failed_today) | Light, pose, enrollment quality |
| False accept incidents | Shared phone, photo attack, PIN misuse |
| % of employee check-ins blocked by geofence | Policy is working vs GPS too strict |
| TAR@FAR 1e-3 on LFW | Encoder still honest |

---

## 12. Risks and mitigations

| Risk | Mitigation |
|------|------------|
| Printed photo or replay | Blink + texture liveness; kiosk lighting |
| Buddy punching from home | Office location lock on phone check-in; kiosk at the door |
| GPS spoof / coarse GPS | Reasonable radius; kiosk still available; do not claim military-grade geo |
| Poor enrollment photo | Quality gates; “add another photo” |
| Threshold too strict / too loose | Lab charts; FAR 1e-3 default |
| Camera `play()` races in the browser | Webcam hook ignores abort; single in-flight start |
| Privacy / labour law | Consent, retention policy, role limits — **legal review is on the customer** |

---

## 13. Out of scope / later

These are known and **not** required for this PRD version:

- Leave requests, WFH, manager exception approvals
- Multi-office timezones as first-class tenants (people have an `office` field; hours are still global)
- Slack alerts (email exists when SMTP is configured)
- PWA install / home-screen check-in as a dedicated track
- Stronger anti-spoof than blink (challenge-response, depth)
- Payroll export beyond attendance CSV

---

## 14. Technical snapshot (for implementers)

| Layer | Choice |
|-------|--------|
| Frontend | React, Vite, Tailwind, Recharts |
| Backend | FastAPI, SQLModel |
| Auth | JWT Bearer |
| DB | SQLite (local), PostgreSQL + Alembic (prod) |
| Index | FAISS `IndexFlatIP` |
| Detect | SCRFD |
| API prefix | `/api/v1` |

**Core resources:** `/auth/*`, `/persons/*`, `/attendance/*` (check-in, check-out, kiosk, export), `/ops/summary`, `/settings`, `/holidays`, `/users`, `/events`, `/liveness/*`, `/verify`, `/identify`, `/metrics`.

---

## 15. Acceptance criteria (release checklist)

A build matches this PRD when:

1. An employee with a photo can check in; without a photo they cannot.
2. HR sees Today update without a manual refresh.
3. Kiosk identifies from the gallery and resets after success/fail.
4. With location lock **on**, a check-in with no GPS or a far coordinate is rejected; a coordinate inside the radius can succeed.
5. With location lock **on**, kiosk check-in still succeeds without GPS.
6. Admin can create an HR user from **Staff**.
7. Reports CSV and activity CSV download.
8. Lab charts load when `reports/evaluation.json` exists.
9. Backend tests and frontend tests pass.

---

## 16. Glossary

| Term | Meaning |
|------|---------|
| **Person** | Workplace identity (name, employee ID, face embeddings). |
| **User** | Login account with a role; employees are linked to one person. |
| **Gallery** | Searchable set of enrolled embeddings. |
| **Verify (1:1)** | Is this face the claimed person? |
| **Identify (1:N)** | Who is this face among enrolled people? |
| **TAR / FAR** | True-accept rate / false-accept rate. |
| **Liveness** | Evidence the camera sees a live person (blink), not a photo. |
| **Geofence** | Circle around the office; phone check-in must fall inside it. |
| **Kiosk** | Staff-supervised entrance device, fullscreen. |
| **Entrance screen** | TV board at `/board` showing who is in. |

---

## 17. Document control

| Version | Date | Notes |
|---------|------|--------|
| 1.0 | 26 Aug 2026 | First full PRD for Sentinel as a face-attendance product, matching the implemented app. |

**Owner:** Product / project lead  
**Reviewers:** Engineering, HR operations (customer)  
**Related:** `README.md` (setup and evaluation), `reports/TAR_FAR_REPORT.md` (encoder numbers)
