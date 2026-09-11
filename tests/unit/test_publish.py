"""Publishing state transitions, release inputs and actual Git fast-forward safety.

All network, signing, upload and clean-build operations are replaced with local
fixtures. Nothing in this suite can publish a real release.
"""
import gzip
import hashlib
import json
import os
from pathlib import Path
import subprocess
from types import SimpleNamespace
from urllib.error import HTTPError, URLError

import pytest

from tools import publish
from tests.support.paths import ROOT


NOTES = ('## v1.1 — 2026-09-11\n### Bug Fixes\n'
         '- **Parent App:** Fixed small screens.\n\n'
         '## v1.0 — 2026-09-10\n### New Features\n- Initial release.\n')


@pytest.mark.parametrize('text,current,reason', [
    (NOTES, '1.1', 'higher'), (NOTES, '0.9', 'second'),
    (NOTES.replace('v1.0', 'v1.1'), '1.0', 'unique'),
    (NOTES.replace('v1.1', 'v01.1'), '1.0', 'leading'),
    (NOTES.replace('## v1.0', '### v1.0'), '1.0', 'at least two'),
    (NOTES.replace('v1.1', 'v1.1.2'), '1.0', 'heading'),
    (NOTES.replace('- **Parent App:** Fixed small screens.', ''), '1.0', 'bullet'),
    (NOTES.replace('Fixed', '\x1b[32mFixed'), '1.0', 'control'),
])
def test_history_errors_fail_closed(text, current, reason):
    with pytest.raises(ValueError, match=reason):
        publish.history_entry(text, current)


def test_numeric_order_and_changelog_preserve_only_latest_notes(tmp_path):
    product, body = publish.history_entry(NOTES.replace('1.1', '1.10').replace('1.0', '1.9'), '1.9')
    assert product == '1.10'
    changelog = publish.changelog_entry('1.10+ppa1~ubuntu26.04.1', body)
    assert '  Bug Fixes\n  * Parent App: Fixed small screens.' in changelog
    assert 'Initial release' not in changelog
    path = tmp_path / 'changelog'
    path.write_text(changelog)
    result = subprocess.run(['dpkg-parsechangelog', '-l', str(path), '-S', 'Version'],
                            capture_output=True, text=True, check=True)
    assert result.stdout.strip() == '1.10+ppa1~ubuntu26.04.1'


def test_environment_and_noninteractive_subprocess_do_not_leak_secrets(monkeypatch, tmp_path):
    monkeypatch.setenv('APT_PACKAGE_PRIVATE_KEY_PASSPHRASE', 'private-test-secret')
    monkeypatch.setenv('DEB_BUILD_OPTIONS', 'nocheck')
    monkeypatch.setenv('GIT_CONFIG_COUNT', '1')

    def run(args, **kwargs):
        assert kwargs['stdin'] == subprocess.DEVNULL
        assert 'APT_PACKAGE_PRIVATE_KEY_PASSPHRASE' not in kwargs['env']
        assert 'GIT_CONFIG_COUNT' not in kwargs['env']
        assert kwargs['env']['DEB_BUILD_OPTIONS'] == 'parallel=2'
        assert kwargs['env']['GIT_TERMINAL_PROMPT'] == '0'
        assert 'BatchMode=yes' in kwargs['env']['GIT_SSH_COMMAND']
        return SimpleNamespace(returncode=0, stdout=' M docs/VersionHistory.md\0')

    monkeypatch.setattr(publish.subprocess, 'run', run)
    assert publish.command('git', 'status', cwd=tmp_path).startswith(' M ')


def git(root, *args):
    return subprocess.run(['git', '-c', 'user.name=Test', '-c', 'user.email=test@example.invalid',
                           '-c', 'commit.gpgsign=false', '-c', 'tag.gpgsign=false', *args],
                          cwd=root, env=publish.environment(), capture_output=True,
                          text=True, check=True).stdout.strip()


@pytest.fixture
def repository(tmp_path):
    root = tmp_path / 'development'
    root.mkdir()
    git(root, 'init', '-b', 'main')
    (root / 'docs').mkdir()
    (root / 'data').mkdir()
    (root / 'docs/README.md').write_text('Tracked documentation directory.\n')
    (root / 'data/app.json').write_text('{"version": "1.0"}\n')
    git(root, 'add', 'data/app.json', 'docs/README.md')
    git(root, 'commit', '-m', 'base')
    (root / publish.HISTORY).write_text(NOTES)
    return root


def test_source_gate_accepts_only_history_and_rejects_other_inputs(repository):
    _, notes, current = publish.source_state(repository)
    assert notes == NOTES and current == '1.0'
    (repository / 'private-unrelated-file').write_text('local content')
    with pytest.raises(ValueError, match='commit application changes'):
        publish.source_state(repository)


@pytest.mark.parametrize('tracked,staged', [(False, False), (True, False), (True, True)])
def test_finish_fast_forwards_real_git_with_manually_edited_history(repository, tmp_path, tracked, staged):
    if tracked:
        (repository / publish.HISTORY).write_text(NOTES.replace('Fixed small screens.', 'Earlier notes.'))
        git(repository, 'add', publish.HISTORY)
        git(repository, 'commit', '-m', 'old history')
        (repository / publish.HISTORY).write_text(NOTES)
    if staged:
        git(repository, 'add', publish.HISTORY)
    base = git(repository, 'rev-parse', 'HEAD')
    directory = tmp_path / 'release'
    directory.mkdir()
    checkout = directory / 'source'
    git(repository, 'clone', str(repository), str(checkout))
    (checkout / 'docs').mkdir(exist_ok=True)
    (checkout / publish.HISTORY).write_text(NOTES)
    (checkout / 'data/app.json').write_text('{"version": "1.1"}\n')
    git(checkout, 'add', publish.HISTORY, 'data/app.json')
    git(checkout, 'commit', '-m', 'release')
    revision = git(checkout, 'rev-parse', 'HEAD')
    git(repository, 'remote', 'add', 'origin', str(checkout))
    state = dict(base=base, revision=revision, history_sha256=hashlib.sha256(NOTES.encode()).hexdigest(),
                 directory=str(directory))
    publish.finish_checkout(repository, state, directory / 'release.log')
    assert git(repository, 'rev-parse', 'HEAD') == revision
    assert not git(repository, 'status', '--porcelain')
    assert json.loads((repository / 'data/app.json').read_text())['version'] == '1.1'


def test_finish_refuses_concurrent_edit_without_losing_it(repository, tmp_path):
    base = git(repository, 'rev-parse', 'HEAD')
    state = dict(base=base, revision='new', history_sha256='frozen-digest')
    before = (repository / publish.HISTORY).read_bytes()
    with pytest.raises(ValueError, match='checkout changed'):
        publish.finish_checkout(repository, state, tmp_path / 'log')
    assert (repository / publish.HISTORY).read_bytes() == before


def test_lock_excludes_second_publisher_and_releases_on_error(repository):
    with publish.locked(repository):
        with pytest.raises(ValueError, match='already running'):
            with publish.locked(repository):
                pytest.fail('second lock acquired')
    with publish.locked(repository) as state_path:
        publish.save(state_path, {'phase': 'upload-started'})
        assert json.loads(state_path.read_text())['phase'] == 'upload-started'


@pytest.fixture
def execution(tmp_path, monkeypatch):
    directory = tmp_path / 'release'
    directory.mkdir()
    (directory / 'source').mkdir()
    state = dict(phase='prepared', version='1.1+ppa1~ubuntu26.04.1', product='1.1',
                 revision='frozen', base='base', source_tag='v1.1+ppa1_ubuntu26.04.1',
                 product_tag='v1.1', directory=str(directory))
    state_path = tmp_path / 'state.json'
    publish.save(state_path, state)
    calls = []

    def command(*args, **kwargs):
        calls.append(args)
        if args[:2] == ('git', 'ls-remote'):
            return '\n'.join(f'frozen\trefs/tags/{state[key]}^{{}}' for key in ('source_tag', 'product_tag'))
        if args[0] == 'dput' and '--check-only' not in args:
            assert json.loads(state_path.read_text())['phase'] == 'upload-started'
        if args[:2] == ('git', 'push'):
            assert json.loads(state_path.read_text())['phase'] == 'push-started'
        return ''

    def inspect(*args):
        (directory / 'source-review.json').write_text('{"sha256": {}}')

    def wait(state, state_path):
        calls.append(('wait',))
        state['phase'] = 'published'
        publish.save(state_path, state)

    monkeypatch.setattr(publish, 'command', command)
    monkeypatch.setattr(publish, 'verify_frozen', lambda state: None)
    monkeypatch.setattr(publish, 'inspect_source', inspect)
    monkeypatch.setattr(publish, 'archive_preflight', lambda: None)
    monkeypatch.setattr(publish, 'sources', lambda version=None: [])
    monkeypatch.setattr(publish, 'wait_for_publication', wait)
    monkeypatch.setattr(publish, 'finish_checkout', lambda *args: calls.append(('finish',)))
    return state, state_path, calls


def test_full_workflow_publishes_without_local_tests(execution):
    state, path, calls = execution
    publish.execute(ROOT, state, path)
    assert state['phase'] == 'complete'
    commands = [call[0] for call in calls]
    assert commands.index('dpkg-buildpackage') < commands.index('debsign')
    assert not {'make', 'lintian', 'sbuild', 'dpkg-checkbuilddeps'} & set(commands)
    assert not any('--check-only' in call for call in calls)
    push = next(i for i, call in enumerate(calls) if call[:2] == ('git', 'push'))
    upload = next(i for i, call in enumerate(calls) if call[0] == 'dput' and '--check-only' not in call)
    assert commands.index('debsign') < push < upload < commands.index('wait') < commands.index('finish')
    assert '--atomic' in calls[push]


@pytest.mark.parametrize('phase', ['upload-started', 'published'])
def test_resume_never_reuploads_or_rebuilds_an_attempted_upload(execution, phase):
    state, path, calls = execution
    state['phase'] = phase
    publish.execute(ROOT, state, path)
    assert not any(call[0] in ('dput', 'dpkg-buildpackage', 'debsign', 'lintian') for call in calls)
    assert state['phase'] == 'complete'


def test_source_integrity_failure_prevents_all_remote_mutations(execution, monkeypatch):
    state, path, calls = execution

    def fail(*args):
        raise ValueError('source integrity failed')

    monkeypatch.setattr(publish, 'inspect_source', fail)
    with pytest.raises(ValueError, match='source integrity failed'):
        publish.execute(ROOT, state, path)
    assert json.loads(path.read_text())['phase'] == 'prepared'
    assert not any(call[0] == 'dput' or call[:2] == ('git', 'push') for call in calls)


@pytest.mark.parametrize('phase', ['signed', 'built'])
def test_resume_signed_source_publishes_without_local_tests(execution, phase):
    state, path, calls = execution
    state['phase'] = phase
    publish.execute(ROOT, state, path)
    assert state['phase'] == 'complete'
    assert not any(call[0] in ('make', 'sbuild', 'lintian', 'dpkg-buildpackage', 'debsign') for call in calls)
    assert sum(call[0] == 'dput' for call in calls) == 1


def test_upload_error_monitors_instead_of_repeating(execution, monkeypatch):
    state, path, calls = execution
    state['phase'] = 'pushed'
    original = publish.command

    def fail(*args, **kwargs):
        result = original(*args, **kwargs)
        if args[0] == 'dput':
            raise ValueError('connection lost after upload')
        return result

    monkeypatch.setattr(publish, 'command', fail)
    publish.execute(ROOT, state, path)
    assert sum(call[0] == 'dput' for call in calls) == 1
    assert ('wait',) in calls and state['phase'] == 'complete'


@pytest.fixture
def launchpad(monkeypatch):
    version = '1.1+ppa1~ubuntu26.04.1'
    source = dict(source_package_version=version, distro_series_link=publish.SERIES,
                  status='Published', self_link=publish.API + '/+sourcepub/1')
    build = dict(arch_tag='amd64', buildstate='Successfully built',
                 self_link=publish.API + '/+build/1', web_link='https://launchpad.net/build/1')
    binary = dict(binary_package_version=version, source_package_version=version,
                  distro_arch_series_link=publish.SERIES + '/amd64', build_link=build['self_link'])
    payload = b'published package fixture'
    index = (f'Package: {publish.release.PACKAGE}\nVersion: {version}\nArchitecture: amd64\n'
             f'Filename: pool/main/o/package.deb\nSize: {len(payload)}\n'
             f'SHA256: {hashlib.sha256(payload).hexdigest()}\n')
    monkeypatch.setattr(publish, 'sources', lambda version: [source])
    monkeypatch.setattr(publish, 'collection', lambda url: [build] if 'getBuilds' in url else [binary])
    monkeypatch.setattr(publish, 'read_url', lambda url: gzip.compress(index.encode())
                        if url.endswith('Packages.gz') else payload)
    return version, source, build, binary


def test_success_requires_exact_downloadable_indexed_package(launchpad):
    version, _, _, _ = launchpad
    result = publish.published_binary(version)
    assert result['version'] == version and result['sha256']


@pytest.mark.parametrize('gate,reason', [
    ('acceptance', 'source acceptance'),
    ('source', 'source publication'),
    ('missing-build', 'create the amd64 build'),
    ('build', 'amd64 build (queued)'),
    ('building', 'amd64 build (building)'),
    ('binary', 'binary publication for this exact build'),
    ('index', 'exact version in the PPA amd64 package index'),
    ('missing-index', 'PPA package index (HTTP 404)'),
])
def test_success_is_not_claimed_while_any_publication_gate_is_pending(launchpad, monkeypatch, gate, reason):
    version, source, build, binary = launchpad
    if gate == 'acceptance':
        monkeypatch.setattr(publish, 'sources', lambda version: [])
    elif gate == 'source':
        source['status'] = 'Pending'
    elif gate == 'missing-build':
        monkeypatch.setattr(publish, 'collection', lambda url: [])
    elif gate == 'build':
        build['buildstate'] = 'Needs building'
    elif gate == 'building':
        build['buildstate'] = 'Currently building'
    elif gate == 'binary':
        binary['binary_package_version'] = '1.0'
    elif gate == 'missing-index':
        def missing(url):
            raise HTTPError(url, 404, 'not found', {}, None)
        monkeypatch.setattr(publish, 'read_url', missing)
    else:
        monkeypatch.setattr(publish, 'read_url', lambda url: gzip.compress(b''))
    progress = {}
    assert publish.published_binary(version, progress=progress) is None
    assert reason in progress['detail']


def test_terminal_launchpad_failure_and_binary_tampering_are_errors(launchpad, monkeypatch):
    version, _, build, _ = launchpad
    build['buildstate'] = 'Failed to build'
    with pytest.raises(ValueError, match='Failed to build'):
        publish.published_binary(version)
    build['buildstate'] = 'Successfully built'
    original = publish.read_url
    monkeypatch.setattr(publish, 'read_url', lambda url: original(url)
                        if url.endswith('Packages.gz') else b'corrupt')
    with pytest.raises(ValueError, match='does not match'):
        publish.published_binary(version)


def test_polling_recovers_transient_network_errors_without_upload(tmp_path, monkeypatch, capsys):
    outcomes = iter([URLError('offline'), None, {'version': '1.1'}])

    def poll(version, *, progress):
        progress['detail'] = 'binary published; waiting for the exact version in the PPA amd64 package index'
        result = next(outcomes)
        if isinstance(result, Exception):
            raise result
        return result

    monkeypatch.setattr(publish, 'published_binary', poll)
    monkeypatch.setattr(publish.time, 'sleep', lambda seconds: None)
    state = {'version': '1.1', 'phase': 'upload-started'}
    path = tmp_path / 'state.json'
    publish.wait_for_publication(state, path)
    assert json.loads(path.read_text())['phase'] == 'published'
    output = capsys.readouterr()
    assert 'PPA amd64 package index; status unavailable (URLError)' in output.err
    assert 'UTC (+' in output.out and 'retrying in 30s' in output.out
    assert 'binary published; waiting for the exact version' in output.out
    assert 'publication confirmed:' in output.out
    assert 'waiting for Launchpad acceptance, amd64 build' not in output.out


def test_polling_observes_publication_after_index_propagation(launchpad, tmp_path, monkeypatch, capsys):
    version, _, _, _ = launchpad
    original = publish.read_url
    ready = False

    def read(url):
        if url.endswith('Packages.gz') and not ready:
            return gzip.compress(b'')
        return original(url)

    def sleep(seconds):
        nonlocal ready
        assert seconds == publish.POLL_SECONDS
        assert not ready, 'publisher kept polling after all checks passed'
        ready = True

    monkeypatch.setattr(publish, 'read_url', read)
    monkeypatch.setattr(publish.time, 'sleep', sleep)
    state = {'version': version, 'phase': 'upload-started'}
    path = tmp_path / 'state.json'
    publish.wait_for_publication(state, path)
    saved = json.loads(path.read_text())
    assert saved['phase'] == 'published' and saved['binary']['version'] == version
    output = capsys.readouterr().out
    assert 'binary published; waiting for the exact version in the PPA amd64 package index' in output
    assert output.count('retrying in') == 1


def test_poll_timeout_identifies_last_pending_gate(tmp_path, monkeypatch):
    ticks = iter([0, 0, 1, publish.WAIT_SECONDS])
    monkeypatch.setattr(publish.time, 'monotonic', lambda: next(ticks))
    monkeypatch.setattr(publish.time, 'sleep', lambda seconds: None)

    def pending(version, *, progress):
        progress['detail'] = 'binary published; waiting for PPA package index'

    monkeypatch.setattr(publish, 'published_binary', pending)
    state = {'version': '1.1', 'phase': 'upload-started'}
    with pytest.raises(ValueError, match='last check: binary published; waiting for PPA package index'):
        publish.wait_for_publication(state, tmp_path / 'state.json')
    assert state['phase'] == 'upload-started'


def test_public_reads_require_cache_revalidation(monkeypatch):
    class Response:
        def __enter__(self):
            return self

        def __exit__(self, *args):
            pass

        def read(self):
            return b'current publication status'

    def open_request(request, *, timeout):
        assert request.full_url == publish.API
        assert request.get_method() == 'GET'
        assert request.get_header('Cache-control') == 'no-cache'
        assert timeout == 30
        return Response()

    monkeypatch.setattr(publish, 'urlopen', open_request)
    assert publish.read_url(publish.API) == b'current publication status'


def test_main_colors_errors_and_success_and_restores_environment(monkeypatch, capsys):
    monkeypatch.setenv('APT_PACKAGE_PRIVATE_KEY_PASSPHRASE', 'secret')

    def fail():
        assert 'APT_PACKAGE_PRIVATE_KEY_PASSPHRASE' not in os.environ
        raise ValueError('release failed')

    monkeypatch.setattr(publish, 'publish', fail)
    assert publish.main([]) == 1
    assert '\033[31m' in capsys.readouterr().err
    assert os.environ['APT_PACKAGE_PRIVATE_KEY_PASSPHRASE'] == 'secret'
    publish.say('published', success=True)
    assert '\033[32m' in capsys.readouterr().out


@pytest.mark.parametrize('args,exit_code', [
    (['--help'], 0), (['--force'], 2), (['upload'], 2), (['plan'], 2),
    (['--stat'], 2), (['--status', 'extra'], 2),
    (['prepare', '/tmp/onpc-release-test'], 2),
    (['check-build', '/tmp/onpc-release-test/source'], 2),
])
def test_launcher_help_and_invalid_arguments_have_no_side_effects(args, exit_code):
    result = subprocess.run([str(ROOT / 'tools/publish.py'), *args],
                            capture_output=True, text=True, timeout=10)
    assert result.returncode == exit_code


@pytest.mark.parametrize('exit_code', [0, 7])
@pytest.mark.parametrize('target,arguments', [('publish', []), ('publish-status', ['--status'])])
def test_make_publish_targets_invoke_one_tool_and_propagate_failure(tmp_path, exit_code, target, arguments):
    # Exercise the real Makefile with a recording publisher, never a live upload.
    checkout = tmp_path / 'checkout with spaces'
    (checkout / 'tools').mkdir(parents=True)
    launcher = checkout / 'tools/publish.py'
    launcher.write_text(
        '#!/usr/bin/python3 -IB\nimport json, sys\nfrom pathlib import Path\n'
        'Path("invocation.json").write_text(json.dumps(sys.argv[1:]))\n'
        f'raise SystemExit({exit_code})\n')
    launcher.chmod(0o755)
    (checkout / target).touch()  # The target must run even when this file exists.
    result = subprocess.run(['make', '--no-print-directory', '-f', str(ROOT / 'Makefile'), target],
                            cwd=checkout, capture_output=True, text=True, timeout=10)
    assert (result.returncode == 0) == (exit_code == 0), result.stderr
    assert json.loads((checkout / 'invocation.json').read_text()) == arguments
    if exit_code:
        assert 'Error 7' in result.stderr


def test_default_make_keeps_its_existing_behavior_without_publishing(tmp_path):
    # A plain `make` must never start publication as an accidental default goal.
    result = subprocess.run(['make', '--no-print-directory', '-f', str(ROOT / 'Makefile'), 'VERSION='],
                            cwd=tmp_path, capture_output=True, text=True, timeout=10)
    assert result.returncode != 0
    assert 'Usage: make bump-version' in result.stdout + result.stderr


@pytest.mark.parametrize('phase', ['upload-started', 'published', 'complete'])
@pytest.mark.parametrize('changed_head', [False, True])
def test_status_monitors_recorded_release_with_changed_checkout_without_writes(
        repository, launchpad, monkeypatch, capsys, phase, changed_head):
    version, _, _, _ = launchpad
    original_head = git(repository, 'rev-parse', 'HEAD')
    state = dict(phase=phase, version=version, base=original_head, revision='release-commit',
                 checkout=str(repository), directory='/missing-release-artifacts')
    # A reader also works while the publisher owns its lock.
    with publish.locked(repository) as path:
        publish.save(path, state)
        journal_before = path.read_bytes()
        if changed_head:
            git(repository, 'commit', '--allow-empty', '-m', 'monitoring fix')
        git(repository, 'switch', '-c', 'local-work')
        (repository / 'docs/README.md').write_text('Uncommitted local work.\n')
        (repository / publish.HISTORY).write_text('Unfinished new release notes.\n')
        head = git(repository, 'rev-parse', 'HEAD')
        status = git(repository, 'status', '--porcelain')

        def forbidden(*args, **kwargs):
            pytest.fail('status mode attempted a publishing or writing operation')

        for name in ('save', 'publish', 'source_state', 'verify_frozen', 'execute', 'finish_checkout'):
            monkeypatch.setattr(publish, name, forbidden)
        original_command = publish.command

        def read_only_command(*args, **kwargs):
            assert args == ('git', 'rev-parse', '--git-common-dir')
            return original_command(*args, **kwargs)

        monkeypatch.setattr(publish, 'command', read_only_command)
        publish.publication_status(repository)
        assert path.read_bytes() == journal_before
        assert git(repository, 'rev-parse', 'HEAD') == head
        assert git(repository, 'status', '--porcelain') == status
        assert (repository / 'docs/README.md').read_text() == 'Uncommitted local work.\n'
        assert (repository / publish.HISTORY).read_text() == 'Unfinished new release notes.\n'
    assert f'\033[32mpublish: published {version} for resolute/amd64' in capsys.readouterr().out


def test_status_resumes_polling_without_updating_journal(repository, launchpad, monkeypatch, capsys):
    version, source, _, _ = launchpad
    source['status'] = 'Pending'
    with publish.locked(repository) as path:
        publish.save(path, {'phase': 'upload-started', 'version': version})
    before = path.read_bytes()
    sleeps = []

    def sleep(seconds):
        assert not sleeps, 'monitor did not finish when publication became ready'
        sleeps.append(seconds)
        source['status'] = 'Published'

    monkeypatch.setattr(publish.time, 'sleep', sleep)
    publish.publication_status(repository)
    assert sleeps == [publish.POLL_SECONDS]
    assert path.read_bytes() == before
    output = capsys.readouterr().out
    assert 'waiting for Launchpad source publication' in output
    assert '\033[32mpublish: published' in output


def test_status_without_journal_selects_latest_numeric_ppa_version(repository, monkeypatch):
    versions = ['1.9+ppa20~ubuntu26.04.1', '1.10+ppa2~ubuntu26.04.1', '1.10+ppa10~ubuntu26.04.1']
    entries = [dict(source_package_version=version, distro_series_link=publish.SERIES) for version in versions]
    entries.append(dict(source_package_version='2.0+ppa1~ubuntu26.04.1', distro_series_link='other-series'))
    monkeypatch.setattr(publish, 'sources', lambda: entries)
    checked = []

    def check(version, *, progress):
        checked.append(version)
        return {'version': version}

    monkeypatch.setattr(publish, 'published_binary', check)
    publish.publication_status(repository)
    assert checked == [versions[-1]]
    assert not publish.journal_directory(repository).exists()


@pytest.mark.parametrize('state,reason', [
    ({'phase': 'prepared'}, 'has not reached the upload step'),
    ({'phase': 'signed'}, 'has not reached the upload step'),
    ({'phase': 'built'}, 'has not reached the upload step'),
    ({'phase': 'push-started'}, 'has not reached the upload step'),
    ({'phase': 'pushed'}, 'has not reached the upload step'),
    ({'phase': 'unknown'}, 'invalid publishing journal'),
    ([], 'invalid publishing journal'),
    ({'phase': 'complete', 'version': None}, 'invalid publication version'),
    ({'phase': 'complete', 'version': 'private\ntext'}, 'unsupported publication version'),
])
def test_status_rejects_invalid_or_not_uploaded_journal_before_network(repository, monkeypatch, state, reason):
    with publish.locked(repository) as path:
        publish.save(path, state)
    monkeypatch.setattr(publish, 'sources', lambda *args: pytest.fail('unexpected network read'))
    with pytest.raises(ValueError, match=reason):
        publish.publication_status(repository)


def test_status_without_any_release_fails_without_creating_journal(repository, monkeypatch):
    monkeypatch.setattr(publish, 'sources', lambda: [])
    with pytest.raises(ValueError, match='no recorded release or Launchpad source'):
        publish.publication_status(repository)
    assert not publish.journal_directory(repository).exists()


@pytest.mark.parametrize('interrupted', [False, True])
def test_status_cli_never_dispatches_publisher(monkeypatch, capsys, interrupted):
    calls = []

    def monitor():
        calls.append('status')
        if interrupted:
            raise KeyboardInterrupt

    monkeypatch.setattr(publish, 'publication_status', monitor)
    monkeypatch.setattr(publish, 'publish', lambda: pytest.fail('publisher called'))
    assert publish.main(['--status']) == (130 if interrupted else 0)
    assert calls == ['status']
    if interrupted:
        assert 'rerun the same command' in capsys.readouterr().err


def test_source_history_follows_all_publication_states_and_pagination(monkeypatch):
    urls = []

    def fetch(url):
        urls.append(url)
        if 'status=Deleted' in url:
            return dict(entries=[dict(source_package_version='1.0+ppa3~ubuntu26.04.1')],
                        next_collection_link=publish.API + '?next-page')
        return dict(entries=[])

    monkeypatch.setattr(publish, 'fetch', fetch)
    assert len(publish.sources()) == 1
    assert publish.API + '?next-page' in urls
    for state in ('Pending', 'Published', 'Superseded', 'Deleted', 'Obsolete'):
        assert any('status=' + state in url for url in urls)


@pytest.mark.parametrize('architectures,registered,accepted', [
    (['amd64'], True, True), (['amd64', 'arm64'], True, False),
    ([], True, False), (['amd64'], False, False),
])
def test_archive_preflight_requires_supported_architecture_and_registered_signer(
        monkeypatch, architectures, registered, accepted):
    monkeypatch.setattr(publish, 'fetch', lambda url: dict(private=False, publish=True, status='Active',
                                                        processors_collection_link='processors'))
    monkeypatch.setattr(publish, 'collection', lambda url:
                        [dict(name=name) for name in architectures] if url == 'processors'
                        else [dict(fingerprint=publish.release.KEY if registered else 'wrong')])
    if accepted:
        publish.archive_preflight()
    else:
        with pytest.raises(ValueError):
            publish.archive_preflight()


def test_public_reads_reject_other_hosts_and_pagination_loops(monkeypatch):
    monkeypatch.setattr(publish, 'urlopen', lambda *args, **kwargs: pytest.fail('unexpected request'))
    with pytest.raises(ValueError, match='service URL'):
        publish.read_url('https://unrelated.invalid/private')
    monkeypatch.setattr(publish, 'fetch', lambda url: {'entries': [], 'next_collection_link': url})
    with pytest.raises(ValueError, match='pagination loop'):
        publish.collection(publish.API)


def test_frozen_artifact_changes_are_rejected(tmp_path, monkeypatch):
    source = tmp_path / 'source'
    source.mkdir()
    artifact = tmp_path / 'package.dsc'
    artifact.write_bytes(b'original')
    state = dict(directory=str(tmp_path), revision='frozen', source_sha256={'package.dsc': publish.digest(artifact)})
    monkeypatch.setattr(publish, 'command', lambda *args, **kwargs: 'frozen' if 'rev-parse' in args else '')
    publish.verify_frozen(state)
    artifact.write_bytes(b'tampered')
    with pytest.raises(ValueError, match='artifact changed'):
        publish.verify_frozen(state)


def test_dput_uses_only_generated_configuration_without_user_hooks(tmp_path):
    import configparser
    config = configparser.ConfigParser()
    config.read(publish.dput_config(tmp_path))
    assert config['onpc']['login'] == 'anonymous'
    assert config['onpc']['incoming'] == '~puffyslipperstechllc/ubuntu/oh-no-parent-control/'
    assert config['onpc']['pre_upload_command'] == config['onpc']['post_upload_command'] == ''
    assert config['onpc']['allow_unsigned_uploads'] == '0'


def test_prepare_uses_real_isolated_git_and_only_the_new_history_entry(repository, tmp_path, monkeypatch):
    (repository / 'debian').mkdir()
    previous = publish.changelog_entry('1.0+ppa6~ubuntu26.04.1', '- Earlier package correction.')
    (repository / 'debian/changelog').write_text(previous)
    (repository / '.gitignore').write_text('.envrc\noutput/\n')
    (repository / '.envrc').write_text('private fixture; never copied')
    git(repository, 'add', 'debian/changelog', '.gitignore')
    git(repository, 'commit', '-m', 'packaging')
    remote = tmp_path / 'remote.git'
    git(repository, 'clone', '--bare', str(repository), str(remote))
    monkeypatch.setattr(publish.release, 'ORIGIN', str(remote))
    monkeypatch.setattr(publish, 'preflight', lambda *args: None)
    monkeypatch.setattr(publish, 'sources', lambda: [dict(source_package_version='1.0+ppa6~ubuntu26.04.1')])
    original = publish.command

    def local(*args, **kwargs):
        # Real Git cloning, staging, commits, tags and version comparisons;
        # only the cryptographic signer and package Make check are replaced.
        if args[:4] == ('git', 'config', '--local', 'commit.gpgsign'):
            args = (*args[:-1], 'false')
        if args[:3] == ('git', 'tag', '-s'):
            args = ('git', '-c', 'tag.gpgsign=false', 'tag', '-a', *args[3:])
        if args[0] == 'make':
            return ''
        return original(*args, **kwargs)

    monkeypatch.setattr(publish, 'command', local)
    base, history, current = publish.source_state(repository)
    product, body = publish.history_entry(history, current)
    directory = tmp_path / 'release'
    directory.mkdir()
    state = publish.prepare(repository, base, history, current, product, body, directory)
    checkout = directory / 'source'
    assert state['version'] == '1.1+ppa1~ubuntu26.04.1'
    assert json.loads((checkout / 'data/app.json').read_text())['version'] == '1.1'
    changelog = (checkout / 'debian/changelog').read_text()
    assert changelog.endswith(previous) and changelog.count('Fixed small screens.') == 1
    assert 'Initial release.' not in changelog
    assert not (checkout / '.envrc').exists()
    assert not git(checkout, 'status', '--porcelain')
    assert git(repository, 'rev-parse', 'HEAD') == base
    assert (repository / 'debian/changelog').read_text() == previous


def test_invalid_history_stops_before_preparation(repository, monkeypatch):
    (repository / publish.HISTORY).write_text(NOTES.replace('v1.1', 'v1.0'))
    monkeypatch.setattr(publish, 'prepare', lambda *args: pytest.fail('release preparation started'))
    with pytest.raises(ValueError, match='unique'):
        publish.publish(repository)


@pytest.mark.parametrize('phase,replaced', [('signed', True), ('built', True),
                                         ('push-started', False), ('upload-started', False)])
def test_corrected_source_can_replace_only_attempts_without_public_writes(repository, tmp_path, monkeypatch, phase, replaced):
    directory = tmp_path / 'old-release'
    directory.mkdir()
    state = dict(phase=phase, checkout=str(repository), directory=str(directory),
                 base='old-base', revision='old-release-commit', history_sha256='old-history')
    with publish.locked(repository) as path:
        publish.save(path, state)
    prepared = []

    def prepare(*args):
        prepared.append(True)
        raise ValueError('reached fresh preparation')

    monkeypatch.setattr(publish, 'prepare', prepare)
    with pytest.raises(ValueError, match='fresh preparation' if replaced else 'inputs differ'):
        publish.publish(repository)
    assert bool(prepared) is replaced
    if replaced:
        assert json.loads((directory / 'release.json').read_text())['outcome'] == 'replaced-before-publication'


def test_push_failure_retains_the_public_write_boundary(execution, monkeypatch):
    state, path, calls = execution
    state['phase'] = 'built'
    original = publish.command

    def command(*args, **kwargs):
        result = original(*args, **kwargs)
        if args[:2] == ('git', 'push'):
            raise ValueError('push outcome uncertain')
        return result

    monkeypatch.setattr(publish, 'command', command)
    with pytest.raises(ValueError, match='push outcome uncertain'):
        publish.execute(ROOT, state, path)
    assert json.loads(path.read_text())['phase'] == 'push-started'
    assert not any(call[0] == 'dput' and '--check-only' not in call for call in calls)
