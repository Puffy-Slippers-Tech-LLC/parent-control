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
from urllib.error import URLError

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


@pytest.mark.parametrize('gate', ['source', 'build', 'binary', 'index'])
def test_success_is_not_claimed_while_any_publication_gate_is_pending(launchpad, monkeypatch, gate):
    version, source, build, binary = launchpad
    if gate == 'source':
        source['status'] = 'Pending'
    elif gate == 'build':
        build['buildstate'] = 'Needs building'
    elif gate == 'binary':
        binary['binary_package_version'] = '1.0'
    else:
        monkeypatch.setattr(publish, 'read_url', lambda url: gzip.compress(b''))
    assert publish.published_binary(version) is None


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


def test_polling_recovers_transient_network_errors_without_upload(tmp_path, monkeypatch):
    outcomes = iter([URLError('offline'), None, {'version': '1.1'}])

    def poll(version):
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
    (['prepare', '/tmp/onpc-release-test'], 2),
    (['check-build', '/tmp/onpc-release-test/source'], 2),
])
def test_launcher_help_and_invalid_arguments_have_no_side_effects(args, exit_code):
    result = subprocess.run([str(ROOT / 'tools/publish.py'), *args],
                            capture_output=True, text=True, timeout=10)
    assert result.returncode == exit_code


@pytest.mark.parametrize('exit_code', [0, 7])
def test_make_publish_invokes_one_no_argument_tool_and_propagates_failure(tmp_path, exit_code):
    # Exercise the real Makefile with a recording publisher, never a live upload.
    checkout = tmp_path / 'checkout with spaces'
    (checkout / 'tools').mkdir(parents=True)
    launcher = checkout / 'tools/publish.py'
    launcher.write_text(
        '#!/usr/bin/python3 -IB\nimport json, sys\nfrom pathlib import Path\n'
        'Path("invocation.json").write_text(json.dumps(sys.argv[1:]))\n'
        f'raise SystemExit({exit_code})\n')
    launcher.chmod(0o755)
    (checkout / 'publish').touch()  # The target must run even when this file exists.
    result = subprocess.run(['make', '--no-print-directory', '-f', str(ROOT / 'Makefile'), 'publish'],
                            cwd=checkout, capture_output=True, text=True, timeout=10)
    assert (result.returncode == 0) == (exit_code == 0), result.stderr
    assert json.loads((checkout / 'invocation.json').read_text()) == []
    if exit_code:
        assert 'Error 7' in result.stderr


def test_default_make_keeps_its_existing_behavior_without_publishing(tmp_path):
    # A plain `make` must never start publication as an accidental default goal.
    result = subprocess.run(['make', '--no-print-directory', '-f', str(ROOT / 'Makefile'), 'VERSION='],
                            cwd=tmp_path, capture_output=True, text=True, timeout=10)
    assert result.returncode != 0
    assert 'Usage: make bump-version' in result.stdout + result.stderr


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
