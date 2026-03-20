from __future__ import annotations

from typing import Any, Dict, List


class LegalComplianceEngine:
    """
    Legal knowledge guardrail engine.
    Does not pretend to 'know every law by memory'.
    Routes legal/tax queries to the right official source set and produces a safe structure.
    """

    def __init__(self) -> None:
        self.official_sources = {
            "colombia_general": [
                {
                    "name": "SUIN-Juriscol",
                    "type": "official_normative_system",
                    "url": "https://www.suin-juriscol.gov.co/",
                },
                {
                    "name": "Función Pública - Gestor Normativo",
                    "type": "official_public_law_source",
                    "url": "https://www1.funcionpublica.gov.co/web/eva/gestor-normativo",
                },
            ],
            "colombia_tax": [
                {
                    "name": "DIAN Normatividad",
                    "type": "official_tax_source",
                    "url": "https://www.dian.gov.co/normatividad/Paginas/Inicio.aspx",
                },
                {
                    "name": "DIAN Normograma",
                    "type": "official_tax_compilation",
                    "url": "https://normograma.dian.gov.co/",
                },
            ],
            "international_accounting": [
                {
                    "name": "IFRS Foundation",
                    "type": "official_accounting_standard_source",
                    "url": "https://www.ifrs.org/",
                },
            ],
        }

    def classify_query(self, query: str) -> Dict[str, Any]:
        text = query.lower()

        domain = "general_legal"
        jurisdiction = "colombia"

        if any(w in text for w in ["impuesto", "tribut", "dian", "renta", "iva", "retencion", "retención"]):
            domain = "tax"
        elif any(w in text for w in ["laboral", "trabajo", "contrato", "empleado", "despido"]):
            domain = "labor"
        elif any(w in text for w in ["sociedad", "accionista", "empresa", "corporativo", "junta"]):
            domain = "corporate"

        if any(w in text for w in ["ifrs", "niif", "ias", "contabilidad internacional"]):
            jurisdiction = "international"

        return {
            "domain": domain,
            "jurisdiction": jurisdiction,
        }

    def source_map(self, query: str) -> Dict[str, Any]:
        cls = self.classify_query(query)

        if cls["jurisdiction"] == "international":
            sources = self.official_sources["international_accounting"]
        elif cls["domain"] == "tax":
            sources = self.official_sources["colombia_tax"] + self.official_sources["colombia_general"]
        else:
            sources = self.official_sources["colombia_general"]

        return {
            "classification": cls,
            "official_sources": sources,
            "warning": (
                "Do not treat legal output as current or final unless validated against official source text and date."
            ),
        }

    def analyze(self, query: str) -> Dict[str, Any]:
        mapping = self.source_map(query)
        cls = mapping["classification"]

        risk_level = "medium"
        if cls["domain"] in {"tax", "labor", "corporate"}:
            risk_level = "high"

        return {
            "query": query,
            "domain": cls["domain"],
            "jurisdiction": cls["jurisdiction"],
            "risk_level": risk_level,
            "official_sources": mapping["official_sources"],
            "required_output_structure": [
                "Issue",
                "Applicable source",
                "Risk",
                "Practical recommendation",
                "Need for official verification",
            ],
            "summary": (
                f"Legal compliance engine classified this as {cls['domain']} / {cls['jurisdiction']}. "
                f"Use official source verification before relying on the answer."
            ),
        }
