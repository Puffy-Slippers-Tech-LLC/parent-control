"""Execute fixed guest programs against read-only filesystem/command fixtures."""

import hashlib
import io
import json
from pathlib import Path
import stat
import subprocess
import sys
from types import SimpleNamespace
from unittest.mock import patch

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'e2e'))
import installation_observations as probes
sys.path.pop(0)


PACKAGE = 'oh-no-parent-control'
ASSET = '/var/lib/onpc-e2e-assets/package.deb'
MARKER = '/run/reboot-required'
PACKAGES = MARKER + '.pkgs'


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
            bad = fault if self.value in (ASSET, PACKAGES, MARKER) else None
            return SimpleNamespace(
                st_mode=(stat.S_IFLNK if bad == 'symlink' or fault == 'dangling-payload' else
                         stat.S_IFDIR if bad == 'directory' else stat.S_IFREG)
                        | (0o666 if bad == 'writable' else 0o644),
                st_uid=1000 if bad == 'owner' else 0,
                st_gid=1000 if bad == 'group' else 0,
                st_nlink=2 if bad == 'hardlink' else 1)

        def resolve(self):
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
