"""Observe installed kiosk pause and SSH admission against real logind and Malcontent."""

from contextlib import contextmanager
import json
import os
from pathlib import Path
import pwd
import signal
import stat
import subprocess
import tempfile
import time

import system_guest as guest
from system_assertions import accepted, call, session_limits
from system_graphical_expiry import child_session, wait_for
from system_session_expiry import identities


ALLOWANCE_MINUTES = 120


def session_properties(session, *names, category='pause-capture:session-properties'):
    return guest.parse_properties(guest.run(['loginctl', 'show-session', session,
        *(f'--property={name}' for name in names)], timeout=10), names,
        category=category)


def listed_child_sessions(uid):
    rows = guest.run(['loginctl', 'list-sessions', '--no-legend', '--no-pager'], timeout=10).splitlines()
    sessions = []
    for row in rows:
        session, user, *_ = row.split()
        if user == str(uid):
            sessions.append(session)
    return sessions


def ssh_sessions(uid):
    sessions = set()
    for session in listed_child_sessions(uid):
        try:
            props = session_properties(session, 'User', 'Service', 'Remote', 'RemoteHost', 'Type',
                                       category='child-ssh:session-properties')
        except guest.CommandError:
            # A closing session can disappear after list-sessions. Confirm
            # that exact ID is gone before treating the failed read as closure.
            if session not in listed_child_sessions(uid):
                continue
            raise
        if props['Service'] == 'sshd':
            guest.require(props['User'] == str(uid) and props['Remote'] == 'yes'
                          and props['RemoteHost'] in ('127.0.0.1', 'localhost')
                          and props['Type'] not in ('wayland', 'x11'),
                          'child-ssh:unexpected-session-identity')
            sessions.add(session)
    return sessions


def ssh_failure(client, started):
    error = client.stderr.read(4096).decode(errors='replace').lower()
    journal = guest.run(['journalctl', '-b', '-u', 'sshd.service', '-u', 'ssh.service',
                         '--no-pager', '-n', '35', '-o', 'cat', f'--since=@{started}'],
                        timeout=15).lower()
    guest.run(['journalctl', '-b', '_TRANSPORT=audit',
               '--no-pager', '-n', '35', '-o', 'cat', f'--since=@{started}'], timeout=15)
    reasons = (
        ('bad ownership or modes', 'authorized-key-permissions'),
        ('access denied', 'account-access-refused'),
        ('host key verification failed', 'host-key-verification'),
        ('load key', 'client-key-unreadable'),
        ('operation not permitted', 'operation-refused'),
        ('permission denied', 'authentication-refused'),
        ('connection refused', 'connection-refused'),
        ('connection closed', 'connection-closed'),
        ('connection reset', 'connection-reset'),
    )
    reason = next((label for message, label in reasons if message in error or message in journal),
                  'unexpected-exit')
    raise guest.GuestError(f'child-ssh:client-exited:{client.returncode}:{reason}')


@contextmanager
def child_ssh_identity(uid, scratch):
    guest.guard()
    account = pwd.getpwuid(uid)
    home = Path(account.pw_dir)
    info = home.lstat()
    guest.require(home.resolve() == home and info.st_uid == uid and stat.S_ISDIR(info.st_mode)
                  and not ssh_sessions(uid), 'child-ssh:home-or-existing-session')
    with tempfile.TemporaryDirectory(dir=scratch) as directory:
        key = Path(directory) / 'identity'
        guest.run(['ssh-keygen', '-q', '-t', 'ed25519', '-N', '', '-f', str(key)], timeout=20)
        known_hosts = key.with_name('known_hosts')
        host_key = Path('/etc/ssh/ssh_host_ed25519_key.pub').read_text().split()[:2]
        known_hosts.write_text('127.0.0.1 ' + ' '.join(host_key) + '\n')
        ssh_dir = home / '.ssh'
        ssh_dir.mkdir(mode=0o755)  # Exclusive: never replace a child's SSH configuration.
        owned = ssh_dir.lstat()
        authorized = ssh_dir / 'authorized_keys'
        try:
            ssh_dir.chmod(0o755)
            with authorized.open('x') as stream:
                stream.write('restrict,from="127.0.0.1" ' + key.with_suffix('.pub').read_text())
                os.fchmod(stream.fileno(), 0o644)
            if guest.package_path().suffix == '.rpm':
                guest.run(['restorecon', str(ssh_dir), str(authorized)], timeout=15)
            yield ['ssh', '-F', '/dev/null', '-o', 'BatchMode=yes', '-o',
                   'PreferredAuthentications=publickey', '-o', 'IdentitiesOnly=yes',
                   '-o', 'IdentityAgent=none', '-o', 'ConnectTimeout=10',
                   '-o', 'StrictHostKeyChecking=yes', '-o', 'UpdateHostKeys=no',
                   '-o', 'GlobalKnownHostsFile=/dev/null', '-o', f'UserKnownHostsFile={known_hosts}',
                   '-i', str(key), '-T', account.pw_name + '@127.0.0.1', '/usr/bin/cat']
        finally:
            current = ssh_dir.lstat()
            guest.require((current.st_dev, current.st_ino) == (owned.st_dev, owned.st_ino),
                          'child-ssh:directory-replaced')
            authorized.unlink(missing_ok=True)
            ssh_dir.rmdir()


@contextmanager
def child_ssh(uid, ssh):
    started = int(time.time())
    try:
        with subprocess.Popen(ssh, stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                              stderr=subprocess.PIPE) as client:
            try:
                pin = os.pidfd_open(client.pid)
            except BaseException:
                client.stdin.close()
                raise
            try:
                def connected():
                    if client.poll() is not None:
                        ssh_failure(client, started)
                    return ssh_sessions(uid)

                active = wait_for(connected, 'child-ssh:no-session', timeout=20)
                guest.require(len(active) == 1, 'child-ssh:ambiguous-session')
                probe = b'onpc-ssh-session\n'
                reply = bytearray()
                os.set_blocking(client.stdout.fileno(), False)
                client.stdin.write(probe)
                client.stdin.flush()

                def echoed():
                    if client.poll() is not None:
                        ssh_failure(client, started)
                    reply.extend(client.stdout.read(len(probe) - len(reply)) or b'')
                    guest.require(probe.startswith(reply), 'child-ssh:unexpected-remote-command-reply')
                    return reply == probe

                wait_for(echoed, 'child-ssh:no-remote-command-reply', timeout=15)
                yield active
            finally:
                try:
                    client.stdin.close()
                    try:
                        client.wait(timeout=5)
                    except subprocess.TimeoutExpired:
                        try:
                            signal.pidfd_send_signal(pin, signal.SIGKILL)
                        except ProcessLookupError:
                            pass
                        client.wait(timeout=5)
                finally:
                    os.close(pin)
    finally:
        wait_for(lambda: not ssh_sessions(uid), 'child-ssh:session-did-not-end', timeout=15)


def require_ssh_account_refusal(uid, ssh):
    server_log = ['journalctl', '-b', '-u', 'sshd.service', '--no-pager']
    before = guest.run([*server_log, '-n', '1', '-o', 'json'], timeout=10)
    guest.require(bool(before), 'ssh-admission:missing-server-journal')
    cursor = json.loads(before)['__CURSOR']
    output = guest.commands.run(['env', 'LC_ALL=C', ssh[0], '-vvv', *ssh[1:]],
                                check=False, timeout=20)
    status = guest.commands.last_returncode
    guest.require(status == 255, f'ssh-admission:exhausted-client-status:{status}')
    guest.require(b'Server accepts key:' in output and b'signing using ssh-ed25519 ' in output,
                  'ssh-admission:key-not-accepted-and-signed')

    # sshd enters PAM account management after verifying the signed key request.
    account = pwd.getpwuid(uid).pw_name
    denial = f'Access denied for user {account} by PAM account configuration'
    wait_for(lambda: denial in guest.run([*server_log, f'--after-cursor={cursor}', '-o', 'cat'],
                                        timeout=10), 'ssh-admission:no-pam-account-refusal', timeout=15)
    guest.require(not ssh_sessions(uid), 'ssh-admission:exhausted-session-open')


def verify_ssh_admission(record, scratch):
    guest.guard()  # Enforcing is the guarded Fedora default.
    guest.require(guest.package_path().suffix == '.rpm', 'ssh-admission:requires-fedora')
    accounts = identities()
    parent, child = accounts['parent'], accounts['child']
    guest.require(child_session(child) is None, 'ssh-admission:child-desktop-already-open')

    def set_allowance(minutes):
        accepted(call(parent, 'SetParentControl', '(ubu)', (child, True, minutes)),
                 category='ssh-admission:parent-save-failed')
        guest.require(session_limits(child) == (2, minutes * 60, [0, 0]),
                      'ssh-admission:unexpected-native-limits')
        daily, grant, requested, total = accepted(call(parent, 'GetTimeStatus', '(uu)', (child, 0)),
                                                category='ssh-admission:parent-time-unavailable')
        has_expected_time = 0 < daily <= minutes * 60 if minutes else daily == 0
        guest.require(has_expected_time and grant == requested == 0 and total == daily,
                      'ssh-admission:unexpected-parent-time')

    with child_ssh_identity(child, scratch) as ssh:
        accepted(call(parent, 'RevokeOneTimeGrant', '(u)', (child,)),
                 category='ssh-admission:parent-revoke-failed')
        set_allowance(ALLOWANCE_MINUTES)
        with child_ssh(child, ssh):
            record('onpc.ssh-admission.available-time', 'publickey; sshd-logind-session; command-round-trip')
        set_allowance(0)
        require_ssh_account_refusal(child, ssh)
        record('onpc.ssh-admission.exhausted', 'signed-key; pam-account-refused; no-session')
        set_allowance(ALLOWANCE_MINUTES)
        with child_ssh(child, ssh):
            record('onpc.ssh-admission.restored-time', 'publickey; sshd-logind-session; command-round-trip')
    guest.require(guest.run(['getenforce']) == 'Enforcing', 'ssh-admission:selinux-not-enforcing')
