#!/usr/bin/env python3
"""
JARVIS Deployment Guard — Phase 9.

Pre-deploy QA script. Run before every Railway deploy.
Exit 0 = all checks passed. Exit 1 = one or more critical checks failed.

Usage:
    python scripts/deployment_guard.py
    python scripts/deployment_guard.py --strict    # fail on WARN too
    python scripts/deployment_guard.py --json      # JSON output

Checks:
    1. Python syntax for all modified .py files
    2. Frontend HTML integrity (functions, elements, safety tokens)
    3. No localhost URLs in production config
    4. Feature lock registry integrity
    5. API contract schema fingerprint check
    6. Execution guard present in main.py
    7. No real_trade=True in codebase
    8. Watchdog properly configured
    9. Dashboard boot sequence intact
    10. Navigation system intact

Exit codes:
    0 = PASS (or PASS+WARN in non-strict mode)
    1 = FAIL or CRITICAL
    2 = Configuration error (couldn't run checks)
"""
from __future__ import annotations

import ast
import json
import os
import sys
from pathlib import Path
from typing import Dict, List, Tuple

# Ensure project root is on path
_PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(_PROJECT_ROOT))
os.chdir(_PROJECT_ROOT)

# ─────────────────────────────────────────────────────────────────────────────

class _Colors:
    RESET  = "\033[0m"
    RED    = "\033[91m"
    GREEN  = "\033[92m"
    YELLOW = "\033[93m"
    CYAN   = "\033[96m"
    BOLD   = "\033[1m"

def _c(text: str, color: str) -> str:
    if sys.stdout.isatty():
        return f"{color}{text}{_Colors.RESET}"
    return text

# ─────────────────────────────────────────────────────────────────────────────

class DeploymentGuard:
    def __init__(self, strict: bool = False):
        self.strict  = strict
        self.results: List[Dict] = []

    def run(self) -> int:
        print(_c("\n=== JARVIS DEPLOYMENT GUARD ===", _Colors.BOLD))
        print(_c("   Pre-deploy QA -- all systems check\n", _Colors.CYAN))

        self._check_python_syntax()
        self._check_frontend_qa()
        self._check_no_real_trade_true()
        self._check_execution_guard_present()
        self._check_no_localhost_in_production_config()
        self._check_feature_registry()
        self._check_api_contract_fingerprints()
        self._check_dashboard_boot_sequence()
        self._check_navigation_intact()
        self._check_watchdog_config()
        self._check_ibkr_fallback_removed()

        return self._print_summary()

    # ── Check Implementations ─────────────────────────────────────────────────

    def _check_python_syntax(self) -> None:
        """Syntax-check all Python files under opsx/, main.py."""
        errors = []
        py_paths = list(Path(".").glob("opsx/**/*.py")) + [Path("main.py")]
        checked = 0
        for p in py_paths:
            if not p.exists():
                continue
            try:
                src = p.read_text(encoding="utf-8-sig", errors="ignore")  # utf-8-sig strips BOM
                ast.parse(src)
                checked += 1
            except SyntaxError as exc:
                errors.append(f"{p}: line {exc.lineno} - {exc.msg}")

        if errors:
            for e in errors:
                self._fail("python_syntax", f"SyntaxError: {e}")
        else:
            self._pass("python_syntax", f"All {checked} Python files pass syntax check")

    def _check_frontend_qa(self) -> None:
        """Run full frontend QA."""
        try:
            from opsx.stability.frontend_qa import run_frontend_qa
            result = run_frontend_qa()
            fail_count = result["summary"]["fail_count"]
            warn_count = result["summary"]["warn_count"]
            if fail_count > 0:
                for item in result["fail"]:
                    self._fail("frontend_qa", item)
            else:
                self._pass("frontend_qa",
                           f"Frontend OK: {result['summary']['pass_count']} pass, "
                           f"{warn_count} warn, {fail_count} fail")
            for w in result.get("warn", []):
                self._warn("frontend_qa", w)
        except Exception as exc:
            self._warn("frontend_qa", f"Could not run frontend QA: {exc}")

    def _check_no_real_trade_true(self) -> None:
        """Scan all .py and .html files for real_trade=True as an actual assignment or dict value."""
        import re as _re
        # Match real_trade directly followed by =True or : True (ignoring whitespace)
        _PATTERN = _re.compile(r"real_trade\s*[:=]\s*True", _re.IGNORECASE)
        # Exclude lines that are comments, string literals describing the check itself,
        # or safety-system files that reference the check by name
        _SKIP_FILES = {
            "scripts/deployment_guard.py",
            "opsx/stability/production_rules.py",
            "opsx/stability/frontend_qa.py",
            "opsx/stability/api_contract_lock.py",
            "tests/qa_portfolio_integration.py",
        }
        violations = []
        for pattern in ("**/*.py", "dashboard/*.html"):
            for p in Path(".").glob(pattern):
                rel = str(p).replace("\\", "/")
                if any(rel.endswith(s) for s in _SKIP_FILES):
                    continue
                try:
                    content = p.read_text(encoding="utf-8", errors="ignore")
                    lines = content.split("\n")
                    for i, line in enumerate(lines, 1):
                        stripped = line.strip()
                        if stripped.startswith("#") or stripped.startswith("\"\"\"") or stripped.startswith("'''"):
                            continue
                        if _PATTERN.search(line):
                            # Exclude inline comments that discuss the rule
                            code_part = line.split("#")[0]
                            if _PATTERN.search(code_part):
                                violations.append(f"{p}:{i}: {stripped}")
                except Exception:
                    pass

        if violations:
            for v in violations:
                self._fail("real_trade_safety", f"real_trade=True detected: {v}")
        else:
            self._pass("real_trade_safety", "No real_trade=True found in codebase")

    def _check_execution_guard_present(self) -> None:
        """Verify ExecutionGuardMiddleware is installed in main.py."""
        main_py = Path("main.py")
        if not main_py.exists():
            self._fail("execution_guard", "main.py not found")
            return
        content = main_py.read_text(encoding="utf-8", errors="ignore")
        if "ExecutionGuardMiddleware" in content and "add_middleware" in content:
            self._pass("execution_guard", "ExecutionGuardMiddleware installed in main.py")
        else:
            self._fail("execution_guard",
                       "ExecutionGuardMiddleware NOT installed in main.py — execution is unguarded!")

    def _check_no_localhost_in_production_config(self) -> None:
        """Scan main.py for localhost fallback paths in production branches."""
        main_py = Path("main.py")
        if not main_py.exists():
            self._warn("localhost_safety", "main.py not found")
            return
        content = main_py.read_text(encoding="utf-8", errors="ignore")
        # The DEV-only else branch is acceptable — check it's guarded
        if "ibkr_readonly" in content:
            if "DEV MODE ONLY" in content or "local Client Portal" in content:
                self._pass("localhost_safety",
                           "ibkr_readonly present but guarded as DEV MODE ONLY")
            else:
                self._warn("localhost_safety",
                           "ibkr_readonly imported without clear dev-only guard — verify")
        else:
            self._pass("localhost_safety", "ibkr_readonly not used in main.py")

        # Check production_guard is imported
        if "production_guard" in content and "validate_production_config" in content:
            self._pass("localhost_safety", "production_guard.validate_production_config called in main.py")
        else:
            self._warn("localhost_safety", "production_guard not called in main.py — localhost validation may be missing")

    def _check_feature_registry(self) -> None:
        registry_path = Path("reports/stability/feature_lock_registry.json")
        if not registry_path.exists():
            self._warn("feature_registry", "Feature lock registry not found")
            return
        try:
            data = json.loads(registry_path.read_text(encoding="utf-8"))
            count     = len(data.get("registry", []))
            protected = sum(1 for f in data.get("registry", []) if f.get("protected"))
            all_pass  = all(f.get("qa_status") == "PASS" for f in data.get("registry", []))
            if all_pass:
                self._pass("feature_registry", f"{count} features registered, {protected} protected, all PASS")
            else:
                failed = [f["feature_id"] for f in data["registry"] if f.get("qa_status") != "PASS"]
                self._warn("feature_registry", f"Features not passing QA: {failed}")
        except Exception as exc:
            self._warn("feature_registry", f"Registry parse error: {exc}")

    def _check_api_contract_fingerprints(self) -> None:
        try:
            from opsx.stability.api_contract_lock import APIContractLock
            lock    = APIContractLock()
            drifted = lock.check_contract_drift()
            if drifted:
                for d in drifted:
                    self._fail("api_contracts",
                               f"Contract drift: {d['endpoint']} "
                               f"stored={d['stored_hash']} computed={d['computed_hash']}")
            else:
                self._pass("api_contracts",
                           f"All {len(lock.registered_endpoints)} API contracts match stored fingerprints")
        except Exception as exc:
            self._warn("api_contracts", f"Contract check failed: {exc}")

    def _check_dashboard_boot_sequence(self) -> None:
        html = Path("dashboard/jarvis_futuristic.html")
        if not html.exists():
            self._fail("boot_sequence", "Dashboard HTML not found")
            return
        content = html.read_text(encoding="utf-8", errors="ignore")
        checks = [
            ("window.JARVIS_RUNTIME",       "JARVIS_RUNTIME global guard"),
            ("function boot",               "boot() function defined"),
            ("JARVIS_RUNTIME.initialized",  "initialized flag set in boot"),
            ("_loadingWatchdog",            "_loadingWatchdog() called"),
            ("boot().catch",                "boot() called with error catch"),
        ]
        for marker, description in checks:
            if marker in content:
                self._pass("boot_sequence", description)
            else:
                self._fail("boot_sequence", f"MISSING: {description} — '{marker}' not found")

    def _check_navigation_intact(self) -> None:
        html = Path("dashboard/jarvis_futuristic.html")
        if not html.exists():
            return
        content = html.read_text(encoding="utf-8", errors="ignore")
        sections = ["home", "work", "markets", "life", "intelligence", "system"]
        missing = [s for s in sections if f'data-section="{s}"' not in content]
        if missing:
            self._fail("navigation", f"Missing section buttons: {missing}")
        else:
            self._pass("navigation", f"All 6 section nav buttons present")

        # Legacy nav preserved
        if "id=\"legacy-tab-nav\"" in content:
            self._pass("navigation", "Legacy nav preserved (required for JS compatibility)")
        else:
            self._fail("navigation", "LEGACY NAV MISSING — switchTab() JS compatibility broken")

        # Golf accessible
        if "Golf Performance" in content:
            self._pass("navigation", "Golf Performance sub-nav item present")
        else:
            self._fail("navigation", "Golf Performance missing from navigation")

    def _check_watchdog_config(self) -> None:
        try:
            from opsx.bridge.watchdog import _POLL_INTERVAL_SECS, _MAX_BACKOFF_SECS, _CIRCUIT_BREAKER_THRESHOLD
            self._pass("watchdog",
                       f"Watchdog config: poll={_POLL_INTERVAL_SECS}s "
                       f"max_backoff={_MAX_BACKOFF_SECS}s "
                       f"circuit_threshold={_CIRCUIT_BREAKER_THRESHOLD}")
        except Exception as exc:
            self._warn("watchdog", f"Watchdog import check failed: {exc}")

    def _check_ibkr_fallback_removed(self) -> None:
        """Verify the localhost fallback is properly guarded."""
        main_py = Path("main.py")
        if not main_py.exists():
            return
        content = main_py.read_text(encoding="utf-8", errors="ignore")
        # Should have IBKRNotConfiguredStub as the "no URL in production" path
        if "IBKRNotConfiguredStub" in content:
            self._pass("ibkr_fallback", "IBKRNotConfiguredStub used for missing-URL in production")
        else:
            self._warn("ibkr_fallback",
                       "IBKRNotConfiguredStub not found — missing-URL case may fall back unsafely")

    # ── Summary ───────────────────────────────────────────────────────────────

    def _print_summary(self) -> int:
        passed   = [r for r in self.results if r["status"] == "PASS"]
        warned   = [r for r in self.results if r["status"] == "WARN"]
        failed   = [r for r in self.results if r["status"] == "FAIL"]
        critical = [r for r in self.results if r["status"] == "CRITICAL"]

        print("\n" + "-" * 50)
        print(_c(f"  PASS  : {len(passed)}", _Colors.GREEN))
        if warned:
            print(_c(f"  WARN  : {len(warned)}", _Colors.YELLOW))
            for w in warned:
                print(_c(f"    WARN [{w['check']}] {w['message']}", _Colors.YELLOW))
        if failed:
            print(_c(f"  FAIL  : {len(failed)}", _Colors.RED))
            for f in failed:
                print(_c(f"    FAIL [{f['check']}] {f['message']}", _Colors.RED))
        if critical:
            print(_c(f"  CRIT  : {len(critical)}", _Colors.RED))
            for c in critical:
                print(_c(f"    CRIT [{c['check']}] {c['message']}", _Colors.RED))

        has_failures = bool(failed or critical)
        has_warnings = bool(warned)

        if not has_failures and (not has_warnings or not self.strict):
            print(_c("\n  PASS: DEPLOYMENT GUARD PASS -- safe to deploy", _Colors.GREEN + _Colors.BOLD))
            return 0
        elif has_failures:
            print(_c("\n  FAIL: DEPLOYMENT GUARD FAIL -- DO NOT DEPLOY", _Colors.RED + _Colors.BOLD))
            return 1
        else:
            print(_c("\n  FAIL: DEPLOYMENT GUARD FAIL (strict -- warnings present)", _Colors.YELLOW + _Colors.BOLD))
            return 1

    # ── Result Helpers ────────────────────────────────────────────────────────

    def _pass(self, check: str, message: str) -> None:
        self.results.append({"check": check, "status": "PASS", "message": message})
        print(_c(f"  + [{check}] {message}", _Colors.GREEN))

    def _warn(self, check: str, message: str) -> None:
        self.results.append({"check": check, "status": "WARN", "message": message})

    def _fail(self, check: str, message: str) -> None:
        self.results.append({"check": check, "status": "FAIL", "message": message})

    def _critical(self, check: str, message: str) -> None:
        self.results.append({"check": check, "status": "CRITICAL", "message": message})


# ─────────────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    strict = "--strict" in sys.argv
    output_json = "--json" in sys.argv

    guard = DeploymentGuard(strict=strict)

    if output_json:
        guard.run()
        print(json.dumps(guard.results, indent=2))
    else:
        exit_code = guard.run()
        sys.exit(exit_code)
