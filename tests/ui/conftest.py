"""Hermetic GTK fixtures for semantic Wayland component tests."""

from __future__ import annotations

import os
import subprocess
import sys
import time
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
UI_TIMEOUT_SECONDS = 20
HOST_DESKTOP_ENVIRONMENT_OVERRIDES = (
    "GDK_BACKEND",
    "GSETTINGS_SCHEMA_DIR",
    "GTK_EXE_PREFIX",
    "GTK_IM_MODULE",
    "GTK_IM_MODULE_FILE",
    "GTK_MODULES",
    "GTK_PATH",
)
TEST_ENVIRONMENT_OVERRIDES = (
    *HOST_DESKTOP_ENVIRONMENT_OVERRIDES,
    "LANG",
    "LC_ALL",
    "GDK_SCALE",
    "GDK_DPI_SCALE",
    "NO_AT_BRIDGE",
    "GTK_THEME",
    "GSK_RENDERER",
    "XDG_SESSION_TYPE",
)
ACCESSIBILITY_EVENTS = (
    "object:children-changed",
    "object:state-changed:showing",
    "window:create",
)
ORIGINAL_ENVIRONMENT = os.environ.copy()

# Dogtail imports GTK while loading its hermetic-session module.  Isolate the
# launcher environment before that import so GTK cannot bind AT-SPI to the
# developer's existing desktop before Dogtail creates the private a11y bus.
for name in HOST_DESKTOP_ENVIRONMENT_OVERRIDES:
    os.environ.pop(name, None)
os.environ.update({
    "LANG": "C.UTF-8",
    "LC_ALL": "C.UTF-8",
    "GDK_SCALE": "1",
    "GDK_DPI_SCALE": "1",
    "GSETTINGS_SCHEMA_DIR": "/usr/share/glib-2.0/schemas",
    # Dogtail imports GTK before HermeticSession.boot().  Prevent that import
    # from attaching libatspi to the host desktop; boot() changes this to 0
    # before it launches the application on the private bus.
    "NO_AT_BRIDGE": "1",
    "GTK_THEME": "Adwaita:dark",
    "GSK_RENDERER": "cairo",
})

from dogtail.hermetic.session import HermeticSession, dump_tree


@pytest.fixture(scope="session")
def hermetic_ui_session():
    """Boot one deterministic private Wayland session for this pytest process."""

    # RequestWindow's deterministic preview is 1918×1443.  Keep the private
    # monitor larger than that canvas so AT-SPI reports the lower duration and
    # custom controls as showing after the gateway transform.
    session = HermeticSession(virtual_monitor="2048x1536")
    session.boot()
    # HermeticSession has already copied the Wayland environment used by the
    # preview process.  Dogtail's tree module imports its optional Ponytail
    # input bridge based on this test runner's environment.  The tests use
    # semantic AT-SPI actions only, while bare Mutter does not expose GNOME
    # Shell's Ponytail service, so keep that optional bridge disabled here.
    os.environ["XDG_SESSION_TYPE"] = "x11"
    settings_directory = Path(session.environment["XDG_CONFIG_HOME"]) / "gtk-4.0"
    settings_directory.mkdir(parents=True, exist_ok=True)
    (settings_directory / "settings.ini").write_text(
        "[Settings]\n"
        "gtk-enable-animations=false\n"
        "gtk-theme-name=Adwaita\n"
        "gtk-icon-theme-name=Adwaita\n"
        "gtk-font-name=Cantarell 11\n",
        encoding="utf-8",
    )
    (settings_directory / "gtk.css").write_text(
        "window, .popover, .tooltip { box-shadow: none; }\n",
        encoding="utf-8",
    )
    try:
        yield session
    finally:
        session.teardown()
        # Pytest and other libraries can add their own environment variables
        # while this session runs.  Restore only the variables this fixture
        # owns rather than clearing those external variables during teardown.
        for name in TEST_ENVIRONMENT_OVERRIDES:
            if name in ORIGINAL_ENVIRONMENT:
                os.environ[name] = ORIGINAL_ENVIRONMENT[name]
            else:
                os.environ.pop(name, None)


@pytest.fixture
def launch_ui(hermetic_ui_session, tmp_path):
    """Launch a preview app, expose its AT-SPI tree, and stop it after a test."""

    processes = []

    def launch(name: str, *, environment_overrides=None, wait_for_application=True):
        log_path = tmp_path / f"{name}.log"
        environment = {
            **hermetic_ui_session.environment,
            "PYTHONPATH": str(ROOT),
            "PYTHONDONTWRITEBYTECODE": "1",
            **(environment_overrides or {}),
        }
        log_file = log_path.open("wb")
        process = subprocess.Popen(
            [sys.executable, str(ROOT / "tests" / "ui" / f"{name}.py")],
            env=environment,
            stdout=log_file,
            stderr=subprocess.STDOUT,
        )
        processes.append((process, log_file))
        if not wait_for_application:
            return process, log_path
        application = hermetic_ui_session.wait_for_app(name)
        return application, log_path

    try:
        yield launch
    finally:
        for process, log_file in reversed(processes):
            if process.poll() is None:
                process.terminate()
                try:
                    process.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    process.kill()
                    process.wait(timeout=5)
            log_file.close()


@pytest.fixture
def wait_for_accessible_node():
    """Wait for a semantic accessibility node using AT-SPI events and a deadline."""

    # Importing Atspi initializes libatspi's process-global desktop connection.
    # This fixture runs only after HermeticSession.boot() has exported the
    # private bus, so the connection cannot be cached against the host desktop.
    import gi

    gi.require_version("Atspi", "2.0")
    from gi.repository import Atspi, GLib

    def wait(
        application, label: str, role_name: str | None = None, *, labelled: bool = False,
    ):
        loop = GLib.MainLoop()

        def wake_for_accessibility_event(*_args):
            loop.quit()

        listener = Atspi.EventListener.new(wake_for_accessibility_event)
        registered_events = [
            event_type for event_type in ACCESSIBILITY_EVENTS
            if listener.register(event_type)
        ]
        deadline = time.monotonic() + UI_TIMEOUT_SECONDS
        try:
            while time.monotonic() < deadline:
                try:
                    if labelled:
                        return application.child(
                            role_name=role_name, label=label, retry=False,
                        )
                    return application.child(
                        label, role_name=role_name, retry=False,
                    )
                except Exception:  # Dogtail reports a search miss with its own type.
                    remaining_milliseconds = max(
                        1, round((deadline - time.monotonic()) * 1000),
                    )
                    timeout_id = GLib.timeout_add(remaining_milliseconds, loop.quit)
                    loop.run()
                    try:
                        GLib.source_remove(timeout_id)
                    except SystemError:
                        # The timeout itself ended the loop and is already gone.
                        pass
        finally:
            for event_type in registered_events:
                listener.deregister(event_type)
        raise AssertionError(
            f"Timed out waiting for {label!r} ({role_name or 'any role'}).\n"
            f"Accessibility tree:\n{dump_tree(application, max_depth=20)}",
        )

    return wait


@pytest.fixture
def wait_for_accessible_state():
    """Wait for an AT-SPI state transition without host-time sleeps."""

    from gi.repository import GLib

    def wait(predicate, description: str):
        deadline = time.monotonic() + UI_TIMEOUT_SECONDS
        while time.monotonic() < deadline:
            if predicate():
                return
            loop = GLib.MainLoop()
            timeout_id = GLib.timeout_add(50, loop.quit)
            loop.run()
            try:
                GLib.source_remove(timeout_id)
            except SystemError:
                pass
        raise AssertionError(f"Timed out waiting for accessibility state: {description}")

    return wait


@pytest.fixture
def capture_ui_snapshot(tmp_path):
    """Save the semantic UI snapshot used for hermetic-test diagnostics.

    Bare Mutter intentionally has no pixel screenshot API.  Dogtail's supported
    hermetic evidence is an AT-SPI tree dump, which preserves labels, roles, and
    state without borrowing the developer's graphical session.
    """

    def capture(application, name: str) -> Path:
        path = tmp_path / f"{name}.a11y-tree.txt"
        path.write_text(dump_tree(application, max_depth=20), encoding="utf-8")
        return path

    return capture


@pytest.fixture
def collect_application_logs():
    """Return redacted preview-process log text for a failing assertion."""

    def collect(log_path: Path) -> str:
        if not log_path.exists():
            return "(application did not create a log)"
        return log_path.read_text(encoding="utf-8", errors="replace")

    return collect
