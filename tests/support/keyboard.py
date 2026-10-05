"""Ordinary keyboard input bound to a freshly resolved public automation ID."""

import time


def deliver_allowance(ui, send, *, child=None):
    """Daily dropdown exception: freshly owned scope and unique keyboard focus."""
    from tests.e2e.accessible_ui import CHILD, NAMED_CUSTOM_CHILDREN
    if ui.input_uncertain:
        raise AssertionError('Keyboard input is uncertain')
    ui.invalidate_observation()
    ui.allowance_keyboard_recipient(NAMED_CUSTOM_CHILDREN.get(child, child) or CHILD)
    ui.input_uncertain = True
    send()
    ui.input_uncertain = False


def raw_allowance_key(key):
    from dogtail import rawinput
    rawinput.keyCombo(key)


def raw_allowance_text(text):
    from dogtail import rawinput
    for character in text:
        rawinput.pressKey(character)
        time.sleep(.02)


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
    from dogtail import rawinput
    deliver(ui, identity, state, lambda: rawinput.pressKey(key))


def key_combo(ui, identity, keys, *, state, post_delay=None):
    """Press one guarded chord; a shorter pause requires caller result polling."""
    if post_delay is not None and (type(post_delay) not in (int, float)
                                  or not 0 <= post_delay <= 0.25):
        raise ValueError('Keyboard post-action delay must be between 0 and 0.25 seconds')
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
