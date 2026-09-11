"""Capture-path detection, behavioural risk, and the fused presence-trust decision."""

from __future__ import annotations

from app.liveness.capture_path import analyse_capture_path, extract_features
from app.risk.behaviour import behaviour_risk
from app.risk.fusion import presence_trust


def _probe(heights, rates, response_ms):
    steps = []
    for requested, reported in zip([240, 480, 720, 3001], heights, strict=True):
        steps.append(
            {
                "kind": "height",
                "requested": requested,
                "reported": reported,
                "actual": reported,
                "response_ms": response_ms.pop(0) if response_ms else 10,
                "applied": True,
            }
        )
    for requested, reported in zip([1, 30, 120, 200], rates, strict=True):
        steps.append(
            {
                "kind": "fps",
                "requested": requested,
                "reported": reported,
                "actual": reported,
                "response_ms": response_ms.pop(0) if response_ms else 10,
                "applied": True,
            }
        )
    return {"schema": 1, "duration_ms": 1500, "steps": steps, "context": {"device_count": 1}}


# --------------------------------------------------------------------- capture path


def test_real_camera_negotiates_and_passes():
    """A real sensor reports distinct modes, clamps the impossible one, and varies in timing."""
    report = _probe([240, 480, 720, 1080], [1, 30, 60, 60], [8, 31, 14, 52, 9, 22, 61, 17])
    rec = analyse_capture_path(report)
    assert rec["live"] is True
    assert rec["score"] < 0.5


def test_camera_that_accepts_impossible_settings_is_flagged():
    report = _probe([3001] * 4, [200] * 4, [5] * 8)
    rec = analyse_capture_path(report)
    assert rec["live"] is False
    assert "accepted an impossible resolution" in rec["cues"]
    assert "accepted an impossible frame rate" in rec["cues"]


def test_uniform_response_times_are_a_cue():
    report = _probe([240, 480, 720, 1080], [1, 30, 60, 60], [5.0] * 8)
    rec = analyse_capture_path(report)
    assert "reconfiguration timings were unnaturally uniform" in rec["cues"]


def test_missing_or_malformed_probe_scores_nothing():
    """No telemetry must mean 'no opinion', never 'guilty'."""
    assert analyse_capture_path(None) is None
    assert analyse_capture_path("not json") is None
    assert analyse_capture_path({"schema": 1, "steps": []}) is None


def test_features_survive_partial_ladders():
    report = _probe([240, 480, 720, 1080], [1, 30, 60, 60], [])
    report["steps"] = report["steps"][:3]
    feats = extract_features(report)
    assert feats["n_steps"] == 3
    assert feats["fps_distinct_reported"] is None


# ----------------------------------------------------------------------- behaviour


def test_impossible_travel_dominates_the_risk():
    rec = behaviour_risk({"history_n": 40, "implied_speed_ms": 900.0})
    assert rec["risk"] >= 0.45
    assert "could not have travelled from the previous punch in time" in rec["cues"]


def test_repeat_partner_reads_as_collusion():
    rec = behaviour_risk({"history_n": 40, "collusion_rate": 0.92})
    assert "almost always punches alongside the same person" in rec["cues"]


def test_clockwork_arrivals_are_suspicious():
    rec = behaviour_risk({"history_n": 30, "arrival_stdev_min": 0.3})
    assert "arrival times are unnaturally regular" in rec["cues"]


def test_new_joiner_is_not_accused():
    """Thin history must damp the score, or every first-week punch is a fraud alert."""
    thin = behaviour_risk({"history_n": 2, "implied_speed_ms": 900.0})
    thick = behaviour_risk({"history_n": 40, "implied_speed_ms": 900.0})
    assert thin["risk"] < thick["risk"]


def test_ordinary_punch_is_quiet():
    rec = behaviour_risk(
        {"history_n": 40, "implied_speed_ms": 1.1, "arrival_zscore": 0.4, "arrival_stdev_min": 11.0}
    )
    assert rec["risk"] == 0.0
    assert rec["reason"] == "consistent with this person's pattern"


# -------------------------------------------------------------------------- fusion


def test_all_signals_healthy_accepts():
    out = presence_trust(
        similarity=0.72,
        threshold=0.5,
        liveness={"spoof_score": 0.1},
        capture_path={"score": 0.05},
        behaviour={"risk": 0.05},
    )
    assert out["decision"] == "accept"
    assert out["vetoed_by"] == []


def test_injected_stream_cannot_be_outvoted_by_a_strong_face():
    """The attack this whole layer exists for: a face swap matches *better* than a real user."""
    out = presence_trust(
        similarity=0.95,
        threshold=0.5,
        liveness={"spoof_score": 0.02},
        capture_path={"score": 0.95},
        behaviour={"risk": 0.05},
    )
    assert out["decision"] == "review"
    assert out["vetoed_by"] == ["vcd"]
    assert out["reason"] == "the camera does not look like real hardware"


def test_proxy_punch_is_caught_by_behaviour_alone():
    out = presence_trust(
        similarity=0.75,
        threshold=0.5,
        liveness={"spoof_score": 0.05},
        capture_path={"score": 0.05},
        behaviour={"risk": 0.9},
    )
    assert out["decision"] == "review"
    assert out["vetoed_by"] == ["behaviour"]


def test_missing_signals_are_dropped_not_penalised():
    """A kiosk punch without geolocation is scored on what it has."""
    out = presence_trust(similarity=0.72, threshold=0.5, liveness={"spoof_score": 0.1})
    assert out["decision"] == "accept"
    assert set(out["missing"]) == {"vcd", "behaviour"}
    assert sum(s["weight"] for s in out["signals"].values()) == 1.0


def test_no_signals_at_all_is_unknown_not_accept():
    out = presence_trust()
    assert out["decision"] == "unknown"
    assert out["trust"] is None


def test_weighted_mean_would_have_accepted_what_the_veto_blocks():
    """Guards the design choice: the geometric mean plus floor must beat a plain average here."""
    signals = {
        "similarity": 0.95,
        "threshold": 0.5,
        "liveness": {"spoof_score": 0.02},
        "capture_path": {"score": 0.95},
        "behaviour": {"risk": 0.05},
    }
    out = presence_trust(**signals)
    confidences = [s["confidence"] for s in out["signals"].values() if s["confidence"] is not None]
    plain_average = sum(confidences) / len(confidences)
    assert plain_average > 0.5  # a mean would have let it through
    assert out["decision"] == "review"
