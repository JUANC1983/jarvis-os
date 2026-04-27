from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Optional


def _now_h() -> int:
    return datetime.now().hour


def _today() -> str:
    return datetime.now().strftime("%Y-%m-%d")


def _ins(
    *,
    iid: str,
    domain: str,
    priority: str,
    icon: str,
    title: str,
    body: str,
    action: Optional[str],
    action_label: Optional[str],
) -> Dict:
    return {
        "id":           iid,
        "domain":       domain,
        "priority":     priority,   # critical | high | medium | low
        "icon":         icon,
        "title":        title,
        "body":         body,
        "action":       action,     # tab name or None
        "action_label": action_label,
    }


class WowEngine:
    """
    Cross-domain proactive intelligence layer.
    All methods are pure — they accept pre-fetched context dicts.
    """

    # ── main API ──────────────────────────────────────────────────────

    def generate_insights(self, ctx: Dict[str, Any]) -> List[Dict]:
        insights: List[Dict] = []
        insights.extend(self._productivity_insights(ctx))
        insights.extend(self._golf_insights(ctx))
        insights.extend(self._project_insights(ctx))
        insights.extend(self._time_aware_insights(ctx))
        insights.extend(self._cross_domain_insights(ctx))

        _order = {"critical": 0, "high": 1, "medium": 2, "low": 3}
        insights.sort(key=lambda x: _order.get(x.get("priority", "low"), 3))

        seen: set = set()
        out: List[Dict] = []
        for ins in insights:
            if ins["id"] not in seen:
                seen.add(ins["id"])
                out.append(ins)
            if len(out) >= 8:
                break
        return out

    def generate_briefing(self, ctx: Dict[str, Any]) -> Dict[str, Any]:
        now    = datetime.now()
        hour   = now.hour
        period = "morning" if hour < 12 else "afternoon" if hour < 18 else "evening"

        tasks     = ctx.get("tasks", [])
        meetings  = ctx.get("meetings", [])
        projects  = ctx.get("projects", [])
        rounds    = ctx.get("rounds", [])
        notif_cnt = ctx.get("notif_unread", 0)
        today     = now.strftime("%Y-%m-%d")
        today_fmt = now.strftime("%A, %B %d")

        done_cnt  = sum(1 for t in tasks if t.get("status") == "done" or t.get("done"))
        todo_cnt  = sum(1 for t in tasks if not t.get("done") and t.get("status") != "done")
        overdue_cnt = sum(
            1 for t in tasks
            if t.get("due_date") and t.get("due_date") < today
            and t.get("status") not in ("done",) and not t.get("done")
        )
        today_meetings = [
            m for m in meetings
            if m.get("day") == "today" or m.get("date", "").startswith(today)
        ]
        active_proj = [p for p in projects if p.get("status", "active") == "active"]

        scores = [r.get("score") or r.get("total_score") for r in rounds
                  if r.get("score") or r.get("total_score")]
        scores = [s for s in scores if isinstance(s, (int, float))]
        last_score = scores[-1] if scores else None

        sections = []

        overview_lines = [
            f"{todo_cnt} task{'s' if todo_cnt != 1 else ''} pending"
            + (f", {overdue_cnt} overdue" if overdue_cnt else ""),
            f"{len(today_meetings)} meeting{'s' if len(today_meetings) != 1 else ''} today",
            f"{len(active_proj)} active project{'s' if len(active_proj) != 1 else ''}",
        ]
        sections.append({
            "icon": "📅",
            "title": f"Good {period} — {today_fmt}",
            "lines": overview_lines,
        })

        top_tasks = [t for t in tasks if not t.get("done") and t.get("status") != "done"][:3]
        if top_tasks:
            sections.append({
                "icon": "🎯",
                "title": "Top priorities",
                "lines": [t.get("text") or t.get("title", "?") for t in top_tasks],
            })

        if today_meetings:
            m = today_meetings[0]
            sections.append({
                "icon": "📞",
                "title": "First meeting today",
                "lines": [m.get("title", "?"), m.get("time", "")],
            })

        if last_score is not None:
            sections.append({
                "icon": "⛳",
                "title": "Golf — last round",
                "lines": [f"Score: {last_score}", f"{len(rounds)} round{'s' if len(rounds) != 1 else ''} total"],
            })

        if notif_cnt > 0:
            sections.append({
                "icon": "🔔",
                "title": f"{notif_cnt} unread notification{'s' if notif_cnt != 1 else ''}",
                "lines": ["Check the bell icon for details"],
            })

        return {
            "generated_at":    now.isoformat(),
            "period":          period,
            "date":            today_fmt,
            "sections":        sections,
            "raw": {
                "todo_cnt":        todo_cnt,
                "done_cnt":        done_cnt,
                "overdue_cnt":     overdue_cnt,
                "meetings_today":  len(today_meetings),
                "active_projects": len(active_proj),
                "last_golf_score": last_score,
                "notif_unread":    notif_cnt,
            },
        }

    def smart_suggestions(self, ctx: Dict[str, Any]) -> List[Dict]:
        tasks    = ctx.get("tasks", [])
        rounds   = ctx.get("rounds", [])
        projects = ctx.get("projects", [])
        hour     = _now_h()
        today    = _today()

        suggestions: List[Dict] = []

        overdue = [
            t for t in tasks
            if t.get("due_date") and t.get("due_date") < today
            and not t.get("done") and t.get("status") != "done"
        ]
        if overdue:
            suggestions.append({
                "id": "review_overdue",
                "label": f"Review {len(overdue)} overdue",
                "icon": "⚠️",
                "tab": "productivity",
                "prefill_chat": f"I have {len(overdue)} overdue tasks. Help me prioritize them.",
                "description": "Tackle overdue tasks",
            })

        if hour < 12:
            suggestions.append({
                "id": "plan_day",
                "label": "Plan my day",
                "icon": "☀️",
                "tab": "chat",
                "prefill_chat": "Help me plan my day and set priorities",
                "description": "AI-powered day planning",
            })

        if 12 <= hour < 18:
            suggestions.append({
                "id": "market_check",
                "label": "Market snapshot",
                "icon": "📊",
                "tab": "markets",
                "prefill_chat": None,
                "description": "Check market conditions",
            })

        stale = [
            p for p in projects
            if p.get("status", "active") == "active"
            and p.get("todo_count", 0) > 0
            and p.get("doing_count", 0) == 0
        ]
        if stale:
            suggestions.append({
                "id": "unblock_project",
                "label": f"Unblock {stale[0].get('name', 'project')[:20]}",
                "icon": "🔓",
                "tab": "projects",
                "prefill_chat": f"Help me unblock the '{stale[0].get('name', '')}' project",
                "description": "Get stalled projects moving",
            })

        if len(rounds) < 3:
            suggestions.append({
                "id": "log_golf",
                "label": "Log golf round",
                "icon": "⛳",
                "tab": "golf",
                "prefill_chat": "I want to log a golf round",
                "description": "Track your game",
            })

        if hour >= 18:
            suggestions.append({
                "id": "eod_summary",
                "label": "EOD summary",
                "icon": "🌙",
                "tab": "chat",
                "prefill_chat": "Give me an end-of-day summary of what I accomplished today",
                "description": "Daily recap",
            })

        suggestions.append({
            "id": "weekly_review",
            "label": "Weekly review",
            "icon": "📋",
            "tab": "chat",
            "prefill_chat": "Give me a weekly review across all my projects, tasks, and goals",
            "description": "Big-picture review",
        })

        return suggestions[:6]

    # ── private insight generators ─────────────────────────────────────

    def _productivity_insights(self, ctx: Dict) -> List[Dict]:
        out   = []
        tasks = ctx.get("tasks", [])
        today = _today()

        overdue = [
            t for t in tasks
            if t.get("due_date") and t.get("due_date") < today
            and not t.get("done") and t.get("status") != "done"
        ]
        done  = [t for t in tasks if t.get("done") or t.get("status") == "done"]
        total = len(tasks)

        if overdue:
            priority = "critical" if len(overdue) >= 3 else "high"
            out.append(_ins(
                iid="overdue_tasks", domain="productivity", priority=priority, icon="⚠️",
                title=f"{len(overdue)} overdue task{'s' if len(overdue) > 1 else ''}",
                body=", ".join(t.get("text", t.get("title", "?")) for t in overdue[:2])
                     + ("…" if len(overdue) > 2 else ""),
                action="productivity", action_label="Review tasks",
            ))

        if total > 0 and len(done) / total >= 0.8:
            out.append(_ins(
                iid="high_completion", domain="productivity", priority="medium", icon="✅",
                title="Strong completion rate!",
                body=f"{len(done)}/{total} tasks done.",
                action=None, action_label=None,
            ))

        return out

    def _golf_insights(self, ctx: Dict) -> List[Dict]:
        out    = []
        rounds = ctx.get("rounds", [])
        if not rounds:
            return out

        scores = [r.get("score") or r.get("total_score") for r in rounds]
        scores = [s for s in scores if isinstance(s, (int, float))]
        if not scores:
            return out

        if len(scores) >= 2:
            if scores[-1] < scores[-2]:
                out.append(_ins(
                    iid="golf_improving", domain="golf", priority="low", icon="⛳",
                    title="Golf improving!",
                    body=f"Last round {scores[-1]} vs previous {scores[-2]} — trending down.",
                    action="golf", action_label="View golf",
                ))
            elif scores[-1] > scores[-2] + 5:
                out.append(_ins(
                    iid="golf_rough", domain="golf", priority="low", icon="⛳",
                    title="Tough round recently",
                    body=f"Score up {scores[-1] - scores[-2]} strokes. Review your game.",
                    action="golf", action_label="View golf",
                ))

        if scores and min(scores) == scores[-1]:
            out.append(_ins(
                iid="golf_best", domain="golf", priority="medium", icon="🏆",
                title="Personal best round!",
                body=f"Score of {scores[-1]} is your best recorded.",
                action="golf", action_label="View golf",
            ))

        return out

    def _project_insights(self, ctx: Dict) -> List[Dict]:
        out      = []
        projects = ctx.get("projects", [])
        active   = [p for p in projects if p.get("status", "active") == "active"]
        stale    = [
            p for p in active
            if p.get("todo_count", 0) > 0 and p.get("doing_count", 0) == 0
        ]

        if stale:
            names = ", ".join(p.get("name", "?") for p in stale[:2])
            out.append(_ins(
                iid="stale_projects", domain="projects", priority="medium", icon="🔴",
                title=f"{len(stale)} stalled project{'s' if len(stale) > 1 else ''}",
                body=f"{names} — no active work.",
                action="projects", action_label="View projects",
            ))

        if len(active) > 5:
            out.append(_ins(
                iid="too_many_projects", domain="projects", priority="medium", icon="📦",
                title=f"{len(active)} active projects",
                body="Consider archiving completed or paused projects.",
                action="projects", action_label="View projects",
            ))

        for p in active:
            t = p.get("task_count", 0)
            d = p.get("done_count", 0)
            if t >= 3 and d / t >= 0.9:
                out.append(_ins(
                    iid=f"near_done_{p.get('id', '')}",
                    domain="projects", priority="low", icon="🎉",
                    title=f"'{p.get('name', '?')}' almost done",
                    body=f"{d}/{t} tasks complete — final stretch!",
                    action="projects", action_label="View",
                ))
                break

        return out

    def _time_aware_insights(self, ctx: Dict) -> List[Dict]:
        out   = []
        hour  = _now_h()
        today = _today()
        meetings     = ctx.get("meetings", [])
        today_m      = [m for m in meetings if m.get("day") == "today" or m.get("date", "").startswith(today)]

        if hour < 9 and today_m:
            out.append(_ins(
                iid="morning_meetings", domain="productivity", priority="medium", icon="☀️",
                title=f"{len(today_m)} meeting{'s' if len(today_m) > 1 else ''} ahead today",
                body="Review your agenda before the day kicks off.",
                action="calendar", action_label="View calendar",
            ))

        if hour >= 17:
            tasks = ctx.get("tasks", [])
            todo  = [t for t in tasks if not t.get("done") and t.get("status") != "done"]
            if todo:
                out.append(_ins(
                    iid="eod_reminder", domain="productivity", priority="low", icon="🌙",
                    title=f"End of day — {len(todo)} tasks still open",
                    body="Consider wrapping up or deferring to tomorrow.",
                    action="productivity", action_label="Review tasks",
                ))

        return out

    def _cross_domain_insights(self, ctx: Dict) -> List[Dict]:
        out   = []
        tasks = ctx.get("tasks", [])
        today = _today()
        meetings = ctx.get("meetings", [])

        overdue_cnt = sum(
            1 for t in tasks
            if t.get("due_date") and t.get("due_date") < today
            and not t.get("done") and t.get("status") != "done"
        )
        today_m_cnt = sum(
            1 for m in meetings
            if m.get("day") == "today" or m.get("date", "").startswith(today)
        )

        if overdue_cnt >= 2 and today_m_cnt >= 3:
            out.append(_ins(
                iid="overload_risk", domain="system", priority="high", icon="🚨",
                title="High load detected",
                body=f"{overdue_cnt} overdue tasks + {today_m_cnt} meetings today. Reschedule?",
                action="chat", action_label="Get help",
            ))

        return out
