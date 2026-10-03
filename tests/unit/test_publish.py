"""Publishing state transitions, release inputs and actual Git fast-forward safety.

All network, signing, upload and clean-build operations are replaced with local
fixtures. Nothing in this suite can publish a real release.
"""
import gzip
import hashlib
import io
import json
import os
from pathlib import Path
import subprocess
import time
from types import SimpleNamespace
from urllib.error import HTTPError, URLError

import pytest

from tools import publish
from tests.support.paths import ROOT


@pytest.fixture(autouse=True)
def isolated_polling_clock(monkeypatch):
    # Patching the shared time module also changes subprocess.wait's backoff,
    # which can consume a polling fixture's clock or publication transition.
    monkeypatch.setattr(publish, 'time', SimpleNamespace(
        monotonic=publish.time.monotonic, sleep=publish.time.sleep))


NOTES = ('## v1.1 — 2026-09-11\n### Bug Fixes\n'
         '- **Parent App:** Fixed small screens.\n\n'
         '## v1.0 — 2026-09-10\n### New Features\n- Initial release.\n')


@pytest.mark.parametrize('text,current,reason', [
    (NOTES, '1.0', 'updateversion'), (NOTES, '0.9', 'equal'),
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
    product, body = publish.history_entry(NOTES.replace('1.1', '1.10').replace('1.0', '1.9'), '1.10')
    assert product == '1.10'
    changelog = publish.changelog_entry('1.10+ppa1~ubuntu26.04.1', body)
    assert '  Bug Fixes\n  * Parent App: Fixed small screens.' in changelog
    assert 'Initial release' not in changelog
    path = tmp_path / 'changelog'
    path.write_text(changelog)
    result = subprocess.run(['dpkg-parsechangelog', '-l', str(path), '-S', 'Version'],
                            capture_output=True, text=True, check=True)
    assert result.stdout.strip() == '1.10+ppa1~ubuntu26.04.1'


def test_publish_refuses_an_unprepared_product_before_external_work(repository, monkeypatch):
    git(repository, 'add', publish.HISTORY)
    git(repository, 'commit', '-m', 'unprepared candidate')
    git(repository, 'switch', '-c', 'releases/v1.1')
    monkeypatch.setattr(publish, 'confirm_main_update', lambda *args: pytest.fail('main pause started'))
    monkeypatch.setattr(publish, 'prepare', lambda *args: pytest.fail('external work started'))
    with pytest.raises(ValueError, match='updateversion'):
        publish.publish(repository)


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
def unsigned_publisher(monkeypatch):
    monkeypatch.setattr(publish, 'signing_configuration', lambda root: {
        'user.name': 'Test', 'user.email': 'test@example.invalid',
        'commit.gpgsign': 'false', 'tag.gpgsign': 'false'})


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


@pytest.fixture
def release_repository(repository):
    (repository / 'data/app.json').write_text('{"version": "1.1"}\n')
    git(repository, 'add', publish.HISTORY, 'data/app.json')
    git(repository, 'commit', '-m', 'release inputs')
    git(repository, 'switch', '-c', 'releases/v1.1')
    return repository


@pytest.mark.usefixtures('release_repository')
def test_source_gate_requires_committed_inputs(repository):
    _, notes, current = publish.source_state(repository)
    assert notes == NOTES and current == '1.1'
    (repository / 'private-unrelated-file').write_text('local content')
    with pytest.raises(ValueError, match='commit all release inputs'):
        publish.source_state(repository)


@pytest.mark.parametrize('branch', ['main', 'feature', 'releases/v01.1', None, 'releases/v1.2'])
def test_wrong_branch_stops_before_preparation(repository, monkeypatch, branch):
    (repository / 'data/app.json').write_text('{"version": "1.1"}\n')
    git(repository, 'add', publish.HISTORY, 'data/app.json')
    git(repository, 'commit', '-m', 'notes')
    if branch is None:
        git(repository, 'checkout', '--detach')
    elif branch != 'main':
        git(repository, 'switch', '-c', branch)
    monkeypatch.setattr(publish, 'prepare', lambda *args: pytest.fail('preparation started'))
    with pytest.raises(ValueError, match='branch|detached'):
        publish.publish(repository)


@pytest.mark.parametrize('tracked,staged', [(False, False), (True, False), (True, True)])
def test_uncommitted_history_is_rejected_without_losing_it(repository, tracked, staged):
    git(repository, 'switch', '-c', 'releases/v1.1')
    if tracked:
        (repository / publish.HISTORY).write_text(NOTES.replace('Fixed small screens.', 'Earlier notes.'))
        git(repository, 'add', publish.HISTORY)
        git(repository, 'commit', '-m', 'old history')
        (repository / publish.HISTORY).write_text(NOTES)
    if staged:
        git(repository, 'add', publish.HISTORY)
    before = (repository / publish.HISTORY).read_bytes()
    status = git(repository, 'status', '--porcelain')
    with pytest.raises(ValueError, match='commit all release inputs'):
        publish.source_state(repository)
    assert (repository / publish.HISTORY).read_bytes() == before
    assert git(repository, 'status', '--porcelain') == status


@pytest.mark.usefixtures('release_repository')
def test_finish_fast_forwards_real_git_with_committed_history(repository, tmp_path):
    base = git(repository, 'rev-parse', 'HEAD')
    directory = tmp_path / 'release'
    directory.mkdir()
    checkout = directory / 'source'
    git(repository, 'clone', str(repository), str(checkout))
    (checkout / 'docs').mkdir(exist_ok=True)
    (checkout / publish.HISTORY).write_text(NOTES)
    (checkout / 'data/app.json').write_text('{"version": "1.1"}\n')
    (checkout / 'debian').mkdir()
    (checkout / 'debian/changelog').write_text(publish.changelog_entry('1.1+ppa1~ubuntu26.04.1', '- Published.'))
    git(checkout, 'add', publish.HISTORY, 'data/app.json', 'debian/changelog')
    git(checkout, 'commit', '-m', 'release')
    revision = git(checkout, 'rev-parse', 'HEAD')
    git(repository, 'remote', 'add', 'origin', str(checkout))
    state = dict(base=base, revision=revision, history_sha256=hashlib.sha256(NOTES.encode()).hexdigest(),
                 directory=str(directory), branch='releases/v1.1', product='1.1')
    publish.finish_checkout(repository, state, directory / 'release.log')
    assert git(repository, 'rev-parse', 'HEAD') == revision
    assert not git(repository, 'status', '--porcelain')
    assert json.loads((repository / 'data/app.json').read_text())['version'] == '1.1'


@pytest.mark.usefixtures('release_repository')
@pytest.mark.parametrize('change', ['history', 'staged-app', 'commit', 'branch'])
def test_finish_refuses_concurrent_edit_without_losing_it(repository, tmp_path, change):
    base = git(repository, 'rev-parse', 'HEAD')
    state = dict(base=base, revision='new', history_sha256=hashlib.sha256(NOTES.encode()).hexdigest(),
                 branch='releases/v1.1', product='1.1')
    if change == 'history':
        (repository / publish.HISTORY).write_text('New work in progress.\n')
    elif change == 'staged-app':
        (repository / 'data/app.json').write_text('{"version": "1.2"}\n')
        git(repository, 'add', 'data/app.json')
    elif change == 'commit':
        git(repository, 'commit', '--allow-empty', '-m', 'concurrent release edit')
    else:
        git(repository, 'switch', 'main')
    before = (repository / publish.HISTORY).read_bytes()
    head = git(repository, 'rev-parse', 'HEAD')
    status = git(repository, 'status', '--porcelain')
    index = git(repository, 'diff', '--cached')
    with pytest.raises(ValueError, match='commit all release inputs|checkout changed|branch'):
        publish.finish_checkout(repository, state, tmp_path / 'log')
    assert (repository / publish.HISTORY).read_bytes() == before
    assert git(repository, 'rev-parse', 'HEAD') == head
    assert git(repository, 'status', '--porcelain') == status
    assert git(repository, 'diff', '--cached') == index


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
                 product_tag='v1.1', branch='releases/v1.1', directory=str(directory))
    state_path = tmp_path / 'state.json'
    publish.save(state_path, state)
    calls = []

    def command(*args, **kwargs):
        calls.append(args)
        if args[:2] == ('git', 'symbolic-ref'):
            return state['branch']
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
    monkeypatch.setattr(publish.release.package_inputs, 'copy', lambda *args: [])
    monkeypatch.setattr(publish, 'verify_frozen', lambda state: None)
    monkeypatch.setattr(publish, 'inspect_source', inspect)
    monkeypatch.setattr(publish, 'archive_preflight', lambda: None)
    monkeypatch.setattr(publish, 'sources', lambda version=None: [])
    monkeypatch.setattr(publish, 'wait_for_publication', wait)
    monkeypatch.setattr(publish, 'update_main_checkout', lambda *args: calls.append(('main-update',)))
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
    assert upload < commands.index('main-update') < commands.index('wait')
    assert '--atomic' in calls[push]
    assert 'HEAD:refs/heads/releases/v1.1' in calls[push]
    assert not any('HEAD:refs/heads/main' in call for call in calls)


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
    (['--stat'], 2), (['--status', 'extra'], 2), (['--reconcile'], 2),
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
                 checkout=str(repository), branch='releases/v1.1', directory='/missing-release-artifacts')
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
            assert args == ('git', 'rev-parse', '--absolute-git-dir')
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
    assert time.sleep is not sleep  # Subprocess timeout/backoff must keep its real clock.
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


@pytest.mark.usefixtures('release_repository')
@pytest.mark.parametrize('remote_branch', ['absent', 'ancestor', 'diverged'])
def test_prepare_uses_real_isolated_git_and_only_the_new_history_entry(repository, tmp_path, monkeypatch, remote_branch):
    (repository / 'debian').mkdir()
    previous = publish.changelog_entry('1.0+ppa6~ubuntu26.04.1', '- Earlier package correction.')
    private = publish.changelog_entry('1.1+local1~ubuntu26.04.1', '- Private candidate.')
    (repository / 'debian/changelog').write_text(private + previous)
    (repository / '.gitignore').write_text('.envrc\noutput/\n')
    (repository / '.envrc').write_text('private fixture; never copied')
    git(repository, 'add', 'debian/changelog', '.gitignore')
    git(repository, 'commit', '-m', 'packaging')
    remote = tmp_path / 'remote.git'
    git(repository, 'clone', '--bare', str(repository), str(remote))
    if remote_branch == 'absent':
        git(remote, 'symbolic-ref', 'HEAD', 'refs/heads/main')
        git(remote, 'update-ref', '-d', 'refs/heads/releases/v1.1')
    # Main is independently ahead, including remotely. It is not a release gate.
    git(repository, 'switch', 'main')
    git(repository, 'commit', '--allow-empty', '-m', 'main moved independently')
    git(repository, 'push', str(remote), 'main')
    main = git(repository, 'rev-parse', 'main')
    git(repository, 'switch', 'releases/v1.1')
    if remote_branch == 'diverged':
        git(remote, 'update-ref', 'refs/heads/releases/v1.1', main)
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
    if remote_branch == 'diverged':
        with pytest.raises(ValueError, match='git failed'):
            publish.prepare(repository, base, history, current, product, body, directory)
        assert git(repository, 'rev-parse', 'HEAD') == base
        assert git(remote, 'rev-parse', 'releases/v1.1') == main
        assert git(remote, 'tag', '--list') == ''
        return
    state = publish.prepare(repository, base, history, current, product, body, directory)
    checkout = directory / 'source'
    assert state['version'] == '1.1+ppa1~ubuntu26.04.1'
    assert state['branch'] == 'releases/v1.1'
    assert json.loads((checkout / 'data/app.json').read_text())['version'] == '1.1'
    assert (checkout / 'data/app.json').read_bytes() == (repository / 'data/app.json').read_bytes()
    assert git(checkout, 'diff', base, 'HEAD', '--', 'data/app.json') == ''
    changelog = (checkout / 'debian/changelog').read_text()
    assert changelog.endswith(previous) and changelog.count('Fixed small screens.') == 1
    assert 'Initial release.' not in changelog
    assert not (checkout / '.envrc').exists()
    assert not git(checkout, 'status', '--porcelain')
    assert git(repository, 'rev-parse', 'HEAD') == base
    assert (repository / 'debian/changelog').read_text() == private + previous
    assert git(remote, 'rev-parse', 'main') == main


@pytest.mark.usefixtures('release_repository')
def test_invalid_history_stops_before_preparation(repository, monkeypatch):
    (repository / publish.HISTORY).write_text(NOTES.replace('v1.1', 'v1.0'))
    git(repository, 'add', publish.HISTORY)
    git(repository, 'commit', '-m', 'invalid notes')
    monkeypatch.setattr(publish, 'prepare', lambda *args: pytest.fail('release preparation started'))
    with pytest.raises(ValueError, match='unique'):
        publish.publish(repository)


@pytest.mark.parametrize('phase,replaced', [('signed', True), ('built', True),
                                         ('push-started', False), ('upload-started', False)])
@pytest.mark.usefixtures('release_repository')
def test_corrected_source_can_replace_only_attempts_without_public_writes(repository, tmp_path, monkeypatch, phase, replaced):
    mkdtemp = publish.tempfile.mkdtemp
    def temporary_release(**options):
        return mkdtemp(prefix=options['prefix'], dir=tmp_path)
    monkeypatch.setattr(publish.tempfile, 'mkdtemp', temporary_release)
    directory = tmp_path / 'old-release'
    directory.mkdir()
    state = dict(phase=phase, checkout=str(repository), directory=str(directory),
                 base='old-base', revision='old-release-commit', history_sha256='old-history',
                 branch='releases/v1.1')
    with publish.locked(repository) as path:
        publish.save(path, state)
    prepared = []

    def prepare(*args):
        prepared.append(True)
        raise ValueError('reached fresh preparation')

    monkeypatch.setattr(publish, 'prepare', prepare)
    monkeypatch.setattr(publish, 'confirm_main_update', lambda *args: {'phase': 'pending'})
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


def test_preflight_checks_only_the_release_ref(tmp_path, monkeypatch):
    calls = []
    monkeypatch.setattr(publish.os, 'geteuid', lambda: 1000)
    monkeypatch.setattr(publish.os, 'access', lambda *args: True)
    monkeypatch.setattr(publish.shutil, 'which', lambda *args, **kwargs: '/fixture/tool')
    monkeypatch.setattr(publish, 'archive_preflight', lambda: None)

    def command(*args, **kwargs):
        calls.append(args)
        return 'amd64' if args[0] == 'dpkg' else ''

    monkeypatch.setattr(publish, 'command', command)
    publish.preflight(tmp_path, tmp_path / 'release.log', 'releases/v1.3')
    assert calls[-1] == ('git', 'push', '--dry-run', publish.release.ORIGIN,
                         'HEAD:refs/heads/releases/v1.3')


@pytest.mark.parametrize('enlistment', ['clone', 'worktree'])
@pytest.mark.parametrize('interrupt_push', [False, True])
def test_release_isolation_and_interrupted_upload_resume(repository, tmp_path, monkeypatch, unsigned_publisher, enlistment, interrupt_push):
    """Real local Git push/merge/locks, with no network, signing or package build."""
    git(repository, 'add', publish.HISTORY)
    git(repository, 'commit', '-m', 'release inputs on main')
    base = git(repository, 'rev-parse', 'HEAD')
    remote = tmp_path / 'public.git'
    git(repository, 'clone', '--bare', str(repository), str(remote))
    git(repository, 'remote', 'add', 'origin', str(remote))
    root = tmp_path / 'release checkout'
    if enlistment == 'clone':
        git(repository, 'clone', str(remote), str(root))
        git(root, 'switch', '-c', 'releases/v1.1')
    else:
        git(repository, 'worktree', 'add', '-b', 'releases/v1.1', str(root))
    directory = tmp_path / 'frozen'
    directory.mkdir()
    checkout = directory / 'source'
    git(root, 'clone', str(root), str(checkout))
    git(checkout, 'remote', 'set-url', 'origin', str(remote))
    (checkout / 'data/app.json').write_text('{"version": "1.1"}\n')
    (checkout / 'debian').mkdir()
    (checkout / 'debian/changelog').write_text(publish.changelog_entry('1.1+ppa1~ubuntu26.04.1', '- Fixed.'))
    git(checkout, 'add', 'data/app.json', 'debian/changelog')
    git(checkout, 'commit', '-m', 'generated release metadata')
    revision = git(checkout, 'rev-parse', 'HEAD')
    for tag in ('v1.1', 'v1.1+ppa1_ubuntu26.04.1'):
        git(checkout, 'tag', '-a', tag, '-m', 'fixture tag')
    state = dict(phase='signed', checkout=str(root), branch='releases/v1.1',
                 base=base, revision=revision, product='1.1', version='1.1+ppa1~ubuntu26.04.1',
                 source_tag='v1.1+ppa1_ubuntu26.04.1', product_tag='v1.1', directory=str(directory),
                 history_sha256=hashlib.sha256(NOTES.encode()).hexdigest())
    with publish.locked(root) as path:
        publish.save(path, state)
    common = Path(git(repository, 'rev-parse', '--git-common-dir'))
    if not common.is_absolute():
        common = repository / common
    shared_journal = common / 'onpc-publish'
    shared_journal.mkdir(exist_ok=True)
    shared_state = shared_journal / 'state.json'
    shared_state.write_text('{"phase": "upload-started", "shared": true}\n')
    shared_before = shared_state.read_bytes()
    assert publish.journal_directory(root).resolve() != shared_journal.resolve()
    monkeypatch.setattr(publish, 'PUBLIC_GIT', str(remote))
    monkeypatch.setattr(publish.release, 'ORIGIN', str(remote))
    monkeypatch.setattr('builtins.input', lambda prompt: 'yes')
    if enlistment == 'clone':
        git(root, 'config', '--local', 'onpc.publishMainCheckout', str(repository))
    def unsigned(candidate, root):
        git(candidate, 'config', 'user.name', 'Test')
        git(candidate, 'config', 'user.email', 'test@example.invalid')
    monkeypatch.setattr(publish, 'configure_signing', unsigned)
    monkeypatch.setattr(publish, 'inspect_source', lambda *args: None)
    monkeypatch.setattr(publish, 'archive_preflight', lambda: None)
    monkeypatch.setattr(publish, 'sources', lambda version=None: [])
    original = publish.command
    uploads = []
    pushes = []

    def command(*args, **kwargs):
        if args[:2] == ('git', 'push'):
            result = original(*args, **kwargs)
            pushes.append(args)
            if interrupt_push and len(pushes) == 1:
                raise KeyboardInterrupt  # Server accepted refs; local phase is uncertain.
            return result
        if args[0] == 'dput':
            uploads.append(args)
            assert json.loads(path.read_text())['phase'] == 'upload-started'
            # Main can commit while the release publisher actually owns its lock.
            # Its separate publishing lock is also available, but this release's
            # lock still prevents a second publisher from repeating the upload.
            with publish.locked(repository):
                git(repository, 'commit', '--allow-empty', '-m', 'independent main work')
            with pytest.raises(ValueError, match='already running'):
                with publish.locked(root):
                    pytest.fail('release lock not held')
            raise KeyboardInterrupt
        return original(*args, **kwargs)

    monkeypatch.setattr(publish, 'command', command)
    if interrupt_push:
        with pytest.raises(KeyboardInterrupt):
            publish.publish(root)
        assert json.loads(path.read_text())['phase'] == 'push-started'
        assert uploads == []
    with pytest.raises(KeyboardInterrupt):
        publish.publish(root)
    assert len(uploads) == 1
    assert len(pushes) == (2 if interrupt_push else 1)
    assert json.loads(path.read_text())['phase'] == 'upload-started'
    assert git(remote, 'rev-parse', 'main') == base
    assert git(remote, 'rev-parse', 'releases/v1.1') == revision
    assert git(root, 'rev-parse', 'HEAD') == base
    main_after_update = []

    def wait(state, state_path):
        head = git(repository, 'rev-parse', 'HEAD')
        assert state['main_update']['phase'] == 'complete'
        assert git(repository, 'status', '--porcelain') == ''
        assert git(remote, 'rev-parse', 'main') == head
        assert git(repository, 'rev-parse', 'origin/main') == head
        assert json.loads((repository / 'data/app.json').read_text())['version'] == '1.1'
        # Main work resumes during monitoring without touching the release.
        git(repository, 'commit', '--allow-empty', '-m', 'main development resumed')
        (repository / 'docs/README.md').write_text('Uncommitted main development.\n')
        main_after_update.append(git(repository, 'rev-parse', 'HEAD'))
        state['phase'] = 'published'
        publish.save(state_path, state)

    monkeypatch.setattr(publish, 'wait_for_publication', wait)
    publish.publish(root)
    assert len(uploads) == 1
    assert json.loads(path.read_text())['phase'] == 'complete'
    assert git(root, 'rev-parse', 'HEAD') == revision
    assert git(root, 'status', '--porcelain') == ''
    assert git(repository, 'rev-parse', 'HEAD') == main_after_update[0]
    assert git(repository, 'status', '--porcelain') == 'M docs/README.md'
    assert (repository / 'docs/README.md').read_text() == 'Uncommitted main development.\n'
    assert shared_state.read_bytes() == shared_before


@pytest.mark.usefixtures('release_repository')
@pytest.mark.parametrize('change', ['branch', 'checkout', 'legacy'])
def test_resume_refuses_changed_owner_before_execution(repository, monkeypatch, change):
    base = git(repository, 'rev-parse', 'HEAD')
    state = dict(phase='upload-started', checkout=str(repository), branch='releases/v1.1',
                 base=base, revision='frozen', history_sha256=hashlib.sha256(NOTES.encode()).hexdigest())
    if change == 'branch':
        git(repository, 'switch', '-c', 'releases/v1.2')
    elif change == 'checkout':
        state['checkout'] += '-another-clone'
    else:
        del state['branch']
    with publish.locked(repository) as path:
        publish.save(path, state)
    before = path.read_bytes()
    monkeypatch.setattr(publish, 'execute', lambda *args: pytest.fail('execution started'))
    with pytest.raises(ValueError, match='branch|checkout|legacy'):
        publish.publish(repository)
    assert path.read_bytes() == before


@pytest.fixture
def main_update_candidate(repository, tmp_path, monkeypatch, unsigned_publisher):
    git(repository, 'add', publish.HISTORY)
    git(repository, 'commit', '-m', 'prepared inputs')
    base = git(repository, 'rev-parse', 'HEAD')
    remote = tmp_path / 'origin.git'
    git(repository, 'clone', '--bare', str(repository), str(remote))
    git(repository, 'remote', 'add', 'origin', str(remote))
    root = tmp_path / 'release-root'
    git(repository, 'clone', str(remote), str(root))
    git(root, 'switch', '-c', 'releases/v1.1')
    git(root, 'config', 'onpc.publishMainCheckout', str(repository))
    directory = tmp_path / 'evidence'
    directory.mkdir()
    source = directory / 'source'
    git(root, 'clone', str(root), str(source))
    (source / 'data/app.json').write_text('{"version": "1.1"}\n')
    git(source, 'add', 'data/app.json')
    git(source, 'commit', '-m', 'release metadata')
    revision = git(source, 'rev-parse', 'HEAD')
    state = dict(phase='upload-started', base=base, revision=revision, directory=str(directory),
                 main_update={'checkout': str(repository), 'phase': 'pending'})
    path = tmp_path / 'state.json'
    publish.save(path, state)
    monkeypatch.setattr(publish.release, 'ORIGIN', str(remote))
    monkeypatch.setattr(publish, 'PUBLIC_GIT', str(remote))

    def unsigned(candidate, root):
        git(candidate, 'config', 'user.name', 'Test')
        git(candidate, 'config', 'user.email', 'test@example.invalid')

    monkeypatch.setattr(publish, 'configure_signing', unsigned)
    return repository, root, remote, state, path


@pytest.mark.parametrize('enlistment', ['clone', 'worktree'])
@pytest.mark.parametrize('main_advanced', [False, True])
def test_publish_commits_every_pending_release_change_and_reconciles_main(
        main_update_candidate, tmp_path, monkeypatch, enlistment, main_advanced):
    target, root, remote, _, _ = main_update_candidate
    if enlistment == 'worktree':
        root = tmp_path / 'linked-release'
        git(target, 'worktree', 'add', '-b', 'releases/v1.1', str(root))
    (root / 'obsolete-file').write_text('Remove during release preparation.\n')
    git(root, 'add', 'obsolete-file')
    git(root, 'commit', '-m', 'earlier release-only change')
    (root / 'obsolete-file').unlink()
    (root / 'data/app.json').write_text('{"version": "1.1"}\n')
    (root / 'docs/README.md').write_text('Staged release edit.\n')
    git(root, 'add', 'docs/README.md')
    (root / 'docs/README.md').write_text('Final release edit.\n')
    (root / 'new-release-file').write_text('New release content.\n')
    (root / '.gitignore').write_text('.envrc\n')
    (root / '.envrc').write_text('ignored fixture, never a credential\n')
    release_before = git(root, 'rev-parse', 'HEAD')
    release_config = git(root, 'config', '--local', '--list')
    if main_advanced:
        (target / 'main-only-file').write_text('Independent development.\n')
        git(target, 'add', 'main-only-file')
        git(target, 'commit', '-m', 'main advanced independently')
    main_before = git(target, 'rev-parse', 'HEAD')
    main_config = git(target, 'config', '--local', '--list')
    monkeypatch.setattr('builtins.input', lambda prompt: 'yes')
    mkdtemp = publish.tempfile.mkdtemp
    monkeypatch.setattr(publish.tempfile, 'mkdtemp', lambda **options:
                        mkdtemp(prefix=options['prefix'], dir=tmp_path))
    prepared = []

    def prepare(checkout, base, history, current, product, notes, directory):
        assert checkout == root and current == product == '1.1'
        assert base != release_before
        assert git(root, 'rev-parse', 'HEAD') == base
        assert git(root, 'status', '--porcelain') == ''
        git(target, 'merge-base', '--is-ancestor', base, 'HEAD')
        assert git(remote, 'rev-parse', 'main') != git(target, 'rev-parse', 'HEAD')
        frozen = directory / 'source'
        git(root, 'clone', str(root), str(frozen))
        (frozen / 'debian').mkdir(exist_ok=True)
        (frozen / 'debian/changelog').write_text('Official release metadata.\n')
        git(frozen, 'add', 'debian/changelog')
        git(frozen, 'commit', '-m', 'official release metadata')
        prepared.append(base)
        return dict(phase='prepared', base=base, revision=git(frozen, 'rev-parse', 'HEAD'),
                    directory=str(directory), product=product)

    monkeypatch.setattr(publish, 'prepare', prepare)
    # Exercise the actual main metadata update/push with only local Git.
    monkeypatch.setattr(publish, 'execute', publish.update_main_checkout)
    publish.publish(root)
    assert len(prepared) == 1
    git(target, 'merge-base', '--is-ancestor', main_before, 'HEAD')
    git(target, 'merge-base', '--is-ancestor', prepared[0], 'HEAD')
    assert git(target, 'rev-parse', 'HEAD') == git(remote, 'rev-parse', 'main')
    assert git(target, 'status', '--porcelain') == ''
    for checkout in (root, target):
        assert (checkout / 'docs/README.md').read_text() == 'Final release edit.\n'
        assert (checkout / 'new-release-file').read_text() == 'New release content.\n'
        assert not (checkout / 'obsolete-file').exists()
        assert git(checkout, 'ls-files', '.envrc') == ''
    assert (root / '.envrc').read_text() == 'ignored fixture, never a credential\n'
    assert git(root, 'config', '--local', '--list') == release_config
    assert git(target, 'config', '--local', '--list') == main_config
    if main_advanced:
        assert (target / 'main-only-file').read_text() == 'Independent development.\n'
    # A clean retry does not create another preparation commit.
    publish.commit_release_inputs(root)
    assert git(root, 'rev-parse', 'HEAD') == prepared[0]


@pytest.mark.usefixtures('release_repository')
@pytest.mark.parametrize('phase', ['push-started', 'pushed', 'upload-started', 'published'])
def test_pending_changes_after_public_write_are_preserved_without_commit(repository, phase):
    (repository / 'pending-release-edit').write_text('Keep this work.\n')
    head = git(repository, 'rev-parse', 'HEAD')
    status = git(repository, 'status', '--porcelain')
    with pytest.raises(ValueError, match='publication started'):
        publish.commit_release_inputs(repository, {'phase': phase})
    assert git(repository, 'rev-parse', 'HEAD') == head
    assert git(repository, 'status', '--porcelain') == status
    assert (repository / 'pending-release-edit').read_text() == 'Keep this work.\n'


@pytest.mark.usefixtures('release_repository')
def test_release_auto_commit_refuses_existing_merge(repository):
    (repository / 'pending-release-edit').write_text('Keep this work.\n')
    (repository / '.git/MERGE_HEAD').write_text(git(repository, 'rev-parse', 'HEAD') + '\n')
    head = git(repository, 'rev-parse', 'HEAD')
    index = git(repository, 'diff', '--cached')
    with pytest.raises(ValueError, match='existing Git operation in release checkout'):
        publish.commit_release_inputs(repository)
    assert git(repository, 'rev-parse', 'HEAD') == head
    assert git(repository, 'diff', '--cached') == index


@pytest.mark.parametrize('answer', ['no', '', None])
def test_main_pause_confirmation_refuses_without_writes(main_update_candidate, monkeypatch, capsys, answer):
    target, root, remote, state, path = main_update_candidate
    before = path.read_bytes()

    def respond(prompt):
        assert 'development is paused' in prompt
        if answer is None:
            raise EOFError
        return answer

    monkeypatch.setattr('builtins.input', respond)
    with pytest.raises(ValueError, match='cancelled'):
        publish.confirm_main_update(root, state['base'])
    assert '\033[1;33m' in capsys.readouterr().out
    assert git(target, 'rev-parse', 'HEAD') == state['base']
    assert git(remote, 'rev-parse', 'main') == state['base']
    assert path.read_bytes() == before


def test_declining_publish_stops_before_preparation(main_update_candidate, monkeypatch):
    target, root, _, _, _ = main_update_candidate
    (target / 'data/app.json').write_text('{"version": "1.1"}\n')
    git(target, 'add', 'data/app.json')
    git(target, 'commit', '-m', 'prepare candidate version on main')
    git(root, 'fetch', str(target), 'main')
    git(root, 'merge', '--ff-only', 'FETCH_HEAD')
    monkeypatch.setattr('builtins.input', lambda prompt: 'no')
    monkeypatch.setattr(publish, 'prepare', lambda *args: pytest.fail('preparation before confirmation'))
    monkeypatch.setattr(publish, 'sources', lambda *args: pytest.fail('network before confirmation'))
    with pytest.raises(ValueError, match='cancelled'):
        publish.publish(root)
    assert not (publish.journal_directory(root) / 'state.json').exists()


def test_main_update_failure_cannot_claim_handoff_or_start_monitoring(execution, monkeypatch, capsys):
    state, path, calls = execution

    def fail(*args):
        raise ValueError('main update failed')

    monkeypatch.setattr(publish, 'update_main_checkout', fail)
    with pytest.raises(ValueError, match='main update failed'):
        publish.execute(ROOT, state, path)
    assert json.loads(path.read_text())['phase'] == 'upload-started'
    assert ('wait',) not in calls
    assert 'MAIN UPDATED' not in capsys.readouterr().out


def test_concurrent_remote_main_push_is_never_overwritten(main_update_candidate, tmp_path, monkeypatch):
    target, root, remote, state, path = main_update_candidate
    peer = tmp_path / 'concurrent-peer'
    git(target, 'clone', str(remote), str(peer))
    git(peer, 'commit', '--allow-empty', '-m', 'concurrent remote change')
    peer_head = git(peer, 'rev-parse', 'HEAD')
    original = publish.command

    def command(*args, **kwargs):
        if args[:2] == ('git', 'push'):
            git(peer, 'push', 'origin', 'main')
        return original(*args, **kwargs)

    monkeypatch.setattr(publish, 'command', command)
    with pytest.raises(ValueError, match='git failed'):
        publish.update_main_checkout(root, state, path)
    assert git(remote, 'rev-parse', 'main') == peer_head
    assert git(target, 'rev-parse', 'HEAD') == state['base']
    assert git(target, 'status', '--porcelain') == ''
    assert json.loads(path.read_text())['main_update']['phase'] == 'ready'


def test_independent_clone_asks_for_main_path(main_update_candidate, monkeypatch):
    target, root, _, state, _ = main_update_candidate
    git(root, 'config', '--unset', 'onpc.publishMainCheckout')
    replies = iter([str(target), 'yes'])
    monkeypatch.setattr('builtins.input', lambda prompt: next(replies))
    assert publish.confirm_main_update(root, state['base']) == state['main_update']


@pytest.mark.parametrize('changed_files', [False, True])
@pytest.mark.parametrize('enlistment', ['clone', 'worktree'])
def test_release_only_inputs_fast_forward_main_and_publish_metadata(
        main_update_candidate, monkeypatch, tmp_path, changed_files, enlistment):
    target, root, remote, state, path = main_update_candidate
    if enlistment == 'worktree':
        root = tmp_path / 'linked-release'
        git(target, 'worktree', 'add', '-b', 'releases/v1.1', str(root))
    if changed_files:
        (root / 'docs/README.md').write_text('Committed release inputs.\n')
        git(root, 'add', 'docs/README.md')
    git(root, 'commit', '--allow-empty', '-m', 'release-only input commit')
    state['base'] = git(root, 'rev-parse', 'HEAD')
    head = git(target, 'rev-parse', 'HEAD')
    monkeypatch.setattr('builtins.input', lambda prompt: 'yes')
    state['main_update'] = publish.confirm_main_update(root, state['base'])
    assert git(target, 'rev-parse', 'HEAD') == state['base']
    assert git(remote, 'rev-parse', 'main') == head
    # A retry after interruption between reconciliation and journal creation
    # reuses the same commit and remains a fast-forward.
    assert publish.confirm_main_update(root, state['base']) == state['main_update']
    publish.update_main_checkout(root, state, path)
    assert state['main_update']['phase'] == 'complete'
    assert git(target, 'rev-parse', 'HEAD') == git(remote, 'rev-parse', 'main')
    git(target, 'merge-base', '--is-ancestor', state['base'], 'HEAD')
    assert git(target, 'status', '--porcelain') == ''
    assert json.loads((target / 'data/app.json').read_text())['version'] == '1.1'
    if changed_files:
        assert (target / 'docs/README.md').read_text() == 'Committed release inputs.\n'


@pytest.mark.parametrize('failure', ['declined', 'dirty', 'fetch-race'])
def test_release_input_reconciliation_preserves_main_on_refusal(
        main_update_candidate, monkeypatch, failure):
    target, root, remote, state, path = main_update_candidate
    git(root, 'commit', '--allow-empty', '-m', 'release-only input commit')
    base = git(root, 'rev-parse', 'HEAD')
    head = git(target, 'rev-parse', 'HEAD')
    remote_head = git(remote, 'rev-parse', 'main')
    before = path.read_bytes()

    def respond(prompt):
        if failure == 'dirty':
            (target / 'docs/README.md').write_text('Uncommitted development.\n')
        return 'no' if failure == 'declined' else 'yes'

    monkeypatch.setattr('builtins.input', respond)
    original = publish.command
    calls = []

    def command(*args, **kwargs):
        calls.append(args)
        result = original(*args, **kwargs)
        if failure == 'fetch-race' and args[:2] == ('git', 'fetch'):
            git(target, 'commit', '--allow-empty', '-m', 'development during fetch')
        return result

    monkeypatch.setattr(publish, 'command', command)
    with pytest.raises(ValueError, match='cancelled|diverged|changes|advanced'):
        publish.confirm_main_update(root, base)
    assert not any(args[:2] == ('git', 'merge') for args in calls)
    if failure in ('declined', 'dirty'):
        assert not any(args[:2] == ('git', 'fetch') for args in calls)
    if failure == 'fetch-race':
        head = git(target, 'rev-parse', 'HEAD')
        assert head != state['base']
    assert git(target, 'rev-parse', 'HEAD') == head
    if failure == 'dirty':
        assert (target / 'docs/README.md').read_text() == 'Uncommitted development.\n'
    else:
        assert git(target, 'status', '--porcelain') == ''
    assert git(remote, 'rev-parse', 'main') == remote_head
    assert path.read_bytes() == before
    assert not list(Path(state['directory']).glob('main-update-*'))


def test_diverged_release_inputs_merge_directly_and_retry_without_extra_commit(
        main_update_candidate, monkeypatch):
    target, root, remote, state, path = main_update_candidate
    (root / 'release-change').write_text('Release work.\n')
    git(root, 'add', 'release-change')
    git(root, 'commit', '-m', 'release-only work')
    state['base'] = git(root, 'rev-parse', 'HEAD')
    (target / 'main-change').write_text('Main work.\n')
    git(target, 'add', 'main-change')
    git(target, 'commit', '-m', 'main-only work')
    main_before = git(target, 'rev-parse', 'HEAD')
    config_before = git(target, 'config', '--local', '--list')
    monkeypatch.setattr('builtins.input', lambda prompt: 'yes')
    publish.confirm_main_update(root, state['base'])
    merged = git(target, 'rev-parse', 'HEAD')
    assert git(target, 'rev-parse', 'HEAD^1') == main_before
    assert git(target, 'rev-parse', 'HEAD^2') == state['base']
    assert (target / 'release-change').read_text() == 'Release work.\n'
    assert (target / 'main-change').read_text() == 'Main work.\n'
    assert git(target, 'config', '--local', '--list') == config_before
    publish.confirm_main_update(root, state['base'])
    assert git(target, 'rev-parse', 'HEAD') == merged
    publish.update_main_checkout(root, state, path)
    assert state['main_update']['phase'] == 'complete'
    assert git(target, 'rev-parse', 'HEAD') == git(remote, 'rev-parse', 'main')
    assert git(target, 'status', '--porcelain') == ''


def test_release_merge_conflict_preserves_commits_and_leaves_actionable_status(
        main_update_candidate, monkeypatch):
    target, root, remote, state, path = main_update_candidate
    for checkout, text in ((target, 'Main edit.\n'), (root, 'Release edit.\n')):
        (checkout / 'docs/README.md').write_text(text)
        git(checkout, 'add', 'docs/README.md')
        git(checkout, 'commit', '-m', 'independent edit')
    head = git(target, 'rev-parse', 'HEAD')
    base = git(root, 'rev-parse', 'HEAD')
    remote_head = git(remote, 'rev-parse', 'main')
    monkeypatch.setattr('builtins.input', lambda prompt: 'yes')
    with pytest.raises(ValueError, match='resolve or abort any merge'):
        publish.confirm_main_update(root, base)
    assert git(target, 'rev-parse', 'HEAD') == head
    assert git(root, 'rev-parse', 'HEAD') == base
    assert git(remote, 'rev-parse', 'main') == remote_head
    assert git(target, 'rev-parse', 'MERGE_HEAD') == base
    assert 'UU docs/README.md' in git(target, 'status', '--porcelain')


@pytest.mark.parametrize('change', ['dirty', 'branch', 'operation', 'origin'])
def test_unsafe_main_is_refused_before_confirmation(main_update_candidate, monkeypatch, change):
    target, root, _, state, _ = main_update_candidate
    if change == 'dirty':
        (target / 'docs/README.md').write_text('Keep this work.\n')
    elif change == 'branch':
        git(target, 'switch', '-c', 'development')
    elif change == 'origin':
        git(target, 'remote', 'set-url', 'origin', '/unrelated/repo')
    else:
        (target / '.git/CHERRY_PICK_HEAD').write_text(state['base'] + '\n')
    monkeypatch.setattr('builtins.input', lambda prompt: pytest.fail('unexpected confirmation'))
    with pytest.raises(ValueError):
        publish.confirm_main_update(root, state['base'])


def test_main_cherry_pick_conflict_never_changes_development_checkout(main_update_candidate):
    target, root, remote, state, path = main_update_candidate
    (target / 'data/app.json').write_text('{"version": "2.0"}\n')
    git(target, 'add', 'data/app.json')
    git(target, 'commit', '-m', 'conflicting main metadata')
    head = git(target, 'rev-parse', 'HEAD')
    with pytest.raises(ValueError, match='cherry-pick failed'):
        publish.update_main_checkout(root, state, path)
    assert git(target, 'rev-parse', 'HEAD') == head
    assert git(target, 'status', '--porcelain') == ''
    assert not (target / '.git/CHERRY_PICK_HEAD').exists()
    assert git(remote, 'rev-parse', 'main') == state['base']
    assert state['main_update']['phase'] == 'pending'


@pytest.mark.parametrize('boundary', ['push-error', 'push-interrupt', 'merge-interrupt'])
def test_main_update_recovery_is_idempotent(main_update_candidate, monkeypatch, boundary):
    target, root, remote, state, path = main_update_candidate
    original = publish.command
    cherry_picks = []
    failed = False

    def command(*args, **kwargs):
        nonlocal failed
        if args[:2] == ('git', 'cherry-pick'):
            cherry_picks.append(args)
        at_boundary = (args[:2] == ('git', 'push') if boundary.startswith('push')
                       else args[:2] == ('git', 'merge') and kwargs.get('cwd') == target)
        if at_boundary and not failed:
            failed = True
            if boundary == 'push-error':
                raise ValueError('remote temporarily unavailable')
            original(*args, **kwargs)
            raise KeyboardInterrupt
        return original(*args, **kwargs)

    monkeypatch.setattr(publish, 'command', command)
    with pytest.raises(ValueError if boundary == 'push-error' else KeyboardInterrupt):
        publish.update_main_checkout(root, state, path)
    recorded = json.loads(path.read_text())
    assert recorded['main_update']['phase'] == ('pushed' if boundary == 'merge-interrupt' else 'ready')
    revision = recorded['main_update']['revision']
    publish.update_main_checkout(root, recorded, path)
    assert len(cherry_picks) == 1
    assert recorded['main_update']['phase'] == 'complete'
    assert git(target, 'rev-parse', 'HEAD') == revision
    assert git(target, 'rev-parse', 'origin/main') == revision
    assert git(remote, 'rev-parse', 'main') == revision
    assert git(target, 'status', '--porcelain') == ''
    # Once the handoff is complete, retries preserve new dirty main work.
    (target / 'docs/README.md').write_text('New development.\n')
    monkeypatch.setattr('builtins.input', lambda prompt: pytest.fail('unexpected reconfirmation'))
    assert publish.confirm_main_update(root, state['base'], recorded['main_update'])['phase'] == 'complete'
    publish.update_main_checkout(root, recorded, path)
    assert (target / 'docs/README.md').read_text() == 'New development.\n'


@pytest.mark.parametrize('diverged', [False, True])
def test_main_sync_handles_remote_advance_without_force(main_update_candidate, tmp_path, diverged):
    target, root, remote, state, path = main_update_candidate
    peer = tmp_path / 'peer'
    git(target, 'clone', str(remote), str(peer))
    (peer / 'remote-work').write_text('Already pushed work.\n')
    git(peer, 'add', 'remote-work')
    git(peer, 'commit', '-m', 'remote main advanced')
    git(peer, 'push', 'origin', 'main')
    remote_head = git(peer, 'rev-parse', 'HEAD')
    if diverged:
        git(target, 'commit', '--allow-empty', '-m', 'local main diverged')
        head = git(target, 'rev-parse', 'HEAD')
        with pytest.raises(ValueError):
            publish.update_main_checkout(root, state, path)
        assert git(target, 'rev-parse', 'HEAD') == head
        assert git(remote, 'rev-parse', 'main') == remote_head
    else:
        publish.update_main_checkout(root, state, path)
        head = git(target, 'rev-parse', 'HEAD')
        assert git(remote, 'rev-parse', 'main') == head
        assert git(target, 'rev-parse', 'origin/main') == head
        assert (target / 'remote-work').read_text() == 'Already pushed work.\n'
    assert git(target, 'status', '--porcelain') == ''


@pytest.mark.parametrize('ending', ['success', 'failure', 'interrupt'])
def test_terminal_monitor_replaces_one_line_and_preserves_banner(monkeypatch, ending):
    class Terminal(io.StringIO):
        def isatty(self):
            return True

    output = Terminal()
    monkeypatch.setattr(publish.sys, 'stdout', output)
    monkeypatch.setattr(publish.shutil, 'get_terminal_size', lambda **kwargs: os.terminal_size((60, 24)))
    monkeypatch.setattr(publish.time, 'sleep', lambda seconds: None)
    outcomes = iter([None, URLError('offline'), ending])

    def poll(version, *, progress):
        progress['detail'] = 'waiting for an exact published package ' + 'x' * 120
        result = next(outcomes)
        if isinstance(result, Exception):
            raise result
        if result == 'failure':
            raise ValueError('terminal build failure')
        if result == 'interrupt':
            raise KeyboardInterrupt
        return {'version': version} if result == 'success' else None

    monkeypatch.setattr(publish, 'published_binary', poll)
    publish.highlight('MAIN UPDATED: development can resume.', success=True)
    if ending == 'success':
        publish.wait_for_publication({'version': '1.1'})
    else:
        with pytest.raises(ValueError if ending == 'failure' else KeyboardInterrupt):
            publish.wait_for_publication({'version': '1.1'})
    text = output.getvalue()
    assert text.count('MAIN UPDATED') == 1 and '\033[1;32m' in text
    assert text.count('\n') == (3 if ending == 'success' else 2)
    updates = text.split('\r\033[2K')[1:3]
    for line in updates:
        plain = line.replace('\033[31m', '').replace('\033[0m', '')
        assert len(plain) <= 59
    assert text.count('\r\033[2K') == 3  # Two updates, then cleanup on every exit.
