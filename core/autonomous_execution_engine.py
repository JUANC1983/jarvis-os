from __future__ import annotations

from typing import Any, Dict, List

from core.agent_orchestrator_pro import AgentOrchestratorPro
from core.computer_control_premium import ComputerControlPremium


class AutonomousExecutionEngine:
    def __init__(self) -> None:
        self.orchestrator = AgentOrchestratorPro()
        self.computer = ComputerControlPremium()

    def propose(self, mission: str, payload: Dict[str, Any]) -> Dict[str, Any]:
        domain = payload.get("domain", "general")
        routing = self.orchestrator.route(domain)

        plan = {
            "mission": mission,
            "domain": domain,
            "primary_agent": routing["primary_agent"],
            "steps": [],
        }

        if mission == "web_research_open":
            plan["steps"] = [
                {"type": "browser", "task": "open", "url": payload.get("url", "")},
                {"type": "browser", "task": "screenshot", "url": payload.get("url", "")},
            ]
        elif mission == "desktop_capture":
            plan["steps"] = [
                {"type": "desktop", "action": "screenshot"},
            ]
        else:
            plan["steps"] = [
                {"type": "analysis", "note": "No autonomous execution template matched yet."}
            ]

        return plan

    def run(self, mission: str, payload: Dict[str, Any], dry_run: bool = True) -> Dict[str, Any]:
        plan = self.propose(mission, payload)
        results: List[Dict[str, Any]] = []

        for step in plan["steps"]:
            if step["type"] == "browser":
                results.append(
                    self.computer.browser_task(
                        url=step.get("url", ""),
                        task=step.get("task", "open"),
                        dry_run=dry_run,
                    )
                )
            elif step["type"] == "desktop":
                results.append(
                    self.computer.desktop_task(
                        action=step.get("action", ""),
                        dry_run=dry_run,
                    )
                )
            else:
                results.append({"status": "ok", "note": step.get("note", "")})

        return {
            "plan": plan,
            "results": results,
            "dry_run": dry_run,
        }
