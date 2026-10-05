"""Launch the production Parent window with scripted, local broker outcomes."""

from __future__ import annotations

import copy
import json
import os
from pathlib import Path
import sys
import time

from parent.oh_no_parent_control_parent.main import Application
from tests.support.language_fixture import LanguageFixture
from parent.oh_no_parent_control_parent.preview_data import (
    PREVIEW_APPS,
    PREVIEW_PREFERENCES,
    PREVIEW_USERS,
)


class ScriptedParentBroker:
    """Deterministic component-test broker; it contains no authorization logic."""

    def __init__(self):
        self._language = LanguageFixture(self._record)
        self._mode = os.environ.get("ONPC_PARENT_COMPONENT_SCENARIO", "normal")
        self._preferences = copy.deepcopy(PREVIEW_PREFERENCES)
        if self._mode in ('catalogue', 'rejected-rule'):
            from tests.fixtures.native_assets import ASSETS, PREFIX, desktop_id
            self._preferences[1002]['apps'] = {
                desktop_id(role): {'state': {'H': 'permanent', 'S': 'conditional'}.get(role, 'allowed'),
                    'targets': [PREFIX + '/' + filename],
                    'patterns': [], 'user_saved_match_rule': False}
                for role, filename, _name, _description, _match in ASSETS}
        if self._mode == "custom-limit":
            self._preferences[1001]["daily_time_limit_minutes"] = 73
        if self._mode in {"grant-only", "exact-hours", "zero-total"}:
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
        if self._mode == 'startup-reboot':
            from gi.repository import Gio
            raise Gio.DBusError.new_for_dbus_error(
                'com.puffyslippers.OhNoParentControl1.Error.RebootRequired', 'private detail')
        if self._mode == "no-users":
            return []
        if self._mode in {"denied", "unavailable"}:
            raise RuntimeError("service unavailable")
        return PREVIEW_USERS

    def get_own_language(self):
        return self._language.read()

    def set_own_language(self, language):
        return self._language.save(language)

    def _wait_for_loading_release(self):
        # The component test must observe both disabled controls before this
        # scripted response completes. A fixed sleep races public tree reads.
        release = Path(os.environ["ONPC_PARENT_COMPONENT_LOADING_RELEASE"])
        deadline = time.monotonic() + 60
        while not release.is_file():
            if time.monotonic() >= deadline:
                raise TimeoutError("loading fixture was not released")
            time.sleep(0.02)

    def get_policy_warnings(self, _uid):
        if self._mode == "policy-warning":
            return ["thunderbird_thunderbird.desktop"]
        return []

    def get_preferences(self, uid):
        self._record("get_preferences", uid=uid)
        if self._mode == "loading":
            self._wait_for_loading_release()
            self._record("get_preferences_ready", uid=uid)
        return copy.deepcopy(self._preferences[uid])

    def list_apps(self, _uid):
        self._record("list_apps")
        if self._mode == "loading":
            self._wait_for_loading_release()
        if self._mode in ('catalogue', 'rejected-rule'):
            from tests.fixtures.native_assets import ASSETS, PREFIX, desktop_id
            return [{'id': desktop_id(role), 'name': name, 'description': description,
                     'icon': 'applications-system', 'targets': [PREFIX + '/' + filename],
                     'suggested_patterns': [PREFIX + '/Lunar Client-*.AppImage']
                        if match == 'pattern' else []}
                    for role, filename, name, description, match in ASSETS]
        return copy.deepcopy(PREVIEW_APPS)

    def get_time_status(self, _uid):
        self._status_attempts += 1
        self._record("get_time_status", attempt=self._status_attempts)
        if self._mode == "status-unavailable":
            raise RuntimeError("temporarily unavailable")
        if self._mode == "status-retries" and self._status_attempts < 3:
            raise RuntimeError("temporarily unavailable")
        daily = 0 if self._mode in {"grant-only", "daily-exhausted", "exact-hours", "zero-total"} else 47 * 60
        grant = 0 if self._mode == "zero-total" else 2 * 60 * 60 if self._mode == "exact-hours" else 15 * 60
        return {
            "daily_allowance_remaining_seconds": daily,
            "one_time_grant_remaining_seconds": grant,
            "additional_one_time_grant_seconds": 0,
            "calculated_active_extension_seconds": max(daily, grant),
        }

    def set_preferences(self, uid, value):
        self._record("set_preferences", uid=uid)
        if self._mode == 'rejected-rule' and any(
                pattern.startswith('/opt/onpc-test-fixtures/Rejected/')
                for policy in value['apps'].values() for pattern in policy.get('patterns', [])):
            from gi.repository import GLib
            raise GLib.Error('synthetic rejected pattern')
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
        if self._mode == "held-save":
            self._wait_for_loading_release()
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

from common.oh_no_parent_control_ui.diagnostic_bundle import build_bundle

def feedback_logs():
    if os.environ.get("ONPC_PARENT_COMPONENT_SCENARIO") == "feedback-collecting":
        release = Path(os.environ["ONPC_FEEDBACK_COLLECTION_RELEASE"])
        deadline = time.monotonic() + 60
        while not release.is_file():
            if time.monotonic() >= deadline:
                raise TimeoutError("feedback collection fixture was not released")
            time.sleep(0.02)
    return build_bundle([])


feedback.collect_logs = feedback_logs

feedback_status = int(os.environ.get("ONPC_FEEDBACK_STATUS", "202"))
feedback_attempts = 0


def feedback_post(_url, **kwargs):
    global feedback_attempts
    feedback_attempts += 1
    part_names = [name for name, _part in kwargs["files"]]
    assert "body" in part_names
    assert "bodyHtml" in part_names
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

if os.environ.get('ONPC_FEEDBACK_CHOOSER_INPUTS'):
    from gi.repository import Gtk, Gio, GLib
    from tests.support.feedback import install_component_chooser
    install_component_chooser(os.environ['ONPC_FEEDBACK_CHOOSER_INPUTS'], Gtk, Gio, GLib)


if os.environ.get("ONPC_PARENT_COMPONENT_SCENARIO") == "feedback-restored-blocks":
    class RestoredBlockEditor(feedback.RichTextEditor):
        """Engineering fixture: ordinary startup restore of a declared delta."""
        def __init__(self, attachment_requested):
            super().__init__(attachment_requested)
            lines = (('Heading sample', {'header': 1}),
                     ('Subheading sample', {'header': 2}),
                     ('Number sample', {'list': 'ordered'}),
                     ('Bullet sample', {'list': 'bullet'}),
                     ('Quote sample', {'blockquote': True}),
                     ('Code sample', {'code-block': 'plain'}), ('Plain sample', {}))
            self._delta = json.dumps({'ops': [op for text, attrs in lines for op in (
                {'insert': text}, {'insert': '\n', 'attributes': attrs})]})

    feedback.RichTextEditor = RestoredBlockEditor


if os.environ.get("ONPC_PARENT_COMPONENT_SCENARIO") == "feedback-restored-link":
    class RestoredLinkEditor(feedback.RichTextEditor):
        """Engineering startup restoration; observations still use public Text."""
        def __init__(self, attachment_requested):
            super().__init__(attachment_requested)
            from tests.e2e.block_semantics import BODY
            self._delta = json.dumps({'ops': [
                {'insert': BODY[:-len('Plain sample')]},
                {'insert': 'Plain', 'attributes': {
                    'bold': True, 'italic': True, 'underline': True, 'strike': True,
                    'link': 'https://example.com/feedback'}},
                {'insert': ' sample\n'}]})

    feedback.RichTextEditor = RestoredLinkEditor


if os.environ.get("ONPC_PARENT_COMPONENT_SCENARIO") == "feedback-attachments":
    class AttachedFeedbackDialog(feedback.FeedbackDialog):
        def __init__(self, *args, **kwargs):
            super().__init__(*args, **kwargs)
            self._attachments_loaded([
                feedback_transport.Attachment.create(f"sample-{index}.txt", b"test attachment")
                for index in range(feedback_transport.MAX_ATTACHMENT_COUNT)
            ], None)

    parent_main.FeedbackDialog = AttachedFeedbackDialog


if os.environ.get("ONPC_PARENT_COMPONENT_SCENARIO") == "attachment-items":
    class AttachmentItemsDialog(feedback.FeedbackDialog):
        def _collection_done(self, data):
            result = super()._collection_done(data)
            # Match the live entry: add only after collection has cleared its
            # status, using real rows and their normal removal callbacks.
            if data is not None and not getattr(self, "_items_prepared", False):
                self._items_prepared = True
                self._attachments_loaded([
                    feedback_transport.Attachment.create("Second note.txt", b"ONPC second synthetic attachment\n"),
                    feedback_transport.Attachment.create("Synthetic note.txt", b"ONPC synthetic attachment\n"),
                ], None)
            return result

    parent_main.FeedbackDialog = AttachmentItemsDialog


startup_error = None
from tests.support.update_required import install_reboot_stub
install_reboot_stub(ScriptedParentBroker()._record)
if os.environ.get("ONPC_PARENT_COMPONENT_SCENARIO") == "startup-denied":
    from gi.repository import Gio
    startup_error = Gio.DBusError.new_for_dbus_error(
        "com.puffyslippers.OhNoParentControl1.Error.AccessDenied", "private-account-detail")
application = Application(client_factory=ScriptedParentBroker, startup_error=startup_error,
                          check_startup=os.environ.get('ONPC_PARENT_COMPONENT_SCENARIO') == 'startup-reboot')
raise SystemExit(application.run([sys.argv[0]]))
