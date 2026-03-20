from core.real_agent_council import RealAgentCouncil
from core.global_risk_monitor import GlobalRiskMonitor
from core.opportunity_scoring_engine import OpportunityScoringEngine
from core.decision_cockpit_engine import DecisionCockpitEngine
from core.owner_digital_twin import OwnerDigitalTwin
from core.audit_engine import AuditEngine


class StrategicCommandCenter:
    def __init__(self):
        self.council = RealAgentCouncil()
        self.risk = GlobalRiskMonitor()
        self.opportunity = OpportunityScoringEngine()
        self.cockpit = DecisionCockpitEngine()
        self.owner = OwnerDigitalTwin()
        self.audit = AuditEngine()

    def run(self, topic: str, domain: str = "general", context: str = "") -> dict:
        owner_name = self.owner.owner_summary()["name"]

        council_payload = self.council.deliberate(
            topic=topic,
            domain=domain,
            owner_name=owner_name,
        )
        risk_payload = self.risk.assess(topic, context)
        opportunity_payload = self.opportunity.score(topic, context)
        cockpit_payload = self.cockpit.evaluate(
            topic=topic,
            domain=domain,
            risk_payload=risk_payload,
            opportunity_payload=opportunity_payload,
            council_payload=council_payload,
        )

        result = {
            "owner": owner_name,
            "topic": topic,
            "domain": domain,
            "context": context,
            "council": council_payload,
            "risk": risk_payload,
            "opportunity": opportunity_payload,
            "decision_cockpit": cockpit_payload,
            "executive_summary": (
                f"JARVIS Strategic Command Center evaluated '{topic}' for {owner_name}. "
                f"Risk score: {risk_payload['risk_score']}. "
                f"Opportunity score: {opportunity_payload['opportunity_score']}. "
                f"Recommended stance: {cockpit_payload['recommended_stance']}."
            ),
        }

        self.audit.log_event("strategic_command_center_run", result)
        return result
