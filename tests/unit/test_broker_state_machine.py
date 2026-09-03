"""Model-based transaction checks for the broker's public policy operations."""

from copy import deepcopy
from dataclasses import replace
from datetime import datetime
from zoneinfo import ZoneInfo

import pytest
from hypothesis import strategies as st
from hypothesis.stateful import RuleBasedStateMachine, invariant, rule, run_state_machine_as_test

from oh_no_parent_control.config import validate
from oh_no_parent_control.core import AccessDenied, BackendFailure, Broker, BrokerError, UserAccount
from oh_no_parent_control.preferences import default_preferences, validate_preferences
from test_config import valid_config


CHILDREN = (1001, 1002)
ADMINISTRATORS = (1003, 1004)
KIOSK = 991
UNRELATED = 1005


class MutableClock:
    def __init__(self):
        self.value = 100

    def tick(self):
        self.value += 10

    def __call__(self):
        return self.value


class ModelAuthorizer:
    def __init__(self):
        self.outcome = "approved"

    def check(self, *_args):
        return self.outcome


class ModelAccounts:
    def __init__(self):
        self.users = {
            1001: UserAccount(1001, "child-one", "Child One", False, False, True),
            1002: UserAccount(1002, "child-two", "Child Two", False, False, True),
            1003: UserAccount(1003, "parent-one", "Parent One", True, False, True),
            1004: UserAccount(1004, "parent-two", "Parent Two", True, False, True),
            KIOSK: UserAccount(KIOSK, "kiosk", "Kiosk", False, False, True),
            UNRELATED: UserAccount(UNRELATED, "unrelated", "Unrelated", False, False, True),
        }
        self.filters = {uid: (False, ()) for uid in CHILDREN}
        self.extensions = {uid: (0, 0) for uid in CHILDREN}
        self.limit_types = {uid: 0 for uid in CHILDREN}
        self.daily_limits = {uid: 0 for uid in CHILDREN}
        self.fail_once = None

    def _fail(self, boundary):
        if self.fail_once == boundary:
            self.fail_once = None
            raise RuntimeError(f"injected {boundary} failure")

    def list_users(self):
        return tuple(self.users.values())

    def get_user(self, uid):
        return self.users[uid]

    def get_filter(self, uid):
        self._fail("get_filter")
        return self.filters[uid]

    def set_filter(self, uid, value):
        self._fail("set_filter")
        self.filters[uid] = value

    def get_extension(self, uid):
        self._fail("get_extension")
        return self.extensions[uid]

    def set_extension(self, uid, value):
        self._fail("set_extension")
        self.extensions[uid] = value

    def get_limit_type(self, uid):
        return self.limit_types[uid]

    def set_limit_type(self, uid, value):
        self._fail("set_limit_type")
        self.limit_types[uid] = value

    def get_daily_limit(self, uid):
        return self.daily_limits[uid]

    def set_daily_limit(self, uid, value):
        self._fail("set_daily_limit")
        self.daily_limits[uid] = value


class ModelPreferences:
    def __init__(self):
        self.values = {uid: self._value(uid) for uid in CHILDREN}

    @staticmethod
    def _value(uid):
        value = default_preferences()
        value["apps"] = {
            f"hard-{uid}.desktop": {
                "state": "permanent", "targets": [f"org.example.Hard{uid}"],
                "patterns": [], "user_saved_match_rule": False,
            },
            f"soft-{uid}.desktop": {
                "state": "conditional", "targets": [f"org.example.Soft{uid}"],
                "patterns": [], "user_saved_match_rule": False,
            },
        }
        return value

    def load(self, uid):
        return validate_preferences(deepcopy(self.values[uid]))

    def save(self, uid, value):
        self.values[uid] = validate_preferences(value)
        return self.load(uid)

    def update_request(self, uid, selected, custom, allow_soft, approver=0):
        value = self.load(uid)
        value["request"] = {
            **value["request"],
            "last_selected_duration": selected,
            "last_custom_minutes": custom,
            "allow_soft_blocked_apps": allow_soft,
            "last_selected_approver_uid": approver,
        }
        return self.save(uid, value)

    def update_request_muted(self, uid, surface, muted):
        value = self.load(uid)
        value["request"]["kiosk_muted" if surface == "kiosk" else "child_muted"] = muted
        return self.save(uid, value)


class ModelExtensions:
    def __init__(self):
        self.enabled = {uid: False for uid in CHILDREN}
        self.fail_once = False

    def set_enabled(self, uid, enabled):
        if self.fail_once:
            self.fail_once = False
            raise RuntimeError("injected extension failure")
        self.enabled[uid] = enabled


class ModelTimerUsage:
    def query_usage(self, _uid):
        return ()

    def query_usage_as(self, _uid, _approver):
        return ()


class ModelRunningApps:
    def preflight(self, *_args):
        return None

    def terminate(self, *_args):
        return 0


class BrokerTransactionMachine(RuleBasedStateMachine):
    """Two children, two administrators, kiosk, and unrelated caller model."""

    def __init__(self):
        super().__init__()
        self.clock = MutableClock()
        self.now = datetime(2026, 8, 30, 10, tzinfo=ZoneInfo("America/Los_Angeles"))
        self.authorizer = ModelAuthorizer()
        self.accounts = ModelAccounts()
        self.preferences = ModelPreferences()
        self.extensions = ModelExtensions()
        self.caller_alive = True
        self.enforced = set()
        self.broker = Broker(
            lambda: validate(valid_config()), self.authorizer, self.accounts,
            self.preferences, self.extensions, ModelTimerUsage(),
            running_apps=ModelRunningApps(), monotonic=self.clock,
            now=lambda: self.now, caller_alive=lambda _sender: self.caller_alive,
        )

    def snapshot(self):
        return {
            "filters": deepcopy(self.accounts.filters),
            "extensions": deepcopy(self.accounts.extensions),
            "limit_types": deepcopy(self.accounts.limit_types),
            "daily_limits": deepcopy(self.accounts.daily_limits),
            "preferences": deepcopy(self.preferences.values),
            "extension_enabled": deepcopy(self.extensions.enabled),
        }

    @staticmethod
    def hard_target(uid):
        return f"org.example.Hard{uid}"

    @rule(child=st.sampled_from(CHILDREN), enabled=st.booleans(),
          minutes=st.integers(min_value=0, max_value=24 * 60))
    def enable_disable_or_change_daily_limit(self, child, enabled, minutes):
        if self.accounts.users[child].is_admin:
            return
        self.broker.set_parent_control(1003, child, enabled, minutes)
        self.enforced.add(child)
        assert self.preferences.load(child)["parent_control_enabled"] is enabled
        assert self.preferences.load(child)["daily_time_limit_minutes"] == minutes
        assert self.accounts.daily_limits[child] == (minutes * 60 if enabled else 0)

    @rule(child=st.sampled_from(CHILDREN), state=st.sampled_from(
        ("allowed", "permanent", "conditional"),
    ))
    def change_app_policy(self, child, state):
        if self.accounts.users[child].is_admin:
            return
        value = self.preferences.load(child)
        key = f"soft-{child}.desktop"
        value["apps"][key] = {
            "state": state,
            "targets": [f"org.example.Soft{child}"],
            "patterns": [],
            "user_saved_match_rule": False,
        }
        self.broker.set_preferences(1003, child, value)
        self.enforced.add(child)

    @rule(child=st.sampled_from(CHILDREN), approver=st.sampled_from(ADMINISTRATORS),
          allow_soft=st.booleans())
    def approve_request(self, child, approver, allow_soft):
        if self.accounts.users[child].is_admin or not self.accounts.users[approver].is_admin:
            return
        before = self.accounts.extensions[child]
        preferences = self.preferences.load(child)
        daily = preferences["daily_time_limit_minutes"] * 60 if preferences["parent_control_enabled"] else 0
        existing = max(0, before[0] + before[1] - int(self.now.timestamp()))
        self.authorizer.outcome = "approved"
        self.caller_alive = True
        self.clock.tick()
        _id, outcome = self.broker.request_access(
            KIOSK, ":1.kiosk", child, approver, 300, allow_soft,
        )
        assert outcome == "approved"
        assert self.accounts.extensions[child] == (
            int(self.now.timestamp()), max(daily, existing) + 300,
        )
        self.enforced.add(child)

    @rule(child=st.sampled_from(CHILDREN), outcome=st.sampled_from(("denied", "cancelled")))
    def denial_or_cancellation_never_relaxes_state(self, child, outcome):
        if self.accounts.users[child].is_admin:
            return
        before = self.snapshot()
        self.authorizer.outcome = outcome
        self.clock.tick()
        _id, actual = self.broker.request_access(KIOSK, ":1.kiosk", child, 1003, 300, False)
        assert actual == outcome
        assert self.snapshot() == before

    @rule(child=st.sampled_from(CHILDREN))
    def disconnected_requester_never_relaxes_state(self, child):
        if self.accounts.users[child].is_admin:
            return
        before = self.snapshot()
        self.authorizer.outcome = "approved"
        self.caller_alive = False
        self.clock.tick()
        _id, outcome = self.broker.request_access(KIOSK, ":1.kiosk", child, 1003, 300, False)
        self.caller_alive = True
        assert outcome == "denied"
        assert self.snapshot() == before

    @rule(child=st.sampled_from(CHILDREN))
    def revoke_preserves_daily_policy_and_restores_full_blocklist(self, child):
        if self.accounts.users[child].is_admin:
            return
        self.broker.revoke_one_time_grant(1003, child)
        assert self.accounts.extensions[child] == (0, 0)
        self.enforced.add(child)

    @rule(child=st.sampled_from(CHILDREN), approver=st.sampled_from(ADMINISTRATORS))
    def account_role_changes_are_revalidated(self, child, approver):
        original_child = self.accounts.users[child]
        self.accounts.users[child] = replace(original_child, is_admin=True)
        before = self.snapshot()
        with pytest.raises(AccessDenied):
            self.broker.request_access(KIOSK, ":1.kiosk", child, approver, 300, False)
        assert self.snapshot() == before
        self.accounts.users[child] = original_child

        original_approver = self.accounts.users[approver]
        self.accounts.users[approver] = replace(original_approver, is_admin=False)
        before = self.snapshot()
        with pytest.raises(AccessDenied):
            self.broker.request_access(KIOSK, ":1.kiosk", child, approver, 300, False)
        assert self.snapshot() == before
        self.accounts.users[approver] = original_approver

    @rule(child=st.sampled_from(CHILDREN), boundary=st.sampled_from((
        "set_limit_type", "set_daily_limit", "set_filter", "set_extension",
        "get_filter", "get_extension", "extensions",
    )))
    def adapter_failure_rolls_back_to_the_recovery_state(self, child, boundary):
        if self.accounts.users[child].is_admin:
            return
        before = self.snapshot()
        if boundary == "extensions":
            self.extensions.fail_once = True
        else:
            self.accounts.fail_once = boundary
        with pytest.raises(BrokerError):
            self.broker.set_parent_control(
                1003, child,
                not self.preferences.load(child)["parent_control_enabled"], 60,
            )
        assert self.snapshot() == before

    @rule(child=st.sampled_from(CHILDREN), transaction=st.sampled_from(
        ("approval", "revocation"),
    ), boundary=st.sampled_from((
        "set_filter", "set_extension", "get_filter", "get_extension",
    )))
    def request_and_revocation_adapter_failures_preserve_recovery_state(
            self, child, transaction, boundary):
        if self.accounts.users[child].is_admin:
            return
        before = self.snapshot()
        self.accounts.fail_once = boundary
        if transaction == "approval":
            self.authorizer.outcome = "approved"
            self.caller_alive = True
            self.clock.tick()
            with pytest.raises(BrokerError):
                self.broker.request_access(KIOSK, ":1.kiosk", child, 1003, 300, False)
        else:
            with pytest.raises(BrokerError):
                self.broker.revoke_one_time_grant(1003, child)
        assert self.snapshot() == before

    @rule(child=st.sampled_from(CHILDREN))
    def unrelated_user_cannot_change_a_child(self, child):
        if self.accounts.users[child].is_admin:
            return
        before = self.snapshot()
        with pytest.raises(AccessDenied):
            self.broker.set_parent_control(UNRELATED, child, True, 60)
        assert self.snapshot() == before

    @invariant()
    def hard_blocks_and_child_state_remain_isolated(self):
        for child in CHILDREN:
            child_filter = self.accounts.filters[child][1]
            assert all(str(child) in target for target in child_filter)
            if child in self.enforced:
                assert self.hard_target(child) in child_filter


def test_broker_transactions_match_the_state_machine_model():
    run_state_machine_as_test(BrokerTransactionMachine)
