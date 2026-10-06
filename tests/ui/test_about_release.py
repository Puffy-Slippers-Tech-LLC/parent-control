"""Visible release notices on each production GTK About surface."""

import json

import pytest

from tests.support.paths import ROOT


pytestmark = pytest.mark.ui


@pytest.mark.parametrize("launcher,menu", (
    ("parent_component_preview", "parent-menu-button"),
    ("kiosk_preview", "kiosk-menu-button"),
    ("child_overlay_preview", "kiosk-menu-button"),
), ids=("parent", "kiosk", "child-overlay"))
def test_about_displays_release_notices(
        launch_ui, automation, wait_for_accessible_state, tmp_path, launcher, menu):
    launch_ui(launcher, wait_for_application=False)
    ui = automation
    wait_for_accessible_state(lambda: ui.find(menu) is not None,
                              "application menu publishes its ID")
    if launcher == 'parent_component_preview':
        assert ui.reader.check_parent_help()
    ui.setValue(menu, 'about')
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
        # Link accessible names include the field label; check displayed copy.
        assert ui.getText(identity) == text
    if launcher != 'kiosk_preview':
        for field in ('website', 'privacy', 'support', 'license', 'legal-notices'):
            assert ui.reader.clickable_link('about-' + field + '-value')
    (tmp_path / f"{launcher}-about-release.json").write_text(
        json.dumps(expected, ensure_ascii=False, indent=2), encoding="utf-8",
    )
