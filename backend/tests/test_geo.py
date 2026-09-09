"""Geofence helpers: Haversine on SQLite; PostGIS when extension is present."""

from __future__ import annotations

from app.core.attendance_policy import _inside_site
from app.core.clock import haversine_m
from app.core.geo import point_within_office, postgis_ready
from app.db.models import Organization, Site
from app.db.session import engine
from sqlmodel import Session


def test_haversine_nearby_is_small():
    d = haversine_m(28.6139, 77.2090, 28.6149, 77.2090)
    assert 90 < d < 140


def test_inside_site_haversine_without_session():
    site = Site(id=1, name="HQ", lat=28.6139, lng=77.2090, radius_m=150)
    assert _inside_site(28.6139, 77.2090, site, session=None) is True
    assert _inside_site(19.0760, 72.8777, site, session=None) is False


def test_point_within_office_on_sqlite(client):
    assert engine is not None
    with Session(engine) as session:
        assert postgis_ready(session) is False
        cfg = Organization(geo_lat=28.6139, geo_lng=77.2090, geo_radius_m=150)
        assert point_within_office(session, 28.6139, 77.2090, cfg) is True
        assert point_within_office(session, 19.0760, 72.8777, cfg) is False
