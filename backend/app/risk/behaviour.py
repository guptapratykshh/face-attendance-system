"""Longitudinal plausibility of a punch, judged against the org's own attendance history.

Per-transaction checks answer "is this a live face at an allowed place". They cannot answer "does
this punch make sense for this person". A colleague punching for you from inside the geofence
passes every per-transaction gate; what gives it away is the pattern - the same pair always
arriving together, an arrival time far outside someone's habit, or a punch that would have needed a
helicopter to reach from the last one.

The published work in this area (Isolation Forest over attendance logs, LSTM over GPS traces) runs
offline as an HR report. Here the features are cheap enough to compute inside the request, so the
score becomes part of the accept decision instead of a monthly audit.

Every feature degrades to None when there is not enough history, and the risk function ignores
None rather than assuming the worst. A new joiner with no history must not be treated as a fraud.
"""

from __future__ import annotations

import math
from datetime import UTC, datetime, timedelta

from sqlmodel import Session, col, select

from app.core.clock import haversine_m
from app.db.models import Attendance

# Above this the punch could not have been reached from the previous one by any normal means.
# Commercial flight cruise is ~250 m/s; anything past that is a location lie or a second person.
IMPOSSIBLE_SPEED_MS = 250.0
# Below this we do not bother: GPS jitter over a short gap produces meaningless speeds.
MIN_TRAVEL_GAP_S = 60.0
# History depth for personal baselines. Long enough to learn a habit, short enough to adapt.
HISTORY_DAYS = 90
HISTORY_LIMIT = 200
# Two people punching within this window, repeatedly, is the classic buddy-punch signature.
COLLUSION_WINDOW_S = 120
COLLUSION_LOOKBACK_DAYS = 30


def _aware(value: datetime | None) -> datetime | None:
    if value is None:
        return None
    return value if value.tzinfo is not None else value.replace(tzinfo=UTC)


def _minutes_into_day(moment: datetime) -> float:
    return moment.hour * 60.0 + moment.minute + moment.second / 60.0


def _mean(values: list[float]) -> float | None:
    return sum(values) / len(values) if values else None


def _stdev(values: list[float]) -> float | None:
    if len(values) < 2:
        return None
    mu = sum(values) / len(values)
    return math.sqrt(sum((v - mu) ** 2 for v in values) / (len(values) - 1))


def _history(session: Session, person_id: int, before: datetime) -> list[Attendance]:
    since = before - timedelta(days=HISTORY_DAYS)
    rows = session.exec(
        select(Attendance)
        .where(col(Attendance.person_id) == person_id)
        .where(col(Attendance.created_at) < before.replace(tzinfo=None))
        .where(col(Attendance.created_at) >= since.replace(tzinfo=None))
        .order_by(col(Attendance.created_at).desc())
        .limit(HISTORY_LIMIT)
    ).all()
    return list(rows)


def _collusion_rate(session: Session, person_id: int, before: datetime) -> tuple[float | None, int | None]:
    """How often this person's punches are shadowed by the same other person, within two minutes.

    A shared office produces a broad spread of near-simultaneous colleagues. Buddy punching
    concentrates on one partner, so we report the strongest single pairing, not the raw count.
    """
    since = before - timedelta(days=COLLUSION_LOOKBACK_DAYS)
    mine = session.exec(
        select(Attendance)
        .where(col(Attendance.person_id) == person_id)
        .where(col(Attendance.created_at) < before.replace(tzinfo=None))
        .where(col(Attendance.created_at) >= since.replace(tzinfo=None))
        .order_by(col(Attendance.created_at).desc())
        .limit(HISTORY_LIMIT)
    ).all()
    if len(mine) < 4:
        return None, None

    others = session.exec(
        select(Attendance)
        .where(col(Attendance.person_id) != person_id)
        .where(col(Attendance.created_at) < before.replace(tzinfo=None))
        .where(col(Attendance.created_at) >= since.replace(tzinfo=None))
        .order_by(col(Attendance.created_at).desc())
        .limit(HISTORY_LIMIT * 20)
    ).all()
    if not others:
        return 0.0, None

    pair_hits: dict[int, int] = {}
    for row in mine:
        mine_at = _aware(row.created_at)
        if mine_at is None:
            continue
        for other in others:
            other_at = _aware(other.created_at)
            if other_at is None:
                continue
            if abs((other_at - mine_at).total_seconds()) <= COLLUSION_WINDOW_S:
                pair_hits[other.person_id] = pair_hits.get(other.person_id, 0) + 1

    if not pair_hits:
        return 0.0, None
    partner, hits = max(pair_hits.items(), key=lambda kv: kv[1])
    return hits / len(mine), int(partner)


def behaviour_features(
    session: Session,
    *,
    person_id: int,
    at: datetime | None = None,
    lat: float | None = None,
    lng: float | None = None,
    site_id: int | None = None,
    similarity: float | None = None,
) -> dict[str, float | int | None]:
    """Describe how well this punch fits the person's established pattern."""
    now = _aware(at) or datetime.now(UTC)
    history = _history(session, person_id, now)

    feats: dict[str, float | int | None] = {
        "history_n": len(history),
        "gap_since_last_s": None,
        "implied_speed_ms": None,
        "distance_from_last_m": None,
        "arrival_minutes": round(_minutes_into_day(now), 2),
        "arrival_deviation_min": None,
        "arrival_zscore": None,
        "arrival_stdev_min": None,
        "site_switch_rate": None,
        "site_is_new": None,
        "collusion_rate": None,
        "collusion_partner_id": None,
        "similarity_drift": None,
    }
    if not history:
        return feats

    previous = history[0]
    prev_at = _aware(previous.created_at)
    if prev_at is not None:
        gap = (now - prev_at).total_seconds()
        feats["gap_since_last_s"] = round(gap, 1)
        if (
            gap >= MIN_TRAVEL_GAP_S
            and lat is not None
            and lng is not None
            and previous.latitude is not None
            and previous.longitude is not None
        ):
            metres = haversine_m(float(previous.latitude), float(previous.longitude), float(lat), float(lng))
            feats["distance_from_last_m"] = round(metres, 1)
            feats["implied_speed_ms"] = round(metres / gap, 3)

    # Personal arrival habit, using the first punch of each past day only.
    first_of_day: dict[str, datetime] = {}
    for row in history:
        moment = _aware(row.created_at)
        if moment is None:
            continue
        key = moment.date().isoformat()
        if key not in first_of_day or moment < first_of_day[key]:
            first_of_day[key] = moment
    arrivals = [_minutes_into_day(m) for m in first_of_day.values()]
    baseline = _mean(arrivals)
    spread = _stdev(arrivals)
    if baseline is not None:
        deviation = _minutes_into_day(now) - baseline
        feats["arrival_deviation_min"] = round(deviation, 2)
        if spread is not None:
            feats["arrival_stdev_min"] = round(spread, 2)
            # A tiny spread means "clockwork" punching, which is itself suspicious, so floor the
            # denominator instead of letting the z-score explode.
            feats["arrival_zscore"] = round(deviation / max(spread, 3.0), 3)

    sites = [row.site_id for row in history if row.site_id is not None]
    if sites:
        switches = sum(1 for a, b in zip(sites, sites[1:], strict=False) if a != b)
        feats["site_switch_rate"] = round(switches / max(len(sites) - 1, 1), 3)
        if site_id is not None:
            feats["site_is_new"] = 0 if site_id in set(sites) else 1

    rate, partner = _collusion_rate(session, person_id, now)
    feats["collusion_rate"] = None if rate is None else round(rate, 3)
    feats["collusion_partner_id"] = partner

    if similarity is not None:
        past = [float(r.similarity) for r in history if r.similarity is not None]
        mean_sim = _mean(past)
        if mean_sim is not None:
            feats["similarity_drift"] = round(float(similarity) - mean_sim, 4)

    return feats


def behaviour_risk(features: dict[str, float | int | None]) -> dict:
    """Turn the features into a [0, 1] risk with the cues that produced it.

    Weighted rules rather than a fitted model, because the training labels for real proxy
    attendance do not exist yet. scripts/simulate_attendance_fraud.py generates the synthetic set
    these weights are tuned against, and scripts/evaluate_trust.py reports them.
    """
    risk = 0.0
    cues: list[str] = []

    speed = features.get("implied_speed_ms")
    if isinstance(speed, (int, float)) and speed > IMPOSSIBLE_SPEED_MS:
        risk += 0.45
        cues.append("could not have travelled from the previous punch in time")
    elif isinstance(speed, (int, float)) and speed > IMPOSSIBLE_SPEED_MS / 5:
        risk += 0.15
        cues.append("moved unusually fast since the previous punch")

    z = features.get("arrival_zscore")
    if isinstance(z, (int, float)):
        if abs(z) > 4:
            risk += 0.20
            cues.append("arrived far outside this person's usual time")
        elif abs(z) > 2.5:
            risk += 0.08
            cues.append("arrived outside this person's usual time")

    spread = features.get("arrival_stdev_min")
    n = features.get("history_n") or 0
    if isinstance(spread, (int, float)) and spread < 1.0 and n >= 10:
        # Humans do not arrive at the same second every day; machines and scripts do.
        risk += 0.15
        cues.append("arrival times are unnaturally regular")

    collusion = features.get("collusion_rate")
    if isinstance(collusion, (int, float)):
        if collusion > 0.8:
            risk += 0.25
            cues.append("almost always punches alongside the same person")
        elif collusion > 0.5:
            risk += 0.10
            cues.append("often punches alongside the same person")

    if features.get("site_is_new") == 1:
        risk += 0.08
        cues.append("first punch at this site")

    drift = features.get("similarity_drift")
    if isinstance(drift, (int, float)) and drift < -0.12:
        risk += 0.12
        cues.append("face match is weaker than usual for this person")

    risk = min(risk, 1.0)
    if n < 5:
        # Too little history to accuse anyone; damp the score toward neutral.
        risk *= 0.4
        cues.append("limited history, score damped")

    return {
        "risk": round(risk, 4),
        "reason": "; ".join(cues) if cues else "consistent with this person's pattern",
        "cues": cues,
        "features": features,
    }
