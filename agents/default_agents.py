from agents.agent_registry import Agent, AgentRegistry


registry = AgentRegistry()


class TraderAgent(Agent):
    def respond(self, message: str) -> str:
        return "Trader agent analyzing setups, execution discipline, entries, exits, and trading process."


class StrategicInvestmentAgent(Agent):
    def respond(self, message: str) -> str:
        return "Strategic Investment agent analyzing macro regimes, commodities, rates, inflation, geopolitical opportunities, and long-term thesis."


class PortfolioManagerAgent(Agent):
    def respond(self, message: str) -> str:
        return "Portfolio Manager reviewing allocation, diversification, portfolio concentration, and capital protection."


class TaxStrategistColombiaGlobalAgent(Agent):
    def respond(self, message: str) -> str:
        return "Tax Strategist Colombia Global evaluating legal tax optimization, Colombian tax exposure, international structuring, and compliance risk."


class AccountingOperationsAgent(Agent):
    def respond(self, message: str) -> str:
        return "Accounting Operations organizing accounting workflows, obligations, reconciliations, and financial document order."


class LawyerAgent(Agent):
    def respond(self, message: str) -> str:
        return "Lawyer reviewing legal implications, contractual exposure, structure, and potential legal risk."


class ChiefOfStaffAgent(Agent):
    def respond(self, message: str) -> str:
        return "Chief of Staff preparing executive priorities, briefings, meeting structure, and operational focus."


class StrategistAgent(Agent):
    def respond(self, message: str) -> str:
        return "Strategist evaluating long-term positioning, strategic direction, leverage points, and decision quality."


class RiskAnalystAgent(Agent):
    def respond(self, message: str) -> str:
        return "Risk Analyst reviewing downside exposure across legal, financial, strategic, medical, and reputational dimensions."


class ChiefMedicalAdvisorAgent(Agent):
    def respond(self, message: str) -> str:
        return "Chief Medical Advisor analyzing symptoms, health context, prevention, labs, and medical reasoning."


class FamilyDoctorAgent(Agent):
    def respond(self, message: str) -> str:
        return "Family Doctor organizing symptoms, history, possible causes, and practical next medical steps."


class BiometricsAnalyzerAgent(Agent):
    def respond(self, message: str) -> str:
        return "Biometrics Analyzer interpreting body metrics, trends, blood markers, and physiological signals."


class FitnessCoachAgent(Agent):
    def respond(self, message: str) -> str:
        return "Fitness Coach reviewing training structure, movement, strength, mobility, and physical progression."


class NutritionistAgent(Agent):
    def respond(self, message: str) -> str:
        return "Nutritionist evaluating nutrition strategy, food structure, energy support, and dietary optimization."


class SleepOptimizerAgent(Agent):
    def respond(self, message: str) -> str:
        return "Sleep Optimizer reviewing sleep quality, recovery, circadian rhythm, and fatigue drivers."


class LongevityStrategistAgent(Agent):
    def respond(self, message: str) -> str:
        return "Longevity Strategist evaluating long-term healthspan, preventive health, aging biomarkers, and resilience."


class SupplementAdvisorAgent(Agent):
    def respond(self, message: str) -> str:
        return "Supplement Advisor reviewing supplementation protocols, interactions, and performance or longevity support."


class StyleAdvisorAgent(Agent):
    def respond(self, message: str) -> str:
        return "Style Advisor recommending outfit strategy, visual coherence, presence, and social-context fit."


class TravelConciergeAgent(Agent):
    def respond(self, message: str) -> str:
        return "Travel Concierge organizing travel logistics, itineraries, efficiency, and context-aware travel support."


class GolfCaddyAIAgent(Agent):
    def respond(self, message: str) -> str:
        return "Golf Caddy AI evaluating yardage, lie, wind, target strategy, and club selection."


class SwingAnalyzerAgent(Agent):
    def respond(self, message: str) -> str:
        return "Swing Analyzer reviewing motion patterns, mechanics, inefficiencies, and golf swing corrections."


class ResearchLibrarianAgent(Agent):
    def respond(self, message: str) -> str:
        return "Research Librarian gathering, comparing, and synthesizing relevant information for decision support."


class ImageAnalyzerAgent(Agent):
    def respond(self, message: str) -> str:
        return "Image Analyzer interpreting visual inputs such as outfits, screenshots, injuries, and document images."


class VideoAnalyzerAgent(Agent):
    def respond(self, message: str) -> str:
        return "Video Analyzer interpreting motion and context from videos such as swing, movement, or scenario footage."


class OpportunityRadarAgent(Agent):
    def respond(self, message: str) -> str:
        return "Opportunity Radar scanning for asymmetric opportunities in markets, business, macro shifts, and timing windows."


class CrisisSimulatorAgent(Agent):
    def respond(self, message: str) -> str:
        return "Crisis Simulator stress-testing scenarios, second-order effects, tail risks, and downside pathways."


class LifeStrategistAgent(Agent):
    def respond(self, message: str) -> str:
        return "Life Strategist optimizing long-term life direction across wealth, family, health, legacy, and time allocation."


class CognitiveBiasDetectorAgent(Agent):
    def respond(self, message: str) -> str:
        return "Cognitive Bias Detector checking for confirmation bias, overconfidence, FOMO, anchoring, and emotional distortion."


class DecisionSimulatorAgent(Agent):
    def respond(self, message: str) -> str:
        return "Decision Simulator projecting consequences, trade-offs, and likely outcomes across multiple decision paths."


class ReputationGuardianAgent(Agent):
    def respond(self, message: str) -> str:
        return "Reputation Guardian evaluating reputational consequences, public image risk, and positioning impact."


class IntelligenceBriefingAgent(Agent):
    def respond(self, message: str) -> str:
        return "Intelligence Briefing agent preparing concise strategic briefings on risks, opportunities, priorities, and signals."


registry.register(ChiefOfStaffAgent("chief_of_staff", "Chief of Staff", "core", "Executive coordination"))
registry.register(StrategistAgent("strategist", "Strategist", "core", "Strategic reasoning"))
registry.register(RiskAnalystAgent("risk_analyst", "Risk Analyst", "core", "Risk evaluation"))
registry.register(LifeStrategistAgent("life_strategist", "Life Strategist", "core", "Long-term life optimization"))
registry.register(CognitiveBiasDetectorAgent("cognitive_bias_detector", "Cognitive Bias Detector", "core", "Bias detection"))
registry.register(DecisionSimulatorAgent("decision_simulator", "Decision Simulator", "core", "Scenario simulation"))
registry.register(ReputationGuardianAgent("reputation_guardian", "Reputation Guardian", "core", "Reputation protection"))
registry.register(IntelligenceBriefingAgent("intelligence_briefing", "Intelligence Briefing", "core", "Briefings"))

registry.register(TraderAgent("trader", "Trader", "finance", "Trading intelligence"))
registry.register(StrategicInvestmentAgent("strategic_investment", "Strategic Investment", "finance", "Macro investing"))
registry.register(PortfolioManagerAgent("portfolio_manager", "Portfolio Manager", "finance", "Portfolio strategy"))
registry.register(TaxStrategistColombiaGlobalAgent("tax_strategist_colombia_global", "Tax Strategist", "finance", "Tax optimization"))
registry.register(AccountingOperationsAgent("accounting_operations", "Accounting Operations", "finance", "Accounting support"))
registry.register(OpportunityRadarAgent("opportunity_radar", "Opportunity Radar", "finance", "Opportunity discovery"))
registry.register(CrisisSimulatorAgent("crisis_simulator", "Crisis Simulator", "finance", "Scenario stress testing"))

registry.register(LawyerAgent("lawyer", "Lawyer", "legal", "Legal review"))

registry.register(ChiefMedicalAdvisorAgent("chief_medical_advisor", "Chief Medical Advisor", "medical", "Primary health advisor"))
registry.register(FamilyDoctorAgent("family_doctor", "Family Doctor", "medical", "General medicine"))
registry.register(BiometricsAnalyzerAgent("biometrics_analyzer", "Biometrics Analyzer", "medical", "Health metrics"))
registry.register(FitnessCoachAgent("fitness_coach", "Fitness Coach", "medical", "Training strategy"))
registry.register(NutritionistAgent("nutritionist", "Nutritionist", "medical", "Nutrition strategy"))
registry.register(SleepOptimizerAgent("sleep_optimizer", "Sleep Optimizer", "medical", "Sleep optimization"))
registry.register(LongevityStrategistAgent("longevity_strategist", "Longevity Strategist", "medical", "Longevity"))
registry.register(SupplementAdvisorAgent("supplement_advisor", "Supplement Advisor", "medical", "Supplements"))

registry.register(StyleAdvisorAgent("style_advisor", "Style Advisor", "lifestyle", "Style advice"))
registry.register(TravelConciergeAgent("travel_concierge", "Travel Concierge", "lifestyle", "Travel planning"))

registry.register(GolfCaddyAIAgent("golf_caddy_ai", "Golf Caddy AI", "golf", "Golf strategy"))
registry.register(SwingAnalyzerAgent("swing_analyzer", "Swing Analyzer", "golf", "Swing analysis"))

registry.register(ResearchLibrarianAgent("research_librarian", "Research Librarian", "knowledge", "Research"))
registry.register(ImageAnalyzerAgent("image_analyzer", "Image Analyzer", "media", "Image analysis"))
registry.register(VideoAnalyzerAgent("video_analyzer", "Video Analyzer", "media", "Video analysis"))
