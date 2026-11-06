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
  --clay: #202020;
  --accent: #202020;
  --accent-hover: #080808;
  --accent-soft: rgba(0, 0, 0, .07);
  --brand: #202020;
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
#dsh017-theme-select,
#dsh017-mode-select {
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

/* Product-inspired interaction layer: low-cost transforms and opacity only. */
html.dsh-theme-changing body,
html.dsh-theme-changing .sidebar,
html.dsh-theme-changing .topbar,
html.dsh-theme-changing .composer,
html.dsh-theme-changing .canvas-pane,
html.dsh-theme-changing .card,
html.dsh-theme-changing .book,
html.dsh-theme-changing .svc,
html.dsh-theme-changing .item,
html.dsh-theme-changing #dsh017-theme-panel,
html.dsh-theme-changing #dsh017-theme-toggle {
  transition:
    background-color 260ms ease,
    color 220ms ease,
    border-color 220ms ease,
    box-shadow 260ms ease;
}
#dsh017-theme-toggle {
  transition: transform 180ms cubic-bezier(.2,.8,.2,1),
              background-color 180ms ease,
              border-color 180ms ease,
              box-shadow 180ms ease;
}
#dsh017-theme-toggle:hover { transform: translateY(-1px); }
#dsh017-theme-toggle:active { transform: scale(.94); }
#dsh017-theme-panel {
  opacity: 0;
  visibility: hidden;
  pointer-events: none;
  transform: translateY(8px) scale(.98);
  transform-origin: right bottom;
  transition: opacity 170ms ease, transform 200ms cubic-bezier(.2,.8,.2,1), visibility 170ms;
}
#dsh017-theme-panel.open {
  opacity: 1;
  visibility: visible;
  pointer-events: auto;
  transform: translateY(0) scale(1);
}
#dsh017-theme-panel select {
  transition: border-color 160ms ease, background-color 160ms ease;
}
#dsh017-theme-panel select:focus-visible {
  outline: 2px solid var(--accent);
  outline-offset: 2px;
}

.sr-only {
  position: absolute !important;
  width: 1px !important;
  height: 1px !important;
  padding: 0 !important;
  margin: -1px !important;
  overflow: hidden !important;
  clip: rect(0, 0, 0, 0) !important;
  white-space: nowrap !important;
  border: 0 !important;
}
/* Claude-inspired: warm paper, quiet navigation, editorial conversation. */
html[data-dsh-theme="claude"] .sidebar {
  width: 264px;
  background: #F1EFE9 !important;
  border-right: 1px solid rgba(47,42,36,.07) !important;
  box-shadow: none !important;
}
html[data-dsh-theme="claude"] .sb-head {
  padding: 22px 18px 16px;
  background: transparent !important;
  border-bottom: 0 !important;
}
html[data-dsh-theme="claude"] .sb-head h2,
html[data-dsh-theme="claude"] .topbar h1 {
  font-family: Georgia, "Noto Serif SC", serif !important;
  font-weight: 500;
  letter-spacing: -.035em;
}
html[data-dsh-theme="claude"] .sb-item {
  border-radius: 9px;
  padding: 10px 12px;
  color: #5C5750 !important;
  transition: background 160ms ease, color 160ms ease, transform 160ms ease;
}
html[data-dsh-theme="claude"] .sb-item:hover {
  background: rgba(255,255,255,.58);
  color: #28241F !important;
}
html[data-dsh-theme="claude"] .sb-item.new {
  background: rgba(255,255,255,.72) !important;
  border: 1px solid rgba(57,48,40,.08) !important;
  box-shadow: 0 1px 2px rgba(40,32,24,.025);
}
html[data-dsh-theme="claude"] .sb-label {
  font-family: var(--dsh-font);
  font-size: 10px;
  letter-spacing: .02em;
  text-transform: none;
  color: #8B847B !important;
}
html[data-dsh-theme="claude"] #presetSel,
html[data-dsh-theme="claude"] #modelSel,
html[data-dsh-theme="claude"] #effortSel,
html[data-dsh-theme="claude"] #permModeSel {
  background: rgba(255,255,255,.72) !important;
  border-color: rgba(57,48,40,.10) !important;
  border-radius: 9px;
}
html[data-dsh-theme="claude"] .sb-foot {
  border-top: 1px solid rgba(47,42,36,.07) !important;
  background: transparent !important;
  text-transform: none;
  letter-spacing: .02em;
  font-family: var(--dsh-font);
}
html[data-dsh-theme="claude"] .topbar {
  background: #F7F5F0 !important;
  border-bottom: 0 !important;
  padding: 15px 24px 7px;
}
html[data-dsh-theme="claude"] .main,
html[data-dsh-theme="claude"] .chat-pane,
html[data-dsh-theme="claude"] .messages-wrap {
  background: #F7F5F0 !important;
}
html[data-dsh-theme="claude"] .messages {
  width: min(100%, 820px);
  margin-inline: auto;
  padding: 42px 32px 24px;
  gap: 34px;
}
html[data-dsh-theme="claude"] .msg-row.assistant .msg-body {
  font-family: var(--dsh-font) !important;
  font-size: 15.5px;
  line-height: 1.82;
  letter-spacing: -.012em;
  color: #292722 !important;
}
html[data-dsh-theme="claude"] .msg-row.user .msg-body {
  max-width: 88%;
  padding: 12px 16px;
  background: #EEECE6 !important;
  color: #34302A !important;
  border: 1px solid rgba(48,42,34,.035);
  border-radius: 17px;
  border-bottom-right-radius: 7px;
  font-weight: 400;
}
html[data-dsh-theme="claude"] .msg-actions {
  margin-top: 9px;
  gap: 5px;
}
html[data-dsh-theme="claude"] .act {
  color: #817A70 !important;
  border-radius: 8px;
}
html[data-dsh-theme="claude"] .act:hover {
  background: #ECE9E2 !important;
  color: #3C3730 !important;
}
html[data-dsh-theme="claude"] .composer {
  width: min(calc(100% - 48px), 820px);
  margin: 0 auto 10px;
  padding: 10px 12px;
  background: #FFFEFC !important;
  border: 1px solid rgba(51,44,36,.14) !important;
  border-radius: 19px;
  box-shadow: 0 3px 16px rgba(52,43,33,.045);
  gap: 10px;
  position: relative;
}
html[data-dsh-theme="claude"] .composer textarea {
  background: transparent !important;
  border: 0 !important;
  box-shadow: none !important;
  min-height: 48px;
  padding: 12px 10px;
  color: #292722 !important;
}
html[data-dsh-theme="claude"] .composer textarea:focus {
  outline: none;
  box-shadow: none !important;
}
html[data-dsh-theme="claude"] .composer button {
  background: #C66A4D !important;
  color: #fff !important;
  width: 38px;
  height: 38px;
  margin-bottom: 3px;
}
html[data-dsh-theme="claude"] .composer-toolbar {
  width: min(calc(100% - 56px), 820px);
  margin: -7px auto 8px;
  padding: 5px 14px;
}
html[data-dsh-theme="claude"] .think-panel {
  background: #F1EFE9 !important;
  border-color: rgba(51,44,36,.10) !important;
  border-radius: 12px;
}
html[data-dsh-theme="claude"] .canvas-pane {
  background: #FFFEFC !important;
  border-left: 1px solid rgba(51,44,36,.10) !important;
}
html[data-dsh-theme="claude"] .canvas-header {
  background: #FFFEFC !important;
}
html[data-dsh-theme="claude"] .canvas-editor {
  background: #FFFEFC !important;
  font-family: var(--dsh-font) !important;
  line-height: 1.75;
}

/* ChatGPT-inspired: neutral workspace, floating sidebar feel, compact composer. */
html[data-dsh-theme="chatgpt"] .sidebar {
  width: 260px;
  background: #F9F9F9 !important;
  border-right: 1px solid #ECECEC !important;
  box-shadow: none !important;
}
html[data-dsh-theme="chatgpt"] .sb-head {
  padding: 18px 16px 12px;
  background: transparent !important;
  border-bottom: 0 !important;
}
html[data-dsh-theme="chatgpt"] .sb-head h2,
html[data-dsh-theme="chatgpt"] .topbar h1 {
  font-family: var(--dsh-font) !important;
  font-weight: 600;
  letter-spacing: -.025em;
}
html[data-dsh-theme="chatgpt"] .sb-item {
  border-radius: 10px;
  padding: 10px 12px;
  color: #303030 !important;
}
html[data-dsh-theme="chatgpt"] .sb-item:hover {
  background: #EEEEEE !important;
}
html[data-dsh-theme="chatgpt"] .sb-item.new {
  background: #FFFFFF !important;
  border: 1px solid #E7E7E7 !important;
  box-shadow: 0 1px 2px rgba(0,0,0,.025);
}
html[data-dsh-theme="chatgpt"] .sb-label {
  font-family: var(--dsh-font);
  font-size: 11px;
  letter-spacing: .01em;
  text-transform: none;
  color: #777 !important;
}
html[data-dsh-theme="chatgpt"] .sb-foot {
  background: transparent !important;
  border-top: 1px solid #EAEAEA !important;
  font-family: var(--dsh-font);
  text-transform: none;
  letter-spacing: 0;
}
html[data-dsh-theme="chatgpt"] .topbar {
  background: #FFFFFF !important;
  border-bottom: 1px solid #F0F0F0 !important;
  padding: 11px 18px;
}
html[data-dsh-theme="chatgpt"] .main,
html[data-dsh-theme="chatgpt"] .chat-pane,
html[data-dsh-theme="chatgpt"] .messages-wrap {
  background: #FFFFFF !important;
}
html[data-dsh-theme="chatgpt"] .messages {
  width: min(100%, 800px);
  margin-inline: auto;
  padding: 32px 26px 20px;
  gap: 30px;
}
html[data-dsh-theme="chatgpt"] .msg-row.assistant .msg-body {
  font-family: var(--dsh-font) !important;
  font-size: 15px;
  line-height: 1.78;
  letter-spacing: 0;
  color: #222 !important;
}
html[data-dsh-theme="chatgpt"] .msg-row.user .msg-body {
  max-width: 82%;
  padding: 11px 17px;
  background: #F4F4F4 !important;
  color: #222 !important;
  border: 0;
  border-radius: 20px;
  border-bottom-right-radius: 7px;
  font-weight: 400;
}
html[data-dsh-theme="chatgpt"] .composer {
  width: min(calc(100% - 42px), 800px);
  margin: 0 auto 10px;
  padding: 9px 11px 9px 16px;
  background: #FFFFFF !important;
  border: 1px solid #E5E5E5 !important;
  border-radius: 25px;
  box-shadow: 0 4px 18px rgba(0,0,0,.055);
  position: relative;
  gap: 9px;
}
html[data-dsh-theme="chatgpt"] .composer textarea {
  background: transparent !important;
  border: 0 !important;
  box-shadow: none !important;
  min-height: 44px;
  padding: 12px 5px;
  color: #222 !important;
}
html[data-dsh-theme="chatgpt"] .composer textarea:focus {
  outline: none;
  box-shadow: none !important;
}
html[data-dsh-theme="chatgpt"] .composer button {
  background: #171717 !important;
  color: #fff !important;
  width: 38px;
  height: 38px;
  margin-bottom: 2px;
}
html[data-dsh-theme="chatgpt"] .composer-toolbar {
  width: min(calc(100% - 52px), 800px);
  margin: -7px auto 8px;
  padding: 5px 15px;
}
html[data-dsh-theme="chatgpt"] .think-panel {
  background: #F7F7F7 !important;
  border-color: #EAEAEA !important;
  border-radius: 12px;
}
html[data-dsh-theme="chatgpt"] .canvas-pane {
  background: #FFFFFF !important;
  border-left: 1px solid #EAEAEA !important;
}
html[data-dsh-theme="chatgpt"] .canvas-header {
  background: #FFFFFF !important;
}
html[data-dsh-theme="chatgpt"] .canvas-editor {
  background: #FFFFFF !important;
  font-family: var(--dsh-font) !important;
  line-height: 1.7;
}

/* Shared ChatGPT/Claude motion: intentional, short, composited transitions. */
#sidebar, .sidebar, .chat-pane, .canvas-pane,
.sb-item, .canvas-file-item, .artifact-card,
.msg-actions, .msg-row, .composer, .composer textarea,
.canvas-header, .canvas-editor-wrap {
  transition-timing-function: cubic-bezier(.2,.8,.2,1);
}
html[data-dsh-theme="chatgpt"] .mask {
  background: rgba(18,18,18,.22);
  backdrop-filter: blur(2px);
  -webkit-backdrop-filter: blur(2px);
}
html[data-dsh-theme="claude"] .mask {
  background: rgba(37,31,25,.18);
}
.msg-row .msg-body { overflow-wrap: anywhere; }
.md-p { margin: 0 0 12px; }
.md-p:last-child { margin-bottom: 0; }
.md-h { margin: 18px 0 9px; font-weight: 650; line-height: 1.35; }
.md-h1 { font-size: 1.45em; }
.md-h2 { font-size: 1.25em; }
.md-h3 { font-size: 1.1em; }
.md-list { margin: 7px 0 12px 22px; padding: 0; }
.md-list li { margin: 4px 0; padding-left: 3px; }
.md-quote {
  margin: 10px 0 14px;
  padding: 3px 0 3px 14px;
  border-left: 3px solid var(--accent, #999);
  color: var(--text-2, #666);
}
.md-inline-code {
  padding: .12em .38em;
  border-radius: 5px;
  background: rgba(127,127,127,.12);
  font: .88em/1.5 ui-monospace, SFMono-Regular, Menlo, monospace;
}
.md-table-wrap {
  max-width: 100%;
  margin: 12px 0 15px;
  overflow-x: auto;
  border: 1px solid var(--border-2, rgba(127,127,127,.2));
  border-radius: 10px;
  -webkit-overflow-scrolling: touch;
}
.md-table {
  width: 100%;
  border-collapse: collapse;
  font-size: 13px;
  line-height: 1.55;
}
.md-table th, .md-table td {
  padding: 8px 11px;
  border-bottom: 1px solid var(--border, rgba(127,127,127,.15));
  border-right: 1px solid var(--border, rgba(127,127,127,.15));
  text-align: left;
  vertical-align: top;
  min-width: 76px;
}
.md-table th {
  background: rgba(127,127,127,.08);
  font-weight: 650;
  color: var(--text);
}
.md-table tr:last-child td { border-bottom: 0; }
.md-table th:last-child, .md-table td:last-child { border-right: 0; }
.md-code {
  margin: 12px 0 15px;
  overflow: hidden;
  border: 1px solid var(--border-2, rgba(127,127,127,.2));
  border-radius: 11px;
  background: rgba(127,127,127,.07);
}
.md-code-head {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 6px 11px;
  border-bottom: 1px solid var(--border, rgba(127,127,127,.15));
  font: 10px/1.4 ui-monospace, SFMono-Regular, Menlo, monospace;
  color: var(--muted, #777);
  letter-spacing: .06em;
  text-transform: uppercase;
}
.md-code pre {
  margin: 0;
  padding: 13px 14px;
  overflow-x: auto;
  font: 12.5px/1.65 ui-monospace, SFMono-Regular, Menlo, monospace;
  white-space: pre;
  -webkit-overflow-scrolling: touch;
}
.md-code code { font: inherit; }
.md-code-copy {
  border: 1px solid var(--border-2, rgba(127,127,127,.2));
  border-radius: 6px;
  background: transparent;
  color: var(--text-2, #777);
  padding: 3px 8px;
  font: 10px/1.3 var(--dsh-font, sans-serif);
  cursor: pointer;
}
.md-code-copy:active { transform: scale(.96); }
.md-link {
  color: var(--accent, #555);
  text-decoration: underline;
  text-decoration-thickness: 1px;
  text-underline-offset: 2px;
}
.md-hr { border: 0; border-top: 1px solid var(--border-2); margin: 16px 0; }
.md-rendered { animation: dsh-markdown-in 180ms ease both; }
@keyframes dsh-markdown-in {
  from { opacity: .65; transform: translateY(2px); }
  to { opacity: 1; transform: none; }
}
.typing .dot { will-change: transform, opacity; }
.composer.is-streaming {
  border-color: var(--accent) !important;
}
.composer.is-streaming::after {
  content: "";
  position: absolute;
  inset: -1px;
  border-radius: inherit;
  pointer-events: none;
  opacity: .65;
  background: linear-gradient(105deg, transparent 20%, rgba(255,255,255,.0) 38%,
    rgba(255,255,255,.45) 50%, rgba(255,255,255,0) 62%, transparent 80%);
  background-size: 220% 100%;
  animation: dsh-composer-shimmer 1.8s ease-in-out infinite;
}
@keyframes dsh-composer-shimmer {
  from { background-position: 120% 0; }
  to { background-position: -120% 0; }
}
#jumpLatest {
  position: absolute;
  z-index: 5;
  left: 50%;
  bottom: 12px;
  transform: translateX(-50%) translateY(5px);
  border: 1px solid var(--border-2);
  border-radius: 999px;
  padding: 7px 12px;
  background: var(--surface);
  color: var(--text-2);
  box-shadow: 0 3px 14px rgba(0,0,0,.1);
  font: 11px/1.2 var(--dsh-font);
  opacity: 0;
  visibility: hidden;
  transition: opacity 150ms ease, transform 150ms ease, visibility 150ms;
}
#jumpLatest.visible {
  opacity: 1;
  visibility: visible;
  transform: translateX(-50%) translateY(0);
}
.canvas-pane {
  display: flex;
  flex: 0 0 0;
  width: 0;
  min-width: 0;
  opacity: 0;
  overflow: hidden;
  transform: translateX(14px);
  pointer-events: none;
  transition: width 260ms cubic-bezier(.2,.8,.2,1),
              flex-basis 260ms cubic-bezier(.2,.8,.2,1),
              opacity 180ms ease, transform 260ms cubic-bezier(.2,.8,.2,1);
}
.canvas-pane.open {
  flex: 0 1 46%;
  width: 46%;
  min-width: 320px;
  opacity: 1;
  transform: translateX(0);
  pointer-events: auto;
}
.canvas-pane .canvas-files,
.canvas-pane .canvas-editor-wrap {
  min-width: 0;
  width: 100%;
}
.canvas-editor-wrap, .canvas-files {
  animation: dsh-canvas-view-in 220ms cubic-bezier(.2,.8,.2,1) both;
}
@keyframes dsh-canvas-view-in {
  from { opacity: 0; transform: translateY(6px); }
  to { opacity: 1; transform: none; }
}
@media (max-width: 1024px) {
  .mask {
    display: block;
    visibility: hidden;
    opacity: 0;
    pointer-events: none;
    transition: opacity 220ms ease, visibility 220ms;
  }
  .mask.show {
    visibility: visible;
    opacity: 1;
    pointer-events: auto;
  }
  .sidebar {
    will-change: transform;
    transition: transform 280ms cubic-bezier(.2,.8,.2,1);
  }
  .sidebar.open { transform: translateX(0); }
}
@media (max-width: 1024px) {
  .canvas-pane {
    display: flex;
    width: 0;
    min-width: 0;
    flex: 0 0 0;
    visibility: hidden;
    opacity: 0;
    pointer-events: none;
    transform: translateY(10px);
  }
  .canvas-pane.open {
    display: flex;
    width: 100%;
    min-width: 0;
    flex: 1 1 100%;
    visibility: visible;
    opacity: 1;
    pointer-events: auto;
    transform: translateY(0);
  }
  .chat-pane { min-width: 0; }
  html[data-dsh-theme="claude"] .messages,
  html[data-dsh-theme="chatgpt"] .messages {
    padding-left: 17px;
    padding-right: 17px;
  }
  html[data-dsh-theme="claude"] .composer,
  html[data-dsh-theme="chatgpt"] .composer {
    width: calc(100% - 24px);
    margin-bottom: calc(8px + env(safe-area-inset-bottom,0px));
  }
  html[data-dsh-theme="claude"] .composer-toolbar,
  html[data-dsh-theme="chatgpt"] .composer-toolbar {
    width: calc(100% - 30px);
  }
}
@media (max-width: 520px) {
  html[data-dsh-theme="claude"] .sidebar,
  html[data-dsh-theme="chatgpt"] .sidebar {
    width: min(88vw, 320px);
  }
  html[data-dsh-theme="claude"] .topbar,
  html[data-dsh-theme="chatgpt"] .topbar {
    padding-left: 10px;
    padding-right: 10px;
  }
  html[data-dsh-theme="claude"] .msg-row.user .msg-body,
  html[data-dsh-theme="chatgpt"] .msg-row.user .msg-body {
    max-width: 92%;
  }
  .md-code pre { font-size: 11.5px; }
}
@media (prefers-reduced-motion: reduce) {
  html.dsh-theme-changing body,
  html.dsh-theme-changing .sidebar,
  html.dsh-theme-changing .topbar,
  html.dsh-theme-changing .composer,
  html.dsh-theme-changing .canvas-pane,
  #dsh017-theme-toggle,
  #dsh017-theme-panel,
  .canvas-pane,
  .canvas-files,
  .canvas-editor-wrap,
  .md-rendered,
  .composer.is-streaming::after,
  #jumpLatest {
    animation: none !important;
    transition: none !important;
  }
  .composer.is-streaming::after { display: none !important; }
}


#dsh017-theme-switcher.dsh017-theme-embedded {
  position: relative !important;
  right: auto !important;
  bottom: auto !important;
  top: auto !important;
  margin-left: 2px;
  flex: 0 0 auto;
}
#dsh017-theme-switcher.dsh017-theme-embedded #dsh017-theme-toggle {
  width: 32px;
  height: 32px;
  box-shadow: none;
  border-radius: 9px;
  font-size: 16px;
}
/* DSH native identity: layered ink/navy surfaces and blue-violet accents. */
html[data-dsh-theme="original"][data-dsh-mode="light"] {
  color-scheme: light;
  --bg:#F4F6FC; --surface:#FFFFFF; --text:#171C2B; --text-2:#515B73;
  --muted:#8790A6; --line:rgba(48,66,112,.11); --line-2:rgba(48,66,112,.18);
  --accent:#536DFA; --accent-hover:#4056DE; --accent-soft:rgba(83,109,250,.12);
  --brand:#536DFA; --bg-soft:#E9EDF8; --bg-hover:#DDE4F5; --mask-fade:#F4F6FC;
  --topbar-bg:rgba(255,255,255,.86); --dsh-shadow:0 8px 30px rgba(49,68,125,.08);
}
html[data-dsh-theme="original"][data-dsh-mode="dark"] {
  color-scheme: dark;
  --bg:#0C1220; --surface:#141D31; --text:#ECF1FF; --text-2:#B2BED8;
  --muted:#7583A3; --line:rgba(150,174,232,.12); --line-2:rgba(150,174,232,.20);
  --accent:#8295FF; --accent-hover:#A0ADFF; --accent-soft:rgba(130,149,255,.15);
  --brand:#8295FF; --bg-soft:#121B2E; --bg-hover:#1C2942; --mask-fade:#0C1220;
  --topbar-bg:rgba(17,26,44,.9); --dsh-shadow:0 10px 32px rgba(0,0,0,.25);
}
html[data-dsh-mode="dark"] { color-scheme:dark; }
html[data-dsh-mode="light"] { color-scheme:light; }
html[data-dsh-mode="dark"] body {
  background:var(--bg) !important;
  color:var(--text) !important;
}
html[data-dsh-mode="dark"] input,
html[data-dsh-mode="dark"] textarea,
html[data-dsh-mode="dark"] select {
  color:var(--text) !important;
  background:var(--surface) !important;
  border-color:var(--line-2) !important;
}
html[data-dsh-mode="dark"] input::placeholder,
html[data-dsh-mode="dark"] textarea::placeholder { color:var(--muted) !important; }

/* Claude: warm charcoal dark mode, paper-like light mode. */
html[data-dsh-theme="claude"][data-dsh-mode="dark"] {
  color-scheme:dark;
  --bg:#242321; --surface:#2D2B28; --text:#F0EEE9; --text-2:#C5C0B7;
  --muted:#969087; --line:rgba(236,229,216,.10); --line-2:rgba(236,229,216,.17);
  --glass-bg:#2D2B28; --glass:#2D2B28; --glass-border:rgba(236,229,216,.12);
  --accent:#D98B6B; --accent-hover:#E4A083; --accent-soft:rgba(217,139,107,.14);
  --brand:#D98B6B; --bg-soft:#1E1D1B; --bg-hover:#37342F;
  --mask-fade:#242321; --topbar-bg:#2D2B28; --dark:#F0EEE9; --dark-text:#242321;
  --dsh-shadow:0 3px 18px rgba(0,0,0,.16);
}
html[data-dsh-theme="claude"][data-dsh-mode="dark"] body,
html[data-dsh-theme="claude"][data-dsh-mode="dark"] .main,
html[data-dsh-theme="claude"][data-dsh-mode="dark"] .chat-pane,
html[data-dsh-theme="claude"][data-dsh-mode="dark"] .messages-wrap,
html[data-dsh-theme="claude"][data-dsh-mode="dark"] .canvas-pane {
  background:#242321 !important; color:#F0EEE9 !important;
}
html[data-dsh-theme="claude"][data-dsh-mode="dark"] .sidebar {
  background:#1E1D1B !important; border-color:rgba(236,229,216,.09) !important;
}
html[data-dsh-theme="claude"][data-dsh-mode="dark"] .topbar,
html[data-dsh-theme="claude"][data-dsh-mode="dark"] .sb-head,
html[data-dsh-theme="claude"][data-dsh-mode="dark"] .sb-foot,
html[data-dsh-theme="claude"][data-dsh-mode="dark"] .canvas-header {
  background:#242321 !important; color:#F0EEE9 !important; border-color:rgba(236,229,216,.10) !important;
}
html[data-dsh-theme="claude"][data-dsh-mode="dark"] .composer {
  background:#302E2A !important; border-color:rgba(236,229,216,.19) !important;
  box-shadow:0 5px 22px rgba(0,0,0,.22) !important;
}
html[data-dsh-theme="claude"][data-dsh-mode="dark"] .composer textarea,
html[data-dsh-theme="claude"][data-dsh-mode="dark"] .canvas-editor {
  background:transparent !important; color:#F0EEE9 !important;
}
html[data-dsh-theme="claude"][data-dsh-mode="dark"] .think-panel,
html[data-dsh-theme="claude"][data-dsh-mode="dark"] .canvas-btn,
html[data-dsh-theme="claude"][data-dsh-mode="dark"] #presetSel,
html[data-dsh-theme="claude"][data-dsh-mode="dark"] #modelSel,
html[data-dsh-theme="claude"][data-dsh-mode="dark"] #effortSel,
html[data-dsh-theme="claude"][data-dsh-mode="dark"] #permModeSel {
  background:#302E2A !important; color:#E7E2D9 !important; border-color:rgba(236,229,216,.15) !important;
}
html[data-dsh-theme="claude"][data-dsh-mode="dark"] .msg-row.user .msg-body {
  background:#3A3731 !important; color:#F0EEE9 !important; border-color:rgba(236,229,216,.07) !important;
}
html[data-dsh-theme="claude"][data-dsh-mode="dark"] .msg-row.assistant .msg-body,
html[data-dsh-theme="claude"][data-dsh-mode="dark"] .canvas-title,
html[data-dsh-theme="claude"][data-dsh-mode="dark"] .sb-head h2,
html[data-dsh-theme="claude"][data-dsh-mode="dark"] .topbar h1 { color:#F0EEE9 !important; }

/* ChatGPT: neutral graphite surfaces, compact chrome and a soft floating composer. */
html[data-dsh-theme="chatgpt"][data-dsh-mode="dark"] {
  color-scheme:dark;
  --bg:#212121; --surface:#2F2F2F; --text:#ECECEC; --text-2:#C5C5C5;
  --muted:#929292; --line:rgba(255,255,255,.09); --line-2:rgba(255,255,255,.15);
  --glass-bg:#292929; --glass:#292929; --glass-border:rgba(255,255,255,.09);
  --accent:#ECECEC; --accent-hover:#FFFFFF; --accent-soft:rgba(255,255,255,.10);
  --brand:#ECECEC; --bg-soft:#171717; --bg-hover:#303030;
  --mask-fade:#212121; --topbar-bg:#212121; --dark:#ECECEC; --dark-text:#171717;
  --dsh-shadow:0 4px 20px rgba(0,0,0,.20);
}
html[data-dsh-theme="chatgpt"][data-dsh-mode="dark"] body,
html[data-dsh-theme="chatgpt"][data-dsh-mode="dark"] .main,
html[data-dsh-theme="chatgpt"][data-dsh-mode="dark"] .chat-pane,
html[data-dsh-theme="chatgpt"][data-dsh-mode="dark"] .messages-wrap,
html[data-dsh-theme="chatgpt"][data-dsh-mode="dark"] .canvas-pane {
  background:#212121 !important; color:#ECECEC !important;
}
html[data-dsh-theme="chatgpt"][data-dsh-mode="dark"] .sidebar {
  background:#171717 !important; border-color:#303030 !important;
}
html[data-dsh-theme="chatgpt"][data-dsh-mode="dark"] .topbar,
html[data-dsh-theme="chatgpt"][data-dsh-mode="dark"] .sb-head,
html[data-dsh-theme="chatgpt"][data-dsh-mode="dark"] .sb-foot,
html[data-dsh-theme="chatgpt"][data-dsh-mode="dark"] .canvas-header {
  background:#212121 !important; color:#ECECEC !important; border-color:#343434 !important;
}
html[data-dsh-theme="chatgpt"][data-dsh-mode="dark"] .composer {
  background:#303030 !important; border-color:#424242 !important;
  box-shadow:0 4px 18px rgba(0,0,0,.2) !important;
}
html[data-dsh-theme="chatgpt"][data-dsh-mode="dark"] .composer textarea,
html[data-dsh-theme="chatgpt"][data-dsh-mode="dark"] .canvas-editor {
  background:transparent !important; color:#ECECEC !important;
}
html[data-dsh-theme="chatgpt"][data-dsh-mode="dark"] .think-panel,
html[data-dsh-theme="chatgpt"][data-dsh-mode="dark"] .canvas-btn,
html[data-dsh-theme="chatgpt"][data-dsh-mode="dark"] #presetSel,
html[data-dsh-theme="chatgpt"][data-dsh-mode="dark"] #modelSel,
html[data-dsh-theme="chatgpt"][data-dsh-mode="dark"] #effortSel,
html[data-dsh-theme="chatgpt"][data-dsh-mode="dark"] #permModeSel {
  background:#2B2B2B !important; color:#E5E5E5 !important; border-color:#454545 !important;
}
html[data-dsh-theme="chatgpt"][data-dsh-mode="dark"] .msg-row.user .msg-body {
  background:#303030 !important; color:#ECECEC !important; border:0 !important;
}
html[data-dsh-theme="chatgpt"][data-dsh-mode="dark"] .msg-row.assistant .msg-body,
html[data-dsh-theme="chatgpt"][data-dsh-mode="dark"] .canvas-title,
html[data-dsh-theme="chatgpt"][data-dsh-mode="dark"] .sb-head h2,
html[data-dsh-theme="chatgpt"][data-dsh-mode="dark"] .topbar h1 { color:#ECECEC !important; }

/* DSH chat: luminous blue-violet accent, translucent navigation, gradient actions. */
html[data-dsh-theme="original"] .shell,
html[data-dsh-theme="original"] .main { background:var(--bg) !important; }
html[data-dsh-theme="original"] .sidebar {
  background:var(--bg-soft) !important; border-right:1px solid var(--line) !important;
  box-shadow:inset -1px 0 rgba(120,145,255,.04) !important;
}
html[data-dsh-theme="original"] .topbar {
  background:var(--topbar-bg) !important; border-bottom:1px solid var(--line) !important;
  backdrop-filter:blur(18px) saturate(1.35); -webkit-backdrop-filter:blur(18px) saturate(1.35);
}
html[data-dsh-theme="original"] .composer {
  background:var(--surface) !important; border:1px solid var(--line-2) !important;
  border-radius:22px !important; box-shadow:var(--dsh-shadow),0 0 0 1px rgba(83,109,250,.035) !important;
}
html[data-dsh-theme="original"] .composer button:not(.btn-stop) {
  background:linear-gradient(135deg,#647CFF,#8A63E9) !important;
  color:#fff !important; box-shadow:0 5px 16px rgba(99,111,247,.30);
}
html[data-dsh-theme="original"] .msg-row.user .msg-body {
  background:linear-gradient(135deg,rgba(93,119,255,.15),rgba(145,105,235,.11)) !important;
  color:var(--text) !important; border:1px solid rgba(119,133,255,.18) !important;
  border-radius:17px !important;
}
html[data-dsh-theme="original"] .canvas-pane,
html[data-dsh-theme="original"] .canvas-header,
html[data-dsh-theme="original"] .think-panel {
  background:var(--surface) !important; border-color:var(--line) !important;
}
html[data-dsh-theme="original"] .sb-item.new {
  border:1px solid var(--line-2) !important; box-shadow:var(--dsh-shadow);
}
html[data-dsh-theme="original"] .sb-item:hover,
html[data-dsh-theme="original"] .act:hover { background:var(--bg-hover) !important; }
html[data-dsh-theme="original"] .canvas-btn.primary,
html[data-dsh-theme="original"] #themeBtn {
  background:linear-gradient(135deg,#647CFF,#8A63E9) !important; color:#fff !important;
  border:0 !important; box-shadow:0 4px 12px rgba(99,111,247,.24);
}
html[data-dsh-theme="original"] .messages-wrap {
  background:
    radial-gradient(ellipse 70% 38% at 50% 0%,rgba(104,124,255,.055),transparent 72%),
    var(--bg) !important;
}
html[data-dsh-theme="original"] .msg-row.assistant .msg-body { color:var(--text) !important; }
html[data-dsh-theme="original"] .model {
  border:1px solid var(--line-2); border-radius:999px; padding:4px 8px;
}
html[data-dsh-theme="original"] #themeBtn { display:inline-flex !important; }
@media(prefers-reduced-motion:no-preference) {
  html[data-dsh-theme="original"] .composer,
  html[data-dsh-theme="claude"] .composer,
  html[data-dsh-theme="chatgpt"] .composer { transition:background-color .24s ease,border-color .24s ease,box-shadow .24s ease; }
}

</style>
"""

_THEME_WIDGET = r"""
<div id="dsh017-theme-switcher">
  <button id="dsh017-theme-toggle" type="button"
          aria-label="切换全站主题" aria-expanded="false"
          aria-controls="dsh017-theme-panel" title="全站主题">◐</button>
  <div id="dsh017-theme-panel" aria-hidden="true">
    <label for="dsh017-theme-select">界面风格</label>
    <select id="dsh017-theme-select">
      <option value="original">DSH 原生</option>
      <option value="claude">Claude 风格</option>
      <option value="chatgpt">ChatGPT 风格</option>
    </select>
    <label for="dsh017-mode-select" class="dsh017-mode-label">颜色模式</label>
    <select id="dsh017-mode-select">
      <option value="system">跟随系统</option>
      <option value="light">浅色</option>
      <option value="dark">深色</option>
    </select>
  </div>
</div>
<script id="dsh017-global-theme-script">
(function () {
  "use strict";
  var themeCookie = "dsh017_theme";
  var modeCookie = "dsh017_mode";
  var allowedThemes = {original:true, claude:true, chatgpt:true};
  var allowedModes = {system:true, light:true, dark:true};
  var root = document.documentElement;
  var currentModeChoice = "system";

  function readCookie(name) {
    var parts = document.cookie ? document.cookie.split(";") : [];
    for (var i=0;i<parts.length;i++) {
      var part=parts[i].trim();
      if(part.indexOf(name+"=")===0) return part.slice(name.length+1);
    }
    return null;
  }
  function prefersDark() {
    return !!(window.matchMedia && window.matchMedia("(prefers-color-scheme: dark)").matches);
  }
  function saveCookie(name,value) {
    try {
      document.cookie=name+"="+value+"; Max-Age=31536000; Path=/; SameSite=Lax"+
        (location.protocol==="https:"?"; Secure":"");
    } catch(e) {}
  }
  function applyTheme(value,persist) {
    if(!allowedThemes[value]) value="original";
    if(persist) root.classList.add("dsh-theme-changing");
    root.setAttribute("data-dsh-theme",value);
    var select=document.getElementById("dsh017-theme-select");
    if(select) select.value=value;
    if(persist) {
      saveCookie(themeCookie,value);
      try { localStorage.setItem(themeCookie,value); } catch(e) {}
      window.setTimeout(function(){root.classList.remove("dsh-theme-changing");},420);
    }
    updateChatBrand(value);
  }
  function applyMode(choice,persist) {
    if(!allowedModes[choice]) choice="system";
    currentModeChoice=choice;
    var effective=(choice==="system"?(prefersDark()?"dark":"light"):choice);
    root.setAttribute("data-dsh-mode",effective);
    root.setAttribute("data-theme",effective);
    root.setAttribute("data-dsh-mode-choice",choice);
    var select=document.getElementById("dsh017-mode-select");
    if(select) select.value=choice;
    var btn=document.getElementById("themeBtn");
    if(btn) {
      btn.textContent=effective==="dark"?"☀":"☾";
      btn.title=effective==="dark"?"切换浅色模式":"切换深色模式";
      btn.setAttribute("aria-label",btn.title);
    }
    if(persist) {
      root.classList.add("dsh-theme-changing");
      saveCookie(modeCookie,choice);
      try {
        localStorage.setItem(modeCookie,choice);
        localStorage.setItem("theme",effective);
      } catch(e) {}
      window.setTimeout(function(){root.classList.remove("dsh-theme-changing");},420);
    }
  }
  function updateChatBrand(theme) {
    var labels={original:"DSH",claude:"Claude",chatgpt:"ChatGPT"};
    var label=labels[theme]||"DSH";
    var title=document.querySelector(".topbar h1");
    var side=document.querySelector(".sb-head h2");
    if(title) title.textContent=label;
    if(side) side.textContent=label;
    if(title || side) document.title=label+" · DSH-017";
    var foot=document.querySelector(".sb-foot");
    if(foot) foot.textContent="GLM-4.7-FLASH · "+(theme==="original"?"DSH 原生":label+" 风格界面");
  }

  var initialTheme=root.getAttribute("data-dsh-theme")||readCookie(themeCookie);
  if(!allowedThemes[initialTheme]) {
    try { initialTheme=localStorage.getItem(themeCookie); } catch(e) {}
  }
  applyTheme(initialTheme||"original",false);

  var initialMode=readCookie(modeCookie);
  if(!allowedModes[initialMode]) {
    try { initialMode=localStorage.getItem(modeCookie); } catch(e) {}
  }
  if(!allowedModes[initialMode]) {
    try {
      var legacy=localStorage.getItem("theme");
      initialMode=(legacy==="dark"||legacy==="light")?legacy:"system";
    } catch(e) { initialMode="system"; }
  }
  applyMode(initialMode||"system",false);

  var media=window.matchMedia?window.matchMedia("(prefers-color-scheme: dark)"):null;
  if(media) {
    var onSystemChange=function(){if(currentModeChoice==="system") applyMode("system",false);};
    if(media.addEventListener) media.addEventListener("change",onSystemChange);
    else if(media.addListener) media.addListener(onSystemChange);
  }

  var toggle=document.getElementById("dsh017-theme-toggle");
  var panel=document.getElementById("dsh017-theme-panel");
  var themeSelect=document.getElementById("dsh017-theme-select");
  var modeSelect=document.getElementById("dsh017-mode-select");
  var widget=document.getElementById("dsh017-theme-switcher");
  var chatTopbar=document.querySelector(".topbar");
  if(widget&&chatTopbar) {
    chatTopbar.appendChild(widget);
    widget.classList.add("dsh017-theme-embedded");
  }
  function setPanelOpen(open,returnFocus) {
    panel.classList.toggle("open",open);
    panel.setAttribute("aria-hidden",open?"false":"true");
    toggle.setAttribute("aria-expanded",open?"true":"false");
    if(open) themeSelect.focus();
    else if(returnFocus) toggle.focus();
  }
  if(toggle&&panel&&themeSelect&&modeSelect) {
    toggle.addEventListener("click",function(){setPanelOpen(!panel.classList.contains("open"),false);});
    themeSelect.addEventListener("change",function(){applyTheme(themeSelect.value,true);});
    modeSelect.addEventListener("change",function(){applyMode(modeSelect.value,true);});
    document.addEventListener("keydown",function(event){
      if(event.key==="Escape"&&panel.classList.contains("open")) setPanelOpen(false,true);
    });
    document.addEventListener("click",function(event){
      if(panel.classList.contains("open")&&!event.target.closest("#dsh017-theme-switcher")) setPanelOpen(false,false);
    });
  }
  window.DSH017={
    applyTheme:applyTheme,
    applyMode:applyMode,
    toggleMode:function(){applyMode(root.getAttribute("data-dsh-mode")==="dark"?"light":"dark",true);},
    getTheme:function(){return root.getAttribute("data-dsh-theme")||"original";},
    getMode:function(){return root.getAttribute("data-dsh-mode")||"light";}
  };
})();;
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
        mode = request.cookies.get("dsh017_mode", "")
        import re
        attrs = ""
        if theme in _ALLOWED_THEMES:
            attrs += ' data-dsh-theme="' + theme + '"'
        if mode in {"light", "dark"}:
            attrs += ' data-dsh-mode="' + mode + '" data-theme="' + mode + '"'
        if attrs:
            html = re.sub(r"<html\b", "<html" + attrs, html, count=1, flags=re.IGNORECASE)

        head_pos = html.lower().find("</head>")
        body_pos = html.lower().rfind("</body>")
        html = html[:head_pos] + _THEME_CSS + html[head_pos:]
        body_pos = html.lower().rfind("</body>")
        html = html[:body_pos] + _THEME_WIDGET + html[body_pos:]
        response.set_data(html)
        return response

    return app
