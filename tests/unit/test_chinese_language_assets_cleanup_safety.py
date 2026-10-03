"""Private files and in-memory guest/SSH doubles; no VM, desktop or shared state.

Compatible in unit and cleanup inventories; no additional resource admission.
"""
import copy
import hashlib
import json
import os
import subprocess
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

import chinese_language_assets as assets
import chinese_language_qualification as qualification
import native_fixtures
import native_fixtures_guest as guest_helper
from parent_setup_qualification import ChineseLanguageQualification, ProductFreeEntryQualification
from private_artifacts import EvidenceError
from tests.support.chinese_assets import guest, catalogue


def test_profile_independently_reads_locale_native_messages_and_glyphs_without_writes():
    g, files, metadata = guest()
    before = copy.deepcopy((files, metadata))
    assets.preflight(g)
    first = assets.verify(g)
    assert assets.verify(g) == first
    assert first['cjk_glyphs'] == len(set(assets.GLYPHS))
    assert first['translations'] == {'mate-polkit': 4, 'Linux-PAM': 2}
    assert first['locale'] == 'zh_CN.UTF-8' and first['provider'] == 'mate-polkit'
    assert (files, metadata) == before
    assert {call[0] for call in g.method_calls} <= {
        'exists', 'is_symlink', 'lstatns', 'realpath', 'filesize', 'read_file', 'command'}
    assert all(call.args[0] == assets.LOCALE_COMMAND for call in g.command.call_args_list)


@pytest.mark.parametrize('fault', ['missing-locale', 'locale', 'missing-catalogue',
    'fallback', 'ambiguous', 'font', 'missing-font', 'owner', 'symlink', 'hardlink',
    'parent-mode', 'package', 'unowned', 'replacement', 'stale-bytes', 'duplicate-manifest'])
def test_refusals_preserve_assets_and_never_prepare(fault):
    g, files, metadata = guest()
    target = assets.LOCALE_PATH
    native = '/usr/share/locale/zh_CN/LC_MESSAGES/mate-polkit.mo'
    if fault == 'missing-locale': files.pop(target)
    if fault == 'locale': files[target] = b'English\0UTF-8\0'
    if fault == 'missing-catalogue': files.pop(native)
    if fault == 'fallback': files[native] = catalogue({'_Cancel': '中文'})
    if fault == 'ambiguous': files[native.replace('/locale/', '/locale-langpack/')] = files[native]
    if fault == 'font': files[assets.FONT_PATH] = b'invalid'
    if fault == 'missing-font': files.pop(assets.FONT_PATH)
    if fault == 'owner': metadata[target]['st_uid'] = 1000
    if fault == 'symlink': g.realpath.side_effect = lambda path: '/foreign' if path == target else path
    if fault == 'hardlink': metadata[target]['st_nlink'] = 2
    if fault == 'parent-mode': metadata['/usr/lib/locale']['st_mode'] |= 0o002
    if fault == 'package': files['/var/lib/dpkg/status'] = b''
    if fault == 'unowned': files['/var/lib/dpkg/info/locales-all.list'] = b'/unrelated\n'
    if fault == 'stale-bytes': files[target] += b'stale'
    if fault == 'duplicate-manifest': files['/var/lib/dpkg/info/locales-all.md5sums'] *= 2
    if fault in ('locale', 'fallback', 'font'):
        # Configured packages with bad semantics must fail the independent
        # content oracle even when their package manifest matches those bytes.
        path, owner = {'locale': (target, 'locales-all'), 'fallback': (native, 'mate-polkit-common'),
                       'font': (assets.FONT_PATH, 'fonts-noto-cjk')}[fault]
        files[f'/var/lib/dpkg/info/{owner}.md5sums'] = (
            hashlib.md5(files[path], usedforsecurity=False).hexdigest() + '  ' + path.lstrip('/') + '\n').encode()
    if fault == 'replacement':
        original = g.read_file.side_effect
        def read(path):
            data = original(path)
            if path == target: metadata[target]['st_ino'] = metadata[target].get('st_ino', 1) + 1
            return data
        g.read_file.side_effect = read
    before = copy.deepcopy(files)
    with pytest.raises((ValueError, KeyError, OSError)):
        if fault == 'unowned': assets.preflight(g)
        else: assets.verify(g)
    assert files == before
    g.write.assert_not_called()


def test_package_profile_changes_source_identity_and_keeps_fedora_branch():
    import prepare_vm
    import guest_test_dependencies as tools
    assert 'tests/integration/chinese_language_assets.py' in prepare_vm.SCRIPT_FILES
    assert set(item.split('=')[0] for item in assets.PACKAGES) <= set(tools.VERSIONS)
    assert 'locales-all' not in tools.FEDORA_VERSIONS
    g, _, _ = guest()
    with pytest.raises(ValueError, match='unsupported-platform'): assets.verify(g, 'fedora')


def test_actual_selector_uses_existing_guarded_product_free_envelope(monkeypatch):
    import check_e2e_chinese_language_assets as selector
    smoke = Mock(return_value=0)
    monkeypatch.setattr(selector, 'smoke', smoke)
    monkeypatch.setattr(selector, 'named_input', lambda: 'verified-input')
    assert selector.main() == 0
    smoke.assert_called_once_with(assets='verified-input', provision_credentials=True,
                                  chinese_language_assets=True)
    assert ChineseLanguageQualification.__bases__ == (ProductFreeEntryQualification,)
    assert ChineseLanguageQualification.observation_only
    context = SimpleNamespace(product_free=True, asset_transfer=Mock())
    journey = ChineseLanguageQualification.journey(context, Mock())
    assert journey.plan is qualification.PLAN
    assert journey.plan.worker_mode == 'product_free_entry'
    assert journey.plan.stage_actions == {'wrong-entry': 'native-refuse', 'desktop': 'native-verify'}


def test_profile_controller_uses_guard_recheck_and_two_independent_reads():
    g, _, _ = guest()
    receipt = {**assets.verify(g), 'unchanged_state': True, 'runtime_locale': 'UTF-8'}
    transport = SimpleNamespace(config={'run': 'owned'}, guard=Mock(), call=Mock(
        return_value=(json.dumps(receipt, sort_keys=True) + '\n').encode()))
    verified = SimpleNamespace(recheck=Mock())
    controller = native_fixtures.NativeFixtures(transport, verified, profile='chinese')
    assert controller.verify() == {**receipt, 'independent_readback': True}
    assert transport.call.call_count == 2 and transport.guard.call_count == 2
    assert verified.recheck.call_count == 4
    with pytest.raises(EvidenceError, match='replay'): controller.verify()


def test_wrong_entry_refuses_before_asset_read_or_runtime_locale(monkeypatch):
    monkeypatch.setattr(guest_helper, 'authority', Mock(side_effect=
        guest_helper.session_control.SessionError('session:source-owner')))
    read = Mock(side_effect=AssertionError('must not inspect assets'))
    monkeypatch.setattr(assets, 'verify', read)
    assert guest_helper.execute('refuse', {}, 'chinese') == {'wrong_entry_refused': True}
    read.assert_not_called()
    with pytest.raises(ValueError): guest_helper.execute('prepare', {}, 'chinese')


@pytest.mark.parametrize('locale_file', ['regular', 'compatibility', 'foreign', 'dangling',
                                        'canonical-link'])
@pytest.mark.parametrize('mutation', [None, 'account', 'locale', 'link'])
def test_actual_guest_read_uses_regular_distribution_identity_and_preserves_state(
        monkeypatch, locale_file, mutation):
    g, files, metadata = guest()
    files['/usr/lib/os-release'] = b'ID=ubuntu\nVERSION_ID="26.04"\n'
    metadata['/usr/lib/os-release'] = {
        'st_mode': 0o100644, 'st_uid': 0, 'st_gid': 0, 'st_nlink': 1}
    # The normal Ubuntu compatibility link must never be opened as a regular
    # file or adopted by weakening the shared reader's link refusal.
    alias, canonical = '/etc/default/locale', '/etc/locale.conf'
    account = '/var/lib/AccountsService/users/' + guest_helper.session_control.ACCOUNTS['standard']
    for path in (canonical, account):
        files[path] = b'LANG=en_US.UTF-8\n'
        metadata[path] = {'st_mode': 0o100644, 'st_uid': 0, 'st_gid': 0, 'st_nlink': 1}
    metadata['/etc'] = {'st_mode': 0o40755, 'st_uid': 0, 'st_gid': 0}
    metadata['/etc/default'] = dict(metadata['/etc'])
    metadata[alias] = {'st_mode': 0o100644 if locale_file == 'regular' else 0o120777,
                       'st_uid': 0, 'st_gid': 0, 'st_nlink': 1, 'st_ino': 1}
    if locale_file == 'regular':
        files[alias] = files[canonical]
    if locale_file == 'dangling':
        files.pop(canonical)
        metadata.pop(canonical)
    links = {'/etc/os-release'} | ({alias} if locale_file != 'regular' else set())
    if locale_file == 'canonical-link':
        links.add(canonical)
        metadata[canonical]['st_mode'] = 0o120777
    g.is_symlink.side_effect = links.__contains__
    g.realpath.side_effect = lambda path: (
        '/foreign' if locale_file == 'foreign' else canonical) if path == alias and path in links else path
    # Model the actual O_NOFOLLOW reader, rather than silently reading the alias.
    def read_file(path):
        if path in links:
            raise OSError('no-follow')
        return files[path]
    g.read_file.side_effect = read_file
    monkeypatch.setattr(assets, 'LocalFiles', lambda: g)
    entry = {'session': 'fresh'}
    parent = SimpleNamespace(pw_uid=1000)
    monkeypatch.setattr(guest_helper, 'authority', lambda: (Mock(), parent, entry))
    monkeypatch.setattr(guest_helper.session_control, 'sessions', lambda: [])
    monkeypatch.setattr(guest_helper.session_control, 'source_session', lambda *args: entry)
    before = copy.deepcopy((files, metadata))
    expected = {**assets.verify(g), 'unchanged_state': True}
    original_verify = assets.verify
    def verify(reader):
        result = original_verify(reader)
        if mutation == 'account': files[account] += b'changed'
        if mutation == 'locale': files[canonical] += b'changed'
        if mutation == 'link': metadata[alias]['st_ino'] += 1
        return result
    monkeypatch.setattr(assets, 'verify', verify)
    if locale_file in ('foreign', 'dangling', 'canonical-link') or mutation:
        with pytest.raises((ValueError, OSError)):
            guest_helper.execute('read', {}, 'chinese')
    else:
        assert guest_helper.execute('read', {}, 'chinese') == expected
        assert guest_helper.execute('read', {}, 'chinese') == expected
    if mutation and locale_file in ('regular', 'compatibility'):
        # The deliberate engineering mutation must be detected, never repaired.
        assert (files, metadata) != before
    else:
        assert (files, metadata) == before
    assert '/etc/os-release' not in [call.args[0] for call in g.read_file.call_args_list]
    if alias in links:
        assert alias not in [call.args[0] for call in g.read_file.call_args_list]
    g.write.assert_not_called()


def test_uncertain_profile_read_cannot_replay_or_release_reply(tmp_path, monkeypatch):
    context = SimpleNamespace(directory=tmp_path, product_free=True, asset_transfer=Mock(),
                              verified=SimpleNamespace(recheck=Mock()))
    journey = qualification.journey(context, Mock())
    stage = 'wrong-entry'
    journey.steps = [{'stage': name} for name in journey.plan.stages[:2]]
    journey.transport = SimpleNamespace(config={}, guard=Mock(), call=Mock(side_effect=OSError))
    journey.ui = SimpleNamespace(observe=Mock(return_value={'outcome': 'passed'}),
                                 boot_proof='a' * 64)
    (tmp_path / (stage + '.request.json')).write_text(json.dumps({'stage': stage, 'screenshot': None}))
    with pytest.raises(OSError): journey.step(Mock())
    assert not (tmp_path / (stage + '.reply.json')).exists()
    journey.progress.assert_not_called()
    with pytest.raises(EvidenceError, match='previous-failure'): journey.step(Mock())


def test_owned_distribution_update_preserves_unrelated_assets_and_changes_receipt():
    g, files, metadata = guest()
    files['/unrelated'] = b'preserve'
    first = assets.verify(g)
    native = '/usr/share/locale/zh_CN/LC_MESSAGES/mate-polkit.mo'
    files[native] = catalogue({message: '新版中文 ' + message for message in assets.CATALOGUES['mate-polkit']})
    files['/var/lib/dpkg/info/mate-polkit-common.md5sums'] = (
        hashlib.md5(files[native], usedforsecurity=False).hexdigest() + '  ' + native.lstrip('/') + '\n').encode()
    files['/var/lib/dpkg/status'] = files['/var/lib/dpkg/status'].replace(b'Version: 1', b'Version: 2')
    assets.preflight(g)
    updated = assets.verify(g)
    assert updated['files'][native] != first['files'][native]
    assert set(updated['packages'].values()) == {'2'}
    assert files['/unrelated'] == b'preserve' and assets.verify(g) == updated


def test_shared_ram_snapshot_readiness_uses_read_only_program_and_refuses_bad_receipt():
    g, _, _ = guest()
    receipt = assets.verify(g)
    transport = Mock(call=Mock(return_value=(json.dumps(receipt, sort_keys=True) + '\n').encode()))
    assert assets.verify_transport(transport) == receipt
    call = transport.call.call_args
    assert call.args[0] == ['/usr/bin/python3', '-I', '-'] and call.kwargs['timeout'] == 90
    compile(call.kwargs['input'], '<shared-readiness>', 'exec')
    for change in ({'provider': 'foreign'}, {'files': {}}, {'packages': {}}, {'locale': 'en_US.UTF-8'}):
        changed = {**receipt, **change}
        transport.call.return_value = (json.dumps(changed, sort_keys=True) + '\n').encode()
        with pytest.raises(ValueError): assets.verify_transport(transport)


def test_partial_package_preparation_retries_once_then_reuses_without_network(tmp_path, monkeypatch):
    import prepare_vm
    from tests.support.chinese_assets import populate
    g, files, metadata = guest()
    files.clear()
    metadata = {path: info for path, info in metadata.items() if info['st_mode'] & 0o170000 == 0o040000}
    g.lstatns.side_effect = lambda path: dict(metadata[path])
    g.exists.side_effect = lambda path: path in files or path in metadata
    files['/var/lib/dpkg/status'] = b''
    metadata['/var/lib/dpkg/status'] = {'st_mode': 0o100644, 'st_uid': 0, 'st_gid': 0, 'st_nlink': 1}
    status = tmp_path / 'var/lib/dpkg/status'
    status.parent.mkdir(parents=True)
    status.write_bytes(b'')
    sources = tmp_path / 'etc/apt/sources.list.d/ubuntu.sources'
    sources.parent.mkdir(parents=True)
    sources.write_text('URIs: https://archive.ubuntu.com/ubuntu/\n')
    monkeypatch.setattr(assets, 'LocalFiles', lambda root: g)
    ssh = Mock()
    monkeypatch.setattr(prepare_vm, 'prepare_ssh', ssh)
    calls = []
    interrupted = True
    def run(command, **kwargs):
        nonlocal interrupted
        calls.append(command)
        if command[0] == 'env':
            if interrupted:
                interrupted = False
                status.write_bytes(b'Package: locales-all\nStatus: install ok unpacked\nVersion: 1\n')
                files['/var/lib/dpkg/status'] = status.read_bytes()
                raise subprocess.CalledProcessError(1, command)
            status.write_text('\n\n'.join(
                f'Package: {name}\nVersion: {version if version != "0" else "1"}\nStatus: install ok installed\n'
                for name, version in prepare_vm.guest_tools.VERSIONS.items()))
            files['/var/lib/dpkg/status'] = status.read_bytes()
            populate(files, metadata)
        return subprocess.CompletedProcess(command, 3 if command[:2] == ['systemctl', 'is-active'] else 0,
                                           'inactive' if command[:2] == ['systemctl', 'is-active'] else '')
    runner = SimpleNamespace(run=run)
    with pytest.raises(subprocess.CalledProcessError):
        prepare_vm.prepare_test_dependencies(runner=runner, root=tmp_path)
    ssh.assert_not_called()
    prepare_vm.prepare_test_dependencies(runner=runner, root=tmp_path)
    assert assets.verify(g)['profile'] == 'chinese'
    calls.clear()
    before = copy.deepcopy(files)
    prepare_vm.prepare_test_dependencies(runner=runner, root=tmp_path)
    assert files == before and not any(command[0] in ('env', 'apt-get') for command in calls)


def test_online_readiness_failure_blocks_snapshot_return_before_product_actions(monkeypatch):
    import online_snapshot
    transport = SimpleNamespace(call=Mock(side_effect=[b'', b'1000\n']))
    monkeypatch.setattr(online_snapshot, 'connect_saved_transport', lambda *args: transport)
    monkeypatch.setattr(online_snapshot.time, 'time', lambda: 1000)
    failure = Mock(side_effect=ValueError('baseline:chinese-locale; run tools/prepare-baseline'))
    monkeypatch.setattr(assets, 'verify_transport', failure)
    lease = SimpleNamespace(capture=SimpleNamespace(state={'guest': {'ubuntu_version': '26.04'}}))
    with pytest.raises(ValueError, match='chinese-locale'):
        online_snapshot.saved_transport(lease, None, None, 'fixture')
    failure.assert_called_once_with(transport)
    assert transport.call.call_count == 2


def test_missing_language_stops_real_bootstrap_before_any_guest_write(tmp_path, monkeypatch):
    from contextlib import contextmanager
    import system_runner
    from tests.support.vm_runner import bootstrap_guest
    g, files = bootstrap_guest()
    files.pop(assets.LOCALE_PATH)
    @contextmanager
    def mounted(*args, **kwargs):
        yield g, '/dev/sda2'
    monkeypatch.setattr(system_runner, 'mounted_guest', mounted)
    lease = Mock()
    commands = Mock()
    with pytest.raises(ValueError, match='chinese-missing-file.*prepare-baseline'):
        system_runner.bootstrap(commands, lease, tmp_path, Mock(), observation_only=True)
    g.write.assert_not_called()
    g.chown.assert_not_called()


@pytest.mark.parametrize('runtime', ['ANSI_X3.4-1968\n', '', RuntimeError('invalid locale')])
def test_missing_generated_locale_fails_with_refresh_guidance(runtime):
    g, _, _ = guest()
    if isinstance(runtime, Exception): g.command.side_effect = runtime
    else: g.command.return_value = runtime
    with pytest.raises(ValueError, match='chinese-locale-runtime.*prepare-baseline'):
        assets.verify(g)


def test_local_reader_pins_regular_descriptor_and_refuses_replacement(tmp_path, monkeypatch):
    g = assets.LocalFiles(tmp_path)
    path = tmp_path / 'file'
    path.write_bytes(b'fixture')
    assert g.realpath('/') == '/' and g.read_file('/file') == b'fixture'
    path.rename(tmp_path / 'old')
    path.symlink_to(tmp_path / 'old')
    with pytest.raises(OSError): g.read_file('/file')
    path.unlink()
    path.write_bytes(b'fixture')
    real_open = assets.os.open
    def replace(name, flags):
        fd = real_open(name, flags)
        path.rename(tmp_path / 'preserved')
        path.write_bytes(b'fixture')
        return fd
    monkeypatch.setattr(assets.os, 'open', replace)
    with pytest.raises(ValueError, match='changed'): g.read_file('/file')
    assert (tmp_path / 'preserved').read_bytes() == b'fixture'
