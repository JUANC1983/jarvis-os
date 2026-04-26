from __future__ import annotations

"""
AI Orchestrator — Phase 5F Brain Layer

Flow: User Input → classify_intent() → inject_memory() → dispatch_agent() → Response

Agents:
  productivity_agent  — tasks, meetings, calendar, daily planning
  golf_agent          — swing, courses, bag, performance, coaching
  project_agent       — projects, kanban, tasks, deadlines
  system_agent        — JARVIS status, notifications, memory, settings
  general_agent       — cross-domain & fallback

This orchestrator is intentionally separate from AgentOrchestratorPro
(which handles trading pipeline). It wraps JARVIS personal-productivity
intelligence with memory context injection.
"""

import re
from datetime import datetime
from typing import Any, Dict, List, Optional

# ── intent classification ────────────────────────────────────────────
_DOMAIN_KEYWORDS: Dict[str, List[str]] = {
    "productivity": [
        "task", "tasks", "todo", "todos", "meeting", "meetings", "calendar",
        "schedule", "agenda", "reminder", "reminders", "deadline", "deadlines",
        "daily", "week", "plan", "tarea", "tareas", "reunión", "reuniones",
        "cita", "productivity", "organize", "organizar", "hoy",
    ],
    "golf": [
        "golf", "swing", "course", "caddie", "birdie", "par", "eagle",
        "handicap", "club", "driver", "iron", "wedge", "putt", "green",
        "fairway", "round", "stroke", "scorecard", "grip", "stance",
        "backswing", "downswing", "hip", "shoulder", "tempo", "plane",
        "bag", "shot", "distance", "yardage", "rangefinder",
    ],
    "project": [
        "project", "projects", "kanban", "sprint", "milestone", "epic",
        "ticket", "board", "backlog", "feature", "bug", "release",
        "deploy", "roadmap", "delivery", "scope", "story", "velocity",
        "proyecto", "proyectos", "tarea de proyecto",
    ],
    "system": [
        "system", "status", "health", "memory", "notification", "notifications",
        "settings", "config", "jarvis", "agent", "agents", "integration",
        "pipeline", "performance", "cpu", "ram", "disk", "log", "error",
        "uptime", "unread", "sistema", "configuración", "notificaciones",
    ],
}

_DOMAIN_WEIGHT: Dict[str, int] = {
    "productivity": 0, "golf": 0, "project": 0, "system": 0,
}

_AGENT_NAMES = {
    "productivity": "productivity_agent",
    "golf":         "golf_agent",
    "project":      "project_agent",
    "system":       "system_agent",
    "general":      "general_agent",
}

_AGENT_DESCRIPTIONS = {
    "productivity_agent": "Tasks, meetings, calendar, daily planning",
    "golf_agent":         "Golf performance, swing, courses, bag",
    "project_agent":      "Projects, kanban, sprints, roadmaps",
    "system_agent":       "JARVIS status, memory, notifications, config",
    "general_agent":      "Cross-domain reasoning and fallback",
}


def classify_intent(message: str) -> str:
    """
    Keyword-based domain classifier.
    Returns one of: productivity | golf | project | system | general
    Ties broken by order of importance.
    """
    msg = message.lower()
    scores: Dict[str, int] = {d: 0 for d in _DOMAIN_KEYWORDS}
    for domain, keywords in _DOMAIN_KEYWORDS.items():
        for kw in keywords:
            # word-boundary match to avoid partial hits
            if re.search(rf"\b{re.escape(kw)}\b", msg):
                scores[domain] += 1

    best = max(scores, key=lambda d: scores[d])
    if scores[best] == 0:
        return "general"
    # require at least 1 clear signal
    return best


# ── agent handlers ───────────────────────────────────────────────────

def _handle_productivity(message: str, context: Dict[str, Any]) -> Dict[str, Any]:
    mem_ctx   = context.get("memory_context", [])
    tasks     = context.get("tasks", [])
    meetings  = context.get("meetings", [])
    events    = context.get("calendar_events", [])

    todo_count  = sum(1 for t in tasks if t.get("status") == "todo")
    doing_count = sum(1 for t in tasks if t.get("status") == "doing")
    done_count  = sum(1 for t in tasks if t.get("status") == "done")
    mtg_count   = len(meetings)
    ev_count    = len(events)

    summary_lines = []
    if tasks:
        summary_lines.append(
            f"Task board: {todo_count} todo, {doing_count} in-progress, {done_count} done."
        )
    if meetings:
        next_mtg = meetings[0].get("title", "") if meetings else ""
        summary_lines.append(f"{mtg_count} meeting(s) today" + (f" — next: {next_mtg}" if next_mtg else "."))
    if events:
        next_ev = events[0].get("title", "") if events else ""
        summary_lines.append(f"{ev_count} calendar event(s)" + (f" — next: {next_ev}" if next_ev else "."))

    response = " ".join(summary_lines) if summary_lines else (
        "Your productivity workspace is empty. Want me to help you plan your day?"
    )

    # Coaching tip from memory
    mem_tip = ""
    high_imp = [e for e in mem_ctx if e.get("importance", 0) >= 7 and e.get("type") == "decision"]
    if high_imp:
        mem_tip = f" Recall: {high_imp[0]['content'][:120]}"

    return {
        "agent":    "productivity_agent",
        "domain":   "productivity",
        "response": response + mem_tip,
        "data": {
            "task_summary": {"todo": todo_count, "doing": doing_count, "done": done_count},
            "meeting_count": mtg_count,
            "event_count":   ev_count,
        },
        "suggestions": _productivity_suggestions(tasks, meetings),
    }


def _productivity_suggestions(tasks: List[Dict], meetings: List[Dict]) -> List[str]:
    tips = []
    overdue_cnt = sum(
        1 for t in tasks
        if t.get("due_date") and t.get("status") != "done"
        and t.get("due_date") < datetime.now().strftime("%Y-%m-%d")
    )
    if overdue_cnt:
        tips.append(f"You have {overdue_cnt} overdue task(s). Want me to reschedule them?")
    if len(meetings) > 3:
        tips.append("Heavy meeting day. Consider blocking focus time.")
    doing = [t for t in tasks if t.get("status") == "doing"]
    if len(doing) > 3:
        tips.append("Too many tasks in-progress. Focus on finishing before starting new ones.")
    return tips[:3]


def _handle_golf(message: str, context: Dict[str, Any]) -> Dict[str, Any]:
    bag     = context.get("golf_bag", {})
    rounds  = context.get("golf_rounds", [])
    mem_ctx = context.get("memory_context", [])

    clubs     = bag.get("clubs", []) if isinstance(bag, dict) else []
    round_cnt = len(rounds)
    avg_score = None
    if rounds:
        scores = [r.get("score") for r in rounds if r.get("score")]
        if scores:
            avg_score = round(sum(scores) / len(scores), 1)

    lines = []
    if clubs:
        lines.append(f"Bag has {len(clubs)} club(s).")
    if round_cnt:
        lines.append(f"{round_cnt} round(s) logged.")
        if avg_score:
            lines.append(f"Average score: {avg_score}.")
    if not lines:
        lines.append("No golf data yet. Upload your bag or log a round to get started.")

    mem_tip = ""
    golf_mem = [e for e in mem_ctx if "golf" in " ".join(e.get("tags", [])).lower()]
    if golf_mem:
        mem_tip = f" Previous insight: {golf_mem[0]['content'][:100]}"

    return {
        "agent":    "golf_agent",
        "domain":   "golf",
        "response": " ".join(lines) + mem_tip,
        "data": {
            "club_count":   len(clubs),
            "round_count":  round_cnt,
            "avg_score":    avg_score,
        },
        "suggestions": _golf_suggestions(bag, rounds),
    }


def _golf_suggestions(bag: Dict, rounds: List[Dict]) -> List[str]:
    tips = []
    if not bag or not bag.get("clubs"):
        tips.append("Add your bag to get personalised club recommendations.")
    if not rounds:
        tips.append("Log your first round to start tracking performance trends.")
    elif len(rounds) >= 3:
        recent = rounds[-3:]
        scores = [r.get("score", 0) for r in recent if r.get("score")]
        if scores and scores[-1] > scores[0]:
            tips.append("Scores trending up recently. Review your recent rounds for patterns.")
    return tips[:3]


def _handle_project(message: str, context: Dict[str, Any]) -> Dict[str, Any]:
    projects = context.get("projects", [])
    mem_ctx  = context.get("memory_context", [])

    active    = [p for p in projects if p.get("status") == "active"]
    total_todo  = sum(p.get("todo_count", 0)  for p in active)
    total_doing = sum(p.get("doing_count", 0) for p in active)
    total_done  = sum(p.get("done_count", 0)  for p in active)

    if not active:
        response = "No active projects. Create one in the Projects tab."
    else:
        proj_names = ", ".join(p.get("name", "?") for p in active[:3])
        response = (
            f"{len(active)} active project(s): {proj_names}. "
            f"Combined: {total_todo} todo, {total_doing} in-progress, {total_done} done."
        )

    mem_tip = ""
    proj_mem = [e for e in mem_ctx if e.get("type") == "decision" and e.get("importance", 0) >= 6]
    if proj_mem:
        mem_tip = f" Decision context: {proj_mem[0]['content'][:100]}"

    return {
        "agent":    "project_agent",
        "domain":   "project",
        "response": response + mem_tip,
        "data": {
            "active_projects": len(active),
            "total_todo":      total_todo,
            "total_doing":     total_doing,
            "total_done":      total_done,
        },
        "suggestions": _project_suggestions(active),
    }


def _project_suggestions(projects: List[Dict]) -> List[str]:
    tips = []
    for p in projects[:3]:
        if p.get("doing_count", 0) == 0 and p.get("todo_count", 0) > 0:
            tips.append(f"'{p.get('name')}' has tasks waiting. Ready to start one?")
        elif p.get("todo_count", 0) == 0 and p.get("done_count", 0) > 0:
            tips.append(f"'{p.get('name')}' looks nearly complete!")
    return tips[:3]


def _handle_system(message: str, context: Dict[str, Any]) -> Dict[str, Any]:
    mem_stats   = context.get("memory_stats", {})
    notif_count = context.get("unread_notifications", 0)
    sys_meta    = context.get("system_meta", {})

    lines = [f"JARVIS is online. {datetime.now().strftime('%Y-%m-%d %H:%M')}."]
    if notif_count:
        lines.append(f"{notif_count} unread notification(s).")
    if mem_stats.get("total"):
        lines.append(f"Memory: {mem_stats['total']} entries, avg importance {mem_stats.get('avg_importance', 0)}.")
    if sys_meta:
        lines.append(f"System: {sys_meta.get('summary', '')}")

    return {
        "agent":    "system_agent",
        "domain":   "system",
        "response": " ".join(lines),
        "data": {
            "memory_entries":        mem_stats.get("total", 0),
            "unread_notifications":  notif_count,
        },
        "suggestions": [],
    }


def _handle_general(message: str, context: Dict[str, Any]) -> Dict[str, Any]:
    mem_ctx = context.get("memory_context", [])
    lines   = ["I'm JARVIS, your AI operating system."]

    if mem_ctx:
        top = mem_ctx[0]
        lines.append(f"Recent context: {top['content'][:120]}")

    lines.append("I can help with productivity, golf, projects, and system management. What do you need?")

    return {
        "agent":    "general_agent",
        "domain":   "general",
        "response": " ".join(lines),
        "data":     {},
        "suggestions": [
            "Show me today's tasks",
            "What projects am I working on?",
            "How is my golf game progressing?",
        ],
    }


# ── main orchestrator class ──────────────────────────────────────────

_AGENT_HANDLERS = {
    "productivity": _handle_productivity,
    "golf":         _handle_golf,
    "project":      _handle_project,
    "system":       _handle_system,
    "general":      _handle_general,
}


class AIOrchestrator:
    """
    Central routing layer for JARVIS personal intelligence.
    Injects Phase 5D memory context before dispatching to each agent.
    """

    def __init__(self) -> None:
        self._request_log: List[Dict[str, Any]] = []   # in-memory audit log

    # ── public API ───────────────────────────────────────────────────

    def route(self, message: str, context: Dict[str, Any]) -> Dict[str, Any]:
        """
        Main entry point.

        Args:
            message: Raw user text
            context: Pre-fetched data dict (memory, tasks, projects, etc.)
                     Built by the caller so the orchestrator stays pure/testable.

        Returns:
            Structured response dict with agent, domain, response, data, suggestions.
        """
        domain  = classify_intent(message)
        handler = _AGENT_HANDLERS.get(domain, _handle_general)

        result = handler(message, context)

        # Audit log (last 50)
        self._request_log.append({
            "ts":      datetime.utcnow().isoformat(),
            "message": message[:120],
            "domain":  domain,
            "agent":   result.get("agent"),
        })
        if len(self._request_log) > 50:
            self._request_log = self._request_log[-50:]

        result["classified_domain"] = domain
        result["timestamp"]         = datetime.utcnow().isoformat()
        return result

    def classify(self, message: str) -> Dict[str, Any]:
        """Classify only — no dispatch. Useful for UI routing."""
        domain = classify_intent(message)
        return {
            "domain":     domain,
            "agent":      _AGENT_NAMES[domain],
            "confidence": "keyword",
            "description": _AGENT_DESCRIPTIONS[_AGENT_NAMES[domain]],
        }

    def health(self) -> Dict[str, Any]:
        return {
            "status":          "ok",
            "agents":          list(_AGENT_NAMES.values()),
            "agent_descriptions": _AGENT_DESCRIPTIONS,
            "total_requests":  len(self._request_log),
            "last_request":    self._request_log[-1] if self._request_log else None,
        }

    def audit_log(self, limit: int = 20) -> List[Dict[str, Any]]:
        return self._request_log[-limit:]
