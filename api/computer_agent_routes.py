from fastapi import APIRouter
from core.computer_control_agent import ComputerControlAgent

router = APIRouter(
    prefix="/computer",
    tags=["computer-control"]
)

agent = ComputerControlAgent()


@router.post("/open-app")
def open_app(payload: dict):

    app = payload.get("app")

    return agent.open_app(app)


@router.post("/open-url")
def open_url(payload: dict):

    url = payload.get("url")

    return agent.open_url(url)


@router.post("/run-command")
def run_command(payload: dict):

    cmd = payload.get("cmd")

    return agent.run_command(cmd)
