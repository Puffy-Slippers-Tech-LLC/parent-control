"""In-memory guestfs, no VM, process, global cache or real ownership changes.

Compatible with parallel unit and cleanup scheduling.
"""
import copy
import hashlib
from pathlib import PurePosixPath
import stat
from unittest.mock import Mock

import pytest
import baseline_fixtures as fixture
import baseline_console as console


class Guest:
    def __init__(self):
        self.nodes = {}
        self.writes = []
        self.links = {}
        self.mkdir('/')
        for path in ('/var', '/var/lib', '/opt', '/usr', '/usr/share', '/usr/share/applications',
                     '/home', '/etc'):
            self.mkdir(path)
        rows = []
        for index, name in enumerate(('onpc-child-riley', 'onpc-child-jordan', 'onpc-parent-jamie'), 1000):
            self.mkdir('/home/' + name)
            self.chown(index, index, '/home/' + name)
            self.chmod(0o700, '/home/' + name)
            rows.append(f'{name}:x:{index}:{index}::/home/{name}:/bin/bash')
        self.write('/etc/passwd', ('\n'.join(rows) + '\n').encode())
        self.writes.clear()

    def exists(self, path): return path in self.nodes
    def is_symlink(self, path): return path in self.links
    def realpath(self, path):
        for parent in (PurePosixPath(path), *PurePosixPath(path).parents):
            if str(parent) in self.links: return '/unexpected'
        return path
    def lstatns(self, path): return dict(self.nodes[path][0])
    def mkdir(self, path):
        assert path not in self.nodes
        self.nodes[path] = [{'st_uid': 0, 'st_gid': 0, 'st_mode': stat.S_IFDIR | 0o755,
                            'st_nlink': 1, 'st_ino': len(self.nodes) + 1, 'st_dev': 1}, b'']
    def chown(self, uid, gid, path): self.nodes[path][0].update(st_uid=uid, st_gid=gid)
    def chmod(self, mode, path): self.nodes[path][0]['st_mode'] = stat.S_IFMT(self.nodes[path][0]['st_mode']) | mode
    def write(self, path, data):
        if path not in self.nodes:
            self.nodes[path] = [{'st_uid': 0, 'st_gid': 0, 'st_mode': stat.S_IFREG | 0o600,
                                'st_nlink': 1, 'st_ino': len(self.nodes) + 1, 'st_dev': 1}, b'']
        self.nodes[path][1] = data
        self.writes.append(path)
    def read_file(self, path): return self.nodes[path][1]
    def checksum(self, algorithm, path): return hashlib.sha256(self.read_file(path)).hexdigest()
    def mv(self, source, target): self.nodes[target] = self.nodes.pop(source)
    def sync(self): pass
    def umask(self, mode): assert mode == 0o077
    def filesize(self, path): return len(self.read_file(path))
    def is_file(self, path): return path in self.nodes and stat.S_ISREG(self.nodes[path][0]['st_mode'])
    def is_dir(self, path): return path in self.nodes and stat.S_ISDIR(self.nodes[path][0]['st_mode'])
    def ln_s(self, target, path): self.links[path] = target


@pytest.fixture
def prepared():
    guest = Guest()
    payload = {key: ('distinct-' + key).encode() for key in
               ('A', 'H', 'S', 'N', 'mechanical', 'onpc-test-gui.py', 'gtk_automation.py')}
    return guest, payload


def test_first_repeat_owned_update_and_preserved_unrelated_state(prepared):
    guest, payload = prepared
    guest.write('/opt/unrelated', b'keep')
    fixture.reconcile(guest, payload)
    before = copy.deepcopy(guest.nodes)
    guest.writes.clear()
    fixture.reconcile(guest, payload)
    assert guest.nodes == before and guest.writes == []
    fixture.reconcile(guest, payload | {'A': b'new distinct A'})
    fixture.verify(guest)
    assert guest.read_file('/opt/unrelated') == b'keep'
    assert guest.read_file(fixture.assets.PREFIX + '/Exact Fixture.AppImage') == b'new distinct A'
    assert guest.read_file(fixture.assets.PREFIX + '/PrismLauncher.AppImage') == payload['N']


@pytest.mark.parametrize('boundary', ['write', 'chown', 'rename', 'record'])
def test_interrupted_placement_retries_only_owned_work(prepared, monkeypatch, boundary):
    guest, payload = prepared
    actual_write, actual_move = guest.write, guest.mv
    actual_chown = guest.chown
    failed = False
    def write(path, data):
        nonlocal failed
        if not failed and boundary == 'write' and path.endswith('.onpc-baseline-new'):
            failed = True
            actual_write(path, data[:3])
            raise OSError('interrupted')
        actual_write(path, data)
    def chown(uid, gid, path):
        nonlocal failed
        actual_chown(uid, gid, path)
        if not failed and boundary == 'chown' and uid != 0 and path.endswith('.onpc-baseline-new'):
            failed = True
            raise OSError('interrupted')
    def move(source, target):
        nonlocal failed
        if not failed and boundary == 'rename' and source.endswith('.onpc-baseline-new'):
            failed = True
            raise OSError('interrupted')
        actual_move(source, target)
        if not failed and boundary == 'record' and source.endswith('.onpc-baseline-new'):
            failed = True
            raise OSError('interrupted')
    monkeypatch.setattr(guest, 'write', write)
    monkeypatch.setattr(guest, 'mv', move)
    monkeypatch.setattr(guest, 'chown', chown)
    with pytest.raises(OSError): fixture.reconcile(guest, payload)
    fixture.reconcile(guest, payload)
    fixture.verify(guest)
    assert not any(path.endswith('.onpc-baseline-new') for path in guest.nodes)


@pytest.mark.parametrize('fault', ['collision', 'link', 'hardlink', 'owner', 'mode', 'parent', 'bytes'])
def test_refuses_foreign_or_tampered_inputs_before_any_write(prepared, fault):
    guest, payload = prepared
    path = fixture.assets.PREFIX + '/Exact Fixture.AppImage'
    if fault == 'collision':
        guest.write(path, b'foreign')
        guest.chown(1001, 1001, path)
        guest.chmod(0o755, path)
    else:
        fixture.reconcile(guest, payload)
        if fault == 'link': guest.links[path] = '/foreign'
        if fault == 'hardlink': guest.nodes[path][0]['st_nlink'] = 2
        if fault == 'owner': guest.nodes[path][0]['st_uid'] = 999
        if fault == 'mode': guest.chmod(0o777, path)
        if fault == 'parent': guest.links[fixture.assets.PREFIX] = '/foreign'
        if fault == 'bytes': guest.write(path, b'foreign')
    before = copy.deepcopy(guest.nodes)
    guest.writes.clear()
    with pytest.raises(ValueError): fixture.reconcile(guest, payload)
    assert guest.nodes == before and guest.writes == []


def test_missing_baseline_is_a_read_only_refusal(prepared):
    guest, _ = prepared
    before = copy.deepcopy(guest.nodes)
    with pytest.raises(KeyError): fixture.verify(guest)
    assert guest.nodes == before


def test_console_reconcile_twice_and_runtime_never_repairs():
    guest = Guest()
    guest.write('/etc/login.defs', b'# keep\nLOGIN_TIMEOUT\t60 # stock\nLOGIN_RETRIES 3\n')
    original = guest.read_file('/etc/login.defs')
    with pytest.raises(ValueError, match='login-stale'): console.login_window(guest)
    assert guest.read_file('/etc/login.defs') == original
    assert console.login_window(guest, prepare=True)['login_timeout_seconds'] == 600
    before = copy.deepcopy(guest.nodes)
    guest.writes.clear()
    console.login_window(guest, prepare=True)
    console.login_window(guest)
    assert guest.nodes == before and not guest.writes
    assert guest.read_file('/etc/login.defs') == original.replace(b'\t60 ', b'\t600 ')


def test_baseline_console_getty_is_idempotent_and_test_route_is_read_only():
    guest = Mock()
    guest.is_file.return_value = guest.is_dir.return_value = True
    links = {}
    guest.realpath.side_effect = lambda path: links.get(path, path)
    guest.is_symlink.side_effect = lambda path: path in links
    guest.exists.return_value = False
    guest.ln_s.side_effect = lambda target, path: links.update({path: target})
    with pytest.raises(ValueError): console.getty(guest)
    guest.ln_s.assert_not_called()
    console.getty(guest, prepare=True)
    console.getty(guest, prepare=True)
    console.getty(guest)
    guest.ln_s.assert_called_once()


@pytest.mark.parametrize('original', [
    b'# LOGIN_TIMEOUT 60\nLOGIN_RETRIES 3\n',
    b'LOGIN_RETRIES 3',
])
def test_console_preparation_adds_missing_timeout_and_preserves_existing_bytes(original):
    guest = Guest()
    guest.write('/etc/login.defs', original)
    before = copy.deepcopy(guest.nodes)
    guest.writes.clear()
    with pytest.raises(ValueError, match='login-stale'):
        console.login_window(guest)
    assert guest.nodes == before and not guest.writes
    console.login_window(guest, prepare=True)
    desired = original + (b'' if original.endswith(b'\n') else b'\n') + b'LOGIN_TIMEOUT\t600\n'
    assert guest.read_file('/etc/login.defs') == desired
    guest.writes.clear()
    console.login_window(guest, prepare=True)
    console.login_window(guest)
    assert not guest.writes


@pytest.mark.parametrize('original', [
    b'LOGIN_TIMEOUT 60\nLOGIN_TIMEOUT 600\n',
    b'LOGIN_TIMEOUT invalid\n',
    b'#' + b'x' * 65534 + b'\n',
])
def test_console_preparation_refuses_ambiguous_invalid_or_oversized_settings(original):
    guest = Guest()
    guest.write('/etc/login.defs', original)
    before = copy.deepcopy(guest.nodes)
    guest.writes.clear()
    with pytest.raises(ValueError):
        console.login_window(guest, prepare=True)
    assert guest.nodes == before and not guest.writes
