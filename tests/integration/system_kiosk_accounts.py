"""Installed classification migration, preserving the complete retained record.

These are engineering fixtures under the exclusive system-test guest lease.
The outer baseline restores every cache/icon/service change after the attempt.
No account, cache or daemon on the development host may enter this route.
"""

from contextlib import contextmanager
import errno
import hashlib
import json
import os
from pathlib import Path
import pwd
import re
import runpy
import shlex
import stat
import subprocess
import sys

import system_guest as guest


NAME = 'oh-no-parent-control'
INTERFACE = 'org.freedesktop.Accounts.User'
DAEMON = 'accounts-daemon.service'
CACHE = Path('/var/lib/AccountsService/users') / NAME
ICON = Path('/var/lib/AccountsService/icons/oh-no-parent-control-phase2')
MASK = Path('/run/systemd/system') / DAEMON
PROVISION = Path('/usr/libexec/oh-no-parent-control-provision')
LIFECYCLE = Path('/usr/libexec/oh-no-parent-control-kiosk-lifecycle')
MIGRATION = Path('/usr/lib/oh-no-parent-control/lifecycle/lifecycle_migration.py')
BOOT = Path('/proc/sys/kernel/random/boot_id')
SLOT = '.onpc-kiosk-visibility-v1'
TRANSACTION = 'user.oh-no-parent-control.visibility-v1'
ORDINARY_ACCOUNTS = {'administrator': 'onpc-parent-jamie', 'standard': 'onpc-child-jordan'}


def owned_bytes(path, *, optional=False, private=False):
    try:
        descriptor = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    except FileNotFoundError:
        guest.require(optional, 'kiosk-accounts:missing-record')
        return None
    with os.fdopen(descriptor, 'rb') as stream:
        info = os.fstat(stream.fileno())
        guest.require(stat.S_ISREG(info.st_mode) and info.st_uid == info.st_gid == 0 and
                      info.st_nlink == 1 and not info.st_mode & 0o022 and
                      (not private or stat.S_IMODE(info.st_mode) == 0o600) and
                      info.st_size <= 1024 * 1024,
                      'kiosk-accounts:unsafe-record')
        data = stream.read(1024 * 1024 + 1)
        guest.require(len(data) <= 1024 * 1024 and
                      (path.lstat().st_dev, path.lstat().st_ino) == (info.st_dev, info.st_ino),
                      'kiosk-accounts:record-changed')
        return data


def fingerprint(path):
    data = owned_bytes(path)
    info = path.stat()
    return {'sha256': hashlib.sha256(data).hexdigest(), 'uid': info.st_uid,
            'gid': info.st_gid, 'mode': stat.S_IMODE(info.st_mode),
            'xattrs': {name: hashlib.sha256(os.getxattr(path, name)).hexdigest()
                       for name in sorted(os.listxattr(path))}}


def fingerprint_difference(expected, actual):
    """Bounded metadata diagnostics never include record or xattr contents."""
    changed = [name for name in sorted(set(expected) | set(actual))
               if expected.get(name) != actual.get(name)]
    detail = {'fields': changed}
    if 'sha256' in changed:
        detail['sha256'] = {'expected': expected.get('sha256'), 'actual': actual.get('sha256')}
    if 'mode' in changed:
        detail['mode'] = {'expected': oct(expected['mode']), 'actual': oct(actual['mode'])}
    if 'xattrs' in changed:
        before, after = expected['xattrs'], actual['xattrs']
        names = [name for name in sorted(set(before) | set(after))
                 if before.get(name) != after.get(name)]
        detail['xattrs'] = [{'name': name[:96], 'expected_sha256': before.get(name),
                             'actual_sha256': after.get(name)} for name in names[:8]]
        detail['omitted_xattrs'] = max(0, len(names) - 8)
    return detail


def require_fingerprints(pairs, failure):
    differences = {role: fingerprint_difference(expected, actual)
                   for role, expected, actual in pairs if expected != actual}
    guest.require(not differences, failure + (':' + json.dumps(differences, sort_keys=True)
                                             if differences else ''))


def verify_fresh_restart(before, after):
    # AccountsService 23.13.9 main.c:on_bus_acquired canonicalizes user cache
    # permissions to 0600 before daemon_new. Only this fresh-start transition
    # admits the documented mode change; every other metadata field stays exact.
    guest.require(before['mode'] in (0o600, 0o644), 'kiosk-accounts:fresh-initial-mode')
    canonical = dict(before, mode=0o600)
    require_fingerprints((('cache', canonical, after),),
                         'kiosk-accounts:fresh-restart-changed-record')


def unit_property(name):
    return guest.run(['systemctl', 'show', '--value', '--property=' + name, DAEMON])


@contextmanager
def stopped_fixture_daemon():
    """Prevent D-Bus activation only while this fixture owns the runtime mask."""
    guest.require(not MASK.exists() and not MASK.is_symlink(),
                  'kiosk-accounts:foreign-runtime-mask')
    guest.require(unit_property('ActiveState') == 'active',
                  'kiosk-accounts:fixture-daemon-not-healthy')
    # Each engineered group owns a bounded set of rapid starts. Reset only a
    # healthy daemon's synthetic restart budget, never a failed service result.
    guest.run(['systemctl', 'reset-failed', DAEMON], timeout=30)
    guest.run(['systemctl', 'mask', '--runtime', DAEMON], timeout=30)
    identity = MASK.lstat()
    guest.require(MASK.is_symlink() and os.readlink(MASK) == '/dev/null',
                  'kiosk-accounts:fixture-mask')
    try:
        guest.run(['systemctl', 'stop', DAEMON], timeout=30)
        guest.require(unit_property('ActiveState') == 'inactive',
                      'kiosk-accounts:daemon-not-stopped')
        yield
    finally:
        current = MASK.lstat()
        guest.require((current.st_dev, current.st_ino) == (identity.st_dev, identity.st_ino) and
                      MASK.is_symlink() and os.readlink(MASK) == '/dev/null',
                      'kiosk-accounts:fixture-mask-replaced')
        guest.run(['systemctl', 'unmask', '--runtime', DAEMON], timeout=30)
        guest.run(['systemctl', 'start', DAEMON], timeout=45)
        guest.require(unit_property('ActiveState') == 'active',
                      'kiosk-accounts:daemon-not-active')


def resolve(account):
    guest.run(['busctl', '--system', 'call', 'org.freedesktop.Accounts',
               '/org/freedesktop/Accounts', 'org.freedesktop.Accounts',
               'FindUserById', 'x', str(account.pw_uid)])
    return f'/org/freedesktop/Accounts/User{account.pw_uid}'


def visibility(account, *, visible=True, saved=True):
    resolve(account)
    raw = guest.run(['busctl', '--system', 'get-property', 'org.freedesktop.Accounts',
                     f'/org/freedesktop/Accounts/User{account.pw_uid}', INTERFACE,
                     'SystemAccount', 'Saved'])
    guest.require(shlex.split(raw) == ['b', str(not visible).lower(), 'b', str(saved).lower()],
                  'kiosk-accounts:public-classification')


def production_provision(account):
    # Follow package configuration: retained visibility belongs to the daemon's
    # start-pre migration, while fresh caching and routing belong to provision.
    distribution = 'fedora' if guest.package_path().suffix == '.rpm' else 'ubuntu'
    needed = guest.run([str(LIFECYCLE), '--distribution', distribution, 'visibility-needed'])
    guest.require(needed in ('yes', 'no'), 'kiosk-accounts:visibility-needed-result')
    if needed == 'yes':
        guest.run(['systemctl', 'restart', DAEMON], timeout=45)
    provision = runpy.run_path(str(PROVISION))
    provision['provision_accounts_service'](account)


def routing(account):
    raw = guest.run(['busctl', '--system', 'get-property', 'org.freedesktop.Accounts',
                     f'/org/freedesktop/Accounts/User{account.pw_uid}', INTERFACE,
                     'Session', 'SessionType', 'SystemAccount'])
    guest.require(shlex.split(raw) == ['s', NAME, 's', 'wayland', 'b', 'false'],
                  'kiosk-accounts:public-routing')


def ordinary_state():
    """Read both declared baseline roles without creating or mutating metadata."""
    baseline = json.loads(guest.BASELINE.read_bytes())
    result = {}
    for role, name in ORDINARY_ACCOUNTS.items():
        account = pwd.getpwnam(name)
        guest.require(baseline['accounts'].get(name) ==
                      {'uid': account.pw_uid, 'role': role} and
                      account.pw_uid > 0 and account.pw_shell == '/bin/bash',
                      'kiosk-accounts:ordinary-baseline-role:' + role)
        path = resolve(account)
        fields = shlex.split(guest.run(['busctl', '--system', 'get-property',
            'org.freedesktop.Accounts', path, INTERFACE, 'IconFile']))
        allowed_icons = {str(ICON.parent / name),
                         '/usr/share/pixmaps/onpc-baseline-' + name + '.png'}
        guest.require(len(fields) == 2 and fields[0] == 's' and fields[1] in allowed_icons,
                      'kiosk-accounts:ordinary-icon-route:' + role)
        result[role] = {'uid': account.pw_uid, 'cache': fingerprint(CACHE.parent / name),
                        'icon_path': fields[1], 'icon': fingerprint(Path(fields[1]))}
    return result


def verify_ordinary(expected):
    actual = ordinary_state()
    guest.require(set(expected) == set(ORDINARY_ACCOUNTS), 'kiosk-accounts:ordinary-witness-roles')
    differences = {}
    for role in ORDINARY_ACCOUNTS:
        before, after = expected[role], actual[role]
        if before == after:
            continue
        # Paths and account identifiers remain private; only fixed role names
        # and bounded cache/icon metadata enter diagnostic output.
        detail = {'fields': [name for name in sorted(set(before) | set(after))
                             if before.get(name) != after.get(name)]}
        for field in ('cache', 'icon'):
            if before[field] != after[field]:
                detail[field] = fingerprint_difference(before[field], after[field])
        differences[role] = detail
    if differences:
        raise guest.GuestError('kiosk-accounts:ordinary-metadata-changed:' +
                               json.dumps(differences, sort_keys=True))


def interrupt_repair(stage):
    """Fault only this child's commit while the real daemon is quiescent.

    The sole substituted service reply admits the production start-pre check
    after an independent inactive/MainPID=0 observation. The surrounding owner
    holds its runtime activation mask. Ordinary matrix repairs use the actual
    installed systemd hook, without this engineering-only substitution.
    """
    guest.guard()
    guest.require(stage in ('failure', 'before', 'after') and MASK.is_symlink() and
                  os.readlink(MASK) == '/dev/null' and
                  unit_property('ActiveState') == 'inactive' and unit_property('MainPID') == '0',
                  'kiosk-accounts:interruption-not-quiescent')
    migration = runpy.run_path(str(MIGRATION))
    native_run = migration['subprocess'].run
    native_replace = migration['os'].replace
    query = ['systemctl', 'show', '--property=ActiveState,SubState,MainPID', DAEMON]

    def start_pre(command, **options):
        if command == query:
            return subprocess.CompletedProcess(command, 0,
                stdout='ActiveState=activating\nSubState=start-pre\nMainPID=0\n')
        return native_run(command, **options)

    def replace(source, destination, **options):
        descriptor = options.get('dst_dir_fd')
        info = os.fstat(descriptor) if type(descriptor) is int else None
        parent = CACHE.parent.stat()
        guest.require(destination == NAME and source == SLOT and info is not None and
                      (info.st_dev, info.st_ino) == (parent.st_dev, parent.st_ino),
                      'kiosk-accounts:interruption-commit-target')
        if stage == 'failure':
            raise OSError(errno.EIO, 'onpc-engineering-precommit')
        if stage == 'before':
            os._exit(72)
        native_replace(source, destination, **options)
        os._exit(73)

    migration['subprocess'].run = start_pre
    migration['os'].replace = replace
    try:
        migration['visibility']()
    except OSError as error:
        if stage == 'failure' and error.errno == errno.EIO and error.strerror == 'onpc-engineering-precommit':
            return 74
        raise
    finally:
        migration['subprocess'].run = native_run
        migration['os'].replace = native_replace
    raise guest.GuestError('kiosk-accounts:interruption-not-reached')


def fixture_record(original, *, hidden):
    """An independent byte oracle includes otherwise unrecognized metadata."""
    guest.require(original.count(b'[User]\n') == 1 and
                  len(re.findall(rb'(?m)^SystemAccount=(?:true|false)$', original)) == 1,
                  'kiosk-accounts:fixture-record-shape')
    raw = re.sub(rb'(?m)^SystemAccount=(?:true|false)$',
                 b'SystemAccount=' + (b'true' if hidden else b'false'), original)
    raw = raw.replace(b'[User]\n', b'[User]\n# Retained metadata must survive classification.\n'
                      b'X-OnpcConfinementMetadata=preserve literal value\\swith escapes\n', 1)
    icon = b'Icon=' + os.fsencode(ICON)
    if re.search(rb'(?m)^Icon=.*$', raw):
        raw = re.sub(rb'(?m)^Icon=.*$', lambda _: icon, raw)
    else:
        raw = raw.replace(b'[User]\n', b'[User]\n' + icon + b'\n', 1)
    return (raw.rstrip(b'\n') + b'\n\n[org.example.OnpcConfinementRetained]\n'
            b'Opaque=retain this extension group\n')


def write_fixture(data):
    """The selected, pinned guest cache is the sole fixture write target."""
    owned_bytes(CACHE)
    descriptor = os.open(CACHE, os.O_WRONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    with os.fdopen(descriptor, 'wb') as stream:
        info = os.fstat(stream.fileno())
        guest.require((info.st_dev, info.st_ino) == (CACHE.lstat().st_dev, CACHE.lstat().st_ino),
                      'kiosk-accounts:fixture-record-replaced')
        stream.write(data)
        stream.truncate()
        stream.flush()
        os.fsync(stream.fileno())


def state_path():
    directory = guest.PAYLOAD / 'private'
    directory.mkdir(mode=0o700, exist_ok=True)
    return directory / 'kiosk-accounts-reboot.json'


def save_witness(account, ordinary):
    path = state_path()
    guest.require(not path.exists() and not path.is_symlink(),
                  'kiosk-accounts:witness-collision')
    with path.open('x') as stream:
        os.fchmod(stream.fileno(), 0o600)
        json.dump({'boot': BOOT.read_text().strip(), 'uid': account.pw_uid,
                   'gid': account.pw_gid, 'cache': fingerprint(CACHE),
                   'icon': fingerprint(ICON), 'ordinary': ordinary}, stream, sort_keys=True)


def verify_preserved(expected, icon):
    require_fingerprints((('cache', expected, fingerprint(CACHE)),
                          ('icon', icon, fingerprint(ICON))),
                         'kiosk-accounts:retained-metadata-changed')


def verify_pending(path, expected, before, account, identity):
    actual = fingerprint(path)
    guest.require(TRANSACTION in actual['xattrs'], 'kiosk-accounts:transaction-marker-missing')
    del actual['xattrs'][TRANSACTION]
    marker = json.loads(os.getxattr(path, TRANSACTION))
    require_fingerprints((('transaction-record', expected, actual),),
                         'kiosk-accounts:transaction-state-changed')
    guest.require(marker.get('version') == 1 and
                  marker.get('uid') == account.pw_uid and
                  (marker.get('device'), marker.get('inode')) == (identity.st_dev, identity.st_ino) and
                  marker.get('before') == before['sha256'] and
                  marker.get('after') == expected['sha256'],
                  'kiosk-accounts:transaction-state-changed')


def exercise(record, *, atomic=True):
    guest.guard()
    guest.verify_package_files()
    guest.enable_diagnostics()
    account = pwd.getpwnam(NAME)
    guest.require(account.pw_shell == '/usr/sbin/nologin' and
                  unit_property('ActiveState') == 'active', 'kiosk-accounts:initial-state')
    original = owned_bytes(CACHE)
    ordinary = ordinary_state()
    original_mode = stat.S_IMODE(CACHE.stat().st_mode)
    original_attributes = {name: os.getxattr(CACHE, name) for name in os.listxattr(CACHE)}
    guest.require(not ICON.exists() and not ICON.is_symlink(), 'kiosk-accounts:icon-collision')
    with ICON.open('xb') as stream:
        os.fchmod(stream.fileno(), 0o644)
        stream.write(Path('/usr/share/oh-no-parent-control/kiosk_account_icon.png').read_bytes())
    icon = fingerprint(ICON)

    with stopped_fixture_daemon():
        # The complete original stays in memory; the outer baseline owns failure
        # recovery, including an interruption before CacheUser recreates it.
        CACHE.unlink()
    visibility(account, visible=False, saved=False)
    production_provision(account)
    visibility(account)
    routing(account)
    fresh = fingerprint(CACHE)
    production_provision(account)
    require_fingerprints((('cache', fresh, fingerprint(CACHE)),),
                         'kiosk-accounts:fresh-retry-changed-record')
    guest.run(['systemctl', 'restart', DAEMON], timeout=45)
    visibility(account)
    verify_fresh_restart(fresh, fingerprint(CACHE))
    verify_ordinary(ordinary)
    record('onpc.kiosk.accounts.fresh-cache-retry-restart', True)

    visible = fixture_record(original, hidden=False)
    with stopped_fixture_daemon():
        write_fixture(visible)
        CACHE.chmod(original_mode)
        for name in os.listxattr(CACHE):
            if name not in original_attributes:
                os.removexattr(CACHE, name)
        for name, value in original_attributes.items():
            os.setxattr(CACHE, name, value)
        os.setxattr(CACHE, 'user.onpc-confinement-metadata', b'retained-xattr')
    visibility(account)
    verify_ordinary(ordinary)
    retained = fingerprint(CACHE)
    invocation = unit_property('InvocationID')
    production_provision(account)
    production_provision(account)
    guest.require(unit_property('InvocationID') == invocation,
                  'kiosk-accounts:visible-retry-restarted-daemon')
    verify_preserved(retained, icon)
    record('onpc.kiosk.accounts.retained-visible-preserved', True)

    # Leave the live daemon's classification visible while making its retained
    # state hidden: a public in-memory readback alone must not count as durable.
    hidden = fixture_record(original, hidden=True)
    write_fixture(hidden)
    visibility(account)
    invocation = unit_property('InvocationID')
    production_provision(account)
    guest.require(unit_property('InvocationID') != invocation,
                  'kiosk-accounts:hidden-repair-did-not-reload')
    visibility(account)
    verify_preserved(retained, icon)
    verify_ordinary(ordinary)
    production_provision(account)
    verify_preserved(retained, icon)
    record('onpc.kiosk.accounts.retained-hidden-preserved-retry', True)

    write_fixture(hidden)
    CACHE.chmod(0o666)
    unsafe_identity = CACHE.lstat()
    refused = False
    try:
        production_provision(account)
    except (SystemExit, guest.CommandError, OSError):
        refused = True
    finally:
        # chmod touches only the same inode the fixture selected above.
        info = CACHE.lstat()
        guest.require(stat.S_ISREG(info.st_mode) and info.st_uid == 0 and
                      (info.st_dev, info.st_ino) ==
                      (unsafe_identity.st_dev, unsafe_identity.st_ino),
                      'kiosk-accounts:unsafe-fixture-replaced')
        CACHE.chmod(retained['mode'])
    guest.require(refused and owned_bytes(CACHE) == hidden and
                  unit_property('ActiveState') == 'active',
                  'kiosk-accounts:unsafe-state-not-preserved')
    production_provision(account)
    visibility(account)
    verify_preserved(retained, icon)
    verify_ordinary(ordinary)
    record('onpc.kiosk.accounts.unsafe-refusal-recovery', True)

    for stage, status in ((('failure', 74), ('before', 72), ('after', 73)) if atomic else ()):
        with stopped_fixture_daemon():
            write_fixture(hidden)
            before = fingerprint(CACHE)
            before_identity = CACHE.stat()
            guest.commands.run([sys.executable, '-B', str(guest.PAYLOAD / 'system_kiosk_accounts.py'),
                                'interrupt-repair', stage], check=False, timeout=60,
                               merge_stderr=False)
            # Observe the transaction boundary before asserting recovery state,
            # without exposing cache/xattr data.
            record('onpc.kiosk.accounts.atomic-observation.' + stage, {
                'stage': stage, 'status': guest.commands.last_returncode,
                'cache_unchanged': fingerprint(CACHE) == before,
                'pending_slot': os.path.lexists(CACHE.parent / SLOT),
                'committed_marker': TRANSACTION in os.listxattr(CACHE),
            })
            guest.require(guest.commands.last_returncode == status,
                          'kiosk-accounts:interruption-result')
            if stage in ('failure', 'before'):
                verify_preserved(before, icon)
                # Both a caught save failure and a process interruption retain
                # the owned record for the next daemon start to recover.
                verify_pending(CACHE.parent / SLOT, retained, before, account, before_identity)
            else:
                verify_pending(CACHE, retained, before, account, before_identity)
                guest.require(not os.path.lexists(CACHE.parent / SLOT),
                              'kiosk-accounts:committed-transaction-slot')
        visibility(account)
        verify_preserved(retained, icon)
        production_provision(account)
        verify_preserved(retained, icon)
        verify_ordinary(ordinary)
        guest.require(not os.path.lexists(CACHE.parent / SLOT),
                      'kiosk-accounts:recovered-transaction-residue')
        record('onpc.kiosk.accounts.atomic-' + stage + '-recovery', True)

    guest.run(['systemctl', 'restart', DAEMON], timeout=45)
    visibility(account)
    verify_preserved(retained, icon)
    verify_ordinary(ordinary)
    save_witness(account, ordinary)
    record('onpc.kiosk.accounts.retained-hidden-daemon-restart', True)
    record('onpc.kiosk.accounts.ordinary-metadata-preserved', True)
    for role in ORDINARY_ACCOUNTS:
        record('onpc.kiosk.accounts.' + role + '-metadata-preserved', True)


def verify_reboot(record):
    guest.guard()
    guest.verify_package_files()
    guest.enable_diagnostics()
    witness = json.loads(owned_bytes(state_path(), private=True))
    account = pwd.getpwnam(NAME)
    guest.require(witness['boot'] != BOOT.read_text().strip() and
                  (witness['uid'], witness['gid']) == (account.pw_uid, account.pw_gid) and
                  account.pw_shell == '/usr/sbin/nologin', 'kiosk-accounts:reboot-identity')
    visibility(account)
    routing(account)
    verify_preserved(witness['cache'], witness['icon'])
    verify_ordinary(witness['ordinary'])
    production_provision(account)
    verify_preserved(witness['cache'], witness['icon'])
    verify_ordinary(witness['ordinary'])
    record('onpc.kiosk.accounts.retained-hidden-reboot-preserved', True)
    record('onpc.kiosk.accounts.ordinary-reboot-preserved', True)
    for role in ORDINARY_ACCOUNTS:
        record('onpc.kiosk.accounts.' + role + '-reboot-preserved', True)


if __name__ == '__main__':
    if len(sys.argv) == 3 and sys.argv[1] == 'interrupt-repair':
        raise SystemExit(interrupt_repair(sys.argv[2]))
    else:
        guest.require(sys.argv[1:] in (['exercise'], ['exercise-live'], ['verify-reboot']),
                      'kiosk-accounts:arguments')
        record = lambda key, value: print(json.dumps({'property': key, 'value': value}, sort_keys=True))
        if sys.argv[1] == 'verify-reboot':
            verify_reboot(record)
        else:
            exercise(record, atomic=sys.argv[1] == 'exercise')
