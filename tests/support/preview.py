"""Owned preview-process lifecycle, independent of GTK and Dogtail imports."""

from contextlib import contextmanager
import subprocess
import sys

from tests.support.paths import ROOT


@contextmanager
def preview_applications(session, directory):
    """Launch preview apps on an already isolated session and reap owned children.

    The caller owns the compositor. This scope owns only the Popen handles and
    log files it creates, including launches that fail accessibility discovery.
    """
    processes = []

    def launch(name, *, environment_overrides=None, wait_for_application=True):
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
        if not wait_for_application:
            return process, log_path
        return session.wait_for_app(name), log_path

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
