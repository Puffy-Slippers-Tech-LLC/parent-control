"""Tests for intrinsic-size About dialog branding."""

from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[2]


class AboutDialogTests(unittest.TestCase):
    def test_gtk_about_logo_uses_its_intrinsic_size(self):
        source = (ROOT / "common/oh_no_parent_control_ui/about.py").read_text(
            encoding="utf-8")

        self.assertIn('Gtk.Picture.new_for_filename(str(branding_asset_path("app_logo.png")))',
                      source)
        self.assertNotIn("logo.set_size_request(", source)
        self.assertNotIn("logo.set_content_fit(", source)

    def test_child_session_uses_the_shared_gtk_about_dialog(self):
        stylesheet = (ROOT / "child/stylesheet.css").read_text(encoding="utf-8")
        kiosk = (ROOT / "kiosk/oh_no_parent_control_kiosk/main.py").read_text(
            encoding="utf-8")

        self.assertNotIn(".oh-no-parent-control-about-logo", stylesheet)
        self.assertIn("AboutDialog(self, links_enabled=self._child_overlay)", kiosk)
