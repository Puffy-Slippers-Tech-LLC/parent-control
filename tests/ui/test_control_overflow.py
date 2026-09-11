"""Pointer and overflow coverage for menus and shared auxiliary windows."""

import json
from pathlib import Path
import tempfile

import pytest
from tests.support.events import read_events

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


@pytest.mark.parametrize("dpi_scale,scroll_page", ((1, False), (1.25, False), (1.25, True)),
                         ids=("normal", "fractional", "fractional-scrolled"))
def test_parent_allowance_popup_stays_attached(
        launch_ui, request_display_scale, dpi_scale, scroll_page, click_control,
        wait_for_accessible_node, wait_for_accessible_state):
    directory = Path(tempfile.mkdtemp(prefix="onpc-parent-allowance-"))
    application, log = launch_ui("parent_component_preview", environment_overrides={
        "ONPC_PARENT_ALLOWANCE_LAYOUT_DIRECTORY": str(directory),
        "ONPC_PARENT_COMPONENT_EVENTS_PATH": str(directory / "events.jsonl"),
        "GSK_RENDERER": "gl",
    })
    window = application.child(role_name="frame", retry=False)
    display_size = (round(1280 / dpi_scale), round(800 / dpi_scale))
    if window.extents[2:] != display_size:
        assert wait_for_accessible_node(application, "Maximize", "button").do_action(0)
    wait_for_accessible_state(
        lambda: window.extents[2:] == display_size, "maximized parent window",
    )
    allowance = wait_for_accessible_node(application, "Daily time allowance", "button")
    wait_for_accessible_state(lambda: allowance.sensitive, "loaded daily allowance")
    if scroll_page:
        scrollbar = wait_for_accessible_node(application, "", "scroll bar")
        original_y = allowance.extents[1]
        scrollbar.value = scrollbar.max_value
        wait_for_accessible_state(
            lambda: allowance.extents[1] < original_y, "page scroll moves the allowance button",
        )
    click_control(allowance)
    custom = wait_for_accessible_node(application, "Custom amount", "button")
    wait_for_accessible_state(lambda: custom.showing, "allowance menu opens")

    def assert_attached(index):
        path = directory / f"layout-{index}.json"
        wait_for_accessible_state(lambda: path.exists(), "popup placement evidence")
        record = json.loads(path.read_text())
        print("Allowance popup:", record, "scale:", dpi_scale, "evidence:", directory)
        _x, button_y, _w, button_height = record["button"]
        menu_x, menu_y, menu_width, menu_height = record["menu"]
        # Use the measured content edge so shadows do not count as a gap.
        # Gravity identifies the edge carrying the arrow; merely checking
        # proximity accepts the regression with an arrow on the opposite edge.
        if record["surface_anchor"] == "north":
            assert record["rect_anchor"] == "south", record
            gap = menu_y - button_y - button_height
        else:
            assert record["surface_anchor"] == "south", record
            assert record["rect_anchor"] == "north", record
            gap = button_y - menu_y - menu_height
        assert 0 <= gap <= 32, record
        assert 0 <= menu_x < menu_x + menu_width <= display_size[0], record
        assert 0 <= menu_y < menu_y + menu_height <= display_size[1], record

    assert_attached(0)
    # Scrolling must reach the final preset while the fixed custom action
    # remains available. Selecting it still uses the normal save path.
    preset = wait_for_accessible_node(application, "23.5 hours", "button")
    preset_scroller = preset.parent
    while preset_scroller.roleName != "scroll pane":
        preset_scroller = preset_scroller.parent
    scrollbar = preset_scroller.child(role_name="scroll bar", retry=False)
    scrollbar.value = scrollbar.max_value
    wait_for_accessible_state(lambda: preset.showing, "last allowance preset scrolls into view")
    assert custom.showing
    assert preset.do_action(0)
    wait_for_accessible_state(
        lambda: any(event["event"] == "set_parent_control"
                    and event["daily_limit_minutes"] == 1410
                    for event in read_events(directory / "events.jsonl")),
        "last allowance preset saves",
    )
    wait_for_accessible_state(lambda: allowance.sensitive, "allowance save completes")
    if scroll_page:
        # Reopening after moving the page must use the button's new position.
        page_scrollbar = wait_for_accessible_node(application, "", "scroll bar")
        original_y = allowance.extents[1]
        page_scrollbar.value = 0
        wait_for_accessible_state(
            lambda: allowance.extents[1] > original_y, "page scroll returns to the top",
        )
    assert allowance.child(role_name="toggle button", retry=False).do_action(0)
    assert_attached(1)
    custom = wait_for_accessible_node(application, "Custom amount", "button")
    assert custom.do_action(0)
    custom_entry = wait_for_accessible_node(application, "Custom daily allowance", "text")
    wait_for_accessible_state(lambda: custom_entry.showing, "custom allowance editor opens")
    assert "Gtk-CRITICAL" not in log.read_text()


@pytest.mark.parametrize("dpi_scale", (1, 1.25))
def test_parent_expanded_legend_follows_content_height(
        launch_ui, request_display_scale, dpi_scale,
        wait_for_accessible_node, wait_for_accessible_state):
    directory = Path(tempfile.mkdtemp(prefix="onpc-parent-legend-"))
    application, log = launch_ui("parent_component_preview", environment_overrides={
        "ONPC_PARENT_LEGEND_LAYOUT_DIRECTORY": str(directory),
        "GSK_RENDERER": "gl",
    })
    window = application.child(role_name="frame", retry=False)
    display_size = (round(1280 / dpi_scale), round(800 / dpi_scale))
    if window.extents[2:] != display_size:
        assert wait_for_accessible_node(application, "Maximize", "button").do_action(0)
    wait_for_accessible_state(
        lambda: window.extents[2:] == display_size, "maximized parent window",
    )
    assert wait_for_accessible_node(application, "App Limits", "page tab").do_action(0)
    legend = wait_for_accessible_node(application, "Legend", "label").parent
    while legend.roleName != "toggle button":
        legend = legend.parent
    assert legend.do_action(0)
    path = directory / "layout.json"
    wait_for_accessible_state(lambda: path.exists(), "expanded legend layout evidence")
    record = json.loads(path.read_text())
    widgets = record["widgets"]
    card_x, card_y, card_width, card_height = widgets[0]["bounds"]
    descriptions = [widget for widget in widgets
                    if "policy-legend-description" in widget["classes"]]
    assert len(descriptions) == 5
    content_bottom = max(widget["bounds"][1] + widget["bounds"][3]
                         for widget in descriptions)
    bottom_gap = card_y + card_height - content_bottom
    print("Legend evidence:", directory, "scale:", dpi_scale,
          "height:", card_height, "bottom gap:", bottom_gap)
    assert 0 <= bottom_gap <= 40, record
    for widget in descriptions:
        x, y, width, height = widget["bounds"]
        assert card_x <= x < x + width <= card_x + card_width, record
        assert card_y <= y < y + height <= card_y + card_height, record
    assert "Gtk-CRITICAL" not in log.read_text()


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
