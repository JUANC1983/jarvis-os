#!/usr/bin/env ts-node
/**
 * JARVIS Engineer Agent — Main Entry Point
 *
 * Modes:
 *   --mode=scan        Map repo, write scan report
 *   --mode=qa          Run safe QA checks
 *   --mode=audit       Full scan + QA + issue detection
 *   --mode=plan        Audit + generate patch plan
 *   --mode=safe-patch  Plan + apply low-risk auto-fixes (requires SAFE_PATCH env mode)
 *
 * Safety:
 *   - Defaults to DRY_RUN (no file writes)
 *   - SafetyGuard blocks destructive commands
 *   - All reports written to tools/jarvis_engineer_agent/reports/
 */

import { loadConfig } from "./config";
import { SafetyGuard } from "./safety_guard";
import { RepoScanner } from "./repo_scanner";
import { QARunner } from "./qa_runner";
import { IssueDetector } from "./issue_detector";
import { PatchPlanner } from "./patch_planner";
import { AgentRunner } from "./agent_runner";
import { RuntimeQA, mergeIssues } from "./runtime_qa";
import {
  writeScanReport,
  writeQAReport,
  writeIssuesReport,
  writePatchPlan,
  writeRuntimeQAReport,
  printSummary,
} from "./reports";

// Parse CLI args
function getMode(): string {
  for (const arg of process.argv.slice(2)) {
    if (arg.startsWith("--mode=")) return arg.replace("--mode=", "").toLowerCase();
  }
  return "scan";
}

function getModes(): string[] {
  return ["scan", "qa", "audit", "plan", "safe-patch", "runtime"];
}

async function main(): Promise<void> {
  const config = loadConfig();
  const guard  = new SafetyGuard(config);
  const mode   = getMode();

  console.log(`\n${"═".repeat(60)}`);
  console.log(`  JARVIS ENGINEER AGENT — ${mode.toUpperCase()}`);
  console.log(`${"═".repeat(60)}\n`);

  const scanner = new RepoScanner(config);
  const runner  = new AgentRunner(config, guard);

  if (mode === "scan") {
    const repoMap = scanner.scan();
    const scanPath = writeScanReport(repoMap);
    console.log(`\n✅ Scan complete. Report: ${scanPath}`);
    console.log(`   ${repoMap.summary.totalPythonFiles} Python files`);
    console.log(`   ${repoMap.summary.totalRoutes} backend routes`);
    console.log(`   ${repoMap.summary.totalFrontendFetches} frontend fetch() calls`);
    console.log(`   ${repoMap.summary.largeFileCount} large files (>200KB)`);
    return;
  }

  if (mode === "qa") {
    const qaRunner = new QARunner(config, guard);
    const qa = qaRunner.run();
    writeQAReport(qa);
    const qaIcon = qa.overallStatus === "PASS" ? "✅" : qa.overallStatus === "WARN" ? "⚠️ " : "❌";
    console.log(`\n${qaIcon} QA ${qa.overallStatus}`);
    return;
  }

  if (mode === "runtime") {
    const rtQA   = new RuntimeQA(config);
    const result = await rtQA.run();
    writeRuntimeQAReport(result);
    const icon =
      result.overallStatus === "OFFLINE" ? "⚪" :
      result.overallStatus === "PASS"    ? "✅" :
      result.overallStatus === "WARN"    ? "⚠️ " : "❌";
    console.log(`\n${icon} Runtime QA: ${result.overallStatus}`);
    if (!result.serverReachable) {
      console.log(`   Server offline at ${result.baseUrl}`);
    } else {
      console.log(`   ${result.passed} clean / ${result.failed} failed / ${result.warnings} warnings`);
      console.log(`   ${result.runtimeIssues.length} issue(s) found`);
    }
    return;
  }

  if (mode === "audit" || mode === "plan" || mode === "safe-patch") {
    // Full pipeline: scan → qa → detect → (optional runtime qa) → plan
    const repoMap  = scanner.scan();
    const qaRunner = new QARunner(config, guard);
    const qa       = qaRunner.run();
    const detector = new IssueDetector(config, repoMap);
    let   issues   = detector.detect();

    // Runtime QA: always run, merge results when realityMode is on
    const rtQA       = new RuntimeQA(config);
    const runtimeResult = await rtQA.run();
    writeRuntimeQAReport(runtimeResult);
    if (runtimeResult.serverReachable) {
      issues = mergeIssues(issues, runtimeResult.runtimeIssues, config.realityMode);
    }

    const planner  = new PatchPlanner(config, guard);
    const plan     = planner.plan(issues);
    const markdown = planner.formatMarkdown(plan);

    writeScanReport(repoMap);
    writeQAReport(qa);
    writeIssuesReport(issues);
    writePatchPlan(plan, markdown);

    if (mode === "safe-patch") {
      if (config.mode !== "SAFE_PATCH") {
        console.log("\n⚠️  safe-patch requires JARVIS_AGENT_MODE=SAFE_PATCH in .env");
        console.log("   Currently in DRY_RUN — no files modified. Plan has been saved.");
      } else {
        const autoPatches = plan.patches.filter(p => p.safeToAutoApply);
        if (!autoPatches.length) {
          console.log("\n✅ No auto-applicable patches found — all changes require manual review.");
        } else {
          console.log(`\n⚠️  ${autoPatches.length} auto-applicable patches found.`);
          console.log("   Review latest_patch_plan.md before applying.");
          console.log("   Each patch includes a rollback plan.");
          for (const patch of autoPatches) {
            console.log(`   - [${patch.severity}] ${patch.issueId} in ${patch.file}`);
          }
        }
      }
    }

    printSummary(qa, issues, plan, runtimeResult);
    return;
  }

  console.error(`Unknown mode: ${mode}`);
  console.error("Valid modes: scan | qa | runtime | audit | plan | safe-patch");
  process.exit(1);
}

main().catch(err => {
  console.error("[FATAL]", err);
  process.exit(1);
});
