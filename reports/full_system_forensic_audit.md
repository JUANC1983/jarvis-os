# JARVIS Full System Forensic Stability Audit

Date: 2026-05-07
Mode: Audit only
Scope: Frontend, backend, bridge, runtime, async systems, security, UX trust, performance, architecture, regression risk.

No production behavior was changed for this report.

## 1. Executive Summary

JARVIS is online and broadly resilient at the page-hydration level, but the system is carrying several production-grade risks: a broken new stability package import, permissive authentication defaults, exposed local secret material, very large monolithic runtime files, broad exception swallowing, duplicated fetch/polling systems, and fragile async/background task ownership.

The most urgent runtime defect found is `opsx/stability/__init__.py` importing `opsx.stability.startup_validator`, which does not exist. Any direct `import opsx.stability` currently fails with `ModuleNotFoundError`. This is production-fatal if a startup hook, deployment validation, or future guard imports the package root.

The highest security defect is the authentication fallback in `main.py:get_optional_user`, which returns owner access when no bearer token is supplied. This pattern is used by roughly 190 route dependencies and makes many API surfaces effectively public-owner in production unless another network layer blocks access.

IBKR-specific architecture appears to have recently received a production guard that blocks hosted localhost fallback and avoids silently creating local IBKR clients in Railway. That is a positive stabilization step, but it does not remove broader dashboard hydration, security, polling, or observability risks.

## 2. Stability Scores

Scores are production-risk oriented, where 100 means strong production confidence.

| Area | Score | Reason |
| --- | ---: | --- |
| Architecture | 54/100 | Main runtime is concentrated in `main.py` and one 12k-line dashboard file. High regression blast radius. |
| Runtime stability | 62/100 | Boot guards and watchdogs exist, but raw fetches, direct intervals, broad catches, and orphan task risks remain. |
| Frontend stability | 58/100 | UI hydrates, but there are many uncaught/hanging fetch risks and duplicated initialization paths. |
| Backend stability | 60/100 | Endpoints respond, but schema inconsistency, broad exception handling, and startup task ownership are weak. |
| Security | 38/100 | Owner fallback auth, tracked/local secrets, debug routes, wildcard bridge CORS, and token prefixes in logs/responses. |
| UX trust | 66/100 | Dashboard has status surfaces, but stale/fallback states can appear healthy or ambiguous. |
| Scalability | 45/100 | Large payloads, repeated portfolio snapshot builds, file-backed mutable state, and polling amplification. |
| Technical debt severity | 82/100 | Monoliths, duplicate helpers, hidden compatibility DOM, and broad global JS functions. |
| Production readiness | 57/100 | Usable and improving, but security and import/runtime risks block high confidence. |

## 3. Top Critical Risks

### CRITICAL: Broken stability package import

Files:
- `opsx/stability/__init__.py`
- Missing: `opsx/stability/startup_validator.py`

Finding:
- `opsx/stability/__init__.py` imports `StartupValidator` from `opsx.stability.startup_validator`.
- That module is absent.
- Verified command:
  - `python -c "import opsx.stability; print('opsx.stability import ok')"`
- Result:
  - `ModuleNotFoundError: No module named 'opsx.stability.startup_validator'`

Impact:
- Any direct import of `opsx.stability` can crash startup, deployment validation, tests, or future runtime guard wiring.

Priority:
- Production fatal if imported by startup. Fix before wiring stability package into app boot.

### CRITICAL: Optional auth grants owner by default

File:
- `main.py`

Function:
- `get_optional_user`

Finding:
- When no bearer token is present, the function returns an owner identity.
- Approximately 190 routes use `Depends(get_optional_user)`.

Impact:
- Production endpoints can behave as owner-authenticated without a token.
- Debug/status/control routes inherit this risk.

Priority:
- Critical security and production trust issue.

### CRITICAL: Secret exposure risk

Files:
- `.env`
- `data/bridge/bridge_token.key`
- `data/jwt_secret.key`

Finding:
- `.env` is present in the working tree and open in the IDE. Previous local inspection showed live-looking API and app secrets.
- Local key files exist under `data`.

Impact:
- If tracked, backed up, uploaded, logged, or deployed unintentionally, credentials can be compromised.

Priority:
- Critical security issue. Rotate exposed credentials if committed or shared.

### HIGH: Debug/admin surfaces use weak auth patterns

Files/functions:
- `main.py` routes around debug, Outlook QA, bridge watchdog, token status, voice QA.

Examples:
- `/api/debug/ibkr`
- `/api/debug/permissions`
- `/api/outlook/token-status`
- `/api/outlook/config-check`
- `/api/outlook/graph-qa`
- `/api/outlook/subscription-debug`
- `/api/voice/qa`
- `/api/bridge/watchdog`

Impact:
- Internal status, token prefixes, bridge state, external service diagnostics, and environment booleans may be visible to unauthenticated callers because optional auth defaults to owner.

Priority:
- High to critical depending on deployment exposure.

## 4. Frontend Forensics

Primary file:
- `dashboard/jarvis_futuristic.html`

Size:
- 601,532 bytes
- 12,116 lines
- 298 `function` declarations
- 145 `async function` declarations
- 100 `fetch(` occurrences
- 7 `setInterval` occurrences
- 16 `addEventListener` occurrences
- 5 `Promise.all` occurrences
- 8 `Promise.allSettled` occurrences

Positive findings:
- Dashboard boot is guarded by `_bootModule`.
- `_fetchWithTimeout` exists and is used heavily.
- Several modules use `Promise.allSettled`, which prevents one failing endpoint from killing the whole panel.
- A loading watchdog exists.
- UI fetch-contract validation passed against backend route declarations.

Primary risks:
- Many raw `fetch()` calls remain outside `_fetchWithTimeout`, `safeFetch`, or `safeApi`.
- Some `Promise.all` blocks can still cascade-fail a whole panel.
- Several direct intervals are not registered in the interval registry.
- Global function declarations and inline handlers make initialization order fragile.
- The file is too large to patch safely without high regression risk.
- Hidden legacy DOM compatibility elements make cleanup risky.

Known frontend cascade points:
- `loadPaperAnalytics`: `/api/paper/analytics` plus `/api/paper/history`.
- `loadLearningFull`: trader learning, calibration, and accuracy endpoints.
- `loadGolf`: dashboard golf plus profile dependency.
- `initVoiceStatus`: voice status plus voice settings.
- `loadWow`: multiple WOW endpoints, mostly guarded with fallback catches.

Interval and polling risks:
- Interval registry exists near the dashboard runtime helpers.
- Direct intervals remain for command history, weather, connection status, and Outlook polling.
- These should be centralized later, but not changed during this audit.

Chart risks:
- Four Chart.js construction sites were found.
- Chart teardown appears partly handled in specific chart loaders, but there is no central page/module teardown.
- Risk increases if tab initialization is rerun or dashboard hot reload is used.

UX trust risks:
- Stale, simulated, degraded, and disconnected states are not always visually distinct.
- Some backend fallbacks return valid-looking payloads with embedded error text.
- Portfolio health can remain critical while the dashboard itself appears healthy, which is accurate technically but confusing operationally.

## 5. Backend Forensics

Primary file:
- `main.py`

Size and shape:
- 289,643 bytes
- 7,107 lines
- 244 FastAPI route decorators
- 3 startup hooks
- 237 broad `except Exception` occurrences
- 12 `create_task` occurrences
- 190 `Depends(get_optional_user)` occurrences

Positive findings:
- The app imports and compiles.
- Route-contract validation for frontend fetches passed.
- A production IBKR guard exists and is integrated into startup and portfolio connector selection.
- Health endpoints exist.

Primary risks:
- `main.py` is a single massive runtime surface with routes, orchestration, auth, background loops, integrations, and portfolio behavior interleaved.
- Broad exception catches frequently convert failures into status JSON, which prevents crashes but hides root causes.
- Startup tasks are created without a clear central lifecycle registry.
- Multiple background loops can duplicate under reload/multi-worker conditions.
- Response schemas are inconsistent across routes.
- Several endpoints expose internal exception strings to clients.
- Many route handlers call engines or external services without a system-wide timeout contract.

Startup/background task map:
- Startup watchdog starts bridge monitoring when remote bridge config is present.
- Reminder scheduler starts from startup.
- Calendar reminder scheduler starts from startup.
- Graph memory startup backfill starts from startup.
- Outlook event queue, subscription renewal, and smart polling start from startup.

Async/runtime risks:
- Background task failures can be logged and swallowed while the service remains "healthy."
- File-backed JSON stores are mutated by many systems without a single write coordination layer.
- Multiple workers can produce divergent in-memory state.
- Portfolio endpoints can independently rebuild broker snapshots and amplify bridge load.

## 6. IBKR / Bridge Infrastructure Audit

Files:
- `opsx/connectors/ibkr_connector.py`
- `opsx/connectors/ibkr_bridge_client.py`
- `opsx/bridge/secure_bridge.py`
- `opsx/bridge/account_separation.py`
- `opsx/bridge/watchdog.py`
- `opsx/bridge/production_guard.py`
- `main.py`

Positive findings:
- `opsx/bridge/production_guard.py` enforces no-localhost hosted-runtime behavior.
- Hosted/runtime bridge startup validates bridge URL and token presence.
- If hosted and not configured, the app can use `IBKRNotConfiguredStub` instead of falling back to localhost.
- Bridge watchdog now contains exponential backoff and circuit breaker behavior.
- Secure bridge uses an IBKR worker thread and loop isolation.
- Account separation and read-only enforcement exist conceptually.

Remaining risks:
- The bridge route surfaces need stricter production auth review.
- Token in WebSocket query strings can leak through logs/proxies.
- `secure_bridge.py` uses wildcard CORS.
- `/bridge/info` exposes bridge metadata and token prefix.
- If the bridge is disconnected, broadcast loops can continue pushing stale/disconnected state.
- Portfolio hydration still depends on several chained components with different error schemas.

Current IBKR trace:
- Frontend portfolio loaders call `/api/portfolio/*`, `/api/debug/ibkr`, and `/api/bridge/watchdog`.
- `main.py` portfolio routes call `_build_unified_snapshot()`.
- `_build_unified_snapshot()` calls configured broker connectors.
- Hosted IBKR path validates remote bridge config through `production_guard`.
- Remote bridge client calls ngrok/bridge URL with token.
- Secure bridge talks to local TWS/Gateway socket through the IBKR worker.
- Snapshot/cache data is returned to backend.
- Backend maps snapshot to dashboard-facing summary, positions, brokers, analysis, and status.
- Dashboard renders connection/portfolio state.

Likely failure classes if live portfolio remains disconnected:
- Remote bridge URL/token absent or invalid in hosted runtime.
- Ngrok tunnel not alive or not reachable from Railway.
- Bridge token mismatch.
- Local bridge alive but IBKR socket 4001 unreachable.
- Read-only handshake or account separation rejects live hydration.
- Snapshot cache returns stale/disconnected data after bridge failure.
- Frontend reads a valid stale/fallback payload and renders critical health instead of hard error.

This audit did not modify IBKR logic because Claude Code is handling that recovery path.

## 7. Security Audit

Critical:
- Optional auth fallback returns owner identity.
- Local `.env` and key material require immediate tracking/history review.

High:
- Debug routes expose internal service state.
- `secure_bridge.py` wildcard CORS.
- Token prefixes appear in logs/responses.
- WebSocket token travels in query string.
- Default/fallback local credentials exist in user/auth engine code and must not be accepted in production.

Medium:
- Error responses often include raw `str(e)`.
- Environment-set booleans are exposed through health/debug routes.
- Bridge info route exposes host/port/token prefix style metadata.

Security stabilization order:
1. Make production optional auth anonymous, not owner.
2. Move debug/admin routes behind strict auth.
3. Rotate and remove committed or shared secrets.
4. Restrict bridge CORS.
5. Remove token prefixes from responses/logs.
6. Validate no live execution route can bypass read-only policy.

## 8. Performance Audit

Frontend bottlenecks:
- 601 KB HTML/JS document.
- 100 fetch call sites.
- Heavy boot fanout across dashboard panels.
- Multiple periodic polling loops.
- Large DOM with many hidden legacy compatibility surfaces.

Backend bottlenecks:
- Portfolio snapshot construction can be repeated by multiple endpoints.
- Route-level external API calls can stack under dashboard boot.
- File-backed JSON state can become a bottleneck and race source.
- Large report/data directories can increase deployment/build context if not ignored.

Bridge bottlenecks:
- Broadcast loops continue even while disconnected.
- Market snapshot polling uses external providers and needs bounded timeout/backoff verification.
- WebSocket client growth requires heartbeat and cleanup to remain reliable.

## 9. Architecture Audit

Giant files:
- `dashboard/jarvis_futuristic.html`: 12,116 lines.
- `main.py`: 7,107 lines.
- `opsx/bridge/secure_bridge.py`: 805 lines.
- Several `core/*` engines exceed 700 lines.

Duplicated or fragile systems:
- Multiple frontend fetch wrappers.
- Multiple loading-state styles.
- Multiple interval ownership patterns.
- Multiple portfolio/status endpoints with overlapping broker state.
- Multiple startup hooks creating background tasks.
- Duplicate function names exist in Python and JS, relying on route/function-object behavior or later JS overrides.

Dead/zombie risk:
- Backup dashboard files exist.
- Hidden legacy DOM nodes are still required by compatibility code.
- New stability package is incomplete.

Regression hotspots:
- Dashboard boot and tab switching.
- Portfolio hydration and broker status.
- Optional auth and debug route access.
- Outlook webhook/subscription/polling stack.
- Paper Lab import/compare with live portfolio.
- Golf Vision camera/MediaPipe runtime.
- Bridge watchdog and hosted IBKR guard.

## 10. Dependency Graph

Frontend:

```text
dashboard boot()
  -> initEvents / initVoice / initUpload / initVoiceStatus / initWeather
  -> _bootModule(loadHome)
  -> _bootModule(loadMarketSnapshot)
  -> _bootModule(loadPortfolioSummary)
  -> _bootModule(loadPaperStatus)
  -> _bootModule(loadLearningMetrics)
  -> _bootModule(loadNews)
  -> _bootModule(loadAgents)
  -> _bootModule(loadPipeline)
  -> _bootModule(loadSystemMetrics)
  -> _bootModule(loadNotifications)
  -> _bootModule(loadWow)
  -> _bootModule(loadCommanderBrief)
  -> _bootModule(loadConnectionStatus)
```

Portfolio:

```text
dashboard portfolio UI
  -> /api/portfolio/summary
  -> /api/portfolio/analysis
  -> /api/portfolio/brokers
  -> /api/portfolio/exposure
  -> /api/portfolio/positions
  -> /api/portfolio/cockpit
  -> /api/debug/ibkr
  -> /api/bridge/watchdog
  -> main._build_unified_snapshot()
  -> IBKR/HAPI connectors
  -> UnifiedPortfolioEngine
  -> PortfolioIntelligenceEngine
  -> dashboard render
```

Hosted IBKR bridge:

```text
main.py portfolio connector selection
  -> production_guard.validate_production_config()
  -> IBKRBridgeClient
  -> ngrok bridge URL
  -> secure_bridge FastAPI
  -> bridge token auth
  -> IBKRWorkerThread
  -> TWS/Gateway socket 4001
  -> snapshot_cache
  -> backend response
  -> frontend hydration
```

Background runtime:

```text
FastAPI startup
  -> bridge watchdog loop
  -> reminder scheduler
  -> calendar reminder scheduler
  -> graph memory backfill
  -> Outlook event queue
  -> Outlook renewal loop
  -> Outlook smart poll loop
```

## 11. Regression Risk Map

CRITICAL:
- `opsx/stability` package root import.
- Auth fallback returning owner.
- Secrets/key material exposure.
- Live execution/read-only policy boundaries.

HIGH:
- Dashboard boot order and global function overrides.
- Portfolio endpoint schema drift.
- Bridge token/URL/ngrok/TWS chain.
- Background startup task duplication.
- Debug/admin endpoint exposure.
- File-backed state writes under concurrent load.

MEDIUM:
- Chart lifecycle and tab reinitialization.
- Polling intervals not centrally owned.
- Promise.all cascade failures.
- Stale cache rendering as valid dashboard state.
- Mobile overflow in dense dashboard panels.
- Backup/zombie files causing future edits to land in wrong file.

LOW:
- Cosmetic wording inconsistencies.
- Duplicate helper naming where behavior is currently stable.
- Report and runtime snapshot directory growth.

## 12. Safe Auto-Fix Candidates

No fixes were applied because the user requested audit-only mode and Claude Code is currently modifying IBKR recovery/stabilization.

Safe candidates after approval:
- Add missing `opsx/stability/startup_validator.py` or remove the broken package-root export.
- Change optional auth fallback behavior in production.
- Move debug routes to strict auth.
- Replace remaining frontend `Promise.all` with `Promise.allSettled` where partial rendering is acceptable.
- Register all dashboard intervals in the existing interval registry.
- Add missing unload cleanup for direct timers and polling handles.
- Remove token prefixes from debug responses/logs.
- Restrict bridge CORS from wildcard to configured origins.
- Add backend response timeout guards to high-fanout dashboard endpoints.

Unsafe or deferred:
- Splitting `main.py`.
- Splitting `jarvis_futuristic.html`.
- Rewriting portfolio architecture.
- Altering IBKR bridge behavior while Claude Code is handling recovery.
- Removing hidden legacy DOM or backup compatibility shims.

## 13. Observability Roadmap

1. Add one correlation ID per dashboard boot and propagate to backend logs.
2. Record per-endpoint timeout, stale, fallback, and live-source state.
3. Add bridge trace states: configured, tunnel reachable, token accepted, socket reachable, readonly accepted, snapshot fresh.
4. Add frontend panel status telemetry: loading, partial, stale, failed, recovered.
5. Add background task heartbeat registry for startup-created loops.
6. Add explicit production readiness endpoint separate from generic health.

## 14. Recommended Stabilization Order

1. Fix `opsx.stability` package import break.
2. Lock production auth: no-token must not become owner.
3. Rotate/remove exposed secrets and verify `.env` is not tracked.
4. Protect debug/admin routes.
5. Finish Claude-owned IBKR recovery without changing dashboard architecture.
6. Normalize portfolio stale/live/disconnected response flags.
7. Centralize frontend timers using existing interval registry.
8. Convert fragile dashboard `Promise.all` blocks to partial-render patterns.
9. Add task lifecycle registry for background loops.
10. Create small contract tests for portfolio, bridge, auth, dashboard boot, Paper Lab, Golf, and onboarding.

## 15. Verification Performed

Commands run:

```text
python -m py_compile main.py opsx\bridge\production_guard.py opsx\stability\api_contract_lock.py opsx\stability\production_rules.py opsx\stability\__init__.py
```

Result:
- Passed.

```text
python tests\validate_ui_sync.py
```

Result:
- Passed.
- All 52 frontend fetch calls checked by the validator had backend route matches.

```text
python -c "import opsx.stability; print('opsx.stability import ok')"
```

Result:
- Failed.
- `ModuleNotFoundError: No module named 'opsx.stability.startup_validator'`.

## 16. Final QA

Verified by audit behavior:
- No features removed.
- No endpoints changed.
- No dashboard code changed.
- No navigation code changed.
- No IBKR logic changed.
- No Paper Lab logic changed.
- No Golf logic changed.
- No onboarding logic changed.

Residual risk:
- This was static/runtime-light audit. Full browser QA with Playwright and live Railway/ngrok/TWS verification remains required for end-to-end production confidence.

JARVIS FULL FORENSIC STABILITY AUDIT COMPLETE
