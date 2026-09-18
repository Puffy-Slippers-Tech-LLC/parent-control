"""Shared .envrc fixture password, verified without changing the offline guest."""

from pathlib import Path
import re
import stat
import sys

from private_artifacts import EvidenceError, require
from secret_variables import SecretVariables, PASSWORD_VARIABLES

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'tests/integration'))
from system_runner import mounted_guest
from test_account_password import read_password, matches
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
    read_password()


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
        password = read_password()
        self.__passwords = {role: password for role in PASSWORD_VARIABLES}
        from watch_activity import secret
        secret(password)
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
        """Verify the prepared accounts. Never change a password or keyring."""
        require(not self._attempted, 'credential:already-attempted')
        self._attempted = True
        try:
            require(lease is verified.lease and lease.fd is not None
                    and lease.state['phase'] == 'isolated'
                    and lease.state['domain_id'] is None, 'credential:outside-provisioning')
            lease.guard(off=True)
            verified.recheck()
            configured = read_password()
            require(all(value == configured for value in self.__passwords.values()),
                    'credential:configuration-changed')
            with mounted_guest(guestfs, lease, readonly=True) as g:
                hashes = shadow(g)
                records = [line.split(':') for line in
                           g.read_file('/etc/passwd').decode('ascii').splitlines()]
                expected = lease.capture.state['guest']['accounts']
                for role, account in ACCOUNTS.items():
                    rows = [row for row in records if row[0] == account.username]
                    saved = [row for row in hashes if row[0] == account.username]
                    require(len(rows) == 1 and len(rows[0]) == 7
                            and rows[0][2] == str(expected[account.username]['uid'])
                            and rows[0][5] == '/home/' + account.username
                            and rows[0][6] == prepare_vm.INTERACTIVE_SHELL
                            and len(saved) == 1, 'credential:fixture-identity')
                    require(matches(self.__passwords[role], saved[0][1]),
                            'credential:password-mismatch; run make prepare-baseline')
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
            raise EvidenceError('credential:verification-failed; check .envrc and run make prepare-baseline') from None
