from typing import List
from core.models import AgentSelection


class IntentRouter:
    def __init__(self):
        self.finance_terms = {
            "trade", "setup", "entry", "stop", "paper trading",
            "macro", "oil", "gold", "inflation", "rates", "war",
            "portfolio", "allocation", "diversification", "broker",
            "commodity", "commodities", "dollar", "tesoro", "bonos"
        }

        self.tax_terms = {
            "tax", "impuesto", "impuestos", "tributario", "tributaria",
            "renta", "declaracion", "declaración", "fiscal", "fiscalidad",
            "colombia tax", "tax strategy", "taxes"
        }

        self.legal_terms = {
            "contract", "clause", "legal", "lawyer", "abogado",
            "agreement", "lawsuit", "terms", "jurisdiction"
        }

        self.medical_terms = {
            "doctor", "medical", "symptom", "pain", "dolor", "lesion",
            "injury", "blood test", "lab", "laboratory", "cholesterol",
            "glucose", "fatigue", "sleep", "supplement", "supplements",
            "medico", "médico", "health", "salud", "longevity"
        }

        self.golf_terms = {
            "golf", "club", "yardage", "hole", "fairway", "green",
            "swing", "driver", "iron", "putt", "caddy"
        }

        self.lifestyle_terms = {
            "style", "outfit", "clothes", "watch", "travel", "trip",
            "hotel", "flight", "look", "presentation"
        }

        self.social_terms = {
            "relationship", "client", "contact", "follow up", "follow-up",
            "protocol", "etiquette", "tone", "negotiation", "deal",
            "reputation", "positioning"
        }

        self.executive_terms = {
            "meeting", "agenda", "briefing", "priorities", "calendar",
            "decision", "compare", "option", "choice", "strategy", "plan"
        }

        self.document_terms = {
            "document", "pdf", "report", "analyze file", "screenshot",
            "image", "photo", "video", "clip"
        }

    def _contains_any(self, text: str, terms: set[str]) -> bool:
        return any(term in text for term in terms)

    def select_agents(self, message: str) -> AgentSelection:
        text = message.lower().strip()
        supporting_agents: List[str] = []
        reasons: List[str] = []
        risk_escalated = False

        # PRIMARY SELECTION
        if self._contains_any(text, self.tax_terms):
            primary_agent = "tax_strategist_colombia_global"
            reasons.append("Tax-related keywords detected.")

        elif self._contains_any(text, self.medical_terms):
            primary_agent = "chief_medical_advisor"
            reasons.append("Medical or health-related keywords detected.")

        elif "swing" in text:
            primary_agent = "swing_analyzer"
            reasons.append("Swing analysis request detected.")

        elif self._contains_any(text, self.golf_terms):
            primary_agent = "golf_caddy_ai"
            reasons.append("Golf-related keywords detected.")

        elif "trade" in text or "setup" in text or "paper trading" in text:
            primary_agent = "trader"
            reasons.append("Trading-specific execution keywords detected.")

        elif self._contains_any(text, self.finance_terms):
            primary_agent = "strategic_investment"
            reasons.append("Macro / investment keywords detected.")

        elif self._contains_any(text, self.legal_terms):
            primary_agent = "lawyer"
            reasons.append("Legal keywords detected.")

        elif self._contains_any(text, self.social_terms):
            primary_agent = "relationship_manager"
            reasons.append("Relationship / social keywords detected.")

        elif self._contains_any(text, self.lifestyle_terms):
            primary_agent = "style_advisor"
            reasons.append("Lifestyle / style / travel keywords detected.")

        elif self._contains_any(text, self.document_terms):
            primary_agent = "document_analyzer"
            reasons.append("Document / image / video keywords detected.")

        elif self._contains_any(text, self.executive_terms):
            primary_agent = "chief_of_staff"
            reasons.append("Executive coordination keywords detected.")

        else:
            primary_agent = "strategist"
            reasons.append("Fallback to strategic reasoning.")

        # SUPPORTING AGENTS
        if self._contains_any(text, self.finance_terms) and primary_agent != "strategic_investment":
            supporting_agents.append("strategic_investment")
            reasons.append("Added Strategic Investment as finance support.")

        if self._contains_any(text, self.tax_terms) and primary_agent != "tax_strategist_colombia_global":
            supporting_agents.append("tax_strategist_colombia_global")
            reasons.append("Added Tax Strategist as tax support.")

        if self._contains_any(text, self.legal_terms) and primary_agent != "lawyer":
            supporting_agents.append("lawyer")
            reasons.append("Added Lawyer as legal support.")

        if self._contains_any(text, self.medical_terms) and primary_agent != "chief_medical_advisor":
            supporting_agents.append("chief_medical_advisor")
            reasons.append("Added Chief Medical Advisor as medical support.")

        if "portfolio" in text or "allocation" in text or "diversification" in text:
            supporting_agents.append("portfolio_manager")
            reasons.append("Added Portfolio Manager for allocation context.")

        if "research" in text or "investigate" in text or "compare" in text:
            supporting_agents.append("research_librarian")
            reasons.append("Added Research Librarian for comparison support.")

        if "risk" in text or self._contains_any(text, self.finance_terms | self.legal_terms | self.medical_terms):
            if primary_agent != "risk_analyst":
                supporting_agents.append("risk_analyst")
                risk_escalated = True
                reasons.append("Sensitive domain detected; escalated to Risk Analyst.")

        if "meeting" in text or "agenda" in text or "briefing" in text:
            if primary_agent != "chief_of_staff":
                supporting_agents.append("chief_of_staff")
                reasons.append("Added Chief of Staff for execution and briefing support.")

        if "image" in text or "photo" in text or "picture" in text:
            supporting_agents.append("image_analyzer")
            reasons.append("Added Image Analyzer for visual support.")

        if "video" in text or "clip" in text:
            supporting_agents.append("video_analyzer")
            reasons.append("Added Video Analyzer for video support.")

        # CLEAN + UNIQUE ORDER PRESERVED
        seen = set()
        dedup_supporting = []
        for agent in supporting_agents:
            if agent != primary_agent and agent not in seen:
                seen.add(agent)
                dedup_supporting.append(agent)

        return AgentSelection(
            primary_agent=primary_agent,
            supporting_agents=dedup_supporting,
            risk_escalated=risk_escalated,
            reasons=reasons,
        )