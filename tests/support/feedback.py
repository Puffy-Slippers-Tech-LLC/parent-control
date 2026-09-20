"""Shared ID-only interactions with the real feedback editor."""


EDITOR_ID = "feedback-editor-input"
DIALOG_CLOSE_IDS = {
    "feedback-privacy-dialog": "feedback-privacy-close",
    "feedback-success-dialog": "feedback-success-close",
}


def feedback_editor(ui, wait_for_accessible_state):
    wait_for_accessible_state(lambda: ui.find(EDITOR_ID) is not None,
                              "feedback editor publishes its public ID")
    return EDITOR_ID


def type_feedback(ui, value, wait_for_accessible_state):
    from dogtail import rawinput
    ui.focus(EDITOR_ID)
    rawinput.typeText(value)
    wait_for_accessible_state(
        lambda: ui.content(EDITOR_ID).strip() == value,
        "rich feedback editor receives typed text",
    )


def dismiss_feedback_dialog(ui, wait_for_accessible_state, identity, *, within):
    """Close a known feedback modal through its stable public response ID."""
    wait_for_accessible_state(lambda: ui.showing(identity), identity + " opens")
    ui.activate(DIALOG_CLOSE_IDS[identity])
    wait_for_accessible_state(lambda: ui.absent(identity, within=within), identity + " closes")
