from __future__ import annotations

import json
from collections import Counter
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List


class CognitiveSelfImprovementEngine:
    """
    Logs decisions, outcomes, and feedback.
    Produces simple pattern analysis and upgrade suggestions for JARVIS.
    """

    def __init__(self, file_path: str = "data/learning/cognitive_feedback.jsonl") -> None:
        self.file_path = Path(file_path)
        self.file_path.parent.mkdir(parents=True, exist_ok=True)
        if not self.file_path.exists():
            self.file_path.write_text("", encoding="utf-8")

    def log_case(
        self,
        category: str,
        prompt: str,
        recommendation: str,
        outcome: str = "",
        score: float = 0.0,
        notes: str = "",
        metadata: Dict[str, Any] | None = None,
    ) -> Dict[str, Any]:
        record = {
            "timestamp": datetime.utcnow().isoformat(),
            "category": category,
            "prompt": prompt,
            "recommendation": recommendation,
            "outcome": outcome,
            "score": float(score),
            "notes": notes,
            "metadata": metadata or {},
        }

        with self.file_path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(record, ensure_ascii=False) + "\n")

        return record

    def _load(self) -> List[Dict[str, Any]]:
        rows: List[Dict[str, Any]] = []
        if not self.file_path.exists():
            return rows

        with self.file_path.open("r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    rows.append(json.loads(line))
                except Exception:
                    continue
        return rows

    def review(self) -> Dict[str, Any]:
        rows = self._load()

        if not rows:
            return {
                "count": 0,
                "average_score": None,
                "top_categories": [],
                "common_failure_patterns": [],
                "system_upgrades": [
                    "No learning data yet. Start logging decisions and outcomes."
                ],
            }

        scores = [r.get("score", 0.0) for r in rows if isinstance(r.get("score", 0.0), (int, float))]
        average_score = round(sum(scores) / len(scores), 4) if scores else None

        categories = Counter(r.get("category", "unknown") for r in rows)
        failure_patterns = Counter()
        for r in rows:
            outcome = str(r.get("outcome", "")).lower()
            notes = str(r.get("notes", "")).lower()
            text = f"{outcome} {notes}"

            if "fomo" in text:
                failure_patterns["fomo"] += 1
            if "late" in text or "tarde" in text:
                failure_patterns["late_timing"] += 1
            if "overtrade" in text or "sobreoper" in text:
                failure_patterns["overtrading"] += 1
            if "sizing" in text or "tamano" in text or "tamaño" in text:
                failure_patterns["position_sizing"] += 1
            if "risk" in text or "riesgo" in text:
                failure_patterns["risk_control"] += 1

        upgrades = []
        if failure_patterns.get("fomo", 0) >= 2:
            upgrades.append("Increase anti-chasing filter strength.")
        if failure_patterns.get("late_timing", 0) >= 2:
            upgrades.append("Require earlier trigger confirmation and clearer invalidation.")
        if failure_patterns.get("overtrading", 0) >= 2:
            upgrades.append("Reduce trade frequency and raise minimum conviction threshold.")
        if failure_patterns.get("position_sizing", 0) >= 2:
            upgrades.append("Tighten default position sizing rules.")
        if failure_patterns.get("risk_control", 0) >= 2:
            upgrades.append("Elevate risk-chair influence in final decisions.")
        if not upgrades:
            upgrades.append("No dominant failure cluster detected. Continue collecting structured outcomes.")

        return {
            "count": len(rows),
            "average_score": average_score,
            "top_categories": categories.most_common(10),
            "common_failure_patterns": failure_patterns.most_common(10),
            "system_upgrades": upgrades,
            "recent_cases": rows[-10:],
        }
