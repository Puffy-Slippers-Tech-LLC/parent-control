import unittest

from parent.oh_no_parent_control_parent.main import (
    STATES, ParentWindow, _duration_label, _minutes_label, _time_status_subtitle,
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


if __name__ == "__main__":
    unittest.main()
