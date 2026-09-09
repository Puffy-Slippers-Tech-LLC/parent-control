"""One reviewable error-report flow for the unprivileged GTK front ends.

Exception messages are draft content, never log content. No report is sent
until the user explicitly submits it in the feedback dialog.
"""

from dataclasses import dataclass
import logging
import sys
import threading

LOG = logging.getLogger("oh-no-parent-control-ui")
COMPONENTS = frozenset(("Kiosk App", "Child App", "Parent App"))
GENERIC_TITLE = "Something went wrong"
GENERIC_DETAIL = "The operation could not be completed. Please try again later."


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
        return f"{self.title}\n{self.detail}\n\n--------------------\n\n{self.internal}"

    @classmethod
    def capture(cls, component, error, title=GENERIC_TITLE, detail=GENERIC_DETAIL):
        if component not in COMPONENTS:
            raise ValueError("Unknown error-report component")
        # Preserve causes and exception messages without frame locals or a
        # traceback's source lines, which can contain credentials and paths.
        messages, seen = [], set()
        current = error
        while current is not None and id(current) not in seen:
            seen.add(id(current))
            messages.append(f"{type(current).__name__}: {current}")
            current = current.__cause__ or (
                None if current.__suppress_context__ else current.__context__
            )
        return cls(component, _bounded(title, 150), _bounded(detail, 600),
                   _bounded("\nCaused by: ".join(messages), 3500))


class ErrorHandler:
    def __init__(self, parent, component, *, dialog_factory=None):
        self.parent = parent
        self.component = component
        self._dialog_factory = dialog_factory
        self._dialog = None
        self._presenting = False

    def capture(self, error, title=GENERIC_TITLE, detail=GENERIC_DETAIL):
        LOG.warning("application error component=%s error_type=%s",
                    self.component, type(error).__name__)
        return ErrorReport.capture(self.component, error, title, detail)

    def handle(self, error, title=GENERIC_TITLE, detail=GENERIC_DETAIL, *, on_close=None):
        return self.present(self.capture(error, title, detail), on_close=on_close)

    def present(self, report, *, on_close=None):
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
            LOG.warning("error reporter unavailable component=%s error_type=%s",
                        self.component, type(error).__name__)
            self._dialog = None
            from gi.repository import Adw
            fallback = Adw.AlertDialog.new(
                "Error report unavailable",
                "The feedback dialog could not be opened. Please try again later.",
            )
            fallback.add_response("close", "Close")
            fallback.set_close_response("close")
            if on_close is not None:
                fallback.connect("response", lambda *_: on_close())
            fallback.present(self.parent)
            return None
        finally:
            self._presenting = False


def show_startup_error(application, component, error):
    """Show a reporting-only surface when management/request startup fails."""
    from gi.repository import Adw, Gtk
    existing = getattr(application, "_startup_error_window", None)
    if existing is not None:
        existing.present()
        if existing._errors._dialog is not None:
            existing._errors._dialog.present()
        return existing
    window = Adw.ApplicationWindow(application=application, title=GENERIC_TITLE,
                                   default_width=560, default_height=180)
    window.set_content(Gtk.Label(label=GENERIC_DETAIL, wrap=True,
                                 margin_start=24, margin_end=24))
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
            LOG.warning("uncaught error presentation failed error_type=%s", type(caught).__name__)
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
