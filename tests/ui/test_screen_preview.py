"""Preview-screen behavior through public IDs and semantic results."""

import pytest

from kiosk.oh_no_parent_control_kiosk.preview_screen import Screen
from tests.support.automation_ids import audit_product_controls


pytestmark = pytest.mark.ui


@pytest.mark.parametrize("value", (
    Screen(800, 600, 100),
    Screen(1920, 1200, 125),
    Screen(3840, 2160, 200),
))
def test_screen_choice_round_trips(value):
    assert Screen.decode(value.encode()) == value


@pytest.mark.parametrize("arguments,message", (
    ((479, 1080, 100), "Enter whole pixel dimensions"),
    ((1920, 1080, 110), "Choose a display scale"),
    ((7680, 7680, 100), "Enter whole pixel dimensions"),
))
def test_screen_choice_rejects_unsupported_values(arguments, message):
    with pytest.raises(ValueError, match=message):
        Screen(*arguments)


@pytest.mark.parametrize("launcher", ("kiosk_preview", "child_overlay_preview"))
def test_screen_dialog_reports_invalid_custom_dimensions_and_recovers(
        launch_ui, automation, wait_for_accessible_state, launcher):
    from tests.support.keyboard import key_combo, type_text

    launch_ui(launcher, wait_for_application=False)
    ui = automation
    wait_for_accessible_state(lambda: ui.find("kiosk-menu-button") is not None,
                              "request screen publishes its menu ID")
    ui.activate("kiosk-menu-button", action_name="menu.popup")
    wait_for_accessible_state(lambda: ui.showing("kiosk-menu-item-change-screens"),
                              "screen action opens")
    ui.activate("kiosk-menu-item-change-screens")
    wait_for_accessible_state(lambda: ui.showing("preview-screen-dialog"),
                              "screen dialog opens")
    ui.activate("preview-screen-scale", action_name="menu.popup")
    wait_for_accessible_state(lambda: ui.showing("preview-screen-scale-125"),
                              "scale choices publish stable IDs")
    ui.activate("preview-screen-scale-125")
    wait_for_accessible_state(
        lambda: "125%" in ui.target("preview-screen-scale").get_description(),
        "selected scale is readable",
    )
    audit_product_controls(ui, "preview-screen-dialog")
    ui.activate("preview-screen-resolution-custom", action_name="row.activate")
    wait_for_accessible_state(lambda: ui.showing("preview-screen-width"),
                              "custom resolution reveals its dimension fields")
    ui.focus("preview-screen-width")
    key_combo(ui, "preview-screen-width", "<Control>a", state=ui.api.StateType.FOCUSED)
    type_text(ui, "preview-screen-width", "479")
    ui.activate("preview-screen-save")
    wait_for_accessible_state(
        lambda: (status := ui.find("preview-screen-status")) is not None
        and status.get_name().startswith(
            "Enter whole pixel dimensions from 480 to 7680"),
        "invalid dimensions are explained",
    )
    assert ui.state("preview-screen-save", ui.api.StateType.SENSITIVE)
    assert ui.state("preview-screen-cancel", ui.api.StateType.SENSITIVE)
    ui.activate("preview-screen-cancel")
    wait_for_accessible_state(lambda: ui.absent("preview-screen-dialog", within="kiosk-request-window"),
                              "screen dialog closes")
