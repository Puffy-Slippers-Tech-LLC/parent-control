"""Private filesystem fixtures for kiosk confinement component tests."""
import copy
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import stat
from types import SimpleNamespace

import pytest

from tests.support.paths import ROOT


def load_helper():
    spec = importlib.util.spec_from_file_location('private_kiosk_pin_storage',
                                                ROOT / 'tools/kiosk_confinement.py')
    helper = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(helper)
    return helper


@pytest.fixture
def private_store(tmp_path, monkeypatch):
    helper = load_helper()
    host, store = tmp_path / 'host', tmp_path / 'store'
    host.mkdir(mode=0o755)
    store.mkdir(mode=0o700)
    overrides, labels, owners = {}, {}, {}
    raw_os = os
    context = SimpleNamespace(filesystem_gid=77, sgid=False)

    def metadata(info, path):
        values = {name: getattr(info, name) for name in dir(info) if name.startswith('st_')}
        # Package inputs and fixture ancestry model root-owned installed state.
        # New private children inherit the modeled filesystem GID until the
        # product explicitly initializes their ownership. Never erase that gap.
        values.update(st_uid=0, st_gid=0)
        values.update(owners.get((info.st_dev, info.st_ino), {}))
        # The test launcher owns fixture ancestors. The product still checks
        # every real child mode, inode, timestamp, link count and membership.
        if path == tmp_path or path in tmp_path.parents:
            values['st_mode'] &= ~0o7022
        values.update(overrides.get(str(path), {}))
        return SimpleNamespace(**values)

    def fd_path(fd):
        return Path(raw_os.readlink('/proc/self/fd/' + str(fd)).removesuffix(' (deleted)'))

    def fstat(fd):
        return metadata(raw_os.fstat(fd), fd_path(fd))

    def fchown(fd, uid, gid):
        assert (uid, gid) == (0, 0)
        info = raw_os.fstat(fd)
        owners.setdefault((info.st_dev, info.st_ino), {}).update(st_uid=uid, st_gid=gid)

    def fchmod(fd, mode):
        raw_os.fchmod(fd, mode)
        info = raw_os.fstat(fd)
        owners.setdefault((info.st_dev, info.st_ino), {}).pop('st_mode', None)

    def mkdir(path, mode=0o777, *, dir_fd=None):
        raw_os.mkdir(path, mode=mode, dir_fd=dir_fd)
        info = raw_os.stat(path, dir_fd=dir_fd, follow_symlinks=False)
        born_mode = info.st_mode | (stat.S_ISGID if context.sgid else 0)
        # Root can open a mode-000 new directory. Model that capability only;
        # preserve its actual masked metadata until explicit initialization.
        raw_os.chmod(path, 0o700, dir_fd=dir_fd)
        owners[(info.st_dev, info.st_ino)] = dict(st_mode=born_mode, st_uid=0,
                                                st_gid=context.filesystem_gid)

    def open_file(path, flags, *args, **kwargs):
        fd = raw_os.open(path, flags, *args, **kwargs)
        if flags & os.O_CREAT and flags & os.O_EXCL:
            info = raw_os.fstat(fd)
            owners[(info.st_dev, info.st_ino)] = dict(st_uid=0, st_gid=context.filesystem_gid)
        return fd

    def symlink(target, name, *, dir_fd=None):
        raw_os.symlink(target, name, dir_fd=dir_fd)
        info = raw_os.stat(name, dir_fd=dir_fd, follow_symlinks=False)
        owners[(info.st_dev, info.st_ino)] = dict(st_uid=0, st_gid=context.filesystem_gid)

    def chown(path, uid, gid, *, dir_fd=None, follow_symlinks=True):
        assert (uid, gid, follow_symlinks) == (0, 0, False)
        info = raw_os.stat(path, dir_fd=dir_fd, follow_symlinks=False)
        owners[(info.st_dev, info.st_ino)] = dict(st_uid=uid, st_gid=gid)

    def stat_path(path, *, dir_fd=None, follow_symlinks=True):
        actual = Path(path)
        if dir_fd is not None:
            actual = fd_path(dir_fd) / actual
        return metadata(raw_os.stat(path, dir_fd=dir_fd, follow_symlinks=follow_symlinks), actual)

    def label_key(fd):
        info = raw_os.fstat(fd)
        return info.st_dev, info.st_ino

    def policy_label(path, mode):
        typ = ('bin_t' if path.startswith('/usr/bin/') else
               'systemd_unit_file_t' if '/user-units/' in path else
               'usr_t' if '/share/' in path else 'lib_t')
        return 'system_u:object_r:' + typ + ':s0'

    def default_label(fd):
        path = fd_path(fd)
        if host in path.parents:
            return policy_label('/' + str(path.relative_to(host)), raw_os.fstat(fd).st_mode)
        return helper.RUNTIME_CONTEXT.decode()

    def getxattr(fd, name):
        assert name == 'security.selinux'
        return (labels.get(label_key(fd), default_label(fd)) + '\0').encode()

    def setxattr(fd, name, value):
        assert name == 'security.selinux'
        labels[label_key(fd)] = value.rstrip(b'\0').decode()

    proxy = SimpleNamespace(**{name: getattr(raw_os, name) for name in dir(raw_os)})
    proxy.fstat, proxy.stat = fstat, stat_path
    proxy.fchown, proxy.chown, proxy.fchmod, proxy.mkdir = fchown, chown, fchmod, mkdir
    proxy.open, proxy.symlink = open_file, symlink
    proxy.getxattr, proxy.setxattr = getxattr, setxattr
    proxy.listxattr = lambda fd: []
    monkeypatch.setattr(helper, 'os', proxy)
    # Credential/ownership metadata double only. Actual multi-GID credentials
    # and loaded policy remain installed acceptance, outside this host fixture.
    monkeypatch.setattr(helper, 'private_root_credentials', lambda: None)
    monkeypatch.setattr(helper, 'runtime_policy_label', policy_label)
    actual_open = helper.runtime_open

    def source_open(path, **kwargs):
        text = str(path)
        return actual_open(host / text.lstrip('/') if text == '/usr' or text.startswith('/usr/')
                           else path, **kwargs)

    monkeypatch.setattr(helper, 'runtime_open', source_open)
    return SimpleNamespace(helper=helper, host=host, store=store, overrides=overrides,
                           labels=labels, fd_path=fd_path, label_key=label_key,
                           policy_label=policy_label, actual_open=actual_open, context=context)


def named_fixture(fixture):
    specs = {
        '/usr/bin/oh-no-parent-control': {'kind': 'file', 'role': 'script'},
        '/usr/lib/oh-no-parent-control/kiosk': {'kind': 'directory', 'role': 'module'},
        '/usr/lib/oh-no-parent-control/kiosk/main.py': {'kind': 'file', 'role': 'module'},
        '/usr/share/extension/wellbeingLogic.mjs': {'kind': 'file', 'role': 'wellbeing'},
        '/usr/share/extension/schemas/gschemas.compiled': {'kind': 'file', 'role': 'wellbeing'},
        '/usr/share/confinement/user-units': {'kind': 'directory', 'role': 'unit'},
        '/usr/share/confinement/user-units/service.conf': {'kind': 'file', 'role': 'unit'},
        '/usr/share/confinement/user-units/masked.service': {
            'kind': 'link', 'role': 'unit', 'link': '/dev/null'},
        '/usr/share/confinement/session-data': {'kind': 'directory', 'role': 'session-data'},
        '/usr/share/confinement/session-data/service': {'kind': 'file', 'role': 'session-data'},
    }
    for path, spec in sorted(specs.items()):
        target = fixture.host / path.lstrip('/')
        target.parent.mkdir(mode=0o755, parents=True, exist_ok=True)
        if spec['kind'] == 'directory':
            target.mkdir(mode=0o755, exist_ok=True)
        elif spec['kind'] == 'link':
            target.symlink_to(spec['link'])
        else:
            target.write_bytes(('original:' + path).encode())
            target.chmod(0o755 if spec['role'] == 'script' else 0o644)
    # pathlib's parents=True uses the ambient umask for intermediate parents,
    # rather than the leaf's explicit mode. Model package-installed ancestry
    # before any test deliberately mutates it, independent of a host umask002.
    for directory in fixture.host.rglob('*'):
        if directory.is_dir() and not directory.is_symlink():
            directory.chmod(0o755)
    return specs


@pytest.fixture
def material_host(private_store, monkeypatch):
    scene, helper = private_store, private_store.helper
    specs = named_fixture(scene)
    native = '/usr/bin/native'
    library = '/usr/lib/library.so'
    vendor = '/usr/lib/helper'
    for name in (native, library, vendor):
        path = scene.host / name.lstrip('/')
        path.parent.mkdir(mode=0o755, parents=True, exist_ok=True)
        path.write_bytes(b'\x7fELF' + name.encode())
        path.chmod(0o755)
    payload = scene.host / str(helper.PAYLOAD).lstrip('/')
    payload.mkdir(mode=0o755, parents=True)
    for path in scene.host.rglob('*'):
        if path.is_dir() and not path.is_symlink():
            path.chmod(0o755)
    config = dict(backend='apparmor', runtime_inputs=specs,
                  executables=[dict(role='service', paths=[native]),
                               dict(role='library', paths=[library]),
                               dict(role='service', paths=['/usr/bin/optional'], optional=True)],
                  preserved_executables=[dict(path=vendor, mode=0o755, label=None)])

    def physical(path):
        path = Path(path)
        return scene.host / str(path).lstrip('/') if path == Path('/usr') or Path('/usr') in path.parents else path

    def logical(path):
        return Path('/') / path.relative_to(scene.host) if scene.host in path.parents else path

    # Only names are translated. Real trust walks, no-follow opens, full inode
    # assertions, byte hashing, membership and all failure checks stay active.
    raw_stat, raw_open, raw_readlink = helper.os.stat, helper.os.open, helper.os.readlink
    path_open, real_trusted = Path.open, helper.trusted
    path_exists, path_is_link, path_iterdir = Path.exists, Path.is_symlink, Path.iterdir
    monkeypatch.setattr(Path, 'exists', lambda path, **kw: path_exists(physical(path), **kw))
    monkeypatch.setattr(Path, 'is_symlink', lambda path: path_is_link(physical(path)))
    monkeypatch.setattr(Path, 'iterdir', lambda path: iter(logical(child) for child in path_iterdir(physical(path))))
    monkeypatch.setattr(Path, 'lstat', lambda path: raw_stat(physical(path), follow_symlinks=False))
    monkeypatch.setattr(Path, 'stat', lambda path, **kw: raw_stat(physical(path), **kw))
    monkeypatch.setattr(Path, 'open', lambda path, *a, **kw: path_open(physical(path), *a, **kw))
    monkeypatch.setattr(helper.os, 'open', lambda path, *a, **kw:
                        raw_open(physical(path) if isinstance(path, (str, Path)) and
                                 str(path).startswith('/') else path, *a, **kw))
    monkeypatch.setattr(helper.os, 'readlink', lambda path, *a, **kw:
                        raw_readlink(physical(path) if path else path, *a, **kw))
    monkeypatch.setattr(helper, 'trusted', lambda path, **kw: logical(real_trusted(physical(path), **kw)))
    monkeypatch.setattr(helper, 'runtime_input_specs', lambda distribution: copy.deepcopy(specs))
    monkeypatch.setattr(helper, 'enforcing', lambda cfg: None)  # No host MAC operations.
    policy = b'attested-private-policy'

    def inputs():
        data = json.dumps(config, sort_keys=True).encode()
        (payload / 'config.json').write_bytes(data)
        (payload / 'config.json').chmod(0o644)
        (payload / 'onpc-kiosk.apparmor').write_bytes(policy)
        (payload / 'onpc-kiosk.apparmor').chmod(0o644)
        return data, policy, ' '.join(hashlib.sha256(item).hexdigest() for item in (data, policy)) + '\n'

    def measure():
        return helper.required_material(*inputs())

    return SimpleNamespace(helper=helper, fixture=scene, specs=specs, config=config,
                           physical=physical, inputs=inputs, measure=measure, payload=payload)
