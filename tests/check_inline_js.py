"""Syntax-check inline scripts in the Shorts page using Node.js."""
import re
import shutil
import subprocess
import tempfile
from pathlib import Path

node = shutil.which("node")
if not node:
    raise SystemExit("Node.js is required for inline JavaScript syntax checks")
source = Path("app/shorts_routes.py").read_text(encoding="utf-8")
match = re.search(r'SHORTS_HTML\s*=\s*r?""".*?<script>(.*?)</script>', source, re.S)
if not match:
    raise SystemExit("Could not locate Shorts inline script")
with tempfile.NamedTemporaryFile("w", suffix=".js", encoding="utf-8", delete=False) as handle:
    handle.write(match.group(1))
    path = handle.name
try:
    subprocess.run([node, "--check", path], check=True)
finally:
    Path(path).unlink(missing_ok=True)
