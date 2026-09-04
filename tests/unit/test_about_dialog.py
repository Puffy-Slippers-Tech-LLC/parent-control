"""Tests for intrinsic-size About dialog branding."""

from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[2]


class AboutDialogTests(unittest.TestCase):
    def test_website_row_uses_a_generic_web_browser_icon(self):
        source = (ROOT / "common/oh_no_parent_control_ui/about.py").read_text(
            encoding="utf-8")

        self.assertIn('_detail_row("web-browser-symbolic", "Website"', source)
        self.assertNotIn('icon_filename="company_logo.png"', source)

    def test_gtk_about_logo_uses_launcher_art_at_the_original_display_size(self):
        source = (ROOT / "common/oh_no_parent_control_ui/about.py").read_text(
            encoding="utf-8")

        self.assertIn('branding_asset_path("app_logo_gnome_launcher.png")', source)
        self.assertIn("_ABOUT_LOGO_WIDTH = 126", source)
        self.assertIn("_ABOUT_LOGO_HEIGHT = 128", source)
        self.assertIn("Gsk.ScalingFilter.TRILINEAR", source)
        self.assertIn("logo = _AboutLogo()", source)

    def test_child_session_uses_the_shared_gtk_about_dialog(self):
        stylesheet = (ROOT / "child/stylesheet.css").read_text(encoding="utf-8")
        kiosk = (ROOT / "kiosk/oh_no_parent_control_kiosk/main.py").read_text(
            encoding="utf-8")

        self.assertNotIn(".oh-no-parent-control-about-logo", stylesheet)
        self.assertIn("AboutDialog(self, links_enabled=self._child_overlay)", kiosk)
