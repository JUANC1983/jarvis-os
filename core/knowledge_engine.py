from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List


class KnowledgeEngine:
    """
    Strategic knowledge synthesis — frameworks, mental models, structured intelligence.
    """

    _FRAMEWORKS: Dict[str, Dict[str, List[str]]] = {
        "finance": {
            "frameworks": ["DCF valuation", "Macro regime analysis", "Kelly criterion sizing", "Risk/reward matrix"],
            "mental_models": ["Second-order effects", "Optionality value", "Tail risk asymmetry", "Compounding leverage"],
        },
        "business": {
            "frameworks": ["Porter's Five Forces", "Unit economics", "Moat analysis", "JTBD framework"],
            "mental_models": ["Network effects", "Switching costs", "Pricing power", "Scalable vs. linear"],
        },
        "health": {
            "frameworks": ["VO2max protocol", "Sleep architecture", "HRV biofeedback", "Biomarker baseline"],
            "mental_models": ["Prevention over cure", "Stress-adaptation cycle", "Dose-response curve"],
        },
        "strategy": {
            "frameworks": ["OODA loop", "Regret minimization", "Inversion thinking", "Energy audit"],
            "mental_models": ["Leverage points", "Systems vs. goals", "Memento mori urgency", "Seneca time"],
        },
        "legal": {
            "frameworks": ["Risk stratification", "Documentation chain", "Jurisdiction mapping"],
            "mental_models": ["Prevention vs. remedy", "Paper trail = leverage", "Intent vs. outcome"],
        },
    }

    _DOMAIN_INSIGHTS: Dict[str, str] = {
        "finance": "Financial edge comes from asymmetry: maximize upside optionality while hard-capping downside. Capital that survives markets long enough compounds exponentially.",
        "business": "Business leverage compounds through scalable systems. The constraint is almost never effort — it's distribution, timing, or product-market fit.",
        "health": "Health is the root asset. Every performance variable — cognitive, emotional, financial — degrades with health. Investment in prevention returns 10x over reactive medicine.",
        "strategy": "The highest-leverage decisions are not urgent. They are the ones that change which game you're playing. Systems beat goals because systems survive motivation.",
        "legal": "Legal risk compounds through inaction. The most expensive legal advice is retroactive. Prevention and documentation cost 5% of what litigation costs.",
    }

    def get_knowledge(self, query: str) -> Dict[str, Any]:
        return self.analyze(query)

    def search(self, query: str) -> Dict[str, Any]:
        return self.analyze(query)

    def analyze(self, query: str) -> Dict[str, Any]:
        text   = (query or "").lower()
        domain = self._detect_domain(text)
        fw     = self._FRAMEWORKS.get(domain, self._FRAMEWORKS["strategy"])

        return {
            "query":   query,
            "domain":  domain,
            "insight": self._DOMAIN_INSIGHTS[domain],
            "core_insight": self._build_core_insight(text, domain),
            "applicable_frameworks": fw["frameworks"][:3],
            "mental_models":         fw["mental_models"][:2],
            "recommendations": {
                "short_term": [
                    "Identify the single binding constraint preventing progress",
                    "Gather 2–3 high-signal data points before acting — not 20",
                    "Decide: is this reversible? If yes, move fast. If not, slow down.",
                ],
                "mid_term": [
                    "Build systems over goals — automate the right default behavior",
                    "Measure leading indicators, not just outcomes",
                    f"Apply {fw['frameworks'][0]} to structure the decision",
                ],
                "long_term": [
                    "Compound small advantages — 1% improvement daily = 37x in a year",
                    "Protect optionality while pursuing asymmetric upside",
                    "Document decisions and their reasoning — future you will thank you",
                ],
            },
            "risk_assessment": {
                "level": "low",
                "note": "Knowledge synthesis stage — no execution risk until action is taken",
            },
            "confidence":       0.82,
            "decision_clarity": "high" if len(text.split()) > 6 else "medium",
            "source":           "knowledge_engine",
            "generated_at":     datetime.utcnow().isoformat(),
        }

    # ------------------------------------------------------------------
    # Private
    # ------------------------------------------------------------------
    def _detect_domain(self, text: str) -> str:
        if any(w in text for w in [
            "money", "invest", "inversión", "inversion", "stock", "market",
            "asset", "capital", "portfolio", "trade", "bolsa", "acciones",
            "dinero", "finanzas", "finance",
        ]):
            return "finance"
        if any(w in text for w in [
            "business", "startup", "empresa", "company", "revenue",
            "product", "customer", "growth", "negocio",
        ]):
            return "business"
        if any(w in text for w in [
            "health", "body", "fitness", "sleep", "energy", "medical",
            "longevity", "salud", "cuerpo", "dormir", "energía",
        ]):
            return "health"
        if any(w in text for w in [
            "legal", "law", "contract", "compliance", "ley", "contrato", "abogado",
        ]):
            return "legal"
        return "strategy"

    def _build_core_insight(self, text: str, domain: str) -> str:
        fw = self._FRAMEWORKS[domain]["frameworks"][0]
        return (
            f"Apply {fw} to structure your analysis. "
            "The highest-leverage action is almost always the one that removes the binding constraint "
            "or breaks the key assumption. "
            "Ask: what would have to be true for this to fail? Then decide if you can live with that."
        )
