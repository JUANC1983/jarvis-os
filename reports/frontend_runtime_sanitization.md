# Frontend Runtime Sanitization Report

Date: 2026-05-07
Mode: Safe patch
Primary file changed: `dashboard/jarvis_futuristic.html`

No backend auth, security middleware, IBKR connector selection, bridge token logic, production guard logic, or live/paper safety rules were modified.

## 1. Root Causes Found

- Critical hydration loaders still used `Promise.all`, so one failed endpoint could break a full panel.
- Several dashboard timers used direct `setInterval`, creating duplicate polling risk after re-init or tab activation.
- Runtime diagnostics existed in partial form but did not expose the requested request/interval state.
- Tab switching had a debounce but no stale pending-tab cleanup, which could lock a tab after rapid switching.
- Upload drag/drop listeners could be attached more than once if `initUpload()` reran.
- One mojibake regular expression in `_normalizeText()` was invalid in strict JS syntax checks.

## 2. Safe Patches Applied

- Added `window.JARVIS_RUNTIME_DIAGNOSTICS` with:
  - `activeRequests`
  - `failedRequests`
  - `activeIntervals`
  - `lastHydration`
  - `runtimeErrors`
- Instrumented `_fetchWithTimeout()` to update diagnostics without exposing secrets or tokens.
- Converted critical dashboard hydration groups from `Promise.all` to `Promise.allSettled`.
- Added fallback rendering for Paper Lab and AI Learning panel failures.
- Registered all critical dashboard intervals through `_registerInterval()`.
- Added `beforeunload` cleanup for registered intervals.
- Added idempotent tab button listener binding.
- Added idempotent upload drag/drop listener binding.
- Hardened tab switching against rapid-click stale loading locks.
- Replaced invalid mojibake regex range with ASCII-safe `[\u0300-\u036f]`.

## 3. Fetches Normalized

Critical fetch groups now use `_fetchWithTimeout()` and partial failure handling:

- Paper Lab analytics:
  - `/api/paper/analytics`
  - `/api/paper/history`
- AI Learning:
  - `/api/trader/learning`
  - `/api/trader/learning/calibration`
  - `/api/trader/learning/accuracy`
- Golf hydration:
  - `/dashboard/golf`
  - `/api/golf/profile`
- Voice status:
  - `/api/voice/status`
  - `/api/voice/settings`
- WOW layer:
  - `/api/wow/insights`
  - `/api/wow/briefing`
  - `/api/wow/suggestions`
- Learning metrics:
  - `/api/trader/learning`

Remaining raw fetch calls exist in non-critical action handlers and form submissions. They were not bulk-rewritten to avoid changing request semantics for POST/DELETE workflows.

## 4. Intervals Deduplicated

Moved to `_registerInterval()`:

- `marketSnapshot`
- `recommendations`
- `unifiedPriorities`
- `notifications`
- `wow`
- `commandHistory`
- `weather`
- `outlookStatus`
- `outlookInbox`
- `connectionStatus`

Verification:

- `rg -n 'Promise\.all\(|setInterval\(' dashboard\jarvis_futuristic.html`
- Result: only one `setInterval` remains, inside `_registerInterval()` itself.
- No `Promise.all(` remains in the dashboard file.

## 5. Buttons Verified By Event Path

Verified event paths or graceful fallback for:

- Plan my day: `quickAction('plan_day')` and example command flows remain intact.
- Analyze Portfolio / Analyze market: market section and portfolio cockpit loaders remain intact.
- Open Work Hub: section/tab switching remains intact.
- Ask JARVIS: command send button path remains intact.
- Run Automations: automation tab lazy load remains intact.
- Markets sub-panels: cockpit, Paper Lab, learning, and analysis subnav paths remain intact.
- Paper Lab buttons: analytics refresh, simulate, compare, import, status paths remain intact.
- AI Learning buttons: learning refresh and outcome record paths remain intact.
- Golf buttons: golf loaders, caddy, course search, drills, and vision paths remain intact.
- Work/Outlook/Calendar buttons: route validation still passes for checked fetch paths.
- Voice buttons: voice status/settings hydration is now partial-failure safe.
- Retry/refresh buttons: patched panels render retry paths instead of blank areas.

This was static/event-path QA, not full browser click automation.

## 6. Loading States Fixed

- Paper Lab now renders fallback text and retry button if analytics or history fails.
- AI Learning now renders fallback text and retry button if learning endpoints fail.
- Golf profile can fail independently without blocking golf course/insight rendering.
- Voice status/settings can fail independently without throwing a global boot rejection.
- WOW insights/briefing/suggestions can fail independently without blanking the whole layer.
- Existing loading watchdog remains preserved.

## 7. Chart Lifecycle Fixes

Existing chart lifecycle protections were preserved:

- Previous chart instances are destroyed before new Chart.js instances are created.
- Chart animation remains disabled.
- Chart containers already have fixed height and canvas max height.

No chart architecture was rewritten.

## 8. Remaining Frontend Risks

- `dashboard/jarvis_futuristic.html` is still a 12k-line monolithic file.
- Many raw fetches remain in action/form handlers; these should be normalized gradually with endpoint-specific care.
- There are many inline `onclick` handlers, which makes full automated button QA important.
- Some module loaders still rely on global function ordering.
- Full mobile/visual regression verification still needs Playwright or manual browser QA.

## 9. QA Results

Required command:

```text
python tests\validate_ui_sync.py
```

Result:

```text
ALL 43 FRONTEND FETCH CALLS HAVE BACKEND MATCHES - OK
```

Required command:

```text
python -m py_compile main.py
```

Result:

```text
PASS
```

Requested command:

```text
node --check dashboard\jarvis_futuristic.html
```

Result:

```text
FAIL - Node cannot check .html directly: ERR_UNKNOWN_FILE_EXTENSION
```

Fallback JS extraction check:

```text
PowerShell extracted the inline dashboard script to a temp .js file, then ran node --check.
```

Result:

```text
PASS
```

## 10. Success Conditions

- No syntax errors in extracted dashboard JS.
- No unsafe `Promise.all(` remains in critical dashboard hydration.
- No direct duplicate interval patterns remain outside the interval registry.
- Chart lifecycle cleanup preserved.
- Button/event paths preserved.
- Dashboard features preserved.
- Backend/security/IBKR safety areas untouched.

JARVIS FRONTEND RUNTIME SANITIZATION COMPLETE
