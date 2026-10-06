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
UI_TIMINGS = None


def _watch_phase(item, phase):
    global UI_WATCH_TEST
    UI_WATCH_TEST = (item.nodeid, phase)
    if UI_OBSERVER is not None:
        UI_OBSERVER.update(*UI_WATCH_TEST)


@contextmanager
def _timed_phase(item, phase):
    global UI_TIMINGS
    if UI_TIMINGS is None and os.environ.get('ONPC_REGRESSION_EVENTS') == '1':
        from tests.support.ui_timing import Timings
        UI_TIMINGS = Timings.retained()
    _watch_phase(item, phase)
    if UI_TIMINGS is not None:
        UI_TIMINGS.begin(item.nodeid, phase)
    try:
        yield
    finally:
        if UI_TIMINGS is not None:
            UI_TIMINGS.publish('end')


def pytest_sessionfinish(session, exitstatus):
    if UI_TIMINGS is not None:
        UI_TIMINGS.close()


@pytest.hookimpl(tryfirst=True)
def pytest_runtest_makereport(item, call):
    """Pair API ownership refusals with launch evidence before fixture cleanup."""
    from tests.support.application_ui import UIClientError

    if call.excinfo is None:
        return
    error = call.excinfo.value
    if not isinstance(error, UIClientError) or error.code != 'Denied':
        return
    launch = item.funcargs.get('launch_ui')
    diagnostic = getattr(launch, 'ownership_diagnostic', None)
    if diagnostic is None:
        return
    ui = item.funcargs.get('automation')
    catalog = ui.reader.application_ui if ui is not None else None
    for note in diagnostic(catalog):
        error.add_note(note)


@pytest.hookimpl(hookwrapper=True)
def pytest_runtest_setup(item):
    with _timed_phase(item, 'setup'):
        yield


@pytest.hookimpl(hookwrapper=True)
def pytest_runtest_call(item):
    with _timed_phase(item, 'call'):
        yield


@pytest.hookimpl(hookwrapper=True)
def pytest_runtest_teardown(item):
    with _timed_phase(item, 'teardown'):
        yield


@pytest.fixture(scope='session', autouse=True)
def ui_operation_timings():
    if UI_TIMINGS is None:
        yield
        return
    from tests.e2e.public_atspi import PublicAtspi
    from tests.e2e.accessible_ui import AccessibleUI
    from tests.support.application_ui import ApplicationUI, ApplicationNode, UIClient
    from tests.support import keyboard
    from tests.support import gui_blocks
    with pytest.MonkeyPatch.context() as patch:
        original_init = AccessibleUI.__init__

        def traced_init(reader, *args, **kwargs):
            original_init(reader, *args, **kwargs)
            reader.wait_trace = UI_TIMINGS.wait_trace

        patch.setattr(AccessibleUI, '__init__', traced_init)
        patch.setattr(AccessibleUI, 'run', UI_TIMINGS.wrap_reader_run(AccessibleUI.run))
        patch.setattr(AccessibleUI, '_read_nodes', UI_TIMINGS.wrap_iterator(
            AccessibleUI._read_nodes, 'reader.traversal'))
        for method in ('catalogue_filter', 'app_rows', 'allowance_preset', 'parent_page'):
            patch.setattr(AccessibleUI, method, UI_TIMINGS.wrap_span(
                getattr(AccessibleUI, method), 'reader.' + method))
        patch.setattr(gui_blocks, 'run_block', UI_TIMINGS.wrap_span(gui_blocks.run_block, 'gui.block'))
        patch.setattr(gui_blocks, 'run_perl', UI_TIMINGS.wrap_span(gui_blocks.run_perl, 'gui.expand'))
        patch.setattr(PublicAtspi, 'call', UI_TIMINGS.wrap_rpc(PublicAtspi.call))
        patch.setattr(PublicAtspi, 'read_many', UI_TIMINGS.wrap_batch(PublicAtspi.read_many))
        for owner, method, label in (
                # Aggregate only fixed operation names and durations. Product
                # RPCs otherwise appear as unaccounted traversal self time;
                # never record their arguments, UI values or response text.
                (UIClient, '_bus', 'application-ui.bus'),
                (UIClient, '_request', 'application-ui.request'),
                (ApplicationUI, '_application', 'application-ui.inventory-projection'),
                (ApplicationNode, 'snapshot', 'application-ui.element-snapshot'),
                (AccessibleUI, 'read_snapshot', 'reader.snapshot'),
                (AccessibleUI, 'wait', 'reader.wait'),
                (AccessibleUI, '_invoke_target', 'input.action'),
                (keyboard, '_deliver_target', 'input.keyboard')):
            patch.setattr(owner, method, UI_TIMINGS.wrap(getattr(owner, method), label))
        yield

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
    boot = boot_preview_session
    if UI_TIMINGS is not None:
        boot = UI_TIMINGS.wrap(boot, 'session.boot')
    boot(session)
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
            teardown = session.teardown
            if UI_TIMINGS is not None:
                teardown = UI_TIMINGS.wrap(teardown, 'session.teardown')
            teardown()
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


@pytest.fixture(autouse=True)
def application_ui_connections(monkeypatch):
    """Close every catalog created by the case, including independent readers.

    Readers share this worker's existing private session bus. Each catalog owns
    only its client connection; it starts no process or additional bus server.
    """
    from tests.support.application_ui import ApplicationUI

    catalogs = []
    initialize = ApplicationUI.__init__

    def tracked_initialize(catalog, *arguments, **keywords):
        initialize(catalog, *arguments, **keywords)
        catalogs.append(catalog)

    monkeypatch.setattr(ApplicationUI, '__init__', tracked_initialize)
    try:
        yield
    finally:
        failures = []
        for catalog in reversed(catalogs):
            try:
                catalog.close()
            except Exception as error:
                failures.append(error)
        if failures:
            raise ExceptionGroup('Application UI connection cleanup failed', failures)


@pytest.fixture
def launch_ui(hermetic_ui_session, wait_for_accessible_state):
    """Expose the shared owned-process launcher on this private compositor."""
    # Later aggregate categories rotate pytest's temporary roots. Keep these
    # diagnostic logs on disk so a failure remains inspectable after teardown.
    from tools.test_retention import allocate
    directory = Path(allocate(tempfile.mkdtemp, prefix="onpc-ui-preview-", dir="/var/tmp"))
    print(f"UI preview logs: {directory}", flush=True)
    manager = preview_applications(hermetic_ui_session, directory)
    if UI_TIMINGS is not None:
        manager = UI_TIMINGS.lifecycle(manager, 'preview')
    with manager as launch:
        launches = []
        history = getattr(hermetic_ui_session, '_onpc_launch_diagnostics', None)
        if history is None:
            history = []
            hermetic_ui_session._onpc_launch_diagnostics = history

        def ownership_diagnostic(catalog):
            # Read only our recorded handles. Never discover/adopt/signal other
            # processes, or disclose bus addresses, UI text or the environment.
            yield f'UI preview ownership: recorded_launch_count={len(launches)}'
            for process, log_path, bus_address in history:
                reader_bus_matches = (None if catalog is None else
                                      catalog._connection_address == bus_address)
                yield ('UI preview launch: '
                       f'launched_pid={process.pid}, returncode={process.poll()}, '
                       f'current_case={any(record[0] is process for record in launches)}, '
                       f'observer_bus_matches_launch={os.environ.get("DBUS_SESSION_BUS_ADDRESS") == bus_address}, '
                       f'catalog_bus_matches_launch={reader_bus_matches}, '
                       f'launch_bus_matches_session={bus_address == hermetic_ui_session.bus_address}, '
                       f'preview_log={log_path}')

        def launch_ready(name, **kwargs):
            complete_language_setup = kwargs.pop('complete_language_setup', True)
            start = launch
            if UI_TIMINGS is not None:
                start = UI_TIMINGS.wrap(start, 'preview.launch')
            result = start(name, **kwargs)
            process, log_path = result
            overrides = kwargs.get('environment_overrides') or {}
            bus_address = overrides.get('DBUS_SESSION_BUS_ADDRESS',
                hermetic_ui_session.environment.get('DBUS_SESSION_BUS_ADDRESS'))
            launches.append((process, log_path, bus_address))
            history.append(launches[-1])
            del history[:-16]
            if complete_language_setup and name in ("parent_preview", "parent_component_preview", "kiosk_preview",
                        "child_overlay_preview", "request_component_preview"):
                import gi
                gi.require_version("Atspi", "2.0")
                from gi.repository import Atspi, GLib
                from tests.e2e.public_atspi import PublicAtspi
                from tests.support.automation import Automation
                from tests.support.application_ui import UIClientError
                api = PublicAtspi(Atspi)
                ui = None
                try:
                    ui = Automation(api, lambda: api.get_desktop(0), query_errors=(GLib.Error,),
                                    owner_pids=launch.owner_pids,
                                    application_ids=launch.application_ids,
                                    application_owners=launch.application_owners,
                                    application_owner_history=launch.application_owner_history,
                                    application_ui_endpoints=launch.application_ui_endpoints,
                                    complete_read_wait=wait_for_accessible_state)
                    ui.reader.timeout = UI_TIMEOUT_SECONDS
                    ui.reader.dispatch = lambda: GLib.MainContext.default().iteration(False)
                    if name in ("parent_preview", "parent_component_preview"):
                        ui.complete_parent_language_setup()
                    else:
                        ui.complete_request_language_setup()
                except UIClientError as error:
                    # Pair endpoint refusal evidence with this launch's exact
                    # owned handle and retained log, before fixture cleanup.
                    process, log_path = result
                    error.add_note('UI preview language setup: '
                                   f'launched_pid={process.pid}, returncode={process.poll()}, '
                                   f'preview_log={log_path}')
                    raise
                finally:
                    try:
                        if ui is not None:
                            ui.reader.application_ui.close()
                    finally:
                        api.reset()
            return result

        for name in ("owner_pids", "application_ids", "application_owners", "application_owner_history",
                     "application_ui_endpoints"):
            setattr(launch_ready, name, getattr(launch, name))
        launch_ready.ownership_diagnostic = ownership_diagnostic
        yield launch_ready


@pytest.fixture
def wait_for_accessible_state():
    """Wait for a complete public UI result with a Python-owned deadline."""

    from gi.repository import GLib
    from tests.e2e.accessible_ui import UiError
    from tests.support.automation import AutomationError

    def wait_attempts(predicate, description, checkpoint):
        deadline = time.monotonic() + UI_TIMEOUT_SECONDS
        attempt = 0
        while time.monotonic() < deadline:
            attempt += 1
            try:
                if checkpoint is not None:
                    checkpoint('predicate', attempt)
                ready = predicate()
                outcome = 'pending'
            except (UiError, AutomationError) as error:
                if str(error) not in ("ui:incomplete-tree", "automation:incomplete-tree"):
                    raise
                # Retry the whole read, never accept a partial tree as presence
                # or absence. Input and ownership failures still propagate.
                ready = False
                outcome = 'incomplete'
            if ready:
                if checkpoint is not None:
                    checkpoint('ready', attempt)
                return
            if checkpoint is not None:
                checkpoint(outcome, attempt)
            # A nested MainLoop installs GI's SIGINT fallback and can swallow
            # cancellation in a dispatched callback. Keep the wait/deadline in
            # Python and dispatch only bounded, nonblocking event work.
            if checkpoint is not None:
                checkpoint('dispatch', attempt)
            for _ in range(32):
                if not GLib.MainContext.default().iteration(False):
                    break
            if checkpoint is not None:
                checkpoint('sleep', attempt)
            time.sleep(.05)
        if checkpoint is not None:
            checkpoint('timeout', attempt)
        raise AssertionError(f"Timed out waiting for public UI state: {description}")

    def wait(predicate, description: str):
        if UI_TIMINGS is None:
            return wait_attempts(predicate, description, None)
        with UI_TIMINGS.span('host.wait', predicate=UI_TIMINGS.source(predicate)) as checkpoint:
            return wait_attempts(predicate, description, checkpoint)

    return wait


@pytest.fixture
def automation(hermetic_ui_session, launch_ui, wait_for_accessible_state):
    """Share Application UI product operations and external-provider adapters."""
    import gi
    gi.require_version("Atspi", "2.0")
    from gi.repository import Atspi, GLib
    from tests.support.automation import Automation
    from tests.e2e.public_atspi import PublicAtspi

    api = PublicAtspi(Atspi)
    ui = None
    try:
        ui = Automation(api, lambda: api.get_desktop(0), query_errors=(GLib.Error,),
                        owner_pids=launch_ui.owner_pids,
                        application_ids=launch_ui.application_ids,
                        application_owners=launch_ui.application_owners,
                        application_owner_history=launch_ui.application_owner_history,
                        application_ui_endpoints=launch_ui.application_ui_endpoints,
                        complete_read_wait=wait_for_accessible_state)
        ui.reader.timeout = UI_TIMEOUT_SECONDS
        ui.reader.dispatch = lambda: GLib.MainContext.default().iteration(False)
        yield ui
    finally:
        try:
            if ui is not None:
                ui.reader.application_ui.close()
        finally:
            api.reset()


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
