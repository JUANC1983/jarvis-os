from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List

from core.agent_schema import build_response, degraded


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
        if not (query or "").strip():
            return degraded("No knowledge query provided", confidence=0.2)
        try:
            return self._analyze_impl(query)
        except Exception as exc:
            return degraded(f"Knowledge synthesis failed: {exc}", confidence=0.25)

    def _analyze_impl(self, query: str) -> Dict[str, Any]:
        text   = (query or "").lower()
        domain = self._detect_domain(text)
        fw     = self._FRAMEWORKS.get(domain, self._FRAMEWORKS["strategy"])
        insight_str = self._DOMAIN_INSIGHTS[domain]
        core_insight = self._build_core_insight(text, domain)
        completeness = min(0.5 + len(text.split()) / 30, 1.0)

        top_framework = fw["frameworks"][0] if fw["frameworks"] else "Systems thinking"
        top_model     = fw["mental_models"][0] if fw["mental_models"] else "Inversion"

        action = (
            f"Apply {top_framework} to structure this decision. "
            f"Mental model: {top_model}. "
            f"Core principle: {insight_str[:100]}. "
            f"Next step: {core_insight[:100]}"
        )

        return build_response(
            confidence=0.82 if len(text.split()) > 6 else 0.62,
            insight=f"[{domain.upper()}] {insight_str}",
            risk_level="low",
            action=action,
            reason=(
                f"Domain: {domain}. "
                f"Applicable framework: {top_framework}. "
                f"Core principle applied: {insight_str[:80]}."
            ),
            signals_used=[
                f"Domain: {domain}",
                f"Framework: {top_framework}",
                f"Mental model: {top_model}",
                f"Query specificity: {'high' if len(text.split()) > 6 else 'low'}",
            ],
            data_sources=["knowledge_framework_library_internal", "mental_model_library_internal"],
            reasoning_path=[
                f"1. Detect domain from query keywords → {domain}",
                f"2. Load framework library for {domain}: {fw['frameworks'][:2]}",
                f"3. Load mental models: {fw['mental_models'][:2]}",
                f"4. Synthesize core insight for domain",
                f"5. Action: apply {top_framework} to this specific query",
            ],
            data_freshness=1.0,
            data_completeness=round(completeness, 2),
        )

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
