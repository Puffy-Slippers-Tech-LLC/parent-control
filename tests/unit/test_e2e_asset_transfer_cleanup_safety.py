"""Transfer failure cannot start a journey, repeat provisioning, or own cleanup."""

import builtins
import hashlib
import inspect
import json
import os
from pathlib import Path, PurePosixPath
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

import provenance
from tests.support.e2e_provenance import source, assets, lease
from tests.support.e2e_transfer import GuestFiles
import asset_transfer as transfer


@pytest.fixture(params=('deb', 'rpm'))
def attempt(tmp_path, source, assets, lease, request):
    if request.param == 'rpm':
        (assets / 'package.deb').rename(assets / 'package.rpm')
        manifest_path = assets / 'artifact-manifest.json'
        manifest = json.loads(manifest_path.read_text())
        manifest['artifacts']['package']['path'] = 'package.rpm'
        manifest_path.write_text(json.dumps(manifest))
        lease.capture.state['guest'] = {'os_id': 'fedora', 'version': '44', 'variant_id': 'workstation'}
    (assets / 'delivery with spaces').mkdir()
    (assets / 'delivery with spaces/file.bin').write_bytes(b'nonsecret asset\x00bytes')
    files = {p.relative_to(assets).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest()
             for p in assets.rglob('*') if p.is_file()}
    (assets / 'transfer-sha256.json').write_text(json.dumps(files))
    lease.state.update(phase='isolated', domain_id=None)
    lease.capture.state['source'] = {'layout': {'disk': '/recorded-disk'}}
    lease.state['baseline_sha256'] = provenance.digest(lease.capture.state)
    verified = provenance.VerifiedInputs(root=source, assets=assets, lease=lease)
    (tmp_path / 'guest/var/lib').mkdir(parents=True)
    guest = GuestFiles(tmp_path / 'guest')
    api = SimpleNamespace(GuestFS=Mock(return_value=guest))
    return transfer.AssetTransfer(verified), lease, guest, api


def test_real_staged_bytes_copied_before_readonly_observation(attempt):
    control, lease, guest, api = attempt
    receipt = control.provision(lease, api)
    assert guest.closed and guest.uploads == receipt['files']
    lease.guard.assert_any_call(off=True)
    assert receipt['sha256'] == provenance.digest(control.verified.asset_files)
    for name, expected in control.verified.asset_files.items():
        assert guest.checksum('sha256', transfer.DESTINATION + '/' + name) == expected
    vm = Mock()
    vm.read.return_value = receipt
    assert control.observe(vm) == receipt
    assert vm.method_calls == [('read', ('assets',), {})]
    with pytest.raises(transfer.EvidenceError, match='already-attempted'):
        control.provision(lease, api)
    assert api.GuestFS.call_count == 1


def test_inventory_api_prefix_is_explicit_and_diagnostic_excludes_paths(attempt, capsys):
    control, lease, guest, api = attempt
    control.provision(lease, api)
    relative = guest.find(transfer.DESTINATION + '/')
    assert guest.find(transfer.DESTINATION) == ['/' + name for name in relative]
    output = capsys.readouterr().err
    assert 'e2e:asset-tree-observed expected_entries=' in output
    assert 'observed_sha256=' in output
    assert 'delivery with spaces' not in output


@pytest.mark.parametrize('fault', ['assets', 'phase', 'running', 'lease',
                                  'corrupt', 'existing', 'symlink', 'interrupt', 'extra', 'late-assets'])
def test_refusals_latch_and_leave_restoration_to_outer_lease(attempt, fault):
    control, lease, guest, api = attempt
    selected_lease = lease
    if fault == 'assets':
        (control.verified.assets / provenance.package_filename(control.verified.asset_files)).write_bytes(b'changed')
    elif fault == 'phase':
        lease.state['phase'] = 'running'
    elif fault == 'running':
        lease.state['domain_id'] = 12
    elif fault == 'lease':
        selected_lease = Mock()
    elif fault == 'corrupt':
        guest.corrupt = True
    elif fault == 'existing':
        guest.path(transfer.DESTINATION).mkdir()
    elif fault == 'symlink':
        guest.path(transfer.DESTINATION).symlink_to('/nonexistent')
    elif fault == 'interrupt':
        guest.upload = Mock(side_effect=KeyboardInterrupt('private-canary'))
    elif fault == 'extra':
        original = guest.find
        guest.find = lambda name: original(name) + ['unexpected-file']
    elif fault == 'late-assets':
        original = guest.sync
        def sync():
            original()
            (control.verified.assets / provenance.package_filename(control.verified.asset_files)).write_bytes(b'late-change')
        guest.sync = sync
    with pytest.raises(BaseException):
        control.provision(selected_lease, api)
    if fault in ('assets', 'phase', 'running', 'lease'):
        api.GuestFS.assert_not_called()
    else:
        assert guest.closed
    with pytest.raises(transfer.EvidenceError, match='already-attempted'):
        control.provision(lease, api)
    vm = Mock()
    with pytest.raises(transfer.EvidenceError, match='verified-provisioning-required'):
        control.observe(vm)
    vm.read.assert_not_called()


@pytest.mark.parametrize('fault', ['inventory', 'package-alias'])
def test_internally_consistent_staging_still_requires_correct_delivery_manifest(attempt, fault):
    control, lease, guest, api = attempt
    assets = control.verified.assets
    package = assets / provenance.package_filename(control.verified.asset_files)
    if fault == 'inventory':
        (assets / 'transfer-sha256.json').write_text('{}')
    else:
        original = assets / ('original' + package.suffix)
        original.write_bytes(package.read_bytes())
        manifest_path = assets / 'artifact-manifest.json'
        manifest = json.loads(manifest_path.read_text())
        manifest['artifacts']['package']['path'] = original.name
        manifest_path.write_text(json.dumps(manifest))
        package.write_bytes(b'wrong alias')
        (assets / 'transfer-sha256.json').write_text(json.dumps({
            p.relative_to(assets).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest()
            for p in assets.rglob('*') if p.is_file() and p.name != 'transfer-sha256.json'}))
    with pytest.raises(transfer.EvidenceError, match='inventory-mismatch|package-alias-mismatch'):
        verified = provenance.VerifiedInputs(root=control.verified.root, assets=assets, lease=lease)
        transfer.AssetTransfer(verified).provision(lease, api)
    api.GuestFS.assert_not_called()


def test_booted_corruption_cannot_be_cleared_by_a_later_good_reply(attempt):
    control, lease, guest, api = attempt
    receipt = control.provision(lease, api)
    vm = Mock()
    vm.read.return_value = {'files': 0, 'sha256': 'forged'}
    with pytest.raises(transfer.EvidenceError, match='booted-assets-mismatch'):
        control.observe(vm)
    vm.read.return_value = receipt
    with pytest.raises(transfer.EvidenceError, match='verified-provisioning-required'):
        control.observe(vm)
    assert vm.read.call_count == 1


@pytest.mark.parametrize('error', [transfer.EvidenceError('private-canary'),
                                 OSError('private-canary'), KeyboardInterrupt('private-canary'),
                                 transfer.EvidenceError('transfer:source-changed')])
def test_transfer_failure_diagnostic_is_finite_and_private(attempt, capsys, error):
    control, lease, guest, api = attempt
    guest.upload = Mock(side_effect=error)
    with pytest.raises(type(error)):
        control.provision(lease, api)
    output = capsys.readouterr().err
    expected = 'transfer:source-changed' if str(error) == 'transfer:source-changed' else (
        'transfer:provisioning-failed')
    assert 'e2e:asset-transfer-rejected code=' + expected in output
    assert 'private-canary' not in output
    assert guest.closed
    with pytest.raises(transfer.EvidenceError, match='already-attempted'):
        control.provision(lease, api)


def execute_observation(guest, capsys, *, wrong_owner=False):
    """Run the exact guest probe over real copied bytes without root or a VM.

    Only map the fixed guest root and root ownership onto the unprivileged
    fixture. Traversal, file kinds, permissions, link counts and hashes are real.
    """
    class GuestPath(type(guest.root)):
        def lstat(self):
            info = super().lstat()
            return SimpleNamespace(st_uid=1 if wrong_owner else 0, st_gid=0,
                                   st_mode=info.st_mode, st_nlink=info.st_nlink)

    def imported(name, *args, **kwargs):
        if name == 'pathlib':
            return SimpleNamespace(Path=lambda value: GuestPath(guest.path(value)),
                                   PurePosixPath=PurePosixPath)
        return builtins.__import__(name, *args, **kwargs)

    capsys.readouterr()
    exec(compile(transfer.OBSERVE, '<fixed-asset-observation>', 'exec'),
         {'__builtins__': {**vars(builtins), '__import__': imported}})
    return json.loads(capsys.readouterr().out)


def test_exact_guest_probe_matches_offline_receipt(attempt, capsys):
    control, lease, guest, api = attempt
    receipt = control.provision(lease, api)
    assert execute_observation(guest, capsys) == receipt


@pytest.mark.parametrize('fault', ['extra-directory', 'file-mode', 'directory-mode',
                                  'file-symlink', 'directory-symlink', 'hardlink',
                                  'fifo', 'owner'])
def test_exact_guest_probe_refuses_unsafe_or_extra_entries(attempt, capsys, fault):
    control, lease, guest, api = attempt
    control.provision(lease, api)
    root = guest.path(transfer.DESTINATION)
    file = root / provenance.package_filename(control.verified.asset_files)
    if fault == 'extra-directory':
        (root / 'unexpected-empty').mkdir(mode=0o755)
    elif fault == 'file-mode':
        file.chmod(0o666)
    elif fault == 'directory-mode':
        root.chmod(0o777)
    elif fault == 'file-symlink':
        (root / 'linked-file').symlink_to(file)
    elif fault == 'directory-symlink':
        (root / 'linked-directory').symlink_to(root / 'fixtures')
    elif fault == 'hardlink':
        os.link(file, root / 'hardlink')
    elif fault == 'fifo':
        os.mkfifo(root / 'fifo')
    with pytest.raises(AssertionError):
        execute_observation(guest, capsys, wrong_owner=fault == 'owner')


@pytest.mark.parametrize('fault', ['changed', 'missing', 'extra'])
def test_exact_guest_probe_detects_changed_file_inventory(attempt, capsys, fault):
    control, lease, guest, api = attempt
    receipt = control.provision(lease, api)
    root = guest.path(transfer.DESTINATION)
    package = root / provenance.package_filename(control.verified.asset_files)
    if fault == 'changed':
        package.write_bytes(b'changed')
    elif fault == 'missing':
        package.unlink()
    else:
        (root / 'extra-file').write_bytes(b'extra')
        (root / 'extra-file').chmod(0o644)
    observed = execute_observation(guest, capsys)
    assert observed != receipt
    vm = Mock()
    vm.read.return_value = observed
    with pytest.raises(transfer.EvidenceError, match='booted-assets-mismatch'):
        control.observe(vm)


@pytest.mark.parametrize('fault', ['', 'lease', 'phase', 'domain', 'run', 'upgrade',
                                  'assets', 'command', 'interrupt', 'late-assets'])
def test_installed_transfer_guard_and_latched_failure(attempt, fault):
    control, lease, guest, api = attempt
    lease.state.update(phase='running', domain_id=12, domain_uuid='vm', run='attempt')
    transport = Mock(config={'domain_uuid': 'vm', 'domain_id': 12, 'run': 'attempt'})
    selected = lease
    if fault == 'lease': selected = Mock()
    if fault == 'phase': lease.state['phase'] = 'isolated'
    if fault == 'domain': transport.config['domain_id'] = 13
    if fault == 'run': transport.config['run'] = 'foreign'
    if fault == 'upgrade': control.verified._upgrade = {'packages': {}}
    package = control.verified.assets / provenance.package_filename(control.verified.asset_files)
    if fault == 'assets': package.write_bytes(b'changed')
    if fault == 'command': transport.call.side_effect = OSError('private-canary')
    if fault == 'interrupt': transport.call.side_effect = KeyboardInterrupt('private-canary')
    if fault == 'late-assets': transport.call.side_effect = lambda *a, **kw: package.write_bytes(b'changed')
    if fault:
        with pytest.raises(BaseException): control.provision_installed(selected, transport)
        with pytest.raises(transfer.EvidenceError, match='verified-provisioning-required'):
            control.observe(Mock())
        if fault not in ('command', 'interrupt', 'late-assets'): transport.call.assert_not_called()
    else:
        receipt = control.provision_installed(lease, transport)
        assert receipt == {'files': len(control.verified.asset_files),
                           'sha256': provenance.digest(control.verified.asset_files)}
        command = transport.call.call_args
        assert command.args[0][:2] == ['/usr/bin/python3', '-c']
        assert inspect.getsource(transfer.provision_installed_assets) in command.args[0][2]
        assert json.loads(command.kwargs['input']) == control.verified.asset_files
        vm = Mock()
        vm.read.return_value = receipt
        assert control.observe(vm) == receipt
    with pytest.raises(transfer.EvidenceError, match='already-attempted'):
        control.provision_installed(lease, transport)
    with pytest.raises(transfer.EvidenceError, match='already-attempted'):
        control.provision(lease, api)
    api.GuestFS.assert_not_called()


@pytest.mark.parametrize('fault', ['', 'collision', 'dangling', 'unsafe-parent', 'source-link',
    'file-link', 'directory-link', 'hardlink', 'mode', 'owner', 'missing', 'extra',
    'empty-directory', 'digest', 'replacement', 'copied-bytes', 'interrupt'])
def test_exact_installed_guest_copy_safety(tmp_path, capsys, fault):
    """Execute the shipped helper with real files/fds, mapping guest root identity."""
    guest = GuestFiles(tmp_path / 'guest')
    source = guest.path('/var/tmp/onpc-system-input')
    destination = guest.path(transfer.DESTINATION)
    source.mkdir(parents=True, mode=0o700)
    destination.parent.mkdir(parents=True)
    source.parent.chmod(0o1777)
    destination.parent.chmod(0o755)
    package = source / 'package.deb'
    package.write_bytes(b'package input')
    package.chmod(0o644)
    (source / 'nested').mkdir(mode=0o700)
    (source / 'nested/with spaces').write_bytes(b'nested input')
    (source / 'nested/with spaces').chmod(0o644)
    files = {p.relative_to(source).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest()
             for p in source.rglob('*') if p.is_file()}
    if fault == 'collision': destination.mkdir()
    if fault == 'dangling': destination.symlink_to(guest.root / 'absent')
    if fault == 'unsafe-parent': destination.parent.chmod(0o777)
    if fault == 'source-link':
        source.rename(source.with_name('real-input'))
        source.symlink_to(source.with_name('real-input'))
    if fault == 'file-link':
        package.rename(source / 'real-package')
        package.symlink_to(source / 'real-package')
    if fault == 'directory-link': (source / 'link').symlink_to(source / 'nested')
    if fault == 'hardlink': os.link(package, source / 'second-link')
    if fault == 'mode': package.chmod(0o666)
    if fault == 'missing': package.unlink()
    if fault == 'extra': (source / 'extra').write_bytes(b'extra')
    if fault == 'empty-directory': (source / 'empty').mkdir()
    if fault == 'digest': package.write_bytes(b'wrong')

    def root_info(info):
        fields = ('st_dev', 'st_ino', 'st_mode', 'st_nlink', 'st_size', 'st_mtime_ns', 'st_ctime_ns')
        return SimpleNamespace(**{field: getattr(info, field) for field in fields},
                               st_uid=1 if fault == 'owner' else 0, st_gid=0)
    class GuestPath(type(source)):
        def lstat(self): return root_info(super().lstat())
    mutated = False
    def read(fd, count):
        nonlocal mutated
        block = os.read(fd, count)
        if block and not mutated and fault in ('replacement', 'interrupt'):
            mutated = True
            if fault == 'interrupt': raise KeyboardInterrupt('private-canary')
            package.unlink()
            package.write_bytes(b'replacement')
        return block
    def write(fd, block):
        return os.write(fd, b'x' * len(block) if fault == 'copied-bytes' else block)
    guest_os = SimpleNamespace(**{name: getattr(os, name) for name in dir(os)})
    guest_os.geteuid = lambda: 0
    guest_os.fstat = lambda fd: root_info(os.fstat(fd))
    guest_os.stat = lambda *a, **kw: root_info(os.stat(*a, **kw))
    guest_os.read, guest_os.write = read, write
    def imported(name, *args, **kwargs):
        if name == 'os': return guest_os
        if name == 'pathlib':
            return SimpleNamespace(Path=lambda value: GuestPath(guest.path(value))
                                   if str(value).startswith('/') else Path(value))
        return builtins.__import__(name, *args, **kwargs)
    namespace = {'__builtins__': {**vars(builtins), '__import__': imported}}
    exec(compile(inspect.getsource(transfer.provision_installed_assets), '<installed-asset-copy>', 'exec'), namespace)
    if fault:
        with pytest.raises((AssertionError, OSError, KeyboardInterrupt)):
            namespace['provision_installed_assets'](files)
    else:
        namespace['provision_installed_assets'](files)
        observed = execute_observation(guest, capsys)
        assert observed == {'files': len(files), 'sha256': provenance.digest(files)}
        with pytest.raises(FileExistsError): namespace['provision_installed_assets'](files)
