"""A one-shot, installed GDM expiry fixture on the guarded automation guest.

The account hook only seeds a real one-second AccountsService grant. The stock
GDM/PAM path still decides admission and creates the desktop. This is fixture
setup, not a customer login/authentication journey. Outer VM restoration owns
all cleanup; this module never signals or terminates a session.
"""

import json
import os
from pathlib import Path
import pwd
import re
import stat
import sys
import time

import system_guest as guest
from system_assertions import accepted, account_property, account_state, call
from system_session_expiry import (
    identities, installed_manager, grant, verify_offline_recovery, verify_pam_scope,
    verify_zero_time_pam,
    verify_request_extension, verify_runtime_rollback,
)

FIXTURE = Path('/var/lib/onpc-test-graphical-expiry')
SEED = Path('/usr/libexec/onpc-test-graphical-expiry-seed')
PAM = Path('/etc/pam.d/gdm-autologin')
BOOT_UNIT = 'onpc-test-graphical-expiry-broker.service'
BOOT_SERVICE = Path('/etc/systemd/system') / BOOT_UNIT
BOOT_DROPIN = Path('/etc/systemd/system/display-manager.service.d/onpc-test-graphical-expiry.conf')


def prepare_broker_boot(*, fedora):
    """Let PID 1 establish the broker before GDM, outside its PAM domain.

    This attempt-only dependency and witness belong to the outer VM restore.
    No login hook starts services or changes Fedora's enforcing SELinux policy.
    """
    marker = guest.guard()
    for path in (BOOT_SERVICE, BOOT_DROPIN):
        guest.require(not path.exists() and not path.is_symlink(),
                      'expiry:broker-boot-fixture-collision')
    for directory in (BOOT_SERVICE.parent, BOOT_DROPIN.parent):
        guest.require(not directory.is_symlink(), 'expiry:broker-boot-directory')
        directory.mkdir(mode=0o755, exist_ok=True)
        info = directory.lstat()
        guest.require(stat.S_ISDIR(info.st_mode) and info.st_uid == info.st_gid == 0
                      and not info.st_mode & 0o022, 'expiry:broker-boot-directory')
    # Pull the broker into the boot transaction without propagating its later
    # deliberate stop (activate_broker's recovery check) through this witness
    # to GDM. broker_ready still refuses an inactive/unidentified broker, and
    # GDM still requires that successful witness before starting.
    service = (f'[Unit]\nWants={guest.BROKER}\nAfter={guest.BROKER}\n'
               '[Service]\nType=oneshot\nRemainAfterExit=yes\nUMask=0077\n'
               f'ExecStart=/usr/bin/env ONPC_EXPECTED_RUN={marker["run"]} '
               f'/usr/bin/python3 -B {guest.PAYLOAD}/system_graphical_expiry.py broker-ready\n'
               'TimeoutStartSec=120\n')
    dropin = f'[Unit]\nRequires={BOOT_UNIT}\nAfter={BOOT_UNIT}\n'
    for path, contents in ((BOOT_SERVICE, service), (BOOT_DROPIN, dropin)):
        with path.open('x') as stream:
            stream.write(contents)
        path.chmod(0o644)
    if fedora:
        guest.run(['restorecon', str(BOOT_SERVICE), str(BOOT_DROPIN.parent), str(BOOT_DROPIN)])
    guest.run(['systemctl', 'daemon-reload'])
    for unit, dependency, relationship in (
            (BOOT_UNIT, guest.BROKER, 'Wants'),
            ('display-manager.service', BOOT_UNIT, 'Requires')):
        for property in (relationship, 'After'):
            value = guest.run(['systemctl', 'show', unit, '--property=' + property, '--value'])
            guest.require(dependency in value.split(), 'expiry:broker-boot-ordering')


def broker_ready():
    """Publish the real broker invocation before the login manager can run."""
    marker = guest.guard()
    guest.enable_diagnostics()
    prepared = json.loads((FIXTURE / 'prepared.json').read_text())
    boot = Path('/proc/sys/kernel/random/boot_id').read_text()
    guest.require(prepared['run'] == marker['run'] and prepared['boot'] != boot,
                  'expiry:broker-boot-reboot-boundary')
    guest.require(guest.run(['systemctl', 'is-active', guest.BROKER]) == 'active',
                  'expiry:broker-boot-inactive')
    invocation = guest.run(['systemctl', 'show', guest.BROKER,
                            '--property=InvocationID', '--value'])
    guest.require(re.fullmatch(r'[0-9a-f]{32}', invocation) is not None
                  and invocation != '0' * 32, 'expiry:broker-boot-invocation')
    with (FIXTURE / 'broker-ready.json').open('x') as stream:
        json.dump({'run': marker['run'], 'boot': boot, 'broker_invocation': invocation}, stream)


def _seed_security_type():
    """Read only the SELinux domain, never environment or command-line input."""
    try:
        with Path('/proc/self/attr/selinux/current').open() as stream:
            context = stream.read(256).strip().split(':')
    except OSError:
        return 'unavailable'
    return (context[2] if len(context) >= 3
            and re.fullmatch(r'[a-zA-Z0-9_]+', context[2]) else 'unavailable')


def seed_account_stack(original, *, fedora):
    """Seed before the one native account include, preserving the complete stack."""
    matches = []
    for index, line in enumerate(original.splitlines(keepends=True)):
        body = line.partition('#')[0].strip()
        pattern = (r'account\s+(?:include|substack)\s+(?:system-auth|password-auth)'
                   if fedora else r'@include\s+common-account')
        if re.fullmatch(pattern, body):
            matches.append(index)
    guest.require(len(matches) == 1, 'expiry:gdm-pam-account-include')
    lines = original.splitlines(keepends=True)
    lines.insert(matches[0], f'account required pam_exec.so quiet quiet_log {SEED}\n')
    return ''.join(lines)


def prepare():
    marker = guest.guard()
    accounts = identities()
    guest.require(not FIXTURE.exists() and not FIXTURE.is_symlink()
                  and not SEED.exists() and not SEED.is_symlink(), 'expiry:graphical-fixture-collision')
    info = PAM.lstat()
    guest.require(stat.S_ISREG(info.st_mode) and info.st_uid == 0,
                  'expiry:gdm-pam-file')
    original = PAM.read_text()
    fedora = guest.package_path().suffix == '.rpm'
    seeded_stack = seed_account_stack(original, fedora=fedora)
    prerequisite_observations = []
    def record(name, value):
        prerequisite_observations.append((name, value))
    verify_offline_recovery(record)
    for service in ('gdm-password', 'gdm-autologin', 'login', 'sshd'):
        verify_pam_scope(service, record)
    accepted(call(accounts['parent'], 'SetParentControl', '(ubu)', (accounts['child'], True, 0)))
    manager = installed_manager()
    account, _ = manager._account(accounts['child'])
    guest.require(not manager._shell_is_available(account), 'expiry:graphical-fixture-already-live')
    manager._set_boolean(account, 'disable-user-extensions', True)
    FIXTURE.mkdir(mode=0o700)
    (FIXTURE / 'prerequisites.json').write_text(json.dumps(prerequisite_observations))
    (FIXTURE / 'prepared.json').write_text(json.dumps({
        'run': marker['run'], 'boot': Path('/proc/sys/kernel/random/boot_id').read_text(),
        'pam_sha256': guest.sha(PAM),
    }))
    prepare_broker_boot(fedora=fedora)
    # Fixed root-owned wrapper, installed only in this guest attempt. Its run
    # token is pinned at preparation, never inferred from a caller's PAM input.
    SEED.write_text('#!/usr/bin/python3\nimport os,sys\n'
                    f'os.environ["ONPC_EXPECTED_RUN"] = {marker["run"]!r}\n'
                    f'sys.path.insert(0, {str(guest.PAYLOAD)!r})\n'
                    'from system_graphical_expiry import seed\nseed()\n')
    SEED.chmod(0o700)
    PAM.write_text(seeded_stack)
    if fedora:
        guest.run(['restorecon', str(SEED), str(PAM)])
    guest.run(['busctl', '--system', 'call', 'org.freedesktop.Accounts',
               f'/org/freedesktop/Accounts/User{accounts["child"]}',
               'org.freedesktop.Accounts.User', 'SetAutomaticLogin', 'b', 'true'])
    guest.require(account_property(accounts['child'], 'org.freedesktop.Accounts.User',
                                   'AutomaticLogin') is True, 'expiry:autologin-readback')


def seed():
    marker = guest.guard()
    accounts = identities()
    prepared = json.loads((FIXTURE / 'prepared.json').read_text())
    boot = Path('/proc/sys/kernel/random/boot_id').read_text()
    guest.require(prepared['run'] == marker['run'] and prepared['boot'] != boot,
                  'expiry:seed-reboot-boundary')
    guest.require(os.environ.get('PAM_TYPE') == 'account'
                  and os.environ.get('PAM_SERVICE') == 'gdm-autologin'
                  and os.environ.get('PAM_USER') == pwd.getpwuid(accounts['child']).pw_name,
                  'expiry:seed-pam-identity')
    # Exclusive creation makes this a one-shot grant even if GDM retries.
    pending = FIXTURE / 'seed-attempt.json'
    guest.require(not (FIXTURE / 'seeded.json').exists(), 'expiry:seed-already-complete')
    with pending.open('x') as stream:
        attempt = {'boot': boot, 'worker': os.getppid(), 'seed_pid': os.getpid(),
                   'started_epoch': time.time(), 'uid': os.getuid(), 'euid': os.geteuid(),
                   'security_type': _seed_security_type(), 'stage': 'broker-witness'}
        def checkpoint():
            stream.seek(0)
            stream.truncate()
            json.dump(attempt, stream)
            stream.flush()
        checkpoint()
        # PID 1 established the broker before GDM. Reading its boot-bound
        # witness avoids service management from Fedora's confined PAM hook.
        try:
            witness = json.loads((FIXTURE / 'broker-ready.json').read_text())
            invocation = witness['broker_invocation']
            guest.require(witness['run'] == marker['run'] and witness['boot'] == boot
                          and re.fullmatch(r'[0-9a-f]{32}', invocation) is not None
                          and invocation != '0' * 32, 'expiry:seed-broker-witness')
        except Exception:
            attempt['failed'] = True
            checkpoint()
            raise
        attempt['stage'] = 'grant'
        checkpoint()
        time.sleep(max(0, int(time.time()) + 1.01 - time.time()))
        deadline = grant(accounts['child'], 1)
        stream.seek(0)
        stream.truncate()
        json.dump({'boot': boot, 'worker': os.getppid(), 'broker_invocation': invocation,
                   'deadline': deadline, 'remaining_seconds': round(deadline - time.time(), 3)}, stream)
    pending.rename(FIXTURE / 'seeded.json')


def child_session(uid):
    rows = guest.run(['loginctl', 'list-sessions', '--no-legend', '--no-pager']).splitlines()
    guest.require(len(rows) <= 32, 'expiry:session-inventory')
    matches = []
    for row in rows:
        session = row.split()[0]
        props = dict(line.split('=', 1) for line in guest.run([
            'loginctl', 'show-session', session, '-p', 'User', '-p', 'Class', '-p', 'Type',
            '-p', 'Service', '-p', 'Remote', '-p', 'Scope', '-p', 'LockedHint']).splitlines())
        if props.get('User') == str(uid) and props.get('Class') == 'user':
            guest.require(props.get('Type') in ('wayland', 'x11')
                          and props.get('Service') == 'gdm-autologin'
                          and props.get('Remote') == 'no', 'expiry:unexpected-child-session')
            matches.append((session, props))
    guest.require(len(matches) <= 1, 'expiry:duplicate-child-session')
    return matches[0] if matches else None


def wait_for(predicate, category, timeout=90):
    deadline = time.monotonic() + timeout
    while True:
        result = predicate()
        if result:
            return result
        guest.require(time.monotonic() < deadline, category)
        time.sleep(0.25)


def screen_lock_observation(child, session, manager, account):
    """Read native Shell activity and lock policy, retaining logind's hint.

    GNOME can lock before its asynchronous logind proxy exists, in which case
    it never sends the initial LockedHint. A stale hint must not override the
    native ScreenSaver interface, normal password mode, and enabled lock policy.
    The installed PAM authentication/account denials are checked separately.
    """
    guest.guard()
    current = child_session(child)
    guest.require(current is not None and current[0] == session, 'expiry:desktop-ended')
    state = {'logind_locked': current[1]['LockedHint'] == 'yes',
             'password_mode': account_property(child, 'org.freedesktop.Accounts.User', 'PasswordMode')}
    for key, arguments in (
        ('screensaver_active', ['gdbus', 'call', '--session', '--dest',
            'org.gnome.ScreenSaver', '--object-path', '/org/gnome/ScreenSaver',
            '--method', 'org.gnome.ScreenSaver.GetActive']),
        ('lock_enabled', ['gsettings', 'get', 'org.gnome.desktop.screensaver', 'lock-enabled']),
        ('lock_disabled', ['gsettings', 'get', 'org.gnome.desktop.lockdown', 'disable-lock-screen']),
    ):
        value = manager._run_command(account, arguments, require_live=True).stdout.strip()
        guest.require(value in ('true', 'false', '(true,)', '(false,)'),
                      'expiry:lock-observation-response')
        state[key] = value in ('true', '(true,)')
    guest.require(state['password_mode'] == 0 and state['lock_enabled']
                  and not state['lock_disabled'], 'expiry:lock-policy-not-enforcing')
    return state


def verify_other_foreground(child, session, record):
    """Expiry must preserve another account's real foreground local VT.

    A transient service opens the installed login PAM stack on an unused fixed
    VT. This is supported fixture setup, not a GDM Switch User journey. The
    service owns only its directly launched sleep; it exits naturally and the
    outer lease restores the guest. No discovered process is signalled.
    """
    marker = guest.guard()
    other = identities()['other']
    def inventory():
        rows = guest.run(['loginctl', 'list-sessions', '--no-legend', '--no-pager']).splitlines()
        guest.require(len(rows) <= 32, 'expiry:foreground-session-inventory')
        return [(row.split()[0], dict(line.split('=', 1) for line in guest.run([
            'loginctl', 'show-session', row.split()[0], '-p', 'User', '-p', 'Class',
            '-p', 'Type', '-p', 'Service', '-p', 'Seat', '-p', 'TTY', '-p', 'Scope',
            '-p', 'Active', '-p', 'LockedHint']).splitlines())) for row in rows]
    initial = inventory()
    guest.require(not any(props.get('TTY') == 'tty7' or
                          (props.get('User') == str(other) and props.get('Class') == 'user')
                          for _, props in initial), 'expiry:foreground-fixture-collision')
    other_state = account_state(other)
    guest.run(['systemd-run', '--quiet', '--collect', '--service-type=exec',
               '--unit=onpc-expiry-foreground-' + marker['run'], '--uid=' + str(other),
               '--property=PAMName=login', '--property=TTYPath=/dev/tty7',
               '--property=StandardInput=tty', '--property=StandardOutput=null',
               '--property=StandardError=null', '/usr/bin/sleep', '90'])
    def created():
        matches = [(ident, props) for ident, props in inventory()
                   if props.get('User') == str(other) and props.get('Class') == 'user']
        guest.require(len(matches) <= 1, 'expiry:foreground-duplicate-session')
        return matches[0] if matches else None
    other_session, props = wait_for(created, 'expiry:foreground-session-not-created', 15)
    record('onpc.expiry.other-foreground-created', json.dumps({
        key: props.get(key) for key in ('Type', 'Seat', 'TTY', 'Service', 'Active', 'LockedHint')
    }, sort_keys=True))
    guest.require(props.get('Type') == 'tty' and props.get('Seat') == 'seat0'
                  and props.get('TTY') == 'tty7' and props.get('Service') == 'login',
                  'expiry:foreground-session-properties')
    deadline = grant(child, 6)
    guest.run(['loginctl', 'activate', other_session])
    def foreground():
        current = dict(inventory()).get(other_session)
        guest.require(current is not None, 'expiry:other-session-ended')
        return current if current.get('Active') == 'yes' else None
    before = wait_for(foreground, 'expiry:other-session-not-foreground', 10)
    guest.require(before.get('LockedHint') == 'no' and time.time() < deadline,
                  'expiry:other-session-not-ready-before-expiry')
    observation_deadline = time.monotonic() + 10
    while time.time() <= deadline + 1:
        guest.require(time.monotonic() < observation_deadline, 'expiry:foreground-clock-discontinuity')
        guest.require(child_session(child)[0] == session, 'expiry:background-child-ended')
        time.sleep(0.25)
    after = foreground()
    guest.require(after is not None and after.get('LockedHint') == 'no'
                  and after['Scope'] == before['Scope']
                  and account_state(other) == other_state
                  and guest.run(['systemctl', 'is-active', after['Scope']]) == 'active',
                  'expiry:foreground-user-disrupted')
    record('onpc.expiry.other-foreground',
           'real-local-tty; same-session-active-and-unlocked-past-child-deadline')
    guest.run(['loginctl', 'activate', session])


def verify(record):
    guest.guard()
    # Retain completed observations even if a native dependency later stalls
    # and pytest cannot finish its JUnit document. The outer collector already
    # preserves this private results directory on both success and failure.
    publish = record
    observations = []
    output = guest.PAYLOAD / 'results'
    output.mkdir(mode=0o700, exist_ok=True)
    def record(name, value):
        observations.append((name, value))
        pending = output / 'session-observations.pending'
        pending.write_text(json.dumps(observations, sort_keys=True))
        pending.replace(output / 'session-observations.json')
        publish(name, value)
    accounts = identities()
    for name, value in json.loads((FIXTURE / 'prerequisites.json').read_text()):
        record(name, value)
    child = accounts['child']
    # SSH readiness precedes graphical boot. The seed publishes its complete
    # result atomically; neither an absent file nor a partial JSON write is a
    # completed GDM observation.
    wait_for(lambda: (FIXTURE / 'seeded.json').is_file(), 'expiry:gdm-seed-not-observed')
    seed_result = json.loads((FIXTURE / 'seeded.json').read_text())
    guest.require(seed_result['boot'] == Path('/proc/sys/kernel/random/boot_id').read_text()
                  and 0 < seed_result['remaining_seconds'] <= 1, 'expiry:one-second-seed')
    session, props = wait_for(lambda: child_session(child), 'expiry:gdm-session-missing')
    scope = props['Scope']
    runtime = guest.run(['systemctl', 'show', scope, '--property=RuntimeMaxUSec', '--value'])
    invocation = guest.run(['systemctl', 'show', guest.BROKER, '--property=InvocationID', '--value'])
    journal = guest.run(['journalctl', '--no-pager', '-b', '_PID=' + str(seed_result['worker'])])
    guest.require(runtime == 'infinity' and invocation == seed_result['broker_invocation']
                  and 'session runtime cap outcome=cleared stage=before-session status=0' in journal,
                  'expiry:gdm-cap-before-session')
    record('onpc.expiry.graphical-login', json.dumps({
        'grant_remaining_seconds': seed_result['remaining_seconds'], 'scope_runtime_max': runtime,
        'pam_before_session_witness': True, 'broker_unchanged_since_before_login': True,
        'type': props['Type'], 'service': props['Service'],
    }, sort_keys=True))
    manager = installed_manager()
    account, _ = manager._account(child)
    wait_for(lambda: manager._shell_is_available(account), 'expiry:gnome-shell-unavailable')
    guest.require(manager._runtime_state(account) == (True, True), 'expiry:extension-inactive')
    lock_state = None
    def locked():
        nonlocal lock_state
        lock_state = screen_lock_observation(child, session, manager, account)
        return lock_state['screensaver_active']
    try:
        wait_for(locked, 'expiry:gnome-screen-not-active')
    finally:
        if lock_state is not None:
            record('onpc.expiry.lock-state', json.dumps(lock_state, sort_keys=True))
    guest.require(time.time() > seed_result['deadline']
                  and guest.run(['systemctl', 'is-active', scope]) == 'active',
                  'expiry:expired-desktop-not-retained')
    record('onpc.expiry.graphical-expiry', 'same-session-active; locked-after-deadline')
    enabled = manager._list(account, 'enabled-extensions')
    disabled = manager._list(account, 'disabled-extensions')
    manager._set_boolean(account, 'disable-user-extensions', True)
    wait_for(lambda: not manager._runtime_state(account)[1], 'expiry:global-disable-not-active')
    guest.activate_broker()
    guest.require(not manager._boolean(account, 'disable-user-extensions')
                  and manager._runtime_state(account) == (True, True)
                  and manager._list(account, 'enabled-extensions') == enabled
                  and manager._list(account, 'disabled-extensions') == disabled,
                  'expiry:live-recovery-readback')
    guest.require(child_session(child)[0] == session, 'expiry:recovery-ended-session')
    record('onpc.expiry.live-recovery', 'configured-and-active; switch-and-selections-verified')
    verify_zero_time_pam(record)
    verify_runtime_rollback(record)
    old_deadline = verify_request_extension(record)
    observation_deadline = time.monotonic() + 20
    while time.time() <= old_deadline + 0.5:
        guest.require(time.monotonic() < observation_deadline, 'expiry:extension-clock-discontinuity')
        guest.require(child_session(child)[0] == session, 'expiry:extended-session-ended')
        time.sleep(0.25)
    guest.require(guest.run(['systemctl', 'is-active', scope]) == 'active'
                  and guest.run(['systemctl', 'show', scope, '--property=RuntimeMaxUSec', '--value'])
                      == 'infinity', 'expiry:extended-scope-not-retained')
    record('onpc.expiry.extended-session', 'same-session-active-past-earlier-approved-deadline')
    verify_other_foreground(child, session, record)


if __name__ == '__main__':
    guest.guard()
    guest.require(sys.argv[1:] in (['prepare'], ['broker-ready']), 'expiry:graphical-arguments')
    (prepare if sys.argv[1] == 'prepare' else broker_ready)()
