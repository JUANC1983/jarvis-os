from fastapi import APIRouter

from core.computer_control_premium import ComputerControlPremium
from core.autonomous_execution_engine import AutonomousExecutionEngine

router = APIRouter(prefix="/computer-control", tags=["computer-control"])
computer = ComputerControlPremium()
autoexec = AutonomousExecutionEngine()


@router.post("/browser")
def browser(payload: dict):
    return computer.browser_task(
        url=payload.get("url", ""),
        task=payload.get("task", "open"),
        selectors=payload.get("selectors", []),
        text=payload.get("text", ""),
        dry_run=payload.get("dry_run", True),
        allowed_domain=payload.get("allowed_domain", ""),
    )


@router.post("/desktop")
def desktop(payload: dict):
    return computer.desktop_task(
        action=payload.get("action", ""),
        x=payload.get("x"),
        y=payload.get("y"),
        text=payload.get("text", ""),
        image_path=payload.get("image_path", ""),
        dry_run=payload.get("dry_run", True),
    )


@router.post("/autonomous/run")
def autonomous_run(payload: dict):
    return autoexec.run(
        mission=payload.get("mission", ""),
        payload=payload.get("payload", {}),
        dry_run=payload.get("dry_run", True),
    )
