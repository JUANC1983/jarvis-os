"""QA: validate all dashboard fetch() calls have matching backend endpoints."""
import re
import sys
from pathlib import Path

html_path  = Path("dashboard/jarvis_futuristic.html")
main_path  = Path("main.py")

html   = html_path.read_text(encoding="utf-8")
mainpy = main_path.read_text(encoding="utf-8")

fetch_pattern = re.compile(r'fetch\(["\'](/api/[^"\'?\s]+)', re.MULTILINE)
fetches = sorted(set(m.group(1) for m in fetch_pattern.finditer(html)))

missing = [ep for ep in fetches if ep not in mainpy]

if missing:
    print("MISSING BACKEND BINDINGS:")
    for m in missing:
        print("  " + m)
    sys.exit(1)
else:
    print(f"ALL {len(fetches)} FRONTEND FETCH CALLS HAVE BACKEND MATCHES - OK")
    for ep in fetches:
        print("  OK " + ep)
