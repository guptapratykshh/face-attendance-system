# Results

Regenerate with:

```bash
python scripts/simulate_attendance_fraud.py --out data/fraud_sim.jsonl
python scripts/evaluate_trust.py --fraud data/fraud_sim.jsonl --out reports/trust_evaluation.json
```

Machine-readable output lands in `reports/trust_evaluation.json`.

---

## Status of these numbers

**Provisional.** The behavioural half runs on simulated org history, which is the same protocol
every published attendance-fraud paper uses. The capture-path half currently runs on a *modelled*
attack distribution, not collected sessions, because the OBS/ManyCam dataset has not been recorded
yet. Do not put these in a submission. They exist to prove the harness works and to show the shape
of the result.

Replace by collecting real sessions:

```bash
# after checking in through a real webcam, then through OBS Virtual Camera
python scripts/collect_capture_sessions.py --tag bonafide --since <iso>
python scripts/collect_capture_sessions.py --tag virtual_faceswap --since <iso>
python scripts/collect_capture_sessions.py --fit weights/vcd_model.joblib
```

---

## Main ablation

Attacks accepted (APCER, %) at a fixed budget of 1% genuine rejection. Lower is better.
Operating points are set per stage from the genuine score distribution, so every row imposes the
same friction on real users and the columns are directly comparable.

| Stage | Presentation | **Injection** | Proxy | BPCER | EER | ROC-AUC |
|---|---|---|---|---|---|---|
| face | 89.3 | **100.0** | 99.3 | 1.0 | 56.4 | 0.384 |
| face + PAD | 0.0 | **100.0** | 98.6 | 1.0 | 41.9 | 0.633 |
| face + PAD + VCD | 0.0 | **23.0** | 98.6 | 1.0 | 17.8 | 0.889 |
| face + PAD + VCD + behaviour | 0.0 | **24.3** | 57.8 | 1.0 | 9.7 | 0.968 |

## What each row says

**Row 2 is the finding.** `face + PAD` is the configuration every published attendance system
ships, and it handles presentation attacks perfectly - 0% accepted - while accepting **100%** of
injection attempts. The defence that the literature treats as solved does not address the attack
the literature does not test.

**Face-only scores AUC 0.384, worse than chance.** This is not a bug and it is worth a paragraph in
the paper. A face swap renders an idealised, well-lit target face, so it matches the enrolled
template *better* than the genuine user does. Face similarity is anti-correlated with legitimacy
under this attack. It is also the direct justification for conjunctive fusion: under any weighted
vote, the strongest signal would be the one pointing the wrong way.

**Capture-path integrity does the work on injection**, taking it from 100% to 23%.

**Behaviour does the work on proxy punching**, taking it from 98.6% to 57.8%, and lifts overall
EER from 17.8% to 9.7%. It barely moves the injection column, which is expected and correct -
these two signals cover different adversaries. That separation is the argument for keeping both.

## Known weaknesses in these numbers

Say all of this in the paper before a reviewer says it.

1. **Residual 23-24% injection acceptance.** The rule-based scorer cannot separate a virtual camera
   configured to *clamp* like real hardware, with varied response times, from a genuinely
   fixed-mode webcam. Both report one resolution and one frame rate. This is the single strongest
   argument for collecting real sessions and fitting the gradient-boosting model, and it should be
   framed that way rather than hidden.
2. **Proxy detection plateaus at 57.8%.** A colleague punching for you inside the geofence, at a
   plausible time, on a real camera, is genuinely close to indistinguishable from a real punch. The
   honest claim is a large reduction, not elimination.
3. **Simulated behaviour.** Arrival habits, collusion pairs, and travel distances come from a
   generative model whose parameters we chose. Cite JSIAR and ICSMILE as precedent, and do not
   claim external validity.
4. **The injection column depends on a modelled attack distribution** until the OBS dataset exists.
   This is the most important thing to fix before submission.

## Figures to produce

1. ROC curves, one per ablation stage, on shared axes. Makes the AUC jump from 0.633 to 0.889 legible.
2. Score histograms for genuine versus each attack family, at the full-stack stage.
3. Per-signal contribution breakdown for a genuine punch, an injected one, and a proxy one - the
   interpretability contribution, and the strongest single figure for a viva.
4. Bar chart of the injection column across stages. One bar drops from 100 to 23; that is the paper.
