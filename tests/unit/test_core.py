import threading
import unittest
from datetime import datetime
from zoneinfo import ZoneInfo

from oh_no_parent_control.config import validate
from oh_no_parent_control.core import (
    AccessDenied, BackendFailure, Broker, Busy, InvalidRequest, RateLimited, RollbackFailure,
    UserAccount, calculate_active_extension_seconds, format_requested_duration,
    seconds_until_local_midnight,
)
from test_config import valid_config
from oh_no_parent_control.preferences import (
    PreferencesError, default_preferences, validate_preferences,
)


class Authorizer:
    def __init__(self, outcome="approved", callback=None):
        self.outcome = outcome
        self.calls = []
        self.callback = callback

    def check(self, request_kind, sender, correlation_id, target_label, approver_username,
              requested_duration, allow_soft_blocked_apps):
        self.calls.append((
            request_kind, sender, correlation_id, target_label, approver_username,
            requested_duration, allow_soft_blocked_apps,
        ))
        if self.callback:
            self.callback()
        return self.outcome


class Accounts:
    def __init__(self):
        self.users = {
            1001: UserAccount(1001, "child", "Child", False, False, True),
            1002: UserAccount(1002, "other", "Other", False, False, True),
            1003: UserAccount(1003, "admin", "Admin", True, False, True),
            1004: UserAccount(1004, "system", "System", False, True, True),
            1005: UserAccount(1005, "remote", "Remote", False, False, False),
            991: UserAccount(991, "kiosk", "Kiosk", False, False, True),
        }
        self.filter = (False, ("old.App",))
        self.extension = (1, 2)
        self.limit_type = 2
        self.daily_limit = 3600
        self.events = []
        self.fail_extension = False
        self.fail_rollback = False
        self.fail_limit_type = False

    def list_users(self):
        return tuple(self.users.values())

    def get_user(self, uid):
        return self.users[uid]

    def get_filter(self, uid):
        self.events.append(("get_filter", uid))
        return self.filter

    def set_filter(self, uid, value):
        self.events.append(("set_filter", uid, value))
        if self.fail_rollback and value == (False, ("old.App",)):
            raise RuntimeError("rollback failed")
        self.filter = value

    def get_extension(self, uid):
        self.events.append(("get_extension", uid))
        return self.extension

    def set_extension(self, uid, value):
        self.events.append(("set_extension", uid, value))
        if self.fail_extension and value != (1, 2):
            raise RuntimeError("failed")
        self.extension = value

    def get_limit_type(self, uid):
        self.events.append(("get_limit_type", uid))
        return self.limit_type

    def set_limit_type(self, uid, value):
        self.events.append(("set_limit_type", uid, value))
        if self.fail_limit_type and value != self.limit_type:
            raise RuntimeError("failed")
        self.limit_type = value

    def get_daily_limit(self, uid):
        self.events.append(("get_daily_limit", uid))
        return self.daily_limit

    def set_daily_limit(self, uid, value):
        self.events.append(("set_daily_limit", uid, value))
        self.daily_limit = value

    def clear_session_runtime_max(self, uid):
        self.events.append(("clear-runtime-max", uid))
        return (f"session-{uid}.scope",)


class Preferences:
    def __init__(self):
        self.values = {}
        value = default_preferences()
        value["apps"] = {
            "game.desktop": {"state": "permanent", "targets": ["org.example.Game"], "patterns": [], "user_saved_match_rule": False},
            "soft.desktop": {"state": "conditional", "targets": ["/usr/bin/game"], "patterns": [], "user_saved_match_rule": False},
        }
        self.values[1001] = value

    def load(self, uid):
        return validate_preferences(self.values.get(uid, default_preferences()))

    def save(self, uid, value):
        self.values[uid] = validate_preferences(value)
        return self.load(uid)

    def update_request(self, uid, selected, custom, allow_soft,
                       last_selected_approver_uid=0):
        value = self.load(uid)
        value["request"] = {
            **value["request"],
            "last_selected_duration": selected,
            "last_custom_minutes": custom,
            "allow_soft_blocked_apps": allow_soft,
            "last_selected_approver_uid": last_selected_approver_uid,
        }
        return self.save(uid, value)

    def update_request_muted(self, uid, surface, muted):
        value = self.load(uid)
        key = "kiosk_muted" if surface == "kiosk" else "child_muted"
        value["request"] = {**value["request"], key: muted}
        return self.save(uid, value)


class Extensions:
    def __init__(self):
        self.calls = []

    def set_enabled(self, uid, enabled):
        self.calls.append((uid, enabled))


class TimerUsage:
    def __init__(self, entries=(), callback=None, error=None):
        self.entries = tuple(entries)
        self.calls = []
        self.as_calls = []
        self.callback = callback
        self.error = error

    def query_usage(self, uid):
        self.calls.append(uid)
        return self.entries

    def query_usage_as(self, uid, approver):
        self.as_calls.append((uid, approver.uid, approver.username))
        if self.callback:
            self.callback()
        if self.error:
            raise self.error
        return self.entries


def make_broker(authorizer=None, accounts=None, preferences=None, extensions=None,
                clock=None, alive=lambda _s: True, timer_usage=None,
                application_catalog=None):
    config = validate(valid_config())
    return Broker(lambda: config, authorizer or Authorizer(), accounts or Accounts(),
                  preferences or Preferences(), extensions, timer_usage or TimerUsage(),
                  application_catalog,
                  monotonic=clock or (lambda: 100),
                  now=lambda: datetime(2026, 8, 30, 10, tzinfo=ZoneInfo("America/Los_Angeles")),
                  caller_alive=alive)


class CoreTests(unittest.TestCase):
    def test_startup_refreshes_only_preference_enabled_managed_children(self):
        accounts, preferences, extensions = Accounts(), Preferences(), Extensions()
        preferences.values[1001]["parent_control_enabled"] = True
        preferences.values[1003] = default_preferences()
        preferences.values[1003]["parent_control_enabled"] = True
        broker = make_broker(
            accounts=accounts, preferences=preferences, extensions=extensions,
        )

        refreshed = broker.refresh_enabled_extensions()

        self.assertEqual(refreshed, (1001,))
        self.assertEqual(extensions.calls, [(1001, True)])

    def test_startup_extension_refresh_reports_install_failure(self):
        class FailingExtensions(Extensions):
            def set_enabled(self, uid, enabled):
                raise RuntimeError("copy failed")

        preferences = Preferences()
        preferences.values[1001]["parent_control_enabled"] = True

        with self.assertRaisesRegex(
                BackendFailure, "could not refresh the child extension for uid 1001"):
            make_broker(
                preferences=preferences, extensions=FailingExtensions(),
            ).refresh_enabled_extensions()

    def test_application_catalog_is_scoped_to_the_selected_managed_user(self):
        observed = []
        broker = make_broker(application_catalog=lambda user: observed.append(user) or ({
            "id": "lunarclient.desktop", "name": "Lunar Client",
            "description": "Minecraft client", "icon": "",
            "targets": ("/home/child/Applications/LunarClient.AppImage",),
        },))

        applications = broker.list_applications(1003, 1001)

        self.assertEqual(observed[0].uid, 1001)
        self.assertEqual(applications[0]["targets"],
                         ("/home/child/Applications/LunarClient.AppImage",))

    def test_application_catalog_requires_administrator_access(self):
        broker = make_broker(application_catalog=lambda _user: ())

        with self.assertRaises(AccessDenied):
            broker.list_applications(1002, 1001)

    def test_requested_duration_is_human_readable_for_polkit(self):
        self.assertEqual(format_requested_duration(3 * 60 * 60 + 2 * 60), "3 hours, 2 minutes")
        self.assertEqual(format_requested_duration(60), "1 minute")
        self.assertEqual(format_requested_duration(6), "6 seconds")
        self.assertEqual(format_requested_duration(0), "the rest of the day")

    def test_remaining_time_formula_uses_later_backend_expiry_then_adds_grant(self):
        self.assertEqual(calculate_active_extension_seconds(31 * 60, 10 * 60, 5 * 60),
                         36 * 60)
        self.assertEqual(calculate_active_extension_seconds(10 * 60, 31 * 60, 5 * 60),
                         36 * 60)

    def test_time_status_reports_formula_operands_and_calculated_extension(self):
        now = datetime(2026, 8, 30, 10, tzinfo=ZoneInfo("America/Los_Angeles"))
        start_of_day = datetime(2026, 8, 30, tzinfo=now.tzinfo)
        accounts, preferences = Accounts(), Preferences()
        preferences.values[1001]["parent_control_enabled"] = True
        preferences.values[1001]["daily_time_limit_minutes"] = 32
        accounts.extension = (int(now.timestamp()), 10 * 60)
        timer_usage = TimerUsage((
            (int(start_of_day.timestamp()) - 60, int(start_of_day.timestamp()) + 30),
            (int(start_of_day.timestamp()) + 60, int(start_of_day.timestamp()) + 90),
        ))

        status = make_broker(
            accounts=accounts, preferences=preferences, timer_usage=timer_usage,
        ).get_time_status(1003, 1001, 5 * 60)

        self.assertEqual(status.daily_allowance_remaining_seconds, 31 * 60)
        self.assertEqual(status.one_time_grant_remaining_seconds, 10 * 60)
        self.assertEqual(status.additional_one_time_grant_seconds, 5 * 60)
        self.assertEqual(status.calculated_active_extension_seconds, 36 * 60)

    def test_child_remaining_time_uses_backend_grant_not_a_cached_claim(self):
        now = datetime(2026, 8, 30, 10, tzinfo=ZoneInfo("America/Los_Angeles"))
        accounts = Accounts()
        accounts.extension = (int(now.timestamp()) - 60, 10 * 60)
        broker = make_broker(accounts=accounts)

        self.assertEqual(broker.calculate_own_remaining_time(1001, 2 * 60), 9 * 60)
        accounts.extension = (0, 0)
        self.assertEqual(broker.calculate_own_remaining_time(1001, 2 * 60), 2 * 60)

    def test_admin_cannot_use_child_owned_remaining_time_endpoint(self):
        with self.assertRaises(AccessDenied):
            make_broker().calculate_own_remaining_time(1003, 0)

    def test_list_exposes_only_local_standard_accounts(self):
        users = make_broker().list_managed_users(991)
        self.assertEqual([(user.uid, user.label) for user in users], [
            (1001, "Child"), (1002, "Other"),
        ])

    def test_live_session_runtime_caps_are_cleared_only_for_managed_children(self):
        accounts = Accounts()
        broker = make_broker(accounts=accounts)

        self.assertEqual(broker.clear_live_session_runtime_caps(), (1001, 1002))
        self.assertEqual(
            [event for event in accounts.events if event[0] == "clear-runtime-max"],
            [("clear-runtime-max", 1001), ("clear-runtime-max", 1002)],
        )

    def test_list_approvers_exposes_only_local_interactive_administrators(self):
        accounts = Accounts()
        accounts.users[1004] = UserAccount(
            1004, "system-admin", "System Admin", True, True, True,
        )
        accounts.users[1005] = UserAccount(
            1005, "remote-admin", "Remote Admin", True, False, False,
        )
        accounts.users[1006] = UserAccount(
            1006, "locked-admin", "Locked Admin", True, False, True, True,
        )
        users = make_broker(accounts=accounts).list_approvers(991)
        self.assertEqual([(user.uid, user.label) for user in users], [(1003, "Admin")])

    def test_managed_child_can_list_approvers_for_its_own_request(self):
        users = make_broker().list_approvers(1001)
        self.assertEqual([(user.uid, user.label) for user in users], [(1003, "Admin")])

    def test_wrong_caller_denied(self):
        with self.assertRaises(AccessDenied):
            make_broker().list_managed_users(1001)

    def test_component_log_access_matches_caller_role(self):
        broker = make_broker()
        for caller_uid, component in (
            (1003, "parent"), (991, "kiosk"), (1001, "child"),
        ):
            with self.subTest(caller_uid=caller_uid, component=component):
                broker.authorize_log_component(caller_uid, component)
        for caller_uid, component in (
            (1001, "parent"), (1003, "child"), (991, "child"),
            (1003, "broker"), (1001, "unknown"),
        ):
            with self.subTest(caller_uid=caller_uid, component=component):
                with self.assertRaises(AccessDenied):
                    broker.authorize_log_component(caller_uid, component)

    def test_preferences_are_scoped_by_role(self):
        broker = make_broker()
        self.assertEqual(broker.get_preferences(1001, 1001)["version"], 3)
        self.assertEqual(broker.get_preferences(991, 1001)["version"], 3)
        self.assertEqual(broker.get_preferences(1003, 1001)["version"], 3)
        with self.assertRaises(AccessDenied):
            broker.get_preferences(1002, 1001)

    def test_only_admin_can_save_policy_or_toggle_extension(self):
        preferences, extensions = Preferences(), Extensions()
        broker = make_broker(preferences=preferences, extensions=extensions)
        value = preferences.load(1001)
        with self.assertRaises(AccessDenied):
            broker.set_preferences(1001, 1001, value)
        with self.assertRaises(AccessDenied):
            broker.set_parent_control(1001, 1001, True, 60)
        saved = broker.set_parent_control(1003, 1001, True, 60)
        self.assertTrue(saved["parent_control_enabled"])
        self.assertEqual(saved["daily_time_limit_minutes"], 60)
        self.assertEqual(extensions.calls, [(1001, True)])

    def test_enabling_parent_control_initializes_exhausted_account(self):
        accounts, preferences, extensions = Accounts(), Preferences(), Extensions()
        accounts.limit_type = 0
        accounts.daily_limit = 7200

        make_broker(
            accounts=accounts, preferences=preferences, extensions=extensions,
        ).set_parent_control(1003, 1001, True, 120)

        self.assertEqual(accounts.limit_type, 2)
        self.assertEqual(accounts.daily_limit, 7200)
        self.assertEqual(
            accounts.filter,
            (False, ("/usr/bin/game", "org.example.Game")),
        )
        self.assertEqual(accounts.extension, (0, 0))

    def test_disabling_daily_limit_removes_only_time_restrictions(self):
        accounts, preferences, extensions = Accounts(), Preferences(), Extensions()
        preferences.values[1001]["parent_control_enabled"] = True

        saved = make_broker(
            accounts=accounts, preferences=preferences, extensions=extensions,
        ).set_parent_control(1003, 1001, False, 90)

        self.assertFalse(saved["parent_control_enabled"])
        self.assertEqual(saved["daily_time_limit_minutes"], 90)
        self.assertEqual(accounts.limit_type, 0)
        self.assertEqual(accounts.daily_limit, 0)
        self.assertEqual(
            accounts.filter,
            (False, ("/usr/bin/game", "org.example.Game")),
        )
        self.assertEqual(accounts.extension, (0, 0))
        self.assertEqual(extensions.calls, [(1001, False)])

    def test_parent_control_failure_restores_account_and_extension(self):
        accounts, preferences, extensions = Accounts(), Preferences(), Extensions()
        accounts.limit_type = 0
        accounts.fail_limit_type = True

        with self.assertRaises(BackendFailure):
            make_broker(
                accounts=accounts, preferences=preferences, extensions=extensions,
            ).set_parent_control(1003, 1001, True, 60)

        self.assertFalse(preferences.load(1001)["parent_control_enabled"])
        self.assertEqual(accounts.limit_type, 0)
        self.assertEqual(accounts.daily_limit, 3600)
        self.assertEqual(accounts.filter, (False, ("old.App",)))
        self.assertEqual(accounts.extension, (1, 2))
        self.assertEqual(extensions.calls, [(1001, True), (1001, False)])

    def test_daily_limit_requires_integer_in_range_before_writes(self):
        accounts, extensions = Accounts(), Extensions()
        broker = make_broker(accounts=accounts, extensions=extensions)

        for value in (-1, 1441, 1.5, True):
            with self.subTest(value=value):
                with self.assertRaises(InvalidRequest):
                    broker.set_parent_control(1003, 1001, True, value)

        self.assertEqual(accounts.events, [])
        self.assertEqual(extensions.calls, [])

    def test_admin_can_revoke_a_grant_without_changing_daily_allowance(self):
        accounts = Accounts()
        accounts.extension = (123, 900)
        accounts.filter = (False, ("org.example.Game",))

        make_broker(accounts=accounts).revoke_one_time_grant(1003, 1001)

        self.assertEqual(accounts.extension, (0, 0))
        self.assertEqual(
            accounts.filter,
            (False, ("/usr/bin/game", "org.example.Game")),
        )
        self.assertEqual(accounts.limit_type, 2)
        self.assertEqual(accounts.daily_limit, 3600)

    def test_changing_daily_limit_preserves_active_grant_and_reapplies_filter(self):
        accounts, preferences, extensions = Accounts(), Preferences(), Extensions()
        preferences.values[1001]["parent_control_enabled"] = True

        saved = make_broker(
            accounts=accounts, preferences=preferences, extensions=extensions,
        ).set_parent_control(1003, 1001, True, 1440)

        self.assertEqual(saved["daily_time_limit_minutes"], 1440)
        self.assertEqual(accounts.daily_limit, 24 * 60 * 60)
        self.assertEqual(
            accounts.filter,
            (False, ("/usr/bin/game", "org.example.Game")),
        )
        self.assertEqual(accounts.extension, (1, 2))
        self.assertEqual(extensions.calls, [])

    def test_saving_app_policy_applies_filter_when_daily_limit_is_disabled(self):
        accounts, preferences = Accounts(), Preferences()
        value = preferences.load(1001)
        self.assertFalse(value["parent_control_enabled"])

        saved = make_broker(
            accounts=accounts, preferences=preferences,
        ).set_preferences(1003, 1001, value)

        self.assertFalse(saved["parent_control_enabled"])
        self.assertEqual(
            accounts.filter,
            (False, ("/usr/bin/game", "org.example.Game")),
        )

    def test_saving_app_policy_refreshes_target_after_app_self_update(self):
        accounts, preferences = Accounts(), Preferences()
        value = preferences.load(1001)
        value["apps"] = {
            "lunarclient.desktop": {
                "state": "conditional",
                "targets": [
                    "/home/child/Applications/Lunar Client-3.7.13.AppImage",
                ],
                "patterns": [],
                "user_saved_match_rule": False,
            },
        }
        catalog = lambda _user: ({
            "id": "lunarclient.desktop",
            "name": "Lunar Client",
            "description": "Minecraft client",
            "icon": "",
            "targets": (
                "/home/child/Applications/Lunar Client-3.7.17.AppImage",
            ),
        },)

        saved = make_broker(
            accounts=accounts, preferences=preferences,
            application_catalog=catalog,
        ).set_preferences(1003, 1001, value)

        expected = "/home/child/Applications/Lunar Client-3.7.17.AppImage"
        self.assertEqual(
            saved["apps"]["lunarclient.desktop"]["targets"], [expected],
        )
        self.assertEqual(accounts.filter, (False, (expected,)))

    def test_app_policy_refresh_preserves_policy_for_missing_launcher(self):
        accounts, preferences = Accounts(), Preferences()
        value = preferences.load(1001)

        saved = make_broker(
            accounts=accounts, preferences=preferences,
            application_catalog=lambda _user: (),
        ).set_preferences(1003, 1001, value)

        self.assertEqual(saved["apps"], value["apps"])
        self.assertEqual(
            accounts.filter,
            (False, ("/usr/bin/game", "org.example.Game")),
        )

    def test_app_policy_save_failure_restores_live_filter(self):
        class FailingPreferences(Preferences):
            def save(self, uid, value):
                raise PreferencesError("failed")

        accounts = Accounts()
        preferences = FailingPreferences()

        with self.assertRaises(BackendFailure):
            make_broker(
                accounts=accounts, preferences=preferences,
            ).set_preferences(1003, 1001, preferences.load(1001))

        self.assertEqual(accounts.filter, (False, ("old.App",)))

    def test_disabling_daily_limit_reapplies_saved_app_filter(self):
        accounts, preferences, extensions = Accounts(), Preferences(), Extensions()
        # A prior one-off extension allowed soft-blocked applications.
        accounts.filter = (False, ("org.example.Game",))
        broker = make_broker(
            accounts=accounts, preferences=preferences, extensions=extensions,
        )

        broker.set_parent_control(1003, 1001, True, 60)
        broker.set_parent_control(1003, 1001, False, 60)

        self.assertEqual(
            accounts.filter,
            (False, ("/usr/bin/game", "org.example.Game")),
        )

    def test_child_and_kiosk_share_request_menu_values(self):
        preferences = Preferences()
        broker = make_broker(preferences=preferences)
        broker.update_request_preferences(1001, 1001, "custom", 22.5, True, 1003)
        request = broker.get_preferences(991, 1001)["request"]
        self.assertEqual(request["last_selected_duration"], "custom")
        self.assertEqual(request["last_custom_minutes"], 22.5)
        self.assertTrue(request["allow_soft_blocked_apps"])
        self.assertEqual(request["last_selected_approver_uid"], 1003)

    def test_kiosk_and_child_mutes_are_independent(self):
        preferences = Preferences()
        broker = make_broker(preferences=preferences)
        broker.set_request_muted(991, 1001, "kiosk", True)
        broker.set_request_muted(1001, 1001, "child", False)
        request = broker.get_preferences(1001, 1001)["request"]
        self.assertTrue(request["kiosk_muted"])
        self.assertFalse(request["child_muted"])
        broker.set_request_muted(1001, 1001, "child", True)
        request = broker.get_preferences(991, 1001)["request"]
        self.assertTrue(request["kiosk_muted"])
        self.assertTrue(request["child_muted"])

    def test_managed_child_can_read_its_own_account(self):
        user = make_broker().get_own_account(1001)
        self.assertEqual((user.uid, user.label), (1001, "Child"))
        with self.assertRaises(AccessDenied):
            make_broker().get_own_account(991)
        with self.assertRaises(AccessDenied):
            make_broker().get_own_account(1003)

    def test_managed_child_request_is_broker_owned_and_targets_caller(self):
        auth, accounts, preferences = Authorizer(), Accounts(), Preferences()
        preferences.values[1001]["parent_control_enabled"] = True

        correlation_id, outcome, granted_duration = make_broker(
            auth, accounts, preferences=preferences,
        ).request_own_access(1001, ":1.20", 1003, 900, True)

        self.assertTrue(correlation_id)
        self.assertEqual((outcome, granted_duration), ("approved", 900))
        self.assertEqual(auth.calls[0][0], "child")
        self.assertEqual(auth.calls[0][1], ":1.20")
        self.assertEqual(accounts.filter, (False, ("org.example.Game",)))
        self.assertIn(("set_extension", 1001, accounts.extension), accounts.events)

    def test_child_request_requires_enabled_managed_caller(self):
        auth, accounts, preferences = Authorizer(), Accounts(), Preferences()
        broker = make_broker(auth, accounts, preferences=preferences)

        with self.assertRaises(AccessDenied):
            broker.request_own_access(1001, ":1.20", 1003, 900, False)
        with self.assertRaises(AccessDenied):
            broker.request_own_access(1003, ":1.21", 1003, 900, False)

        self.assertEqual(auth.calls, [])
        self.assertEqual(accounts.events, [])

    def test_child_request_revalidates_preferences_after_authorization(self):
        accounts, preferences = Accounts(), Preferences()
        preferences.values[1001]["parent_control_enabled"] = True

        def disable():
            preferences.values[1001]["parent_control_enabled"] = False

        with self.assertRaises(AccessDenied):
            make_broker(
                Authorizer(callback=disable), accounts, preferences=preferences,
            ).request_own_access(1001, ":1.20", 1003, 900, False)

        self.assertEqual(accounts.events, [])

    def test_child_request_rejects_unvalidated_approver_before_polkit(self):
        auth, accounts, preferences = Authorizer(), Accounts(), Preferences()
        preferences.values[1001]["parent_control_enabled"] = True

        with self.assertRaises(AccessDenied):
            make_broker(
                auth, accounts, preferences=preferences,
            ).request_own_access(1001, ":1.20", 1002, 900, False)

        self.assertEqual(auth.calls, [])
        self.assertEqual(accounts.events, [])

    def test_admin_target_is_rejected_without_authorization(self):
        auth, accounts = Authorizer(), Accounts()
        with self.assertRaises(AccessDenied):
            make_broker(auth, accounts).request_access(
                991, ":1.2", 1003, 1003, 900, False,
            )
        self.assertEqual(auth.calls, [])

    def test_account_created_after_broker_start_is_discovered(self):
        accounts = Accounts()
        broker = make_broker(accounts=accounts)
        accounts.users[1006] = UserAccount(
            1006, "new-child", "New Child", False, False, True,
        )
        self.assertIn(1006, [user.uid for user in broker.list_managed_users(991)])

    def test_unrestricted_account_is_initialized_after_single_authorization(self):
        auth, accounts = Authorizer(), Accounts()
        accounts.limit_type = 0
        accounts.daily_limit = 7200
        make_broker(auth, accounts).request_access(991, ":1.2", 1001, 1003, 900, False)
        self.assertEqual(len(auth.calls), 1)
        self.assertEqual(auth.calls[0][0], "kiosk")
        self.assertEqual(accounts.limit_type, 2)
        self.assertEqual(accounts.daily_limit, 0)

    def test_account_change_during_authorization_causes_no_writes(self):
        accounts = Accounts()

        def promote():
            old = accounts.users[1001]
            accounts.users[1001] = UserAccount(
                old.uid, old.username, old.label, True, old.is_system, old.is_local,
            )

        with self.assertRaises(AccessDenied):
            make_broker(Authorizer(callback=promote), accounts).request_access(
                991, ":1.2", 1001, 1003, 900, False,
            )
        self.assertEqual(accounts.events, [])

    def test_approver_change_during_authorization_causes_no_writes(self):
        accounts = Accounts()

        def demote():
            old = accounts.users[1003]
            accounts.users[1003] = UserAccount(
                old.uid, old.username, old.label, False, old.is_system, old.is_local,
            )

        with self.assertRaises(AccessDenied):
            make_broker(Authorizer(callback=demote), accounts).request_access(
                991, ":1.2", 1001, 1003, 900, False,
            )
        self.assertEqual(accounts.events, [])

    def test_non_admin_approver_is_rejected_without_authorization(self):
        auth, accounts = Authorizer(), Accounts()
        with self.assertRaises(AccessDenied):
            make_broker(auth, accounts).request_access(
                991, ":1.2", 1001, 1002, 900, False,
            )
        self.assertEqual(auth.calls, [])
        self.assertEqual(accounts.events, [])

    def test_duration_and_toggle_are_validated_before_authorization(self):
        auth, accounts = Authorizer(), Accounts()
        broker = make_broker(auth, accounts)
        for duration, allow_soft in ((5, False), (86401, False), (900, 1)):
            with self.assertRaises(InvalidRequest):
                broker.request_access(991, ":1.2", 1001, 1003, duration, allow_soft)
        self.assertEqual(auth.calls, [])
        self.assertEqual(accounts.events, [])

    def test_rest_of_day_is_calculated_after_approval(self):
        accounts = Accounts()
        make_broker(accounts=accounts).request_access(991, ":1.2", 1001, 1003, 0, False)
        self.assertEqual(accounts.extension[1], 14 * 60 * 60)

    def test_denial_makes_no_writes_and_one_check(self):
        auth, accounts, timer_usage = Authorizer("denied"), Accounts(), TimerUsage()
        result = make_broker(auth, accounts, timer_usage=timer_usage).request_access(
            991, ":1.2", 1001, 1003, 900, False,
        )
        self.assertEqual(result[1], "denied")
        self.assertEqual(len(auth.calls), 1)
        self.assertEqual(timer_usage.as_calls, [])
        self.assertEqual(accounts.events, [])

    def test_kiosk_usage_query_runs_as_authenticated_approver(self):
        timer_usage = TimerUsage()
        result = make_broker(timer_usage=timer_usage).request_access(
            991, ":1.2", 1001, 1003, 900, False,
        )
        self.assertEqual(result[1], "approved")
        self.assertEqual(timer_usage.as_calls, [(1001, 1003, "admin")])

    def test_usage_query_failure_makes_no_account_writes(self):
        accounts = Accounts()
        timer_usage = TimerUsage(error=RuntimeError("failed"))
        with self.assertRaises(BackendFailure):
            make_broker(accounts=accounts, timer_usage=timer_usage).request_access(
                991, ":1.2", 1001, 1003, 900, False,
            )
        self.assertEqual(accounts.events, [])

    def test_approver_change_during_usage_query_makes_no_account_writes(self):
        accounts = Accounts()

        def demote():
            old = accounts.users[1003]
            accounts.users[1003] = UserAccount(
                old.uid, old.username, old.label, False, old.is_system, old.is_local,
            )

        timer_usage = TimerUsage(callback=demote)
        with self.assertRaises(AccessDenied):
            make_broker(accounts=accounts, timer_usage=timer_usage).request_access(
                991, ":1.2", 1001, 1003, 900, False,
            )
        self.assertEqual(accounts.events, [])

    def test_disconnected_caller_makes_no_writes(self):
        accounts = Accounts()
        result = make_broker(accounts=accounts, alive=lambda _s: False).request_access(
            991, ":1.2", 1001, 1003, 900, False
        )
        self.assertEqual(result[1], "denied")
        self.assertEqual(accounts.events, [])

    def test_allow_soft_omits_only_soft_targets(self):
        accounts = Accounts()
        result = make_broker(accounts=accounts).request_access(
            991, ":1.2", 1001, 1003, 900, True,
        )
        self.assertEqual(result[1], "approved")
        self.assertEqual(accounts.filter, (False, ("org.example.Game",)))

    def test_filter_precedes_extension_and_readback(self):
        accounts = Accounts()
        make_broker(accounts=accounts).request_access(
            991, ":1.2", 1001, 1003, 900, False,
        )
        names = [event[0] for event in accounts.events]
        self.assertLess(names.index("set_filter"), names.index("set_extension"))
        self.assertEqual(accounts.filter, (False, ("/usr/bin/game", "org.example.Game")))
        self.assertEqual(accounts.extension[1], 900)

    def test_kiosk_grant_uses_shared_accumulative_formula(self):
        now = datetime(2026, 8, 30, 10, tzinfo=ZoneInfo("America/Los_Angeles"))
        accounts, preferences = Accounts(), Preferences()
        preferences.values[1001]["parent_control_enabled"] = True
        preferences.values[1001]["daily_time_limit_minutes"] = 32
        accounts.extension = (int(now.timestamp()), 10 * 60)
        start = int(datetime(2026, 8, 30, tzinfo=now.tzinfo).timestamp())

        make_broker(
            accounts=accounts,
            preferences=preferences,
            timer_usage=TimerUsage(((start, start + 60),)),
        ).request_access(991, ":1.2", 1001, 1003, 5 * 60, False)

        self.assertEqual(accounts.extension[1], 36 * 60)

    def test_request_restores_configured_daily_allowance(self):
        accounts = Accounts()
        accounts.limit_type = 2
        accounts.daily_limit = 4 * 60 * 60
        preferences = Preferences()
        preferences.values[1001]["daily_time_limit_minutes"] = 120

        make_broker(accounts=accounts, preferences=preferences).request_access(
            991, ":1.2", 1001, 1003, 900, False,
        )

        self.assertEqual(accounts.limit_type, 2)
        self.assertEqual(accounts.daily_limit, 2 * 60 * 60)
        self.assertIn(("set_daily_limit", 1001, 2 * 60 * 60), accounts.events)

    def test_extension_failure_rolls_filter_back(self):
        accounts = Accounts()
        accounts.fail_extension = True
        with self.assertRaises(BackendFailure):
            make_broker(accounts=accounts).request_access(
                991, ":1.2", 1001, 1003, 900, False,
            )
        self.assertEqual(accounts.filter, (False, ("old.App",)))

    def test_rollback_failure_is_escalated(self):
        accounts = Accounts()
        accounts.fail_extension = accounts.fail_rollback = True
        with self.assertRaises(RollbackFailure):
            make_broker(accounts=accounts).request_access(
                991, ":1.2", 1001, 1003, 900, False,
            )

    def test_rate_limit(self):
        auth = Authorizer()
        broker = make_broker(auth, clock=lambda: 100)
        broker.request_access(991, ":1.2", 1001, 1003, 900, False)
        self.assertEqual(len(auth.calls), 1)
        with self.assertRaises(RateLimited):
            broker.request_access(991, ":1.3", 1001, 1003, 900, False)
        self.assertEqual(len(auth.calls), 1)

    def test_denied_or_cancelled_request_does_not_consume_rate_limit(self):
        for outcome in ("denied", "cancelled"):
            with self.subTest(outcome=outcome):
                auth = Authorizer(outcome)
                broker = make_broker(auth, clock=lambda: 100)
                self.assertEqual(
                    broker.request_access(991, ":1.2", 1001, 1003, 900, False)[1],
                    outcome,
                )
                auth.outcome = "approved"
                self.assertEqual(
                    broker.request_access(991, ":1.3", 1001, 1003, 900, False)[1],
                    "approved",
                )
                self.assertEqual(len(auth.calls), 2)

    def test_concurrent_request_is_busy(self):
        entered, release = threading.Event(), threading.Event()
        auth = Authorizer(callback=lambda: (entered.set(), release.wait(2)))
        broker = make_broker(authorizer=auth)
        thread = threading.Thread(
            target=lambda: broker.request_access(
                991, ":1.2", 1001, 1003, 900, False,
            )
        )
        thread.start()
        self.assertTrue(entered.wait(1))
        with self.assertRaises(Busy):
            broker.request_access(991, ":1.3", 1001, 1003, 900, False)
        release.set()
        thread.join()

    def test_local_midnight_dst_boundaries(self):
        zone = ZoneInfo("America/Los_Angeles")
        self.assertEqual(seconds_until_local_midnight(datetime(2026, 3, 7, 0, tzinfo=zone)), 86400)
        self.assertEqual(seconds_until_local_midnight(datetime(2026, 3, 8, 0, tzinfo=zone)), 23 * 3600)
        self.assertEqual(seconds_until_local_midnight(datetime(2026, 11, 1, 0, tzinfo=zone)), 25 * 3600)


if __name__ == "__main__":
    unittest.main()
