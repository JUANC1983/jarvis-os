from __future__ import annotations

from typing import Any, Dict, List


class SystemGuardrailsEngine:
    def evaluate(self, text: str) -> Dict[str, Any]:
        t = (text or "").lower()
        flags: List[str] = []
        domain = "general"
        level = "normal"

        if any(w in t for w in ["suicidio", "self-harm", "matarme"]):
            flags.append("self_harm_risk")
            level = "critical"

        if any(w in t for w in ["invertir", "trading", "acciones", "crypto", "oil", "petroleo"]):
            domain = "finance"

        if any(w in t for w in ["fiebre", "dolor", "medicamento", "examen", "lab", "sintoma", "sintoma"]):
            domain = "medical"
            if level != "critical":
                level = "high"

        if any(w in t for w in ["impuestos", "tributario", "dian", "demanda", "contrato", "legal"]):
            domain = "legal"
            if level != "critical":
                level = "high"

        if any(w in t for w in ["urgente", "emergency", "grave", "hospital"]):
            flags.append("urgency_detected")
            level = "critical"

        return {
            "domain": domain,
            "risk_level": level,
            "flags": flags,
            "summary": f"Guardrails classified this request as {domain} / {level}.",
        }
