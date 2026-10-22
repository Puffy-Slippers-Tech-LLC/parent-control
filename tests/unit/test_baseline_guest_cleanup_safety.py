"""Guest preparation adapters only; no libvirt, disks, or host processes used."""
from tests.support.vm_registry import vm_name
from contextlib import contextmanager
from pathlib import Path
import hashlib
import json
import stat
from unittest.mock import Mock, call

import pytest
import baseline_guest as guest
import prepare_baseline as host
from tests.support.vm_baseline import rig


@pytest.fixture
def preparation(monkeypatch):
    import baseline_fixtures
    import baseline_console
    monkeypatch.setattr(baseline_fixtures, 'build_payload', Mock(return_value={}))
    monkeypatch.setattr(baseline_fixtures, 'reconcile', Mock(return_value={
        '/opt/onpc-baseline-assets/test': ('mechanical', 0o755, 'system')}))
    monkeypatch.setattr(baseline_fixtures, 'reconcile_clean', Mock(return_value={}))
    monkeypatch.setattr(baseline_fixtures, 'verify_clean', Mock())
    monkeypatch.setattr(baseline_fixtures, 'reconcile_native_rules', Mock())
    monkeypatch.setattr(baseline_fixtures, 'verify_native_rules', Mock())
    monkeypatch.setattr(baseline_fixtures, 'refresh_clean_compiled', Mock())
    monkeypatch.setattr(baseline_console, 'reconcile', Mock())
    files, links = {}, {}
    files['/etc/os-release'] = b'ID=ubuntu\nVERSION_ID=26.04\n'
    files['/etc/shadow'] = ''.join(f'{account.username}:hash:20000:0:99999:7:::\n'
                                 for account in guest.prepare_vm.IDENTITIES).encode()
    monkeypatch.setattr(guest, 'matches', lambda password, encoded: password == 'fixture-password' and encoded == 'hash')
    directories = {'/', '/var', '/var/lib', '/etc', '/etc/systemd',
                   '/etc/systemd/system', '/etc/systemd/system/multi-user.target.wants'}
    modes = {}
    g = Mock()
    g.exists.side_effect = lambda p: p in files or p in directories or p in links
    g.is_symlink.side_effect = lambda p: p in links
    g.realpath.side_effect = lambda p: links.get(p, p)
    g.mkdir.side_effect = directories.add
    g.chmod.side_effect = lambda mode, p: modes.update({p: mode})
    g.lstatns.side_effect = lambda p: {'st_uid': 0, 'st_gid': 0, 'st_nlink': 1,
        'st_mode': (0o40000 if p in directories else 0o100000) | modes.get(p, 0o755)}
    g.write.side_effect = lambda p, data: files.update({p: data})
    g.read_file.side_effect = files.__getitem__
    g.checksum.side_effect = lambda algorithm, path: hashlib.new(algorithm, files[path]).hexdigest()
    g.readlink.side_effect = links.__getitem__
    g.glob_expand.return_value = []
    g.ln_s.side_effect = lambda target, p: links.update({p: target})
    g.rm.side_effect = lambda p: (links if p in links else files).pop(p)
    def move(source, target):
        files[target] = files.pop(source)
        if source in modes:
            modes[target] = modes.pop(source)
    g.mv.side_effect = move
    capture = Mock()
    capture.watch = None
    capture.state = {'operation': 'a' * 32}
    capture.source.domain.XMLDesc.return_value = '<domain><devices><graphics type="spice"/></devices></domain>'
    capture.source.domain.ID.return_value = 15
    capture.source.snapshot.return_value = ({}, True)
    @contextmanager
    def mounted(api, selected):
        assert selected is capture
        capture.revalidate(off=True)
        yield g
    monkeypatch.setattr(guest, 'mounted', mounted)
    def boot():
        if b'--prepare-native' in files[guest.UNIT]:
            assert guest.STAGE + '/password' not in files
            assert files[guest.STAGE + '/success'] == b''
            assert b'ConditionPathExists=' + guest.STAGE.encode() + b'/mode' in files[guest.UNIT]
            files[guest.STAGE + '/success'] = b'success\n'
            return
        assert files[guest.STAGE + '/password'] == b'fixture-password'
        assert modes[guest.STAGE + '/password'] == 0o600
        assert modes[guest.STAGE] == 0o700
        files.pop(guest.STAGE + '/password')
        files[guest.STAGE + '/success'] = b'success\n'
    capture.source.domain.create.side_effect = boot
    monkeypatch.setattr(guest.time, 'sleep', Mock())
    return Mock(capture=capture, g=g, files=files, links=links, modes=modes, boot=boot)


def test_repeat_stages_only_maintained_code_and_never_the_host_envrc(preparation):
    p = preparation
    for _ in range(2):
        guest.prepare(p.capture, Mock(), 'fixture-password')
        assert guest.UNIT not in p.files and guest.LINK not in p.links
        assert guest.STAGE + '/password' not in p.files
        assert not any(path.endswith('.envrc') for path in p.files)
        assert not any(b'fixture-password' in data for data in p.files.values())
    assert p.capture.source.domain.create.call_count == 4
    p.capture.source.shutdown.assert_not_called()


@pytest.mark.parametrize('os_id', ['ubuntu', 'fedora'])
def test_clean_preparation_never_builds_fixtures_and_removes_shared_module_copy(preparation, os_id):
    import baseline_fixtures
    p = preparation
    if os_id == 'fedora':
        p.files['/etc/os-release'] = b'ID=fedora\nVERSION_ID=44\nVARIANT_ID=workstation\n'
        p.files['/etc/selinux/config'] = b'SELINUX=enforcing\nSELINUXTYPE=targeted\n'
    def environment_after_guest_setup(*args):
        assert p.capture.source.domain.create.call_count == 1
        return {}
    baseline_fixtures.reconcile_clean.side_effect = environment_after_guest_setup
    guest.prepare(p.capture, Mock(), 'fixture-password')
    baseline_fixtures.build_payload.assert_not_called()
    baseline_fixtures.reconcile.assert_not_called()
    baseline_fixtures.reconcile_clean.assert_called_once()
    assert baseline_fixtures.reconcile_native_rules.call_count == int(os_id == 'ubuntu')
    assert baseline_fixtures.verify_native_rules.call_count == int(os_id == 'ubuntu')
    guest.verify_clean_sources(p.g)
    for identity in guest.prepare_vm.IDENTITIES:
        relative = Path(identity.icon_file).relative_to(guest.prepare_vm.CHECKOUT)
        assert p.files[guest.STAGE + '/checkout/' + str(relative)] == Path(identity.icon_file).read_bytes()


@pytest.mark.parametrize('completed_retirement', [False, True])
def test_legacy_native_preflight_precedes_source_retirement_and_all_guest_boots(
        preparation, monkeypatch, completed_retirement):
    import baseline_fixtures
    p = preparation
    p.files['/etc/os-release'] = b'ID=fedora\nVERSION_ID=44\nVARIANT_ID=workstation\n'
    accounts = {identity.username: {'uid': 1000 + index, 'role': identity.role}
                for index, identity in enumerate(guest.prepare_vm.IDENTITIES)}
    marker = guest.prepare_vm.marker_document(
        guest.prepare_vm.GuestIdentity(guest.prepare_vm.HOSTNAME, 'a' * 32, '44', 'kvm', 'fedora'),
        accounts, 'b' * 64)
    marker['schema_version'] = 3
    guest.write(p.g, str(guest.prepare_vm.MARKER), json.dumps(marker).encode())
    guest.write(p.g, baseline_fixtures.RECORD, json.dumps({
        'purpose': baseline_fixtures.CLEAN_PURPOSE if completed_retirement else baseline_fixtures.PURPOSE
    }).encode())
    preflight = Mock(side_effect=ValueError('native compiler ambiguity'))
    monkeypatch.setattr(baseline_fixtures, '_retirement_plan', preflight)
    if completed_retirement:
        baseline_fixtures.refresh_clean_compiled.side_effect = ValueError('native compiler ambiguity')
    sources = Mock()
    monkeypatch.setattr(guest, 'prepare_source_retirement', sources)
    before = dict(p.files)
    with pytest.raises(ValueError, match='native compiler ambiguity'):
        guest.prepare(p.capture, Mock(), 'fixture-password')
    assert p.files == before
    sources.assert_not_called()
    p.capture.source.domain.create.assert_not_called()
    if completed_retirement:
        preflight.assert_not_called()
        baseline_fixtures.refresh_clean_compiled.assert_called_once_with(p.g)
    else:
        preflight.assert_called_once_with(p.g, 'b' * 64, publish=False)


@pytest.mark.parametrize('failure', ['boot', 'readiness'])
def test_native_readiness_failure_cannot_capture_old_success_and_retries(preparation, failure):
    p = preparation
    def boot():
        if b'--prepare-native' not in p.files[guest.UNIT]:
            p.boot()
            return
        assert p.files[guest.STAGE + '/success'] == b''
        if failure == 'boot':
            raise RuntimeError('interrupted native preparation')
        # A failed one-shot powers off without publishing success.
    p.capture.source.domain.create.side_effect = boot
    with pytest.raises((RuntimeError, host.CaptureError), match='native'):
        guest.prepare(p.capture, Mock(), 'fixture-password', mode='auto')
    assert p.files[guest.STAGE + '/success'] == b''
    p.capture.source.domain.create.side_effect = p.boot
    guest.prepare(p.capture, Mock(), 'fixture-password', mode='auto')
    assert guest.UNIT not in p.files and guest.LINK not in p.links
    guest.verify_clean_sources(p.g)


def test_clean_capture_refuses_archived_fixture_sources_without_deleting_the_tree(preparation):
    p = preparation
    root = '/var/tmp/onpc-system-input-snapshot-' + 'a' * 32 + '-' + 'b' * 32
    p.g.mkdir(root)
    p.g.glob_expand.return_value = [root]
    p.g.find.return_value = ['checkout/tests/fixtures/onpc_test_application.c']
    p.files[root + '/checkout/tests/fixtures/onpc_test_application.c'] = b'legacy source'
    before = dict(p.files)
    with pytest.raises(host.CaptureError, match='guest:fixture-input-source-retained'):
        guest.verify_clean_sources(p.g)
    assert p.files == before


def test_clean_baseline_refuses_packed_or_unused_inputs_before_capture(preparation):
    p = preparation
    root = '/var/tmp/onpc-system-input-snapshot-' + 'a' * 32 + '-' + 'b' * 32
    p.g.mkdir(root)
    p.g.glob_expand.return_value = [root]
    p.g.find.return_value = ['fixtures.tar.gz']
    p.files[root + '/fixtures.tar.gz'] = b'opaque previous fixture bytes'
    before = dict(p.files)
    with pytest.raises(host.CaptureError, match='guest:fixture-input-retained'):
        guest.verify_clean_sources(p.g)
    assert p.files == before


@pytest.mark.parametrize('boundary', ['boot', 'source-removal'])
def test_clean_preparation_retry_owns_new_sources_after_staging_and_partial_removal(preparation, boundary):
    p = preparation
    remove = p.g.rm.side_effect
    failed = False
    if boundary == 'boot':
        p.capture.source.domain.create.side_effect = RuntimeError('interrupted preparation')
    else:
        def interrupted_remove(path):
            nonlocal failed
            result = remove(path)
            if path.endswith('/tests/fixtures/native_trust.py') and not failed:
                failed = True
                raise RuntimeError('interrupted preparation')
            return result
        p.g.rm.side_effect = interrupted_remove
    with pytest.raises(RuntimeError, match='interrupted preparation'):
        guest.prepare(p.capture, Mock(), 'fixture-password')
    assert guest.SOURCE_STAGING in p.files
    p.g.rm.side_effect = remove
    p.capture.source.domain.create.side_effect = p.boot
    guest.prepare(p.capture, Mock(), 'fixture-password')
    guest.verify_clean_sources(p.g)


@pytest.mark.parametrize('fault', [None, 'tampered', 'symlink', 'interrupted', 'substituted-retry'])
@pytest.mark.parametrize('os_id,extra_environment', [('ubuntu', False), ('fedora', False), ('fedora', True)])
def test_source_retirement_requires_complete_old_digest_and_preserves_avatar_and_unrelated(
        preparation, monkeypatch, fault, os_id, extra_environment):
    p = preparation
    # This test exercises source retirement itself rather than full preparation.
    sources = guest.prepare_vm.LEGACY_SCRIPT_FILES
    if extra_environment:
        sources = (*sources, 'tests/fixtures/baseline_environment.py')
    for relative in sources:
        guest.write(p.g, guest.STAGE + '/checkout/' + relative,
                    (guest.prepare_vm.CHECKOUT / relative).read_bytes())
    identities = {item.username: {'uid': 1000 + index, 'role': item.role}
                  for index, item in enumerate(guest.prepare_vm.IDENTITIES)}
    marker = guest.prepare_vm.marker_document(
        guest.prepare_vm.GuestIdentity(guest.prepare_vm.HOSTNAME, 'a' * 32,
                                      '26.04' if os_id == 'ubuntu' else '44', 'kvm', os_id),
        identities, guest.prepare_vm.preparation_source_digest(
            lambda relative: (guest.prepare_vm.CHECKOUT / relative).read_bytes(), sources))
    marker['schema_version'] = guest.prepare_vm.MARKER_VERSION if os_id == 'ubuntu' else 3
    if os_id == 'ubuntu':
        marker['guest']['ubuntu_version'] = marker['guest'].pop('version')
        marker['guest'].pop('os_id')
    guest.write(p.g, str(guest.prepare_vm.MARKER), json.dumps(marker).encode())
    p.g.checksum.side_effect = lambda algorithm, path: hashlib.new(algorithm, p.files[path]).hexdigest()
    target = guest.STAGE + '/checkout/tests/fixtures/onpc_test_application.c'
    if fault == 'tampered':
        p.files[target] = b'foreign'
    elif fault == 'symlink':
        p.links[target] = '/unrelated'
    p.files[guest.STAGE + '/avatar.png'] = b'avatar'
    p.files[guest.STAGE + '/unrelated'] = b'preserved'
    if fault in ('tampered', 'symlink'):
        before = dict(p.files)
        with pytest.raises((host.CaptureError, ValueError)):
            guest.prepare_source_retirement(p.g)
        assert p.files == before
        return
    if fault in ('interrupted', 'substituted-retry'):
        remove = p.g.rm.side_effect
        def interrupted(path):
            remove(path)
            raise RuntimeError('interrupted source removal')
        p.g.rm.side_effect = interrupted
        with pytest.raises(RuntimeError, match='interrupted source removal'):
            guest.prepare_source_retirement(p.g)
        assert guest.SOURCE_RETIREMENT in p.files
        p.g.rm.side_effect = remove
        if fault == 'substituted-retry':
            p.files[target] = b'substituted'
            before = dict(p.files)
            with pytest.raises(host.CaptureError, match='source-retirement-substituted'):
                guest.prepare_source_retirement(p.g)
            assert p.files == before
            return
    guest.prepare_source_retirement(p.g)
    assert not any(guest.STAGE + '/checkout/' + relative in p.files
                   for relative in guest.prepare_vm.FIXTURE_SOURCE_FILES)
    assert p.files[guest.STAGE + '/avatar.png'] == b'avatar'
    assert p.files[guest.STAGE + '/unrelated'] == b'preserved'
    guest.prepare_source_retirement(p.g)


@pytest.mark.parametrize('graphics', ['vnc', 'spice'])
def test_clipboard_setup_reconciles_existing_console_and_channel(graphics):
    import xml.etree.ElementTree as ET
    root = ET.fromstring(f'''<domain><devices>
        <graphics type="{graphics}"><clipboard copypaste="no"/></graphics>
        <channel type="unix"><target name="com.redhat.spice.0"/></channel>
        <channel type="unix"><target name="unrelated"/></channel>
        </devices></domain>''')
    guest.configure_clipboard(root)
    first = ET.tostring(root)
    guest.configure_clipboard(root)
    assert ET.tostring(root) == first
    displays = root.findall("devices/graphics[@type='spice']")
    assert len(displays) == 1
    assert displays[0].find('clipboard').attrib == {'copypaste': 'yes'}
    assert displays[0].find('filetransfer').attrib == {'enable': 'no'}
    channels = root.findall('devices/channel')
    assert len(channels) == 2
    assert channels[0].find('target').get('name') == 'unrelated'
    assert channels[1].attrib == {'type': 'spicevmc'}
    assert channels[1].find('target').attrib == {
        'type': 'virtio', 'name': 'com.redhat.spice.0'}


def test_preparation_orders_background_apt_jobs_after_its_package_work():
    assert 'Before=display-manager.service apt-daily.service apt-daily-upgrade.service' in guest.SERVICE


@pytest.mark.parametrize('reboot', [False, True])
def test_auto_updates_request_at_most_one_observed_reboot(preparation, monkeypatch, reboot):
    import e2e_watch
    p = preparation
    attach = Mock()
    monkeypatch.setattr(e2e_watch, 'attach_display', attach)
    boots = []
    def boot():
        boots.append(True)
        if b'--prepare-native' in p.files[guest.UNIT]:
            p.boot()
        elif len(boots) == 1:
            p.boot()
            assert p.files[guest.STAGE + '/mode'] == b'auto'
            if reboot:
                p.files[guest.STAGE + '/success'] = b''
                p.files[guest.STAGE + '/reboot-required'] = b'old-boot-id'
        else:
            assert b'--verify-reboot' in p.files[guest.UNIT]
            assert b'ConditionPathExists=' + guest.STAGE.encode() + b'/reboot-required' in p.files[guest.UNIT]
            p.files[guest.STAGE + '/success'] = b'success\n'
            p.files.pop(guest.STAGE + '/reboot-required')
    p.capture.source.domain.create.side_effect = boot
    guest.prepare(p.capture, Mock(), 'fixture-password', mode='auto')
    assert len(boots) == attach.call_count == 2 + int(reboot)
    assert all(call.args[0] is p.capture for call in attach.call_args_list)
    assert guest.UNIT not in p.files


@pytest.fixture
def guest_entry(tmp_path, monkeypatch):
    import baseline_guest_entry as entry
    root = tmp_path / 'preparation'
    root.mkdir()
    (root / 'checkout').mkdir()
    (root / 'password').write_text('fixture-password')
    (root / 'password').chmod(0o600)
    (root / 'mode').write_text('manual')
    boot = tmp_path / 'boot-id'
    boot.write_text('new-boot-id')
    monkeypatch.setattr(entry, 'ROOT', root)
    monkeypatch.setattr(entry, 'BOOT_ID', boot)
    monkeypatch.setattr(entry.os, 'geteuid', lambda: 0)
    monkeypatch.setattr(entry.os, 'chdir', Mock())
    real_fstat = entry.os.fstat
    def fstat(fd):
        info = real_fstat(fd)
        return Mock(st_mode=info.st_mode, st_nlink=info.st_nlink, st_uid=0)
    monkeypatch.setattr(entry.os, 'fstat', fstat)
    monkeypatch.setattr(entry.prepare_vm, 'CHECKOUT', root / 'checkout')
    monkeypatch.setattr(entry.prepare_vm, 'main', Mock(return_value=0))
    monkeypatch.setattr(entry.prepare_vm, '_read_os_release', lambda path: {'ID': 'ubuntu', 'VERSION_ID': '26.04'})
    monkeypatch.setattr(entry.prepare_vm.guest_tools, 'verify_installed', Mock())
    return entry, root


@pytest.mark.parametrize('mode', ['auto', 'manual'])
@pytest.mark.parametrize('setup_status', [0, 1])
def test_guest_entry_updates_only_after_successful_auto_setup(guest_entry, monkeypatch, mode, setup_status):
    entry, root = guest_entry
    (root / 'mode').write_text(mode)
    entry.prepare_vm.main.return_value = setup_status
    update = Mock()
    monkeypatch.setattr(entry, 'update_system', update)
    # Fixed reboot path is only a read; fixture chooses whether it is present.
    exists = Path.exists
    monkeypatch.setattr(Path, 'exists', lambda p: False if str(p) == '/run/reboot-required' else exists(p))
    assert entry.main(['--vm', vm_name()]) == setup_status
    assert update.call_count == int(mode == 'auto' and setup_status == 0)
    assert (root / 'success').exists() == (setup_status == 0)
    assert not (root / 'password').exists()


def test_guest_update_failure_never_marks_success(guest_entry, monkeypatch):
    entry, root = guest_entry
    (root / 'mode').write_text('auto')
    monkeypatch.setattr(entry, 'update_system', Mock(side_effect=RuntimeError('update failed')))
    with pytest.raises(RuntimeError, match='update failed'):
        entry.main(['--vm', vm_name()])
    assert not (root / 'success').exists()


@pytest.mark.parametrize('failure', [None, 'tabs', 0, 1, 2, 3, 4, 5, 6, 7, 'static', 'inactive', 'empty'])
@pytest.mark.parametrize('os_id', ['ubuntu', 'fedora'])
def test_native_preparation_uses_packaged_service_and_gates_success(
        guest_entry, monkeypatch, failure, os_id):
    import subprocess
    entry, root = guest_entry
    if os_id == 'fedora':
        monkeypatch.setattr(entry.prepare_vm, '_read_os_release', lambda path:
                            {'ID': 'fedora', 'VERSION_ID': '44', 'VARIANT_ID': 'workstation'})
    cli = '/usr/sbin/fapolicyd-cli' if os_id == 'ubuntu' else '/usr/bin/fapolicyd-cli'
    vendor = 'debdb' if os_id == 'ubuntu' else 'rpmdb'
    calls = []
    clock = Mock()
    clock.monotonic.side_effect = range(0, 10000, 10)
    monkeypatch.setattr(entry, 'time', clock)
    def run(command, **kwargs):
        calls.append(command)
        if len(calls) - 1 == failure:
            raise subprocess.CalledProcessError(1, command)
        output = 'active\n'
        if command[-1] == '--dump-db':
            output = '' if failure == 'empty' else vendor + ' /usr/bin/vendor 12 ' + 'a' * 64 + '\n'
            if failure == 'tabs':
                output = output.replace(' ', '\t')
        elif command[1:2] == ['is-enabled']:
            output = 'static\n' if failure == 'static' else 'enabled\n'
        elif command[1:2] == ['is-active'] and failure == 'inactive':
            output = 'inactive\n'
        return Mock(stdout=output)
    monkeypatch.setattr(entry.prepare_vm, 'Runner', lambda: Mock(run=run))
    if failure in (None, 'tabs'):
        assert entry.main(['--prepare-native', '--vm', vm_name()]) == 0
        assert (root / 'success').read_text() == 'success\n'
        first = list(calls)
        # Repeat/update/retry use the same supported idempotent service APIs;
        # no database bytes, trust entries or config are written by this code.
        assert entry.main(['--prepare-native', '--vm', vm_name()]) == 0
        assert calls == first * 2
        assert first == [
            [cli, '--check-config'],
            ['systemctl', 'enable', 'fapolicyd.service'],
            ['systemctl', 'start', 'fapolicyd.service'],
            ['systemctl', 'is-enabled', 'fapolicyd.service'],
            ['systemctl', 'is-active', 'fapolicyd.service'],
            [cli, '--dump-db'],
            [cli, '--check-status'],
            [cli, '--dump-db']]
    else:
        with pytest.raises((subprocess.CalledProcessError, ValueError)):
            entry.main(['--prepare-native', '--vm', vm_name()])
        assert not (root / 'success').exists()
    entry.prepare_vm.main.assert_not_called()
    assert (root / 'password').read_text() == 'fixture-password'


def test_native_preparation_waits_for_database_and_native_initialization(guest_entry, monkeypatch, capsys):
    import subprocess
    entry, root = guest_entry
    missing = subprocess.CalledProcessError(1, ['fapolicyd-cli', '--dump-db'],
        stderr='mdb_env_open failed, error 2 No such file or directory\n')
    vendor = 'debdb /usr/bin/vendor 12 ' + 'a' * 64 + '\n'
    dumps = iter([missing, 'Trust database is empty\n', vendor, vendor * 2])
    events = []
    def run(command, **kwargs):
        events.append(command[-1])
        if command[-1] == '--dump-db':
            value = next(dumps)
            if isinstance(value, Exception):
                raise value
            return Mock(stdout=value)
        if command[-1] == '--check-status':
            assert events.count('--dump-db') == 3
        return Mock(stdout='enabled\n' if command[1:2] == ['is-enabled'] else 'active\n')
    clock = Mock()
    clock.monotonic.side_effect = range(20)
    monkeypatch.setattr(entry, 'time', clock)
    monkeypatch.setattr(entry.prepare_vm, 'Runner', lambda: Mock(run=run))
    assert entry.main(['--prepare-native', '--vm', vm_name()]) == 0
    assert clock.sleep.call_count == 2
    assert events[-2:] == ['--check-status', '--dump-db']
    assert 'database_rows=2 vendor_rows=2' in capsys.readouterr().out
    assert (root / 'success').read_text() == 'success\n'


@pytest.mark.parametrize('os_id', ['ubuntu', 'fedora'])
@pytest.mark.parametrize('outcome', ['success', 'exhausted', 'journal-failure', 'clipped-deadline',
                                    'inactive', 'unknown-output', 'unknown-stderr', 'unknown-exit'])
def test_native_status_readiness_retries_only_exact_report_timeout(
        guest_entry, monkeypatch, capsys, os_id, outcome):
    import subprocess
    entry, root = guest_entry
    if os_id == 'fedora':
        monkeypatch.setattr(entry.prepare_vm, '_read_os_release', lambda path:
                            {'ID': 'fedora', 'VERSION_ID': '44', 'VARIANT_ID': 'workstation'})
    cli = '/usr/sbin/fapolicyd-cli' if os_id == 'ubuntu' else '/usr/bin/fapolicyd-cli'
    vendor = 'debdb' if os_id == 'ubuntu' else 'rpmdb'
    row = vendor + ' /usr/bin/vendor 12 ' + 'a' * 64 + '\n'
    transient = "Can't find fapolicyd: timed out waiting for report\n"
    now = [0.0]
    clock = Mock()
    clock.monotonic.side_effect = lambda: now[0]
    clock.sleep.side_effect = lambda seconds: now.__setitem__(0, now[0] + seconds)
    monkeypatch.setattr(entry, 'time', clock)
    calls, failures = [], []
    status_calls = 0
    successful_handshake = False
    fresh_dump = False
    def run(command, **kwargs):
        nonlocal status_calls, successful_handshake, fresh_dump
        calls.append(command)
        if command[0] == 'journalctl':
            assert command == ['journalctl', '--boot', '--unit=fapolicyd.service', '--no-pager', '--lines=80']
            assert kwargs == {'check': False, 'timeout': 30}
            if outcome == 'journal-failure':
                raise subprocess.CalledProcessError(1, command, output='journal refused')
            return Mock(stdout='bounded native startup diagnostics\n')
        if command[1:2] == ['is-active']:
            if outcome == 'inactive' and status_calls:
                return Mock(stdout='inactive\n')
            return Mock(stdout='active\n')
        if command[-1] == '--dump-db':
            if successful_handshake:
                fresh_dump = True
                assert kwargs['timeout'] == 120
                return Mock(stdout=row * 2)
            return Mock(stdout=row)  # A readable old LMDB does not prove readiness.
        if command[-1] == '--check-status':
            status_calls += 1
            assert calls[-3:-1] == [['systemctl', 'is-active', 'fapolicyd.service'], [cli, '--dump-db']]
            assert 0 < kwargs['timeout'] <= min(60, 180 - now[0])
            if outcome == 'success' and status_calls == 2:
                successful_handshake = True
                return Mock(stdout='native status report\n')
            if outcome == 'clipped-deadline' and kwargs['timeout'] < 26:
                now[0] += kwargs['timeout']
                failure = subprocess.TimeoutExpired(command, kwargs['timeout'])
            else:
                now[0] += min(26, kwargs['timeout'])
                failure = subprocess.CalledProcessError(
                    2 if outcome == 'unknown-exit' else 1, command,
                    output='unexpected report failure\n' if outcome == 'unknown-output' else transient,
                    stderr='unexpected stderr\n' if outcome == 'unknown-stderr' else '')
            failures.append(failure)
            raise failure
        return Mock(stdout='enabled\n' if command[1:2] == ['is-enabled'] else '')
    monkeypatch.setattr(entry.prepare_vm, 'Runner', lambda: Mock(run=run))
    if outcome == 'success':
        assert entry.main(['--prepare-native', '--vm', vm_name()]) == 0
        assert status_calls == 2 and clock.sleep.call_count == 1
        assert fresh_dump and calls[-1] == [cli, '--dump-db']
        assert (root / 'success').read_text() == 'success\n'
        assert 'database_rows=2 vendor_rows=2' in capsys.readouterr().out
    else:
        with pytest.raises((subprocess.SubprocessError, ValueError)) as raised:
            entry.main(['--prepare-native', '--vm', vm_name()])
        assert not fresh_dump and not (root / 'success').exists()
        if outcome.startswith('unknown'):
            assert raised.value is failures[0]
            assert status_calls == 1 and clock.sleep.call_count == 0
        elif outcome == 'inactive':
            assert 'native-not-ready' in str(raised.value)
            assert status_calls == 1
        else:
            assert now[0] == 180
            assert raised.value is failures[-1]
            assert status_calls > 1
            output = capsys.readouterr().out
            assert 'native:readiness-timeout' in output
            assert ('native:journal-unavailable' if outcome == 'journal-failure'
                    else 'bounded native startup diagnostics') in output


def test_native_preparation_failure_retains_both_diagnostic_streams(guest_entry, monkeypatch, capsys):
    import subprocess
    entry, root = guest_entry
    failure = subprocess.CalledProcessError(1, ['fapolicyd-cli', '--check-status'],
        output="Can't find fapolicyd: timed out waiting for report\n", stderr='native error\n')
    monkeypatch.setattr(entry, 'prepare_native', Mock(side_effect=failure))
    with pytest.raises(subprocess.CalledProcessError):
        entry.main(['--prepare-native', '--vm', vm_name()])
    captured = capsys.readouterr()
    assert failure.stdout in captured.out
    assert failure.stderr in captured.err
    assert not (root / 'success').exists()


def test_auto_guest_records_reboot_before_success(guest_entry, monkeypatch):
    entry, root = guest_entry
    (root / 'mode').write_text('auto')
    monkeypatch.setattr(entry, 'update_system', Mock())
    exists = Path.exists
    monkeypatch.setattr(Path, 'exists', lambda p: True if str(p) == '/run/reboot-required' else exists(p))
    assert entry.main(['--vm', vm_name()]) == 0
    assert (root / 'reboot-required').read_text() == 'new-boot-id'
    assert not (root / 'success').exists()


def test_guest_requires_a_different_boot_before_success(guest_entry, monkeypatch):
    entry, root = guest_entry
    (root / 'reboot-required').write_text('new-boot-id')
    assert entry.main(['--verify-reboot', '--vm', vm_name()]) == 1
    assert not (root / 'success').exists()
    (root / 'reboot-required').write_text('old-boot-id')
    read = Path.read_text
    monkeypatch.setattr(Path, 'read_text', lambda p, *a, **k:
                        '' if str(p) == '/var/lib/dpkg/status' else read(p, *a, **k))
    assert entry.main(['--verify-reboot', '--vm', vm_name()]) == 0
    assert (root / 'success').read_text() == 'success\n'
    assert not (root / 'reboot-required').exists()


@pytest.mark.parametrize('failure', [None, 0, 1, 2])
def test_updates_use_bounded_noninteractive_apt_and_stop_on_failure(monkeypatch, failure):
    import baseline_guest_entry as entry
    import subprocess
    calls = []
    def run(command, **kwargs):
        calls.append(command)
        assert kwargs['check'] and kwargs['timeout'] == 3600
        assert kwargs['env']['DEBIAN_FRONTEND'] == 'noninteractive'
        assert kwargs['stdin'] == subprocess.DEVNULL
        if len(calls) - 1 == failure:
            raise subprocess.CalledProcessError(1, command)
    monkeypatch.setattr(entry.subprocess, 'run', run)
    monkeypatch.setattr(Path, 'read_text', lambda *_: '')
    verify = Mock()
    monkeypatch.setattr(entry.prepare_vm.guest_tools, 'verify_installed', verify)
    if failure is not None:
        with pytest.raises(subprocess.CalledProcessError):
            entry.update_system()
        assert len(calls) == failure + 1
        verify.assert_not_called()
    else:
        entry.update_system()
        assert [command[-1] for command in calls] == ['update', 'dist-upgrade', 'check']
        assert 'APT::Update::Error-Mode=any' in calls[0]
        assert 'DPkg::Lock::Timeout=300' in calls[1]
        verify.assert_called_once()
        # No freshness cache: a second invocation runs the same update steps.
        entry.update_system()
        assert calls[:3] == calls[3:]
        assert verify.call_count == 2


def test_baseline_boot_uses_shared_endpoint_and_collector(preparation, monkeypatch):
    import e2e_watch
    import xml.etree.ElementTree as ET
    p = preparation
    observer = Mock()
    p.capture.watch = observer
    attach = Mock()
    monkeypatch.setattr(e2e_watch, 'attach_display', attach)
    def boot():
        configured = ET.fromstring(p.capture.source.connection.defineXML.call_args.args[0])
        assert configured.findall('devices/graphics')[0].get('type') == 'spice'
        assert configured.find('devices/graphics/clipboard').attrib == {'copypaste': 'yes'}
        assert configured.find('devices/graphics/filetransfer').attrib == {'enable': 'no'}
        assert configured.find('devices/channel').attrib == {'type': 'spicevmc'}
        assert configured.find('devices/channel/target').attrib == {
            'type': 'virtio', 'name': 'com.redhat.spice.0'}
        copied = configured.findall('devices/graphics')[1]
        assert copied.attrib == {'type': 'dbus', 'p2p': 'yes'}
        assert copied.find('gl').get('enable') == 'no'
        assert attach.call_count == p.capture.source.domain.create.call_count - 1
        p.boot()
    xml = p.capture.source.domain.XMLDesc.return_value
    p.capture.source.domain.XMLDesc.return_value = xml.replace('<devices>',
        '<cpu mode="host-passthrough" migratable="off"/><devices><memballoon model="virtio"/>')
    p.capture.source.domain.create.side_effect = boot
    guest.prepare(p.capture, Mock(), 'fixture-password')
    assert attach.call_args.args[0] is p.capture
    adapter = attach.call_args.args[1]
    assert isinstance(adapter, e2e_watch.DisplayAdapter)
    assert adapter.source is p.capture.source and adapter.domain_id == 15
    observer.close.assert_not_called()  # Capture.run owns final lease cleanup.
    cpu = ET.fromstring(p.capture.source.connection.defineXML.call_args.args[0]).find('cpu')
    assert cpu.get('migratable') == 'on'
    assert cpu.find("feature[@name='invtsc']").get('policy') == 'disable'
    configured = ET.fromstring(p.capture.source.connection.defineXML.call_args.args[0])
    assert configured.find('devices/memballoon').get('freePageReporting') == 'on'


@pytest.mark.parametrize('model', ['virtio', 'virtio-transitional', 'virtio-non-transitional', 'none'])
def test_memory_reporting_preserves_memory_allocation_and_device_identity(model):
    import xml.etree.ElementTree as ET
    root = ET.fromstring('<domain><memory>12288000</memory><currentMemory>6144000</currentMemory>'
        f'<devices><memballoon model="{model}"><address slot="5"/></memballoon></devices></domain>')
    guest.configure_snapshot_memory(root)
    assert root.findtext('memory') == '12288000'
    assert root.findtext('currentMemory') == '6144000'
    assert root.find('devices/memballoon/address').get('slot') == '5'
    assert root.find('devices/memballoon').get('freePageReporting') == (
        None if model == 'none' else 'on')


@pytest.mark.parametrize('changed,accepted', [
    ('<currentMemory unit="KiB">512</currentMemory>', True),
    ('<currentMemory unit="MiB">1024</currentMemory>', False),
    ('<currentMemory unit="KiB">1024</currentMemory><devices><disk/></devices>', False),
])
def test_baseline_display_ignores_only_live_memory_report(preparation, monkeypatch, changed, accepted):
    import e2e_watch
    domain = preparation.capture.source.domain
    report = '<currentMemory unit="KiB">1024</currentMemory>'
    xml = '<domain>' + report + '<devices><graphics type="spice"/></devices></domain>'
    domain.XMLDesc.return_value = xml
    observer = Mock()
    preparation.capture.watch = observer
    def attach(owner, adapter):
        assert owner is preparation.capture
        adapter.revalidate()
        domain.XMLDesc.return_value = xml.replace(report, changed)
        if accepted:
            adapter.revalidate()
        else:
            with pytest.raises(host.CaptureError, match='preparation-display-changed'):
                adapter.revalidate()
        # Each separate boot starts with its own unchanged fake definition.
        domain.XMLDesc.return_value = xml
    monkeypatch.setattr(e2e_watch, 'attach_display', attach)
    guest.prepare(preparation.capture, Mock(), 'fixture-password')
    observer.close.assert_not_called()


def test_guest_failure_cannot_reuse_success_from_previous_run(preparation):
    p = preparation
    p.files[guest.STAGE + '/success'] = b'success\n'
    p.capture.source.domain.create.side_effect = lambda: p.files.pop(guest.STAGE + '/password')
    with pytest.raises(host.CaptureError, match='guest:preparation-failed'):
        guest.prepare(p.capture, Mock(), 'fixture-password')


@pytest.fixture
def failure_retention(tmp_path, monkeypatch):
    state = Mock(active=False, allocated=False, fail=None, artifact=tmp_path / 'evidence' / 'preparation.log')
    @contextmanager
    def session():
        if state.fail == 'session':
            raise RuntimeError('private retention failure fixture-password')
        state.active = True
        try:
            yield
            if state.fail == 'finalize':
                raise RuntimeError('private retention failure fixture-password')
        finally:
            state.active = False
    def allocate(factory, **options):
        assert state.active and not state.allocated
        assert factory is guest.tempfile.mkdtemp
        assert options == {'prefix': 'onpc-baseline-preparation-failure-'}
        if state.fail == 'allocate':
            raise RuntimeError('private retention failure fixture-password')
        state.artifact.parent.mkdir(mode=0o700)
        assert not list(state.artifact.parent.iterdir())
        state.allocated = True
        return str(state.artifact.parent)
    original_open = guest.os.open
    def open_file(path, flags, mode):
        assert state.active and state.allocated
        assert path == state.artifact
        assert flags == guest.os.O_WRONLY | guest.os.O_CREAT | guest.os.O_EXCL
        assert mode == 0o600
        if state.fail == 'write':
            raise OSError('private retention failure fixture-password')
        return original_open(path, flags, mode)
    monkeypatch.setattr(guest, 'recovery_session', session)
    monkeypatch.setattr(guest, 'allocate', allocate)
    monkeypatch.setattr(guest.os, 'open', open_file)
    return state


def test_guest_failure_reports_only_bounded_diagnostic_tokens(preparation, failure_retention, capsys):
    p = preparation
    log = b'private fixture-password\nprepare-vm: [stage:guard] private\nprepare-vm: [guard:os] private\n'
    p.files[guest.STAGE + '/preparation.log'] = log
    p.g.filesize.return_value = len(log)
    p.g.pread.return_value = log
    p.capture.source.domain.create.side_effect = lambda: p.files.pop(guest.STAGE + '/password')
    with pytest.raises(host.CaptureError) as caught:
        guest.prepare(p.capture, Mock(), 'fixture-password')
    assert 'diagnostics:stage:guard,guard:os' in str(caught.value)
    assert 'private' not in str(caught.value) and 'fixture-password' not in str(caught.value)
    p.g.pread.assert_called_once_with(guest.STAGE + '/preparation.log', len(log), 0)
    assert '; artifact:' + str(failure_retention.artifact) in str(caught.value)
    assert failure_retention.artifact.read_bytes() == log
    assert stat.S_IMODE(failure_retention.artifact.stat().st_mode) == 0o600
    assert not failure_retention.active
    output = capsys.readouterr()
    assert 'private' not in output.out + output.err
    assert 'fixture-password' not in output.out + output.err


def test_preparation_failure_retains_only_the_last_16_kib(preparation, failure_retention):
    p = preparation
    log = b'old excluded data' + b'x' * 16384
    path = guest.STAGE + '/preparation.log'
    p.files[path] = log
    p.g.filesize.return_value = len(log)
    p.g.pread.return_value = log[-16384:]
    assert guest.preparation_failure(p.g) == 'no-stage; artifact:' + str(failure_retention.artifact)
    p.g.pread.assert_called_once_with(path, 16384, len(log) - 16384)
    assert failure_retention.artifact.read_bytes() == log[-16384:]


def test_missing_preparation_log_keeps_original_failure(preparation, failure_retention):
    assert guest.preparation_failure(preparation.g) == 'no-log; inspect guest preparation.log'
    preparation.g.pread.assert_not_called()
    assert not failure_retention.allocated


@pytest.mark.parametrize('unsafe', ['symlink', 'ancestor-link', 'directory', 'owner', 'hardlink'])
def test_unsafe_preparation_log_is_never_read_or_retained(preparation, failure_retention, unsafe):
    p = preparation
    path = guest.STAGE + '/preparation.log'
    p.files[path] = b'private fixture-password'
    original_stat = p.g.lstatns.side_effect
    def info(candidate):
        result = original_stat(candidate)
        if candidate == path:
            if unsafe == 'directory':
                result['st_mode'] = 0o40700
            elif unsafe == 'owner':
                result['st_uid'] = 1000
            elif unsafe == 'hardlink':
                result['st_nlink'] = 2
        return result
    p.g.lstatns.side_effect = info
    if unsafe == 'symlink':
        p.files.pop(path)
        p.links[path] = '/etc/shadow'
    elif unsafe == 'ancestor-link':
        p.g.realpath.side_effect = lambda candidate: '/elsewhere/preparation.log' if candidate == path else candidate
    assert guest.preparation_failure(p.g) == 'unsafe-log; inspect guest preparation.log'
    p.g.filesize.assert_not_called()
    p.g.pread.assert_not_called()
    p.g.read_file.assert_not_called()
    assert not failure_retention.allocated


@pytest.mark.parametrize('failure', ['session', 'allocate', 'write', 'finalize'])
def test_retention_failure_preserves_preparation_failure(preparation, failure_retention, capsys, failure):
    p = preparation
    log = b'prepare-vm: [guard:os] private fixture-password\n'
    p.files[guest.STAGE + '/preparation.log'] = log
    p.g.filesize.return_value = len(log)
    p.g.pread.return_value = log
    p.capture.source.domain.create.side_effect = lambda: p.files.pop(guest.STAGE + '/password')
    failure_retention.fail = failure
    with pytest.raises(host.CaptureError) as caught:
        guest.prepare(p.capture, Mock(), 'fixture-password')
    assert str(caught.value) == ('guest:preparation-failed; diagnostics:guard:os; '
                                 'inspect guest preparation.log; retention:failed')
    assert not failure_retention.active
    output = capsys.readouterr()
    assert 'private' not in output.out + output.err
    assert 'fixture-password' not in output.out + output.err


def test_preparation_log_read_failure_preserves_failure_category(preparation, failure_retention):
    p = preparation
    p.files[guest.STAGE + '/preparation.log'] = b'private'
    p.g.filesize.side_effect = RuntimeError('private fixture-password')
    assert guest.preparation_failure(p.g) == 'log-read-failed; inspect guest preparation.log'
    p.g.pread.assert_not_called()
    assert not failure_retention.allocated


def test_guard_failure_prevents_staging_and_boot(preparation):
    p = preparation
    p.capture.revalidate.side_effect = host.CaptureError('guard:changed')
    with pytest.raises(host.CaptureError, match='guard:changed'):
        guest.prepare(p.capture, Mock(), 'fixture-password')
    p.g.write.assert_not_called()
    p.capture.source.domain.create.assert_not_called()


def test_symlinked_staging_cannot_overwrite_unrelated_files(preparation):
    p = preparation
    p.links[guest.STAGE] = '/unrelated'
    with pytest.raises(host.CaptureError, match='preparation-directory'):
        guest.prepare(p.capture, Mock(), 'fixture-password')
    p.g.write.assert_not_called()
    p.capture.source.domain.create.assert_not_called()


def test_replaced_running_instance_is_never_stopped(preparation):
    p = preparation
    p.capture.source.snapshot.return_value = ({}, False)
    p.capture.source.domain.ID.side_effect = [15, 16, 16]
    with pytest.raises(host.CaptureError, match='instance-changed'):
        guest.prepare(p.capture, Mock(), 'fixture-password')
    p.capture.source.shutdown.assert_not_called()


def test_timeout_preserves_the_recorded_pre_ssh_instance_for_service_owned_shutdown(preparation, monkeypatch):
    p = preparation
    p.capture.source.snapshot.return_value = ({}, False)
    monkeypatch.setattr(guest.time, 'monotonic', Mock(side_effect=[0, 7501]))
    with pytest.raises(host.CaptureError, match='preparation-timeout'):
        guest.prepare(p.capture, Mock(), 'fixture-password')
    p.capture.source.domain.create.assert_called_once_with()
    p.capture.source.domain.ID.assert_called_with()
    p.capture.source.shutdown.assert_not_called()
    p.capture.source.domain.destroyFlags.assert_not_called()
    assert 'SuccessAction=poweroff' in guest.SERVICE and 'FailureAction=poweroff' in guest.SERVICE


def test_capture_prepares_before_hashing_inspection_and_snapshot_and_retries(rig):
    rig.source.off = True
    prepare = Mock(side_effect=host.CaptureError('guest:failed'))
    capture = rig.capture()
    capture.prepare_guest = prepare
    with pytest.raises(host.CaptureError, match='guest:failed'):
        capture.run(refresh=True)
    assert not rig.source.creations
    rig.inspect.assert_not_called()
    prepare.side_effect = lambda held: rig.top.write_bytes(b'new prepared guest')
    observed = rig.inspect.return_value
    def inspect(*_args):
        assert rig.top.read_bytes() == b'new prepared guest'
        return observed
    rig.inspect.side_effect = inspect
    capture = rig.capture()
    capture.prepare_guest = prepare
    capture.run(refresh=True)
    assert capture.state['phase'] == 'finalized'
    assert len(rig.source.creations) == 1


def test_missing_password_precedes_any_host_dependency_or_vm_access(monkeypatch):
    monkeypatch.setattr('test_account_password.read_password', Mock(side_effect=ValueError('TEST_ACCOUNT_PASSWORD missing')))
    tools, source = Mock(), Mock()
    monkeypatch.setattr(host.shutil, 'which', tools)
    monkeypatch.setattr(host, 'LibvirtSource', source)
    assert host.main(['--mode', 'manual', '--vm', vm_name()]) == 1
    tools.assert_not_called()
    source.assert_not_called()


@pytest.mark.parametrize('appliance_support', [False, True])
def test_fedora_staging_labels_owned_paths_without_weakening_selinux(preparation, appliance_support):
    p = preparation
    p.files['/etc/os-release'] = b'ID=fedora\nVERSION_ID=44\nVARIANT_ID=workstation\n'
    p.files['/etc/selinux/config'] = b'SELINUX=enforcing\nSELINUXTYPE=targeted\n'
    p.g.feature_available.return_value = appliance_support
    p.g.is_file.return_value = True
    guest.prepare(p.capture, Mock(), 'fixture-password')
    assert p.g.feature_available.call_args_list == [call(['selinuxrelabel'])] * 3
    policy = '/etc/selinux/targeted/contexts/files/file_contexts'
    groups = [[guest.STAGE, guest.UNIT, guest.LINK], [],
              [guest.STAGE, guest.UNIT, guest.LINK]]
    if appliance_support:
        assert p.g.setfiles.call_args_list == [call(policy, paths) for paths in groups]
        p.g.command.assert_not_called()
    else:
        assert p.g.command.call_args_list == [
            call(['/usr/sbin/setfiles', '-m', policy, *paths]) for paths in groups]
        p.g.setfiles.assert_not_called()
    assert p.files['/etc/selinux/config'] == b'SELINUX=enforcing\nSELINUXTYPE=targeted\n'


@pytest.mark.parametrize('missing_tool', [False, True])
def test_fedora_relabel_failure_prevents_boot_and_hides_guest_data(preparation, missing_tool):
    p = preparation
    p.files['/etc/os-release'] = b'ID=fedora\nVERSION_ID=44\nVARIANT_ID=workstation\n'
    p.files['/etc/selinux/config'] = b'SELINUX=enforcing\nSELINUXTYPE=targeted\n'
    p.g.feature_available.return_value = False
    p.g.is_file.return_value = not missing_tool
    p.g.command.side_effect = RuntimeError('private guest data fixture-password')
    code = 'selinux-setfiles-missing' if missing_tool else 'selinux-relabel-failed'
    with pytest.raises(host.CaptureError, match=code) as error:
        guest.prepare(p.capture, Mock(), 'fixture-password')
    assert 'private guest data' not in str(error.value)
    assert 'fixture-password' not in str(error.value)
    assert p.g.command.call_count == int(not missing_tool)
    p.capture.source.domain.create.assert_not_called()


def test_fedora_manual_entry_does_not_update_and_auto_requires_a_new_boot(guest_entry, monkeypatch):
    entry, root = guest_entry
    monkeypatch.setattr(entry.prepare_vm, '_read_os_release', lambda path:
                        {'ID': 'fedora', 'VERSION_ID': '44', 'VARIANT_ID': 'workstation'})
    update = Mock()
    monkeypatch.setattr(entry, 'update_system', update)
    assert entry.main(['--vm', vm_name(1)]) == 0
    update.assert_not_called()
    (root / 'success').unlink()
    (root / 'password').write_text('fixture-password')
    (root / 'password').chmod(0o600)
    (root / 'mode').write_text('auto')
    assert entry.main(['--vm', vm_name(1)]) == 0
    update.assert_called_once_with('fedora')
    assert (root / 'reboot-required').read_text() == 'new-boot-id'
    assert not (root / 'success').exists()


def test_fedora_updates_use_dnf_and_verify_rpm_inventory(monkeypatch):
    import baseline_guest_entry as entry
    run, verify = Mock(), Mock()
    monkeypatch.setattr(entry.subprocess, 'run', run)
    monkeypatch.setattr(entry.prepare_vm.guest_tools, 'verify_installed', verify)
    entry.update_system('fedora')
    assert [call.args[0] for call in run.call_args_list] == [
        ['dnf5', '--refresh', '-y', 'upgrade'], ['dnf5', 'check']]
    assert all(call.kwargs['check'] and call.kwargs['timeout'] == 3600 for call in run.call_args_list)
    assert verify.call_args.args == ('fedora',)
