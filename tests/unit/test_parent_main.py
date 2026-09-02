import unittest
import inspect
from pathlib import Path

from parent.oh_no_parent_control_parent.main import (
    APPLICATION_ICON_NAME, PREVIEW_USERS, PreviewBrokerClient, STATES, ParentWindow, _can_start, _duration_label, _minutes_label,
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
