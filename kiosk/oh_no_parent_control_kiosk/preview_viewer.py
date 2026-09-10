"""Development-only viewer of one existing Mutter monitor.

The operator explicitly permits Mutter 50's private ScreenCast/RemoteDesktop
interfaces here. Production entry points never import this module. All calls
use the launcher's disposable bus; no host desktop capture or input is allowed.
"""

import json
import logging
import os
from pathlib import Path
import signal
import socket
import subprocess

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Gdk", "4.0")
gi.require_version("Gst", "1.0")
gi.require_version("GLibUnix", "2.0")
from gi.repository import Gdk, Gio, GLib, GLibUnix, Gst, Gtk

from .preview_screen import SCREEN, Screen

LOG = logging.getLogger(__name__)
VIEWER_FD = "ONPC_PREVIEW_VIEWER_FD"
CAST = "org.gnome.Mutter.ScreenCast"
REMOTE = "org.gnome.Mutter.RemoteDesktop"
PROPERTIES = "org.freedesktop.DBus.Properties"


class MonitorStream:
    """Lossless RGB PipeWire capture and input on the same monitor/session."""

    def __init__(self, screen, on_frame, on_error):
        self.screen = screen
        self.on_error = on_error
        self.pipeline = None
        self.remote = None
        self.subscription = None
        self.connection = None
        self.keys = set()
        self.buttons = set()
        address = os.environ["DBUS_SESSION_BUS_ADDRESS"]
        runtime = Path(os.environ["PIPEWIRE_RUNTIME_DIR"])
        # The launcher restores XDG_RUNTIME_DIR for the host-facing window.
        # The bus and PipeWire must still name its owned private runtime.
        if (address != f"unix:path={runtime}/bus" or runtime.parent.parent != Path("/tmp")
                or not runtime.parent.name.startswith("onpc-screen-")
                or runtime.stat().st_uid != os.getuid()):
            raise RuntimeError("The screen viewer requires a disposable preview bus.")
        try:
            self.connection = Gio.DBusConnection.new_for_address_sync(
                address, Gio.DBusConnectionFlags.AUTHENTICATION_CLIENT
                | Gio.DBusConnectionFlags.MESSAGE_BUS_CONNECTION, None, None,
            )
            from .preview import DISPLAY_NAME, DISPLAY_PATH
            _, monitors, logical, _ = self.call(DISPLAY_NAME, DISPLAY_PATH, DISPLAY_NAME,
                                               "GetCurrentState")
            if len(monitors) != 1 or len(logical) != 1:
                raise RuntimeError("The screen viewer requires exactly one configured monitor.")
            self.connector = monitors[0][0][0]
            self.logical_width = round(screen.width / logical[0][2])
            self.logical_height = round(screen.height / logical[0][2])
            self.remote, = self.call(REMOTE, "/org/gnome/Mutter/RemoteDesktop", REMOTE,
                                     "CreateSession")
            session_id, = self.call(REMOTE, self.remote, PROPERTIES, "Get",
                                    "(ss)", (REMOTE + ".Session", "SessionId"))
            self.cast, = self.call(CAST, "/org/gnome/Mutter/ScreenCast", CAST,
                                   "CreateSession", "(a{sv})", ({
                                       "remote-desktop-session-id": GLib.Variant("s", session_id),
                                   },))
            self.stream, = self.call(CAST, self.cast, CAST + ".Session", "RecordMonitor",
                                     "(sa{sv})", (self.connector, {
                                         "cursor-mode": GLib.Variant("u", 1),
                                     }))
            self.on_frame = on_frame
            self.subscription = self.connection.signal_subscribe(
                CAST, CAST + ".Stream", "PipeWireStreamAdded", self.stream, None,
                Gio.DBusSignalFlags.NONE, self._stream_added,
            )
            self.call(REMOTE, self.remote, REMOTE + ".Session", "Start")
            # Initialize the seat before the supervisor maps the app. A balanced
            # Shift press/release creates the keyboard without typing anything.
            self.motion(0, 0)
            self.key(42, True)
            self.key(42, False)
        except BaseException:
            self.close()
            raise

    def call(self, service, path, interface, method, signature=None, values=()):
        return self.connection.call_sync(
            service, path, interface, method,
            GLib.Variant(signature, values) if signature else None, None,
            Gio.DBusCallFlags.NO_AUTO_START, 3000, None,
        ).unpack()

    def _stream_added(self, _connection, _sender, _path, _interface, _signal, parameters):
        try:
            node_id, = parameters.unpack()
            # target-object uses the stable PipeWire object serial, not the
            # deprecated GStreamer path property (which takes a node ID).
            objects = json.loads(subprocess.run(
                ["pw-dump"], check=True, capture_output=True, text=True, timeout=3,
            ).stdout)
            serial = next(item["info"]["props"]["object.serial"] for item in objects
                          if item["id"] == node_id and item["type"] == "PipeWire:Interface:Node")
            self.pipeline = Gst.parse_launch(
                f"pipewiresrc target-object={serial} on-disconnect=error ! "
                "video/x-raw ! gtk4paintablesink name=screen sync=false"
            )
            self.sink = self.pipeline.get_by_name("screen")
            self.paintable = self.sink.get_property("paintable")
            self.frame_handler = self.paintable.connect(
                "invalidate-contents", lambda *_: self.on_frame(self.paintable))
            bus = self.pipeline.get_bus()
            bus.add_signal_watch()
            bus.connect("message::error", lambda _bus, message: self.on_error(message.parse_error()[0]))
            if self.pipeline.set_state(Gst.State.PLAYING) == Gst.StateChangeReturn.FAILURE:
                raise RuntimeError("The preview video stream could not start.")
            LOG.info("preview capture connected monitor=%s physical=%dx%d",
                     self.connector, self.screen.width, self.screen.height)
        except Exception as error:
            self.on_error(error)

    def input(self, method, signature, values):
        self.call(REMOTE, self.remote, REMOTE + ".Session", method, signature, values)

    def motion(self, x, y):
        self.input("NotifyPointerMotionAbsolute", "(sdd)", (self.stream, x, y))

    def button(self, code, pressed):
        self.input("NotifyPointerButton", "(ib)", (code, pressed))
        self.buttons.add(code) if pressed else self.buttons.discard(code)

    def key(self, code, pressed):
        self.input("NotifyKeyboardKeycode", "(ub)", (code, pressed))
        self.keys.add(code) if pressed else self.keys.discard(code)

    def release(self):
        for code in tuple(self.keys):
            self.key(code, False)
        for code in tuple(self.buttons):
            self.button(code, False)

    def close(self):
        if self.pipeline:
            self.paintable.disconnect(self.frame_handler)
            self.pipeline.set_state(Gst.State.NULL)
            self.pipeline.get_bus().remove_signal_watch()
            self.pipeline = None
        if self.connection:
            if self.subscription:
                self.connection.signal_unsubscribe(self.subscription)
            if self.remote:
                try:
                    self.release()
                    self.call(REMOTE, self.remote, REMOTE + ".Session", "Stop")
                except GLib.Error:
                    pass  # The owning compositor may already have stopped.
            self.connection.close_sync(None)
            self.connection = None


def content_rectangle(width, height, screen):
    zoom = min(width / screen.width, height / screen.height)
    return ((width - screen.width * zoom) / 2, (height - screen.height * zoom) / 2,
            screen.width * zoom, screen.height * zoom)


class Viewer(Gtk.Application):
    def __init__(self):
        super().__init__(application_id="com.puffyslippers.ScreenPreview",
                         flags=Gio.ApplicationFlags.NON_UNIQUE)
        self.screen = Screen.decode(os.environ[SCREEN])
        self.capture = None
        self.control = None
        self.video_connected = False
        self.app_mapped = VIEWER_FD not in os.environ
        self.ready = False
        self.failed = False
        self.connect("activate", self._activate)
        self.connect("shutdown", self._shutdown)

    def _shutdown(self, *_args):
        if self.capture:
            self.capture.close()
        if self.control:
            self.control.close()

    def _control_message(self, _fd, condition):
        if condition & (GLib.IOCondition.HUP | GLib.IOCondition.ERR):
            self.quit()
            return False
        if self.control.recv(4096) == b"app-ready":
            self.app_mapped = True
        return True

    def _activate(self, *_args):
        try:
            Gst.init(None)
            for factory in ("pipewiresrc", "gtk4paintablesink"):
                if not Gst.ElementFactory.find(factory):
                    raise RuntimeError(f"{factory} is required. Run ./setup.sh --dependencies-only.")
            self.window = Gtk.ApplicationWindow(application=self, title="Screen Preview")
            header = Gtk.HeaderBar()
            header.set_title_widget(Gtk.Label(label=(
                f"{self.screen.width} × {self.screen.height} · {self.screen.percent}% display scale")))
            self.pixel_view = Gtk.ToggleButton(label="100% pixels")
            self.pixel_view.set_tooltip_text("One captured pixel per host display pixel; scroll to inspect.")
            header.pack_end(self.pixel_view)
            self.window.set_titlebar(header)
            self.picture = Gtk.Picture(can_shrink=True, content_fit=Gtk.ContentFit.CONTAIN,
                                       hexpand=True, vexpand=True, focusable=True)
            self.picture.set_cursor_from_name("none")  # Cursor is embedded by Mutter.
            self.scroller = Gtk.ScrolledWindow(hexpand=True, vexpand=True)
            self.scroller.set_child(self.picture)
            self.status = Gtk.Label(label="Connecting to preview screen…", margin_top=6, margin_bottom=6)
            box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
            box.append(self.scroller)
            box.append(self.status)
            self.window.set_child(box)
            self.window.set_default_size(1100, 760)
            self.pixel_view.connect("toggled", self._zoom_changed)
            self.window.connect("notify::is-active", self._focus_changed)
            self._install_input()
            self.window.present()
            self.window.get_surface().connect("notify::scale", self._zoom_changed)
            self._zoom_changed()
            if VIEWER_FD in os.environ:
                self.control = socket.socket(fileno=int(os.environ.pop(VIEWER_FD)))
                GLib.io_add_watch(self.control.fileno(), GLib.IOCondition.IN | GLib.IOCondition.HUP,
                                  self._control_message)
            self.capture = MonitorStream(self.screen, self._frame, self._error)
            GLib.timeout_add_seconds(20, self._startup_timeout)
        except Exception as error:
            self._error(error)

    def _zoom_changed(self, *_args):
        pixel_view = self.pixel_view.get_active()
        scale = self.window.get_surface().get_scale()
        self.picture.set_halign(Gtk.Align.CENTER if pixel_view else Gtk.Align.FILL)
        self.picture.set_valign(Gtk.Align.CENTER if pixel_view else Gtk.Align.FILL)
        self.picture.set_size_request(round(self.screen.width / scale) if pixel_view else -1,
                                      round(self.screen.height / scale) if pixel_view else -1)
        self.scroller.set_policy(Gtk.PolicyType.AUTOMATIC if pixel_view else Gtk.PolicyType.NEVER,
                                 Gtk.PolicyType.AUTOMATIC if pixel_view else Gtk.PolicyType.NEVER)
        self.status.set_text("100% pixels · Scroll to inspect" if pixel_view
                             else "Fit to window · Screen resolution and app layout stay unchanged")

    def _frame(self, paintable):
        dimensions = (paintable.get_intrinsic_width(), paintable.get_intrinsic_height())
        if 0 in dimensions:
            return  # Paintable clears during stream setup/teardown.
        if dimensions != (
                self.screen.width, self.screen.height):
            self._error(RuntimeError("The captured frame does not match the selected resolution."))
            return
        self.picture.set_paintable(paintable)
        if not self.video_connected:
            self.video_connected = True
            if self.control:
                self.control.send(b"video")
        if not self.ready and self.app_mapped and self.window.get_mapped():
            self.ready = True
            LOG.info("preview viewer received full-resolution frame %dx%d",
                     self.screen.width, self.screen.height)
            if self.control:
                self.control.send(b"ready")
            self.picture.grab_focus()

    def _startup_timeout(self):
        if not self.ready:
            self._error(RuntimeError("No preview video arrived within 20 seconds."))
        return GLib.SOURCE_REMOVE

    def _error(self, error):
        # No input values, account data or session environment in diagnostics.
        LOG.error("preview viewer failed: %s", error)
        self.failed = True
        self.quit()

    def _focus_changed(self, *_args):
        if self.capture and not self.window.is_active():
            self.capture.release()

    def _motion(self, _controller, x, y):
        if not self.ready:
            return False
        left, top, width, height = content_rectangle(
            self.picture.get_width(), self.picture.get_height(), self.screen)
        if not (left <= x < left + width and top <= y < top + height):
            return False
        # RecordMonitor's absolute-input coordinates are captured pixels;
        # Mutter divides by the monitor scale when delivering Wayland input.
        self.capture.motion((x - left) / width * self.screen.width,
                            (y - top) / height * self.screen.height)
        return True

    def _click(self, gesture, _count, x, y, pressed):
        codes = {1: 272, 2: 274, 3: 273, 8: 275, 9: 276}
        code = codes.get(gesture.get_current_button())
        inside = self._motion(gesture, x, y)
        if self.capture and code and (inside or (not pressed and code in self.capture.buttons)):
            self.picture.grab_focus()
            self.capture.button(code, pressed)

    def _install_input(self):
        motion = Gtk.EventControllerMotion()
        motion.connect("motion", self._motion)
        self.picture.add_controller(motion)
        click = Gtk.GestureClick(button=0)
        click.connect("pressed", lambda g, n, x, y: self._click(g, n, x, y, True))
        click.connect("released", lambda g, n, x, y: self._click(g, n, x, y, False))
        self.picture.add_controller(click)
        keys = Gtk.EventControllerKey()
        keys.connect("key-pressed", self._key_pressed)
        keys.connect("key-released", self._key_released)
        self.picture.add_controller(keys)
        scroll = Gtk.EventControllerScroll(flags=Gtk.EventControllerScrollFlags.BOTH_AXES)
        scroll.connect("scroll", self._scroll)
        self.picture.add_controller(scroll)

    def _key_pressed(self, _controller, _keyval, keycode, _state):
        if self.ready and keycode >= 8:
            self.capture.key(keycode - 8, True)
            return True
        return False

    def _key_released(self, _controller, _keyval, keycode, _state):
        if self.ready and keycode >= 8:
            self.capture.key(keycode - 8, False)

    def _scroll(self, _controller, dx, dy):
        if self.ready:
            self.capture.input("NotifyPointerAxis", "(ddu)", (dx * 15, dy * 15, 0))
            self.capture.input("NotifyPointerAxis", "(ddu)", (0, 0, 1))
        return True


def run(viewer):
    for sig in (signal.SIGTERM, signal.SIGINT, signal.SIGHUP):
        GLibUnix.signal_add(GLib.PRIORITY_DEFAULT, sig, lambda: (viewer.quit(), False)[1])
    viewer.run([])
    return 1 if viewer.failed else 0


def main():
    logging.basicConfig(level=logging.INFO)
    return run(Viewer())


if __name__ == "__main__":
    raise SystemExit(main())
