import { execSync, spawnSync } from "child_process";
import * as path from "path";
import { Config } from "./config";
import { SafetyGuard } from "./safety_guard";

export interface QAResult {
  runAt: string;
  repoPath: string;
  checks: QACheck[];
  passed: number;
  failed: number;
  warnings: number;
  overallStatus: "PASS" | "FAIL" | "WARN";
}

export interface QACheck {
  name: string;
  status: "pass" | "fail" | "warn" | "skip";
  detail: string;
  duration_ms: number;
}

const SAFE_COMMANDS: readonly string[] = [
  "python -m py_compile",
  "python -c",
  "python --version",
];

function isSafeQACommand(cmd: string): boolean {
  return SAFE_COMMANDS.some(safe => cmd.trim().startsWith(safe));
}

export class QARunner {
  private config: Config;
  private guard: SafetyGuard;

  constructor(config: Config, guard: SafetyGuard) {
    this.config = config;
    this.guard = guard;
  }

  private runPy(args: string[], label: string): QACheck {
    const t0 = Date.now();
    const guardResult = this.guard.checkCommand(`python ${args.join(" ")}`);
    if (!guardResult.allowed) {
      return { name: label, status: "skip", detail: guardResult.reason, duration_ms: 0 };
    }
    const result = spawnSync("python", args, {
      cwd: this.config.repoPath,
      encoding: "utf-8",
      timeout: 30000,
    });
    const duration_ms = Date.now() - t0;
    if (result.error) {
      return { name: label, status: "fail", detail: result.error.message, duration_ms };
    }
    if (result.status !== 0) {
      return { name: label, status: "fail", detail: (result.stderr || result.stdout || "non-zero exit").trim().slice(0, 500), duration_ms };
    }
    return { name: label, status: "pass", detail: (result.stdout || "OK").trim().slice(0, 200), duration_ms };
  }

  private checkImport(module: string): QACheck {
    return this.runPy(["-c", `import ${module}; print('${module} OK')`], `import:${module}`);
  }

  private checkFileExists(relPath: string): QACheck {
    const abs = path.join(this.config.repoPath, relPath);
    const fs = require("fs");
    if (fs.existsSync(abs)) {
      return { name: `file_exists:${relPath}`, status: "pass", detail: "File present", duration_ms: 0 };
    }
    return { name: `file_exists:${relPath}`, status: "fail", detail: `Missing: ${relPath}`, duration_ms: 0 };
  }

  private checkRequirements(): QACheck {
    const t0 = Date.now();
    const reqPath = path.join(this.config.repoPath, "requirements.txt");
    const fs = require("fs");
    if (!fs.existsSync(reqPath)) {
      return { name: "requirements.txt", status: "warn", detail: "requirements.txt not found", duration_ms: 0 };
    }
    const content = fs.readFileSync(reqPath, "utf-8");
    const deps = content.split("\n").filter((l: string) => l.trim() && !l.startsWith("#")).length;
    return { name: "requirements.txt", status: "pass", detail: `${deps} dependencies listed`, duration_ms: Date.now() - t0 };
  }

  private checkMainRouteCount(): QACheck {
    const t0 = Date.now();
    const fs = require("fs");
    const mainPy = path.join(this.config.repoPath, "main.py");
    if (!fs.existsSync(mainPy)) {
      return { name: "main.py:routes", status: "fail", detail: "main.py not found", duration_ms: 0 };
    }
    const content = fs.readFileSync(mainPy, "utf-8");
    const routes = (content.match(/@app\.(get|post|put|patch|delete)\(/g) || []).length;
    const status = routes > 0 ? "pass" : "fail";
    return { name: "main.py:routes", status, detail: `${routes} routes registered`, duration_ms: Date.now() - t0 };
  }

  private checkEnvExample(): QACheck {
    const fs = require("fs");
    const envEx = path.join(this.config.repoPath, ".env.example");
    const envFile = path.join(this.config.repoPath, ".env");
    if (fs.existsSync(envFile)) {
      const content = fs.readFileSync(envFile, "utf-8");
      // Warn if it looks like it has real keys (non-empty values after =)
      const hasRealKeys = content.split("\n").some((line: string) => {
        const [, val] = line.split("=");
        return val && val.trim().length > 10 && !val.trim().startsWith("<");
      });
      if (hasRealKeys) {
        return { name: ".env:safety", status: "warn", detail: ".env has non-empty values — ensure it is in .gitignore", duration_ms: 0 };
      }
    }
    return { name: ".env:safety", status: "pass", detail: ".env not exposed in repo scan", duration_ms: 0 };
  }

  private checkGitIgnore(): QACheck {
    const fs = require("fs");
    const gi = path.join(this.config.repoPath, ".gitignore");
    if (!fs.existsSync(gi)) {
      return { name: ".gitignore", status: "warn", detail: ".gitignore missing", duration_ms: 0 };
    }
    const content = fs.readFileSync(gi, "utf-8");
    const hasEnv = content.includes(".env");
    const hasData = content.includes("data/") || content.includes("*.db");
    if (!hasEnv) {
      return { name: ".gitignore", status: "warn", detail: ".env not in .gitignore — potential secret exposure", duration_ms: 0 };
    }
    return { name: ".gitignore", status: "pass", detail: `.env protected. data: ${hasData}`, duration_ms: 0 };
  }

  run(): QAResult {
    console.log("[QA] Running safe QA checks...");

    const checks: QACheck[] = [
      // Core compile + import
      this.runPy(["-m", "py_compile", "main.py"], "py_compile:main.py"),
      this.checkImport("fastapi"),
      this.checkImport("uvicorn"),
      this.checkImport("httpx"),
      this.checkImport("feedparser"),
      // File presence
      this.checkFileExists("main.py"),
      this.checkFileExists("dashboard/jarvis_futuristic.html"),
      this.checkFileExists("core/ai_orchestrator.py"),
      this.checkFileExists("core/product_brain_pro.py"),
      this.checkFileExists("core/golf_dashboard_engine.py"),
      this.checkFileExists("core/live_news_engine.py"),
      this.checkFileExists("opsx/connectors/outlook_auth.py"),
      this.checkFileExists("opsx/connectors/outlook_webhook.py"),
      // Route count
      this.checkMainRouteCount(),
      this.checkRequirements(),
      // Security
      this.checkEnvExample(),
      this.checkGitIgnore(),
    ];

    const passed   = checks.filter(c => c.status === "pass").length;
    const failed   = checks.filter(c => c.status === "fail").length;
    const warnings = checks.filter(c => c.status === "warn").length;

    const overallStatus: QAResult["overallStatus"] =
      failed > 0 ? "FAIL" : warnings > 0 ? "WARN" : "PASS";

    checks.forEach(c => {
      const icon = c.status === "pass" ? "✅" : c.status === "fail" ? "❌" : c.status === "warn" ? "⚠️ " : "⏭️ ";
      console.log(`  ${icon} [${c.name}] ${c.detail}`);
    });

    console.log(`\n[QA] Result: ${overallStatus} — ${passed} pass / ${failed} fail / ${warnings} warn`);

    return {
      runAt: new Date().toISOString(),
      repoPath: this.config.repoPath,
      checks,
      passed,
      failed,
      warnings,
      overallStatus,
    };
  }
}
