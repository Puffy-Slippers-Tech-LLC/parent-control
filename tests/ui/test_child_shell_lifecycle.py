"""Live GNOME Shell lifecycle smoke for the production child extension."""

from __future__ import annotations

import os
import re
import signal
import hashlib
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

import pytest


pytestmark = pytest.mark.ui
ROOT = Path(__file__).resolve().parents[2]
UUID = "oh-no-parent-control@tech.puffyslippers.com"
ARTIFACTS = ROOT / "artifacts" / "ui" / "child-shell"
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
        # Return a failing result so the caller can retain the reviewable
        # attempt artifacts before presenting this bounded-timeout diagnostic.
        return subprocess.CompletedProcess(
            process.args,
            124,
            stdout,
            f"{stderr}\nChild Shell runner exceeded its {timeout}s deadline.",
        )
    return subprocess.CompletedProcess(process.args, process.returncode, stdout, stderr)


def _new_artifact_root(scenario: str) -> Path:
    # Unix sockets are not supported by every workspace filesystem. The Shell
    # runtime needs one for its private D-Bus, while reviewable evidence is
    # copied to ARTIFACTS below after every completed attempt.
    ARTIFACTS.mkdir(parents=True, exist_ok=True)
    return Path(tempfile.mkdtemp(prefix=f"onpc-child-{scenario}-", dir="/tmp"))


def _tree_fingerprint(root: Path) -> str | None:
    if not root.exists():
        return None
    digest = hashlib.sha256()
    for path in sorted(root.rglob("*")):
        relative = path.relative_to(root).as_posix().encode()
        if path.is_symlink():
            digest.update(b"L\0" + relative + b"\0" + os.readlink(path).encode())
        elif path.is_file():
            digest.update(b"F\0" + relative + b"\0")
            digest.update(path.read_bytes())
    return digest.hexdigest()


def _copy_reviewable_artifacts(artifact_root: Path, destination: Path) -> None:
    # Runtime directories can contain sockets, so publish only reviewable text
    # diagnostics and PNGs rather than recursively copying implementation state.
    candidates = [
        artifact_root / "lifecycle-events.log",
        artifact_root / "reload-evidence.log",
        artifact_root / "request-overlay-events.tsv",
        artifact_root / "request-overlay.a11y-tree.txt",
    ]
    for directory in (artifact_root / "logs", artifact_root / "screenshots"):
        if directory.exists():
            candidates.extend(directory.glob("*"))
    for source in candidates:
        if not source.is_file():
            continue
        relative = source.relative_to(artifact_root)
        target = destination / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, target)


def _preserve_attempt_artifacts(artifact_root: Path, scenario: str) -> Path:
    destination = ARTIFACTS / scenario / artifact_root.name
    _copy_reviewable_artifacts(artifact_root, destination)
    return destination


def _publish_success_artifacts(artifact_root: Path, scenario: str) -> None:
    # The scenario's per-run evidence remains above; this stable path makes
    # the latest passing logs and screenshots convenient to review.
    _copy_reviewable_artifacts(artifact_root, ARTIFACTS / "latest" / scenario)


def _assert_preview_evidence(
    artifact_root: Path,
    generations: int,
    diagnostic: str,
) -> list[str]:
    logs = [artifact_root / "logs" / f"child-preview-generation-{generation}.log"
            for generation in range(1, generations + 1)]
    screenshots = [artifact_root / "screenshots" / f"generation-{generation}.png"
                   for generation in range(1, generations + 1)]
    for path in [*logs, *screenshots, artifact_root / "lifecycle-events.log"]:
        assert path.is_file(), f"Required nested-Shell artifact is missing: {path}\n{diagnostic}"
    for screenshot in screenshots:
        assert screenshot.read_bytes().startswith(b"\x89PNG\r\n\x1a\n"), (
            f"Nested-Shell screenshot is not a PNG: {screenshot}\n{diagnostic}"
        )
    stages = (artifact_root / "lifecycle-events.log").read_text(
        encoding="utf-8", errors="replace"
    )
    assert "stage=setup outcome=success error_category=none" in stages, diagnostic
    assert "stage=screenshot outcome=success error_category=none" in stages, diagnostic
    assert "stage=shutdown outcome=success error_category=none" in stages, diagnostic
    return [path.read_text(encoding="utf-8", errors="replace") for path in logs]


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
    artifact_root = _new_artifact_root("lifecycle")
    environment = {
        **os.environ,
        "ONPC_CHILD_SHELL_ARTIFACT_DIR": str(artifact_root),
        "ONPC_CHILD_SHELL_PYTHON": os.environ.get("PYTHON", sys.executable),
        "ONPC_PREVIEW_READY_TIMEOUT_SECONDS": "30",
    }
    result = _run_child_shell(environment)
    retained_artifacts = _preserve_attempt_artifacts(artifact_root, "lifecycle")

    shell_log_path = artifact_root / "logs/child-preview-generation-1.log"
    shell_log = shell_log_path.read_text(encoding="utf-8", errors="replace") \
        if shell_log_path.exists() else "(Shell log was not created)"
    diagnostic = (
        f"Artifact directory: {retained_artifacts}\n"
        f"runner stdout:\n{result.stdout}\nrunner stderr:\n{result.stderr}\n"
        f"complete Shell log:\n{shell_log}"
    )
    assert result.returncode == 0, diagnostic
    assert re.search(
        r"accessible request name: Request time, 00:4[45] left, generation-one",
        result.stdout,
    ), diagnostic
    logs = _assert_preview_evidence(artifact_root, 1, diagnostic)
    extension_dir = artifact_root / "data/gnome-shell/extensions" / UUID
    assert (extension_dir / "extension.js").is_file()
    assert not any(path.is_symlink() for path in extension_dir.iterdir())
    failures = [failure for log in logs for failure in _extension_error_context(log)]
    assert not failures, (
        "Extension-attributable Shell diagnostics were emitted:\n"
        + "\n---\n".join(failures)
        + f"\n{diagnostic}"
    )
    _publish_success_artifacts(artifact_root, "lifecycle")


def test_child_indicator_opens_one_shared_overlay_and_can_reopen():
    artifact_root = _new_artifact_root("interaction")
    environment = {
        **os.environ,
        "ONPC_CHILD_SHELL_ARTIFACT_DIR": str(artifact_root),
        "ONPC_CHILD_SHELL_PYTHON": os.environ.get("PYTHON", sys.executable),
        "ONPC_CHILD_SHELL_SCENARIO": "indicator-interaction",
        "ONPC_PREVIEW_READY_TIMEOUT_SECONDS": "30",
    }
    result = _run_child_shell(environment, timeout=105)
    retained_artifacts = _preserve_attempt_artifacts(artifact_root, "interaction")

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
        f"Artifact directory: {retained_artifacts}\n"
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
    logs = _assert_preview_evidence(artifact_root, 1, diagnostic)
    failures = [failure for log in logs for failure in _extension_error_context(log)]
    assert not failures, (
        "Extension-attributable Shell diagnostics were emitted:\n"
        + "\n---\n".join(failures)
        + f"\n{diagnostic}"
    )
    _publish_success_artifacts(artifact_root, "interaction")


def test_child_extension_reload_uses_only_a_controlled_copy():
    artifact_root = _new_artifact_root("reload")
    repository_before = _tree_fingerprint(ROOT / "child")
    developer_extension = Path.home() / ".local/share/gnome-shell/extensions" / UUID
    developer_before = _tree_fingerprint(developer_extension)
    environment = {
        **os.environ,
        "ONPC_CHILD_SHELL_ARTIFACT_DIR": str(artifact_root),
        "ONPC_CHILD_SHELL_PYTHON": os.environ.get("PYTHON", sys.executable),
        "ONPC_CHILD_SHELL_SCENARIO": "reload",
        "ONPC_PREVIEW_READY_TIMEOUT_SECONDS": "30",
    }
    result = _run_child_shell(environment, timeout=120)
    retained_artifacts = _preserve_attempt_artifacts(artifact_root, "reload")
    logs = [
        (artifact_root / "logs" / f"child-preview-generation-{generation}.log").read_text(
            encoding="utf-8", errors="replace"
        ) if (artifact_root / "logs" / f"child-preview-generation-{generation}.log").exists()
        else "(Shell log was not created)"
        for generation in (1, 2)
    ]
    diagnostic = (
        f"Artifact directory: {retained_artifacts}\n"
        f"runner stdout:\n{result.stdout}\nrunner stderr:\n{result.stderr}\n"
        f"generation-one log:\n{logs[0]}\n"
        f"generation-two log:\n{logs[1]}"
    )
    assert result.returncode == 0, diagnostic
    assert "generation-one" in result.stdout and "generation-two" in result.stdout, diagnostic
    assert (artifact_root / "reload-evidence.log").read_text(encoding="utf-8") == (
        "source=controlled-copy marker=generation-two\n"
    )
    assert "generation-one" not in (artifact_root / "controlled-extension/previewMode.js").read_text(
        encoding="utf-8"
    )
    assert _tree_fingerprint(ROOT / "child") == repository_before, diagnostic
    assert _tree_fingerprint(developer_extension) == developer_before, diagnostic
    verified_logs = _assert_preview_evidence(artifact_root, 2, diagnostic)
    failures = [failure for log in verified_logs for failure in _extension_error_context(log)]
    assert not failures, (
        "Extension-attributable Shell diagnostics were emitted:\n"
        + "\n---\n".join(failures)
        + f"\n{diagnostic}"
    )
    _publish_success_artifacts(artifact_root, "reload")
