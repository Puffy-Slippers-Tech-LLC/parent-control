"""Fresh fixture passwords, provisioned once on the held, never-booted guest.

Use virt-customize's public password-file interface. No baseline password is
stored or requested, no root password is changed, and no guest command is run.
The outer lease owns restoration even after a partial provisioning failure.
"""

import os
from pathlib import Path
import re
import secrets
import stat
import sys

from private_artifacts import EvidenceError, _directory, _read, require
from secret_variables import SecretVariables, PASSWORD_VARIABLES

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'tests/integration'))
from system_runner import mounted_guest
from owned_commands import Commands
import prepare_vm
sys.path.pop(0)

# Reuse the canonical fixture identities, never a caller-supplied account.
ACCOUNTS = dict(zip(('parent', 'other-parent', 'child', 'other-child'),
                    prepare_vm.IDENTITIES, strict=True))

VT6_LOGIN_TIMEOUT = 600


def provision_vt6_login_window(lease, verified, guestfs):
    """Bound stock login's lifetime around full checks on the offline fixture.

    Only the active disk is changed; the outer lease restores it even after a
    partial write. The accepted baseline and host login configuration are inputs,
    never write targets. No PAM, authentication retries or input gates change.
    """
    boundary = 'lease'
    try:
        require(lease is verified.lease and lease.fd is not None
                and lease.state['phase'] == 'isolated'
                and lease.state['domain_id'] is None, 'credential:outside-provisioning')
        lease.guard(off=True)
        path = '/etc/login.defs'
        boundary = 'mount'
        with mounted_guest(guestfs, lease) as g:
            def metadata():
                require(g.realpath(path) == path, 'credential:login-path')
                info = g.lstatns(path)
                require(stat.S_ISREG(info['st_mode']) and info['st_uid'] == 0
                        and info['st_gid'] == 0 and info['st_nlink'] == 1
                        and not info['st_mode'] & 0o7022,
                        'credential:login-file')
                return tuple(info[key] for key in
                             ('st_dev', 'st_ino', 'st_mode', 'st_uid', 'st_gid', 'st_nlink'))
            boundary = 'metadata'
            before = metadata()
            boundary = 'read'
            require(0 < g.filesize(path) <= 65536, 'credential:login-size')
            original = g.read_file(path)
            require(len(original) <= 65536 and b'\x00' not in original,
                    'credential:login-content')
            boundary = 'configuration'
            lines = original.splitlines(keepends=True)
            selected = [i for i, line in enumerate(lines)
                        if line.split() and line.split()[0] == b'LOGIN_TIMEOUT']
            require(len(selected) == 1, 'credential:login-setting')
            index = selected[0]
            match = re.fullmatch(rb'([ \t]*LOGIN_TIMEOUT[ \t]+)(60|600)([ \t]*(?:#[^\r\n]*)?)(\r?\n)?',
                                 lines[index])
            require(match is not None, 'credential:login-setting')
            lines[index] = (match[1] + str(VT6_LOGIN_TIMEOUT).encode('ascii')
                            + match[3] + (match[4] or b''))
            prepared = b''.join(lines)
            boundary = 'before-write'
            # mounted_guest runs the full disk/lease guard before opening and
            # after closing its appliance. Reentering it here would run locking
            # qemu-img info against the disk held by our own libguestfs writer.
            require(metadata() == before, 'credential:login-file-changed')
            boundary = 'write'
            if prepared != original:
                g.write(path, prepared)
            boundary = 'readback'
            require(metadata() == before and g.read_file(path) == prepared,
                    'credential:login-write-failed')
            boundary = 'close'
        boundary = 'after-close'
        lease.guard(off=True)
        return {'login_timeout_seconds': VT6_LOGIN_TIMEOUT,
                'configuration': 'login.defs', 'readback_verified': True}
    except BaseException as error:
        if isinstance(error, (KeyboardInterrupt, SystemExit)):
            raise KeyboardInterrupt('credential:login-window-interrupted') from None
        # Preserve only our fixed predicates, never an exception's guest path,
        # file contents or libguestfs diagnostic text. Other failures retain the
        # exact operation boundary, so a failed attempt is actionable.
        safe = {'credential:' + suffix for suffix in (
            'outside-provisioning', 'login-path', 'login-file', 'login-size',
            'login-content', 'login-setting', 'login-file-changed', 'login-write-failed')}
        code = str(error) if isinstance(error, EvidenceError) and str(error) in safe else (
            'credential:login-window-' + boundary + '-failed')
        raise EvidenceError(code) from None


def preflight(commands):
    require(commands.run(['dpkg-query', '-W', '-f=${Version}', 'openssl'], timeout=10)
            == b'3.5.5-1ubuntu3.5', 'credential:openssl-prerequisite')


def shadow(g):
    """Read only canonical account databases; raw identities/hashes stay private."""
    for path in ('/etc/passwd', '/etc/shadow'):
        require(g.realpath(path) == path, 'credential:account-path')
        info = g.lstatns(path)
        require(info['st_uid'] == 0 and info['st_nlink'] == 1
                and info['st_mode'] & 0o170000 == 0o100000, 'credential:account-file')
    require(g.filesize('/etc/shadow') <= 1024 * 1024, 'credential:account-size')
    rows = [line.split(':') for line in g.read_file('/etc/shadow').decode('ascii').splitlines()]
    require(all(len(row) == 9 for row in rows)
            and len({row[0] for row in rows}) == len(rows), 'credential:account-records')
    return rows


class FixtureCredentials:
    def __init__(self):
        self.__passwords = {role: secrets.token_hex(24) for role in PASSWORD_VARIABLES}
        self.variables = SecretVariables(self.__passwords)
        self._attempted = False
        self._lease = None
        self._ready = False

    def __repr__(self):
        return '<FixtureCredentials [redacted]>'

    def worker_secrets(self, lease):
        require(self._ready and lease is self._lease and lease.fd is not None
                and lease.state['phase'] == 'isolated'
                and lease.state['domain_id'] is None, 'credential:provisioning-required')
        lease.guard(off=True)
        return self.variables

    def provision(self, lease, verified, directory, guestfs, commands):
        require(not self._attempted, 'credential:already-attempted')
        self._attempted = True
        try:
            require(lease is verified.lease and lease.fd is not None
                    and lease.state['phase'] == 'isolated'
                    and lease.state['domain_id'] is None, 'credential:outside-provisioning')
            lease.guard(off=True)
            verified.recheck()
            # Match the accepted baseline's account identities before any write.
            with mounted_guest(guestfs, lease, readonly=True) as g:
                before = shadow(g)
                passwd = g.read_file('/etc/passwd')
                records = [line.split(':') for line in passwd.decode('ascii').splitlines()]
                expected = lease.capture.state['guest']['accounts']
                for account in ACCOUNTS.values():
                    rows = [row for row in records if row[0] == account.username]
                    require(len(rows) == 1 and len(rows[0]) == 7
                            and rows[0][2] == str(expected[account.username]['uid'])
                            and rows[0][6] == prepare_vm.INTERACTIVE_SHELL
                            and sum(row[0] == account.username for row in before) == 1,
                            'credential:fixture-identity')
            directory = Path(directory)
            parent = _directory(directory)
            os.close(parent)
            private = directory / 'fixture-secrets'
            private.mkdir(mode=0o700)
            paths = self.variables.stage_password_files(private)
            pinned = _directory(private)
            try:
                def check_files():
                    current = _directory(private)
                    try:
                        old, new = os.fstat(pinned), os.fstat(current)
                        require((old.st_dev, old.st_ino) == (new.st_dev, new.st_ino),
                                'credential:directory-replaced')
                        require(set(os.listdir(pinned)) == {path.name for path in paths.values()},
                                'credential:secret-files')
                        for role, path in paths.items():
                            require(_read(pinned, path.name) == self.__passwords[role].encode('ascii'),
                                    'credential:secret-file-changed')
                    finally:
                        os.close(current)
                check_files()
                lease.guard(off=True)
                disk = lease.capture.state['source']['layout']['disk']
                args = ['virt-customize', '--format', 'qcow2', '-a', disk,
                        '--no-network', '--password-crypto', 'sha512']
                for role, account in ACCOUNTS.items():
                    args.extend(('--password', account.username + ':file:' + str(paths[role])))
                print('e2e:fixture-credentials-started', file=sys.stderr, flush=True)
                commands.run(args, timeout=300)
                lease.guard(off=True)
                check_files()
            finally:
                os.close(pinned)
            with mounted_guest(guestfs, lease, readonly=True) as g:
                after = shadow(g)
                require(g.read_file('/etc/passwd') == passwd, 'credential:identity-changed')
                require([row[0] for row in before] == [row[0] for row in after],
                        'credential:accounts-changed')
                roles = {account.username: role for role, account in ACCOUNTS.items()}
                for old, new in zip(before, after, strict=True):
                    role = roles.get(old[0])
                    if role is None:
                        require(old == new, 'credential:unrelated-account-changed')
                        continue
                    require(old[:1] + old[2:] == new[:1] + new[2:]
                            and old[1] != new[1], 'credential:fixture-state-changed')
                    match = re.fullmatch(r'\$6\$([./a-zA-Z0-9]{1,16})\$[./a-zA-Z0-9]{86}', new[1])
                    require(match is not None, 'credential:password-hash')
                    # Only stdin contains the password. No diagnostic directory:
                    # password hashes never enter command artifacts or reports.
                    hashed = Commands().run(['/usr/bin/openssl', 'passwd', '-6', '-salt', match[1], '-stdin'],
                                            input=self.__passwords[role].encode('ascii') + b'\n',
                                            timeout=10, merge_stderr=False)
                    require(hashed.strip() == new[1].encode('ascii'), 'credential:password-mismatch')
            verified.recheck()
            self._lease, self._ready = lease, True
            print('e2e:fixture-credentials-verified', file=sys.stderr, flush=True)
            return {'accounts': len(ACCOUNTS), 'passwords_verified': True,
                    'unrelated_accounts_preserved': True}
        except BaseException as error:
            self._ready = False
            print('e2e:fixture-credentials-rejected', file=sys.stderr, flush=True)
            if isinstance(error, KeyboardInterrupt):
                raise KeyboardInterrupt('credential:provisioning-interrupted') from None
            raise EvidenceError('credential:provisioning-failed') from None
