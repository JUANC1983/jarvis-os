import * as https from "https";
import * as http from "http";
import { Config } from "./config";
import { SafetyGuard } from "./safety_guard";
import { Issue } from "./issue_detector";

export interface AgentTask {
  prompt: string;
  context: string;
  targetFile?: string;
  mode: "analyze" | "suggest" | "patch";
}

export interface AgentResponse {
  success: boolean;
  source: "cursor" | "local_fallback";
  response: string;
  error?: string;
}

// Safe task templates — these never ask Cursor to push/deploy/delete
const SAFE_TASK_TEMPLATES: Record<string, (ctx: string) => string> = {
  dead_buttons:     (ctx) => `Analyze this JARVIS dashboard code and identify all buttons that have onclick handlers calling functions that do not exist. List each button's text and the missing function name.\n\n${ctx}`,
  outlook_audit:    (ctx) => `Audit this JARVIS Outlook polling code. Check: (1) deduplication before AI processing, (2) 401 error handling, (3) token refresh flow. Report issues only. Do not modify.\n\n${ctx}`,
  trader_prompt:    (ctx) => `Review this trading agent implementation. Identify: (1) missing catalyst/risk/thesis fields, (2) hallucination risks, (3) missing uncertainty handling. Suggest improvements.\n\n${ctx}`,
  qa_report:        (ctx) => `Run a QA analysis of this JARVIS backend code. Identify: missing routes, unhandled exceptions, silent failures. Report in JSON format with severity levels.\n\n${ctx}`,
  suggest_patch:    (ctx) => `Suggest a minimal, safe patch for this issue in JARVIS. Provide exact diff format. Do NOT suggest deleting files, pushing to git, or deploying.\n\n${ctx}`,
};

export class AgentRunner {
  private config: Config;
  private guard: SafetyGuard;

  constructor(config: Config, guard: SafetyGuard) {
    this.config = config;
    this.guard = guard;
  }

  async runTask(task: AgentTask): Promise<AgentResponse> {
    // Safety: never run patch tasks in DRY_RUN mode
    if (task.mode === "patch" && this.config.dryRun) {
      return {
        success: false,
        source: "local_fallback",
        response: "",
        error: "DRY_RUN mode: patch tasks are blocked. Switch to SAFE_PATCH mode.",
      };
    }

    // Try Cursor SDK if key available
    if (this.config.cursorAvailable && this.config.cursorApiKey) {
      try {
        const result = await this.callCursorAPI(task);
        return { success: true, source: "cursor", response: result };
      } catch (err) {
        console.warn(`[AGENT] Cursor API failed: ${err} — falling back to local analysis`);
      }
    }

    // Local fallback — structured analysis without external API
    return this.localFallback(task);
  }

  private callCursorAPI(task: AgentTask): Promise<string> {
    return new Promise((resolve, reject) => {
      const body = JSON.stringify({
        model: "cursor-small",
        messages: [
          {
            role: "system",
            content: "You are a safe engineering assistant for the JARVIS project. Never suggest deleting files, pushing to git, or deploying. Always output structured analysis.",
          },
          { role: "user", content: task.prompt },
        ],
        max_tokens: 1500,
      });

      const options = {
        hostname: "api.cursor.sh",
        path: "/v1/chat/completions",
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          "Authorization": `Bearer ${this.config.cursorApiKey}`,
          "Content-Length": Buffer.byteLength(body),
        },
        timeout: 30000,
      };

      const req = https.request(options, (res) => {
        let data = "";
        res.on("data", (chunk) => data += chunk);
        res.on("end", () => {
          try {
            const parsed = JSON.parse(data);
            const content = parsed?.choices?.[0]?.message?.content;
            if (content) resolve(content);
            else reject(new Error(`Cursor API returned no content: ${data.slice(0, 200)}`));
          } catch (e) {
            reject(new Error(`Failed to parse Cursor response: ${data.slice(0, 200)}`));
          }
        });
      });

      req.on("error", reject);
      req.on("timeout", () => { req.destroy(); reject(new Error("Cursor API timeout")); });
      req.write(body);
      req.end();
    });
  }

  private localFallback(task: AgentTask): AgentResponse {
    // Structured local analysis based on task type
    const analysis = this.analyzeLocally(task);
    return {
      success: true,
      source: "local_fallback",
      response: analysis,
    };
  }

  private analyzeLocally(task: AgentTask): string {
    const lines: string[] = [
      `[LOCAL ANALYSIS — Cursor API not available]`,
      `Task: ${task.prompt.slice(0, 100)}...`,
      `Mode: ${task.mode}`,
      ``,
      `Recommendation:`,
    ];

    if (task.mode === "analyze") {
      lines.push(
        `1. Review the identified issue in file: ${task.targetFile || "see context"}`,
        `2. Apply the recommended fix from the patch plan`,
        `3. Test with: python -m py_compile main.py && python -c "import main; print('OK')"`,
        `4. Backup the file before any edits: git stash or cp file file.bak`,
      );
    } else if (task.mode === "suggest") {
      lines.push(
        `1. See latest_patch_plan.md for detailed fix instructions`,
        `2. Each patch includes a rollback plan (git checkout HEAD -- <file>)`,
        `3. Run npm run qa after applying any patch`,
      );
    }

    lines.push(``, `To enable AI-powered analysis: set CURSOR_API_KEY in .env`);
    return lines.join("\n");
  }

  buildIssueTask(issue: Issue): AgentTask {
    return {
      prompt: `${issue.problem}\n\nRecommended fix: ${issue.recommended_fix}\nFile: ${issue.file}`,
      context: `Issue ID: ${issue.id}, Severity: ${issue.severity}, Module: ${issue.module}`,
      targetFile: issue.file,
      mode: "suggest",
    };
  }
}
