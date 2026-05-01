/**
 * runtime_qa.ts — JARVIS Engineer Agent Runtime QA Module
 *
 * Hits real running endpoints using safe GET-only requests.
 * Never modifies state. Never deletes. Never deploys.
 *
 * When server is unreachable: returns serverReachable=false and skips gracefully.
 * REALITY_MODE: runtime results override static analysis severity.
 */
import * as http  from "http";
import * as https from "https";
import { Config }  from "./config";
import { Issue, Severity, IssueType } from "./issue_detector";

// ─────────────────────────────────────────────────────────────
// Types
// ─────────────────────────────────────────────────────────────

export interface EndpointResult {
  label:          string;
  url:            string;
  statusCode:     number | null;
  responseTimeMs: number;
  body:           Record<string, unknown> | null;
  rawBody:        string;
  error:          string | null;
  reachable:      boolean;
  issues:         Issue[];
}

export interface RuntimeQAResult {
  runAt:            string;
  baseUrl:          string;
  realityMode:      boolean;
  serverReachable:  boolean;
  endpointResults:  EndpointResult[];
  runtimeIssues:    Issue[];
  passed:           number;
  failed:           number;
  warnings:         number;
  overallStatus:    "PASS" | "WARN" | "FAIL" | "OFFLINE";
}

// ─────────────────────────────────────────────────────────────
// Helpers
// ─────────────────────────────────────────────────────────────

let _rtCounter = 0;
function rtId(prefix: string): string {
  return `RT_${prefix}_${String(++_rtCounter).padStart(3, "0")}`;
}

function httpGet(
  url: string,
  timeoutMs = 6000,
): Promise<{ statusCode: number; body: string }> {
  return new Promise((resolve, reject) => {
    const mod = url.startsWith("https") ? https : http;
    const req = (mod as typeof http).get(url, { timeout: timeoutMs }, (res) => {
      let data = "";
      res.on("data", (chunk: Buffer) => (data += chunk.toString()));
      res.on("end", () => resolve({ statusCode: res.statusCode ?? 0, body: data }));
    });
    req.on("error",   reject);
    req.on("timeout", () => { req.destroy(); reject(new Error("request timeout")); });
  });
}

function tryParse(raw: string): Record<string, unknown> | null {
  try { return JSON.parse(raw) as Record<string, unknown>; }
  catch { return null; }
}

// ─────────────────────────────────────────────────────────────
// Per-module analysis
// ─────────────────────────────────────────────────────────────

function analyzeHome(body: Record<string, unknown> | null, _code: number, url: string): Issue[] {
  const issues: Issue[] = [];
  if (!body) return issues;

  if (body.status === "error") {
    issues.push({
      id: rtId("HOME"),
      severity: "high",
      type: "BUG_FIX",
      module: "home",
      file: "main.py",
      problem: `/dashboard/home returned status:error — home overview is broken`,
      recommended_fix: "Check the /dashboard/home endpoint and fix the underlying exception",
      risk: "medium",
      auto_fix_allowed: false,
    });
  }
  return issues;
}

function analyzeOutlook(body: Record<string, unknown> | null, statusCode: number, url: string): Issue[] {
  const issues: Issue[] = [];

  if (statusCode === 401 || statusCode === 403) {
    issues.push({
      id: rtId("OUTLOOK_AUTH"),
      severity: "critical",
      type: "BUG_FIX",
      module: "outlook",
      file: "opsx/connectors/outlook_auth.py",
      problem: `Outlook /status returned HTTP ${statusCode} — authentication is broken or token expired`,
      recommended_fix: "Re-authenticate via /api/outlook/auth-url and complete the OAuth flow",
      risk: "high",
      auto_fix_allowed: false,
    });
    return issues;
  }

  if (!body) return issues;

  const authenticated = body.authenticated as boolean | undefined;
  if (authenticated === false) {
    issues.push({
      id: rtId("OUTLOOK_UNAUTH"),
      severity: "critical",
      type: "BUG_FIX",
      module: "outlook",
      file: "opsx/connectors/outlook_auth.py",
      problem: "Outlook reports authenticated:false — no valid token stored",
      recommended_fix: "Visit /api/outlook/auth-url to re-authenticate with Microsoft Graph",
      risk: "high",
      auto_fix_allowed: false,
    });
  }

  if (body.error) {
    issues.push({
      id: rtId("OUTLOOK_ERR"),
      severity: "high",
      type: "BUG_FIX",
      module: "outlook",
      file: "main.py",
      problem: `Outlook status endpoint returned error: ${String(body.error).slice(0, 200)}`,
      recommended_fix: "Fix the outlook status endpoint or re-authenticate",
      risk: "medium",
      auto_fix_allowed: false,
    });
  }
  return issues;
}

function analyzeCalendar(body: Record<string, unknown> | null, statusCode: number, url: string): Issue[] {
  const issues: Issue[] = [];

  if (statusCode >= 500) {
    issues.push({
      id: rtId("CAL_500"),
      severity: "critical",
      type: "BUG_FIX",
      module: "calendar",
      file: "main.py",
      problem: `Calendar events endpoint returned HTTP ${statusCode} — server error`,
      recommended_fix: "Check /api/calendar/events exception handler in main.py",
      risk: "high",
      auto_fix_allowed: false,
    });
    return issues;
  }

  if (!body) return issues;

  if (body.status === "error") {
    const errMsg = String(body.error || "unknown").slice(0, 200);
    issues.push({
      id: rtId("CAL_DISCONNECTED"),
      severity: "high",
      type: "UX_FIX",
      module: "calendar",
      file: "dashboard/jarvis_futuristic.html",
      problem: `Calendar not connected — API returned status:error (${errMsg})`,
      recommended_fix: "Connect Google Calendar or Outlook Calendar in settings. Dashboard should show 'Calendario no conectado'",
      risk: "low",
      auto_fix_allowed: false,
    });
  } else if (Array.isArray(body.events) && (body.events as unknown[]).length === 0) {
    // Empty but connected — low severity informational
    issues.push({
      id: rtId("CAL_EMPTY"),
      severity: "low",
      type: "QA_IMPROVEMENT",
      module: "calendar",
      file: "dashboard/jarvis_futuristic.html",
      problem: "Calendar is connected but returned 0 events for today — may be correct or connector issue",
      recommended_fix: "Verify calendar connector returns real events, or confirm calendar is intentionally empty",
      risk: "low",
      auto_fix_allowed: false,
    });
  }
  return issues;
}

function analyzeMarkets(body: Record<string, unknown> | null, statusCode: number, url: string): Issue[] {
  const issues: Issue[] = [];

  if (statusCode >= 500) {
    issues.push({
      id: rtId("MKT_500"),
      severity: "critical",
      type: "BUG_FIX",
      module: "markets",
      file: "main.py",
      problem: `Markets endpoint returned HTTP ${statusCode} — market engine crashed`,
      recommended_fix: "Check /api/markets/recommended exception handler and market data engine",
      risk: "high",
      auto_fix_allowed: false,
    });
    return issues;
  }

  if (!body) return issues;
  if (body.status === "error") {
    issues.push({
      id: rtId("MKT_ERR"),
      severity: "high",
      type: "BUG_FIX",
      module: "markets",
      file: "core/product_brain_pro.py",
      problem: `Markets returned status:error — ${String(body.error || "").slice(0, 200)}`,
      recommended_fix: "Fix product_brain_pro.py recommendations() or check yfinance connectivity",
      risk: "medium",
      auto_fix_allowed: false,
    });
    return issues;
  }

  const items = (body.items as Record<string, unknown>[]) || [];
  if (!items.length) {
    issues.push({
      id: rtId("MKT_EMPTY"),
      severity: "high",
      type: "BUG_FIX",
      module: "markets",
      file: "core/product_brain_pro.py",
      problem: "Markets returned 0 recommendation items — engine produced no results",
      recommended_fix: "Check yfinance connectivity and ProductBrainPro.recommendations()",
      risk: "medium",
      auto_fix_allowed: false,
    });
    return issues;
  }

  // FAKE DATA: all scores within ±2 points of each other (≥4 items)
  const scores = items.map(i => Number(i.setup_score ?? i.score)).filter(s => !isNaN(s));
  if (scores.length >= 4) {
    const min = Math.min(...scores);
    const max = Math.max(...scores);
    if (max - min <= 2) {
      issues.push({
        id: rtId("MKT_FAKE_SCORE"),
        severity: "critical",
        type: "BUG_FIX",
        module: "markets",
        file: "core/product_brain_pro.py",
        problem: `ALL ${scores.length} market scores are identical or within 2 points (min=${min}, max=${max}) — market engine is not using real logic or data`,
        recommended_fix: "Market engine is broken — scores should vary by symbol. Check ProductBrainPro.analyze_asset() and yfinance data flow",
        risk: "high",
        auto_fix_allowed: false,
      });
    }
  }

  // FAKE DATA: all signals identical (≥4 items)
  const signals = items.map(i => String(i.signal || "")).filter(Boolean);
  if (signals.length >= 4) {
    const uniqueSignals = new Set(signals);
    if (uniqueSignals.size === 1) {
      issues.push({
        id: rtId("MKT_FAKE_SIGNAL"),
        severity: "critical",
        type: "BUG_FIX",
        module: "markets",
        file: "core/product_brain_pro.py",
        problem: `ALL ${signals.length} market signals are identical ("${signals[0]}") — market engine is returning fake/hardcoded signals`,
        recommended_fix: "Fix signal generation in the market brain — signals must differ by symbol, score, and macro regime",
        risk: "high",
        auto_fix_allowed: false,
      });
    }
  }

  // Missing prices: more than half
  const nullPrices = items.filter(i => i.price == null || i.price === 0).length;
  if (nullPrices > items.length * 0.5) {
    issues.push({
      id: rtId("MKT_NULL_PRICE"),
      severity: "high",
      type: "BUG_FIX",
      module: "markets",
      file: "core/market_data_engine.py",
      problem: `${nullPrices}/${items.length} market items have null/zero price — yfinance may be failing or rate-limited`,
      recommended_fix: "Check market_data_engine.py get_quotes() and verify yfinance connectivity",
      risk: "medium",
      auto_fix_allowed: false,
    });
  }

  // Missing thesis/catalyst/risk fields
  const missingFields = items.filter(i => !i.thesis_short && !i.catalyst && !i.risk).length;
  if (missingFields > items.length * 0.5) {
    issues.push({
      id: rtId("MKT_MISSING_FIELDS"),
      severity: "medium",
      type: "AGENT_QUALITY",
      module: "markets",
      file: "core/product_brain_pro.py",
      problem: `${missingFields}/${items.length} market cards missing thesis/catalyst/risk fields`,
      recommended_fix: "Ensure trader() returns thesis_short, catalyst, risk, and last_updated for every symbol",
      risk: "low",
      auto_fix_allowed: false,
    });
  }

  return issues;
}

function analyzeVoice(body: Record<string, unknown> | null, statusCode: number, url: string): Issue[] {
  const issues: Issue[] = [];

  if (statusCode === 404) {
    issues.push({
      id: rtId("VOICE_ROUTE"),
      severity: "high",
      type: "BUG_FIX",
      module: "voice",
      file: "main.py",
      problem: "Voice status endpoint returned 404 — route is missing or path has changed",
      recommended_fix: "Verify @app.get('/api/voice/status') or '/api/voice/settings' exists in main.py",
      risk: "medium",
      auto_fix_allowed: false,
    });
    return issues;
  }

  if (!body) return issues;

  const configured = body.configured as boolean | undefined;
  if (configured === false) {
    issues.push({
      id: rtId("VOICE_NOT_CONFIGURED"),
      severity: "medium",
      type: "QA_IMPROVEMENT",
      module: "voice",
      file: "core/voice_service.py",
      problem: "ElevenLabs TTS is not configured — ELEVENLABS_API_KEY not set",
      recommended_fix: "Set ELEVENLABS_API_KEY in .env to enable voice output. Voice commands still work (text-only mode)",
      risk: "low",
      auto_fix_allowed: false,
    });
  }

  if (body.error || body.tts_available === false) {
    const reason = String(body.tts_reason || body.error || "unknown");
    issues.push({
      id: rtId("VOICE_TTS_FAIL"),
      severity: "medium",
      type: "BUG_FIX",
      module: "voice",
      file: "core/voice_service.py",
      problem: `Voice TTS unavailable: ${reason}`,
      recommended_fix: "Check ELEVENLABS_API_KEY and verify API key is valid and has credits",
      risk: "low",
      auto_fix_allowed: false,
    });
  }
  return issues;
}

function analyzeNews(body: Record<string, unknown> | null, statusCode: number, url: string): Issue[] {
  const issues: Issue[] = [];
  if (!body) return issues;

  if (body.status === "error") {
    issues.push({
      id: rtId("NEWS_ERR"),
      severity: "high",
      type: "BUG_FIX",
      module: "news",
      file: "core/live_news_engine.py",
      problem: `News feed returned status:error — ${String(body.error || "").slice(0, 200)}`,
      recommended_fix: "Check live_news_engine.py and verify RSS sources are reachable",
      risk: "medium",
      auto_fix_allowed: false,
    });
    return issues;
  }

  const items = (body.items as unknown[]) || [];
  if (!items.length) {
    issues.push({
      id: rtId("NEWS_EMPTY"),
      severity: "medium",
      type: "BUG_FIX",
      module: "news",
      file: "core/live_news_engine.py",
      problem: "News feed returned 0 items — RSS sources may be blocked or feedparser missing",
      recommended_fix: "Verify feedparser is installed (pip install feedparser) and RSS URLs are accessible",
      risk: "medium",
      auto_fix_allowed: false,
    });
  } else {
    // Check for fake/placeholder news titles
    const fakeTitles = (items as Record<string, unknown>[]).filter(n =>
      String(n.title || "").toLowerCase().includes("unavailable") ||
      String(n.title || "").toLowerCase().includes("fallback") ||
      String(n.source || "").toLowerCase() === "system"
    );
    if (fakeTitles.length) {
      issues.push({
        id: rtId("NEWS_FALLBACK"),
        severity: "medium",
        type: "BUG_FIX",
        module: "news",
        file: "core/live_news_engine.py",
        problem: `${fakeTitles.length} news item(s) are fallback/system placeholders, not real news`,
        recommended_fix: "feedparser may not be installed or RSS sources are unreachable. Run: pip install feedparser",
        risk: "low",
        auto_fix_allowed: false,
      });
    }
  }
  return issues;
}

// ─────────────────────────────────────────────────────────────
// Main RuntimeQA class
// ─────────────────────────────────────────────────────────────

export class RuntimeQA {
  private config: Config;

  constructor(config: Config) {
    this.config = config;
  }

  private async probe(
    label: string,
    path: string,
    analyzerFn: (body: Record<string, unknown> | null, code: number, url: string) => Issue[],
  ): Promise<EndpointResult> {
    const url = `${this.config.localUrl}${path}`;
    const t0  = Date.now();
    try {
      const { statusCode, body: rawBody } = await httpGet(url, 7000);
      const responseTimeMs = Date.now() - t0;
      const body = tryParse(rawBody);
      const issues = analyzerFn(body, statusCode, url);

      console.log(
        `  ${issues.some(i => i.severity === "critical") ? "🔴" :
            issues.some(i => i.severity === "high")     ? "🟠" :
            issues.some(i => i.severity === "medium")   ? "🟡" :
            issues.length ? "⚠️ " : "✅"} ` +
        `[${label}] HTTP ${statusCode} (${responseTimeMs}ms)${issues.length ? ` — ${issues.length} issue(s)` : ""}`
      );

      return { label, url, statusCode, responseTimeMs, body, rawBody: rawBody.slice(0, 500), error: null, reachable: true, issues };
    } catch (err) {
      const responseTimeMs = Date.now() - t0;
      const error = err instanceof Error ? err.message : String(err);
      console.log(`  ⚪ [${label}] UNREACHABLE — ${error}`);
      return { label, url, statusCode: null, responseTimeMs, body: null, rawBody: "", error, reachable: false, issues: [] };
    }
  }

  async run(): Promise<RuntimeQAResult> {
    console.log(`[RUNTIME_QA] Probing ${this.config.localUrl} ...`);
    if (this.config.realityMode) {
      console.log("[RUNTIME_QA] REALITY MODE: ON — runtime results override static severity");
    }

    // Quick connectivity check first
    let serverReachable = false;
    try {
      await httpGet(`${this.config.localUrl}/api/mode`, 3000);
      serverReachable = true;
    } catch {
      console.log(`[RUNTIME_QA] Server not reachable at ${this.config.localUrl} — skipping runtime checks`);
    }

    if (!serverReachable) {
      return {
        runAt:           new Date().toISOString(),
        baseUrl:         this.config.localUrl,
        realityMode:     this.config.realityMode,
        serverReachable: false,
        endpointResults: [],
        runtimeIssues:   [],
        passed:          0,
        failed:          0,
        warnings:        0,
        overallStatus:   "OFFLINE",
      };
    }

    // Run all probes
    const results = await Promise.all([
      this.probe("home",        "/dashboard/home",                  analyzeHome),
      this.probe("outlook",     "/api/outlook/status",              analyzeOutlook),
      this.probe("calendar",    "/api/calendar/events?range=day",   analyzeCalendar),
      this.probe("markets",     "/api/markets/recommended",         analyzeMarkets),
      this.probe("voice",       "/api/voice/settings",              analyzeVoice),
      this.probe("news",        "/api/news/feed?limit=5",           analyzeNews),
    ]);

    // Aggregate all runtime issues
    const runtimeIssues = results.flatMap(r => r.issues);

    const passed   = results.filter(r => r.reachable && r.issues.length === 0).length;
    const failed   = results.filter(r => r.reachable && r.issues.some(i => i.severity === "critical" || i.severity === "high")).length;
    const warnings = results.filter(r => r.reachable && r.issues.length > 0 && !r.issues.some(i => i.severity === "critical" || i.severity === "high")).length;

    const hasCritical = runtimeIssues.some(i => i.severity === "critical");
    const hasHigh     = runtimeIssues.some(i => i.severity === "high");
    const overallStatus: RuntimeQAResult["overallStatus"] =
      hasCritical ? "FAIL" : hasHigh ? "FAIL" : warnings > 0 ? "WARN" : "PASS";

    console.log(
      `[RUNTIME_QA] Result: ${overallStatus} — ` +
      `${passed} clean / ${failed} failed / ${warnings} warn | ` +
      `${runtimeIssues.length} runtime issues`
    );

    return {
      runAt:           new Date().toISOString(),
      baseUrl:         this.config.localUrl,
      realityMode:     this.config.realityMode,
      serverReachable: true,
      endpointResults: results,
      runtimeIssues,
      passed,
      failed,
      warnings,
      overallStatus,
    };
  }
}

// ─────────────────────────────────────────────────────────────
// Issue merger — REALITY_MODE logic
// ─────────────────────────────────────────────────────────────

const SEVERITY_ORDER: Record<Severity, number> = { critical: 0, high: 1, medium: 2, low: 3 };

export function mergeIssues(staticIssues: Issue[], runtimeIssues: Issue[], realityMode: boolean): Issue[] {
  if (!runtimeIssues.length) return staticIssues;

  const merged = [...staticIssues];

  for (const ri of runtimeIssues) {
    // Try to find a matching static issue by module
    const existingIdx = merged.findIndex(
      si => si.module === ri.module && si.type === ri.type
    );

    if (existingIdx >= 0) {
      const si = merged[existingIdx];
      if (realityMode && SEVERITY_ORDER[ri.severity] < SEVERITY_ORDER[si.severity]) {
        // Runtime confirms static issue with higher severity — elevate
        merged[existingIdx] = {
          ...si,
          severity: ri.severity,
          id: `${si.id}+${ri.id}`,
          problem: `[RUNTIME CONFIRMED] ${ri.problem}`,
          recommended_fix: ri.recommended_fix,
        };
      }
      // Always add as separate issue too if it's a different specific problem
      if (ri.id !== si.id) {
        merged.push({ ...ri, id: `${ri.id}` });
      }
    } else {
      merged.push(ri);
    }
  }

  // Sort: critical first, then by module
  return merged.sort((a, b) => SEVERITY_ORDER[a.severity] - SEVERITY_ORDER[b.severity]);
}
