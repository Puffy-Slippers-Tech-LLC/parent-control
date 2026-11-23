"""Publishing state transitions, release inputs and actual Git fast-forward safety.

All network, signing, upload and clean-build operations are replaced with local
fixtures. Nothing in this suite can publish a real release.
"""
from datetime import date
import gzip
import hashlib
from http.client import IncompleteRead
import json
import os
from pathlib import Path
import subprocess
from types import SimpleNamespace
from urllib.error import HTTPError, URLError

import pytest

from tools import publish, upgrade_history
from tools.publish import update_version
from tools.publishing import channels
from tests.support.paths import ROOT


@pytest.fixture(autouse=True)
def isolated_polling_clock(monkeypatch):
    # Patching the shared time module also changes subprocess.wait's backoff,
    # which can consume a polling fixture's clock or publication transition.
    monkeypatch.setattr(publish, 'time', SimpleNamespace(
        monotonic=publish.time.monotonic, sleep=publish.time.sleep))
    # Local package builds are outside these Git/state-machine fixtures.
    monkeypatch.setattr(publish, 'update_version', lambda root: None)


NOTES = ('## v1.1 — 2026-09-11\n### Bug Fixes\n'
         '- **Parent App:** Fixed small screens.\n\n'
         '## v1.0 — 2026-09-10\n### New Features\n- Initial release.\n')


@pytest.mark.parametrize('text,current,reason', [
    (NOTES, '1.0', 'updateversion'), (NOTES, '0.9', 'equal'),
    (NOTES.replace('v1.0', 'v1.1'), '1.0', 'unique'),
    (NOTES.replace('- **Parent App:** Fixed small screens.', ''), '1.0', 'bullet'),
    (NOTES.replace('Fixed', '\x1b[32mFixed'), '1.0', 'control'),
])
def test_history_errors_fail_closed(text, current, reason):
    with pytest.raises(ValueError, match=reason):
        publish.history_entry(text, current)


def test_publish_prepares_an_unprepared_product_before_external_work(repository, monkeypatch, unsigned_publisher):
    (repository / 'debian').mkdir()
    (repository / 'debian/changelog').write_text(publish.changelog_entry('1.0', 'Initial release.'))
    git(repository, 'add', 'debian/changelog')
    git(repository, 'add', publish.HISTORY)
    git(repository, 'commit', '-m', 'unprepared candidate')
    git(repository, 'switch', '-c', 'releases/v1.1')
    original = publish.command
    builds = []

    def command(*args, **kwargs):
        if args[0] == str(repository / 'tools/build_package.py'):
            assert json.loads((repository / 'data/app.json').read_text())['version'] == '1.1'
            assert '1.1+local1~ubuntu26.04.1' in (repository / 'debian/changelog').read_text()
            builds.append(args)
            return 'local packages built'
        return original(*args, **kwargs)

    monkeypatch.setattr(publish, 'command', command)
    monkeypatch.setattr(publish, 'update_version', update_version)
    def pause(*args):
        raise ValueError('stop before external work')
    monkeypatch.setattr(publish, 'confirm_main_update', pause)
    monkeypatch.setattr(publish, 'prepare', lambda *args: pytest.fail('external work started'))
    with pytest.raises(ValueError, match='stop before external work'):
        publish.publish(repository)
    assert len(builds) == 1 and len(builds[0]) == 1  # Default queued build, both formats.
    assert git(repository, 'status', '--porcelain') == ''
    assert json.loads(git(repository, 'show', 'HEAD:data/app.json'))['version'] == '1.1'
    before = (repository / 'debian/changelog').read_bytes()
    head = git(repository, 'rev-parse', 'HEAD')
    with pytest.raises(ValueError, match='stop before external work'):
        publish.publish(repository)
    assert len(builds) == 2
    assert (repository / 'debian/changelog').read_bytes() == before
    assert git(repository, 'rev-parse', 'HEAD') == head
    assert git(repository, 'status', '--porcelain') == ''


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


@pytest.mark.parametrize('branch', ['feature', 'releases/v01.1', None, 'releases/v1.2'])
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
    with publish.locked(repository, product='1.1'):
        with pytest.raises(ValueError, match='already running'):
            with publish.locked(repository, product='1.2'):
                pytest.fail('second lock acquired')
    with publish.locked(repository, product='1.2') as state_path:
        publish.save(state_path, {'phase': 'upload-started'})
        assert json.loads(state_path.read_text())['phase'] == 'upload-started'


@pytest.fixture
def execution(tmp_path, monkeypatch):
    directory = tmp_path / 'release'
    directory.mkdir()
    (directory / 'source').mkdir()
    state = dict(phase='prepared', version='1.1+ppa1~ubuntu26.04.1', product='1.1',
                 revision='frozen', base='base', source_tag='v1.1+ppa1_ubuntu26.04.1',
                 product_tag='v1.1', branch='releases/v1.1', directory=str(directory),
                 checkout=str(ROOT), main_update={'phase': 'pending', 'checkout': str(ROOT)})
    state_path = tmp_path / 'v1.1' / 'state.json'
    state_path.parent.mkdir()
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
    def update_main(root, current_state, current_path):
        calls.append(('main-update',))
        current_state['main_update']['phase'] = 'complete'
        publish.save(current_path, current_state)

    monkeypatch.setattr(publish, 'confirm_main_update', lambda root, base, update: update)
    monkeypatch.setattr(publish, 'update_main_checkout', update_main)
    monkeypatch.setattr(publish, 'finish_checkout', lambda *args: calls.append(('finish',)))
    return state, state_path, calls


def test_full_workflow_publishes_without_local_tests(execution, tmp_path, monkeypatch):
    state, path, calls = execution
    # The same checkout previously published DEB and has an unfinished RPM
    # attempt for a different release. Neither record belongs to this run.
    journal_root = path.parent.parent
    older_release = journal_root / 'v1.0'
    older_release.mkdir()
    old_journals = {}
    for directory in (journal_root, older_release):
        old_deb = directory / 'state.json'
        old_channels = directory / 'channels.json'
        publish.save(old_deb, {'product': '1.0', 'phase': 'complete'})
        publish.save(old_channels, {'product': '1.0', 'branch': 'releases/v1.0',
                                    'deb': {'phase': 'published'}, 'rpm': {'phase': 'upload-started'}})
        old_journals.update({old: old.read_bytes() for old in (old_deb, old_channels)})
    channels_path = path.with_name('channels.json')
    root = tmp_path / 'checkout'
    state['checkout'] = str(root)
    (root / 'data').mkdir(parents=True)
    (root / 'docs').mkdir()
    # Channel gates select the history product before metadata preparation.
    (root / 'data/app.json').write_text('{"version": "1.0"}')
    (root / publish.HISTORY).write_text(NOTES)
    monkeypatch.setattr(publish, 'journal_directory', lambda root: journal_root)
    original = publish.command

    def command(*args, **kwargs):
        if args[:3] == ('git', 'branch', '--show-current'):
            return state['branch']
        return original(*args, **kwargs)

    def source_history(version=None):
        if any(call[0] == 'dput' for call in calls):
            return [dict(source_package_version=state['version'], distro_series_link=publish.SERIES)]
        return []

    def submit(revision, authorization):
        recorded = json.loads(channels_path.read_text())
        assert recorded['rpm']['phase'] == 'upload-started'
        assert not any(call[0] == 'dput' for call in calls)
        assert ('wait',) not in calls
        assert authorization == 'private test credential'
        calls.append(('copr-submit',))
        return dict(id=123, ownername=channels.copr.OWNER, projectname=channels.copr.PROJECT)

    def authorized_builder():
        calls.append(('copr-preflight',))
        return 'private test credential'

    monkeypatch.setattr(publish, 'command', command)
    monkeypatch.setattr(publish, 'sources', source_history)
    launchpad_failed = True

    def public_check(*args, **kwargs):
        calls.append(('public-check',))
        if launchpad_failed:
            raise ValueError('Launchpad build failed after submission')
        return {'version': state['version']}

    monkeypatch.setattr(publish, 'published_binary', public_check)
    monkeypatch.setattr(publish, 'publish', lambda root, **options: publish.execute(root, state, path, **options))
    monkeypatch.setattr(channels, 'pin_source', lambda *a: state['revision'])
    monkeypatch.setattr(channels.copr, 'authorized_builder', authorized_builder)
    monkeypatch.setattr(channels.copr, 'submit', submit)

    def copr_status(product, record, *, retry_rejected=False):
        if ('copr-submit',) not in calls:
            return 'absent', 'not submitted'
        if not any(call[0] == 'dput' for call in calls):
            assert record['phase'] == 'upload-started'
            return 'uncertain', 'recorded COPR submission is not yet visible'
        return 'published', 'verified'

    monkeypatch.setattr(channels.copr, 'status', copr_status)

    def reject_credentials():
        raise ValueError('invalid COPR token')

    def launchpad_unreachable(version=None):
        raise URLError('Launchpad offline')

    with monkeypatch.context() as patch:
        patch.setattr(channels.copr, 'authorized_builder', reject_credentials)
        with pytest.raises(ValueError, match='blocked both submissions.*invalid COPR token'):
            channels.run(root, publish)
    with monkeypatch.context() as patch:
        patch.setattr(publish, 'sources', launchpad_unreachable)
        with pytest.raises(ValueError, match='blocked both submissions.*status unavailable'):
            channels.run(root, publish)
    assert all(call[:2] == ('git', 'symbolic-ref') for call in calls)

    with monkeypatch.context() as patch:
        external_journal = tmp_path / 'external build journal'
        patch.setattr(publish, 'journal_directory', lambda root: external_journal)
        patch.setattr(publish, 'sources', lambda version=None: [dict(
            source_package_version=state['version'], distro_series_link=publish.SERIES)])
        for _ in range(2):
            with pytest.raises(ValueError, match='blocked both submissions.*Launchpad build failed'):
                channels.run(root, publish)
    assert all(call[:2] == ('git', 'symbolic-ref') or call == ('public-check',) for call in calls)
    calls.clear()

    def reject_archive():
        raise ValueError('PPA is not active')

    with monkeypatch.context() as patch:
        patch.setattr(publish, 'archive_preflight', reject_archive)
        with pytest.raises(ValueError, match='PPA is not active'):
            channels.run(root, publish)
    assert json.loads(path.read_text())['phase'] == 'signed'
    assert not any(call[:2] == ('git', 'push') or call[0] in ('copr-submit', 'dput') for call in calls)

    with monkeypatch.context() as patch:
        patch.setattr(channels, 'pin_source', lambda *a: 'different signed commit')
        with pytest.raises(ValueError, match='same signed source commit'):
            channels.run(root, publish)
    assert json.loads(path.read_text())['phase'] == 'pushed'
    assert not any(call[0] in ('copr-submit', 'dput') for call in calls)

    with monkeypatch.context() as patch:
        outcomes = iter([('absent', 'not submitted'), ('uncertain', 'COPR offline')])
        patch.setattr(channels.copr, 'status', lambda *a, **k: next(outcomes))
        with pytest.raises(ValueError, match='blocked both submissions.*COPR offline'):
            channels.run(root, publish)
    assert not any(call[0] in ('copr-submit', 'dput') for call in calls)

    def interrupt_after_copr_post(revision, authorization):
        submit(revision, authorization)
        raise KeyboardInterrupt

    with monkeypatch.context() as patch:
        patch.setattr(channels.copr, 'submit', interrupt_after_copr_post)
        with pytest.raises(KeyboardInterrupt):
            channels.run(root, publish)
    assert json.loads(path.read_text())['phase'] == 'pushed'
    assert ('copr-submit',) in calls and not any(call[0] == 'dput' for call in calls)

    with pytest.raises(ValueError, match='publication failed for deb'):
        channels.run(root, publish)
    channel_state = json.loads(channels_path.read_text())
    assert channel_state['rpm']['phase'] == 'published'
    assert json.loads(path.read_text())['phase'] == 'upload-started'

    launchpad_failed = False
    channels.run(root, publish)
    assert json.loads(path.read_text())['phase'] == 'complete'
    commands = [call[0] for call in calls]
    assert commands.count('copr-submit') == commands.count('dput') == 1
    assert commands.index('dpkg-buildpackage') < commands.index('debsign')
    assert not {'make', 'lintian', 'sbuild', 'dpkg-checkbuilddeps'} & set(commands)
    assert not any('--check-only' in call for call in calls)
    push = next(i for i, call in enumerate(calls) if call[:2] == ('git', 'push'))
    upload = next(i for i, call in enumerate(calls) if call[0] == 'dput' and '--check-only' not in call)
    assert commands.index('debsign') < push < upload < commands.index('public-check') < commands.index('finish')
    assert commands.index('copr-preflight') < commands.index('dpkg-buildpackage')
    assert upload < commands.index('main-update') < commands.index('public-check')
    assert push < commands.index('copr-submit') < upload < commands.index('public-check')
    assert ('wait',) not in calls  # No second poll through the legacy publisher.
    assert '--atomic' in calls[push]
    assert 'HEAD:refs/heads/releases/v1.1' in calls[push]
    assert not any('HEAD:refs/heads/main' in call for call in calls)
    before = list(calls)
    channels.run(root, publish)
    assert all(call[:2] == ('git', 'symbolic-ref') or call == ('public-check',) for call in calls[len(before):])
    assert {old: old.read_bytes() for old in old_journals} == old_journals
    handoff = journal_root / 'channels-monitor.json'
    assert json.loads(handoff.read_text())['journal'] == str(channels_path.resolve())
    current = {journal: journal.read_bytes() for journal in (path, channels_path, handoff)}
    channels.run(root, publish, status=True)
    assert {journal: journal.read_bytes() for journal in current} == current


@pytest.mark.parametrize('phase', ['upload-started', 'published'])
def test_resume_never_reuploads_or_rebuilds_an_attempted_upload(execution, phase, tmp_path, monkeypatch):
    state, path, calls = execution
    state['phase'] = phase
    root = tmp_path / 'checkout'
    (root / 'data').mkdir(parents=True)
    (root / 'docs').mkdir()
    (root / 'data/app.json').write_text('{"version": "1.1"}')
    (root / publish.HISTORY).write_text(NOTES)
    main_phase = 'complete' if phase == 'upload-started' else 'pending'
    state.update(checkout=str(root), main_update={'phase': main_phase, 'checkout': str(root)})
    publish.save(path, state)
    monkeypatch.setattr(publish, 'journal_directory', lambda root: path.parent.parent)
    original = publish.command
    monkeypatch.setattr(publish, 'command', lambda *args, **kwargs:
                        state['branch'] if args[:3] == ('git', 'branch', '--show-current')
                        else original(*args, **kwargs))
    monkeypatch.setattr(publish, 'sources', lambda version=None: [dict(
        source_package_version=state['version'], distro_series_link=publish.SERIES)])
    checks = []

    def check(version, *, progress):
        checks.append(version)
        if phase == 'upload-started' and len(checks) == 1:
            progress['detail'] = 'queued'
            return None
        return {'version': version}

    monkeypatch.setattr(publish, 'published_binary', check)
    rpm_result = ('failed', 'COPR build 10 failed') if phase == 'published' else ('published', 'verified')
    monkeypatch.setattr(channels.copr, 'status', lambda *a, **k: rpm_result)
    monkeypatch.setattr(channels.copr, 'authorized_builder', lambda: pytest.fail('checked credentials for an existing release'))
    monkeypatch.setattr(channels.copr, 'submit', lambda *a: pytest.fail('repeated COPR submission'))
    monkeypatch.setattr(publish, 'publish', lambda *a, **k: pytest.fail('re-entered full publisher'))
    monkeypatch.setattr(publish, 'verify_frozen', lambda *a: pytest.fail('required old upload archives'))
    if main_phase == 'complete':
        monkeypatch.setattr(publish, 'confirm_main_update', lambda *a: pytest.fail('repeated completed main pause'))
        channels_path = path.with_name('channels.json')
        deb_record = dict(phase='upload-started', version=state['version'])
        revision = 'a' * 40
        publish.save(channels_path, dict(product=state['product'], branch=state['branch'], deb=deb_record,
                                        rpm=dict(phase='rejected', revision=revision, http_status=400)))
        before = path.read_bytes()
        submissions = []

        def retry_status(product, record, *, retry_rejected):
            if submissions:
                assert record['build_id'] == 10
                return 'published', 'verified'
            assert retry_rejected
            return 'absent', 'not submitted'

        def retry_submit(commit, authorization):
            assert commit == revision and authorization == 'private test credential'
            recorded = publish.load_journal(channels_path)['rpm']
            assert recorded['phase'] == 'upload-started' and recorded['revision'] == commit
            submissions.append(commit)
            return dict(id=10, ownername=channels.copr.OWNER, projectname=channels.copr.PROJECT)

        with monkeypatch.context() as patch:
            patch.setattr(channels, 'deb_status', lambda *a: pytest.fail('COPR retry checked Launchpad'))
            patch.setattr(publish, 'resume_delivery', lambda *a: pytest.fail('COPR retry touched DEB delivery'))
            patch.setattr(channels, 'pin_source', lambda *a: revision)
            patch.setattr(channels.copr, 'status', retry_status)
            patch.setattr(channels.copr, 'authorized_builder', lambda: 'private test credential')
            patch.setattr(channels.copr, 'submit', retry_submit)
            channels.run(root, publish, retry_rejected=True)
        assert submissions == [revision]
        assert publish.load_journal(channels_path)['deb'] == deb_record
        assert path.read_bytes() == before
    if phase == 'published':
        with pytest.raises(ValueError, match='publication failed for rpm'):
            channels.run(root, publish)
    else:
        channels.run(root, publish)
    assert not any(call[0] in ('dput', 'dpkg-buildpackage', 'debsign', 'lintian') for call in calls)
    assert ('wait',) not in calls
    assert json.loads(path.read_text())['phase'] == 'complete'
    assert calls.count(('main-update',)) == (0 if main_phase == 'complete' else 1)


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


@pytest.fixture
def copr_service(monkeypatch):
    copr = channels.copr
    base = 'https://download.copr.fedorainfracloud.org/results/test/project/'
    build = dict(id=10, ownername=copr.OWNER, projectname=copr.PROJECT, state='succeeded',
                 chroots=list(copr.chroots()), source_package={'name': publish.release.PACKAGE, 'version': '1.1-1'})
    listing = [build]
    payload = b'published RPM fixture'
    responses = {}
    repositories = {chroot: base + chroot + '/' for chroot in copr.chroots()}
    configuration = dict(ownername=copr.OWNER, name=copr.PROJECT, chroot_repos=repositories)
    packages = {10: {}}

    def index_repositories(storage):
        configuration['storage'] = storage
        responses.clear()
        for chroot, target in copr.chroots().items():
            release = '1' + target.dist
            name = publish.release.PACKAGE
            filename = f'{name}-1.1-{release}.{target.architecture}.rpm'
            directory = f'Packages/{name[0]}' if storage == 'pulp' else f'00000010-{name}'
            href = f'{directory}/{filename}'
            primary = (f'<metadata xmlns="http://linux.duke.edu/metadata/common"><package>'
                       f'<name>{name}</name><arch>{target.architecture}</arch>'
                       f'<version epoch="0" ver="1.1" rel="{release}"/><location href="{href}"/>'
                       f'<checksum type="sha256">{hashlib.sha256(payload).hexdigest()}</checksum>'
                       f'<size package="{len(payload)}"/></package></metadata>').encode()
            packed = gzip.compress(primary)
            repomd = (f'<repomd xmlns="http://linux.duke.edu/metadata/repo"><data type="primary">'
                      f'<location href="repodata/primary.xml.gz"/><checksum type="sha256">'
                      f'{hashlib.sha256(packed).hexdigest()}</checksum></data></repomd>').encode()
            repository = repositories[chroot]
            responses.update({repository + 'repodata/repomd.xml': repomd,
                              repository + 'repodata/primary.xml.gz': packed,
                              repository + href: payload})
            packages[10][chroot] = {'packages': [dict(name=name, epoch=None, version='1.1', release=release,
                                                    arch=target.architecture)]}

    index_repositories('pulp')

    def api(endpoint, **params):
        if endpoint == '/project':
            return configuration
        if endpoint.startswith('/build/built-packages/'):
            return packages.get(int(endpoint.rsplit('/', 1)[-1]), {})
        if endpoint.startswith('/build/source-build-config/'):
            return {'source_type': 'scm', 'source_dict': dict(
                type='git', clone_url=copr.GIT_URL, committish='a' * 40, subdirectory='',
                spec=None, srpm_build_method='make_srpm')}
        pytest.fail('unexpected COPR API operation: ' + endpoint)

    monkeypatch.setattr(copr, 'api', api)
    monkeypatch.setattr(copr, 'builds', lambda: listing)
    monkeypatch.setattr(copr, 'read', lambda url, **kwargs: responses[url])
    return SimpleNamespace(build=build, listing=listing, responses=responses, packages=packages,
                           index_repositories=index_repositories)


def test_success_requires_exact_downloadable_indexed_package(launchpad, copr_service, monkeypatch):
    version, old_source, _, _ = launchpad
    result = publish.published_binary(version)
    assert result['version'] == version and result['sha256']
    build, listing = copr_service.build, copr_service.listing
    record = {'build_id': build['id']}
    listing.append(dict(build, id=11, state='failed'))
    assert channels.copr.status('1.1', record)[0] == 'published'
    assert record['build_id'] == 10
    fedora45 = 'fedora-45-x86_64'
    rpm = copr_service.packages[10][fedora45]['packages'][0]
    rpm['release'] = '2.fc45'
    assert channels.copr.status('1.1', record)[0] == 'pending'
    rpm['release'] = '1.fc45'
    copr_service.packages[11] = {fedora45: copr_service.packages[10][fedora45]}
    with pytest.raises(ValueError, match='cannot distinguish builds with the same RPM identity'):
        channels.copr.status('1.1', record)
    del copr_service.packages[11]
    build['state'] = 'running'
    assert channels.copr.status('1.1', record)[0] == 'pending'
    assert record['build_id'] == 10  # A later failed rebuild cannot retarget this attempt.
    newer = version.replace('+ppa1', '+ppa2')
    monkeypatch.setattr(publish, 'sources', lambda version=None: [old_source, dict(
        old_source, source_package_version=newer)])
    original = publish.published_binary

    def check(candidate, *, progress):
        if candidate == newer:
            raise ValueError('newer build failed')
        return original(candidate, progress=progress)

    monkeypatch.setattr(publish, 'published_binary', check)
    deb_record = {'phase': 'upload-started', 'version': version}
    assert channels.deb_status('1.1', deb_record, publish)[0] == 'published'
    assert deb_record['published_version'] == version
    # Without a verified publication, continue following the exact submitted
    # revision even when a later same-product source exists and failed.
    def pending(candidate, *, progress):
        if candidate == newer:
            raise ValueError('newer build failed')
        progress['detail'] = 'queued'
        return None

    monkeypatch.setattr(publish, 'published_binary', pending)
    assert channels.deb_status('1.1', deb_record, publish) == ('pending', 'queued')
    assert deb_record['version'] == version


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


def test_terminal_launchpad_failure_and_binary_tampering_are_errors(launchpad, monkeypatch, copr_service):
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
    copr_build, listing, responses = copr_service.build, copr_service.listing, copr_service.responses
    # Recover a lost POST response even when source generation failed before
    # COPR learned the package's name/version. Never submit it again.
    copr_build.update(state='failed', source_package={})
    record = {'phase': 'upload-started', 'revision': 'a' * 40}
    with pytest.raises(ValueError, match='build 10 failed'):
        channels.copr.status('1.1', record)
    assert record['build_id'] == 10
    listing.clear()
    with pytest.raises(ValueError, match='HTTP 403'):
        channels.copr.status('1.1', {'phase': 'rejected', 'revision': 'a' * 40, 'http_status': 403})
    rejection = {'phase': 'rejected', 'revision': 'a' * 40, 'http_status': 400}
    assert channels.copr.status('1.1', dict(rejection, build_id=10))[0] == 'uncertain'
    assert channels.copr.status('1.1', rejection.copy(), retry_rejected=True)[0] == 'absent'
    listing.append(copr_build)
    with pytest.raises(ValueError, match='build 10 failed'):
        channels.copr.status('1.1', rejection.copy(), retry_rejected=True)
    other_revision = dict(rejection, revision='b' * 40)
    copr_build['source_package'] = {'name': publish.release.PACKAGE, 'version': '1.1-1'}
    outcome, detail = channels.copr.status('1.1', other_revision, retry_rejected=True)
    assert outcome == 'uncertain' and 'different source' in detail
    assert 'build_id' not in other_revision
    copr_build['state'] = 'succeeded'
    copr_service.index_repositories('legacy')
    assert channels.copr.status('1.1', {'build_id': 10})[0] == 'published'
    rpm_url = next(url for url in responses if url.endswith('.rpm'))
    responses[rpm_url] = b'corrupt RPM'
    with pytest.raises(ValueError, match='RPM checksum mismatch'):
        channels.copr.status('1.1', {'build_id': 10})

    record = {}
    journal = []
    monkeypatch.setattr(channels, 'pin_source', lambda *args: 'a' * 40)
    monkeypatch.setattr(channels, 'check', lambda *args, **kwargs: ('absent', 'not submitted'))
    monkeypatch.setattr(channels.copr, 'submit', lambda *args: [])
    channels.submit_rpm(ROOT, ROOT, '1.1', record, 'test credential', publish,
                        lambda: journal.append(record.copy()))
    assert journal == [dict(phase='upload-started', revision='a' * 40)]
    assert record == journal[0]


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


def test_public_reads_require_cache_revalidation(monkeypatch):
    truncated = False

    class Response:
        def __enter__(self):
            return self

        def __exit__(self, *args):
            pass

        def read(self):
            if truncated:
                raise IncompleteRead(b'private response bytes', 10)
            return b'current publication status'

    def open_request(request, *, timeout):
        assert request.full_url == publish.API
        assert request.get_method() == 'GET'
        assert request.get_header('Cache-control') == 'no-cache'
        assert timeout == 30
        return Response()

    monkeypatch.setattr(publish, 'urlopen', open_request)
    assert publish.read_url(publish.API) == b'current publication status'

    copr = channels.copr
    repository = 'https://download.copr.fedorainfracloud.org/results/test/project/repodata/repomd.xml'
    pulp = 'https://packages.redhat.com/api/pulp-content/public-copr/test/project/repodata/repomd.xml'
    blob = 'https://copr-pulp-prod.s3.amazonaws.com/artifact/digest'
    permission_url = copr.API + f'/project/permissions/can_build_in/test-user/{copr.OWNER}/{copr.PROJECT}'
    permission = dict(who='test-user', ownername=copr.OWNER, projectname=copr.PROJECT, can_build_in=True)
    auth_status = 200

    def json_response(value):
        response = Response()
        response.read = lambda: json.dumps(value).encode()
        return response

    def get_opener(redirect):
        def open_copr(request, *, timeout):
            assert request.get_header('Cache-control') == 'no-cache'
            assert timeout == 30
            if request.full_url == repository:
                forwarded = redirect.redirect_request(request, None, 301, '', {}, pulp)
                final = redirect.redirect_request(forwarded, None, 302, '', {}, blob)
                assert final.full_url == blob
                assert final.get_method() == 'GET' and not final.has_header('Authorization')
                for unexpected in (pulp.replace('https:', 'http:'), pulp.replace('public-copr', 'private'),
                                   'https://copr-pulp-prod.s3.amazonaws.com.unrelated.invalid/artifact/digest'):
                    assert redirect.redirect_request(request, None, 302, '', {}, unexpected) is None
            elif request.full_url == copr.API + '/auth-check':
                assert request.get_method() == 'GET' and request.has_header('Authorization')
                assert redirect.redirect_request(request, None, 302, '', {}, pulp) is None
                if auth_status != 200:
                    raise HTTPError(request.full_url, auth_status, 'private details', {}, None)
                return json_response({'name': 'test-user'})
            elif request.full_url == permission_url:
                assert request.get_method() == 'GET' and not request.has_header('Authorization')
                return json_response(permission)
            else:
                assert request.full_url == copr.API + '/build/create/scm'
                assert request.get_method() == 'POST' and request.has_header('Authorization')
                assert redirect.redirect_request(request, None, 302, '', {}, pulp) is None
                if request.data != b'{}':
                    assert json.loads(request.data) == dict(
                        ownername=copr.OWNER, projectname=copr.PROJECT, clone_url=copr.GIT_URL,
                        committish='a' * 40, subdirectory='', scm_type='git', source_build_method='make_srpm',
                        chroots=['fedora-44-x86_64', 'fedora-45-x86_64'], enable_net=False)
                    return json_response({'id': 10})
            return Response()

        return SimpleNamespace(open=open_copr)

    monkeypatch.setattr(copr, 'build_opener', get_opener)
    assert copr.read(repository) == b'current publication status'
    assert copr.read(copr.API + '/build/create/scm', data=b'{}',
                     authorization='private test credential') == b'current publication status'
    assert copr.submit('a' * 40, 'private test credential') == {'id': 10}
    with pytest.raises(ValueError, match='unexpected authenticated COPR endpoint'):
        copr.read(permission_url, authorization='private test credential')
    monkeypatch.setattr(copr, 'credentials', lambda: 'private test credential')
    assert copr.authorized_builder() == 'private test credential'
    permission['can_build_in'] = False
    with pytest.raises(ValueError, match='cannot build in'):
        copr.authorized_builder()
    auth_status = 401
    with pytest.raises(ValueError, match='rejected the account preflight') as error:
        copr.authorized_builder()
    assert 'private details' not in str(error.value)

    truncated = True
    with pytest.raises(URLError, match='IncompleteRead') as error:
        publish.read_url(publish.API)
    assert 'private response bytes' not in str(error.value)
    with pytest.raises(URLError, match='IncompleteRead'):
        copr.read(repository)
    with pytest.raises(URLError, match='IncompleteRead'):
        copr.read(copr.API + '/build/create/scm', data=b'{}', authorization='private test credential')


def test_main_colors_errors_and_success_and_restores_environment(monkeypatch, capsys):
    monkeypatch.setenv('APT_PACKAGE_PRIVATE_KEY_PASSPHRASE', 'secret')

    def fail(*args, **kwargs):
        assert 'APT_PACKAGE_PRIVATE_KEY_PASSPHRASE' not in os.environ
        raise ValueError('release failed')

    monkeypatch.setattr(channels, 'run', fail)
    assert publish.main([]) == 1
    assert '\033[31m' in capsys.readouterr().err
    assert os.environ['APT_PACKAGE_PRIVATE_KEY_PASSPHRASE'] == 'secret'
    publish.say('published', success=True)
    assert '\033[32m' in capsys.readouterr().out

    monkeypatch.setattr(channels, 'run', lambda *args, **kwargs: pytest.fail('preflight dispatched publication'))
    checks = []
    monkeypatch.setattr(channels.copr, 'project', lambda: checks.append('project'))
    monkeypatch.setattr(channels.copr, 'authorized_builder', lambda: checks.append('builder'))
    assert publish.main(['--preflight-rpm']) == 0
    assert checks == ['project', 'builder']
    assert 'fedora-44-x86_64, fedora-45-x86_64' in capsys.readouterr().out


@pytest.mark.parametrize('args,exit_code', [
    (['--help'], 0), (['--force'], 2), (['--status', 'extra'], 2),
    (['prepare', '/tmp/onpc-release-test'], 2),
    (['check-build', '/tmp/onpc-release-test/source'], 2),
])
def test_launcher_help_and_invalid_arguments_have_no_side_effects(args, exit_code):
    result = subprocess.run([str(ROOT / 'tools/publish.py'), *args],
                            capture_output=True, text=True, timeout=10)
    assert result.returncode == exit_code


@pytest.mark.parametrize('phase', ['upload-started', 'published', 'complete'])
@pytest.mark.parametrize('changed_head', [False, True])
def test_status_monitors_recorded_release_with_changed_checkout_without_writes(
        repository, launchpad, monkeypatch, capsys, phase, changed_head):
    version, _, _, _ = launchpad
    original_head = git(repository, 'rev-parse', 'HEAD')
    state = dict(phase=phase, version=version, base=original_head, revision='release-commit',
                 checkout=str(repository), branch='releases/v1.1', directory='/missing-release-artifacts')
    # A reader also works while the publisher owns its lock.
    with publish.locked(repository, product='1.1') as path:
        publish.save(path, state)
        journal_before = path.read_bytes()
        if changed_head:
            git(repository, 'commit', '--allow-empty', '-m', 'monitoring fix')
        git(repository, 'switch', '-c', 'releases/v1.1')
        (repository / 'docs/README.md').write_text('Uncommitted local work.\n')
        (repository / publish.HISTORY).write_text('Unfinished new release notes.\n')
        head = git(repository, 'rev-parse', 'HEAD')
        status = git(repository, 'status', '--porcelain')

        def forbidden(*args, **kwargs):
            pytest.fail('status mode attempted a publishing or writing operation')

        for name in ('save', 'source_state', 'verify_frozen', 'execute', 'finish_checkout'):
            monkeypatch.setattr(publish, name, forbidden)
        original_command = publish.command

        def read_only_command(*args, **kwargs):
            assert args in (('git', 'rev-parse', '--absolute-git-dir'),
                            ('git', 'branch', '--show-current'),
                            ('git', 'symbolic-ref', '--short', 'HEAD'))
            return original_command(*args, **kwargs)

        monkeypatch.setattr(publish, 'command', read_only_command)
        publish.publish(repository)
        assert path.read_bytes() == journal_before
        assert git(repository, 'rev-parse', 'HEAD') == head
        assert git(repository, 'status', '--porcelain') == status
        assert (repository / 'docs/README.md').read_text() == 'Uncommitted local work.\n'
        assert (repository / publish.HISTORY).read_text() == 'Unfinished new release notes.\n'
    assert f'\033[32mpublish: published {version} for resolute/amd64' in capsys.readouterr().out


@pytest.mark.parametrize('state,reason', [
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


@pytest.mark.parametrize('interrupted', [False, True])
def test_status_cli_never_dispatches_publisher(monkeypatch, capsys, interrupted):
    calls = []

    def monitor(*args):
        calls.append('status')
        if interrupted:
            raise KeyboardInterrupt

    monkeypatch.setattr(channels, 'monitor_status', monitor)
    monkeypatch.setattr(publish, 'publish', lambda: pytest.fail('publisher called'))
    assert publish.main(['--status']) == (130 if interrupted else 0)
    assert calls == ['status']
    output = capsys.readouterr()
    assert output.out == ''
    if interrupted:
        assert 'rerun the same command' in output.err


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
                 branch='releases/v1.1', product='1.1')
    with publish.locked(repository, product='1.1') as path:
        publish.save(path, state)
    prepared = []

    def prepare(*args):
        prepared.append(True)
        raise ValueError('reached fresh preparation')

    monkeypatch.setattr(publish, 'prepare', prepare)
    monkeypatch.setattr(publish, 'confirm_main_update', lambda *args: {
        'checkout': str(repository), 'phase': 'pending'})
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
    with publish.locked(root, product='1.1') as path:
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
    with pytest.raises(KeyboardInterrupt) as interrupted:
        publish.publish(root)
    # Keep unexpected interruptions visible instead of losing their origin
    # when pytest.raises consumes them. Record frames only, without locals.
    assert len(uploads) == 1, {
        'pushes': len(pushes),
        'interruption_frames': [(frame.name, frame.lineno + 1)
                                for frame in interrupted.traceback][-12:],
    }
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
@pytest.mark.parametrize('change', ['branch', 'checkout', 'missing branch'])
def test_resume_refuses_changed_owner_before_execution(repository, monkeypatch, change):
    base = git(repository, 'rev-parse', 'HEAD')
    state = dict(phase='upload-started', checkout=str(repository), branch='releases/v1.1', product='1.1',
                 base=base, revision='frozen', history_sha256=hashlib.sha256(NOTES.encode()).hexdigest())
    if change == 'branch':
        state['branch'] = 'releases/v1.2'
    elif change == 'checkout':
        state['checkout'] += '-another-clone'
    else:
        del state['branch']
    with publish.locked(repository, product='1.1') as path:
        publish.save(path, state)
    before = path.read_bytes()
    monkeypatch.setattr(publish, 'execute', lambda *args: pytest.fail('execution started'))
    with pytest.raises(ValueError, match='branch|checkout'):
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
    state = dict(phase='upload-started', version='1.1+ppa1~ubuntu26.04.1',
                 base=base, revision=revision, directory=str(directory),
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
        main_update_candidate, tmp_path, monkeypatch, capsys, enlistment, main_advanced):
    from tools import agent_adapter, launcher_git, launcher_worktrees

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
    (root / 'config').mkdir()
    (root / 'config/environment.json').write_text(json.dumps(dict(families=[{}], branches=[
        dict(name='main', host='local', repo_root=str(target)),
        dict(name='worktree', host='local', repo_root=str(root)),
    ])))
    git(target, 'push', 'origin', 'HEAD:refs/heads/worktree', 'HEAD:refs/heads/releases/v1.1')
    git(target, 'fetch', 'origin')
    git(target, 'branch', '--set-upstream-to=origin/main', 'main')
    git(target, 'branch', '--track', 'worktree', 'origin/releases/v1.1')
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
    today = date(2026, 9, 12)

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
        package_version = '1.1+ppa1~ubuntu26.04.1'
        (frozen / 'debian/changelog').write_text(publish.changelog_entry(package_version, notes))
        git(frozen, 'add', 'debian/changelog')
        git(frozen, 'commit', '-m', 'official release metadata')
        git(frozen, 'tag', '-a', 'v1.1', '-m', 'fixture release tag')
        git(frozen, 'push', str(remote), 'HEAD:refs/heads/releases/v1.1', 'refs/tags/v1.1')
        history_path = frozen / publish.HISTORY
        history_path.write_text('## v1.2\n\n' + history)
        assert upgrade_history.upgrade_matrix(frozen, 'deb', today=today) == ('1.1', ['1.0'])
        history_path.write_text('## v1.2 — 2026-09-12\n\n' + history)
        with pytest.raises(ValueError):
            upgrade_history.release_history(frozen)
        history_path.write_text(history)
        prepared.append(base)
        return dict(phase='upload-started', base=base, revision=git(frozen, 'rev-parse', 'HEAD'),
                    checkout=str(root), branch='releases/v1.1', directory=str(directory),
                    product=product, version=package_version,
                    history_sha256=hashlib.sha256(history.encode()).hexdigest())

    build_and_propagate = []
    original = publish.command

    def command(*args, **kwargs):
        if Path(args[0]).name == 'build_package.py':
            candidate = kwargs['cwd']
            assert candidate == target
            assert json.loads((candidate / 'data/app.json').read_text())['version'] == '1.2'
            assert (candidate / publish.HISTORY).read_text() == '## v1.2\n\n' + NOTES
            assert '  * Start development builds for version 1.2.' in (candidate / 'debian/changelog').read_text()
            assert upgrade_history.upgrade_matrix(candidate, 'deb', today=today) == ('1.2', ['1.0', '1.1'])
            build_and_propagate.append('build')
            return 'fixture packages built'
        return original(*args, **kwargs)

    def propagate(checkout, run, checkpoint, paths, message, *, published_main):
        assert 'You can resume main development.' not in capsys.readouterr().out
        assert checkout == target and paths == [] and message == 'Start v1.2 development'
        assert launcher_worktrees.commit_skill_targets(target, publishing=True) == [
            dict(branch='main', remote='origin', ref='refs/heads/main'),
            dict(branch='worktree', remote='origin', ref='refs/heads/worktree'),
        ]
        git(checkout, 'merge-base', '--is-ancestor', published_main, 'HEAD')
        assert git(checkout, 'rev-parse', 'v1.1^{}') == git(run.parent / 'source', 'rev-parse', 'HEAD')
        if main_advanced and 'propagate-error' not in build_and_propagate:
            peer = tmp_path / 'peer'
            git(target, 'clone', str(remote), str(peer))
            git(peer, 'commit', '--allow-empty', '-m', 'Concurrent remote main commit')
            git(peer, 'push', 'origin', 'main')
            git(target, 'fetch', 'origin')
            git(target, 'merge', '--ff-only', 'origin/main')
            build_and_propagate.append('propagate-error')
            raise ValueError('development propagation temporarily unavailable')
        git(target, 'push', 'origin', published_main + ':refs/heads/worktree')
        build_and_propagate.append('propagate')
        return published_main

    monkeypatch.setattr(publish, 'command', command)
    monkeypatch.setattr(agent_adapter, 'resolve_selection', lambda root: SimpleNamespace(
        adapter=lambda: SimpleNamespace(readiness=lambda root, environment: None)))
    monkeypatch.setattr(launcher_git, 'commit_push_propagate', propagate)
    monkeypatch.setattr(publish, 'prepare', prepare)
    # Exercise the actual main update and handoff with only local Git.
    monkeypatch.setattr(publish, 'execute', lambda *args: publish.resume_delivery(*args, confirmed=True))
    if main_advanced:
        with pytest.raises(ValueError, match='development propagation temporarily unavailable'):
            publish.publish(root)
        assert 'You can resume main development.' not in capsys.readouterr().out
        git(target, 'remote', 'set-url', '--push', 'origin', str(tmp_path / 'wrong-destination'))
        with pytest.raises(ValueError, match='origin fetch and push URLs'):
            publish.publish(root)
        assert 'You can resume main development.' not in capsys.readouterr().out
        git(target, 'config', '--unset', 'remote.origin.pushurl')
    publish.publish(root)
    assert len(prepared) == 1
    assert build_and_propagate == (['build', 'propagate-error', 'propagate'] if main_advanced
                                   else ['build', 'propagate'])
    assert ('\033[1;32mpublish: MAIN UPDATED: v1.2 development version built and propagated.'
            in capsys.readouterr().out)
    assert (root / publish.HISTORY).read_text() == NOTES
    assert (target / publish.HISTORY).read_text() == '## v1.2\n\n' + NOTES
    assert git(remote, 'rev-parse', 'releases/v1.1') == git(target, 'rev-parse', 'v1.1^{}')
    assert git(remote, 'rev-parse', 'worktree') == git(target, 'rev-parse', 'HEAD' + ('^' if main_advanced else ''))
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
    assert not (publish.journal_directory(root) / 'v1.1' / 'state.json').exists()


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
    monitor = json.loads((publish.journal_directory(target) / 'monitor.json').read_text())
    assert monitor['journal'] == str(path.resolve())
    assert monitor['version'] == state['version']
    if changed_files:
        assert (target / 'docs/README.md').read_text() == 'Committed release inputs.\n'


@pytest.mark.parametrize('phase,release_journal', [
    ('upload-started', 'present'), ('upload-started', 'removed'),
    ('upload-started', 'reused'), ('published', 'reused'), ('complete', 'reused'),
])
def test_main_monitor_prefers_handoff_and_preserves_journals(
        main_update_candidate, monkeypatch, phase, release_journal):
    target, root, _, state, path = main_update_candidate
    with publish.locked(target) as old_path:
        publish.save(old_path, {'phase': 'complete', 'version': '1.0+ppa1~ubuntu26.04.1'})
    old_bytes = old_path.read_bytes()
    publish.update_main_checkout(root, state, path)
    state['phase'] = phase
    publish.save(path, state)
    if release_journal == 'removed':
        path.unlink()
    elif release_journal == 'reused':
        publish.save(path, {'phase': 'prepared', 'version': '1.2+ppa1~ubuntu26.04.1'})
    before = path.read_bytes() if path.exists() else None
    monitor_path = old_path.with_name('monitor.json')
    monitor_bytes = monitor_path.read_bytes()
    seen = []
    monkeypatch.setattr(publish, 'wait_for_publication', lambda value: seen.append(value['version']))
    monkeypatch.setattr(publish, 'sources', lambda *args: pytest.fail('selected latest PPA instead of handoff'))
    publish.publication_status(target)
    assert seen == [state['version']]
    assert old_path.read_bytes() == old_bytes
    assert monitor_path.read_bytes() == monitor_bytes
    assert (path.read_bytes() if path.exists() else None) == before


def test_main_monitor_handoff_retry_preserves_newer_release(main_update_candidate):
    target, root, _, state, path = main_update_candidate
    publish.update_main_checkout(root, state, path)
    monitor_path = publish.journal_directory(target) / 'monitor.json'
    monitor_path.unlink()
    # Completed-update retries repair an interrupted or missing handoff.
    publish.update_main_checkout(root, state, path)
    first = monitor_path.read_bytes()
    newer = dict(state, version='1.2+ppa1~ubuntu26.04.1')
    publish.reconcile_main_monitor(newer, path)
    latest = monitor_path.read_bytes()
    assert latest != first
    publish.update_main_checkout(root, state, path)
    assert monitor_path.read_bytes() == latest


def test_main_monitor_handoff_failure_prevents_completion(main_update_candidate, monkeypatch):
    target, root, _, state, path = main_update_candidate
    original = publish.save

    def save(destination, value):
        if destination.name == 'monitor.json':
            raise OSError('handoff write failed')
        return original(destination, value)

    monkeypatch.setattr(publish, 'save', save)
    with pytest.raises(OSError, match='handoff write failed'):
        publish.update_main_checkout(root, state, path)
    assert json.loads(path.read_text())['main_update']['phase'] == 'pushed'
    assert state['main_update']['phase'] == 'pushed'
    monkeypatch.setattr(publish, 'save', original)
    publish.update_main_checkout(root, state, path)
    assert state['main_update']['phase'] == 'complete'
    assert (publish.journal_directory(target) / 'monitor.json').exists()


def test_main_publish_monitors_without_authorizing_publication(main_update_candidate, monkeypatch):
    target, root, _, state, path = main_update_candidate
    publish.update_main_checkout(root, state, path)
    monitor_path = publish.journal_directory(target) / 'monitor.json'
    before = monitor_path.read_bytes()
    checked = []
    monkeypatch.setattr(publish, 'wait_for_publication', lambda state: checked.append(state['version']))
    publish.publish(target)
    assert checked == [state['version']]
    assert monitor_path.read_bytes() == before
    assert not monitor_path.with_name('state.json').exists()


@pytest.mark.parametrize('record', [None, [],
    {'version': '1.1+ppa1~ubuntu26.04.1', 'phase': 'prepared', 'journal': '/missing'},
    {'version': '1.1+ppa1~ubuntu26.04.1', 'phase': 'upload-started', 'journal': 'relative'},
])
def test_main_monitor_rejects_invalid_reference_before_network(tmp_path, monkeypatch, record):
    (tmp_path / 'monitor.json').write_text(json.dumps(record))
    monkeypatch.setattr(publish, 'journal_directory', lambda root: tmp_path)
    monkeypatch.setattr(publish, 'sources', lambda *args: pytest.fail('network before validation'))
    with pytest.raises(ValueError, match='invalid main publication monitoring record'):
        publish.publication_status(tmp_path)


def test_main_monitor_reads_current_release_phase(main_update_candidate, monkeypatch):
    target, root, _, state, path = main_update_candidate
    publish.update_main_checkout(root, state, path)
    state['phase'] = 'prepared'
    publish.save(path, state)
    monkeypatch.setattr(publish, 'wait_for_publication', lambda *args: pytest.fail('ignored current phase'))
    with pytest.raises(ValueError, match='has not reached the upload step'):
        publish.publication_status(target)


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
