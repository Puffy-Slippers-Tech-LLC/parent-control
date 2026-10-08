"""Shared bounded runner for isolated GNOME Shell UI scenarios."""

import os
from pathlib import Path
import re
import subprocess
import sys

from tests.support.paths import ROOT
from tools.test_storage import scratch_descriptors

KILL_AFTER = 30.0


def extension_error_context(log: str, uuid: str) -> list[str]:
    """Attribute a diagnostic and its entire stack, never adjacent records."""
    # GLib/GJS records start with a timestamped, unindented header. Stack
    # continuations belong to that record even across blank lines. In particular,
    # Shell's benign extension-discovery notice must not lend its UUID to a
    # nearby missing-service warning from the isolated desktop.
    records = re.split(r"(?m)(?=^\S[^\n]*\b\d{2}:\d{2}:\d{2}(?:\.\d+)?:)", log)
    error_level = re.compile(r"(?:JS ERROR|CRITICAL|WARNING|ERROR)", re.IGNORECASE)
    return [record.strip() for record in records
            if error_level.search(record) and uuid.lower() in record.lower()]


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
