"""Launch the production Parent window with scripted, local broker outcomes."""

from __future__ import annotations

import copy
import json
import os
import sys
import time

from parent.oh_no_parent_control_parent.main import (
    Application,
    PREVIEW_APPS,
    PREVIEW_PREFERENCES,
    PREVIEW_USERS,
)


class ScriptedParentBroker:
    """Deterministic component-test broker; it contains no authorization logic."""

    def __init__(self):
        self._mode = os.environ.get("ONPC_PARENT_COMPONENT_SCENARIO", "normal")
        self._preferences = copy.deepcopy(PREVIEW_PREFERENCES)
        if self._mode == "custom-limit":
            self._preferences[1001]["daily_time_limit_minutes"] = 73
        self._status_attempts = 0
        self._events_path = os.environ.get("ONPC_PARENT_COMPONENT_EVENTS_PATH")

    def _record(self, event, **details):
        """Expose fake-broker call order to the black-box component harness."""
        if not self._events_path:
            return
        with open(self._events_path, "a", encoding="utf-8") as handle:
            handle.write(json.dumps({"event": event, **details}, sort_keys=True) + "\n")

    def list_users(self):
        self._record("list_users")
        if self._mode == "no-users":
            return []
        if self._mode in {"denied", "unavailable"}:
            raise RuntimeError("service unavailable")
        return PREVIEW_USERS

    def get_preferences(self, uid):
        self._record("get_preferences", uid=uid)
        if self._mode == "loading":
            time.sleep(1)
        return copy.deepcopy(self._preferences[uid])

    def list_apps(self, _uid):
        self._record("list_apps")
        if self._mode == "loading":
            time.sleep(1)
        return copy.deepcopy(PREVIEW_APPS)

    def get_time_status(self, _uid):
        self._status_attempts += 1
        self._record("get_time_status", attempt=self._status_attempts)
        if self._mode == "status-unavailable":
            raise RuntimeError("temporarily unavailable")
        if self._mode == "status-retries" and self._status_attempts < 3:
            raise RuntimeError("temporarily unavailable")
        return {
            "daily_allowance_remaining_seconds": 47 * 60,
            "one_time_grant_remaining_seconds": 15 * 60,
            "additional_one_time_grant_seconds": 0,
            "calculated_active_extension_seconds": 47 * 60,
        }

    def set_preferences(self, uid, value):
        self._record("set_preferences", uid=uid)
        if self._mode == "save-fails":
            raise RuntimeError("save rejected")
        self._preferences[uid] = copy.deepcopy(value)
        return self.get_preferences(uid)

    def set_parent_control(self, uid, enabled, daily_limit_minutes):
        self._record(
            "set_parent_control", uid=uid, enabled=enabled,
            daily_limit_minutes=daily_limit_minutes,
        )
        if self._mode == "slow-save":
            time.sleep(1)
        if self._mode == "save-fails":
            raise RuntimeError("save rejected")
        self._preferences[uid]["parent_control_enabled"] = enabled
        self._preferences[uid]["daily_time_limit_minutes"] = daily_limit_minutes
        return self.get_preferences(uid)

    def revoke_one_time_grant(self, _uid):
        self._record("revoke_one_time_grant")
        return None


raise SystemExit(Application(client_factory=ScriptedParentBroker).run([sys.argv[0]]))
