"""Inception-ResNet-v1 backbone producing 512-D face embeddings.

Vendored from facenet-pytorch (Tim Esler, MIT License) because that package pins
torch<2.3 and numpy<2.0, which cannot be satisfied alongside a current torch. Only the
model definition is needed; the pretrained weights are the same published tensors.

Module and parameter names are kept byte-identical to the upstream definition so the
official `20180402-114759-vggface2.pt` state dict loads without remapping.

Reference: Schroff et al., "FaceNet: A Unified Embedding for Face Recognition and
Clustering", CVPR 2015. The paper's contribution is the triplet-loss embedding; this
particular backbone is the Inception-ResNet-v1 variant trained on VGGFace2.
"""

from __future__ import annotations

from pathlib import Path

import torch
from torch import nn
from torch.nn import functional as F

WEIGHTS_URL = (
    "https://github.com/timesler/facenet-pytorch/releases/download/v2.2.9/"
    "20180402-114759-vggface2.pt"
)
# Kept for documentation: the upstream release also ships a CASIA-WebFace checkpoint.
WEIGHTS_URL_CASIA = (
    "https://github.com/timesler/facenet-pytorch/releases/download/v2.2.9/"
    "20180408-102900-casia-webface.pt"
)


class BasicConv2d(nn.Module):
    def __init__(self, in_planes, out_planes, kernel_size, stride, padding=0):
        super().__init__()
        self.conv = nn.Conv2d(
            in_planes, out_planes, kernel_size=kernel_size, stride=stride, padding=padding, bias=False
        )
        self.bn = nn.BatchNorm2d(out_planes, eps=0.001, momentum=0.1, affine=True)
        self.relu = nn.ReLU(inplace=False)

    def forward(self, x):
        return self.relu(self.bn(self.conv(x)))


class Block35(nn.Module):
    def __init__(self, scale=1.0):
        super().__init__()
        self.scale = scale
        self.branch0 = BasicConv2d(256, 32, kernel_size=1, stride=1)
        self.branch1 = nn.Sequential(
            BasicConv2d(256, 32, kernel_size=1, stride=1),
            BasicConv2d(32, 32, kernel_size=3, stride=1, padding=1),
        )
        self.branch2 = nn.Sequential(
            BasicConv2d(256, 32, kernel_size=1, stride=1),
            BasicConv2d(32, 32, kernel_size=3, stride=1, padding=1),
            BasicConv2d(32, 32, kernel_size=3, stride=1, padding=1),
        )
        self.conv2d = nn.Conv2d(96, 256, kernel_size=1, stride=1)
        self.relu = nn.ReLU(inplace=False)

    def forward(self, x):
        out = torch.cat((self.branch0(x), self.branch1(x), self.branch2(x)), 1)
        out = self.conv2d(out)
        return self.relu(out * self.scale + x)


class Block17(nn.Module):
    def __init__(self, scale=1.0):
        super().__init__()
        self.scale = scale
        self.branch0 = BasicConv2d(896, 128, kernel_size=1, stride=1)
        self.branch1 = nn.Sequential(
            BasicConv2d(896, 128, kernel_size=1, stride=1),
            BasicConv2d(128, 128, kernel_size=(1, 7), stride=1, padding=(0, 3)),
            BasicConv2d(128, 128, kernel_size=(7, 1), stride=1, padding=(3, 0)),
        )
        self.conv2d = nn.Conv2d(256, 896, kernel_size=1, stride=1)
        self.relu = nn.ReLU(inplace=False)

    def forward(self, x):
        out = torch.cat((self.branch0(x), self.branch1(x)), 1)
        out = self.conv2d(out)
        return self.relu(out * self.scale + x)


class Block8(nn.Module):
    def __init__(self, scale=1.0, noReLU=False):
        super().__init__()
        self.scale = scale
        self.noReLU = noReLU
        self.branch0 = BasicConv2d(1792, 192, kernel_size=1, stride=1)
        self.branch1 = nn.Sequential(
            BasicConv2d(1792, 192, kernel_size=1, stride=1),
            BasicConv2d(192, 192, kernel_size=(1, 3), stride=1, padding=(0, 1)),
            BasicConv2d(192, 192, kernel_size=(3, 1), stride=1, padding=(1, 0)),
        )
        self.conv2d = nn.Conv2d(384, 1792, kernel_size=1, stride=1)
        if not self.noReLU:
            self.relu = nn.ReLU(inplace=False)

    def forward(self, x):
        out = torch.cat((self.branch0(x), self.branch1(x)), 1)
        out = self.conv2d(out)
        out = out * self.scale + x
        return out if self.noReLU else self.relu(out)


class Mixed_6a(nn.Module):
    def __init__(self):
        super().__init__()
        self.branch0 = BasicConv2d(256, 384, kernel_size=3, stride=2)
        self.branch1 = nn.Sequential(
            BasicConv2d(256, 192, kernel_size=1, stride=1),
            BasicConv2d(192, 192, kernel_size=3, stride=1, padding=1),
            BasicConv2d(192, 256, kernel_size=3, stride=2),
        )
        self.branch2 = nn.MaxPool2d(3, stride=2)

    def forward(self, x):
        return torch.cat((self.branch0(x), self.branch1(x), self.branch2(x)), 1)


class Mixed_7a(nn.Module):
    def __init__(self):
        super().__init__()
        self.branch0 = nn.Sequential(
            BasicConv2d(896, 256, kernel_size=1, stride=1),
            BasicConv2d(256, 384, kernel_size=3, stride=2),
        )
        self.branch1 = nn.Sequential(
            BasicConv2d(896, 256, kernel_size=1, stride=1),
            BasicConv2d(256, 256, kernel_size=3, stride=2),
        )
        self.branch2 = nn.Sequential(
            BasicConv2d(896, 256, kernel_size=1, stride=1),
            BasicConv2d(256, 256, kernel_size=3, stride=1, padding=1),
            BasicConv2d(256, 256, kernel_size=3, stride=2),
        )
        self.branch3 = nn.MaxPool2d(3, stride=2)

    def forward(self, x):
        return torch.cat((self.branch0(x), self.branch1(x), self.branch2(x), self.branch3(x)), 1)


class InceptionResnetV1(nn.Module):
    """Inception-Resnet-V1 face encoder.

    Args:
        pretrained: "vggface2", "casia-webface", or None for random init.
        classify: when True the forward pass returns logits instead of embeddings.
        num_classes: class count for the optional classification head.
        dropout_prob: dropout before the embedding projection.
    """

    def __init__(
        self,
        pretrained: str | None = None,
        classify: bool = False,
        num_classes: int | None = None,
        dropout_prob: float = 0.6,
    ):
        super().__init__()
        self.pretrained = pretrained
        self.classify = classify
        self.num_classes = num_classes

        self.conv2d_1a = BasicConv2d(3, 32, kernel_size=3, stride=2)
        self.conv2d_2a = BasicConv2d(32, 32, kernel_size=3, stride=1)
        self.conv2d_2b = BasicConv2d(32, 64, kernel_size=3, stride=1, padding=1)
        self.maxpool_3a = nn.MaxPool2d(3, stride=2)
        self.conv2d_3b = BasicConv2d(64, 80, kernel_size=1, stride=1)
        self.conv2d_4a = BasicConv2d(80, 192, kernel_size=3, stride=1)
        self.conv2d_4b = BasicConv2d(192, 256, kernel_size=3, stride=2)
        self.repeat_1 = nn.Sequential(*[Block35(scale=0.17) for _ in range(5)])
        self.mixed_6a = Mixed_6a()
        self.repeat_2 = nn.Sequential(*[Block17(scale=0.10) for _ in range(10)])
        self.mixed_7a = Mixed_7a()
        self.repeat_3 = nn.Sequential(*[Block8(scale=0.20) for _ in range(5)])
        self.block8 = Block8(noReLU=True)
        self.avgpool_1a = nn.AdaptiveAvgPool2d(1)
        self.dropout = nn.Dropout(dropout_prob)
        self.last_linear = nn.Linear(1792, 512, bias=False)
        self.last_bn = nn.BatchNorm1d(512, eps=0.001, momentum=0.1, affine=True)

        if pretrained == "vggface2":
            tmp_classes = 8631
        elif pretrained == "casia-webface":
            tmp_classes = 10575
        elif pretrained is None and num_classes is None:
            raise RuntimeError("num_classes is required when pretrained is None")
        else:
            tmp_classes = num_classes

        if pretrained is not None:
            self.logits = nn.Linear(512, tmp_classes)
            load_weights(self, pretrained)

        if self.num_classes is not None:
            self.logits = nn.Linear(512, self.num_classes)

    def forward(self, x):
        """Return L2-normalised 512-D embeddings, or logits when `classify` is set."""
        x = self.conv2d_1a(x)
        x = self.conv2d_2a(x)
        x = self.conv2d_2b(x)
        x = self.maxpool_3a(x)
        x = self.conv2d_3b(x)
        x = self.conv2d_4a(x)
        x = self.conv2d_4b(x)
        x = self.repeat_1(x)
        x = self.mixed_6a(x)
        x = self.repeat_2(x)
        x = self.mixed_7a(x)
        x = self.repeat_3(x)
        x = self.block8(x)
        x = self.avgpool_1a(x)
        x = self.dropout(x)
        x = self.last_linear(x.view(x.shape[0], -1))
        x = self.last_bn(x)
        if self.classify and self.num_classes is not None:
            return self.logits(x)
        return F.normalize(x, p=2, dim=1)


def load_weights(model: InceptionResnetV1, name: str) -> None:
    """Load published weights into `model`, caching the download under weights/."""
    if name == "vggface2":
        url = WEIGHTS_URL
    elif name == "casia-webface":
        url = WEIGHTS_URL_CASIA
    else:
        raise ValueError(f"unknown pretrained weights: {name}")

    from app.core.config import settings

    cache_dir = settings.weights_dir
    cache_dir.mkdir(parents=True, exist_ok=True)
    dest = cache_dir / Path(url).name

    if not dest.exists():
        from torch.hub import download_url_to_file

        print(f"Downloading FaceNet weights -> {dest}")
        download_url_to_file(url, str(dest))

    state_dict = torch.load(dest, map_location="cpu", weights_only=True)
    model.load_state_dict(state_dict)
