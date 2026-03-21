from pathlib import Path
import webbrowser

SANDBOX_ROOT = Path("sandbox")
SANDBOX_ROOT.mkdir(parents=True, exist_ok=True)

ALLOWED_APPS = {
    "notepad": "notepad",
    "calculator": "calc",
    "chrome": "start chrome",
}

ALLOWED_DOMAINS = {
    "google.com",
    "localhost",
    "127.0.0.1",
}

class SecureExecutor:
    def open_app(self, app: str, dry_run: bool = True):
        app_key = str(app).lower().strip()
        if app_key not in ALLOWED_APPS:
            return {"status": "blocked", "reason": "app not allowlisted"}

        if dry_run:
            return {"status": "dry_run", "action": "open_app", "app": app_key}

        import subprocess
        result = subprocess.run(ALLOWED_APPS[app_key], shell=True, capture_output=True, text=True)
        return {"status": "succeeded", "stdout": result.stdout, "stderr": result.stderr}

    def open_url(self, url: str, dry_run: bool = True):
        url = str(url).strip()
        try:
            host = url.split("//", 1)[1].split("/", 1)[0].lower()
        except Exception:
            return {"status": "blocked", "reason": "invalid url"}

        host = host.replace("www.", "")
        if host not in ALLOWED_DOMAINS:
            return {"status": "blocked", "reason": "domain not allowlisted"}

        if dry_run:
            return {"status": "dry_run", "action": "open_url", "url": url}

        webbrowser.open(url)
        return {"status": "succeeded", "url": url}

    def write_text(self, path: str, content: str, dry_run: bool = True):
        rel = Path(path)
        target = (SANDBOX_ROOT / rel).resolve()
        if SANDBOX_ROOT.resolve() not in target.parents and target != SANDBOX_ROOT.resolve():
            return {"status": "blocked", "reason": "path escapes sandbox"}

        if dry_run:
            return {"status": "dry_run", "action": "write_text", "path": str(target)}

        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content, encoding="utf-8")
        return {"status": "succeeded", "path": str(target)}

    def read_text(self, path: str, dry_run: bool = True):
        rel = Path(path)
        target = (SANDBOX_ROOT / rel).resolve()
        if SANDBOX_ROOT.resolve() not in target.parents and target != SANDBOX_ROOT.resolve():
            return {"status": "blocked", "reason": "path escapes sandbox"}

        if dry_run:
            return {"status": "dry_run", "action": "read_text", "path": str(target)}

        if not target.exists():
            return {"status": "failed", "reason": "file not found"}

        return {"status": "succeeded", "path": str(target), "content": target.read_text(encoding="utf-8")}
