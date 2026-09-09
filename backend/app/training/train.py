"""Fine-tune Inception-ResNet-v1 with an ArcFace head on the VGGFace2 subset.

Early blocks stay frozen so the 402-identity subset cannot wash out the published
VGGFace2 features. The ArcFace head (and the later residual blocks) are what move.

Usage:
    python scripts/train.py
    python scripts/train.py --epochs 8 --batch-size 32
"""

from __future__ import annotations

import argparse
import csv
import time
from pathlib import Path

import torch
from torch import nn
from torch.optim import AdamW
from torch.optim.lr_scheduler import CosineAnnealingLR
from torch.utils.data import DataLoader

from app.core.config import settings
from app.encoders.facenet import resolve_device
from app.encoders.inception_resnet_v1 import InceptionResnetV1
from app.training.dataset import IdentityFolder, default_eval_transform, default_train_transform
from app.training.losses import ArcFaceHead

FROZEN_PREFIXES = (
    "conv2d_1a",
    "conv2d_2a",
    "conv2d_2b",
    "maxpool_3a",
    "conv2d_3b",
    "conv2d_4a",
    "conv2d_4b",
    "repeat_1",
    "mixed_6a",
)


def freeze_early(model: nn.Module) -> int:
    frozen = 0
    for name, param in model.named_parameters():
        if any(name.startswith(p) for p in FROZEN_PREFIXES):
            param.requires_grad_(False)
            frozen += 1
    return frozen


def accuracy(logits: torch.Tensor, labels: torch.Tensor) -> float:
    return float((logits.argmax(dim=1) == labels).float().mean().item())


def run_epoch(model, head, loader, optimizer, device, train: bool, margin: float) -> dict:
    model.train(train)
    head.train(train)
    total_loss = 0.0
    total_acc = 0.0
    n = 0
    ctx = torch.enable_grad() if train else torch.no_grad()
    with ctx:
        for images, labels in loader:
            images = images.to(device, non_blocking=True)
            labels = labels.to(device, non_blocking=True)
            embeddings = model(images)
            logits = head(embeddings, labels, margin=margin)
            loss = nn.functional.cross_entropy(logits, labels)
            if train:
                optimizer.zero_grad(set_to_none=True)
                loss.backward()
                nn.utils.clip_grad_norm_(
                    [p for p in list(model.parameters()) + list(head.parameters()) if p.requires_grad],
                    5.0,
                )
                optimizer.step()
            bs = labels.size(0)
            total_loss += float(loss.item()) * bs
            total_acc += accuracy(logits, labels) * bs
            n += bs
    return {"loss": total_loss / max(n, 1), "acc": total_acc / max(n, 1)}


def margin_at_epoch(epoch: int, warmup: int, target: float) -> float:
    if warmup <= 0:
        return target
    return target * min(1.0, (epoch + 1) / warmup)


def train(
    data_dir: Path | None = None,
    epochs: int = 8,
    batch_size: int = 32,
    lr: float = 1e-4,
    head_lr: float = 1e-3,
    weight_decay: float = 1e-4,
    num_workers: int = 0,
    seed: int = 0,
) -> Path:
    torch.manual_seed(seed)
    settings.ensure_dirs()
    root = data_dir or (settings.data_dir / "train_aligned")
    if not root.exists():
        raise SystemExit(f"missing {root}; run `python scripts/prepare_crops.py --train` first")

    device = resolve_device(settings.device)
    train_ds = IdentityFolder(root, split="train", transform=default_train_transform(), seed=seed)
    val_ds = IdentityFolder(root, split="val", transform=default_eval_transform(), seed=seed)
    n_classes = len(train_ds.classes)
    print(f"device={device}  identities={n_classes}  train={len(train_ds)}  val={len(val_ds)}")

    train_loader = DataLoader(
        train_ds,
        batch_size=batch_size,
        shuffle=True,
        num_workers=num_workers,
        pin_memory=device.type == "cuda",
        drop_last=True,
    )
    val_loader = DataLoader(val_ds, batch_size=batch_size, shuffle=False, num_workers=num_workers)

    model = InceptionResnetV1(pretrained="vggface2").to(device)
    frozen = freeze_early(model)
    print(f"froze {frozen} early-block parameters")
    head = ArcFaceHead(512, n_classes).to(device)

    params = [
        {"params": [p for p in model.parameters() if p.requires_grad], "lr": lr},
        {"params": head.parameters(), "lr": head_lr},
    ]
    optimizer = AdamW(params, weight_decay=weight_decay)
    scheduler = CosineAnnealingLR(optimizer, T_max=epochs)

    log_path = settings.training_log
    log_path.parent.mkdir(parents=True, exist_ok=True)
    best_acc = -1.0
    best_path = settings.checkpoint_dir / "facenet_arcface.pt"

    with log_path.open("w", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=["epoch", "margin", "train_loss", "train_acc", "val_loss", "val_acc", "seconds"])
        writer.writeheader()
        fh.flush()
        for epoch in range(epochs):
            t0 = time.perf_counter()
            margin = margin_at_epoch(epoch, warmup=2, target=0.5)
            train_m = run_epoch(model, head, train_loader, optimizer, device, True, margin)
            val_m = run_epoch(model, head, val_loader, optimizer, device, False, margin)
            scheduler.step()
            elapsed = time.perf_counter() - t0
            row = {
                "epoch": epoch + 1,
                "margin": round(margin, 4),
                "train_loss": round(train_m["loss"], 4),
                "train_acc": round(train_m["acc"], 4),
                "val_loss": round(val_m["loss"], 4),
                "val_acc": round(val_m["acc"], 4),
                "seconds": round(elapsed, 1),
            }
            writer.writerow(row)
            fh.flush()
            print(
                f"epoch {epoch + 1}/{epochs}  m={margin:.2f}  "
                f"train {train_m['loss']:.3f}/{train_m['acc'] * 100:.1f}%  "
                f"val {val_m['loss']:.3f}/{val_m['acc'] * 100:.1f}%  {elapsed:.0f}s"
            )
            if val_m["acc"] >= best_acc:
                best_acc = val_m["acc"]
                torch.save(
                    {
                        "backbone": {k: v.detach().cpu() for k, v in model.state_dict().items()},
                        "head": {k: v.detach().cpu() for k, v in head.state_dict().items()},
                        "n_classes": n_classes,
                        "epoch": epoch + 1,
                        "val_acc": best_acc,
                    },
                    best_path,
                )
    print(f"best val acc {best_acc * 100:.2f}% -> {best_path}")
    return best_path


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--data-dir", type=Path, default=None)
    ap.add_argument("--epochs", type=int, default=8)
    ap.add_argument("--batch-size", type=int, default=32)
    ap.add_argument("--lr", type=float, default=1e-4)
    ap.add_argument("--head-lr", type=float, default=1e-3)
    ap.add_argument("--num-workers", type=int, default=0)
    args = ap.parse_args()
    train(
        data_dir=args.data_dir,
        epochs=args.epochs,
        batch_size=args.batch_size,
        lr=args.lr,
        head_lr=args.head_lr,
        num_workers=args.num_workers,
    )


if __name__ == "__main__":
    main()
