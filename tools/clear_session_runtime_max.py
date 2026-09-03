#!/usr/bin/python3
"""Drop the login-time systemd session cap installed by pam_malcontent.

pam_malcontent still denies a new login when remaining time is zero. It also
stores systemd.runtime_max_sec on the PAM handle, and pam_systemd turns that
into RuntimeMaxSec= on the graphical session scope. This helper runs after
pam_systemd in the session stack and removes that cap so an in-session grant
cannot be undone by a stale kill timer. In-session expiry is a screen lock,
not session teardown.
"""

from __future__ import annotations

import os
import re
import subprocess

SESSION_ID = re.compile(r"^[A-Za-z0-9]+$")
SYSTEMCTL = "/usr/bin/systemctl"
SET_PROPERTY_TIMEOUT_SECONDS = 3


def session_scope_unit(session_id: str) -> str | None:
    """Return the logind session scope name, or None if the id is unusable."""
    if not SESSION_ID.fullmatch(session_id):
        return None
    return f"session-{session_id}.scope"


def clear_runtime_max(session_id: str, run=subprocess.run) -> bool:
    """Clear RuntimeMaxSec on the current login session. Never raise."""
    unit = session_scope_unit(session_id)
    if unit is None:
        return False
    try:
        completed = run(
            [SYSTEMCTL, "set-property", "--runtime", unit, "RuntimeMaxSec=infinity"],
            check=False,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            timeout=SET_PROPERTY_TIMEOUT_SECONDS,
        )
    except (OSError, subprocess.TimeoutExpired):
        return False
    return getattr(completed, "returncode", 1) == 0


def main() -> int:
    # A failure here must not deny the session: account-time remaining is
    # already enforced by pam_malcontent, and lock enforcement is in-session.
    clear_runtime_max(os.environ.get("XDG_SESSION_ID", ""))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
