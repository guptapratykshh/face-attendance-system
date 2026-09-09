"""Thin CLI wrapper so `python scripts/train.py` matches the other data scripts."""

from __future__ import annotations

from _common import PROJECT_ROOT  # noqa: F401  — puts backend on sys.path
from app.training.train import main

if __name__ == "__main__":
    main()
