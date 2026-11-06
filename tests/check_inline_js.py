"""Syntax-check inline JavaScript in all interactive pages using Node.js."""
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.chat_ui import CHAT_HTML
from app.providers import PROVIDERS_HTML

node = shutil.which("node")
if not node:
    raise SystemExit("Node.js is required for inline JavaScript syntax checks")


def scripts_from_html(label, html):
    scripts = re.findall(
        r"<script(?:\s[^>]*)?>(.*?)</script\s*>",
        html,
        re.S | re.I,
    )
    if not scripts:
        raise SystemExit(f"Could not locate {label} inline scripts")
    return [(f"{label} inline script {index}", source)
            for index, source in enumerate(scripts, 1)]


shorts_source = (ROOT / "app/shorts_routes.py").read_text(encoding="utf-8")
shorts_match = re.search(
    r'SHORTS_HTML\s*=\s*r?""".*?<script>(.*?)</script>',
    shorts_source,
    re.S,
)
if not shorts_match:
    raise SystemExit("Could not locate Shorts inline script")

scripts = [("Shorts inline script", shorts_match.group(1))]
scripts.extend(scripts_from_html("Chat UI", CHAT_HTML))
scripts.extend(scripts_from_html("Provider UI", PROVIDERS_HTML))

for label, source in scripts:
    with tempfile.NamedTemporaryFile(
        "w", suffix=".js", encoding="utf-8", delete=False
    ) as handle:
        handle.write(source)
        path = handle.name
    try:
        subprocess.run([node, "--check", path], check=True)
    except subprocess.CalledProcessError as exc:
        raise SystemExit(f"JavaScript syntax check failed: {label}") from exc
    finally:
        Path(path).unlink(missing_ok=True)
    print(f"JavaScript syntax OK: {label}")
