"""Execute fixed guest programs against read-only filesystem/command fixtures."""

import hashlib
import io
import json
from pathlib import Path, PurePosixPath
import os
import stat
import subprocess
import sys
from types import SimpleNamespace
from unittest.mock import patch
import xml.etree.ElementTree as ET

import pytest

import installation_observations as probes


PACKAGE = 'oh-no-parent-control'
ASSET = '/var/lib/onpc-e2e-assets/package.deb'
MARKER = '/run/reboot-required'
PACKAGES = MARKER + '.pkgs'
SUDO = '/usr/lib/cargo/bin/sudo'


def execute_probe(program, *, files, query, metadata=None, fault=None):
    """No guest path or package subprocess is allowed to reach the host."""
    calls = []

    class GuestPath:
        def __init__(self, value):
            self.value = value

        def __str__(self):
            return self.value

        def __eq__(self, other):
            return isinstance(other, GuestPath) and self.value == other.value

        def lstat(self):
            if self.value not in files:
                raise FileNotFoundError
            bad = fault if self.value in (ASSET, PACKAGES, MARKER, SUDO) else None
            return SimpleNamespace(
                st_mode=(stat.S_IFLNK if bad == 'symlink' or fault == 'dangling-payload' else
                         stat.S_IFDIR if bad == 'directory' else stat.S_IFREG)
                        | (0o666 if bad == 'writable' else 0o644),
                st_uid=1000 if bad == 'owner' else 0,
                st_gid=1000 if bad == 'group' else 0,
                st_nlink=2 if bad == 'hardlink' else 1)

        def resolve(self, strict=False):
            if self.value == '/usr/bin/sudo':
                assert strict
                if fault == 'resolve-error':
                    raise FileNotFoundError('private-canary')
                return GuestPath('/unexpected' if fault == 'other-implementation' else SUDO)
            return GuestPath('/unexpected') if fault == 'parent-symlink' else self

        def read_text(self):
            return files[self.value].decode()

        def open(self, mode):
            assert mode == 'rb'
            return io.BytesIO(files[self.value])

    def command(args, **kwargs):
        assert kwargs == dict(capture_output=True, text=True, check=True, timeout=15)
        calls.append(args)
        if args[0] == '/usr/bin/dpkg-query':
            if isinstance(query, Exception):
                raise query
            if program == probes.SUDO_IMPLEMENTATION:
                if args == ('/usr/bin/dpkg-query', '-S', SUDO):
                    return SimpleNamespace(stdout='private-canary' if fault == 'package-owner' else 'sudo-rs: ' + SUDO + '\n')
                assert args == ('/usr/bin/dpkg-query', '-W',
                    '-f=${binary:Package}\t${Version}\t${db:Status-Status}\n', 'sudo-rs')
                return SimpleNamespace(stdout=query)
            assert args in (
                ('/usr/bin/dpkg-query', '-W', '-f=${Package}\t${db:Status-Status}\n'),
                ('/usr/bin/dpkg-query', '-W',
                 '-f=${Package}\t${Version}\t${Architecture}\t${Status}\n', PACKAGE))
            return SimpleNamespace(stdout=query)
        assert args[:3] == ('/usr/bin/dpkg-deb', '-f', ASSET)
        return SimpleNamespace(stdout=metadata[args[3]] + '\n')

    with patch.dict(sys.modules, {'pathlib': SimpleNamespace(Path=GuestPath),
                                 'subprocess': SimpleNamespace(run=command)}):
        exec(program, {})
    return calls


def execute_layout_probe(fault=None):
    """Execute the exact fixed layout program without touching host system paths."""
    desktop = '/usr/share/applications/com.puffyslippers.OhNoParentControl.Parent.desktop'
    entries = [
        {'path': '/usr/lib/oh-no-parent-control/main.py', 'kind': 'file',
         'mode': 0o755, 'target': ''},
        {'path': desktop, 'kind': 'file', 'mode': 0o640, 'target': ''},
        {'path': '/usr/bin/oh-no-parent-control', 'kind': 'symlink',
         'mode': 0o777, 'target': '../lib/oh-no-parent-control/main.py'},
    ]
    if fault == 'inventory-schema':
        entries[0]['private'] = True
    elif fault == 'inventory-path':
        entries[0]['path'] = '/../etc/shadow'
    elif fault == 'inventory-duplicate':
        entries.append(dict(entries[0]))
    raw = (json.dumps(entries, sort_keys=True) + '\n').encode()
    inventory = '/var/lib/onpc-e2e-assets/installed-files.json'
    files = {
        inventory: dict(kind='file', mode=0o644, uid=0, gid=0, data=raw),
        '/usr/lib/oh-no-parent-control/main.py': dict(kind='file', mode=0o755, uid=0, gid=0),
        desktop: dict(kind='file', mode=0o640, uid=0, gid=27),
        '/usr/bin/oh-no-parent-control': dict(kind='symlink', mode=0o777, uid=0, gid=0,
                                             target='../lib/oh-no-parent-control/main.py'),
        '/etc/oh-no-parent-control/config.json': dict(kind='file', mode=0o600, uid=0, gid=0),
        '/etc/pam.d/common-auth': dict(kind='file', mode=0o644, uid=0, gid=0,
                                      data=b'auth pam_oh_no_parent_control.so\n'),
        '/etc/pam.d/common-account': dict(kind='file', mode=0o644, uid=0, gid=0,
            data=b'account pam_malcontent.so\naccount pam_oh_no_parent_control.so\n'),
        '/usr/share/wayland-sessions/oh-no-parent-control.desktop':
            dict(kind='file', mode=0o644, uid=0, gid=0),
        '/usr/share/gnome-session/sessions/oh-no-parent-control.session':
            dict(kind='file', mode=0o644, uid=0, gid=0),
        '/usr/share/polkit-1/rules.d/00-oh-no-parent-control-session.rules':
            dict(kind='file', mode=0o644, uid=0, gid=0),
    }
    for suffix in ('child.request-own-access', 'kiosk.request-access'):
        files['/usr/share/polkit-1/actions/tech.puffyslippers.com.ohnoparentcontrol.'
              + suffix + '.policy'] = dict(kind='file', mode=0o644, uid=0, gid=0,
                                           data=b'<policy><action/></policy>')
    mutations = {
        'missing-entry': ('/usr/lib/oh-no-parent-control/main.py', None),
        'entry-owner': ('/usr/lib/oh-no-parent-control/main.py', ('uid', 1000)),
        'entry-group': (desktop, ('gid', 0)),
        'entry-mode': ('/usr/lib/oh-no-parent-control/main.py', ('mode', 0o644)),
        'config-mode': ('/etc/oh-no-parent-control/config.json', ('mode', 0o644)),
        'pam-token': ('/etc/pam.d/common-auth', ('data', b'private-canary\n')),
        'pam-order': ('/etc/pam.d/common-account', ('data',
            b'account pam_oh_no_parent_control.so\naccount pam_malcontent.so\n')),
    }
    if fault in mutations:
        name, change = mutations[fault]
        if change is None:
            del files[name]
        else:
            files[name][change[0]] = change[1]
    elif fault == 'symlink-target':
        files['/usr/bin/oh-no-parent-control']['target'] = 'private-canary'

    class GuestPath:
        def __init__(self, value):
            self.value = str(value)

        def __str__(self):
            return self.value

        def __eq__(self, other):
            return isinstance(other, GuestPath) and self.value == other.value

        def resolve(self):
            return self

        def lstat(self):
            value = files[self.value]
            kind = stat.S_IFLNK if value['kind'] == 'symlink' else stat.S_IFREG
            return SimpleNamespace(st_mode=kind | value['mode'], st_uid=value['uid'],
                                   st_gid=value['gid'], st_nlink=1,
                                   st_size=len(value.get('data', b'')))

        def read_bytes(self):
            return files[self.value].get('data', b'')

        def read_text(self):
            return self.read_bytes().decode()

    def command(args, **kwargs):
        assert kwargs == dict(capture_output=True, text=True, check=True, timeout=15)
        assert args == ('/usr/bin/dpkg', '--verify', PACKAGE)
        return SimpleNamespace(stdout='changed\n' if fault == 'package-verify' else '')

    def readlink(path):
        return files[str(path)]['target']

    root = SimpleNamespace(findall=lambda name: [] if fault == 'polkit-action' else [object()])
    modules = {
        'pathlib': SimpleNamespace(Path=GuestPath, PurePosixPath=PurePosixPath),
        'subprocess': SimpleNamespace(run=command),
        'grp': SimpleNamespace(getgrnam=lambda name: SimpleNamespace(gr_gid=27)),
        'os': SimpleNamespace(readlink=readlink),
    }
    with patch.dict(sys.modules, modules), patch.object(ET, 'parse', return_value=SimpleNamespace(
            getroot=lambda: root)):
        exec(probes.INSTALLED_LAYOUT, {})
    return raw


@pytest.mark.parametrize('fault', [None, 'installed', 'residual', 'database-error',
    'empty-database', 'malformed', 'payload', 'dangling-payload', 'product-marker',
    'symlink', 'parent-symlink', 'owner', 'group', 'writable', 'hardlink', 'directory'])
def test_absence_requires_successful_database_query_and_clean_product_state(fault, capsys):
    query = 'base-files\tinstalled\n'
    files = {PACKAGES: b'unrelated-package\n'}
    if fault in ('installed', 'residual'):
        query += PACKAGE + '\t' + ('installed' if fault == 'installed' else 'config-files') + '\n'
    elif fault == 'database-error':
        query = subprocess.CalledProcessError(2, 'dpkg-query', stderr='private-canary')
    elif fault == 'empty-database':
        query = ''
    elif fault == 'malformed':
        query = 'private-canary\n'
    elif fault in ('payload', 'dangling-payload'):
        # Both real and dangling paths exist to lstat and must disqualify absence.
        files['/usr/lib/oh-no-parent-control'] = b''
    elif fault == 'product-marker':
        files[PACKAGES] = (PACKAGE + '\n').encode()
    if fault:
        with pytest.raises((AssertionError, subprocess.CalledProcessError)):
            execute_probe(probes.ABSENT, files=files, query=query, fault=fault)
    else:
        calls = execute_probe(probes.ABSENT, files=files, query=query)
        assert len(calls) == 1
    assert capsys.readouterr().out == ('' if fault else 'package-absent\n')


@pytest.mark.parametrize('fault', [None, 'installed', 'product-marker', 'installer-child',
                                   'wrong-shell', 'wrong-user'])
def test_refusal_result_follows_exact_shell_and_requires_clean_package_state(fault, capsys):
    device = __import__('os').makedev(4, 64)

    class RefusalPath:
        def __init__(self, value):
            self.value = str(value)

        def __truediv__(self, value):
            return RefusalPath(self.value.rstrip('/') + '/' + str(value))

        def __str__(self):
            return self.value

        def lstat(self):
            if self.value == PACKAGES:
                return SimpleNamespace(st_mode=stat.S_IFREG | 0o644, st_uid=0, st_gid=0,
                                       st_nlink=1)
            raise FileNotFoundError

        def resolve(self, strict=False):
            executables = {'/proc/101/exe': '/usr/bin/login',
                           '/proc/202/exe': '/unexpected' if fault == 'wrong-shell' else '/usr/bin/bash'}
            return RefusalPath(executables.get(self.value, self.value))

        def read_text(self):
            values = {
                PACKAGES: PACKAGE + '\n' if fault == 'product-marker' else 'unrelated\n',
                '/proc/101/task/101/children': '202\n',
                '/proc/202/stat': '202 (bash) S 101 202 202 ' + str(device) + ' 202 ' + '0 '*14,
                '/proc/202/task/202/children': '303\n' if fault == 'installer-child' else '',
            }
            if self.value == '/proc/202/status':
                uid = '999' if fault == 'wrong-user' else '1000'
                return 'Uid:\t' + ' '.join([uid]*4) + '\n'
            return values[self.value]

        def __eq__(self, other):
            return isinstance(other, RefusalPath) and self.value == other.value

    def command(args, **kwargs):
        assert kwargs == dict(capture_output=True, text=True, check=True, timeout=15)
        if args[0] == '/usr/bin/dpkg-query':
            row = 'base-files\tinstalled\n'
            if fault == 'installed':
                row += PACKAGE + '\tinstalled\n'
            return SimpleNamespace(stdout=row)
        assert args == ('/usr/bin/systemctl', 'show', 'serial-getty@ttyS0.service',
                        '--property=MainPID', '--value')
        return SimpleNamespace(stdout='101\n')

    modules = {
        'pathlib': SimpleNamespace(Path=RefusalPath),
        'subprocess': SimpleNamespace(run=command),
        'os': SimpleNamespace(makedev=lambda major, minor: device),
        'pwd': SimpleNamespace(getpwnam=lambda _: SimpleNamespace(pw_uid=1000)),
    }
    if fault:
        with patch.dict(sys.modules, modules), pytest.raises((AssertionError, KeyError)):
            exec(probes.REFUSED, {})
    else:
        with patch.dict(sys.modules, modules):
            exec(probes.REFUSED, {})
    assert capsys.readouterr().out == ('' if fault else 'install-refused-safe\n')


@pytest.mark.parametrize('fault', [None, 'version', 'architecture', 'package', 'unconfigured',
    'query-error', 'missing-asset', 'missing-marker', 'missing-package-marker',
    'unrelated-marker', 'metadata-package', 'metadata-newline', 'symlink', 'parent-symlink',
    'owner', 'group', 'writable', 'hardlink', 'directory'])
def test_install_result_requires_artifact_identity_configured_package_and_product_marker(fault, capsys):
    files = {ASSET: b'release-package-bytes', MARKER: b'', PACKAGES: (PACKAGE + '\n').encode()}
    metadata = dict(Package=PACKAGE, Version='1.2.3', Architecture='amd64')
    row = [PACKAGE, '1.2.3', 'amd64', 'install ok installed']
    for name, index in [('package', 0), ('version', 1), ('architecture', 2), ('unconfigured', 3)]:
        if fault == name:
            row[index] = 'wrong'
    if fault in ('missing-asset', 'missing-marker', 'missing-package-marker'):
        del files[{'missing-asset': ASSET, 'missing-marker': MARKER,
                   'missing-package-marker': PACKAGES}[fault]]
    if fault == 'unrelated-marker':
        files[PACKAGES] = b'unrelated-package\n'
    if fault == 'metadata-package':
        metadata['Package'] = 'unrelated-package'
    if fault == 'metadata-newline':
        metadata['Version'] = '1.2.3\nprivate-canary'
    query = '\t'.join(row) + '\n'
    if fault == 'query-error':
        query = subprocess.CalledProcessError(2, 'dpkg-query', stderr='private-canary')
    if fault:
        with pytest.raises((AssertionError, FileNotFoundError, subprocess.CalledProcessError)):
            execute_probe(probes.INSTALLED, files=files, query=query, metadata=metadata, fault=fault)
        assert capsys.readouterr().out == ''
    else:
        calls = execute_probe(probes.INSTALLED, files=files, query=query, metadata=metadata)
        assert len(calls) == 4
        assert json.loads(capsys.readouterr().out) == {
            'package_sha256': hashlib.sha256(files[ASSET]).hexdigest(),
            'installed_identity_verified': True, 'product_reboot_required': True}


@pytest.mark.parametrize('fault', [None, 'inventory-schema', 'inventory-path',
    'inventory-duplicate', 'missing-entry', 'entry-owner', 'entry-group', 'entry-mode',
    'symlink-target', 'package-verify', 'config-mode', 'pam-token', 'pam-order', 'polkit-action'])
def test_installed_layout_reuses_bound_inventory_and_requires_integration_files(fault, capsys):
    if fault:
        with pytest.raises((AssertionError, KeyError)):
            execute_layout_probe(fault)
        assert capsys.readouterr().out == ''
    else:
        raw = execute_layout_probe()
        assert json.loads(capsys.readouterr().out) == {
            'installed_files': 3,
            'inventory_sha256': hashlib.sha256(raw).hexdigest(),
            'installed_layout_verified': True,
        }


@pytest.mark.parametrize('fault', [None, 'resolve-error', 'other-implementation', 'package-owner',
    'database-error', 'version', 'status', 'package', 'trailing', 'owner', 'group', 'writable',
    'hardlink', 'directory', 'symlink', 'parent-symlink'])
def test_sudo_implementation_requires_installed_owner_and_safe_package_identity(fault, capsys):
    query = 'sudo-rs\t0.2.13-0ubuntu1.2\tinstalled\n'
    if fault == 'database-error':
        query = subprocess.CalledProcessError(2, 'dpkg-query', stderr='private-canary')
    elif fault in ('version', 'status', 'package'):
        query = query.replace({'version': '0.2.13-0ubuntu1.2', 'status': 'installed',
                               'package': 'sudo-rs'}[fault], 'private-canary')
    elif fault == 'trailing':
        query += '\n'
    if fault:
        with pytest.raises((AssertionError, FileNotFoundError, subprocess.CalledProcessError)):
            execute_probe(probes.SUDO_IMPLEMENTATION, files={SUDO: b''}, query=query, fault=fault)
        assert capsys.readouterr().out == ''
    else:
        execute_probe(probes.SUDO_IMPLEMENTATION, files={SUDO: b''}, query=query)
        assert json.loads(capsys.readouterr().out) == {
            'implementation': 'sudo-rs', 'package_version': '0.2.13-0ubuntu1.2', 'executable': SUDO}
