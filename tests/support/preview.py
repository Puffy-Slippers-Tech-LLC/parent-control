"""Owned preview-process lifecycle, independent of GTK and Dogtail imports."""

from contextlib import contextmanager
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
                [sys.executable, str(ROOT / "tests/ui" / f"{name}.py")],
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
        elif name == "e2e_watch_window_probe":
            identity = "org.onpc.E2EWatch"
        else:
            identity = None  # Other launchers need their own explicit contract.
        application_ids[process] = identity
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
