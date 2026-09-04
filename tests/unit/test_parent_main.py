import unittest
import inspect
from pathlib import Path
from unittest import mock

from parent.oh_no_parent_control_parent.main import (
    APPLICATION_ICON_NAME, CATALOG_ROW_BATCH_SIZE, CUSTOM_DAILY_LIMIT_INDEX, DAILY_LIMIT_PRESETS, MATCH_RULES, MAX_TIME_STATUS_RETRIES, PREVIEW_USERS, PreviewBrokerClient, STATES, ParentWindow, _can_start, _daily_limit_label, _daily_limit_selection, _duration_label, _minutes_label,
    PREVIEW_THUNDERBIRD_ICON, _time_status_subtitle,
)


class FakeDropDown:
    def __init__(self, owner):
        self.owner = owner
        self.blocked = False

    def handler_block(self, _handler):
        self.blocked = True

    def handler_unblock(self, _handler):
        self.blocked = False

    def set_model(self, _model):
        if not self.blocked:
            self.owner._account_changed()

    def set_selected(self, _index):
        if not self.blocked:
            self.owner._account_changed()


class FakeSensitiveWidget:
    def __init__(self, active=False):
        self.active = active
        self.sensitive = None

    def get_active(self):
        return self.active

    def set_sensitive(self, sensitive):
        self.sensitive = sensitive


class FakeVisibleWidget:
    def __init__(self):
        self.visible = False

    def set_visible(self, visible):
        self.visible = visible


class FakeToggleButton:
    def __init__(self, active):
        self.active = active

    def get_active(self):
        return self.active


class ParentWindowHarness:
    _users_loaded = ParentWindow._users_loaded
    _account_changed = ParentWindow._account_changed

    def __init__(self):
        self._users = []
        self._account_changed_handler = 1
        self._account = FakeDropDown(self)
        self._no_users_message = FakeVisibleWidget()
        self.load_count = 0
        self.apps_load_uids = []
        self.toasts = []

    def _ensure_apps_load(self, uid):
        self.apps_load_uids.append(uid)

    def _load_selected(self):
        self.load_count += 1

    def _toast(self, message):
        self.toasts.append(message)


class ParentWindowTests(unittest.TestCase):
    def test_runtime_icon_matches_the_installed_parent_desktop_icon(self):
        root = Path(__file__).resolve().parents[2]
        desktop_entry = (
            root / "data/applications/com.puffyslippers.OhNoParentControl.Parent.desktop"
        ).read_text(encoding="utf-8")

        self.assertIn(f"Icon={APPLICATION_ICON_NAME}", desktop_entry)
        self.assertIn(
            "self.set_icon_name(APPLICATION_ICON_NAME)",
            inspect.getsource(ParentWindow.__init__),
        )

    def test_preview_client_uses_fixture_data_and_persists_ui_changes_in_memory(self):
        client = PreviewBrokerClient()

        self.assertEqual(client.list_users(), PREVIEW_USERS)
        preferences = client.get_preferences(1001)
        preferences["daily_time_limit_minutes"] = 120
        client.set_preferences(1001, preferences)

        self.assertEqual(client.get_preferences(1001)["daily_time_limit_minutes"], 120)

    def test_preview_shows_the_three_policy_and_match_rule_combinations(self):
        client = PreviewBrokerClient()
        applications = {app["id"]: app for app in client.list_apps(1001)}
        policies = client.get_preferences(1001)["apps"]

        self.assertEqual(
            [(app_id, policies[app_id]["state"], bool(policies[app_id]["patterns"]))
             for app_id in (
                 "thunderbird_thunderbird.desktop",
                 "lunarclient.desktop",
                 "com.mojang.Minecraft.desktop",
             )],
            [
                ("thunderbird_thunderbird.desktop", "allowed", True),
                ("lunarclient.desktop", "permanent", True),
                ("com.mojang.Minecraft.desktop", "conditional", False),
            ],
        )
        self.assertEqual(
            applications["com.mojang.Minecraft.desktop"]["suggested_patterns"], [],
        )

    def test_preview_uses_the_bundled_thunderbird_icon(self):
        client = PreviewBrokerClient()
        applications = {app["id"]: app for app in client.list_apps(1001)}

        self.assertEqual(
            applications["thunderbird_thunderbird.desktop"]["icon"],
            PREVIEW_THUNDERBIRD_ICON,
        )
        self.assertTrue(Path(PREVIEW_THUNDERBIRD_ICON).is_file())

    def test_loading_an_exact_match_policy_accepts_an_empty_pattern_list(self):
        class SettableToggle:
            def set_active(self, _active):
                pass

        class ExactMatchRow:
            app = {"id": "calculator.desktop", "targets": ["/usr/bin/gnome-calculator"]}
            policy_buttons = {"conditional": SettableToggle()}
            user_saved_match_rule = False
            match_rule = "not-yet-loaded"

        class ExactMatchHarness:
            _preferences_loaded = ParentWindow._preferences_loaded
            _apply_app_policies = ParentWindow._apply_app_policies
            _default_match_rule = ParentWindow._default_match_rule
            _update_match_rule_icon = lambda self, _row: None
            _load_time_status = lambda self: None

            def __init__(self):
                self._enabled = SettableToggle()
                self._set_daily_limit_value = lambda *_args: None
                self._rows = [ExactMatchRow()]
                self._selected_uid = lambda: 1001
                self._loading = False
                self._set_apps_sensitive = lambda _sensitive: None
                self._update_apps_loading_ui = lambda: None
                self._filter = lambda *_args: None

        harness = ExactMatchHarness()
        harness._preferences_loaded({
            "parent_control_enabled": True,
            "daily_time_limit_minutes": 90,
            "apps": {"calculator.desktop": {"state": "conditional", "patterns": []}},
        })

        self.assertIsNone(harness._rows[0].match_rule)

    def test_parent_app_only_starts_when_broker_authorizes_its_caller(self):
        class AuthorizedClient:
            def list_users(self):
                return []

        class DeniedClient:
            def list_users(self):
                raise RuntimeError("administrator access is required")

        self.assertTrue(_can_start(AuthorizedClient))
        self.assertFalse(_can_start(DeniedClient))

    def test_app_policy_states_keep_the_original_three_state_visuals(self):
        self.assertEqual(
            [(state["id"], state["icon"], state["css"]) for state in STATES],
            [
                ("allowed", "emblem-ok-symbolic", "policy-allowed"),
                ("permanent", "window-close-symbolic", "policy-hard-blocked"),
                ("conditional", "dialog-warning-symbolic", "policy-soft-blocked"),
            ],
        )

    def test_parent_title_bar_uses_the_shared_product_logo(self):
        source = inspect.getsource(ParentWindow._build)
        stylesheet = (
            Path(__file__).resolve().parents[2]
            / "parent/oh_no_parent_control_parent/style.css"
        ).read_text(encoding="utf-8")

        self.assertIn('branding_asset_path("app_logo_gnome_launcher.png")', source)
        self.assertIn("title_logo.set_pixel_size(48)", source)
        self.assertIn('css_classes=["parent-title-brand"]', source)
        self.assertIn(".parent-title-brand image {", stylesheet)

    def test_match_rule_states_use_the_new_rule_icons_and_selected_button_classes(self):
        self.assertEqual(
            [(rule["id"], rule["glyph"], rule["css"]) for rule in MATCH_RULES],
            [
                ("pattern", "***", "match-rule-pattern"),
                ("precise", "ABC", "match-rule-precise"),
            ],
        )
        stylesheet = (
            Path(__file__).resolve().parents[2]
            / "parent/oh_no_parent_control_parent/style.css"
        ).read_text(encoding="utf-8")
        self.assertIn(".match-rule-button.match-rule-pattern {", stylesheet)
        self.assertIn(".match-rule-button.match-rule-precise {", stylesheet)
        self.assertIn(".match-rule-icon {\n  font-size: 16px;", stylesheet)
        self.assertIn("padding: 2px 1px 0;", stylesheet)
        self.assertIn(".match-rule-icon.match-rule-pattern {\n  font-size: 20px;", stylesheet)
        self.assertIn("padding-top: 3px;", stylesheet)
        self.assertIn("min-width: 36px;", stylesheet)
        self.assertNotIn(".match-rule-button.match-rule-pattern:hover", stylesheet)

    def test_app_policy_headings_use_measurement_matched_control_slots(self):
        source = inspect.getsource(ParentWindow._build)

        self.assertIn('self._match_rule_slot()', source)
        self.assertIn('self._policy_selector_slot()', source)
        self.assertIn('self._policy_column_heading(', source)

    def test_match_and_access_rule_headings_are_multi_select_filters(self):
        source = inspect.getsource(ParentWindow._policy_column_heading)
        stylesheet = (
            Path(__file__).resolve().parents[2]
            / "parent/oh_no_parent_control_parent/style.css"
        ).read_text(encoding="utf-8")
        build = inspect.getsource(ParentWindow._build)

        self.assertIn("Gtk.Popover(", source)
        self.assertIn("Gtk.CheckButton(", source)
        self.assertIn("popover.popup()", source)
        self.assertIn("icon_factory(item)", source)
        self.assertIn('css_classes=["app-policy-filter-item-label"]', source)
        self.assertIn("MATCH_RULES, self._match_rule_filters", build)
        self.assertIn("STATES, self._access_rule_filters", build)
        self.assertIn("self._match_rule_filter_icon", build)
        self.assertIn("self._access_rule_filter_icon", build)
        self.assertIn(".app-policy-filter {", stylesheet)
        self.assertIn(".app-policy-filter-item-label {", stylesheet)
        self.assertIn(
            ".match-rule-header .app-policy-filter {\n  margin-right: 41px;",
            stylesheet,
        )
        self.assertNotIn(
            ".match-rule-header .app-policy-column-header {",
            stylesheet,
        )

    def test_app_table_filters_rows_by_search_match_rule_and_access_rule(self):
        class FakeSearch:
            def get_text(self):
                return "calc"

        class VisibleRow:
            def __init__(self, search_text, match_rule, access):
                self.search_text = search_text
                self.match_rule = match_rule
                self.app = {
                    "targets": ["/usr/bin/gnome-calculator"],
                    "suggested_patterns": [],
                }
                self.policy_buttons = {
                    "allowed": FakeToggleButton(access == "allowed"),
                    "permanent": FakeToggleButton(access == "permanent"),
                    "conditional": FakeToggleButton(access == "conditional"),
                }
                self.visible = None

            def set_visible(self, visible):
                self.visible = visible

        shown = VisibleRow("calculator desktop", None, "conditional")
        hidden_search = VisibleRow("firefox desktop", None, "conditional")
        hidden_match = VisibleRow(
            "calc pattern", "/usr/lib/calc/calc-*.0", "conditional",
        )
        hidden_access = VisibleRow("calculator allowed", None, "allowed")
        window = type("WindowHarness", (), {})()
        window._search = FakeSearch()
        window._match_rule_filters = {"precise"}
        window._access_rule_filters = {"conditional"}
        window._rows = [shown, hidden_search, hidden_match, hidden_access]
        window._default_match_rule = lambda row: ParentWindow._default_match_rule(
            window, row,
        )
        window._is_pattern = ParentWindow._is_pattern
        window._row_match_rule_id = lambda row: ParentWindow._row_match_rule_id(
            window, row,
        )
        window._row_access_rule_id = ParentWindow._row_access_rule_id
        window._row_matches_filters = (
            lambda row, query: ParentWindow._row_matches_filters(window, row, query)
        )

        ParentWindow._filter(window)

        self.assertTrue(shown.visible)
        self.assertFalse(hidden_search.visible)
        self.assertFalse(hidden_match.visible)
        self.assertFalse(hidden_access.visible)

    def test_main_body_is_split_into_screen_and_app_limit_tabs(self):
        source = inspect.getsource(ParentWindow._build)

        account_picker = source.index("account_actions.append(self._account)")
        view_stack = source.index("pages = Adw.ViewStack")
        screen_tab = source.index(
            'screen_limits_page, "screen-limits", "Screen Limits", "alarm-symbolic"'
        )
        app_tab = source.index(
            'app_limits_page, "app-limits", "App Limits", "view-grid-symbolic"'
        )

        self.assertLess(account_picker, view_stack)
        self.assertLess(view_stack, screen_tab)
        self.assertLess(screen_tab, app_tab)
        self.assertIn("screen_limits_page.set_child(Adw.Clamp(", source)
        self.assertIn("screen_limits.append(screen_limit_rows)", source)
        self.assertIn("app_limits.append(self._legend_card())", source)
        self.assertIn("app_limits.append(apps_section)", source)
        self.assertIn("app_limits_page.set_child(Adw.Clamp(", source)

    def test_screen_limits_use_reference_card_and_calculation_layout(self):
        source = inspect.getsource(ParentWindow._build)
        stylesheet = (
            Path(__file__).resolve().parents[2]
            / "parent/oh_no_parent_control_parent/style.css"
        ).read_text(encoding="utf-8")

        self.assertIn('self._account.set_factory(self._account_factory())', source)
        factory = inspect.getsource(ParentWindow._account_factory)
        self.assertIn("Adw.Avatar(", factory)
        self.assertIn("Gdk.Texture.new_from_filename(icon_file)", factory)
        self.assertNotIn("👦🏻", factory)
        self.assertIn('self._time_status = Adw.ExpanderRow(', source)
        self.assertIn('self._time_status.add_suffix(self._time_status_value)', source)
        self.assertIn('self._time_status.add_row(self._time_calculation_panel())', source)
        self.assertEqual(source.count("maximum_size=CONTENT_MAX_WIDTH"), 4)
        self.assertIn(".account-picker {", stylesheet)
        self.assertIn('css_classes=["account-actions-separator"]', source)
        self.assertIn(".account-actions-separator {", stylesheet)
        self.assertIn("margin: 35px 0;", stylesheet)
        self.assertIn("margin: 18px 30px 18px 120px;", stylesheet)
        self.assertIn(".revoke-grant-button:hover {", stylesheet)
        self.assertIn(".revoke-grant-button:active {", stylesheet)
        self.assertIn('icon_name="action-unavailable-symbolic", pixel_size=40', source)
        self.assertIn("width_request=270, max_width_chars=36", source)
        self.assertIn("width_request=320", source)
        self.assertNotIn("revoke_icon.append", source)
        self.assertIn(".screen-limits-card-header {", stylesheet)
        self.assertIn(".screen-limit-switch:checked {", stylesheet)
        self.assertIn(".calculation-panel {", stylesheet)
        self.assertIn(".remaining-time-value {", stylesheet)

    def test_screen_limit_setting_icons_are_centered_in_their_tile(self):
        source = inspect.getsource(ParentWindow._setting_icon)

        self.assertIn("container = Gtk.CenterBox(", source)
        self.assertIn("container.set_center_widget(Gtk.Image(", source)

    def test_calculation_layout_groups_the_first_two_operands_in_max(self):
        source = inspect.getsource(ParentWindow._time_calculation_panel)

        self.assertIn('css_classes=["equation-maximum"]', source)
        self.assertIn('label="max("', source)
        self.assertIn('label=","', source)
        self.assertIn('label=")"', source)
        self.assertIn('label="+"', source)
        self.assertIn('label="="', source)

    def test_policy_selector_measurement_slot_is_fully_transparent(self):
        source = inspect.getsource(ParentWindow._policy_selector_slot)

        self.assertIn('opacity=0, css_classes=["policy-selector"]', source)

    def test_match_rule_control_is_centered_in_a_dedicated_cell(self):
        root = Path(__file__).resolve().parents[2]
        stylesheet = (
            root / "parent/oh_no_parent_control_parent/style.css"
        ).read_text(encoding="utf-8")
        source = inspect.getsource(ParentWindow._add_app_row)

        self.assertIn(".match-rule-cell {\n  min-width: 92px;", stylesheet)
        self.assertIn("width_request=92, halign=Gtk.Align.CENTER", source)

    def test_match_rule_button_uses_an_interactive_capsule(self):
        stylesheet = (
            Path(__file__).resolve().parents[2]
            / "parent/oh_no_parent_control_parent/style.css"
        ).read_text(encoding="utf-8")

        self.assertIn(".match-rule-button.policy-choice {", stylesheet)
        self.assertIn("min-height: 36px;", stylesheet)
        self.assertIn(".match-rule-button.policy-choice:hover {", stylesheet)
        self.assertIn("border-radius: 12px;", stylesheet)

    def test_app_limits_reference_layout_uses_one_wide_card(self):
        source = inspect.getsource(ParentWindow._build)
        initializer = inspect.getsource(ParentWindow.__init__)
        stylesheet = (
            Path(__file__).resolve().parents[2]
            / "parent/oh_no_parent_control_parent/style.css"
        ).read_text(encoding="utf-8")

        self.assertIn(
            "self.set_default_size(DEFAULT_WINDOW_WIDTH, 1168)", initializer,
        )
        self.assertIn('css_classes=["app-limits-card"]', source)
        self.assertIn('label="App Limits", xalign=0', source)
        self.assertIn('css_classes=["apps-section"]', source)
        self.assertIn('css_classes=["apps-panel"]', source)
        self.assertIn('css_classes=["apps-table-overlay"]', source)
        self.assertIn('css_classes=["apps-loading-mask"]', source)
        self.assertIn('label="Loading installed apps…"', source)
        self.assertIn(".app-limits-card {", stylesheet)
        self.assertIn(".apps-section {\n  margin: 16px 29px 16px;", stylesheet)
        self.assertIn(".apps-loading-mask {", stylesheet)
        self.assertIn(".policy-choice {\n  min-width: 36px;", stylesheet)

    def test_match_rule_legend_uses_normal_visual_state(self):
        source = inspect.getsource(ParentWindow._legend_section)

        self.assertIn("icon = Gtk.Button(", source)
        self.assertIn("can_focus=False, can_target=False", source)
        self.assertNotIn("sensitive=False", source)

    def test_legend_icons_use_the_same_dimensions_as_app_table_controls(self):
        stylesheet = (
            Path(__file__).resolve().parents[2]
            / "parent/oh_no_parent_control_parent/style.css"
        ).read_text(encoding="utf-8")
        source = inspect.getsource(ParentWindow._legend_section)

        self.assertNotIn(".policy-choice.policy-legend-icon {", stylesheet)
        self.assertNotIn(
            ".match-rule-button.policy-choice.policy-legend-icon {", stylesheet,
        )
        self.assertIn(".policy-choice {\n  min-width: 36px;\n  min-height: 36px;",
                      stylesheet)
        self.assertIn(
            ".match-rule-button.policy-choice {\n  min-width: 36px;\n"
            "  min-height: 36px;",
            stylesheet,
        )
        self.assertEqual(source.count("can_focus=False, can_target=False"), 2)

    def test_legend_is_one_collapsed_expandable_card(self):
        source = inspect.getsource(ParentWindow._legend_card)
        toggled = inspect.getsource(ParentWindow._legend_toggled)
        stylesheet = (
            Path(__file__).resolve().parents[2]
            / "parent/oh_no_parent_control_parent/style.css"
        ).read_text(encoding="utf-8")

        self.assertIn('label="Legend"', source)
        self.assertIn('active=False', source)
        self.assertIn('reveal_child=False', source)
        self.assertIn('"App Access (What happens)", STATES', source)
        self.assertIn('"Match Rule (How apps are matched)", MATCH_RULES', source)
        self.assertIn('orientation=Gtk.Orientation.VERTICAL', source)
        self.assertIn('card.add_css_class("expanded")', toggled)
        self.assertIn('.policy-legend.expanded {', stylesheet)

    def test_legend_book_icon_is_centered_in_its_tile(self):
        source = inspect.getsource(ParentWindow._legend_card)

        self.assertIn("book = Gtk.CenterBox(", source)
        self.assertIn("book.set_center_widget(Gtk.Image(", source)
        self.assertNotIn("hexpand=True, halign=Gtk.Align.CENTER", source)

    def test_daily_limit_labels_use_singular_only_for_one_minute(self):
        self.assertEqual(_minutes_label(0), "0 minutes")
        self.assertEqual(_minutes_label(1), "1 minute")
        self.assertEqual(_minutes_label(1440), "1440 minutes")

    def test_daily_limit_menu_has_requested_presets_and_custom_selection(self):
        self.assertEqual(DAILY_LIMIT_PRESETS[:4], (0, 15, 30, 45))
        self.assertEqual(DAILY_LIMIT_PRESETS[-1], 23 * 60 + 30)
        self.assertEqual(_daily_limit_label(90), "1.5 hours")
        self.assertEqual(_daily_limit_selection(30), (2, False))
        self.assertEqual(_daily_limit_selection(31), (CUSTOM_DAILY_LIMIT_INDEX, True))

    def test_time_status_explicitly_shows_formula_operands_and_result(self):
        subtitle = _time_status_subtitle({
            "daily_allowance_remaining_seconds": 31 * 60,
            "one_time_grant_remaining_seconds": 10 * 60,
            "additional_one_time_grant_seconds": 5 * 60,
            "calculated_active_extension_seconds": 36 * 60,
        })

        self.assertIn("Daily allowance remaining: 31m", subtitle)
        self.assertIn("One-time grant remaining: 10m", subtitle)
        self.assertIn("Additional one-time grant: 5m", subtitle)
        self.assertIn("max(31m, 10m) + 5m = 36m", subtitle)
        self.assertEqual(_duration_label(65), "1m 5s")

    def test_revoke_confirmation_discloses_that_the_child_is_locked(self):
        source = inspect.getsource(ParentWindow._confirm_revoke)

        self.assertIn("close their running blocked apps", source)
        self.assertIn("lock their desktop when no time remains", source)

    def test_revoke_is_disabled_when_authoritative_remaining_time_is_zero(self):
        class Label:
            def set_label(self, _label):
                pass

        window = type("WindowHarness", (), {})()
        window._time_status_loading = True
        window._time_status_refresh_pending = False
        window._time_status_retry_id = 0
        window._time_status_retry_count = 0
        window._cancel_time_status_retry = lambda: None
        window._load_pending_time_status_refresh = lambda: None
        window._selected_uid = lambda: 1001
        window._time_status_value = Label()
        window._time_operand_values = [Label(), Label(), Label(), Label()]
        window._loading = False
        window._account = FakeSensitiveWidget()
        window._revoke = FakeSensitiveWidget()
        window._enabled = FakeSensitiveWidget(active=True)
        window._daily_limit = FakeSensitiveWidget()
        window._apps_group = FakeSensitiveWidget()
        window._set_apps_sensitive = lambda sensitive: ParentWindow._set_apps_sensitive(
            window, sensitive,
        )

        ParentWindow._time_status_loaded(window, 1001, {
            "daily_allowance_remaining_seconds": 0,
            "one_time_grant_remaining_seconds": 0,
            "additional_one_time_grant_seconds": 0,
            "calculated_active_extension_seconds": 0,
        })

        self.assertEqual(window._remaining_time_seconds, 0)
        self.assertFalse(window._revoke.sensitive)

    def test_transient_time_status_failure_retries_before_showing_unavailable(self):
        class Label:
            def __init__(self, label):
                self.label = label

            def set_label(self, label):
                self.label = label

        window = type("WindowHarness", (), {
            "_retry_time_status": ParentWindow._retry_time_status,
        })()
        window._time_status_loading = True
        window._time_status_refresh_pending = False
        window._time_status_retry_id = 0
        window._time_status_retry_count = 0
        window._selected_uid = lambda: 1001
        window._time_status_value = Label("59 minutes")
        window._time_operand_values = [Label("59m") for _index in range(4)]
        window._load_time_status = mock.Mock()

        with mock.patch(
            "parent.oh_no_parent_control_parent.main.GLib.timeout_add_seconds",
            return_value=73,
        ) as timeout_add:
            ParentWindow._time_status_failed(window, 1001, RuntimeError("busy"))

        self.assertEqual(window._time_status_value.label, "59 minutes")
        self.assertEqual(window._time_status_retry_id, 73)
        retry_callback = timeout_add.call_args.args[1]
        self.assertEqual(retry_callback(), 0)
        window._load_time_status.assert_called_once_with(retry=True)

    def test_time_status_failure_shows_unavailable_after_bounded_retries(self):
        class Label:
            def __init__(self):
                self.label = "value"

            def set_label(self, label):
                self.label = label

        window = type("WindowHarness", (), {})()
        window._time_status_loading = True
        window._time_status_refresh_pending = False
        window._time_status_retry_id = 0
        window._time_status_retry_count = MAX_TIME_STATUS_RETRIES
        window._selected_uid = lambda: 1001
        window._time_status_value = Label()
        window._time_operand_values = [Label() for _index in range(4)]

        ParentWindow._time_status_failed(window, 1001, RuntimeError("busy"))

        self.assertEqual(window._time_status_value.label, "Unavailable")
        self.assertEqual(
            [label.label for label in window._time_operand_values], ["—"] * 4,
        )

    def test_overlapping_time_status_refresh_is_coalesced(self):
        window = type("WindowHarness", (), {})()
        window._time_status_loading = True
        window._time_status_refresh_pending = False
        window._selected_uid = lambda: 1001

        ParentWindow._load_time_status(window)

        self.assertTrue(window._time_status_refresh_pending)

    def test_loading_users_loads_initial_selection_once(self):
        window = ParentWindowHarness()

        window._users_loaded([(1001, "Child")])

        self.assertEqual(window.load_count, 1)
        self.assertEqual(window.apps_load_uids, [1001])

    def test_loading_no_users_does_not_load_preferences(self):
        window = ParentWindowHarness()

        window._users_loaded([])

        self.assertEqual(window.load_count, 0)
        self.assertEqual(window.apps_load_uids, [])
        self.assertTrue(window._no_users_message.visible)
        self.assertEqual(window.toasts, ["No interactive non-admin users were found"])

    def test_app_settings_stay_enabled_when_daily_limit_is_off(self):
        window = type("WindowHarness", (), {})()
        window._loading = False
        window._selected_uid = lambda: 1001
        window._account = FakeSensitiveWidget()
        window._revoke = FakeSensitiveWidget()
        window._enabled = FakeSensitiveWidget(active=False)
        window._daily_limit = FakeSensitiveWidget()
        window._apps_group = FakeSensitiveWidget()

        ParentWindow._set_apps_sensitive(window, True)

        self.assertTrue(window._apps_group.sensitive)
        self.assertFalse(window._daily_limit.sensitive)

    def test_selecting_an_app_policy_state_starts_an_auto_save(self):
        window = type("WindowHarness", (), {})()
        window._loading = False
        window.save_count = 0
        window._save_app_policy = lambda: setattr(
            window, "save_count", window.save_count + 1,
        )
        window._filter = lambda *_args: None

        ParentWindow._policy_changed(window, FakeToggleButton(active=True))

        self.assertEqual(window.save_count, 1)

    def test_filename_only_match_rule_uses_its_app_executable_directory(self):
        row = type("PolicyRow", (), {})()
        row.app = {"targets": ["/home/child/Applications/Lunar Client.AppImage"]}

        self.assertEqual(
            ParentWindow._canonical_match_rule(row, "*Lunar*Client*"),
            "/home/child/Applications/*Lunar*Client*",
        )

    def test_app_policy_uses_the_current_daily_limit(self):
        class FakePolicyButton:
            def get_active(self):
                return True

        row = type("PolicyRow", (), {})()
        row.app = {"id": "example.desktop", "targets": ["example"]}
        row.policy_buttons = {
            "allowed": FakePolicyButton(),
            "permanent": FakeToggleButton(active=False),
            "conditional": FakeToggleButton(active=False),
        }
        row.user_saved_match_rule = False
        row.match_rule = None
        window = type("WindowHarness", (), {})()
        window._preferences = {
            "daily_time_limit_minutes": 30,
            "apps": {},
        }
        window._daily_limit_minutes = lambda: 60
        window._rows = [row]

        value = ParentWindow._app_policy_value(window)

        self.assertEqual(value["daily_time_limit_minutes"], 60)

    def test_app_policy_preserves_unlisted_launchers(self):
        row = type("PolicyRow", (), {})()
        row.app = {"id": "visible.desktop", "targets": ["/usr/bin/visible"]}
        row.policy_buttons = {
            "allowed": FakeToggleButton(active=True),
            "permanent": FakeToggleButton(active=False),
            "conditional": FakeToggleButton(active=False),
        }
        row.user_saved_match_rule = False
        row.match_rule = None
        window = type("WindowHarness", (), {})()
        window._preferences = {
            "daily_time_limit_minutes": 30,
            "apps": {
                "gone.desktop": {
                    "state": "permanent", "targets": ["/opt/gone.AppImage"],
                },
            },
        }
        window._daily_limit_minutes = lambda: 30
        window._rows = [row]

        value = ParentWindow._app_policy_value(window)

        self.assertEqual(value["apps"], window._preferences["apps"])

    def test_completed_auto_save_does_not_reload_the_widgets(self):
        window = type("WindowHarness", (), {})()
        window._save_in_progress = True
        window._pending_saves = []
        window._selected_uid = lambda: 1001
        window._preferences_loaded = lambda _preferences: self.fail("unexpected reload")
        window._start_next_save = lambda: None

        preferences = {"apps": {"example.desktop": {"state": "conditional"}}}
        ParentWindow._save_succeeded(window, 1001, preferences)

        self.assertFalse(window._save_in_progress)
        self.assertEqual(window._preferences, preferences)

    def test_selected_account_loads_apps_independently_of_preferences(self):
        source = inspect.getsource(ParentWindow._load_selected)

        self.assertIn("self._ensure_apps_load(uid)", source)
        self.assertIn("self._client.get_preferences(uid)", source)
        self.assertNotIn("self._client.list_apps(uid)", source)
        self.assertLess(
            source.index("self._ensure_apps_load(uid)"),
            source.index("self._client.get_preferences(uid)"),
        )
        self.assertEqual(CATALOG_ROW_BATCH_SIZE, 8)

    def test_app_catalog_is_cached_until_the_app_limits_tab_is_shown(self):
        window = type("WindowHarness", (), {
            "_apps_loaded": ParentWindow._apps_loaded,
            "_apps_mask_should_show": ParentWindow._apps_mask_should_show,
            "_maybe_populate_app_table": ParentWindow._maybe_populate_app_table,
        })()
        window._apps_load_generation = 1
        window._selected_uid = lambda: 1001
        window._app_limits_visible = False
        window._apps_loading = True
        window._catalog_building = False
        window._apps_table_ready = False
        window._preferences = {"apps": {}}
        window._app_catalog = None
        window.catalog_sets = 0
        window.ui_updates = 0
        window._set_catalog = lambda _apps: setattr(
            window, "catalog_sets", window.catalog_sets + 1,
        )
        window._update_apps_loading_ui = lambda: setattr(
            window, "ui_updates", window.ui_updates + 1,
        )

        ParentWindow._apps_loaded(window, 1001, 1, [{"id": "one.desktop"}])

        self.assertFalse(window._apps_loading)
        self.assertEqual(window._app_catalog[0]["id"], "one.desktop")
        self.assertEqual(window.catalog_sets, 0)
        self.assertFalse(window._apps_mask_should_show())

        window._app_limits_visible = True
        self.assertTrue(window._apps_mask_should_show())
        ParentWindow._maybe_populate_app_table(window)
        self.assertEqual(window.catalog_sets, 1)

    def test_app_limits_tab_keeps_the_table_masked_until_rows_are_ready(self):
        window = type("WindowHarness", (), {
            "_apps_mask_should_show": ParentWindow._apps_mask_should_show,
            "_visible_page_changed": ParentWindow._visible_page_changed,
        })()
        window._pages = type("Pages", (), {
            "get_visible_child_name": lambda self: "app-limits",
        })()
        window._app_limits_visible = False
        window._apps_loading = True
        window._catalog_building = False
        window._apps_table_ready = False
        window._preferences = None
        window._app_catalog = None
        window._maybe_populate_app_table = lambda: None
        window.mask_visible = None
        window.spinner_spinning = None
        window._apps_loading_mask = type("Mask", (), {
            "set_visible": lambda self, visible: setattr(window, "mask_visible", visible),
        })()
        window._apps_loading_spinner = type("Spinner", (), {
            "set_spinning": lambda self, spinning: setattr(
                window, "spinner_spinning", spinning,
            ),
        })()
        window._update_apps_loading_ui = lambda: ParentWindow._update_apps_loading_ui(
            window,
        )

        with mock.patch(
            "parent.oh_no_parent_control_parent.main.GLib.idle_add",
        ) as idle_add:
            ParentWindow._visible_page_changed(window)

        self.assertTrue(window._app_limits_visible)
        self.assertTrue(window._apps_mask_should_show())
        self.assertTrue(window.mask_visible)
        self.assertTrue(window.spinner_spinning)
        idle_add.assert_called_once_with(window._maybe_populate_app_table)

        window._apps_loading = False
        window._app_catalog = []
        window._catalog_building = False
        window._apps_table_ready = True
        window._preferences = {"apps": {}}
        window._update_apps_loading_ui()
        self.assertFalse(window._apps_mask_should_show())
        self.assertFalse(window.mask_visible)
        self.assertFalse(window.spinner_spinning)

    def test_stale_app_catalog_results_are_ignored_after_account_change(self):
        window = type("WindowHarness", (), {
            "_apps_loaded": ParentWindow._apps_loaded,
            "_apps_failed": ParentWindow._apps_failed,
        })()
        window._apps_load_generation = 2
        window._selected_uid = lambda: 1002
        window._apps_loading = True
        window._app_catalog = None
        window._update_apps_loading_ui = lambda: None
        window._maybe_populate_app_table = lambda: None

        ParentWindow._apps_loaded(window, 1001, 1, [{"id": "stale.desktop"}])
        ParentWindow._apps_failed(window, 1001, 1, RuntimeError("gone"))

        self.assertTrue(window._apps_loading)
        self.assertIsNone(window._app_catalog)


if __name__ == "__main__":
    unittest.main()
