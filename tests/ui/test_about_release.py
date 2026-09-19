"""Visible release notices on each production GTK About surface."""

import json

import pytest

from tests.support.paths import ROOT


pytestmark = pytest.mark.ui


@pytest.mark.parametrize("launcher,menu,about", (
    ("parent_component_preview", "parent-menu-button", "parent-menu-about"),
    ("kiosk_preview", "kiosk-menu-button", "kiosk-menu-item-about"),
    ("child_overlay_preview", "kiosk-menu-button", "kiosk-menu-item-about"),
), ids=("parent", "kiosk", "child-overlay"))
def test_about_displays_release_notices(
        launch_ui, automation, wait_for_accessible_state, tmp_path, launcher, menu, about):
    launch_ui(launcher, wait_for_application=False)
    ui = automation
    wait_for_accessible_state(lambda: ui.find(menu) is not None,
                              "application menu publishes its ID")
    ui.activate(menu, action_name="menu.popup")
    wait_for_accessible_state(lambda: ui.find(about) is not None,
                              "About menu item publishes its ID")
    ui.activate(about)
    wait_for_accessible_state(lambda: ui.find("about-dialog") is not None,
                              "About dialog publishes its ID")
    version = json.loads((ROOT / "data/app.json").read_text())["version"]
    expected = {
        "about-version": f"Version {version}",
        "about-license-label": "License",
        "about-license-value": "GNU General Public License v3.0",
        "about-legal-notices-label": "Legal notices",
        "about-legal-notices-value": "Malcontent integration and bundled-font notices",
        "about-integration-notice": "Uses the separately installed Malcontent parental-controls service "
        "through public system APIs. Not affiliated with or endorsed by the "
        "Malcontent authors or GNOME.",
        "about-copyright": "© 2026 Puffy Slippers Tech LLC\nGPL-3.0-only · No warranty.",
    }
    for identity, text in expected.items():
        assert ui.text(identity) == text
        ui.reveal(identity)
    (tmp_path / f"{launcher}-about-release.json").write_text(
        json.dumps(expected, ensure_ascii=False, indent=2), encoding="utf-8",
    )
