"""Production request window with deterministic asynchronous broker replies."""

from __future__ import annotations

import copy
import json
import os
import sys

from gi.repository import GLib

from kiosk.oh_no_parent_control_kiosk.main import Application, RequestWindow, configure_logging


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
        if self.scenario == "service-failure" and method.startswith("Request"):
            return Reply(error=RuntimeError("org.example.Secret /private/path"))
        if method == "GetOwnAccount":
            return Reply(USERS[0])
        if method == "ListManagedUsers":
            return Reply((() if self.scenario == "no-children" else USERS,))
        if method == "ListApprovers":
            return Reply((() if self.scenario == "no-approvers" else APPROVERS,))
        if method == "GetPreferences":
            return Reply((json.dumps(self.preferences[values[0]]),))
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


class ComponentWindow(RequestWindow):
    def __init__(self, application, **kwargs):
        super().__init__(application, broker_connection=BROKER, **kwargs)
        # Bare Mutter has no shell to activate a windowed preview.  Exercise
        # the production request-surface state so RemoteDesktop keyboard input
        # has an active fullscreen target in both request modes.
        self.fullscreen()

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
