"""Central configuration and filesystem layout."""

from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

PROJECT_ROOT = Path(__file__).resolve().parents[3]

PLACEHOLDER_SECRETS = frozenset(
    {
        "dev-secret-change-me-please-use-env",
        "change-me-in-production",
    }
)


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_prefix="FRS_", extra="ignore")

    # Paths
    data_dir: Path = PROJECT_ROOT / "data"
    weights_dir: Path = PROJECT_ROOT / "weights"
    checkpoint_dir: Path = PROJECT_ROOT / "checkpoints"
    reports_dir: Path = PROJECT_ROOT / "reports"

    # Encoder selection: "facenet" (vendored InceptionResnetV1) or "arcface" (buffalo_l w600k_r50)
    encoder: str = "facenet"
    # Optional fine-tuned checkpoint; when set, overrides the pretrained FaceNet weights.
    facenet_checkpoint: Path | None = None
    device: str = "auto"  # auto -> mps if available, else cpu

    # Detection
    det_thresh: float = 0.5
    det_size: int = 640

    # Recognition thresholds. Defaults are replaced at startup by the values
    # calibrated on LFW at FAR=1e-3 if an evaluation report is present.
    verify_threshold: float = 0.5
    identify_threshold: float = 0.5
    target_far: float = 1e-3

    # API
    api_prefix: str = "/api/v1"
    max_upload_bytes: int = 8 * 1024 * 1024
    cors_origins: list[str] = [
        "http://localhost:5173",
        "http://127.0.0.1:5173",
        "http://localhost:4173",
        "http://localhost",
        "http://127.0.0.1",
    ]

    # Auth
    secret_key: str = "dev-secret-change-me-please-use-env"
    algorithm: str = "HS256"
    access_token_expire_minutes: int = 60 * 12
    admin_username: str = "admin"
    admin_password: str | None = None
    allow_public_register: bool = False
    require_liveness: bool = True
    rate_limit: bool = True

    # Storage
    database_url: str = f"sqlite:///{PROJECT_ROOT / 'frs.db'}"

    # Office clock
    tz: str = "Asia/Kolkata"
    work_start: str = "09:00"
    work_end: str = "18:00"
    late_grace_minutes: int = 15

    # Optional email when a face is enrolled
    smtp_host: str | None = None
    smtp_port: int = 587
    smtp_user: str | None = None
    smtp_password: str | None = None
    smtp_from: str | None = None
    alert_email: str | None = None

    # Liveness
    ear_closed_thresh: float = 0.21
    ear_open_thresh: float = 0.28
    spoof_score_thresh: float = 0.5

    # LLM Assist (OpenAI-compatible)
    llm_api_key: str | None = None
    llm_base_url: str = "https://api.openai.com/v1"
    llm_model: str = "gpt-4o-mini"
    embed_model: str = "text-embedding-3-small"

    @field_validator("cors_origins", mode="before")
    @classmethod
    def _split_origins(cls, value: object) -> object:
        if isinstance(value, str):
            text = value.strip()
            if text.startswith("["):
                return json.loads(text)
            return [part.strip() for part in text.split(",") if part.strip()]
        return value

    @property
    def lfw_dir(self) -> Path:
        return self.data_dir / "lfw"

    @property
    def lfw_images_dir(self) -> Path:
        return self.lfw_dir / "lfw_funneled"

    @property
    def lfw_pairs(self) -> Path:
        return self.lfw_dir / "pairs.txt"

    @property
    def lfw_people(self) -> Path:
        return self.lfw_dir / "people.txt"

    @property
    def train_dir(self) -> Path:
        return self.data_dir / "train"

    @property
    def eval_report(self) -> Path:
        return self.reports_dir / "evaluation.json"

    @property
    def training_log(self) -> Path:
        return self.checkpoint_dir / "training_log.csv"

    @property
    def is_sqlite(self) -> bool:
        return self.database_url.startswith("sqlite")

    @property
    def secret_is_placeholder(self) -> bool:
        key = self.secret_key.strip()
        return key in PLACEHOLDER_SECRETS or len(key.encode("utf-8")) < 32

    def ensure_dirs(self) -> None:
        for d in (self.data_dir, self.weights_dir, self.checkpoint_dir, self.reports_dir):
            d.mkdir(parents=True, exist_ok=True)


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
