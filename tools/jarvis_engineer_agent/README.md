# JARVIS Engineer Agent

Safe internal engineering agent for JARVIS.

**Purpose:** Audit, QA, issue detection, patch planning, and self-improvement — without breaking production.

---

## Safety First

- Defaults to **DRY_RUN** mode — no file writes
- Blocks: `git push`, `rm -rf`, `railway deploy`, DB drops, secret exposure
- Never auto-patches `RISKY_CHANGE` issues
- All changes require manual review unless explicitly `SAFE_PATCH` + `auto_fix_allowed: true`

---

## Setup

```bash
cd tools/jarvis_engineer_agent
cp .env.example .env
# Optionally add CURSOR_API_KEY for AI-powered analysis
npm install
```

---

## Commands

| Command | Description |
|---------|-------------|
| `npm run scan` | Map repo structure → `reports/latest_scan.json` |
| `npm run qa` | Run safe QA checks → `reports/latest_qa.json` |
| `npm run audit` | Full audit → scan + QA + issues + plan |
| `npm run plan` | Same as audit (alias) |
| `npm run safe-patch` | Plan + flag auto-applicable low-risk patches |

---

## Modes

Set `JARVIS_AGENT_MODE` in `.env`:

| Mode | Description |
|------|-------------|
| `DRY_RUN` (default) | Scan and report only, no file changes |
| `PATCH_PLAN` | Generate patch plan, no file changes |
| `SAFE_PATCH` | Apply only `auto_fix_allowed: true` + low-risk patches (with backup) |
| `BLOCKED` | All actions blocked (set manually for emergencies) |

---

## Reports

All reports written to `tools/jarvis_engineer_agent/reports/`:

- `latest_scan.json` — repo map
- `latest_qa.json` — QA results  
- `latest_issues.json` — detected issues with severity
- `latest_patch_plan.json` — structured patch plan
- `latest_patch_plan.md` — human-readable patch plan with diffs

### Issue Severity

| Severity | Meaning |
|----------|---------|
| `critical` | Production broken, must fix now |
| `high` | Major bug or broken flow |
| `medium` | UX issue or quality problem |
| `low` | Performance or minor improvement |

---

## Protected Files / Folders

These are **never** written or deleted:

- `.env`
- `data/`
- `memory/`
- `generated_audio/`
- `logs/`
- Railway config
- Credential files (`.key`, `.pem`, `.secret`)

---

## Cursor SDK Integration

If `CURSOR_API_KEY` is set, the agent uses Cursor's API for AI-powered analysis.

If not set, the agent falls back to local static analysis — **all core features still work**.

---

## Golf Module

The Golf module (`core/golf_dashboard_engine.py`) is **protected**:
- Agent will never suggest removing Golf
- Any missing Golf component is flagged as `critical`
- Golf camera, swing scoring, drills, and club bag are audited in every run

---

## Rollback

Every patch entry includes a rollback plan:

```bash
git checkout HEAD -- <file>
```

---

## Running a Full Audit

```bash
cd tools/jarvis_engineer_agent
npm run audit
```

Then review:
- `reports/latest_issues.json` for detected problems
- `reports/latest_patch_plan.md` for fix instructions
