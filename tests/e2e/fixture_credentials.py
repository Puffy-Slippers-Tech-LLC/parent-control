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
    """Verify the baseline login timeout without repairing the attempt."""
    from baseline_console import login_window
    require(lease is verified.lease and lease.fd is not None
            and lease.state['phase'] == 'isolated'
            and lease.state['domain_id'] is None, 'credential:outside-provisioning')
    try:
        lease.guard(off=True)
        with mounted_guest(guestfs, lease, readonly=True) as g:
            result = login_window(g)
        lease.guard(off=True)
        return result
    except (KeyboardInterrupt, SystemExit):
        raise KeyboardInterrupt('credential:login-window-interrupted') from None
    except Exception:
        raise EvidenceError('credential:login-window-verification-failed; run tools/prepare-baseline') from None


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
        self._online = False

    def __repr__(self):
        return '<FixtureCredentials [redacted]>'

    def worker_secrets(self, lease, *, online=False):
        require(self._ready and lease is self._lease and lease.fd is not None
                and online is self._online
                and lease.state['phase'] == ('running' if online else 'isolated')
                and (lease.state['domain_id'] is not None if online else
                     lease.state['domain_id'] is None), 'credential:provisioning-required')
        lease.guard(off=not online)
        return self.variables

    def provision_online(self, lease, transport):
        """Diagnostic workers reuse the snapshot's live credential verifier."""
        from online_snapshot import verify_credentials
        require(not self._attempted, 'credential:already-attempted')
        self._attempted = True
        require(lease.fd is not None and lease.state['phase'] == 'running'
                and lease.state['domain_id'] is not None, 'credential:outside-provisioning')
        lease.guard()
        require(all(value == read_password() for value in self.__passwords.values()),
                'credential:configuration-changed')
        verify_credentials(transport, lease)
        lease.guard()
        self._lease, self._ready, self._online = lease, True, True

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
                            'credential:password-mismatch; run tools/prepare-baseline')
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
            raise EvidenceError('credential:verification-failed; check .envrc and run tools/prepare-baseline') from None
