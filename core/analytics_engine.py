from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional


# ── scoring helpers ──────────────────────────────────────────────────

def _clamp(v: float, lo: float = 0.0, hi: float = 100.0) -> float:
    return max(lo, min(hi, v))

def _trend(values: List[float]) -> str:
    """Return 'improving', 'declining', or 'stable' from a list of values."""
    if len(values) < 2:
        return "stable"
    delta = values[-1] - values[0]
    if abs(delta) < 2:
        return "stable"
    return "improving" if delta < 0 else "declining"  # lower score = better in golf

def _golf_trend(scores: List[float]) -> str:
    if len(scores) < 2:
        return "stable"
    delta = scores[-1] - scores[0]
    if abs(delta) < 1:
        return "stable"
    return "improving" if delta < 0 else "declining"


class AnalyticsEngine:
    """
    Aggregates data from live JARVIS engines to produce
    actionable metrics across productivity, golf, and projects.
    All methods are pure — they accept pre-fetched data dicts
    so the engine is testable without real engines.
    """

    # ── productivity ──────────────────────────────────────────────────

    def productivity_metrics(
        self,
        tasks:    List[Dict],
        meetings: List[Dict],
        events:   List[Dict] | None = None,
    ) -> Dict[str, Any]:
        events = events or []
        now    = datetime.now()
        today  = now.strftime("%Y-%m-%d")

        # Task breakdown
        done_tasks  = [t for t in tasks if t.get("status") == "done" or t.get("done")]
        todo_tasks  = [t for t in tasks if t.get("status") == "todo" and not t.get("done")]
        doing_tasks = [t for t in tasks if t.get("status") == "doing"]
        total_tasks = len(tasks)

        completion_rate = round(len(done_tasks) / total_tasks * 100, 1) if total_tasks else 0.0

        # Overdue tasks (has due_date in the past and not done)
        overdue = [
            t for t in tasks
            if t.get("due_date")
            and t.get("due_date") < today
            and t.get("status") not in ("done",)
            and not t.get("done")
        ]

        # Meeting load today
        today_meetings = [
            m for m in meetings
            if (m.get("day") == "today"
                or m.get("date", "").startswith(today)
                or str(m.get("time", "")).startswith(today[:10]))
        ]

        # Productivity score (0-100)
        score = self._compute_productivity_score(
            total_tasks, len(done_tasks), len(overdue),
            len(today_meetings), len(doing_tasks),
        )

        return {
            "productivity_score":  score,
            "task_total":          total_tasks,
            "task_done":           len(done_tasks),
            "task_todo":           len(todo_tasks),
            "task_doing":          len(doing_tasks),
            "task_overdue":        len(overdue),
            "completion_rate":     completion_rate,
            "meetings_today":      len(today_meetings),
            "calendar_events":     len(events),
            "overdue_titles":      [t.get("text", t.get("title", "?")) for t in overdue[:3]],
            "insights":            self._productivity_insights(
                score, completion_rate, len(overdue), len(today_meetings),
            ),
        }

    def _compute_productivity_score(
        self,
        total: int,
        done:  int,
        overdue: int,
        meetings: int,
        doing: int,
    ) -> int:
        if total == 0:
            return 50  # neutral when no data

        base = (done / total) * 60              # up to 60 pts for completion rate
        in_flight = min(doing / max(total, 1) * 20, 20)  # up to 20 pts for active work
        overdue_penalty = min(overdue * 8, 30)  # -8 pts per overdue, max -30
        meeting_penalty = max(0, (meetings - 4) * 3)     # penalty if > 4 meetings

        score = base + in_flight - overdue_penalty - meeting_penalty + 20  # 20 pt base
        return int(_clamp(score))

    def _productivity_insights(
        self, score: int, completion_rate: float,
        overdue: int, meetings: int,
    ) -> List[str]:
        tips = []
        if overdue > 0:
            tips.append(f"{overdue} overdue task(s) dragging your score down.")
        if completion_rate >= 80:
            tips.append("Strong completion rate — keep the momentum.")
        elif completion_rate < 40 and completion_rate > 0:
            tips.append("Low completion rate. Consider reducing WIP.")
        if meetings > 4:
            tips.append("Heavy meeting load today. Block focus time.")
        if score >= 80:
            tips.append("Excellent productivity today!")
        elif score < 40:
            tips.append("Tough day. Focus on one high-impact task.")
        return tips[:3]

    # ── golf performance ──────────────────────────────────────────────

    def golf_metrics(
        self,
        rounds:    List[Dict],
        bag:       List[Dict] | None = None,
    ) -> Dict[str, Any]:
        bag = bag or []

        if not rounds:
            return {
                "rounds_played":    0,
                "avg_score":        None,
                "best_score":       None,
                "last_score":       None,
                "handicap_estimate": None,
                "trend":            "no data",
                "recent_scores":    [],
                "club_count":       len(bag),
                "insights":         ["No rounds logged yet. Log your first round to start tracking."],
            }

        scores = [r.get("score") or r.get("total_score") for r in rounds if r.get("score") or r.get("total_score")]
        scores = [s for s in scores if isinstance(s, (int, float))]

        avg    = round(sum(scores) / len(scores), 1) if scores else None
        best   = min(scores) if scores else None
        last   = scores[-1] if scores else None
        trend  = _golf_trend(scores[-5:]) if len(scores) >= 2 else "stable"

        # Simple handicap estimate (scratch = 72, basic formula)
        handicap = None
        if avg is not None:
            handicap = round(max(0.0, avg - 72), 1)

        # Performance band
        band = "beginner"
        if avg:
            if avg <= 75:   band = "scratch / low handicap"
            elif avg <= 85: band = "mid handicap"
            elif avg <= 95: band = "high handicap"

        return {
            "rounds_played":    len(rounds),
            "avg_score":        avg,
            "best_score":       best,
            "last_score":       last,
            "handicap_estimate": handicap,
            "performance_band": band,
            "trend":            trend,
            "recent_scores":    scores[-10:],
            "club_count":       len(bag),
            "insights":         self._golf_insights(avg, best, last, trend, len(rounds)),
        }

    def _golf_insights(
        self, avg: Optional[float], best: Optional[float],
        last: Optional[float], trend: str, count: int,
    ) -> List[str]:
        tips = []
        if trend == "improving":
            tips.append("Your scores are trending downward — good improvement!")
        elif trend == "declining":
            tips.append("Scores trending up recently. Review your swing fundamentals.")
        if avg and best and (avg - best) > 10:
            tips.append(f"Gap between avg ({avg}) and best ({best}) suggests consistency issues.")
        if count < 5:
            tips.append("Log more rounds to unlock full trend analysis.")
        if last and avg and last < avg:
            tips.append("Last round was below your average — strong session!")
        return tips[:3]

    # ── project metrics ───────────────────────────────────────────────

    def project_metrics(self, projects: List[Dict]) -> Dict[str, Any]:
        active   = [p for p in projects if p.get("status", "active") == "active"]
        archived = [p for p in projects if p.get("status") == "archived"]

        total_tasks = sum(p.get("task_count", 0) for p in active)
        total_done  = sum(p.get("done_count",  0) for p in active)
        total_todo  = sum(p.get("todo_count",  0) for p in active)
        total_doing = sum(p.get("doing_count", 0) for p in active)

        overall_rate = round(total_done / total_tasks * 100, 1) if total_tasks else 0.0

        stale = [
            p for p in active
            if p.get("task_count", 0) > 0
            and p.get("doing_count", 0) == 0
            and p.get("todo_count", 0) > 0
        ]

        return {
            "active_projects":  len(active),
            "archived_projects": len(archived),
            "total_tasks":      total_tasks,
            "total_done":       total_done,
            "total_todo":       total_todo,
            "total_doing":      total_doing,
            "overall_rate":     overall_rate,
            "stale_projects":   [p.get("name", "?") for p in stale[:3]],
            "project_breakdown": [
                {
                    "id":       p.get("id"),
                    "name":     p.get("name", "?"),
                    "color":    p.get("color", "cyan"),
                    "done":     p.get("done_count", 0),
                    "todo":     p.get("todo_count", 0),
                    "doing":    p.get("doing_count", 0),
                    "total":    p.get("task_count", 0),
                    "rate":     round(
                        p.get("done_count", 0) / p.get("task_count", 1) * 100, 1
                    ) if p.get("task_count", 0) else 0,
                }
                for p in active[:6]
            ],
            "insights": self._project_insights(active, overall_rate, stale),
        }

    def _project_insights(
        self, active: List[Dict], rate: float, stale: List[Dict],
    ) -> List[str]:
        tips = []
        if stale:
            names = ", ".join(p.get("name", "?") for p in stale[:2])
            tips.append(f"Stale projects with no active work: {names}.")
        if rate >= 80:
            tips.append("Project portfolio is mostly complete — time to archive or plan next sprint.")
        elif rate < 20 and active:
            tips.append("Low overall completion. Prioritise ruthlessly.")
        if len(active) > 5:
            tips.append("Managing 5+ projects simultaneously — consider reducing WIP.")
        return tips[:3]

    # ── full summary ──────────────────────────────────────────────────

    def full_summary(
        self,
        tasks:    List[Dict],
        meetings: List[Dict],
        projects: List[Dict],
        rounds:   List[Dict],
        bag:      List[Dict],
        events:   List[Dict] | None = None,
        memory_stats: Dict | None = None,
        notif_unread: int = 0,
    ) -> Dict[str, Any]:
        prod    = self.productivity_metrics(tasks, meetings, events)
        golf    = self.golf_metrics(rounds, bag)
        proj    = self.project_metrics(projects)
        mem     = memory_stats or {}

        # Top-level JARVIS health score (average of available scores)
        jarvis_score = int(_clamp(
            (prod["productivity_score"] * 0.6 + min(golf["rounds_played"] * 5, 40) * 0.4)
        ))

        return {
            "generated_at":         datetime.utcnow().isoformat(),
            "jarvis_health_score":  jarvis_score,
            "productivity":         prod,
            "golf":                 golf,
            "projects":             proj,
            "system": {
                "memory_entries":    mem.get("total", 0),
                "unread_notifications": notif_unread,
                "insights":          mem.get("insights", 0),
            },
        }
