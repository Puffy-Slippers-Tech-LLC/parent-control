"""Publishing test entry points share a local-only pipeline and preserve failures."""
import json
import os
from pathlib import Path
import subprocess

import pytest

from tools import publishing_checks as checks
from tools import publish

ROOT = Path(__file__).resolve().parents[2]


def test_snapshot_includes_working_changes_and_prepares_history_without_mutating_checkout(tmp_path):
    root, copied = tmp_path / 'working', tmp_path / 'copy'
    root.mkdir()
    for name, content in {
        'data/app.json': '{"version": "1.0"}\n',
        'docs/VersionHistory.md': '## v1.1 — 2026-09-11\n- Next release.\n\n## v1.0 — 2026-09-10\n- Initial.\n',
        'debian/changelog': publish.changelog_entry('1.0+ppa1~ubuntu26.04.1', '- Initial.'),
        '.gitignore': '.envrc\n', 'tool': 'original\n', 'deleted': 'remove\n',
    }.items():
        path = root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content)
    publish.command('git', 'init', '-q', cwd=root)
    publish.command('git', 'add', '--all', cwd=root)
    publish.command('git', '-c', 'user.name=Tests', '-c', 'user.email=tests@invalid',
                    '-c', 'commit.gpgsign=false', 'commit', '-q', '-m', 'Initial', cwd=root)
    (root / 'tool').write_text('working edit\n')
    (root / 'tool').chmod(0o755)
    (root / 'deleted').unlink()
    (root / 'new-file').write_text('untracked\n')
    (root / '.envrc').write_text('PRIVATE_TEST_VALUE=not-for-package\n')
    before = publish.command('git', 'status', '--porcelain', cwd=root)
    checks.snapshot(root, copied, tmp_path / 'test.log')
    assert (copied / 'tool').read_text() == 'working edit\n'
    assert os.access(copied / 'tool', os.X_OK)
    assert (copied / 'new-file').read_text() == 'untracked\n'
    assert not (copied / '.envrc').exists() and not (copied / 'deleted').exists()
    assert json.loads((copied / 'data/app.json').read_text())['version'] == '1.1'
    assert json.loads((root / 'data/app.json').read_text())['version'] == '1.0'
    assert publish.command('git', 'status', '--porcelain', cwd=root) == before
    assert publish.command('git', 'status', '--porcelain', cwd=copied) == ''
    # Already-published metadata also supports ordinary test-all runs.
    checks.snapshot(copied, tmp_path / 'again', tmp_path / 'test.log')
    assert (tmp_path / 'again/debian/changelog').read_bytes() == (copied / 'debian/changelog').read_bytes()


@pytest.mark.parametrize('failure', [None, 'source', 'sbuild', 'binary'])
def test_pipeline_runs_source_and_binary_checks_and_retains_failure(tmp_path, monkeypatch, failure):
    directory = tmp_path / 'attempt'
    directory.mkdir()
    version = '1.1+ppa1~ubuntu26.04.1'
    calls = []
    monkeypatch.setattr(checks.os, 'geteuid', lambda: 1000)
    monkeypatch.setattr(checks.build, 'check_prerequisites', lambda: None)
    monkeypatch.setattr(checks.shutil, 'which', lambda *a, **k: '/usr/bin/tool')
    monkeypatch.setattr(checks.tempfile, 'mkdtemp', lambda **k: str(directory))
    monkeypatch.setattr(checks, 'snapshot', lambda root, checkout, log: checkout.mkdir())

    def command(*args, **kwargs):
        calls.append(args)
        if args[0] == 'dpkg-parsechangelog':
            return version
        if args[0] == 'lintian':
            stage = 'source' if args[-1].endswith('_source.changes') else 'binary'
            if stage == failure:
                raise ValueError(stage + ' failed')
        return ''

    def inspect(root, candidate):
        assert candidate == version
        (root.parent / 'source-review.json').write_text('{"sha256": {}}')

    def build(root):
        calls.append(('sbuild',))
        if failure == 'sbuild':
            raise ValueError('sbuild failed')
        return dict(directory=str(directory / 'build'), status='passed')

    monkeypatch.setattr(checks.publish, 'command', command)
    monkeypatch.setattr(checks.source, 'inspect_archive', inspect)
    monkeypatch.setattr(checks.build, 'check_build', build)
    if failure:
        with pytest.raises(ValueError, match=failure + ' failed'):
            checks.run(tmp_path)
    else:
        checks.run(tmp_path)
    result = json.loads((directory / 'result.json').read_text())
    assert result['status'] == ('failed' if failure else 'passed')
    names = [call[0] for call in calls]
    assert not {'dput', 'debsign', 'gpg'} & set(names)
    assert not any(call[:2] == ('git', 'push') for call in calls)
    assert names.count('lintian') == (1 if failure in ('source', 'sbuild') else 2)
    assert names.count('sbuild') == (0 if failure == 'source' else 1)


@pytest.mark.parametrize('target,category', [('test-publish', 'publish'), ('test-all', 'all')])
@pytest.mark.parametrize('status', [0, 7])
def test_make_entrypoints_dispatch_and_propagate_failure(tmp_path, target, category, status):
    (tmp_path / 'tools').mkdir()
    launcher = tmp_path / 'tools/run-tests'
    launcher.write_text(f'#!/bin/sh\nprintf "%s\\n" "$@"\nexit {status}\n')
    launcher.chmod(0o755)
    (tmp_path / target).touch()
    result = subprocess.run(['make', '--no-print-directory', '-f', str(ROOT / 'Makefile'), target],
                            cwd=tmp_path, text=True, capture_output=True)
    assert result.stdout.strip() == category
    assert bool(result.returncode) == bool(status)


def test_category_dispatch_uses_shared_script_and_rejects_options():
    # The maintained launcher imports these modules from tools/.
    from test_commands import plan
    commands, safety = plan(ROOT, 'publish', [])
    assert commands == [['/usr/bin/python3', '-B', str(ROOT / 'tools/publishing_checks.py')]]
    assert not safety
    with pytest.raises(ValueError, match='no arguments'):
        plan(ROOT, 'publish', ['--skip-build'])
