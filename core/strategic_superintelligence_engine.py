from core.global_signal_engine import GlobalSignalEngine
from core.macro_liquidity_engine import MacroLiquidityEngine
from core.opportunity_discovery_engine import OpportunityDiscoveryEngine
from core.global_opportunity_radar import GlobalOpportunityRadar
from core.portfolio_brain import PortfolioBrain
from core.asset_allocation_engine import AssetAllocationEngine
from core.geopolitical_engine import GeopoliticalRiskEngine
from core.wealth_strategist import WealthStrategist
from core.life_strategy_engine import LifeStrategyEngine


class StrategicSuperintelligenceEngine:

    def __init__(self):

        self.signals = GlobalSignalEngine()
        self.liquidity = MacroLiquidityEngine()
        self.discovery = OpportunityDiscoveryEngine()
        self.radar = GlobalOpportunityRadar()
        self.portfolio = PortfolioBrain()
        self.allocation = AssetAllocationEngine()
        self.geopolitics = GeopoliticalRiskEngine()
        self.wealth = WealthStrategist()
        self.life = LifeStrategyEngine()


    def strategic_brain(self, context):

        report = {}

        try:
            report["global_signals"] = self.signals.detect_signals()
        except:
            report["global_signals"] = []

        try:
            report["macro_liquidity"] = self.liquidity.analyze()
        except:
            report["macro_liquidity"] = {}

        try:
            report["opportunities"] = self.discovery.scan()
        except:
            report["opportunities"] = []

        try:
            report["global_radar"] = self.radar.scan()
        except:
            report["global_radar"] = []

        try:
            report["geopolitical_risks"] = self.geopolitics.analyze(context)
        except:
            report["geopolitical_risks"] = []

        return report


    def master_decision(self, context, portfolio=None, risk_profile="balanced"):

        intelligence = self.strategic_brain(context)

        strategy = {}

        try:
            strategy["wealth_strategy"] = self.wealth.strategy("build wealth")
        except:
            strategy["wealth_strategy"] = {}

        try:
            strategy["allocation"] = self.allocation.recommend(risk_profile)
        except:
            strategy["allocation"] = {}

        portfolio_analysis = {}

        if portfolio:

            try:
                portfolio_analysis["structure"] = self.portfolio.analyze_portfolio(portfolio)
                portfolio_analysis["risk"] = self.portfolio.risk_estimate(portfolio)
            except:
                pass

        return {

            "strategic_intelligence": intelligence,

            "recommended_strategy": strategy,

            "portfolio_analysis": portfolio_analysis,

            "strategic_summary":
            "Jarvis strategic layer synthesized macro signals, opportunities, and risk structures to generate high level decision guidance."

        }
