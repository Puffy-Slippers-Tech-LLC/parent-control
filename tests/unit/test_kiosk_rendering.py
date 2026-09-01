import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
KIOSK_MAIN = ROOT / "kiosk/oh_no_parent_control_kiosk/main.py"


class KioskRenderingTests(unittest.TestCase):
    def test_preview_uses_the_production_window_without_privileged_services(self):
        source = KIOSK_MAIN.read_text(encoding="utf-8")

        self.assertIn('parser.add_argument(\n        "--preview"', source)
        self.assertIn("RequestWindow(self, preview=self._preview)", source)
        self.assertIn("self._system_bus = None if preview", source)
        self.assertIn("self._request_content.set_accounts(PREVIEW_USERS)", source)
        self.assertIn("This is a visual preview; no access was requested.", source)
        self.assertIn("PREVIEW_DEFAULT_WIDTH = 1918", source)
        self.assertIn("PREVIEW_DEFAULT_HEIGHT = 1443", source)

    def test_gateway_texture_uses_gtk_snapshot_api(self):
        source = KIOSK_MAIN.read_text(encoding="utf-8")

        self.assertIn("class GatewayBackground(Gtk.Widget):", source)
        self.assertIn("snapshot.append_texture(self._texture, image_bounds)", source)
        self.assertNotIn("Gdk.cairo_set_source_texture", source)

    def test_gateway_artwork_is_static_with_animated_gateway_energy(self):
        source = KIOSK_MAIN.read_text(encoding="utf-8")

        self.assertNotIn("zoom =", source)
        self.assertIn("def _append_gateway_energy", source)
        self.assertIn("snapshot.append_cairo(bounds)", source)
        self.assertIn("random.SystemRandom()", source)
        self.assertIn("def _new_lightning_bolt", source)
        self.assertIn("randomly sourced lightning moving into the gateway", source)
        self.assertIn('"branches": tuple(', source)
        self.assertIn("for _branch in range(self._random.randint(0, 4))", source)
        self.assertIn("branch_lightness,", source)
        self.assertIn("(1 - progress) ** branch_fade_rate", source)
        self.assertIn("(1 - progress) ** branch_taper_rate", source)
        self.assertIn('"thickness": self._random.uniform(0.22, 6.6)', source)
        self.assertIn('"brightness": self._random.uniform(0.28, 2.4)', source)
        self.assertIn('"fade_rate": self._random.uniform(0.68, 1.35)', source)
        self.assertIn("thickness = bolt[\"thickness\"] * (1 - progress) ** 1.35", source)
        self.assertIn('"path_offsets": self._new_winding_offsets()', source)
        self.assertIn('"detail_offsets": self._new_secondary_offsets()', source)
        self.assertIn('"winding": self._random.uniform(0.08, 0.16)', source)
        self.assertIn("def _new_winding_offsets", source)
        self.assertIn("def _new_secondary_offsets", source)
        self.assertIn("smooth_fraction = (1 - math.cos(math.pi * fraction)) / 2", source)
        self.assertNotIn("math.sin(step * 8.7", source)


if __name__ == "__main__":
    unittest.main()
