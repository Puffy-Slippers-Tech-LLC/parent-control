// The application-owned editor API. The host accepts data, never caller scripts.
// Quill's public user-source edits feed the ordinary text-change/draft bridge.
(() => {
  const formats = {
    'feedback-format-bold': ['bold', true],
    'feedback-format-italic': ['italic', true],
    'feedback-format-underline': ['underline', true],
    'feedback-format-strike': ['strike', true],
    'feedback-format-ordered': ['list', 'ordered'],
    'feedback-format-bulleted': ['list', 'bullet'],
    'feedback-format-quote': ['blockquote', true],
    'feedback-format-code': ['code-block', true],
  };
  const styles = {
    'feedback-format-normal': 'normal',
    'feedback-format-heading-1': 'heading-1',
    'feedback-format-heading-2': 'heading-2',
  };
  const known = new Set([
    'feedback-webview', 'feedback-editor-selection', 'feedback-editor-input',
    'feedback-format-toolbar', 'feedback-format-style', ...Object.keys(styles),
    ...Object.keys(formats), 'feedback-format-link', 'feedback-format-attachment',
    'feedback-format-clear', 'feedback-link-target', 'feedback-link-editor',
    'feedback-link-preview', 'feedback-link-save', 'feedback-link-remove',
  ]);
  let lastSelection = {index: 0, length: 0};
  quill.on('selection-change', range => {
    if (range) lastSelection = {index: range.index, length: range.length};
  });
  const selection = () => {
    const current = quill.getSelection() || lastSelection;
    const end = quill.getLength() - 1;
    const index = Math.min(current.index, end);
    return {index, length: Math.min(current.length, end - index)};
  };
  const currentFormats = () => quill.getFormat(selection());
  const restoreSelection = () => {
    const range = selection();
    quill.setSelection(range.index, range.length, 'silent');
  };
  const currentStyle = () => {
    const header = currentFormats().header;
    return header === 1 ? 'heading-1' : header === 2 ? 'heading-2' : 'normal';
  };
  const plainText = () => quill.getText().replace(/\n$/, '');
  const draft = () => ({type: 'change', text: plainText(), revision: draftRevision,
    html: quill.getSemanticHTML(), delta: JSON.stringify(quill.getContents())});

  function target(id) {
    if (!known.has(id)) throw new Error('Unknown editor control');
    if (id === 'feedback-webview' || id === 'feedback-editor-selection') return editor;
    const nodes = document.querySelectorAll(`[id="${id}"]`);
    if (nodes.length !== 1) throw new Error('Missing or ambiguous editor control');
    return nodes[0];
  }
  function available(node) {
    if (node.id in styles) node = target('feedback-format-style');
    for (let owner = node; owner; owner = owner.parentElement) {
      if (owner.hidden || owner.classList.contains('ql-hidden') ||
          owner.getAttribute('aria-hidden') === 'true') return false;
    }
    // Style items are logical alternatives of the available style selector;
    // callers need not open Quill's transient popup to choose one.
    return true;
  }
  function value(id, node) {
    if (id === 'feedback-editor-selection') return selection();
    if (id === 'feedback-editor-input' || id === 'feedback-webview') return plainText();
    if (id === 'feedback-format-style') return currentStyle();
    if (id in styles) return currentStyle() === styles[id];
    if (id in formats) {
      const [format, enabled] = formats[id];
      return currentFormats()[format] === enabled;
    }
    if (id === 'feedback-link-target') return node.value;
    return null;
  }
  function text(id, node) {
    return ['feedback-editor-input', 'feedback-webview', 'feedback-link-target'].includes(id)
      ? value(id, node) : node.getAttribute('aria-label') || node.textContent || '';
  }
  function capabilities(id) {
    const ops = ['getElementById', 'getText', 'getValue'];
    if (['feedback-editor-input', 'feedback-webview', 'feedback-link-target'].includes(id))
      ops.push('setText', 'setValue');
    if (id === 'feedback-editor-selection' || id === 'feedback-format-style' || id in formats)
      ops.push('setValue');
    if (id === 'feedback-format-style') ops.push('getChoices');
    if (id in formats || id in styles || [
      'feedback-format-style', 'feedback-format-link', 'feedback-format-attachment',
      'feedback-format-clear', 'feedback-link-save', 'feedback-link-remove',
    ].includes(id)) ops.push('activate');
    return ops;
  }
  function setValue(id, node, next) {
    if (id === 'feedback-editor-input' || id === 'feedback-webview') {
      if (typeof next !== 'string') throw new Error('Text must be a string');
      quill.setText(next, 'user');
    } else if (id === 'feedback-link-target') {
      if (typeof next !== 'string') throw new Error('Text must be a string');
      node.value = next;
      node.dispatchEvent(new Event('input', {bubbles: true}));
      node.dispatchEvent(new Event('change', {bubbles: true}));
    } else if (id === 'feedback-editor-selection') {
      if (!next || typeof next !== 'object' || Object.keys(next).sort().join(',') !== 'index,length' ||
          !Number.isInteger(next.index) || !Number.isInteger(next.length) ||
          next.index < 0 || next.length < 0 || next.index + next.length > quill.getLength() - 1)
        throw new Error('Selection must be a valid index and length');
      quill.setSelection(next.index, next.length, 'user');
    } else if (id === 'feedback-format-style') {
      const choice = Object.keys(styles).find(key => styles[key] === next);
      if (!choice) throw new Error('Unknown text style');
      restoreSelection();
      target(choice).click();
    } else if (id in formats) {
      if (typeof next !== 'boolean') throw new Error('Format value must be boolean');
      if (value(id, node) !== next) {
        restoreSelection();
        node.click();
      }
    } else {
      throw new Error('Control value is read only');
    }
  }
  window.feedbackEditor.ui = request => {
    try {
      const {element_id: id, operation} = request;
      const node = target(id);
      const visible = available(node);
      const enabled = visible && quill.isEnabled() && !node.disabled;
      const operations = capabilities(id);
      if (!operations.includes(operation)) throw new Error('Unsupported editor operation');
      let result;
      if (operation === 'getElementById') {
        result = {id, visible, enabled, operations, value: value(id, node),
          text: text(id, node)};
      } else if (operation === 'getValue') {
        result = value(id, node);
      } else if (operation === 'getText') {
        result = text(id, node);
      } else if (operation === 'getChoices') {
        result = Object.values(styles);
      } else {
        if (!enabled) throw new Error('Editor control is unavailable');
        if (operation === 'activate') {
          if (id.startsWith('feedback-format-')) restoreSelection();
          node.click();
        }
        else setValue(id, node, operation === 'setText' ? request.text : request.value);
        publish();
        result = null;
      }
      return {result, draft: draft()};
    } catch (_error) {
      return {error: 'Unsupported, invalid or unavailable editor operation'};
    }
  };
})();
