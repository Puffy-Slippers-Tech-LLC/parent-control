"""Publishing jobs keep local prerequisites and results independent."""
import json
import os
from pathlib import Path
import subprocess

import pytest

from tools import publishing_checks as checks
from tools import publish

ROOT = Path(__file__).resolve().parents[2]


@pytest.mark.parametrize('release_date,expected_version', [
    (' — 2026-09-11', '1.1'), (' - 2026-09-11', '1.1'),
    ('', '1.1'), (' -', '1.1'), (' —', '1.1'),
])
def test_snapshot_includes_working_changes_and_prepares_history_without_mutating_checkout(
        tmp_path, release_date, expected_version):
    root, copied = tmp_path / 'working', tmp_path / 'copy'
    root.mkdir()
    for name, content in {
        'data/app.json': '{"version": "1.0"}\n',
        'docs/VersionHistory.md': f'## v1.1{release_date}\n- Next release.\n\n## v1.0 — 2026-09-10\n- Initial.\n',
        'debian/changelog': publish.changelog_entry('1.0+ppa1~ubuntu26.04.1', '- Initial.'),
        'Makefile': ('package-source-files:\n'
                     '\t@printf "%s\\n" Makefile data/app.json debian/changelog tool new-file\n'),
        '.gitignore': '.envrc\n', 'tool': 'original\n', 'deleted': 'remove\n',
        'docs/internal.md': 'initial\n', 'tests/test_unused.py': 'initial\n',
        'tools/internal.py': 'initial\n',
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
    for name in ('docs/internal.md', 'tests/test_unused.py', 'tools/internal.py'):
        (root / name).write_text('unrelated editing with whitespace errors\n\n')
    before = publish.command('git', 'status', '--porcelain', cwd=root)
    checks.snapshot(root, copied, tmp_path / 'test.log')
    assert (copied / 'tool').read_text() == 'working edit\n'
    assert os.access(copied / 'tool', os.X_OK)
    assert (copied / 'new-file').read_text() == 'untracked\n'
    assert not (copied / '.envrc').exists() and not (copied / 'deleted').exists()
    assert not (copied / 'docs').exists()
    assert not (copied / 'tests').exists()
    assert not (copied / 'tools').exists()
    assert json.loads((copied / 'data/app.json').read_text())['version'] == expected_version
    assert (copied / 'debian/changelog').read_text().startswith(
        'oh-no-parent-control (1.1+local1~ubuntu26.04.1)')
    if not release_date.endswith('2026-09-11'):
        with pytest.raises(ValueError, match='invalid VersionHistory.md heading'):
            publish.history_entry((root / 'docs/VersionHistory.md').read_text(), '1.1')
    assert json.loads((root / 'data/app.json').read_text())['version'] == '1.0'
    assert publish.command('git', 'status', '--porcelain', cwd=root) == before
    assert publish.command('git', 'status', '--porcelain', cwd=copied) == ''
    # Already-published metadata also supports ordinary test-all runs.
    checks.snapshot(copied, tmp_path / 'again', tmp_path / 'test.log')
    assert (tmp_path / 'again/debian/changelog').read_bytes() == (copied / 'debian/changelog').read_bytes()


@pytest.mark.parametrize('package_format,failure', [
    ('deb', None), ('deb', 'source'), ('deb', 'sbuild'), ('deb', 'binary'),
    ('rpm', None), ('rpm', 'rpm'),
])
def test_pipeline_runs_source_and_binary_checks_and_retains_failure(tmp_path, monkeypatch, package_format, failure):
    directory = tmp_path / 'attempt'
    directory.mkdir()
    version = '1.1+ppa1~ubuntu26.04.1'
    calls = []
    monkeypatch.setattr(checks.os, 'geteuid', lambda: 1000)
    def prerequisites(selected):
        assert selected == package_format, 'another format must not gate this job'

    monkeypatch.setattr(checks.build, 'check_prerequisites', lambda: prerequisites('deb'))
    monkeypatch.setattr(checks.rpm, 'prerequisites', lambda: prerequisites('rpm'))
    def which(tool, **kwargs):
        if package_format == 'rpm':
            assert tool in ('git', 'make'), 'RPM validation must not require Debian tools'
        return '/usr/bin/tool'

    monkeypatch.setattr(checks.shutil, 'which', which)
    monkeypatch.setattr(checks.tempfile, 'mkdtemp', lambda **k: str(directory))
    monkeypatch.setattr(checks, 'snapshot', lambda root, checkout, log: checkout.mkdir())

    def command(*args, **kwargs):
        calls.append(args)
        if args[0] == 'dpkg-parsechangelog':
            return version
        if args[0] == 'lintian':
            assert kwargs['temporary_directory'] == directory
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
    def rpm_build(root, checkout, directory):
        calls.append(('rpm',))
        if failure == 'rpm':
            raise ValueError('rpm failed')
        return dict(status='passed')

    monkeypatch.setattr(checks.rpm, 'check_build', rpm_build)
    if failure:
        with pytest.raises(ValueError, match=failure + ' failed'):
            checks.run(tmp_path, package_format=package_format)
    else:
        checks.run(tmp_path, package_format=package_format)
    result = json.loads((directory / 'result.json').read_text())
    assert result['status'] == ('failed' if failure else 'passed')
    names = [call[0] for call in calls]
    assert result['package_format'] == package_format
    assert names.count('rpm') == int(package_format == 'rpm')
    if package_format == 'rpm' and not failure:
        assert result['rpm']['status'] == 'passed'
    assert not {'dput', 'debsign', 'gpg'} & set(names)
    assert not any(call[:2] == ('git', 'push') for call in calls)
    assert names.count('lintian') == (0 if package_format == 'rpm' else 1 if failure in ('source', 'sbuild') else 2)
    assert names.count('sbuild') == (0 if package_format == 'rpm' or failure == 'source' else 1)
    if package_format == 'rpm':
        assert not any(name.startswith('dpkg') or name == 'unshare' for name in names)


def test_command_keeps_external_tool_scratch_inside_the_owned_attempt(tmp_path, monkeypatch):
    monkeypatch.setenv('TMPDIR', '/untrusted-caller-location')
    result = publish.command('/usr/bin/mktemp', '-d', temporary_directory=tmp_path)
    assert Path(result).is_dir()
    assert Path(result).parent == tmp_path
    assert 'TMPDIR' not in publish.environment()


@pytest.mark.parametrize('target,category', [('test-all', 'all'),
                                            ('test-all-verify', 'all-verify')])
@pytest.mark.parametrize('status', [0, 7])
def test_make_entrypoints_dispatch_and_propagate_failure(tmp_path, target, category, status):
    (tmp_path / 'tools').mkdir()
    # Exercise the real Make dispatcher in the private checkout, stopping at
    # the stub runner so this check never starts tests or accesses a VM.
    for name in ('tools/vm_selection.py', 'tests/integration/vm_config.py'):
        destination = tmp_path / name
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_bytes((ROOT / name).read_bytes())
    vm = 'onpc-fixture'
    (tmp_path / 'config').mkdir()
    (tmp_path / 'config/test-vm.json').write_text(json.dumps({'families': [{
        'family': 'fixture', 'package_format': 'deb', 'fixture_path': 'common/ubuntu/common', 'vms': [{
        'name': vm, 'disk_anchor': str(tmp_path / 'unused.qcow2'), 'enabled': 'true',
    }]}]}))
    launcher = tmp_path / 'tools/run-tests'
    launcher.write_text(f'#!/bin/sh\nprintf "%s\\n" "$@"\nexit {status}\n')
    launcher.chmod(0o755)
    (tmp_path / target).touch()
    result = subprocess.run(['make', '--no-print-directory', '-f', str(ROOT / 'Makefile'),
                             target, f'VM={vm}'],
                            cwd=tmp_path, text=True, capture_output=True)
    assert result.stdout.splitlines() == [category, '--vm', vm], result.stderr
    assert bool(result.returncode) == bool(status), result.stderr


def test_category_dispatch_uses_shared_script_and_rejects_options():
    # The maintained launcher imports these modules from tools/.
    from test_commands import plan, suite_inventory
    commands, safety = plan(ROOT, 'publish', [])
    assert commands == [['/usr/bin/python3', '-B', str(ROOT / 'tools/publishing_checks.py'),
                         '--package-format', value] for value in ('deb', 'rpm')]
    for category, command in zip(('publish-deb', 'publish-rpm'), commands, strict=True):
        assert plan(ROOT, category, []) == ([command], False)
    assert list(suite_inventory(('publish',))) == ['publish-deb', 'publish-rpm']
    previous = {'publish': {'scope': 'host', 'args': []}}
    assert suite_inventory(('publish',), inventory=previous) == previous
    assert not safety
    with pytest.raises(ValueError, match='no arguments'):
        plan(ROOT, 'publish', ['--skip-build'])
