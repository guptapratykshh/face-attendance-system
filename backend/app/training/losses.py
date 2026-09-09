"""ArcFace additive-angular-margin head (Deng et al., CVPR 2019).

Maps unit-norm embeddings onto class logits with a margin `m` on the target angle
and a scale `s`. The margin is the only thing that changes relative to a linear
classifier: it forces the backbone to pack same-identity embeddings more tightly.
"""

from __future__ import annotations

import math

import torch
from torch import nn
from torch.nn import functional as F


class ArcFaceHead(nn.Module):
    def __init__(self, in_features: int, out_features: int, s: float = 32.0, m: float = 0.5):
        super().__init__()
        self.in_features = in_features
        self.out_features = out_features
        self.s = s
        self.m = m
        self.weight = nn.Parameter(torch.empty(out_features, in_features))
        nn.init.xavier_uniform_(self.weight)
        self.cos_m = math.cos(m)
        self.sin_m = math.sin(m)
        self.th = math.cos(math.pi - m)
        self.mm = math.sin(math.pi - m) * m

    def forward(self, embeddings: torch.Tensor, labels: torch.Tensor, margin: float | None = None) -> torch.Tensor:
        """Return scaled logits. `margin` overrides `self.m` so the trainer can warm it up."""
        cosine = F.linear(F.normalize(embeddings, dim=1), F.normalize(self.weight, dim=1))
        cosine = cosine.clamp(-1.0 + 1e-7, 1.0 - 1e-7)
        if margin is None:
            cos_m, sin_m, th, mm = self.cos_m, self.sin_m, self.th, self.mm
        else:
            cos_m, sin_m = math.cos(margin), math.sin(margin)
            th = math.cos(math.pi - margin)
            mm = math.sin(math.pi - margin) * margin
        sine = torch.sqrt((1.0 - cosine.pow(2)).clamp(0.0, 1.0))
        phi = cosine * cos_m - sine * sin_m
        # Numerical guard used by the original ArcFace implementation: when theta + m
        # would leave the monotonic region, fall back to cosine - mm.
        phi = torch.where(cosine > th, phi, cosine - mm)
        one_hot = F.one_hot(labels, num_classes=self.out_features).to(cosine.dtype)
        logits = one_hot * phi + (1.0 - one_hot) * cosine
        return logits * self.s
