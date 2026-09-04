#!/usr/bin/env python3
"""Run syntax/lint checks using the public GNOME JavaScript runtime."""

import shutil
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
JS_FILES = [
    ROOT / "child" / name
    for name in (
        "branding.js",
        "indicatorLogic.mjs",
        "logger.js",
        "previewMode.js",
        "sessionPreparationClient.js",
        "timeCalculationClient.js",
        "timerQuery.js",
    )
]


def main():
    gjs = shutil.which("gjs")
    if gjs is None:
        print("GJS is required for make check-static; install the Ubuntu archive package.", file=sys.stderr)
        return 2
    result = 0
    for path in JS_FILES:
        # GJS has no --check flag.  Module mode parses and loads each module
        # through the same maintained runtime used by the Shell extension.
        if path.name == "extension.js":
            continue
        completed = subprocess.run([gjs, "-m", str(path)], cwd=ROOT, check=False)
        result = result or completed.returncode
    return result


if __name__ == "__main__":
    raise SystemExit(main())
