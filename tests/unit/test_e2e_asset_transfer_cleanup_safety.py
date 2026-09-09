"""Transfer failure cannot start a journey, repeat provisioning, or own cleanup."""

import builtins
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

import provenance
from tests.support.e2e_provenance import source, assets, lease
import asset_transfer as transfer


class GuestFiles:
    """Filesystem-backed guestfs double; corrupted uploads change actual bytes."""
    def __init__(self, root):
        self.root = root
        self.closed = False
        self.uploads = 0
        self.corrupt = False

    def path(self, name):
        return self.root / name.lstrip('/')

    def set_backend(self, *_): pass
    def set_network(self, *_): pass
    def add_drive_opts(self, *_, **__): pass
    def launch(self): pass
    def inspect_os(self): return ['/dev/test']
    def inspect_get_mountpoints(self, *_): return {'/': '/dev/test'}
    def mount(self, *_): pass
    def sync(self): pass
    def close(self): self.closed = True
    def realpath(self, name): return name
    def exists(self, name): return self.path(name).exists()
    def is_symlink(self, name): return self.path(name).is_symlink()
    def mkdir(self, name): self.path(name).mkdir()
    def chown(self, *_): pass
    def chmod(self, mode, name): self.path(name).chmod(mode)

    def upload(self, source, name):
        self.uploads += 1
        self.path(name).write_bytes(Path(source).read_bytes() + (b'corrupt' if self.corrupt else b''))

    def checksum(self, algorithm, name):
        assert algorithm == 'sha256'
        return hashlib.sha256(self.path(name).read_bytes()).hexdigest()

    def find(self, name):
        # The public API strips the supplied prefix, including its trailing
        # separator only when supplied (libguestfs daemon/find.c + lib/file.c).
        prefix = '' if name.endswith('/') else '/'
        return [prefix + p.relative_to(self.path(name)).as_posix()
                for p in self.path(name).rglob('*')]


@pytest.fixture
def attempt(tmp_path, source, assets, lease):
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


@pytest.mark.parametrize('fault', ['source', 'assets', 'phase', 'running', 'lease',
                                  'corrupt', 'existing', 'symlink', 'interrupt', 'extra', 'late-assets'])
def test_refusals_latch_and_leave_restoration_to_outer_lease(attempt, fault):
    control, lease, guest, api = attempt
    selected_lease = lease
    if fault == 'source':
        (control.verified.root / 'local-change.py').write_text('changed')
    elif fault == 'assets':
        (control.verified.assets / 'package.deb').write_bytes(b'changed')
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
            (control.verified.assets / 'package.deb').write_bytes(b'late-change')
        guest.sync = sync
    with pytest.raises(BaseException):
        control.provision(selected_lease, api)
    if fault in ('source', 'assets', 'phase', 'running', 'lease'):
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
    if fault == 'inventory':
        (assets / 'transfer-sha256.json').write_text('{}')
    else:
        original = assets / 'original.deb'
        original.write_bytes((assets / 'package.deb').read_bytes())
        manifest_path = assets / 'artifact-manifest.json'
        manifest = json.loads(manifest_path.read_text())
        manifest['artifacts']['package']['path'] = original.name
        manifest_path.write_text(json.dumps(manifest))
        (assets / 'package.deb').write_bytes(b'wrong alias')
        (assets / 'transfer-sha256.json').write_text(json.dumps({
            p.relative_to(assets).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest()
            for p in assets.rglob('*') if p.is_file() and p.name != 'transfer-sha256.json'}))
    verified = provenance.VerifiedInputs(root=control.verified.root, assets=assets, lease=lease)
    with pytest.raises(transfer.EvidenceError, match='inventory-mismatch|package-mismatch'):
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
    file = root / 'package.deb'
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
    if fault == 'changed':
        (root / 'package.deb').write_bytes(b'changed')
    elif fault == 'missing':
        (root / 'package.deb').unlink()
    else:
        (root / 'extra-file').write_bytes(b'extra')
        (root / 'extra-file').chmod(0o644)
    observed = execute_observation(guest, capsys)
    assert observed != receipt
    vm = Mock()
    vm.read.return_value = observed
    with pytest.raises(transfer.EvidenceError, match='booted-assets-mismatch'):
        control.observe(vm)
