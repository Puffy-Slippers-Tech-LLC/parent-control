#!/usr/bin/env python3
"""Wait until fapolicyd is actively enforcing execution decisions."""

from __future__ import annotations

import errno
import subprocess
import time


PROBE = "/usr/libexec/oh-no-parent-control-execution-policy-probe"
PROBE_EXECUTED = 23
RETRY_SECONDS = 0.25


class ReadinessError(RuntimeError):
    """The execution-policy readiness probe failed unexpectedly."""


def policy_is_enforcing(probe: str = PROBE) -> bool:
    """Return true only when fapolicyd denies execution of the canary."""
    try:
        completed = subprocess.run(
            (probe,),
            stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            check=False,
        )
    except PermissionError as error:
        if error.errno in {errno.EACCES, errno.EPERM}:
            return True
        raise ReadinessError("could not execute the readiness probe") from error
    except OSError as error:
        raise ReadinessError("could not execute the readiness probe") from error

    if completed.returncode == PROBE_EXECUTED:
        return False
    raise ReadinessError(
        f"readiness probe returned unexpected status {completed.returncode}"
    )


def wait_until_enforcing() -> None:
    """Block service startup until the kernel has enforced the canary deny."""
    while not policy_is_enforcing():
        time.sleep(RETRY_SECONDS)


def main() -> int:
    wait_until_enforcing()
    print("fapolicyd execution enforcement is ready", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
