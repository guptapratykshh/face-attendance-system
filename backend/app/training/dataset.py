"""ImageFolder dataset over aligned VGGFace2 crops, with a per-identity hold-out."""

from __future__ import annotations

from pathlib import Path

import numpy as np
from PIL import Image
from torch.utils.data import Dataset
from torchvision import transforms

from app.encoders.facenet import INPUT_SIZE, fixed_image_standardization


def default_train_transform(size: int = INPUT_SIZE) -> transforms.Compose:
    return transforms.Compose(
        [
            transforms.Resize(size),
            transforms.RandomHorizontalFlip(),
            transforms.ColorJitter(brightness=0.15, contrast=0.15, saturation=0.1),
            transforms.RandomAffine(degrees=8, translate=(0.04, 0.04), scale=(0.95, 1.05)),
            transforms.ToTensor(),
            transforms.Lambda(lambda t: t * 255.0),
            transforms.Lambda(fixed_image_standardization),
        ]
    )


def default_eval_transform(size: int = INPUT_SIZE) -> transforms.Compose:
    return transforms.Compose(
        [
            transforms.Resize(size),
            transforms.ToTensor(),
            transforms.Lambda(lambda t: t * 255.0),
            transforms.Lambda(fixed_image_standardization),
        ]
    )


class IdentityFolder(Dataset):
    """One sample per JPEG under `root/<class_id>/*.jpg`.

    The val split holds out a fraction of *images* per identity (not identities) so the
    ArcFace head can still be scored: a fully identity-disjoint split would have no
    classifier weights for the val classes.
    """

    def __init__(
        self,
        root: Path,
        split: str = "train",
        val_fraction: float = 0.15,
        seed: int = 0,
        transform=None,
    ):
        self.root = Path(root)
        self.split = split
        self.transform = transform
        class_dirs = sorted(d for d in self.root.iterdir() if d.is_dir())
        if not class_dirs:
            raise FileNotFoundError(f"no class folders under {root}")
        self.class_to_idx = {d.name: i for i, d in enumerate(class_dirs)}
        self.classes = [d.name for d in class_dirs]

        rng = np.random.default_rng(seed)
        samples: list[tuple[Path, int]] = []
        for d in class_dirs:
            files = sorted(d.glob("*.jpg"))
            if not files:
                continue
            n_val = max(1, int(round(len(files) * val_fraction))) if len(files) > 2 else 0
            order = rng.permutation(len(files))
            val_set = set(order[:n_val].tolist())
            for i, path in enumerate(files):
                is_val = i in val_set
                if (split == "val" and is_val) or (split == "train" and not is_val):
                    samples.append((path, self.class_to_idx[d.name]))
        if not samples:
            raise RuntimeError(f"split {split!r} is empty under {root}")
        self.samples = samples

    def __len__(self) -> int:
        return len(self.samples)

    def __getitem__(self, idx: int):
        path, label = self.samples[idx]
        image = Image.open(path).convert("RGB")
        if self.transform is not None:
            image = self.transform(image)
        return image, label
