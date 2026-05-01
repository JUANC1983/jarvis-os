import * as fs from "fs";
import * as path from "path";
import { Config } from "./config";
import { RepoMap } from "./repo_scanner";

export type Severity = "critical" | "high" | "medium" | "low";
export type IssueType =
  | "BUG_FIX" | "QA_IMPROVEMENT" | "PERFORMANCE"
  | "UX_FIX" | "AGENT_QUALITY" | "NEW_TECH_SUGGESTION" | "RISKY_CHANGE";

export interface Issue {
  id: string;
  severity: Severity;
  type: IssueType;
  module: string;
  file: string;
  problem: string;
  recommended_fix: string;
  risk: string;
  auto_fix_allowed: boolean;
}

let _issueCounter = 0;
function issueId(prefix: string): string {
  return `${prefix}_${String(++_issueCounter).padStart(3, "0")}`;
}

export class IssueDetector {
  private config: Config;
  private repoMap: RepoMap;

  constructor(config: Config, repoMap: RepoMap) {
    this.config = config;
    this.repoMap = repoMap;
  }

  private readFile(relPath: string): string {
    try {
      return fs.readFileSync(path.join(this.config.repoPath, relPath), "utf-8");
    } catch {
      return "";
    }
  }

  private detectStuckLoadingStates(): Issue[] {
    const issues: Issue[] = [];
    const html = this.readFile("dashboard/jarvis_futuristic.html");
    if (!html) return issues;

    // Find id="..." elements whose initial content is "Loading..." or "Loading…"
    const loadingPattern = /id="([^"]+)"[^>]*>[^<]*Loading[…\.]{2,}/g;
    const catches = [...html.matchAll(loadingPattern)];
    for (const m of catches) {
      const elemId = m[1];
      // Check if there's a corresponding catch that clears this element
      const clearPattern = new RegExp(`qs\\(["']${elemId}["']\\)`, "g");
      const clearMatches = [...html.matchAll(clearPattern)];
      if (clearMatches.length < 2) {
        issues.push({
          id: issueId("LOADING"),
          severity: "medium",
          type: "UX_FIX",
          module: "dashboard",
          file: "dashboard/jarvis_futuristic.html",
          problem: `Element #${elemId} shows "Loading…" and may not be cleared on error`,
          recommended_fix: `Add catch block that sets qs("${elemId}").textContent to a descriptive error message`,
          risk: "low",
          auto_fix_allowed: false,
        });
      }
    }
    return issues;
  }

  private detectDeadButtons(): Issue[] {
    const issues: Issue[] = [];
    const html = this.readFile("dashboard/jarvis_futuristic.html");
    if (!html) return issues;

    // JS keywords / builtins that are not user-defined functions
    const JS_KEYWORDS = new Set([
      "if", "for", "while", "switch", "return", "typeof", "instanceof",
      "new", "delete", "void", "throw", "try", "catch", "finally",
      "function", "class", "import", "export", "const", "let", "var",
      "true", "false", "null", "undefined", "this", "super",
      "document", "window", "console", "setTimeout", "setInterval",
      "Promise", "fetch", "JSON", "Math", "Object", "Array", "String",
      "Number", "Boolean", "Date", "RegExp", "Error", "Event",
    ]);

    // Buttons with onclick but no corresponding function definition
    const btnPattern = /onclick="([a-zA-Z_]\w*)\(/g;
    const funcPattern = /function ([a-zA-Z_]\w*)\s*\(/g;
    const allFunctions = new Set([...html.matchAll(funcPattern)].map(m => m[1]));
    // Also include event-bound names via on("...", fn)
    const evPattern = /on\(["'](\w+)["'],\s*(\w+)\)/g;
    for (const m of html.matchAll(evPattern)) allFunctions.add(m[2]);

    const seen = new Set<string>();
    for (const m of html.matchAll(btnPattern)) {
      const fn = m[1];
      if (seen.has(fn)) continue;
      seen.add(fn);
      // Skip JS keywords and builtins
      if (JS_KEYWORDS.has(fn)) continue;
      // Skip underscore-prefixed globals (browser APIs like _gaq etc.)
      if (fn.startsWith("_") && fn.length < 4) continue;
      if (!allFunctions.has(fn)) {
        issues.push({
          id: issueId("DEAD_BTN"),
          severity: "high",
          type: "BUG_FIX",
          module: "dashboard",
          file: "dashboard/jarvis_futuristic.html",
          problem: `Button calls onclick="${fn}()" but function "${fn}" is not defined in the dashboard`,
          recommended_fix: `Define function ${fn}() or remove the dead button`,
          risk: "low",
          auto_fix_allowed: false,
        });
      }
    }
    return issues;
  }

  private detectMissingRoutes(): Issue[] {
    const issues: Issue[] = [];
    const registeredRoutes = new Set(
      this.repoMap.mainRoutes.map(r => r.replace(/^(GET|POST|PUT|PATCH|DELETE)\s+/, ""))
    );

    // Also build a set without path parameters for fuzzy matching
    // e.g. /dashboard/tasks/{task_id} → /dashboard/tasks/
    const routePrefixes = new Set(
      [...registeredRoutes].map(r => r.replace(/\{[^}]+\}/g, "").replace(/\/+$/, ""))
    );

    for (const fetchUrl of this.repoMap.frontendFetches) {
      // Skip dynamic urls with template expressions
      if (fetchUrl.includes("${") || fetchUrl.includes("{") || fetchUrl.startsWith("http")) continue;
      // Skip relative paths that aren't API routes
      if (!fetchUrl.startsWith("/api/") && !fetchUrl.startsWith("/dashboard/") && !fetchUrl.startsWith("/jarvis/")) continue;
      // Strip query string and trailing slash
      const clean = fetchUrl.split("?")[0].replace(/\/+$/, "");
      if (!clean) continue;

      // Check exact match
      if (registeredRoutes.has(clean)) continue;
      // Check if it's a parameterized route prefix match
      const matchedPrefix = [...routePrefixes].some(prefix =>
        prefix && (clean === prefix || clean.startsWith(prefix + "/"))
      );
      if (matchedPrefix) continue;

      issues.push({
        id: issueId("MISSING_ROUTE"),
        severity: "high",
        type: "BUG_FIX",
        module: "backend",
        file: "main.py",
        problem: `Frontend fetches "${clean}" but no matching route found in main.py`,
        recommended_fix: `Add @app.get("${clean}") or @app.post("${clean}") to main.py, or check if URL is dynamic`,
        risk: "medium",
        auto_fix_allowed: false,
      });
    }
    return issues;
  }

  private detectFakeData(): Issue[] {
    const issues: Issue[] = [];
    const mainPy = this.readFile("main.py");
    if (!mainPy) return issues;

    const fakePatterns = [
      { pattern: /random\.\w+\([\d.,\s]+\)/g, name: "random number" },
      { pattern: /fake_price|FAKE_PRICE/g, name: "fake_price" },
      { pattern: /"price":\s*\d+\.\d+[^,\n]{0,30}#\s*fake/gi, name: "hardcoded fake price comment" },
    ];

    for (const { pattern, name } of fakePatterns) {
      const matches = [...mainPy.matchAll(pattern)];
      if (matches.length) {
        issues.push({
          id: issueId("FAKE_DATA"),
          severity: "high",
          type: "BUG_FIX",
          module: "markets",
          file: "main.py",
          problem: `Detected potential fake/hardcoded data pattern: ${name} (${matches.length} occurrence(s))`,
          recommended_fix: "Replace with real yfinance / API calls",
          risk: "medium",
          auto_fix_allowed: false,
        });
      }
    }
    return issues;
  }

  private detectAgentQuality(): Issue[] {
    const issues: Issue[] = [];
    const orchestratorPath = "core/ai_orchestrator.py";
    const content = this.readFile(orchestratorPath);
    if (!content) return issues;

    // Check for Spanish-first behavior
    if (!content.includes("_is_spanish") && !content.includes("spanish")) {
      issues.push({
        id: issueId("AGENT_LANG"),
        severity: "medium",
        type: "AGENT_QUALITY",
        module: "ai_orchestrator",
        file: orchestratorPath,
        problem: "No Spanish-first detection found in ai_orchestrator.py",
        recommended_fix: "Add _is_spanish() heuristic and respond in Spanish when detected",
        risk: "low",
        auto_fix_allowed: false,
      });
    }

    // Check for generic fallback responses
    const genericPatterns = ["I don't know", "I cannot", "As an AI language model"];
    for (const gp of genericPatterns) {
      if (content.includes(gp)) {
        issues.push({
          id: issueId("AGENT_GENERIC"),
          severity: "low",
          type: "AGENT_QUALITY",
          module: "ai_orchestrator",
          file: orchestratorPath,
          problem: `Generic AI response pattern found: "${gp}"`,
          recommended_fix: "Replace with JARVIS-specific, contextual responses",
          risk: "low",
          auto_fix_allowed: false,
        });
      }
    }
    return issues;
  }

  private detectOutlookIssues(): Issue[] {
    const issues: Issue[] = [];
    const mainPy = this.readFile("main.py");
    if (!mainPy) return issues;

    // Check polling deduplication
    if (!mainPy.includes("_ms_email_store.get") && !mainPy.includes("email_store")) {
      issues.push({
        id: issueId("OUTLOOK_DEDUP"),
        severity: "high",
        type: "BUG_FIX",
        module: "outlook",
        file: "main.py",
        problem: "Outlook polling may process duplicate emails — no deduplication store found",
        recommended_fix: "Add email_store.get(msg_id) check before AI processing",
        risk: "high",
        auto_fix_allowed: false,
      });
    }

    // Check for 401 handling
    if (!mainPy.includes("reauth_required")) {
      issues.push({
        id: issueId("OUTLOOK_401"),
        severity: "high",
        type: "BUG_FIX",
        module: "outlook",
        file: "main.py",
        problem: "No reauth_required flag in Outlook error responses",
        recommended_fix: "Return reauth_required:true on 401 so frontend can prompt re-authentication",
        risk: "medium",
        auto_fix_allowed: false,
      });
    }
    return issues;
  }

  private detectVoiceIssues(): Issue[] {
    const issues: Issue[] = [];
    const mainPy = this.readFile("main.py");
    if (!mainPy) return issues;

    if (!mainPy.includes("tts_available") && !mainPy.includes("ELEVENLABS")) {
      issues.push({
        id: issueId("VOICE_FALLBACK"),
        severity: "medium",
        type: "BUG_FIX",
        module: "voice",
        file: "main.py",
        problem: "No ElevenLabs TTS fallback detected — voice may fail silently",
        recommended_fix: "Return {tts_available:false, tts_reason:'...'} when ELEVENLABS_API_KEY not set",
        risk: "low",
        auto_fix_allowed: false,
      });
    }

    // Check voice routes through command router
    if (!mainPy.includes("_COMMAND_ROUTES") || !mainPy.includes("voice_command")) {
      issues.push({
        id: issueId("VOICE_ROUTER"),
        severity: "high",
        type: "BUG_FIX",
        module: "voice",
        file: "main.py",
        problem: "Voice command does not appear to route through central command router",
        recommended_fix: "Wire voice_command() through _COMMAND_ROUTES for consistent intent handling",
        risk: "medium",
        auto_fix_allowed: false,
      });
    }
    return issues;
  }

  private detectCalendarIssues(): Issue[] {
    const issues: Issue[] = [];
    const html = this.readFile("dashboard/jarvis_futuristic.html");
    if (!html) return issues;

    if (!html.includes("Calendario no conectado") && !html.includes("not connected") && !html.includes("calendar.*connect")) {
      issues.push({
        id: issueId("CAL_STATE"),
        severity: "medium",
        type: "UX_FIX",
        module: "calendar",
        file: "dashboard/jarvis_futuristic.html",
        problem: "Calendar does not show a clear 'not connected' state when Google Calendar / Outlook is not configured",
        recommended_fix: "Detect status:'error' in API response and show 'Calendario no conectado' message",
        risk: "low",
        auto_fix_allowed: false,
      });
    }
    return issues;
  }

  private detectGolfIntegrity(): Issue[] {
    const issues: Issue[] = [];
    // Verify golf module is present — DO NOT SUGGEST REMOVAL
    const golfEngine = path.join(this.config.repoPath, "core", "golf_dashboard_engine.py");
    const golfHtml = this.readFile("dashboard/jarvis_futuristic.html");

    if (!fs.existsSync(golfEngine)) {
      issues.push({
        id: issueId("GOLF_MISSING"),
        severity: "critical",
        type: "BUG_FIX",
        module: "golf",
        file: "core/golf_dashboard_engine.py",
        problem: "golf_dashboard_engine.py is missing from core/",
        recommended_fix: "Restore golf_dashboard_engine.py from version control",
        risk: "high",
        auto_fix_allowed: false,
      });
    }

    if (golfHtml && !golfHtml.includes("tab-golf") && !golfHtml.includes('data-tab="golf"')) {
      issues.push({
        id: issueId("GOLF_TAB"),
        severity: "critical",
        type: "BUG_FIX",
        module: "golf",
        file: "dashboard/jarvis_futuristic.html",
        problem: "Golf tab not found in dashboard HTML",
        recommended_fix: "Restore golf tab panel and nav button",
        risk: "high",
        auto_fix_allowed: false,
      });
    }

    return issues;
  }

  private detectLargeFiles(): Issue[] {
    return this.repoMap.largeFiles.map(f => ({
      id: issueId("LARGE_FILE"),
      severity: "low" as Severity,
      type: "PERFORMANCE" as IssueType,
      module: "repo",
      file: f.relativePath,
      problem: `Large file: ${f.sizeKb}KB / ${f.lines} lines — may slow CI and code review`,
      recommended_fix: "Consider splitting into smaller modules if possible",
      risk: "low",
      auto_fix_allowed: false,
    }));
  }

  detect(): Issue[] {
    console.log("[DETECTOR] Running issue detection...");

    const issues: Issue[] = [
      ...this.detectStuckLoadingStates(),
      ...this.detectDeadButtons(),
      ...this.detectMissingRoutes(),
      ...this.detectFakeData(),
      ...this.detectAgentQuality(),
      ...this.detectOutlookIssues(),
      ...this.detectVoiceIssues(),
      ...this.detectCalendarIssues(),
      ...this.detectGolfIntegrity(),
      ...this.detectLargeFiles(),
    ];

    const counts: Record<Severity, number> = { critical: 0, high: 0, medium: 0, low: 0 };
    for (const i of issues) counts[i.severity]++;

    console.log(
      `[DETECTOR] Found ${issues.length} issues: ` +
      `${counts.critical} critical / ${counts.high} high / ${counts.medium} medium / ${counts.low} low`
    );
    return issues;
  }
}
