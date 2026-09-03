#!/usr/bin/env python3
"""Run ShellCheck against repository Bash entry points."""

import shutil
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SHELL_FILES = [
    ROOT / "install.sh",
    ROOT / "setup.sh",
    *(ROOT / "tests/integration/guest" / name for name in ("collect", "run", "setup", "verify")),
]


def main():
    shellcheck = shutil.which("shellcheck")
    if shellcheck is None:
        print("ShellCheck is required for make check-static; install the Ubuntu archive package.", file=sys.stderr)
        return 2
    files = [path for path in SHELL_FILES if path.is_file()]
    return subprocess.run(
        [
            shellcheck,
            "--rcfile", str(ROOT / ".shellcheckrc"),
            "--severity=error",
            *map(str, files),
        ],
        cwd=ROOT,
        check=False,
    ).returncode


if __name__ == "__main__":
    raise SystemExit(main())
