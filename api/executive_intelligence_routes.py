from fastapi import APIRouter

from core.strategic_foresight_engine import StrategicForesightEngine
from core.legal_compliance_engine import LegalComplianceEngine
from core.accounting_intelligence_engine import AccountingIntelligenceEngine

router = APIRouter(prefix="/executive-intel", tags=["executive-intelligence"])

foresight_engine = StrategicForesightEngine()
legal_engine = LegalComplianceEngine()
accounting_engine = AccountingIntelligenceEngine()


@router.post("/foresight")
def foresight(payload: dict):
    topic = payload.get("topic", "")
    context = payload.get("context", "")
    return foresight_engine.simulate(topic=topic, context=context)


@router.post("/legal")
def legal(payload: dict):
    query = payload.get("query", "")
    return legal_engine.analyze(query=query)


@router.post("/accounting/financials")
def accounting_financials(payload: dict):
    return accounting_engine.analyze_financials(payload)


@router.post("/accounting/policy")
def accounting_policy(payload: dict):
    query = payload.get("query", "")
    return accounting_engine.accounting_policy_view(query=query)
