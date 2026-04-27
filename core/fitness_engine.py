"""Fitness Engine — Running, Cycling, Gym, Tennis modules.

Each sport persists its own history file. All methods are
thread-safe and return dicts ready for JSON serialisation.
"""
from __future__ import annotations

import hashlib
import json
import threading
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional


# ── Coaching tips library ─────────────────────────────────────────────

_TIPS: Dict[str, List[str]] = {
    "running": [
        "Keep a conversational pace on easy days — if you can't hold a full sentence, slow down.",
        "Aim for a cadence of 170–180 steps/min to reduce injury risk.",
        "Run your long runs at least 90 seconds per mile slower than race pace.",
        "Strength training twice a week significantly reduces running injuries.",
        "Hydrate 30 minutes before every run and every 20 minutes during long efforts.",
        "A proper warm-up of 5–10 min easy jog reduces strain on cold muscles.",
        "Hill repeats once a week build power and efficiency without extra mileage.",
    ],
    "cycling": [
        "Aim for a cadence of 85–95 RPM — it's easier on your joints than grinding.",
        "Practise two-minute rest intervals for every 20 minutes at Zone 3 effort.",
        "Proper saddle height should leave a slight bend in your knee at the bottom of the pedal stroke.",
        "On climbs, stay seated as long as possible to conserve energy.",
        "Fuel with carbohydrates every 45 min during rides over 90 minutes.",
        "Core strength directly translates to power transfer on the bike.",
        "Keep your shoulders relaxed — tension wastes energy on long rides.",
    ],
    "gym": [
        "Progressive overload: increase weight or reps by 5% each week to keep gaining.",
        "Compound lifts first — squats, deadlifts, bench — while you're freshest.",
        "Rest 90–120 seconds between heavy sets; 45–60 seconds for hypertrophy work.",
        "Track your lifts — you can't manage what you don't measure.",
        "Warm up with 50% of working weight for two sets before heavy sets.",
        "Sleep is where the gains happen. 7–9 hours is non-negotiable.",
        "Protein timing: consume 20–40g within 30 minutes of finishing your session.",
    ],
    "tennis": [
        "Focus on consistent first-serve placement over raw pace.",
        "Watch the ball until it contacts your strings — simple but game-changing.",
        "Practice cross-court rallies — 80% of points should go cross-court.",
        "Split-step just as your opponent makes contact to improve reaction time.",
        "A strong serve is built on leg drive, not arm strength.",
        "Record yourself — your felt technique and your real technique often differ.",
        "Consistency beats winners. Push opponents to beat you, not yourself.",
    ],
}

_TARGETS: Dict[str, Dict[str, Any]] = {
    "running":  {"weekly_km": 30,  "weekly_sessions": 4},
    "cycling":  {"weekly_km": 80,  "weekly_sessions": 3},
    "gym":      {"weekly_sessions": 4, "weekly_sets": 60},
    "tennis":   {"weekly_sessions": 3},
}


# ── Helpers ────────────────────────────────────────────────────────────

def _now() -> str:
    return datetime.utcnow().isoformat()

def _today() -> str:
    return datetime.utcnow().strftime("%Y-%m-%d")

def _gen_id() -> str:
    return hashlib.sha256(datetime.utcnow().isoformat().encode()).hexdigest()[:10]

def _week_start() -> str:
    d = datetime.utcnow()
    return (d - timedelta(days=d.weekday())).strftime("%Y-%m-%d")


# ── Per-sport entry schemas ────────────────────────────────────────────
# Running:  {distance_km, duration_min, pace_min_km, heart_rate, route, notes}
# Cycling:  {distance_km, duration_min, avg_speed_kmh, elevation_m, notes}
# Gym:      {exercises: [{name, sets, reps, weight_kg}], notes, muscle_groups}
# Tennis:   {result, opponent, score, duration_min, notes}


class FitnessEngine:
    """Handles logging and retrieval for all fitness sports per user."""

    SPORTS = ("running", "cycling", "gym", "tennis")

    def __init__(self, base_dir: str, user_id: str = "owner") -> None:
        self._base = Path(base_dir)
        self._user = user_id
        self._lock = threading.Lock()
        self._base.mkdir(parents=True, exist_ok=True)
        for sport in self.SPORTS:
            p = self._path(sport)
            if not p.exists():
                self._write(sport, {"workouts": []})

    # ── Public API ─────────────────────────────────────────────────────

    def log_workout(self, sport: str, data: Dict[str, Any]) -> Dict[str, Any]:
        self._check_sport(sport)
        entry = {
            "id":      _gen_id(),
            "date":    data.get("date", _today()),
            "logged_at": _now(),
            **{k: v for k, v in data.items() if k != "id"},
        }
        with self._lock:
            d = self._read(sport)
            d["workouts"].append(entry)
            if len(d["workouts"]) > 200:
                d["workouts"] = d["workouts"][-150:]
            self._write(sport, d)
        return entry

    def get_history(self, sport: str, limit: int = 10, offset: int = 0) -> Dict[str, Any]:
        self._check_sport(sport)
        workouts = list(reversed(self._read(sport).get("workouts", [])))
        return {
            "sport":   sport,
            "total":   len(workouts),
            "items":   workouts[offset: offset + limit],
            "offset":  offset,
            "limit":   limit,
        }

    def get_stats(self, sport: str) -> Dict[str, Any]:
        self._check_sport(sport)
        workouts = self._read(sport).get("workouts", [])
        week = _week_start()

        if sport == "running":
            return self._running_stats(workouts, week)
        if sport == "cycling":
            return self._cycling_stats(workouts, week)
        if sport == "gym":
            return self._gym_stats(workouts, week)
        if sport == "tennis":
            return self._tennis_stats(workouts, week)
        return {}

    def get_tips(self, sport: str, n: int = 3) -> List[str]:
        self._check_sport(sport)
        import random
        pool = _TIPS.get(sport, [])
        return random.sample(pool, min(n, len(pool)))

    def get_targets(self, sport: str) -> Dict[str, Any]:
        self._check_sport(sport)
        return _TARGETS.get(sport, {})

    def all_stats(self) -> Dict[str, Any]:
        return {sport: self.get_stats(sport) for sport in self.SPORTS}

    # ── Sport-specific stats ───────────────────────────────────────────

    def _running_stats(self, workouts: List[Dict], week: str) -> Dict[str, Any]:
        all_km = [w.get("distance_km", 0) for w in workouts if w.get("distance_km")]
        week_w = [w for w in workouts if w.get("date", "") >= week]
        week_km = sum(w.get("distance_km", 0) for w in week_w)
        paces = [w.get("pace_min_km") for w in workouts if w.get("pace_min_km")]
        return {
            "sport": "running",
            "total_sessions":   len(workouts),
            "total_km":         round(sum(all_km), 1),
            "week_sessions":    len(week_w),
            "week_km":          round(week_km, 1),
            "best_km":          round(max(all_km), 1) if all_km else 0,
            "avg_pace_min_km":  round(sum(paces) / len(paces), 2) if paces else None,
            "last_run":         workouts[-1] if workouts else None,
            "targets":          _TARGETS["running"],
        }

    def _cycling_stats(self, workouts: List[Dict], week: str) -> Dict[str, Any]:
        all_km = [w.get("distance_km", 0) for w in workouts if w.get("distance_km")]
        week_w = [w for w in workouts if w.get("date", "") >= week]
        week_km = sum(w.get("distance_km", 0) for w in week_w)
        speeds = [w.get("avg_speed_kmh") for w in workouts if w.get("avg_speed_kmh")]
        return {
            "sport": "cycling",
            "total_sessions":   len(workouts),
            "total_km":         round(sum(all_km), 1),
            "week_sessions":    len(week_w),
            "week_km":          round(week_km, 1),
            "best_km":          round(max(all_km), 1) if all_km else 0,
            "avg_speed_kmh":    round(sum(speeds) / len(speeds), 1) if speeds else None,
            "last_ride":        workouts[-1] if workouts else None,
            "targets":          _TARGETS["cycling"],
        }

    def _gym_stats(self, workouts: List[Dict], week: str) -> Dict[str, Any]:
        week_w = [w for w in workouts if w.get("date", "") >= week]
        all_sets = []
        for w in workouts:
            for ex in w.get("exercises", []):
                all_sets.extend([ex] * int(ex.get("sets", 1)))
        week_sets = sum(
            len(w.get("exercises", [])) * max(1, sum(e.get("sets", 1) for e in w.get("exercises", [])))
            for w in week_w
        )
        top_lifts: Dict[str, float] = {}
        for w in workouts:
            for ex in w.get("exercises", []):
                n = ex.get("name", "")
                kg = ex.get("weight_kg", 0) or 0
                if n and kg > top_lifts.get(n, 0):
                    top_lifts[n] = kg
        return {
            "sport": "gym",
            "total_sessions":   len(workouts),
            "week_sessions":    len(week_w),
            "week_sets_est":    week_sets,
            "personal_bests":   top_lifts,
            "last_session":     workouts[-1] if workouts else None,
            "targets":          _TARGETS["gym"],
        }

    def _tennis_stats(self, workouts: List[Dict], week: str) -> Dict[str, Any]:
        week_w = [w for w in workouts if w.get("date", "") >= week]
        wins   = [w for w in workouts if (w.get("result") or "").lower() == "win"]
        losses = [w for w in workouts if (w.get("result") or "").lower() == "loss"]
        return {
            "sport": "tennis",
            "total_sessions":   len(workouts),
            "week_sessions":    len(week_w),
            "total_wins":       len(wins),
            "total_losses":     len(losses),
            "win_rate":         round(len(wins) / max(len(workouts), 1) * 100, 1),
            "last_match":       workouts[-1] if workouts else None,
            "targets":          _TARGETS["tennis"],
        }

    # ── Storage ────────────────────────────────────────────────────────

    def _path(self, sport: str) -> Path:
        return self._base / f"{self._user}_{sport}.json"

    def _read(self, sport: str) -> Dict:
        try:
            return json.loads(self._path(sport).read_text(encoding="utf-8"))
        except Exception:
            return {"workouts": []}

    def _write(self, sport: str, data: Dict) -> None:
        self._path(sport).write_text(
            json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8"
        )

    @staticmethod
    def _check_sport(sport: str) -> None:
        if sport not in FitnessEngine.SPORTS:
            raise ValueError(f"Unknown sport '{sport}'. Valid: {FitnessEngine.SPORTS}")
