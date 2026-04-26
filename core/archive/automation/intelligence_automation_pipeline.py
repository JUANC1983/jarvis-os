from datetime import datetime
from core.audit_engine import AuditEngine
from core.news_intelligence_engine import NewsIntelligenceEngine
from core.global_intelligence_engine import GlobalIntelligenceEngine
from core.narrative_detection_engine import NarrativeDetectionEngine
from core.macro_regime_engine import MacroRegimeEngine
from core.opportunity_radar_engine import OpportunityRadarEngine
from core.alert_engine import AlertEngine

class IntelligenceAutomationPipeline:

    def __init__(self):

        self.audit=AuditEngine()

        self.news=NewsIntelligenceEngine()

        self.global_engine=GlobalIntelligenceEngine()

        self.narratives=NarrativeDetectionEngine()

        self.regime=MacroRegimeEngine()

        self.radar=OpportunityRadarEngine()

        self.alerts=AlertEngine()

    def run(self):

        news=self.news.fetch_news()

        narrative_scan=self.narratives.analyze("global markets")

        regime_scan=self.regime.analyze("macro")

        radar=self.radar.scan("global macro","market regime")

        alerts=self.alerts.evaluate()

        result={
            "timestamp":datetime.utcnow().isoformat(),
            "news_items":len(news),
            "dominant_narratives":narrative_scan["dominant_narratives"],
            "macro_regime":regime_scan["regime"],
            "opportunities":radar["opportunities"],
            "alerts_triggered":alerts["triggered"]
        }

        self.audit.log_event("automation_intelligence_pipeline",result)

        return result
