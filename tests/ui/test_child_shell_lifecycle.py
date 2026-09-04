"""Live GNOME Shell lifecycle smoke for the production child extension."""

from __future__ import annotations

import os
import re
import signal
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


def _run_child_shell(environment, timeout=90):
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
        raise AssertionError(
            f"Child Shell runner exceeded its {timeout}s deadline.\n"
            f"runner stdout:\n{stdout}\nrunner stderr:\n{stderr}"
        )
    return subprocess.CompletedProcess(process.args, process.returncode, stdout, stderr)


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
        result = _run_child_shell(environment)

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


def test_child_indicator_opens_one_shared_overlay_and_can_reopen():
    with tempfile.TemporaryDirectory(prefix="onpc-child-interaction-") as temporary:
        artifact_root = Path(temporary)
        environment = {
            **os.environ,
            "ONPC_CHILD_SHELL_ARTIFACT_DIR": str(artifact_root),
            "ONPC_CHILD_SHELL_PYTHON": os.environ.get("PYTHON", sys.executable),
            "ONPC_CHILD_SHELL_SCENARIO": "indicator-interaction",
            "ONPC_PREVIEW_READY_TIMEOUT_SECONDS": "30",
        }
        result = _run_child_shell(environment, timeout=105)

        def artifact(path, missing):
            return path.read_text(encoding="utf-8", errors="replace") \
                if path.exists() else missing

        shell_log = artifact(
            artifact_root / "logs/child-preview-generation-1.log",
            "(Shell log was not created)",
        )
        overlay_log = artifact(
            artifact_root / "logs/request-overlay.log",
            "(overlay log was not created)",
        )
        events = artifact(
            artifact_root / "request-overlay-events.tsv",
            "(request-launch event log was not created)",
        )
        accessibility = artifact(
            artifact_root / "request-overlay.a11y-tree.txt",
            "(accessibility snapshot was not created)",
        )
        diagnostic = (
            f"runner stdout:\n{result.stdout}\nrunner stderr:\n{result.stderr}\n"
            f"request-launch events:\n{events}\n"
            f"complete overlay log:\n{overlay_log}\n"
            f"redacted accessibility snapshot:\n{accessibility}\n"
            f"complete Shell log:\n{shell_log}"
        )
        assert result.returncode == 0, diagnostic
        assert "launches=2 max_concurrent_overlays=1 reopened=true" in result.stdout, diagnostic
        assert events.count("request-launch\t") == 2, diagnostic
        assert "kiosk app starting overlay=True" in overlay_log, diagnostic
        assert overlay_log.count("request station window initialized overlay=True") == 2, diagnostic
        failures = _extension_error_context(shell_log)
        assert not failures, (
            "Extension-attributable Shell diagnostics were emitted:\n"
            + "\n---\n".join(failures)
            + f"\n{diagnostic}"
        )
