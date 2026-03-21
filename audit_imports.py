import ast
import os
from pathlib import Path

ROOT = Path(".")
skip_dirs = {
    ".git", ".venv", "__pycache__", "node_modules", "dist", "build"
}

local_roots = {
    "api", "core", "interfaces", "memory", "dashboard", "agents",
    "config", "database", "automation", "uploads", "logs", "data"
}

stdlib_like = {
    "os","sys","json","time","datetime","typing","pathlib","re","math","statistics",
    "subprocess","threading","asyncio","collections","itertools","functools",
    "hashlib","random","uuid","tempfile","shutil","traceback","logging","csv",
    "sqlite3","dataclasses","enum","io","base64","glob"
}

imports = set()

for path in ROOT.rglob("*.py"):
    if any(part in skip_dirs for part in path.parts):
        continue
    try:
        tree = ast.parse(path.read_text(encoding="utf-8", errors="ignore"))
    except Exception:
        continue

    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                top = alias.name.split(".")[0]
                imports.add(top)
        elif isinstance(node, ast.ImportFrom):
            if node.module:
                top = node.module.split(".")[0]
                imports.add(top)

filtered = sorted(
    x for x in imports
    if x not in stdlib_like and x not in local_roots
)

mapping = {
    "PIL": "Pillow",
    "bs4": "beautifulsoup4",
    "cv2": "opencv-python-headless",
    "dotenv": "python-dotenv",
    "pptx": "python-pptx",
    "whisper": "openai-whisper",
    "twilio": "twilio",
    "yaml": "PyYAML",
    "sklearn": "scikit-learn",
}

lines = []
for item in filtered:
    lines.append(f"{item} -> {mapping.get(item, item)}")

out = Path("dependency_audit.txt")
out.write_text("\n".join(lines), encoding="utf-8")

print("Dependency audit generated:")
print(out.resolve())
print("\nDetected imports:\n")
print("\n".join(lines))
