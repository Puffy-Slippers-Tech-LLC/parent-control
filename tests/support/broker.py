"""Recording broker adapters for deterministic transaction tests.

These doubles do not call OS services. Each factory call owns fresh mutable
state; failure flags and callbacks are explicit test inputs.
"""

from datetime import datetime
from zoneinfo import ZoneInfo

from oh_no_parent_control.config import validate
from oh_no_parent_control.core import Broker, UserAccount
from oh_no_parent_control.preferences import default_preferences, validate_preferences
from tests.support.configuration import valid_config

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


class RunningApps:
    def __init__(self, events=None, *, terminated=0, error=None):
        self.calls = []
        self.events = events
        self.terminated = terminated
        self.error = error

    def preflight(self, uid, targets, patterns):
        self.calls.append(("preflight", uid, targets, patterns))

    def terminate(self, uid, targets, patterns):
        self.calls.append(("terminate", uid, targets, patterns))
        if self.events is not None:
            self.events.append(("terminate_apps", uid, targets, patterns))
        if self.error:
            raise self.error
        return self.terminated


def make_broker(authorizer=None, accounts=None, preferences=None, extensions=None,
                clock=None, alive=lambda _s: True, timer_usage=None,
                application_catalog=None, running_apps=None):
    config = validate(valid_config())
    return Broker(lambda: config, authorizer or Authorizer(), accounts or Accounts(),
                  preferences or Preferences(), extensions, timer_usage or TimerUsage(),
                  application_catalog,
                  running_apps or RunningApps(),
                  monotonic=clock or (lambda: 100),
                  now=lambda: datetime(2026, 8, 30, 10, tzinfo=ZoneInfo("America/Los_Angeles")),
                  caller_alive=alive)
