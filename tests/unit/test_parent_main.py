import unittest
import inspect
from pathlib import Path

from parent.oh_no_parent_control_parent.main import (
    APPLICATION_ICON_NAME, MATCH_RULES, PREVIEW_USERS, PreviewBrokerClient, STATES, ParentWindow, _can_start, _duration_label, _minutes_label,
    _time_status_subtitle,
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
        self.load_count = 0
        self.toasts = []

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
                 "org.gnome.Software.desktop",
                 "org.gnome.Epiphany.desktop",
                 "org.gnome.Calculator.desktop",
             )],
            [
                ("org.gnome.Software.desktop", "allowed", True),
                ("org.gnome.Epiphany.desktop", "permanent", True),
                ("org.gnome.Calculator.desktop", "conditional", False),
            ],
        )
        self.assertEqual(
            applications["org.gnome.Calculator.desktop"]["suggested_patterns"], [],
        )

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
            _default_match_rule = ParentWindow._default_match_rule
            _update_match_rule_icon = lambda self, _row: None
            _load_time_status = lambda self: None

            def __init__(self):
                self._enabled = SettableToggle()
                self._daily_limit = type("DailyLimit", (), {"set_selected": lambda *_args: None})()
                self._rows = [ExactMatchRow()]
                self._selected_uid = lambda: 1001
                self._set_apps_sensitive = lambda _sensitive: None

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

    def test_main_body_is_split_into_screen_and_app_limit_tabs(self):
        source = inspect.getsource(ParentWindow._build)

        account_picker = source.index("account_section.append(self._account)")
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
        self.assertIn('self._time_status = Adw.ExpanderRow(', source)
        self.assertIn('self._time_status.add_suffix(self._time_status_value)', source)
        self.assertIn('self._time_status.add_row(self._time_calculation_panel())', source)
        self.assertEqual(source.count("maximum_size=CONTENT_MAX_WIDTH"), 4)
        self.assertIn(".account-picker {", stylesheet)
        self.assertIn(".screen-limits-card-header {", stylesheet)
        self.assertIn(".screen-limit-switch:checked {", stylesheet)
        self.assertIn(".calculation-panel {", stylesheet)
        self.assertIn(".remaining-time-value {", stylesheet)

    def test_policy_selector_measurement_slot_is_fully_transparent(self):
        source = inspect.getsource(ParentWindow._policy_selector_slot)

        self.assertIn('opacity=0, css_classes=["policy-selector"]', source)

    def test_match_rule_control_is_centered_in_a_dedicated_cell(self):
        root = Path(__file__).resolve().parents[2]
        stylesheet = (
            root / "parent/oh_no_parent_control_parent/style.css"
        ).read_text(encoding="utf-8")
        source = inspect.getsource(ParentWindow._set_catalog)

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
        self.assertIn(".app-limits-card {", stylesheet)
        self.assertIn(".apps-section {\n  margin: 16px 29px 16px;", stylesheet)
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

    def test_daily_limit_labels_use_singular_only_for_one_minute(self):
        self.assertEqual(_minutes_label(0), "0 minutes")
        self.assertEqual(_minutes_label(1), "1 minute")
        self.assertEqual(_minutes_label(1440), "1440 minutes")

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

    def test_loading_users_loads_initial_selection_once(self):
        window = ParentWindowHarness()

        window._users_loaded([(1001, "Child")])

        self.assertEqual(window.load_count, 1)

    def test_loading_no_users_does_not_load_preferences(self):
        window = ParentWindowHarness()

        window._users_loaded([])

        self.assertEqual(window.load_count, 0)
        self.assertEqual(window.toasts, ["No interactive non-admin users were found"])

    def test_app_settings_stay_enabled_when_daily_limit_is_off(self):
        window = type("WindowHarness", (), {})()
        window._loading = False
        window._selected_uid = lambda: 1001
        window._account = FakeSensitiveWidget()
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
        window._daily_limit = type("DailyLimit", (), {"get_selected": lambda _self: 60})()
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
        window._daily_limit = type("DailyLimit", (), {"get_selected": lambda _self: 30})()
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


if __name__ == "__main__":
    unittest.main()
