# JARVIS Pre-Omega System Audit
**Date:** 2026-05-06  
**Scope:** Full architectural audit before Omega evolution phase  
**Status:** Phase 1 complete — active systems catalogued, debt mapped, consolidation opportunities identified

---

## 1. Codebase Scale

| Dimension | Count |
|-----------|-------|
| `main.py` lines | 6,529 |
| Registered API routes | 232 |
| Background task patterns | 8 |
| Core modules (`core/`) | 122 files |
| OPSX connectors (`opsx/`) | 30 files |
| Archive directories | 13 |
| Total Python files (non-venv) | ~363 |

---

## 2. Active Subsystems

### 2.1 Portfolio Intelligence Stack (COMPLETE)
| Module | File | Status |
|--------|------|--------|
| IBKR TWS Connector | `opsx/connectors/ibkr_connector.py` | Active — 9/9 trade methods blocked |
| IBKR Read-Only | `opsx/connectors/ibkr_readonly.py` | Active |
| Hapi Read-Only | `opsx/connectors/hapi_readonly.py` | Active |
| Unified Portfolio Engine | `core/unified_portfolio_engine.py` | Active |
| Portfolio Intelligence Engine | `core/portfolio_intelligence_engine.py` | Active |
| Portfolio Engine (institutional) | `core/portfolio_engine.py` | Active |
| Paper Trading Engine | `core/paper_trading_engine.py` | Active |

### 2.2 Trader Intelligence Stack (UPGRADED — Phase 2)
| Module | File | Status |
|--------|------|--------|
| TraderAlphaEngine | `core/trader_alpha_engine.py` | Active — regime + explainability added |
| TraderLearningEngine | `core/trader_learning_engine.py` | Active — 5-bucket calibration |
| `/api/trader/analyze` | `main.py:5795` | NEW — portfolio-aware, regime-aware |
| `/api/trader/learning` | `main.py` | Active |
| `/api/trader/audit` | `main.py` | Active |

**New TraderAlphaEngine capabilities (Post-Phase 2):**
- Market regime detection: `bull` / `bear` / `sideways` / `panic` / `high_vol` / `low_liquidity`
- Portfolio context filter: penalizes over-concentration, low-cash states, existing holdings
- Learning integration: `TraderLearningEngine.get_adapted_score_adjustment()` applied per-symbol
- Full explainability block: `why` / `confidence_factors` / `key_risk` / `uncertainty` / `alternative_scenario`

### 2.3 Market Intelligence Stack
| Module | File | Status |
|--------|------|--------|
| MarketIntelligenceEngine | `core/market_intelligence_engine.py` | Active |
| `/api/markets/snapshot` | `main.py` | Active — 30s polling |
| `/api/markets/analyze` | `main.py` | Active — lightweight fallback |
| `/api/markets/recommended` | `main.py` | Active |
| `/api/markets/news` | `main.py` | Active |

### 2.4 AI Orchestration & Agents
| System | Notes |
|--------|-------|
| `JarvisOrchestrator` | Primary conversation router |
| `ProductBrain` | Product intelligence agent |
| Agent Council (3 agents) | Commander, Analyst, Executor roles |
| FAISS Vector Memory | Semantic similarity search |
| GraphMemoryEngine | Entity relationship graph |
| JarvisMemory | Episodic/structured memory |

### 2.5 External Integrations
| Integration | Status |
|-------------|--------|
| Outlook/Calendar | Active — OAuth2 single-tenant |
| Voice (Whisper + TTS) | Active |
| News Feed | Active |
| Golf Intelligence | Active |
| Analytics Pipeline | Active |
| File Upload + RAG | Active |

---

## 3. API Surface Summary

```
232 total routes across:
  /api/portfolio/*     — 8 endpoints (unified, summary, positions, brokers, exposure, pnl, intelligence, history)
  /api/trader/*        — 6 endpoints (analyze[NEW], audit, learning, learning/calibration, learning/accuracy, learning/record-outcome)
  /api/markets/*       — 6 endpoints (snapshot, analyze, recommended, news, regime, indices)
  /api/paper/*         — 5 endpoints (status, simulate-trade, import-from-real, compare-real, reset)
  /api/outlook/*       — 4 endpoints
  /api/calendar/*      — 4 endpoints
  /api/voice/*         — 5 endpoints
  /api/golf/*          — 12 endpoints
  /api/news/*          — 3 endpoints
  /api/projects/*      — 4 endpoints
  /api/analytics/*     — 3 endpoints
  /api/life/*          — 8 endpoints
  /api/command/*       — 3 endpoints
  /api/automations/*   — 4 endpoints
  /dashboard/*         — legacy endpoints (trader, portfolio, recommendations)
  ...remaining routes  — system, health, auth, uploads, personality
```

---

## 4. Memory Architecture (3 Systems)

| System | Type | Persistence | Status |
|--------|------|-------------|--------|
| `JarvisMemory` | Structured episodic | SQLite / JSON | Active |
| `FaissVectorMemory` | Semantic vector search | .faiss index file | Active |
| `GraphMemoryEngine` | Entity relationships | networkx graph | Active |

**Consolidation opportunity:** No unified memory access layer. Each system accessed independently. A `UnifiedMemoryEngine` adapter would simplify orchestration code and enable cross-system queries.

---

## 5. Data Persistence Map

```
data/
  portfolio/
    ibkr_tws_snapshot.json       — IBKR live snapshot
    unified_snapshot.json        — merged broker snapshot
    paper_positions.json         — paper trading state
    portfolio_engine_snapshot.json
    portfolio_engine_history.json
    trading_guardrail_log.json   — blocked trade attempts log
  learning/
    signal_outcomes.json         — outcome history
    learning_metrics.json        — aggregated metrics
    accuracy_history.json        — symbol accuracy over time
  memory/
    ...                          — JarvisMemory files
  faiss/
    ...                          — vector index
```

---

## 6. Technical Debt Map

### HIGH priority
| Issue | Location | Impact |
|-------|----------|--------|
| 13 archive directories | `**/archive*` | Dead code weight, import confusion risk |
| No WebSocket support | Architecture-wide | Real-time data requires polling workarounds |
| `real_trade` guard duplicated | 20+ endpoints | Should be enforced at middleware level |
| Dashboard uses both `/dashboard/*` and `/api/*` | `jarvis_futuristic.html` | Dual routing patterns, tech debt |

### MEDIUM priority
| Issue | Location | Impact |
|-------|----------|--------|
| `_build_unified_snapshot()` has no timeout | `main.py:5818` | Broker hang could block request thread |
| Paper trading state not versioned | `data/portfolio/paper_positions.json` | No history or rollback |
| TraderAlphaEngine fetches yfinance synchronously | `core/trader_alpha_engine.py` | Blocks FastAPI event loop |
| 3 independent memory systems | Various | Query duplication, inconsistent context |

### LOW priority
| Issue | Location | Impact |
|-------|----------|--------|
| Market regime uses only local ticker ATR | `trader_alpha_engine.py` | Does not use SPY/VIX macro context |
| Confidence score is linear `score/100` | Multiple | Does not reflect calibration curve |
| `_no_data_report()` pattern repeated | 3+ modules | Minor duplication |

---

## 7. Consolidation Opportunities

1. **Memory Layer** — Wrap JarvisMemory + FAISS + GraphMemory behind `UnifiedMemoryGateway` for consistent access
2. **Real-trade guard** — Add FastAPI middleware that injects `real_trade: False` into every response automatically
3. **Archive cleanup** — Remove or namespace 13 archive dirs to eliminate dead code noise
4. **Async broker calls** — Make `_build_unified_snapshot()` async with per-broker timeout to prevent request blocking
5. **Unified schema layer** — Add Pydantic response models to key endpoints for type safety and OpenAPI docs

---

## 8. Security Guardrails Audit

| Guard | Implementation | Test Coverage |
|-------|----------------|---------------|
| IBKR trade block (9 methods) | `SecurityViolationError` + guardrail log | 9/9 blocked, 40-test suite |
| IBKR read-only connect | `readonly=True` in ib_insync | Confirmed |
| `real_trade: False` everywhere | Manual per-endpoint | 24/24 QA checks pass |
| Hapi read-only | `TradingBlockedError` wrapper | Active |
| No order execution path | No `placeOrder` chain exists | Architecture-verified |

---

## 9. Dashboard UI Audit

**Element IDs verified:** 43/43 required IDs present (Phase 2/3 QA gate)  
**Fetch bindings:** 68/68 frontend `fetch()` calls matched to backend endpoints  
**New in Phase 2:** regime badge, explainability block, portfolio context notes, learning history in trader panel

---

## 10. Phase Completion Status

| Phase | Name | Status |
|-------|------|--------|
| Phase 1 | IBKR TWS Connector + Security | COMPLETE |
| Phase 2 | Institutional Portfolio Engine | COMPLETE |
| Phase 3 | Bloomberg-lite Dashboard UX | COMPLETE |
| Phase 4 | Paper Trading + Learning Layer | COMPLETE |
| Phase 5 | Trader Audit + Reliability Score | COMPLETE |
| Phase 6 | Multi-broker Architecture | COMPLETE |
| Phase 7 | Railway Bridge (pending deploy) | PARTIAL |
| Phase 8 | Pre-Omega QA | IN PROGRESS |
| Omega-1 | Trader Intelligence Maturity | COMPLETE (Phase 2 of Pre-Omega) |
| Omega-2 | Human-First UX | NOT STARTED |
| Omega-3 | Proactive Intelligence Engine | NOT STARTED |
| Omega-4 | Memory Consolidation | NOT STARTED |
| Omega-5 | Trust + Explainability (trader) | COMPLETE |
| Omega-6 | Performance Hardening | NOT STARTED |
| Omega-7 | Production Stability QA | NOT STARTED |

---

*Generated by JARVIS Engineer Agent — 2026-05-06*  
*All systems read-only. `real_trade: False` enforced system-wide.*
