"""Offline Quill rich-text editor hosted in the supported GTK 4 WebKit widget."""

from __future__ import annotations

from . import messages as m
from .message import render
from .translation_widgets import context_for, register_retranslation

import json
from html import escape
from common.oh_no_parent_control_ui.diagnostic_events import get_logger, error_code
from pathlib import Path

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("JavaScriptCore", "6.0")
gi.require_version("WebKit", "6.0")
from gi.repository import Gtk, WebKit

from common.oh_no_parent_control_ui.accessibility import describe_control
from common.oh_no_parent_control_ui.application_ui import UIError, bind_ui


LOG = get_logger("rich-text-editor")
ASSET_DIR = Path(__file__).with_name("rich_editor")


class RichTextEditor(Gtk.Box):
    """Quill-backed editor whose draft never leaves the local WebKit process."""

    def __init__(self, attachment_requested, *, placeholder=m.EDITOR_PLACEHOLDER):
        super().__init__(orientation=Gtk.Orientation.VERTICAL,
                         css_classes=["feedback-rich-editor"])
        self.set_overflow(Gtk.Overflow.HIDDEN)
        self._attachment_requested = attachment_requested
        self._placeholder = placeholder
        self._plain_text = ""
        self._html = ""
        self._delta = '{"ops":[{"insert":"\\n"}]}'
        self._ready = False
        self._editor_generation = 0
        self._editor_revision = -1

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
            m.YOUR_FEEDBACK,
            m.EDITOR_DESCRIPTION,
            automation_id="feedback-webview",
        )
        editor_ids = tuple(key for key in self._labels(context_for(self).translations)
                           if key.startswith("feedback-"))
        if attachment_requested is None:
            editor_ids = tuple(key for key in editor_ids
                               if key != "feedback-format-attachment")
        bind_ui(self._view, aliases=(*editor_ids, "feedback-editor-selection",
                                     "feedback-editor-document", "feedback-editor-insert",
                                     "feedback-undo", "feedback-redo", "feedback-webview"),
                dispatcher=self._ui_dispatch,
                operations=("getElementById", "getValue", "setValue", "getText",
                            "setText", "activate", "getChoices"))
        self.append(self._view)
        self._view.load_html(self._document(), None)
        register_retranslation(self, self._retranslate)

    def _retranslate(self, translations):
        if not self._ready:
            return
        labels = self._labels(translations)
        context = context_for(self)
        labels.update(direction=context.direction, language=context.language)
        # JSON is a JavaScript value, never markup or a script assembled from data.
        self._view.evaluate_javascript(
            'window.feedbackEditor.labels(' + json.dumps(labels) + ');',
            -1, None, None, None, None, None,
        )

    def _labels(self, translations):
        return {key: render(value, translations) for key, value in {
            'feedback-format-toolbar': m.FEEDBACK_FORMATTING,
            'feedback-editor-input': m.YOUR_FEEDBACK,
            'feedback-format-style': m.TEXT_STYLE,
            'feedback-format-normal': m.NORMAL_TEXT,
            'feedback-format-heading-1': m.HEADING_1,
            'feedback-format-heading-2': m.HEADING_2,
            'feedback-format-bold': m.BOLD,
            'feedback-format-italic': m.ITALIC,
            'feedback-format-underline': m.UNDERLINE,
            'feedback-format-strike': m.STRIKETHROUGH,
            'feedback-format-ordered': m.NUMBERED_LIST,
            'feedback-format-bulleted': m.BULLETED_LIST,
            'feedback-format-quote': m.QUOTE,
            'feedback-format-code': m.CODE_BLOCK,
            'feedback-format-link': m.INSERT_LINK,
            'feedback-format-attachment': m.ADD_ATTACHMENT,
            'feedback-format-clear': m.REMOVE_FORMATTING,
            'feedback-link-target': m.LINK_TARGET,
            'feedback-link-editor': m.LINK_EDITOR,
            'feedback-link-preview': m.OPEN_LINK_PREVIEW,
            'feedback-link-save': m.SAVE_LINK,
            'edit-link': m.EDIT_LINK,
            'feedback-link-remove': m.REMOVE_LINK,
            'placeholder': self._placeholder,
            'code-block': m.CODE_BLOCK,
            'numbered-list-item': m.NUMBERED_LIST_ITEM,
            'bulleted-list-item': m.BULLETED_LIST_ITEM,
        }.items()}

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

    def set_text(self, text):
        """Seed a literal draft, including before the web process is ready."""
        self._plain_text = text
        self._html = "<p>" + escape(text).replace("\n", "<br>") + "</p>"
        self._delta = json.dumps({"ops": [{"insert": text + "\n"}]})
        if self._ready:
            self._view.evaluate_javascript(
                f"window.feedbackEditor.restore(JSON.parse({json.dumps(self._delta)}));",
                -1, None, None, None, None, None,
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
            LOG.warning("rich-text-editor.001")
            return
        self._apply_editor_message(payload)

    def _apply_editor_message(self, payload):
        if not isinstance(payload, dict):
            LOG.warning("rich-text-editor.002")
            return
        kind = payload.get("type")
        if kind == "ready":
            self._editor_generation += 1
            self._editor_revision = -1
            self._ready = True
            self._retranslate(context_for(self).translations)
            encoded_delta = json.dumps(self._delta)
            self._view.evaluate_javascript(
                f"window.feedbackEditor.restore(JSON.parse({encoded_delta}));",
                -1, None, None, None, None, None,
            )
            LOG.info("rich-text-editor.003")
            return
        if kind == "attachment":
            if self._attachment_requested is not None:
                self._attachment_requested()
            return
        if kind != "change":
            LOG.warning("rich-text-editor.004")
            return
        revision = payload.get("revision")
        if revision is not None:
            if type(revision) is not int or revision <= self._editor_revision:
                return
        text = payload.get("text")
        rich_html = payload.get("html")
        delta = payload.get("delta")
        if not all(isinstance(item, str) for item in (text, rich_html, delta)):
            LOG.warning("rich-text-editor.005")
            return
        try:
            parsed_delta = json.loads(delta)
        except ValueError:
            LOG.warning("rich-text-editor.006")
            return
        if not isinstance(parsed_delta, dict) or not isinstance(parsed_delta.get("ops"), list):
            LOG.warning("rich-text-editor.007")
            return
        # Contents are deliberately never logged: feedback may contain PII.
        self._plain_text = text
        self._html = rich_html
        self._delta = delta
        if revision is not None:
            self._editor_revision = revision

    def _ui_dispatch(self, operation, arguments, complete):
        """Run a finite editor operation; callers never supply JavaScript."""
        if not self._ready:
            complete(None, UIError("Unavailable"))
            return
        request = json.dumps({**arguments, "operation": operation}, ensure_ascii=True)
        generation = self._editor_generation

        def finished(view, result, *_args):
            try:
                value = view.evaluate_javascript_finish(result)
                if not self._ready or generation != self._editor_generation:
                    raise ValueError("Editor document changed")
                response = json.loads(value.to_string())
                if "error" in response:
                    raise ValueError(response["error"])
                # Commit the same change message before acknowledging input,
                # even if WebKit's script-message delivery is still queued.
                self._apply_editor_message(response["draft"])
            except Exception:
                # Never return editor contents or JavaScript exceptions as logs.
                complete(None, UIError("Failed"))
                return
            complete(response["result"])

        self._view.evaluate_javascript(
            "JSON.stringify(window.feedbackEditor.ui(" + request + "));",
            -1, None, None, None, finished, None,
        )

    def _decide_policy(self, _view, decision, decision_type):
        if decision_type in (WebKit.PolicyDecisionType.NAVIGATION_ACTION,
                             WebKit.PolicyDecisionType.NEW_WINDOW_ACTION):
            action = decision.get_navigation_action()
            request = action.get_request() if action is not None else None
            uri = request.get_uri() if request is not None else ""
            if uri and uri != "about:blank":
                decision.ignore()
                LOG.info("rich-text-editor.008")
                return True
        return False

    def _web_process_terminated(self, _view, reason):
        self._ready = False
        self._editor_generation += 1
        LOG.warning("rich-text-editor.009", reason=reason.value_nick)
        self._view.reload()

    def _document(self):
        quill_js = (ASSET_DIR / "quill.js").read_text(encoding="utf-8")
        quill_css = (ASSET_DIR / "quill.snow.css").read_text(encoding="utf-8")
        ui_js = (ASSET_DIR / "application_ui.js").read_text(encoding="utf-8")
        context = context_for(self)
        labels = self._labels(context.translations)
        labels.update(direction=context.direction, language=context.language)
        initial_labels = json.dumps(labels)
        attachment_button = (
            '<button id="feedback-format-attachment" class="ql-attachment" type="button" '
            'aria-label="Add attachment">📎</button>'
            if self._attachment_requested is not None else ""
        )
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
/* Decorations propagate visually across nested inline elements but are not
   inherited computed styles. Expose both on combined Quill formats so public
   accessibility text attributes describe the formatting the customer applied. */
#feedback-editor-input s u, #feedback-editor-input u s,
#feedback-editor-input s a {{
  text-decoration-line: underline line-through;
}}
#feedback-format-toolbar {{ border: 0; border-bottom: 1px solid rgba(36,36,42,.13); flex: none;
            display: flex; flex-wrap: wrap; align-items: center; gap: 4px 10px;
            padding: 7px 10px; background: #fcfcfe; font: inherit; }}
#feedback-format-toolbar::after {{ display: none; }}
#feedback-format-toolbar .ql-formats {{ display: flex; align-items: center; margin: 0; }}
#feedback-format-toolbar .ql-formats:nth-child(2) {{ padding-inline-end: 8px;
                                  border-inline-end: 1px solid #dddde5; }}
#feedback-format-toolbar .ql-formats:last-child {{ margin-inline-start: auto; }}
#feedback-format-toolbar button {{ width: 36px; height: 30px; padding: 6px 9px; border-radius: 5px; }}
#feedback-format-toolbar button:hover {{ background: #efeaff; }}
#feedback-format-toolbar .ql-picker {{ color: #343437; font: inherit; }}
#feedback-format-toolbar .ql-picker.ql-header {{ width: auto; min-width: 112px; height: auto;
  max-width: calc(100vw - 40px); }}
#feedback-format-toolbar .ql-picker-label {{ display: flex; align-items: center; padding: 0 10px;
                           border: 1px solid #e0e0e5; border-radius: 8px; background: white; }}
#feedback-format-toolbar .ql-picker-label svg {{ right: 8px; }}
#feedback-format-toolbar .ql-picker-label svg polygon {{ display: none; }}
#feedback-format-toolbar .ql-picker-label::after {{ content: ''; width: 5px; height: 5px;
                                  border-right: 2px solid; border-bottom: 2px solid;
                                  transform: rotate(45deg); margin-block-start: -3px;
                                  margin-inline-start: auto; margin-inline-end: 2px; }}
#feedback-format-toolbar .ql-picker-label::before,
#feedback-format-toolbar .ql-picker-item {{ white-space: normal; overflow-wrap: anywhere; }}
/* Keep formatting choices inside even the shortest editor viewport. */
#feedback-format-toolbar .ql-picker-options {{ border-radius: 8px; background: white;
  max-height: calc(100vh - 48px); overflow-y: auto; box-sizing: border-box; }}
#feedback-format-toolbar .ql-stroke {{ stroke: #343437; }}
#feedback-format-toolbar .ql-fill {{ fill: #343437; }}
#feedback-format-toolbar .ql-active .ql-stroke,
#feedback-format-toolbar button:hover .ql-stroke {{ stroke: #7650ff; }}
#feedback-format-toolbar .ql-active .ql-fill,
#feedback-format-toolbar button:hover .ql-fill {{ fill: #7650ff; }}
#feedback-editor-root {{ border: 0; flex: 1; min-height: 0; overflow: hidden; font: inherit; }}
.ql-editor {{ min-height: 0; overflow-y: auto; padding: 14px 18px; line-height: 1.45;
  text-align: start; }}
.ql-editor.feedback-empty::before {{ content: attr(data-placeholder);
  position: absolute; pointer-events: none; font-style: italic;
  left: 18px; right: 18px; color: #8c8c9b; white-space: pre-wrap; }}
.ql-toolbar button:focus-visible, .ql-toolbar .ql-picker-label:focus-visible {{
  outline: 2px solid #7657f6; outline-offset: 2px;
}}
#feedback-format-toolbar .ql-attachment {{ padding: 3px 7px; font-size: 19px; line-height: 24px; }}
#feedback-format-toolbar .ql-picker-label[data-label]::before,
#feedback-format-toolbar .ql-picker-item[data-label]::before {{ content: attr(data-label) !important; }}
.ql-tooltip a.ql-action[data-label]::after {{ content: attr(data-label) !important; }}
.ql-tooltip a.ql-remove[data-label]::before {{ content: attr(data-label) !important; }}
.ql-tooltip a.ql-remove::after {{ content: none !important; }}
.ql-tooltip[data-label]::before {{ content: attr(data-label) !important; }}
</style></head><body>
<div id="feedback-format-toolbar" role="toolbar">
  <span class="ql-formats">
    <select class="ql-header">
      <option selected></option>
      <option value="1"></option>
      <option value="2"></option>
    </select>
  </span>
  <span class="ql-formats">
    <button id="feedback-format-bold" class="ql-bold"></button>
    <button id="feedback-format-italic" class="ql-italic"></button>
    <button id="feedback-format-underline" class="ql-underline"></button>
    <button id="feedback-format-strike" class="ql-strike"></button>
  </span>
  <span class="ql-formats">
    <button id="feedback-format-ordered" class="ql-list" value="ordered"></button>
    <button id="feedback-format-bulleted" class="ql-list" value="bullet"></button>
    <button id="feedback-format-quote" class="ql-blockquote"></button>
    <button id="feedback-format-code" class="ql-code-block"></button>
  </span>
  <span class="ql-formats">
    <button id="feedback-format-link" class="ql-link"></button>
    {attachment_button}
    <button id="feedback-format-clear" class="ql-clean"></button>
  </span>
</div>
<div id="feedback-editor-root"></div>
<script>{quill_js}</script>
<script>
'use strict';
const bridge = window.webkit.messageHandlers.feedbackEditor;
const quill = new Quill('#feedback-editor-root', {{
  theme: 'snow',
  placeholder: '',
  formats: ['header', 'bold', 'italic', 'underline', 'strike', 'list', 'blockquote',
            'code-block', 'link'],
  modules: {{ toolbar: {{ container: '#feedback-format-toolbar', handlers: {{
    attachment: () => bridge.postMessage(JSON.stringify({{ type: 'attachment' }})),
  }} }} }},
}});
function identify(selector, id) {{
  const element = document.querySelector(selector);
  if (!element)
    throw new Error(`Missing generated rich-editor control: ${{id}}`);
  element.id = id;
  return element;
}}
const editor = identify(
  '#feedback-editor-root .ql-editor', 'feedback-editor-input');
// Draft direction follows its content, independently of the product's language.
// Relabeling only changes the surrounding UI, never Quill formats or undo state.
editor.setAttribute('dir', 'auto');
const stylePicker = document.querySelector(
  '#feedback-format-toolbar .ql-picker.ql-header');
if (!stylePicker)
  throw new Error('Missing generated rich-editor style picker');
identify(
  '#feedback-format-toolbar .ql-picker.ql-header .ql-picker-label',
  'feedback-format-style');
for (const option of stylePicker.querySelectorAll('.ql-picker-item')) {{
  const value = option.getAttribute('data-value');
  const identity = value === '1' ? 'feedback-format-heading-1'
    : value === '2' ? 'feedback-format-heading-2' : 'feedback-format-normal';
  option.id = identity;
}}
identify('.ql-tooltip input[data-link]', 'feedback-link-target');
identify('.ql-tooltip', 'feedback-link-editor');
identify('.ql-tooltip .ql-preview', 'feedback-link-preview');
identify('.ql-tooltip .ql-action', 'feedback-link-save');
identify('.ql-tooltip .ql-remove', 'feedback-link-remove');
// WebKit does not expose all native block meanings in a contenteditable.
// Derive ARIA from the current content, including undo and restored deltas.
// Never change the editor role or Quill's document model.
let semanticNodes = new Set();
let translatedLabels = {{}};
function updateStyleLabel() {{
  if (!translatedLabels['feedback-format-normal']) return;
  const picker = document.getElementById('feedback-format-style');
  const selected = picker.getAttribute('data-value');
  picker.setAttribute('data-label', selected === '1'
    ? translatedLabels['feedback-format-heading-1'] : selected === '2'
    ? translatedLabels['feedback-format-heading-2'] : translatedLabels['feedback-format-normal']);
}}
new MutationObserver(updateStyleLabel).observe(
  document.getElementById('feedback-format-style'), {{attributes: true, attributeFilter: ['data-value']}});
function updateLinkAction() {{
  const tooltip = document.getElementById('feedback-link-editor');
  const action = document.getElementById('feedback-link-save');
  const label = tooltip.classList.contains('ql-editing')
    ? translatedLabels['feedback-link-save'] : translatedLabels['edit-link'];
  if (!label) return;
  action.setAttribute('aria-label', label);
  action.setAttribute('title', label);
  action.setAttribute('data-label', label);
}}
new MutationObserver(updateLinkAction).observe(
  document.getElementById('feedback-link-editor'), {{attributes: true, attributeFilter: ['class']}});
function exposeBlockSemantics() {{
  const current = new Map();
  for (const heading of editor.querySelectorAll('h1, h2'))
    current.set(heading, {{role: 'heading', 'aria-level': heading.tagName.slice(1)}});
  for (const quote of editor.querySelectorAll('blockquote'))
    current.set(quote, {{role: 'blockquote'}});
  for (const block of editor.querySelectorAll('.ql-code-block-container'))
    current.set(block, {{role: 'code', 'aria-roledescription': translatedLabels['code-block']}});
  for (const item of editor.querySelectorAll('li[data-list]'))
    current.set(item, {{'aria-roledescription': item.getAttribute('data-list') === 'ordered'
      ? translatedLabels['numbered-list-item']
      : translatedLabels['bulleted-list-item']}});
  for (const node of new Set([...semanticNodes, ...current.keys()])) {{
    const attributes = current.get(node) || {{}};
    for (const key of ['role', 'aria-level', 'aria-roledescription']) {{
      if (key in attributes) {{
        if (node.getAttribute(key) !== attributes[key])
          node.setAttribute(key, attributes[key]);
      }} else if (node.hasAttribute(key)) {{
        node.removeAttribute(key);
      }}
    }}
  }}
  semanticNodes = new Set(current.keys());
}}
let draftRevision = 0;
function updateWatermark() {{
  // Quill's ql-blank excludes empty headings, lists, quotes and code blocks.
  // The sole terminal newline means no draft content, regardless of format.
  editor.classList.toggle('feedback-empty', quill.getLength() === 1);
}}
function publish() {{
  updateWatermark();
  exposeBlockSemantics();
  const text = quill.getText().replace(/\\n$/, '');
  bridge.postMessage(JSON.stringify({{
    type: 'change', text, revision: ++draftRevision,
    html: quill.getSemanticHTML(),
    delta: JSON.stringify(quill.getContents()),
  }}));
}}
quill.on('text-change', publish);
window.feedbackEditor = {{
  labels(labels) {{
    translatedLabels = labels;
    document.documentElement.setAttribute('dir', labels.direction);
    document.documentElement.setAttribute('lang', labels.language);
    for (const [id, label] of Object.entries(labels)) {{
      const node = document.getElementById(id);
      if (!node) continue;
      node.setAttribute('aria-label', label);
      node.setAttribute('title', label);
      node.setAttribute('data-label', label);
    }}
    editor.setAttribute('data-placeholder', labels.placeholder);
    updateWatermark();
    updateStyleLabel();
    updateLinkAction();
    exposeBlockSemantics();
  }},
  clear() {{ quill.setContents([]); publish(); }},
  focus() {{ quill.focus(); }},
  restore(delta) {{ quill.setContents(delta); publish(); }},
}};
window.feedbackEditor.labels({initial_labels});
{ui_js}
bridge.postMessage(JSON.stringify({{ type: 'ready' }}));
</script></body></html>"""
