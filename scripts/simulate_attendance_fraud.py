#!/usr/bin/env python3
"""Generate a synthetic org history with known fraud injected, for evaluating the trust score.

Real proxy-attendance labels do not exist: nobody annotates their own buddy punching. Every
published result in this area is therefore measured on controlled injection, and this script
follows the same protocol (JSIAR 2026, IEEE ICSMILE 2026) so the numbers are comparable.

It builds a population of employees with individual arrival habits, then injects four fraud types
whose ground truth we know:

    impossible_travel - a punch from a location the person could not have reached in the elapsed
                        time, which is what mock-location apps produce
    collusion         - a pair who always punch within a couple of minutes of each other, the
                        classic buddy-punch signature
    clockwork         - punches at almost exactly the same second every day, which is a script,
                        not a person
    off_pattern       - a punch far outside the person's own established arrival window

    python scripts/simulate_attendance_fraud.py --out data/fraud_sim.jsonl --days 60 --people 40

Writes JSONL where each record carries the behaviour features and an `is_fraud` label, ready for
scripts/evaluate_trust.py.
"""

from __future__ import annotations

import argparse
import json
import math
import random
from datetime import UTC, datetime, timedelta
from pathlib import Path

from _common import PROJECT_ROOT  # noqa: F401  (puts backend/ on sys.path)

# Office at a plausible city location; individual homes scatter around it.
OFFICE_LAT, OFFICE_LNG = 22.3072, 73.1812
FRAUD_TYPES = ("impossible_travel", "collusion", "clockwork", "off_pattern")


def _jitter_coord(lat: float, lng: float, metres: float, rng: random.Random) -> tuple[float, float]:
    bearing = rng.uniform(0, 2 * math.pi)
    dlat = (metres * math.cos(bearing)) / 111_320.0
    dlng = (metres * math.sin(bearing)) / (111_320.0 * math.cos(math.radians(lat)))
    return lat + dlat, lng + dlng


def build(days: int, people: int, fraud_rate: float, seed: int) -> list[dict]:
    rng = random.Random(seed)
    start = datetime(2026, 6, 1, tzinfo=UTC)

    # Each person has a habitual arrival minute and their own punctuality.
    habits = {
        pid: {
            "mean_min": rng.uniform(8 * 60 + 30, 9 * 60 + 45),
            "stdev_min": rng.uniform(4.0, 18.0),
            "site_id": rng.choice([1, 1, 1, 2]),
        }
        for pid in range(1, people + 1)
    }
    # One colluding pair, so the collusion feature has something real to find.
    partner_a, partner_b = 1, 2

    records: list[dict] = []
    for day in range(days):
        date = start + timedelta(days=day)
        if date.weekday() >= 5:
            continue
        for pid, habit in habits.items():
            if rng.random() < 0.06:
                continue  # absent

            fraud_type = None
            if rng.random() < fraud_rate:
                fraud_type = rng.choice(FRAUD_TYPES)

            minute = rng.gauss(habit["mean_min"], habit["stdev_min"])
            lat, lng = _jitter_coord(OFFICE_LAT, OFFICE_LNG, rng.uniform(0, 60), rng)
            site_id = habit["site_id"]
            prev_lat, prev_lng = _jitter_coord(OFFICE_LAT, OFFICE_LNG, rng.uniform(0, 60), rng)
            gap_s = rng.uniform(8 * 3600, 16 * 3600)
            similarity = rng.gauss(0.74, 0.05)

            if fraud_type == "off_pattern":
                minute = habit["mean_min"] + rng.choice([-1, 1]) * rng.uniform(5, 9) * habit["stdev_min"]
            elif fraud_type == "clockwork":
                minute = habit["mean_min"]  # to the second, every day
            elif fraud_type == "impossible_travel":
                gap_s = rng.uniform(120, 900)
                prev_lat, prev_lng = _jitter_coord(OFFICE_LAT, OFFICE_LNG, rng.uniform(300_000, 900_000), rng)
            elif fraud_type == "collusion":
                similarity = rng.gauss(0.66, 0.05)

            moment = date + timedelta(minutes=float(minute))
            records.append(
                {
                    "person_id": pid,
                    "at": moment.isoformat(),
                    "lat": lat,
                    "lng": lng,
                    "prev_lat": prev_lat,
                    "prev_lng": prev_lng,
                    "gap_since_last_s": gap_s,
                    "site_id": site_id,
                    "similarity": max(0.0, min(1.0, similarity)),
                    "personal_mean_min": habit["mean_min"],
                    "personal_stdev_min": habit["stdev_min"],
                    "fraud_type": fraud_type,
                    "is_fraud": int(fraud_type is not None),
                }
            )

            # The colluding partner shadows this punch within the detection window.
            if pid == partner_a and fraud_type == "collusion":
                shadow = moment + timedelta(seconds=rng.uniform(10, 100))
                records.append(
                    {
                        "person_id": partner_b,
                        "at": shadow.isoformat(),
                        "lat": lat,
                        "lng": lng,
                        "prev_lat": prev_lat,
                        "prev_lng": prev_lng,
                        "gap_since_last_s": gap_s,
                        "site_id": site_id,
                        "similarity": max(0.0, min(1.0, rng.gauss(0.66, 0.05))),
                        "personal_mean_min": habits[partner_b]["mean_min"],
                        "personal_stdev_min": habits[partner_b]["stdev_min"],
                        "fraud_type": "collusion",
                        "is_fraud": 1,
                        "collusion_partner_id": partner_a,
                    }
                )

    records.sort(key=lambda r: r["at"])
    return records


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--out", type=Path, default=Path("data/fraud_sim.jsonl"))
    ap.add_argument("--days", type=int, default=60)
    ap.add_argument("--people", type=int, default=40)
    ap.add_argument("--fraud-rate", type=float, default=0.08)
    ap.add_argument("--seed", type=int, default=7)
    args = ap.parse_args()

    records = build(args.days, args.people, args.fraud_rate, args.seed)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    with args.out.open("w") as fh:
        for row in records:
            fh.write(json.dumps(row) + "\n")

    frauds = sum(r["is_fraud"] for r in records)
    print(f"wrote {len(records)} punches to {args.out}")
    print(f"  fraudulent: {frauds} ({100 * frauds / len(records):.1f}%)")
    for kind in FRAUD_TYPES:
        print(f"  {kind:18} {sum(1 for r in records if r['fraud_type'] == kind)}")


if __name__ == "__main__":
    main()
