"""Live GNOME Shell lifecycle smoke for the production child extension."""

from __future__ import annotations

import os
import re
import subprocess
import sys
import tempfile
from pathlib import Path

import pytest


pytestmark = pytest.mark.ui
ROOT = Path(__file__).resolve().parents[2]
UUID = "oh-no-parent-control@tech.puffyslippers.com"
ERROR_LEVEL = re.compile(r"(?:JS ERROR|CRITICAL|WARNING|ERROR)", re.IGNORECASE)
EXTENSION_IDENTITY = re.compile(
    rf"(?:{re.escape(UUID)}|gnome-shell/extensions/.+/{re.escape(UUID)})",
    re.IGNORECASE,
)


def _extension_error_context(log: str) -> list[str]:
    lines = log.splitlines()
    failures = []
    for index, line in enumerate(lines):
        context = "\n".join(lines[max(0, index - 4):index + 5])
        if ERROR_LEVEL.search(context) and EXTENSION_IDENTITY.search(context):
            failures.append(context)
    return failures


def test_child_extension_lifecycle_in_isolated_shell():
    # Keep XDG_RUNTIME_DIR comfortably below sockaddr_un.sun_path's limit.
    # Pytest's nested tmp_path can exceed it before AT-SPI adds its suffix.
    with tempfile.TemporaryDirectory(prefix="onpc-child-shell-") as temporary:
        artifact_root = Path(temporary)
        environment = {
            **os.environ,
            "ONPC_CHILD_SHELL_ARTIFACT_DIR": str(artifact_root),
            "ONPC_CHILD_SHELL_PYTHON": os.environ.get("PYTHON", sys.executable),
            "ONPC_PREVIEW_READY_TIMEOUT_SECONDS": "30",
        }
        result = subprocess.run(
            ["bash", str(ROOT / "tests/ui/run-child-shell-lifecycle")],
            cwd=ROOT,
            env=environment,
            text=True,
            capture_output=True,
            timeout=90,
            check=False,
        )

        shell_log_path = artifact_root / "logs/child-preview-generation-1.log"
        shell_log = shell_log_path.read_text(encoding="utf-8", errors="replace") \
            if shell_log_path.exists() else "(Shell log was not created)"
        diagnostic = (
            f"runner stdout:\n{result.stdout}\nrunner stderr:\n{result.stderr}\n"
            f"complete Shell log:\n{shell_log}"
        )
        assert result.returncode == 0, diagnostic
        assert re.search(
            r"accessible request name: Request time, 00:4[45] left",
            result.stdout,
        ), diagnostic
        extension_dir = artifact_root / "data/gnome-shell/extensions" / UUID
        assert (extension_dir / "extension.js").is_file()
        assert not any(path.is_symlink() for path in extension_dir.iterdir())
        failures = _extension_error_context(shell_log)
        assert not failures, (
            "Extension-attributable Shell diagnostics were emitted:\n"
            + "\n---\n".join(failures)
            + f"\nComplete Shell log:\n{shell_log}"
        )
