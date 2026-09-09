"""ArcFace encoder: w600k_r50 ONNX from the InsightFace buffalo_l pack.

Serves two purposes: a strong reference point for the TAR@FAR comparison, and a
production-grade fallback encoder. Weights are used as published; nothing is trained here.
"""

from __future__ import annotations

import numpy as np
import onnxruntime as ort

from app.encoders.base import FaceEncoder, l2_normalize
from app.encoders.model_store import recognition_path

INPUT_SIZE = 112


class ArcFaceEncoder(FaceEncoder):
    name = "arcface-w600k_r50"
    dim = 512
    input_size = INPUT_SIZE

    def __init__(self, batch_size: int = 16, providers: list[str] | None = None):
        self.batch_size = batch_size
        opts = ort.SessionOptions()
        opts.graph_optimization_level = ort.GraphOptimizationLevel.ORT_ENABLE_ALL
        opts.log_severity_level = 3
        self.session = ort.InferenceSession(
            str(recognition_path()),
            sess_options=opts,
            providers=providers or ["CPUExecutionProvider"],
        )
        self.input_name = self.session.get_inputs()[0].name
        self.output_name = self.session.get_outputs()[0].name

    def embed(self, faces: np.ndarray) -> np.ndarray:
        if faces.ndim != 4 or faces.shape[-1] != 3:
            raise ValueError(f"expected (N, H, W, 3) uint8 batch, got {faces.shape}")
        out = np.empty((len(faces), self.dim), dtype=np.float32)
        for start in range(0, len(faces), self.batch_size):
            chunk = faces[start : start + self.batch_size].astype(np.float32)
            # ArcFace's published preprocessing: (x - 127.5) / 127.5, NCHW.
            blob = ((chunk - 127.5) / 127.5).transpose(0, 3, 1, 2)
            emb = self.session.run([self.output_name], {self.input_name: blob})[0]
            out[start : start + len(chunk)] = emb
        # The ONNX graph emits unnormalised logits; cosine scoring requires unit norm.
        return l2_normalize(out).astype(np.float32)


def load_arcface(**kwargs) -> ArcFaceEncoder:
    return ArcFaceEncoder(**kwargs)
