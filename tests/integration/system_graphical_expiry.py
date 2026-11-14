"""A one-shot, installed GDM expiry fixture on the guarded automation guest.

The account hook only seeds a real one-second AccountsService grant. The stock
GDM/PAM path still decides admission and creates the desktop. This is fixture
setup, not a customer login/authentication journey. Outer VM restoration owns
all cleanup. The crash history signals only its identity-recorded broker;
no session is signalled or terminated.
"""

import hashlib
import json
import os
from pathlib import Path
import pwd
import re
import signal
import stat
import sys
import time

import system_guest as guest
from system_assertions import accepted, account_property, account_state, call, validation_stage
from system_session_expiry import (
    LIMITS, REQUEST_EXTENSION_SECONDS, identities, installed_manager, grant, verify_zero_time_pam,
    verify_request_extension, verify_runtime_rollback, request_global_extension_disable,
    wait_for_extension_recovery,
)

FIXTURE = Path('/var/lib/onpc-test-graphical-expiry')
SEED = Path('/usr/libexec/onpc-test-graphical-expiry-seed')
PAM = Path('/etc/pam.d/gdm-autologin')
BOOT_UNIT = 'onpc-test-graphical-expiry-broker.service'
BOOT_SERVICE = Path('/etc/systemd/system') / BOOT_UNIT
BOOT_DROPIN = Path('/etc/systemd/system/display-manager.service.d/onpc-test-graphical-expiry.conf')


def prepare_broker_boot(*, fedora, fixture=FIXTURE, helper='system_graphical_expiry.py'):
    """Let PID 1 establish the broker before GDM, outside its PAM domain.

    This attempt-only dependency and witness belong to the outer VM restore.
    No login hook starts services or changes Fedora's enforcing SELinux policy.
    """
    marker = guest.guard()
    guest.require((fixture / 'prepared.json').is_file()
                  and helper in {'system_graphical_expiry.py', 'system_extension_startup.py'},
                  'expiry:broker-boot-input')
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
               f'/usr/bin/python3 -B {guest.PAYLOAD}/{helper} broker-ready\n'
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
    accepted(call(accounts['parent'], 'SetParentControl', '(ubu)', (accounts['child'], True, 0)))
    manager = installed_manager()
    account, _ = manager._account(accounts['child'])
    guest.require(not manager._shell_is_available(account), 'expiry:graphical-fixture-already-live')
    manager._set_boolean(account, 'disable-user-extensions', True)
    FIXTURE.mkdir(mode=0o700)
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


def child_session(uid, *, service='gdm-autologin'):
    guest.require(service in ('gdm-autologin', 'gdm-password'), 'expiry:session-service')
    rows = guest.run(['loginctl', 'list-sessions', '--no-legend', '--no-pager']).splitlines()
    guest.require(len(rows) <= 32, 'expiry:session-inventory')
    matches = []
    for row in rows:
        fields = row.split()
        guest.require(len(fields) >= 2 and fields[1].isdecimal(), 'expiry:session-row')
        # Greeter and SSH sessions can end between list and show. Their
        # properties are irrelevant here; inspect only the listed child's UID.
        # A failed read of that child's session still fails the check.
        if fields[1] != str(uid):
            continue
        session = fields[0]
        props = dict(line.split('=', 1) for line in guest.run([
            'loginctl', 'show-session', session, '-p', 'User', '-p', 'Class', '-p', 'Type',
            '-p', 'Service', '-p', 'Remote', '-p', 'Scope', '-p', 'LockedHint']).splitlines())
        if props.get('User') == str(uid) and props.get('Class') == 'user':
            guest.require(props.get('Type') in ('wayland', 'x11')
                          and props.get('Service') == service
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


def screen_lock_observation(child, session, manager, account, *, service='gdm-autologin'):
    """Supporting native state only; guarded graphical input proves protection."""
    guest.guard()
    current = child_session(child, service=service)
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


def startup_observation():
    """Read the seeded desktop and foreground without granting or entering it.

    This is bounded engineering diagnosis, not secure-lock acceptance. Native
    hints are retained alongside the independently inspected public surface.
    """
    guest.guard()
    accounts = identities()
    wait_for(lambda: (FIXTURE / 'seeded.json').is_file(), 'expiry:gdm-seed-not-observed')
    session, props = wait_for(lambda: child_session(accounts['child']),
                              'expiry:gdm-session-missing')
    manager = installed_manager()
    account, _ = manager._account(accounts['child'])
    wait_for(lambda: manager._shell_is_available(account), 'expiry:gnome-shell-unavailable')
    foreground = []
    for row in guest.run(['loginctl', 'list-sessions', '--no-legend', '--no-pager']).splitlines():
        identity = row.split()[0]
        values = dict(line.split('=', 1) for line in guest.run([
            'loginctl', 'show-session', identity, '-p', 'Active', '-p', 'Class',
            '-p', 'Type', '-p', 'Remote', '-p', 'Seat', '-p', 'User']).splitlines())
        if values.get('Active') == 'yes' and values.get('Remote') == 'no' \
                and values.get('Seat') == 'seat0' and values.get('Type') in ('wayland', 'x11'):
            foreground.append({'class': values['Class'],
                               'child': values['User'] == str(accounts['child'])})
    guest.require(len(foreground) == 1, 'expiry:startup-foreground')
    return {'session': session, 'scope': props['Scope'],
            'foreground': foreground[0],
            'extension': manager._runtime_state(account),
            'native_lock': screen_lock_observation(accounts['child'], session, manager, account)}


def graphical_history(command):
    """Finite fixture transitions for the host's guarded graphical history.

    Entitlements are changed only at declared history/recovery boundaries. The
    host owns real input, original work comparisons and lock observations; this
    leaf cannot claim those results from session hints or a grant readback.
    """
    marker = guest.guard()
    accounts = identities()
    child = accounts['child']
    path = FIXTURE / 'graphical-history.json'
    if command in ('host-ready', 'revoke-ready', 'approval-ready', 'policy-ready',
                   'replacement-ready', 'crash-ready', 'stop-ready', 'stall-ready', 'timer-ready',
                   'reply-ready', 'retry-ready', 'outage-ready'):
        guest.require(not path.exists(), 'expiry:graphical-history-replayed')
        wait_for(lambda: (FIXTURE / 'seeded.json').is_file(), 'expiry:gdm-seed-not-observed')
        seeded = json.loads((FIXTURE / 'seeded.json').read_text())
        boot = Path('/proc/sys/kernel/random/boot_id').read_text()
        guest.require(seeded['boot'] == boot and 0 < seeded['remaining_seconds'] <= 1,
                      'expiry:one-second-seed')
        session, props = wait_for(lambda: child_session(child), 'expiry:gdm-session-missing')
        manager = installed_manager()
        account, _ = manager._account(child)
        wait_for(lambda: manager._shell_is_available(account), 'expiry:gnome-shell-unavailable')
        guest.require(manager._runtime_state(account) == (True, True), 'expiry:extension-inactive')
        history = {'run': marker['run'], 'boot': boot, 'session': session,
                   'scope': props['Scope'], 'grants': 0,
                   'foreground_revoke': command == 'revoke-ready',
                   'pending_approval': command == 'approval-ready',
                   'policy_order': command == 'policy-ready', 'policy_steps': 0,
                   'session_replacement': command == 'replacement-ready',
                   'broker_crash': command == 'crash-ready',
                   'broker_stop': command == 'stop-ready',
                   'broker_stall': command == 'stall-ready',
                   'timer_replacement': command == 'timer-ready',
                   'lock_reply': command == 'reply-ready',
                   'lock_retry': command == 'retry-ready',
                   'lock_outage': command == 'outage-ready',
                   'broker_invocation': guest.run(['systemctl', 'show', guest.BROKER,
                                                  '--property=InvocationID', '--value']),
                   'account': [pwd.getpwuid(child).pw_name, child,
                               pwd.getpwuid(child).pw_gid, pwd.getpwuid(child).pw_dir],
                   'other_state': hashlib.sha256(repr(account_state(accounts['other'])).encode()).hexdigest()}
        with path.open('x') as stream:
            json.dump(history, stream)
        # Setup/recovery grants are headroom, not waits. The short measured
        # grants below are issued only after the corresponding desktop is ready.
        seconds = 1200
    else:
        history = json.loads(path.read_text())
        guest.require(history['run'] == marker['run']
                      and history['boot'] == Path('/proc/sys/kernel/random/boot_id').read_text(),
                      'expiry:graphical-history-identity')
        if command == 'stall-cleanup':
            guest.require(history.get('broker_stall') is True, 'expiry:stall-cleanup-kind')
            return stall_history(command, history, path, accounts)
        if command == 'timer-cleanup':
            guest.require(history.get('timer_replacement') is True, 'expiry:timer-cleanup-kind')
            return timer_history(command, history, path, accounts)
        if history.get('session_replacement'):
            return replacement_history(command, history, path, accounts)
        current = child_session(child)
        guest.require(current is not None and current[0] == history['session']
                      and current[1]['Scope'] == history['scope']
                      and guest.run(['systemctl', 'is-active', history['scope']]) == 'active'
                      and hashlib.sha256(repr(account_state(accounts['other'])).encode()).hexdigest()
                          == history['other_state'], 'expiry:graphical-history-continuity')
        if history.get('broker_crash'):
            return crash_history(command, history, path, accounts)
        if history.get('broker_stop'):
            return stop_history(command, history, path, accounts)
        if history.get('broker_stall'):
            return stall_history(command, history, path, accounts)
        if history.get('timer_replacement'):
            return timer_history(command, history, path, accounts)
        if history.get('lock_reply'):
            from system_lock_reply import history as reply_history
            return reply_history(command, history, path, accounts)
        if history.get('lock_retry'):
            from system_lock_reply import retry_history
            return retry_history(command, history, path, accounts)
        if history.get('lock_outage'):
            from system_lock_reply import outage_history
            return outage_history(command, history, path, accounts)
        if history.get('policy_order') and command.startswith('policy-') and command != 'policy-complete':
            sequence = ('policy-renew-seed', 'policy-renew', 'policy-allowance-seed',
                        'policy-allowance', 'policy-disable-seed', 'policy-disable',
                        'policy-restrict')
            index = history['policy_steps']
            guest.require(index < len(sequence) and command == sequence[index],
                          'expiry:policy-order')
            if command.endswith('-seed'):
                if index:
                    guest.require(time.time() >= history['policy_original_expiry'],
                                  'expiry:policy-original-deadline-not-crossed')
                history['policy_original_expiry'] = grant(child, 180)
                if command == 'policy-disable-seed':
                    # The allowance control cleared its grant. Keep that daily
                    # entitlement until the new grant exists, so setup cannot
                    # lock the desktop before the disablement being tested.
                    accepted(call(accounts['parent'], 'SetParentControl', '(ubu)', (child, True, 0)))
                result = {'remaining_seconds': history['policy_original_expiry'] - time.time()}
            elif command == 'policy-restrict':
                guest.require(time.time() >= history['policy_original_expiry'],
                              'expiry:policy-original-deadline-not-crossed')
                # First restore a positive daily balance, then install the
                # measured grant before reducing daily time. Enabling at zero
                # could lock before that grant exists and invalidate the history.
                accepted(call(accounts['parent'], 'SetParentControl', '(ubu)', (child, True, 15)))
                expiry = grant(child, 180)
                accepted(call(accounts['parent'], 'SetParentControl', '(ubu)', (child, True, 0)))
                guest.require(expiry - time.time() >= 120, 'expiry:policy-restrict-headroom')
                result = {'remaining_seconds': expiry - time.time()}
                # Continue only the existing lock/recovery/peer mechanics.
                history['grants'] = 1
            else:
                guest.require(history['policy_original_expiry'] - time.time() >= 120,
                              'expiry:policy-change-insufficient-headroom')
                if command == 'policy-renew':
                    grant(child, 1200)
                elif command == 'policy-allowance':
                    accepted(call(accounts['parent'], 'SetParentControl', '(ubu)', (child, True, 15)))
                    accepted(call(accounts['parent'], 'RevokeOneTimeGrant', '(u)', (child,)))
                    guest.require(account_property(child, LIMITS, 'DailyLimit') == 900
                                  and account_property(child, LIMITS, 'ActiveExtension')[1] == 0,
                                  'expiry:policy-allowance-authority')
                else:
                    accepted(call(accounts['parent'], 'SetParentControl', '(ubu)', (child, False, 0)))
                    guest.require(account_property(child, LIMITS, 'LimitType') == 0
                                  and account_property(child, LIMITS, 'ActiveExtension')[1] == 0,
                                  'expiry:policy-disable-authority')
                result = {'original_remaining_seconds': history['policy_original_expiry'] - time.time()}
                guest.require(result['original_remaining_seconds'] > 0,
                              'expiry:policy-change-missed-deadline')
            history['policy_steps'] += 1
            path.write_text(json.dumps(history))
            return result
        if history.get('foreground_revoke'):
            sequence = ('revoke-zero', 'revoke-positive-setup', 'revoke-positive',
                        'revoke-complete')
            index = history['grants']
            guest.require(index < len(sequence) and command == sequence[index],
                          'expiry:foreground-revoke-order')
            if command == 'revoke-positive-setup':
                accepted(call(accounts['parent'], 'SetParentControl', '(ubu)', (child, True, 15)))
                seconds = 1200
            elif command == 'revoke-complete':
                history['complete'] = True
                history['grants'] += 1
                path.write_text(json.dumps(history))
                return {'completed': True}
            else:
                before = account_property(child, LIMITS, 'ActiveExtension')
                guest.require(before[1] == 1200 and before[0] + before[1] > time.time() + 300,
                              'expiry:foreground-revoke-live-grant')
                # Anchor in the guest clock before the public management call,
                # never at reply receipt or the start of lock polling.
                triggered_ns = time.monotonic_ns()
                accepted(call(accounts['parent'], 'RevokeOneTimeGrant', '(u)', (child,)))
                guest.require(account_property(child, LIMITS, 'ActiveExtension')[1] == 0
                              and account_property(child, LIMITS, 'DailyLimit')
                                  == (0 if command == 'revoke-zero' else 900),
                              'expiry:foreground-revoke-authority')
                history['grants'] += 1
                history[command] = triggered_ns
                path.write_text(json.dumps(history))
                return {'revoked_monotonic_ns': triggered_ns}
            history['grants'] += 1
            path.write_text(json.dumps(history))
            deadline = grant(child, seconds)
            return {'remaining_seconds': deadline - time.time()}
        if command in ('host-complete', 'approval-complete', 'policy-complete'):
            guest.require(history['grants'] == 4 and not history.get('complete'),
                          'expiry:graphical-history-incomplete')
            guest.require((command == 'approval-complete') == history.get('pending_approval', False),
                          'expiry:graphical-history-kind')
            guest.require((command == 'policy-complete') == history.get('policy_order', False),
                          'expiry:graphical-history-kind')
            if history.get('policy_order'):
                guest.require(history['policy_steps'] == 7, 'expiry:policy-history-incomplete')
            if history.get('pending_approval'):
                guest.require(history.get('approvals') == ['approval-natural', 'approval-peer'],
                              'expiry:approval-history-incomplete')
            history['complete'] = True
            path.write_text(json.dumps(history))
            return {'completed': True}
        sequence = (('approval-natural', 'natural-recovery', 'approval-peer', 'peer-recovery')
                    if history.get('pending_approval') else
                    ('natural-grant', 'natural-recovery', 'peer-grant', 'peer-recovery'))
        index = history['grants']
        guest.require(index < len(sequence) and command == sequence[index],
                      'expiry:graphical-history-order')
        seconds = ((300, 1200, 300, 1200) if history.get('pending_approval') else
                   (45, 1200, 15, 1200))[index]
        history['grants'] += 1
        path.write_text(json.dumps(history))
    deadline = grant(child, seconds)
    remaining = deadline - time.time()
    guest.require(0 < remaining <= seconds, 'expiry:graphical-history-grant')
    return {'remaining_seconds': remaining}


def fault_recorded_broker(invocation, record, *, stop=False,
                         process_signal=signal.SIGKILL, expected=None):
    """Signal only the pinned broker; resume requires its original receipt."""
    from system_kiosk_confinement import process_identity, exited
    guest.guard()
    guest.require(process_signal in (signal.SIGKILL, signal.SIGSTOP, signal.SIGCONT)
                  and (not stop or process_signal == signal.SIGKILL)
                  and (process_signal != signal.SIGCONT or expected is not None),
                  'expiry:broker-fault-kind')
    def properties():
        return dict(line.split('=', 1) for line in guest.run([
            'systemctl', 'show', guest.BROKER, '-p', 'MainPID', '-p', 'InvocationID',
            '-p', 'ActiveState']).splitlines())
    before = properties()
    guest.require(re.fullmatch(r'[0-9a-f]{32}', invocation) is not None
                  and invocation != '0' * 32 and before['InvocationID'] == invocation
                  and before['ActiveState'] == 'active' and int(before['MainPID']) > 1,
                  'expiry:crash-broker-identity')
    pid = int(before['MainPID'])
    descriptor = os.pidfd_open(pid)
    try:
        process = Path('/proc') / str(pid)
        identity = process_identity(process)
        guest.require(identity[1] == 1 and identity[2] == ('0',) * 4
                      and any(line.endswith('/' + guest.BROKER)
                              for line in (process / 'cgroup').read_text().splitlines()),
                      'expiry:crash-broker-owner')
        recorded = {'invocation': invocation, 'pid': pid, 'start': identity[0]}
        guest.require(expected is None or recorded == expected, 'expiry:broker-fault-identity-changed')
        record(recorded)
        guest.guard()
        guest.require(properties() == before and not exited(descriptor)
                      and process_identity(process) == identity,
                      'expiry:crash-broker-replaced')
        if stop:
            guest.run(['systemctl', 'stop', guest.BROKER])
        else:
            signal.pidfd_send_signal(descriptor, process_signal)
        if process_signal in (signal.SIGSTOP, signal.SIGCONT):
            def observed():
                guest.require(properties() == before and not exited(descriptor)
                              and process_identity(process) == identity,
                              'expiry:crash-broker-replaced')
                state = (process / 'stat').read_text().rsplit(')', 1)[1].split()[0]
                return (state == 'T' if process_signal == signal.SIGSTOP else state != 'T')
            wait_for(observed, 'expiry:broker-signal-not-observed', timeout=10)
            return
        wait_for(lambda: exited(descriptor), 'expiry:crash-not-observed', timeout=10)
        wait_for(lambda: (guest.run(['systemctl', 'show', guest.BROKER,
                                    '--property=ActiveState', '--value']) == 'inactive'
                          and guest.run(['systemctl', 'show', guest.BROKER,
                                         '--property=Result', '--value']) == 'success' if stop else
                          guest.run(['systemctl', 'show', guest.BROKER,
                                     '--property=ExecMainStatus', '--value']) == str(signal.SIGKILL))
                 and guest.run(['systemctl', 'show', guest.BROKER,
                                '--property=MainPID', '--value']) == '0',
                 'expiry:crash-service-exit-not-observed', timeout=10)
    finally:
        os.close(descriptor)


def crash_history(command, history, path, accounts):
    """Two finite outages, each retaining its original grant and deadline."""
    child = accounts['child']
    sequence = ('crash-natural-arm', 'crash-inject', 'crash-natural-recovery',
                'crash-peer-arm', 'crash-inject', 'crash-peer-recovery', 'crash-complete')
    index = history['grants']
    guest.require(index < len(sequence) and command == sequence[index], 'expiry:crash-order')
    if command.endswith('-arm'):
        history['original_expiry'] = grant(child, 180)
        history['original_grant'] = account_property(child, LIMITS, 'ActiveExtension')
        history['child_state'] = hashlib.sha256(repr(account_state(child)).encode()).hexdigest()
        result = {'remaining_seconds': history['original_expiry'] - time.time()}
    elif command == 'crash-inject':
        guest.require(history['original_expiry'] - time.time() >= 120,
                      'expiry:crash-insufficient-headroom')
        # Prevent live clients from ending the declared outage through ordinary
        # D-Bus activation. This is an owned fault, never a supervision change.
        history['mask'] = guest.runtime_service_mask(guest.BROKER, category='expiry:crash')
        path.write_text(json.dumps(history))
        def record(identity):
            history['crash_identity'] = identity
            path.write_text(json.dumps(history))
        fault_recorded_broker(history['broker_invocation'], record)
        guest.require(time.time() < history['original_expiry'], 'expiry:crash-after-expiry')
        history.setdefault('crashes', []).append(history['crash_identity'])
        result = {'remaining_seconds': history['original_expiry'] - time.time()}
    elif command.endswith('-recovery'):
        mask_identity = tuple(history['mask'])
        guest.runtime_service_mask(guest.BROKER, category='expiry:crash', identity=mask_identity)
        guest.require(time.time() >= history['original_expiry']
                      and guest.run(['systemctl', 'show', guest.BROKER,
                                     '--property=MainPID', '--value']) == '0'
                      and hashlib.sha256(repr(account_state(child)).encode()).hexdigest()
                          == history['child_state'], 'expiry:crash-outage-not-retained')
        recovered_by = time.monotonic() + 300
        guest.remove_runtime_service_mask(guest.BROKER, mask_identity, category='expiry:crash')
        guest.activate_broker(restart=False)
        invocation = guest.run(['systemctl', 'show', guest.BROKER,
                                '--property=InvocationID', '--value'])
        status = accepted(call(accounts['parent'], 'GetTimeStatus', '(uu)', (child, 0)))
        guest.require(re.fullmatch(r'[0-9a-f]{32}', invocation) is not None
                      and invocation != '0' * 32 and invocation != history['broker_invocation']
                      and status == [0, 0, 0, 0]
                      and account_property(child, LIMITS, 'ActiveExtension') == history['original_grant']
                      and hashlib.sha256(repr(account_state(child)).encode()).hexdigest()
                          == history['child_state']
                      and time.monotonic() < recovered_by,
                      'expiry:crash-recovery-time-or-state')
        history['broker_invocation'] = invocation
        history.setdefault('recoveries', []).append({'zero_balance': True, 'grant_unchanged': True})
        # Only after proving recovery did not restore expired time, declare the
        # normal recovery grant needed for authenticated original-work readback.
        deadline = grant(child, 1200)
        result = {'remaining_seconds': deadline - time.time()}
    else:
        guest.require(len(history.get('crashes', [])) == 2
                      and len(history.get('recoveries', [])) == 2,
                      'expiry:crash-history-incomplete')
        history['complete'] = True
        result = {'completed': True}
    history['grants'] += 1
    path.write_text(json.dumps(history))
    return result


def stop_history(command, history, path, accounts):
    """One grant-only outage with a fixed, outage-inclusive recovery deadline."""
    child = accounts['child']
    sequence = ('stop-arm', 'stop-inject', 'stop-recovery', 'stop-complete')
    index = history['grants']
    guest.require(index < len(sequence) and command == sequence[index], 'expiry:stop-order')
    if command == 'stop-arm':
        history['original_expiry'] = grant(child, 180)
        history['recover_by'] = time.monotonic() + history['original_expiry'] - time.time() + 300
        history['original_grant'] = account_property(child, LIMITS, 'ActiveExtension')
        history['child_state'] = hashlib.sha256(repr(account_state(child)).encode()).hexdigest()
        guest.require(account_property(child, LIMITS, 'DailyLimit') == 0, 'expiry:stop-not-grant-only')
        result = {'remaining_seconds': history['original_expiry'] - time.time()}
    elif command == 'stop-inject':
        guest.require(history['original_expiry'] - time.time() >= 120,
                      'expiry:stop-insufficient-headroom')
        history['mask'] = guest.runtime_service_mask(guest.BROKER, category='expiry:stop')
        path.write_text(json.dumps(history))
        def record(identity):
            history['stop_identity'] = identity
            path.write_text(json.dumps(history))
        fault_recorded_broker(history['broker_invocation'], record, stop=True)
        history['service_start'] = guest.run(['systemctl', 'show', guest.BROKER,
                                              '--property=ExecMainStartTimestampMonotonic', '--value'])
        guest.require(time.time() < history['original_expiry'], 'expiry:stop-after-expiry')
        result = {'remaining_seconds': history['original_expiry'] - time.time()}
    elif command == 'stop-recovery':
        mask_identity = tuple(history['mask'])
        guest.runtime_service_mask(guest.BROKER, category='expiry:stop', identity=mask_identity)
        guest.require(time.time() >= history['original_expiry']
                      and guest.run(['systemctl', 'show', guest.BROKER,
                                     '--property=MainPID', '--value']) == '0'
                      and guest.run(['systemctl', 'show', guest.BROKER,
                                     '--property=ActiveState', '--value']) == 'inactive'
                      and guest.run(['systemctl', 'show', guest.BROKER,
                                     '--property=ExecMainStartTimestampMonotonic', '--value'])
                          == history['service_start']
                      and hashlib.sha256(repr(account_state(child)).encode()).hexdigest()
                          == history['child_state'], 'expiry:stop-outage-not-retained')
        guest.remove_runtime_service_mask(guest.BROKER, mask_identity, category='expiry:stop')
        guest.activate_broker(restart=False)
        invocation = guest.run(['systemctl', 'show', guest.BROKER,
                                '--property=InvocationID', '--value'])
        guest.require(re.fullmatch(r'[0-9a-f]{32}', invocation) is not None
                      and invocation != '0' * 32 and invocation != history['broker_invocation']
                      and accepted(call(accounts['parent'], 'GetTimeStatus', '(uu)', (child, 0))) == [0, 0, 0, 0]
                      and account_property(child, LIMITS, 'ActiveExtension') == history['original_grant']
                      and hashlib.sha256(repr(account_state(child)).encode()).hexdigest()
                          == history['child_state']
                      and time.monotonic() < history['recover_by'], 'expiry:stop-recovery-time-or-state')
        history['recovered'] = True
        deadline = grant(child, 1200)
        result = {'remaining_seconds': deadline - time.time()}
    else:
        guest.require(history.get('recovered') is True and 'stop_identity' in history,
                      'expiry:stop-history-incomplete')
        history['complete'] = True
        result = {'completed': True}
    history['grants'] += 1
    path.write_text(json.dumps(history))
    return result


def stall_history(command, history, path, accounts):
    """Pause and resume only the same broker across each original expiry."""
    from system_kiosk_confinement import process_identity
    child = accounts['child']
    if command == 'stall-cleanup':
        if history.get('stalled'):
            fault_recorded_broker(history['broker_invocation'], lambda identity: None,
                process_signal=signal.SIGCONT, expected=history['stall_identity'])
            history['stalled'] = False
            path.write_text(json.dumps(history))
        return {'completed': True}
    sequence = ('stall-natural-arm', 'stall-inject', 'stall-natural-recovery',
                'stall-peer-arm', 'stall-inject', 'stall-peer-recovery', 'stall-complete')
    index = history['grants']
    guest.require(index < len(sequence) and command == sequence[index], 'expiry:stall-order')
    if command.endswith('-arm'):
        history['original_expiry'] = grant(child, 180)
        history['recover_by'] = time.monotonic() + history['original_expiry'] - time.time() + 300
        history['original_grant'] = account_property(child, LIMITS, 'ActiveExtension')
        history['child_state'] = hashlib.sha256(repr(account_state(child)).encode()).hexdigest()
        result = {'remaining_seconds': history['original_expiry'] - time.time()}
    elif command == 'stall-inject':
        guest.require(history['original_expiry'] - time.time() >= 120,
                      'expiry:stall-insufficient-headroom')
        def record(identity):
            # Record restoration ownership before delivering any signal.
            history['stall_identity'] = identity
            history['stalled'] = True
            path.write_text(json.dumps(history))
        fault_recorded_broker(history['broker_invocation'], record, process_signal=signal.SIGSTOP)
        guest.require(time.time() < history['original_expiry'], 'expiry:stall-after-expiry')
        history.setdefault('stalls', []).append(history['stall_identity'])
        result = {'remaining_seconds': history['original_expiry'] - time.time()}
    elif command.endswith('-recovery'):
        identity = history['stall_identity']
        process = Path('/proc') / str(identity['pid'])
        guest.require(history.get('stalled') is True and time.time() >= history['original_expiry']
                      and process_identity(process) == (identity['start'], 1, ('0',) * 4)
                      and (process / 'stat').read_text().rsplit(')', 1)[1].split()[0] == 'T'
                      and hashlib.sha256(repr(account_state(child)).encode()).hexdigest()
                          == history['child_state'], 'expiry:stall-outage-not-retained')
        fault_recorded_broker(history['broker_invocation'], lambda identity: None,
            process_signal=signal.SIGCONT, expected=identity)
        history['stalled'] = False
        path.write_text(json.dumps(history))
        guest.require(accepted(call(accounts['parent'], 'GetTimeStatus', '(uu)', (child, 0))) == [0, 0, 0, 0]
                      and guest.run(['systemctl', 'show', guest.BROKER,
                                     '--property=InvocationID', '--value']) == history['broker_invocation']
                      and account_property(child, LIMITS, 'ActiveExtension') == history['original_grant']
                      and hashlib.sha256(repr(account_state(child)).encode()).hexdigest()
                          == history['child_state']
                      and time.monotonic() < history['recover_by'], 'expiry:stall-recovery-time-or-state')
        history.setdefault('recoveries', []).append({'zero_balance': True, 'grant_unchanged': True})
        deadline = grant(child, 1200)
        result = {'remaining_seconds': deadline - time.time()}
    else:
        guest.require(len(history.get('stalls', [])) == 2 and len(history.get('recoveries', [])) == 2
                      and history.get('stalled') is False, 'expiry:stall-history-incomplete')
        history['complete'] = True
        result = {'completed': True}
    history['grants'] += 1
    path.write_text(json.dumps(history))
    return result


TIMER = 'org.freedesktop.MalcontentTimer1'
TIMER_UNIT = 'malcontent-timerd.service'


def timer_identity():
    """Pin the native bus owner to its actual systemd process, not restart speed."""
    from system_kiosk_confinement import process_identity
    def bus(method, value):
        return json.loads(guest.run(['busctl', '--system', '--json=short', 'call',
            'org.freedesktop.DBus', '/org/freedesktop/DBus', 'org.freedesktop.DBus',
            method, 's', value]))['data'][0]
    owner = bus('GetNameOwner', TIMER)
    pid = bus('GetConnectionUnixProcessID', owner)
    properties = dict(line.split('=', 1) for line in guest.run([
        'systemctl', 'show', TIMER_UNIT, '-p', 'MainPID', '-p', 'InvocationID',
        '-p', 'ActiveState']).splitlines())
    guest.require(re.fullmatch(r':[0-9]+\.[0-9]+', owner) is not None
                  and type(pid) is int and pid > 1 and properties['MainPID'] == str(pid)
                  and properties['ActiveState'] == 'active'
                  and re.fullmatch(r'[0-9a-f]{32}', properties['InvocationID']) is not None
                  and properties['InvocationID'] != '0' * 32, 'expiry:timer-owner-identity')
    process = Path('/proc') / str(pid)
    identity = process_identity(process)
    guest.require(any(line.endswith('/' + TIMER_UNIT)
                      for line in (process / 'cgroup').read_text().splitlines())
                  and bus('GetNameOwner', TIMER) == owner, 'expiry:timer-process-owner')
    return {'owner': owner, 'pid': pid, 'start': identity[0],
            'invocation': properties['InvocationID']}


def timer_history(command, history, path, accounts):
    """Replace one real timer owner across expiry; never replay expired time."""
    from system_kiosk_confinement import exited, user_command
    child = accounts['child']
    if command == 'timer-cleanup':
        if history.get('timer_mask') is not None:
            guest.remove_runtime_service_mask(TIMER_UNIT, tuple(history['timer_mask']),
                                               category='expiry:timer')
            history['timer_mask'] = None
            path.write_text(json.dumps(history))
            guest.run(['systemctl', 'start', TIMER_UNIT], timeout=30)
        return {'completed': True}
    sequence = ('timer-arm', 'timer-inject', 'timer-recovery', 'timer-complete')
    index = history['grants']
    guest.require(index < len(sequence) and command == sequence[index], 'expiry:timer-order')
    if command == 'timer-arm':
        history['original_expiry'] = grant(child, 180)
        history['recover_by'] = time.monotonic() + history['original_expiry'] - time.time() + 300
        history['original_grant'] = account_property(child, LIMITS, 'ActiveExtension')
        history['child_state'] = hashlib.sha256(repr(account_state(child)).encode()).hexdigest()
        accepted(call(accounts['parent'], 'GetTimeStatus', '(uu)', (child, 0)))
        history['old_timer'] = timer_identity()
        result = {'remaining_seconds': history['original_expiry'] - time.time()}
    elif command == 'timer-inject':
        guest.require(history['original_expiry'] - time.time() >= 120,
                      'expiry:timer-insufficient-headroom')
        old = history['old_timer']
        descriptor = os.pidfd_open(old['pid'])
        try:
            guest.require(timer_identity() == old and not exited(descriptor),
                          'expiry:timer-replaced-before-fault')
            history['timer_mask'] = guest.runtime_service_mask(TIMER_UNIT, category='expiry:timer')
            path.write_text(json.dumps(history))
            guest.require(timer_identity() == old and not exited(descriptor),
                          'expiry:timer-replaced-before-fault')
            guest.run(['systemctl', 'stop', TIMER_UNIT])
            wait_for(lambda: exited(descriptor), 'expiry:timer-old-process-not-exited', timeout=10)
        finally:
            os.close(descriptor)
        guest.require(time.time() < history['original_expiry'], 'expiry:timer-fault-after-expiry')
        result = {'remaining_seconds': history['original_expiry'] - time.time()}
    elif command == 'timer-recovery':
        mask = tuple(history['timer_mask'])
        guest.runtime_service_mask(TIMER_UNIT, category='expiry:timer', identity=mask)
        guest.require(time.time() >= history['original_expiry']
                      and guest.run(['systemctl', 'show', TIMER_UNIT,
                                     '--property=MainPID', '--value']) == '0'
                      and guest.run(['busctl', '--system', 'call', 'org.freedesktop.DBus',
                                     '/org/freedesktop/DBus', 'org.freedesktop.DBus',
                                     'NameHasOwner', 's', TIMER]) == 'b false'
                      and hashlib.sha256(repr(account_state(child)).encode()).hexdigest()
                          == history['child_state'], 'expiry:timer-outage-not-retained')
        guest.remove_runtime_service_mask(TIMER_UNIT, mask, category='expiry:timer')
        history['timer_mask'] = None
        path.write_text(json.dumps(history))
        guest.run(['systemctl', 'start', TIMER_UNIT], timeout=30)
        new = timer_identity()
        old = history['old_timer']
        guest.require(new['owner'] != old['owner'] and new['invocation'] != old['invocation']
                      and (new['pid'], new['start']) != (old['pid'], old['start']),
                      'expiry:timer-owner-not-replaced')
        # Query as the real child, retaining the native API's authorization and
        # reconstruction. Root cannot stand in for this client.
        native = json.loads(user_command(pwd.getpwuid(child), [
            '/usr/bin/busctl', '--system', '--json=short', 'call', TIMER,
            '/org/freedesktop/MalcontentTimer1', TIMER + '.Child',
            'GetEstimatedTimes', 's', 'login-session']).decode())
        observed, estimates = native['data']
        guest.require(set(estimates) == {''} and estimates[''][0] is True
                      and estimates[''][2] <= observed
                      and accepted(call(accounts['parent'], 'GetTimeStatus', '(uu)', (child, 0))) == [0, 0, 0, 0]
                      and account_property(child, LIMITS, 'ActiveExtension') == history['original_grant']
                      and hashlib.sha256(repr(account_state(child)).encode()).hexdigest()
                          == history['child_state'] and timer_identity() == new
                      and time.monotonic() < history['recover_by'], 'expiry:timer-reconstruction')
        history['new_timer'] = new
        history['recovered'] = True
        deadline = grant(child, 1200)
        result = {'remaining_seconds': deadline - time.time()}
    else:
        guest.require(history.get('recovered') is True and history.get('timer_mask') is None,
                      'expiry:timer-history-incomplete')
        history['complete'] = True
        result = {'completed': True}
    history['grants'] += 1
    path.write_text(json.dumps(history))
    return result


def replacement_history(command, history, path, accounts):
    """Keep the original deadline while replacing only its owned desktop."""
    child = accounts['child']
    account = pwd.getpwuid(child)
    guest.require(history['account'] == [account.pw_name, child, account.pw_gid, account.pw_dir]
                  and hashlib.sha256(repr(account_state(accounts['other'])).encode()).hexdigest()
                      == history['other_state'], 'expiry:replacement-account-changed')
    sequence = ('replacement-arm', 'replacement-entitlement', 'replacement-bind',
                'replacement-complete')
    index = history['grants']
    guest.require(index < len(sequence) and command == sequence[index],
                  'expiry:replacement-order')
    if command == 'replacement-arm':
        current = child_session(child)
        guest.require(current is not None and current[0] == history['session']
                      and current[1]['Scope'] == history['scope'],
                      'expiry:original-session-changed')
        history['original_expiry'] = grant(child, 600)
        result = {'remaining_seconds': history['original_expiry'] - time.time()}
    elif command == 'replacement-entitlement':
        wait_for(lambda: child_session(child) is None, 'expiry:original-session-not-ended')
        guest.require(history['original_expiry'] - time.time() >= 300,
                      'expiry:replacement-setup-headroom')
        deadline = grant(child, 1200)
        history['replacement_grant'] = account_property(child, LIMITS, 'ActiveExtension')
        result = {'remaining_seconds': deadline - time.time()}
    else:
        current = child_session(child, service='gdm-password')
        guest.require(current is not None and current[0] != history['session']
                      and current[1]['Scope'] != history['scope'],
                      'expiry:replacement-session-not-new')
        live_grant = account_property(child, LIMITS, 'ActiveExtension')
        guest.require(live_grant == history['replacement_grant']
                      and live_grant[0] + live_grant[1] - time.time() >= 300
                      # Malcontent's daily-limit flag is bit 1; bit 0 is a schedule.
                      and account_property(child, LIMITS, 'LimitType') == 2
                      and account_property(child, LIMITS, 'DailyLimit') == 0,
                      'expiry:replacement-entitlement-changed')
        if command == 'replacement-bind':
            guest.require(history['original_expiry'] - time.time() >= 180,
                          'expiry:replacement-entry-headroom')
            history['replacement_session'] = current[0]
            history['replacement_scope'] = current[1]['Scope']
            result = {'remaining_seconds': live_grant[0] + live_grant[1] - time.time()}
        else:
            guest.require(current[0] == history['replacement_session']
                          and current[1]['Scope'] == history['replacement_scope']
                          and time.time() >= history['original_expiry'],
                          'expiry:replacement-history-incomplete')
            history['complete'] = True
            result = {'completed': True}
    history['grants'] += 1
    path.write_text(json.dumps(history))
    return result


def pending_approval(command):
    """Hold one real challenge until the host finishes its expiry observation.

    The owning SSH command retains both pidfds and cancels the challenge in its
    context cleanup. A fixed attempt-local finish file coordinates the existing
    streaming transport; no detached process or inherited VM owner is created.
    """
    import select
    from system_caller import PersistentCaller, TextAgent

    guest.guard()
    guest.require(command in ('approval-natural', 'approval-peer'), 'expiry:approval-command')
    began = time.monotonic()
    accounts = identities()
    child = accounts['child']
    finish = FIXTURE / (command + '.finish')
    guest.require(not finish.exists() and not finish.is_symlink(), 'expiry:approval-replayed')
    with PersistentCaller(child) as caller, TextAgent(caller) as agent:
        graphical_history(command)
        extension = account_property(child, LIMITS, 'ActiveExtension')
        expiry = sum(extension)
        caller.send({'kind': 'call', 'method': 'RequestOwnAccess', 'signature': '(uub)',
                     'args': (accounts['parent'], 300, False), 'timeout_ms': 900000})
        agent.prompt(accounts['parent'], pwd.getpwnam('onpc-parent-casey').pw_uid)
        busy = call(accounts['parent'], 'SetParentControl', '(ubu)', (child, True, 1440))
        guest.require(busy.get('error') == guest.BUS + '.Error.Busy',
                      'expiry:approval-transaction-not-held')
        remaining = expiry - time.time()
        guest.require(remaining >= 180, 'expiry:approval-insufficient-headroom')
        print('onpc-approval-ready:' + json.dumps({
            'remaining_seconds': remaining, 'elapsed_seconds': time.monotonic() - began}), flush=True)
        deadline = time.monotonic() + remaining + 180
        while not finish.exists():
            guest.guard()
            guest.require(time.monotonic() < deadline, 'expiry:approval-observation-deadline')
            guest.require(caller.child.poll() is None and agent.child.poll() is None
                          and not select.select([caller.child.stdout], [], [], 0)[0],
                          'expiry:approval-ended-before-observation')
            time.sleep(0.25)
        # Still the same live challenge after the independently observed result.
        guest.require(not select.select([caller.child.stdout], [], [], 0)[0]
                      and agent.child.poll() is None and time.time() >= expiry,
                      'expiry:approval-not-pending-across-expiry')
        agent.close()
        result = accepted(caller.receive())
        guest.require(result[1] in ('denied', 'cancelled') and result[2] == 0,
                      'expiry:approval-not-cancelled')
    guest.require(account_property(child, LIMITS, 'ActiveExtension') == extension,
                  'expiry:pending-approval-changed-grant')
    path = FIXTURE / 'graphical-history.json'
    history = json.loads(path.read_text())
    history.setdefault('approvals', []).append(command)
    path.write_text(json.dumps(history))
    print('onpc-approval-complete', flush=True)


def finish_pending_approval():
    guest.guard()
    history = json.loads((FIXTURE / 'graphical-history.json').read_text())
    guest.require(history['run'] == guest.guard()['run'] and history.get('pending_approval')
                  and history['boot'] == Path('/proc/sys/kernel/random/boot_id').read_text()
                  and history['grants'] in (1, 3), 'expiry:approval-finish-order')
    command = 'approval-natural' if history['grants'] == 1 else 'approval-peer'
    with (FIXTURE / (command + '.finish')).open('x') as stream:
        stream.write('finish\n')


def verify_pending_approval(record):
    guest.guard()
    history = json.loads((FIXTURE / 'graphical-history.json').read_text())
    guest.require(history.get('pending_approval') is True and history.get('complete') is True
                  and history.get('approvals') == ['approval-natural', 'approval-peer']
                  and history['grants'] == 4, 'expiry:approval-history-incomplete')
    record('onpc.expiry.pending-approval',
           'challenge-ready-180s-before-expiry; pending-through-original-deadline; '
           'timed-protection; cancellation-without-grant; original-work-recovered; peer-input-preserved')


def verify_foreground_revoke(record):
    """The host owns protection, retained work and positive-input observations."""
    guest.guard()
    history = json.loads((FIXTURE / 'graphical-history.json').read_text())
    guest.require(history.get('foreground_revoke') is True
                  and history.get('complete') is True and history['grants'] == 4,
                  'expiry:foreground-revoke-incomplete')
    record('onpc.expiry.foreground-revoke',
           'zero-daily-bounded-protected-lock; original-work-recovered; positive-daily-usable')


def verify_policy_order(record):
    guest.guard()
    history = json.loads((FIXTURE / 'graphical-history.json').read_text())
    guest.require(history.get('policy_order') is True and history.get('complete') is True
                  and history['policy_steps'] == 7 and history['grants'] == 4,
                  'expiry:policy-history-incomplete')
    record('onpc.expiry.policy-order',
           'renewal-allowance-disable-before-original-expiry; entitled-input-preserved; '
           'restricted-natural-lock; protected-input; original-work-recovered; peer-input-preserved')


def verify_session_replacement(record):
    guest.guard()
    history = json.loads((FIXTURE / 'graphical-history.json').read_text())
    guest.require(history.get('session_replacement') is True and history.get('complete') is True
                  and history['grants'] == 4
                  and history['replacement_session'] != history['session'],
                  'expiry:replacement-history-incomplete')
    record('onpc.expiry.session-replacement',
           'pending-displayed-tick; original-session-ended; same-account-new-session; '
           'positive-replacement-input-and-work-past-original-deadline; peer-input-and-work')


def verify_broker_crash(record):
    guest.guard()
    history = json.loads((FIXTURE / 'graphical-history.json').read_text())
    guest.require(history.get('broker_crash') is True and history.get('complete') is True
                  and history['grants'] == 7 and len(history['crashes']) == 2
                  and len(history['recoveries']) == 2, 'expiry:crash-history-incomplete')
    record('onpc.expiry.broker-crash',
           'identity-recorded-SIGKILL-before-expiry; outage-through-protected-input; '
           'original-deadline; activated-new-owner-zero-balance-unchanged-grant; '
           'original-session-and-work; peer-input-and-work')


def verify_broker_stop(record):
    guest.guard()
    history = json.loads((FIXTURE / 'graphical-history.json').read_text())
    guest.require(history.get('broker_stop') is True and history.get('complete') is True
                  and history['grants'] == 4 and history.get('recovered') is True,
                  'expiry:stop-history-incomplete')
    record('onpc.expiry.broker-stop',
           'identity-recorded-service-stop-before-expiry; inactive-through-protected-input; '
           'original-deadline; new-owner-zero-balance-unchanged-grant; '
           'outage-inclusive-recovery; original-session-and-work; peer-input-and-work')


def verify_broker_stall(record):
    guest.guard()
    history = json.loads((FIXTURE / 'graphical-history.json').read_text())
    guest.require(history.get('broker_stall') is True and history.get('complete') is True
                  and history['grants'] == 7 and len(history['stalls']) == 2
                  and len(history['recoveries']) == 2 and history.get('stalled') is False,
                  'expiry:stall-history-incomplete')
    record('onpc.expiry.broker-stall',
           'identity-recorded-SIGSTOP-before-expiry; stopped-through-protected-input; '
           'same-process-SIGCONT; original-deadline; zero-balance-unchanged-grant; '
           'outage-inclusive-work-recovery; original-session; foreground-peer-input-and-work')


def verify_timer_replacement(record):
    guest.guard()
    history = json.loads((FIXTURE / 'graphical-history.json').read_text())
    guest.require(history.get('timer_replacement') is True and history.get('complete') is True
                  and history['grants'] == 4 and history.get('recovered') is True
                  and history.get('timer_mask') is None, 'expiry:timer-history-incomplete')
    record('onpc.expiry.timer-replacement',
           'old-owner-process-exited; absent-through-original-expiry-and-protected-input; '
           'distinct-new-bus-process-and-service-owner; native-child-exhausted-state; '
           'zero-balance-unchanged-grant; outage-inclusive-work-recovery; '
           'original-child-session-and-work; same-peer-input-and-work')


def verify_lock_completion(record):
    guest.guard()
    history = json.loads((FIXTURE / 'graphical-history.json').read_text())
    guest.require(history.get('lock_reply') is True and history.get('complete') is True
                  and history.get('reply_histories') == ['delayed', 'missing']
                  and (FIXTURE / 'lock-reply' / 'restored').is_file(),
                  'expiry:lock-reply-history-incomplete')
    record('onpc.expiry.lock-replies',
           'real-shell-requests; native-completion-before-held-reply; '
           'public-native-action-gate-restored-before-forwarding; '
           'independent-timely-lock-and-protected-input; delayed-ack-after-input; '
           'missing-reply-client-failure; original-child-work; same-peer-input-and-work; '
           'normal-facade-restored-with-same-native-owner; no-lock-retry-owner')


def verify_lock_retry(record):
    guest.guard()
    history = json.loads((FIXTURE / 'graphical-history.json').read_text())
    guest.require(history.get('lock_retry') is True and history.get('complete') is True
                  and history.get('renewal_cancelled_retry') is True
                  and history.get('transient_recovered') is True
                  and (FIXTURE / 'lock-reply' / 'restored').is_file(),
                  'expiry:lock-retry-history-incomplete')
    record('onpc.expiry.lock-retry',
           'real-transient-failure-and-retry; original-deadline-timely-protection; '
           'confirmed-renewal-cancels-stale-retry; original-child-work; same-peer-input-and-work; '
           'normal-lock-service-restored')


def verify_lock_outage(record):
    guest.guard()
    history = json.loads((FIXTURE / 'graphical-history.json').read_text())
    guest.require(history.get('lock_outage') is True and history.get('complete') is True
                  and history.get('outage_protection') == 'unsupported-input-remained-usable'
                  and (FIXTURE / 'lock-reply' / 'restored').is_file(),
                  'expiry:lock-outage-history-incomplete')
    record('onpc.expiry.lock-outage',
           'characterization-only; protection-unsupported; real-lock-refusals; '
           'original-expiry-and-revocation-crossed-with-usable-original-child-work; '
           'same-shell-session-bus-and-child-session; same-parent-input-and-work; '
           'normal-lock-availability-and-protected-input-restored; no-protection-or-customer-credit')


def verify(record):
    guest.guard()
    history = json.loads((FIXTURE / 'graphical-history.json').read_text())
    guest.require(history.get('complete') is True and not history.get('foreground_revoke')
                  and not history.get('pending_approval') and not history.get('policy_order')
                  and not history.get('session_replacement') and not history.get('broker_crash')
                  and not history.get('broker_stop') and not history.get('broker_stall')
                  and not history.get('timer_replacement') and not history.get('lock_reply'),
                  'expiry:graphical-history-incomplete')
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
    record('onpc.expiry.lock-state', json.dumps(
        screen_lock_observation(child, session, manager, account), sort_keys=True))
    guest.require(time.time() > seed_result['deadline']
                  and guest.run(['systemctl', 'is-active', scope]) == 'active',
                  'expiry:expired-desktop-not-retained')
    record('onpc.expiry.graphical-expiry',
           'same-session-active; guarded-lock-input-and-original-work-verified-by-host')
    record('onpc.expiry.other-foreground',
           'graphical-peer-input-and-original-work-verified-by-host')
    enabled = manager._list(account, 'enabled-extensions')
    disabled = manager._list(account, 'disabled-extensions')
    # Live clients can replace an unprotected stop job with D-Bus activation.
    # Reuse the owned runtime mask to stop first, seed the disabled setting,
    # then reactivate without a second stop. The new broker must recover it.
    with guest.isolated_broker_for_faults():
        request_global_extension_disable(manager, account)
        guest.require(manager._boolean(account, 'disable-user-extensions'),
                      'expiry:live-recovery-disable-not-observed')
    wait_for_extension_recovery(manager, account, 'expiry:live-extension-not-recovered')
    guest.require(not manager._boolean(account, 'disable-user-extensions')
                  and manager._runtime_state(account) == (True, True)
                  and manager._list(account, 'enabled-extensions') == enabled
                  and manager._list(account, 'disabled-extensions') == disabled,
                  'expiry:live-recovery-readback')
    guest.require(child_session(child)[0] == session, 'expiry:recovery-ended-session')
    record('onpc.expiry.live-recovery',
           'monitor-or-startup-recovery; configured-and-active; switch-and-selections-verified')
    with validation_stage('session-validation', 'zero-time-pam'):
        verify_zero_time_pam(record)
    with validation_stage('session-validation', 'runtime-rollback'):
        verify_runtime_rollback(record)
    # Keep authenticated child/kiosk requests and final recovery checks even
    # when the monitor restores the extension before approval completes.
    request_global_extension_disable(manager, account)
    with validation_stage('session-validation', 'authenticated-extension'):
        old_deadline = verify_request_extension(record)
    wait_for_extension_recovery(manager, account, 'expiry:grant-extension-not-recovered')
    guest.require(not manager._boolean(account, 'disable-user-extensions')
                  and manager._runtime_state(account) == (True, True)
                  and manager._list(account, 'enabled-extensions') == enabled
                  and manager._list(account, 'disabled-extensions') == disabled,
                  'expiry:kiosk-grant-did-not-recover-extension')
    record('onpc.expiry.kiosk-grant-recovery',
           'polkit-authenticated; monitor-or-grant-recovery; configured-and-active; switch-and-selections-verified')
    with validation_stage('session-validation', 'original-grant-deadline'):
        observation_deadline = time.monotonic() + REQUEST_EXTENSION_SECONDS + 20
        while time.time() <= old_deadline + 0.5:
            guest.require(time.monotonic() < observation_deadline, 'expiry:extension-clock-discontinuity')
            guest.require(child_session(child)[0] == session, 'expiry:extended-session-ended')
            time.sleep(0.25)
    guest.require(guest.run(['systemctl', 'is-active', scope]) == 'active'
                  and guest.run(['systemctl', 'show', scope, '--property=RuntimeMaxUSec', '--value'])
                      == 'infinity', 'expiry:extended-scope-not-retained')
    record('onpc.expiry.extended-session', 'same-session-active-past-earlier-approved-deadline')


if __name__ == '__main__':
    guest.guard()
    commands = ('host-ready', 'natural-grant', 'natural-recovery',
                'peer-grant', 'peer-recovery', 'host-complete', 'revoke-ready',
                'revoke-zero', 'revoke-positive-setup', 'revoke-positive', 'revoke-complete',
                'approval-ready', 'approval-complete', 'policy-ready', 'policy-complete',
                'policy-renew-seed', 'policy-renew', 'policy-allowance-seed',
                'policy-allowance', 'policy-disable-seed', 'policy-disable', 'policy-restrict',
                'replacement-ready', 'replacement-arm', 'replacement-entitlement',
                'replacement-bind', 'replacement-complete', 'crash-ready',
                'crash-natural-arm', 'crash-peer-arm', 'crash-inject',
                'crash-natural-recovery', 'crash-peer-recovery', 'crash-complete',
                'stop-ready', 'stop-arm', 'stop-inject', 'stop-recovery', 'stop-complete',
                'stall-ready', 'stall-natural-arm', 'stall-peer-arm', 'stall-inject',
                'stall-natural-recovery', 'stall-peer-recovery', 'stall-complete', 'stall-cleanup',
                'timer-ready', 'timer-arm', 'timer-inject', 'timer-recovery', 'timer-complete', 'timer-cleanup',
                'reply-ready', 'reply-delayed-arm', 'reply-delayed-recovery',
                'reply-missing-arm', 'reply-missing-wait', 'reply-missing-recovery', 'reply-complete',
                'retry-ready', 'retry-renew-arm', 'retry-renew', 'retry-renew-available', 'retry-renew-check',
                'retry-arm', 'retry-recovery', 'retry-complete',
                'outage-ready', 'outage-arm', 'outage-revoke', 'outage-restore',
                'outage-recovery', 'outage-complete')
    guest.require(len(sys.argv) == 2 and sys.argv[1] in (
        'prepare', 'broker-ready', 'host-observe', 'approval-natural', 'approval-peer',
        'approval-finish', *commands),
                  'expiry:graphical-arguments')
    if sys.argv[1] == 'host-observe':
        print(json.dumps(startup_observation(), sort_keys=True))
    elif sys.argv[1] in ('approval-natural', 'approval-peer'):
        pending_approval(sys.argv[1])
    elif sys.argv[1] == 'approval-finish':
        finish_pending_approval()
    elif sys.argv[1] in commands:
        print(json.dumps(graphical_history(sys.argv[1]), sort_keys=True))
    else:
        (prepare if sys.argv[1] == 'prepare' else broker_ready)()
