"""Shared bounded runner for isolated GNOME Shell UI scenarios."""

import os
import signal
import subprocess

from tests.support.paths import ROOT


def run_child_shell(environment, timeout=90):
    process = subprocess.Popen(
        ["bash", str(ROOT / "tests/ui/run-child-shell-lifecycle")],
        cwd=ROOT,
        env=environment,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        start_new_session=True,
    )
    try:
        stdout, stderr = process.communicate(timeout=timeout)
    except subprocess.TimeoutExpired:
        # Signal only the runner this test explicitly spawned. Its trapped
        # teardown owns and identity-checks every nested service it stops.
        os.killpg(process.pid, signal.SIGTERM)
        try:
            stdout, stderr = process.communicate(timeout=30)
        except subprocess.TimeoutExpired:
            os.killpg(process.pid, signal.SIGKILL)
            stdout, stderr = process.communicate(timeout=10)
        # Return a failing result so the caller can retain the reviewable
        # attempt artifacts before presenting this bounded-timeout diagnostic.
        return subprocess.CompletedProcess(
            process.args,
            124,
            stdout,
            f"{stderr}\nChild Shell runner exceeded its {timeout}s deadline.",
        )
    return subprocess.CompletedProcess(process.args, process.returncode, stdout, stderr)
