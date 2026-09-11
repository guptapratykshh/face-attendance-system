# Method

Section 4 of the paper, written against the shipped implementation so the text and the code cannot
drift apart.

---

## 4.1 Constraint-probe telemetry

**Intuition.** Liveness reads the content of the video. To see the *source*, ask the camera to
change shape and watch how it reacts. Real hardware negotiates with a driver: it supports a
discrete set of modes, refuses what it cannot do, and takes measurably different amounts of time
for standard versus unusual requests. A virtual camera is a software buffer, so it either accepts
everything instantly or sits locked at whatever the operator configured.

**Procedure.** Before frame capture begins - never during, because the probe resizes the track -
the client walks a ladder of `applyConstraints` requests:

- frame height: 240, 480, 720, 3001
- frame rate: 1, 30, 120, 200

3001 and 200 are deliberately out of range. For each probe we record four values:

| Value | Source |
|---|---|
| requested | what we asked for |
| reported | `track.getSettings()` |
| actual | `videoHeight`, or frames counted via `requestVideoFrameCallback` |
| response_ms | wall time for `applyConstraints` to settle |

A rejected `applyConstraints` is recorded as evidence rather than aborting the ladder.

**Camera labels are excluded.** arXiv 2512.10653 found them routinely renamed or blanked by attack
tooling; they look discriminative on collected data and fail in deployment.

Implementation: [frontend/src/lib/captureProbe.ts](../../../frontend/src/lib/captureProbe.ts).

## 4.2 Capture-path scoring

Eighteen features are derived from the ladder, grouped as:

- **acceptance** - exact-match rate on in-range heights, whether the out-of-range height or frame
  rate was accepted, `applyConstraints` failure rate
- **diversity** - count of distinct reported heights and frame rates across the ladder. One
  distinct value across eight probes is prima facie evidence of a fixed software buffer
- **consistency** - disagreement between reported and actually rendered dimensions, and between
  reported and measured frame rate
- **timing** - mean and coefficient of variation of response times. A CV near zero means nothing
  was really reconfigured

Scoring is a documented weighted rule set by default, and a `HistGradientBoostingClassifier` once
labelled sessions exist. The rules remain the fallback for malformed telemetry, and a missing probe
yields *no opinion* rather than a guilty verdict, so older clients and non-browser callers are not
penalised.

Implementation: [backend/app/liveness/capture_path.py](../../../backend/app/liveness/capture_path.py).

## 4.3 Longitudinal plausibility

Attendance is a repeated event, so each person accumulates a personal baseline for free. Features
are computed per punch against up to 90 days of that person's history:

| Feature | Catches |
|---|---|
| implied speed from the previous punch | mock-location apps, shared accounts |
| deviation from personal mean arrival, as a z-score | punches outside someone's own habit |
| standard deviation of arrival times | scripted "clockwork" punching |
| strongest single near-simultaneous partner over 30 days | buddy punching |
| site novelty and site-switch rate | unusual movement between locations |
| face similarity drift from personal mean | a different person passing the face gate |

Two design decisions matter. The arrival z-score floors its denominator at three minutes, because
an unnaturally small spread is itself the clockwork signal and would otherwise produce an infinite
score. And collusion is measured as the *strongest single pairing*, not the raw count of
near-simultaneous colleagues: a shared office produces many coincidental neighbours, while buddy
punching concentrates on one partner.

Every feature degrades to null when history is thin, and the risk score is damped below five prior
punches. A new joiner must not be flagged as fraud in their first week.

Implementation: [backend/app/risk/behaviour.py](../../../backend/app/risk/behaviour.py).

## 4.4 Conjunctive fusion

**Why not a weighted average.** The four signals are not interchangeable votes. Under injection,
face similarity is *anti-correlated* with legitimacy - a face swap renders an idealised target
face and matches better than the real user, which the ablation shows as a below-chance AUC of 0.384
for face alone. Any mean, arithmetic or in log-odds space, lets that strong wrong signal outvote
the capture-path signal that would have caught it. We verified this: at similarity 0.95 with a
failed capture path, a plain average scores above threshold and accepts the attack.

The security requirement is conjunctive - every gate must hold - so fusion is two-part:

1. **Weighted geometric mean** of the per-signal confidences,
   \[ s = \exp\left(\sum_i w_i \log c_i\right) \]
   with weights renormalised over whichever signals are present. Unlike an arithmetic mean, one
   near-zero confidence drags the product down instead of being averaged away.
2. **Per-signal veto floor.** Any signal below the floor rejects the punch regardless of the score,
   and the breakdown names which one did it.

Missing signals are dropped and the remaining weights renormalised, so a kiosk punch with no
geolocation is scored on what it has rather than penalised for what it lacks.

**Calibration.** A raw weighted score is not a probability. Where labelled sessions exist, Platt
scaling maps the score to P(genuine), so the accept threshold can be chosen from a target
false-accept rate instead of by taste. Until then the score is reported as uncalibrated and the
evaluation fixes operating points from the genuine-score distribution rather than a constant.

**Interpretability.** The breakdown persists on the attendance row as `trust_score` and
`trust_breakdown_json`: per-signal confidence, weight, veto flag, the weakest signal, and a
human-readable reason. This is what makes every rejection explainable to the employee who was
rejected, and is the response to the auditability gap LaED identifies.

Implementation: [backend/app/risk/fusion.py](../../../backend/app/risk/fusion.py).

---

## Reproducibility

| Step | Command |
|---|---|
| Recognition operating point | `python scripts/evaluate.py --encoders facenet arcface` |
| Synthetic org history | `python scripts/simulate_attendance_fraud.py --out data/fraud_sim.jsonl` |
| Ablation | `python scripts/evaluate_trust.py --fraud data/fraud_sim.jsonl` |
| Export collected sessions | `python scripts/collect_capture_sessions.py --export data/vcd_sessions.jsonl` |
| Fit the detector | `python scripts/collect_capture_sessions.py --fit weights/vcd_model.joblib` |

Unit tests covering the three modules: `backend/tests/test_trust.py`.
