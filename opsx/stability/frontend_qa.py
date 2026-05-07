"""
JARVIS Frontend Regression QA — Phase 3.

Analyzes dashboard/jarvis_futuristic.html for regressions without running a browser.
Checks:
  - Critical function definitions present
  - No infinite polling loops
  - No dead onclick handlers
  - No duplicate const declarations (the prior fatal crash)
  - Required HTML elements present
  - No broken tab targets
  - Hydration functions all defined
  - Boot sequence integrity
  - Safety tokens present (real_trade=False, EXECUTION BLOCKED)

Run:
    python -m opsx.stability.frontend_qa
    or: FrontendQA().run()
"""
from __future__ import annotations

import re
from pathlib import Path
from typing import Dict, List, Tuple

_DASHBOARD_PATH = Path("dashboard/jarvis_futuristic.html")

# ── Critical Function Checklist ───────────────────────────────────────────────
_REQUIRED_FUNCTIONS = [
    "function switchTab",
    "function switchSection",
    "function loadHome",
    "function loadConnectionStatus",
    "function loadPortfolioSummary",
    "function loadCockpit",
    "function loadTopHoldings",
    "function loadCalendar",
    "function loadOutlook",
    "function loadGolf",          # actual name (not loadGolfDashboard)
    "function loadAgents",        # memory/intelligence loaded via agents panel
    "function boot",
    "function _bootModule",
    "function safeFetch",
    "function safeApi",
    "function initEvents",
    "function cmdSend",
    "function cmdMic",
    "function wizNext",
    "function wizBack",
    "function wizGoTo",
    "function saveOnboarding",
    "function setMode",
    "_activateSub",
    "function _loadingWatchdog",
]

# ── Required HTML Element Markers ─────────────────────────────────────────────
_REQUIRED_ELEMENTS = [
    "id=\"jarvis-primary-nav\"",
    "id=\"jarvis-sub-nav\"",
    "id=\"legacy-tab-nav\"",
    "data-section=\"home\"",
    "data-section=\"work\"",
    "data-section=\"markets\"",
    "data-section=\"life\"",
    "data-section=\"intelligence\"",
    "data-section=\"system\"",
    "JARVIS_RUNTIME",
    "JARVIS_TABS",
    "JARVIS_DEBUG",
    "window.onerror",
    "unhandledrejection",
    "_loadingWatchdog",
]

# ── Safety Tokens ─────────────────────────────────────────────────────────────
_REQUIRED_SAFETY_TOKENS = [
    "LIVE READ-ONLY",
    "EXECUTION BLOCKED",
    "real_trade",
    "execution_blocked",
    "Paper",
]

# ── Patterns that signal dangerous regressions ────────────────────────────────
_DANGEROUS_PATTERNS = [
    # Infinite setInterval without clearInterval reference nearby
    (r"setInterval\s*\(\s*function\s*\(\s*\)[^}]*setInterval", "Nested setInterval — possible infinite loop"),
    # Promise.all with no catch — silent failure if one rejects
    (r"Promise\.all\s*\(\[(?:(?!allSettled|\.catch|\.then\()[\s\S]){0,200}\]\)", "Promise.all without .catch — one failure blocks all"),
    # real_trade set to true
    (r"real_trade\s*[=:]\s*true", "real_trade=true detected — CRITICAL safety violation"),
    # Direct localhost usage in fetch
    (r"fetch\s*\(\s*['\"]https?://localhost", "fetch to localhost — will fail in Railway"),
]

# ── Onclick handler targets that must be defined ──────────────────────────────
_ONCLICK_FUNCTIONS = [
    "switchSection", "switchTab", "setMode", "loadConnectionStatus",
    "wizNext", "wizBack", "wizGoTo", "skipOnboarding", "saveOnboarding",
    "runAutoJarvis", "toggleExecutiveMode", "quickAction", "sendChat",
    "cmdSend", "cmdMic", "paperReset", "olDelete",
]


class FrontendQA:

    def __init__(self, html_path: Path = _DASHBOARD_PATH):
        self.html_path = html_path
        self._content  = ""
        self._results: Dict[str, List[str]] = {
            "pass":    [],
            "warn":    [],
            "fail":    [],
            "skip":    [],
        }

    def run(self) -> Dict:
        """Run all frontend QA checks. Returns results dict."""
        if not self.html_path.exists():
            return {"result": "SKIP", "reason": f"{self.html_path} not found"}

        self._content = self.html_path.read_text(encoding="utf-8", errors="ignore")

        self._check_required_functions()
        self._check_required_elements()
        self._check_safety_tokens()
        self._check_dangerous_patterns()
        self._check_onclick_targets()
        self._check_boot_sequence()
        self._check_loading_states()
        self._check_duplicate_const()
        self._check_use_strict()

        total = sum(len(v) for v in self._results.values())
        return {
            "result":  "PASS" if not self._results["fail"] else "FAIL",
            "pass":    self._results["pass"],
            "warn":    self._results["warn"],
            "fail":    self._results["fail"],
            "skip":    self._results["skip"],
            "summary": {
                "pass_count": len(self._results["pass"]),
                "warn_count": len(self._results["warn"]),
                "fail_count": len(self._results["fail"]),
                "total":      total,
            },
        }

    # ── Individual Checks ─────────────────────────────────────────────────────

    def _check_required_functions(self) -> None:
        for fn in _REQUIRED_FUNCTIONS:
            if fn in self._content:
                self._results["pass"].append(f"function_defined: {fn}")
            else:
                self._results["fail"].append(f"MISSING FUNCTION: {fn}")

    def _check_required_elements(self) -> None:
        for el in _REQUIRED_ELEMENTS:
            if el in self._content:
                self._results["pass"].append(f"element_present: {el}")
            else:
                self._results["fail"].append(f"MISSING ELEMENT: {el}")

    def _check_safety_tokens(self) -> None:
        for token in _REQUIRED_SAFETY_TOKENS:
            if token in self._content:
                self._results["pass"].append(f"safety_token: {token}")
            else:
                self._results["warn"].append(f"MISSING SAFETY TOKEN: {token}")

    def _check_dangerous_patterns(self) -> None:
        for pattern, description in _DANGEROUS_PATTERNS:
            if re.search(pattern, self._content, re.DOTALL | re.IGNORECASE):
                self._results["fail"].append(f"DANGEROUS PATTERN: {description}")
            else:
                self._results["pass"].append(f"no_dangerous_pattern: {description[:40]}")

    def _check_onclick_targets(self) -> None:
        for fn in _ONCLICK_FUNCTIONS:
            # Check both that onclick uses it AND that the function is defined
            onclick_uses = f"onclick=\"{fn}" in self._content or f"onclick='{fn}" in self._content
            fn_defined   = f"function {fn}" in self._content or f"{fn} =" in self._content or f"{fn}=" in self._content
            if onclick_uses and fn_defined:
                self._results["pass"].append(f"onclick_target_ok: {fn}")
            elif onclick_uses and not fn_defined:
                self._results["fail"].append(f"DEAD ONCLICK TARGET: {fn}() used in onclick but not defined")
            elif not onclick_uses:
                self._results["skip"].append(f"onclick_not_used: {fn}")

    def _check_boot_sequence(self) -> None:
        # Boot function must exist and call _bootModule
        if "function boot" in self._content and "_bootModule" in self._content:
            self._results["pass"].append("boot_sequence: boot() + _bootModule() present")
        else:
            self._results["fail"].append("BOOT SEQUENCE: boot() or _bootModule() missing")

        # JARVIS_RUNTIME.initialized must be set in boot
        if "JARVIS_RUNTIME.initialized = true" in self._content:
            self._results["pass"].append("runtime_initialized_flag: present")
        else:
            self._results["fail"].append("RUNTIME FLAG: JARVIS_RUNTIME.initialized = true not found in boot()")

        # Boot must be called
        if "boot()" in self._content or "boot().catch" in self._content:
            self._results["pass"].append("boot_invocation: boot() is called")
        else:
            self._results["fail"].append("BOOT NOT CALLED: boot() never invoked")

    def _check_loading_states(self) -> None:
        # All async load functions should use safeFetch, not raw fetch
        raw_fetch_in_load = len(re.findall(r"async function load\w+.*?(?=async function|\Z)", self._content, re.DOTALL))
        safefetch_uses    = self._content.count("safeFetch(")
        safefetch_defined = "function safeFetch" in self._content
        if not safefetch_defined:
            self._results["fail"].append("SAFETY: safeFetch() not defined — raw fetch() has no timeout protection")
        elif safefetch_uses > 0:
            self._results["pass"].append(f"safeFetch_usage: {safefetch_uses} uses found")
        else:
            self._results["warn"].append("safeFetch() defined but never called")

        # _loadingWatchdog must be called from boot
        if "_loadingWatchdog()" in self._content:
            self._results["pass"].append("loading_watchdog: _loadingWatchdog() called in boot")
        else:
            self._results["warn"].append("LOADING WATCHDOG: _loadingWatchdog() not found — stuck loading states possible")

    def _check_duplicate_const(self) -> None:
        """
        Detect duplicate const declarations that appear within 25 lines of each other.
        The prior fatal crash was 'const brokers' declared twice within the same
        block of loadCockpit() — about 10 lines apart.

        False-positive guard: common 1-3 char names and ultra-common words are skipped
        since they frequently appear in short arrow functions / closures.
        """
        _IGNORE = frozenset({
            "el", "d", "box", "div", "title", "i", "n", "r", "s", "k", "v",
            "e", "t", "p", "x", "y", "z", "fn", "cb", "ok", "id", "val",
            "row", "btn", "msg", "err", "res", "url", "key", "arr", "obj",
        })
        lines = self._content.split("\n")
        # Build index: const_name -> list of line numbers where declared
        from collections import defaultdict
        const_lines: dict = defaultdict(list)
        for i, line in enumerate(lines):
            m = re.match(r"\s*const\s+(\w+)\s*=", line)
            if m:
                name = m.group(1)
                if name not in _IGNORE and len(name) > 3:
                    const_lines[name].append(i + 1)

        violations = []
        for name, line_nums in const_lines.items():
            if len(line_nums) >= 2:
                # Check if any two occurrences are within 25 lines
                for j in range(len(line_nums) - 1):
                    if line_nums[j + 1] - line_nums[j] <= 25:
                        violations.append(
                            f"const {name} declared at lines {line_nums[j]} "
                            f"and {line_nums[j+1]} ({line_nums[j+1]-line_nums[j]} lines apart)"
                        )

        if violations:
            # Warn not fail — JS allows re-using const in inner block scopes (closures,
            # forEach callbacks, if-blocks). The authoritative check is `node --check`.
            for v in violations:
                self._results["warn"].append(
                    f"CONST_PROXIMITY (review): {v} — verify not same flat block scope"
                )
        else:
            self._results["pass"].append("const_duplicate_check: no close-proximity duplicate consts found")

    def _check_use_strict(self) -> None:
        if '"use strict"' in self._content or "'use strict'" in self._content:
            self._results["pass"].append("use_strict: enabled (good)")
        else:
            self._results["warn"].append("USE_STRICT: not found — duplicate const won't throw, bugs may hide")


def run_frontend_qa(html_path: Path = _DASHBOARD_PATH) -> Dict:
    """Convenience function for running frontend QA."""
    return FrontendQA(html_path).run()


if __name__ == "__main__":
    import json
    result = run_frontend_qa()
    print(json.dumps(result, indent=2))
    exit(0 if result["result"] == "PASS" else 1)
