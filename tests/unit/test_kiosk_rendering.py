import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
KIOSK_MAIN = ROOT / "kiosk/oh_no_parent_control_kiosk/main.py"
KIOSK_CONTENT = ROOT / "kiosk/oh_no_parent_control_kiosk/request_content.py"


class KioskRenderingTests(unittest.TestCase):
    def test_request_header_uses_the_product_logo(self):
        source = KIOSK_CONTENT.read_text(encoding="utf-8")

        self.assertIn('branding_asset_path("app_logo.png")', source)
        self.assertIn("Gtk.Image.new_from_file", source)
        self.assertIn("icon.set_pixel_size(52)", source)
        self.assertNotIn('Gtk.Image.new_from_icon_name("alarm-symbolic")', source)

    def test_kiosk_and_preview_play_the_soundtrack_on_a_loop(self):
        source = KIOSK_MAIN.read_text(encoding="utf-8")
        makefile = (ROOT / "Makefile").read_text(encoding="utf-8")

        self.assertIn('gi.require_version("Gst", "1.0")', source)
        self.assertIn('class BackgroundMusic:', source)
        self.assertIn('Path(__file__).with_name("Gearbox_Waltz.mp3")', source)
        self.assertIn('self._bus.connect("message::eos", self._restart)', source)
        self.assertIn('Gst.SeekFlags.FLUSH | Gst.SeekFlags.KEY_UNIT', source)
        self.assertIn('str(soundtrack or Path(__file__).with_name("Gearbox_Waltz.mp3"))', source)
        self.assertIn('self._music = BackgroundMusic(soundtrack)', source)
        self.assertIn('self._music.start()', source)
        self.assertIn('self._music.close()', source)
        self.assertIn('--preview --soundtrack "$(CURDIR)/data/Gearbox_Waltz.mp3"', makefile)

    def test_preview_uses_the_production_window_without_privileged_services(self):
        source = KIOSK_MAIN.read_text(encoding="utf-8")

        self.assertIn('parser.add_argument(\n        "--preview"', source)
        self.assertIn("self, preview=self._preview, soundtrack=self._soundtrack", source)
        self.assertIn("self._system_bus = None if preview", source)
        self.assertIn("self._request_content.set_accounts(PREVIEW_USERS)", source)
        self.assertIn("This is a visual preview; no access was requested.", source)
        self.assertIn("PREVIEW_DEFAULT_WIDTH = 1918", source)
        self.assertIn("PREVIEW_DEFAULT_HEIGHT = 1443", source)

    def test_preview_watches_its_assets_and_source(self):
        source = KIOSK_MAIN.read_text(encoding="utf-8")

        self.assertIn("directory.monitor_directory(", source)
        self.assertIn('path.name in {"style.css", "kiosk-background.jpeg"}', source)
        self.assertIn("self._load_stylesheet()", source)
        self.assertIn("window._background.reload_texture()", source)
        self.assertIn("os.execv(sys.executable, sys.orig_argv)", source)

    def test_preview_content_is_a_window_drag_handle(self):
        source = KIOSK_MAIN.read_text(encoding="utf-8")

        self.assertIn("if self._preview:\n            # The production kiosk", source)
        self.assertIn("drag_handle = Gtk.WindowHandle()", source)
        self.assertIn("drag_handle.set_child(layout)", source)
        self.assertIn("self.set_content(drag_handle)", source)

    def test_gateway_texture_uses_gtk_snapshot_api(self):
        source = KIOSK_MAIN.read_text(encoding="utf-8")

        self.assertIn("class GatewayBackground(Gtk.Widget):", source)
        self.assertIn("GATEWAY_CENTERING_OFFSET = 0.03125", source)
        self.assertIn("rendered_width * GATEWAY_CENTERING_OFFSET", source)
        self.assertIn("snapshot.append_texture(self._texture, image_bounds)", source)
        self.assertNotIn("Gdk.cairo_set_source_texture", source)

    def test_request_form_matches_the_gateway_perspective(self):
        source = KIOSK_MAIN.read_text(encoding="utf-8")

        self.assertIn("class GatewayAlignedRequest(Gtk.Widget):", source)
        self.assertIn("GATEWAY_FORM_YAW_DEGREES = 10.0", source)
        self.assertIn("GATEWAY_FORM_PERSPECTIVE_DEPTH = 1_200.0", source)
        self.assertIn("GATEWAY_FORM_CENTERING_OFFSET = 0.019", source)
        self.assertIn("width * GATEWAY_FORM_CENTERING_OFFSET", source)
        self.assertIn(".perspective(GATEWAY_FORM_PERSPECTIVE_DEPTH)", source)
        self.assertIn(".rotate_3d(", source)
        self.assertIn("self._child.allocate(child_width, child_height, baseline, transform)", source)
        self.assertIn("self.snapshot_child(self._child, snapshot)", source)
        self.assertIn("self._request_surface = GatewayAlignedRequest(self._request_content)", source)
        self.assertIn('self._stack.add_named(self._request_surface, "request")', source)
        self.assertNotIn(".skew(", source)

    def test_account_selectors_stay_in_the_transformed_form(self):
        source = KIOSK_CONTENT.read_text(encoding="utf-8")

        self.assertIn("class GatewayDropDown(Gtk.Box):", source)
        self.assertIn("outside the request form's snapshot", source)
        self.assertIn("self._accounts = GatewayDropDown(self._account_changed)", source)
        self.assertIn("self._approvers = GatewayDropDown()", source)
        self.assertNotIn("Gtk.DropDown", source)

    def test_four_block_chains_connect_form_to_gateway_corners(self):
        source = KIOSK_MAIN.read_text(encoding="utf-8")

        self.assertIn("GATEWAY_ARTWORK_WIDTH = 3_840", source)
        self.assertIn("GATEWAY_ARTWORK_HEIGHT = 2_160", source)
        self.assertIn("GATEWAY_INNER_CORNERS = (", source)
        corners_start = source.index("GATEWAY_INNER_CORNERS = (")
        corners_end = source.index("# Project the complete form", corners_start)
        corner_constants = source[corners_start:corners_end]
        self.assertEqual(corner_constants.count("/ GATEWAY_ARTWORK_WIDTH,"), 4)
        self.assertEqual(corner_constants.count("/ GATEWAY_ARTWORK_HEIGHT),"), 4)
        for source_corner in (
            "(1_374 / GATEWAY_ARTWORK_WIDTH, 347 / GATEWAY_ARTWORK_HEIGHT)",
            "(2_276 / GATEWAY_ARTWORK_WIDTH, 405 / GATEWAY_ARTWORK_HEIGHT)",
            "(2_276 / GATEWAY_ARTWORK_WIDTH, 1_780 / GATEWAY_ARTWORK_HEIGHT)",
            "(1_374 / GATEWAY_ARTWORK_WIDTH, 1_837 / GATEWAY_ARTWORK_HEIGHT)",
        ):
            self.assertIn(source_corner, corner_constants)
        self.assertIn("def _gateway_artwork_geometry(width, height):", source)
        self.assertGreaterEqual(
            source.count("_gateway_artwork_geometry(width, height)"), 3,
        )
        self.assertIn("transform.transform_point(Graphene.Point().init(x, y))", source)
        self.assertIn("for gateway_corner, form_corner in zip(", source)
        self.assertIn("gateway_inset =", source)
        self.assertIn("start[0] - unit_x * gateway_inset", source)
        self.assertIn("form_overlap =", source)
        self.assertIn("end[0] + unit_x * form_overlap", source)
        self.assertIn("gateway_corners = _gateway_inner_corners(width, height)", source)
        opening_clip = source.index("context.clip()")
        chain_draw = source.index("self._draw_minecraft_chain(")
        self.assertLess(opening_clip, chain_draw)

        chain_snapshot = source.index("self._append_gateway_chains(snapshot)")
        form_snapshot = source.index("self.snapshot_child(self._child, snapshot)")
        self.assertLess(chain_snapshot, form_snapshot)

        self.assertIn("def _draw_minecraft_chain", source)
        self.assertIn("for link_index in range(link_count):", source)
        self.assertIn("edge_on = link_index % 2 == 1", source)
        self.assertIn("if link_index == link_count - 1:", source)
        self.assertIn("edge_on = False", source)
        self.assertIn("sag = min(link_length * 1.25, distance * 0.13)", source)
        self.assertIn("def _chain_curve_samples", source)
        self.assertIn("control_y = (start[1] + end[1]) / 2 + sag * 2", source)
        self.assertIn("def _chain_curve_position", source)
        self.assertIn("def _append_angular_link_path", source)
        self.assertIn("context.set_fill_rule(cairo.FillRule.EVEN_ODD)", source)

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
