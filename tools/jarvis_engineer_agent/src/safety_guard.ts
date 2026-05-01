import * as path from "path";
import { Config } from "./config";

// Commands that are unconditionally blocked
const BLOCKED_COMMANDS: readonly string[] = [
  "rm -rf",
  "git push",
  "git push --force",
  "railway deploy",
  "railway down",
  "del /s",
  "rmdir /s",
  "DROP DATABASE",
  "DROP TABLE",
  "TRUNCATE",
  "truncate",
  "format c:",
  "deltree",
  "rd /s",
  "npx railway",
];

// File patterns that must never be written/deleted
const PROTECTED_PATHS: readonly string[] = [
  ".env",
  "data/",
  "memory/",
  "generated_audio/",
  "logs/",
  "railway.toml",
  "railway.json",
  ".railwayignore",
  "Procfile",
  "*.key",
  "*.pem",
  "*.secret",
  "backup/",
  "backups/",
];

// Files safe to read but never auto-delete
const NEVER_DELETE: readonly string[] = [
  "main.py",
  "dashboard/jarvis_futuristic.html",
  "core/ai_orchestrator.py",
  "core/product_brain_pro.py",
  "core/golf_dashboard_engine.py",
];

export interface GuardResult {
  allowed: boolean;
  reason: string;
  severity: "ok" | "warn" | "blocked";
}

export class SafetyGuard {
  private config: Config;

  constructor(config: Config) {
    this.config = config;
  }

  checkCommand(cmd: string): GuardResult {
    const lower = cmd.toLowerCase().trim();
    for (const blocked of BLOCKED_COMMANDS) {
      if (lower.includes(blocked.toLowerCase())) {
        return {
          allowed: false,
          reason: `BLOCKED: command contains prohibited pattern "${blocked}"`,
          severity: "blocked",
        };
      }
    }
    // Warn on git operations
    if (lower.startsWith("git ") && !lower.startsWith("git diff") && !lower.startsWith("git status") && !lower.startsWith("git log")) {
      return {
        allowed: false,
        reason: `BLOCKED: git write operation not permitted (use: git diff / git status / git log only)`,
        severity: "blocked",
      };
    }
    return { allowed: true, reason: "ok", severity: "ok" };
  }

  checkFilePath(filePath: string, operation: "read" | "write" | "delete"): GuardResult {
    const normalized = filePath.replace(/\\/g, "/");
    const rel = normalized.includes(this.config.repoPath.replace(/\\/g, "/"))
      ? normalized.replace(this.config.repoPath.replace(/\\/g, "/"), "").replace(/^\//, "")
      : normalized;

    // Block .env always
    if (rel === ".env" || rel.endsWith("/.env")) {
      return { allowed: false, reason: `BLOCKED: .env file is protected`, severity: "blocked" };
    }

    // Block secrets
    if (rel.match(/\.(key|pem|secret|crt|pfx)$/i)) {
      return { allowed: false, reason: `BLOCKED: credential file "${rel}"`, severity: "blocked" };
    }

    if (operation === "delete" || operation === "write") {
      // Block protected paths
      for (const p of PROTECTED_PATHS) {
        if (p.endsWith("/") && rel.startsWith(p)) {
          return { allowed: false, reason: `BLOCKED: "${rel}" is in protected folder "${p}"`, severity: "blocked" };
        }
        if (!p.endsWith("/") && rel === p) {
          return { allowed: false, reason: `BLOCKED: "${rel}" is a protected file`, severity: "blocked" };
        }
      }

      // Block delete of critical files
      if (operation === "delete") {
        for (const nd of NEVER_DELETE) {
          if (rel === nd || rel.endsWith("/" + nd)) {
            return { allowed: false, reason: `BLOCKED: cannot delete critical file "${rel}"`, severity: "blocked" };
          }
        }
      }

      // In DRY_RUN mode, no writes at all
      if (this.config.dryRun && operation === "write") {
        return { allowed: false, reason: `DRY_RUN: write blocked — use SAFE_PATCH mode to apply changes`, severity: "warn" };
      }
    }

    return { allowed: true, reason: "ok", severity: "ok" };
  }

  requireBackupBefore(filePath: string): boolean {
    const rel = filePath.replace(/\\/g, "/").replace(this.config.repoPath.replace(/\\/g, "/") + "/", "");
    const requiresBackup = [".html", ".py", ".ts", ".js", ".json"].some(ext => rel.endsWith(ext));
    return requiresBackup;
  }

  assertSafe(cmd: string): void {
    const result = this.checkCommand(cmd);
    if (!result.allowed) {
      throw new Error(`[SAFETY_GUARD] ${result.reason}`);
    }
  }

  logGuardDecision(result: GuardResult, context: string): void {
    const prefix = result.severity === "blocked" ? "🚫 BLOCKED" :
                   result.severity === "warn"    ? "⚠️  WARN" : "✅ OK";
    console.log(`[GUARD] ${prefix} [${context}] ${result.reason}`);
  }
}
