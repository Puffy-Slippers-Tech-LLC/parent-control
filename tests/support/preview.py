"""Owned preview-process lifecycle, independent of GTK and Dogtail imports."""

from contextlib import contextmanager
import json
import subprocess
import sys
import tempfile

from tests.support.paths import ROOT


def boot_preview_session(session):
    """Keep graphical runtime sockets outside WebKit's /var/tmp symlink.

    Dogtail uses tempfile's public default for its private runtime root and
    exposes no directory argument. Scope the default to this synchronous boot;
    pytest workers run in separate processes, with no concurrent tests inside
    a worker. Capture and subsequent test fixtures keep their disk-backed default.
    """
    previous = tempfile.tempdir
    try:
        tempfile.tempdir = '/tmp'
        session.boot()
    finally:
        tempfile.tempdir = previous


@contextmanager
def preview_applications(session, directory):
    """Launch preview apps on an already isolated session and reap owned children.

    The caller owns the compositor. This scope owns only the Popen handles and
    log files it creates, including launches that fail accessibility discovery.
    """
    processes = []
    application_ids = {}
    explicit_endpoints = {}

    def launch(name, *, environment_overrides=None, wait_for_application=False):
        # Readiness belongs to the caller's public-ID adapter. A script name is
        # launch metadata, never an accessibility application selector.
        if wait_for_application:
            raise ValueError("preview readiness requires a public automation ID")
        log_path = directory / f"{name}.log"
        environment = {
            **session.environment,
            "PYTHONPATH": str(ROOT),
            "PYTHONDONTWRITEBYTECODE": "1",
            **(environment_overrides or {}),
        }
        log_file = log_path.open("wb")
        try:
            process = subprocess.Popen(
                # Enable before importing GTK/WebKit so startup, runtime and
                # teardown faults reach the same retained stderr log. Python
                # 3.14 also includes the native stack when its build supports it.
                [sys.executable, "-X", "faulthandler",
                 str(ROOT / "tests/ui" / f"{name}.py")],
                env=environment, stdout=log_file, stderr=subprocess.STDOUT,
            )
        except BaseException:
            log_file.close()
            raise
        processes.append((process, log_file))
        # These are declared launcher contracts, not process/UI discovery.
        if name in ("parent_preview", "parent_component_preview"):
            identity = "com.puffyslippers.OhNoParentControl.Parent"
        elif name in ("child_overlay_preview", "child_error_preview") or (
                name == "request_component_preview"
                and environment.get("ONPC_REQUEST_COMPONENT_OVERLAY") == "1"):
            identity = "com.puffyslippers.OhNoParentControl.ChildRequest"
        elif name in ("kiosk_preview", "request_component_preview"):
            identity = "com.puffyslippers.OhNoParentControl"
        elif name in ("e2e_watch_window_probe", "ui_watch_window_probe", "watch_window_probe"):
            identity = "org.onpc.E2EWatch"
        else:
            identity = None  # Other launchers need their own explicit contract.
        application_ids[process] = identity
        if name == 'child_error_preview':
            explicit_endpoints[process] = log_path
        return process, log_path

    # Readiness adapters can verify public surface ownership using only the
    # handles this scope spawned. Never discover/adopt a process by its name.
    launch.owner_pids = lambda: frozenset(
        process.pid for process, _log in processes if process.poll() is None)
    launch.application_ids = lambda: frozenset(
        application_ids[process] for process, _log in processes
        if process.poll() is None and application_ids[process] is not None)
    launch.application_owners = lambda: {
        identity: frozenset(process.pid for process, _log in processes
                            if application_ids[process] == identity and process.poll() is None)
        for identity in launch.application_ids()
    }
    # Negative accessibility observations can briefly outlive their exact
    # process after it exits. Retain only the PIDs this scope itself spawned so
    # the reader can retry those stale nodes without trusting them for input.
    launch.application_owner_history = lambda: {
        identity: frozenset(process.pid for process, _log in processes
                            if application_ids[process] == identity)
        for identity in frozenset(application_ids.values()) if identity is not None
    }

    def application_ui_endpoints():
        receipts = []
        for process, log_path in explicit_endpoints.items():
            if process.poll() is not None:
                continue
            log = log_path.read_text(encoding='utf-8', errors='replace')
            lines = log.splitlines() if log.endswith('\n') else log.splitlines()[:-1]
            values = [json.loads(line.removeprefix('ONPC_APPLICATION_UI_ENDPOINT '))
                      for line in lines if line.startswith('ONPC_APPLICATION_UI_ENDPOINT ')]
            if not values:
                # The recorded process is starting. Its missing export cannot
                # establish public absence or release another action.
                from tests.support.automation import AutomationError
                raise AutomationError('automation:incomplete-tree')
            if len(values) != 1 or values[0].get('pid') != process.pid \
                    or values[0].get('application_id') != application_ids[process]:
                raise ValueError('Invalid launch-owned Application UI endpoint')
            receipts.append(values[0])
        return receipts

    launch.application_ui_endpoints = application_ui_endpoints

    try:
        yield launch
    finally:
        failures = []
        for process, log_file in reversed(processes):
            try:
                if process.poll() is None:
                    process.terminate()
                    try:
                        process.wait(timeout=5)
                    except subprocess.TimeoutExpired:
                        process.kill()
                        process.wait(timeout=5)
            except BaseException as error:
                failures.append(error)
            finally:
                log_file.close()
        if failures:
            raise BaseExceptionGroup("Preview process cleanup failed", failures)
