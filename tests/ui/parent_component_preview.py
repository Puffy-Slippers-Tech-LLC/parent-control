"""Launch the production Parent window with scripted, local broker outcomes."""

from __future__ import annotations

import copy
import json
import os
import sys
import time

from parent.oh_no_parent_control_parent.main import Application
from parent.oh_no_parent_control_parent.preview_data import (
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
        if self._mode in {"grant-only", "exact-hours"}:
            self._preferences[1001]["daily_time_limit_minutes"] = 0
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
        daily = 0 if self._mode in {"grant-only", "daily-exhausted", "exact-hours"} else 47 * 60
        grant = 2 * 60 * 60 if self._mode == "exact-hours" else 15 * 60
        return {
            "daily_allowance_remaining_seconds": daily,
            "one_time_grant_remaining_seconds": grant,
            "additional_one_time_grant_seconds": 0,
            "calculated_active_extension_seconds": max(daily, grant),
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


# Every component preview uses a fake feedback transport, so UI interaction
# cannot send real email. Exercise the production encoder and retry controller.
from unittest.mock import Mock
import requests
from common.oh_no_parent_control_ui import feedback, feedback_transport
from parent.oh_no_parent_control_parent import main as parent_main

feedback.collect_logs = lambda: b"PK\x03\x04component-test archive"
feedback_status = int(os.environ.get("ONPC_FEEDBACK_STATUS", "202"))
feedback_attempts = 0


def feedback_post(_url, **kwargs):
    global feedback_attempts
    feedback_attempts += 1
    part_names = [name for name, _part in kwargs["files"]]
    assert "body" in part_names
    assert "bodyHtml" in part_names
    message_html = next(part[1] for name, part in kwargs["files"]
                        if name == "bodyHtml")
    title = next(part[1] for name, part in kwargs["files"] if name == "title")
    if title == feedback_transport.DEFAULT_TITLE:
        assert "<strong>" in message_html
    if feedback_status == 413 and feedback_attempts > 1:
        assert not any(name == "attachments" and part[0] == "oh-no-parent-control-logs.zip"
                       for name, part in kwargs["files"])
    result = requests.Response()
    result.status_code = feedback_status if feedback_attempts == 1 else 202
    result._content = json.dumps({"ok": result.status_code == 202}).encode()
    result._content_consumed = True
    return result


feedback_session = Mock()
feedback_session.__enter__ = Mock(return_value=feedback_session)
feedback_session.__exit__ = Mock(return_value=False)
feedback_session.post.side_effect = feedback_post
feedback_transport.requests.Session = lambda: feedback_session


if os.environ.get("ONPC_PARENT_COMPONENT_SCENARIO") == "feedback-attachments":
    class AttachedFeedbackDialog(feedback.FeedbackDialog):
        def __init__(self, *args, **kwargs):
            super().__init__(*args, **kwargs)
            self._attachments_loaded([
                feedback_transport.Attachment.create(f"sample-{index}.txt", b"test attachment")
                for index in range(feedback_transport.MAX_ATTACHMENT_COUNT)
            ], None)

    parent_main.FeedbackDialog = AttachedFeedbackDialog


application = Application(client_factory=ScriptedParentBroker)
if directory := os.environ.get("ONPC_PARENT_ALLOWANCE_LAYOUT_DIRECTORY"):
    from tests.ui.parent_allowance_probe import attach
    application.connect_after("activate", attach, directory)
if directory := os.environ.get("ONPC_PARENT_LEGEND_LAYOUT_DIRECTORY"):
    from tests.ui.parent_legend_probe import attach
    application.connect_after("activate", attach, directory)
raise SystemExit(application.run([sys.argv[0]]))
