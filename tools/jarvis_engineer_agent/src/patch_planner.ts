import * as fs from "fs";
import * as path from "path";
import { Config } from "./config";
import { Issue, Severity, IssueType } from "./issue_detector";
import { SafetyGuard } from "./safety_guard";

export interface PatchPlan {
  createdAt: string;
  mode: string;
  totalIssues: number;
  criticalCount: number;
  highCount: number;
  patches: PatchEntry[];
  blockedPatches: BlockedPatch[];
  priorityOrder: string[];
}

export interface PatchEntry {
  issueId: string;
  severity: Severity;
  type: IssueType;
  file: string;
  action: "edit" | "add_function" | "add_endpoint" | "update_catch_block";
  description: string;
  safeToAutoApply: boolean;
  requiresBackup: boolean;
  estimatedRisk: "low" | "medium" | "high";
  rollbackPlan: string;
  diffHint: string;
}

export interface BlockedPatch {
  issueId: string;
  reason: string;
  manualStepsRequired: string[];
}

const SEVERITY_ORDER: Record<Severity, number> = { critical: 0, high: 1, medium: 2, low: 3 };

export class PatchPlanner {
  private config: Config;
  private guard: SafetyGuard;

  constructor(config: Config, guard: SafetyGuard) {
    this.config = config;
    this.guard = guard;
  }

  plan(issues: Issue[]): PatchPlan {
    console.log("[PLANNER] Building patch plan...");

    const patches: PatchEntry[] = [];
    const blockedPatches: BlockedPatch[] = [];

    const sorted = [...issues].sort((a, b) => SEVERITY_ORDER[a.severity] - SEVERITY_ORDER[b.severity]);

    for (const issue of sorted) {
      const fileGuard = this.guard.checkFilePath(
        path.join(this.config.repoPath, issue.file),
        this.config.mode === "SAFE_PATCH" ? "write" : "read"
      );

      if (!fileGuard.allowed && this.config.mode === "SAFE_PATCH") {
        blockedPatches.push({
          issueId: issue.id,
          reason: fileGuard.reason,
          manualStepsRequired: [`Manually apply fix to ${issue.file}: ${issue.recommended_fix}`],
        });
        continue;
      }

      const requiresBackup = this.guard.requireBackupBefore(path.join(this.config.repoPath, issue.file));

      // Only auto-apply when: SAFE_PATCH mode + low risk + auto_fix_allowed
      const safeToAutoApply =
        this.config.mode === "SAFE_PATCH" &&
        issue.auto_fix_allowed &&
        issue.risk === "low" &&
        issue.severity !== "critical";

      patches.push({
        issueId: issue.id,
        severity: issue.severity,
        type: issue.type,
        file: issue.file,
        action: this.inferAction(issue),
        description: issue.recommended_fix,
        safeToAutoApply,
        requiresBackup,
        estimatedRisk: issue.risk as "low" | "medium" | "high",
        rollbackPlan: `git checkout HEAD -- ${issue.file}`,
        diffHint: this.buildDiffHint(issue),
      });
    }

    const criticalCount = patches.filter(p => p.severity === "critical").length;
    const highCount     = patches.filter(p => p.severity === "high").length;

    const priorityOrder = patches
      .sort((a, b) => SEVERITY_ORDER[a.severity] - SEVERITY_ORDER[b.severity])
      .map(p => `[${p.severity.toUpperCase()}] ${p.issueId} — ${p.file}`);

    console.log(
      `[PLANNER] ${patches.length} patches planned (${criticalCount} critical, ${highCount} high), ` +
      `${blockedPatches.length} blocked`
    );

    return {
      createdAt: new Date().toISOString(),
      mode: this.config.mode,
      totalIssues: issues.length,
      criticalCount,
      highCount,
      patches,
      blockedPatches,
      priorityOrder,
    };
  }

  private inferAction(issue: Issue): PatchEntry["action"] {
    if (issue.type === "UX_FIX" && issue.problem.includes("Loading")) return "update_catch_block";
    if (issue.type === "BUG_FIX" && issue.problem.includes("route")) return "add_endpoint";
    if (issue.type === "BUG_FIX" && issue.problem.includes("function")) return "add_function";
    return "edit";
  }

  private buildDiffHint(issue: Issue): string {
    switch (issue.type) {
      case "UX_FIX":
        return `In catch block: element.textContent = "Error — ${issue.module} no disponible";`;
      case "BUG_FIX":
        if (issue.problem.includes("route")) {
          return `@app.get("${issue.file}")\ndef handler(): return {"status": "ok"}`;
        }
        return `# Apply fix: ${issue.recommended_fix}`;
      case "AGENT_QUALITY":
        return `# Improve agent prompt to include Spanish-first behavior and structured output`;
      default:
        return `# Manual review required: ${issue.recommended_fix}`;
    }
  }

  formatMarkdown(plan: PatchPlan): string {
    const lines: string[] = [
      `# JARVIS Engineer Agent — Patch Plan`,
      ``,
      `**Generated:** ${plan.createdAt}`,
      `**Mode:** ${plan.mode}`,
      `**Total issues:** ${plan.totalIssues}`,
      `**Critical:** ${plan.criticalCount} | **High:** ${plan.highCount}`,
      ``,
      `---`,
      ``,
      `## Priority Order`,
      ``,
      ...plan.priorityOrder.map(p => `- ${p}`),
      ``,
      `---`,
      ``,
      `## Patches`,
      ``,
    ];

    for (const patch of plan.patches) {
      lines.push(
        `### ${patch.issueId} [${patch.severity.toUpperCase()}] — ${patch.file}`,
        ``,
        `**Type:** ${patch.type}`,
        `**Action:** ${patch.action}`,
        `**Risk:** ${patch.estimatedRisk}`,
        `**Auto-apply:** ${patch.safeToAutoApply ? "✅ Allowed" : "❌ Manual required"}`,
        `**Requires backup:** ${patch.requiresBackup ? "Yes" : "No"}`,
        ``,
        `**Description:**`,
        patch.description,
        ``,
        `**Rollback:**`,
        `\`\`\`bash`,
        patch.rollbackPlan,
        `\`\`\``,
        ``,
        `**Diff hint:**`,
        `\`\`\``,
        patch.diffHint,
        `\`\`\``,
        ``,
        `---`,
        ``,
      );
    }

    if (plan.blockedPatches.length) {
      lines.push(`## Blocked Patches (Manual Required)`, ``);
      for (const bp of plan.blockedPatches) {
        lines.push(
          `### ${bp.issueId}`,
          `**Reason:** ${bp.reason}`,
          ``,
          `**Manual steps:**`,
          ...bp.manualStepsRequired.map(s => `- ${s}`),
          ``,
        );
      }
    }

    return lines.join("\n");
  }
}
