"""Syntax-check embedded JavaScript used by the mobile web interfaces."""
import re
import shutil
import subprocess
import tempfile
from pathlib import Path

node = shutil.which("node")
if not node:
    raise SystemExit("Node.js is required for inline JavaScript syntax checks")

sources = {
    "Shorts": ("app/shorts_routes.py", r'SHORTS_HTML\s*=\s*r?"""(.*?)"""'),
    "Workspace": ("app/workspace_ui.py", r"WORKSPACE_HTML\s*=\s*r?'''(.*?)'''"),
    "Providers": ("app/providers.py", r"PROVIDERS_HTML\s*=\s*r?'''(.*?)'''"),
}

for label, (filename, html_pattern) in sources.items():
    source = Path(filename).read_text(encoding="utf-8")
    html_match = re.search(html_pattern, source, re.S)
    if not html_match:
        raise SystemExit("Could not locate %s HTML template" % label)
    scripts = re.findall(r"<script[^>]*>(.*?)</script>", html_match.group(1), re.S)
    if not scripts:
        raise SystemExit("Could not locate %s inline JavaScript" % label)
    for index, script in enumerate(scripts, 1):
        with tempfile.NamedTemporaryFile("w", suffix=".js", encoding="utf-8", delete=False) as handle:
            handle.write(script)
            path = handle.name
        try:
            subprocess.run([node, "--check", path], check=True)
        finally:
            Path(path).unlink(missing_ok=True)
