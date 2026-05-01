import * as fs from "fs";
import * as path from "path";
import { RepoMap } from "./repo_scanner";
import { QAResult } from "./qa_runner";
import { Issue } from "./issue_detector";
import { PatchPlan } from "./patch_planner";
import { RuntimeQAResult } from "./runtime_qa";

const REPORTS_DIR = path.join(__dirname, "..", "reports");

function ensureDir(): void {
  if (!fs.existsSync(REPORTS_DIR)) fs.mkdirSync(REPORTS_DIR, { recursive: true });
}

function writeJSON(filename: string, data: unknown): string {
  ensureDir();
  const outPath = path.join(REPORTS_DIR, filename);
  fs.writeFileSync(outPath, JSON.stringify(data, null, 2), "utf-8");
  console.log(`[REPORTS] Written: ${outPath}`);
  return outPath;
}

function writeText(filename: string, content: string): string {
  ensureDir();
  const outPath = path.join(REPORTS_DIR, filename);
  fs.writeFileSync(outPath, content, "utf-8");
  console.log(`[REPORTS] Written: ${outPath}`);
  return outPath;
}

export function writeScanReport(repoMap: RepoMap): string {
  return writeJSON("latest_scan.json", {
    ...repoMap,
    // Trim large arrays for readability
    pythonFiles: repoMap.pythonFiles.map(f => ({ path: f.relativePath, sizeKb: f.sizeKb, lines: f.lines })),
    htmlFiles:   repoMap.htmlFiles.map(f => ({ path: f.relativePath, sizeKb: f.sizeKb, lines: f.lines })),
  });
}

export function writeQAReport(qa: QAResult): string {
  return writeJSON("latest_qa.json", qa);
}

export function writeIssuesReport(issues: Issue[]): string {
  const counts: Record<string, number> = { critical: 0, high: 0, medium: 0, low: 0 };
  for (const i of issues) counts[i.severity] = (counts[i.severity] || 0) + 1;

  return writeJSON("latest_issues.json", {
    generatedAt: new Date().toISOString(),
    total: issues.length,
    bySeverity: counts,
    issues,
  });
}

export function writePatchPlan(plan: PatchPlan, markdown: string): { json: string; md: string } {
  const json = writeJSON("latest_patch_plan.json", plan);
  const md   = writeText("latest_patch_plan.md", markdown);
  return { json, md };
}

export function writeRuntimeQAReport(result: RuntimeQAResult): string {
  return writeJSON("latest_runtime_qa.json", result);
}

export function printSummary(qa: QAResult, issues: Issue[], plan: PatchPlan, runtimeQA?: RuntimeQAResult): void {
  const SEP = "═".repeat(60);
  console.log(`\n${SEP}`);
  console.log("  JARVIS ENGINEER AGENT — SUMMARY");
  console.log(SEP);

  // QA
  const qaIcon = qa.overallStatus === "PASS" ? "✅" : qa.overallStatus === "WARN" ? "⚠️ " : "❌";
  console.log(`\n${qaIcon} QA: ${qa.overallStatus} — ${qa.passed} pass / ${qa.failed} fail / ${qa.warnings} warn`);

  // Issues
  const crit = issues.filter(i => i.severity === "critical").length;
  const high = issues.filter(i => i.severity === "high").length;
  const med  = issues.filter(i => i.severity === "medium").length;
  const low  = issues.filter(i => i.severity === "low").length;
  console.log(`\n🔍 Issues: ${issues.length} total`);
  console.log(`   🔴 Critical: ${crit}`);
  console.log(`   🟠 High:     ${high}`);
  console.log(`   🟡 Medium:   ${med}`);
  console.log(`   🟢 Low:      ${low}`);

  // Patches
  const autoable = plan.patches.filter(p => p.safeToAutoApply).length;
  console.log(`\n🔧 Patches: ${plan.patches.length} planned`);
  console.log(`   ✅ Auto-applicable: ${autoable}`);
  console.log(`   🚫 Manual required: ${plan.patches.length - autoable}`);
  console.log(`   🔒 Blocked:         ${plan.blockedPatches.length}`);

  // Runtime QA section
  if (runtimeQA) {
    const rtIcon =
      runtimeQA.overallStatus === "OFFLINE" ? "⚪" :
      runtimeQA.overallStatus === "PASS"    ? "✅" :
      runtimeQA.overallStatus === "WARN"    ? "⚠️ " : "❌";
    console.log(`\n${rtIcon} RUNTIME QA: ${runtimeQA.overallStatus}`);
    if (runtimeQA.serverReachable) {
      console.log(`   Base URL:  ${runtimeQA.baseUrl}`);
      console.log(`   Reality:   ${runtimeQA.realityMode ? "ON" : "OFF"}`);
      console.log(`   Endpoints: ${runtimeQA.passed} clean / ${runtimeQA.failed} failed / ${runtimeQA.warnings} warn`);
      for (const ep of runtimeQA.endpointResults) {
        const epIcon =
          !ep.reachable                                        ? "⚪" :
          ep.issues.some(i => i.severity === "critical")      ? "🔴" :
          ep.issues.some(i => i.severity === "high")          ? "🟠" :
          ep.issues.length                                     ? "🟡" : "✅";
        const timing = ep.responseTimeMs ? ` (${ep.responseTimeMs}ms)` : "";
        const issueNote = ep.issues.length ? ` — ${ep.issues.length} issue(s)` : "";
        console.log(`   ${epIcon} ${ep.label.padEnd(10)} HTTP ${ep.statusCode ?? "N/A"}${timing}${issueNote}`);
      }
      if (runtimeQA.runtimeIssues.length) {
        console.log(`   ⚠️  ${runtimeQA.runtimeIssues.length} runtime issue(s) added to patch plan`);
      }
    } else {
      console.log(`   Server offline at ${runtimeQA.baseUrl} — skipped runtime checks`);
    }
  }

  console.log(`\n📁 Reports written to: ${REPORTS_DIR}`);
  console.log(`   latest_scan.json`);
  console.log(`   latest_qa.json`);
  console.log(`   latest_issues.json`);
  console.log(`   latest_patch_plan.json`);
  console.log(`   latest_patch_plan.md`);
  if (runtimeQA) console.log(`   latest_runtime_qa.json`);
  console.log(`\n${SEP}\n`);
}
