"""Visible release notices on each production GTK About surface."""

import json

import pytest

from tests.support.paths import ROOT


pytestmark = pytest.mark.ui


@pytest.mark.parametrize("launcher,menu", (
    ("parent_component_preview", "Parent app menu"),
    ("kiosk_preview", "Request-screen menu"),
    ("child_overlay_preview", "Request-screen menu"),
), ids=("parent", "kiosk", "child-overlay"))
def test_about_displays_release_notices(
        launch_ui, wait_for_accessible_node, capture_ui_snapshot, launcher, menu):
    application, _log = launch_ui(launcher)
    find = wait_for_accessible_node
    assert find(application, menu, "toggle button").do_action(0)
    assert find(application, "About", "button").do_action(0)
    version = json.loads((ROOT / "data/app.json").read_text())["version"]
    for text in (
        f"Version {version}",
        "License",
        "GNU General Public License v3.0",
        "Legal notices",
        "Malcontent integration and bundled-font notices",
        "Uses the separately installed Malcontent parental-controls service "
        "through public system APIs. Not affiliated with or endorsed by the "
        "Malcontent authors or GNOME.",
        "© 2026 Puffy Slippers Tech LLC\nGPL-3.0-only · No warranty.",
    ):
        assert find(application, text).showing
    capture_ui_snapshot(application, f"{launcher}-about-release")
