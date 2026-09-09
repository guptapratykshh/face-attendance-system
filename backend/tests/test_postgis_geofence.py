"""PostGIS ST_DWithin geofence path (skipped unless Postgres+PostGIS is available)."""

from __future__ import annotations

import os

import pytest
from app.core.config import settings
from app.core.geo import point_within_site, postgis_ready, sync_site_geom
from app.db.models import Organization, Site
from app.db.session import configure_engine
from app.db.session import engine as global_engine
from sqlalchemy import text
from sqlmodel import Session, SQLModel


def _pg_url() -> str | None:
    url = os.environ.get("FRS_DATABASE_URL") or settings.database_url
    if not str(url).startswith("postgresql"):
        return None
    return str(url)


@pytest.fixture(scope="module")
def pg_session():
    url = _pg_url()
    if url is None:
        pytest.skip("FRS_DATABASE_URL is not Postgres")
    configure_engine(url)
    assert global_engine is not None
    with Session(global_engine) as session:
        try:
            session.connection().execute(text("CREATE EXTENSION IF NOT EXISTS postgis"))
            session.commit()
        except Exception as exc:
            pytest.skip(f"PostGIS unavailable: {exc}")
        if not postgis_ready(session):
            pytest.skip("postgis extension not loaded")
        SQLModel.metadata.create_all(global_engine)
        # Ensure geom columns exist (migration may not have run)
        session.connection().execute(
            text("ALTER TABLE site ADD COLUMN IF NOT EXISTS geom geography(Point, 4326)")
        )
        session.connection().execute(
            text("ALTER TABLE attendance ADD COLUMN IF NOT EXISTS punch_geom geography(Point, 4326)")
        )
        session.commit()
        yield session


def test_postgis_ready(pg_session: Session):
    assert postgis_ready(pg_session) is True


def test_st_dwithin_inside_and_outside(pg_session: Session):
    import secrets

    org = Organization(name="Geo Org", slug=f"geo-{secrets.token_hex(4)}")
    pg_session.add(org)
    pg_session.commit()
    pg_session.refresh(org)
    site = Site(
        org_id=org.id,
        name="Gate",
        lat=28.6139,
        lng=77.2090,
        radius_m=150,
    )
    pg_session.add(site)
    pg_session.commit()
    pg_session.refresh(site)
    sync_site_geom(pg_session, site)
    pg_session.commit()

    assert point_within_site(pg_session, 28.6139, 77.2090, site) is True
    assert point_within_site(pg_session, 19.0760, 72.8777, site) is False

    hit = pg_session.connection().execute(
        text(
            """
            SELECT ST_DWithin(
                geom,
                ST_SetSRID(ST_MakePoint(:lng, :lat), 4326)::geography,
                :radius
            )
            FROM site WHERE id = :id
            """
        ),
        {"id": int(site.id), "lat": 28.6139, "lng": 77.2090, "radius": 150},
    ).scalar()
    assert hit is True
