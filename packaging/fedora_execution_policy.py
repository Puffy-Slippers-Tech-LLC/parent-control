#!/usr/bin/python3
"""Recognize an unenforced stock dependency without adopting administrator policy.

The same standalone source is embedded in RPM pretrans and postun, where the
product payload may not exist. No DNF state files or distribution rules change.
"""
from __future__ import annotations

import argparse
import grp
import hashlib
import json
import os
from pathlib import Path
import re
import stat
import subprocess
import tempfile

OWNER = 0
PURPOSE = 'onpc-fedora-original-execution-policy-v1'
STATE = '/var/lib/oh-no-parent-control/fedora-execution-policy.json'
GENERATED = {'/etc/fapolicyd/compiled.rules', '/etc/fapolicyd/compiled.rules.prev'}
INTEGRATIONS = {
    '/etc/fapolicyd/rules.d/00-oh-no-parent-control-canary.rules': 'installed-fapolicyd-canary',
    '/etc/fapolicyd/rules.d/02-oh-no-parent-control-original-allow.rules': 'installed-fapolicyd-original-policy',
    '/etc/fapolicyd/rules.d/99-oh-no-parent-control-allow.rules': 'installed-fapolicyd-fallback',
    '/etc/fapolicyd/trust.d/oh-no-parent-control.trust': 'installed-child-extension-trust',
}
LAYERS = {'/etc/fapolicyd/rules.d/01-oh-no-parent-control-deny.rules',
          '/etc/fapolicyd/rules.d/89-oh-no-parent-control.rules'}


class Policy:
    def __init__(self, root=Path('/')):
        self.root = root
        self.state = self.path(STATE)

    def path(self, name):
        return self.root / name.lstrip('/')

    def secure(self, path, *, directory=False, private=False):
        # The injectable root is only used by host regressions; production
        # checks all ancestors starting at /. Never adopt links or hardlinks.
        relatives = path.relative_to(self.root).parts
        for depth in range(len(relatives)):
            parent = self.root.joinpath(*relatives[:depth])
            info = parent.lstat()
            if not stat.S_ISDIR(info.st_mode) or info.st_uid != OWNER or info.st_mode & 0o022:
                raise ValueError('unsafe execution-policy ancestor')
        info = path.lstat()
        expected = stat.S_ISDIR if directory else stat.S_ISREG
        if (not expected(info.st_mode) or info.st_uid != OWNER or info.st_mode & 0o022
                or (not directory and info.st_nlink != 1)
                or (private and stat.S_IMODE(info.st_mode) != 0o600)):
            raise ValueError('unsafe execution-policy ownership')
        return info

    def run(self, arguments):
        result = subprocess.run(arguments, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                text=True, timeout=30, env={**os.environ, 'LC_ALL': 'C'})
        if len(result.stdout) > 1024 * 1024:
            raise ValueError('execution-policy command output exceeds limit')
        return result

    def record(self):
        if not self.state.exists() and not self.state.is_symlink():
            return None
        info = self.secure(self.state, private=True)
        if info.st_size > 4096:
            raise ValueError('execution-policy provenance exceeds limit')
        value = json.loads(self.state.read_text())
        if (not isinstance(value, dict) or set(value) != {'purpose', 'basis', 'active', 'enabled', 'permissive'}
                or value['purpose'] != PURPOSE or value['basis'] not in ('absent', 'dependency', 'preserve')
                or type(value['active']) is not bool or type(value['enabled']) is not bool
                or type(value['permissive']) is not bool
                or (value['basis'] != 'preserve' and (value['active'] or value['enabled']))
                or (value['permissive'] and value['basis'] == 'preserve')):
            raise ValueError('invalid execution-policy provenance')
        return value

    def save(self, value):
        if not self.state.parent.exists() and not self.state.parent.is_symlink():
            self.secure(self.state.parent.parent, directory=True)
            self.state.parent.mkdir(mode=0o700)
        self.secure(self.state.parent, directory=True)
        self.record()  # Existing finite records must be ours, even on retry.
        descriptor, temporary = tempfile.mkstemp(prefix='.fedora-execution-', dir=self.state.parent)
        try:
            with os.fdopen(descriptor, 'w') as stream:
                json.dump(value, stream, sort_keys=True)
                stream.write('\n')
                stream.flush()
                os.fsync(stream.fileno())
            os.replace(temporary, self.state)
            directory = os.open(self.state.parent, os.O_RDONLY | os.O_DIRECTORY)
            try:
                os.fsync(directory)
            finally:
                os.close(directory)
        finally:
            Path(temporary).unlink(missing_ok=True)

    def owned(self, name):
        path = self.path(name)
        self.secure(path)
        if name in INTEGRATIONS:
            witness = self.state.parent / INTEGRATIONS[name]
            self.secure(witness, private=True)
            return path.read_bytes() == witness.read_bytes()
        witness = self.state.parent / 'installed-fapolicyd-fallback'
        self.secure(witness, private=True)
        return path.read_bytes().startswith(b'# Generated by Oh No! Parent Control. Do not edit.\n')

    def stock(self, *, product=False, compiled=True):
        """Compare relevant files with native RPM digest/owner/mode metadata.

        rpm -V also checks mutable files outside policy. We instead validate
        the exact config inventory and every relevant RPM file, rejecting both
        edits and unowned additions. Generated compiled files are checked by
        the supported compiler when classifying an installed dependency.
        """
        config = self.path('/etc/fapolicyd')
        self.secure(config, directory=True)
        if self.path('/etc/fapolicyd/fapolicyd.rules').exists():
            return False
        algorithm = self.run(['rpm', '-q', '--queryformat', '%{FILEDIGESTALGO}', 'fapolicyd'])
        if algorithm.returncode or algorithm.stdout not in ('8', '10'):
            return False
        digest_type = {'8': 'sha256', '10': 'sha512'}[algorithm.stdout]
        result = self.run(['rpm', '-q', '--queryformat',
                           '[%{FILENAMES}\t%{FILEDIGESTS}\t%{FILEMODES}\t%{FILEUSERNAME}\t%{FILEGROUPNAME}\t%{FILEFLAGS}\n]',
                           'fapolicyd'])
        if result.returncode:
            return False
        expected, samples = {}, {}
        for line in result.stdout.splitlines():
            parts = line.split('\t')
            if len(parts) != 6:
                return False
            name, digest, mode, owner, group, flags = parts
            if int(flags) & 64:  # RPMFILE_GHOST: generated files have no shipped digest.
                continue
            if name != '/etc/fapolicyd' and not name.startswith(('/etc/fapolicyd/', '/usr/share/fapolicyd/')):
                continue
            destination = expected if name == '/etc/fapolicyd' or name.startswith('/etc/fapolicyd/') else samples
            if name in destination or '..' in Path(name).parts or owner != 'root':
                return False
            destination[name] = (digest, int(mode), grp.getgrnam(group).gr_gid)
        if '/etc/fapolicyd/fapolicyd.conf' not in expected:
            return False
        native_directory = expected.pop('/etc/fapolicyd', None)
        config_info = self.secure(config, directory=True)
        if native_directory is None or (config_info.st_mode, config_info.st_gid) != native_directory[1:]:
            return False
        # Fedora copies the known-libs defaults from RPM-owned sample files in
        # %post; the live rule paths themselves are ghost entries. Verify their
        # exact shipped source bytes, not a ghost's nonexistent RPM digest.
        listing = '/usr/share/fapolicyd/default-ruleset.known-libs'

        def shipped(name):
            if name not in samples:
                raise ValueError('missing shipped policy source')
            path = self.path(name)
            info = self.secure(path)
            digest, mode, gid = samples[name]
            data = path.read_bytes()
            if (info.st_mode != mode or info.st_gid != gid or not digest
                    or hashlib.new(digest_type, data).hexdigest() != digest):
                raise ValueError('modified shipped policy source')
            return data

        defaults = shipped(listing).decode().splitlines()
        if (not defaults or len(defaults) > 64 or len(set(defaults)) != len(defaults)
                or any(not re.fullmatch(r'[0-9][A-Za-z0-9._-]{0,127}\.rules', name) for name in defaults)):
            return False
        rules_gid = expected.get('/etc/fapolicyd/rules.d', ('', 0, -1))[2]
        if rules_gid == -1:
            return False
        for filename in defaults:
            sample = '/usr/share/fapolicyd/sample-rules/' + filename
            data = shipped(sample)
            expected['/etc/fapolicyd/rules.d/' + filename] = (
                hashlib.new(digest_type, data).hexdigest(), samples[sample][1], rules_gid)
        actual = {}
        for path in config.rglob('*'):
            name = '/' + path.relative_to(self.root).as_posix()
            info = self.secure(path, directory=path.is_dir() and not path.is_symlink())
            if name in GENERATED:
                continue
            if product and name in INTEGRATIONS.keys() | LAYERS:
                if not self.owned(name):
                    return False
                continue
            if name not in expected:
                return False
            actual[name] = path
            digest, mode, gid = expected[name]
            if info.st_mode != mode or info.st_gid != gid:
                return False
            if stat.S_ISREG(info.st_mode):
                if not digest or hashlib.new(digest_type, path.read_bytes()).hexdigest() != digest:
                    return False
        if set(actual) != set(expected):
            return False
        if compiled:
            result = self.run(['/usr/sbin/fagenrules', '--check'])
            if result.returncode or '/usr/sbin/fagenrules: No change' not in result.stdout.splitlines():
                return False
        return True

    def capture(self):
        baseline = self.state.parent / 'fapolicyd-before-install'
        if baseline.exists() or baseline.is_symlink():
            self.secure(baseline, directory=True)
            # Upgrades/configuration retries preserve the original provenance.
            # Legacy versions had no receipt: their prior policy stays intact.
            self.record()
            return
        self.record()
        installed = self.run(['rpm', '-q', '--queryformat', '%{NAME}', 'fapolicyd'])
        state = self.run(['systemctl', 'show', 'fapolicyd.service', '--property=LoadState',
                          '--property=ActiveState', '--property=UnitFileState'])
        rows = [line.split('=', 1) for line in state.stdout.splitlines()]
        service = dict(rows) if all(len(row) == 2 for row in rows) else {}
        known = (state.returncode == 0 and len(rows) == 3 and
                 set(service) == {'LoadState', 'ActiveState', 'UnitFileState'})
        inactive = known and service['ActiveState'] in ('inactive', 'failed')
        disabled = known and service['UnitFileState'] == 'disabled'
        missing = (known and service['LoadState'] == 'not-found' and inactive and
                   service['UnitFileState'] == '')
        # Unknown states never authorize permissive integration. For preserved
        # policies the shared preinst captures the native service flags; only
        # proven clean provenance overrides its post-dependency snapshot.
        active = not inactive
        enabled = not (disabled or missing)
        basis = 'preserve'
        if not active and not enabled:
            config = self.path('/etc/fapolicyd')
            if installed.returncode == 1 and missing and not config.exists() and not config.is_symlink():
                basis = 'absent'
            elif installed.returncode == 0 and installed.stdout == 'fapolicyd' and service['LoadState'] == 'loaded':
                # Read existing committed DNF metadata in pretrans. New reasons
                # are committed only after RPM posttrans has finished.
                reason = self.run(['dnf5', '--quiet', '--cacheonly', '--disable-repo=*',
                                   'repoquery', '--installed', '--queryformat', '%{name}|%{reason}',
                                   'fapolicyd'])
                if (reason.returncode == 0 and reason.stdout.strip() in
                        ('fapolicyd|Dependency', 'fapolicyd|Weak Dependency')):
                    try:
                        if self.stock():
                            basis = 'dependency'
                    except (OSError, ValueError, KeyError):
                        pass  # Unproven/custom policy is preserved, never adopted.
        self.save(dict(purpose=PURPOSE, basis=basis, active=active, enabled=enabled, permissive=False))

    def eligible(self):
        value = self.record()
        # Configuration is allowed to have pending owned source changes before
        # the readiness gate compiles them. Pretrans alone validates the prior
        # compiled policy while classifying a retained dependency.
        allowed = bool(value and value['basis'] != 'preserve' and self.stock(product=True, compiled=False))
        if value and value['permissive'] and not allowed:
            raise ValueError('originally permissive policy changed; preserve administrator edits')
        return allowed

    def commit(self):
        if not self.eligible() or not self.owned('/etc/fapolicyd/rules.d/02-oh-no-parent-control-original-allow.rules'):
            raise ValueError('original policy was not integrated')
        value = self.record()
        value['permissive'] = True
        self.save(value)

    def flags(self):
        value = self.record()
        if value is None or value['basis'] == 'preserve':
            return
        baseline = self.state.parent / 'fapolicyd-before-install.pending'
        self.secure(baseline, directory=True)
        for name in ('active', 'enabled'):
            path = baseline / name
            if path.exists() or path.is_symlink():
                self.secure(path)
            if value[name]:
                path.touch(mode=0o600)
            else:
                path.unlink(missing_ok=True)

    def restore_stock(self):
        value = self.record()
        # Source classification deliberately precedes compilation: the live
        # compiled file can still contain our just-removed integrations.
        return bool(value and value['basis'] != 'preserve' and self.stock(compiled=False))

    def cleanup(self):
        if self.record() is not None:
            self.state.unlink()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=('capture', 'eligible', 'commit', 'flags', 'restore-stock', 'cleanup'))
    arguments = parser.parse_args()
    if os.geteuid() != 0:
        parser.exit(1, 'fedora-execution-policy: must run as root\n')
    policy = Policy()
    try:
        action = arguments.action.replace('-', '_')
        result = getattr(policy, action)()
        if arguments.action in ('eligible', 'restore-stock'):
            print('yes' if result else 'no')
    except (OSError, ValueError, KeyError, subprocess.SubprocessError):
        # Stable diagnostic; source names and package output stay private.
        parser.exit(1, 'fedora-execution-policy: unsafe or unproven original policy\n')


if __name__ == '__main__':
    main()
