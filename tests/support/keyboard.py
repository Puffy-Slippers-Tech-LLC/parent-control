"""Ordinary keyboard input bound to a freshly resolved public automation ID."""

import time


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


def key_combo(ui, identity, keys, *, state):
    """Press one ordinary chord after a fresh ID and recipient-state check."""
    from dogtail import rawinput
    deliver(ui, identity, state, lambda: rawinput.keyCombo(keys))


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
