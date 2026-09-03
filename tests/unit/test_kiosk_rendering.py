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
        self.assertIn("icon.set_pixel_size(48)", source)
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
        self.assertIn('def fade_out(self, duration_ms):', source)
        self.assertIn('self._music.fade_out(SUCCESS_LOGOUT_DELAY_MS)', source)
        self.assertIn('self._music.cancel_fade()', source)
        self.assertIn('--preview --soundtrack "$(CURDIR)/data/Gearbox_Waltz.mp3"', makefile)

    def test_kiosk_has_a_sound_toggle_left_of_the_menu(self):
        source = KIOSK_MAIN.read_text(encoding="utf-8")

        self.assertIn('def set_muted(self, muted):', source)
        self.assertIn('self._player.set_property("mute", muted)', source)
        self.assertIn('icon_name="audio-volume-high-symbolic"', source)
        self.assertIn('self._mute_button.connect("clicked", self._toggle_mute)', source)
        self.assertIn('self._music.set_muted(muted)', source)
        self.assertIn('"audio-volume-muted-symbolic" if muted', source)
        self.assertLess(
            source.index("top_controls.append(self._mute_button)"),
            source.index("top_controls.append(menu_button)"),
        )

    def test_child_overlay_reuses_the_fullscreen_kiosk_gui(self):
        source = KIOSK_MAIN.read_text(encoding="utf-8")
        content = KIOSK_CONTENT.read_text(encoding="utf-8")
        makefile = (ROOT / "Makefile").read_text(encoding="utf-8")
        css = (ROOT / "kiosk/oh_no_parent_control_kiosk/style.css").read_text(
            encoding="utf-8",
        )

        self.assertNotIn("OVERLAY_SCALE", source)
        self.assertNotIn("class OverlayViewport", source)
        self.assertIn('parser.add_argument(\n        "--child-overlay"', source)
        self.assertIn("lock_child_selector=self._child_overlay", source)
        self.assertIn(
            '"com.puffyslippers.OhNoParentControl.ChildRequest"', source,
        )
        self.assertIn('self._bus_call("GetOwnAccount"', source)
        self.assertIn('"RequestOwnAccess"', source)
        self.assertIn('CHILD_SUCCESS_COPY = "Time granted, click here to close"', source)
        self.assertIn('CHILD_SUCCESS_TITLE = "Time granted"', source)
        self.assertIn("self._show_child_success()", source)
        self.assertIn("SUCCESS_LOGOUT_DELAY_MS = 3_000", source)
        self.assertIn("SUCCESS_COUNTDOWN_SECONDS = SUCCESS_LOGOUT_DELAY_MS // 1_000", source)
        self.assertIn('f"{self._success_action_label} ({remaining})"', source)
        self.assertIn("self._tick_success_countdown", source)
        self.assertIn("self._schedule_success_logout()", source)
        self.assertIn("approved request acknowledged; closing overlay", source)
        self.assertIn('close_click.connect("released", self._close_overlay)', source)
        self.assertIn("self._result_surface.add_controller(close_click)", source)
        self.assertIn("self.close()", source)
        self.assertIn("application.quit()", source)
        self.assertIn("muted_for_surface", content)
        self.assertIn("window.oh-no-parent-control-overlay", css)
        self.assertIn("preview-child-overlay:", makefile)
        self.assertIn("--preview --child-overlay", makefile)
        self.assertIn("if self._child_overlay:\n            menu.append(\"Help\", \"win.help\")", source)
        self.assertLess(
            source.index("if self._child_overlay:\n            menu.append(\"Help\", \"win.help\")"),
            source.index('menu.append("About", "win.about")'),
        )

    def test_escape_matches_the_cancel_action_when_no_auth_prompt_is_open(self):
        source = KIOSK_MAIN.read_text(encoding="utf-8")

        self.assertIn("self._cancel = self._close_overlay if self._child_overlay else self._logout", source)
        self.assertIn("escape.connect(\"key-pressed\", self._escape_pressed)", source)
        self.assertIn("Gdk.KEY_Escape", source)
        self.assertLess(
            source.index("if self._state.in_flight"),
            source.index("self._cancel()"),
        )
        self.assertIn("def _escape_pressed(self, _controller, keyval, _keycode, _state):", source)
        self.assertIn("if self._state.in_flight:\n            return False", source)
        self.assertIn("self._cancel()\n        return True", source)

    def test_preview_uses_the_production_window_without_privileged_services(self):
        source = KIOSK_MAIN.read_text(encoding="utf-8")

        self.assertIn('parser.add_argument(\n        "--preview"', source)
        self.assertIn(
            "self, preview=self._preview, soundtrack=self._soundtrack,\n"
            "            child_overlay=self._child_overlay,",
            source,
        )
        self.assertIn("self._system_bus = None if preview", source)
        self.assertIn("PREVIEW_USERS[:1] if self._child_overlay else PREVIEW_USERS", source)
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
        self.assertIn(".perspective(GATEWAY_FORM_PERSPECTIVE_DEPTH * scale)", source)
        self.assertIn(".rotate_3d(", source)
        self.assertIn(".scale(scale, scale)", source)
        self.assertIn("def _gateway_form_scale(width, height, form_width, form_height):", source)
        self.assertIn("self._child.allocate(child_width, child_height, baseline, transform)", source)
        self.assertIn("self.snapshot_child(self._child, snapshot)", source)
        self.assertIn("self._request_surface = GatewayAlignedRequest(self._request_content)", source)
        self.assertIn('self._stack.add_named(self._request_surface, "request")', source)
        self.assertIn("self._result_surface = GatewayAlignedRequest(self._result_view)", source)
        self.assertIn('self._stack.add_named(self._result_surface, "result")', source)
        self.assertNotIn('self._stack.add_named(self._result_view, "result")', source)
        self.assertNotIn(".skew(", source)

    def test_request_form_scales_with_the_gateway_artwork(self):
        source = KIOSK_MAIN.read_text(encoding="utf-8")

        self.assertIn("preview_cover = max(", source)
        self.assertIn("PREVIEW_DEFAULT_WIDTH / GATEWAY_ARTWORK_WIDTH", source)
        self.assertIn("PREVIEW_DEFAULT_HEIGHT / GATEWAY_ARTWORK_HEIGHT", source)
        self.assertIn("window_cover / preview_cover", source)
        self.assertIn("fit = min(width / form_width, height / form_height)", source)
        self.assertIn("return min(design_scale, fit)", source)
        self.assertIn("_gateway_form_scale(\n            width, height, child_width, child_height,", source)

    def test_form_scale_is_identity_at_the_preview_resolution(self):
        from oh_no_parent_control_kiosk.main import (
            PREVIEW_DEFAULT_HEIGHT, PREVIEW_DEFAULT_WIDTH, _gateway_form_scale,
        )

        self.assertAlmostEqual(
            _gateway_form_scale(
                PREVIEW_DEFAULT_WIDTH, PREVIEW_DEFAULT_HEIGHT, 400, 700,
            ),
            1.0,
            places=5,
        )
        wide_scale = _gateway_form_scale(3840, 2160, 400, 700)
        self.assertGreater(wide_scale, 1.0)
        tall_small = _gateway_form_scale(800, 600, 400, 780)
        self.assertLessEqual(tall_small, 600 / 780)

    def test_request_form_uses_the_minecraft_board_chrome(self):
        content = KIOSK_CONTENT.read_text(encoding="utf-8")
        chrome = (ROOT / "kiosk/oh_no_parent_control_kiosk/chrome.py").read_text(
            encoding="utf-8",
        )
        css = (ROOT / "kiosk/oh_no_parent_control_kiosk/style.css").read_text(
            encoding="utf-8",
        )
        makefile = (ROOT / "Makefile").read_text(encoding="utf-8")

        self.assertIn("class RequestContent(MetalBoard):", content)
        self.assertIn('branding_asset_path("app_logo.png")', content)
        self.assertIn("icon.set_pixel_size(48)", content)
        self.assertIn("oh-no-parent-control-logo-plate", content)
        self.assertIn("CHILD_HEAD", content)
        self.assertIn("APPROVER_HEAD", content)
        self.assertIn("SHIELD, display_size=20", content)
        self.assertIn("PixelIcon(LOCK, display_size=16", content)
        self.assertIn("PixelIcon(POINTER", content)
        self.assertIn('label="REQUEST"', content)
        self.assertIn('label="CANCEL"', content)
        self.assertIn("class MetalBoard(Gtk.Box):", chrome)
        self.assertIn("class MetalPanel(Gtk.Box):", chrome)
        self.assertIn("class ArmoredButton(Gtk.Button):", chrome)
        self.assertIn("def paint_board_frame(", chrome)
        self.assertIn("def paint_button_hardware(", chrome)
        self.assertIn("BOARD_CHAIN_ANCHOR_SIDE_INSET = 12.0", chrome)
        self.assertIn("BOARD_CHAIN_ANCHOR_END_INSET = 34.0", chrome)
        self.assertIn("connector_x =", chrome)
        self.assertIn('panel_kind="header"', content)
        self.assertIn('panel_kind="well"', content)
        self.assertIn('panel_kind="footer"', content)
        self.assertIn('armor_kind="request"', content)
        self.assertIn('armor_kind="cancel"', content)
        self.assertIn("def _paint_block_texture(", chrome)
        self.assertIn("padding: 22px 18px;", css)
        self.assertIn("font-size: 16px;", css)
        self.assertIn("font-size: 0.70em;", css)
        self.assertIn("font-size: 0.90em;", css)
        self.assertIn("font-size: 0.92em;", css)
        self.assertIn("font-size: 1.08em;", css)
        self.assertIn("min-height: 62px;", css)
        self.assertIn("oh-no-parent-control-status-inner", content)
        self.assertIn("margin: 8px 28px 10px 22px;", css)
        self.assertIn("padding-bottom: 2px;", css)
        self.assertIn("set_natural_wrap_mode(Gtk.NaturalWrapMode.WORD)", content)
        self.assertIn("set_max_width_chars(26)", content)
        self.assertIn("set_overflow(Gtk.Overflow.VISIBLE)", content)
        self.assertIn('FORM_FONT_FAMILY = "Monocraft"', chrome)
        self.assertIn("add_font_file", chrome)
        self.assertIn('font-family: "Monocraft"', css)
        self.assertIn("kiosk/oh_no_parent_control_kiosk/fonts/Monocraft.ttf", makefile)
        self.assertTrue(
            (ROOT / "kiosk/oh_no_parent_control_kiosk/fonts/Monocraft.ttf").is_file(),
        )
        self.assertTrue(
            (ROOT / "kiosk/oh_no_parent_control_kiosk/fonts/OFL.txt").is_file(),
        )
        from oh_no_parent_control_kiosk.chrome import (
            FORM_FONT_FAMILY, register_form_font,
        )

        self.assertEqual(FORM_FONT_FAMILY, "Monocraft")
        self.assertTrue(register_form_font())

    def test_account_selectors_stay_in_the_transformed_form(self):
        source = KIOSK_CONTENT.read_text(encoding="utf-8")
        css = (ROOT / "kiosk/oh_no_parent_control_kiosk/style.css").read_text(
            encoding="utf-8",
        )

        self.assertIn("class GatewayDropDown(Gtk.Box):", source)
        self.assertIn("outside the request form's snapshot", source)
        self.assertIn("self._accounts = GatewayDropDown(self._account_changed)", source)
        self.assertIn("self._approvers = GatewayDropDown(self._approver_changed)", source)
        self.assertIn("apply_gtk_user_icon", source)
        self.assertIn("parse_listed_user", source)
        self.assertNotIn("Gtk.DropDown", source)
        self.assertIn("VISIBLE_ACCOUNT_CHOICES = 2", source)
        self.assertIn("len(self._choice_buttons) - VISIBLE_ACCOUNT_CHOICES", source)
        self.assertIn("self._scroll_offset <= index < self._scroll_offset + VISIBLE_ACCOUNT_CHOICES", source)
        self.assertIn('self._scroll_button("pan-up-symbolic", -1)', source)
        self.assertIn('self._scroll_button("pan-down-symbolic", 1)', source)
        self.assertIn("oh-no-parent-control-account-scroll", source)
        self.assertIn("Gtk.EventControllerScrollFlags.VERTICAL", source)
        self.assertIn("button.oh-no-parent-control-account-scroll", css)

    def test_allow_soft_row_is_a_full_width_toggle_button(self):
        source = KIOSK_CONTENT.read_text(encoding="utf-8")
        css = (ROOT / "kiosk/oh_no_parent_control_kiosk/style.css").read_text(
            encoding="utf-8",
        )

        self.assertIn("filter_row = Gtk.Button()", source)
        self.assertIn("self._allow_soft.set_can_target(False)", source)
        self.assertIn('filter_row.connect("clicked", self._toggle_allow_soft)', source)
        self.assertIn("def _toggle_allow_soft(self, _button):", source)
        self.assertIn(
            "self._allow_soft.set_active(not self._allow_soft.get_active())",
            source,
        )
        self.assertIn(
            "button.oh-no-parent-control-app-filter-toggle:hover",
            css,
        )

    def test_screen_limit_off_disables_the_request_form_without_a_footer_error(self):
        source = KIOSK_CONTENT.read_text(encoding="utf-8")

        self.assertNotIn("self._duration_menu = Gtk.Overlay()", source)
        self.assertIn("self._screen_limit_overlay = Gtk.Overlay()", source)
        self.assertIn(
            'label="Screen limit is not enabled in Parent App"', source,
        )
        self.assertIn(
            "self._screen_limit_overlay.add_overlay(self._screen_limit_notice)", source,
        )
        self.assertLess(
            source.index("self.append(child_selector)"),
            source.index("self.append(self._screen_limit_overlay)"),
        )
        self.assertLess(
            source.index("self.append(self._screen_limit_overlay)"),
            source.index("self.append(self._cancel)"),
        )
        self.assertIn("self._screen_time_limit_enabled is not None", source)
        self.assertIn(
            "self._custom_entry.set_sensitive(request_available and time_limit_enabled)",
            source,
        )
        self.assertIn("self._allow_soft.set_sensitive(request_available)", source)
        self.assertIn("self._filter_row.set_sensitive(request_available)", source)
        self.assertIn("self._approvers.set_sensitive(request_available)", source)
        self.assertIn("self._cancel.set_sensitive(self._controls_enabled)", source)
        self.assertIn("self._status.remove_css_class(\"oh-no-parent-control-error\")", source)

    def test_four_block_chains_connect_gateway_corners_to_form_rail_lugs(self):
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
        self.assertIn("side = BOARD_CHAIN_ANCHOR_SIDE_INSET", source)
        self.assertIn("end = BOARD_CHAIN_ANCHOR_END_INSET", source)
        self.assertIn("(side, end)", source)
        self.assertIn("(child_width - side, child_height - end)", source)
        self.assertIn("for gateway_corner, form_corner in zip(", source)
        self.assertIn("gateway_inset =", source)
        self.assertIn("start[0] + start_extend[0] * gateway_inset", source)
        self.assertIn("form_overlap =", source)
        self.assertIn("end[0] + end_extend[0] * form_overlap", source)
        self.assertIn("start_extend=_unit_vector(opening_center, gateway_corner)", source)
        self.assertIn("end_extend=_unit_vector(form_corner, form_center)", source)
        self.assertIn("gateway_corners = _gateway_inner_corners(width, height)", source)
        self.assertIn("_convex_hull((*gateway_corners, *self._form_corners))", source)
        self.assertIn("def _convex_hull(points):", source)
        opening_clip = source.index("context.clip()")
        chain_draw = source.index("self._draw_minecraft_chain(")
        self.assertLess(opening_clip, chain_draw)
        self.assertLess(
            source.index("_convex_hull((*gateway_corners, *self._form_corners))"),
            opening_clip,
        )

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

    def test_chain_clip_includes_form_corners_outside_the_gateway(self):
        from oh_no_parent_control_kiosk.main import _convex_hull, _unit_vector

        gateway = (
            (100.0, 100.0),
            (300.0, 110.0),
            (300.0, 400.0),
            (100.0, 410.0),
        )
        form = (
            (140.0, 20.0),
            (260.0, 20.0),
            (260.0, 500.0),
            (140.0, 500.0),
        )
        hull = set(_convex_hull((*gateway, *form)))
        for corner in form:
            self.assertIn(corner, hull)
        self.assertIn((100.0, 100.0), hull)
        self.assertIn((300.0, 110.0), hull)
        self.assertIn((100.0, 410.0), hull)
        self.assertIn((300.0, 400.0), hull)
        self.assertLess(_unit_vector((200.0, 255.0), (100.0, 100.0))[0], 0)
        self.assertLess(_unit_vector((200.0, 260.0), (140.0, 20.0))[1], 0)

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
