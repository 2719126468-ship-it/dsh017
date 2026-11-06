"""Global lightweight theme switcher and baseline browser hardening."""

from flask import request

_THEME_COOKIE = "dsh017_theme"
_ALLOWED_THEMES = {"original", "claude", "chatgpt"}

_THEME_CSS = r"""
<style id="dsh017-global-themes">
:root[data-dsh-theme="claude"] {
  color-scheme: light;
  --bg: #F7F5F0;
  --surface: #FFFEFA;
  --text: #2D2A26;
  --text-2: #625D56;
  --muted: #8B857D;
  --line: rgba(56, 50, 43, .12);
  --line-2: rgba(56, 50, 43, .18);
  --glass-bg: rgba(255, 254, 250, .88);
  --glass: rgba(255, 254, 250, .88);
  --glass-border: rgba(56, 50, 43, .12);
  --clay: #C76645;
  --accent: #C76645;
  --accent-hover: #A94F32;
  --accent-soft: rgba(199, 102, 69, .12);
  --brand: #C76645;
  --bg-soft: #F0EEE8;
  --bg-hover: #E9E5DC;
  --border: rgba(56, 50, 43, .12);
  --border-2: rgba(56, 50, 43, .18);
  --mask-fade: #F7F5F0;
  --topbar-bg: #FFFEFA;
  --dark: #2D2A26;
  --dark-text: #FFFEFA;
  --dsh-glow: radial-gradient(ellipse 60% 45% at 50% 0%, rgba(199, 102, 69, .075), transparent 70%);
  --dsh-shadow: 0 1px 2px rgba(36, 31, 26, .035);
  --dsh-font: -apple-system, BlinkMacSystemFont, "Segoe UI", "Noto Sans SC", sans-serif;
}
:root[data-dsh-theme="chatgpt"] {
  color-scheme: light;
  --bg: #FFFFFF;
  --surface: #F7F7F8;
  --text: #0D0D0D;
  --text-2: #424242;
  --muted: #777777;
  --line: rgba(13, 13, 13, .08);
  --line-2: rgba(13, 13, 13, .13);
  --glass-bg: rgba(247, 247, 248, .94);
  --glass: rgba(247, 247, 248, .94);
  --glass-border: rgba(13, 13, 13, .09);
  --clay: #10A37F;
  --accent: #10A37F;
  --accent-hover: #0E8F70;
  --accent-soft: rgba(16, 163, 127, .11);
  --brand: #10A37F;
  --bg-soft: #F7F7F8;
  --bg-hover: #ECEDEF;
  --border: rgba(13, 13, 13, .08);
  --border-2: rgba(13, 13, 13, .13);
  --mask-fade: #FFFFFF;
  --topbar-bg: #FFFFFF;
  --dark: #0D0D0D;
  --dark-text: #FFFFFF;
  --dsh-glow: none;
  --dsh-shadow: 0 1px 2px rgba(0, 0, 0, .035);
  --dsh-font: -apple-system, BlinkMacSystemFont, "Segoe UI", "Noto Sans SC", sans-serif;
}
html[data-dsh-theme="claude"] body,
html[data-dsh-theme="chatgpt"] body {
  background: var(--bg) !important;
  color: var(--text) !important;
  font-family: var(--dsh-font) !important;
}
html[data-dsh-theme="claude"] body::before,
html[data-dsh-theme="chatgpt"] body::before {
  background: var(--dsh-glow) !important;
  opacity: 1;
}
html[data-dsh-theme="claude"] button,
html[data-dsh-theme="claude"] input,
html[data-dsh-theme="claude"] textarea,
html[data-dsh-theme="claude"] select,
html[data-dsh-theme="chatgpt"] button,
html[data-dsh-theme="chatgpt"] input,
html[data-dsh-theme="chatgpt"] textarea,
html[data-dsh-theme="chatgpt"] select {
  font-family: var(--dsh-font);
}
html[data-dsh-theme="claude"] input,
html[data-dsh-theme="claude"] textarea,
html[data-dsh-theme="claude"] select,
html[data-dsh-theme="chatgpt"] input,
html[data-dsh-theme="chatgpt"] textarea,
html[data-dsh-theme="chatgpt"] select {
  color: var(--text) !important;
  background: var(--surface) !important;
  border-color: var(--line-2) !important;
}
html[data-dsh-theme="claude"] input::placeholder,
html[data-dsh-theme="claude"] textarea::placeholder,
html[data-dsh-theme="chatgpt"] input::placeholder,
html[data-dsh-theme="chatgpt"] textarea::placeholder {
  color: var(--muted) !important;
  opacity: 1;
}
html[data-dsh-theme="claude"] header,
html[data-dsh-theme="claude"] .topbar,
html[data-dsh-theme="claude"] .sidebar,
html[data-dsh-theme="claude"] .canvas-pane,
html[data-dsh-theme="claude"] .canvas-header,
html[data-dsh-theme="claude"] .composer,
html[data-dsh-theme="claude"] .sb-head,
html[data-dsh-theme="claude"] .sb-foot,
html[data-dsh-theme="chatgpt"] header,
html[data-dsh-theme="chatgpt"] .topbar,
html[data-dsh-theme="chatgpt"] .sidebar,
html[data-dsh-theme="chatgpt"] .canvas-pane,
html[data-dsh-theme="chatgpt"] .canvas-header,
html[data-dsh-theme="chatgpt"] .composer,
html[data-dsh-theme="chatgpt"] .sb-head,
html[data-dsh-theme="chatgpt"] .sb-foot {
  background: var(--surface) !important;
  color: var(--text) !important;
  border-color: var(--line) !important;
  backdrop-filter: none !important;
  -webkit-backdrop-filter: none !important;
}
html[data-dsh-theme="claude"] .card,
html[data-dsh-theme="claude"] .svc,
html[data-dsh-theme="claude"] .book,
html[data-dsh-theme="claude"] .item,
html[data-dsh-theme="claude"] .info,
html[data-dsh-theme="chatgpt"] .card,
html[data-dsh-theme="chatgpt"] .svc,
html[data-dsh-theme="chatgpt"] .book,
html[data-dsh-theme="chatgpt"] .item,
html[data-dsh-theme="chatgpt"] .info {
  background: var(--glass-bg) !important;
  color: var(--text) !important;
  border-color: var(--glass-border) !important;
  box-shadow: var(--dsh-shadow) !important;
  border-radius: 14px !important;
}
html[data-dsh-theme="claude"] .more,
html[data-dsh-theme="claude"] .sort-chip,
html[data-dsh-theme="claude"] .type-chip,
html[data-dsh-theme="claude"] .dur-chip,
html[data-dsh-theme="claude"] .canvas-btn,
html[data-dsh-theme="chatgpt"] .more,
html[data-dsh-theme="chatgpt"] .sort-chip,
html[data-dsh-theme="chatgpt"] .type-chip,
html[data-dsh-theme="chatgpt"] .dur-chip,
html[data-dsh-theme="chatgpt"] .canvas-btn {
  background: var(--surface) !important;
  color: var(--text-2) !important;
  border-color: var(--line-2) !important;
}
html[data-dsh-theme="claude"] .sp,
html[data-dsh-theme="claude"] .pg,
html[data-dsh-theme="claude"] .dlbtn,
html[data-dsh-theme="chatgpt"] .sp,
html[data-dsh-theme="chatgpt"] .pg,
html[data-dsh-theme="chatgpt"] .dlbtn {
  background: var(--surface) !important;
  color: var(--text-2) !important;
  border-color: var(--line-2) !important;
}
html[data-dsh-theme="claude"] .overlay .title,
html[data-dsh-theme="claude"] .overlay .author,
html[data-dsh-theme="claude"] .action,
html[data-dsh-theme="claude"] .back-btn,
html[data-dsh-theme="chatgpt"] .overlay .title,
html[data-dsh-theme="chatgpt"] .overlay .author,
html[data-dsh-theme="chatgpt"] .action,
html[data-dsh-theme="chatgpt"] .back-btn {
  color: #FFFFFF !important;
}
html[data-dsh-theme="claude"] .card::before,
html[data-dsh-theme="claude"] .svc::before,
html[data-dsh-theme="claude"] .book::before,
html[data-dsh-theme="chatgpt"] .card::before,
html[data-dsh-theme="chatgpt"] .svc::before,
html[data-dsh-theme="chatgpt"] .book::before {
  background: var(--accent) !important;
}
html[data-dsh-theme="claude"] .bar button,
html[data-dsh-theme="claude"] .controls .btn:not(.ghost),
html[data-dsh-theme="claude"] .btn:not(.ghost),
html[data-dsh-theme="claude"] #go,
html[data-dsh-theme="chatgpt"] .bar button,
html[data-dsh-theme="chatgpt"] .controls .btn:not(.ghost),
html[data-dsh-theme="chatgpt"] .btn:not(.ghost),
html[data-dsh-theme="chatgpt"] #go {
  background: var(--accent) !important;
  color: #FFFFFF !important;
  border-color: var(--accent) !important;
}
html[data-dsh-theme="claude"] a,
html[data-dsh-theme="chatgpt"] a {
  text-decoration-color: var(--line-2);
}
html[data-dsh-theme="claude"] .face-back,
html[data-dsh-theme="chatgpt"] .face-back {
  background: var(--surface) !important;
  border-color: var(--line-2) !important;
  box-shadow: var(--dsh-shadow) !important;
}
html[data-dsh-theme="claude"] .face-back::before,
html[data-dsh-theme="chatgpt"] .face-back::before {
  color: var(--accent) !important;
  text-shadow: none !important;
}
html[data-dsh-theme="claude"] #diffPanel,
html[data-dsh-theme="chatgpt"] #diffPanel {
  background: var(--surface) !important;
  color: var(--text) !important;
  border-color: var(--line-2) !important;
}
html[data-dsh-theme="claude"][data-theme="dark"] .msg-row.user .msg-body,
html[data-dsh-theme="chatgpt"][data-theme="dark"] .msg-row.user .msg-body {
  background: var(--bg-soft) !important;
  color: var(--text) !important;
}
html[data-dsh-theme="claude"] #themeBtn,
html[data-dsh-theme="chatgpt"] #themeBtn {
  display: none !important;
}
html[data-dsh-theme="claude"] :focus-visible,
html[data-dsh-theme="chatgpt"] :focus-visible {
  outline: 2px solid var(--accent) !important;
  outline-offset: 2px;
}
@media (prefers-reduced-motion: reduce) {
  #dsh017-theme-switcher *,
  #dsh017-theme-switcher *::before,
  #dsh017-theme-switcher *::after {
    transition-duration: .01ms !important;
    animation-duration: .01ms !important;
  }
}
#dsh017-theme-switcher {
  position: fixed;
  right: 10px;
  bottom: calc(10px + env(safe-area-inset-bottom, 0px));
  z-index: 10000;
  font: 13px/1.3 -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
}
#dsh017-theme-toggle {
  display: grid;
  place-items: center;
  width: 38px;
  height: 38px;
  border: 1px solid var(--line-2, rgba(128,128,128,.35));
  border-radius: 50%;
  background: var(--surface, #242424);
  color: var(--text, #fff);
  box-shadow: 0 2px 12px rgba(0,0,0,.16);
  cursor: pointer;
  font-size: 18px;
  line-height: 1;
  -webkit-tap-highlight-color: transparent;
}
#dsh017-theme-panel {
  position: absolute;
  right: 0;
  bottom: 46px;
  width: min(210px, calc(100vw - 24px));
  padding: 12px;
  border: 1px solid var(--line-2, rgba(128,128,128,.35));
  border-radius: 14px;
  background: var(--surface, #242424);
  color: var(--text, #fff);
  box-shadow: 0 8px 28px rgba(0,0,0,.18);
}
#dsh017-theme-panel[hidden] { display: none !important; }
#dsh017-theme-panel label {
  display: block;
  margin: 0 0 7px;
  color: var(--text-2, #aaa);
  font-size: 12px;
}
#dsh017-theme-select {
  display: block;
  width: 100%;
  min-height: 38px;
  padding: 7px 9px;
  border: 1px solid var(--line-2, rgba(128,128,128,.35));
  border-radius: 9px;
  background: var(--bg, #111);
  color: var(--text, #fff);
  font-size: 13px;
}
</style>
"""

_THEME_WIDGET = r"""
<div id="dsh017-theme-switcher">
  <button id="dsh017-theme-toggle" type="button"
          aria-label="切换全站主题" aria-expanded="false"
          aria-controls="dsh017-theme-panel" title="全站主题">◐</button>
  <div id="dsh017-theme-panel" hidden>
    <label for="dsh017-theme-select">全站外观主题</label>
    <select id="dsh017-theme-select">
      <option value="original">DSH 原生</option>
      <option value="claude">Claude 风格</option>
      <option value="chatgpt">ChatGPT 风格</option>
    </select>
  </div>
</div>
<script id="dsh017-global-theme-script">
(function () {
  "use strict";
  var cookieName = "dsh017_theme";
  var allowed = {original: true, claude: true, chatgpt: true};
  var root = document.documentElement;

  function cookieTheme() {
    var parts = document.cookie ? document.cookie.split(";") : [];
    for (var i = 0; i < parts.length; i++) {
      var part = parts[i].trim();
      if (part.indexOf(cookieName + "=") === 0) {
        var value = part.slice(cookieName.length + 1);
        return allowed[value] ? value : null;
      }
    }
    return null;
  }

  function applyTheme(value, persist) {
    if (!allowed[value]) value = "original";
    root.setAttribute("data-dsh-theme", value);
    var select = document.getElementById("dsh017-theme-select");
    if (select) select.value = value;
    if (persist) {
      try {
        document.cookie = cookieName + "=" + value +
          "; Max-Age=31536000; Path=/; SameSite=Lax" +
          (location.protocol === "https:" ? "; Secure" : "");
        try { localStorage.setItem(cookieName, value); } catch (e) {}
      } catch (e) {}
    }
  }

  var initial = root.getAttribute("data-dsh-theme") || cookieTheme();
  if (!allowed[initial]) {
    try {
      var stored = localStorage.getItem(cookieName);
      if (allowed[stored]) initial = stored;
    } catch (e) {}
  }
  applyTheme(initial || "original", false);

  var toggle = document.getElementById("dsh017-theme-toggle");
  var panel = document.getElementById("dsh017-theme-panel");
  var select = document.getElementById("dsh017-theme-select");
  if (!toggle || !panel || !select) return;

  toggle.addEventListener("click", function () {
    var open = panel.hidden;
    panel.hidden = !open;
    toggle.setAttribute("aria-expanded", open ? "true" : "false");
    if (open) select.focus();
  });
  select.addEventListener("change", function () {
    applyTheme(select.value, true);
    panel.hidden = true;
    toggle.setAttribute("aria-expanded", "false");
    toggle.focus();
  });
  document.addEventListener("keydown", function (event) {
    if (event.key === "Escape" && !panel.hidden) {
      panel.hidden = true;
      toggle.setAttribute("aria-expanded", "false");
      toggle.focus();
    }
  });
  document.addEventListener("click", function (event) {
    if (!panel.hidden && !event.target.closest("#dsh017-theme-switcher")) {
      panel.hidden = true;
      toggle.setAttribute("aria-expanded", "false");
    }
  });
})();
</script>
"""


def install_theme_support(app):
    """Install a shared appearance selector and conservative security headers.

    The preference cookie is intentionally host-wide (no port is encoded in
    browser cookie scope), so all DSH-017 services share one theme selection.
    It stores presentation only and is not an authentication credential.
    """

    @app.after_request
    def _dsh017_theme_and_security_headers(response):
        response.headers.setdefault("X-Content-Type-Options", "nosniff")
        response.headers.setdefault("X-Frame-Options", "DENY")
        response.headers.setdefault("Referrer-Policy", "strict-origin-when-cross-origin")
        response.headers.setdefault(
            "Permissions-Policy",
            "camera=(), microphone=(), geolocation=(), payment=()",
        )

        if (
            response.mimetype != "text/html"
            or request.path.startswith("/api/")
            or request.path in {"/health", "/metrics"}
        ):
            return response

        html = response.get_data(as_text=True)
        if "</head>" not in html.lower() or "</body>" not in html.lower():
            return response

        theme = request.cookies.get(_THEME_COOKIE, "")
        if theme in _ALLOWED_THEMES:
            import re
            html = re.sub(
                r"<html\b",
                '<html data-dsh-theme="' + theme + '"',
                html,
                count=1,
                flags=re.IGNORECASE,
            )

        head_pos = html.lower().find("</head>")
        body_pos = html.lower().rfind("</body>")
        html = html[:head_pos] + _THEME_CSS + html[head_pos:]
        body_pos = html.lower().rfind("</body>")
        html = html[:body_pos] + _THEME_WIDGET + html[body_pos:]
        response.set_data(html)
        return response

    return app
