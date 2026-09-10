import unittest
from pathlib import Path
from types import SimpleNamespace


from tests.support.paths import ROOT
KIOSK_MAIN = ROOT / "kiosk/oh_no_parent_control_kiosk/main.py"
KIOSK_CONTENT = ROOT / "kiosk/oh_no_parent_control_kiosk/request_content.py"


class KioskRenderingTests(unittest.TestCase):
    def test_snowflake_field_uses_120_percent_of_its_previous_count(self):
        from oh_no_parent_control_kiosk.snowflakes import (
            COUNT_MULTIPLIER,
            SnowflakeField,
        )

        width, height = 1920, 1080
        artwork = (0, 0, width, height)
        field = SnowflakeField()
        field.configure(width, height, artwork)

        self.assertEqual(COUNT_MULTIPLIER, 1.2)
        self.assertEqual(len(field._flakes), 59)

    def test_request_header_uses_the_product_logo(self):
        source = KIOSK_CONTENT.read_text(encoding="utf-8")

        self.assertIn('branding_asset_path("app_logo.png")', source)
        self.assertIn("Gtk.Image.new_from_file", source)
        self.assertIn("icon.set_pixel_size(36)", source)
        self.assertIn("xalign=0.5", source)
        self.assertIn("justify=Gtk.Justification.CENTER", source)
        self.assertNotIn('Gtk.Image.new_from_icon_name("alarm-symbolic")', source)
        self.assertNotIn("Choose your extra time", source)

    def test_custom_duration_caption_has_display_only_pointer_spacing(self):
        source = KIOSK_CONTENT.read_text(encoding="utf-8")

        self.assertIn(
            'display_label = f" {label}" if seconds is None else label',
            source,
        )
        self.assertIn('label=display_label, hexpand=True', source)
        self.assertIn('button, f"Request {label}"', source)

    def test_request_surfaces_only_connect_flash_triggered_audio(self):
        source = KIOSK_MAIN.read_text(encoding="utf-8")
        makefile = (ROOT / "Makefile").read_text(encoding="utf-8")

        self.assertNotIn("BackgroundMusic", source)
        self.assertNotIn("soundtrack", source)
        self.assertNotIn("Gearbox_Waltz", makefile)
        self.assertFalse((ROOT / "data/Gearbox_Waltz.mp3").exists())
        self.assertIn("self._thunder = LightningAudio()", source)
        self.assertIn("self._background.set_lightning_audio(self._thunder.play)", source)
        self.assertIn("self._apply_mute(True)", source)
        self.assertIn("self._thunder.close()", source)
        self.assertIn("self._thunder.fade_out(SUCCESS_LOGOUT_DELAY_MS)", source)
        self.assertIn("self._thunder.cancel_fade()", source)

    def test_kiosk_has_a_sound_and_lightning_toggle_left_of_the_menu(self):
        source = KIOSK_MAIN.read_text(encoding="utf-8")

        self.assertIn("self._mute_icon = PixelIcon(SPEAKER, display_size=28, label=\"\")", source)
        self.assertIn("menu_icon = PixelIcon(MENU, display_size=31, label=\"\")", source)
        self.assertIn(
            'armor_kind="hud", tooltip_text="Mute sound and lightning"', source,
        )
        self.assertIn('self._mute_button.connect("clicked", self._toggle_mute)', source)
        self.assertIn('self._thunder.set_muted(muted)', source)
        self.assertIn('self._background.set_lightning_enabled(not muted)', source)
        self.assertIn('def set_lightning_enabled(self, enabled):', source)
        self.assertIn('if not self._lightning_enabled:', source)
        self.assertIn('self._lightning_bolts.clear()', source)
        self.assertIn("SPEAKER_MUTED if muted else SPEAKER", source)
        self.assertNotIn("audio-volume-high-symbolic", source)
        self.assertNotIn("audio-volume-muted-symbolic", source)
        self.assertLess(
            source.index("top_controls.append(self._mute_button)"),
            source.index("top_controls.append(menu_button)"),
        )

    def test_muted_gateway_clears_and_suppresses_lightning(self):
        from oh_no_parent_control_kiosk.main import GatewayBackground

        redraws = []
        background = SimpleNamespace(
            _lightning_enabled=True,
            _lightning_bolts=[{"starts_at": 0.0}],
            _next_lightning_burst_at=42.0,
            queue_draw=lambda: redraws.append(True),
        )

        GatewayBackground.set_lightning_enabled(background, False)

        self.assertFalse(background._lightning_enabled)
        self.assertEqual(background._lightning_bolts, [])
        self.assertEqual(background._next_lightning_burst_at, 0.0)
        self.assertEqual(redraws, [True])
        # The muted path returns before it asks GTK for a drawing context.
        GatewayBackground._append_gateway_energy(background, None, 800, 600, 1.0)

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
        self.assertIn('CHILD_SUCCESS_COPY = "Time granted, Close"', source)
        self.assertIn('CHILD_SUCCESS_TITLE = "Time granted"', source)
        self.assertIn("self._show_child_success()", source)
        self.assertIn("SUCCESS_LOGOUT_DELAY_MS = 3_000", source)
        self.assertIn("SUCCESS_COUNTDOWN_SECONDS = SUCCESS_LOGOUT_DELAY_MS // 1_000", source)
        self.assertIn('f"{self._success_action_label} ({remaining})"', source)
        self.assertIn("self._tick_success_countdown", source)
        self.assertIn("self._schedule_success_logout()", source)
        self.assertIn("approved request acknowledged; closing overlay", source)
        self.assertNotIn('close_click.connect("released", self._close_overlay)', source)
        self.assertIn('self._result_action.connect("clicked", self._result_dismissed)', source)
        self.assertIn("self.close()", source)
        self.assertIn("application.quit()", source)
        self.assertIn("muted_for_surface", content)
        self.assertIn("window.oh-no-parent-control-overlay", css)
        self.assertIn("preview-child-overlay:", makefile)
        self.assertIn("oh_no_parent_control_kiosk.preview --child-overlay", makefile)
        self.assertIn(
            "if self._child_overlay:\n            help_item = self._hud_menu_item(\"HELP\", HELP)",
            source,
        )
        self.assertIn('self._hud_menu_item("ABOUT", ABOUT)', source)
        self.assertLess(
            source.index('self._hud_menu_item("HELP", HELP)'),
            source.index('self._hud_menu_item("ABOUT", ABOUT)'),
        )
        self.assertIn('always_show_arrow=False', source)
        self.assertIn("oh-no-parent-control-hud-button", source)
        self.assertIn("oh-no-parent-control-hud-menu", source)
        self.assertIn("popover_content.append(HudMenuStem())", source)
        self.assertIn("menu_board.append(menu_actions)", source)
        self.assertIn("menu_button.connect(\"notify::active\", self._menu_state_changed)", source)
        self.assertIn('"request-screen menu expanded=%s overlay=%s"', source)
        self.assertNotIn("open-menu-symbolic", source)

    def test_result_action_matches_request_and_cancel_button_width(self):
        source = KIOSK_MAIN.read_text(encoding="utf-8")
        content = KIOSK_CONTENT.read_text(encoding="utf-8")

        self.assertIn("self._result_action = ArmoredButton(", source)
        self.assertIn("hexpand=True, armor_kind=\"request\"", source)
        self.assertIn("self._result_action.set_margin_start(10)", source)
        self.assertIn("self._result_action.set_margin_end(10)", source)
        self.assertIn("self._request.set_margin_start(3)", content)
        self.assertIn("self._request.set_margin_end(3)", content)
        self.assertIn("self._cancel.set_margin_start(3)", content)
        self.assertIn("self._cancel.set_margin_end(3)", content)

    def test_result_title_reserves_space_for_pixel_font_ink(self):
        css = (ROOT / "kiosk/oh_no_parent_control_kiosk/style.css").read_text(
            encoding="utf-8",
        )

        title_rule = css.split(".oh-no-parent-control-page-title {", 1)[1]
        title_rule = title_rule.split("}", 1)[0]
        self.assertIn("min-height: 24px;", title_rule)
        self.assertIn("margin-top: 8px;", title_rule)
        self.assertIn("padding: 12px 0 3px;", title_rule)

    def test_kiosk_success_omits_redundant_child_detail(self):
        source = KIOSK_MAIN.read_text(encoding="utf-8")

        self.assertIn('self._show_result("Request approved", "")', source)
        self.assertNotIn("The requested access is ready for", source)
        self.assertNotIn("self._requested_label", source)

    def test_results_without_detail_use_compact_board_height(self):
        source = KIOSK_MAIN.read_text(encoding="utf-8")
        css = (ROOT / "kiosk/oh_no_parent_control_kiosk/style.css").read_text(
            encoding="utf-8",
        )

        self.assertIn("if detail:", source)
        self.assertIn(
            'self._result_view.remove_css_class(\n'
            '                "oh-no-parent-control-compact-result",',
            source,
        )
        self.assertIn(
            'self._result_view.add_css_class(\n'
            '                "oh-no-parent-control-compact-result",',
            source,
        )
        compact_rule = css.split(
            ".oh-no-parent-control-secondary-page."
            "oh-no-parent-control-compact-result {",
            1,
        )[1].split("}", 1)[0]
        self.assertIn("min-height: 144px;", compact_rule)

    def test_escape_matches_the_cancel_action_when_no_auth_prompt_is_open(self):
        source = KIOSK_MAIN.read_text(encoding="utf-8")

        self.assertIn("self._cancel = self._close_overlay if self._child_overlay else self._logout", source)
        self.assertIn("escape.connect(\"key-pressed\", self._escape_pressed)", source)
        self.assertIn("Gdk.KEY_Escape", source)
        escape_source = source.split("    def _escape_pressed(", 1)[1].split("    def ", 1)[0]
        self.assertLess(escape_source.index("if self._state.in_flight"),
                        escape_source.index("self._result_dismissed()"))
        self.assertIn("def _escape_pressed(self, _controller, keyval, _keycode, _state):", source)
        self.assertIn("if self._state.in_flight:\n            return False", source)
        self.assertIn("self._cancel()\n        return True", source)

    def test_screen_time_disabled_never_enables_request_submission(self):
        content = KIOSK_CONTENT.read_text(encoding="utf-8")

        self.assertIn(
            "self._controls_enabled and self._ready and\n"
            "            self._screen_time_limit_enabled is True",
            content,
        )

    def test_preview_uses_the_production_window_without_privileged_services(self):
        source = KIOSK_MAIN.read_text(encoding="utf-8")

        self.assertIn('parser.add_argument(\n        "--preview"', source)
        self.assertIn(
            "self, preview=self._preview,\n"
            "            child_overlay=self._child_overlay,",
            source,
        )
        self.assertIn("self._interactive_preview = broker_connection is not None", source)
        self.assertIn("broker_connection if broker_connection is not None else", source)
        self.assertIn("(None if preview else Gio.bus_get_sync", source)
        self.assertIn("PREVIEW_USERS[:1] if self._child_overlay else PREVIEW_USERS", source)
        self.assertIn("This is a visual preview; no access was requested.", source)
        self.assertIn("PREVIEW_DEFAULT_WIDTH = 1918", source)
        self.assertIn("PREVIEW_DEFAULT_HEIGHT = 1443", source)

    def test_preview_watches_its_assets_and_source(self):
        source = KIOSK_MAIN.read_text(encoding="utf-8")

        self.assertIn("directory.monitor_directory(", source)
        self.assertIn('"style.css", "kiosk-background-still.png", "kiosk-background-scenery-clear.png",', source)
        self.assertIn("self._load_stylesheet()", source)
        self.assertIn("window._background.reload_texture()", source)
        self.assertIn("os.execv(sys.executable, sys.orig_argv)", source)

    def test_preview_content_is_a_window_drag_handle(self):
        source = KIOSK_MAIN.read_text(encoding="utf-8")

        self.assertIn(
            'if self._preview and not self._child_overlay and not os.environ.get("ONPC_PREVIEW_SCREEN_FD"):\n'
            "            # The production kiosk",
            source,
        )
        self.assertIn("drag_handle = Gtk.WindowHandle()", source)
        self.assertIn("drag_handle.set_child(layout)", source)
        self.assertIn("self.set_content(drag_handle)", source)

    def test_clean_scenery_plate_matches_source_coordinates_and_ships(self):
        import cairo
        from oh_no_parent_control_kiosk.floating_islands import SOURCE_WIDTH, SOURCE_HEIGHT

        asset = ROOT / "kiosk/oh_no_parent_control_kiosk/kiosk-background-scenery-clear.png"
        texture = cairo.ImageSurface.create_from_png(str(asset))
        self.assertEqual((texture.get_width(), texture.get_height()),
                         (SOURCE_WIDTH, SOURCE_HEIGHT))
        self.assertIn(asset.relative_to(ROOT).as_posix(),
                      (ROOT / "Makefile").read_text(encoding="utf-8"))

    def test_gateway_texture_uses_gtk_snapshot_api(self):
        source = KIOSK_MAIN.read_text(encoding="utf-8")

        self.assertIn("class GatewayBackground(Gtk.Widget):", source)
        self.assertIn("_gateway_scene_regions(width, height)", source)
        self.assertIn("snapshot.append_texture(self._texture, image_bounds)", source)
        self.assertNotIn("Gdk.cairo_set_source_texture", source)

    def test_request_form_matches_the_gateway_perspective(self):
        source = KIOSK_MAIN.read_text(encoding="utf-8")

        self.assertIn("class GatewayAlignedRequest(Gtk.Widget):", source)
        self.assertIn("GATEWAY_FORM_YAW_DEGREES = 10.0", source)
        self.assertIn("GATEWAY_FORM_PERSPECTIVE_DEPTH = 1_200.0", source)
        self.assertIn("corners = _gateway_inner_corners(width, height)", source)
        self.assertIn(".perspective(GATEWAY_FORM_PERSPECTIVE_DEPTH)", source)
        self.assertIn(".rotate_3d(", source)
        self.assertIn("self._viewport.allocate(child_width, child_height, baseline, transform)", source)
        self.assertIn("self.snapshot_child(self._viewport, snapshot)", source)
        self.assertIn("self._request_surface = GatewayAlignedRequest(self._request_content)", source)
        self.assertIn('self._stack.add_named(self._request_surface, "request")', source)
        self.assertIn("self._result_surface = GatewayAlignedRequest(self._result_view)", source)
        self.assertIn('self._stack.add_named(self._result_surface, "result")', source)
        self.assertNotIn('self._stack.add_named(self._result_view, "result")', source)
        self.assertNotIn(".skew(", source)

    def test_scene_preserves_both_sides_and_reserves_desktop_space(self):
        from oh_no_parent_control_kiosk.main import (
            _gateway_artwork_geometry, _gateway_scene_regions, _gateway_scene_point,
        )
        from oh_no_parent_control_kiosk.floating_islands import ISLANDS, SOURCE_WIDTH, SOURCE_HEIGHT
        from oh_no_parent_control_kiosk.snowflakes import GATEWAY_OUTER_BOUNDS

        for width, height in ((480, 800), (1366, 768), (1536, 960), (1920, 1080),
                              (3440, 1440), (3840, 1080), (3840, 1600), (3840, 2160)):
            with self.subTest(size=(width, height)):
                regions = _gateway_scene_regions(width, height)
                edge = 0
                for (x, y, clip_width, clip_height), artwork in regions:
                    self.assertAlmostEqual(x, edge)
                    self.assertEqual((y, clip_height), (0, height))
                    self.assertGreater(clip_width, 0)
                    edge = x + clip_width
                self.assertAlmostEqual(edge, width)
                self.assertAlmostEqual(_gateway_scene_point(width, height, 0, 0)[0], 0)
                self.assertAlmostEqual(_gateway_scene_point(width, height, 1, 1)[0], width)
                for island in ISLANDS:
                    for source_x, source_y in island.outline:
                        x, y = _gateway_scene_point(
                            width, height, source_x / SOURCE_WIDTH, source_y / SOURCE_HEIGHT,
                        )
                        self.assertTrue(0 < x < width and 0 < y < height)
                if width >= 1536:
                    artwork_width = _gateway_artwork_geometry(width, height)[2]
                    outer_width = artwork_width * (GATEWAY_OUTER_BOUNDS[2] - GATEWAY_OUTER_BOUNDS[0])
                    self.assertLessEqual(outer_width, width * 0.40 + 1e-6)

    def test_tall_desktops_preserve_the_laptop_gateway_proportions(self):
        from oh_no_parent_control_kiosk.main import _gateway_inner_corners

        def opening(width, height):
            corners = _gateway_inner_corners(width, height)
            return (corners[1][0] - corners[0][0],
                    min(point[1] for point in corners[2:])
                    - max(point[1] for point in corners[:2]))

        laptop_width, laptop_height = opening(1920, 1200)
        for width, height in ((3440, 1440), (3840, 1600), (3840, 2160)):
            with self.subTest(size=(width, height)):
                opening_width, opening_height = opening(width, height)
                self.assertGreater(opening_width, laptop_width)
                self.assertAlmostEqual(opening_width / opening_height,
                                       laptop_width / laptop_height)

        # More horizontal space alone must not stretch the frame, and the
        # existing laptop allocations at 100% and 125% remain unchanged.
        for ultrawide, laptop in zip(opening(3840, 1080), opening(1920, 1080)):
            self.assertAlmostEqual(ultrawide, laptop)
        for width, height, expected in ((1920, 1200, 640), (1536, 960, 614.4)):
            with self.subTest(laptop=(width, height)):
                self.assertAlmostEqual(opening(width, height)[0], expected * 902 / 1416)

    def test_scenery_keeps_source_proportions_at_every_screen_shape(self):
        from oh_no_parent_control_kiosk.main import _gateway_scene_regions
        from oh_no_parent_control_kiosk.floating_islands import (
            SCENERY, SOURCE_WIDTH, SOURCE_HEIGHT, scenery_artwork_geometry,
        )

        for width, height in ((480, 800), (1366, 768), (1536, 960), (1920, 1200),
                              (2560, 1440), (3840, 1600), (3840, 1080), (3840, 2160)):
            with self.subTest(size=(width, height)):
                regions = _gateway_scene_regions(width, height)
                for item in SCENERY:
                    index = 0 if item.outline[0][0] < SOURCE_WIDTH / 2 else 2
                    clip, backdrop = regions[index]
                    x, y, artwork_width, artwork_height = scenery_artwork_geometry(backdrop, item)
                    self.assertAlmostEqual(artwork_width / SOURCE_WIDTH,
                                           artwork_height / SOURCE_HEIGHT)
                    for source_x, source_y in item.outline:
                        rendered_x = x + source_x * artwork_width / SOURCE_WIDTH
                        rendered_y = y + source_y * artwork_height / SOURCE_HEIGHT
                        self.assertGreaterEqual(rendered_x + 1e-6, clip[0])
                        self.assertLessEqual(rendered_x, clip[0] + clip[2] + 1e-6)
                        self.assertGreaterEqual(rendered_y, 0)
                        self.assertLessEqual(rendered_y, height + 1e-6)

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
        self.assertIn("icon.set_pixel_size(36)", content)
        self.assertIn("oh-no-parent-control-logo-plate", content)
        self.assertIn("icon = dropdown.account_icon", content)
        self.assertIn('apply_gtk_user_icon(icon, "", pixel_size=24)', content)
        self.assertIn("SHIELD, display_size=20", content)
        self.assertIn("PixelIcon(LOCK, display_size=16", content)
        self.assertIn("PixelIcon(POINTER", content)
        self.assertIn('label="REQUEST"', content)
        self.assertIn('label="CANCEL"', content)
        self.assertIn("class MetalBoard(Gtk.Box):", chrome)
        self.assertIn("class MetalPanel(Gtk.Box):", chrome)
        self.assertIn("class ArmoredButton(Gtk.Button):", chrome)
        self.assertIn("class ArmoredMenuButton(Gtk.MenuButton):", chrome)
        self.assertIn("class HudIconFrame(Gtk.Overlay):", chrome)
        self.assertIn("class HudMenuStem(Gtk.Widget):", chrome)
        self.assertIn("class HudMenuBoard(Gtk.Box):", chrome)
        self.assertIn("SPEAKER = _parse_sprite(", chrome)
        self.assertIn("SPEAKER_MUTED = _parse_sprite(", chrome)
        self.assertIn("MENU = _parse_sprite(", chrome)
        self.assertIn("def set_pixels(self, pixels):", chrome)
        self.assertIn('kind == "hud"', chrome)
        self.assertIn("context.scale(0.5, 0.5)", chrome)
        self.assertIn("width * 2, height * 2, fill_face=False", chrome)
        self.assertIn("def paint_board_frame(", chrome)
        self.assertIn("def paint_button_hardware(", chrome)
        self.assertIn("button.oh-no-parent-control-hud-button", css)
        self.assertIn("menubutton.oh-no-parent-control-hud-button > button", css)
        self.assertIn("popover.oh-no-parent-control-hud-menu", css)
        self.assertIn("button.oh-no-parent-control-hud-menu-item", css)
        self.assertIn("min-width: 66px;", css)
        self.assertIn("min-height: 66px;", css)
        self.assertIn("oh-no-parent-control-hud-menu-icon", css)
        self.assertIn("oh-no-parent-control-hud-menu-actions", css)
        self.assertIn("width - source_width + stem_width / 2", chrome)
        self.assertNotIn("border-radius: 18px;", css)
        from oh_no_parent_control_kiosk.chrome import (
            ABOUT, HELP, MENU, SPEAKER, SPEAKER_MUTED,
        )

        for sprite in (HELP, ABOUT):
            self.assertEqual(len(sprite), 8)
            self.assertEqual(len(sprite[0]), 8)
        for sprite in (SPEAKER, SPEAKER_MUTED, MENU):
            self.assertEqual(len(sprite), 16)
            self.assertEqual(len(sprite[0]), 16)
        self.assertIn("BOARD_CHAIN_ANCHOR_SIDE_INSET = 12.0", chrome)
        self.assertIn("BOARD_CHAIN_ANCHOR_END_INSET = 34.0", chrome)
        self.assertIn("connector_x =", chrome)
        self.assertIn('panel_kind="header"', content)
        self.assertIn('panel_kind="well"', content)
        self.assertIn('panel_kind="footer"', content)
        self.assertIn('armor_kind="request"', content)
        self.assertIn('armor_kind="cancel"', content)
        self.assertIn("set_margin_start(10)", content)
        self.assertIn("set_margin_end(10)", content)
        self.assertIn("def _paint_block_texture(", chrome)
        self.assertIn("padding: 4px 8px;", css)
        self.assertIn("font-size: 14px;", css)
        self.assertIn("font-size: 0.90em;", css)
        self.assertIn("font-size: 0.92em;", css)
        self.assertIn("oh-no-parent-control-account-row-inner", content)
        self.assertIn("inner.set_margin_bottom(4)", content)
        self.assertIn("margin: 0;", css)
        self.assertIn("padding: 2px 0 0;", css)
        self.assertIn("oh-no-parent-control-choices-inner", content)
        self.assertIn("self._duration_box.set_margin_bottom(6)", content)
        self.assertIn("self._duration_box.set_margin_start(4)", content)
        self.assertIn("self._duration_box.set_margin_end(4)", content)
        self.assertNotIn("self._duration_box.set_margin_start(8)", content)
        self.assertNotIn("self._duration_box.set_margin_end(8)", content)
        self.assertIn("Insets are set on the FlowBox by RequestContent.", css)
        self.assertIn("padding: 2px 8px;", css)
        self.assertIn("font-size: 0.92em;", css)
        self.assertIn("min-height: 26px;", css)
        self.assertIn("min-height: 48px;", css)
        self.assertIn("oh-no-parent-control-status-inner", content)
        self.assertIn("margin: 4px 28px 8px 22px;", css)
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

    def test_form_controls_match_request_and_cancel_button_width(self):
        source = KIOSK_CONTENT.read_text(encoding="utf-8")
        css = (ROOT / "kiosk/oh_no_parent_control_kiosk/style.css").read_text(
            encoding="utf-8",
        )

        self.assertIn(
            'row = MetalPanel(spacing=0, panel_kind="metal", hexpand=True)',
            source,
        )
        self.assertIn("row.set_margin_start(10)", source)
        self.assertIn("row.set_margin_end(10)", source)
        self.assertIn("oh-no-parent-control-account-row-inner", source)
        self.assertIn("inner.set_margin_start(10)", source)
        self.assertIn("inner.set_margin_end(12)", source)
        self.assertIn("self._choices.set_margin_start(10)", source)
        self.assertIn("self._choices.set_margin_end(10)", source)
        self.assertIn("filter_row = Gtk.Button(hexpand=True)", source)
        self.assertIn("filter_row.set_margin_start(10)", source)
        self.assertIn("filter_row.set_margin_end(10)", source)
        self.assertIn('self._allow_soft, "Allow soft blocked apps",', source)
        self.assertIn("self._allow_soft = Gtk.Switch(valign=Gtk.Align.CENTER)", source)
        self.assertIn("self._allow_soft.set_can_target(False)", source)
        self.assertIn('filter_row.connect("clicked", self._toggle_allow_soft)', source)
        self.assertIn("def _toggle_allow_soft(self, _button):", source)
        self.assertIn(
            "button.oh-no-parent-control-app-filter-toggle:hover",
            css,
        )
        self.assertIn(".oh-no-parent-control-account-row {\n  min-width: 0;", css)
        self.assertIn(
            ".oh-no-parent-control-account-row {\n  min-width: 0;\n"
            "  margin-left: 0;\n  margin-right: 0;\n"
            "  padding: 0;\n  border: none;",
            css,
        )
        self.assertIn(
            ".oh-no-parent-control-account-row-inner {\n"
            "  /* The child widget owns these insets; adding CSS margins doubles them. */\n"
            "  margin: 0;",
            css,
        )
        self.assertIn(".oh-no-parent-control-choices {\n  min-width: 0;", css)
        self.assertIn(
            ".oh-no-parent-control-choices {\n  min-width: 0;\n"
            "  margin-left: 0;\n  margin-right: 0;",
            css,
        )
        self.assertIn(
            "button.oh-no-parent-control-app-filter-toggle {\n  min-width: 0;\n"
            "  min-height: 28px;\n  padding: 3px 6px;\n  margin-left: 0;\n"
            "  margin-right: 0;",
            css,
        )
        self.assertNotIn("min-width: 348px;", css)
        self.assertNotIn("min-width: 336px;", css)

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
            source.index("self.append(actions)"),
        )
        self.assertIn("self._screen_time_limit_enabled is True", source)
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
        form_snapshot = source.index("self.snapshot_child(self._viewport, snapshot)")
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

if __name__ == "__main__":
    unittest.main()
