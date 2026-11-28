"""Observe installed kiosk pause and SSH admission against real logind and Malcontent."""

from contextlib import contextmanager
from datetime import datetime
import json
import math
import os
from pathlib import Path
import pwd
import signal
import stat
import subprocess
import sys
import tempfile
import time

from gi.repository import Gio, GLib

import system_guest as guest
from system_assertions import accepted, account_property, call, session_limits
from system_caller import FixturePassword, PersistentCaller, SessionCaller, TextAgent
from system_extension_monitor import Shell
from system_graphical_expiry import child_session, wait_for
from system_session_expiry import LIMITS, identities, installed_manager
from system_usage_checkpoint import (TIMER, Trace, bus_identity, covered, is_call,
                                     is_reply, merge, shell_senders, values)


LOGIN = 'org.freedesktop.login1'
SESSION = LOGIN + '.Session'
PROPERTIES = 'org.freedesktop.DBus.Properties'
ACCOUNTS = 'org.freedesktop.Accounts'
ALLOWANCE_MINUTES = 120
AWAY_SECONDS = 8
LOCK_TIMEOUT_SECONDS = 5
TRANSFER_MARGIN_SECONDS = 5
VT = '6'


def prepare():
    guest.guard()
    accounts = identities()
    child = accounts['child']
    account, _ = installed_manager()._account(child)
    guest.require(child_session(child) is None and not account_property(
        child, ACCOUNTS + '.User', 'AutomaticLogin'), 'pause-capture:child-desktop-already-prepared')
    accepted(call(accounts['parent'], 'SetParentControl', '(ubu)', (child, True, ALLOWANCE_MINUTES)))
    accepted(call(accounts['parent'], 'RevokeOneTimeGrant', '(u)', (child,)))
    guest.require(session_limits(child) == (2, ALLOWANCE_MINUTES * 60, [0, 0]),
                  'pause-capture:daily-limit-fixture')
    guest.run(['busctl', '--system', 'call', ACCOUNTS, f'/org/freedesktop/Accounts/User{account.pw_uid}',
               ACCOUNTS + '.User', 'SetAutomaticLogin', 'b', 'true'])
    guest.require(account_property(child, ACCOUNTS + '.User', 'AutomaticLogin') is True,
                  'pause-capture:autologin-not-prepared')


def session_properties(session, *names, category='pause-capture:session-properties'):
    return guest.parse_properties(guest.run(['loginctl', 'show-session', session,
        *(f'--property={name}' for name in names)], timeout=10), names,
        category=category)


def child_usage(reader):
    reader.send({'kind': 'timer-self-usage'})
    return accepted(reader.receive(), category='pause-capture:cannot-read-child-usage')


def daily_remaining(records, epoch):
    day = datetime.fromtimestamp(epoch).replace(hour=0, minute=0, second=0, microsecond=0)
    start_today = int(day.timestamp())
    intervals = [(max(start, start_today), min(end, epoch)) for start, end in records
                 if max(start, start_today) < min(end, epoch)]
    return max(0, ALLOWANCE_MINUTES * 60 - covered(intervals))


def grant_status(kiosk, child):
    status = accepted(kiosk.call('GetGrantStatus', '(uu)', (child, 0)))
    guest.require(len(status) == 12, 'pause-capture:invalid-grant-status')
    return status


def approve(kiosk, accounts):
    parent, child = accounts['parent'], accounts['child']
    password = FixturePassword()
    password.install(parent)
    with TextAgent(kiosk) as agent:
        kiosk.send({'kind': 'call', 'method': 'RequestAccess', 'signature': '(uuub)',
                    'args': (child, parent, 600, False)})
        agent.prompt(parent, pwd.getpwnam('onpc-parent-casey').pw_uid)
        agent.authenticate(password)
        result = accepted(kiosk.receive(), category='pause-capture:initial-approval-failed')
    guest.require(result[1] == 'approved', 'pause-capture:initial-approval-not-committed')


def pause_trace(kiosk, child, revision, session_path, owners, other_readers):
    broker, logind, timer = owners
    # Match only the work of this pause. Observe public traffic without
    # intercepting requests, modifying the daemon, or supplying a timer reply.
    rules = (f"sender='{broker}'", f"sender='{logind}'",
             f"type='method_call',sender='{kiosk.name}',member='PauseGrant'")
    with Trace(extra_rules=rules) as trace:
        result = kiosk.call('PauseGrant', '(ut)', (child, revision))
        request = trace.until(lambda row: is_call(
            row, kiosk.name, guest.BUS, 'PauseGrant', destination=guest.BUS))
        guest.require(request is not None and values(request, '(ut)') == (child, revision),
                      'pause-capture:missing-pause-request')
        reply = trace.reply(request, broker)
        guest.require(reply is not None, 'pause-capture:missing-pause-reply')
        rows = trace.rows[trace.rows.index(request) + 1:trace.rows.index(reply)]

    def exchanges(calls, owner):
        for request in calls:
            response = next((row for row in rows if is_reply(row, request, owner)), None)
            if response is not None and response['kind'] == 2:
                yield request, response

    def broker_logind(row, member):
        return is_call(row, broker, LOGIN + '.Manager', member, destination=LOGIN)

    locks = [row for row in rows if broker_logind(row, 'LockSession')]
    locked_reads = [reply for _, reply in exchanges(
        (row for row in rows if is_call(row, broker, PROPERTIES, 'GetAll', destination=LOGIN)
         and row['path'] == session_path), logind) if values(reply, '(a{sv})')[0]['LockedHint']]
    queries = [(query, reply, values(reply, '(a(tt))')[0])
               for query, reply in exchanges(
        (row for row in rows if row['sender'] not in other_readers and row['destination'] in (TIMER, timer)
         and row['kind'] == 1 and row['interface'] == TIMER + '.Parent' and row['member'] == 'QueryUsage'
         and values(row, '(uss)') == (child, 'login-session', '')), timer)]
    writes = [row for row in rows if is_call(row, broker, PROPERTIES, 'Set', destination=ACCOUNTS)
              and row['path'] == f'/org/freedesktop/Accounts/User{child}'
              and values(row, '(ssv)')[:2] == (LIMITS, 'ActiveExtension')]
    session_checks = [row for row in rows if broker_logind(row, 'ListSessions')]
    return result, locks, locked_reads, queries, writes, session_checks


def check_pause(kiosk, child, session, path, owners, other_readers, record, *, away=None):
    before = grant_status(kiosk, child)
    source = account_property(child, LIMITS, 'ActiveExtension')
    guest.require(before[8] == 'fixed' and before[9] == sum(source),
                  'pause-capture:running-fixed-fixture')
    result, locks, locked_reads, queries, writes, session_checks = pause_trace(
        kiosk, child, before[0], path, owners, other_readers)
    label = 'raw-switch' if away else 'already-locked-with-ssh'
    if away:
        away_start, away_end, prior = away
        guest.require(len(locks) == 1 and values(locks[0], '(s)') == (session,),
                      'pause-capture:expected-lock-request-for-child-desktop')
        lock = locks[0]
        lock_read = next((row for row in locked_reads if row['monotonic'] > lock['monotonic']), None)
        if lock_read is not None:
            record('onpc.pause-capture.lock-observed-seconds',
                   f"{lock_read['monotonic'] - lock['monotonic']:.3f}")
        guest.require(lock_read is not None, 'pause-capture:broker-did-not-observe-locked-hint')
        min_end = int(lock['wall']) - 1
        old_ends = {end for _, end in prior}
        qualifying = next(((reply, usage) for query, reply, usage in queries
                           if query['monotonic'] > lock_read['monotonic'] and any(
                               min_end <= end <= int(reply['wall']) and end not in old_ends
                               for _, end in usage)), None)
        guest.require(qualifying is not None, 'pause-capture:missing-fresh-completed-usage-after-lock')
        usage_reply, completed = qualifying
        latency = usage_reply['monotonic'] - lock['monotonic']
        record('onpc.pause-capture.completed-usage-observed-seconds', f'{latency:.3f}')
        guest.require(0 < latency <= LOCK_TIMEOUT_SECONDS,
                      'pause-capture:lock-and-usage-exceeded-product-deadline')
        guest.require(any(start <= away_start and end >= away_end for start, end in merge(completed)),
                      'pause-capture:completed-usage-missed-switched-away-time')
    else:
        guest.require(not locks and locked_reads and len(queries) == 1,
                      'pause-capture:already-locked-session-required-another-lock-or-usage-poll')
        _, usage_reply, completed = queries[0]
        guest.require(completed and max(end for _, end in completed) <
                      int(usage_reply['wall']) - LOCK_TIMEOUT_SECONDS,
                      'pause-capture:already-locked-record-was-still-fresh')

    accepted(result, category=f'pause-capture:{label}-pause-did-not-succeed')
    guest.require(len(writes) == 1 and usage_reply['monotonic'] < writes[0]['monotonic'],
                  'pause-capture:grant-shortened-before-completed-usage')
    shortened = account_property(child, LIMITS, 'ActiveExtension')
    boundary = sum(shortened)
    capture_check = next((row for row in session_checks
                          if usage_reply['monotonic'] < row['monotonic'] < writes[0]['monotonic']), None)
    captured_second = boundary - TRANSFER_MARGIN_SECONDS
    guest.require(shortened[0] == source[0] and values(writes[0], '(ssv)')[2] == tuple(shortened)
                  and capture_check is not None
                  and int(usage_reply['wall']) <= captured_second <= int(capture_check['wall']),
                  'pause-capture:grant-boundary-not-set-after-usage-observation')
    after = grant_status(kiosk, child)
    elapsed_daily = daily_remaining(completed, captured_second)
    expected = sum(source) - boundary - elapsed_daily
    guest.require(expected > 0 and after[0] > before[0] and after[2] == elapsed_daily
                  and after[5] == before[5] + expected,
                  'pause-capture:saved-balance-does-not-match-completed-usage')
    if away:
        # At the same stop boundary, treating the switched-away seconds as
        # unspent daily time gives a different saved balance.
        counterfactual_daily = daily_remaining(prior, captured_second)
        guest.require(counterfactual_daily - elapsed_daily >= away_end - away_start,
                      'pause-capture:saved-balance-does-not-distinguish-switched-away-usage')
    guest.require(session_properties(session, 'Active', 'LockedHint') ==
                  {'Active': 'no', 'LockedHint': 'yes'}, 'pause-capture:child-desktop-not-locked')
    record(f'onpc.pause-capture.{label}', 'passed')
    return after[0], usage_reply['wall']


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


def verify(record, scratch):
    guest.guard()
    accounts = identities()
    child = accounts['child']
    kiosk_uid = json.loads(Path('/etc/oh-no-parent-control/config.json').read_text())['kiosk_uid']
    session, _ = wait_for(lambda: child_session(child), 'pause-capture:child-autologin')
    manager = installed_manager()
    account, _ = manager._account(child)
    address = wait_for(lambda: manager._live_session_address(account), 'pause-capture:child-bus')
    shell = Shell(account, address)
    try:
        other_readers = shell_senders(shell, child)
        system = Gio.bus_get_sync(Gio.BusType.SYSTEM, None)
        with SessionCaller(kiosk_uid) as kiosk, PersistentCaller(child) as reader:
            approve(kiosk, accounts)
            child_usage(reader)
            owners = tuple(bus_identity(system, 'GetNameOwner', name) for name in (guest.BUS, LOGIN, TIMER))
            path, = system.call_sync(LOGIN, '/org/freedesktop/login1', LOGIN + '.Manager',
                'GetSession', GLib.Variant('(s)', (session,)), GLib.VariantType.new('(o)'),
                Gio.DBusCallFlags.NONE, 5000, None).unpack()
            other_readers = {*other_readers, reader.name}
            props = session_properties(session, 'Seat', 'Active', 'LockedHint', 'VTNr')
            original_vt = props['VTNr']
            guest.require(props['Seat'] == 'seat0' and props['Active'] == 'yes' and
                          props['LockedHint'] == 'no' and original_vt.isdecimal()
                          and original_vt != VT and guest.run(['fgconsole']) == original_vt,
                          'pause-capture:child-not-on-foreground-vt')
            terminals = [row.split()[1] for row in guest.run(['who']).splitlines() if row.strip()]
            guest.require('tty' + VT not in terminals, 'pause-capture:destination-vt-in-use')
            guest.run(['chvt', VT], timeout=10)
            try:
                wait_for(lambda: session_properties(session, 'Active', 'LockedHint') ==
                         {'Active': 'no', 'LockedHint': 'no'}, 'pause-capture:raw-vt-did-not-retain-unlocked-child')
                away_start = math.ceil(time.time())
                time.sleep(AWAY_SECONDS)
                away_end = int(time.time())
                prior = child_usage(reader)
                guest.require(away_end > away_start and all(
                    end <= away_start or start >= away_end for start, end in prior),
                    'pause-capture:raw-vt-produced-completed-usage')
                guest.require(session_properties(session, 'Active', 'LockedHint') ==
                              {'Active': 'no', 'LockedHint': 'no'}, 'pause-capture:child-locked-before-pause')
                revision, first_capture = check_pause(kiosk, child, session, path, owners,
                    other_readers, record, away=(away_start, away_end, prior))
                wait_for(lambda: time.time() >= first_capture + LOCK_TIMEOUT_SECONDS + 2,
                         'pause-capture:prior-record-did-not-age', timeout=15)
                accepted(kiosk.call('UseSavedTime', '(ut)', (child, revision)),
                         category='pause-capture:cannot-start-second-fixed-grant')
                with child_ssh_identity(child, scratch) as ssh, child_ssh(child, ssh) as active:
                    check_pause(kiosk, child, session, path, owners, other_readers, record)
                    guest.require(ssh_sessions(child) == active, 'pause-capture:pause-ended-child-ssh-session')
            finally:
                guest.require(guest.run(['fgconsole']) == VT, 'pause-capture:owned-vt-replaced')
                guest.run(['chvt', original_vt], timeout=10)
                guest.require(guest.run(['fgconsole']) == original_vt, 'pause-capture:vt-not-restored')
    finally:
        shell.close()


if __name__ == '__main__':
    guest.require(sys.argv[1:] == ['prepare'], 'pause-capture:invalid-preparation-command')
    prepare()
