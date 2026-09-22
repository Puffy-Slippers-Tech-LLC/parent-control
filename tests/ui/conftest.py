"""Hermetic GTK fixtures for semantic Wayland component tests."""

from __future__ import annotations

import os
import tempfile
import time
from contextlib import contextmanager
from pathlib import Path

import pytest
from tests.support.preview import boot_preview_session, preview_applications

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
    "MUTTER_DEBUG_DISABLE_ANIMATIONS",
)
ORIGINAL_ENVIRONMENT = os.environ.copy()
UI_OBSERVER = None
UI_WATCH_TEST = ('', 'setup')


def _watch_phase(item, phase):
    global UI_WATCH_TEST
    UI_WATCH_TEST = (item.nodeid, phase)
    if UI_OBSERVER is not None:
        UI_OBSERVER.update(*UI_WATCH_TEST)


def pytest_runtest_setup(item):
    _watch_phase(item, 'setup')


def pytest_runtest_call(item):
    _watch_phase(item, 'call')


def pytest_runtest_teardown(item):
    _watch_phase(item, 'teardown')

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
    # Keep GTK's default GPU renderer. Cairo cannot render the request form's
    # perspective node and substitutes a solid magenta rectangle.
    # Keep mapping deterministic for state/readiness observations. Application
    # animations (including spinner coverage) remain separate.
    "MUTTER_DEBUG_DISABLE_ANIMATIONS": "1",
})

from dogtail.hermetic.session import HermeticSession, dump_tree


@pytest.fixture(scope="session")
def ui_monitor_size():
    # The session is shared across modules. Both dimensions divide by 1.25,
    # enabling real fractional scaling, while the height keeps overflow/reveal
    # behavior covered through semantic ID-addressed scrolling.
    return "1280x800"


@pytest.fixture(scope="session")
def hermetic_ui_session(ui_monitor_size, request):
    """Boot one deterministic private Wayland session for this pytest process."""

    session = HermeticSession(virtual_monitor=ui_monitor_size)
    boot_preview_session(session)
    # Install Dogtail's bare-Mutter input backend before dogtail.tree imports
    # rawinput.  Importing the backend otherwise eagerly probes the optional
    # GNOME Shell Ponytail service, which a bare-Mutter session intentionally
    # lacks.  Limit the compatibility override to that import, then restore
    # Wayland so rawinput selects the installed RemoteDesktop backend.
    os.environ["XDG_SESSION_TYPE"] = "x11"
    try:
        input_backend = session.install_input()
    finally:
        os.environ["XDG_SESSION_TYPE"] = session.environment["XDG_SESSION_TYPE"]
    # Create Mutter's virtual input devices before the application maps.  In a
    # shell-less compositor there is no later desktop activation step to bind
    # a newly created virtual keyboard to an already mapped window.
    input_backend.connectMonitor()
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
    global UI_OBSERVER
    from tests.support.ui_watch import start
    from tools.regression_ui import buckets
    selected = buckets([item.nodeid for item in request.session.items])
    branch = selected[0].name.removeprefix('UI — ') if len(selected) == 1 else 'UI tests'
    UI_OBSERVER = start(session, branch=branch)
    if UI_OBSERVER is not None:
        UI_OBSERVER.update(*UI_WATCH_TEST)
    try:
        yield session
    finally:
        try:
            if UI_OBSERVER is not None:
                UI_OBSERVER.close()
        finally:
            UI_OBSERVER = None
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
def temporary_display_scale(hermetic_ui_session):
    """Allow a test to observe both applying and restoring the real scale."""
    return lambda scale: _display_scale(hermetic_ui_session, scale)


@pytest.fixture
def request_display_scale(temporary_display_scale, dpi_scale):
    with temporary_display_scale(dpi_scale):
        yield


@contextmanager
def _display_scale(hermetic_ui_session, dpi_scale):
    """Set actual Wayland scaling on the fixture's private compositor only.

    GDK_SCALE is an X11 override and cannot exercise Wayland HiDPI. Use
    Mutter's documented DisplayConfig interface with a temporary configuration:
    https://gitlab.gnome.org/GNOME/mutter/-/blob/main/data/dbus-interfaces/org.gnome.Mutter.DisplayConfig.xml
    """
    from gi.repository import Gio, GLib

    connection = Gio.DBusConnection.new_for_address_sync(
        hermetic_ui_session.bus_address,
        Gio.DBusConnectionFlags.AUTHENTICATION_CLIENT
        | Gio.DBusConnectionFlags.MESSAGE_BUS_CONNECTION,
        None, None,
    )

    def call(method, parameters=None):
        return connection.call_sync(
            "org.gnome.Mutter.DisplayConfig", "/org/gnome/Mutter/DisplayConfig",
            "org.gnome.Mutter.DisplayConfig", method, parameters, None,
            Gio.DBusCallFlags.NONE, 3000, None,
        ).unpack()

    try:
        _serial, monitors, logical_monitors, _properties = call("GetCurrentState")
        assert len(monitors) == len(logical_monitors) == 1
        specification, modes, _properties = monitors[0]
        mode = next(mode for mode in modes if mode[-1].get("is-current"))
        # Use the compositor's exact supported value (fractional scales may
        # be represented as floats with slightly different precision).
        matching_scales = [scale for scale in mode[5] if scale == pytest.approx(dpi_scale)]
        assert matching_scales, (
            f"Private test output {mode[1]}x{mode[2]} does not support "
            f"required scale {dpi_scale}; supported scales: {mode[5]}"
        )
        supported_scale = matching_scales[0]
        x, y, original_scale, transform, primary, _monitors, _properties = logical_monitors[0]

        def apply(scale):
            serial, *_state = call("GetCurrentState")
            call("ApplyMonitorsConfig", GLib.Variant(
                "(uua(iiduba(ssa{sv}))a{sv})",
                (serial, 1, [(x, y, scale, transform, primary,
                              [(specification[0], mode[0], {})])], {}),
            ))

        try:
            apply(supported_scale)
            yield
        finally:
            apply(original_scale)
    finally:
        connection.close_sync(None)


@pytest.fixture
def launch_ui(hermetic_ui_session):
    """Expose the shared owned-process launcher on this private compositor."""
    # Later aggregate categories rotate pytest's temporary roots. Keep these
    # diagnostic logs on disk so a failure remains inspectable after teardown.
    from tools.test_retention import allocate
    directory = Path(allocate(tempfile.mkdtemp, prefix="onpc-ui-preview-", dir="/var/tmp"))
    print(f"UI preview logs: {directory}", flush=True)
    with preview_applications(hermetic_ui_session, directory) as launch:
        yield launch


@pytest.fixture
def wait_for_accessible_state():
    """Wait for an AT-SPI state transition without host-time sleeps."""

    from gi.repository import GLib
    from tests.e2e.accessible_ui import UiError
    from tests.support.automation import AutomationError

    def wait(predicate, description: str):
        deadline = time.monotonic() + UI_TIMEOUT_SECONDS
        while time.monotonic() < deadline:
            try:
                ready = predicate()
            except (UiError, AutomationError) as error:
                if str(error) not in ("ui:incomplete-tree", "automation:incomplete-tree"):
                    raise
                # Retry the whole read, never accept a partial tree as presence
                # or absence. Input and ownership failures still propagate.
                ready = False
            if ready:
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
def automation(hermetic_ui_session, launch_ui, wait_for_accessible_state):
    """Return the shared public-ID AT-SPI adapter for the private session."""
    import gi
    gi.require_version("Atspi", "2.0")
    from gi.repository import Atspi, GLib
    from tests.support.automation import Automation

    return Automation(Atspi, lambda: Atspi.get_desktop(0), query_errors=(GLib.Error,),
                      owner_pids=launch_ui.owner_pids,
                      application_ids=launch_ui.application_ids,
                      application_owners=launch_ui.application_owners,
                      application_owner_history=launch_ui.application_owner_history,
                      complete_read_wait=wait_for_accessible_state)


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
