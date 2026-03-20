from __future__ import annotations

import os
from pathlib import Path
from typing import Any, Dict, List
from urllib.parse import urlparse

import pyautogui
from playwright.sync_api import sync_playwright


class ComputerControlPremium:
    def __init__(self) -> None:
        self.audit_log = Path("logs/computer_control.jsonl")
        self.audit_log.parent.mkdir(parents=True, exist_ok=True)
        self.enabled = os.getenv("JARVIS_COMPUTER_CONTROL_ENABLED", "false").lower() == "true"
        self.default_dry_run = os.getenv("JARVIS_COMPUTER_CONTROL_DRY_RUN", "true").lower() == "true"
        self.allowed_domains = [
            d.strip() for d in os.getenv("JARVIS_ALLOWED_DOMAINS", "localhost,127.0.0.1,google.com").split(",")
            if d.strip()
        ]
        pyautogui.FAILSAFE = True

    def _log(self, event: Dict[str, Any]) -> None:
        with self.audit_log.open("a", encoding="utf-8") as f:
            f.write(str(event) + "\n")

    def _domain_allowed(self, url: str, allowed_domain: str = "") -> bool:
        parsed = urlparse(url)
        host = parsed.netloc.lower()
        if allowed_domain:
            return allowed_domain.lower() in host
        return any(d.lower() in host for d in self.allowed_domains)

    def browser_task(self, url: str, task: str = "open", selectors: List[str] | None = None, text: str = "", dry_run: bool | None = None, allowed_domain: str = "") -> Dict[str, Any]:
        selectors = selectors or []
        dry_run = self.default_dry_run if dry_run is None else dry_run

        if not self.enabled:
            return {"status": "blocked", "reason": "computer control disabled by env"}

        if not self._domain_allowed(url, allowed_domain):
            return {"status": "blocked", "reason": "domain not allowed", "url": url}

        event = {
            "type": "browser_task",
            "url": url,
            "task": task,
            "selectors": selectors,
            "text": text,
            "dry_run": dry_run,
        }
        self._log(event)

        if dry_run:
            return {"status": "dry_run", "event": event}

        with sync_playwright() as p:
            browser = p.chromium.launch(headless=False)
            context = browser.new_context()
            page = context.new_page()
            page.goto(url)

            if task == "open":
                result = {"status": "ok", "title": page.title()}

            elif task == "click" and selectors:
                page.locator(selectors[0]).click()
                result = {"status": "ok", "clicked": selectors[0]}

            elif task == "fill" and selectors:
                page.locator(selectors[0]).fill(text)
                result = {"status": "ok", "filled": selectors[0], "text": text}

            elif task == "screenshot":
                output = "logs/browser_task.png"
                page.screenshot(path=output)
                result = {"status": "ok", "screenshot": output}

            else:
                result = {"status": "error", "reason": "unsupported browser task"}

            context.close()
            browser.close()
            return result

    def desktop_task(self, action: str, x: int | None = None, y: int | None = None, text: str = "", image_path: str = "", dry_run: bool | None = None) -> Dict[str, Any]:
        dry_run = self.default_dry_run if dry_run is None else dry_run

        if not self.enabled:
            return {"status": "blocked", "reason": "computer control disabled by env"}

        event = {
            "type": "desktop_task",
            "action": action,
            "x": x,
            "y": y,
            "text": text,
            "image_path": image_path,
            "dry_run": dry_run,
        }
        self._log(event)

        if dry_run:
            return {"status": "dry_run", "event": event}

        if action == "click" and x is not None and y is not None:
            pyautogui.click(x, y)
            return {"status": "ok", "action": "click", "x": x, "y": y}

        if action == "write":
            pyautogui.write(text, interval=0.02)
            return {"status": "ok", "action": "write", "text": text}

        if action == "hotkey":
            keys = [k.strip() for k in text.split("+") if k.strip()]
            pyautogui.hotkey(*keys)
            return {"status": "ok", "action": "hotkey", "keys": keys}

        if action == "screenshot":
            output = "logs/desktop_task.png"
            pyautogui.screenshot(output)
            return {"status": "ok", "screenshot": output}

        return {"status": "error", "reason": "unsupported desktop task"}
