"""Live GNOME Shell lifecycle smoke for the production child extension."""

from __future__ import annotations

import os
import re
import hashlib
import json
import shutil
import sys
from pathlib import Path

import pytest

from tests.support.child_shell import extension_error_context, run_child_shell

# The Devkit viewer needs an outer display. Request our private compositor
# explicitly instead of depending on another module having booted it first.
# This also keeps focused and bucket runs off the developer's desktop.
pytestmark = [pytest.mark.ui, pytest.mark.usefixtures('hermetic_ui_session')]
ROOT = Path(__file__).resolve().parents[2]
UUID = "oh-no-parent-control@tech.puffyslippers.com"
ARTIFACTS = ROOT / "artifacts" / "ui" / "child-shell"


def _new_artifact_root(scenario: str, render_artifacts) -> Path:
    # Unix sockets are not supported by every workspace filesystem. The Shell
    # runtime needs one for its private D-Bus, while reviewable evidence is
    # copied to ARTIFACTS below after every completed attempt.
    ARTIFACTS.mkdir(parents=True, exist_ok=True)
    return render_artifacts(f"onpc-child-{scenario}-", parent="/tmp", shader_cache=True)


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
    from tools.test_retention import allocate
    destination = ARTIFACTS / scenario / artifact_root.name
    destination.parent.mkdir(parents=True, exist_ok=True)
    def create():
        destination.mkdir(mode=0o700)
        return destination
    allocate(create)
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
    return extension_error_context(log, UUID)


def test_child_extension_lifecycle_in_isolated_shell(render_artifacts):
    # Keep XDG_RUNTIME_DIR comfortably below sockaddr_un.sun_path's limit.
    # Pytest's nested tmp_path can exceed it before AT-SPI adds its suffix.
    artifact_root = _new_artifact_root("lifecycle", render_artifacts)
    environment = {
        **os.environ,
        "ONPC_CHILD_SHELL_ARTIFACT_DIR": str(artifact_root),
        "ONPC_CHILD_SHELL_PYTHON": os.environ.get("PYTHON", sys.executable),
        "ONPC_PREVIEW_READY_TIMEOUT_SECONDS": "30",
    }
    result = run_child_shell(environment)
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
        r"public request text: Request time, 00:4[45], generation-one",
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


def test_child_indicator_opens_one_shared_overlay_and_can_reopen(render_artifacts):
    artifact_root = _new_artifact_root("interaction", render_artifacts)
    environment = {
        **os.environ,
        "ONPC_CHILD_SHELL_ARTIFACT_DIR": str(artifact_root),
        "ONPC_CHILD_SHELL_PYTHON": os.environ.get("PYTHON", sys.executable),
        "ONPC_CHILD_SHELL_SCENARIO": "indicator-interaction",
        "ONPC_PREVIEW_READY_TIMEOUT_SECONDS": "30",
    }
    result = run_child_shell(environment, timeout=105)
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


def test_editor_preview_uses_real_shell_reminder_banner(render_artifacts):
    artifact_root = _new_artifact_root('reminder-preview', render_artifacts)
    environment = {
        **os.environ,
        'ONPC_CHILD_SHELL_ARTIFACT_DIR': str(artifact_root),
        'ONPC_CHILD_SHELL_PYTHON': os.environ.get('PYTHON', sys.executable),
        'ONPC_CHILD_SHELL_SCENARIO': 'indicator-interaction',
        'ONPC_CHILD_REMINDER_PREVIEW': '1',
        'ONPC_PREVIEW_READY_TIMEOUT_SECONDS': '30',
    }
    result = run_child_shell(environment, timeout=180)
    retained = _preserve_attempt_artifacts(artifact_root, 'reminder-preview')
    shell_path = artifact_root / 'logs/child-preview-generation-1.log'
    shell_log = shell_path.read_text(encoding='utf-8', errors='replace') if shell_path.exists() else '(missing)'
    diagnostic = f'Artifacts: {retained}\n{result.stdout}\n{result.stderr}\n{shell_log}'
    assert result.returncode == 0, diagnostic
    assert 'Real Shell reminder preview and unsaved draft cancellation passed' in result.stdout, diagnostic
    logs = _assert_preview_evidence(artifact_root, 1, diagnostic)
    assert not [failure for log in logs for failure in _extension_error_context(log)], diagnostic


def test_child_panel_refreshes_language_after_overlay_save(render_artifacts):
    # Sample ordinary, RTL and complex-script changes through the complete
    # overlay-to-panel refresh. Catalogue parity covers every other language.
    # Independently reviewed literal meanings; do not predict from runtime MO.
    oracles = {
        'he': dict(request='בקשה', panel='בקשת זמן, %(time)s',
            countdown='הנפשת ספירה לאחור של דקה אחת',
            description='קריאת הזמן שנותר או פתיחת טופס בקשה לזמן נוסף. פתיחת תפריט ההקשר להגדרות הנפשת הספירה לאחור.'),
        'ta': dict(request='கோரிக்கை', panel='நேரத்தைக் கோரவும், %(time)s',
            countdown='ஒரு நிமிட பின்னோக்கு எண்ணிக்கை அசைவூட்டம்',
            description='மீதமுள்ள நேரத்தைப் படிக்கவும் அல்லது கூடுதல் நேரத்தைக் கோரும் படிவத்தைத் திறக்கவும். பின்னோக்கு எண்ணிக்கை அசைவூட்ட அமைப்புகளுக்குச் சூழல் பட்டியைத் திறக்கவும்.'),
        'en': dict(request='REQUEST', panel='Request time, %(time)s',
            countdown='One minute count down animation',
            description='Read the remaining time or open the request-more-time form. Open the context menu for countdown animation settings.'),
    }
    artifact_root = _new_artifact_root('localization', render_artifacts)
    environment = {
        **os.environ,
        'ONPC_CHILD_SHELL_ARTIFACT_DIR': str(artifact_root),
        'ONPC_CHILD_SHELL_PYTHON': os.environ.get('PYTHON', sys.executable),
        'ONPC_CHILD_SHELL_SCENARIO': 'indicator-interaction',
        'ONPC_CHILD_LOCALIZATION_ORACLES': json.dumps(oracles),
        'ONPC_PREVIEW_READY_TIMEOUT_SECONDS': '30',
    }
    result = run_child_shell(environment, timeout=600)
    retained = _preserve_attempt_artifacts(artifact_root, 'localization')
    shell_path = artifact_root / 'logs/child-preview-generation-1.log'
    shell_log = shell_path.read_text(encoding='utf-8', errors='replace') if shell_path.exists() else '(missing)'
    diagnostic = f'Artifacts: {retained}\n{result.stdout}\n{result.stderr}\n{shell_log}'
    assert result.returncode == 0, diagnostic
    assert 'Child panel localization cycle passed' in result.stdout, diagnostic
    for language in oracles:
        assert f'Child panel localization reviewed: {language}' in result.stdout, diagnostic
        assert (artifact_root / 'screenshots' / f'language-{language}.png').is_file(), diagnostic
    events = (artifact_root / 'request-overlay-events.tsv').read_text(encoding='utf-8')
    assert events.count('request-launch\t') == len(oracles), diagnostic
    logs = _assert_preview_evidence(artifact_root, 1, diagnostic)
    assert not [failure for log in logs for failure in _extension_error_context(log)], diagnostic
    _publish_success_artifacts(artifact_root, 'localization')


def test_child_extension_reload_uses_only_a_controlled_copy(render_artifacts):
    artifact_root = _new_artifact_root("reload", render_artifacts)
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
    result = run_child_shell(environment, timeout=120)
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
