from __future__ import annotations

"""
Universal agent output schema builder.

All JARVIS decision agents return EXACTLY this structure from analyze():

{
    "status":     "ok" | "degraded",
    "confidence": float (0.0–1.0),
    "insight":    str,
    "risk_level": "low" | "medium" | "high",
    "action":     str,          # specific, executable, measurable
    "reason":     str,
    "data": {
        "signals_used":       list[str],
        "data_sources":       list[str],
        "reasoning_path":     list[str],
        "data_freshness":     float (0.0–1.0),
        "data_completeness":  float (0.0–1.0),
    }
}
"""

from typing import Any, List


def build_response(
    *,
    status: str = "ok",
    confidence: float,
    insight: str,
    risk_level: str,
    action: str,
    reason: str,
    signals_used: List[str],
    data_sources: List[str],
    reasoning_path: List[str],
    data_freshness: float = 1.0,
    data_completeness: float = 1.0,
) -> dict:
    """Build a fully-compliant universal agent response."""
    if risk_level not in ("low", "medium", "high"):
        risk_level = "medium"
    confidence = max(0.0, min(1.0, float(confidence)))
    data_freshness = max(0.0, min(1.0, float(data_freshness)))
    data_completeness = max(0.0, min(1.0, float(data_completeness)))
    return {
        "status": status,
        "confidence": round(confidence, 3),
        "insight": str(insight),
        "risk_level": risk_level,
        "action": str(action),
        "reason": str(reason),
        "data": {
            "signals_used": list(signals_used),
            "data_sources": list(data_sources),
            "reasoning_path": list(reasoning_path),
            "data_freshness": round(data_freshness, 3),
            "data_completeness": round(data_completeness, 3),
        },
    }


def degraded(reason: str = "Data unavailable or unreliable", confidence: float = 0.25) -> dict:
    """Standard degraded-mode response. confidence must be 0.2–0.5."""
    confidence = max(0.2, min(0.5, float(confidence)))
    return {
        "status": "degraded",
        "confidence": round(confidence, 3),
        "insight": "Fallback mode active",
        "risk_level": "medium",
        "action": "wait",
        "reason": reason,
        "data": {},
    }
