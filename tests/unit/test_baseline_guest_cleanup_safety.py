"""Guest preparation adapters only; no libvirt, disks, or host processes used."""
from contextlib import contextmanager
from pathlib import Path
from unittest.mock import Mock

import pytest
import baseline_guest as guest
import prepare_baseline as host
from tests.support.vm_baseline import rig


@pytest.fixture
def preparation(monkeypatch):
    files, links = {}, {}
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
    g.lstatns.side_effect = lambda p: {'st_uid': 0, 'st_nlink': 1,
        'st_mode': (0o40000 if p in directories else 0o100000) | modes.get(p, 0o755)}
    g.write.side_effect = lambda p, data: files.update({p: data})
    g.read_file.side_effect = files.__getitem__
    g.readlink.side_effect = links.__getitem__
    g.ln_s.side_effect = lambda target, p: links.update({p: target})
    g.rm.side_effect = lambda p: (links if p in links else files).pop(p)
    capture = Mock()
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
    assert p.capture.source.domain.create.call_count == 2
    p.capture.source.shutdown.assert_not_called()


def test_preparation_orders_background_apt_jobs_after_its_package_work():
    assert 'Before=display-manager.service apt-daily.service apt-daily-upgrade.service' in guest.SERVICE


@pytest.mark.parametrize('reboot', [False, True])
def test_auto_updates_request_at_most_one_observed_reboot(preparation, monkeypatch, reboot):
    import e2e_watch
    p = preparation
    start = Mock(return_value=Mock())
    monkeypatch.setattr(e2e_watch, 'start', start)
    boots = []
    def boot():
        boots.append(True)
        if len(boots) == 1:
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
    assert len(boots) == start.call_count == 1 + int(reboot)
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
    monkeypatch.setattr(entry.prepare_vm.guest_tools, 'verify_packages', Mock())
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
    assert entry.main([]) == setup_status
    assert update.call_count == int(mode == 'auto' and setup_status == 0)
    assert (root / 'success').exists() == (setup_status == 0)
    assert not (root / 'password').exists()


def test_guest_update_failure_never_marks_success(guest_entry, monkeypatch):
    entry, root = guest_entry
    (root / 'mode').write_text('auto')
    monkeypatch.setattr(entry, 'update_system', Mock(side_effect=RuntimeError('update failed')))
    with pytest.raises(RuntimeError, match='update failed'):
        entry.main([])
    assert not (root / 'success').exists()


def test_auto_guest_records_reboot_before_success(guest_entry, monkeypatch):
    entry, root = guest_entry
    (root / 'mode').write_text('auto')
    monkeypatch.setattr(entry, 'update_system', Mock())
    exists = Path.exists
    monkeypatch.setattr(Path, 'exists', lambda p: True if str(p) == '/run/reboot-required' else exists(p))
    assert entry.main([]) == 0
    assert (root / 'reboot-required').read_text() == 'new-boot-id'
    assert not (root / 'success').exists()


def test_guest_requires_a_different_boot_before_success(guest_entry, monkeypatch):
    entry, root = guest_entry
    (root / 'reboot-required').write_text('new-boot-id')
    assert entry.main(['--verify-reboot']) == 1
    assert not (root / 'success').exists()
    (root / 'reboot-required').write_text('old-boot-id')
    read = Path.read_text
    monkeypatch.setattr(Path, 'read_text', lambda p, *a, **k:
                        '' if str(p) == '/var/lib/dpkg/status' else read(p, *a, **k))
    assert entry.main(['--verify-reboot']) == 0
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
    monkeypatch.setattr(entry.prepare_vm.guest_tools, 'verify_packages', verify)
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
    start = Mock(return_value=observer)
    monkeypatch.setattr(e2e_watch, 'start', start)
    def boot():
        configured = ET.fromstring(p.capture.source.connection.defineXML.call_args.args[0])
        assert configured.findall('devices/graphics')[0].get('type') == 'spice'
        copied = configured.findall('devices/graphics')[1]
        assert copied.attrib == {'type': 'dbus', 'p2p': 'yes'}
        assert copied.find('gl').get('enable') == 'no'
        start.assert_not_called()
        p.boot()
    p.capture.source.domain.create.side_effect = boot
    guest.prepare(p.capture, Mock(), 'fixture-password')
    adapter = start.call_args.args[0]
    assert isinstance(adapter, e2e_watch.DisplayAdapter)
    assert adapter.source is p.capture.source and adapter.domain_id == 15
    observer.close.assert_called_once()


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
    def start(adapter):
        adapter.revalidate()
        domain.XMLDesc.return_value = xml.replace(report, changed)
        if accepted:
            adapter.revalidate()
        else:
            with pytest.raises(host.CaptureError, match='preparation-display-changed'):
                adapter.revalidate()
        return observer
    monkeypatch.setattr(e2e_watch, 'start', start)
    guest.prepare(preparation.capture, Mock(), 'fixture-password')
    observer.close.assert_called_once()


def test_guest_failure_cannot_reuse_success_from_previous_run(preparation):
    p = preparation
    p.files[guest.STAGE + '/success'] = b'success\n'
    p.capture.source.domain.create.side_effect = lambda: p.files.pop(guest.STAGE + '/password')
    with pytest.raises(host.CaptureError, match='guest:preparation-failed'):
        guest.prepare(p.capture, Mock(), 'fixture-password')


def test_guest_failure_reports_only_bounded_diagnostic_tokens(preparation):
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


def test_timeout_requests_shutdown_only_for_the_spawned_instance(preparation, monkeypatch):
    p = preparation
    p.capture.source.snapshot.return_value = ({}, False)
    monkeypatch.setattr(guest.time, 'monotonic', Mock(side_effect=[0, 7501]))
    with pytest.raises(host.CaptureError, match='preparation-timeout'):
        guest.prepare(p.capture, Mock(), 'fixture-password')
    p.capture.source.shutdown.assert_called_once_with(p.capture.revalidate, requested=False)


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
    assert host.main(['--mode', 'manual']) == 1
    tools.assert_not_called()
    source.assert_not_called()
