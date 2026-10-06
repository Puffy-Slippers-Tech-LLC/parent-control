"""Finite legacy edit recipes over Application UI, plus external keyboard input.

Product editing never sends native keys. The bounded legacy chord vocabulary is
translated into the same public text, selection and action operations used by
installed helpers. External provider and fixture recipients retain native input.
"""

import time

from common.oh_no_parent_control_ui.application_ui_client import UIClientError
from tests.support.application_ui import is_product_node, utf16_index, utf16_length


def _target(ui, identity):
    return ui.id_target(identity) if hasattr(ui, "id_target") else ui.target(identity)


def _product(ui, identity):
    node = _target(ui, identity)
    return node if is_product_node(node) else None


def _input(ui, node, operation, *arguments):
    if ui.input_uncertain:
        raise AssertionError("Application UI input is uncertain")
    reader = getattr(ui, 'reader', ui)
    reader.invalidate_observation()
    try:
        return getattr(node, operation)(*arguments)
    except UIClientError as error:
        ui.input_uncertain = error.uncertain
        raise


def _edit_state(ui, node):
    reader = getattr(ui, 'reader', ui)
    if not hasattr(reader, '_application_edit_state'):
        reader._application_edit_state = {}
    key = (node.client.owner, node.surface_id, node.identity)
    return reader._application_edit_state.setdefault(key, {})


def _selection(node, state):
    value = node.getText()
    if node.identity in ('feedback-editor-input', 'feedback-webview'):
        selection = node.client.getValue('feedback-editor-selection', surface_id=node.surface_id)
        return (value, utf16_index(value, selection['index']),
                utf16_index(value, selection['index'] + selection['length']))
    start, end = state.get('selection', (len(value), len(value)))
    return value, min(start, len(value)), min(end, len(value))


def _select(ui, node, state, text, start, end):
    if node.identity in ('feedback-editor-input', 'feedback-webview'):
        selection = node.client.getElementById('feedback-editor-selection', surface_id=node.surface_id)
        _input(ui, selection, 'setValue', {'index': utf16_length(text[:start]),
                                          'length': utf16_length(text[start:end])})
    else:
        # Native entry selection is not part of Application UI. Keep only the
        # recipe's intended replacement range; acceptance never reads it back
        # as widget focus, caret or selection state.
        state['selection'] = (start, end)


def _insert(ui, node, text):
    state = _edit_state(ui, node)
    if 'unicode' in state:
        state['unicode'] += text
        return
    if node.identity in ('feedback-editor-input', 'feedback-webview'):
        insert = node.client.getElementById('feedback-editor-insert', surface_id=node.surface_id)
        _input(ui, insert, 'setText', text)
        return
    value, start, end = _selection(node, state)
    commit = node.identity == 'parent-custom-daily-limit' and text.endswith(('\n', '\t'))
    text = text[:-1] if commit else text
    _input(ui, node, 'setText', value[:start] + text + value[end:])
    state['selection'] = (start + len(text), start + len(text))
    if commit:
        _input(ui, _target(ui, node.identity), 'activate')


def _product_key(ui, node, key):
    state = _edit_state(ui, node)
    if key in ('<Control>z', '<Control><Shift>z'):
        identity = 'feedback-redo' if '<Shift>' in key else 'feedback-undo'
        _input(ui, node.client.getElementById(identity, surface_id=node.surface_id), 'activate')
    elif key == '<Control><Shift>u':
        state['unicode'] = ''
    elif key in ('Return', 'Enter') and 'unicode' in state:
        scalar = state.pop('unicode')
        _insert(ui, node, chr(int(scalar, 16)))
    elif key in ('<Alt>F4', 'Escape'):
        if node.identity == 'language-search' and key == 'Escape':
            _input(ui, node, 'setText', '')
        elif node.identity.startswith('parent-filter-'):
            # Composite filter values do not require popup dismissal.
            return
        else:
            surface = node.client.getElementById(node.surface_id, surface_id=node.surface_id)
            _input(ui, surface, 'close')
    elif key in ('<Control>Tab', 'Tab', '<Shift>Tab'):
        # Every later API operation names its own recipient. Focus navigation
        # was preparation only and carries no independent acceptance claim.
        if node.identity == 'parent-custom-daily-limit':
            _input(ui, node, 'activate')
    elif key in ('Return', 'Enter', 'space') and node.identity not in (
            'feedback-editor-input', 'feedback-webview'):
        _input(ui, node, 'activate')
    elif key == 'Return':
        _insert(ui, node, '\n')
    else:
        value, start, end = _selection(node, state)
        if key == '<Control>a':
            _select(ui, node, state, value, 0, len(value))
        elif key == '<Control>Home':
            _select(ui, node, state, value, 0, 0)
        elif key == '<Control>End':
            _select(ui, node, state, value, len(value), len(value))
        elif key == '<Control><Shift>End':
            _select(ui, node, state, value, start, len(value))
        elif key == 'Home':
            index = value.rfind('\n', 0, end) + 1
            _select(ui, node, state, value, index, index)
        elif key == 'Right':
            index = end if start != end else min(len(value), end + 1)
            _select(ui, node, state, value, index, index)
        elif key == 'Left':
            index = start if start != end else max(0, start - 1)
            _select(ui, node, state, value, index, index)
        elif key == '<Shift>Right':
            _select(ui, node, state, value, start, min(len(value), end + 1))
        elif key == 'BackSpace':
            if start == end:
                _select(ui, node, state, value, max(0, start - 1), end)
            _insert(ui, node, '')
        else:
            raise AssertionError('Unsupported Application UI edit recipe')


def recipient(ui, identity, state):
    """Reacquire ``identity`` and require its declared input-recipient state."""
    node = ui.id_target(identity) if hasattr(ui, "id_target") else ui.target(identity)
    if not node.get_state_set().contains(state):
        raise AssertionError(f"Keyboard recipient {identity!r} lacks {state!s}")
    return node


def deliver(ui, identity, state, send):
    """Deliver once; a backend exception permanently leaves input uncertain."""
    if ui.input_uncertain:
        raise AssertionError("Keyboard input is uncertain")
    recipient(ui, identity, state)
    ui.input_uncertain = True
    send()
    ui.input_uncertain = False


def press_key(ui, identity, key, *, state):
    """Press one ordinary key after a fresh ID and recipient-state check."""
    node = _product(ui, identity)
    if node is not None:
        return _product_key(ui, node, key)
    from dogtail import rawinput
    deliver(ui, identity, state, lambda: rawinput.pressKey(key))


def key_combo(ui, identity, keys, *, state, post_delay=None):
    """Press one guarded chord; a shorter pause requires caller result polling."""
    if post_delay is not None and (type(post_delay) not in (int, float)
                                  or not 0 <= post_delay <= 0.25):
        raise ValueError('Keyboard post-action delay must be between 0 and 0.25 seconds')
    node = _product(ui, identity)
    if node is not None:
        return _product_key(ui, node, keys)
    from dogtail import rawinput
    def send():
        if post_delay is None:
            rawinput.keyCombo(keys)
            return
        from dogtail.config import config
        previous = config.action_delay
        try:
            config.action_delay = post_delay
            rawinput.keyCombo(keys)
        finally:
            config.action_delay = previous
    deliver(ui, identity, state, send)


def repeat_cursor(ui, identity, keys, count):
    """One bounded cursor movement in an identified, focused text recipient.

    Only arrows are allowed: no focus, dialog or application transition can be
    requested inside the batch. The caller must independently verify its exact
    selection/caret result before any subsequent editing action.
    """
    if keys not in ('Right', 'Left', '<Shift>Right') or type(count) is not int or not 0 <= count <= 128:
        raise ValueError('Invalid bounded cursor movement')
    node = _product(ui, identity)
    if node is not None:
        state = _edit_state(ui, node)
        value, start, end = _selection(node, state)
        if keys == '<Shift>Right':
            return _select(ui, node, state, value, start, min(len(value), end + count))
        index = min(len(value), end + count) if keys == 'Right' else max(0, start - count)
        return _select(ui, node, state, value, index, index)
    from dogtail import rawinput
    from dogtail.config import config
    def send():
        # Dogtail defaults to a one-second post-action pause. Cursor movement
        # needs only bounded event pacing; exact readback remains the result gate.
        previous = config.action_delay
        try:
            config.action_delay = 0.05
            for _ in range(count):
                rawinput.keyCombo(keys)
        finally:
            config.action_delay = previous
    deliver(ui, identity, ui.api.StateType.FOCUSED, send)


def type_text(ui, identity, value, *, interval=0):
    """Type nonsecret text once into the freshly ID-resolved focused control."""
    if type(interval) not in (int, float) or not 0 <= interval <= 0.25:
        raise ValueError('Keyboard typing interval must be between 0 and 0.25 seconds')
    node = _product(ui, identity)
    if node is not None:
        return _insert(ui, node, value)
    from dogtail import rawinput
    def send():
        if not interval:
            rawinput.typeText(value)
            return
        # The hermetic Mutter backend accepts but ignores Dogtail's delay
        # argument. Bound sustained input explicitly to avoid losing key events.
        for character in value:
            rawinput.pressKey(character)
            time.sleep(interval)
    deliver(ui, identity, ui.api.StateType.FOCUSED, send)
