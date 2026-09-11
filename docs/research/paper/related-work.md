# Related work

The comparison table for section 2. The purpose of this table is to make one column empty.

## Face attendance systems

| System | Year | Recognition | Liveness | Location | Longitudinal | Injection tested |
|---|---|---|---|---|---|---|
| HybridFaceNet | 2025 | YOLOv7 + lightweight FaceNet | MediaPipe | Encrypted GPS geofence | No | **No** |
| ArcFace + GPS + MiniFASNet | 2025 | ArcFace / MobileFaceNet | MiniFASNet, passive | GPS | No | **No** |
| Three-Layer Mobile | 2026 | InsightFace buffalo_m, 512-D | Silent-FAS, Fourier aux | Server-side Haversine | No | **No** |
| Geo-Attendance | 2026 | face-api.js, 128-D on-device | Implicit | GPS + consistency | Partial, as one of five score inputs | **No** |
| LaED | 2026 | Lightweight edge-aware | Yes | No | No | **No** |
| **This work** | 2026 | FaceNet / ArcFace, 512-D | Blink + texture | PostGIS `ST_DWithin` | Yes, in the accept path | **Yes** |

Reported numbers, for the results discussion:

- HybridFaceNet: 96.8% accuracy, 40% false-positive reduction, 30 fps, 500+ subjects.
- ArcFace + GPS + MiniFASNet: 95.00% accuracy, 0.0216 s per face, FAR 0%.
- Three-Layer Mobile: pilot only, n=6. 70-85% recognition, 88-93% anti-spoofing, 3.2 s latency.
  Reports TAR@FAR, APCER/BPCER/ACER, CEP-95 - the closest protocol to ours.
- Geo-Attendance: legitimate user 92/100, GPS spoof 38/100, accept threshold 80.

Note when writing: the Three-Layer paper is a pilot with six volunteers and says so honestly. Cite
it for its evaluation protocol, which is the most rigorous in the group, not for its numbers.

## Presentation attack detection

State that this is the frontier we deliberately do not compete with, and give the numbers so the
reader knows we know.

| Method | Avg HTER | Avg AUC |
|---|---|---|
| ViTAF | 23.85 | 82.82 |
| ViT-L | 21.08 | 85.61 |
| FLIP | 18.73 | 87.90 |
| I-FAS | 11.30 | 93.71 |
| TAR-FAS (CVPR 2026) | 7.54 | 96.67 |

TAR-FAS: chain-of-thought with visual tools, MLLM invoking LBP/FFT/wavelet/Laplacian/HOG, trained
on ToolFAS-16K annotated by Gemini 2.5 Pro, evaluated on the 1-to-11 cross-domain protocol.
FaceCoT: 1.08M VQA samples, 14 attack types, +4.06% AUC and -5.00% HTER over prior best.

**The argument to make:** these operate on the same axis - the content of the frame. An injected
stream is a *genuine* frame of a *synthetic* face; there is no presentation artefact to find. A
better PAD model does not help. This is what makes capture-path integrity an orthogonal
contribution rather than an incremental one.

## Behavioural anomaly detection on attendance

| Work | Method | Data | Result | In accept path |
|---|---|---|---|---|
| JSIAR 2026 | Isolation Forest + LOF | 1,200 records, injected proxy | P 87.3%, R 91.7%, AUC 0.943 | No |
| ELKOMIKA | Isolation Forest + threshold filter + LSTM | GPS entry/exit traces | 99.74% accuracy | No |
| Zenodo RFID | 7-dim features, rules + Isolation Forest | RFID scans | Normal 19.3% vs proxy 87.5% | No |
| IEEE ICSMILE 2026 | Supervised, buddy-punch and clockwork features | 4 fingerprint terminals | ROC-AUC up to 1.000 | No |

All four are offline HR analytics. None gate the punch. All evaluate on synthetic fraud injection,
which is the precedent for doing the same.

## Virtual camera detection

Single relevant work: arXiv 2512.10653.

- Browser-based, `applyConstraints` probes on frame height and frame rate (1, 5, 30, 60, 120, 200).
- Records requested, browser-reported, actually applied, and response time.
- HistGradientBoosting, CatBoost, and an ensemble; performance similar across all three, which the
  authors read as data quality mattering more than model choice.
- Camera labels discarded: routinely renamed or blank. Observed tooling includes OBS Studio,
  SplitCam, ManyCam, Iriun Webcam.
- Scope limited to virtual camera software; feed overwriting and session hijacking excluded.
- **Evaluated standalone.** Stated future work: integrate with liveness detection, exploit temporal
  patterns, adapt to evolving tooling.

This paper is that stated future work, applied to a domain where the longitudinal signal exists for
free because attendance is by definition a repeated event.
