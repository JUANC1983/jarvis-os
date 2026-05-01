import * as dotenv from "dotenv";
import * as path from "path";
import * as fs from "fs";

dotenv.config({ path: path.join(__dirname, "..", ".env") });

export type AgentMode = "DRY_RUN" | "PATCH_PLAN" | "SAFE_PATCH" | "BLOCKED";

export interface Config {
  mode: AgentMode;
  repoPath: string;
  cursorApiKey: string | null;
  cursorAvailable: boolean;
  dryRun: boolean;
}

function resolveMode(raw: string | undefined): AgentMode {
  const modes: AgentMode[] = ["DRY_RUN", "PATCH_PLAN", "SAFE_PATCH"];
  const upper = (raw || "DRY_RUN").toUpperCase() as AgentMode;
  return modes.includes(upper) ? upper : "DRY_RUN";
}

export function loadConfig(): Config {
  const repoPath = process.env.JARVIS_REPO_PATH || path.resolve(__dirname, "..", "..", "..");
  const cursorApiKey = process.env.CURSOR_API_KEY || null;
  const mode = resolveMode(process.env.JARVIS_AGENT_MODE);

  if (!fs.existsSync(repoPath)) {
    console.error(`[CONFIG] JARVIS repo path not found: ${repoPath}`);
    process.exit(1);
  }

  const config: Config = {
    mode,
    repoPath,
    cursorApiKey,
    cursorAvailable: !!cursorApiKey,
    dryRun: mode === "DRY_RUN",
  };

  console.log(`[CONFIG] mode=${config.mode} repo=${config.repoPath} cursor=${config.cursorAvailable}`);
  return config;
}
