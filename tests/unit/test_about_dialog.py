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

    def test_child_about_logo_has_no_css_size_override(self):
        source = (ROOT / "child/stylesheet.css").read_text(encoding="utf-8")
        rule = source.split(".oh-no-parent-control-about-logo {", 1)[1].split("}", 1)[0]

        self.assertNotIn("width:", rule)
        self.assertNotIn("height:", rule)
