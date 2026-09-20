"""Ordinary keyboard input bound to a freshly resolved public automation ID."""


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


def type_text(ui, identity, value):
    """Type nonsecret text once into the freshly ID-resolved focused control."""
    from dogtail import rawinput
    deliver(ui, identity, ui.api.StateType.FOCUSED, lambda: rawinput.typeText(value))
