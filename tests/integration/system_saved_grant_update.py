"""Saved time across one guarded, real package update; engineering fixture only.

The runner calls prepare after the previous package's boot, verify_updated after
the native update and verify_reboot after the candidate's boot, in one attempt.
The previous package selects the history. An explicit feature-bearing pair
checks saved records and a pending transition; the newest earlier release
checks a grant that predates the record store. Public customer cases stay
separate.
"""

from dataclasses import replace
import json
import os
from pathlib import Path
import pwd
import time

import system_guest as guest
from system_assertions import accepted, account_property
from system_caller import FixturePassword, PersistentCaller, SessionCaller, TextAgent
from system_enforcement import call
from system_previous_upgrade import binding, boot, load_state, save_state
from system_removal import (GRANTS, LIMITS, grant_record, installed_grant_store, seed_saved_time,
                            verify_recovered_saved_time, verify_saved_balance)
from system_session_expiry import grant, identities

FEATURE_MODULE = Path('/usr/lib/oh-no-parent-control/broker/oh_no_parent_control/grant_store.py')
MIGRATION_MARKER = Path('/var/lib/oh-no-parent-control/migration-in-progress')
DAILY_MINUTES = 30
SAVED_SECONDS = 611
FIXED_SECONDS = 14400  # Outlasts the update and reboot, so the tuple stays live.
RELEASE_GRANT_SECONDS = 43200
DEFERRED_SECONDS = 900


def prepare(record):
    marker = guest.guard()
    guest.wait_for_boot()
    previous = guest.PAYLOAD / ('previous-package' + guest.package_path().suffix)
    installed = json.loads((guest.PAYLOAD / 'results/previous-install.json').read_text())
    guest.require(boot() != installed['boot'] and guest.reboot_cleared() and
                  guest.sha(previous) == installed['previous_package_sha256'],
                  'saved-grant-update:previous-package-not-booted')
    old = guest.package_identity(previous, installed=True)
    release = json.loads((guest.PAYLOAD / 'previous-inputs.json').read_text())['source'].get(
        'release_name')
    # Explicit pairs carry the feature; a released source must predate it.
    feature = release is None
    guest.require(FEATURE_MODULE.is_file() is feature, 'saved-grant-update:previous-package-history')
    record('onpc.saved-grant-update.packages', json.dumps({
        'history': 'feature-bearing' if feature else 'earlier-release',
        'previous_release': release, 'previous_version': old,
        'candidate_version': guest.package_identity(guest.package_path()),
        'previous_sha256': guest.sha(previous), 'candidate_sha256': marker['package_sha256'],
    }, sort_keys=True))
    accounts = identities()
    state = {'schema': 1, 'binding': binding(marker), 'boot': boot(), 'old_version': old,
             'feature': feature, 'accounts': accounts}
    state.update((prepare_feature if feature else prepare_release)(accounts, record))
    save_state(state)


def prepare_feature(accounts, record):
    parent, child, other = accounts['parent'], accounts['child'], accounts['other']
    for uid in (child, other):
        call(parent, 'SetParentControl', '(ubu)', (uid, True, DAILY_MINUTES))
    module = installed_grant_store()
    store = module.GrantStore(GRANTS)
    current = store.load(child, pwd.getpwuid(child).pw_name)
    guest.require(not current.has_state, 'saved-grant-update:saved-fixture-not-fresh')
    # A nondefault app choice makes its preservation observable.
    written = store.write(replace(current, saved=module.SavedBalance(SAVED_SECONDS, True)))
    saved, saved_digest = grant_record(child)
    guest.require(saved == written.document(), 'saved-grant-update:saved-fixture-readback')
    guest.activate_broker()
    verify_saved(accounts, saved, saved_digest)
    record('onpc.saved-grant-update.broker-restart', 'exact-saved-seconds-and-app-choice')
    grant(other, FIXED_SECONDS)
    # Match the package's own boundary: its exclusion marker, then a verified
    # broker stop. The transition stays pending until the candidate starts.
    guest.require(not os.path.lexists(MIGRATION_MARKER), 'saved-grant-update:marker-present')
    MIGRATION_MARKER.touch(mode=0o644, exist_ok=False)
    guest.run(['systemctl', 'stop', guest.BROKER], timeout=60)
    guest.require(guest.run(['systemctl', 'show', '--property=ActiveState', '--value', guest.BROKER])
                  in ('inactive', 'failed'), 'saved-grant-update:broker-not-stopped')
    pending, pending_digest = seed_saved_time(other, pending=True)
    record('onpc.saved-grant-update.prepared',
           'saved-record-survived-restart; second-child-pause-pending-at-update-boundary')
    return {'saved': saved, 'saved_digest': saved_digest,
            'pending': pending, 'pending_digest': pending_digest}


def prepare_release(accounts, record):
    parent, child = accounts['parent'], accounts['child']
    guest.require(not os.path.lexists(GRANTS), 'saved-grant-update:grant-store-before-feature')
    call(parent, 'SetParentControl', '(ubu)', (child, True, DAILY_MINUTES))
    password = FixturePassword()
    password.install(parent)
    other_parent = pwd.getpwnam('onpc-parent-casey').pw_uid
    kiosk = json.loads(Path('/etc/oh-no-parent-control/config.json').read_text())['kiosk_uid']
    with PersistentCaller(kiosk) as caller, TextAgent(caller) as agent:
        caller.send({'kind': 'call', 'method': 'RequestAccess', 'signature': '(uuub)',
                     'args': (child, parent, RELEASE_GRANT_SECONDS, True)})
        agent.prompt(parent, other_parent)
        agent.authenticate(password)
        guest.require(accepted(caller.receive())[1] == 'approved',
                      'saved-grant-update:request-not-approved')
    running = account_property(child, LIMITS, 'ActiveExtension')
    guest.require(len(running) == 2 and running[1] >= RELEASE_GRANT_SECONDS and
                  running[0] <= time.time() < sum(running), 'saved-grant-update:grant-not-running')
    record('onpc.saved-grant-update.prepared', 'earlier-release-immediate-grant; no-grant-store')
    return {'running': running, 'other_parent': other_parent}


def verify_saved(accounts, saved, digest):
    verify_saved_balance(accounts, seconds=SAVED_SECONDS, revision=saved['revision'])
    guest.require(grant_record(accounts['child'])[1] == digest, 'saved-grant-update:saved-record-changed')


def verify_deadline(state, *, saved=None):
    """The pre-feature tuple keeps running and is never treated as pausable."""
    accounts = state['accounts']
    child = accounts['child']
    status = verify_saved_balance(accounts, seconds=0 if saved is None else saved['saved']['seconds'],
                                  revision=0 if saved is None else saved['revision'])
    guest.require(account_property(child, LIMITS, 'ActiveExtension') == state['running'] and
                  status[3] > 0 and status[8] == 'deadline' and status[9] == sum(state['running']),
                  'saved-grant-update:deadline-grant-changed')
    if saved is None:
        guest.require(not os.path.lexists(GRANTS / f'{child}.json'),
                      'saved-grant-update:saved-balance-appeared')


def verify_current(state):
    if not state['feature']:
        verify_deadline(state)
        return
    accounts = state['accounts']
    verify_saved(accounts, state['saved'], state['saved_digest'])
    # Recovery abandons the pause once: revision +1, saved time and tuple unchanged.
    verify_recovered_saved_time({'parent': accounts['parent'], 'child': accounts['other']},
                                state['pending'])


def verify_untouched(state):
    """Before any candidate broker runs, migration keeps every record intact."""
    accounts = state['accounts']
    if state['feature']:
        guest.require(grant_record(accounts['child'])[1] == state['saved_digest'] and
                      grant_record(accounts['other'])[1] == state['pending_digest'],
                      'saved-grant-update:migration-changed-records')
    else:
        guest.require(not os.path.lexists(GRANTS / f"{accounts['child']}.json"),
                      'saved-grant-update:saved-balance-appeared')


def verify_updated(record):
    marker = guest.guard()
    state = load_state(marker)
    guest.require(boot() == state['boot'], 'saved-grant-update:update-boot-boundary')
    activation = json.loads((guest.PAYLOAD / 'results/update-activation.json').read_text())
    requested = activation['update_requested_reboot']
    guest.require(activation['package_sha256'] == marker['package_sha256'] and type(requested) is bool,
                  'saved-grant-update:activation-evidence')
    guest.verify_package_files()
    guest.require(guest.package_identity(guest.package_path(), installed=True) != state['old_version'],
                  'saved-grant-update:package-version-unchanged')
    if requested:
        guest.require(guest.reboot_requested(), 'saved-grant-update:update-reboot-marker-lost')
        verify_untouched(state)
        guest.verify_reboot_gate()
    else:
        guest.require(guest.reboot_cleared(), 'saved-grant-update:update-reboot-marker-unexpected')
        guest.activate_broker(restart=False)
        verify_current(state)
    record('onpc.saved-grant-update.updated',
           'records-intact-until-reboot' if requested else 'broker-recovered-after-activation')


def save_deferred(state, record):
    accounts = state['accounts']
    parent, child = accounts['parent'], accounts['child']
    password = FixturePassword()
    password.install(parent)
    # Child rules: the child's own local session, approved by its selected parent.
    with SessionCaller(child) as caller, TextAgent(caller) as agent:
        caller.send({'kind': 'call', 'method': 'RequestDeferredAccess', 'signature': '(uuubt)',
                     'args': (child, parent, DEFERRED_SECONDS, False, 0)})
        agent.prompt(parent, state['other_parent'])
        agent.authenticate(password)
        result = accepted(caller.receive())
    guest.require(result[1:] == ['saved', ''], 'saved-grant-update:deferred-not-saved')
    saved, _ = grant_record(child)
    guest.require(saved['uid'] == child and saved['fixed'] is None and saved['intent'] is None and
                  saved['saved'] == {'seconds': DEFERRED_SECONDS, 'allow_soft_blocked_apps': False},
                  'saved-grant-update:deferred-record')
    verify_deadline(state, saved=saved)
    record('onpc.saved-grant-update.deferred', 'saved-independently; deadline-grant-unchanged')


def verify_reboot(record):
    marker = guest.guard()
    state = load_state(marker)
    guest.require(boot() != state['boot'] and guest.reboot_cleared(),
                  'saved-grant-update:candidate-reboot-not-observed')
    guest.installed()
    verify_current(state)
    if not state['feature']:
        save_deferred(state, record)
    record('onpc.saved-grant-update.rebooted',
           'saved-and-recovered-records-exact' if state['feature'] else
           'deadline-grant-kept; no-saved-balance; deferred-approval-saved')
