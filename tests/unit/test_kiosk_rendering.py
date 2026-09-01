import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
KIOSK_MAIN = ROOT / "kiosk/oh_no_parent_control_kiosk/main.py"


class KioskRenderingTests(unittest.TestCase):
    def test_gateway_texture_uses_gtk_snapshot_api(self):
        source = KIOSK_MAIN.read_text(encoding="utf-8")

        self.assertIn("class GatewayBackground(Gtk.Widget):", source)
        self.assertIn("snapshot.append_texture(self._texture, image_bounds)", source)
        self.assertNotIn("Gdk.cairo_set_source_texture", source)


if __name__ == "__main__":
    unittest.main()
