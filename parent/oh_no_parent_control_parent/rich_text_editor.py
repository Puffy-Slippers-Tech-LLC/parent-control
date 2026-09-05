"""Offline Quill rich-text editor hosted in the supported GTK 4 WebKit widget."""

from __future__ import annotations

import json
import logging
from pathlib import Path

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("JavaScriptCore", "6.0")
gi.require_version("WebKit", "6.0")
from gi.repository import Gtk, WebKit

from common.oh_no_parent_control_ui.accessibility import describe_control


LOG = logging.getLogger("oh-no-parent-control-parent")
ASSET_DIR = Path(__file__).with_name("rich_editor")


class RichTextEditor(Gtk.Box):
    """Quill-backed editor whose draft never leaves the local WebKit process."""

    def __init__(self, attachment_requested):
        super().__init__(orientation=Gtk.Orientation.VERTICAL,
                         css_classes=["feedback-rich-editor"])
        self.set_overflow(Gtk.Overflow.HIDDEN)
        self._attachment_requested = attachment_requested
        self._plain_text = ""
        self._html = ""
        self._delta = '{"ops":[{"insert":"\\n"}]}'
        self._ready = False

        manager = WebKit.UserContentManager()
        if not manager.register_script_message_handler("feedbackEditor"):
            raise RuntimeError("Could not register the rich-editor message bridge")
        manager.connect("script-message-received::feedbackEditor", self._message_received)
        settings = WebKit.Settings()
        settings.set_enable_javascript(True)
        settings.set_javascript_can_open_windows_automatically(False)
        settings.set_javascript_can_access_clipboard(False)
        settings.set_allow_file_access_from_file_urls(False)
        settings.set_enable_html5_database(False)
        settings.set_enable_html5_local_storage(False)
        self._view = WebKit.WebView(
            network_session=WebKit.NetworkSession.new_ephemeral(),
            user_content_manager=manager,
            settings=settings,
        )
        self._view.connect("decide-policy", self._decide_policy)
        self._view.connect("web-process-terminated", self._web_process_terminated)
        self._view.set_vexpand(True)
        self._view.set_hexpand(True)
        describe_control(
            self._view,
            "Your feedback",
            "Write and format feedback. Use the toolbar for headings, bold, italic, "
            "underline, lists, quotes, code, links, attachments, and remove formatting.",
        )
        self.append(self._view)
        self._view.load_html(self._document(), None)

    @property
    def plain_text(self):
        return self._plain_text

    @property
    def html(self):
        return self._html

    @property
    def delta(self):
        return self._delta

    def clear(self):
        self._plain_text = ""
        self._html = ""
        self._delta = '{"ops":[{"insert":"\\n"}]}'
        if self._ready:
            self._view.evaluate_javascript(
                "window.feedbackEditor.clear();", -1, None, None, None, None, None,
            )

    def grab_editor_focus(self):
        if self._ready:
            self._view.evaluate_javascript(
                "window.feedbackEditor.focus();", -1, None, None, None, None, None,
            )
        else:
            self._view.grab_focus()

    def _message_received(self, _manager, value):
        try:
            payload = json.loads(value.to_string())
        except (TypeError, ValueError):
            LOG.warning("rich editor bridge rejected malformed message")
            return
        if not isinstance(payload, dict):
            LOG.warning("rich editor bridge rejected non-object message")
            return
        kind = payload.get("type")
        if kind == "ready":
            self._ready = True
            encoded_delta = json.dumps(self._delta)
            self._view.evaluate_javascript(
                f"window.feedbackEditor.restore(JSON.parse({encoded_delta}));",
                -1, None, None, None, None, None,
            )
            LOG.info("rich editor ready engine=quill version=2.0.3")
            return
        if kind == "attachment":
            self._attachment_requested()
            return
        if kind != "change":
            LOG.warning("rich editor bridge rejected unknown message type")
            return
        text = payload.get("text")
        rich_html = payload.get("html")
        delta = payload.get("delta")
        if not all(isinstance(item, str) for item in (text, rich_html, delta)):
            LOG.warning("rich editor bridge rejected invalid change payload")
            return
        try:
            parsed_delta = json.loads(delta)
        except ValueError:
            LOG.warning("rich editor bridge rejected invalid delta")
            return
        if not isinstance(parsed_delta, dict) or not isinstance(parsed_delta.get("ops"), list):
            LOG.warning("rich editor bridge rejected invalid delta shape")
            return
        # Contents are deliberately never logged: feedback may contain PII.
        self._plain_text = text
        self._html = rich_html
        self._delta = delta

    def _decide_policy(self, _view, decision, decision_type):
        if decision_type in (WebKit.PolicyDecisionType.NAVIGATION_ACTION,
                             WebKit.PolicyDecisionType.NEW_WINDOW_ACTION):
            action = decision.get_navigation_action()
            request = action.get_request() if action is not None else None
            uri = request.get_uri() if request is not None else ""
            if uri and uri != "about:blank":
                decision.ignore()
                LOG.info("rich editor blocked external navigation")
                return True
        return False

    def _web_process_terminated(self, _view, reason):
        self._ready = False
        LOG.warning("rich editor process terminated reason=%s", reason.value_nick)
        self._view.reload()

    @staticmethod
    def _document():
        quill_js = (ASSET_DIR / "quill.js").read_text(encoding="utf-8")
        quill_css = (ASSET_DIR / "quill.snow.css").read_text(encoding="utf-8")
        # The page is an immutable in-memory document. CSP forbids every network
        # source; only the bundled editor and inline app bootstrap can execute.
        return f"""<!doctype html>
<html><head><meta charset="utf-8">
<meta http-equiv="Content-Security-Policy"
      content="default-src 'none'; img-src 'none'; style-src 'unsafe-inline'; script-src 'unsafe-inline'">
<style>{quill_css}</style>
<style>
html, body {{ margin: 0; height: 100%; overflow: hidden; background: transparent; color: #292934;
              font: 16px Ubuntu, system-ui, sans-serif; }}
body {{ display: flex; flex-direction: column; }}
#toolbar {{ border: 0; border-bottom: 1px solid rgba(36,36,42,.13); flex: none;
            display: flex; flex-wrap: wrap; align-items: center; gap: 4px 10px;
            padding: 7px 10px; background: #fcfcfe; font: inherit; }}
#toolbar::after {{ display: none; }}
#toolbar .ql-formats {{ display: flex; align-items: center; margin: 0; }}
#toolbar .ql-formats:nth-child(2) {{ padding-right: 8px;
                                  border-right: 1px solid #dddde5; }}
#toolbar .ql-formats:last-child {{ margin-left: auto; }}
#toolbar button {{ width: 36px; height: 30px; padding: 6px 9px; border-radius: 5px; }}
#toolbar button:hover {{ background: #efeaff; }}
#toolbar .ql-picker {{ color: #343437; font: inherit; }}
#toolbar .ql-picker.ql-header {{ width: 112px; height: 30px; }}
#toolbar .ql-picker-label {{ display: flex; align-items: center; padding: 0 10px;
                           border: 1px solid #e0e0e5; border-radius: 8px; background: white; }}
#toolbar .ql-picker-label svg {{ right: 8px; }}
#toolbar .ql-picker-label svg polygon {{ display: none; }}
#toolbar .ql-picker-label::after {{ content: ''; width: 5px; height: 5px;
                                  border-right: 2px solid; border-bottom: 2px solid;
                                  transform: rotate(45deg); margin: -3px 2px 0 auto; }}
#toolbar .ql-picker-options {{ border-radius: 8px; background: white; }}
#toolbar .ql-stroke {{ stroke: #343437; }}
#toolbar .ql-fill {{ fill: #343437; }}
#toolbar .ql-active .ql-stroke, #toolbar button:hover .ql-stroke {{ stroke: #7650ff; }}
#toolbar .ql-active .ql-fill, #toolbar button:hover .ql-fill {{ fill: #7650ff; }}
#editor {{ border: 0; flex: 1; min-height: 0; overflow: hidden; font: inherit; }}
.ql-editor {{ min-height: 0; overflow-y: auto; padding: 14px 18px; line-height: 1.45; }}
.ql-editor.ql-blank::before {{ left: 18px; right: 18px; color: #8c8c9b; }}
.ql-toolbar button:focus-visible, .ql-toolbar .ql-picker-label:focus-visible {{
  outline: 2px solid #7657f6; outline-offset: 2px;
}}
#toolbar .ql-attachment {{ padding: 3px 7px; font-size: 19px; line-height: 24px; }}
</style></head><body>
<div id="toolbar" role="toolbar" aria-label="Feedback formatting">
  <span class="ql-formats">
    <select class="ql-header" title="Text style" aria-label="Text style">
      <option selected></option><option value="1">Heading 1</option><option value="2">Heading 2</option>
    </select>
  </span>
  <span class="ql-formats">
    <button class="ql-bold" title="Bold" aria-label="Bold"></button>
    <button class="ql-italic" title="Italic" aria-label="Italic"></button>
    <button class="ql-underline" title="Underline" aria-label="Underline"></button>
    <button class="ql-strike" title="Strikethrough" aria-label="Strikethrough"></button>
  </span>
  <span class="ql-formats">
    <button class="ql-list" value="ordered" title="Numbered list" aria-label="Numbered list"></button>
    <button class="ql-list" value="bullet" title="Bulleted list" aria-label="Bulleted list"></button>
    <button class="ql-blockquote" title="Quote" aria-label="Quote"></button>
    <button class="ql-code-block" title="Code block" aria-label="Code block"></button>
  </span>
  <span class="ql-formats">
    <button class="ql-link" title="Insert link" aria-label="Insert link"></button>
    <button class="ql-attachment" type="button" title="Add attachment" aria-label="Add attachment">📎</button>
    <button class="ql-clean" title="Remove formatting" aria-label="Remove formatting"></button>
  </span>
</div>
<div id="editor" aria-label="Your feedback"></div>
<script>{quill_js}</script>
<script>
'use strict';
const bridge = window.webkit.messageHandlers.feedbackEditor;
const quill = new Quill('#editor', {{
  theme: 'snow',
  placeholder: 'Describe your idea, or what happened and what you expected...',
  formats: ['header', 'bold', 'italic', 'underline', 'strike', 'list', 'blockquote',
            'code-block', 'link'],
  modules: {{ toolbar: {{ container: '#toolbar', handlers: {{
    attachment: () => bridge.postMessage(JSON.stringify({{ type: 'attachment' }})),
  }} }} }},
}});
function publish() {{
  const text = quill.getText().replace(/\\n$/, '');
  bridge.postMessage(JSON.stringify({{
    type: 'change', text,
    html: quill.getSemanticHTML(),
    delta: JSON.stringify(quill.getContents()),
  }}));
}}
quill.on('text-change', publish);
window.feedbackEditor = {{
  clear() {{ quill.setContents([]); publish(); }},
  focus() {{ quill.focus(); }},
  restore(delta) {{ quill.setContents(delta); publish(); }},
}};
bridge.postMessage(JSON.stringify({{ type: 'ready' }}));
</script></body></html>"""
