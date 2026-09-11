"""Pointer and overflow coverage for menus and shared auxiliary windows."""

import pytest

# Reuse the existing private-compositor scaling fixture.
from tests.ui.test_request_layout import request_display_scale


pytestmark = pytest.mark.ui


@pytest.fixture
def click_control(hermetic_ui_session, request_display_scale):
    from dogtail.hermetic.mutter import MutterInputBackend
    from tests.ui.mutter_input import click_at

    backend = MutterInputBackend(bus_address=hermetic_ui_session.bus_address)
    backend.connectMonitor()
    try:
        def click(control):
            x, y, width, height = control.extents
            assert width > 0 and height > 0
            click_at(backend, 1, x + width / 2, y + height / 2)
        yield click
    finally:
        backend.disconnect()


def _inside(control, width, height):
    x, y, w, h = control.extents
    return w > 0 and h > 0 and 0 <= x < x + w <= width and 0 <= y < y + h <= height


@pytest.mark.parametrize("dpi_scale", (1, 1.25))
def test_parent_controls_fit_and_filters_open(
        launch_ui, request_display_scale, dpi_scale, click_control,
        wait_for_accessible_node, wait_for_accessible_state):
    application, log = launch_ui("parent_component_preview")
    window = application.child(role_name="frame", retry=False)
    print("Parent bounds:", window.extents, "scale:", dpi_scale)
    wait_for_accessible_state(
        lambda: _inside(window, 1280 / dpi_scale, 800 / dpi_scale),
        "parent window fits the logical display",
    )
    # Wayland accessibility coordinates are local to the window. Maximize
    # before pointer input so they agree with the private monitor coordinates.
    display_size = (round(1280 / dpi_scale), round(800 / dpi_scale))
    if window.extents[2:] != display_size:
        assert wait_for_accessible_node(application, "Maximize", "button").do_action(0)
    wait_for_accessible_state(
        lambda: window.extents[2:] == (round(1280 / dpi_scale), round(800 / dpi_scale)),
        "maximized parent window",
    )
    assert wait_for_accessible_node(application, "App Limits", "page tab").do_action(0)
    search = wait_for_accessible_node(application, "Search installed apps", "entry")
    wait_for_accessible_state(lambda: search.sensitive, "loaded app catalog")
    for label, choice_label in (("Match Rule", "Precise execution path"),
                                ("Access Rule", "Hard Blocked")):
        trigger = wait_for_accessible_node(application, f"Filter {label}", "button")
        click_control(trigger)
        choice = wait_for_accessible_node(application, choice_label, "check box")
        wait_for_accessible_state(lambda: choice.showing, f"{label} choices open")
        checked = choice.checked
        click_control(choice)
        wait_for_accessible_state(lambda: choice.checked != checked, f"{label} filter toggles")
        click_control(choice)
        from dogtail import rawinput
        rawinput.pressKey("Escape")
    assert "Gtk-CRITICAL" not in log.read_text()


@pytest.mark.parametrize("dpi_scale", (1.25,))
def test_feedback_text_style_choices_fit_compact_editor(
        launch_ui, request_display_scale, dpi_scale,
        wait_for_accessible_node, wait_for_accessible_state):
    application, _log = launch_ui("parent_component_preview", environment_overrides={
        "ONPC_PARENT_COMPONENT_SCENARIO": "feedback-attachments",
    })
    assert wait_for_accessible_node(application, "Feedback", "button").do_action(0)
    dialog = wait_for_accessible_node(application, "Send Feedback", "frame")
    style = wait_for_accessible_node(dialog, "Normal", "button")
    assert style.do_action(0)
    heading = wait_for_accessible_node(dialog, "Heading 2", "button")
    document = wait_for_accessible_node(dialog, "", "document web")

    def inside_editor(control):
        x, y, width, height = document.extents
        cx, cy, cw, ch = control.extents
        return cw > 0 and ch > 0 and x <= cx < cx + cw <= x + width and y <= cy < cy + ch <= y + height

    # Focus scrolls the compact options list without moving the toolbar out
    # of the WebView. An unbounded popup instead scrolls the entire document.
    assert heading.grab_focus()
    wait_for_accessible_state(
        lambda: inside_editor(heading) and inside_editor(style),
        "complete text-style choice and toolbar inside the editor",
    )
    assert heading.do_action(0)


@pytest.mark.parametrize("dpi_scale", (1, 1.25))
@pytest.mark.parametrize("launcher,menu", (
    ("parent_component_preview", "Parent app menu"),
    ("kiosk_preview", "Request-screen menu"),
    ("child_overlay_preview", "Request-screen menu"),
))
def test_about_fits_display(
        launch_ui, request_display_scale, dpi_scale, launcher, menu,
        wait_for_accessible_node, wait_for_accessible_state):
    application, log = launch_ui(launcher)
    assert wait_for_accessible_node(application, menu, "toggle button").do_action(0)
    about = wait_for_accessible_node(application, "About", "button")
    wait_for_accessible_state(lambda: about.showing, "About menu item opens")
    assert about.do_action(0)
    dialog = wait_for_accessible_node(application, "About", "frame")
    print("About bounds:", dialog.extents, "scale:", dpi_scale)
    wait_for_accessible_state(
        lambda: _inside(dialog, 1280 / dpi_scale, 800 / dpi_scale),
        "About window fits the logical display",
    )
    copyright = wait_for_accessible_node(
        dialog, "© 2026 Puffy Slippers Tech LLC\nGPL-3.0-only · No warranty.", "label",
    )
    scrollbar = wait_for_accessible_node(dialog, "", "scroll bar")
    scrollbar.value = scrollbar.max_value
    print("About footer bounds:", copyright.extents, "scroll:", scrollbar.value, scrollbar.max_value)
    wait_for_accessible_state(
        lambda: _inside(copyright, *dialog.extents[2:]), "About footer is reachable by scrolling",
    )
    assert "Gtk-CRITICAL" not in log.read_text()


@pytest.mark.parametrize("dpi_scale", (1, 1.25))
@pytest.mark.parametrize("attachments", (False, True), ids=("no-files", "five-files"))
def test_feedback_actions_fit_display(
        launch_ui, request_display_scale, dpi_scale, attachments,
        wait_for_accessible_node, wait_for_accessible_state):
    application, log = launch_ui("parent_component_preview", environment_overrides={
        "ONPC_PARENT_COMPONENT_SCENARIO": "feedback-attachments" if attachments else "normal",
    })
    assert wait_for_accessible_node(application, "Feedback", "button").do_action(0)
    dialog = wait_for_accessible_node(application, "Send Feedback", "frame")
    for label in ("Close", "Send Feedback"):
        button = wait_for_accessible_node(dialog, label, "button")
        print("Feedback bounds:", dialog.extents, label, button.extents, "scale:", dpi_scale)
        wait_for_accessible_state(
            lambda: _inside(button, 1280 / dpi_scale, 800 / dpi_scale),
            f"feedback {label} fits the logical display",
        )
    if attachments:
        scrollbar = wait_for_accessible_node(dialog, "", "scroll bar")
        scrollbar.value = scrollbar.max_value
        remove = wait_for_accessible_node(dialog, "Remove sample-4.txt", "button")
        wait_for_accessible_state(
            lambda: _inside(remove, *dialog.extents[2:]), "last attachment is reachable",
        )
    assert wait_for_accessible_node(dialog, "Close", "button").do_action(0)
    wait_for_accessible_state(
        lambda: not application.is_child("Send Feedback", role_name="frame", retry=False),
        "feedback closes",
    )
    assert "Gtk-CRITICAL" not in log.read_text()
