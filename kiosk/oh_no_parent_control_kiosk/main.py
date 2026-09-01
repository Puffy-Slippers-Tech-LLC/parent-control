"""Libadwaita application for the GNOME Kiosk request station."""

from __future__ import annotations

import logging
import json
import sys
from pathlib import Path

import gi

gi.require_version("Adw", "1")
gi.require_version("Gtk", "4.0")
from gi.repository import Adw, Gio, GLib, Gtk

from .model import RequestState, public_error
from .request_content import RequestContent

BUS_NAME = "com.puffyslippers.OhNoParentControl1"
OBJECT_PATH = "/com/puffyslippers/OhNoParentControl1"
INTERFACE = BUS_NAME
# An authorization prompt remains open until the administrator responds.
# G_MAXINT is GIO's supported no-timeout value.
REQUEST_TIMEOUT_MS = GLib.MAXINT
# Keep the confirmation visible briefly before returning to GDM.
SUCCESS_LOGOUT_DELAY_MS = 3_000
LOG = logging.getLogger("oh-no-parent-control")


class BrokerLogHandler(logging.Handler):
    """Forward kiosk records to the broker-owned daily log."""

    def __init__(self):
        super().__init__()
        self._connection = None

    def emit(self, record):
        try:
            if self._connection is None:
                self._connection = Gio.bus_get_sync(Gio.BusType.SYSTEM, None)
            self._connection.call(
                BUS_NAME, OBJECT_PATH, INTERFACE, "LogEvent",
                GLib.Variant("(sss)", ("kiosk", record.levelname, self.format(record))),
                GLib.VariantType.new("()"), Gio.DBusCallFlags.NONE, 5_000, None, None,
            )
        except Exception:
            self._connection = None


def configure_logging():
    handler = BrokerLogHandler()
    handler.setFormatter(logging.Formatter("%(name)s: %(message)s"))
    root = logging.getLogger()
    root.handlers.clear()
    root.addHandler(handler)
    root.setLevel(logging.INFO)


class RequestWindow(Adw.ApplicationWindow):
    def __init__(self, application):
        super().__init__(application=application, title="Oh No! Parent Control")
        self.add_css_class("oh-no-parent-control-window")
        self.set_default_size(800, 600)
        self._state = RequestState()
        self._success_logout_source_id = None
        self._system_bus = Gio.bus_get_sync(Gio.BusType.SYSTEM, None)
        self._build()
        LOG.info("request station window initialized")
        self.connect("map", lambda *_args: self.fullscreen())
        self._load_users()

    def _build(self):
        self._stack = Gtk.Stack(transition_type=Gtk.StackTransitionType.CROSSFADE)
        self.set_content(self._stack)
        self._request_content = RequestContent(
            self._request_access, self._logout, self._load_users,
            self._load_preferences,
        )
        self._stack.add_named(self._request_content, "request")

        self._result_view = self._page("Request result")
        self._result_title = Gtk.Label(css_classes=["oh-no-parent-control-page-title"])
        self._result_detail = Gtk.Label(wrap=True, justify=Gtk.Justification.CENTER)
        self._result_view.append(self._result_title)
        self._result_view.append(self._result_detail)
        return_button = Gtk.Button(label="Return to Login")
        return_button.add_css_class("oh-no-parent-control-request-button")
        return_button.connect("clicked", self._logout)
        self._result_view.append(return_button)
        self._stack.add_named(self._result_view, "result")

    @staticmethod
    def _page(title):
        box = Gtk.Box(
            orientation=Gtk.Orientation.VERTICAL, spacing=24,
            halign=Gtk.Align.CENTER, valign=Gtk.Align.CENTER,
        )
        box.add_css_class("oh-no-parent-control-dialog")
        box.add_css_class("oh-no-parent-control-secondary-page")
        box.append(Gtk.Label(label=title, css_classes=["oh-no-parent-control-page-title"]))
        return box

    def _logout(self, *_args):
        # OnSuccess=gnome-session-shutdown.target on the application unit turns
        # this clean exit into a supported kiosk-session logout back to GDM.
        LOG.info("return to login requested")
        self.get_application().quit()

    def _logout_after_success(self):
        self._success_logout_source_id = None
        LOG.info("approved request acknowledged; returning to login")
        self._logout()
        return GLib.SOURCE_REMOVE

    def _schedule_success_logout(self):
        if self._success_logout_source_id is not None:
            GLib.source_remove(self._success_logout_source_id)
        self._success_logout_source_id = GLib.timeout_add(
            SUCCESS_LOGOUT_DELAY_MS, self._logout_after_success,
        )

    def _bus_call(self, method, parameters, reply_signature, callback, timeout=30_000):
        self._system_bus.call(
            BUS_NAME, OBJECT_PATH, INTERFACE, method, parameters,
            GLib.VariantType.new(reply_signature), Gio.DBusCallFlags.NONE,
            timeout, None, callback,
        )

    def _load_users(self, *_args):
        LOG.info("request-account discovery started")
        self._request_content.set_loading()
        self._bus_call("ListManagedUsers", None, "(a(us))", self._users_done)
        self._bus_call("ListApprovers", None, "(a(us))", self._approvers_done)

    def _users_done(self, connection, result):
        try:
            users, = connection.call_finish(result).unpack()
            LOG.info("managed-user discovery completed count=%d", len(users))
            self._request_content.set_accounts(users)
        except Exception as error:
            LOG.warning("users outcome=unavailable error_type=%s", type(error).__name__)
            self._show_error(error)

    def _approvers_done(self, connection, result):
        try:
            users, = connection.call_finish(result).unpack()
            LOG.info("approver discovery completed count=%d", len(users))
            self._request_content.set_approvers(users)
        except Exception as error:
            LOG.warning("approvers outcome=unavailable error_type=%s", type(error).__name__)
            self._show_error(error)

    def _load_preferences(self, target_uid):
        LOG.info("preferences load started target_uid=%d", target_uid)
        self._bus_call(
            "GetPreferences", GLib.Variant("(u)", (target_uid,)), "(s)",
            self._preferences_done,
        )

    def _preferences_done(self, connection, result):
        try:
            encoded, = connection.call_finish(result).unpack()
            self._request_content.set_preferences(json.loads(encoded))
            LOG.info("preferences load completed")
        except Exception as error:
            LOG.warning("preferences outcome=unavailable error_type=%s", type(error).__name__)

    def _request_access(self, *_args):
        if not self._state.begin():
            return
        try:
            target_uid, target_label, approver_uid, duration_seconds, allow_soft = \
                self._request_content.selected()
            selected, custom, allow_soft = self._request_content.selected_preferences()
        except ValueError as error:
            self._state.finish()
            self._request_content.show_validation_error(str(error))
            return
        self._set_request_controls(False)
        self._requested_label = target_label
        LOG.info("target_uid=%d approver_uid=%d duration_seconds=%d "
                 "allow_soft=%s stage=request", target_uid, approver_uid,
                 duration_seconds, allow_soft)
        try:
            self._pending_request = (
                target_uid, approver_uid, duration_seconds, allow_soft,
            )
            self._bus_call(
                "UpdateRequestPreferences",
                GLib.Variant("(usdb)", (target_uid, selected, custom, allow_soft)),
                "(s)", self._preferences_saved,
            )
        except Exception as error:
            self._request_failed(error)

    def _preferences_saved(self, connection, result):
        try:
            connection.call_finish(result)
            target_uid, approver_uid, duration_seconds, allow_soft = self._pending_request
            self._bus_call(
                "RequestAccess",
                GLib.Variant(
                    "(uuub)",
                    (target_uid, approver_uid, duration_seconds, allow_soft),
                ),
                "(ss)", self._request_done, REQUEST_TIMEOUT_MS,
            )
        except Exception as error:
            self._request_failed(error)

    def _request_done(self, connection, result):
        try:
            correlation_id, outcome = connection.call_finish(result).unpack()
            if outcome not in {"approved", "denied", "cancelled"}:
                raise ValueError("broker returned malformed result")
            LOG.info("request=%s outcome=%s", correlation_id, outcome)
            if outcome == "approved":
                self._show_result(
                    "Request approved", f"The requested access is ready for {self._requested_label}."
                )
                self._schedule_success_logout()
            elif outcome == "cancelled":
                # Cancellation is not an error or a session transition.  The
                # administrator returns to the same kiosk request form without
                # an additional message.
                self._request_content.clear_validation_error()
                self._stack.set_visible_child_name("request")
            else:
                # A completed authorization attempt that was not approved
                # (for example, an incorrect password) is actionable, so keep
                # the request choices visible and show the error in place.
                self._request_content.show_validation_error("Request denied")
                self._stack.set_visible_child_name("request")
        except Exception as error:
            self._request_failed(error)
        finally:
            self._state.finish()
            self._set_request_controls(True)

    def _request_failed(self, error):
        LOG.warning("outcome=unavailable error_type=%s", type(error).__name__)
        self._state.finish()
        self._set_request_controls(True)
        self._show_error(error)

    def _set_request_controls(self, enabled):
        self._request_content.set_controls_sensitive(enabled)

    def _show_error(self, error):
        title, detail = public_error(error)
        self._show_result(title, detail)

    def _show_result(self, title, detail):
        self._result_title.set_text(title)
        self._result_detail.set_text(detail)
        self._stack.set_visible_child_name("result")


class Application(Adw.Application):
    def __init__(self):
        super().__init__(application_id="com.puffyslippers.OhNoParentControl")
        Adw.StyleManager.get_default().set_color_scheme(Adw.ColorScheme.FORCE_DARK)
        self._css_provider = None

    def do_activate(self):
        window = self.get_active_window() or RequestWindow(self)
        if self._css_provider is None:
            self._css_provider = Gtk.CssProvider()
            self._css_provider.load_from_path(str(Path(__file__).with_name("style.css")))
            Gtk.StyleContext.add_provider_for_display(
                window.get_display(), self._css_provider,
                Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION,
            )
        window.present()


def main():
    configure_logging()
    LOG.info("kiosk app starting")
    return Application().run(sys.argv)


if __name__ == "__main__":
    raise SystemExit(main())
