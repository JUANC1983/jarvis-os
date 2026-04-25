from __future__ import annotations

import re
from typing import Any, Dict, List


class FitnessPerformanceEngine:

    def analyze(self, query: str) -> Dict[str, Any]:
        """
        Primary entry point — compatible with AgentOrchestratorPro._try_methods().
        Derives focus from the query and builds a structured fitness response.
        """
        text  = (query or "").lower()
        focus = self._detect_focus(text)

        # Attempt to extract body weight from the query for nutrition
        weight = self._extract_weight(text)
        plan      = self.microcycle()
        nutrition = self.nutrition(weight)

        recommendations: List[str] = [
            f"Weekly microcycle: {', '.join(plan.get('plan', []))}",
            f"Daily protein target: {nutrition.get('protein_target', 0):.0f} g "
            f"(based on {weight} kg body weight)",
            "Prioritise 7–9 hours of sleep — it drives 80% of muscle adaptation",
            "Track performance weekly and adjust volume by ±10% based on recovery",
        ]

        if focus == "strength":
            recommendations.insert(0, "Focus: progressive overload — increase weight or reps each session")
        elif focus == "cardio":
            recommendations.insert(0, "Focus: Zone 2 cardio 3×/week + one interval session")
        elif focus == "mobility":
            recommendations.insert(0, "Focus: daily 15-min mobility work, prioritise hip flexors and thoracic spine")
        elif focus == "weight_loss":
            recommendations.insert(0, "Focus: caloric deficit 300–500 kcal/day + 3 strength sessions/week")

        return {
            "query":        query,
            "focus":        focus,
            "weekly_plan":  plan.get("plan", []),
            "nutrition":    nutrition,
            "recommendations": recommendations,
            "source":       "fitness_performance",
        }

    # ------------------------------------------------------------------ #
    # Private helpers                                                      #
    # ------------------------------------------------------------------ #
    def _detect_focus(self, text: str) -> str:
        if any(w in text for w in [
            "fuerza", "strength", "músculo", "muscle", "ganar masa", "bulk",
            "pesas", "weights", "hipertrofia", "hypertrophy",
        ]):
            return "strength"
        if any(w in text for w in [
            "cardio", "resistencia", "endurance", "correr", "run",
            "ciclismo", "cycling", "aeróbico", "aerobic",
        ]):
            return "cardio"
        if any(w in text for w in [
            "movilidad", "mobility", "flexibilidad", "flexibility",
            "yoga", "stretch", "postura", "posture",
        ]):
            return "mobility"
        if any(w in text for w in [
            "perder peso", "lose weight", "bajar de peso", "adelgazar",
            "quemar grasa", "fat loss", "deficit",
        ]):
            return "weight_loss"
        return "general"

    def _extract_weight(self, text: str) -> float:
        match = re.search(r'\b(\d{2,3})\s*(?:kg|kilos?|libras?|lbs?)?\b', text)
        if match:
            val = float(match.group(1))
            if 30 <= val <= 250:   # sanity range in kg
                return val
        return 75.0  # sensible default

    # ------------------------------------------------------------------ #
    # Original methods — untouched                                         #
    # ------------------------------------------------------------------ #
    def microcycle(self) -> Dict[str, Any]:
        return {
            "plan": [
                "strength training",
                "mobility",
                "cardio zone2",
                "recovery",
            ]
        }

    def nutrition(self, weight: float) -> Dict[str, Any]:
        protein = weight * 1.8
        return {
            "protein_target": protein,
            "note": "adjust calories depending goal",
        }
