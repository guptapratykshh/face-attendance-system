"""FaceNet encoder: Inception-ResNet-v1 producing 512-D unit-norm embeddings."""

from __future__ import annotations

from pathlib import Path

import numpy as np
import torch

from app.core.config import settings
from app.encoders.base import FaceEncoder, l2_normalize
from app.encoders.inception_resnet_v1 import InceptionResnetV1

INPUT_SIZE = 160


def resolve_device(spec: str = "auto") -> torch.device:
    if spec != "auto":
        return torch.device(spec)
    if torch.backends.mps.is_available():
        return torch.device("mps")
    if torch.cuda.is_available():
        return torch.device("cuda")
    return torch.device("cpu")


def fixed_image_standardization(x: torch.Tensor) -> torch.Tensor:
    """The preprocessing the published FaceNet weights were trained with: (x - 127.5)/128."""
    return (x - 127.5) / 128.0


class FaceNetEncoder(FaceEncoder):
    name = "facenet"
    dim = 512
    input_size = INPUT_SIZE

    def __init__(
        self,
        checkpoint: Path | None = None,
        device: str = "auto",
        pretrained: str | None = "vggface2",
        batch_size: int = 32,
    ):
        self.device = resolve_device(device)
        self.batch_size = batch_size
        self.checkpoint = checkpoint

        model = InceptionResnetV1(pretrained=pretrained)
        if checkpoint is not None:
            state = torch.load(checkpoint, map_location="cpu", weights_only=True)
            # Fine-tuning saves {"backbone": ..., "head": ...}; only the backbone matters here.
            if isinstance(state, dict) and "backbone" in state:
                state = state["backbone"]
            missing, unexpected = model.load_state_dict(state, strict=False)
            # `logits` belongs to the discarded pretrain classifier, so it is expected to differ.
            missing = [k for k in missing if not k.startswith("logits.")]
            unexpected = [k for k in unexpected if not k.startswith("logits.")]
            if missing or unexpected:
                raise RuntimeError(
                    f"checkpoint mismatch: missing={missing[:5]} unexpected={unexpected[:5]}"
                )
            self.name = "facenet-finetuned"

        self.model = model.eval().to(self.device)
        for p in self.model.parameters():
            p.requires_grad_(False)

    @torch.inference_mode()
    def embed(self, faces: np.ndarray) -> np.ndarray:
        if faces.ndim != 4 or faces.shape[-1] != 3:
            raise ValueError(f"expected (N, H, W, 3) uint8 batch, got {faces.shape}")
        out = np.empty((len(faces), self.dim), dtype=np.float32)
        for start in range(0, len(faces), self.batch_size):
            chunk = faces[start : start + self.batch_size]
            t = torch.from_numpy(np.ascontiguousarray(chunk)).to(self.device)
            t = t.permute(0, 3, 1, 2).float()
            t = fixed_image_standardization(t)
            emb = self.model(t).float().cpu().numpy()
            out[start : start + len(chunk)] = emb
        # The backbone already normalises; repeat it so float32 round-trips stay unit-norm.
        return l2_normalize(out).astype(np.float32)


def load_facenet(
    checkpoint: Path | None = None, device: str | None = None, **kwargs
) -> FaceNetEncoder:
    return FaceNetEncoder(
        checkpoint=checkpoint if checkpoint is not None else settings.facenet_checkpoint,
        device=device or settings.device,
        **kwargs,
    )
