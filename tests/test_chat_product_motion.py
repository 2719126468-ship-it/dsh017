import unittest

from app.chat_ui import CHAT_HTML
from app.ui_theme import _THEME_CSS, _THEME_WIDGET


class ChatProductMotionTests(unittest.TestCase):
    def test_chat_has_a_non_intrusive_jump_to_latest_control(self):
        self.assertEqual(CHAT_HTML.count("async function requestStream"), 1)
        self.assertEqual(CHAT_HTML.count("function renderAssistantMarkdown"), 1)
        self.assertEqual(CHAT_HTML.count("var WS ="), 1)
        self.assertEqual(CHAT_HTML.count("<script>"), 2)
        self.assertEqual(CHAT_HTML.count("</script>"), 2)
        self.assertIn('id="jumpLatest"', CHAT_HTML)
        self.assertIn("function isNearBottom()", CHAT_HTML)
        self.assertIn("autoFollow = isNearBottom()", CHAT_HTML)
        self.assertIn("scrollBottom(force)", CHAT_HTML)
        self.assertIn("autoFollow = true", CHAT_HTML)

    def test_streaming_batches_chunks_and_renders_markdown_blocks_incrementally(self):
        self.assertIn("function queueStreamText(state, chunk)", CHAT_HTML)
        self.assertIn("requestAnimationFrame(function(){ flushStreamText(state); })", CHAT_HTML)
        self.assertIn("function updateStreamPreview(state)", CHAT_HTML)
        self.assertIn("function processStreamLine(state, line)", CHAT_HTML)
        self.assertIn("function createStreamCodeBlock(state, language)", CHAT_HTML)
        self.assertIn("function createStreamTable(state, headerLine)", CHAT_HTML)
        self.assertIn("function appendStreamTableRow(state, line, header)", CHAT_HTML)
        self.assertIn("state.codeTextNode.nodeValue = state.codeCommitted + state.buffer", CHAT_HTML)
        self.assertIn("state.tableCandidate = line", CHAT_HTML)
        self.assertIn("function finalizeStreamMarkdown(state)", CHAT_HTML)
        self.assertIn("finalizeStreamMarkdown(streamState)", CHAT_HTML)
        self.assertNotIn("bodyEl.innerHTML = ''", CHAT_HTML)
        self.assertIn("composer.classList.add('is-streaming')", CHAT_HTML)
        self.assertIn("composer.classList.remove('is-streaming')", CHAT_HTML)
        self.assertIn("code.appendChild(state.codeTextNode)", CHAT_HTML)

    def test_generation_can_be_stopped_and_keeps_partial_reply(self):
        self.assertIn('id="stop"', CHAT_HTML)
        self.assertIn("function stopGeneration()", CHAT_HTML)
        self.assertIn("new AbortController()", CHAT_HTML)
        self.assertIn("requestOptions.signal = activeController.signal", CHAT_HTML)
        self.assertIn("activeReader.cancel()", CHAT_HTML)
        self.assertIn("var stoppedBeforeRead = new Error('Generation stopped')", CHAT_HTML)
        self.assertIn("stoppedSignal.name = 'AbortError'", CHAT_HTML)
        self.assertIn("if(wasStopped)", CHAT_HTML)
        self.assertIn("history.push({role:'assistant', content: fullText, fresh:true})", CHAT_HTML)
        self.assertIn("stopBtn.onclick = stopGeneration", CHAT_HTML)
        self.assertIn("stopBtn.hidden = true", CHAT_HTML)
        self.assertIn(".composer #stop[hidden]{display:none}", CHAT_HTML)
        self.assertIn("回复已停止", CHAT_HTML)

    def test_completed_assistant_messages_use_safe_dom_markdown_renderer(self):
        self.assertIn("function renderAssistantMarkdown(target, source)", CHAT_HTML)
        self.assertIn("function appendInlineMarkdown(parent, source)", CHAT_HTML)
        self.assertIn("code.textContent = codeLines.join", CHAT_HTML)
        self.assertIn("node.textContent = token.slice", CHAT_HTML)
        self.assertIn("node.rel = 'noopener noreferrer'", CHAT_HTML)
        self.assertIn("renderAssistantMarkdown(bodyEl2, fullText)", CHAT_HTML)
        self.assertIn("copyButton.onclick = function()", CHAT_HTML)
        self.assertIn("(codeCopy, codeLines.join(nl))", CHAT_HTML)
        self.assertIn("tableSeparatorPattern", CHAT_HTML)
        self.assertIn("className = 'md-table'", CHAT_HTML)
        self.assertIn("isTableStart(index)", CHAT_HTML)
        self.assertIn("headerCells.forEach", CHAT_HTML)
        self.assertIn(".md-table-wrap", _THEME_CSS)
        self.assertIn("codeLines.join(nl)", CHAT_HTML)

    def test_product_themes_have_distinct_chat_layouts_and_motion(self):
        self.assertIn('html[data-dsh-theme="claude"] .msg-row.assistant .msg-body', _THEME_CSS)
        self.assertIn('html[data-dsh-theme="chatgpt"] .msg-row.assistant .msg-body', _THEME_CSS)
        self.assertIn('html[data-dsh-theme="claude"] .composer', _THEME_CSS)
        self.assertIn('html[data-dsh-theme="chatgpt"] .composer', _THEME_CSS)
        self.assertIn(".composer.is-streaming::after", _THEME_CSS)
        self.assertIn("#jumpLatest.visible", _THEME_CSS)
        self.assertIn(".canvas-pane.open", _THEME_CSS)
        self.assertIn(".mask.show", _THEME_CSS)
        self.assertIn("@media (prefers-reduced-motion: reduce)", _THEME_CSS)

    def test_all_visual_themes_keep_a_working_global_dark_mode(self):
        self.assertIn('id="dsh017-mode-select"', _THEME_WIDGET)
        self.assertIn('window.DSH017=', _THEME_WIDGET)
        self.assertIn('toggleMode:function()', _THEME_WIDGET)
        self.assertIn('data-dsh-mode="dark"', _THEME_CSS)
        self.assertIn('html[data-dsh-theme="claude"][data-dsh-mode="dark"] .composer', _THEME_CSS)
        self.assertIn('html[data-dsh-theme="chatgpt"][data-dsh-mode="dark"] .composer', _THEME_CSS)
        self.assertNotIn('html[data-dsh-theme="chatgpt"] #themeBtn', _THEME_CSS)
        self.assertNotIn('html[data-dsh-theme="claude"] #themeBtn', _THEME_CSS)
        self.assertIn('window.DSH017.toggleMode()', CHAT_HTML)

    def test_dsh_native_theme_has_its_own_visual_identity(self):
        self.assertIn('html[data-dsh-theme="original"] .composer', _THEME_CSS)
        self.assertIn('linear-gradient(135deg,#647CFF,#8A63E9)', _THEME_CSS)
        self.assertIn('html[data-dsh-theme="original"][data-dsh-mode="dark"]', _THEME_CSS)

    def test_canvas_pane_uses_transitionable_closed_and_open_states(self):
        self.assertIn(".canvas-pane{display:flex;flex:0 0 0;width:0", CHAT_HTML)
        self.assertIn("transition:flex-basis var(--dur-panel)", CHAT_HTML)
        self.assertIn("width var(--dur-panel) var(--ease)", CHAT_HTML)
        self.assertIn("visibility:hidden", CHAT_HTML)
        self.assertIn("visibility:visible", CHAT_HTML)
        self.assertIn(".canvas-pane.open{flex:0 0 clamp(300px,42%,620px)", CHAT_HTML)
        self.assertIn("@media (max-width:1024px)", CHAT_HTML)
        self.assertIn(".canvas-pane.open{flex:1 1 100%;width:100%;height:100%", CHAT_HTML)
        self.assertNotIn(".canvas-pane{display:none", CHAT_HTML)

    def test_theme_panel_is_accessible_and_uses_animated_open_state(self):
        self.assertIn('aria-hidden="true"', _THEME_WIDGET)
        self.assertIn('aria-expanded="false"', _THEME_WIDGET)
        self.assertIn('panel.classList.toggle("open", open)', _THEME_WIDGET)
        self.assertIn('panel.setAttribute("aria-hidden"', _THEME_WIDGET)
        self.assertIn('event.key === "Escape"', _THEME_WIDGET)

    def test_chat_theme_control_is_docked_in_the_chat_header(self):
        self.assertIn('document.querySelector(".topbar")', _THEME_WIDGET)
        self.assertIn('chatTopbar.appendChild(widget)', _THEME_WIDGET)
        self.assertIn('.dsh017-theme-embedded', _THEME_CSS)


if __name__ == "__main__":
    unittest.main()
