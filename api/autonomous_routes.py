from fastapi import APIRouter
from core.autonomous_orchestrator import AutonomousOrchestrator

router = APIRouter()

brain = AutonomousOrchestrator()

@router.post("/jarvis/autonomous")

def autonomous(payload:dict):

    task = payload.get("task")

    return brain.run(task)
