"""Demo Engine — seeds realistic data for a fresh JARVIS user.

Call seed_all() once on first launch. Idempotent: re-running
adds data only if existing counts are below the minimum thresholds.
"""
from __future__ import annotations

from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict
import json
import random


def _today() -> str:
    return datetime.utcnow().strftime("%Y-%m-%d")


def _date(offset_days: int) -> str:
    return (datetime.utcnow() + timedelta(days=offset_days)).strftime("%Y-%m-%d")


# ── Demo content libraries ─────────────────────────────────────────────

_DEMO_TASKS = [
    {"text": "Review Q2 financial report", "priority": "high",   "day": "today",    "category": "finance",     "done": False},
    {"text": "Prepare investor slide deck", "priority": "high",  "day": "today",    "category": "work",        "done": False},
    {"text": "Morning run — 5 km target",  "priority": "medium", "day": "today",    "category": "health",      "done": True},
    {"text": "Call with product team",      "priority": "medium", "day": "tomorrow", "category": "work",        "done": False},
    {"text": "Update portfolio allocation", "priority": "high",  "day": "today",    "category": "finance",     "done": False},
    {"text": "Swing practice session",      "priority": "low",   "day": "tomorrow", "category": "golf",        "done": False},
    {"text": "Read market open briefing",   "priority": "medium","day": "today",    "category": "finance",     "done": True},
]

_DEMO_MEETINGS = [
    {"title": "Market Open Strategy",  "time": "09:00", "notes": "Review overnight positions and key levels"},
    {"title": "Team Standup",          "time": "10:30", "notes": "Sprint progress check"},
    {"title": "Portfolio Review",      "time": "14:00", "notes": "Monthly rebalance discussion"},
]

_DEMO_PROJECTS = [
    {
        "name": "Q2 Strategy Plan",
        "description": "Quarterly business and investment strategy",
        "color": "cyan",
        "tasks": [
            {"title": "Competitive analysis",       "status": "done",    "urgency": "high"},
            {"title": "Revenue projections",        "status": "done",    "urgency": "high"},
            {"title": "Resource allocation plan",   "status": "doing",   "urgency": "medium"},
            {"title": "Presentation to board",      "status": "todo",    "urgency": "high"},
            {"title": "KPI dashboard setup",        "status": "todo",    "urgency": "medium"},
        ],
    },
    {
        "name": "Personal Fitness Goals",
        "description": "Training plan for the next 8 weeks",
        "color": "ok",
        "tasks": [
            {"title": "Set weekly mileage target",  "status": "done",    "urgency": "medium"},
            {"title": "Book golf lesson",            "status": "doing",   "urgency": "low"},
            {"title": "Gym program — Week 1-4",     "status": "todo",    "urgency": "medium"},
            {"title": "Track body metrics",         "status": "todo",    "urgency": "low"},
        ],
    },
]

_DEMO_GOLF_ROUNDS = [
    {"score": 88, "course_name": "Pines Golf Club",   "notes": "Solid ball-striking, 3 putts hurt", "date": _date(-14)},
    {"score": 85, "course_name": "Riverside Links",   "notes": "Best round this month",              "date": _date(-7)},
    {"score": 82, "course_name": "Highland Course",   "notes": "Personal best — driver was on fire",  "date": _date(-2)},
]

_DEMO_GOLF_BAG = {
    "Driver":    {"brand": "TaylorMade", "model": "Stealth 2", "carry_yards": 265, "total_yards": 280, "miss": "right"},
    "3-Wood":    {"brand": "TaylorMade", "model": "Stealth 2", "carry_yards": 230, "total_yards": 245, "miss": "straight"},
    "7-Iron":    {"brand": "Callaway",   "model": "Apex Pro",  "carry_yards": 170, "total_yards": 180, "miss": "left"},
    "PW":        {"brand": "Callaway",   "model": "Jaws MD5",  "carry_yards": 125, "total_yards": 132, "miss": "straight"},
    "Putter":    {"brand": "Scotty Cameron", "model": "Newport", "carry_yards": 0,  "total_yards": 0,  "miss": "straight"},
}

_DEMO_RUNNING = [
    {"distance_km": 5.1,  "duration_min": 28, "pace_min_km": 5.49, "notes": "Easy morning run",  "date": _date(-10)},
    {"distance_km": 8.3,  "duration_min": 44, "pace_min_km": 5.30, "notes": "Tempo effort",      "date": _date(-7)},
    {"distance_km": 12.0, "duration_min": 68, "pace_min_km": 5.67, "notes": "Long run Sunday",   "date": _date(-4)},
    {"distance_km": 5.0,  "duration_min": 26, "pace_min_km": 5.20, "notes": "Fast 5k",           "date": _date(-1)},
]

_DEMO_GYM = [
    {
        "exercises": [
            {"name": "Bench Press",  "sets": 4, "reps": 8,  "weight_kg": 90},
            {"name": "Dumbbell Row", "sets": 3, "reps": 10, "weight_kg": 32},
            {"name": "Shoulder Press","sets":3, "reps": 10, "weight_kg": 60},
        ],
        "muscle_groups": "chest, back, shoulders",
        "notes": "Push-pull day",
        "date": _date(-5),
    },
    {
        "exercises": [
            {"name": "Squat",     "sets": 4, "reps": 6,  "weight_kg": 120},
            {"name": "Deadlift",  "sets": 3, "reps": 5,  "weight_kg": 140},
            {"name": "Leg Press", "sets": 3, "reps": 12, "weight_kg": 180},
        ],
        "muscle_groups": "legs, glutes",
        "notes": "Leg day — PR on squat",
        "date": _date(-2),
    },
]

_DEMO_CALENDAR_EVENTS = [
    {"title": "Market Open Review",   "start": f"{_today()}T09:00:00", "duration_minutes": 30,
     "description": "Check overnight moves, futures, key levels for the day"},
    {"title": "Team Weekly Standup",  "start": f"{_today()}T10:30:00", "duration_minutes": 45,
     "description": "Sprint check-in and blockers"},
    {"title": "Golf Lesson — Coach",  "start": f"{_date(2)}T16:00:00", "duration_minutes": 60,
     "description": "Focus on short game and putting"},
    {"title": "Portfolio Rebalance",  "start": f"{_date(3)}T14:00:00", "duration_minutes": 90,
     "description": "Monthly allocation review with risk adjustment"},
]


# ── Seeding helpers ───────────────────────────────────────────────────

class DemoEngine:
    """Injects demo data into all JARVIS engines for a given user."""

    def __init__(self, uid: str = "owner") -> None:
        self.uid = uid

    def seed_all(self, force: bool = False) -> Dict[str, Any]:
        """Seed all modules. Returns a report of what was seeded."""
        report: Dict[str, Any] = {}
        report["tasks"]    = self._seed_tasks(force)
        report["meetings"] = self._seed_meetings(force)
        report["projects"] = self._seed_projects(force)
        report["golf"]     = self._seed_golf(force)
        report["running"]  = self._seed_running(force)
        report["gym"]      = self._seed_gym(force)
        report["calendar"] = self._seed_calendar(force)
        report["mode"]     = "demo"
        return report

    # ── Tasks ─────────────────────────────────────────────────────────

    def _seed_tasks(self, force: bool) -> str:
        try:
            from core.dashboard_workspace_engine import DashboardWorkspaceEngine
            ws = DashboardWorkspaceEngine()
            data = ws._read()
            existing = data.get("tasks", [])
            if len(existing) >= 3 and not force:
                return f"skipped ({len(existing)} existing)"
            for t in _DEMO_TASKS:
                ws.add_task(t["text"], t["priority"], t["day"], t.get("category", "general"))
            return f"seeded {len(_DEMO_TASKS)}"
        except Exception as e:
            return f"error: {e}"

    # ── Meetings ──────────────────────────────────────────────────────

    def _seed_meetings(self, force: bool) -> str:
        try:
            from core.meetings_engine import MeetingsEngine
            me = MeetingsEngine()
            existing = me.get_meetings()
            if len(existing) >= 2 and not force:
                return f"skipped ({len(existing)} existing)"
            for m in _DEMO_MEETINGS:
                me.add_meeting(m["title"], m["time"], m.get("notes", ""))
            return f"seeded {len(_DEMO_MEETINGS)}"
        except Exception as e:
            return f"error: {e}"

    # ── Projects ──────────────────────────────────────────────────────

    def _seed_projects(self, force: bool) -> str:
        try:
            from core.project_planner_engine import ProjectPlannerEngine
            pl = ProjectPlannerEngine()
            existing = pl.list_projects(user_id=self.uid)
            real = [p for p in existing if not p.get("name", "").startswith("__")]
            if len(real) >= 1 and not force:
                return f"skipped ({len(real)} existing)"
            for proj_def in _DEMO_PROJECTS:
                p = pl.create_project(
                    name=proj_def["name"],
                    description=proj_def["description"],
                    color=proj_def.get("color", "cyan"),
                    user_id=self.uid,
                )
                pid = p["id"]
                for task_def in proj_def["tasks"]:
                    pl.create_task(
                        project_id=pid,
                        title=task_def["title"],
                        status=task_def["status"],
                        urgency=task_def["urgency"],
                        user_id=self.uid,
                    )
            return f"seeded {len(_DEMO_PROJECTS)} projects"
        except Exception as e:
            return f"error: {e}"

    # ── Golf ──────────────────────────────────────────────────────────

    def _seed_golf(self, force: bool) -> str:
        try:
            from core.golf_dashboard_engine import GolfDashboardEngine
            ge = GolfDashboardEngine()
            profile = ge.get_profile()
            rounds = profile.get("rounds", [])
            if len(rounds) >= 2 and not force:
                return f"skipped ({len(rounds)} rounds)"
            for r in _DEMO_GOLF_ROUNDS:
                ge.log_round(r["score"], r["course_name"], r["notes"])
            # Seed bag
            for club, data in _DEMO_GOLF_BAG.items():
                try: ge.upsert_club(club, data)
                except Exception: pass
            return f"seeded {len(_DEMO_GOLF_ROUNDS)} rounds + bag"
        except Exception as e:
            return f"error: {e}"

    # ── Running ───────────────────────────────────────────────────────

    def _seed_running(self, force: bool) -> str:
        try:
            from pathlib import Path
            from core.fitness_engine import FitnessEngine
            base = Path(__file__).resolve().parent.parent / "data" / "fitness" / self.uid
            fe = FitnessEngine(str(base), self.uid)
            hist = fe.get_history("running", limit=5)
            if hist["total"] >= 2 and not force:
                return f"skipped ({hist['total']} existing)"
            for run in _DEMO_RUNNING:
                fe.log_workout("running", run)
            return f"seeded {len(_DEMO_RUNNING)} runs"
        except Exception as e:
            return f"error: {e}"

    # ── Gym ───────────────────────────────────────────────────────────

    def _seed_gym(self, force: bool) -> str:
        try:
            from pathlib import Path
            from core.fitness_engine import FitnessEngine
            base = Path(__file__).resolve().parent.parent / "data" / "fitness" / self.uid
            fe = FitnessEngine(str(base), self.uid)
            hist = fe.get_history("gym", limit=5)
            if hist["total"] >= 1 and not force:
                return f"skipped ({hist['total']} existing)"
            for session in _DEMO_GYM:
                fe.log_workout("gym", session)
            return f"seeded {len(_DEMO_GYM)} sessions"
        except Exception as e:
            return f"error: {e}"

    # ── Calendar ──────────────────────────────────────────────────────

    def _seed_calendar(self, force: bool) -> str:
        try:
            from core.calendar_engine import CalendarEngine
            cal_path = Path(__file__).resolve().parent.parent / "data" / f"calendar_{self.uid}.json"
            ce = CalendarEngine(str(cal_path))
            existing = ce.list_events()
            if len(existing) >= 2 and not force:
                return f"skipped ({len(existing)} existing)"
            for ev in _DEMO_CALENDAR_EVENTS:
                ce.create_event(
                    title=ev["title"],
                    start=ev["start"],
                    duration_minutes=ev.get("duration_minutes", 60),
                    description=ev.get("description", ""),
                    participants=[],
                    reminder_minutes=15,
                )
            return f"seeded {len(_DEMO_CALENDAR_EVENTS)} events"
        except Exception as e:
            return f"error: {e}"
