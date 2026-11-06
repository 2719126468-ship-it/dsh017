"""Syntax-check inline JavaScript in the Shorts and Chat UI pages using Node.js."""
import re
import shutil
import subprocess
import tempfile
from pathlib import Path

from app.chat_ui import CHAT_HTML

node = shutil.which("node")
if not node:
    raise SystemExit("Node.js is required for inline JavaScript syntax checks")

shorts_source = Path("app/shorts_routes.py").read_text(encoding="utf-8")
shorts_match = re.search(r'SHORTS_HTML\\s*=\\s*r?""" .*? <script>(.*?)</script>', shorts_source, re.S | re.X)
if not shorts_match:
    shorts_match = re.search(r'SHORTS_HTML\\s*=\\s*r?""".*?<script>(.*?)</script>', shorts_source, re.S)
if not shorts_match:
    raise SystemExit("Could not locate Shorts inline script")

chat_scripts = re.findall(r"<script(?:\\s[^>]*)?>(.*?)</script\\s*>", CHAT_HTML, re.S | re.I)
if not chat_scripts:
    raise SystemExit("Could not locate Chat UI inline scripts")

scripts = [("Shorts inline script", shorts_match.group(1))]
scripts.extend((f"Chat UI inline script {index}", source) for index, source in enumerate(chat_scripts, 1))

for label, source in scripts:
    with tempfile.NamedTemporaryFile("w", suffix=".js", encoding="utf-8", delete=False) as handle:
        handle.write(source)
        path = handle.name
    try:
        subprocess.run([node, "--check", path], check=True)
    except subprocess.CalledProcessError as exc:
        raise SystemExit(f"JavaScript syntax check failed: {label}") from exc
    finally:
        Path(path).unlink(missing_ok=True)
    print(f"JavaScript syntax OK: {label}")
