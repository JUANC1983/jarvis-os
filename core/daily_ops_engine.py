from __future__ import annotations

from datetime import date, datetime
from typing import Any, Dict, List

from core.agent_schema import build_response, degraded


class DailyOpsEngine:
    """
    Daily operational intelligence — session briefings, priority architecture, execution cadence.
    """

    _MORNING = [
        "Review overnight market moves — VIX, futures, any macro catalyst",
        "Confirm your 3 highest-priority tasks for today (not 10 — 3)",
        "10-min clarity exercise: write the single most important question you need to answer today",
        "Check JARVIS agent alerts from overnight",
    ]
    _AFTERNOON = [
        "Mid-day check: are you on your #1 priority task?",
        "Batch reactive work into this window — email, messages, admin",
        "Decision review: any pending choice needs resolution today?",
        "Energy status: if low, switch to low-complexity tasks now",
    ]
    _EVENING = [
        "Mark completed tasks — carry-forward only what truly matters tomorrow",
        "Journal one win and one miss from today",
        "Set tomorrow's top 3 priorities tonight — not in the morning",
        "Review any open positions, pending decisions, or follow-ups needed",
    ]

    _PRINCIPLES: Dict[str, str] = {
        "morning":   "Protect the first 90 minutes — no reactive tasks until your #1 priority is in motion.",
        "afternoon": "Energy is lower now — batch decisions, avoid complex analysis, favour execution.",
        "evening":   "Close open loops tonight. Decisions deferred become tomorrow's drag.",
    }

    def run(self, query: str = "") -> Dict[str, Any]:
        return self.analyze(query)

    def analyze(self, query: str = "") -> Dict[str, Any]:
        try:
            return self._analyze_impl(query)
        except Exception as exc:
            return degraded(f"Daily ops analysis failed: {exc}", confidence=0.25)

    def _analyze_impl(self, query: str = "") -> Dict[str, Any]:
        hour    = datetime.now().hour
        session = "morning" if hour < 12 else ("afternoon" if hour < 17 else "evening")
        checklist = {
            "morning":   self._MORNING,
            "afternoon": self._AFTERNOON,
            "evening":   self._EVENING,
        }[session]

        principle   = self._PRINCIPLES[session]
        exec_insight = self._execution_insight(session)
        top_action  = f"Complete your {session} checklist now. {checklist[0]}"

        return build_response(
            confidence=0.85,
            insight=(
                f"{session.title()} session ({date.today().isoformat()}). "
                f"Principle: {principle} "
                f"Operational focus: {exec_insight[:100]}"
            ),
            risk_level="low",
            action=(
                f"{top_action} "
                f"Then protect 90 uninterrupted minutes for your #1 priority task."
            ),
            reason=(
                f"Session={session} derived from hour={hour}. "
                f"Checklist has {len(checklist)} items. "
                f"Two signals: time-of-day rhythm + cognitive load management."
            ),
            signals_used=[
                f"Session: {session} (hour={hour})",
                f"Date: {date.today().isoformat()}",
                f"Checklist items: {len(checklist)}",
                f"Principle: {principle[:60]}",
            ],
            data_sources=["realtime_clock", "daily_ops_protocol_internal"],
            reasoning_path=[
                f"1. Determine session from current hour: {hour}h → {session}",
                f"2. Load {session} checklist ({len(checklist)} items)",
                f"3. Apply session principle: {principle[:60]}",
                f"4. Top action: {checklist[0][:80]}",
                "5. Protect 90-min deep work block for #1 priority",
            ],
            data_freshness=1.0,
            data_completeness=1.0,
        )

    def run_daily_briefing(self, focus: str = "global macro") -> Dict[str, Any]:
        return {
            "run_at":   datetime.utcnow().isoformat(),
            "focus":    focus,
            "status":   "ready",
            "briefing": self.analyze(focus),
        }

    def _execution_insight(self, session: str) -> str:
        insights = {
            "morning": (
                "The morning window is your highest-cognitive-function period. "
                "Use it for your hardest task — the one you've been avoiding. "
                "Your future self will thank you."
            ),
            "afternoon": (
                "Afternoon is optimal for collaboration, communication, and execution of clear tasks. "
                "Avoid major strategic decisions after 3pm — decision quality degrades."
            ),
            "evening": (
                "Evening is for reflection, not initiation. "
                "Closing open loops tonight frees mental bandwidth for tomorrow's performance. "
                "Write tomorrow's top 3 before you sleep."
            ),
        }
        return insights[session]
