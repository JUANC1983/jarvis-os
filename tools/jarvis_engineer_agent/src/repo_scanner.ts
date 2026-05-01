import * as fs from "fs";
import * as path from "path";
import { Config } from "./config";

export interface FileInfo {
  relativePath: string;
  absolutePath: string;
  sizeKb: number;
  lines: number;
}

export interface RepoMap {
  scannedAt: string;
  repoPath: string;
  pythonFiles: FileInfo[];
  htmlFiles: FileInfo[];
  tsFiles: FileInfo[];
  coreModules: string[];
  mainRoutes: string[];
  frontendFetches: string[];
  connectors: string[];
  agents: string[];
  largeFiles: FileInfo[];
  summary: {
    totalPythonFiles: number;
    totalHtmlFiles: number;
    totalRoutes: number;
    totalFrontendFetches: number;
    largeFileCount: number;
  };
}

const IGNORE_DIRS = new Set(["node_modules", ".git", "__pycache__", "dist", "venv", ".venv", "archive", "backup"]);
const LARGE_FILE_KB = 200;

export class RepoScanner {
  private config: Config;

  constructor(config: Config) {
    this.config = config;
  }

  private walkDir(dir: string, exts: string[]): string[] {
    const results: string[] = [];
    let entries: fs.Dirent[];
    try { entries = fs.readdirSync(dir, { withFileTypes: true }); }
    catch { return results; }

    for (const e of entries) {
      if (IGNORE_DIRS.has(e.name)) continue;
      const full = path.join(dir, e.name);
      if (e.isDirectory()) {
        results.push(...this.walkDir(full, exts));
      } else if (e.isFile() && exts.some(x => e.name.endsWith(x))) {
        results.push(full);
      }
    }
    return results;
  }

  private fileInfo(absPath: string): FileInfo {
    const stat = fs.statSync(absPath);
    let lines = 0;
    try {
      const content = fs.readFileSync(absPath, "utf-8");
      lines = content.split("\n").length;
    } catch { /* binary or unreadable */ }
    return {
      relativePath: path.relative(this.config.repoPath, absPath).replace(/\\/g, "/"),
      absolutePath: absPath,
      sizeKb: Math.round(stat.size / 1024),
      lines,
    };
  }

  private extractPythonRoutes(mainPyPath: string): string[] {
    const routes: string[] = [];
    try {
      const content = fs.readFileSync(mainPyPath, "utf-8");
      const matches = content.matchAll(/@app\.(get|post|put|patch|delete)\(["']([^"']+)["']/g);
      for (const m of matches) routes.push(`${m[1].toUpperCase()} ${m[2]}`);
    } catch { /* ignore */ }
    return routes;
  }

  private extractFrontendFetches(htmlPath: string): string[] {
    const fetches: string[] = [];
    try {
      const content = fs.readFileSync(htmlPath, "utf-8");
      const matches = content.matchAll(/fetch\(["'`]([^"'`\$\{]+)["'`]/g);
      for (const m of matches) {
        const url = m[1].trim();
        if (url.startsWith("/") || url.startsWith("http")) fetches.push(url);
      }
    } catch { /* ignore */ }
    return [...new Set(fetches)].sort();
  }

  scan(): RepoMap {
    const repo = this.config.repoPath;
    console.log(`[SCANNER] Scanning repo: ${repo}`);

    const pyFiles  = this.walkDir(repo, [".py"]).map(f => this.fileInfo(f));
    const htmlFiles = this.walkDir(path.join(repo, "dashboard"), [".html"]).map(f => this.fileInfo(f));
    const tsFiles  = this.walkDir(path.join(repo, "tools"), [".ts"]).map(f => this.fileInfo(f));

    const coreDir = path.join(repo, "core");
    const coreModules = fs.existsSync(coreDir)
      ? fs.readdirSync(coreDir).filter(f => f.endsWith(".py") && !f.startsWith("__")).map(f => f.replace(".py", ""))
      : [];

    const connectorDir = path.join(repo, "opsx", "connectors");
    const connectors = fs.existsSync(connectorDir)
      ? fs.readdirSync(connectorDir).filter(f => f.endsWith(".py")).map(f => f.replace(".py", ""))
      : [];

    const agents = coreModules.filter(m =>
      m.includes("agent") || m.includes("orchestrator") || m.includes("brain") || m.includes("intelligence")
    );

    const mainPy = path.join(repo, "main.py");
    const mainRoutes = fs.existsSync(mainPy) ? this.extractPythonRoutes(mainPy) : [];

    const dashboardHtml = path.join(repo, "dashboard", "jarvis_futuristic.html");
    const frontendFetches = fs.existsSync(dashboardHtml) ? this.extractFrontendFetches(dashboardHtml) : [];

    const largeFiles = [...pyFiles, ...htmlFiles].filter(f => f.sizeKb >= LARGE_FILE_KB);

    const result: RepoMap = {
      scannedAt: new Date().toISOString(),
      repoPath: repo,
      pythonFiles: pyFiles,
      htmlFiles,
      tsFiles,
      coreModules,
      mainRoutes,
      frontendFetches,
      connectors,
      agents,
      largeFiles,
      summary: {
        totalPythonFiles: pyFiles.length,
        totalHtmlFiles: htmlFiles.length,
        totalRoutes: mainRoutes.length,
        totalFrontendFetches: frontendFetches.length,
        largeFileCount: largeFiles.length,
      },
    };

    console.log(
      `[SCANNER] Found ${pyFiles.length} .py files, ${mainRoutes.length} routes, ` +
      `${frontendFetches.length} frontend fetches, ${largeFiles.length} large files`
    );
    return result;
  }
}
