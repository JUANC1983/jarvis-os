from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List


class LegalComplianceEngine:
    """
    Legal intelligence engine — Colombia-first, internationally aware.
    Structured legal guidance with source verification, risk stratification,
    and actionable recommendations. NOT a substitute for licensed legal counsel.
    """

    DISCLAIMER = (
        "This is not legal advice. Consult a licensed attorney before acting on "
        "any legal analysis. Laws change — always verify against current official sources."
    )

    OFFICIAL_SOURCES = {
        "colombia_general": [
            {"name": "SUIN-Juriscol",           "url": "https://www.suin-juriscol.gov.co/"},
            {"name": "Función Pública — EVA",   "url": "https://www1.funcionpublica.gov.co/web/eva/gestor-normativo"},
        ],
        "colombia_tax": [
            {"name": "DIAN Normatividad",       "url": "https://www.dian.gov.co/normatividad/"},
            {"name": "DIAN Normograma",         "url": "https://normograma.dian.gov.co/"},
        ],
        "colombia_labor": [
            {"name": "Ministerio del Trabajo",  "url": "https://www.mintrabajo.gov.co/normatividad"},
            {"name": "Código Sustantivo Trabajo", "url": "https://www.funcionpublica.gov.co/eva/gestornormativo/norma.php?i=33104"},
        ],
        "international": [
            {"name": "IFRS Foundation",         "url": "https://www.ifrs.org/"},
        ],
    }

    # Key Colombia 2024 reference thresholds
    COLOMBIA_REF = {
        "uvt_2024":                  47_065,
        "uvt_2025":                  49_799,
        "declaracion_renta_minimo":  "162 UVT patrimonio / 40 UVT ingresos",
        "iva_general":               "19%",
        "retencion_honorarios":      "10% (no declarantes) / 11% (declarantes)",
        "smmlv_2025":                1_423_500,
        "sagrilaft_umbral":          "Empresas con activos totales ≥ 40.000 SMMLV",
    }

    # ------------------------------------------------------------------
    # Public API (backward compat preserved)
    # ------------------------------------------------------------------

    def analyze(self, query: str) -> Dict[str, Any]:
        text        = (query or "").lower()
        domain      = self._classify_domain(text)
        jurisdiction = self._classify_jurisdiction(text)
        risk        = self._assess_risk(domain, text)
        sources     = self._get_sources(domain, jurisdiction)

        return {
            "query":        query,
            "domain":       domain,
            "jurisdiction": jurisdiction,
            "risk_level":   risk["level"],
            "risk_factors": risk["factors"],
            "legal_reasoning": self._build_reasoning(domain),
            "key_analysis":    self._key_analysis(domain, text),
            "official_sources": sources,
            "required_documentation": self._required_docs(domain),
            "key_thresholds":  self._key_thresholds(domain),
            "recommendations": {
                "short_term": self._short_term(domain, text),
                "mid_term":   self._mid_term(domain),
                "long_term":  self._long_term(),
            },
            "required_output_structure": [
                "Issue", "Applicable source", "Risk", "Practical recommendation", "Official verification needed",
            ],
            "confidence":       0.75,
            "decision_clarity": "medium",
            "disclaimer":       self.DISCLAIMER,
            "source":           "legal_compliance",
            "generated_at":     datetime.utcnow().isoformat(),
        }

    def classify_query(self, query: str) -> Dict[str, Any]:
        text = query.lower()
        return {
            "domain":       self._classify_domain(text),
            "jurisdiction": self._classify_jurisdiction(text),
        }

    def source_map(self, query: str) -> Dict[str, Any]:
        text  = query.lower()
        domain = self._classify_domain(text)
        jurisdiction = self._classify_jurisdiction(text)
        return {
            "classification":  self.classify_query(query),
            "official_sources": self._get_sources(domain, jurisdiction),
            "warning":         self.DISCLAIMER,
        }

    # ------------------------------------------------------------------
    # Classification
    # ------------------------------------------------------------------

    def _classify_domain(self, text: str) -> str:
        if any(w in text for w in [
            "impuesto", "tribut", "dian", "renta", "iva", "retencion", "retención",
            "rut", "declaracion", "declaración", "factura", "tributar", "tax",
        ]):
            return "tax"
        if any(w in text for w in [
            "laboral", "trabajo", "empleado", "despido", "contrato laboral",
            "pension", "cesantias", "nómina", "nomina", "liquidacion",
        ]):
            return "labor"
        if any(w in text for w in [
            "sociedad", "sas", "empresa", "accionista", "corporativo",
            "junta directiva", "escritura", "sagrilaft", "cámara comercio",
        ]):
            return "corporate"
        if any(w in text for w in [
            "contrato", "contract", "obligacion", "incumplimiento", "demanda",
            "breach", "cláusula", "clausula",
        ]):
            return "contracts"
        if any(w in text for w in [
            "propiedad", "inmueble", "arrendamiento", "hipoteca", "predial",
            "escritura", "folio", "registro",
        ]):
            return "real_estate"
        if any(w in text for w in [
            "ifrs", "niif", "ias", "contabilidad", "balance", "estados financieros",
        ]):
            return "accounting"
        return "general_legal"

    def _classify_jurisdiction(self, text: str) -> str:
        if any(w in text for w in ["ifrs", "international", "eeuu", "usa", "global", "internacional"]):
            return "international"
        return "colombia"

    def _assess_risk(self, domain: str, text: str) -> Dict[str, Any]:
        high_risk = {"tax", "labor", "corporate"}
        level = "high" if domain in high_risk else "medium"

        factors_map: Dict[str, List[str]] = {
            "tax": [
                "Non-compliance carries penalties (100–200% of unpaid tax) + interest (DTF + 2 points)",
                "DIAN statute of limitations: 3 years general, 5 years for fraud or non-declaration",
                "International structures may trigger FATCA/CRS reporting obligations",
                "Transfer pricing rules apply to transactions with related parties abroad",
            ],
            "labor": [
                "Colombian labor code is strongly pro-worker — employer carries burden of proof",
                "Wrongful dismissal without just cause: indemnification up to 180 days salary",
                "De facto labor relationship (contract of work + subordination) = labor law applies",
                "Non-formal arrangements create hidden labor liabilities — common trap for startups",
            ],
            "corporate": [
                "SAS (Sociedad por Acciones Simplificada) is the preferred flexible structure",
                "Directors have personal liability if corporate veil pierced (fraud, capitalization failure)",
                "SAGRILAFT compliance mandatory above ~40,000 SMMLV in total assets",
                "Actas must be formally documented — verbal decisions have no legal weight",
            ],
            "contracts": [
                "Verbal agreements are valid but extremely hard to enforce — written evidence is key",
                "Colombiam civil code requires: offer + acceptance + cause + object + capacity",
                "Penalty clauses (cláusula penal) must be reasonable — courts can reduce excessive ones",
            ],
        }
        return {
            "level":   level,
            "factors": factors_map.get(domain, ["Standard legal risk — validate with official sources"]),
        }

    def _get_sources(self, domain: str, jurisdiction: str) -> List[Dict[str, str]]:
        if jurisdiction == "international":
            return self.OFFICIAL_SOURCES["international"]
        if domain == "tax":
            return self.OFFICIAL_SOURCES["colombia_tax"] + self.OFFICIAL_SOURCES["colombia_general"]
        if domain == "labor":
            return self.OFFICIAL_SOURCES["colombia_labor"] + self.OFFICIAL_SOURCES["colombia_general"]
        return self.OFFICIAL_SOURCES["colombia_general"]

    def _build_reasoning(self, domain: str) -> str:
        reasoning: Dict[str, str] = {
            "tax": (
                "Colombian tax law is complex and frequently reformed by annual tax reform bills. "
                "The applicable regime depends on entity type (natural vs. jurídica), "
                "revenue threshold, economic activity, and residency. "
                "DIAN has administrative faculties to audit 3–5 years retroactively. "
                "The 'principio de buena fe' requires proactive compliance, not reactive defense."
            ),
            "labor": (
                "The Código Sustantivo del Trabajo (CST) provides strong worker protections. "
                "The key legal test: is there subordination (power to direct work) + habitual activity + remuneration? "
                "If yes — formal contract obligations apply regardless of how the arrangement was labeled. "
                "Risk area: independent contractor agreements that de facto operate as employment."
            ),
            "corporate": (
                "SAS structure offers flexibility (single shareholder OK, no fixed capital requirements) and limited liability. "
                "Key obligations: formal actas for all major decisions, SAGRILAFT for large entities, "
                "RUT vigente, and annual renovación de matrícula mercantil. "
                "Directors must document decisions to avoid personal liability under Article 23 of Law 222/1995."
            ),
            "contracts": (
                "Colombian contract law follows civil and commercial code. "
                "Written contracts are enforceable; verbal ones theoretically valid but practically unenforceable. "
                "For contracts >50 SMMLV: notarial requirement in some categories (real estate, powers of attorney). "
                "Electronic contracts are valid under Ley 527 de 1999 (e-commerce law)."
            ),
            "real_estate": (
                "Property rights in Colombia are registered at the Oficina de Registro de Instrumentos Públicos. "
                "Due diligence must cover: folio de matrícula inmobiliaria (property history), "
                "gravámenes (liens), paz y salvo predial, and curaduria urbana zoning restrictions. "
                "Scritpura pública + registro is required for title transfer to be legally valid."
            ),
            "accounting": (
                "NIIF (IFRS) mandatory adoption in Colombia: Group 1 (large enterprises) since 2016, "
                "Group 2 (SMEs) since 2017. Key divergences from local GAAP: "
                "fair value measurement, financial instrument classification (IFRS 9), and lease treatment (IFRS 16). "
                "Regulatory basis: Decreto 2649/1993 superseded by Decreto Único Reglamentario 2420/2015."
            ),
        }
        return reasoning.get(domain, (
            "Legal analysis requires precise case-specific facts. "
            "Identify the applicable code (civil, commercial, labor, penal), "
            "the relevant articles, and assess whether your facts trigger those provisions."
        ))

    def _key_analysis(self, domain: str, text: str) -> List[str]:
        analysis: Dict[str, List[str]] = {
            "tax": [
                f"UVT 2024: ${self.COLOMBIA_REF['uvt_2024']:,} COP — threshold for most tax obligations",
                f"Declaración de renta: required if patrimonio >{self.COLOMBIA_REF['declaracion_renta_minimo']}",
                f"IVA general rate: {self.COLOMBIA_REF['iva_general']}",
                f"Retención honorarios: {self.COLOMBIA_REF['retencion_honorarios']}",
            ],
            "labor": [
                f"SMMLV 2025: ${self.COLOMBIA_REF['smmlv_2025']:,} COP/month",
                "Parafiscales: employer pays EPS (8.5%), ARL (0.5–8.7%), CCF (4%), ICBF (3%), SENA (2%)",
                "Prima: 15 days salary each semester (June 30 + December 20)",
                "Cesantías: 1 month salary per year, deposited February 14",
            ],
            "corporate": [
                "SAS: minimum 1 shareholder, no minimum capital, maximum flexibility",
                f"SAGRILAFT threshold: activos totales ≥ 40,000 SMMLV",
                "Matrícula mercantil: renewed January–March each year",
                "RUES registration required for all commercial entities",
            ],
        }
        return analysis.get(domain, [
            "Identify the specific legal question and applicable jurisdiction",
            "Verify current regulations — laws change frequently in Colombia",
        ])

    def _required_docs(self, domain: str) -> List[str]:
        docs: Dict[str, List[str]] = {
            "tax":        ["RUT vigente", "Certificados de retención", "Extractos bancarios 2 años", "Declaraciones anteriores"],
            "labor":      ["Contrato escrito", "Comprobantes de pago nómina", "Correspondencia relevante", "Reglamento interno"],
            "corporate":  ["Escritura de constitución", "Actas de junta/asamblea", "RUT empresa", "Certificado existencia y representación"],
            "real_estate": ["Folio de matrícula inmobiliaria", "Paz y salvo predial", "Escritura pública", "Certificado uso de suelo"],
            "contracts":  ["Contrato escrito firmado", "Comunicaciones relevantes", "Prueba de cumplimiento/incumplimiento"],
        }
        return docs.get(domain, [
            "All relevant written agreements",
            "Email and message correspondence",
            "Financial records related to the matter",
        ])

    def _key_thresholds(self, domain: str) -> Dict[str, Any]:
        if domain == "tax":
            return {k: v for k, v in self.COLOMBIA_REF.items()}
        if domain == "labor":
            return {"smmlv_2025": f"${self.COLOMBIA_REF['smmlv_2025']:,} COP"}
        return {}

    def _short_term(self, domain: str, text: str) -> List[str]:
        recs: Dict[str, List[str]] = {
            "tax": [
                "Verify your RUT is active and updated — DIAN.gov.co",
                f"Check UVT value (${self.COLOMBIA_REF['uvt_2025']:,} for 2025) to assess your obligations",
                "Consult a contador público titulado before filing any declaration",
            ],
            "labor": [
                "Document any verbal agreement in writing immediately — today, not tomorrow",
                "Consult a labor attorney before terminating any contract",
                "Review all contractor relationships for subordination indicators",
            ],
            "corporate": [
                "Ensure all junta decisions are formalized in signed actas",
                "Verify SAGRILAFT compliance status for your company size",
                "Check that matrícula mercantil is current",
            ],
        }
        return recs.get(domain, [
            "Document your situation with all relevant facts and dates",
            "Consult a licensed attorney before taking any legal action",
            "Read the applicable official source directly — do not rely on third-party summaries",
        ])

    def _mid_term(self, domain: str) -> List[str]:
        return [
            "Engage a specialist attorney in your specific domain",
            "Build a legal compliance calendar: deadlines, filings, renewals",
            "Document all material communications — paper trail is your only defense",
            "Seek a second legal opinion before any decision >50M COP in consequence",
        ]

    def _long_term(self) -> List[str]:
        return [
            "Annual preventive legal audit — far cheaper than reactive litigation",
            "Proactive entity structuring for tax efficiency and liability protection",
            "Relationship with trusted contador + abogado: they pay for themselves 10× over",
            "Subscribe to DIAN and Ministerio del Trabajo updates — Colombian law changes frequently",
        ]
