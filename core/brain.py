from typing import List

from core.identity import JarvisIdentity
from core.models import (
    AgentExecutionResult,
    AgentSelection,
    BrainSynthesis,
)
from core.intent_ai_router import IntentAIRouter
from core.strategic_council import StrategicCouncil
from agents.default_agents import registry

try:
    from memory_vector.vector_memory_engine import VectorMemoryEngine
except Exception:
    VectorMemoryEngine = None


class JarvisCoreBrain:
    def __init__(self):
        self.identity = JarvisIdentity()
        self.router = IntentAIRouter()
        self.council = StrategicCouncil()
        self.vector_memory = VectorMemoryEngine() if VectorMemoryEngine else None

    def plan(self, message: str) -> AgentSelection:
        enriched_message = f"{self.identity.system_prompt_context()} User request: {message}"
        return self.router.classify_intent(enriched_message)

    def recall_memories(self, message: str) -> List[dict]:
        if not self.vector_memory:
            return []

        try:
            return self.vector_memory.recall(message)
        except Exception:
            return []

    def remember_interaction(self, message: str, primary_agent: str) -> None:
        if not self.vector_memory:
            return

        try:
            self.vector_memory.remember(f"[owner={self.identity.owner.name}] [agent={primary_agent}] {message}")
        except Exception:
            pass

    def execute_agents(self, selection: AgentSelection, message: str) -> List[AgentExecutionResult]:
        ordered_agents = [selection.primary_agent] + selection.supporting_agents
        results: List[AgentExecutionResult] = []

        for agent_name in ordered_agents:
            agent = registry.get(agent_name)
            if not agent:
                continue

            results.append(
                AgentExecutionResult(
                    agent_name=agent.name,
                    display_name=agent.display_name,
                    category=agent.category,
                    response=agent.respond(message),
                )
            )

        return results

    def synthesize(
        self,
        message: str,
        selection: AgentSelection,
        direct_results: List[AgentExecutionResult],
        council_results: List[AgentExecutionResult],
        retrieved_memories: List[dict],
    ) -> BrainSynthesis:
        if not direct_results:
            return BrainSynthesis(
                executive_summary="No agents were available to process this request.",
                key_points=[],
                recommended_next_steps=["Review agent registry configuration."],
                risk_flags=["Agent execution failure."],
                consulted_agents=[],
                primary_agent=selection.primary_agent,
            )

        primary_result = direct_results[0]

        key_points = [result.response for result in direct_results]

        for result in council_results:
            council_line = f"[Council] {result.display_name}: {result.response}"
            if council_line not in key_points:
                key_points.append(council_line)

        if retrieved_memories:
            for memory in retrieved_memories[:3]:
                memory_text = memory.get("text", "").strip()
                if memory_text:
                    key_points.append(f"Relevant memory: {memory_text}")

        recommended_next_steps = self._recommend_next_steps(message, selection)
        risk_flags = self._risk_flags(message, selection)

        executive_summary = (
            f"JARVIS, acting as the personal strategic intelligence system of {self.identity.owner.name}, "
            f"used '{primary_result.display_name}' as the lead agent, consulted {max(len(direct_results) - 1, 0)} direct supporting agent(s), "
            f"and ran a Strategic Council with {len(council_results)} expert contribution(s). "
            f"Primary assessment: {primary_result.response}"
        )

        if retrieved_memories:
            executive_summary += f" Retrieved {len(retrieved_memories)} relevant memory item(s)."

        consulted = [result.agent_name for result in direct_results]
        for result in council_results:
            if result.agent_name not in consulted:
                consulted.append(result.agent_name)

        return BrainSynthesis(
            executive_summary=executive_summary,
            key_points=key_points,
            recommended_next_steps=recommended_next_steps,
            risk_flags=risk_flags,
            consulted_agents=consulted,
            primary_agent=selection.primary_agent,
        )

    def respond(self, message: str) -> BrainSynthesis:
        selection = self.plan(message)
        retrieved_memories = self.recall_memories(message)
        direct_results = self.execute_agents(selection, message)
        council_results = self.council.run(selection.primary_agent, message)
        synthesis = self.synthesize(message, selection, direct_results, council_results, retrieved_memories)
        self.remember_interaction(message, selection.primary_agent)
        return synthesis

    def _recommend_next_steps(self, message: str, selection: AgentSelection) -> List[str]:
        steps: List[str] = []

        if selection.primary_agent == "chief_medical_advisor":
            steps.extend([
                "Document symptoms, timing, severity, and what triggers or relieves them.",
                "Add labs, images, medications, supplements, or prior history for a stronger review.",
                "Escalate to urgent care immediately if symptoms worsen or show red flags.",
            ])

        if selection.primary_agent == "tax_strategist_colombia_global":
            steps.extend([
                "Gather tax structure, entities, investments, and supporting fiscal documents.",
                "Compare personal, corporate, and international structures before acting.",
                "Validate legal and compliance implications before implementation.",
            ])

        if selection.primary_agent in {"strategic_investment", "portfolio_manager", "trader"}:
            steps.extend([
                "Define thesis, horizon, invalidation, and downside scenario explicitly.",
                "Separate long-term capital allocation from tactical execution.",
                "Review exposure, concentration, tax impact, and liquidity before acting.",
            ])

        if selection.primary_agent == "life_strategist":
            steps.extend([
                "Clarify the life objective across wealth, family, health, and time.",
                "List trade-offs explicitly, not just upside.",
                "Choose the option that compounds long-term life quality, not only short-term gain.",
            ])

        if not steps:
            steps.extend([
                "Clarify your desired outcome and key constraints.",
                "Add documents, context, or data for deeper reasoning.",
                "Review timing, risk, and second-order effects before acting.",
            ])

        return steps[:5]

    def _risk_flags(self, message: str, selection: AgentSelection) -> List[str]:
        flags: List[str] = []
        text = message.lower()

        if selection.risk_escalated:
            flags.append("Sensitive domain detected; risk review recommended.")

        if selection.primary_agent in {"chief_medical_advisor", "family_doctor"}:
            flags.append("Medical guidance should not replace urgent or in-person care.")

        if selection.primary_agent in {"trader", "strategic_investment", "portfolio_manager", "tax_strategist_colombia_global"}:
            flags.append("Financial and tax decisions require independent validation, sizing, and documentation.")

        if selection.primary_agent == "lawyer":
            flags.append("Legal conclusions should be checked against documents and jurisdiction.")

        if "urgent" in text or "emergency" in text or "emergencia" in text:
            flags.append("Urgency language detected; prioritize immediate escalation if necessary.")

        return flags
