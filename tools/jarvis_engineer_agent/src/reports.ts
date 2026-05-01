import * as fs from "fs";
import * as path from "path";
import { RepoMap } from "./repo_scanner";
import { QAResult } from "./qa_runner";
import { Issue } from "./issue_detector";
import { PatchPlan } from "./patch_planner";

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

export function printSummary(qa: QAResult, issues: Issue[], plan: PatchPlan): void {
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

  console.log(`\n📁 Reports written to: ${REPORTS_DIR}`);
  console.log(`   latest_scan.json`);
  console.log(`   latest_qa.json`);
  console.log(`   latest_issues.json`);
  console.log(`   latest_patch_plan.json`);
  console.log(`   latest_patch_plan.md`);
  console.log(`\n${SEP}\n`);
}
