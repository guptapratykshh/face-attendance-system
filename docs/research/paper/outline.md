# Paper outline

**Working title:** Beyond the Presented Face: Capture-Path Integrity and Longitudinal Plausibility
for Trustworthy Workplace Attendance

**Target:** arXiv preprint first, then IEEE Access or IET Biometrics.
See [../competitive-and-literature-analysis.md](../competitive-and-literature-analysis.md) section 7.

---

## The one-sentence claim

Published face-attendance systems combine face recognition, geofencing, and liveness detection, and
all of them are defeated by a browser injection attack that none of them test; adding capture-path
integrity and longitudinal behavioural plausibility closes the gap without rejecting more genuine
users.

## Contributions, in the order a reviewer will check them

1. **An attack result.** Reimplement the published face + geofence + liveness configuration and
   measure it under virtual-camera injection. Prediction, supported by the current harness: 100% of
   injected attempts are accepted. Nobody has published this number.
2. **A negative result about active liveness.** Blink challenge-response does not merely underperform
   against injection, it provides no signal at all, because the attacker performs the blink. Show
   this directly rather than asserting it.
3. **A method.** Constraint-probe capture-path integrity fused with longitudinal spatio-temporal
   plausibility, combined conjunctively rather than by weighted vote.
4. **A calibration and interpretability result.** Per-signal breakdown explains every rejection,
   addressing the auditability gap that LaED raises.

---

## Section plan

### 1. Introduction
Attendance fraud is a live commercial problem, face check-in is the standard answer, and the answer
has a hole in it. State the four contributions.

### 2. Related work
Three groups, with the gap falling between them. Use the table in
[related-work.md](related-work.md).

- Face attendance systems: HybridFaceNet, ArcFace+GPS+MiniFASNet, Three-Layer Mobile,
  Geo-Attendance, LaED. All test print and replay. None test injection.
- Presentation attack detection: TAR-FAS, FaceCoT, I-FAS, FLIP. State plainly that we do not
  compete on PAD modelling and explain why that is the correct scope decision.
- Behavioural anomaly detection on attendance logs: JSIAR, ELKOMIKA, ICSMILE. All offline HR
  reporting, none in the accept path.
- Virtual camera detection: arXiv 2512.10653, the only serious treatment, evaluated standalone and
  explicitly naming integration with liveness and temporal patterns as future work. This paper is
  that integration.

### 3. Threat model
Four adversaries, increasing in capability:

| Adversary | Capability | Defeated by |
|---|---|---|
| A1 print | Holds a photo to the camera | Texture PAD |
| A2 replay | Plays a video on a screen | Texture PAD, frozen-frame check |
| A3 injection | Virtual camera feeding a real-time face swap | Capture-path integrity |
| A4 proxy | A genuine colleague punching on your behalf | Longitudinal behaviour |

State explicitly what is out of scope: a fully compromised client that forges the telemetry itself,
which needs device attestation, not detection. The VCD paper draws the same boundary.

### 4. Method
- 4.1 Constraint-probe telemetry - the ladder, the four values per probe, why camera labels are
  excluded. Implementation: [frontend/src/lib/captureProbe.ts](../../../frontend/src/lib/captureProbe.ts).
- 4.2 Capture-path scoring - features, rules, gradient boosting.
  [backend/app/liveness/capture_path.py](../../../backend/app/liveness/capture_path.py).
- 4.3 Longitudinal plausibility - impossible travel, arrival-habit deviation, clockwork detection,
  collusion pairing, similarity drift.
  [backend/app/risk/behaviour.py](../../../backend/app/risk/behaviour.py).
- 4.4 Conjunctive fusion - the argument that a weighted mean is the wrong operator here, because a
  face swap produces a *higher* similarity than a genuine user and would outvote the signal that
  catches it. Weighted geometric mean plus per-signal veto floor.
  [backend/app/risk/fusion.py](../../../backend/app/risk/fusion.py).

### 5. Experimental setup
- Recognition backbone and LFW operating point, from the existing evaluation harness.
- Capture sessions: bonafide across browsers and machines, versus OBS, ManyCam, SplitCam driving
  static images, replayed video, and a real-time face swap.
- Synthetic org history with injected fraud, following the JSIAR and ICSMILE protocol.
- Metrics: APCER, BPCER, ACER per ISO/IEC 30107-3; EER; ROC-AUC. **Operating points are fixed at a
  common genuine-rejection budget**, not an arbitrary threshold, so the ablation stages are
  comparable. Justify this - reporting attack rates at a fixed threshold flatters a permissive
  system.

### 6. Results
The ablation is the paper. See [results.md](results.md).

### 7. Limitations
Be first to say these; a reviewer will find them anyway.

- Telemetry is client-reported. A sufficiently determined attacker patches the client and forges
  it. Detection raises cost, attestation is the real fix.
- The rule-based scorer cannot separate a *locked* virtual camera (one that clamps like real
  hardware and varies its timings) from a genuinely fixed-mode webcam. This is visible in the
  current numbers as residual injection acceptance, and is the main motivation for collecting real
  sessions and fitting the model.
- Behavioural weights are tuned against synthetic fraud because real proxy-attendance labels do not
  exist. Same limitation as every published result in that subfield; say so and cite them.
- Single-organisation deployment. No claim about cross-organisation generalisation.
- No demographic fairness audit yet. LaED makes this a live expectation for the venue.

### 8. Conclusion and future work
Attestation-backed capture, passive challenge-response along the lines of coded illumination, and a
field trial with real attack attempts.

---

## Writing order

Results and related work first, because they are the two sections that can invalidate the framing.
Do not write the introduction until the ablation numbers are stable on collected data.
