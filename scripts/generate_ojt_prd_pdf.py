#!/usr/bin/env python3
"""Build the Polaris-branded OJT PRD PDF (v1.1 resubmit).

Addresses mentor feedback (Soumen Mukherjee):
1. True multimodal: Vision (face) + Language (LLM text) - blink is only anti-spoof inside vision.
2. PostGIS geospatial component in the reference stack.
3. Full 16-chapter documentation with DB schemas, API specs, and RTM.
"""

from __future__ import annotations

from pathlib import Path

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_JUSTIFY, TA_LEFT
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import inch
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import (
    ListFlowable,
    ListItem,
    PageBreak,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "docs" / "OJT-PRD.pdf"
LOGO = ROOT / "docs" / "assets" / "polaris-logo.png"

NAVY = colors.Color(26 / 255, 54 / 255, 93 / 255)
TABLE_HEAD = colors.Color(235 / 255, 248 / 255, 255 / 255)
TABLE_GRID = colors.Color(180 / 255, 198 / 255, 220 / 255)
ORANGE = colors.Color(245 / 255, 166 / 255, 35 / 255)
BODY = colors.Color(0.12, 0.12, 0.12)
MUTED = colors.Color(0.35, 0.38, 0.42)

MARGIN_L = 0.75 * inch
MARGIN_R = 0.75 * inch
MARGIN_T = 1.0 * inch
MARGIN_B = 0.65 * inch


def _register_fonts() -> tuple[str, str]:
    regular = "/System/Library/Fonts/Supplemental/Arial.ttf"
    bold = "/System/Library/Fonts/Supplemental/Arial Bold.ttf"
    pdfmetrics.registerFont(TTFont("PRDBody", regular))
    pdfmetrics.registerFont(TTFont("PRDBold", bold))
    return "PRDBody", "PRDBold"


def _styles(body: str, bold: str) -> dict[str, ParagraphStyle]:
    base = getSampleStyleSheet()
    s: dict[str, ParagraphStyle] = {}
    s["title"] = ParagraphStyle(
        "prd_title", parent=base["Title"], fontName=bold, fontSize=18, leading=22,
        textColor=NAVY, spaceAfter=3, alignment=TA_LEFT,
    )
    s["subtitle"] = ParagraphStyle(
        "prd_sub", parent=base["Normal"], fontName=bold, fontSize=12, leading=15,
        textColor=NAVY, spaceAfter=8,
    )
    s["course"] = ParagraphStyle(
        "prd_course", parent=base["Normal"], fontName=body, fontSize=9, leading=12,
        textColor=BODY, spaceAfter=8,
    )
    s["h1"] = ParagraphStyle(
        "prd_h1", parent=base["Heading1"], fontName=bold, fontSize=12, leading=15,
        textColor=NAVY, spaceBefore=12, spaceAfter=6,
    )
    s["h2"] = ParagraphStyle(
        "prd_h2", parent=base["Heading2"], fontName=bold, fontSize=10.5, leading=13,
        textColor=NAVY, spaceBefore=8, spaceAfter=4,
    )
    s["h3"] = ParagraphStyle(
        "prd_h3", parent=base["Heading3"], fontName=bold, fontSize=9.5, leading=12,
        textColor=NAVY, spaceBefore=6, spaceAfter=3,
    )
    s["body"] = ParagraphStyle(
        "prd_body", parent=base["Normal"], fontName=body, fontSize=9, leading=11.8,
        textColor=BODY, alignment=TA_JUSTIFY, spaceAfter=5,
    )
    s["bullet"] = ParagraphStyle(
        "prd_bullet", parent=base["Normal"], fontName=body, fontSize=9, leading=11.5,
        textColor=BODY, leftIndent=6, spaceAfter=1.5,
    )
    s["cell"] = ParagraphStyle(
        "prd_cell", parent=base["Normal"], fontName=body, fontSize=8, leading=10.5, textColor=BODY,
    )
    s["cell_b"] = ParagraphStyle(
        "prd_cell_b", parent=base["Normal"], fontName=bold, fontSize=8, leading=10.5, textColor=BODY,
    )
    s["head_cell"] = ParagraphStyle(
        "prd_head_cell", parent=base["Normal"], fontName=bold, fontSize=8, leading=10.5, textColor=NAVY,
    )
    s["note"] = ParagraphStyle(
        "prd_note", parent=base["Normal"], fontName=body, fontSize=8, leading=10.5,
        textColor=MUTED, spaceAfter=6,
    )
    s["mono"] = ParagraphStyle(
        "prd_mono", parent=base["Normal"], fontName=body, fontSize=7.5, leading=10,
        textColor=BODY, leftIndent=8, spaceAfter=1,
    )
    return s


def _header_footer(canvas, doc) -> None:
    canvas.saveState()
    page_w, page_h = letter
    if LOGO.exists():
        logo_w = 1.3 * inch
        logo_h = logo_w * (552 / 2301)
        canvas.drawImage(
            str(LOGO), page_w - MARGIN_R - logo_w + 0.05 * inch, page_h - 0.7 * inch,
            width=logo_w, height=logo_h, mask="auto", preserveAspectRatio=True,
        )
    canvas.setStrokeColor(ORANGE)
    canvas.setFillColor(ORANGE)
    canvas.setLineWidth(1.5)
    y = page_h - 0.85 * inch
    canvas.line(MARGIN_L, y, page_w - MARGIN_R, y)
    canvas.setFont("PRDBody", 7.5)
    canvas.setFillColor(MUTED)
    canvas.drawCentredString(
        page_w / 2, 0.38 * inch,
        f"Polaris School of Technology - OJT PRD v1.1 - Page {doc.page}",
    )
    canvas.restoreState()


def _table(data: list[list], col_widths: list[float], styles: dict) -> Table:
    wrapped: list[list] = []
    for r_i, row in enumerate(data):
        out_row = []
        for c_i, cell in enumerate(row):
            if isinstance(cell, Paragraph):
                out_row.append(cell)
            else:
                style = styles["head_cell"] if r_i == 0 else (
                    styles["cell_b"] if c_i == 0 else styles["cell"]
                )
                out_row.append(Paragraph(str(cell), style))
        wrapped.append(out_row)
    t = Table(wrapped, colWidths=col_widths, hAlign="LEFT", repeatRows=1)
    t.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), TABLE_HEAD),
                ("GRID", (0, 0), (-1, -1), 0.5, TABLE_GRID),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("LEFTPADDING", (0, 0), (-1, -1), 5),
                ("RIGHTPADDING", (0, 0), (-1, -1), 5),
                ("TOPPADDING", (0, 0), (-1, -1), 3.5),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 3.5),
                ("BACKGROUND", (0, 1), (-1, -1), colors.white),
            ]
        )
    )
    return t


def _bullets(items: list[str], styles: dict) -> ListFlowable:
    return ListFlowable(
        [ListItem(Paragraph(i, styles["bullet"]), leftIndent=10, value="•") for i in items],
        bulletType="bullet",
        start="•",
        leftIndent=12,
        bulletFontName="PRDBody",
        bulletFontSize=9,
        spaceBefore=1,
        spaceAfter=4,
    )


def build() -> Path:
    body, bold = _register_fonts()
    styles = _styles(body, bold)
    story: list = []
    W = 7.0 * inch  # usable width approx

    # ---------- cover ----------
    story.append(Paragraph("Product Requirement Document (PRD)", styles["title"]))
    story.append(Paragraph("Face Attendance System (Sentinel)", styles["subtitle"]))
    story.append(
        Paragraph(
            "<b>Course / Track:</b> On-the-Job Training (OJT) Project Framework<br/>"
            "<b>Track:</b> Multimodal AI (Computer Vision + Language / LLM)<br/>"
            "<b>Document:</b> Comprehensive PRD v1.1 (16 chapters) - Resubmit after mentor review<br/>"
            "<b>Status:</b> Addresses feedback from Soumen Mukherjee (2026-09-03)",
            styles["course"],
        )
    )
    story.append(
        Paragraph(
            "<b>Revision note:</b> v1.0 incorrectly treated blink (a second visual cue) as the multimodal "
            "partner. v1.1 defines <b>Vision + Language (LLM)</b> as the two modalities, adds "
            "<b>PostGIS</b> as the geospatial layer, and expands to a full 16-chapter package with "
            "database schemas, API specifications, and a requirements traceability matrix.",
            styles["note"],
        )
    )

    # ========== 1 ==========
    story.append(Paragraph("Chapter 1 - Document Overview &amp; Metadata", styles["h1"]))
    story.append(
        _table(
            [
                ["Field", "Description / Student Inputs"],
                ["Project Title", "Face Attendance System (working name: Sentinel)"],
                ["Project Track", "Multimodal AI - Vision + Language (LLM)"],
                ["Team Members &amp; IDs", "Pratyksh Gupta - MSU ID: 240410700133"],
                ["Assigned Mentor", "Soumen Mukherjee"],
                ["Document Version &amp; Date", "v1.1 | 3 September 2026 (resubmit)"],
                ["Primary deliverable", "Deployed full-stack multimodal AI app: Web UI + REST API"],
                ["Domain", "Computer Vision + NLP/LLM - automate attendance &amp; org Q&amp;A"],
                ["Reference papers", "ArcFace (CVPR 2019); FaceNet (CVPR 2015); RAG (Lewis et al., 2020)"],
                ["Eval dataset", "LFW View 2 (face); org attendance corpus + WikiQA-style FAQ for RAG lab"],
            ],
            [2.0 * inch, 5.0 * inch],
            styles,
        )
    )
    story.append(Paragraph("<b>Document map (16 chapters)</b>", styles["h3"]))
    story.append(
        _table(
            [
                ["Ch.", "Title"],
                ["1", "Document Overview &amp; Metadata"],
                ["2", "Executive Summary &amp; Problem Statement"],
                ["3", "Goals, Scope &amp; Success Metrics"],
                ["4", "Stakeholders, Personas &amp; User Journeys"],
                ["5", "System Architecture &amp; High-Level Design"],
                ["6", "Technical Stack &amp; Infrastructure"],
                ["7", "Functional Requirements"],
                ["8", "Non-Functional Requirements"],
                ["9", "Data Strategy &amp; Full Database Schema"],
                ["10", "API Specification"],
                ["11", "Track D - Multimodal AI (Vision + Language)"],
                ["12", "Geospatial Design (PostGIS)"],
                ["13", "UI/UX &amp; Presentation Layer"],
                ["14", "Testing, QA &amp; Validation"],
                ["15", "Deployment, CI/CD &amp; Milestones"],
                ["16", "Risk Management &amp; Requirements Traceability Matrix"],
            ],
            [0.6 * inch, 6.4 * inch],
            styles,
        )
    )

    # ========== 2 ==========
    story.append(Paragraph("Chapter 2 - Executive Summary &amp; Problem Statement", styles["h1"]))
    story.append(Paragraph("2.1 Problem Statement", styles["h2"]))
    story.append(
        Paragraph(
            "Schools, campuses, and workplaces still mark attendance with paper registers, shared PINs, "
            "RFID cards, or a remote “I am here” button. These methods are easy to share, easy to fake, "
            "and hard to audit. Separately, staff and managers ask the same questions every morning "
            "(“Who is late?”, “Is Rohan present?”, “Who still has no photo?”) and get answers only by "
            "scrolling spreadsheets.",
            styles["body"],
        )
    )
    story.append(
        Paragraph(
            "This project builds a <b>multimodal face attendance platform</b>: a camera proves "
            "<b>who</b> is present (vision), and a natural-language assistant answers "
            "<b>what the attendance record means</b> (language / LLM). Check-in can also be locked "
            "to an organisation site using <b>PostGIS</b> geofences so a remote punch fails.",
            styles["body"],
        )
    )
    story.append(Paragraph("2.2 Why current solutions are insufficient", styles["h2"]))
    story.append(
        _bullets(
            [
                "Consumer face unlock is one device / one user - not a multi-person org gallery with HR dashboards.",
                "Pure CV demos rarely expose evaluation (TAR@FAR) or a language layer for operators.",
                "Spreadsheets answer questions slowly and do not ground answers in live attendance rows.",
                "Haversine-only geofence prototypes do not meet the reference requirement for PostGIS spatial types and queries.",
            ],
            styles,
        )
    )

    # ========== 3 ==========
    story.append(Paragraph("Chapter 3 - Goals, Scope &amp; Success Metrics", styles["h1"]))
    story.append(Paragraph("3.1 Primary goals", styles["h2"]))
    story.append(
        _bullets(
            [
                "Enroll faces; identify people at check-in with a published encoder (ArcFace / FaceNet).",
                "Fuse <b>vision identity</b> with optional blink anti-spoof (vision-internal), then write attendance.",
                "Provide a <b>text / LLM assistant</b> that answers attendance questions with grounded SQL / RAG retrieval.",
                "Enforce site presence with <b>PostgreSQL + PostGIS</b> (<font face='Courier'>geography</font>, "
                "<font face='Courier'>ST_DWithin</font>).",
                "Ship a React web app + FastAPI REST API with JWT roles (platform admin, org admin/HR, employee).",
            ],
            styles,
        )
    )
    story.append(Paragraph("3.2 Success metrics", styles["h2"]))
    story.append(
        _table(
            [
                ["Metric", "Target"],
                ["Dashboard load", "&lt; 2 s on campus Wi-Fi"],
                ["Authentication", "JWT; hashed passwords; role-restricted routes"],
                ["CRUD accuracy", "Person create/update/deactivate visible on dashboard"],
                ["Report generation", "CSV export; LLM answers cite attendance facts"],
                ["UI", "Responsive desktop + phone browser"],
                ["Recognition", "TAR@FAR = 1e-3 on LFW View 2; threshold from that curve"],
                ["Check-in latency", "Detect + embed + match &lt; 1 s CPU (one face)"],
                ["Geofence", "PostGIS ST_DWithin; outside radius → reject"],
                ["LLM grounding", "≥ 90% of lab FAQ answers cite a retrieved attendance / person row"],
            ],
            [2.0 * inch, 5.0 * inch],
            styles,
        )
    )
    story.append(Paragraph("3.3 In scope / out of scope", styles["h2"]))
    story.append(
        _table(
            [
                ["In scope (v1.1)", "Out of scope"],
                [
                    "Org login, face enroll/check-in, Today dashboard, CSV, LLM chat, PostGIS geofence, blink anti-spoof",
                    "Payroll/leave, native mobile stores, training a face net from scratch on private mega-data, certified ISO PAD",
                ],
            ],
            [3.5 * inch, 3.5 * inch],
            styles,
        )
    )

    # ========== 4 ==========
    story.append(PageBreak())
    story.append(Paragraph("Chapter 4 - Stakeholders, Personas &amp; User Journeys", styles["h1"]))
    story.append(
        _table(
            [
                ["Persona", "Needs"],
                ["Platform admin", "Create organisations; open any org; no org code at login"],
                ["Org admin / HR", "Enroll faces, set sites/geofence, Today board, ask LLM “who is late?”"],
                ["Employee", "Org code + login; camera check-in; see own history"],
                ["Reception / operator", "Kiosk check-in; verify faces in lab"],
                ["Mentor / evaluator", "Measurable multimodal fusion, PostGIS, full docs"],
            ],
            [1.8 * inch, 5.2 * inch],
            styles,
        )
    )
    story.append(Paragraph("4.1 Journey - face check-in (vision)", styles["h2"]))
    story.append(
        Paragraph(
            "Employee enters org code → signs in → camera captures frame (+ blink burst if required) → "
            "GPS sent when geofence active → PostGIS tests point-in-radius → face embed + gallery match → "
            "present row written → Today board updates.",
            styles["body"],
        )
    )
    story.append(Paragraph("4.2 Journey - language assistant (LLM)", styles["h2"]))
    story.append(
        Paragraph(
            "HR opens Assist → types “Who is still not in today?” → retriever pulls attendance + person "
            "rows (and optional FAQ docs) → LLM answers in plain language with cited names/times → "
            "HR can open the person record. The assistant never marks attendance by itself; vision check-in does.",
            styles["body"],
        )
    )

    # ========== 5 ==========
    story.append(Paragraph("Chapter 5 - System Architecture &amp; High-Level Design", styles["h1"]))
    story.append(Paragraph("5.1 End-to-end pipeline", styles["h2"]))
    story.append(
        _table(
            [
                ["Stage", "Description"],
                [
                    "Data ingestion",
                    "Webcam / upload images (vision); user text prompts (language); browser GPS for punches; "
                    "LFW offline for face eval; FAQ / wiki snippets for RAG",
                ],
                [
                    "Vision engine",
                    "SCRFD detect → 5-pt align → ArcFace/FaceNet embed → FAISS cosine gallery; blink/texture anti-spoof",
                ],
                [
                    "Language engine",
                    "Embed query → retrieve attendance/person/FAQ chunks → LLM generate grounded answer (RAG)",
                ],
                [
                    "Fusion",
                    "Late fusion of modalities: vision decides identity/presence; language consumes structured "
                    "events + text. Cross-modal handoff via shared person_id / attendance_id",
                ],
                [
                    "Storage",
                    "PostgreSQL + PostGIS (prod); SQLite ok for pure unit tests; FAISS gallery; vector store for RAG chunks",
                ],
                ["Presentation", "React + Vite SPA; FastAPI /api/v1"],
            ],
            [1.5 * inch, 5.5 * inch],
            styles,
        )
    )
    story.append(Paragraph("5.2 Architecture diagram (logical)", styles["h2"]))
    for line in [
        "React SPA  --JWT/images/text/GPS-->  FastAPI (/api/v1)",
        "   |-- /attendance/check-in --> Vision pipeline --> Gallery match --> Attendance row",
        "   |-- /assist/chat ---------> Retriever + LLM (RAG) --> Grounded answer",
        "   |-- /schedule/sites ------> PostGIS geography CRUD + ST_DWithin gate",
        "PostgreSQL+PostGIS | FAISS face gallery | Chunk/vector index (RAG)",
    ]:
        story.append(Paragraph(line.replace(" ", "&nbsp;"), styles["mono"]))

    # ========== 6 ==========
    story.append(Paragraph("Chapter 6 - Technical Stack &amp; Infrastructure", styles["h1"]))
    story.append(
        _table(
            [
                ["Component", "Chosen", "Rationale"],
                ["Frontend / UI", "React, Vite, TypeScript, Tailwind", "SPA for dashboard + chat; fast iteration"],
                ["Backend API", "FastAPI, Uvicorn, SQLModel", "Same language as CV; OpenAPI; uploads"],
                ["ML / Vision", "OpenCV, SCRFD, ArcFace ONNX / FaceNet", "Published encoders; CPU ONNX Runtime"],
                ["ML / Language", "Sentence embeddings + LLM API (or local SLM)", "RAG over attendance + FAQ; tool-calling for SQL"],
                ["Database", "PostgreSQL + <b>PostGIS</b>", "Required geospatial types/queries; org data"],
                ["Vector / search", "FAISS (faces); pgvector or FAISS (text chunks)", "Face cosine + RAG retrieval"],
                ["Deployment", "Docker Compose; Render/Railway/VM", "API + web + Postgres/PostGIS"],
            ],
            [1.35 * inch, 2.4 * inch, 3.25 * inch],
            styles,
        )
    )
    story.append(
        Paragraph(
            "Assigned core stack remains Python + OpenCV + React + FastAPI. <b>PostGIS is mandatory</b> "
            "on the production database path (mentor / reference stack). Local SQLite may run UI tests "
            "without geo; any geofence acceptance test runs against Postgres+PostGIS.",
            styles["body"],
        )
    )

    # ========== 7 ==========
    story.append(Paragraph("Chapter 7 - Functional Requirements", styles["h1"]))
    story.append(
        _table(
            [
                ["ID", "Requirement"],
                ["FR-01", "Platform admin creates organisations (slug, type) and can impersonate org context"],
                ["FR-02", "Org users login with organization code + username + password (JWT)"],
                ["FR-03", "Admin/HR CRUD people; enroll 1-5 face photos; deactivate removes from gallery"],
                ["FR-04", "Employee/kiosk check-in with webcam; present only if similarity ≥ τ"],
                ["FR-05", "Optional blink challenge rejects still-photo bursts (vision anti-spoof, not modality #2)"],
                ["FR-06", "When geofence on, check-in must send lat/lng; PostGIS ST_DWithin must pass"],
                ["FR-07", "Today dashboard: present / late / not in / waiting for photo"],
                ["FR-08", "CSV export of attendance for a date range"],
                ["FR-09", "LLM Assist: natural-language Q&amp;A over attendance + people + FAQ with citations"],
                ["FR-10", "Sites CRUD with PostGIS geography point + radius_m"],
                ["FR-11", "Health endpoint reports encoder, gallery size, thresholds"],
                ["FR-12", "Role gates: employee cannot list all attendance; HR can"],
            ],
            [0.8 * inch, 6.2 * inch],
            styles,
        )
    )

    # ========== 8 ==========
    story.append(Paragraph("Chapter 8 - Non-Functional Requirements", styles["h1"]))
    story.append(
        _bullets(
            [
                "<b>Performance:</b> dashboard &lt; 2 s; face inference &lt; 1 s CPU; LLM first token &lt; 5 s typical.",
                "<b>Scalability:</b> one org / campus (hundreds of identities); few concurrent check-ins.",
                "<b>Security &amp; privacy:</b> hashed passwords; JWT expiry; HTTPS; biometric faces not public; "
                "LLM sees only org-scoped retrieved rows.",
                "<b>Reliability:</b> reject bad frames; 503 if encoder down; geofence fail-closed when required.",
                "<b>Observability:</b> access events + spoof/liveness logs; assist queries logged without raw secrets.",
            ],
            styles,
        )
    )

    # ========== 9 ==========
    story.append(PageBreak())
    story.append(Paragraph("Chapter 9 - Data Strategy &amp; Full Database Schema", styles["h1"]))
    story.append(Paragraph("9.1 Data sources", styles["h2"]))
    story.append(
        _bullets(
            [
                "Live enrollment photos and check-in frames (org biometric data).",
                "Punch GPS coordinates validated in PostGIS.",
                "LFW for offline face TAR@FAR (not mixed into live gallery).",
                "Org FAQ / policy snippets + generated attendance summaries for RAG (WikiQA-style lab set optional).",
            ],
            styles,
        )
    )
    story.append(Paragraph("9.2 Core relational schema (PostgreSQL)", styles["h2"]))
    story.append(
        _table(
            [
                ["Table", "Key columns"],
                [
                    "organization",
                    "id, name, slug UNIQUE, tz, work_start/end, geo_lat, geo_lng, geo_radius_m, "
                    "geofence_on_self_punch, org_type, kernel, labels…",
                ],
                ["platform_user", "id, username UNIQUE, hashed_password, is_admin, role"],
                [
                    "user",
                    "id, org_id, username, hashed_password, role, is_admin, person_id UNIQUE; "
                    "UNIQUE(org_id, username)",
                ],
                [
                    "person",
                    "id, org_id, name, employee_id, email, department, is_active, deactivated_at; "
                    "UNIQUE(org_id, employee_id)",
                ],
                [
                    "site",
                    "id, org_id, name, lat, lng, radius_m, is_default, "
                    "<b>geom geography(Point,4326)</b> generated/stored for PostGIS",
                ],
                [
                    "faceembedding",
                    "id, person_id, encoder, dim, vector (float[]/bytea), quality_json",
                ],
                [
                    "attendance",
                    "id, org_id, person_id, user_id, site_id, decision, similarity, encoder, source, "
                    "late, latitude, longitude, <b>punch_geom geography(Point,4326)</b>, checked_out_at, created_at",
                ],
                ["accessevent", "id, org_id, kind, person_id, decision, similarity, detail, created_at"],
                ["holiday", "id, org_id, day, name"],
                ["spoofalert", "id, org_id, actor_user_id, person_id, reason, image, created_at"],
                [
                    "assist_chunk",
                    "id, org_id, source_type, source_id, text, embedding vector - RAG chunks",
                ],
                ["assist_message", "id, org_id, user_id, role, content, citations_json, created_at"],
            ],
            [1.5 * inch, 5.5 * inch],
            styles,
        )
    )
    story.append(Paragraph("9.3 PostGIS DDL (excerpt)", styles["h2"]))
    for line in [
        "CREATE EXTENSION IF NOT EXISTS postgis;",
        "ALTER TABLE site ADD COLUMN geom geography(Point,4326);",
        "UPDATE site SET geom = ST_SetSRID(ST_MakePoint(lng, lat),4326)::geography;",
        "CREATE INDEX site_geom_gix ON site USING GIST (geom);",
        "-- inside fence if: ST_DWithin(site.geom, punch_geom, radius_m)",
    ]:
        story.append(Paragraph(line.replace(" ", "&nbsp;"), styles["mono"]))
    story.append(Paragraph("9.4 Privacy &amp; versioning", styles["h2"]))
    story.append(
        Paragraph(
            "Faces are biometric-class data: org-scoped storage; deactivate deletes gallery vectors. "
            "Code + PRD on GitHub; weights via download scripts; evaluation.json versioned; "
            "DVC/Git LFS optional for large assets.",
            styles["body"],
        )
    )

    # ========== 10 ==========
    story.append(Paragraph("Chapter 10 - API Specification", styles["h1"]))
    story.append(
        Paragraph(
            "Base URL: <font face='Courier'>/api/v1</font>. Auth: "
            "<font face='Courier'>Authorization: Bearer &lt;JWT&gt;</font>. "
            "Platform admin may send <font face='Courier'>X-Org-Id</font>.",
            styles["body"],
        )
    )
    story.append(Paragraph("10.1 Auth &amp; identity", styles["h2"]))
    story.append(
        _table(
            [
                ["Method", "Path", "Purpose"],
                ["GET", "/auth/config", "Public flags, org labels, geofence, default site"],
                ["POST", "/auth/login", "Body: username, password, org?; → access_token"],
                ["POST", "/auth/register", "Employee signup when allowed"],
                ["GET", "/auth/me", "User + linked person + org"],
                ["POST", "/auth/password", "Change password"],
            ],
            [0.9 * inch, 2.0 * inch, 4.1 * inch],
            styles,
        )
    )
    story.append(Paragraph("10.2 People &amp; enrollment", styles["h2"]))
    story.append(
        _table(
            [
                ["Method", "Path", "Purpose"],
                ["GET/POST", "/persons", "List / create"],
                ["GET/PATCH", "/persons/{id}", "Read / update"],
                ["DELETE", "/persons/{id}", "Soft deactivate"],
                ["POST", "/persons/{id}/enroll", "multipart images → embeddings"],
                ["POST", "/persons/{id}/login", "Create linked user login"],
                ["GET", "/persons/{id}/timeline", "Attendance + events"],
            ],
            [1.1 * inch, 2.3 * inch, 3.6 * inch],
            styles,
        )
    )
    story.append(Paragraph("10.3 Attendance &amp; geofence punches", styles["h2"]))
    story.append(
        _table(
            [
                ["Method", "Path", "Purpose"],
                ["POST", "/attendance/check-in", "image + lat/lng + challenge_id? → present/reject"],
                ["POST", "/attendance/check-out", "Optional face verify"],
                ["POST", "/attendance/kiosk", "Staff kiosk face or PIN"],
                ["GET", "/attendance/today", "Caller’s today status"],
                ["GET", "/attendance", "HR list (from/to/filters)"],
                ["GET", "/attendance/export", "CSV download"],
                ["POST", "/attendance/manual", "HR override"],
            ],
            [0.9 * inch, 2.4 * inch, 3.7 * inch],
            styles,
        )
    )
    story.append(
        Paragraph(
            "Check-in error codes: <font face='Courier'>no_face</font>, "
            "<font face='Courier'>no_match</font>, <font face='Courier'>liveness_failed</font>, "
            "<font face='Courier'>location_required</font>, <font face='Courier'>outside_geofence</font>.",
            styles["body"],
        )
    )
    story.append(Paragraph("10.4 Sites, assist (LLM), vision lab", styles["h2"]))
    story.append(
        _table(
            [
                ["Method", "Path", "Purpose"],
                ["GET/POST", "/schedule/sites", "List / create PostGIS sites"],
                ["PATCH/DELETE", "/schedule/sites/{id}", "Update / delete site"],
                ["POST", "/assist/chat", "Body: {message} → {answer, citations[]}"],
                ["GET", "/assist/history", "Prior assist messages"],
                ["POST", "/verify", "Two-image similarity (lab)"],
                ["POST", "/identify", "1:N identify"],
                ["POST", "/liveness/challenge|/check", "Blink challenge session"],
                ["GET", "/ops/summary", "Today board aggregates"],
                ["GET", "/health", "Encoder, gallery, thresholds"],
            ],
            [1.2 * inch, 2.5 * inch, 3.3 * inch],
            styles,
        )
    )
    story.append(Paragraph("10.5 Example payloads", styles["h2"]))
    story.append(
        Paragraph(
            "<b>POST /assist/chat</b> request: "
            "<font face='Courier'>{\"message\": \"Who is late today?\"}</font><br/>"
            "response: <font face='Courier'>{\"answer\": \"Rohan (EMP-12) checked in at 09:42 (late).\", "
            "\"citations\": [{\"type\": \"attendance\", \"id\": 104}]}</font>",
            styles["body"],
        )
    )

    # ========== 11 ==========
    story.append(PageBreak())
    story.append(Paragraph("Chapter 11 - Track D: Multimodal AI (Vision + Language)", styles["h1"]))
    story.append(
        Paragraph(
            "<b>Mentor correction (v1.1):</b> Pairing a static face crop with a blink video is "
            "<i>not</i> two modalities - both are vision. The required second modality is "
            "<b>language / text via an LLM</b> (audio may be added later as speech-to-text into the same text channel).",
            styles["note"],
        )
    )
    story.append(Paragraph("11.1 Multimodal data fusion", styles["h2"]))
    story.append(
        _table(
            [
                ["Stream", "Modality", "Role"],
                ["A - Vision", "RGB face image (+ optional blink burst)", "Who is present? Anti-spoof inside vision"],
                ["B - Language", "Natural language text (+ optional STT audio→text)", "What does attendance mean? Org Q&amp;A"],
            ],
            [1.4 * inch, 2.6 * inch, 3.0 * inch],
            styles,
        )
    )
    story.append(
        Paragraph(
            "<b>Fusion strategy:</b> <i>Late / decision-level fusion with shared identifiers.</i> "
            "Vision writes <font face='Courier'>attendance</font> rows keyed by "
            "<font face='Courier'>person_id</font>. The language stack retrieves those rows (and FAQ "
            "chunks), then an LLM generates an answer. We do not claim early pixel-text cross-attention "
            "transformers for v1; RAG + structured tools is the track-appropriate fusion.",
            styles["body"],
        )
    )
    story.append(Paragraph("11.2 Model architecture", styles["h2"]))
    story.append(
        _bullets(
            [
                "<b>Vision:</b> SCRFD → align → ArcFace/FaceNet → 512-D → FAISS cosine; blink/EAR + freeze cues.",
                "<b>Language:</b> query embedder → top-k chunk / SQL tool retrieval → LLM (API or local SLM) "
                "with citation prompt template.",
                "<b>Reference:</b> Deng et al., ArcFace (CVPR 2019); Schroff et al., FaceNet (CVPR 2015); "
                "Lewis et al., RAG for Knowledge-Intensive NLP (2020).",
            ],
            styles,
        )
    )
    story.append(Paragraph("11.3 Fine-tuning &amp; prompt strategy", styles["h2"]))
    story.append(
        _bullets(
            [
                "Face encoder: prefer published weights; optional small FaceNet fine-tune with LFW identities excluded.",
                "LLM: prompt templates force “answer only from retrieved rows; say unknown if missing.”",
                "Optional PEFT/LoRA on a small SLM in Month 3 if API cost / offline demo requires it.",
            ],
            styles,
        )
    )
    story.append(Paragraph("11.4 XAI, safety &amp; latency", styles["h2"]))
    story.append(
        _bullets(
            [
                "Vision XAI: show similarity, match name, failure reason codes; lab verify cosine.",
                "Language XAI: show citations (attendance id / person id / FAQ chunk).",
                "Safety: no attendance mutation from chat; org isolation on retrieval; hallucination → “I don’t know”.",
                "Metrics: face TAR@FAR; assist grounded-answer rate; RAGAS-style faithfulness on a 50-Q lab set.",
                "Latency: exact face cosine for small N; cache FAQ embeddings; bound LLM context.",
            ],
            styles,
        )
    )

    # ========== 12 ==========
    story.append(Paragraph("Chapter 12 - Geospatial Design (PostGIS)", styles["h1"]))
    story.append(
        Paragraph(
            "The reference stack requires a <b>PostGIS</b> geospatial component. Attendance punches are "
            "not trusted without a spatial predicate against organisation sites.",
            styles["body"],
        )
    )
    story.append(Paragraph("12.1 Spatial model", styles["h2"]))
    story.append(
        _bullets(
            [
                "Each <font face='Courier'>site</font> stores <font face='Courier'>lat</font>, "
                "<font face='Courier'>lng</font>, <font face='Courier'>radius_m</font> and "
                "<font face='Courier'>geom geography(Point,4326)</font>.",
                "Each punch stores <font face='Courier'>latitude</font>, <font face='Courier'>longitude</font> "
                "and <font face='Courier'>punch_geom</font>.",
                "Gate: <font face='Courier'>ST_DWithin(site.geom, punch_geom, radius_m)</font> "
                "(metre distances on geography).",
                "Org-level office fence uses the same pattern when no multi-site list exists.",
            ],
            styles,
        )
    )
    story.append(Paragraph("12.2 Behavioural rules", styles["h2"]))
    story.append(
        _table(
            [
                ["Condition", "System behaviour"],
                ["geofence_on_self_punch = false", "GPS optional; no PostGIS reject"],
                ["geofence on, GPS missing", "400 location_required"],
                ["Point outside all fenced sites", "403 outside_geofence"],
                ["Kiosk on trusted device", "Policy may skip GPS; still logged"],
            ],
            [2.8 * inch, 4.2 * inch],
            styles,
        )
    )
    story.append(Paragraph("12.3 Why not Haversine-only", styles["h2"]))
    story.append(
        Paragraph(
            "A Python Haversine helper may remain as a fallback for SQLite unit tests, but production "
            "deployments <b>must</b> enable PostGIS and execute spatial checks in SQL so the reference "
            "stack and indexing (GiST) are real, reviewable artefacts.",
            styles["body"],
        )
    )

    # ========== 13 ==========
    story.append(Paragraph("Chapter 13 - UI/UX &amp; Presentation Layer", styles["h1"]))
    story.append(
        _bullets(
            [
                "Login: org code + username/password; catchy org-focused hero copy.",
                "Employee: Check in (camera oval), My attendance calendar.",
                "HR: Today board, People, Enroll, Sites/geofence, Reports/CSV, <b>Assist (LLM chat)</b>.",
                "Lab: Verify / Identify / Liveness for operators.",
                "Default theme: light; optional dark toggle. Responsive layout. Dashboard load &lt; 2 s.",
            ],
            styles,
        )
    )

    # ========== 14 ==========
    story.append(Paragraph("Chapter 14 - Testing, QA &amp; Validation", styles["h1"]))
    story.append(
        _bullets(
            [
                "<b>Unit/integration:</b> Pytest for auth, enroll, check-in shape, CSV, role 403s, "
                "assist citation schema; Vitest for login/dashboard.",
                "<b>Model:</b> LFW View 2 TAR@FAR; still-photo fails blink; RAG faithfulness on fixed FAQ set.",
                "<b>PostGIS:</b> Dockerized Postgres+PostGIS tests - inside/outside radius fixtures.",
                "<b>Edge cases:</b> no face, multi-face, unknown visitor, deactivated person, GPS denied, "
                "LLM with empty retrieval → honest unknown.",
            ],
            styles,
        )
    )

    # ========== 15 ==========
    story.append(PageBreak())
    story.append(Paragraph("Chapter 15 - Deployment, CI/CD &amp; Milestones", styles["h1"]))
    story.append(Paragraph("15.1 Engineering practices", styles["h2"]))
    story.append(
        _bullets(
            [
                "GitHub: main / development / feature/* ; PRs; tags before vivas.",
                "Docker Compose: api, web, <b>postgres:postgis</b> image.",
                "CI: GitHub Actions - pytest (+ PostGIS service) + frontend build.",
                "Live URL + demo video by 25 November 2026.",
            ],
            styles,
        )
    )
    story.append(Paragraph("15.2 Milestone roadmap", styles["h2"]))
    story.append(
        _table(
            [
                ["Phase", "Deliverables", "Deadline"],
                ["PRD approval", "This v1.1 PRD reviewed/approved", "30 Aug - 3 Sept 2026"],
                ["GitHub base", "Repo layout, README, Compose with PostGIS", "6 September 2026"],
                [
                    "Viva 1",
                    "Face pipeline + TAR@FAR; JWT; schema; PostGIS sites DDL; assist stub",
                    "15-22 September 2026",
                ],
                [
                    "Viva 2",
                    "Enroll/check-in UI; geofence gate; LLM RAG chat; CSV; API tests",
                    "15-22 October 2026",
                ],
                [
                    "Viva 3",
                    "E2E polish; grounded-answer eval; Docker deploy; model card",
                    "15-22 November 2026",
                ],
                ["Final", "Live link + demo video", "25 November 2026"],
                ["External viva", "Defence + live demo", "15-22 December 2026"],
            ],
            [1.2 * inch, 3.8 * inch, 2.0 * inch],
            styles,
        )
    )

    # ========== 16 ==========
    story.append(Paragraph("Chapter 16 - Risk Management &amp; Requirements Traceability Matrix", styles["h1"]))
    story.append(Paragraph("16.1 Risks", styles["h2"]))
    story.append(
        _table(
            [
                ["Risk", "Severity", "Mitigation"],
                ["CPU / no GPU", "High", "ONNX ArcFace; Colab only if fine-tuning"],
                ["LLM cost / rate limits", "Medium", "Cache retrieval; local SLM fallback; tight prompts"],
                ["LLM hallucination", "High", "Citations required; refuse when retrieval empty"],
                ["False reject / accept", "High", "LFW τ; re-enroll; blink anti-spoof"],
                ["PostGIS ops complexity", "Medium", "Compose image; fallback tests documented"],
                ["Scope creep", "High", "Freeze FRs in Ch.7; stretch after Viva 2"],
            ],
            [2.2 * inch, 1.0 * inch, 3.8 * inch],
            styles,
        )
    )
    story.append(Paragraph("16.2 Requirements Traceability Matrix (RTM)", styles["h2"]))
    story.append(
        Paragraph(
            "Maps each functional requirement to design chapters, primary APIs/tables, and viva proof.",
            styles["note"],
        )
    )
    story.append(
        _table(
            [
                ["Req", "Design ch.", "Primary artefact", "Verification"],
                ["FR-01", "4, 9, 10", "organization, /orgs", "Viva 1 - create org"],
                ["FR-02", "4, 10", "POST /auth/login", "Viva 1 - JWT org login"],
                ["FR-03", "7, 9, 10", "person, faceembedding, /persons/*/enroll", "Viva 2 - enroll UI"],
                ["FR-04", "5, 11", "POST /attendance/check-in", "Viva 2 - present decision"],
                ["FR-05", "11, 14", "/liveness/*", "Still-photo fails test"],
                ["FR-06", "12, 9", "PostGIS ST_DWithin", "Inside/outside fixture"],
                ["FR-07", "13, 10", "GET /ops/summary", "Dashboard &lt; 2 s"],
                ["FR-08", "7, 10", "GET /attendance/export", "CSV download"],
                ["FR-09", "11, 10", "POST /assist/chat + assist_* tables", "Grounded FAQ ≥ 90%"],
                ["FR-10", "12, 10", "/schedule/sites + site.geom", "CRUD + GiST index"],
                ["FR-11", "10", "GET /health", "CI smoke"],
                ["FR-12", "8, 10", "role deps", "403 pytest"],
            ],
            [0.7 * inch, 1.0 * inch, 3.3 * inch, 2.0 * inch],
            styles,
        )
    )

    story.append(Spacer(1, 10))
    story.append(Paragraph("Appendix A - Roles (summary)", styles["h2"]))
    story.append(
        _table(
            [
                ["Role", "Capabilities"],
                ["Platform admin", "All orgs; no org code; X-Org-Id"],
                ["Org admin / HR", "People, enroll, sites, reports, Assist, Today"],
                ["Employee", "Check-in, own attendance"],
                ["Operator", "Kiosk + vision lab (no people admin)"],
            ],
            [1.6 * inch, 5.4 * inch],
            styles,
        )
    )
    story.append(Paragraph("Appendix B - Model card outline (Month 3)", styles["h2"]))
    story.append(
        _bullets(
            [
                "Vision input: aligned RGB crop → 512-D unit embedding; decision cosine ≥ τ @ FAR=1e-3 + anti-spoof.",
                "Language input: user text → retrieved org rows/chunks → LLM answer with citations.",
                "Limitations: lighting/pose/masks; LLM may abstain; geofence needs GPS permission.",
                "Ethics: workplace/school notice; delete embeddings on exit; org data isolation.",
            ],
            styles,
        )
    )
    story.append(Spacer(1, 8))
    story.append(
        Paragraph(
            "End of comprehensive PRD v1.1 - Face Attendance System (Multimodal AI: Vision + Language) - "
            "Polaris School of Technology OJT. Prepared for resubmit to mentor Soumen Mukherjee.",
            styles["note"],
        )
    )

    OUT.parent.mkdir(parents=True, exist_ok=True)
    doc = SimpleDocTemplate(
        str(OUT),
        pagesize=letter,
        leftMargin=MARGIN_L,
        rightMargin=MARGIN_R,
        topMargin=MARGIN_T,
        bottomMargin=MARGIN_B,
        title="Face Attendance System - OJT PRD v1.1",
        author="Pratyksh Gupta",
        subject="Polaris School of Technology - OJT Product Requirement Document (Resubmit)",
    )
    doc.build(story, onFirstPage=_header_footer, onLaterPages=_header_footer)
    return OUT


if __name__ == "__main__":
    path = build()
    print(f"Wrote {path}")
