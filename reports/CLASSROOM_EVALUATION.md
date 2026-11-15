# Classroom attendance demo evaluation

Generated: 2026-11-15T22:49:50.840176+05:30

Demo organization: `classroom-demo`. Encoder: `arcface-w600k_r50`. Threshold: 0.2557 (LFW-calibrated operating point).

## Registered sample identities

10 fictional student records each linked to one LFW face image and enrolled in one lecture. They are **not real students**. Their source images stay local and are not committed.

## Small probe check

- Known held-out photos: 10/10 correctly identified, 0/10 rejected, 0/10 assigned to a different registered identity.
- Unregistered photos: 0/7 falsely accepted.
- Known identification accuracy: 100.0%.
- False accept rate on this tiny unregistered set: 0.0%.

## Composite classroom scan

A 3 × 4 grid of the ten held-out photos produced 10 face detections. Correctly assigned: 10/10; assigned to another demo identity: 0; below threshold: 0; low quality: 0; missed tiles: 0; extra detections: 0. Detection recall: 100.0%; correct-assignment recall: 100.0%.

These small LFW checks are smoke tests, not an independent classroom accuracy estimate: the operating threshold was also calibrated on LFW, and a composite photo does not reproduce classroom distance, occlusion, lighting, motion, or camera angle. A real evaluation needs consented student enrollment images and separately labeled lecture frames. Measure face detection recall, present-student recall, false matches, missed students, and per-lecture attendance precision. A still photo can also be replayed or manipulated; this batch route has no liveness check. Use consented data, restrict access to the attendance log, and manually review unknown and not-seen students. A single photo cannot establish absence.
