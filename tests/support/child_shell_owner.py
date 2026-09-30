"""Isolated lifetime owner for the explicitly launched nested Shell tree.

Only this private subprocess becomes a Linux subreaper. Orphans from its sole
launch become its waitable children, including services which call setsid().
Cleanup uses the kernel's direct-child relationship and unreaped identities;
it never scans host processes, executable names or runtime environments.
"""

import ctypes
import os
from pathlib import Path
import signal
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / 'tools'))

from tools.regression_process import Control
from tools.test_storage import runtime_allocation
from tools.test_retention import remove


def become_subreaper():
    # prctl(PR_SET_CHILD_SUBREAPER) affects this guardian only, not pytest.
    libc = ctypes.CDLL(None, use_errno=True)
    if libc.prctl(36, ctypes.c_ulong(1), ctypes.c_ulong(0),
                  ctypes.c_ulong(0), ctypes.c_ulong(0)) != 0:
        error = ctypes.get_errno()
        raise OSError(error, os.strerror(error))


def reap_owned_descendants():
    # This owner has launched only its one runner, and only this thread reaps.
    # Once that runner is reaped, remaining children are kernel-adopted descendants
    # of that explicit launch. Each waitid check confirms current parenthood
    # without reaping before pinning/signalling. Reaping killed parents can
    # adopt another generation; repeat until the owned tree is empty.
    children = Path(f'/proc/self/task/{os.getpid()}/children')
    while True:
        pending = [int(pid) for pid in children.read_text().split()]
        if not pending:
            return
        for pid in pending:
            if os.waitid(os.P_PID, pid, os.WEXITED | os.WNOHANG | os.WNOWAIT) is not None:
                continue  # Already exited; signalling a zombie is unnecessary.
            try:
                descriptor = os.pidfd_open(pid)
            except OSError:
                # No other thread or Popen can reap these adopted children.
                # Kernel parenthood and the unreaped child pin this PID even
                # under descriptor pressure; no discovered host PID is used.
                descriptor = None
            try:
                if descriptor is None:
                    os.kill(pid, signal.SIGKILL)
                else:
                    signal.pidfd_send_signal(descriptor, signal.SIGKILL)
            except ProcessLookupError:
                pass
            except PermissionError:
                # A confined descendant can exit between the first check
                # and signalling, retaining a profile that refuses signals
                # even to its zombie. Confirm exit without reaping; a live
                # refusal remains an error, never an authorization fallback.
                if os.waitid(os.P_PID, pid, os.WEXITED | os.WNOHANG | os.WNOWAIT) is None:
                    raise
            finally:
                if descriptor is not None:
                    os.close(descriptor)
        for pid in pending:
            os.waitpid(pid, 0)


def run_owned(root, environment, timeout, kill_after):
    # The guardian owns socket allocation and inherited scratch locks until
    # the Shell's trapped cleanup AND adopted-descendant reaping finish. EOF
    # from pytest requests cleanup even if pytest was killed without finally.
    with Control().installed(pipe=True) as control:
        runtime = Path(runtime_allocation(tempfile.mkdtemp, prefix='onpc-shell-'))
        info = runtime.stat()
        record = dict(path=str(runtime), device=info.st_dev, inode=info.st_ino, mode=0o700)
        try:
            return control.run(
                ['bash', str(root / 'tests/ui/run-child-shell-lifecycle')],
                cwd=root,
                env={**environment, 'ONPC_CHILD_SHELL_RUNTIME_DIR': str(runtime)},
                output=lambda data: (sys.stdout.buffer.write(data), sys.stdout.buffer.flush()),
                stderr_output=lambda data: (sys.stderr.buffer.write(data), sys.stderr.buffer.flush()),
                timeout=timeout, kill_after=kill_after, cancel_signal=signal.SIGTERM)
        finally:
            # A refusal must retain the registered runtime for recovery;
            # deleting it cannot substitute for settling owned descendants.
            reap_owned_descendants()
            remove(record)


def main():
    root, timeout, kill_after = sys.argv[1:]
    become_subreaper()
    return run_owned(Path(root), os.environ.copy(), float(timeout), float(kill_after))


if __name__ == '__main__':
    sys.exit(main())
