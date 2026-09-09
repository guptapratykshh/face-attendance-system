# TAR@FAR Report

Generated: 2026-08-25T06:38:16.746571+00:00
Protocol: LFW View 2 — 6000 pairs, 10-fold accuracy.

Grounding paper: Schroff, Kalenichenko, Philbin. *FaceNet: A Unified Embedding for Face Recognition and Clustering*. CVPR 2015.

Embeddings are L2-normalised; the score is cosine similarity. The operating threshold served by the API is the cosine value that realises FAR = 1e-3 on this protocol.

## Results

| Encoder | LFW acc. (10-fold) | EER | TAR@FAR=1e-2 | TAR@FAR=1e-3 | TAR@FAR=1e-4 | Threshold (FAR=1e-3) |
|---|---:|---:|---:|---:|---:|---:|
| `facenet` | 98.10% ± 0.65% | 2.43% | 97.33% | 95.03% | 60.20% | 0.5009 |
| `arcface-w600k_r50` | 98.80% ± 0.51% | 2.13% | 97.83% | 97.63% | 97.63% | 0.2557 |
| `facenet-finetuned` | 94.25% ± 0.73% | 6.17% | 87.40% | 72.63% | 70.10% | 0.5575 |

**Served encoder:** `arcface-w600k_r50` (highest TAR at FAR = 1e-3).

## Score statistics

### facenet

- Genuine cosine: mean 0.745 ± 0.151 [-0.255, 0.988]
- Impostor cosine: mean 0.027 ± 0.153 [-0.387, 0.745]

### arcface-w600k_r50

- Genuine cosine: mean 0.659 ± 0.138 [-0.116, 0.968]
- Impostor cosine: mean 0.004 ± 0.057 [-0.189, 0.232]

### facenet-finetuned

- Genuine cosine: mean 0.631 ± 0.181 [-0.173, 0.976]
- Impostor cosine: mean 0.048 ± 0.159 [-0.426, 0.572]

## Notes

- FaceNet is the vendored Inception-ResNet-v1 checkpoint trained on VGGFace2 (`20180402-114759-vggface2.pt`).
- ArcFace is InsightFace `w600k_r50` (ResNet-50, WebFace600K) used as a published reference, not trained here.
- Fine-tuning uses an ArcFace head on a 402-identity VGGFace2 subset with LFW-overlapping identities excluded. With only 402 classes the fine-tune is expected to trail the published weights on LFW; that gap is the result, not a bug.
- FAR = 1e-4 is below 1/3000 impostor pairs, so TAR@FAR=1e-4 is limited by protocol size.
