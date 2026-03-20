from fastapi import APIRouter

from core.strategic_command_center import StrategicCommandCenter

router = APIRouter(prefix="/command-center", tags=["command-center"])
command_center = StrategicCommandCenter()


@router.post("/run")
def run_command_center(payload: dict):
    topic = payload.get("topic", "")
    domain = payload.get("domain", "general")
    context = payload.get("context", "")
    return command_center.run(topic=topic, domain=domain, context=context)


@router.post("/finance")
def run_finance_command_center(payload: dict):
    topic = payload.get("topic", "")
    context = payload.get("context", "")
    return command_center.run(topic=topic, domain="finance", context=context)


@router.post("/health")
def run_health_command_center(payload: dict):
    topic = payload.get("topic", "")
    context = payload.get("context", "")
    return command_center.run(topic=topic, domain="health", context=context)


@router.post("/life")
def run_life_command_center(payload: dict):
    topic = payload.get("topic", "")
    context = payload.get("context", "")
    return command_center.run(topic=topic, domain="life", context=context)
