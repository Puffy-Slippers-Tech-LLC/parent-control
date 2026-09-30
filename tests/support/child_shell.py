"""Shared bounded runner for isolated GNOME Shell UI scenarios."""

import os
from pathlib import Path
import subprocess
import sys

from tests.support.paths import ROOT
from tools.test_storage import scratch_descriptors

KILL_AFTER = 30.0


def run_child_shell(environment, timeout=90):
    return _run_child_shell(environment, timeout)


def _run_child_shell(environment, timeout):
    # A separate guardian owns the complete Shell tree and short runtime.
    # Its read end detects pytest death. Only pytest keeps the write end;
    # communicate() must not close it at the start of normal execution.
    read_fd, write_fd = os.pipe()
    process = None
    try:
        process = subprocess.Popen(
            [sys.executable, '-B', str(Path(__file__).with_name('child_shell_owner.py')),
             str(ROOT), str(timeout), str(KILL_AFTER)],
            cwd=ROOT, env=environment, text=True, stdin=read_fd,
            stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            start_new_session=True, pass_fds=scratch_descriptors())
    finally:
        os.close(read_fd)
        # A failed launch leaves no guardian and must release both ends.
        if process is None:
            os.close(write_fd)
    try:
        try:
            stdout, stderr = process.communicate()
        except BaseException:
            os.close(write_fd)
            write_fd = None
            # The guardian still owns descendant cleanup if the outer UI
            # deadline kills this worker while we wait. Never kill the guardian
            # and abandon its detached service identities/runtime allocation.
            process.communicate()
            raise
    finally:
        if write_fd is not None:
            os.close(write_fd)
        process.stdout.close()
        process.stderr.close()
    return subprocess.CompletedProcess(process.args, process.returncode, stdout, stderr)
