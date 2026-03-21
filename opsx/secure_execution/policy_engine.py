from typing import Dict, Tuple
from opsx.secure_execution.schemas import RiskLevel, TaskRequest

ALLOWED_ACTIONS = {
    "desktop": {"open_app"},
    "browser": {"open_url"},
    "filesystem": {"read_text", "write_text"},
    "trading": {"simulate"},
}

ALLOWED_APPS = {
    "notepad": "notepad",
    "calculator": "calc",
    "chrome": "start chrome",
}

BLOCKED_CAPABILITIES = {
    "trading.place_order",
    "trading.real_order",
    "system.shell",
    "system.delete",
    "system.install",
    "system.shutdown",
}

def classify_risk(task: TaskRequest) -> RiskLevel:
    cap = task.capability.lower()
    act = task.action.lower()

    if cap.startswith("trading"):
        return RiskLevel.critical
    if cap.startswith("filesystem"):
        return RiskLevel.high
    if cap.startswith("browser"):
        return RiskLevel.medium
    if cap.startswith("desktop"):
        return RiskLevel.low
    return RiskLevel.high

def requires_approval(task: TaskRequest) -> bool:
    return classify_risk(task) in {RiskLevel.medium, RiskLevel.high, RiskLevel.critical}

def validate_task(task: TaskRequest) -> Tuple[bool, str]:
    cap = task.capability.lower()
    act = task.action.lower()

    if cap in BLOCKED_CAPABILITIES:
        return False, "capability blocked by policy"

    family = cap.split(".")[0]
    if family not in ALLOWED_ACTIONS:
        return False, "capability family not allowed"

    if act not in ALLOWED_ACTIONS[family]:
        return False, "action not allowed for capability family"

    if cap == "desktop.open_app":
        app = str(task.args.get("app", "")).lower().strip()
        if app not in ALLOWED_APPS:
            return False, "app not in allowlist"

    if cap == "browser.open_url":
        url = str(task.args.get("url", "")).strip().lower()
        if not (url.startswith("https://") or url.startswith("http://")):
            return False, "url must start with http/https"

    if cap == "filesystem.write_text":
        path = str(task.args.get("path", "")).strip()
        if ".." in path or ":" in path or path.startswith("/") or path.startswith("\\"):
            return False, "path escapes sandbox"

    if cap == "filesystem.read_text":
        path = str(task.args.get("path", "")).strip()
        if ".." in path or ":" in path or path.startswith("/") or path.startswith("\\"):
            return False, "path escapes sandbox"

    if cap == "trading.simulate":
        return False, "trading execution blocked in secure executor; simulation should stay in analytics/trader service"

    return True, "ok"
