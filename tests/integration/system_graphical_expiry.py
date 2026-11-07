"""A one-shot, installed GDM expiry fixture on the guarded automation guest.

The account hook only seeds a real one-second AccountsService grant. The stock
GDM/PAM path still decides admission and creates the desktop. This is fixture
setup, not a customer login/authentication journey. Outer VM restoration owns
all cleanup; this module never signals or terminates a session.
"""

import hashlib
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
    LIMITS, REQUEST_EXTENSION_SECONDS, identities, installed_manager, grant, verify_zero_time_pam,
    verify_request_extension, verify_runtime_rollback, request_global_extension_disable,
    wait_for_extension_recovery, isolated_broker_for_extension_faults,
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
        session = row.split()[0]
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
    if command in ('host-ready', 'revoke-ready', 'approval-ready'):
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
        current = child_session(child)
        guest.require(current is not None and current[0] == history['session']
                      and current[1]['Scope'] == history['scope']
                      and guest.run(['systemctl', 'is-active', history['scope']]) == 'active'
                      and hashlib.sha256(repr(account_state(accounts['other'])).encode()).hexdigest()
                          == history['other_state'], 'expiry:graphical-history-continuity')
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
        if command in ('host-complete', 'approval-complete'):
            guest.require(history['grants'] == 4 and not history.get('complete'),
                          'expiry:graphical-history-incomplete')
            guest.require((command == 'approval-complete') == history.get('pending_approval', False),
                          'expiry:graphical-history-kind')
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


def verify(record):
    guest.guard()
    history = json.loads((FIXTURE / 'graphical-history.json').read_text())
    guest.require(history.get('complete') is True and not history.get('foreground_revoke')
                  and not history.get('pending_approval'),
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
    with isolated_broker_for_extension_faults():
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
    verify_zero_time_pam(record)
    verify_runtime_rollback(record)
    # Keep authenticated child/kiosk requests and final recovery checks even
    # when the monitor restores the extension before approval completes.
    request_global_extension_disable(manager, account)
    old_deadline = verify_request_extension(record)
    wait_for_extension_recovery(manager, account, 'expiry:grant-extension-not-recovered')
    guest.require(not manager._boolean(account, 'disable-user-extensions')
                  and manager._runtime_state(account) == (True, True)
                  and manager._list(account, 'enabled-extensions') == enabled
                  and manager._list(account, 'disabled-extensions') == disabled,
                  'expiry:kiosk-grant-did-not-recover-extension')
    record('onpc.expiry.kiosk-grant-recovery',
           'polkit-authenticated; monitor-or-grant-recovery; configured-and-active; switch-and-selections-verified')
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
                'approval-ready', 'approval-complete')
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
