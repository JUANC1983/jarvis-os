from fastapi import APIRouter
from core.jarvis_operator import JarvisOperator

router = APIRouter(prefix="/operator")

operator = JarvisOperator()

@router.post("/open-app")

def open_app(payload:dict):

    return operator.open_app(payload["app"])


@router.post("/open-url")

def open_url(payload:dict):

    return operator.open_url(payload["url"])


@router.post("/command")

def run_command(payload:dict):

    return operator.run_command(payload["cmd"])
