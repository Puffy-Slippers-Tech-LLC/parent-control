"""Production request window with deterministic asynchronous broker replies."""

from __future__ import annotations

import copy
import json
import os
import sys

from gi.repository import GLib

from kiosk.oh_no_parent_control_kiosk.main import Application, Graphene, RequestWindow, configure_logging
from kiosk.oh_no_parent_control_kiosk.selection_store import SelectionStore
from gi.repository import Gtk


USERS = ((1001, "Alex Morgan", ""), (1002, "Sam Rivera", ""))
APPROVERS = ((1000, "Taylor Morgan", ""), (1010, "Avery Quinn", ""))
PREFERENCES = {
    uid: {"parent_control_enabled": True, "request": {
        "last_selected_duration": "1800", "last_custom_minutes": 7.5,
        "allow_soft_blocked_apps": False, "last_selected_approver_uid": 1000,
        "kiosk_muted": False, "child_muted": True,
    }} for uid, _label, _icon in USERS
}


class Reply:
    def __init__(self, value=None, error=None):
        self.value, self.error = value, error

    def unpack(self):
        if self.error:
            raise self.error
        return self.value


class Broker:
    def __init__(self):
        self.scenario = os.environ.get("ONPC_REQUEST_COMPONENT_SCENARIO", "normal")
        self.path = os.environ.get("ONPC_REQUEST_COMPONENT_EVENTS_PATH")
        self.preferences = copy.deepcopy(PREFERENCES)
        if self.scenario == "two-hours-grant-only":
            self.preferences[1001]["request"]["last_selected_duration"] = "7200"
        if self.scenario == "control-disabled":
            self.preferences[1001]["parent_control_enabled"] = False
        elif self.scenario == "remembered":
            self.preferences[1001]["request"].update({
                "last_selected_duration": "custom",
                "last_custom_minutes": 2.5,
                "allow_soft_blocked_apps": True,
                "last_selected_approver_uid": 1010,
                "kiosk_muted": False,
                "child_muted": True,
            })
        elif self.scenario in {"custom-too-small", "custom-too-large"}:
            self.preferences[1001]["request"].update({
                "last_selected_duration": "custom",
                "last_custom_minutes": (
                    0.09 if self.scenario == "custom-too-small" else 1440.1
                ),
            })
        elif self.scenario == "rest-of-day":
            self.preferences[1001]["request"]["last_selected_duration"] = "0"

    def record(self, event, **details):
        if self.path:
            with open(self.path, "a", encoding="utf-8") as output:
                output.write(json.dumps({"event": event, **details}, sort_keys=True) + "\n")

    def call(self, _name, _path, _interface, method, parameters, _reply_type,
             _flags, _timeout, _cancellable, callback):
        values = () if parameters is None else parameters.unpack()
        self.record("call", method=method, values=values)
        reply = self.reply(method, values)
        delay = (
            12_000 if self.scenario == "loading" and method == "GetPreferences"
            else 1_500 if self.scenario == "slow-request" and method.startswith("Request")
            else 0
        )
        source = GLib.timeout_add if delay else GLib.idle_add
        source(delay, lambda: (callback(self, reply), GLib.SOURCE_REMOVE)[1]) if delay else source(
            lambda: (callback(self, reply), GLib.SOURCE_REMOVE)[1],
        )

    @staticmethod
    def call_finish(reply):
        return reply

    def reply(self, method, values):
        if self.scenario.startswith("service-failure") and method.startswith("Request"):
            return Reply(error=RuntimeError("org.example.Secret /private/path"))
        if method == "GetOwnAccount":
            return Reply(USERS[0])
        if method == "ListManagedUsers":
            return Reply((() if self.scenario == "no-children" else USERS,))
        if method == "ListApprovers":
            return Reply((() if self.scenario == "no-approvers" else APPROVERS,))
        if method == "GetPreferences":
            return Reply((json.dumps(self.preferences[values[0]]),))
        if method == "GetTimeStatus":
            if self.scenario == "estimate-unavailable":
                return Reply(error=RuntimeError("org.example.Secret /private/path"))
            uid, additional = values
            daily = 47 * 60 if uid == 1001 else 0
            grant = 15 * 60
            if self.scenario == "two-hours-grant-only":
                daily = grant = 0
            return Reply((daily, grant, additional, max(daily, grant) + additional))
        if method == "UpdateRequestPreferences":
            uid, duration, custom, soft, approver = values
            self.preferences[uid]["request"].update({
                "last_selected_duration": duration, "last_custom_minutes": custom,
                "allow_soft_blocked_apps": soft, "last_selected_approver_uid": approver,
            })
            return Reply(("saved",))
        if method == "SetRequestMuted":
            uid, surface, muted = values
            self.preferences[uid]["request"][f"{surface}_muted"] = muted
            return Reply(("saved",))
        if method.startswith("Request"):
            outcome = {"denied": "denied", "cancelled": "cancelled"}.get(
                self.scenario, "approved",
            )
            return Reply(("request-id", outcome, 300) if method == "RequestOwnAccess"
                         else ("request-id", outcome))
        return Reply(error=RuntimeError("unexpected request-form call"))


BROKER = Broker()

# Exercise the real dialog/encoder without any external feedback submission.
from common.oh_no_parent_control_ui import feedback, feedback_transport
from unittest.mock import Mock

def feedback_logs():
    if BROKER.scenario == "service-failure-logs-unavailable":
        raise PermissionError("component-test diagnostic access denied")
    return b"PK\x03\x04component-test archive"


feedback.collect_logs = feedback_logs

def feedback_post(_url, **kwargs):
    parts = dict(kwargs["files"])
    BROKER.record("feedback", subject=parts["title"][1], message=parts["body"][1])
    response = Mock(status_code=202, json=Mock(return_value={"ok": True}))
    response.__enter__ = Mock(return_value=response)
    response.__exit__ = Mock()
    return response

feedback_session = Mock(post=Mock(side_effect=feedback_post))
feedback_session.__enter__ = Mock(return_value=feedback_session)
feedback_session.__exit__ = Mock()
feedback_transport.requests.Session = lambda: feedback_session


class ComponentWindow(RequestWindow):
    def _build(self):
        super()._build()
        # Explicit test-local storage exercises the production form's persistence
        # without enabling writes to the developer's normal preview state.
        path = os.environ.get("ONPC_REQUEST_COMPONENT_SELECTIONS_PATH")
        if path:
            self._request_content._selection_store = SelectionStore(
                path, child_overlay=self._child_overlay,
            )

    def __init__(self, application, **kwargs):
        super().__init__(application, broker_connection=BROKER, **kwargs)
        # Bare Mutter has no shell to activate a windowed preview.  Exercise
        # the production request-surface state so RemoteDesktop keyboard input
        # has an active fullscreen target in both request modes.
        self.fullscreen()
        if BROKER.scenario in {"pointer", "service-failure-pointer"}:
            self._last_pointer_layout = None
            self.add_tick_callback(self._record_pointer_layout)

    def _record_pointer_layout(self, *_args):
        # AT-SPI reports untransformed widget rectangles for this GTK 3D plane.
        # Observe actual allocated centers through GTK's public transform API;
        # input still travels through Mutter to the real production widgets.
        targets = {}
        reachable = {}
        form = self._request_content
        widgets = (("duration", form._duration_buttons[0]), ("request", form._request))
        if self._stack.get_visible_child_name() == "result":
            widgets = (("result", self._result_action), ("report", self._report_row))
        for name, widget in widgets:
            if widget.get_width() <= 0 or not widget.get_mapped():
                return GLib.SOURCE_CONTINUE
            valid, point = widget.compute_point(self, Graphene.Point().init(
                widget.get_width() / 2, widget.get_height() / 2,
            ))
            if not valid:
                return GLib.SOURCE_CONTINUE
            targets[name] = [point.x, point.y]
            picked = self.pick(point.x, point.y, Gtk.PickFlags.DEFAULT)
            while picked is not None and picked is not widget:
                picked = picked.get_parent()
            reachable[name] = picked is widget
        scrollbar = self._request_surface._scrollbar
        if self._stack.get_visible_child_name() == "request" and scrollbar.get_mapped():
            valid, point = scrollbar.compute_point(self, Graphene.Point().init(
                scrollbar.get_width() / 2, scrollbar.get_height() - 4,
            ))
            if valid:
                targets["scrollbar"] = [point.x, point.y]
                targets["scroll_position"] = [scrollbar.get_adjustment().get_value()]
        layout = (targets, reachable)
        if layout != self._last_pointer_layout:
            BROKER.record("pointer_layout", targets=targets, reachable=reachable)
            self._last_pointer_layout = layout
        return GLib.SOURCE_CONTINUE

    def _logout(self, *_args):
        BROKER.record("logout", overlay=self._child_overlay)
        self._stack.set_visible_child_name("request")

    def _close_overlay(self, *_args):
        BROKER.record("close_overlay", overlay=self._child_overlay)
        self._stack.set_visible_child_name("request")

    def _escape_pressed(self, *args):
        handled = super()._escape_pressed(*args)
        BROKER.record("escape", handled=handled, in_flight=self._state.in_flight)
        return handled

    def _show_result(self, title, detail):
        BROKER.record(
            "result", title=title, detail=detail, overlay=self._child_overlay,
        )
        super()._show_result(title, detail)


overlay = os.environ.get("ONPC_REQUEST_COMPONENT_OVERLAY") == "1"
configure_logging(preview=True, component="child" if overlay else "kiosk")
raise SystemExit(Application(
    preview=True, child_overlay=overlay, window_factory=ComponentWindow,
).run([sys.argv[0]]))
