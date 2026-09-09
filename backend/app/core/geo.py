"""PostGIS geofence helpers with Haversine fallback for SQLite / non-PostGIS DBs."""

from __future__ import annotations

from sqlalchemy import text
from sqlmodel import Session

from app.core.clock import haversine_m
from app.db.models import Organization, Site

_POSTGIS_CACHE: dict[int, bool] = {}


def postgis_ready(session: Session | None) -> bool:
    if session is None:
        return False
    bind = session.get_bind()
    if bind.dialect.name != "postgresql":
        return False
    key = id(bind)
    if key in _POSTGIS_CACHE:
        return _POSTGIS_CACHE[key]
    try:
        ok = bool(
            session.connection().execute(text("SELECT EXISTS(SELECT 1 FROM pg_extension WHERE extname = 'postgis')")).scalar()
        )
    except Exception:
        ok = False
    _POSTGIS_CACHE[key] = ok
    return ok


def sync_site_geom(session: Session, site: Site) -> None:
    """Keep site.geom in sync with lat/lng when PostGIS is available."""
    if not postgis_ready(session) or site.id is None:
        return
    if site.lat is None or site.lng is None:
        session.connection().execute(
            text("UPDATE site SET geom = NULL WHERE id = :id"),
            {"id": int(site.id)},
        )
        return
    session.connection().execute(
        text(
            """
            UPDATE site
            SET geom = ST_SetSRID(ST_MakePoint(:lng, :lat), 4326)::geography
            WHERE id = :id
            """
        ),
        {"id": int(site.id), "lat": float(site.lat), "lng": float(site.lng)},
    )


def set_punch_geom(session: Session, attendance_id: int, lat: float | None, lng: float | None) -> None:
    if not postgis_ready(session) or attendance_id is None:
        return
    if lat is None or lng is None:
        return
    session.connection().execute(
        text(
            """
            UPDATE attendance
            SET punch_geom = ST_SetSRID(ST_MakePoint(:lng, :lat), 4326)::geography
            WHERE id = :id
            """
        ),
        {"id": int(attendance_id), "lat": float(lat), "lng": float(lng)},
    )


def point_within_site(session: Session, lat: float, lng: float, site: Site) -> bool:
    if site.lat is None or site.lng is None:
        return False
    radius = float(site.radius_m or 0)
    if radius <= 0:
        return False
    if postgis_ready(session) and site.id is not None:
        sync_site_geom(session, site)
        hit = session.connection().execute(
            text(
                """
                SELECT ST_DWithin(
                    geom,
                    ST_SetSRID(ST_MakePoint(:lng, :lat), 4326)::geography,
                    :radius
                )
                FROM site
                WHERE id = :id AND geom IS NOT NULL
                """
            ),
            {"id": int(site.id), "lat": float(lat), "lng": float(lng), "radius": radius},
        ).scalar()
        if hit is not None:
            return bool(hit)
    return haversine_m(float(site.lat), float(site.lng), float(lat), float(lng)) <= radius


def point_within_office(session: Session, lat: float, lng: float, cfg: Organization) -> bool:
    if cfg.geo_lat is None or cfg.geo_lng is None:
        return True
    radius = float(cfg.geo_radius_m or 0)
    if radius <= 0:
        return True
    if postgis_ready(session):
        hit = session.connection().execute(
            text(
                """
                SELECT ST_DWithin(
                    ST_SetSRID(ST_MakePoint(:olng, :olat), 4326)::geography,
                    ST_SetSRID(ST_MakePoint(:lng, :lat), 4326)::geography,
                    :radius
                )
                """
            ),
            {
                "olat": float(cfg.geo_lat),
                "olng": float(cfg.geo_lng),
                "lat": float(lat),
                "lng": float(lng),
                "radius": radius,
            },
        ).scalar()
        if hit is not None:
            return bool(hit)
    return haversine_m(float(cfg.geo_lat), float(cfg.geo_lng), float(lat), float(lng)) <= radius
