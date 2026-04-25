from __future__ import annotations

from datetime import date, datetime
from typing import Any, Dict, List


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
        hour    = datetime.now().hour
        session = "morning" if hour < 12 else ("afternoon" if hour < 17 else "evening")
        checklist = {
            "morning":   self._MORNING,
            "afternoon": self._AFTERNOON,
            "evening":   self._EVENING,
        }[session]

        return {
            "query":   query or f"Daily ops briefing — {session}",
            "session": session,
            "date":    date.today().isoformat(),
            "focus_principle":   self._PRINCIPLES[session],
            "checklist":         checklist,
            "execution_insight": self._execution_insight(session),
            "recommendations": {
                "short_term": [
                    f"Complete your {session} checklist in the next 15 minutes",
                    "Identify your single most important task and protect 90 uninterrupted minutes for it",
                    "If your energy is low right now: walk outside 10 min before starting",
                ],
                "mid_term": [
                    "Review your weekly targets every Monday — 3 big rocks maximum",
                    "Batch reactive work (messages, email) into 2 scheduled windows per day",
                    "Weekly review Friday PM: what worked, what didn't, what shifts next week",
                ],
                "long_term": [
                    "Systems over willpower — automate routine decisions so cognitive load goes to high-leverage work",
                    "4 focused hours outperform 8 distracted hours every time",
                    "Build a daily shutdown ritual — signals to brain that work is done",
                ],
            },
            "risk_assessment": {
                "level": "low",
                "note": "Decision fatigue is real — operational rhythm protects against it",
                "warning": "Skipping evening review means tomorrow starts with yesterday's open loops",
            },
            "confidence":       0.85,
            "decision_clarity": "high",
            "source":           "daily_ops",
            "generated_at":     datetime.utcnow().isoformat(),
        }

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
