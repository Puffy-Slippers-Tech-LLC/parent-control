"""Owned, disposable Mutter screen for kiosk and child fullscreen previews.

The launcher creates its own bus, PipeWire, compositor and viewer. DisplayConfig
is used only through a connection to that explicit private bus, never bus_get.
Each new screen is verified before the previous preview is stopped.
"""

import argparse
from contextlib import ExitStack
import logging
import os
from pathlib import Path
import select
import shutil
import signal
import socket
import subprocess
import sys
import tempfile
import time

from .preview_screen import ACTUAL_SCALE, CONTROL_FD, SCREEN, Screen

LOG = logging.getLogger(__name__)
DISPLAY_NAME = "org.gnome.Mutter.DisplayConfig"
DISPLAY_PATH = "/org/gnome/Mutter/DisplayConfig"
REGISTRY_PATHS = ("/usr/libexec/at-spi2-registryd", "/usr/lib/at-spi2-core/at-spi2-registryd",
                  "/usr/lib/at-spi2-registryd")


class OwnedProcess:
    """Signals target only the unreaped direct child held by this Popen."""

    def __init__(self, command, **kwargs):
        self.child = subprocess.Popen(command, start_new_session=True, **kwargs)

    def close(self):
        if self.child.poll() is not None:
            return
        self.child.terminate()
        try:
            self.child.wait(timeout=5)
        except subprocess.TimeoutExpired:
            self.child.kill()
            self.child.wait(timeout=5)


def private_environment(root, host):
    environment = dict(host)
    for key in ("DISPLAY", "WAYLAND_DISPLAY", "DBUS_SESSION_BUS_ADDRESS",
                "AT_SPI_BUS_ADDRESS", "GDK_SCALE", "GDK_DPI_SCALE", "GTK_THEME",
                "GSK_RENDERER", "GSETTINGS_SCHEMA_DIR", "GTK_EXE_PREFIX",
                "GTK_IM_MODULE", "GTK_IM_MODULE_FILE", "GTK_MODULES", "GTK_PATH",
                "GI_TYPELIB_PATH", "LD_LIBRARY_PATH", "LD_PRELOAD", "GIO_EXTRA_MODULES",
                "GIO_MODULE_DIR", "GTK_A11Y", "GTK_USE_PORTAL",
                "PIPEWIRE_REMOTE", "PIPEWIRE_CONFIG_DIR", "PIPEWIRE_CONFIG_NAME",
                "PIPEWIRE_CONFIG_PREFIX", "WIREPLUMBER_CONFIG_DIR", "WIREPLUMBER_DATA_DIR",
                "WIREPLUMBER_MODULE_DIR", "WIREPLUMBER_PROFILE",
                CONTROL_FD, SCREEN, ACTUAL_SCALE):
        environment.pop(key, None)
    for key, directory in (("XDG_CONFIG_HOME", "config"), ("XDG_CACHE_HOME", "cache"),
                           ("XDG_DATA_HOME", "data"), ("XDG_STATE_HOME", "state"),
                           ("XDG_RUNTIME_DIR", "runtime")):
        path = root / directory
        path.mkdir(mode=0o700)
        environment[key] = str(path)
    environment.update({
        "GSETTINGS_BACKEND": "keyfile", "GDK_BACKEND": "wayland",
        "GSETTINGS_SCHEMA_DIR": "/usr/share/glib-2.0/schemas",
        "XDG_SESSION_TYPE": "wayland", "NO_AT_BRIDGE": "0",
        "DBUS_SESSION_BUS_ADDRESS": f"unix:path={root}/runtime/bus",
        "AT_SPI_BUS_ADDRESS": f"unix:path={root}/runtime/bus",
        "PIPEWIRE_RUNTIME_DIR": str(root / "runtime"),
    })
    # Mutter 50 supports fractional scaling by default. Use system schemas:
    # a GUI-launched terminal can inherit incompatible bundled app schemas.
    (root / "config/glib-2.0/settings").mkdir(parents=True)
    (root / "config/glib-2.0/settings/keyfile").write_text(
        "[org/gnome/mutter]\nexperimental-features=[]\n", encoding="utf-8",
    )
    return environment


def wait_until(probe, processes, description, timeout=20):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if any(process.child.poll() is not None for process in processes):
            raise RuntimeError(f"Preview service exited while waiting for {description}; see terminal logs.")
        result = probe()
        if result:
            return result
        time.sleep(0.05)
    raise RuntimeError(f"Timed out waiting for {description}; see terminal logs.")


def apply_screen(connection, screen):
    from gi.repository import Gio, GLib

    def call(method, parameters=None):
        return connection.call_sync(
            DISPLAY_NAME, DISPLAY_PATH, DISPLAY_NAME, method, parameters, None,
            Gio.DBusCallFlags.NO_AUTO_START, 3000, None,
        ).unpack()

    serial, monitors, _logical, _properties = call("GetCurrentState")
    if len(monitors) != 1:
        raise RuntimeError("The private preview must have exactly one virtual monitor.")
    spec, modes, _properties = monitors[0]
    mode = next((mode for mode in modes if mode[1:3] == (screen.width, screen.height)
                 or list(mode[1:3]) == [screen.width, screen.height]), None)
    if mode is None:
        raise RuntimeError("Mutter did not create the requested resolution.")
    # GNOME labels scales to the nearest 25%. Non-divisible modes can expose
    # e.g. 1.249 instead of 1.25 so the logical monitor has whole dimensions.
    scale = next((value for value in mode[5]
                  if round(value * 4) * 25 == screen.percent), None)
    if scale is None:
        supported = ", ".join(f"{round(value * 4) * 25}%" for value in mode[5])
        raise ValueError(f"This resolution supports {supported}. Choose one of these scales.")
    call("ApplyMonitorsConfig", GLib.Variant(
        "(uua(iiduba(ssa{sv}))a{sv})",
        (serial, 1, [(0, 0, scale, 0, True, [(spec[0], mode[0], {})])],
         {"layout-mode": GLib.Variant("u", 1)}),
    ))
    _serial, _monitors, logical, _properties = call("GetCurrentState")
    if len(logical) != 1 or abs(logical[0][2] - scale) > 0.0001:
        raise RuntimeError("Mutter did not apply the requested display scale.")
    LOG.info("preview screen physical=%dx%d scale=%.4f logical=%dx%d",
             screen.width, screen.height, scale,
             round(screen.width / scale), round(screen.height / scale))
    return scale


class PreviewSession:
    def __init__(self, screen, host, *, child_overlay=False, viewer=True, app_command=None,
                 viewer_command=None):
        self.resources = ExitStack()
        self.processes = []
        try:
            self.root = Path(self.resources.enter_context(
                tempfile.TemporaryDirectory(prefix="onpc-screen-", dir="/tmp")))
            self.environment = private_environment(self.root, host)
            # No service directories: all services are directly spawned and
            # owned below, so host portal/systemd activation cannot leak in.
            bus_config = self.root / "bus.conf"
            bus_config.write_text(
                '<busconfig><type>session</type>'
                f'<listen>{self.environment["DBUS_SESSION_BUS_ADDRESS"]}</listen>'
                '<auth>EXTERNAL</auth><policy context="default">'
                '<allow send_destination="*"/><allow receive_sender="*"/>'
                '<allow own="*"/></policy></busconfig>', encoding="utf-8",
            )
            bus = self.start(["dbus-daemon", "--nofork", f"--config-file={bus_config}"])
            wait_until(lambda: (self.root / "runtime/bus").is_socket(), [bus], "private bus")
            from gi.repository import Gio
            self.connection = Gio.DBusConnection.new_for_address_sync(
                self.environment["DBUS_SESSION_BUS_ADDRESS"],
                Gio.DBusConnectionFlags.AUTHENTICATION_CLIENT
                | Gio.DBusConnectionFlags.MESSAGE_BUS_CONNECTION, None, None,
            )
            self.resources.callback(self.connection.close_sync, None)
            registry = next((path for path in REGISTRY_PATHS if Path(path).is_file()), None)
            if registry is None:
                raise RuntimeError("AT-SPI registry is required. Run ./setup.sh --dependencies-only.")
            self.start([registry])
            pipewire = self.start(["pipewire"])
            wait_until(lambda: (self.root / "runtime/pipewire-0").is_socket(),
                       [bus, pipewire], "private PipeWire")
            self.start(["wireplumber", "--profile=policy"])
            LOG.info("private PipeWire linking policy started (no hardware monitors)")
            self.compositor = self.start([
                "mutter", "--headless", "--devkit", "--wayland", "--no-x11",
                "--wayland-display", "preview-wayland",
                "--virtual-monitor", f"{screen.width}x{screen.height}",
            ])

            def ready():
                try:
                    self.connection.call_sync(
                        DISPLAY_NAME, DISPLAY_PATH, DISPLAY_NAME, "GetCurrentState",
                        None, None, Gio.DBusCallFlags.NO_AUTO_START, 500, None,
                    )
                    return (self.root / "runtime/preview-wayland").is_socket()
                except Exception:
                    return False

            wait_until(ready, self.processes, "virtual monitor")
            self.scale = apply_screen(self.connection, screen)
            self.control, client = socket.socketpair(socket.AF_UNIX, socket.SOCK_SEQPACKET)
            self.resources.callback(self.control.close)
            self.environment.update({
                "WAYLAND_DISPLAY": "preview-wayland", SCREEN: screen.encode(),
                ACTUAL_SCALE: str(self.scale),
                CONTROL_FD: str(client.fileno()),
            })
            self.resources.callback(client.close)
            self.viewer = None
            if viewer:
                viewer_environment = dict(self.environment)
                viewer_environment.pop(CONTROL_FD, None)
                # Only the viewer connects to the host display. Its bus,
                # PipeWire and settings still belong to this private session.
                for key in ("DISPLAY", "WAYLAND_DISPLAY", "XAUTHORITY", "XDG_RUNTIME_DIR"):
                    viewer_environment.pop(key, None)
                    if key in host:
                        viewer_environment[key] = host[key]
                viewer_environment["GDK_BACKEND"] = (
                    "x11" if host.get("GDK_BACKEND") == "x11" or not host.get("WAYLAND_DISPLAY")
                    else "wayland")
                viewer_control, viewer_client = socket.socketpair(socket.AF_UNIX, socket.SOCK_SEQPACKET)
                self.resources.callback(viewer_control.close)
                with viewer_client:
                    viewer_environment["ONPC_PREVIEW_VIEWER_FD"] = str(viewer_client.fileno())
                    self.viewer = self.start(
                        viewer_command or [sys.executable, "-m", "oh_no_parent_control_kiosk.preview_viewer"],
                        env=viewer_environment, pass_fds=(viewer_client.fileno(),),
                    )

                    def video_ready():
                        readable, _, _ = select.select([viewer_control], [], [], 0)
                        return bool(readable) and viewer_control.recv(4096) == b"video"

                    wait_until(video_ready, self.processes, "full-resolution preview video", timeout=25)
            # The viewer establishes the virtual seat before GTK maps. Bare
            # Mutter otherwise has no keyboard focus to assign to the app.
            command = app_command or [sys.executable, "-m", "oh_no_parent_control_kiosk.main",
                                      "--preview"]
            if child_overlay:
                command = [*command, "--child-overlay"]
            with client:
                self.application = self.start(command, pass_fds=(client.fileno(),))

            def application_ready():
                readable, _, _ = select.select([self.control], [], [], 0)
                return bool(readable) and self.control.recv(4096) == b"ready"

            wait_until(application_ready, self.processes, "fullscreen GTK surface")
            if viewer:
                viewer_control.send(b"app-ready")

                def app_video_ready():
                    readable, _, _ = select.select([viewer_control], [], [], 0)
                    return bool(readable) and viewer_control.recv(4096) == b"ready"

                wait_until(app_video_ready, self.processes, "rendered application video")
            # Fail before replacing a working preview when a child immediately exits.
            time.sleep(0.3)
            if not self.running():
                raise RuntimeError("The new preview failed to open; see terminal logs.")
        except BaseException:
            self.close()
            raise

    def start(self, command, **kwargs):
        process = OwnedProcess(command, env=kwargs.pop("env", self.environment), **kwargs)
        self.processes.append(process)
        self.resources.callback(process.close)
        return process

    def running(self):
        return all(process.child.poll() is None for process in self.processes)

    def close(self):
        self.resources.close()


def main(argv=None, *, session_factory=PreviewSession):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--screen", default=Screen().encode())
    parser.add_argument("--child-overlay", action="store_true")
    args = parser.parse_args(argv)
    screen = Screen.decode(args.screen)
    for program in ("mutter", "dbus-daemon", "pipewire", "wireplumber", "pw-dump"):
        if not shutil.which(program):
            parser.error(f"{program} is required. Run ./setup.sh --dependencies-only.")
    version = subprocess.run(["mutter", "--version"], capture_output=True, text=True,
                             check=True, timeout=5).stdout.strip()
    if not version.startswith("mutter 50."):
        parser.error("Screen previews require the validated Mutter 50.x development interface.")
    logging.basicConfig(level=logging.INFO)
    host = dict(os.environ)
    session = None

    def interrupted(_signum, _frame):
        raise KeyboardInterrupt

    previous = {sig: signal.signal(sig, interrupted) for sig in (signal.SIGTERM, signal.SIGHUP)}
    try:
        session = session_factory(screen, host, child_overlay=args.child_overlay)
        while session.running():
            readable, _, _ = select.select([session.control], [], [], 0.2)
            if not readable:
                continue
            message = session.control.recv(4096)
            if not message:
                break
            if message == b"ready":
                continue  # The same surface returned after a live source reload.
            try:
                screen = Screen.decode(message)
                replacement = session_factory(screen, host, child_overlay=args.child_overlay)
            except Exception as error:
                # Includes GIO display/renderer errors. The prior session is
                # still owned and usable when preparation of a new one fails.
                LOG.warning("preview screen change rejected: %s", error)
                session.control.send(str(error).encode()[:4096])
                continue
            old = session
            session = replacement
            try:
                old.control.send(b"ok")
            finally:
                old.close()
    except KeyboardInterrupt:
        pass
    finally:
        if session is not None:
            session.close()
        for sig, handler in previous.items():
            signal.signal(sig, handler)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
