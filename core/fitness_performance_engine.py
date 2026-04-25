from __future__ import annotations

import re
from datetime import datetime
from typing import Any, Dict, List


class FitnessPerformanceEngine:
    """
    Elite performance and body optimization engine.
    Periodized programming, evidence-based nutrition, recovery science.
    """

    _MODELS: Dict[str, Dict[str, Any]] = {
        "strength": {
            "description": "Maximal force production — progressive overload at 80–90% 1RM",
            "frequency":   "4×/week",
            "split":       "Upper A / Lower A / Upper B / Lower B",
            "rep_range":   "3–6 reps, 80–90% 1RM",
            "overload":    "2.5kg/session upper body, 5kg/session lower body (linear periodization)",
            "protein_multiplier": 2.0,
        },
        "hypertrophy": {
            "description": "Maximum muscle growth — volume emphasis at 60–75% 1RM",
            "frequency":   "4–5×/week",
            "split":       "Push / Pull / Legs / Push / Pull",
            "rep_range":   "8–15 reps, 3–5 sets, ~2 RIR",
            "overload":    "Double progression: reps then weight",
            "protein_multiplier": 1.9,
        },
        "cardio": {
            "description": "VO2max and aerobic base development",
            "frequency":   "5×/week",
            "split":       "3× Zone2 + 1× HIIT + 1× Long aerobic",
            "rep_range":   "N/A",
            "overload":    "Volume before intensity — add 10% volume per week max",
            "protein_multiplier": 1.6,
        },
        "weight_loss": {
            "description": "Body composition shift — deficit + muscle preservation",
            "frequency":   "4×/week",
            "split":       "3× Full body strength + 1× HIIT",
            "rep_range":   "10–15 reps, metabolic emphasis",
            "overload":    "Caloric deficit 300–500 kcal/day — diet does the heavy lifting",
            "protein_multiplier": 1.8,
        },
        "mobility": {
            "description": "Range of motion and tissue quality — daily practice",
            "frequency":   "Daily",
            "split":       "Full-body 20min + targeted area work",
            "rep_range":   "N/A",
            "overload":    "ROM + tissue quality progression",
            "protein_multiplier": 1.4,
        },
        "general": {
            "description": "Well-rounded performance foundation",
            "frequency":   "3–4×/week",
            "split":       "Full body 2× + Cardio 2×",
            "rep_range":   "8–12 reps",
            "overload":    "Progressive volume",
            "protein_multiplier": 1.7,
        },
    }

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def analyze(self, query: str) -> Dict[str, Any]:
        text   = (query or "").lower()
        focus  = self._detect_focus(text)
        weight = self._extract_weight(text)
        model  = self._MODELS[focus]
        plan   = self._build_microcycle(focus)
        nutr   = self._build_nutrition(weight, focus)
        rec    = self._recovery_protocol(focus)

        return {
            "query":          query,
            "focus":          focus,
            "training_model": model,
            "weekly_plan":    plan,
            "nutrition":      nutr,
            "recovery":       rec,
            "recommendations": {
                "short_term": self._short_term(focus, weight),
                "mid_term":   self._mid_term(focus),
                "long_term":  self._long_term(focus),
            },
            "risk_assessment": {
                "level": "low",
                "overtraining_signals": [
                    "HRV drop >10% sustained 3+ consecutive days",
                    "Persistent fatigue not resolved by full rest day",
                    "Performance declining despite consistent effort",
                ],
                "injury_prevention": [
                    "10-min structured warm-up before every session — non-negotiable",
                    "Deload week every 4–6 weeks: reduce volume 40%, maintain intensity",
                    "Never train through sharp joint pain — dull muscle soreness is fine",
                ],
            },
            "confidence":       0.86,
            "decision_clarity": "high",
            "source":           "fitness_performance",
            "generated_at":     datetime.utcnow().isoformat(),
        }

    # Backward compatibility
    def microcycle(self) -> Dict[str, Any]:
        return {
            "plan": [d["session"] for d in self._build_microcycle("general")[:4]]
        }

    def nutrition(self, weight: float) -> Dict[str, Any]:
        return {
            "protein_target": round(weight * 1.8, 0),
            "note":           "adjust calories depending goal",
        }

    # ------------------------------------------------------------------
    # Private
    # ------------------------------------------------------------------

    def _detect_focus(self, text: str) -> str:
        if any(w in text for w in [
            "fuerza", "strength", "1rm", "powerlifting", "fuerza maxima",
        ]):
            return "strength"
        if any(w in text for w in [
            "músculo", "muscle", "ganar masa", "bulk", "hipertrofia", "hypertrophy", "pesas", "weights",
        ]):
            return "hypertrophy"
        if any(w in text for w in [
            "cardio", "resistencia", "endurance", "correr", "run",
            "ciclismo", "cycling", "aeróbico", "aerobic", "vo2",
        ]):
            return "cardio"
        if any(w in text for w in [
            "movilidad", "mobility", "flexibilidad", "flexibility",
            "yoga", "stretch", "postura", "posture",
        ]):
            return "mobility"
        if any(w in text for w in [
            "perder peso", "lose weight", "bajar de peso", "adelgazar",
            "quemar grasa", "fat loss", "deficit", "bajar grasa", "grasa",
        ]):
            return "weight_loss"
        return "general"

    def _extract_weight(self, text: str) -> float:
        m = re.search(r'\b(\d{2,3})\s*(?:kg|kilos?|libras?|lbs?)?\b', text)
        if m:
            val = float(m.group(1))
            if 30 <= val <= 250:
                return val
        return 75.0

    def _build_microcycle(self, focus: str) -> List[Dict[str, Any]]:
        plans = {
            "strength": [
                {"day": "Mon", "session": "Lower A — Squat focus",        "detail": "Squat 5×3-5, Romanian DL 4×5, leg press 3×8",           "intensity": "High"},
                {"day": "Tue", "session": "Upper A — Press focus",        "detail": "Bench 5×3-5, OHP 4×5, weighted dip 3×6",                "intensity": "High"},
                {"day": "Wed", "session": "Active recovery",              "detail": "20min mobility work, light walk",                         "intensity": "Low"},
                {"day": "Thu", "session": "Lower B — Hinge focus",        "detail": "Deadlift 4×3-5, RDL 3×6, lunges 3×8 each",              "intensity": "High"},
                {"day": "Fri", "session": "Upper B — Pull focus",         "detail": "Barbell row 5×5, weighted pull-up 4×5, face pull 3×15", "intensity": "High"},
                {"day": "Sat", "session": "Optional — Zone2 / accessory", "detail": "30–40min Zone2 + weak-point work",                       "intensity": "Low"},
                {"day": "Sun", "session": "Rest",                         "detail": "Full rest — recovery IS training",                        "intensity": "None"},
            ],
            "weight_loss": [
                {"day": "Mon", "session": "Full body strength A",  "detail": "Compound 4×10-12: squat, bench, row",               "intensity": "Medium"},
                {"day": "Tue", "session": "Zone2 cardio",          "detail": "40min at 65–70% HRmax — conversational pace",        "intensity": "Medium"},
                {"day": "Wed", "session": "HIIT",                  "detail": "20min: 40s all-out / 20s rest × 20 rounds",          "intensity": "High"},
                {"day": "Thu", "session": "Full body strength B",  "detail": "Compound 4×10-12: DL, OHP, pull-up",                "intensity": "Medium"},
                {"day": "Fri", "session": "Zone2 cardio",          "detail": "45min — slightly longer, flat intensity",            "intensity": "Medium"},
                {"day": "Sat", "session": "Active lifestyle",      "detail": "Walk, swim, sport — move 60+ min, enjoy it",         "intensity": "Low"},
                {"day": "Sun", "session": "Rest",                  "detail": "Full rest",                                         "intensity": "None"},
            ],
            "general": [
                {"day": "Mon", "session": "Full body A",       "detail": "Squat, bench, row — 3×10-12",             "intensity": "Medium"},
                {"day": "Tue", "session": "Zone2 cardio",      "detail": "30–40min conversational pace",             "intensity": "Low-Medium"},
                {"day": "Wed", "session": "Mobility + rest",   "detail": "20min full-body mobility",                 "intensity": "Low"},
                {"day": "Thu", "session": "Full body B",       "detail": "DL, OHP, pull-up/row — 3×10-12",          "intensity": "Medium"},
                {"day": "Fri", "session": "Cardio or sport",   "detail": "30–45min — any activity you enjoy",        "intensity": "Medium"},
                {"day": "Sat", "session": "Active recovery",   "detail": "Walk, light hike, golf",                   "intensity": "Low"},
                {"day": "Sun", "session": "Rest",              "detail": "Full rest",                                "intensity": "None"},
            ],
        }
        return plans.get(focus, plans["general"])

    def _build_nutrition(self, weight: float, focus: str) -> Dict[str, Any]:
        mult = self._MODELS[focus]["protein_multiplier"]
        protein_g = round(weight * mult, 0)

        calorie_delta = {
            "strength":    200,
            "hypertrophy": 250,
            "cardio":      100,
            "weight_loss": -400,
            "mobility":    0,
            "general":     100,
        }.get(focus, 100)

        tdee = round(weight * 33 + calorie_delta, 0)
        carbs_g = round(weight * (2.5 if focus == "cardio" else 2.0), 0)
        fat_g   = round(tdee * 0.25 / 9, 0)

        return {
            "protein_target_g":  protein_g,
            "estimated_calories": tdee,
            "carbs_g":           carbs_g,
            "fat_g":             fat_g,
            "meal_timing": {
                "pre_workout":     "Carbs + protein 90min before training",
                "post_workout":    f"{round(protein_g/4, 0)}g protein + 50g carbs within 45min",
                "daily_pattern":   "4–5 meals, protein at every meal, no meal skipping",
            },
            "priority_supplements": [
                "Creatine monohydrate 5g/day — most-studied ergogenic, safe long-term",
                "Vitamin D3 4000IU/day if sun-deprived",
                "Magnesium glycinate 400mg before bed — sleep quality and recovery",
            ],
            "note": "Adjust calories ±200/week based on weekly body weight trend over 7-day rolling average",
        }

    def _recovery_protocol(self, focus: str) -> Dict[str, Any]:
        return {
            "sleep":          "7–9h per night — 80% of muscle protein synthesis occurs in slow-wave sleep",
            "hrv_monitoring": "Track morning HRV: drop >10% sustained = reduce intensity that day",
            "deload_protocol": "Every 4–6 weeks: cut volume 40%, maintain intensity — prevents plateau and injury",
            "active_recovery": "Light activity (walking, swimming) on rest days improves next-session performance",
            "nutrition_window": "Post-workout nutrition within 45min maximizes mTOR activation",
            "stress_note":     "Psychological stress impairs recovery as much as overtraining — manage both",
        }

    def _short_term(self, focus: str, weight: float) -> List[str]:
        protein = round(weight * self._MODELS[focus]["protein_multiplier"], 0)
        base = [
            f"Track three things weekly: body weight, key lift numbers, energy level 1–10",
            f"Hit {protein}g protein/day — this is the single most impactful variable",
            "Prioritize 7–9h sleep — zero other intervention compensates for this",
        ]
        if focus == "weight_loss":
            base.insert(0, "Create deficit through diet (300–500 kcal) NOT excessive cardio alone")
        elif focus in ("strength", "hypertrophy"):
            base.insert(0, "Start creatine 5g/day today — takes 14 days for full saturation")
        return base

    def _mid_term(self, focus: str) -> List[str]:
        return [
            "Reassess programming at 6 weeks — if not progressing, problem is sleep, nutrition, or volume",
            "Progressive overload: if all reps completed with good form → increase weight next session",
            "Add 15min mobility work if not already — injury prevention compounds over months",
            "DEXA scan at 12 weeks for accurate body composition data (not just scale weight)",
        ]

    def _long_term(self, focus: str) -> List[str]:
        return [
            "Build the habit infrastructure: same time, same gym, same sequence — decision fatigue kills consistency",
            "VO2max improvement: single strongest longevity biomarker — invest in it now",
            "Muscle mass after 40 becomes the primary longevity variable — build it, never stop",
            "Annual fitness test: VO2max, grip strength, squat 1RM — track your trajectory, not others'",
        ]
