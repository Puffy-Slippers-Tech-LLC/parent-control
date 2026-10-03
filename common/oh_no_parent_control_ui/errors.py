"""Error reports contain fixed categories only, never exception messages."""

from common.oh_no_parent_control_ui import messages as m

from dataclasses import dataclass
from common.oh_no_parent_control_ui.diagnostic_events import get_logger, error_code, ERROR_CODES
from common.oh_no_parent_control_ui.diagnostic_events import record_exception
import sys
import threading

LOG = get_logger("errors")
COMPONENTS = frozenset(("Kiosk App", "Child App", "Parent App"))
GENERIC_TITLE = m.SOMETHING_WENT_WRONG
GENERIC_DETAIL = m.THE_OPERATION_COULD_NOT_BE_COMPLETED_PLEASE_TRY_AGAIN_LATER


def broker_reboot_required(error):
    """Recognize a fixed broker status, never message text or a generic outage."""
    from gi.repository import Gio, GLib
    return (isinstance(error, GLib.Error) and Gio.DBusError.get_remote_error(error) ==
            'com.puffyslippers.OhNoParentControl1.Error.RebootRequired')


def request_reboot(done):
    """Ask logind as the caller, retaining its authorization/inhibitor policy."""
    from gi.repository import Gio, GLib

    def completed(connection, result):
        try:
            connection.call_finish(result)
        except Exception as error:
            done(error)
        else:
            done(None)

    def connected(_source, result):
        try:
            connection = Gio.bus_get_finish(result)
            connection.call(
                'org.freedesktop.login1', '/org/freedesktop/login1',
                'org.freedesktop.login1.Manager', 'Reboot', GLib.Variant('(b)', (True,)),
                GLib.VariantType.new('()'), Gio.DBusCallFlags.NONE, 120_000, None,
                completed,
            )
        except Exception as error:
            done(error)

    try:
        Gio.bus_get(Gio.BusType.SYSTEM, None, connected)
    except Exception as error:
        done(error)


def show_update_required(parent=None, *, application=None, on_close=None):
    """One shared, localized notice for a confirmed pending product reboot."""
    from gi.repository import Gtk
    from .translation_widgets import localized, set_text
    from .accessibility import add_dialog_button, add_identified_window_controls, set_automation_id
    owner = parent if parent is not None else application
    if owner is None:
        raise ValueError('An update notice requires a window or application')
    existing = getattr(owner, '_update_required_dialog', None)
    if existing is not None:
        existing.present()
        return existing
    application_options = {'application': application} if application is not None else {}
    dialog = localized(Gtk.Dialog, title=m.RESTART_REQUIRED, transient_for=parent,
                       modal=True, destroy_with_parent=True, default_width=480,
                       **application_options)
    set_automation_id(dialog, 'update-required-dialog')
    header = Gtk.HeaderBar()
    add_identified_window_controls(header, 'update-required-window-controls')
    dialog.set_titlebar(header)
    message = localized(Gtk.Label, label=m.RESTART_FOR_PROPER_OPERATION, wrap=True,
                        margin_top=24, margin_bottom=24, margin_start=24, margin_end=24)
    set_automation_id(message, 'update-required-message')
    dialog.get_content_area().append(message)
    status = localized(Gtk.Label, label='', wrap=True, visible=False,
                       margin_bottom=16, margin_start=24, margin_end=24)
    set_automation_id(status, 'update-required-status')
    dialog.get_content_area().append(status)
    close = add_dialog_button(dialog, m.CLOSE, Gtk.ResponseType.CLOSE, 'update-required-close')
    reboot = add_dialog_button(dialog, m.REBOOT_NOW, Gtk.ResponseType.ACCEPT,
                               'update-required-reboot', css_class='destructive-action')
    dialog.set_default_response(Gtk.ResponseType.CLOSE)
    owner._update_required_dialog = dialog
    pending = False

    def closed(current, _response):
        nonlocal pending
        if pending:
            return
        if _response == Gtk.ResponseType.ACCEPT:
            pending = True
            close.set_sensitive(False)
            reboot.set_sensitive(False)
            status.set_visible(False)

            def finished(error):
                nonlocal pending
                if error is not None:
                    record_exception(error)
                    pending = False
                    close.set_sensitive(True)
                    reboot.set_sensitive(True)
                    set_text(status, 'label', GENERIC_DETAIL)
                    status.set_visible(True)
                # Success means accepted, not yet rebooted. Never issue an
                # automatic retry or dismiss into apparently working controls.

            request_reboot(finished)
            return
        owner._update_required_dialog = None
        current.destroy()
        if on_close is not None:
            on_close()

    dialog.connect('response', closed)
    dialog.connect('close-request', lambda *_: pending)
    dialog.present()
    return dialog


def _bounded(text, limit):
    # Leave room for user additions within the transport's 5,000 UTF-16 limit.
    cleaned = text.replace("\0", "�")
    encoded = cleaned.encode("utf-16-le", errors="replace")
    if len(encoded) <= limit * 2:
        return cleaned
    return encoded[:(limit - 14) * 2].decode("utf-16-le", errors="ignore") + "\n[truncated]"


@dataclass(frozen=True)
class ErrorReport:
    component: str
    title: str
    detail: str
    internal: str

    @property
    def subject(self):
        return f"[Oh No! Parent Control] [{self.component}] Error Report"

    @property
    def message(self):
        codes = self.internal.split(",") if type(self.internal) is str else []
        safe = codes if 0 < len(codes) <= 8 and all(code in ERROR_CODES for code in codes) else ["other"]
        return (GENERIC_TITLE + "\n" + GENERIC_DETAIL + "\n\n"
                + m.ERROR_CATEGORIES % {'categories': ", ".join(safe)})

    @classmethod
    def capture(cls, component, error, title=GENERIC_TITLE, detail=GENERIC_DETAIL):
        if component not in COMPONENTS:
            raise ValueError("Unknown error-report component")
        # Do not format exception messages, arbitrary caller explanations,
        # tracebacks, source lines, paths, or locals into the report.
        messages, seen = [], set()
        current = error
        while current is not None and id(current) not in seen and len(messages) < 8:
            seen.add(id(current))
            messages.append(error_code(current))
            current = current.__cause__ or (
                None if current.__suppress_context__ else current.__context__
            )
        return cls(component, GENERIC_TITLE, GENERIC_DETAIL, ",".join(messages))


class ErrorHandler:
    def __init__(self, parent, component, *, dialog_factory=None):
        self.parent = parent
        self.component = component
        self._dialog_factory = dialog_factory
        self._dialog = None
        self._presenting = False

    def capture(self, error, title=GENERIC_TITLE, detail=GENERIC_DETAIL):
        record_exception(error)
        LOG.warning("errors.001", component=self.component, error_type=error_code(error))
        return ErrorReport.capture(self.component, error, title, detail)

    def handle(self, error, title=GENERIC_TITLE, detail=GENERIC_DETAIL, *, on_close=None):
        return self.present(self.capture(error, title, detail), on_close=on_close)

    def present(self, report, *, on_close=None):
        from .translation_widgets import localized
        # Repeated polling failures must not overwrite an edited/in-flight draft
        # or create a modal window storm. A later error can open a fresh report
        # after this one is dismissed.
        if self._presenting:
            return None
        if self._dialog is not None:
            self._dialog.present()
            return self._dialog
        self._presenting = True
        try:
            factory = self._dialog_factory
            if factory is None:
                from .feedback import FeedbackDialog
                factory = FeedbackDialog

            def closed():
                dialog, self._dialog = self._dialog, None
                if dialog is not None:
                    dialog.destroy()
                if on_close is not None:
                    on_close()

            self._dialog = factory(
                self.parent, kiosk_session=self.component == "Kiosk App",
                report=report, on_close=closed,
            )
            self._dialog.present()
            return self._dialog
        except Exception as error:
            # Reporting failures cannot recursively trigger another reporter.
            LOG.warning("errors.002", component=self.component, error_type=error_code(error))
            self._dialog = None
            from gi.repository import Gtk
            from .accessibility import (
                add_dialog_button,
                add_identified_window_controls,
                set_automation_id,
            )
            fallback = localized(Gtk.Dialog, 
                title=m.ERROR_REPORT_UNAVAILABLE, transient_for=self.parent, modal=True,
            )
            set_automation_id(fallback, "error-report-unavailable-dialog")
            header = Gtk.HeaderBar()
            add_identified_window_controls(
                header, "error-report-unavailable-window-controls",
            )
            fallback.set_titlebar(header)
            message = localized(Gtk.Label, 
                label=m.THE_FEEDBACK_DIALOG_COULD_NOT_BE_OPENED_PLEASE_TRY_AGAIN_LATER,
                wrap=True, xalign=0,
                margin_top=18, margin_bottom=18, margin_start=18, margin_end=18,
            )
            set_automation_id(message, "error-report-unavailable-message")
            fallback.get_content_area().append(message)
            add_dialog_button(
                fallback, m.CLOSE, Gtk.ResponseType.CLOSE,
                "error-report-unavailable-close",
                description=m.CLOSE_THE_ERROR_REPORT_NOTICE,
            )
            fallback.set_default_response(Gtk.ResponseType.CLOSE)
            fallback.connect("response", lambda current, _response: current.destroy())
            if on_close is not None:
                fallback.connect("response", lambda *_: on_close())
            fallback.present(self.parent)
            return None
        finally:
            self._presenting = False


def show_startup_error(application, component, error):
    """Show a reporting-only surface when management/request startup fails."""
    from gi.repository import Adw, Gtk
    from .translation_widgets import localized
    from .accessibility import add_identified_window_controls, set_automation_id
    existing = getattr(application, "_startup_error_window", None)
    if existing is not None:
        existing.present()
        if existing._errors._dialog is not None:
            existing._errors._dialog.present()
        return existing
    window = localized(Adw.ApplicationWindow, application=application, title=GENERIC_TITLE,
                                   default_width=560, default_height=180)
    set_automation_id(window, "startup-error-window")
    toolbar = Adw.ToolbarView()
    header = Adw.HeaderBar()
    add_identified_window_controls(header, "startup-error-window-controls")
    toolbar.add_top_bar(header)
    message = localized(Gtk.Label, label=GENERIC_DETAIL, wrap=True,
                        margin_start=24, margin_end=24)
    set_automation_id(message, "startup-error-message")
    toolbar.set_content(message)
    window.set_content(toolbar)
    window.present()
    application._startup_error_window = window
    window._errors = ErrorHandler(window, component)
    window._errors.handle(error, on_close=application.quit)
    return window


def install_exception_hooks(application, component):
    """Route uncaught Python/GTK callbacks and workers onto the GTK main loop."""
    from gi.repository import GLib
    previous, previous_thread = sys.excepthook, threading.excepthook
    pending = False
    stopped = False
    lock = threading.Lock()

    def deliver(error):
        nonlocal pending
        try:
            if stopped:
                return GLib.SOURCE_REMOVE
            window = next((w for w in application.get_windows()
                           if hasattr(w, "_show_error")), None)
            if window is None:
                show_startup_error(application, component, error)
            else:
                try:
                    window._show_error(error)
                except Exception:
                    # A partially constructed window may not have its public
                    # error surface yet. Keep startup failures reviewable.
                    show_startup_error(application, component, error)
        except Exception as caught:
            LOG.warning("errors.003", error_type=error_code(caught))
        finally:
            with lock:
                pending = False
        return GLib.SOURCE_REMOVE

    def uncaught(kind, error, _traceback):
        nonlocal pending
        if issubclass(kind, (SystemExit, KeyboardInterrupt)):
            return
        with lock:
            if pending or stopped:
                return
            pending = True
        GLib.idle_add(deliver, error)

    def thread_uncaught(args):
        uncaught(args.exc_type, args.exc_value, args.exc_traceback)

    def shutdown(*_args):
        nonlocal stopped
        with lock:
            stopped = True
        if sys.excepthook is uncaught:
            sys.excepthook = previous
        if threading.excepthook is thread_uncaught:
            threading.excepthook = previous_thread

    sys.excepthook = uncaught
    threading.excepthook = thread_uncaught
    application.connect("shutdown", shutdown)
