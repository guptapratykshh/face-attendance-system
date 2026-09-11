# Competitive and Literature Analysis

**Project:** Sentinel Face Attendance Platform
**Purpose:** locate a defensible research contribution for the external publication track
**Date:** 11 September 2026

---

## 1. Executive summary

Sentinel's current technical differentiators - face recognition, PostGIS geofencing, and blink-based
liveness - are **already published**. At least five peer-reviewed 2025-26 systems combine face
recognition with GPS geofencing and liveness detection, and one of them already fuses five signals
into a single presence score. Swapping Haversine for PostGIS `ST_DWithin` is an engineering choice,
not a research contribution.

There is, however, a clean and currently unoccupied gap. Every attendance system in the literature
is evaluated **only against printed photos and screen replays**. None of them test **injection
attacks**, where an attacker feeds a deepfake directly into the browser through virtual camera
software and never presents anything to a physical camera. This matters directly for Sentinel,
because the active blink challenge it implements is documented to fail completely against that
attack class.

The recommended contribution is a **calibrated presence-trust score that fuses capture-path
integrity, content liveness, face match, and longitudinal spatio-temporal plausibility**, evaluated
under an injection threat model the attendance literature has never applied.

---

## 2. Commercial competitors

### 2.1 Feature and stack comparison

| Product | Positioning | Capture stack | Location | Anti-fraud | Integrations | Pricing |
|---|---|---|---|---|---|---|
| **Truein** | Contract, hourly, multi-site workforces | Android BYOD, no dedicated hardware; offline capture with deferred sync | GPS geofencing per site | "AI TimeGuard" anomaly layer over attendance data; blocks photo tricks, shared IDs, proxy punches | ADP, QuickBooks, Sage, Paychex, Xero | Quote-based, no free tier |
| **Jibble** | Low-cost general purpose | iOS, Android, web, desktop, Chrome extension, tablet kiosk | GPS with per-job-site geofences | Face recognition plus selfie verification; tamper-proof pay periods and audit trail | Slack, Microsoft Teams, SSO, 2FA | Free for unlimited users, paid tiers |
| **Spintly** | Wireless cloud access control first, attendance second | Dedicated face recognition reader; BLE, NFC, QR mobile credentials | Building and door level, not geofence | Physical access control model | Cloud API and SDK | Hardware plus subscription |
| **ZKTeco ZKBio Time** | Organisations already running ZKTeco terminals | Proprietary wall terminals, local capture | Terminal location is implicit | Device-level biometric matching | Centralised reporting | Perpetual plus hardware |
| **HROne / factoHR / ClockShark** | HRMS suites with attendance modules | Mobile plus web | GPS geofencing | Varies; mostly rule-based | Full payroll and statutory | Per employee per month |

### 2.2 What the market has converged on

Every serious commercial product now ships the same three primitives: **face capture on commodity
hardware, GPS geofencing, and offline-tolerant sync**. Truein is the only vendor advertising an
analytics layer over attendance history rather than per-punch checks alone, which it markets as AI
TimeGuard for detecting unusual correction activity and suspicious clock-in patterns.

Two observations matter for positioning:

- **Nobody advertises capture-path integrity.** No vendor in this segment claims virtual camera or
  injection detection. Fraud messaging is uniformly about "photo tricks" and "buddy punching",
  meaning presentation attacks only.
- **Anomaly detection is a differentiator vendors are just now reaching for.** Truein has it;
  Jibble and the HRMS suites do not. This confirms the commercial value of the behavioural half of
  the proposed contribution.

---

## 3. Academic landscape

### 3.1 The saturated cluster: face + geofence + liveness

| Work | Venue / year | Stack | Reported result |
|---|---|---|---|
| **HybridFaceNet** | IEEE, 2025 | YOLOv7 detection, lightweight FaceNet for edge, MediaPipe liveness, encrypted GPS geofencing, blockchain-secured logs, Django + TensorFlow | 96.8% accuracy, 40% false-positive reduction, 30 fps, 500+ subjects |
| **Web-Based Attendance with ArcFace, GPS and Liveness** | Smatika, 2025 | ArcFace / MobileFaceNet, MiniFASNet passive liveness, GPS geofencing | 95.00% accuracy, 0.0216 s per face, FAR 0% |
| **Three-Layer Mobile Attendance** | IJRPR, V7(5) | Flutter client, Spring Boot 3 with JWT and RBAC, Flask inference; InsightFace buffalo_m 512-D, Silent-FAS with Fourier auxiliary supervision; server-side Haversine | Pilot only, n=6: 70-85% recognition, 88-93% anti-spoofing, 3.2 s latency. Reports TAR@FAR, APCER/BPCER/ACER (ISO/IEC 30107-3), CEP-95 |
| **Geo-Attendance** | IJSRD, 14(2), 2026 | React Native, Express.js, React admin; face-api.js SSD MobileNetV1 + ResNet-34 128-D on-device | Fuses GPS, face, movement, device activity, location consistency into a 0-100 Presence Score. Legitimate user 92, GPS spoof 38, threshold 80 |
| **LaED** | Nature Scientific Reports, 2026 | Lightweight edge-aware explainable model | Addresses spoof resistance, open-set identity, demographic fairness, auditability, privacy together |

**Implication for Sentinel.** The combination the project currently offers is comprehensively
covered. Geo-Attendance in particular already implements multi-signal fusion into a single
confidence score, which forecloses "fusion into one score" as a standalone novelty claim. The
Three-Layer paper already uses the exact evaluation triple (TAR@FAR, ACER, CEP-95) that would be
the obvious protocol.

### 3.2 Where the field says the gaps are

Two systematic reviews agree on the open problems:

- **Bhoyar et al., IJERT 14(12), 2025** - existing systems "lack comprehensive integration of
  high-accuracy recognition with multi-layered anti-spoofing, real-time analytics, and intelligent
  attendance logic in a unified framework"; specifically no guidance on how to combine multiple
  liveness checks, what thresholds to use, or how to balance security against user experience.
- **Systematic literature review 2020-2024** - evaluation practices are inconsistent, real-world
  deployment studies are missing, and robustness under pose and illumination variation is weak.

Neither review mentions injection attacks. That absence is itself the finding.

### 3.3 Presentation attack detection state of the art

Do **not** compete here. The frontier moved to multimodal LLMs in 2026:

| Method | Avg HTER (lower better) | Avg AUC |
|---|---|---|
| ViTAF | 23.85 | 82.82 |
| ViT-L | 21.08 | 85.61 |
| FLIP | 18.73 | 87.90 |
| I-FAS | 11.30 | 93.71 |
| **TAR-FAS** (CVPR 2026) | **7.54** | **96.67** |

TAR-FAS reformulates anti-spoofing as chain-of-thought with visual tools, letting an MLLM invoke
LBP, FFT, wavelet, Laplacian and HOG operators during reasoning, trained on a 16,172-image
tool-use dataset annotated by Gemini 2.5 Pro. FaceCoT extends this with 1.08M VQA samples across
14 attack types. Beating these requires resources a student project does not have, and the attempt
would be judged against them directly.

### 3.4 Behavioural anomaly detection on attendance logs

An active but low-tier area, and importantly all of it is **post-hoc log analysis**, not a
real-time decision:

- **JSIAR, 2026** - Isolation Forest plus Local Outlier Factor over device fingerprints,
  submission timing, session concurrency, geolocation traces. 1,200 synthetic records with injected
  proxy scenarios: precision 87.3%, recall 91.7%, AUC 0.943.
- **ELKOMIKA** - Isolation Forest with threshold filtering and LSTM over GPS entry/exit distance
  anomalies: 99.74% accuracy.
- **Zenodo, RFID attendance** - seven-dimensional behavioural feature vector (session duration,
  deviation from official start, deviation from personal average arrival, historical rhythm,
  short-stay behaviour, inter-arrival time, scan frequency), rule layer plus Isolation Forest.
  Normal sessions score 19.3%, proxy sessions 87.5%, latency 150-250 ms.
- **IEEE ICSMILE, 2026** - buddy punching via repeated near-simultaneous punches and persistent
  pair co-occurrence; "clockwork attendance" via abnormally low timestamp variability. ROC-AUC up
  to 1.000 under synthetic injection.

**Implication.** Behavioural detection alone is not novel. Its value here is as the second signal
in a fused real-time gate, and as the component that catches what capture-path integrity cannot.

### 3.5 The gap: injection attacks and capture-path integrity

This is the opening.

**The attack.** Instead of holding a photo to a camera, the attacker registers a virtual camera
device - OBS Virtual Camera, ManyCam, SplitCam, Iriun Webcam - and feeds a pre-recorded or
real-time face-swapped stream. The browser's `getUserMedia` returns it as a legitimate device. The
physical camera is never involved.

**Why Sentinel is exposed.** The literature is unambiguous that active challenge-response fails
against this. Because a real person is driving the face swap in real time, the synthetic face
blinks on cue, turns on cue, and follows an on-screen target. Liveness evaluates the *content* of
the video, not its *source*. Sentinel's `timed_blink` in
[backend/app/liveness/blink.py](../../backend/app/liveness/blink.py) and the texture check in
[backend/app/liveness/texture.py](../../backend/app/liveness/texture.py) are both content checks,
so both are bypassed by construction.

**State of virtual camera detection.** One serious treatment exists
([arXiv 2512.10653](https://arxiv.org/html/2512.10653)), and it states plainly that VCD "remains an
underexplored area in the literature". Its method is well suited to reproduction:

- Probe the camera during the session with `applyConstraints`, requesting a ladder of frame heights
  and frame rates (1, 5, 30, 60, 120, 200 fps).
- For each probe record the requested value, the value the browser reports, the value actually
  applied, and the response time.
- Train gradient boosting (histogram gradient boosting, CatBoost, and an ensemble) on those
  metrics. Virtual cameras betray themselves through resolution ceilings, uniform response times,
  and configuration anomalies.
- Camera labels are **not** usable as a feature; they are routinely obfuscated or renamed.

Critically, that paper evaluates VCD **as a standalone layer** and names its own future work as
integrating VCD with liveness detection and exploiting temporal patterns. That is exactly the
proposed contribution, which means the gap is both real and externally validated.

---

## 4. Threat model coverage

The empty column is the contribution.

| Work | Print attack | Screen replay | 3D mask | GPS spoof | **Injection / virtual camera** | Longitudinal fraud |
|---|---|---|---|---|---|---|
| HybridFaceNet | Yes | Yes | No | Yes | **No** | No |
| ArcFace + GPS + MiniFASNet | Yes | Yes | No | No | **No** | No |
| Three-Layer Mobile | Yes | Yes | No | Yes | **No** | No |
| Geo-Attendance | Yes | No | No | Yes | **No** | Partial (consistency signal) |
| LaED | Yes | Yes | No | No | **No** | No |
| JSIAR / ELKOMIKA / ICSMILE | No | No | No | Partial | **No** | Yes (offline only) |
| arXiv 2512.10653 | No | No | No | No | **Yes** (standalone) | No |
| **Sentinel (proposed)** | Yes | Yes | No | Yes | **Yes** | **Yes (real-time)** |

---

## 5. Novelty statement

> We present the first workplace face-attendance system whose accept/reject decision is a single
> calibrated presence-trust probability fusing four heterogeneous signals: capture-path integrity
> (virtual camera detection), content liveness (blink and texture), face match confidence, and
> longitudinal spatio-temporal plausibility derived from the organisation's own attendance history.
> We show that the face-plus-geofence-plus-liveness designs that dominate the current attendance
> literature are defeated by browser injection attacks at near-100% success, that capture-path
> integrity alone is insufficient once an attacker controls the client, and that the fused score
> restores security without degrading the false-rejection rate for genuine users.

Three separately defensible claims:

1. **An attack result.** Published attendance designs, reimplemented faithfully, fall to virtual
   camera injection. Nobody has measured this.
2. **A method.** Fusion of capture-path integrity with longitudinal behaviour, calibrated to a
   target FAR, which is the integration the VCD authors named as future work.
3. **An interpretability result.** The per-signal breakdown explains every rejection, addressing
   the auditability gap LaED raises and satisfying the XAI requirement of the Multimodal AI track.

---

## 6. Evaluation protocol

Adopt the protocol the strongest competing paper already uses, so results are directly comparable:

- **Recognition:** TAR@FAR at 1e-2, 1e-3, 1e-4 - already produced by
  [backend/app/eval/metrics.py](../../backend/app/eval/metrics.py).
- **Anti-spoofing:** APCER, BPCER, ACER per ISO/IEC 30107-3, plus HTER and AUC for cross-domain
  comparison against the FAS table in section 3.3.
- **Geofence:** CEP-95, false-in and false-out rates.
- **Behavioural:** precision, recall, ROC-AUC under controlled synthetic fraud injection, matching
  the JSIAR and ICSMILE setups.
- **Ablation (this is the table that carries the paper):** face only, then +PAD, then +VCD, then
  +behaviour, reported against both presentation and injection attack sets.

**Attack dataset.** Self-collected and cheap: bonafide sessions from real users, plus attack
sessions driven through OBS Virtual Camera, ManyCam and SplitCam using static images,
pre-recorded video, and a real-time face swap. This is the long pole - start collecting early.

---

## 7. Target venues

| Venue | Fit | Notes |
|---|---|---|
| arXiv preprint | First | Establishes the date on the attack result |
| IEEE Access | Strong | Open access, systems-plus-evaluation papers, reasonable turnaround |
| IET Biometrics | Strong | Exactly the injection-attack scope |
| Springer Multimedia Tools and Applications | Good | Tolerant of applied system papers |
| IJCB / BIOSIG workshops | Good | Where PAD and injection work is actively discussed |
| Pattern Recognition Letters | Stretch | Requires a sharper methodological claim |

---

## 8. What to stop doing

- **Do not** position PostGIS as a differentiator. It is an implementation detail; Haversine gives
  the same decision at office scale.
- **Do not** claim multi-signal fusion alone as novel. Geo-Attendance published a 0-100 presence
  score in early 2026.
- **Do not** attempt to beat TAR-FAS or FaceCoT on PAD benchmarks.
- **Do not** build the paper on the LLM assist feature. Enterprise NL-to-SQL is a crowded field
  where agentic systems already reach 91-94% execution accuracy; the current naive RAG assist is
  far behind that frontier and would be judged against it.

---

## 9. References

1. Masram, More, Patel. *HybridFaceNet: AI-ML Framework for Digital Attendance Systems with GPS and
   Multi-Modal Biometrics.* IEEE, 2025. doi:10.1109/ic366947.2025.11290197
2. *Web-Based Attendance System Using ArcFace, GPS Validation and Liveness Detection.* Smatika
   16(2), 2025. doi:10.32664/smatika.v16i02.2382
3. *A Three-Layer Mobile Attendance System Integrating ArcFace, Silent Face Anti-Spoofing and GPS
   Geofencing for Higher Education.* IJRPR V7(5).
4. *Geo-Attendance: multi-signal presence scoring.* IJSRD 14(2), 2026.
5. *LaED: lightweight, edge-aware and explainable deep learning for privacy-preserving facial
   attendance tracking.* Nature Scientific Reports, 2026. doi:10.1038/s41598-026-42051-8
6. Bhoyar, Khadse, Dhak. *A Systematic Review of Face Recognition Attendance Systems: Anti-Spoofing
   Integration, Intelligent Automation, and Research Gaps.* IJERT 14(12), 2025.
   doi:10.17577/IJERTV14IS120515
7. Zhang et al. *From Intuition to Investigation: A Tool-Augmented Reasoning MLLM Framework for
   Generalizable Face Anti-Spoofing.* CVPR 2026.
8. *FaceCoT: Chain-of-Thought Reasoning in MLLMs for Face Anti-Spoofing.* 2026.
9. *Virtual camera detection: Catching video injection attacks in remote biometric systems.* arXiv
   2512.10653. doi:10.48550/arxiv.2512.10653
10. *A Behavioral Anomaly Detection Framework for Proxy Attendance Identification in Web-Based
    Systems.* JSIAR, March 2026.
11. Sugiantoro et al. *Enhancing Isolation Forest with Threshold-based Filtering and LSTM for
    Attendance Anomaly Detection.* ELKOMIKA.
12. *Machine Learning for Attendance Fraud Detection in Biometric Logs.* IEEE ICSMILE 2026.
    doi:10.1109/icsmile69273.2026.11519283
13. *A Multi-method Active Liveness Detection Approach.* Springer.
    doi:10.1007/978-3-032-07986-2_43
