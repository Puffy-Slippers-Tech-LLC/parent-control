"""Shared semantic interactions with the real feedback editor."""


def feedback_editor(application, wait_for_accessible_node):
    section = wait_for_accessible_node(application, "Your feedback", "section")
    return section.child(role_name="entry")


def type_feedback(editor, value, wait_for_accessible_state):
    from dogtail import rawinput
    assert editor.grab_focus()
    rawinput.typeText(value)
    wait_for_accessible_state(
        lambda: editor.text.strip() == value,
        "rich feedback editor receives typed text",
    )
