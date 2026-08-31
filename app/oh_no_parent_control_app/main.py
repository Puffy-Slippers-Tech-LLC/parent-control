"""Libadwaita application for the GNOME Kiosk request station."""

from __future__ import annotations

import logging
import sys

import gi

gi.require_version("Adw", "1")
gi.require_version("Gtk", "4.0")
from gi.repository import Adw, Gio, GLib, Gtk

from .model import RequestState, public_error

BUS_NAME = "com.puffyslippers.OhNoParentControl1"
OBJECT_PATH = "/com/puffyslippers/OhNoParentControl1"
INTERFACE = BUS_NAME
REQUEST_TIMEOUT_MS = 190_000
LOG = logging.getLogger("oh-no-parent-control")


class RequestWindow(Adw.ApplicationWindow):
    def __init__(self, application):
        super().__init__(application=application, title="Oh No! Parent Control")
        self.set_default_size(800, 600)
        self._state = RequestState()
        self._system_bus = Gio.bus_get_sync(Gio.BusType.SYSTEM, None)
        self._durations = []
        self._profiles = []
        self._child_label = ""
        self._build()
        self.connect("map", lambda *_args: self.fullscreen())
        self._load_options()

    def _build(self):
        self._stack = Gtk.Stack(transition_type=Gtk.StackTransitionType.CROSSFADE)
        self.set_content(self._stack)

        self._request_view = self._page("Request more time")
        self._request_status = Gtk.Label(label="Loading administrator-configured choices…")
        self._request_status.set_wrap(True)
        self._request_view.append(self._request_status)
        self._duration_dropdown = Gtk.DropDown()
        self._profile_dropdown = Gtk.DropDown()
        self._duration_row = self._choice_row("Additional time", self._duration_dropdown)
        self._profile_row = self._choice_row("App restriction profile", self._profile_dropdown)
        self._request_view.append(self._duration_row)
        self._request_view.append(self._profile_row)
        self._continue = Gtk.Button(label="Continue", css_classes=["suggested-action"])
        self._continue.connect("clicked", self._show_review)
        self._continue.set_sensitive(False)
        self._request_view.append(self._continue)
        self._stack.add_named(self._request_view, "request")

        self._review_view = self._page("Parent review")
        self._review_summary = Gtk.Label(wrap=True, justify=Gtk.Justification.CENTER)
        self._review_view.append(self._review_summary)
        review_buttons = Gtk.Box(spacing=12, halign=Gtk.Align.CENTER)
        self._cancel = Gtk.Button(label="Cancel")
        self._cancel.connect("clicked", lambda *_args: self._stack.set_visible_child_name("request"))
        self._authorize = Gtk.Button(label="Authorize", css_classes=["suggested-action"])
        self._authorize.connect("clicked", self._request_access)
        review_buttons.append(self._cancel)
        review_buttons.append(self._authorize)
        self._review_view.append(review_buttons)
        self._spinner = Gtk.Spinner()
        self._review_view.append(self._spinner)
        self._stack.add_named(self._review_view, "review")

        self._result_view = self._page("Request result")
        self._result_title = Gtk.Label(css_classes=["title-2"])
        self._result_detail = Gtk.Label(wrap=True, justify=Gtk.Justification.CENTER)
        self._result_view.append(self._result_title)
        self._result_view.append(self._result_detail)
        return_button = Gtk.Button(label="Return to Login", css_classes=["suggested-action"])
        return_button.connect("clicked", lambda *_args: self.get_application().quit())
        self._result_view.append(return_button)
        self._stack.add_named(self._result_view, "result")

    @staticmethod
    def _page(title):
        box = Gtk.Box(
            orientation=Gtk.Orientation.VERTICAL, spacing=24,
            halign=Gtk.Align.CENTER, valign=Gtk.Align.CENTER,
            margin_top=48, margin_bottom=48, margin_start=48, margin_end=48,
        )
        box.append(Gtk.Label(label=title, css_classes=["title-1"]))
        return box

    @staticmethod
    def _choice_row(label, dropdown):
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
        item_label = Gtk.Label(label=label, xalign=0)
        item_label.add_css_class("heading")
        box.append(item_label)
        box.append(dropdown)
        return box

    def _bus_call(self, method, parameters, reply_signature, callback, timeout=30_000):
        self._system_bus.call(
            BUS_NAME, OBJECT_PATH, INTERFACE, method, parameters,
            GLib.VariantType.new(reply_signature), Gio.DBusCallFlags.NONE,
            timeout, None, callback,
        )

    def _load_options(self):
        self._bus_call("GetRequestOptions", None, "(sa(ss)a(ss))", self._options_done)

    def _options_done(self, connection, result):
        try:
            child_label, durations, profiles = connection.call_finish(result).unpack()
            if not durations or not profiles or profiles[0][0] != "":
                raise ValueError("broker returned malformed options")
            self._child_label = child_label
            self._durations = list(durations)
            self._profiles = list(profiles)
            self._duration_dropdown.set_model(Gtk.StringList.new([x[1] for x in durations]))
            self._profile_dropdown.set_model(Gtk.StringList.new([x[1] for x in profiles]))
            self._duration_dropdown.set_selected(0)
            self._profile_dropdown.set_selected(0)
            self._request_status.set_text(f"Request access for {child_label}")
            self._continue.set_sensitive(True)
        except Exception as error:
            LOG.warning("options outcome=unavailable error_type=%s", type(error).__name__)
            self._show_error(error)

    def _selected(self):
        duration = self._durations[self._duration_dropdown.get_selected()]
        profile = self._profiles[self._profile_dropdown.get_selected()]
        return duration, profile

    def _show_review(self, *_args):
        duration, profile = self._selected()
        profile_text = "leave the current app restrictions unchanged" if not profile[0] else (
            f'replace the active restrictions with “{profile[1]}”'
        )
        self._review_summary.set_text(
            f'Grant “{duration[1]}” to {self._child_label} and {profile_text}.\n\n'
            "Press Authorize to open the administrator authentication dialog."
        )
        self._stack.set_visible_child_name("review")

    def _request_access(self, *_args):
        if not self._state.begin():
            return
        duration, profile = self._selected()
        self._set_request_controls(False)
        self._spinner.start()
        LOG.info("duration=%s profile=%s stage=request", duration[0], profile[0] or "none")
        try:
            self._bus_call(
                "RequestAccess", GLib.Variant("(ss)", (duration[0], profile[0])),
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
                self._show_result("Request approved", "The requested access is ready.")
            elif outcome == "cancelled":
                self._show_result("Authorization cancelled", "No changes were made.")
            else:
                self._show_result("Request denied", "No changes were made.")
        except Exception as error:
            self._request_failed(error)
        finally:
            self._state.finish()
            self._set_request_controls(True)
            self._spinner.stop()

    def _request_failed(self, error):
        LOG.warning("outcome=unavailable error_type=%s", type(error).__name__)
        self._state.finish()
        self._set_request_controls(True)
        self._spinner.stop()
        self._show_error(error)

    def _set_request_controls(self, enabled):
        self._authorize.set_sensitive(enabled)
        self._cancel.set_sensitive(enabled)

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

    def do_activate(self):
        window = self.get_active_window() or RequestWindow(self)
        window.present()


def main():
    logging.basicConfig(level=logging.INFO, format="[oh-no-parent-control] %(levelname)s %(message)s")
    return Application().run(sys.argv)


if __name__ == "__main__":
    raise SystemExit(main())
