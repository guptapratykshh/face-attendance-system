"""One-shot copy of people, faces, users, and attendance from SQLite into Postgres.

Usage (Postgres must already be migrated):

    FRS_DATABASE_URL=postgresql+psycopg://frs:frs@localhost:5432/frs \\
      python scripts/migrate_sqlite_to_postgres.py --sqlite frs.db
"""

from __future__ import annotations

import argparse
from pathlib import Path

from app.core.config import PROJECT_ROOT, settings
from app.db.models import (
    AccessEvent,
    AppSetting,
    Attendance,
    FaceEmbedding,
    Person,
    SpoofAlert,
    User,
)
from sqlalchemy.orm import sessionmaker
from sqlmodel import Session, SQLModel, create_engine, select


def _session(url: str) -> Session:
    engine = create_engine(url)
    factory = sessionmaker(bind=engine, class_=Session, expire_on_commit=False)
    return factory()


def _copy(model: type[SQLModel], src: Session, dst: Session) -> int:
    rows = list(src.exec(select(model)).all())
    for row in rows:
        payload = row.model_dump()
        dst.merge(model(**payload))
    dst.commit()
    return len(rows)


def main() -> None:
    parser = argparse.ArgumentParser(description="Copy FRS SQLite rows into Postgres")
    parser.add_argument("--sqlite", type=Path, default=PROJECT_ROOT / "frs.db")
    parser.add_argument("--postgres", default=settings.database_url)
    args = parser.parse_args()
    sqlite_url = f"sqlite:///{args.sqlite.resolve()}"
    if args.postgres.startswith("sqlite"):
        raise SystemExit("FRS_DATABASE_URL / --postgres must point at PostgreSQL")

    src = _session(sqlite_url)
    dst = _session(args.postgres)
    try:
        counts = {
            "person": _copy(Person, src, dst),
            "user": _copy(User, src, dst),
            "faceembedding": _copy(FaceEmbedding, src, dst),
            "accessevent": _copy(AccessEvent, src, dst),
            "attendance": _copy(Attendance, src, dst),
            "appsetting": _copy(AppSetting, src, dst),
            "spoofalert": _copy(SpoofAlert, src, dst),
        }
    finally:
        src.close()
        dst.close()
    print("copied", counts)


if __name__ == "__main__":
    main()
