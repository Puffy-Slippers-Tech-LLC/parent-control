"""Private native-trust and old-release control regressions; no live VM or trust DB."""

import hashlib
import json
import os
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

import system_trusted_fixtures as trusted
import system_enforcement as enforcement
from tests.fixtures import baseline_assets


@pytest.mark.parametrize('variant', ['trusted-hard', 'trusted-soft'])
def test_provision_consumes_exact_baseline_declaration_and_native_verification(monkeypatch, variant):
    accounts = {role: SimpleNamespace(pw_dir='/home/' + role, pw_uid=1001 + index)
                for index, role in enumerate(('child', 'other', 'parent'))}
    monkeypatch.setattr(enforcement.guest, 'guard', Mock())
    monkeypatch.setattr(enforcement.guest, 'enable_diagnostics', Mock())
    monkeypatch.setattr(enforcement.pwd, 'getpwnam', lambda name: accounts[
        {'onpc-child-riley': 'child', 'onpc-child-jordan': 'other', 'onpc-parent-jamie': 'parent'}[name]])
    files, verify = Mock(), Mock()
    monkeypatch.setattr(enforcement, 'verify_fixture_files', files)
    monkeypatch.setattr(trusted, 'verify_trust', verify)
    assert enforcement.provision_native(variant) == {'child': 1001, 'other': 1002, 'parent': 1003}
    target, desktop, _ = enforcement.native_paths(variant)
    declaration = baseline_assets.native_files(accounts)
    files.assert_called_once_with({str(path): declaration[str(path)] for path in (target, desktop)}, {})
    verify.assert_called_once_with(variant=variant)


@pytest.mark.parametrize('fault', [None, 'missing', 'duplicate', 'source', 'size', 'digest',
                                  'extra-column', 'untrusted'])
def test_native_database_requires_exact_positive_and_negative_identities(fault):
    files = {'/fixed/hard': {'size': 42, 'sha256': 'a' * 64},
             '/fixed/soft': {'size': 43, 'sha256': 'b' * 64}}
    rows = ['filedb /fixed/hard 42 ' + 'a' * 64, 'filedb /fixed/soft 43 ' + 'b' * 64]
    if fault == 'missing':
        rows.pop()
    elif fault == 'duplicate':
        rows.append(rows[0])
    elif fault == 'source':
        rows[0] = rows[0].replace('filedb', 'rpmdb')
    elif fault == 'size':
        rows[0] = rows[0].replace(' 42 ', ' 41 ')
    elif fault == 'digest':
        rows[0] = rows[0].replace('a' * 64, 'c' * 64)
    elif fault == 'extra-column':
        rows[0] += ' extra'
    elif fault == 'untrusted':
        rows.append('filedb /fixed/original 42 ' + 'a' * 64)
    rows.append('rpmdb /unrelated 99 ' + 'c' * 64)
    if fault:
        with pytest.raises(trusted.guest.GuestError, match='trusted-fixtures:'):
            trusted.validate_database('\n'.join(rows), files, ['/fixed/original'])
    else:
        trusted.validate_database('\n'.join(rows), files, ['/fixed/original'])


def test_native_database_refuses_trusted_original_with_real_whitespace_path():
    path = str(enforcement.native_paths('whitespace')[0])
    assert trusted.database_row(f'filedb {path} 42 ' + 'a' * 64) == [
        'filedb', path, '42', 'a' * 64]
    with pytest.raises(trusted.guest.GuestError, match='untrusted-input-changed'):
        trusted.validate_database(f'filedb {path} 42 ' + 'a' * 64, {}, [path])


@pytest.fixture
def private_metadata(monkeypatch, tmp_path):
    original = os.fstat
    original_lstat = trusted.Path.lstat

    def root(info):
        fields = list(info)
        fields[4] = fields[5] = 0
        return os.stat_result(fields)

    monkeypatch.setattr(trusted.os, 'fstat', lambda fd: root(original(fd)))
    def metadata(path):
        info = root(original_lstat(path))
        if not path.is_relative_to(tmp_path):
            # Model protected VM ancestors without depending on the developer's
            # checkout permissions. Keep all private fixture metadata real.
            fields = list(info)
            fields[0] &= ~0o022
            info = os.stat_result(fields)
        return info

    monkeypatch.setattr(trusted.Path, 'lstat', metadata)


@pytest.mark.parametrize('fault', [None, 'mode', 'hardlink', 'size', 'link', 'parent-link', 'parent-mode'])
def test_record_reader_refuses_substitution_and_unsafe_metadata(tmp_path, private_metadata, fault):
    parent = tmp_path / 'records'
    parent.mkdir(mode=0o700)
    path = parent / 'record'
    path.write_bytes(b'fixed')
    path.chmod(0o600)
    if fault == 'mode':
        path.chmod(0o644)
    elif fault == 'hardlink':
        os.link(path, tmp_path / 'alias')
    elif fault == 'size':
        path.write_bytes(b'x' * 11)
    elif fault == 'link':
        destination = path.with_name('original')
        path.rename(destination)
        path.symlink_to(destination)
    elif fault == 'parent-link':
        destination = parent.with_name('original')
        parent.rename(destination)
        parent.symlink_to(destination, target_is_directory=True)
    elif fault == 'parent-mode':
        parent.chmod(0o777)
    if fault:
        with pytest.raises((trusted.guest.GuestError, OSError)):
            trusted.root_file(path, 0o600, limit=10)
    else:
        assert trusted.root_file(path, 0o600, limit=10) == b'fixed'


def test_configuration_reader_requires_exact_recorded_vendor_group(tmp_path, private_metadata, monkeypatch):
    path = tmp_path / 'config'
    path.write_bytes(b'trust = rpmdb,file\n')
    path.chmod(0o640)
    original = trusted.os.fstat

    def metadata(fd):
        fields = list(original(fd))
        fields[5] = 42
        return os.stat_result(fields)

    monkeypatch.setattr(trusted.os, 'fstat', metadata)
    with pytest.raises(trusted.guest.GuestError, match='record-metadata'):
        trusted.root_file(path, 0o640)
    assert trusted.root_file(path, 0o640, gid=42) == path.read_bytes()


@pytest.mark.parametrize('entry', ['verify_trust', 'qualify'])
def test_attempt_guard_refuses_before_native_reads_or_policy(monkeypatch, entry):
    monkeypatch.setattr(trusted.guest, 'guard', Mock(side_effect=trusted.guest.GuestError('guard')))
    reader, policy = Mock(), Mock()
    monkeypatch.setattr(trusted, 'root_file', reader)
    monkeypatch.setattr(trusted, 'call', policy)
    with pytest.raises(trusted.guest.GuestError, match='guard'):
        getattr(trusted, entry)(Mock()) if entry == 'qualify' else trusted.verify_trust()
    reader.assert_not_called()
    policy.assert_not_called()


@pytest.fixture(params=['ubuntu', 'fedora'])
def live_receipt(tmp_path, monkeypatch, request):
    platform = request.param
    payload = tmp_path / 'fixtures/mechanical'
    payload.mkdir(parents=True)
    contents = {'mechanical': b'original', 'trusted-hard': b'hard', 'trusted-soft': b'soft'}
    for variant, raw in contents.items():
        (payload / ('onpc-test-application' if variant == 'mechanical' else 'identity-' + variant)).write_bytes(raw)
    monkeypatch.setattr(trusted.guest, 'PAYLOAD', tmp_path)
    h = lambda raw: hashlib.sha256(raw).hexdigest()
    files = {str(enforcement.native_paths(variant)[0]):
             dict(sha256=h(contents[variant]), size=len(contents[variant]), mode=0o755, uid=0, gid=0)
             for variant in trusted.TRUSTED_VARIANTS}
    fixture = {'purpose': 'onpc-reusable-fixtures-v1', 'pending': None,
               'files': {path: {key: value for key, value in spec.items() if key != 'size'}
                         for path, spec in files.items()}}
    original = dict(sha256=h(contents['mechanical']), mode=0o755, uid=0, gid=0)
    fixture['files'][baseline_assets.MECHANICAL] = original
    raw_files = {str(enforcement.native_paths(variant)[0]): contents[variant]
                 for variant in trusted.TRUSTED_VARIANTS}
    from tests.fixtures.native_assets import ACTIVITY_PREFIX, ACTIVITY_EXECUTABLE, GUI_FILES, activity_sources
    for target, source in zip((ACTIVITY_EXECUTABLE,
                              *(ACTIVITY_PREFIX + '/' + name for name in GUI_FILES)), activity_sources()):
        raw = source.encode()
        raw_files[target] = raw
        spec = dict(sha256=h(raw), size=len(raw),
                    mode=baseline_assets.trusted_file_modes()[target], uid=0, gid=0)
        files[target] = spec
        fixture['files'][target] = {key: value for key, value in spec.items() if key != 'size'}
        path = tmp_path / source
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(raw)
    for variant in ('command', 'whitespace'):
        path = str(enforcement.native_paths(variant)[0])
        fixture['files'][path] = original
        raw_files[path] = contents['mechanical']
    raw_files[str(trusted.FIXTURE_RECORD)] = json.dumps(fixture).encode()
    raw_files[trusted.TRUST_FILE] = ''.join(
        f'{path} {spec["size"]} {spec["sha256"]}\n' for path, spec in files.items()).encode()
    tools = trusted.native_tool_paths(platform)
    for label, executable in tools.items():
        raw_files[executable] = label.encode()
    before_config = b'trust = debdb\n' if platform == 'ubuntu' else b'trust = rpmdb,file\n'
    config = before_config.replace(b'debdb', b'debdb,file') if platform == 'ubuntu' else before_config
    backend_record = dict(purpose='onpc-native-file-backend-v1', os_id=platform,
                          before_hex=before_config.hex(), after_hex=config.hex(),
                          metadata=dict(mode=0o640, uid=0, gid=42), complete=True)
    raw_files[trusted.BACKEND_CONFIG] = config
    raw_files[trusted.BACKEND_RECORD] = json.dumps(backend_record).encode()
    record = dict(purpose=trusted.TRUST_PURPOSE, preparation_script_sha256='a' * 64,
                  fixture_record_sha256=h(raw_files[str(trusted.FIXTURE_RECORD)]), files=files,
                  trust_file_sha256=h(raw_files[trusted.TRUST_FILE]),
                  trust_file_metadata=dict(mode=0o600, uid=0, gid=42),
                  backend=dict(config_sha256=h(config), record_sha256=h(raw_files[trusted.BACKEND_RECORD]),
                               mode=0o640, uid=0, gid=42,
                               sources=['debdb', 'file'] if platform == 'ubuntu' else ['rpmdb', 'file']),
                  native=dict(os_id=platform, package='fapolicyd', version='1.3.6-1', service_gid=42,
                              daemon_sha256=h(b'daemon'), cli_sha256=h(b'cli')))
    transaction = dict(purpose=trusted.TRUST_PURPOSE, complete=record, pending=None)
    marker = dict(baseline_sha256='b' * 64, preparation_sha256='c' * 64,
                  selected_inputs_sha256='d' * 64)
    monkeypatch.setattr(trusted.guest, 'guard', lambda: marker)
    monkeypatch.setattr(trusted.guest, 'enable_diagnostics', Mock())
    monkeypatch.setattr(trusted.guest, 'package_path', lambda:
                        tmp_path / ('package.rpm' if platform == 'fedora' else 'package.deb'))
    monkeypatch.setattr(trusted.grp, 'getgrnam', lambda name: SimpleNamespace(gr_gid=42))
    resolve = trusted.Path.resolve

    def native_alias(path):
        if str(path) in ('/usr/sbin/fapolicyd', '/usr/sbin/fapolicyd-cli'):
            return trusted.Path(tools['cli' if path.name.endswith('-cli') else 'daemon'])
        return resolve(path)

    monkeypatch.setattr(trusted.Path, 'resolve', native_alias)

    def read(path, mode, **options):
        if str(path) == str(trusted.guest.BASELINE):
            return json.dumps(dict(preparation_script_sha256='a' * 64)).encode()
        if str(path) == trusted.TRUST_RECORD:
            return json.dumps(transaction).encode()
        return raw_files[str(path)]

    monkeypatch.setattr(trusted, 'root_file', read)
    run = Mock()

    def command(argv, **options):
        if argv == ['fapolicyd-cli', '--dump-db']:
            return '\n'.join(f'filedb {path} {spec["size"]} {spec["sha256"]}'
                             for path, spec in files.items())
        if argv[1] == '-qf':
            return 'fapolicyd'
        if argv[1] == '-S':
            return 'fapolicyd: ' + argv[2]
        return 'fapolicyd 1.3.6-1'

    run.side_effect = command
    monkeypatch.setattr(trusted.guest, 'run', run)
    return SimpleNamespace(record=record, transaction=transaction, raw_files=raw_files, run=run,
                           tools=tools, backend_record=backend_record)


@pytest.mark.parametrize('fault', [None, 'baseline-binding', 'fixture-record', 'unfinished',
                                  'fragment', 'native-tool', 'native-package', 'trusted-bytes',
                                  'untrusted-bytes', 'native-owner', 'native-alias', 'backend-config',
                                  'backend-receipt', 'backend-incomplete', 'backend-disabled', 'backend-pending',
                                  'service-group', 'missing-service-group', 'trust-group'])
def test_live_consumer_requires_complete_matching_receipt_and_exact_inputs(live_receipt, monkeypatch, fault):
    state = live_receipt
    if fault == 'baseline-binding':
        state.record['preparation_script_sha256'] = 'e' * 64
    elif fault == 'fixture-record':
        state.raw_files[str(trusted.FIXTURE_RECORD)] += b' '
    elif fault == 'unfinished':
        state.transaction['pending'] = state.record
    elif fault == 'fragment':
        state.raw_files[trusted.TRUST_FILE] += b'# changed\n'
    elif fault == 'native-tool':
        state.raw_files[state.tools['cli']] = b'foreign'
    elif fault == 'native-package':
        state.record['native']['version'] = '1.3.6-2'
    elif fault == 'native-owner':
        state.run.side_effect = lambda *args, **kw: 'foreign'
    elif fault == 'service-group':
        monkeypatch.setattr(trusted.grp, 'getgrnam', lambda name: SimpleNamespace(gr_gid=43))
    elif fault == 'missing-service-group':
        monkeypatch.setattr(trusted.grp, 'getgrnam', Mock(side_effect=KeyError('fixed-group')))
    elif fault == 'trust-group':
        state.record['trust_file_metadata']['gid'] = 43
    elif fault == 'native-alias':
        # Only the fixed distribution alias is supported, never an arbitrary
        # native tool reached through a replaced system-folder link.
        state.tools['cli'] = '/foreign/fapolicyd-cli'
    elif fault == 'backend-config':
        state.raw_files[trusted.BACKEND_CONFIG] += b'# changed\n'
    elif fault == 'backend-receipt':
        state.raw_files[trusted.BACKEND_RECORD] += b' '
    elif fault == 'backend-incomplete':
        state.backend_record['complete'] = False
        raw = json.dumps(state.backend_record).encode()
        state.raw_files[trusted.BACKEND_RECORD] = raw
        state.record['backend']['record_sha256'] = hashlib.sha256(raw).hexdigest()
    elif fault == 'backend-disabled':
        config = state.raw_files[trusted.BACKEND_CONFIG].replace(b',file', b'')
        state.raw_files[trusted.BACKEND_CONFIG] = config
        state.record['backend']['config_sha256'] = hashlib.sha256(config).hexdigest()
    elif fault == 'backend-pending':
        original = trusted.os.path.lexists
        monkeypatch.setattr(trusted.os.path, 'lexists',
                            lambda path: str(path) == trusted.BACKEND_PENDING or original(path))
    elif fault in ('trusted-bytes', 'untrusted-bytes'):
        variant = 'trusted-hard' if fault == 'trusted-bytes' else 'command'
        state.raw_files[str(enforcement.native_paths(variant)[0])] = b'foreign'
    if fault:
        with pytest.raises(trusted.guest.GuestError):
            trusted.verify_trust()
    else:
        result = trusted.verify_trust()
        assert result['provenance'] == state.record
        assert result['baseline_sha256'] == 'b' * 64
    assert all(call.args[0][0] in ('dpkg-query', 'rpm', 'fapolicyd-cli') for call in state.run.call_args_list)
    assert all(call.args[0][1] not in ('--file', '--update') for call in state.run.call_args_list)


@pytest.mark.parametrize('fault', [None, 'source', 'runtime', 'mode', 'owner', 'unfinished',
                                  'tool', 'backend', 'missing-db', 'duplicate-db', 'wrong-db',
                                  'source-db', 'trusted-control'])
def test_activity_preflight_reads_exact_prepared_runtime_and_active_trust(live_receipt, monkeypatch, fault):
    import native_fixtures_guest as activity
    from tests.fixtures.native_assets import ACTIVITY_EXECUTABLE, ACTIVITY_PREFIX, GUI_FILES, activity_sources
    state = live_receipt
    targets = (ACTIVITY_EXECUTABLE, *(ACTIVITY_PREFIX + '/' + name for name in GUI_FILES))
    expected = {source: state.record['files'][path]['sha256']
                for source, path in zip(activity_sources(), targets)}
    monkeypatch.setattr(activity, 'activity_root_file',
                        lambda path, mode=0o600, gid=0, **kw:
                        trusted.root_file(path, mode, gid=gid, **kw))
    monkeypatch.setattr(activity.os, 'geteuid', lambda: 0)
    database = [f'filedb {path} {spec["size"]} {spec["sha256"]}'
                for path, spec in state.record['files'].items()]
    if fault == 'source': expected[activity_sources()[0]] = 'f' * 64
    if fault == 'runtime': state.raw_files[targets[1]] += b'changed'
    if fault == 'mode': state.record['files'][targets[1]]['mode'] = 0o755
    if fault == 'owner': state.record['files'][targets[0]]['uid'] = 1001
    if fault == 'unfinished': state.transaction['pending'] = state.record
    if fault == 'tool': state.raw_files[state.tools['cli']] += b'changed'
    if fault == 'backend': state.raw_files[trusted.BACKEND_CONFIG] += b'changed'
    if fault == 'missing-db': database.pop()
    if fault == 'duplicate-db': database.append(database[-1])
    if fault == 'wrong-db': database[-1] = database[-1][:-64] + 'f' * 64
    if fault == 'source-db': database[-1] = database[-1].replace('filedb ', 'rpmdb ', 1)
    if fault == 'trusted-control':
        database.append('filedb /opt/onpc-test-fixtures/Applications/Exact Fixture.AppImage 1 ' + 'a' * 64)
    command = Mock(return_value=SimpleNamespace(stdout=('\n'.join(database) + '\n').encode()))
    monkeypatch.setattr(activity.subprocess, 'run', command)
    if fault:
        with pytest.raises(ValueError): activity.activity_readback(expected)
    else:
        result = activity.activity_readback(expected)
        assert result == {'native_trust': True, 'files': {
            source: {'sha256': expected[source], 'mode': state.record['files'][path]['mode']}
            for source, path in zip(activity_sources(), targets)}}
    assert command.call_count <= 1
    if command.called:
        assert command.call_args.args[0] == [state.tools['cli'], '--dump-db']


@pytest.mark.parametrize('fault', [None, 'child-parent', 'writable-parent', 'runtime-mode',
                                  'runtime-link', 'hardlink'])
def test_activity_root_reader_preserves_strict_root_metadata(tmp_path, private_metadata, monkeypatch, fault):
    import native_fixtures_guest as activity
    monkeypatch.setattr(activity, 'ROOT_DIRECTORY', tmp_path)
    parent = tmp_path / 'activity'
    parent.mkdir(mode=0o755)
    path = parent / 'onpc-test-gui.py'
    path.write_bytes(b'fixed activity runtime')
    path.chmod(0o644)
    if fault == 'runtime-mode': path.chmod(0o666)
    if fault == 'runtime-link':
        path.rename(parent / 'original')
        path.symlink_to(parent / 'original')
    if fault == 'hardlink': os.link(path, parent / 'alias')
    original = activity.os.fstat
    original_stat = activity.os.stat
    target_inode = parent.stat().st_ino

    def metadata(info):
        fields = list(info)
        fields[4] = fields[5] = 0
        # Reader comparisons use the same protected metadata for directory
        # descriptors and entries. Model a replaced ancestor, never chown host.
        if info.st_ino == target_inode:
            if fault == 'child-parent': fields[4] = 1001
            if fault == 'writable-parent': fields[0] |= 0o020
        return os.stat_result(fields)

    monkeypatch.setattr(activity.os, 'fstat', lambda fd: metadata(original(fd)))
    monkeypatch.setattr(activity.os, 'stat', lambda *args, **kw: metadata(original_stat(*args, **kw)))
    if fault:
        with pytest.raises((ValueError, OSError)): activity.activity_root_file(path, 0o644)
    else:
        assert activity.activity_root_file(path, 0o644) == b'fixed activity runtime'


@pytest.fixture
def qualification(tmp_path, monkeypatch):
    (tmp_path / 'results').mkdir()
    (tmp_path / 'results/previous-install.json').write_text(json.dumps({
        'boot': 'before', 'previous_package_sha256': 'a' * 64}))
    monkeypatch.setattr(trusted.guest, 'PAYLOAD', tmp_path)
    monkeypatch.setattr(trusted.guest, 'guard', Mock())
    monkeypatch.setattr(trusted.guest, 'wait_for_boot', Mock())
    monkeypatch.setattr(trusted.guest, 'reboot_cleared', lambda: True)
    monkeypatch.setattr(trusted.guest, 'sha', lambda path: 'a' * 64)
    monkeypatch.setattr(trusted.guest, 'package_path', lambda: tmp_path / 'package.rpm')
    monkeypatch.setattr(trusted.guest, 'KIOSK_CONFINEMENT_STATE', tmp_path / 'absent')
    monkeypatch.setattr(trusted.guest, 'verify_package_files', Mock())
    monkeypatch.setattr(trusted.guest, 'package_identity',
                        lambda path, **kwargs: 'old' if path.name.startswith('previous-') else 'new')
    read_text = trusted.Path.read_text
    monkeypatch.setattr(trusted.Path, 'read_text', lambda path, *a, **kw:
                        'after' if str(path) == '/proc/sys/kernel/random/boot_id' else read_text(path, *a, **kw))
    trust = Mock(return_value={'exact': 'provenance'})
    monkeypatch.setattr(trusted, 'verify_trust', trust)
    monkeypatch.setattr(trusted, 'record_execution_backend', Mock())
    accounts = {'child': 1001, 'other': 1002, 'parent': 1003}
    monkeypatch.setattr(trusted, 'provision_native',
                        lambda variant, *, trusted_variants: accounts.copy())
    monkeypatch.setattr(trusted.pwd, 'getpwnam', lambda name: SimpleNamespace(pw_uid=1004))
    preferences = {'apps': {}, 'parent_control_enabled': False, 'daily_time_limit_minutes': 37}
    calls, launches, rules = [], [], []

    def call(uid, method, signature='()', args=()):
        calls.append((uid, method))
        if method == 'GetPreferences':
            return [json.dumps(preferences) if args[0] == 1001 else '{"unchanged": true}']
        if method == 'SetParentControl':
            preferences['parent_control_enabled'] = True
        elif method == 'SetPreferences':
            preferences.update(json.loads(args[1]))
        return []

    monkeypatch.setattr(trusted, 'call', call)
    monkeypatch.setattr(trusted, 'observe_launch',
                        lambda uid, allowed, *, variant: launches.append((uid, allowed, variant)))
    monkeypatch.setattr(trusted, 'record_rules',
                        lambda stage, uid, blocked, record, *, variant:
                        rules.append((stage, uid, blocked, variant)))
    password = Mock()
    monkeypatch.setattr(trusted, 'FixturePassword', lambda: password)
    caller = Mock()
    caller.receive.return_value = {'result': [True, 'approved']}
    caller.__enter__ = Mock(return_value=caller)
    caller.__exit__ = Mock(return_value=False)
    agent = Mock()
    agent.__enter__ = Mock(return_value=agent)
    agent.__exit__ = Mock(return_value=False)
    monkeypatch.setattr(trusted, 'PersistentCaller', lambda uid: caller)
    monkeypatch.setattr(trusted, 'TextAgent', lambda target: agent)
    return SimpleNamespace(calls=calls, launches=launches, rules=rules, trust=trust,
                           password=password, caller=caller, agent=agent)


def test_old_release_qualification_keeps_all_role_controls_and_real_approval(qualification):
    state = qualification
    record = Mock()
    trusted.qualify(record)
    assert state.launches == [
        (1001, True, 'trusted-hard'), (1002, True, 'trusted-hard'),
        (1001, True, 'trusted-soft'), (1002, True, 'trusted-soft'),
        (1001, False, 'trusted-hard'), (1002, True, 'trusted-hard'),
        (1001, False, 'trusted-soft'), (1002, True, 'trusted-soft'),
        (1001, False, 'trusted-hard'), (1002, True, 'trusted-hard'),
        (1001, True, 'trusted-soft'), (1002, True, 'trusted-soft')]
    assert [(stage, blocked, variant) for stage, uid, blocked, variant in state.rules] == [
        ('unrestricted', False, 'trusted-hard'), ('unrestricted', False, 'trusted-soft'),
        ('strict', True, 'trusted-hard'), ('strict', True, 'trusted-soft'),
        ('approved', True, 'trusted-hard'), ('approved', False, 'trusted-soft')]
    state.password.install.assert_called_once_with(1003)
    state.agent.prompt.assert_called_once_with(1003, 1004)
    state.agent.authenticate.assert_called_once_with(state.password)
    state.caller.send.assert_called_once_with({'kind': 'call', 'method': 'RequestOwnAccess',
                                              'signature': '(uub)', 'args': (1003, 600, True)})
    assert state.trust.call_count == 2
    state.caller.__exit__.assert_called_once()
    state.agent.__exit__.assert_called_once()
    assert state.calls[-1] == (1003, 'GetPreferences')


@pytest.mark.parametrize('fault', ['trust', 'same-boot', 'same-package', 'refused-approval',
                                  'changed-provenance'])
def test_qualification_refuses_invalid_inputs_and_never_drops_a_control(qualification, monkeypatch, fault):
    state = qualification
    if fault == 'trust':
        state.trust.side_effect = trusted.guest.GuestError('native-trust-mismatch')
    elif fault == 'same-boot':
        monkeypatch.setattr(trusted.guest, 'reboot_cleared', lambda: False)
    elif fault == 'same-package':
        monkeypatch.setattr(trusted.guest, 'package_identity', lambda *a, **kw: 'new')
    elif fault == 'refused-approval':
        state.caller.receive.return_value = {'result': [False, 'denied']}
    else:
        state.trust.side_effect = [{'exact': 'provenance'}, {'substituted': 'provenance'}]
    with pytest.raises(trusted.guest.GuestError):
        trusted.qualify(Mock())
    if fault in ('trust', 'same-boot', 'same-package'):
        assert state.calls == [] and state.launches == []
        state.password.install.assert_not_called()
    elif fault == 'refused-approval':
        assert len(state.launches) == 8
        state.agent.__exit__.assert_called_once()
        state.caller.__exit__.assert_called_once()

