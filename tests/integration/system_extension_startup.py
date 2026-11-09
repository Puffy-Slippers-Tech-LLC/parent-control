"""One installed offline/reboot/live-startup history; outer VM restore owns cleanup.

The boot witness runs before GDM, so neither login recovery nor the session
monitor can supply the missing durable repair. Live faults are staged while
the identity-checked broker is stopped, then attributed to its new startup.
"""

import json
import os
from pathlib import Path
import stat
import sys
import time

import system_guest as guest
from system_assertions import accepted, account_property, call
from system_extension_monitor import (
    BrokerEvents, DISABLED_CHOICE, ENABLED_CHOICE, Shell, UUID,
    invocation, native_choices, state_digest,
)
from system_graphical_expiry import child_session, prepare_broker_boot, wait_for
from system_session_expiry import grant, identities, installed_manager

FIXTURE = guest.PAYLOAD / 'results' / 'extension-startup'
BOOT_ID = Path('/proc/sys/kernel/random/boot_id')
HISTORY_SECONDS = 600


def preserved(manager, accounts, prepared):
    for role in ('child', 'other', 'parent'):
        guest.require(state_digest(accounts[role]) == prepared['accounts'][role],
                      'extension-startup:account-state-changed')
    for role in ('other', 'parent'):
        guest.require(native_choices(manager, accounts[role]) == prepared['choices'][role],
                      'extension-startup:unrelated-extension-choices-changed')


def repaired(manager, child, expected):
    guest.require(native_choices(manager, child) == expected,
                  'extension-startup:durable-settings-not-repaired')


def fault(manager, account, expected, *, individual, global_switch):
    """Finite real GNOME settings faults, with the broker already stopped."""
    guest.require(guest.run(['systemctl', 'show', guest.BROKER,
                             '--property=ActiveState', '--value']) == 'inactive',
                  'extension-startup:fault-broker-not-stopped')
    if individual:
        manager._set_list(account, 'enabled-extensions',
                          [value for value in expected[0] if value != UUID])
        manager._set_list(account, 'disabled-extensions', expected[1] + [UUID])
    if global_switch:
        manager._set_boolean(account, 'disable-user-extensions', True)
    actual = native_choices(manager, account.pw_uid)
    guest.require(actual == [([value for value in expected[0] if value != UUID]
                              if individual else expected[0]),
                             (expected[1] + [UUID] if individual else expected[1]),
                             global_switch], 'extension-startup:fault-not-observed')


def startup_proof(parent, *, live, writes):
    identity = invocation()
    timings, = accepted(call(parent, 'GetStartupTimings'))
    guest.require(timings['policy_ready_ns'] <= timings['extensions_ready_ns']
                  <= timings['register_started_ns'] <= timings['register_finished_ns'],
                  'extension-startup:readiness-order')
    events = BrokerEvents(timings)
    # Incident files contain copies of the original diagnostic records. Count
    # each event once, retaining its real writer segment and sequence identity.
    unique = {}
    for row in events.read():
        if row['segment'] == events.segment:
            sequence = row['sequence']
            guest.require(sequence not in unique or unique[sequence] == row,
                          'extension-startup:conflicting-log-record')
            unique[sequence] = row
    rows = list(unique.values())
    ready, = [row for row in rows if row['event'] == 'service.ready']
    startup = [row for row in rows if row['event'] == 'core.extension-startup']
    accepted_rows = [row for row in startup if row['fields']['outcome'] == 'accepted']
    guest.require(len(accepted_rows) == 1
                  and any(row['fields']['outcome'] == 'saved-off' for row in startup)
                  and not any(row['fields']['outcome'] in {'failed', 'child-unavailable'}
                              for row in startup), 'extension-startup:startup-not-accepted')
    completed = accepted_rows[0]
    operation = completed['operation']
    owned = [row for row in rows if row['operation'] == operation]
    started, = [row for row in owned if row['event'] == 'core.extension-startup'
                and row['fields']['outcome'] == 'started']
    context, = [row for row in owned if row['event'] == 'extension-manager.activation-context']
    guest.require(context['fields']['shell_available'] is live
                  and context['fields']['recover_global_switch'] is True
                  and started['sequence'] < completed['sequence'] < ready['sequence'],
                  'extension-startup:wrong-recovery-owner')
    # Structured logs quantize elapsed time to milliseconds. Sequence and the
    # operation boundary are exact; allow two milliseconds when mapping that
    # clock back to the public nanosecond readiness witness.
    completed_ns = int((events.origin + completed['elapsed_ms'] / 1000) * 1e9)
    guest.require(completed_ns <= timings['extensions_ready_ns'] + 2_000_000,
                  'extension-startup:repair-after-extension-readiness')
    mutations = [row for row in rows if row['sequence'] < ready['sequence']
                 and row['event'] == 'extension-manager.command'
                 and row['fields']['operation'] in {'set', 'reset', 'enable', 'disable'}]
    guest.require(bool(mutations) is writes
                  and all(row['operation'] == operation
                          and started['sequence'] < row['sequence'] < completed['sequence']
                          for row in mutations), 'extension-startup:unexpected-startup-writes')
    guest.require(invocation() == identity, 'extension-startup:broker-replaced-during-proof')
    return {'broker_invocation': identity, 'accepted_before_registration': True,
            'accepted_before_extensions_ready': True, 'live_shell': live,
            'startup_mutations': len(mutations)}


def mask_identity(mask):
    info = mask.lstat()
    guest.require(stat.S_ISLNK(info.st_mode) and info.st_uid == info.st_gid == 0
                  and os.readlink(mask) == '/dev/null', 'extension-startup:unsafe-broker-mask')
    return [info.st_dev, info.st_ino, info.st_uid, info.st_gid, info.st_mode]


def prepare():
    marker = guest.guard()
    deadline = time.monotonic() + HISTORY_SECONDS
    accounts = identities()
    manager = installed_manager()
    child = accounts['child']
    account, _ = manager._account(child)
    guest.require(not manager._shell_is_available(account), 'extension-startup:prepare-live-shell')
    guest.require(not FIXTURE.exists() and not FIXTURE.is_symlink(),
                  'extension-startup:fixture-collision')
    from oh_no_parent_control.preferences import PreferenceStore
    store = PreferenceStore()
    guest.require(all(not store.load(accounts[role])['parent_control_enabled']
                      for role in ('other', 'parent')), 'extension-startup:unrelated-controls-not-off')
    # Make saved-off isolation non-vacuous: startup must leave this peer's
    # genuine individual/global disablement intact, including all other choices.
    peer, _ = manager._account(accounts['other'])
    peer_enabled, peer_disabled, _ = native_choices(manager, accounts['other'])
    manager._set_list(peer, 'enabled-extensions', [value for value in peer_enabled if value != UUID])
    manager._set_list(peer, 'disabled-extensions',
                      [value for value in peer_disabled if value != UUID] + [UUID])
    manager._set_boolean(peer, 'disable-user-extensions', True)
    other_accounts = {role: state_digest(accounts[role]) for role in ('other', 'parent')}
    other_choices = {role: native_choices(manager, accounts[role]) for role in ('other', 'parent')}
    accepted(call(accounts['parent'], 'SetParentControl', '(ubu)', (child, True, 1440)))
    grant(child, 7200)
    enabled, disabled, global_switch = native_choices(manager, child)
    guest.require(global_switch is False
                  and not {ENABLED_CHOICE, DISABLED_CHOICE}.intersection(enabled + disabled),
                  'extension-startup:choice-fixture-collision')
    expected = [[value for value in enabled if value != UUID] + [ENABLED_CHOICE, UUID],
                [value for value in disabled if value != UUID] + [DISABLED_CHOICE], False]
    manager._set_list(account, 'enabled-extensions', expected[0])
    manager._set_list(account, 'disabled-extensions', expected[1])
    prepared = {'run': marker['run'], 'boot': BOOT_ID.read_text(),
                'accounts': {**other_accounts, 'child': state_digest(child)},
                'choices': {**other_choices, 'child': expected}}
    identity = invocation()
    with guest.isolated_broker_for_faults():
        fault(manager, account, expected, individual=True, global_switch=True)
    offline = startup_proof(accounts['parent'], live=False, writes=True)
    guest.require(offline['broker_invocation'] != identity,
                  'extension-startup:offline-broker-not-restarted')
    repaired(manager, child, expected)
    preserved(manager, accounts, prepared)
    prepared['offline'] = offline
    FIXTURE.parent.mkdir(mode=0o700, exist_ok=True)
    FIXTURE.mkdir(mode=0o700)
    with (FIXTURE / 'prepared.json').open('x') as stream:
        json.dump(prepared, stream)
    prepare_broker_boot(fedora=guest.package_path().suffix == '.rpm',
                        fixture=FIXTURE, helper='system_extension_startup.py')
    guest.run(['busctl', '--system', 'call', 'org.freedesktop.Accounts',
               f'/org/freedesktop/Accounts/User{child}',
               'org.freedesktop.Accounts.User', 'SetAutomaticLogin', 'b', 'true'])
    guest.require(account_property(child, 'org.freedesktop.Accounts.User', 'AutomaticLogin') is True,
                  'extension-startup:autologin-not-set')
    # Leave this exact owned runtime mask and fault for the real reboot. /run
    # naturally loses the mask on reboot; outer VM restoration owns failures.
    mask = Path('/run/systemd/system') / guest.BROKER
    guest.require(not mask.exists() and not mask.is_symlink(), 'extension-startup:foreign-broker-mask')
    identity = invocation()
    guest.run(['systemctl', 'mask', '--runtime', guest.BROKER], timeout=30)
    mask_owner = mask_identity(mask)
    guest.require(invocation() == identity, 'extension-startup:boot-broker-replaced')
    guest.run(['systemctl', 'stop', guest.BROKER], timeout=30)
    fault(manager, account, expected, individual=True, global_switch=True)
    guest.require(mask_identity(mask) == mask_owner
                  and not manager._shell_is_available(account)
                  and time.monotonic() < deadline, 'extension-startup:boot-fault-owner')
    preserved(manager, accounts, prepared)
    with (FIXTURE / 'boot-fault.json').open('x') as stream:
        json.dump({'run': marker['run'], 'boot': prepared['boot'], 'mask_identity': mask_owner,
                   'stopped_invocation': identity, 'individual_disabled': True,
                   'globally_disabled': True}, stream)


def broker_ready():
    """Require repaired durable settings before any child GNOME Shell exists."""
    marker = guest.guard()
    guest.enable_diagnostics()
    prepared = json.loads((FIXTURE / 'prepared.json').read_text())
    fault_witness = json.loads((FIXTURE / 'boot-fault.json').read_text())
    boot = BOOT_ID.read_text()
    guest.require(prepared['run'] == fault_witness['run'] == marker['run']
                  and prepared['boot'] == fault_witness['boot'] != boot
                  and fault_witness['individual_disabled'] and fault_witness['globally_disabled'],
                  'extension-startup:boot-fault-boundary')
    mask = Path('/run/systemd/system') / guest.BROKER
    guest.require(not mask.exists() and not mask.is_symlink(),
                  'extension-startup:runtime-mask-survived-reboot')
    manager = installed_manager()
    accounts = identities()
    account, _ = manager._account(accounts['child'])
    guest.require(not manager._shell_is_available(account)
                  and child_session(accounts['child']) is None,
                  'extension-startup:boot-child-already-live')
    proof = startup_proof(accounts['parent'], live=False, writes=True)
    guest.require(proof['broker_invocation'] != fault_witness['stopped_invocation'],
                  'extension-startup:boot-broker-not-renewed')
    repaired(manager, accounts['child'], prepared['choices']['child'])
    preserved(manager, accounts, prepared)
    guest.require(not manager._shell_is_available(account), 'extension-startup:boot-shell-race')
    with (FIXTURE / 'broker-ready.json').open('x') as stream:
        json.dump({'run': marker['run'], 'boot': boot, 'proof': proof,
                   'durable_repaired_before_gdm': True, 'no_child_shell': True}, stream)


def verify(publish):
    marker = guest.guard()
    guest.enable_diagnostics()
    deadline = time.monotonic() + HISTORY_SECONDS
    def wait(predicate, category):
        return wait_for(predicate, 'extension-startup:' + category,
                        timeout=max(0, deadline - time.monotonic()))
    prepared = json.loads((FIXTURE / 'prepared.json').read_text())
    witness = json.loads((FIXTURE / 'broker-ready.json').read_text())
    guest.require(prepared['run'] == witness['run'] == marker['run']
                  and prepared['boot'] != witness['boot'] == BOOT_ID.read_text()
                  and witness['durable_repaired_before_gdm'] and witness['no_child_shell'],
                  'extension-startup:boot-witness')
    accounts = identities()
    child = accounts['child']
    manager = installed_manager()
    account, _ = manager._account(child)
    session, props = wait(lambda: child_session(child), 'fresh-child-session')
    wait(lambda: manager._shell_is_available(account), 'fresh-shell-unavailable')
    guest.require(invocation() == witness['proof']['broker_invocation'],
                  'extension-startup:boot-broker-replaced-before-login')
    expected = prepared['choices']['child']
    observations = []
    def record(name, value):
        observations.append([name, value])
        pending = FIXTURE / 'observations.pending'
        pending.write_text(json.dumps(observations, sort_keys=True))
        pending.replace(FIXTURE / 'observations.json')
        publish('onpc.extension-startup.' + name, json.dumps(value, sort_keys=True))
    shell = Shell(account, manager.session_bus_address(child))
    def healthy():
        try:
            info = shell.info()
        except shell.GLib.Error as error:
            if shell.Gio.DBusError.get_remote_error(error) in {
                    'org.freedesktop.DBus.Error.UnknownMethod',
                    'org.freedesktop.DBus.Error.UnknownObject'}:
                return False  # Shell can own its name before exporting this object.
            raise
        return info.get('state') == 1 and info.get('enabled') is True and shell.enabled()
    try:
        wait(healthy, 'fresh-extension-not-active')
        guest.require(props['LockedHint'] == 'no'
                      and guest.run(['loginctl', 'show-session', session,
                                     '--property=Active', '--value']) == 'yes'
                      and shell.call('org.gnome.ScreenSaver', '/org/gnome/ScreenSaver',
                                     'org.gnome.ScreenSaver', 'GetActive', '()', (), '(b)') is False,
                      'extension-startup:fresh-session-locked')
        def native_time_usable():
            try:
                deadline_us = shell.call('com.puffyslippers.OhNoParentControl.ChildUI',
                    '/com/puffyslippers/OhNoParentControl/NativeTime',
                    'com.puffyslippers.OhNoParentControl.NativeTime1', 'GetDeadline', '()', (), '(t)')
                return deadline_us > time.monotonic_ns() // 1000
            except shell.GLib.Error:
                return False  # The normal fresh-login timer may still be initializing.
        wait(native_time_usable, 'native-deadline-not-usable')
        repaired(manager, child, expected)
        preserved(manager, accounts, prepared)
        record('offline', prepared['offline'])
        record('reboot', {**witness['proof'], 'durable_repaired_before_gdm': True,
                         'fresh_native_session': True, 'unlocked': True,
                         'native_deadline_usable': True})
        for name, individual, global_switch in (
                ('live-individual', True, False), ('live-global', False, True),
                ('healthy-restart', False, False)):
            identity = invocation()
            with guest.isolated_broker_for_faults():
                if individual or global_switch:
                    fault(manager, account, expected, individual=individual, global_switch=global_switch)
                    wait(lambda: not healthy(), name + '-fault-not-active')
                preserved(manager, accounts, prepared)
            proof = startup_proof(accounts['parent'], live=True, writes=individual or global_switch)
            guest.require(proof['broker_invocation'] != identity,
                          'extension-startup:live-broker-not-restarted')
            wait(healthy, name + '-not-recovered')
            current = child_session(child)
            guest.require(current is not None and current[0] == session
                          and time.monotonic() < deadline, 'extension-startup:live-session-replaced')
            repaired(manager, child, expected)
            preserved(manager, accounts, prepared)
            record(name, {**proof, 'same_native_session': True,
                          'saved_controls_grants_and_unrelated_choices_preserved': True})
    finally:
        shell.close()


if __name__ == '__main__':
    guest.require(len(sys.argv) == 2 and sys.argv[1] in {'prepare', 'broker-ready'},
                  'extension-startup:arguments')
    if sys.argv[1] == 'prepare':
        prepare()
    else:
        broker_ready()
