"""Installed-platform evidence checks use private files and command doubles."""

import json
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, call

import pytest

import system_kiosk_platform as platform


AUDIT_PATH = Path('/home/kiosk/onpc-platform-ladspa.so')
AUDIT_LINES = {
    'apparmor': ('audit: apparmor="DENIED" operation="file_mmap" '
                 'profile="onpc-kiosk-audio" pid=4242 comm="wireplumber" '
                 'name="/home/kiosk/onpc-platform-ladspa.so" denied_mask="m"'),
    'selinux': ('type=AVC msg=audit(1:2): avc:  denied  { execute } for pid=4242 '
                'comm="wireplumber" path="/home/kiosk/onpc-platform-ladspa.so" '
                'scontext=system_u:system_r:onpc_kiosk_audio_t:s0 '
                'tcontext=unconfined_u:object_r:user_home_t:s0 tclass=file permissive=0'),
}


@pytest.mark.parametrize('backend', ['apparmor', 'selinux'])
def test_audit_denial_requires_the_owned_audio_mapping(backend):
    assert platform.audit_denial(AUDIT_LINES[backend], backend, 4242, AUDIT_PATH)


@pytest.mark.parametrize('backend,old,new', [
    ('apparmor', 'pid=4242', 'pid=42420'),
    ('apparmor', 'pid=4242', 'ppid=4242'),
    ('apparmor', str(AUDIT_PATH), str(AUDIT_PATH) + '.other'),
    ('apparmor', 'profile="onpc-kiosk-audio"', 'profile="onpc-kiosk-audio-other"'),
    ('apparmor', 'apparmor="DENIED"', 'apparmor="ALLOWED"'),
    ('apparmor', 'operation="file_mmap"', 'operation="open"'),
    ('apparmor', 'denied_mask="m"', 'denied_mask="r"'),
    ('selinux', 'pid=4242', 'pid=42420'),
    ('selinux', 'pid=4242', 'ppid=4242'),
    ('selinux', str(AUDIT_PATH), str(AUDIT_PATH) + '.other'),
    ('selinux', 'onpc_kiosk_audio_t:s0', 'onpc_kiosk_manager_t:s0'),
    ('selinux', 'onpc_kiosk_audio_t:s0', 'onpc_kiosk_audio_t:s0:c1'),
    ('selinux', 'permissive=0', 'permissive=1'),
    ('selinux', 'permissive=0', 'permissive=01'),
    ('selinux', 'avc:  denied', 'avc:  granted'),
    ('selinux', '{ execute }', '{ read }'),
    ('selinux', 'tclass=file', 'tclass=process'),
    ('selinux', 'tclass=file', 'tclass=file_other'),
])
def test_audit_denial_rejects_unrelated_or_unenforced_records(backend, old, new):
    line = AUDIT_LINES[backend].replace(old, new)
    assert not platform.audit_denial(line, backend, 4242, AUDIT_PATH)


@pytest.mark.parametrize('backend', ['apparmor', 'selinux'])
def test_audit_denial_does_not_combine_separate_records(backend):
    line = AUDIT_LINES[backend]
    split = line.index('path=' if backend == 'selinux' else 'name=')
    assert not platform.audit_denial(line[:split] + '\n' + line[split:],
                                     backend, 4242, AUDIT_PATH)


def test_native_mappings_only_include_executable_absolute_files(tmp_path):
    (tmp_path / 'maps').write_text(
        '1000-2000 r-xp 0 00:00 1 /usr/lib64/liblua-5.4.so\n'
        '2000-3000 r--p 0 00:00 2 /home/kiosk/data.so (deleted)\n'
        '3000-4000 rwxp 0 00:00 3 /usr/lib64/plugin with spaces.so\n'
        '4000-5000 r-xp 0 00:00 1 /usr/lib64/liblua-5.4.so\n'
        '5000-6000 r-xp 0 00:00 0 [vdso]\n'
        '6000-7000 r-xp 0 00:00 0\n'
        '7000-8000 r-xp 0 00:00 4 relative.so\n')
    assert platform.native_mappings(tmp_path) == [
        Path('/usr/lib64/liblua-5.4.so'), Path('/usr/lib64/plugin with spaces.so')]


def test_native_mappings_refuse_deleted_executable_evidence(tmp_path):
    (tmp_path / 'maps').write_text(
        '1000-2000 r-xp 0 00:00 1 /usr/lib64/liblua-5.4.so (deleted)\n')
    with pytest.raises(platform.guest.GuestError, match='platform:deleted-native-map'):
        platform.native_mappings(tmp_path)


def test_guest_guard_precedes_account_service_and_diagnostic_actions(monkeypatch):
    monkeypatch.setattr(platform.guest, 'guard', Mock(
        side_effect=platform.guest.GuestError('identity')))
    diagnostics, account, command, user_command, inventory = (Mock() for _ in range(5))
    monkeypatch.setattr(platform.guest, 'enable_diagnostics', diagnostics)
    monkeypatch.setattr(platform.pwd, 'getpwnam', account)
    monkeypatch.setattr(platform.guest, 'run', command)
    monkeypatch.setattr(platform, 'user_command', user_command)
    monkeypatch.setattr(platform, 'package_inventory', inventory)
    with pytest.raises(platform.guest.GuestError, match='identity'):
        platform.verify(Mock())
    for action in (diagnostics, account, command, user_command, inventory):
        action.assert_not_called()


def test_environment_preserves_empty_lua_paths_and_equals_in_values(tmp_path):
    (tmp_path / 'environ').write_bytes(b'LUA_PATH=\0LUA_CPATH=\0OTHER=one=two\0')
    assert platform.environment(tmp_path) == {'LUA_PATH': '', 'LUA_CPATH': '',
                                               'OTHER': 'one=two'}


@pytest.fixture
def runtime_directory(tmp_path, monkeypatch):
    directory = tmp_path / 'runtime-fixture'

    def mkdtemp(*, prefix, dir):
        assert prefix == 'onpc-platform-'
        assert dir == Path('/run/user/41001')
        directory.mkdir(mode=0o700)
        return str(directory)

    native_fstat = platform.os.fstat

    def fstat(fd):
        info = native_fstat(fd)
        return SimpleNamespace(st_dev=info.st_dev, st_ino=info.st_ino,
                               st_uid=0, st_mode=info.st_mode)

    monkeypatch.setattr(platform.tempfile, 'mkdtemp', mkdtemp)
    monkeypatch.setattr(platform.os, 'fstat', fstat)
    monkeypatch.setattr(platform.os, 'fchown', Mock())
    return directory


def test_runtime_fixture_writes_exclusively_and_cleans_owned_files(runtime_directory):
    account = SimpleNamespace(pw_uid=41001, pw_gid=41002)
    with platform.runtime_fixture(account) as (directory, write):
        assert directory == runtime_directory
        assert directory.stat().st_mode & 0o777 == 0o755
        canary = write('canary.lua', b'return "canary"\n', owner=account)
        assert canary.read_bytes() == b'return "canary"\n'
        assert canary.stat().st_mode & 0o777 == 0o644
        platform.os.fchown.assert_called_once()
        assert platform.os.fchown.call_args.args[1:] == (41001, 41002)
        with pytest.raises(platform.guest.GuestError, match='platform:fixture-name'):
            write('canary.lua', b'replacement')
        with pytest.raises(platform.guest.GuestError, match='platform:fixture-name'):
            write('../outside', b'outside')
        assert canary.read_bytes() == b'return "canary"\n'
    assert not runtime_directory.exists()


@pytest.mark.parametrize('change,category', [
    ('file', 'platform:fixture-file-replaced'),
    ('extra', 'platform:foreign-fixture-entry'),
    ('directory', 'platform:fixture-directory-replaced'),
])
def test_runtime_fixture_refuses_replacements_and_preserves_all_data(runtime_directory,
                                                                  change, category):
    account = SimpleNamespace(pw_uid=41001, pw_gid=41002)
    displaced = runtime_directory.with_name('displaced')
    with pytest.raises(platform.guest.GuestError, match=category):
        with platform.runtime_fixture(account) as (directory, write):
            owned = write('owned', b'owned-by-attempt')
            if change == 'file':
                owned.rename(displaced)
                owned.write_bytes(b'foreign-replacement')
            elif change == 'extra':
                (directory / 'foreign').write_bytes(b'foreign-entry')
            else:
                directory.rename(displaced)
                directory.mkdir()
                (directory / 'foreign').write_bytes(b'foreign-directory')
                write('late', b'held-directory-descriptor')
                assert not (directory / 'late').exists()
    if change == 'file':
        assert displaced.read_bytes() == b'owned-by-attempt'
        assert (runtime_directory / 'owned').read_bytes() == b'foreign-replacement'
    elif change == 'extra':
        assert (runtime_directory / 'owned').read_bytes() == b'owned-by-attempt'
        assert (runtime_directory / 'foreign').read_bytes() == b'foreign-entry'
    else:
        assert (displaced / 'owned').read_bytes() == b'owned-by-attempt'
        assert (displaced / 'late').read_bytes() == b'held-directory-descriptor'
        assert (runtime_directory / 'foreign').read_bytes() == b'foreign-directory'


@pytest.fixture
def audio_process(tmp_path, monkeypatch):
    proc_root = tmp_path / 'proc'
    process = proc_root / '4242'
    (process / 'attr').mkdir(parents=True)
    (process / 'attr/current').write_text('onpc-kiosk-audio (enforce)\n')
    values = {'WIREPLUMBER_CONFIG_DIR': '/etc/wireplumber:/usr/share/wireplumber',
              'WIREPLUMBER_DATA_DIR': '/usr/share/wireplumber',
              'LUA_PATH': '', 'LUA_CPATH': ''}
    (process / 'environ').write_bytes(b'\0'.join(
        (name + '=' + value).encode() for name, value in values.items()) + b'\0')
    (process / 'maps').write_text('1000-2000 r-xp 0 00:00 1 /usr/lib64/liblua-5.4.so\n')
    monkeypatch.setattr(platform, 'Path',
                        lambda value: proc_root if str(value) == '/proc' else Path(value))
    monkeypatch.setattr(platform, 'user_command', Mock(return_value=b'4242\n'))
    identity = ('start', 1, ('41001',) * 4)
    monkeypatch.setattr(platform, 'process_identity', Mock(return_value=identity))
    return SimpleNamespace(process=process, values=values, identity=identity, account=object())


@pytest.mark.parametrize('backend,label', [
    ('apparmor', 'onpc-kiosk-audio (enforce)'),
    ('selinux', 'system_u:system_r:onpc_kiosk_audio_t:s0'),
])
def test_audio_snapshot_accepts_exact_enforcing_label_and_isolated_environment(audio_process,
                                                                             backend, label):
    (audio_process.process / 'attr/current').write_text(label + '\0\n')
    process, identity, values, library, mappings = platform.audio_snapshot(audio_process.account,
                                                                         backend)
    assert process == audio_process.process
    assert identity == audio_process.identity
    assert values == audio_process.values
    assert library == Path('/usr/lib64/liblua-5.4.so')
    assert mappings == [library]


@pytest.mark.parametrize('name', [
    'WIREPLUMBER_MODULE_DIR', 'PIPEWIRE_MODULE_DIR', 'PIPEWIRE_CONFIG_DIR', 'SPA_PLUGIN_DIR',
    'LUA_PATH_5_4', 'LUA_CPATH_5_4', 'LUA_PATH_5_5', 'LUA_CPATH_5_5',
    'LD_PRELOAD', 'LD_LIBRARY_PATH', 'XDG_CONFIG_HOME', 'XDG_DATA_HOME',
])
def test_audio_snapshot_refuses_each_native_or_lua_environment_override(audio_process, name):
    with (audio_process.process / 'environ').open('ab') as stream:
        stream.write((name + '=\0').encode())
    with pytest.raises(platform.guest.GuestError, match='platform:audio-injection:' + name):
        platform.audio_snapshot(audio_process.account, 'apparmor')


@pytest.mark.parametrize('name', ['WIREPLUMBER_CONFIG_DIR', 'WIREPLUMBER_DATA_DIR',
                                'LUA_PATH', 'LUA_CPATH'])
@pytest.mark.parametrize('missing', [False, True])
def test_audio_snapshot_requires_fixed_configuration_and_empty_lua_search(audio_process,
                                                                         name, missing):
    values = dict(audio_process.values)
    if missing:
        del values[name]
    else:
        values[name] = '/home/kiosk/injection'
    (audio_process.process / 'environ').write_bytes(b'\0'.join(
        (key + '=' + value).encode() for key, value in values.items()) + b'\0')
    with pytest.raises(platform.guest.GuestError, match='platform:audio-environment:' + name):
        platform.audio_snapshot(audio_process.account, 'apparmor')


@pytest.mark.parametrize('label', ['onpc-kiosk-audio (complain)',
                                  'onpc-kiosk-manager (enforce)'])
def test_audio_snapshot_refuses_permissive_or_other_role(audio_process, label):
    (audio_process.process / 'attr/current').write_text(label)
    with pytest.raises(platform.guest.GuestError, match='platform:audio-label'):
        platform.audio_snapshot(audio_process.account, 'apparmor')


@pytest.mark.parametrize('failed_probe', [None, 'positive', 'restricted'])
def test_lua_cwd_result_requires_dropped_uid_positive_and_restricted_negative(tmp_path,
                                                                           monkeypatch,
                                                                           failed_probe):
    account = SimpleNamespace(pw_uid=41001, pw_gid=41002)
    library = Path('/usr/lib64/liblua-5.4.so')
    values = {'PATH': '/usr/bin:/bin', 'LUA_PATH': '', 'LUA_CPATH': '', 'OTHER': 'one=two'}
    original = dict(values)
    probes = []

    def run(command, **options):
        assert command[:8] == ['/usr/bin/setpriv', '--reuid', '41001', '--regid', '41002',
                               '--clear-groups', '/usr/bin/env', '-i']
        assert options == {'check': True, 'timeout': 45, 'merge_stderr': False}
        python = command.index('/usr/bin/python3')
        inner_env = command.index('/usr/bin/env', 7)
        assert command[inner_env + 1] == '-i'
        selected = dict(item.split('=', 1) for item in command[inner_env + 2:python])
        assert command[python:] == ['/usr/bin/python3', '-I', '-c', platform.LUA_PROBE,
                                   str(library), str(tmp_path)]
        assert selected['OTHER'] == 'one=two'
        restricted = 'LUA_PATH' in selected
        assert ('LUA_CPATH' in selected) is restricted
        if restricted:
            assert selected['LUA_PATH'] == selected['LUA_CPATH'] == ''
        probes.append(restricted)
        if failed_probe == ('restricted' if restricted else 'positive'):
            return b'{"loaded": false, "missing": false}'
        return json.dumps({'loaded': not restricted, 'missing': restricted}).encode()

    monkeypatch.setattr(platform.guest, 'commands', SimpleNamespace(run=Mock(side_effect=run)))
    record = Mock()
    write = Mock()
    if failed_probe is None:
        platform.verify_lua(account, library, tmp_path, values, record, write)
        record.assert_called_once_with('onpc.platform.actual-lua-cwd-denied', True)
        assert probes == [False, True]
    else:
        with pytest.raises(platform.guest.GuestError, match='platform:actual-lua-default-search'):
            platform.verify_lua(account, library, tmp_path, values, record, write)
        record.assert_not_called()
        assert probes == ([False] if failed_probe == 'positive' else [False, True])
    assert values == original
    write.assert_called_once_with('onpc_platform_canary.lua', b'return "onpc-platform-canary"\n')


@pytest.mark.parametrize('backend,root', [
    ('apparmor', '/usr/lib/x86_64-linux-gnu'), ('selinux', '/usr/lib64'),
])
@pytest.mark.parametrize('positive_ok', [False, True])
def test_native_api_requires_same_uid_elf_positive_before_mapping_denial(tmp_path, monkeypatch,
                                                                       backend, root, positive_ok):
    account = SimpleNamespace(pw_uid=41001, pw_gid=41002)
    process = Path('/proc/4242')
    source = Path(root) / 'pipewire-0.3/libpipewire-module-metadata.so'
    target = tmp_path / 'onpc-platform-ladspa.so'
    key = 'onpc-platform-' + tmp_path.name
    identity = ('start', 1, ('41001',) * 4)
    trusted = Mock()
    write = Mock(return_value=target)
    monkeypatch.setattr(platform, 'trusted_native', trusted)
    native_read_bytes = Path.read_bytes
    monkeypatch.setattr(Path, 'read_bytes', lambda path:
                        b'\x7fELFowned-distro-library' if path == source else native_read_bytes(path))
    monkeypatch.setattr(platform.guest, 'sha', Mock(return_value='same-elf-digest'))
    journal = Mock(return_value='-- cursor: cursor-at-owned-probe')
    monkeypatch.setattr(platform.guest, 'run', journal)
    monkeypatch.setattr(platform, 'audio_journal', Mock(
        return_value=str(source) + ': undefined symbol: ladspa_descriptor'))
    monkeypatch.setattr(platform, 'kernel_audit', Mock(
        return_value=AUDIT_LINES[backend].replace(str(AUDIT_PATH), str(target))))
    mappings = Mock(return_value=[source])
    monkeypatch.setattr(platform, 'native_mappings', mappings)
    monkeypatch.setattr(platform, 'process_identity', Mock(return_value=identity))
    settle = Mock()
    monkeypatch.setattr(platform, 'settle_kernel_audit', settle)
    monkeypatch.setattr(platform, 'wait_for',
                        lambda predicate, category: platform.guest.require(predicate(), category))
    requests = []
    state = {}

    def run(command, **options):
        assert command[:8] == ['/usr/bin/setpriv', '--reuid', '41001', '--regid', '41002',
                               '--clear-groups', '/usr/bin/env', '-i']
        assert options == {'check': True, 'timeout': 45, 'merge_stderr': False}
        if '/usr/bin/python3' in command:
            assert not requests
            assert command[-5:] == ['/usr/bin/python3', '-I', '-c',
                                    'import ctypes,sys;ctypes.CDLL(sys.argv[1])', str(target)]
            write.assert_called_once_with('onpc-platform-ladspa.so', b'\x7fELFowned-distro-library',
                                          owner=account)
            if not positive_ok:
                raise platform.guest.GuestError('elf-positive-failed')
            return b''
        payload = command[command.index('pw-metadata'):]
        assert payload[:3] == ['pw-metadata', '-n', 'sm-objects']
        if '-d' in payload:
            assert payload == ['pw-metadata', '-n', 'sm-objects', '-d', '0', key]
            state.clear()
        elif len(payload) > 3:
            assert payload[3:5] == ['0', key]
            assert payload[6:] == ['Spa:String:JSON']
            value = json.loads(payload[5])
            assert value['type'] == 'pw-module'
            assert value['name'] == 'libpipewire-module-filter-chain'
            node = value['args']['filter.graph']['nodes'][0]
            assert node['type'] == 'ladspa'
            requests.append(node['plugin'])
            state[key] = value
        return ('Found "sm-objects" metadata 7\n' + json.dumps(state)).encode()

    commands = Mock(side_effect=run)
    monkeypatch.setattr(platform.guest, 'commands', SimpleNamespace(run=commands))
    record = Mock()
    if positive_ok:
        platform.verify_native_api(account, backend, process, identity, tmp_path, record, write)
        assert requests == [str(source), str(target)]
        assert not state
        assert record.call_args_list == [
            call('onpc.platform.trusted-native-api-positive', True),
            call('onpc.platform.native-api-audit',
                 AUDIT_LINES[backend].replace(str(AUDIT_PATH), str(target))),
            call('onpc.platform.native-api-map-denied', True),
        ]
        mappings.assert_called_once_with(process)
        journal.assert_called_once()
        settle.assert_called_once_with(backend)
    else:
        with pytest.raises(platform.guest.GuestError, match='elf-positive-failed'):
            platform.verify_native_api(account, backend, process, identity, tmp_path, record, write)
        commands.assert_called_once()
        journal.assert_not_called()
        mappings.assert_not_called()
        record.assert_not_called()
        settle.assert_not_called()
    trusted.assert_called_once_with(source)


@pytest.mark.parametrize('backend,interval,delay', [
    ('apparmor', '5', 6), ('apparmor', '0', None), ('selinux', None, None),
])
def test_audit_spacing_reads_existing_interval_without_mutation(monkeypatch, backend, interval, delay):
    path = Mock()
    path.read_text.return_value = interval
    constructor = Mock(return_value=path)
    sleep = Mock()
    monkeypatch.setattr(platform, 'Path', constructor)
    monkeypatch.setattr(platform.time, 'sleep', sleep)
    platform.settle_kernel_audit(backend)
    if backend == 'apparmor':
        constructor.assert_called_once_with('/proc/sys/kernel/printk_ratelimit')
    else:
        constructor.assert_not_called()
    if delay is not None:
        sleep.assert_called_once_with(delay)
    else:
        sleep.assert_not_called()


@pytest.mark.parametrize('interval', ['-1', '31'])
def test_audit_spacing_refuses_unbounded_interval(monkeypatch, interval):
    path = Mock()
    path.read_text.return_value = interval
    sleep = Mock()
    monkeypatch.setattr(platform, 'Path', Mock(return_value=path))
    monkeypatch.setattr(platform.time, 'sleep', sleep)
    with pytest.raises(platform.guest.GuestError, match='platform:audit-interval-out-of-bounds'):
        platform.settle_kernel_audit('apparmor')
    sleep.assert_not_called()
