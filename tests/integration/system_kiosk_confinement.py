"""Installed kernel-boundary probes, separate from customer UI acceptance."""
import ctypes
import errno
import json
import os
from pathlib import Path
import pwd
import select
import signal
import sys
import time
import tempfile
import shutil
import hashlib
import runpy
import shlex
import re
import stat
import struct
import fcntl
import grp
import socket
from contextlib import ExitStack, contextmanager

import system_guest as guest


ENV = ['PATH=/usr/bin:/bin', 'LANG=C', 'LC_ALL=C']
PROC = Path('/proc')
MANAGER_SID = 'system_u:system_r:onpc_kiosk_manager_t:s0'
SIBLING_PARENT = Path('/usr/share')
REQUIRED_ANCESTOR = Path('/usr/lib/systemd')
REQUIRED_EXECUTABLE = REQUIRED_ANCESTOR / 'systemd'
PROBE_TRUST_DIRECTORY = Path('/etc/fapolicyd/trust.d')


def required_ancestor_checkpoint():
    from system_native_update import private, read_private
    marker = guest.guard()
    data = read_private(private() / 'required-ancestor.json')
    guest.require(data['binding'] == {key: marker[key] for key in
                  ('run', 'package_sha256', 'selected_inputs_sha256')} and
                  data['path'] == str(REQUIRED_ANCESTOR), 'kiosk-required:checkpoint-binding')
    return data


def required_ancestor_state():
    info = REQUIRED_ANCESTOR.lstat()
    guest.require(REQUIRED_ANCESTOR.resolve(strict=True) == REQUIRED_ANCESTOR and
                  stat.S_ISDIR(info.st_mode), 'kiosk-required:ancestor-type')
    return {'identity': sibling_identity(REQUIRED_ANCESTOR),
            'executable_sha256': guest.sha(REQUIRED_EXECUTABLE)}


def required_ordinary_access(expected):
    from system_kiosk_accounts import verify_ordinary
    verify_ordinary(expected)
    digest = guest.sha(REQUIRED_EXECUTABLE)
    for role in ('onpc-parent-jamie', 'onpc-child-jordan'):
        account = pwd.getpwnam(role)
        guest.require(hashlib.sha256(user_command(account,
                      ['/usr/bin/cat', str(REQUIRED_EXECUTABLE)])).hexdigest() == digest and
                      b'systemd ' in user_command(account, [str(REQUIRED_EXECUTABLE), '--version']),
                      'kiosk-required:ordinary-access')


def prepare_required_ancestor():
    """Persist the exact owned mutation before changing a real required parent."""
    from system_kiosk_accounts import ordinary_state
    from system_native_update import publish
    marker = guest.guard()
    guest.enable_diagnostics()
    wait_kiosk_inactive(pwd.getpwnam('oh-no-parent-control'))
    original = required_ancestor_state()
    info = original['identity']
    guest.require(info[3:] == [0, 0] and not info[2] & 0o022,
                  'kiosk-required:ancestor-trust')
    # Independently bind this parent to the installed native inventory.
    preparation = runpy.run_path('/usr/libexec/oh-no-parent-control-kiosk-confinement')
    config = json.loads(Path('/usr/share/oh-no-parent-control/confinement/config.json').read_text())
    records = preparation['inventory'](config)
    guest.require(any(Path(row['path']).resolve() == REQUIRED_EXECUTABLE for row in records),
                  'kiosk-required:not-required')
    ordinary = ordinary_state()
    required_ordinary_access(ordinary)
    data = {'binding': {key: marker[key] for key in
            ('run', 'package_sha256', 'selected_inputs_sha256')},
            'path': str(REQUIRED_ANCESTOR), 'original': original, 'ordinary': ordinary,
            'since': str(time.time()), 'kernel': guest.run(['uname', '-r']),
            'backend': config['backend']}
    publish('required-ancestor.json', data)
    REQUIRED_ANCESTOR.chmod(stat.S_IMODE(info[2]) | 0o020)
    expected = {**original, 'identity': [*info[:2], info[2] | 0o020, *info[3:]]}
    guest.require(required_ancestor_state() == expected, 'kiosk-required:mutation')


def required_refusal_markers(since, *, require_preparation=True):
    """Keep closed native causes and source times, never raw journal text."""
    raw = guest.run(['journalctl', '-b', '--since=@' + since, '--no-pager', '-o', 'json'],
                    timeout=30)
    rows = []
    pattern = re.compile(r'onpc\.kiosk confinement preparation outcome=denied '
                         r'role=(manager|gate) stage=(executable-inventory) reason=(untrusted-path)(?: |$)')
    native = re.compile(r'onpc\.pam kiosk execution-boundary outcome=(denied) stage=(prepare)(?: |$)')
    for line in raw.splitlines():
        row = json.loads(line)
        message = row.get('MESSAGE', '')
        for kind, expression in (('preparation', pattern), ('native', native)):
            match = expression.search(message) if isinstance(message, str) else None
            if match:
                rows.append({'kind': kind, 'fields': list(match.groups()),
                             'source_us': row['__REALTIME_TIMESTAMP']})
    guest.require((not require_preparation or any(row['kind'] == 'preparation' for row in rows)) and
                  any(row['kind'] == 'native' for row in rows), 'kiosk-required:missing-native-cause')
    return rows


def verify_required_refusal():
    """Run the original native PAM refusal while the exact mutation is present."""
    from system_native_update import publish
    data = required_ancestor_checkpoint()
    info = data['original']['identity']
    guest.require(required_ancestor_state() == {**data['original'],
                  'identity': [*info[:2], info[2] | 0o020, *info[3:]]},
                  'kiosk-required:mutation-changed')
    account = pwd.getpwnam('oh-no-parent-control')
    with tempfile.TemporaryDirectory(prefix='required-refusal-', dir=guest.PAYLOAD) as directory:
        with tempfile.TemporaryFile(dir=directory) as diagnostic:
            saved = os.dup(2)
            try:
                os.dup2(diagnostic.fileno(), 2)
                status, result = first_exec(account, Path(directory),
                    [str(REQUIRED_EXECUTABLE), '--version'], service='systemd-user', armed=False)
            finally:
                os.dup2(saved, 2)
                os.close(saved)
            diagnostic.seek(0)
            cause = diagnostic.read(65537)
    guest.require(len(cause) <= 65536 and b'onpc.kiosk confinement preparation outcome=denied '
                  b'role=manager stage=executable-inventory reason=untrusted-path ' in cause,
                  'kiosk-required:original-cause')
    guest.require(status == 125 and json.loads(result)['pam'] != 0,
                  'kiosk-required:unsafe-ancestor-admitted')
    required_ordinary_access(data['ordinary'])
    publish('required-native-refusal.json', {'status': status, 'pam': json.loads(result)['pam'],
            'preparation': {'role': 'manager', 'stage': 'executable-inventory', 'reason': 'untrusted-path'},
            'markers': required_refusal_markers(data['since'], require_preparation=False)})


def verify_required_gdm_refusal():
    """Independent safe session result plus causes from the actual GDM attempt."""
    from system_native_update import publish, private, read_private
    data = required_ancestor_checkpoint()
    prior = read_private(private() / 'required-native-refusal.json')
    deadline = time.monotonic() + 75
    while True:
        guest.guard()
        try:
            markers = required_refusal_markers(data['since'])
        except guest.GuestError as error:
            if str(error) != 'kiosk-required:missing-native-cause':
                raise
            markers = []
        previous = max(int(row['source_us']) for row in prior['markers'])
        if all(any(row['kind'] == kind and int(row['source_us']) > previous
                   for row in markers) for kind in ('native', 'preparation')):
            break
        guest.require(time.monotonic() < deadline, 'kiosk-required:no-new-gdm-refusal')
        time.sleep(0.25)
    account = pwd.getpwnam('oh-no-parent-control')
    wait_kiosk_inactive(account)
    sessions = guest.run(['loginctl', 'list-sessions', '--no-legend', '--no-pager'])
    guest.require(not any(account.pw_name in line.split() for line in sessions.splitlines()),
                  'kiosk-required:graphical-session-admitted')
    required_ordinary_access(data['ordinary'])
    publish('required-gdm-refusal.json', {'markers': markers, 'station_session': 'absent',
                                        'ordinary_access': 'passed'})


def restore_required_ancestor():
    """Restore only the recorded inode/owner/bytes and expected mode transition."""
    from system_native_update import publish, private
    guest.guard()
    if not (private() / 'required-ancestor.json').exists():
        # No durable mutation intent means preparation did not reach chmod.
        return
    data = required_ancestor_checkpoint()
    original = data['original']
    current = required_ancestor_state()
    info = original['identity']
    mutated = {**original, 'identity': [*info[:2], info[2] | 0o020, *info[3:]]}
    guest.require(current in (original, mutated), 'kiosk-required:restoration-identity')
    descriptor = os.open(REQUIRED_ANCESTOR, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
    try:
        actual = os.fstat(descriptor)
        guest.require([actual.st_dev, actual.st_ino, actual.st_mode, actual.st_uid, actual.st_gid]
                      == current['identity'], 'kiosk-required:restoration-identity')
        os.fchmod(descriptor, stat.S_IMODE(info[2]))
    finally:
        os.close(descriptor)
    guest.require(required_ancestor_state() == original, 'kiosk-required:restoration-mismatch')
    required_ordinary_access(data['ordinary'])
    publish('required-restored.json', {'outcome': 'passed', 'original': original})


def cleanup_required_ancestor():
    from system_native_update import publish
    data = required_ancestor_checkpoint()
    guest.require(required_ancestor_state() == data['original'], 'kiosk-required:cleanup-identity')
    wait_kiosk_inactive(pwd.getpwnam('oh-no-parent-control'))
    required_ordinary_access(data['ordinary'])
    publish('required-cleanup.json', {'outcome': 'passed', 'original': data['original']})


def verify_required_recovery(record):
    from system_native_update import private, read_private
    data = required_ancestor_checkpoint()
    guest.require(required_ancestor_state() == data['original'], 'kiosk-required:not-restored')
    for name in ('required-native-refusal.json', 'required-gdm-refusal.json', 'required-restored.json'):
        record('onpc.kiosk.required.' + name, json.dumps(read_private(private() / name), sort_keys=True))
    record('onpc.kiosk.required.input', json.dumps(data, sort_keys=True))
    config = json.loads(Path('/usr/share/oh-no-parent-control/confinement/config.json').read_text())
    record_native_packages(config, record)
    record('onpc.kiosk.required.census', json.dumps(census(), sort_keys=True))
    account = pwd.getpwnam('oh-no-parent-control')
    guest.require(b'systemd ' in user_command(account,
        ['/usr/bin/systemd-run', '--user', '--wait', '--collect', '--pipe',
         '--unit=onpc-required-positive', '/usr/bin/systemctl', '--version']),
        'kiosk-required:positive-native-exec')
    require_service_denial(account, config['backend'], 'onpc-required-denied.service',
                           ['/bin/sh', '-c', 'exit 0'], record)
    required_ordinary_access(data['ordinary'])
    record('onpc.kiosk.required.restored-ordinary-access', 'passed')


def sibling_identity(path):
    info = path.lstat()
    return [info.st_dev, info.st_ino, info.st_mode, info.st_uid, info.st_gid]


def sibling_snapshot(path):
    """Finite inert fixtures only; never recurse into an unexpected entry."""
    identity = sibling_identity(path)
    if stat.S_ISDIR(identity[2]):
        guest.require(sorted(item.name for item in path.iterdir()) == ['canary'],
                      'kiosk-sibling:unexpected-contents')
        guest.require(stat.S_ISREG((path / 'canary').lstat().st_mode),
                      'kiosk-sibling:unexpected-type')
        return {'identity': identity, 'canary': sibling_snapshot(path / 'canary')}
    guest.require(stat.S_ISREG(identity[2]) and path.lstat().st_nlink == 1 and
                  path.lstat().st_size <= 128,
                  'kiosk-sibling:unexpected-type')
    return {'identity': identity, 'sha256': guest.sha(path)}


def sibling_remove(path, expected):
    # Compare everything before unlinking any child. Unknown/replaced entries
    # are preserved for the enclosing controller's identity-owned recovery.
    guest.require(sibling_snapshot(path) == expected, 'kiosk-sibling:cleanup-identity')
    if 'canary' in expected:
        (path / 'canary').unlink()
        path.rmdir()
    else:
        path.unlink()


def sibling_checkpoint():
    from system_native_update import private, read_private
    marker = guest.guard()
    data = read_private(private() / 'sibling-inputs.json')
    guest.require(data['binding'] == {key: marker[key] for key in
                  ('run', 'package_sha256', 'selected_inputs_sha256')},
                  'kiosk-sibling:checkpoint-binding')
    prefix = 'onpc-sibling-' + marker['run'] + '-'
    guest.require(len(data['rows']) == 5 and
                  [row['name'] for row in data['rows']] == [prefix + suffix for suffix in
                   ('root-0775', 'root-0777', 'user-0755', 'user-0555', 'omitted')],
                  'kiosk-sibling:checkpoint-paths')
    return data


def sibling_create(path, mode, uid, gid, content, *, directory):
    """Exclusive creation; these files are deliberate attempt mutations."""
    if directory:
        path.mkdir(mode=0o700)
        target = path / 'canary'
    else:
        target = path
    with target.open('xb') as output:
        output.write(content)
    target.chmod(0o444 if directory else mode)
    os.chown(path, uid, gid, follow_symlinks=False)
    path.chmod(mode)
    return sibling_snapshot(path)


def prepare_siblings():
    from system_native_update import publish
    marker = guest.guard()
    guest.enable_diagnostics()
    account = pwd.getpwnam('oh-no-parent-control')
    wait_kiosk_inactive(account)
    parent = SIBLING_PARENT.lstat()
    guest.require(SIBLING_PARENT.resolve(strict=True) == SIBLING_PARENT and
                  stat.S_ISDIR(parent.st_mode) and parent.st_uid == parent.st_gid == 0 and
                  not parent.st_mode & 0o022, 'kiosk-sibling:fixture-parent')
    child = pwd.getpwnam('onpc-child-riley')
    guest.require(child.pw_uid > 0 and child.pw_uid != account.pw_uid,
                  'kiosk-sibling:ordinary-identity')
    rows = []
    try:
        for suffix, mode, uid, gid, directory in (
                ('root-0775', 0o775, 0, 0, True), ('root-0777', 0o777, 0, 0, True),
                ('user-0755', 0o755, child.pw_uid, child.pw_gid, True),
                ('user-0555', 0o555, child.pw_uid, child.pw_gid, True),
                ('omitted', 0o644, child.pw_uid, child.pw_gid, False)):
            name = 'onpc-sibling-' + marker['run'] + '-' + suffix
            path = SIBLING_PARENT / name
            # Preflight all destinations, including restoration aliases, before
            # exclusive creation. Never adopt a dangling link or old fixture.
            guest.require(not os.path.lexists(path) and not os.path.lexists(str(path) + '-saved'),
                          'kiosk-sibling:fixture-collision')
            snapshot = sibling_create(path, mode, uid, gid,
                                      ('original-' + suffix + '\n').encode(), directory=directory)
            rows.append(dict(name=name, snapshot=snapshot, directory=directory))
        data = {'binding': {key: marker[key] for key in
                ('run', 'package_sha256', 'selected_inputs_sha256')}, 'rows': rows}
        sibling_ordinary_controls(rows, lambda *_: None, 'before-entry')
        publish('sibling-inputs.json', data)
    except BaseException:
        for row in reversed(rows):
            sibling_remove(SIBLING_PARENT / row['name'], row['snapshot'])
        raise


def sibling_ordinary_controls(rows, record, stage):
    for role in ('onpc-child-riley', 'onpc-parent-jamie'):
        account = pwd.getpwnam(role)
        for row in rows:
            path = SIBLING_PARENT / row['name']
            guest.require(sibling_snapshot(path) == row['snapshot'],
                          'kiosk-sibling:host-fixture-changed')
            target = path / 'canary' if row['directory'] else path
            output = user_command(account, ['/usr/bin/cat', str(target)])
            guest.require(hashlib.sha256(output).hexdigest() ==
                          (row['snapshot']['canary'] if row['directory'] else
                           row['snapshot'])['sha256'], 'kiosk-sibling:ordinary-access')
            if row['directory']:
                guest.require(user_command(account, ['/usr/bin/ls', '-A', str(path)]).strip() ==
                              b'canary', 'kiosk-sibling:ordinary-contents')
    record('onpc.kiosk.sibling.ordinary.' + stage, 'passed')


def sibling_private_views(rows, record, stage):
    """Observe actual live process roots, independent of preparation records."""
    result = census()
    account = pwd.getpwnam('oh-no-parent-control')
    seen = 0
    for process in PROC.iterdir():
        if not process.name.isdecimal():
            continue
        try:
            identity = process_identity(process)
            if str(account.pw_uid) not in identity[2]:
                continue
            descriptor = os.pidfd_open(int(process.name))
        except (ProcessLookupError, FileNotFoundError):
            continue
        try:
            for row in rows:
                visible = process / 'root' / SIBLING_PARENT.relative_to('/') / row['name']
                if row['directory']:
                    info = visible.lstat()
                    guest.require(stat.S_ISDIR(info.st_mode) and not list(visible.iterdir()) and
                                  [info.st_dev, info.st_ino] != row['snapshot']['identity'][:2],
                                  'kiosk-sibling:mutable-directory-visible')
                else:
                    guest.require(not os.path.lexists(visible), 'kiosk-sibling:omitted-entry-visible')
            guest.require(not exited(descriptor) and process_identity(process) == identity,
                          'kiosk-sibling:observer-lifecycle-changed')
            seen += 1
        finally:
            os.close(descriptor)
    guest.require(seen > 0, 'kiosk-sibling:no-private-view')
    record('onpc.kiosk.sibling.private.' + stage,
           json.dumps(dict(processes=seen, **result), sort_keys=True))


@contextmanager
def sibling_replacement(row):
    path = SIBLING_PARENT / row['name']
    saved = path.with_name(path.name + '-saved')
    guest.require(sibling_snapshot(path) == row['snapshot'] and not os.path.lexists(saved),
                  'kiosk-sibling:replacement-identity')
    path.rename(saved)
    replacement = None
    try:
        original = row['snapshot']['identity']
        replacement = sibling_create(path, stat.S_IMODE(original[2]), original[3], original[4],
                                     b'replacement-mutable-content\n', directory=row['directory'])
        guest.require(replacement['identity'][:2] != original[:2],
                      'kiosk-sibling:replacement-not-new')
        yield {**row, 'snapshot': replacement}
    finally:
        if replacement is not None:
            sibling_remove(path, replacement)
        guest.require(not os.path.lexists(path) and sibling_snapshot(saved) == row['snapshot'],
                      'kiosk-sibling:restoration-identity')
        saved.rename(path)
        guest.require(sibling_snapshot(path) == row['snapshot'], 'kiosk-sibling:restoration-mismatch')


def verify_sibling_isolation(record):
    guest.guard()
    guest.enable_diagnostics()
    rows = sibling_checkpoint()['rows']
    config = json.loads(Path('/usr/share/oh-no-parent-control/confinement/config.json').read_text())
    record_native_packages(config, record)
    record('onpc.kiosk.sibling.fixtures', json.dumps(rows, sort_keys=True))
    record('onpc.kiosk.sibling.kernel', guest.run(['uname', '-r']))
    account = pwd.getpwnam('oh-no-parent-control')
    unit = f'user@{account.pw_uid}.service'
    manager = PROC / str(manager_pid(unit))
    descriptor = os.pidfd_open(int(manager.name))
    identity = process_identity(manager)
    namespace = os.readlink(manager / 'ns/mnt')
    generation = (manager / 'root/usr/share/oh-no-parent-control/confinement/generation').read_text()
    try:
        sibling_ordinary_controls(rows, record, 'initial')
        sibling_private_views(rows, record, 'initial')
        guest.require(b'systemd ' in user_command(account,
            ['/usr/bin/systemd-run', '--user', '--wait', '--collect', '--pipe',
             '--unit=onpc-sibling-positive', '/usr/bin/systemctl', '--version']),
            'kiosk-sibling:positive-native-exec')
        require_service_denial(account, config['backend'], 'onpc-sibling-denied.service',
                               ['/bin/sh', '-c', 'exit 0'], record)
        # Replace one masked directory and the omitted file in the SAME live
        # station, retaining the old inodes for exact restoration.
        with sibling_replacement(rows[1]) as directory, sibling_replacement(rows[4]) as omitted:
            replaced = [rows[0], directory, rows[2], rows[3], omitted]
            record('onpc.kiosk.sibling.replacements', json.dumps(replaced, sort_keys=True))
            sibling_ordinary_controls(replaced, record, 'replacement')
            sibling_private_views(replaced, record, 'replacement')
            guest.require(not exited(descriptor) and manager_pid(unit) == int(manager.name) and
                          process_identity(manager) == identity and
                          os.readlink(manager / 'ns/mnt') == namespace and
                          (manager / 'root/usr/share/oh-no-parent-control/confinement/generation').read_text()
                          == generation, 'kiosk-sibling:retained-manager-changed')
            record('onpc.kiosk.sibling.retained-manager', 'passed')
        sibling_ordinary_controls(rows, record, 'restored')
        sibling_private_views(rows, record, 'restored')
        record('onpc.kiosk.sibling.restoration', 'passed')
    finally:
        os.close(descriptor)


def cleanup_siblings():
    from system_native_update import publish
    rows = sibling_checkpoint()['rows']
    for row in rows:
        path = SIBLING_PARENT / row['name']
        guest.require(not os.path.lexists(str(path) + '-saved') and
                      sibling_snapshot(path) == row['snapshot'], 'kiosk-sibling:cleanup-identity')
    for row in reversed(rows):
        sibling_remove(SIBLING_PARENT / row['name'], row['snapshot'])
    guest.require(all(not os.path.lexists(SIBLING_PARENT / row['name']) for row in rows),
                  'kiosk-sibling:cleanup-incomplete')
    publish('sibling-cleanup.json', {'outcome': 'passed', 'fixtures': rows})


def wait_kiosk_inactive(account, *,
                        identity_category='kiosk-confinement:kiosk-identity-changed',
                        active_category='kiosk-confinement:manager-already-active'):
    """Let a completed GDM logout settle without adopting or stopping its manager."""
    deadline = time.monotonic() + 75
    unit = f'user@{account.pw_uid}.service'
    while True:
        guest.guard()
        guest.require(pwd.getpwnam('oh-no-parent-control').pw_uid == account.pw_uid,
                      identity_category)
        state = guest.run(['systemctl', 'show', '--value', '--property=ActiveState', unit])
        if state in ('inactive', 'failed'):
            return
        guest.require(state in ('active', 'activating', 'deactivating') and
                      time.monotonic() < deadline, active_category)
        time.sleep(0.25)


def exited(pidfd):
    poll = select.poll()
    poll.register(pidfd, select.POLLIN)
    return bool(poll.poll(0))


def process_identity(process):
    # The comm field can contain spaces and parentheses; fields after its last
    # ')' begin at stat field 3. Keep starttime to detect reuse as well as exit.
    fields = (process / 'stat').read_text().rsplit(')', 1)[1].split()
    status = dict(line.split(':', 1) for line in (process / 'status').read_text().splitlines()
                  if ':' in line)
    return (fields[19], int(status['PPid']), tuple(status['Uid'].split()))


def census_thread_identity(thread):
    """A task can exit while its parent and process pidfd remain live."""
    try:
        return process_identity(thread)
    except (FileNotFoundError, ProcessLookupError) as error:
        raise guest.GuestError('kiosk-census:process-lifecycle-changed') from error


def confined_thread_roles(thread, config, backend, generation, host_namespace):
    guest.require(os.readlink(thread / 'ns/mnt') != host_namespace,
                  'kiosk-census:unconfined-namespace')
    marker = 'usr/share/oh-no-parent-control/confinement/generation'
    guest.require((thread / 'root' / marker).read_text() == generation,
                  'kiosk-census:unconfined-generation')
    attribute = 'attr/apparmor/current' if backend == 'apparmor' else 'attr/current'
    label = (thread / attribute).read_text().strip().rstrip('\0')
    if backend == 'apparmor':
        guest.require(label.endswith(' (enforce)'), 'kiosk-census:unenforced-thread')
        roles = label.removesuffix(' (enforce)').split('//&')
        guest.require(all(role in config['apparmor_profiles'] for role in roles),
                      'kiosk-census:unconfined-thread')
        return roles
    roles = label.split(':')
    guest.require(len(roles) == 4 and roles[:2] == ['system_u', 'system_r'] and
        roles[3] == 's0' and roles[2] in {
            'onpc_kiosk_' + name.replace('-', '_') + '_t' for name in config['domains']},
        'kiosk-census:unconfined-thread')
    return [roles[2]]


def census(*, required_roles=('manager', 'app', 'service', 'wellbeing', 'pipewire')):
    """Read-only engineering check after the real GDM request form appears.

    Include every process with any kiosk UID and every surviving thread. This
    catches daemons forked by earlier PAM callbacks, not just the final app.
    Only role counts leave the guest; command lines and account data do not.
    """
    guest.guard()
    account = pwd.getpwnam('oh-no-parent-control')
    payload = Path('/usr/share/oh-no-parent-control/confinement')
    config = json.loads((payload / 'config.json').read_text())
    preparation = runpy.run_path('/usr/libexec/oh-no-parent-control-kiosk-confinement')
    preparation['enforcing'](config)
    backend = config['backend']
    unit = f'user@{account.pw_uid}.service'
    manager = PROC / str(manager_pid(unit))
    manager_fd = os.pidfd_open(int(manager.name))
    try:
        deadline = time.monotonic() + 5
        first_race = None
        while True:
            try:
                return census_processes(account, config, backend, manager, manager_fd, unit,
                                        required_roles=required_roles)
            except guest.GuestError as error:
                # A changing task set is not a security-policy refusal. Discard
                # the whole observation and keep the original manager pinned.
                if str(error) != 'kiosk-census:process-lifecycle-changed':
                    raise
                if first_race is None:
                    first_race = error
                if time.monotonic() >= deadline:
                    raise first_race
                time.sleep(0.05)
                guest.guard()
                preparation['enforcing'](config)
                guest.require(not exited(manager_fd) and
                              manager_pid(unit) == int(manager.name),
                              'kiosk-census:manager-lifecycle-changed')
                if time.monotonic() >= deadline:
                    raise first_race
    finally:
        os.close(manager_fd)


def census_processes(account, config, backend, manager, manager_fd, unit, *,
                     required_roles=('manager', 'app', 'service', 'wellbeing', 'pipewire')):
    payload = Path('/usr/share/oh-no-parent-control/confinement')
    manager_identity = process_identity(manager)
    guest.require(manager_identity[2] == (str(account.pw_uid),) * 4,
                  'kiosk-census:manager-uid')
    marker = str(payload / 'generation').lstrip('/')
    generation = (manager / 'root' / marker).read_text()
    guest.require(generation.strip() != 'unconfined', 'kiosk-census:manager-generation')
    host_namespace = os.readlink(PROC / '1/ns/mnt')
    attribute = 'attr/apparmor/current' if backend == 'apparmor' else 'attr/current'
    expected = 'onpc-kiosk-manager (enforce)' if backend == 'apparmor' else MANAGER_SID
    guest.require((manager / attribute).read_text().strip().rstrip('\0') == expected,
                  'kiosk-census:manager-label')
    counts = {}
    for process in PROC.iterdir():
        if not process.name.isdecimal():
            continue
        pidfd = None
        try:
            pidfd = os.pidfd_open(int(process.name))
            identity = process_identity(process)
            threads = {thread: census_thread_identity(thread)
                       for thread in (process / 'task').iterdir()}
            # Linux credentials belong to individual threads. A root leader
            # must not hide a sibling which adopted any kiosk credential.
            relevant = any(str(account.pw_uid) in value[2] for value in threads.values())
            if (relevant and backend == 'selinux' and
                    (process / 'attr/current').read_text().strip().rstrip('\0') ==
                    'system_u:system_r:policykit_auth_t:s0'):
                password_helper_process(process, account, config, manager, generation,
                                        host_namespace, identity, threads)
                counts['policykit_auth_t'] = counts.get('policykit_auth_t', 0) + len(threads)
                relevant = False
            for thread in threads if relevant else ():
                for role in confined_thread_roles(thread, config, backend, generation, host_namespace):
                    counts[role] = counts.get(role, 0) + 1
            guest.require(set((process / 'task').iterdir()) == set(threads) and
                          all(census_thread_identity(thread) == value
                              for thread, value in threads.items()) and
                          process_identity(process) == identity and not exited(pidfd),
                          'kiosk-census:process-lifecycle-changed')
        except (FileNotFoundError, ProcessLookupError):
            if pidfd is not None:
                guest.require(exited(pidfd), 'kiosk-census:live-process-unreadable')
        finally:
            if pidfd is not None:
                os.close(pidfd)
    guest.require(not exited(manager_fd) and process_identity(manager) == manager_identity and
                  manager_pid(unit) == int(manager.name), 'kiosk-census:manager-lifecycle-changed')
    guest.require(all(role in config['domains'] for role in required_roles),
                  'kiosk-census:unknown-required-role')
    for role in required_roles:
        name = ('onpc-kiosk-' + role if backend == 'apparmor'
                else 'onpc_kiosk_' + role.replace('-', '_') + '_t')
        guest.require(counts.get(name, 0) > 0, 'kiosk-census:required-service-missing:' + role)
    return {'backend': backend, 'confined_thread_roles': counts}


def password_helper_process(process, account, config, manager, generation,
                            host_namespace, identity, threads):
    """Qualify one measured Fedora native helper, never a domain-wide exception."""
    path = '/usr/lib/polkit-1/polkit-agent-helper-1'
    expected = dict(path=path, mode=0o4755,
                    label='system_u:object_r:policykit_auth_exec_t:s0')
    guest.require(config.get('preserved_executables') == [expected] and
                  re.fullmatch(r'[0-9a-f]{64}\n', generation) is not None,
                  'kiosk-password:unmeasured-inventory')
    # The global enforcing bit alone does not exclude a permissive helper
    # domain. Reuse the installed preparation check, including its vendor SID.
    preparation = runpy.run_path('/usr/libexec/oh-no-parent-control-kiosk-confinement')
    preparation['enforcing'](config)
    parent = PROC / str(identity[1])
    parent_fd = os.pidfd_open(identity[1])
    try:
        parent_identity = process_identity(parent)
        parent_threads = {thread: process_identity(thread) for thread in (parent / 'task').iterdir()}
        namespace = os.readlink(manager / 'ns/mnt')
        guest.require(namespace != host_namespace and bool(threads) and bool(parent_threads),
                      'kiosk-password:empty-or-host-namespace')
        marker = 'usr/share/oh-no-parent-control/confinement/generation'
        for thread, value in threads.items():
            guest.require(value[2] == (str(account.pw_uid), '0', '0', '0') and
                          value[1] == int(parent.name), 'kiosk-password:credentials')
            guest.require((thread / 'attr/current').read_text().strip().rstrip('\0') ==
                          'system_u:system_r:policykit_auth_t:s0', 'kiosk-password:thread-label')
            guest.require(os.readlink(thread / 'ns/mnt') == namespace and
                          (thread / 'root' / marker).read_text() == generation,
                          'kiosk-password:namespace-generation')
        for thread, value in parent_threads.items():
            guest.require(value[2] == (str(account.pw_uid),) * 4 and
                          os.readlink(thread / 'ns/mnt') == namespace and
                          confined_thread_roles(thread, config, 'selinux', generation, host_namespace) ==
                          ['onpc_kiosk_polkit_t'], 'kiosk-password:parent-role')
        parent_exe = (parent / 'exe').stat()
        guest.require(any((parent_exe.st_dev, parent_exe.st_ino) ==
                          (pinned.st_dev, pinned.st_ino)
                          for entry in config['executables'] if entry['role'] == 'polkit'
                          for name in entry['paths']
                          for pinned in [(manager / 'root' / name.lstrip('/')).stat()]),
                      'kiosk-password:parent-executable')
        pinned = manager / 'root' / path.lstrip('/')
        with pinned.open('rb') as stream:
            before = os.fstat(stream.fileno())
            guest.require(stat.S_ISREG(before.st_mode) and before.st_nlink in (0, 1) and
                          before.st_uid == before.st_gid == 0 and
                          stat.S_IMODE(before.st_mode) == expected['mode'] and
                          stream.read(4) == b'\x7fELF' and
                          'security.capability' not in os.listxattr(stream.fileno()) and
                          os.getxattr(stream.fileno(), 'security.selinux').rstrip(b'\0').decode('ascii') ==
                          expected['label'], 'kiosk-password:executable-metadata')
            stream.seek(0)
            record = dict(expected, uid=0, gid=0,
                          sha256=hashlib.file_digest(stream, 'sha256').hexdigest())
            after = os.fstat(stream.fileno())
            guest.require(all(getattr(before, field) == getattr(after, field) for field in
                          ('st_dev', 'st_ino', 'st_size', 'st_mode', 'st_uid', 'st_gid',
                           'st_mtime_ns', 'st_ctime_ns')), 'kiosk-password:executable-changed')
        manifest = json.loads((Path('/run/oh-no-parent-control-confinement') /
                               generation.strip() / 'records.json').read_text())
        guest.require(manifest.get('preserved') == [record], 'kiosk-password:generation-inventory')
        for target in (*threads, manager):
            visible = (target / 'root' / path.lstrip('/')).stat()
            mounts = [line.split() for line in (target / 'mountinfo').read_text().splitlines()
                      if line.split()[4] == path]
            guest.require((visible.st_dev, visible.st_ino) == (before.st_dev, before.st_ino) and
                          len(mounts) == 1 and 'ro' in mounts[0][5].split(','),
                          'kiosk-password:unpinned-executable')
        for thread in threads:
            actual = (thread / 'exe').stat()
            guest.require((actual.st_dev, actual.st_ino) == (before.st_dev, before.st_ino) and
                          (thread / 'attr/current').read_text().strip().rstrip('\0') ==
                          'system_u:system_r:policykit_auth_t:s0' and
                          os.readlink(thread / 'ns/mnt') == namespace and
                          (thread / 'root' / marker).read_text() == generation,
                          'kiosk-password:helper-lifecycle-changed')
        guest.require(set((parent / 'task').iterdir()) == set(parent_threads) and
                      all(process_identity(thread) == value for thread, value in parent_threads.items()) and
                      process_identity(parent) == parent_identity and not exited(parent_fd) and
                      all(os.readlink(thread / 'ns/mnt') == namespace and
                          confined_thread_roles(thread, config, 'selinux', generation, host_namespace) ==
                          ['onpc_kiosk_polkit_t'] for thread in parent_threads) and
                      ((parent / 'exe').stat().st_dev, (parent / 'exe').stat().st_ino) ==
                      (parent_exe.st_dev, parent_exe.st_ino),
                      'kiosk-password:parent-lifecycle-changed')
    finally:
        os.close(parent_fd)


def user_command(account, command, *, check=True):
    return guest.commands.run(
        ['/usr/bin/setpriv', '--reuid', str(account.pw_uid), '--regid', str(account.pw_gid),
         '--clear-groups', '/usr/bin/env', '-i', *ENV,
         f'XDG_RUNTIME_DIR=/run/user/{account.pw_uid}',
         f'DBUS_SESSION_BUS_ADDRESS=unix:path=/run/user/{account.pw_uid}/bus', *command],
        check=check, timeout=45, merge_stderr=False)


def service_target(manager, command):
    """Measure the actual namespace object, and refuse absent native loaders."""
    canonical = Path(command).resolve(strict=True)
    visible = manager / 'root' / canonical.relative_to('/')
    info = visible.stat()
    guest.require(stat.S_ISREG(info.st_mode) and info.st_mode & 0o111,
                  'kiosk-service:target-not-executable')
    with visible.open('rb') as stream:
        header = stream.read(64)
        if header.startswith(b'#!'):
            loader = header[2:].splitlines()[0].split()[0].decode()
        else:
            guest.require(header[:6] == b'\x7fELF\x02\x01', 'kiosk-service:target-format')
            offset = struct.unpack_from('<Q', header, 32)[0]
            size, count = struct.unpack_from('<HH', header, 54)
            guest.require(size == 56 and 0 < count <= 256, 'kiosk-service:elf-headers')
            loader = None
            for index in range(count):
                stream.seek(offset + index * size)
                program = stream.read(size)
                guest.require(len(program) == size, 'kiosk-service:elf-header-missing')
                if struct.unpack_from('<I', program)[0] == 3:  # PT_INTERP
                    start, length = struct.unpack_from('<Q', program, 8)[0], struct.unpack_from('<Q', program, 32)[0]
                    guest.require(1 < length <= 4096, 'kiosk-service:elf-loader-size')
                    stream.seek(start)
                    value = stream.read(length)
                    guest.require(len(value) == length and value.endswith(b'\0'),
                                  'kiosk-service:elf-loader-missing')
                    loader = value[:-1].decode()
                    break
    result = {'path': str(canonical), 'device': info.st_dev, 'inode': info.st_ino,
              'sha256': guest.sha(visible)}
    guest.require(result['sha256'] == guest.sha(canonical), 'kiosk-service:control-target-drift')
    entry = Path(command).lstat()
    result['entry'] = {'device': entry.st_dev, 'inode': entry.st_ino, 'mode': entry.st_mode,
                       'uid': entry.st_uid, 'gid': entry.st_gid}
    if stat.S_ISLNK(entry.st_mode):
        result['entry']['link'] = os.readlink(command)
    # Btrfs stat() reports a per-subvolume anonymous device, whereas AVCs
    # identify the backing superblock. Use the actual containing namespace
    # mount, including any more specific file bind, rather than st_dev lookup.
    mounts = []
    for line in (manager / 'mountinfo').read_text().splitlines():
        left, right = line.split(' - ', 1)
        mountpoint = Path(re.sub(r'\\([0-7]{3})', lambda match: chr(int(match[1], 8)), left.split()[4]))
        if canonical.is_relative_to(mountpoint):
            mounts.append((len(mountpoint.parts), right.split(), line))
    depth = max((item[0] for item in mounts), default=-1)
    containing = [item for item in mounts if item[0] == depth]
    guest.require(len(containing) == 1, 'kiosk-service:target-filesystem')
    _, mount, result['mount'] = containing[0]
    fields = result['mount'].split(' - ', 1)[0].split()
    unescape = lambda value: re.sub(r'\\([0-7]{3})', lambda match: chr(int(match[1], 8)), value)
    result['audit_name'] = (Path(unescape(fields[3])).name
                            if canonical == Path(unescape(fields[4])) else canonical.name)
    if mount[0] == 'tmpfs':
        result['audit_device'] = 'tmpfs'
    else:
        source = Path(mount[1]).resolve(strict=True)
        device = source.stat()
        guest.require(stat.S_ISBLK(device.st_mode), 'kiosk-service:target-block-device')
        block = Path('/sys/dev/block') / f'{os.major(device.st_rdev)}:{os.minor(device.st_rdev)}' / 'uevent'
        values = dict(line.split('=', 1) for line in block.read_text().splitlines())
        result['audit_device'] = values['DEVNAME']
    if loader is not None:
        loader = Path(loader).resolve(strict=True)
        native = manager / 'root' / loader.relative_to('/')
        metadata = native.stat()
        guest.require(stat.S_ISREG(metadata.st_mode) and metadata.st_mode & 0o111,
                      'kiosk-service:loader-not-executable')
        with native.open('rb') as stream:
            guest.require(stream.read(6) == b'\x7fELF\x02\x01', 'kiosk-service:loader-format')
        result['loader'] = {'path': str(loader), 'sha256': guest.sha(native)}
        guest.require(result['loader']['sha256'] == guest.sha(loader), 'kiosk-service:control-loader-drift')
    return result


def service_audit_denial(line, backend, pid, target, uid, *, profile=False):
    """Match one native executor's enforcing operation and exact target object."""
    if not re.search(r'\bpid=' + re.escape(str(pid)) + r'\b', line):
        return False
    quoted = dict(re.findall(r'\b(apparmor|operation|profile|name|target|path|dev|denied_mask)="([^"]*)"', line))
    if backend == 'apparmor':
        if (quoted.get('apparmor'), quoted.get('profile')) != ('DENIED', 'onpc-kiosk-manager'):
            return False
        if profile:
            return all(quoted.get(key) == value for key, value in {
                'operation': 'change_onexec', 'name': 'unconfined', 'target': 'unconfined'}.items())
        owners = dict(re.findall(r'\b(fsuid|ouid)=([0-9]+)\b', line))
        return (quoted.get('operation') == 'exec' and quoted.get('name') == target['path'] and
                quoted.get('denied_mask') == 'x' and owners.get('fsuid') == str(uid))
    if backend != 'selinux' or 'avc:  denied' not in line:
        return False
    fields = dict(re.findall(r'\b(scontext|tcontext|tclass|permissive|ino)=([^\s]+)', line))
    if fields.get('scontext') != MANAGER_SID or fields.get('permissive') != '0':
        return False
    if profile:
        return (re.search(r'\{\s*setexec\s*\}', line) is not None and
                fields.get('tcontext') == MANAGER_SID and fields.get('tclass') == 'process')
    return (re.search(r'\{\s*(?:execute|execute_no_trans)\s*\}', line) is not None and
            fields.get('tclass') == 'file' and fields.get('ino') == str(target['inode']) and
            ('path' not in quoted or quoted['path'] == target['path']) and
            quoted.get('name') == target['audit_name'] and
            quoted.get('dev') == target['audit_device'])


def service_native_denial(row, account, unit, invocation, pid, command, stage, boot, started):
    expected = {'MESSAGE_ID': '641257651c1b4ec9a8624d7a40a9e1e7',
                'CODE_FILE': 'src/core/executor.c', 'USER_UNIT': unit,
                'USER_INVOCATION_ID': invocation, '_PID': str(pid),
                '_UID': str(account.pw_uid), '_BOOT_ID': boot, 'EXECUTABLE': command[0]}
    if not all(row.get(key) == value for key, value in expected.items()):
        return False
    if any(key in row and row[key] != value for key, value in {
            '_SYSTEMD_USER_UNIT': unit, '_SYSTEMD_INVOCATION_ID': invocation}.items()):
        return False
    error = row.get('ERRNO')
    return (error in ('1', '13') and str(row.get('__REALTIME_TIMESTAMP', '')).isdigit() and
            int(row['__REALTIME_TIMESTAMP']) >= started * 1_000_000 and
            row.get('MESSAGE') == f'{unit}: Failed at step {stage} spawning {command[0]}: ' +
            ('Permission denied' if error == '13' else 'Operation not permitted'))


def require_service_denial(account, backend, unit, command, record, *, setting=None, writable=False):
    """Keep native/unit identity until its independent fresh kernel proof is saved."""
    from system_kiosk_platform import kernel_audit, settle_kernel_audit, wait_for
    manager_unit = f'user@{account.pw_uid}.service'
    manager = PROC / str(manager_pid(manager_unit))
    identity = process_identity(manager)
    manager_invocation = guest.run(['systemctl', 'show', '--value', '--property=InvocationID', manager_unit])
    target = service_target(manager, command[0])
    before_unit = user_command(account, ['/usr/bin/systemctl', '--user', 'show', unit,
        '--property=InvocationID,ActiveState'], check=False).decode()
    guest.require('InvocationID=\n' in before_unit and 'ActiveState=inactive\n' in before_unit,
                  'kiosk-service:unit-already-active')
    strict = setting is not None and '=-' not in setting
    stage = ('APPARMOR' if backend == 'apparmor' else 'SELINUX_CONTEXT') if strict else 'EXEC'
    status = (231 if backend == 'apparmor' else 229) if strict else 203
    settle_kernel_audit(backend)
    before = set(kernel_audit(backend).splitlines())
    cursor = guest.run(['journalctl', '-b', '-n', '0', '--show-cursor', '--no-pager', '-o', 'cat'])
    guest.require(cursor.startswith('-- cursor: ') and '\n' not in cursor, 'kiosk-service:journal-cursor')
    boot = Path('/proc/sys/kernel/random/boot_id').read_text().strip().replace('-', '')
    started = time.time()
    if writable:
        launch = ['/usr/bin/systemctl', '--user', 'start', unit]
    else:
        launch = ['/usr/bin/systemd-run', '--user', '--wait', '--pipe', '--unit=' + unit]
        if setting is not None:
            launch.append('--property=' + setting)
        launch.extend(command)
    output = user_command(account, launch, check=False)
    actual = guest.commands.last_returncode
    properties = dict(line.split('=', 1) for line in user_command(account,
        ['/usr/bin/systemctl', '--user', 'show', unit,
         '--property=InvocationID,ExecMainPID,ExecMainCode,ExecMainStatus,ExecStart,Result,ActiveState']).decode().splitlines())
    record_key = 'onpc.kiosk.service-denial.' + unit
    record(record_key + '.request', json.dumps({'command': command, 'setting': setting,
        'target': target, 'manager_pid': manager.name, 'manager_identity': identity,
        'manager_invocation': manager_invocation, 'unit': properties,
        'returncode': actual, 'stdout': output.decode(errors='replace')}, sort_keys=True))
    invocation = properties.get('InvocationID', '')
    guest.require(re.fullmatch(r'[a-f0-9]{32}', invocation) is not None,
                  'kiosk-service:invocation-missing')
    try:
        pid = properties.get('ExecMainPID', '')
        guest.require(re.fullmatch(r'[1-9][0-9]*', pid) is not None and
                      properties.get('ExecMainCode') == '1' and properties.get('ExecMainStatus') == str(status) and
                      properties.get('Result') == 'exit-code' and properties.get('ActiveState') == 'failed' and
                      (writable or actual == status), 'kiosk-service:native-status')
        guest.require(properties.get('ExecStart', '').startswith('{ path=' + command[0] + ' ; ') and
                      ' ; pid=' + pid + ' ; ' in properties['ExecStart'], 'kiosk-service:executor-target')

        native_rows = ''

        def native():
            nonlocal native_rows
            rows = guest.run(['journalctl', '-b', 'USER_UNIT=' + unit,
                'MESSAGE_ID=641257651c1b4ec9a8624d7a40a9e1e7',
                '--after-cursor=' + cursor.removeprefix('-- cursor: '), '-n', '20', '--no-pager', '-o', 'json'])
            native_rows = rows
            return any(service_native_denial(json.loads(line), account, unit, invocation,
                       pid, command, stage, boot, started) for line in rows.splitlines())

        try:
            wait_for(native, 'kiosk-service:native-denial-not-observed')
        finally:
            record(record_key + '.native-diagnostics', native_rows)

        kernel_rows = []
        def enforcing():
            nonlocal kernel_rows
            kernel_rows = [line for line in kernel_audit(backend).splitlines()
                if line not in before and re.search(r'\bpid=' + re.escape(pid) + r'\b', line)]
            for line in kernel_rows:
                event = re.search(r'\baudit\(([0-9]+(?:\.[0-9]+)?):[0-9]+\)', line)
                if (line not in before and event and float(event[1]) >= started and
                        service_audit_denial(line, backend, pid, target, account.pw_uid, profile=strict)):
                    record(record_key + '.kernel-denial', line)
                    return True
            return False

        try:
            wait_for(enforcing, 'kiosk-service:kernel-denial-not-observed')
        finally:
            record(record_key + '.kernel-observations', json.dumps(kernel_rows))
        guest.require(process_identity(manager) == identity and
                      guest.run(['systemctl', 'show', '--value', '--property=InvocationID', manager_unit]) ==
                      manager_invocation, 'kiosk-service:manager-changed')
        guest.require(service_target(manager, command[0]) == target, 'kiosk-service:target-changed')
    finally:
        current = user_command(account, ['/usr/bin/systemctl', '--user', 'show', unit,
            '--value', '--property=InvocationID']).decode().strip()
        guest.require(current == invocation, 'kiosk-service:unit-replaced')
        user_command(account, ['/usr/bin/systemctl', '--user', 'reset-failed', unit])
        record(record_key + '.owned-unit-reset', True)


def caller_identity(service):
    guest.require(service in ('gdm-password', 'systemd-user'),
                  'kiosk-confinement:unsupported-pam-caller')
    role = 'xdm' if service == 'gdm-password' else 'init'
    return f'system_u:system_r:{role}_t:s0', role + '_exec_t'


@contextmanager
def pam_caller_command(directory, service, *, expected_selinux='Enforcing'):
    """Run an engineering PAM worker in its real Fedora caller domain."""
    guest.guard(expected_selinux=expected_selinux)
    context, executable_type = caller_identity(service)
    with tempfile.TemporaryDirectory(prefix='pam-caller-', dir=directory) as temporary:
        caller = Path(temporary) / 'caller'
        shutil.copyfile(Path('/usr/bin/python3').resolve(), caller)
        caller.chmod(0o700)
        guest.run(['/usr/bin/chcon', '-t', executable_type, str(caller)])
        yield ['/usr/bin/runcon', context, str(caller), '-B']


def bootstrap_logger_endpoint(path):
    """Pin the public logging endpoint separately from a client's socket FD."""
    def identity(info):
        return [info.st_dev, info.st_ino, info.st_mode, info.st_uid, info.st_gid, info.st_nlink]
    entry = path.lstat()
    resolved = path.resolve(strict=True)
    info = resolved.stat()
    guest.require(stat.S_ISSOCK(info.st_mode), 'kiosk-bootstrap:logger-endpoint-type')
    return {'path': str(path), 'resolved': str(resolved), 'entry': identity(entry),
            'identity': identity(info)}


def bootstrap_logger_descriptor(fd):
    """Observe the one known logger without opening proc after final PAM MAC."""
    before = os.fstat(fd)
    status = fcntl.fcntl(fd, fcntl.F_GETFL)
    flags = fcntl.fcntl(fd, fcntl.F_GETFD)
    after = os.fstat(fd)
    guest.require(stat.S_ISSOCK(before.st_mode) and
                  (before.st_dev, before.st_ino, before.st_mode) ==
                  (after.st_dev, after.st_ino, after.st_mode),
                  'kiosk-bootstrap:logger-descriptor-flags')
    return [before.st_dev, before.st_ino, before.st_mode,
            status | (os.O_CLOEXEC if flags & fcntl.FD_CLOEXEC else 0),
            f'socket:[{before.st_ino}]']


def bootstrap_logger_socket(fd, endpoint):
    """Inspect only an owned CLOEXEC duplicate; never close the caller's FD."""
    descriptor = bootstrap_logger_descriptor(fd)
    duplicate = fcntl.fcntl(fd, fcntl.F_DUPFD_CLOEXEC, 3)
    connection = None
    try:
        guest.require(socket.getdefaulttimeout() is None, 'kiosk-bootstrap:logger-socket-timeout')
        connection = socket.socket(fileno=duplicate)
        if connection.family != socket.AF_UNIX:
            return None
        kind = connection.getsockopt(socket.SOL_SOCKET, socket.SO_TYPE)
        if kind not in (socket.SOCK_DGRAM, socket.SOCK_STREAM):
            return None
        try:
            peer = connection.getpeername()
        except OSError as error:
            if error.errno == errno.ENOTCONN:
                return None
            raise
        if not isinstance(peer, str) or not peer.startswith('/') or len(os.fsencode(peer)) > 108:
            return None
        try:
            peer_path = Path(peer).resolve(strict=True)
        except FileNotFoundError:
            return None
        if str(peer_path) != endpoint['resolved']:
            return None
        pinned = os.fstat(duplicate)
        guest.require(descriptor[3] & os.O_CLOEXEC and
                      [pinned.st_dev, pinned.st_ino, pinned.st_mode] == descriptor[:3] and
                      bootstrap_logger_descriptor(fd) == descriptor,
                      'kiosk-bootstrap:logger-probe-identity-changed')
        return {'fd': fd, 'socket_type': kind, 'peer': peer, 'endpoint': endpoint,
                'descriptor': descriptor}
    finally:
        if connection is not None:
            connection.close()
        else:
            os.close(duplicate)


def bootstrap_logger_prepare(path=Path('/dev/log')):
    """Eagerly establish libc's real retained logger before the PAM baseline."""
    endpoint = bootstrap_logger_endpoint(path)
    before = bootstrap_descriptors(PROC / 'self')
    guest.require(len(before) <= 128, 'kiosk-bootstrap:logger-descriptor-bound')
    library = ctypes.CDLL(None, use_errno=True)
    library.openlog.argtypes = [ctypes.c_char_p, ctypes.c_int, ctypes.c_int]
    library.openlog.restype = None
    # NULL leaves libc's stable program identity in place; libc retains an
    # ident pointer, so a temporary ctypes string must not be supplied here.
    library.openlog(None, 0x08, 10 << 3)  # LOG_NDELAY, LOG_AUTHPRIV.
    after = bootstrap_descriptors(PROC / 'self')
    guest.require(len(after) <= 128 and all(after.get(fd) == value for fd, value in before.items()),
                  'kiosk-bootstrap:logger-changed-caller-descriptor')
    candidates = []
    for fd, value in after.items():
        if stat.S_ISSOCK(value[2]):
            receipt = bootstrap_logger_socket(int(fd), endpoint)
            if receipt is not None:
                guest.require(receipt['descriptor'] == value, 'kiosk-bootstrap:logger-proc-identity')
                candidates.append(receipt)
    guest.require(len(candidates) == 1, 'kiosk-bootstrap:logger-connected-socket-missing-or-ambiguous')
    receipt = candidates[0]
    added = set(after) - set(before)
    guest.require(added in (set(), {str(receipt['fd'])}) and
                  bootstrap_logger_endpoint(path) == endpoint, 'kiosk-bootstrap:logger-setup-drift')
    receipt['introduced'] = str(receipt['fd']) in added
    return receipt


def bootstrap_logger_validate(receipt, before, *, path=Path('/dev/log')):
    """Bind the child's actual socket probe to the independent parent census."""
    guest.require(isinstance(receipt, dict) and set(receipt) == {
        'fd', 'socket_type', 'peer', 'endpoint', 'descriptor', 'introduced'} and
        type(receipt['fd']) is int and receipt['fd'] > 2 and
        type(receipt['socket_type']) is int and
        type(receipt['introduced']) is bool and
        receipt['socket_type'] in (socket.SOCK_DGRAM, socket.SOCK_STREAM) and
        isinstance(receipt['peer'], str) and receipt['peer'].startswith('/') and
        len(os.fsencode(receipt['peer'])) <= 108,
        'kiosk-bootstrap:logger-receipt')
    endpoint = bootstrap_logger_endpoint(path)
    value = before.get(str(receipt['fd']))
    guest.require(receipt['endpoint'] == endpoint, 'kiosk-bootstrap:logger-endpoint-changed')
    guest.require(str(Path(receipt['peer']).resolve(strict=True)) == endpoint['resolved'],
                  'kiosk-bootstrap:logger-peer-changed')
    guest.require(isinstance(value, list) and len(value) == 5 and value == receipt['descriptor'] and
                  stat.S_ISSOCK(value[2]) and value[3] & os.O_CLOEXEC,
                  'kiosk-bootstrap:logger-descriptor-changed')


def bootstrap_logger_after(receipt):
    """Retain a bounded post-PAM proof or error for only this fixture's FD."""
    try:
        observed = bootstrap_logger_socket(receipt['fd'], receipt['endpoint'])
        guest.require(observed is not None, 'kiosk-bootstrap:logger-post-pam-not-connected')
        observed['introduced'] = receipt['introduced']
        return observed
    except (OSError, guest.GuestError) as error:
        return {'error': {'type': type(error).__name__,
                          'errno': error.errno if isinstance(error, OSError) else None,
                          'category': str(error)[:128] if isinstance(error, guest.GuestError) else 'socket-probe'}}


def bootstrap_logger_transition(original, current, before, after, *, path=Path('/dev/log')):
    """Only a fixture-created logger may renew its same independently proved FD."""
    bootstrap_logger_validate(original, before, path=path)
    guest.require(isinstance(current, dict) and 'error' not in current,
                  'kiosk-bootstrap:logger-post-pam-probe')
    bootstrap_logger_validate(current, after, path=path)
    guest.require(all(original[key] == current[key] for key in
                      ('fd', 'socket_type', 'peer', 'endpoint', 'introduced')) and
                  original['descriptor'][0] == current['descriptor'][0] and
                  original['descriptor'][2:4] == current['descriptor'][2:4],
                  'kiosk-bootstrap:logger-resource-changed')
    logger_fd = str(original['fd'])
    for fd, value in before.items():
        expected = current['descriptor'] if original['introduced'] and fd == logger_fd else value
        guest.require(after.get(fd) == expected, 'kiosk-bootstrap:caller-descriptor-changed')
    extra = {fd: value for fd, value in after.items() if fd not in before}
    guest.require(len(extra) == 1 and all(value[4] ==
        '/run/oh-no-parent-control-kiosk-admission.lock' and value[3] & os.O_CLOEXEC
        for value in extra.values()), 'kiosk-bootstrap:setup-descriptor-leak')


def first_exec(account, directory, command, *, fd_mode=None, service='gdm-password', armed=True,
               expected_selinux='Enforcing', witness=None):
    """A real PAM final-session call followed by the caller's actual exec.

    Root Python is only the engineering harness: it is already running before
    the tested boundary. No interpreter entry is added to production policy.
    """
    backend = json.loads(Path('/usr/share/oh-no-parent-control/confinement/config.json').read_text())['backend']
    module = next(path for path in (
        Path('/usr/lib/x86_64-linux-gnu/security/pam_oh_no_parent_control.so'),
        Path('/usr/lib64/security/pam_oh_no_parent_control.so')) if path.is_file())
    fixture = directory / service
    contents = f'session required {module} kiosk-confinement\n'
    if backend == 'selinux':
        context, _ = caller_identity(service)
        if Path('/proc/self/attr/current').read_text().strip().rstrip('\0') != context:
            # init_t may read the prepared PAM input, but cannot create a
            # user_tmp_t file. Prepare scenario data before entering the real
            # caller domain; never add a production permission for the fixture.
            fixture.write_text(contents)
            # Enter the vendor's real PAM caller domain before opening PAM.
            # In particular, unconfined_t lacks nosuid_transition on the private
            # /usr view. Adding that permission would test a different boundary.
            # The root-private interpreter copy is only a scenario fixture with
            # a vendor entrypoint label; production policy remains unchanged.
            with pam_caller_command(directory, service,
                                    expected_selinux=expected_selinux) as caller:
                # init_t cannot write the harness's user_tmp_t capture files.
                # Inherited pipes carry the bounded result and diagnostics without a
                # production permission or a differently labelled fixture file.
                with ExitStack() as channels:
                    result_read, result_write = os.pipe2(os.O_CLOEXEC | os.O_NONBLOCK)
                    channels.callback(os.close, result_read)
                    channels.callback(os.close, result_write)
                    diagnostic_read, diagnostic_write = os.pipe2(os.O_CLOEXEC | os.O_NONBLOCK)
                    channels.callback(os.close, diagnostic_read)
                    channels.callback(os.close, diagnostic_write)
                    request_data = {'command': command, 'directory': str(directory),
                        'fd_mode': fd_mode, 'service': service, 'armed': armed,
                        'result_fd': result_write, 'diagnostic_fd': diagnostic_write,
                        'expected_selinux': expected_selinux}
                    if witness:
                        request_data['witness'] = witness
                    request = json.dumps(request_data)
                    try:
                        guest.commands.run([*caller,
                            str(Path(__file__).resolve()), 'first-exec', request], timeout=180 if witness else 90,
                            merge_stderr=False, pass_fds=(result_write, diagnostic_write,
                                *(witness.values() if witness else ())))
                    finally:
                        # Nonblocking writes cannot deadlock a full pipe while
                        # Commands owns the bounded child wait. Read only this
                        # finite channel, including after a command failure.
                        diagnostic = bytearray()
                        while len(diagnostic) <= 65536:
                            try:
                                chunk = os.read(diagnostic_read, 65537 - len(diagnostic))
                            except BlockingIOError:
                                break
                            if not chunk:
                                break
                            diagnostic.extend(chunk)
                        guest.require(len(diagnostic) <= 65536,
                                      'kiosk-confinement:caller-diagnostic-size')
                        pending = memoryview(diagnostic)
                        while pending:
                            pending = pending[os.write(2, pending):]
                    try:
                        last = os.read(result_read, 4097)
                    except BlockingIOError:
                        last = b''
                guest.require(last.startswith(b'onpc-first-exec:'),
                              'kiosk-confinement:caller-result-missing')
                guest.require(len(last) <= 4096, 'kiosk-confinement:caller-result-size')
                result = json.loads(last.removeprefix(b'onpc-first-exec:'))
                guest.require(set(result) == {'status', 'data'} and type(result['status']) is int
                              and isinstance(result['data'], str),
                              'kiosk-confinement:caller-result-invalid')
                return result['status'], bytes.fromhex(result['data'])
        guest.require(fixture.read_text() == contents, 'kiosk-confinement:caller-pam-fixture')
    else:
        fixture.write_text(contents)
    pam = ctypes.CDLL('libpam.so.0')
    class Conversation(ctypes.Structure):
        _fields_ = [('conv', ctypes.c_void_p), ('data', ctypes.c_void_p)]
    pam.pam_start_confdir.argtypes = [ctypes.c_char_p, ctypes.c_char_p,
        ctypes.POINTER(Conversation), ctypes.c_char_p, ctypes.POINTER(ctypes.c_void_p)]
    pam.pam_open_session.argtypes = [ctypes.c_void_p, ctypes.c_int]
    read_fd, write_fd = os.pipe2(os.O_CLOEXEC)
    try:
        child = os.fork()
    except BaseException:
        os.close(read_fd)
        os.close(write_fd)
        raise
    if child == 0:
        os.close(read_fd)
        try:
            if witness:
                for fd in witness.values():
                    os.set_inheritable(fd, False)
                host_namespace = os.open('/proc/self/ns/mnt', os.O_RDONLY | os.O_CLOEXEC)
                logger = bootstrap_logger_prepare()
                before = bootstrap_descriptors(PROC / 'self')
            target = command[0]
            descriptor = None
            if fd_mode == 'file':
                descriptor = os.open(target, os.O_RDONLY)
            elif fd_mode == 'memfd':
                descriptor = os.memfd_create('onpc-confinement-probe', os.MFD_CLOEXEC)
                os.write(descriptor, Path(target).read_bytes())
            handle = ctypes.c_void_p()
            conv = Conversation()
            status = pam.pam_start_confdir(service.encode(), account.pw_name.encode(),
                ctypes.byref(conv), os.fsencode(directory), ctypes.byref(handle))
            if status == 0:
                status = pam.pam_open_session(handle, 0)
            if status:
                os.write(write_fd, json.dumps({'pam': status}).encode())
                os._exit(125)
            if witness:
                event = {'phase': 'admitted', 'pid': os.getpid(),
                         'before': before, 'logger': logger, 'logger_after': bootstrap_logger_after(logger)}
                encoded = (json.dumps(event, sort_keys=True) + '\n').encode()
                guest.require(len(encoded) <= 4096 and
                              os.write(witness['events'], encoded) == len(encoded),
                              'kiosk-bootstrap:admission-event')
                poll = select.poll()
                poll.register(witness['release'], select.POLLIN | select.POLLHUP)
                guest.require(poll.poll(75000) and os.read(witness['release'], 1) == b'E',
                              'kiosk-bootstrap:release-timeout')
                os.dup2(witness['output'], 1)
            os.setgroups([])
            os.setgid(account.pw_gid)
            os.setuid(account.pw_uid)
            if witness and service == 'systemd-user':
                restrictions = bootstrap_restrictions(host_namespace, command[0])
                encoded = (json.dumps({'phase': 'restrictions', 'result': restrictions}, sort_keys=True) + '\n').encode()
                guest.require(len(encoded) <= 4096 and os.write(witness['events'], encoded) == len(encoded),
                              'kiosk-bootstrap:restrictions-event')
            if witness:
                os.close(host_namespace)
            os.write(write_fd, b'armed\n')
            try:
                os.execve(descriptor if descriptor is not None else target, command,
                          {'PATH': '/usr/bin:/bin', 'LANG': 'C'})
            except OSError as error:
                os.write(write_fd, json.dumps({'exec_errno': error.errno}).encode())
                os._exit(126)
        except BaseException as error:
            if witness:
                detail = {'stage': 'first-exec-witness', 'type': type(error).__name__,
                          'errno': error.errno if isinstance(error, OSError) else None,
                          'category': str(error) if isinstance(error, guest.GuestError) else 'fixture-failure'}
                os.write(2, (json.dumps(detail, sort_keys=True) + '\n').encode())
            os._exit(124)
    os.close(write_fd)
    return wait_first_exec(child, read_fd, armed=armed, **({'timeout_ms': 180000} if witness else {}))


def wait_first_exec(child, read_fd, *, armed, timeout_ms=75000):
    """Own the unreaped fork child even if pidfd acquisition fails."""
    pidfd = None
    reaped = False
    try:
        pidfd = os.pidfd_open(child)
        poll = select.poll()
        poll.register(pidfd, select.POLLIN)
        if not poll.poll(timeout_ms):
            raise AssertionError('confinement probe timed out')
        _, status = os.waitpid(child, 0)
        reaped = True
        data = os.read(read_fd, 4096)
        guest.require(data.startswith(b'armed\n') == armed, 'kiosk-confinement:unexpected-pam-admission')
        return os.waitstatus_to_exitcode(status), data.removeprefix(b'armed\n')
    finally:
        if not reaped:
            try:
                if pidfd is None:
                    # This direct child is still unreaped, so its PID cannot
                    # be recycled. No process discovery establishes ownership.
                    os.kill(child, signal.SIGKILL)
                else:
                    signal.pidfd_send_signal(pidfd, signal.SIGKILL)
            except ProcessLookupError:
                pass
            os.waitpid(child, 0)
        if pidfd is not None:
            os.close(pidfd)
        os.close(read_fd)


def manager_pid(unit):
    return int(guest.run(['systemctl', 'show', '--value', '--property=MainPID', unit]))


def lifecycle_label(backend):
    attribute = 'attr/apparmor/current' if backend == 'apparmor' else 'attr/current'
    return Path('/proc/self', attribute).read_text().strip().rstrip('\0')


def lifecycle_denials():
    """Fork only owned denial probes from the surviving PAM lifecycle domain."""
    for command in (['/bin/sh', '-c', 'exit 0'], ['/usr/bin/python3', '-c', 'pass']):
        read_fd, write_fd = os.pipe2(os.O_CLOEXEC)
        try:
            child = os.fork()
        except BaseException:
            os.close(read_fd)
            os.close(write_fd)
            raise
        if child == 0:
            os.close(read_fd)
            try:
                os.execve(command[0], command, {'PATH': '/usr/bin:/bin', 'LANG': 'C'})
            except OSError as error:
                os.write(write_fd, json.dumps({'exec_errno': error.errno}).encode())
                os._exit(126)
            os._exit(124)
        os.close(write_fd)
        status, data = wait_first_exec(child, read_fd, armed=False)
        guest.require(status == 126 and json.loads(data).get('exec_errno') in (errno.EACCES, errno.EPERM),
                      'kiosk-lifecycle:exec-not-denied')


def lifecycle_teardown(pam, handle, backend, expected):
    """The real close/delete/end callbacks retain the non-exec child's label."""
    stages = []
    for stage, callback, flags in (
        ('parent-exited', None, 0),
        ('close-session', pam.pam_close_session, 0),
        ('delete-credentials', pam.pam_setcred, 4),
        # systemd marks child pam_end cleanup with PAM_DATA_SILENT.
        ('end', pam.pam_end, 0x40000000),
    ):
        status = None if callback is None else callback(handle, flags)
        # systemd continues teardown even when a provider reports failure.
        # Retain every status and prove the boundary after each callback;
        # the observer separately refuses incomplete teardown acceptance.
        guest.require(lifecycle_label(backend) == expected, 'kiosk-lifecycle:label-' + stage)
        lifecycle_denials()
        stages.append({'stage': stage, 'pam_status': status})
    return stages


def lifecycle_executor(request):
    """Trusted engineering executor; never an admitted production entrypoint.

    Follow systemd's setup_pam ordering using the installed systemd-user stack,
    including its actual vendor teardown callbacks. Only this initial executor
    enters init_t; its non-exec lifecycle child must inherit manager-pam.
    """
    backend = request['backend']
    for name in ('executor_release', 'helper_release', 'events'):
        os.set_inheritable(request[name], False)
    expected = ('onpc-kiosk-manager (enforce)' if backend == 'apparmor'
                else 'system_u:system_r:onpc_kiosk_manager_pam_t:s0')
    account = pwd.getpwnam('oh-no-parent-control')
    pam = ctypes.CDLL('libpam.so.0')
    class Conversation(ctypes.Structure):
        _fields_ = [('conv', ctypes.c_void_p), ('data', ctypes.c_void_p)]
    pam.pam_start.argtypes = [ctypes.c_char_p, ctypes.c_char_p,
                             ctypes.POINTER(Conversation), ctypes.POINTER(ctypes.c_void_p)]
    for name in ('pam_acct_mgmt', 'pam_setcred', 'pam_open_session', 'pam_close_session', 'pam_end'):
        getattr(pam, name).argtypes = [ctypes.c_void_p, ctypes.c_int]
    handle = ctypes.c_void_p()
    conversation = Conversation()
    guest.require(pam.pam_start(b'systemd-user', account.pw_name.encode(),
        ctypes.byref(conversation), ctypes.byref(handle)) == 0, 'kiosk-lifecycle:pam-start')
    guest.require(pam.pam_acct_mgmt(handle, 0) == 0, 'kiosk-lifecycle:pam-account')
    # Retain even failed establishment so the observer can prove all subsequent
    # boundaries before refusing qualification. The owned kiosk credential route
    # must succeed rather than consume the global "other" fallback.
    establish_status = pam.pam_setcred(handle, 2)
    guest.require(pam.pam_open_session(handle, 0) == 0, 'kiosk-lifecycle:pam-open')
    guest.require(lifecycle_label(backend) == expected, 'kiosk-lifecycle:executor-label')
    child = os.fork()
    if child == 0:
        os.close(request['executor_release'])
        try:
            os.setgroups([])
            os.setgid(account.pw_gid)
            os.setuid(account.pw_uid)
            parent = os.getppid()
            os.write(request['events'], (json.dumps({'phase': 'ready', 'pid': os.getpid(),
                'parent': parent}) + '\n').encode())
            guest.require(os.read(request['helper_release'], 1) == b'T', 'kiosk-lifecycle:helper-release')
            guest.require(os.getppid() != parent, 'kiosk-lifecycle:parent-still-alive')
            stages = lifecycle_teardown(pam, handle, backend, expected)
            os.write(request['events'], (json.dumps({'phase': 'finished', 'stages': stages,
                'establish_status': establish_status}) + '\n').encode())
            os._exit(0)
        except BaseException:
            os._exit(124)
    os.close(request['helper_release'])
    try:
        guest.require(os.read(request['executor_release'], 1) == b'E', 'kiosk-lifecycle:executor-release')
        os.setgroups([])
        os.setgid(account.pw_gid)
        os.setuid(account.pw_uid)
        os.execve('/usr/lib/systemd/systemd', ['/usr/lib/systemd/systemd', '--version'],
                  {'PATH': '/usr/bin:/bin', 'LANG': 'C'})
    except BaseException:
        # The direct unreaped child cannot have a recycled PID. EOF on the
        # observer's helper channel also lets it exit if this executor fails.
        os.kill(child, signal.SIGKILL)
        os.waitpid(child, 0)
        raise


def lifecycle_event(fd):
    """Read one bounded atomic event without allowing a lost worker to hang."""
    poll = select.poll()
    poll.register(fd, select.POLLIN | select.POLLHUP)
    deadline = time.monotonic() + 75
    data = bytearray()
    while not data.endswith(b'\n'):
        remaining = max(0, int((deadline - time.monotonic()) * 1000))
        guest.require(remaining > 0 and poll.poll(remaining), 'kiosk-lifecycle:event-timeout')
        part = os.read(fd, 1)
        guest.require(bool(part), 'kiosk-lifecycle:event-missing')
        data.extend(part)
        guest.require(len(data) <= 4096, 'kiosk-lifecycle:event-size')
    return json.loads(data)


def lifecycle_wait(pid, pidfd):
    poll = select.poll()
    poll.register(pidfd, select.POLLIN)
    guest.require(bool(poll.poll(75000)), 'kiosk-lifecycle:worker-timeout')
    _, status = os.waitpid(pid, 0)
    return os.waitstatus_to_exitcode(status)


def lifecycle_generation_diagnostic(manager, helper, record):
    """Explain a failed equality check without changing its failure or state."""
    try:
        from system_kiosk_accounts import owned_bytes

        guest.require(all(isinstance(value, str) and
                          re.fullmatch(r'[a-f0-9]{64}\n', value) for value in (manager, helper)),
                      'kiosk-lifecycle:diagnostic-marker')
        record('onpc.kiosk.pam-lifecycle.manager-generation', manager.strip())
        record('onpc.kiosk.pam-lifecycle.helper-generation', helper.strip())
        preparation = runpy.run_path('/usr/libexec/oh-no-parent-control-kiosk-confinement')
        trusted = preparation['trusted']
        runtime = trusted(Path('/run/oh-no-parent-control-confinement'), directory=True)
        guest.require(stat.S_IMODE(runtime.stat().st_mode) == 0o700,
                      'kiosk-lifecycle:diagnostic-runtime')
        manifests = []
        for generation in (manager.strip(), helper.strip()):
            manifest = json.loads(owned_bytes(trusted(runtime / generation / 'records.json'),
                                              private=True))
            guest.require(type(manifest) is dict, 'kiosk-lifecycle:diagnostic-manifest')
            manifests.append(manifest)
        differences = {}
        for section in ('records', 'preserved', 'layout'):
            states = []
            for manifest in manifests:
                rows = manifest[section]
                guest.require(type(rows) is list and len(rows) <= 32768,
                              'kiosk-lifecycle:diagnostic-section')
                paths = {}
                for row in rows:
                    path = row.get('path') if type(row) is dict else None
                    guest.require(isinstance(path, str) and path.startswith('/usr/') and
                                  str(Path(path)) == path and '..' not in Path(path).parts and
                                  len(path) <= 4096 and not any(ord(char) < 32 for char in path) and
                                  path not in paths, 'kiosk-lifecycle:diagnostic-path')
                    paths[path] = row
                states.append(paths)
            before, after = states
            added, removed = sorted(after.keys() - before.keys()), sorted(before.keys() - after.keys())
            changed = sorted(path for path in before.keys() & after.keys() if before[path] != after[path])
            differences[section] = {
                name: {'count': len(paths), 'paths': paths[:8]}
                for name, paths in (('added', added), ('removed', removed), ('changed', changed))}
        record('onpc.kiosk.pam-lifecycle.generation-diagnostic',
               json.dumps({'status': 'compared', **differences}, sort_keys=True))
    except Exception:
        # Diagnostics and their recorder must never replace the equality
        # failure, including unsafe or unavailable runtime records.
        try:
            record('onpc.kiosk.pam-lifecycle.generation-diagnostic', '{"status":"unavailable"}')
        except Exception:
            pass


def optional_cgfs_session(backend):
    """Select only the declared Ubuntu optional profile, using the installed parser."""
    if backend != 'apparmor':
        return False
    integration = runpy.run_path('/usr/libexec/oh-no-parent-control-kiosk-confinement-integration')

    def declared(name, seen=()):
        source, ancestry = integration['included_source'](name, seen)
        found = False
        for raw, group, control, module in integration['pam_lines'](source):
            if group == '@include' or (group == 'session' and control in ('include', 'substack')):
                found = declared(module, ancestry) or found
            elif group == 'session' and control == 'optional' and module == 'pam_cgfs.so':
                logical = re.sub(r'\\[ \t]*\n', ' ', raw)
                found = (shlex.split(logical, comments=True) == [
                    'session', 'optional', 'pam_cgfs.so', '-c',
                    'freezer,memory,name=systemd']) or found
        return found

    return declared('systemd-user')


def lifecycle_cgfs_mapping(process, native_files, record):
    """Observe the native PAM load; never load a module to manufacture evidence."""
    module = Path('/usr/lib/x86_64-linux-gnu/security/pam_cgfs.so')
    # Called only for an active declared profile. A plain stack skips this
    # witness; a declared callback with missing bytes must never count as one.
    guest.require(os.path.lexists(module), 'kiosk-lifecycle:cgfs-module-missing')
    preparation = runpy.run_path('/usr/libexec/oh-no-parent-control-kiosk-confinement')
    path = preparation['trusted'](module, symlinks=True)
    measured = preparation['source_record']('library', path)
    guest.require(native_files is not None and
                  {'path': str(path), 'sha256': measured['sha256']} in native_files,
                  'kiosk-lifecycle:cgfs-native-receipt')
    before = path.stat()
    with (process / 'maps').open() as stream:
        maps = stream.read(8 * 1024 * 1024 + 1)
    guest.require(len(maps) <= 8 * 1024 * 1024, 'kiosk-lifecycle:cgfs-maps-size')
    matching = []
    for line in maps.splitlines():
        fields = line.split(maxsplit=5)
        if len(fields) != 6 or 'pam_cgfs.so' not in fields[5]:
            continue
        guest.require(fields[5] == str(path), 'kiosk-lifecycle:cgfs-mapped-path')
        device = fields[3].split(':')
        guest.require(len(device) == 2 and all(re.fullmatch(r'[0-9a-f]+', part) for part in device)
                      and fields[4].isdecimal(), 'kiosk-lifecycle:cgfs-map-format')
        guest.require((int(device[0], 16), int(device[1], 16), int(fields[4])) ==
                      (os.major(before.st_dev), os.minor(before.st_dev), before.st_ino),
                      'kiosk-lifecycle:cgfs-mapped-identity')
        matching.append(fields[1])
    guest.require(any('x' in permissions for permissions in matching),
                  'kiosk-lifecycle:cgfs-not-loaded')
    after = preparation['source_record']('library', path)
    current = path.stat()
    guest.require(after == measured and all(getattr(current, field) == getattr(before, field)
                  for field in ('st_dev', 'st_ino', 'st_size', 'st_mode', 'st_uid', 'st_gid',
                                'st_mtime_ns', 'st_ctime_ns')),
                  'kiosk-lifecycle:cgfs-module-changed')
    record('onpc.kiosk.pam-lifecycle.pam-cgfs-native-mapping', json.dumps({
        'path': str(path), 'sha256': measured['sha256'],
        'device': f'{os.major(before.st_dev):x}:{os.minor(before.st_dev):x}',
        'inode': before.st_ino}, sort_keys=True))


def verify_pam_lifecycle(account, unit, backend, directory, record, *, native_files=None):
    """Hold a real PAM child past executor exit; retain the saved user manager."""
    saved_pid = manager_pid(unit)
    saved_identity = process_identity(PROC / str(saved_pid))
    expected = ('onpc-kiosk-manager (enforce)' if backend == 'apparmor'
                else 'system_u:system_r:onpc_kiosk_manager_pam_t:s0')
    caller = directory / 'lifecycle-caller'
    shutil.copyfile(Path('/usr/bin/python3').resolve(), caller)
    caller.chmod(0o700)
    command = [str(caller), '-B', str(Path(__file__).resolve()), 'pam-lifecycle']
    if backend == 'selinux':
        context, executable_type = caller_identity('systemd-user')
        guest.run(['/usr/bin/chcon', '-t', executable_type, str(caller)])
        command = ['/usr/bin/runcon', context, *command]
    libc = ctypes.CDLL(None, use_errno=True)
    previous = ctypes.c_int()
    guest.require(libc.prctl(37, ctypes.byref(previous), 0, 0, 0) == 0, 'kiosk-lifecycle:get-subreaper')
    guest.require(libc.prctl(36, 1, 0, 0, 0) == 0, 'kiosk-lifecycle:set-subreaper')
    descriptors = set()
    workers = {}
    try:
        def pipe():
            pair = os.pipe2(os.O_CLOEXEC)
            descriptors.update(pair)
            return pair
        executor_read, executor_write = pipe()
        helper_read, helper_write = pipe()
        event_read, event_write = pipe()
        executor = os.fork()
        if executor == 0:
            try:
                for fd in (executor_write, helper_write, event_read):
                    os.close(fd)
                for fd in (executor_read, helper_read, event_write):
                    os.set_inheritable(fd, True)
                request = json.dumps({'backend': backend, 'executor_release': executor_read,
                                      'helper_release': helper_read, 'events': event_write})
                os.execve(command[0], [*command, request], dict(os.environ))
            except BaseException:
                os._exit(124)
        workers[executor] = None
        workers[executor] = os.pidfd_open(executor)
        for fd in (executor_read, helper_read, event_write):
            os.close(fd)
            descriptors.remove(fd)
        ready = lifecycle_event(event_read)
        guest.require(set(ready) == {'phase', 'pid', 'parent'} and ready['phase'] == 'ready' and
                      type(ready['pid']) is int and ready['pid'] > 1 and ready['parent'] == executor,
                      'kiosk-lifecycle:spawn-identity')
        helper = ready['pid']
        workers[helper] = None
        workers[helper] = os.pidfd_open(helper)
        identity = process_identity(PROC / str(helper))
        guest.require(identity[1:] == (executor, (str(account.pw_uid),) * 4), 'kiosk-lifecycle:helper-identity')
        attribute = 'attr/apparmor/current' if backend == 'apparmor' else 'attr/current'
        guest.require((PROC / str(helper) / attribute).read_text().strip().rstrip('\0') == expected,
                      'kiosk-lifecycle:waiting-label')
        marker = 'usr/share/oh-no-parent-control/confinement/generation'
        helper_generation = (PROC / str(helper) / 'root' / marker).read_text()
        manager_generation = (PROC / str(saved_pid) / 'root' / marker).read_text()
        if helper_generation != manager_generation:
            lifecycle_generation_diagnostic(manager_generation, helper_generation, record)
        guest.require(helper_generation == manager_generation, 'kiosk-lifecycle:waiting-generation')
        if optional_cgfs_session(backend):
            lifecycle_cgfs_mapping(PROC / str(helper), native_files, record)
            guest.require(process_identity(PROC / str(helper)) == identity and
                          not exited(workers[helper]), 'kiosk-lifecycle:mapping-helper-changed')
        os.write(executor_write, b'E')
        status = lifecycle_wait(executor, workers[executor])
        os.close(workers.pop(executor))
        guest.require(status == 0, 'kiosk-lifecycle:executor-exec')
        after = process_identity(PROC / str(helper))
        guest.require(after[0] == identity[0] and after[1:] == (os.getpid(), identity[2]) and
                      not exited(workers[helper]), 'kiosk-lifecycle:post-parent-identity')
        guest.require((PROC / str(helper) / attribute).read_text().strip().rstrip('\0') == expected,
                      'kiosk-lifecycle:post-parent-label')
        os.write(helper_write, b'T')
        finished = lifecycle_event(event_read)
        guest.require(set(finished) == {'phase', 'stages', 'establish_status'} and
                      finished['phase'] == 'finished' and type(finished['establish_status']) is int and
                      isinstance(finished['stages'], list) and
                      [item.get('stage') for item in finished['stages']] == ['parent-exited',
                      'close-session', 'delete-credentials', 'end'], 'kiosk-lifecycle:teardown-result')
        status = lifecycle_wait(helper, workers[helper])
        os.close(workers.pop(helper))
        guest.require(status == 0, 'kiosk-lifecycle:teardown-exit')
        guest.require(manager_pid(unit) == saved_pid and process_identity(PROC / str(saved_pid)) == saved_identity,
                      'kiosk-lifecycle:saved-manager-changed')
        record('onpc.kiosk.pam-lifecycle.establish-credentials-status', finished['establish_status'])
        for item in finished['stages'][1:]:
            guest.require(set(item) == {'stage', 'pam_status'} and type(item['pam_status']) is int,
                          'kiosk-lifecycle:callback-result')
            record('onpc.kiosk.pam-lifecycle.' + item['stage'] + '-status', item['pam_status'])
        record('onpc.kiosk.pam-lifecycle.post-parent-close-setcred-end-denials', True)
        guest.require(finished['establish_status'] == 0 and
                      all(item['pam_status'] == 0 for item in finished['stages'][1:]),
                      'kiosk-lifecycle:credential-teardown-incomplete')
    finally:
        try:
            for fd in descriptors:
                os.close(fd)
            # Only explicit spawn identities from this root-owned protocol may
            # be signalled. Reap the executor first so its child is adopted here.
            errors = []
            for pid, pidfd in workers.items():
                try:
                    try:
                        if pidfd is None:
                            os.kill(pid, signal.SIGKILL)
                        else:
                            signal.pidfd_send_signal(pidfd, signal.SIGKILL)
                    except ProcessLookupError:
                        pass
                    os.waitpid(pid, 0)
                except BaseException as error:
                    errors.append(error)
                finally:
                    if pidfd is not None:
                        os.close(pidfd)
            if errors:
                raise errors[0]
        finally:
            guest.require(libc.prctl(36, previous.value, 0, 0, 0) == 0, 'kiosk-lifecycle:restore-subreaper')


def bwrap_probe_child(request):
    """Root-owned engineering entry into the app boundary, never a product route.

    AppArmor can restrict the already-running harness immediately. SELinux
    enters through an independent root-private interpreter fixture carrying the
    existing Python entrypoint type, as the PAM caller probes do. No production
    interpreter or dynamic-transition permission is added for this fixture.
    """
    backend = request['backend']
    expected = ('onpc-kiosk-app (enforce)' if backend == 'apparmor'
                else 'system_u:system_r:onpc_kiosk_app_t:s0')
    if backend == 'apparmor':
        library = ctypes.CDLL('libapparmor.so.1', use_errno=True)
        library.aa_change_profile.argtypes = [ctypes.c_char_p]
        guest.require(library.aa_change_profile(b'onpc-kiosk-app') == 0,
                      'kiosk-bwrap:app-profile-entry')
    guest.require(lifecycle_label(backend) == expected, 'kiosk-bwrap:app-label')
    os.setgroups([])
    os.setgid(request['gid'])
    os.setuid(request['uid'])
    guest.require(process_identity(PROC / 'self')[2] == (str(request['uid']),) * 4 and
                  os.stat('/proc/self/ns/mnt').st_ino == request['namespace'] and
                  Path('/usr/share/oh-no-parent-control/confinement/generation').read_text() ==
                  request['generation'], 'kiosk-bwrap:app-boundary')
    proof = {name: request[name] for name in ('uid', 'namespace', 'generation')}
    proof['role'] = expected
    os.set_inheritable(request['proof_fd'], False)
    data = json.dumps(proof).encode()
    guest.require(os.write(request['proof_fd'], data) == len(data), 'kiosk-bwrap:proof-write')
    try:
        os.execve('/usr/bin/bwrap', request['arguments'], {'PATH': '/usr/bin:/bin', 'LANG': 'C'})
    except OSError as error:
        # Failure to enter native bubblewrap is a broken probe, never evidence
        # about the later mount/execute attack.
        os.write(2, (json.dumps({'bwrap_setup': 'initial-exec', 'errno': error.errno}) + '\n').encode())
        os._exit(126)


def bwrap_child_pid(data):
    guest.require(len(data) <= 4096, 'kiosk-bwrap:native-child-info-size')
    try:
        info = json.loads(data)
    except (ValueError, UnicodeDecodeError):
        info = None
    guest.require(isinstance(info, dict) and type(info.get('child-pid')) is int and
                  info['child-pid'] > 1, 'kiosk-bwrap:native-child-info-missing')
    return info['child-pid']


def bwrap_audit_denial(line, backend, pid, target, *, mode='bind', source_inode=None, uid=None):
    """Match the attack stage, exact native child and enforcing sandbox role."""
    if not re.search(r'\bpid=' + re.escape(str(pid)) + r'\b', line):
        return False
    if backend == 'apparmor':
        fields = dict(re.findall(r'\b(apparmor|operation|profile|name)="([^"]*)"', line))
        if mode == 'tmpfs-file':
            owners = dict(re.findall(r'\b(fsuid|ouid)=([0-9]+)\b', line))
            return (fields == {'apparmor': 'DENIED', 'operation': 'mknod',
                               'profile': 'onpc-kiosk-bwrap', 'name': '/newroot' + target} and
                    'class="file"' in line and 'requested_mask="c"' in line and 'denied_mask="c"' in line and
                    type(uid) is int and owners == {'fsuid': str(uid), 'ouid': str(uid)})
        return fields == {'apparmor': 'DENIED', 'operation': 'mount',
                          'profile': 'onpc-kiosk-bwrap', 'name': '/newroot' + target} and bool(
                              re.search(r'\berror=-13\b', line))
    if backend != 'selinux' or mode not in ('bind', 'data', 'tmpfs-file'):
        return False
    fields = dict(re.findall(r'\b(scontext|tcontext|tclass|permissive|ino)=([^\s]+)', line))
    objects = dict(re.findall(r'\b(name|dev|path)="([^"]*)"', line))
    expected_name = ('bwrap-canary' if mode == 'bind' else
                     Path(target).name if mode == 'tmpfs-file' else None)
    expected_context = ('unconfined_u:object_r:user_tmp_t:s0' if mode == 'bind'
                        else 'system_u:object_r:tmpfs_t:s0')
    inode = fields.pop('ino', '')
    return ('avc:  denied' in line and re.search(r'\{\s*execute\s*\}', line) is not None and
            re.fullmatch(r'[1-9][0-9]*', inode) is not None and
            (mode != 'bind' or type(source_inode) is int and int(inode) == source_inode) and
            objects.get('name') == expected_name and objects.get('dev') == 'tmpfs' and
            ('path' not in objects or objects['path'] == target) and
            fields == {'scontext': 'system_u:system_r:onpc_kiosk_bwrap_t:s0',
                       'tcontext': expected_context, 'tclass': 'file', 'permissive': '0'})


def record_bwrap_probe(record, name, status, output, info, stderr):
    record('onpc.kiosk.bwrap.' + name + '.probe', json.dumps({
        'status': status, 'stdout': output[:4096].decode(errors='replace'),
        'stderr': stderr[:4096].decode(errors='replace'),
        'native_info': info[:4096].decode(errors='replace'),
        'truncated': any(len(value) > 4096 for value in (output, info, stderr)),
    }, sort_keys=True))


def require_bwrap_denial(status, output, info, token, backend, target, before, started, record, *,
                         stderr=b'', mode='bind', source_inode=None, uid=None):
    from system_kiosk_platform import kernel_audit, wait_for
    guest.require(b'bwrap_setup' not in output + stderr, 'kiosk-bwrap:probe-setup-failed')
    pid = bwrap_child_pid(info)
    guest.require(status != 0 and token not in output, 'kiosk-bwrap:user-bytes-executed')
    if backend == 'selinux':
        # bubblewrap has one final exec. Its exact target/stage binds the AVC
        # object to this request even when auditd reports no PATH record.
        guest.require(stderr == ('bwrap: execvp ' + target + ': Permission denied\n').encode(),
                      'kiosk-bwrap:native-exec-denial-missing')
    elif mode == 'tmpfs-file':
        guest.require(stderr == ("bwrap: Can't create file " + target + ': Permission denied\n').encode(),
                      'kiosk-bwrap:native-create-denial-missing')

    def observed():
        for line in kernel_audit(backend).splitlines():
            event = re.search(r'\baudit\(([0-9]+(?:\.[0-9]+)?):[0-9]+\)', line)
            if (line not in before and event and float(event[1]) >= started and
                    bwrap_audit_denial(line, backend, pid, target, mode=mode,
                                       source_inode=source_inode, uid=uid)):
                record('onpc.kiosk.bwrap.kernel-denial', line)
                return True
        return False

    wait_for(observed, 'kiosk-bwrap:kernel-denial-not-observed')


@contextmanager
def trusted_probe_copy(path, backend):
    """Admit only this attempt's copied ELF to the independent Fedora policy.

    The MAC probes still require their exact enforcing kernel denial. Stock
    fapolicyd can otherwise reject the unconfined positive control first.
    No rule, directory allowance, daemon mode or executable label changes.
    """
    guest.require(backend in ('apparmor', 'selinux'), 'kiosk-input:backend')
    if backend != 'selinux':
        yield
        return
    guest.guard()
    from system_enforcement import TrustRefreshCompletion, TrustRefreshDiagnostic

    def refresh():
        diagnostic = TrustRefreshDiagnostic()
        completion = TrustRefreshCompletion()
        guest.run(['fapolicyd-cli', '--update'])
        completion.wait(time.monotonic() + 120, diagnostic)

    for parent in (PROBE_TRUST_DIRECTORY, *PROBE_TRUST_DIRECTORY.parents):
        info = parent.lstat()
        guest.require(stat.S_ISDIR(info.st_mode) and info.st_uid == 0 and
                      not info.st_mode & 0o022, 'kiosk-input:unsafe-trust-parent')
    source = path.lstat()
    guest.require(stat.S_ISREG(source.st_mode) and source.st_nlink == 1 and
                  path.resolve(strict=True) == path, 'kiosk-input:unsafe-probe-copy')
    expected = [str(path), str(source.st_size), guest.sha(path)]
    original = {'copied-systemctl': '/usr/bin/systemctl',
                'bwrap-canary': '/usr/bin/xdg-dbus-proxy'}.get(path.name)
    guest.require(original is not None and expected[2] == guest.sha(Path(original)),
                  'kiosk-input:probe-copy-digest')
    fragment = PROBE_TRUST_DIRECTORY / ('onpc-system-' + path.parent.name + '-' + path.name + '.trust')
    guest.require(not fragment.exists() and not fragment.is_symlink(),
                  'kiosk-input:trust-collision')
    guest.run(['fapolicyd-cli', '--file', 'add', str(path), '--trust-file', fragment.name])
    info = fragment.lstat()
    guest.require(stat.S_ISREG(info.st_mode) and info.st_uid == 0 and
                  info.st_nlink == 1 and not info.st_mode & 0o022,
                  'kiosk-input:unsafe-trust-fragment')
    contents = fragment.read_bytes()
    rows = [line.split() for line in contents.decode().splitlines()
            if line.strip() and not line.startswith('#')]
    guest.require(rows == [expected], 'kiosk-input:unexpected-trust-entries')
    try:
        guest.run(['restorecon', str(fragment)])
        refresh()
        current = path.lstat()
        guest.require((current.st_dev, current.st_ino, current.st_size) ==
                      (source.st_dev, source.st_ino, source.st_size) and
                      guest.sha(path) == expected[2], 'kiosk-input:probe-copy-changed')
        yield
    finally:
        current = fragment.lstat()
        guest.require((current.st_dev, current.st_ino) == (info.st_dev, info.st_ino) and
                      current.st_uid == 0 and stat.S_ISREG(current.st_mode) and
                      current.st_nlink == 1 and not current.st_mode & 0o022 and
                      fragment.read_bytes() == contents, 'kiosk-input:trust-fragment-changed')
        fragment.unlink()
        refresh()


def verify_bwrap_inputs(account, directory, record):
    """User bytes cannot acquire a pinned executable's authority through a bind."""
    config = json.loads(Path('/usr/share/oh-no-parent-control/confinement/config.json').read_text())
    backend = config['backend']
    guest.require(backend in ('apparmor', 'selinux'), 'kiosk-bwrap:backend')
    manager = PROC / str(manager_pid(f'user@{account.pw_uid}.service'))
    identity = process_identity(manager)
    marker = 'usr/share/oh-no-parent-control/confinement/generation'
    generation = (manager / 'root' / marker).read_text()
    copied = directory / 'bwrap-canary'
    shutil.copyfile('/usr/bin/xdg-dbus-proxy', copied)
    copied.chmod(0o755)
    os.chown(copied, account.pw_uid, account.pw_gid)
    with ExitStack() as resources:
        resources.enter_context(trusted_probe_copy(copied, backend))
        def descriptor(path, flags):
            fd = os.open(path, flags | os.O_CLOEXEC)
            resources.callback(os.close, fd)
            return fd
        manager_fd = os.pidfd_open(int(manager.name))
        resources.callback(os.close, manager_fd)
        namespace = descriptor(manager / 'ns/mnt', os.O_RDONLY)
        root = descriptor(manager / 'root', os.O_RDONLY | os.O_DIRECTORY)
        namespace_inode = os.fstat(namespace).st_ino
        guest.require(not exited(manager_fd) and process_identity(manager) == identity and
                      namespace_inode != os.stat('/proc/self/ns/mnt').st_ino,
                      'kiosk-bwrap:manager-boundary')
        temporary = resources.enter_context(tempfile.TemporaryDirectory(
            prefix='bwrap-caller-', dir=guest.PAYLOAD))
        caller = Path(temporary) / 'caller'
        if backend == 'selinux':
            shutil.copyfile(Path('/usr/bin/python3').resolve(), caller)
            caller.chmod(0o700)
            guest.run(['/usr/bin/chcon', '-t', 'onpc_kiosk_python_exec_t', str(caller)])

        def probe(arguments, name, *, input_fd=None, control=False):
            output_read, output_write = os.pipe2(os.O_CLOEXEC)
            try:
                info_read, info_write = os.pipe2(os.O_CLOEXEC)
            except BaseException:
                os.close(output_read)
                os.close(output_write)
                raise
            try:
                proof_read, proof_write = os.pipe2(os.O_CLOEXEC)
            except BaseException:
                os.close(output_read)
                os.close(output_write)
                os.close(info_read)
                os.close(info_write)
                raise
            try:
                error_read, error_write = os.pipe2(os.O_CLOEXEC)
            except BaseException:
                for fd in (output_read, output_write, proof_read, proof_write, info_read, info_write):
                    os.close(fd)
                raise
            try:
                child = os.fork()
            except BaseException:
                for fd in (output_read, output_write, proof_read, proof_write, info_read, info_write,
                           error_read, error_write):
                    os.close(fd)
                raise
            if child == 0:
                os.close(output_read)
                os.close(proof_read)
                os.close(info_read)
                os.close(error_read)
                try:
                    os.dup2(output_write, 1)
                    os.dup2(error_write, 2)
                    os.close(output_write)
                    os.close(error_write)
                    os.setns(namespace, os.CLONE_NEWNS)
                    os.fchdir(root)
                    os.chroot('.')
                    os.chdir('/')
                    for fd in (namespace, root, manager_fd):
                        os.close(fd)
                    if control:
                        os.setgroups([])
                        os.setgid(account.pw_gid)
                        os.setuid(account.pw_uid)
                        os.execve(str(copied), arguments, {'PATH': '/usr/bin:/bin', 'LANG': 'C'})
                    arguments = [arguments[0], '--info-fd', str(info_write), *arguments[1:]]
                    os.set_inheritable(info_write, True)
                    request = dict(backend=backend, uid=account.pw_uid, gid=account.pw_gid,
                        namespace=namespace_inode, generation=generation, arguments=arguments,
                        proof_fd=proof_write)
                    if input_fd is not None:
                        os.set_inheritable(input_fd, True)
                    if backend == 'selinux':
                        library = ctypes.CDLL('libselinux.so.1', use_errno=True)
                        library.setexeccon.argtypes = [ctypes.c_char_p]
                        guest.require(library.setexeccon(b'system_u:system_r:onpc_kiosk_app_t:s0') == 0,
                                      'kiosk-bwrap:app-exec-context')
                        os.set_inheritable(proof_write, True)
                        os.execve(str(caller), [str(caller), '-B', str(Path(__file__).resolve()),
                            'bwrap-exec', json.dumps(request)], {'PATH': '/usr/bin:/bin', 'LANG': 'C'})
                    bwrap_probe_child(request)
                    os._exit(124)
                except BaseException as error:
                    try:
                        category = str(error) if isinstance(error, guest.GuestError) else type(error).__name__
                        diagnostic = json.dumps({'bwrap_setup': category, 'errno': getattr(error, 'errno', None)})
                        os.write(2, (diagnostic + '\n').encode())
                    finally:
                        os._exit(124)
            os.close(output_write)
            os.close(proof_write)
            os.close(info_write)
            os.close(error_write)
            try:
                status, output = wait_first_exec(child, output_read, armed=False)
                proof = os.read(proof_read, 4097)
                info = os.read(info_read, 4097)
                stderr = os.read(error_read, 4097)
                record_bwrap_probe(record, name, status, output, info, stderr)
                guest.require(b'bwrap_setup' not in output + stderr, 'kiosk-bwrap:probe-setup-failed')
                if not control:
                    expected = dict(uid=account.pw_uid, namespace=namespace_inode, generation=generation,
                        role='onpc-kiosk-app (enforce)' if backend == 'apparmor'
                             else 'system_u:system_r:onpc_kiosk_app_t:s0')
                    guest.require(len(proof) <= 4096 and proof and json.loads(proof) == expected,
                                  'kiosk-bwrap:app-proof-missing')
                    bwrap_child_pid(info)
                return status, output, info, stderr
            finally:
                os.close(proof_read)
                os.close(info_read)
                os.close(error_read)

        base = ['/usr/bin/bwrap', '--die-with-parent', '--unshare-pid', '--as-pid-1',
                '--ro-bind', '/usr', '/usr', '--ro-bind', '/etc', '/etc',
                '--proc', '/proc', '--dev', '/dev', '--tmpfs', '/tmp',
                '--symlink', 'usr/lib', '/lib', '--symlink', 'usr/lib64', '/lib64',
                '--ro-bind', str(directory), str(directory)]
        status, output, _, _ = probe([*base, '--', '/usr/bin/xdg-dbus-proxy', '--version'], 'native-positive')
        guest.require(status == 0 and output.startswith(b'xdg-dbus-proxy '),
                      'kiosk-bwrap:native-sandbox-positive')
        token = output
        record('onpc.kiosk.bwrap.native-sandbox-positive', True)
        scanner = next(entry['paths'][0] for entry in config['executables'] if entry['role'] == 'scanner')
        for role, target in (('proxy', '/usr/bin/xdg-dbus-proxy'), ('scanner', scanner)):
            arguments = [target, '--version']
            status, output, _, _ = probe(arguments, role + '-canary', control=True)
            guest.require(status == 0 and output == token, 'kiosk-bwrap:canary-positive')
            for mode in ('bind', 'data', 'tmpfs-file'):
                from system_kiosk_platform import kernel_audit, settle_kernel_audit
                settle_kernel_audit(backend)
                before = set(kernel_audit(backend).splitlines())
                started = time.time()
                with copied.open('rb') as stream:
                    fd = stream.fileno()
                    source_inode = os.fstat(fd).st_ino
                    mutation = (['--ro-bind', str(copied), target] if mode == 'bind' else
                        ['--perms', '0755', '--ro-bind-data', str(fd), target] if mode == 'data' else
                        ['--tmpfs', str(Path(target).parent), '--perms', '0755', '--file', str(fd), target])
                    status, output, info, stderr = probe([*base, *mutation, '--', *arguments],
                                                        role + '-' + mode, input_fd=fd)
                require_bwrap_denial(status, output, info, token, backend, target, before,
                                    started, record, stderr=stderr, mode=mode,
                                    source_inode=source_inode, uid=account.pw_uid)
                record('onpc.kiosk.bwrap.' + role + '.' + mode + '-denied', status)
        guest.require(not exited(manager_fd) and process_identity(manager) == identity and
                      (manager / 'root' / marker).read_text() == generation,
                      'kiosk-bwrap:manager-changed')


def verify_user_inputs(account, backend, record):
    runtime = Path(f'/run/user/{account.pw_uid}')
    with tempfile.TemporaryDirectory(prefix='onpc-confinement-input-', dir=runtime) as temporary:
        directory = Path(temporary)
        directory.chmod(0o755)
        os.chown(directory, account.pw_uid, account.pw_gid)
        copied = directory / 'copied-systemctl'
        shutil.copy2('/usr/bin/systemctl', copied)
        os.chown(copied, account.pw_uid, account.pw_gid)
        alias = directory / 'interpreter-alias'
        alias.symlink_to('/usr/bin/python3')
        os.lchown(alias, account.pw_uid, account.pw_gid)
        for index, command in enumerate(([str(copied), '--version'], [str(alias), '-c', 'pass'])):
            with ExitStack() as resources:
                if index == 0:
                    resources.enter_context(trusted_probe_copy(copied, backend))
                user_command(account, command)
                record('onpc.kiosk.writable-input-positive.' + str(index), True)
                require_service_denial(account, backend, f'onpc-confinement-writable-{index}.service',
                                       command, record)
        verify_bwrap_inputs(account, directory, record)
    unit_directory = runtime / 'systemd/user'
    created = []
    for path in (unit_directory.parent, unit_directory):
        if not path.exists():
            path.mkdir(mode=0o700)
            os.chown(path, account.pw_uid, account.pw_gid)
            created.append(path)
    unit = unit_directory / 'onpc-confinement-prefix.service'
    with unit.open('x') as stream:
        stream.write('[Service]\nType=oneshot\nExecStart=+/bin/sh -c "exit 0"\n')
    os.chown(unit, account.pw_uid, account.pw_gid)
    identity = (unit.stat().st_dev, unit.stat().st_ino)
    contents = unit.read_bytes()
    metadata = unit.stat()
    try:
        user_command(account, ['/usr/bin/systemctl', '--user', 'daemon-reload'])
        effective = dict(line.split('=', 1) for line in user_command(account,
            ['/usr/bin/systemctl', '--user', 'show', unit.name,
             '--property=FragmentPath,ExecStartEx']).decode().splitlines())
        record('onpc.kiosk.plus-unit-input', json.dumps({'sha256': guest.sha(unit),
            'uid': metadata.st_uid, 'gid': metadata.st_gid, 'mode': metadata.st_mode,
            'effective': effective}, sort_keys=True))
        guest.require(effective.get('FragmentPath') == str(unit) and
                      ' ; flags=privileged ; ' in effective.get('ExecStartEx', ''),
                      'kiosk-confinement:plus-unit-input')
        user_command(account, ['/bin/sh', '-c', 'exit 0'])
        record('onpc.kiosk.plus-unit-input-positive', True)
        require_service_denial(account, backend, unit.name, ['/bin/sh', '-c', 'exit 0'],
                               record, writable=True)
        record('onpc.kiosk.copied-alias-and-plus-unit-denied', True)
    finally:
        current = unit.stat()
        guest.require((current.st_dev, current.st_ino) == identity and unit.read_bytes() == contents and
                      (current.st_uid, current.st_gid, current.st_mode) ==
                      (metadata.st_uid, metadata.st_gid, metadata.st_mode),
                      'kiosk-confinement:unit-identity-changed')
        unit.unlink()
        user_command(account, ['/usr/bin/systemctl', '--user', 'reset-failed', unit.name], check=False)
        user_command(account, ['/usr/bin/systemctl', '--user', 'daemon-reload'])
        for path in reversed(created):
            path.rmdir()


def manager_boundary(account, unit, backend, *, retained_view=False):
    """Pin the actual manager and every thread across a single observation."""
    process = PROC / str(manager_pid(unit))
    pidfd = os.pidfd_open(int(process.name))
    try:
        identity = process_identity(process)
        expected = ('onpc-kiosk-manager (enforce)' if backend == 'apparmor' else MANAGER_SID)
        attribute = 'attr/apparmor/current' if backend == 'apparmor' else 'attr/current'
        namespace = os.readlink(process / 'ns/mnt')
        marker = ('root/usr/share/oh-no-parent-control/confinement/' +
                  ('retained-view' if retained_view else 'generation'))
        generation = (process / marker).read_text()
        marker_pattern = (r'ONPC-KIOSK-VIEW\t1\t' + re.escape(backend) +
                          r'\t[a-f0-9]{64}\t[a-f0-9]{64}\n'
                          if retained_view else r'[a-f0-9]{64}\n')
        guest.require(identity[2] == (str(account.pw_uid),) * 4 and
                      namespace != os.readlink(PROC / '1/ns/mnt') and
                      re.fullmatch(marker_pattern, generation) is not None,
                      'kiosk-confinement:manager-boundary')
        threads = {thread: census_thread_identity(thread)
                   for thread in (process / 'task').iterdir()}
        guest.require(bool(threads), 'kiosk-confinement:manager-threads-missing')
        for target in (process, *threads):
            guest.require(process_identity(target)[2] == identity[2] and
                          (target / attribute).read_text().strip().rstrip('\0') == expected and
                          os.readlink(target / 'ns/mnt') == namespace and
                          (target / marker).read_text() == generation,
                          'kiosk-confinement:manager-thread-boundary')
        guest.require(not exited(pidfd) and process_identity(process) == identity and
                      manager_pid(unit) == int(process.name) and
                      set((process / 'task').iterdir()) == set(threads) and
                      all(census_thread_identity(thread) == value for thread, value in threads.items()) and
                      (not retained_view or all((target / marker).read_text() == generation
                                               for target in (process, *threads))),
                      'kiosk-confinement:manager-lifecycle-changed')
        return {'pid': int(process.name), 'identity': identity,
                'label': expected, 'namespace': namespace, 'generation': generation}
    finally:
        os.close(pidfd)


def bootstrap_descriptors(process):
    """Exclude only the transient descriptor used to enumerate our own table."""
    result = {}
    for entry in (process / 'fd').iterdir():
        try:
            info = entry.stat()
            flags = dict(line.split(':', 1) for line in
                         (process / 'fdinfo' / entry.name).read_text().splitlines())
            result[entry.name] = [info.st_dev, info.st_ino, info.st_mode,
                                  int(flags['flags'].strip(), 8), os.readlink(entry)]
        except FileNotFoundError:
            guest.require(process == PROC / 'self', 'kiosk-bootstrap:descriptor-disappeared')
    return result


def bootstrap_object(path, *, follow=False):
    info = path.stat() if follow else path.lstat()
    return [info.st_dev, info.st_ino, info.st_mode, info.st_uid, info.st_gid,
            info.st_size, info.st_mtime_ns, info.st_ctime_ns, info.st_nlink]


def bootstrap_restrictions(host_namespace, executable):
    """Harmless actual kernel attempts from the already admitted PAM worker."""
    result = {}
    for name, operation in (
        ('mount', lambda library: library.mount(None, b'/usr', None, ctypes.c_ulong(33), None)),
        ('mount-namespace', lambda library: library.unshare(0x00020000)),
        ('user-namespace', lambda library: library.unshare(0x10000000)),
        ('host-namespace', lambda library: library.setns(host_namespace, 0x00020000)),
    ):
        library = ctypes.CDLL(None, use_errno=True)
        ctypes.set_errno(0)
        status = operation(library)
        error = ctypes.get_errno()
        result[name] = {'status': status, 'errno': error}
        guest.require(status == -1 and error in (errno.EACCES, errno.EPERM),
                      'kiosk-bootstrap:authority-not-denied:' + name)
    paths = [Path(executable)]
    for directory in (Path('/usr/lib64/systemd'), Path('/usr/lib/x86_64-linux-gnu/systemd')):
        if directory.exists():
            paths.extend(sorted(directory.glob('libsystemd-*.so'))[:1])
    guest.require(len(paths) == 2, 'kiosk-bootstrap:library-source-missing')
    for path in paths:
        descriptor = None
        try:
            descriptor = os.open(path, os.O_WRONLY | os.O_CLOEXEC)
        except OSError as error:
            result[str(path)] = error.errno
            guest.require(error.errno in (errno.EROFS, errno.EACCES, errno.EPERM),
                          'kiosk-bootstrap:source-write-error')
        else:
            raise guest.GuestError('kiosk-bootstrap:source-write-admitted')
        finally:
            if descriptor is not None:
                os.close(descriptor)
        guest.require(not os.access(path.parent, os.W_OK, effective_ids=True),
                      'kiosk-bootstrap:source-replacement-admitted')
    for path in (Path('/usr'), Path('/run/oh-no-parent-control-confinement')):
        guest.require(not os.access(path, os.W_OK, effective_ids=True),
                      'kiosk-bootstrap:skeleton-or-record-write-admitted')
    return result


def bootstrap_mounts(process):
    result = {}
    for line in (process / 'mountinfo').read_text().splitlines():
        left, right = line.split(' - ', 1)
        fields = left.split()
        path = re.sub(r'\\([0-7]{3})', lambda match: chr(int(match[1], 8)), fields[4])
        guest.require(path not in result or not (path == '/usr' or path.startswith('/usr/')),
                      'kiosk-bootstrap:stacked-mount')
        result[path] = {'id': int(fields[0]), 'options': fields[5].split(','),
                        'filesystem': right.split()[0], 'superoptions': right.split()[2].split(',')}
    return result


def bootstrap_source_trust(path, kind, info, link):
    # Linux symlink mode bits do not grant write access. Their exact text,
    # ownership and the read-only containing skeleton establish this boundary.
    is_link = stat.S_ISLNK(info[2])
    guest.require(info[3:5] == [0, 0] and (
        kind == 'link' and is_link and os.readlink(path) == link or
        kind != 'link' and not is_link and not info[2] & 0o022),
        'kiosk-bootstrap:source-writable')


def bootstrap_view(process, *, source=None):
    """Independently observe mounted objects; a parsed V alone is no witness."""
    deadline = time.monotonic() + 60
    root = process / 'root'
    marker = root / 'usr/share/oh-no-parent-control/confinement/retained-view'
    fields = marker.read_text().rstrip('\n').split('\t')
    guest.require(len(fields) == 5 and fields[:2] == ['ONPC-KIOSK-VIEW', '1'] and
                  fields[2] in ('apparmor', 'selinux') and all(
                  re.fullmatch(r'[a-f0-9]{64}', value) for value in fields[3:]),
                  'kiosk-bootstrap:marker')
    backend, material, view = fields[2:]
    directory = Path('/run/oh-no-parent-control-confinement') / view
    completed = {item.name: bootstrap_object(item) + [guest.sha(item)]
                 for item in directory.iterdir()}
    required_records = {'material.json', 'view', 'pins', 'ready', 'runtime.json'}
    guest.require(required_records <= set(completed) and all(
        value[3:5] == [0, 0] and not value[2] & 0o022 and value[8] == 1
        for value in completed.values()), 'kiosk-bootstrap:completed-trust')
    encoded = (directory / 'view').read_bytes()
    digest = hashlib.sha256(b'ONPC-KIOSK-VIEW\0' + len(encoded).to_bytes(8, 'big') + encoded).hexdigest()
    guest.require(digest == view and len(encoded) <= 64 * 1024 * 1024,
                  'kiosk-bootstrap:view-digest')
    lines = encoded.decode().splitlines()
    header = lines[0].split('\t')
    guest.require(header[:6] == ['ONPC-KIOSK-RECEIPT', '2', 'V', backend, 'manager', material]
                  and len(lines) <= 32769, 'kiosk-bootstrap:view-header')
    material_bytes = (directory / 'material.json').read_bytes()
    guest.require(hashlib.sha256(b'ONPC-KIOSK-MATERIAL\0' +
        len(material_bytes).to_bytes(8, 'big') + material_bytes).hexdigest() == material,
        'kiosk-bootstrap:material-digest')
    ready = (directory / 'ready').read_text().rstrip('\n').split('\t')
    guest.require(len(ready) == 14 and ready[:5] == ['ONPC-KIOSK-READY', '2', material, view,
                  guest.sha(directory / 'pins')] and
                  ready[5] == Path('/proc/sys/kernel/random/boot_id').read_text().strip() and
                  list(map(int, ready[6:8])) == bootstrap_object(directory)[:2] and
                  list(map(int, ready[10:12])) == bootstrap_object(marker)[:2],
                  'kiosk-bootstrap:ready-binding')
    mounts = bootstrap_mounts(process)
    mounts = {path: value for path, value in mounts.items()
              if path == '/usr' or path.startswith('/usr/')}
    objects, coverage, sources, expected_mounts = {}, {}, {}, set()
    for line in lines[1:]:
        guest.require(time.monotonic() < deadline, 'kiosk-bootstrap:view-observation-timeout')
        values = line.split('\t')
        if values[0] == 'N':
            guest.require(len(values) == 23, 'kiosk-bootstrap:node-fields')
            path, kind, required, source_class, acquisition, role = values[1:7]
            guest.require(path == '/usr' or path.startswith('/usr/'), 'kiosk-bootstrap:node-path')
            if kind in ('absent', 'empty-directory'):
                continue
            actual = root / path.lstrip('/')
            info = bootstrap_object(actual)
            objects[path] = info
            # Gate skeleton parents are newly made. Every actual retained leaf
            # and every nested directory source must retain the original inode.
            if kind not in ('tree', 'link'):
                guest.require(info[:2] == list(map(int, values[10:12])),
                              'kiosk-bootstrap:mounted-source-inode')
            if kind == 'link':
                guest.require(os.readlink(actual) == values[21], 'kiosk-bootstrap:mounted-link')
            if required == '1' and kind == 'file':
                guest.require(guest.sha(actual) == values[19], 'kiosk-bootstrap:mounted-source-bytes')
            if values[22] == '1':
                expected_mounts.add(path)
                guest.require(path in mounts and 'ro' in mounts[path]['options'],
                              'kiosk-bootstrap:required-readonly-mount')
            if source_class in ('native', 'runtime', 'payload', 'vendor'):
                bootstrap_source_trust(actual, kind, info, values[21])
                sources[path] = {'kind': kind, 'role': role, 'class': source_class,
                                 'sha256': values[19]}
                if kind == 'link':
                    # Native recreates links in fresh invocation parents; it
                    # verifies trusted ownership/type and exact text, not V's
                    # link inode. Keep the full dentry in objects above so a
                    # later manager observation still detects replacement.
                    sources[path].update(link=values[21], ownership=info[2:5])
                else:
                    # Bound executable/library/directory sources (and nested
                    # coverage below) must remain the original manager's.
                    sources[path]['identity'] = info
        else:
            guest.require(values[0] == 'C' and len(values) == 13,
                          'kiosk-bootstrap:coverage-fields')
            path = values[2]
            actual = bootstrap_object(root / path.lstrip('/'))
            guest.require(actual[:2] == list(map(int, values[5:7])) and path in mounts and
                          'ro' in mounts[path]['options'], 'kiosk-bootstrap:nested-coverage')
            coverage[path] = actual
            expected_mounts.add(path)
    guest.require({path for path in mounts if path == '/usr' or path.startswith('/usr/')} ==
                  expected_mounts, 'kiosk-bootstrap:unexpected-nested-mount')
    guest.require(objects and sources and '/usr' in mounts and
                  'ro' in mounts['/usr']['options'], 'kiosk-bootstrap:empty-view')
    result = {'backend': backend, 'material': material, 'view': view,
              'marker': bootstrap_object(marker), 'completed': completed,
              'directory': bootstrap_object(directory),
              'objects': objects, 'coverage': coverage, 'sources': sources,
              'root': bootstrap_object(root, follow=True)[:5], 'usr': bootstrap_object(root / 'usr'),
              'ready': ready, 'mounts': mounts}
    if source is None:
        guest.require(list(map(int, ready[8:10])) == result['usr'][:2] and
                      int(ready[12]) == mounts['/usr']['id'], 'kiosk-bootstrap:ready-source-attachment')
    if source is not None:
        guest.require(source['material'] == material and source['view'] == view and
                      source['completed'] == completed and source['directory'] == result['directory'] and
                      source['marker'] == result['marker'] and
                      source['sources'] == sources and source['coverage'] == coverage,
                      'kiosk-bootstrap:retained-view-not-manager-source')
    return result


def bootstrap_process(process, account, backend, *, label=None, expected_groups=None, record=None):
    identity = process_identity(process)
    attribute = 'attr/apparmor/current' if backend == 'apparmor' else 'attr/current'
    expected = label or ('onpc-kiosk-manager (enforce)' if backend == 'apparmor' else MANAGER_SID)
    if expected_groups is None:
        expected_groups = sorted(set(os.getgrouplist(account.pw_name, account.pw_gid)))
    privileged = {0}
    for name in ('root', 'sudo', 'wheel', 'admin'):
        try:
            privileged.add(grp.getgrnam(name).gr_gid)
        except KeyError:
            pass
    guest.require(account.pw_uid != 0 and account.pw_gid not in privileged and
                  not set(expected_groups) & privileged, 'kiosk-bootstrap:privileged-groups')
    namespaces = {name: bootstrap_object(process / 'ns' / name, follow=True)[:2]
                  for name in ('mnt', 'user', 'pid')}
    status = dict(line.split(':', 1) for line in (process / 'status').read_text().splitlines() if ':' in line)
    observed_label = (process / attribute).read_text().strip().rstrip('\0')
    host_namespaces = {name: bootstrap_object(PROC / '1/ns' / name, follow=True)[:2]
                       for name in ('mnt', 'user', 'pid')}
    if record is not None:
        record('onpc.kiosk.bootstrap.process-authority', json.dumps({
            'pid': int(process.name), 'label': observed_label, 'expected_label': expected,
            'namespaces': namespaces, 'host_namespaces': host_namespaces,
            'credentials': {name: status[name].split() for name in ('Uid', 'Gid', 'Groups')},
            'capabilities': {name: status[name].strip() for name in
                             ('CapEff', 'CapPrm', 'CapInh', 'CapAmb', 'CapBnd')},
        }, sort_keys=True))
    guest.require(observed_label == expected and
                  all(int(status[name].strip(), 16) == 0 for name in
                      ('CapEff', 'CapPrm', 'CapInh', 'CapAmb')) and
                  namespaces['mnt'] != host_namespaces['mnt'] and all(
                  namespaces[name] == host_namespaces[name]
                  for name in ('user', 'pid')), 'kiosk-bootstrap:process-authority')
    tasks = {}
    for item in (process / 'task').iterdir():
        thread_identity = census_thread_identity(item)
        fields = dict(line.split(':', 1) for line in (item / 'status').read_text().splitlines() if ':' in line)
        guest.require(thread_identity[2] == (str(account.pw_uid),) * 4 and
            tuple(fields['Gid'].split()) == (str(account.pw_gid),) * 4 and
            sorted(set(map(int, fields['Groups'].split()))) == list(expected_groups) and
            all(int(fields[name].strip(), 16) == 0 for name in ('CapEff', 'CapPrm', 'CapInh', 'CapAmb')) and
            (item / attribute).read_text().strip().rstrip('\0') == expected and
            bootstrap_object(item / 'root', follow=True)[:5] == bootstrap_object(process / 'root', follow=True)[:5] and
            all(bootstrap_object(item / 'ns' / name, follow=True)[:2] == value
                for name, value in namespaces.items()), 'kiosk-bootstrap:task-authority')
        tasks[item.name] = thread_identity
    guest.require(bool(tasks) and set(tasks) == {item.name for item in (process / 'task').iterdir()} and
                  all(census_thread_identity(process / 'task' / name) == value
                      for name, value in tasks.items()) and process_identity(process) == identity,
                  'kiosk-bootstrap:task-set-changed')
    return {'identity': identity, 'label': expected, 'namespaces': namespaces,
            'root': bootstrap_object(process / 'root', follow=True)[:5],
            'executable': bootstrap_object(process / 'exe', follow=True),
            'executable_sha256': guest.sha(process / 'exe'),
            'cgroup': (process / 'cgroup').read_text(),
            'tasks': tasks}


def bootstrap_manager_unchanged(account, unit, backend, expected, pidfd):
    guest.require(not exited(pidfd) and manager_boundary(account, unit, backend, retained_view=True) ==
                  {key: value for key, value in expected.items() if key != 'invocation'} and
                  guest.run(['systemctl', 'show', '--value', '--property=InvocationID', unit]) ==
                  expected['invocation'], 'kiosk-bootstrap:manager-replaced')


def bootstrap_manager_policy(backend, process, source, record):
    """Query the actual enforcing SELinux manager domain, never a policy double.

    Combined with the observed empty capability sets, host user namespace,
    read-only sources and root DAC, these decisions exclude creation/entry of
    a privileged namespace or an unconfined executable transition.
    """
    if backend != 'selinux':
        return
    class Decision(ctypes.Structure):
        _fields_ = [('allowed', ctypes.c_uint32), ('decided', ctypes.c_uint32),
                    ('auditallow', ctypes.c_uint32), ('auditdeny', ctypes.c_uint32),
                    ('seqno', ctypes.c_uint32), ('flags', ctypes.c_uint32)]
    library = ctypes.CDLL('libselinux.so.1', use_errno=True)
    library.string_to_security_class.argtypes = [ctypes.c_char_p]
    library.string_to_security_class.restype = ctypes.c_ushort
    library.string_to_av_perm.argtypes = [ctypes.c_ushort, ctypes.c_char_p]
    library.string_to_av_perm.restype = ctypes.c_uint32
    library.security_compute_av_flags_raw.argtypes = [ctypes.c_char_p, ctypes.c_char_p,
        ctypes.c_ushort, ctypes.c_uint32, ctypes.POINTER(Decision)]
    library.security_check_context_raw.argtypes = [ctypes.c_char_p]
    observed_sid = (process / 'attr/current').read_text().strip().rstrip('\0')
    unconfined_sid = lifecycle_label('selinux')
    guest.require(observed_sid == MANAGER_SID, 'kiosk-bootstrap:manager-policy-role')
    guest.require(unconfined_sid.split(':', 3)[2] == 'unconfined_t' and
                  library.security_check_context_raw(unconfined_sid.encode()) == 0,
                  'kiosk-bootstrap:unconfined-control-context')
    checks = [(observed_sid, kind, permission) for kind, permissions in (
        ('capability', ('sys_admin', 'sys_ptrace')),
        ('cap_userns', ('sys_admin',)), ('user_namespace', ('create',)),
        ('process', ('setcurrent', 'setexec', 'dyntransition')))
        for permission in permissions]
    checks.extend((target, 'process', permission) for target in (
        unconfined_sid, caller_identity('systemd-user')[0])
        for permission in ('transition', 'dyntransition'))
    fscontext = 'system_u:object_r:tmpfs_t:s0'
    guest.require(source['mounts']['/usr']['filesystem'] == 'tmpfs' and any(
        option in ('fscontext=' + fscontext, 'fscontext="' + fscontext + '"')
        for option in source['mounts']['/usr']['superoptions']),
        'kiosk-bootstrap:manager-filesystem-context')
    checks.extend((fscontext, 'filesystem', permission) for permission in ('mount', 'remount', 'unmount'))
    root = process / 'root'
    directory_sid = os.getxattr(root / 'usr', 'security.selinux').rstrip(b'\0').decode()
    checks.append((directory_sid, 'dir', 'mounton'))
    native = [(path, row) for path, row in source['sources'].items()
              if row['class'] == 'native' and row['role'] in ('manager', 'executor', 'library')]
    guest.require({'manager', 'executor', 'library'} <= {row['role'] for path, row in native},
                  'kiosk-bootstrap:manager-policy-native-inputs')
    for path, row in native:
        sid = os.getxattr(root / path.lstrip('/'), 'security.selinux').rstrip(b'\0').decode()
        checks.extend((sid, 'file', permission) for permission in
                      ('mounton', 'write', 'append', 'create', 'relabelfrom', 'relabelto'))
        if row['role'] in ('manager', 'executor'):
            host_sid = os.getxattr(path, 'security.selinux').rstrip(b'\0').decode()
            checks.append((host_sid, 'file', 'execute_no_trans'))
    rows = []
    for target, kind, permission in sorted(set(checks)):
        guest.require(library.security_check_context_raw(target.encode()) == 0,
                      'kiosk-bootstrap:invalid-policy-query-context')
        cls = library.string_to_security_class(kind.encode())
        perm = library.string_to_av_perm(cls, permission.encode())
        decision = Decision()
        status = library.security_compute_av_flags_raw(observed_sid.encode(), target.encode(),
                                                       cls, perm, ctypes.byref(decision))
        row = {'source': observed_sid, 'target': target, 'class': kind, 'permission': permission,
               'status': status, 'allowed': decision.allowed, 'flags': decision.flags}
        rows.append(row)
        record('onpc.kiosk.bootstrap.manager-policy', json.dumps(rows, sort_keys=True))
        guest.require(cls and perm and status == 0 and not decision.flags & 1 and
                      not decision.allowed & perm, 'kiosk-bootstrap:manager-policy-authority:' + permission)


def bootstrap_pam_witness(account, directory, command, record, *, service='gdm-password', manager=None):
    """Hold only our PAM child, then its exact ELF on a full stdout pipe.

    Blocking stdout preserves a live post-exec object without ptrace, a signal,
    vendor mutation, replacement ELF, or extra policy. Draining releases it.
    """
    backend = json.loads(Path('/usr/share/oh-no-parent-control/confinement/config.json').read_text())['backend']
    descriptors, workers = set(), {}
    child = pidfd = observed_fd = None
    reaped = False
    try:
        def pipe():
            pair = os.pipe2(os.O_CLOEXEC)
            descriptors.update(pair)
            return pair
        def close(fd):
            os.close(fd)
            descriptors.remove(fd)
        events_read, events_write = pipe()
        release_read, release_write = pipe()
        output_read, output_write = pipe()
        result_read, result_write = pipe()
        start_read, start_write = pipe()
        # Fill exactly the pipe's capacity. A native --version flush blocks
        # until the parent has independently pinned and inspected its ELF.
        capacity = fcntl.fcntl(output_write, fcntl.F_GETPIPE_SZ)
        guest.require(0 < capacity <= 1024 * 1024, 'kiosk-bootstrap:pipe-capacity')
        filler = b'P' * capacity
        guest.require(os.write(output_write, filler) == capacity, 'kiosk-bootstrap:pipe-fill')
        sentry = os.open('/dev/null', os.O_RDWR | os.O_CLOEXEC)
        descriptors.add(sentry)
        child = os.fork()
        if child == 0:
            try:
                for fd in (events_read, release_write, output_read, result_read, start_write):
                    os.close(fd)
                guest.require(os.read(start_read, 1) == b'B', 'kiosk-bootstrap:worker-not-pinned')
                os.close(start_read)
                if backend == 'selinux':
                    # Commands' sequence is process-local after fork. Keep
                    # this worker's caller captures in its own retained child
                    # directory rather than overwrite the parent's next file.
                    guest.require(guest.commands.directory is not None,
                                  'kiosk-bootstrap:command-evidence-unavailable')
                    guest.commands.directory = Path(tempfile.mkdtemp(
                        prefix='bootstrap-pam-', dir=guest.commands.directory))
                status, data = first_exec(account, directory, command, service=service,
                    witness={'events': events_write, 'release': release_read,
                             'output': output_write, 'sentry': sentry})
                os.write(result_write, json.dumps({'status': status, 'data': data.hex()}).encode())
                os._exit(0)
            except BaseException as error:
                detail = {'stage': 'pam-witness', 'type': type(error).__name__,
                          'errno': error.errno if isinstance(error, OSError) else None,
                          'category': str(error) if isinstance(error, guest.GuestError) else 'worker-failure'}
                os.write(2, (json.dumps(detail, sort_keys=True) + '\n').encode())
                os._exit(124)
        pidfd = os.pidfd_open(child)
        for fd in (events_write, release_read, output_write, result_write, sentry, start_read):
            close(fd)
        os.write(start_write, b'B')
        close(start_write)
        event = lifecycle_event(events_read)
        record('onpc.kiosk.bootstrap.' + service + '.' + Path(command[0]).name + '.admission',
               json.dumps(event, sort_keys=True))
        guest.require(set(event) == {'phase', 'pid', 'before', 'logger', 'logger_after'} and event['phase'] == 'admitted' and
                      type(event['pid']) is int and event['pid'] > 1,
                      'kiosk-bootstrap:admission-protocol')
        # Only a PID supplied by this direct child's private channel can be
        # observed. It is never signalled; the owned wrapper reaps it.
        observed = PROC / str(event['pid'])
        observed_fd = os.pidfd_open(event['pid'])
        before, after = event['before'], bootstrap_descriptors(observed)
        try:
            logger_endpoint = bootstrap_logger_endpoint(Path('/dev/log'))
        except (OSError, guest.GuestError) as error:
            logger_endpoint = {'error': type(error).__name__, 'errno': getattr(error, 'errno', None),
                               'category': str(error)[:128] if isinstance(error, guest.GuestError) else 'endpoint-probe'}
        record('onpc.kiosk.bootstrap.' + service + '.' + Path(command[0]).name + '.descriptors',
               json.dumps({'before': before, 'after': after, 'logger_before': event['logger'],
                           'logger_after': event['logger_after'], 'logger_endpoint': logger_endpoint}, sort_keys=True))
        bootstrap_logger_transition(event['logger'], event['logger_after'], before, after)
        record('onpc.kiosk.bootstrap.' + service + '.' + Path(command[0]).name + '.logger',
               json.dumps({'before': event['logger'], 'after': event['logger_after']}, sort_keys=True))
        expected = ('onpc-kiosk-manager (enforce)' if backend == 'apparmor' else
                    'system_u:system_r:onpc_kiosk_manager_pam_t:s0') if service == 'systemd-user' else (
                    'onpc-kiosk-gate (enforce)' if backend == 'apparmor' else
                    'system_u:system_r:onpc_kiosk_gate_t:s0')
        attribute = 'attr/apparmor/current' if backend == 'apparmor' else 'attr/current'
        current_expected = caller_identity(service)[0] if backend == 'selinux' and service == 'gdm-password' else expected
        guest.require((observed / attribute).read_text().strip().rstrip('\0') == current_expected and
                      not exited(observed_fd), 'kiosk-bootstrap:admitted-role')
        if backend == 'selinux' and service == 'gdm-password':
            guest.require((observed / 'attr/exec').read_text().strip().rstrip('\0') == expected,
                          'kiosk-bootstrap:pending-gate-role')
        view = bootstrap_view(observed, source=manager)
        record('onpc.kiosk.bootstrap.' + service + '.' + Path(command[0]).name + '.view',
               json.dumps(view, sort_keys=True))
        os.write(release_write, b'E')
        if service == 'systemd-user':
            restrictions = lifecycle_event(events_read)
            guest.require(set(restrictions) == {'phase', 'result'} and restrictions['phase'] == 'restrictions',
                          'kiosk-bootstrap:restriction-protocol')
            record('onpc.kiosk.bootstrap.' + Path(command[0]).name + '.restrictions',
                   json.dumps({'role': current_expected, 'operations': restrictions['result']}, sort_keys=True))
        if service in ('systemd-user', 'gdm-password'):
            target = Path(command[0])
            deadline = time.monotonic() + 10
            while True:
                guest.require(not exited(observed_fd), 'kiosk-bootstrap:exec-exited-before-observation')
                actual = (observed / 'exe').stat()
                selected = (observed / 'root' / target.relative_to('/')).stat()
                if (actual.st_dev, actual.st_ino) == (selected.st_dev, selected.st_ino):
                    break
                guest.require(time.monotonic() < deadline, 'kiosk-bootstrap:exec-observation-timeout')
                time.sleep(0.01)
            actual = bootstrap_process(observed, account, backend,
                                       label=expected if service == 'gdm-password' else None,
                                       expected_groups=(), record=record)
            guest.require(actual['identity'][2] == (str(account.pw_uid),) * 4,
                          'kiosk-bootstrap:exec-credentials')
            record('onpc.kiosk.bootstrap.entrypoint.' + target.name + '.' + service,
                   json.dumps(actual, sort_keys=True))
        # The gate's --help is short-lived; its pre-exec view above, successful
        # allowed final entry and completed-record comparison prove admission.
        received = bytearray()
        os.set_blocking(output_read, False)
        deadline = time.monotonic() + 75
        while not exited(pidfd):
            try:
                received.extend(os.read(output_read, 65536))
            except BlockingIOError:
                pass
            guest.require(len(received) <= capacity + 65536 and time.monotonic() < deadline,
                          'kiosk-bootstrap:output-timeout')
            time.sleep(0.01)
        while True:
            chunk = os.read(output_read, 65536)
            if not chunk:
                break
            received.extend(chunk)
            guest.require(len(received) <= capacity + 65536, 'kiosk-bootstrap:output-size')
        _, status = os.waitpid(child, 0)
        reaped = True
        result = json.loads(os.read(result_read, 4096))
        record('onpc.kiosk.bootstrap.' + service + '.' + Path(command[0]).name + '.result',
               json.dumps(result, sort_keys=True))
        guest.require(os.waitstatus_to_exitcode(status) == 0 and result == {'status': 0, 'data': ''} and
                      bytes(received[:capacity]) == filler and
                      (service != 'systemd-user' or b'systemd ' in received[capacity:]),
                      'kiosk-bootstrap:positive-exec')
        return view
    finally:
        # Close the release/stdio writers first. The wrapper's bounded
        # first_exec owner then reaps its child before the wrapper is reaped.
        saved_result = result_read if 'result_read' in locals() and result_read in descriptors else None
        for fd in tuple(descriptors):
            if fd != saved_result:
                close(fd)
        if child is not None and not reaped:
            try:
                if pidfd is None:
                    # Our direct unreaped child cannot have its PID reused.
                    os.kill(child, signal.SIGKILL)
                elif not exited(pidfd):
                    poll = select.poll()
                    poll.register(pidfd, select.POLLIN)
                    if not poll.poll(80000):
                        signal.pidfd_send_signal(pidfd, signal.SIGKILL)
            except ProcessLookupError:
                pass
            os.waitpid(child, 0)
        if saved_result is not None:
            try:
                os.set_blocking(saved_result, False)
                detail = os.read(saved_result, 4097)
                if detail:
                    record('onpc.kiosk.bootstrap.' + service + '.' + Path(command[0]).name + '.failure-result',
                           detail[:4096].decode(errors='replace'))
            except BlockingIOError:
                pass
            finally:
                close(saved_result)
        if observed_fd is not None:
            os.close(observed_fd)
        if pidfd is not None:
            os.close(pidfd)


def bootstrap_reexec(account, unit, backend, record, *, retained_view=False):
    """The supported owned notify-reload transaction; no package mutations."""
    options = {'retained_view': True} if retained_view else {}
    boundary = manager_boundary(account, unit, backend, **options)
    guest.require(guest.run(['systemctl', 'show', '--value', '--property=Type', unit]) == 'notify-reload' and
                  guest.run(['systemctl', 'show', '--value', '--property=ReloadSignal', unit]) == '59',
                  'kiosk-confinement:unsupported-manager-reexec-protocol')
    guest.run(['systemctl', 'reload', unit], timeout=75)
    guest.require(manager_boundary(account, unit, backend, **options) == boundary,
                  'kiosk-confinement:reexec-changed-manager-boundary')
    guest.require(b'systemd ' in user_command(account, ['/usr/bin/systemd-run', '--user', '--wait',
        '--collect', '--pipe', '--unit=onpc-confinement-after-reexec', '/usr/bin/systemctl', '--version']),
        'kiosk-confinement:service-after-reexec')
    user_command(account, ['/bin/sh', '-c', 'exit 0'])
    require_service_denial(account, backend, 'onpc-confinement-after-reexec-denied.service',
                           ['/bin/sh', '-c', 'exit 0'], record)
    guest.require(manager_boundary(account, unit, backend, **options) == boundary,
                  'kiosk-confinement:reexec-changed-manager-boundary')
    record('onpc.kiosk.manager-boundary-after-reexec', json.dumps(boundary, sort_keys=True))


def bootstrap_service_entrypoint(account, backend, executable, source, record, *, pam_route=False,
                                 manager_pid_value=None):
    """Observe the selected copied ELF on the real manager-to-manager route."""
    unit = 'onpc-bootstrap-' + Path(executable).name + '.service'
    if not pam_route:
        inactive = user_command(account, ['/usr/bin/systemctl', '--user', 'show', unit,
            '--property=InvocationID,ActiveState'], check=False).decode()
        guest.require('InvocationID=\n' in inactive and 'ActiveState=inactive\n' in inactive,
                      'kiosk-bootstrap:entrypoint-unit-already-active')
    read_fd, write_fd = os.pipe2(os.O_CLOEXEC)
    start_read, start_write = os.pipe2(os.O_CLOEXEC)
    child = pidfd = native_fd = None
    reaped = False
    invocation = None
    namespace = None
    try:
        if pam_route:
            guest.require(backend == 'apparmor', 'kiosk-bootstrap:unsupported-extra-pam-route')
            guest.require(type(manager_pid_value) is int and manager_pid_value > 1,
                          'kiosk-bootstrap:pam-route-manager-not-pinned')
            manager = PROC / str(manager_pid_value)
            namespace = os.open(manager / 'ns/mnt', os.O_RDONLY | os.O_CLOEXEC)
            guest.require(manager_pid(f'user@{account.pw_uid}.service') == manager_pid_value and
                          (manager / 'root/usr/share/oh-no-parent-control/confinement/retained-view').read_text().split('\t')[-1].strip() ==
                          source['view'], 'kiosk-bootstrap:pam-route-manager-view')
            apparmor = ctypes.CDLL('libapparmor.so.1', use_errno=True)
            apparmor.aa_change_profile.argtypes = [ctypes.c_char_p]
            library = ctypes.CDLL(None, use_errno=True)
        capacity = fcntl.fcntl(write_fd, fcntl.F_GETPIPE_SZ)
        guest.require(0 < capacity <= 1024 * 1024 and
                      os.write(write_fd, b'P' * capacity) == capacity, 'kiosk-bootstrap:pipe-fill')
        child = os.fork()
        if child == 0:
            try:
                os.close(read_fd)
                os.close(start_write)
                guest.require(os.read(start_read, 1) == b'B', 'kiosk-bootstrap:worker-not-pinned')
                os.close(start_read)
                os.dup2(write_fd, 1)
                os.close(write_fd)
                if pam_route:
                    guest.require(library.setns(namespace, 0x00020000) == 0,
                                  'kiosk-bootstrap:pam-route-setns')
                    os.close(namespace)
                    selected = Path(executable).stat()
                    guest.require([selected.st_dev, selected.st_ino] ==
                                  source['sources'][executable]['identity'][:2],
                                  'kiosk-bootstrap:pam-route-not-selected-copy')
                    guest.require(apparmor.aa_change_profile(b'onpc-kiosk-manager-pam') == 0,
                                  'kiosk-bootstrap:pam-route-profile')
                    os.setgroups([])
                    os.setgid(account.pw_gid)
                    os.setuid(account.pw_uid)
                    os.execve(executable, [executable, '--version'], {'PATH': '/usr/bin:/bin', 'LANG': 'C'})
                arguments = ['/usr/bin/setpriv', '--reuid', str(account.pw_uid),
                    '--regid', str(account.pw_gid), '--clear-groups', '/usr/bin/env', '-i', *ENV,
                    f'XDG_RUNTIME_DIR=/run/user/{account.pw_uid}',
                    f'DBUS_SESSION_BUS_ADDRESS=unix:path=/run/user/{account.pw_uid}/bus',
                    '/usr/bin/systemd-run', '--user', '--wait', '--pipe', '--unit=' + unit,
                    executable, '--version']
                os.execve(arguments[0], arguments, dict(os.environ))
            except BaseException as error:
                os.write(2, (json.dumps({'stage': 'entrypoint', 'type': type(error).__name__,
                    'errno': error.errno if isinstance(error, OSError) else None,
                    'category': str(error) if isinstance(error, guest.GuestError) else 'fixture-failure'}) + '\n').encode())
                os._exit(124)
        pidfd = os.pidfd_open(child)
        os.close(start_read)
        start_read = None
        os.write(start_write, b'B')
        os.close(start_write)
        start_write = None
        os.close(write_fd)
        write_fd = None
        if pam_route:
            process = PROC / str(child)
        else:
            deadline = time.monotonic() + 15
            while True:
                properties = dict(line.split('=', 1) for line in user_command(account,
                    ['/usr/bin/systemctl', '--user', 'show', unit,
                     '--property=InvocationID,ExecMainPID,ActiveState'], check=False).decode().splitlines())
                if properties.get('ExecMainPID', '0') != '0':
                    invocation = properties['InvocationID']
                    break
                guest.require(not exited(pidfd) and time.monotonic() < deadline,
                              'kiosk-bootstrap:service-entrypoint-not-started')
                time.sleep(0.025)
            process = PROC / properties['ExecMainPID']
        native_fd = os.pidfd_open(int(process.name))
        deadline = time.monotonic() + 10
        while bootstrap_object(process / 'exe', follow=True)[:2] != source['sources'][executable]['identity'][:2]:
            guest.require(not exited(native_fd) and time.monotonic() < deadline,
                          'kiosk-bootstrap:service-entrypoint-not-selected-copy')
            time.sleep(0.01)
        observed = bootstrap_process(process, account, backend,
                                     expected_groups=() if pam_route else None, record=record)
        guest.require(bootstrap_view(process, source=source)['usr'] == source['usr'] and
                      not exited(native_fd), 'kiosk-bootstrap:service-entrypoint-view')
        record('onpc.kiosk.bootstrap.entrypoint.' + Path(executable).name +
               ('.apparmor-manager-pam' if pam_route else '.manager'),
               json.dumps({'invocation': invocation, 'process': observed}, sort_keys=True))
        os.set_blocking(read_fd, False)
        output = bytearray()
        deadline = time.monotonic() + 75
        while not exited(pidfd):
            try:
                output.extend(os.read(read_fd, 65536))
            except BlockingIOError:
                pass
            guest.require(time.monotonic() < deadline and len(output) <= capacity + 65536,
                          'kiosk-bootstrap:service-entrypoint-output')
            time.sleep(0.01)
        while True:
            chunk = os.read(read_fd, 65536)
            if not chunk:
                break
            output.extend(chunk)
            guest.require(len(output) <= capacity + 65536, 'kiosk-bootstrap:service-entrypoint-output')
        _, status = os.waitpid(child, 0)
        reaped = True
        guest.require(os.waitstatus_to_exitcode(status) == 0 and output[:capacity] == b'P' * capacity and
                      b'systemd ' in output[capacity:], 'kiosk-bootstrap:service-entrypoint-exit')
    finally:
        for fd in (read_fd, write_fd, start_read, start_write):
            if fd is not None:
                os.close(fd)
        if child is not None and not reaped:
            try:
                if pidfd is None:
                    os.kill(child, signal.SIGKILL)
                elif not exited(pidfd):
                    signal.pidfd_send_signal(pidfd, signal.SIGKILL)
            except ProcessLookupError:
                pass
            os.waitpid(child, 0)
        try:
            if invocation:
                current = dict(line.split('=', 1) for line in user_command(account,
                    ['/usr/bin/systemctl', '--user', 'show', unit,
                     '--property=InvocationID,LoadState,ActiveState,ExecMainPID'], check=False).decode().splitlines())
                if current.get('InvocationID') == invocation:
                    # A failed observation can leave the owned blocked native
                    # process alive. Never stop a replacement invocation.
                    user_command(account, ['/usr/bin/systemctl', '--user', 'stop', unit])
                    user_command(account, ['/usr/bin/systemctl', '--user', 'reset-failed', unit], check=False)
                else:
                    guest.require(current.get('InvocationID', '') == '' and
                                  current.get('LoadState') == 'not-found' and
                                  current.get('ActiveState') == 'inactive' and
                                  current.get('ExecMainPID') == '0' and native_fd is not None and exited(native_fd),
                                  'kiosk-bootstrap:entrypoint-unit-replaced')
        finally:
            for fd in (native_fd, pidfd, namespace):
                if fd is not None:
                    os.close(fd)


def bootstrap_start_manager(unit, backend, record):
    """Preserve the first start failure and bounded native cause before restore."""
    try:
        guest.run(['systemctl', 'start', unit], timeout=75)
    except BaseException:
        try:
            for name, command in (
                ('unit', ['systemctl', 'show', unit,
                          '--property=InvocationID,MainPID,ActiveState,SubState,Result,ExecMainStatus']),
                ('journal', ['journalctl', '--no-pager', '--utc', '-b', '-u', unit,
                             '-n', '100', '-o', 'short-precise']),
            ):
                try:
                    output = guest.run(command, timeout=10)
                    record('onpc.kiosk.bootstrap.start-failure.' + name, output[-65536:])
                except Exception:
                    record('onpc.kiosk.bootstrap.start-failure.' + name, 'diagnostic-unavailable')
            from system_kiosk_platform import kernel_audit
            record('onpc.kiosk.bootstrap.start-failure.kernel', kernel_audit(backend)[-65536:])
        except Exception:
            # Diagnostic collection never replaces the original start error.
            pass
        raise


def verify_bootstrap_permissions(record):
    """Finite fresh/retained admission with the exact loaded production policy."""
    marker = guest.guard()
    guest.enable_diagnostics()
    payload = Path('/usr/share/oh-no-parent-control/confinement')
    config = json.loads((payload / 'config.json').read_text())
    backend = config['backend']
    preparation = runpy.run_path('/usr/libexec/oh-no-parent-control-kiosk-confinement')
    preparation['enforcing'](config)
    policy = payload / ('onpc-kiosk.apparmor' if backend == 'apparmor' else 'onpc-kiosk.cil')
    state = Path('/var/lib/oh-no-parent-control/kiosk-confinement.json')
    attestation = json.loads(state.read_text())
    guest.require(attestation['backend'] == backend and
                  attestation['loaded_config_sha256'] == guest.sha(payload / 'config.json') and
                  attestation['loaded_policy_sha256'] == guest.sha(policy), 'kiosk-bootstrap:attestation')
    original = {'policy': guest.sha(policy), 'config': guest.sha(payload / 'config.json'),
                'attestation': bootstrap_object(state) + [guest.sha(state)], 'pam': guest.pam_service_state()}
    record('onpc.kiosk.bootstrap.candidate', json.dumps({
        'binding': {key: marker[key] for key in ('run', 'package_sha256', 'selected_inputs_sha256')},
        'boot': Path('/proc/sys/kernel/random/boot_id').read_text().strip(),
        'backend': backend, 'state': original, 'attestation': attestation}, sort_keys=True))
    record_native_packages(config, record)
    account = pwd.getpwnam('oh-no-parent-control')
    unit = f'user@{account.pw_uid}.service'
    wait_kiosk_inactive(account)
    bootstrap_start_manager(unit, backend, record)
    invocation = guest.run(['systemctl', 'show', '--value', '--property=InvocationID', unit])
    pidfd = None
    try:
        guest.require(re.fullmatch(r'[a-f0-9]{32}', invocation), 'kiosk-bootstrap:manager-invocation')
        boundary = manager_boundary(account, unit, backend, retained_view=True)
        pidfd = os.pidfd_open(boundary['pid'])
        expected = {**boundary, 'invocation': invocation}
        process = PROC / str(boundary['pid'])
        identity = bootstrap_process(process, account, backend, record=record)
        cgroup = guest.run(['systemctl', 'show', '--value', '--property=ControlGroup', unit])
        actual_cgroup = identity['cgroup'].strip().removeprefix('0::')
        guest.require(cgroup.startswith('/') and (actual_cgroup == cgroup or
                      actual_cgroup.startswith(cgroup + '/')), 'kiosk-bootstrap:manager-cgroup')
        source = bootstrap_view(process)
        bootstrap_manager_policy(backend, process, source, record)
        selected = source['sources']['/usr/lib/systemd/systemd']['identity'][:2]
        guest.require(bootstrap_object(process / 'exe', follow=True)[:2] == selected,
                      'kiosk-bootstrap:manager-not-selected-copy')
        record('onpc.kiosk.bootstrap.manager', json.dumps({'invocation': invocation,
            'process': identity, 'view': source}, sort_keys=True))
        with tempfile.TemporaryDirectory(prefix='kiosk-bootstrap-', dir=guest.PAYLOAD) as temporary:
            directory = Path(temporary)
            for executable in ('/usr/lib/systemd/systemd', '/usr/lib/systemd/systemd-executor'):
                bootstrap_pam_witness(account, directory, [executable, '--version'], record,
                                      service='systemd-user')
                bootstrap_manager_unchanged(account, unit, backend, expected, pidfd)
                bootstrap_service_entrypoint(account, backend, executable, source, record)
                bootstrap_manager_unchanged(account, unit, backend, expected, pidfd)
                if backend == 'apparmor':
                    bootstrap_service_entrypoint(account, backend, executable, source, record,
                                                 pam_route=True, manager_pid_value=boundary['pid'])
                    bootstrap_manager_unchanged(account, unit, backend, expected, pidfd)
            bootstrap_pam_witness(account, directory, ['/usr/libexec/gdm-wayland-session', '--help'],
                                  record, manager=source)
            bootstrap_manager_unchanged(account, unit, backend, expected, pidfd)
            guest.require(bootstrap_view(process) == source, 'kiosk-bootstrap:gate-changed-manager-dentries')
        bootstrap_reexec(account, unit, backend, record, retained_view=True)
        bootstrap_manager_unchanged(account, unit, backend, expected, pidfd)
        guest.require(bootstrap_view(process) == source and
                      bootstrap_process(process, account, backend, record=record) == identity,
                      'kiosk-bootstrap:reexec-source-or-process-changed')
        for setting in ('AppArmorProfile=unconfined',) if backend == 'apparmor' else (
                'SELinuxContext=' + lifecycle_label('selinux'),):
            require_service_denial(account, backend, 'onpc-bootstrap-unconfined.service',
                                   ['/usr/bin/systemctl', '--version'], record, setting=setting)
        record('onpc.kiosk.bootstrap.production-admission-reexec', True)
    finally:
        try:
            guest.require(guest.run(['systemctl', 'show', '--value', '--property=InvocationID', unit]) == invocation,
                          'kiosk-bootstrap:manager-replaced')
            guest.run(['systemctl', 'stop', unit], timeout=75)
        finally:
            if pidfd is not None:
                os.close(pidfd)
            preparation['enforcing'](config)
            guest.require(original == {'policy': guest.sha(policy), 'config': guest.sha(payload / 'config.json'),
                'attestation': bootstrap_object(state) + [guest.sha(state)], 'pam': guest.pam_service_state()},
                'kiosk-bootstrap:policy-or-pam-changed')
            record('onpc.kiosk.bootstrap.policy-pam-unchanged', True)


def verify_updates(account, unit, backend, record):
    """Model the unlink/replacement operations performed by distro packages.

    Root scenario mutations are restored byte-for-byte with original labels;
    the user manager must keep its independent executable/library dentries.
    """
    @contextmanager
    def replacement(program):
        original = program.read_bytes()
        with tempfile.TemporaryDirectory(prefix='.onpc-confinement-update-', dir=program.parent) as temporary:
            backup = Path(temporary) / 'original'
            candidate = Path(temporary) / 'replacement'
            shutil.copy2(program, candidate)
            with candidate.open('ab') as stream:
                stream.write(b'\0onpc-owned-package-update-probe\0')
            program.rename(backup)
            try:
                candidate.rename(program)
                yield hashlib.sha256(original).digest()
            finally:
                if program.exists():
                    program.unlink()
                backup.rename(program)

    boundary = manager_boundary(account, unit, backend)
    library_directory = Path('/usr/lib64/systemd' if backend == 'selinux'
                             else '/usr/lib/x86_64-linux-gnu/systemd')
    libraries = sorted(library_directory.glob('libsystemd-*.so'))
    guest.require(bool(libraries), 'kiosk-confinement:systemd-libraries-missing')
    with ExitStack() as mutations:
        expected = {program: mutations.enter_context(replacement(program))
                    for program in [Path('/usr/bin/systemctl'), *libraries]}
        def pinned_bytes():
            root = Path(f'/proc/{manager_pid(unit)}/root')
            for program, digest in expected.items():
                guest.require(hashlib.sha256((root / str(program).lstrip('/')).read_bytes()).digest() == digest,
                              'kiosk-confinement:package-replacement-detached-mount')
                guest.require(hashlib.sha256(program.read_bytes()).digest() != digest,
                              'kiosk-confinement:update-not-applied')
        pinned_bytes()
        bootstrap_reexec(account, unit, backend, record)
        pinned_bytes()
        guest.require(manager_boundary(account, unit, backend) == boundary,
                      'kiosk-confinement:reexec-changed-manager-boundary')
        record('onpc.kiosk.executable-library-replacement-and-reexec', True)
    plugin_directory = Path('/usr/lib64/gstreamer-1.0' if backend == 'selinux'
                            else '/usr/lib/x86_64-linux-gnu/gstreamer-1.0')
    before = plugin_directory / 'libgstpython.so'
    existed = before.exists()
    previous = before.read_bytes() if existed else None
    with tempfile.TemporaryDirectory(prefix='.onpc-confinement-plugin-', dir=plugin_directory.parent) as temporary:
        backup = Path(temporary) / 'original'
        plugin_directory.rename(backup)
        plugin_directory.mkdir(mode=0o755)
        try:
            (plugin_directory / 'libgstpython.so').write_bytes(b'owned-update-probe')
            in_manager = Path(f'/proc/{manager_pid(unit)}/root') / str(before).lstrip('/')
            guest.require(in_manager.exists() == existed and
                          (not existed or in_manager.read_bytes() == previous),
                          'kiosk-confinement:plugin-parent-replacement-exposed-library')
            record('onpc.kiosk.plugin-parent-replacement', True)
        finally:
            (plugin_directory / 'libgstpython.so').unlink()
            plugin_directory.rmdir()
            backup.rename(plugin_directory)
    guest.require(manager_boundary(account, unit, backend) == boundary,
                  'kiosk-confinement:updates-changed-manager-boundary')


@contextmanager
def appended_probe(path, suffix):
    """Restore the opened fixture inode, including package-verified timestamps."""
    with os.fdopen(os.open(path, os.O_RDWR | os.O_NOFOLLOW), 'r+b') as stream:
        before = os.fstat(stream.fileno())
        original = stream.read()
        try:
            stream.write(suffix)
            stream.flush()
            yield
        finally:
            stream.seek(0)
            stream.write(original)
            stream.truncate()
            stream.flush()
            os.utime(stream.fileno(), ns=(before.st_atime_ns, before.st_mtime_ns))


@contextmanager
def untrusted_alias_owner(path, uid):
    """Change only one real distro alias owner; refuse any substituted entry."""
    guest.guard()
    guest.require(type(uid) is int and uid > 0, 'kiosk-alias:fixture-uid')
    parent = os.open(path.parent, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW | os.O_CLOEXEC)
    try:
        directory = os.fstat(parent)
        guest.require(directory.st_uid == 0 and not directory.st_mode & 0o022,
                      'kiosk-alias:unsafe-parent')
        original = os.stat(path.name, dir_fd=parent, follow_symlinks=False)
        guest.require(stat.S_ISLNK(original.st_mode) and original.st_uid == original.st_gid == 0 and
                      original.st_nlink == 1, 'kiosk-alias:unsafe-original')
        target = os.readlink(path.name, dir_fd=parent)

        def unchanged(*owners):
            actual = os.stat(path.name, dir_fd=parent, follow_symlinks=False)
            guest.require(all(getattr(actual, field) == getattr(original, field) for field in
                          ('st_dev', 'st_ino', 'st_mode', 'st_gid', 'st_nlink', 'st_mtime_ns')) and
                          actual.st_uid in owners and os.readlink(path.name, dir_fd=parent) == target,
                          'kiosk-alias:fixture-replaced')

        unchanged(original.st_uid)
        try:
            os.chown(path.name, uid, original.st_gid, dir_fd=parent, follow_symlinks=False)
            unchanged(uid)
            yield
        finally:
            # A failed chown may leave the original owner. Accept only our two
            # attributable states before restoring the same pinned parent entry.
            unchanged(original.st_uid, uid)
            os.chown(path.name, original.st_uid, original.st_gid,
                     dir_fd=parent, follow_symlinks=False)
            unchanged(original.st_uid)
            os.utime(path.name, ns=(original.st_atime_ns, original.st_mtime_ns),
                     dir_fd=parent, follow_symlinks=False)
            # Reading the link after utime can advance its atime again.
            restored = os.stat(path.name, dir_fd=parent, follow_symlinks=False)
            guest.require(all(getattr(restored, field) == getattr(original, field) for field in
                          ('st_dev', 'st_ino', 'st_mode', 'st_uid', 'st_gid', 'st_nlink',
                           'st_atime_ns', 'st_mtime_ns')), 'kiosk-alias:restoration-changed')
    finally:
        os.close(parent)


def verify_payload_attestation_faults(account, directory, policy, record):
    """Neither a fresh manager nor boot loading may attest changed payload bytes."""
    from system_removal import admission_removal_state, private_recovery_record
    integration = '/usr/libexec/oh-no-parent-control-kiosk-confinement-integration'
    state = Path('/var/lib/oh-no-parent-control/kiosk-confinement.json')
    config = json.loads((policy.parent / 'config.json').read_bytes())
    preparation = runpy.run_path('/usr/libexec/oh-no-parent-control-kiosk-confinement')
    command = ['/usr/lib/systemd/systemd', '--version']
    status, data = first_exec(account, directory, command, service='systemd-user')
    guest.require(status == 0 and not data, 'kiosk-confinement:payload-attestation-positive')
    preparation['enforcing'](config)
    for name, path, category, key in (
        ('configuration', policy.parent / 'config.json', 'unloaded-configuration-generation-admitted',
         'onpc.kiosk.unloaded-configuration-generation-denied'),
        ('policy', policy, 'unloaded-policy-generation-admitted',
         'onpc.kiosk.unloaded-policy-generation-denied'),
    ):
        guest.require(manager_pid(f'user@{account.pw_uid}.service') == 0,
                      'kiosk-confinement:payload-drift-manager-active')
        ownership = admission_removal_state()
        attestation = private_recovery_record(state)
        with appended_probe(path, b'\n'):
            # No user manager exists: systemd-user must independently reject
            # config-only drift rather than relying on another manager's view.
            status, data = first_exec(account, directory, command, service='systemd-user', armed=False)
            guest.require(status == 125 and json.loads(data)['pam'] != 0,
                          'kiosk-confinement:' + category)
            record(key, True)
            output = guest.commands.run([integration, 'load'], timeout=90,
                                        check=False, merge_stderr=True)
            status = guest.commands.last_returncode
            record('onpc.kiosk.' + name + '-drift-loader-result', json.dumps({
                'status': status, 'output': output.decode(errors='replace')}, sort_keys=True))
            guest.require(type(status) is int and status != 0 and
                          re.findall(rb'(?:^|\s)reason=([^;\s]+)', output) ==
                          [b'policy-load-incomplete-reconfigure-required'],
                          'kiosk-confinement:payload-drift-boot-reattested')
            guest.require(admission_removal_state() == ownership and
                          private_recovery_record(state) == attestation,
                          'kiosk-confinement:payload-drift-ownership-changed')
            preparation['enforcing'](config)
            record('onpc.kiosk.' + name + '-drift-loader-refused', True)
        status, data = first_exec(account, directory, command, service='systemd-user')
        guest.require(status == 0 and not data,
                      'kiosk-confinement:payload-attestation-recovery')
        guest.require(admission_removal_state() == ownership and
                      private_recovery_record(state) == attestation,
                      'kiosk-confinement:payload-drift-recovery-changed-ownership')
        preparation['enforcing'](config)
        record('onpc.kiosk.' + name + '-attestation-recovered', True)


def verify_admission_faults(account, directory, backend, record):
    command = ['/usr/lib/systemd/systemd', '--version']
    status, data = first_exec(account, directory, command, service='systemd-user')
    guest.require(status == 0 and not data, 'kiosk-confinement:manager-first-exec-positive')
    # Root-owned ELF bytes do not make a user-owned distribution alias trusted.
    # Preserve its real target and test the installed PAM preparation path,
    # rather than substituting the preparer's filesystem checks in the worker.
    with untrusted_alias_owner(Path('/usr/bin/python3'), account.pw_uid):
        status, data = first_exec(account, directory, command, service='systemd-user', armed=False)
        guest.require(status == 125 and json.loads(data)['pam'] != 0,
                      'kiosk-confinement:untrusted-executable-alias-admitted')
        record('onpc.kiosk.user-owned-executable-alias-denied', True)
    status, data = first_exec(account, directory, command, service='systemd-user')
    guest.require(status == 0 and not data, 'kiosk-confinement:executable-alias-recovery')
    record('onpc.kiosk.restored-executable-alias-admitted', True)
    for name in ('/etc/pam.d/gdm-password', '/usr/lib/pam.d/systemd-user'):
        with appended_probe(Path(name), b'\n# owned integration-drift probe\n'):
            status, data = first_exec(account, directory, command, service='systemd-user', armed=False)
            guest.require(status == 125 and json.loads(data)['pam'] != 0,
                          'kiosk-confinement:drift-admitted')
    record('onpc.kiosk.pam-vendor-drift-denied', True)
    policy = Path('/usr/share/oh-no-parent-control/confinement') / (
        'onpc-kiosk.apparmor' if backend == 'apparmor' else 'onpc-kiosk.cil')
    verify_payload_attestation_faults(account, directory, policy, record)
    if backend == 'apparmor':
        restore = ['/usr/sbin/apparmor_parser', '-r', str(policy)]
        mutations = [(['/usr/sbin/apparmor_parser', '-C', '-r', str(policy)], restore),
                     (['/usr/sbin/apparmor_parser', '-R', str(policy)], restore)]
    else:
        mutations = [(['/usr/sbin/setenforce', '0'], ['/usr/sbin/setenforce', '1']),
            (['/usr/sbin/semanage', 'permissive', '-a', 'onpc_kiosk_app_t'],
             ['/usr/sbin/semanage', 'permissive', '-d', 'onpc_kiosk_app_t']),
            (['/usr/sbin/semodule', '-r', 'onpc-kiosk'],
             ['/usr/sbin/semodule', '-i', str(policy)])]
    for index, (mutation, restore) in enumerate(mutations):
        try:
            guest.run(mutation, timeout=60)
            expected = 'Permissive' if mutation == ['/usr/sbin/setenforce', '0'] else 'Enforcing'
            status, data = first_exec(account, directory, command, service='systemd-user',
                                      armed=False, expected_selinux=expected)
            guest.require(status == 125 and json.loads(data)['pam'] != 0,
                          'kiosk-confinement:unenforced-policy-admitted')
        finally:
            guest.run(restore, timeout=60)
        status, data = first_exec(account, directory, command, service='systemd-user')
        guest.require(status == 0 and not data, 'kiosk-confinement:policy-recovery')
        record('onpc.kiosk.unenforced-policy-denied.' + str(index), True)


def verify_namespace_guard(record):
    """Exercise real namespace open/init/close callbacks, outside UI acceptance."""
    from system_kiosk_scope import ordinary_accounts
    guest.guard()
    guest.enable_diagnostics()
    accounts = {'ordinary': pwd.getpwnam('root'), **ordinary_accounts(),
                'kiosk': pwd.getpwnam('oh-no-parent-control')}
    installed = runpy.run_path('/usr/libexec/oh-no-parent-control-kiosk-confinement-integration')
    namespace_directory = Path('/etc/security/namespace.d')
    guest.require(namespace_directory.is_dir(), 'kiosk-namespace:configuration-directory-missing')
    parent_namespace = os.readlink('/proc/self/ns/mnt')
    with tempfile.TemporaryDirectory(prefix='kiosk-namespace-', dir=guest.PAYLOAD) as temporary:
        directory = Path(temporary)
        poly = directory / 'poly'
        poly.mkdir(mode=0o700)
        original_poly = poly.stat()
        instances = directory / 'instances'
        instances.mkdir(mode=0)
        initialized = directory / 'initialized'
        script = directory / 'init'
        script.write_text('#!/bin/sh\nset -eu\nprintf namespace-init > ' + shlex.quote(str(initialized)) + '\n')
        script.chmod(0o700)
        service = directory / 'onpc-namespace-probe'
        # This synthetic service never changes its SELinux exec context.
        # pam_namespace documents use_current_context for exactly that case;
        # no production policy or caller transition is needed for the fixture.
        service.write_text('auth required pam_permit.so\n' + installed['guarded_sessions'](
            'session required pam_namespace.so unmount_on_close use_current_context\n') +
            'session required pam_permit.so\n')
        configuration = namespace_directory / (directory.name + '.conf')
        contents = (f'{poly} {instances}/ tmpdir:iscript={script} ~' +
                    ','.join(account.pw_name for account in accounts.values()) + '\n')
        with configuration.open('x') as stream:
            stream.write(contents)
        configuration.chmod(0o600)
        identity = configuration.stat()
        try:
            for role, account in accounts.items():
                kiosk = role == 'kiosk'
                read_fd, write_fd = os.pipe2(os.O_CLOEXEC)
                try:
                    child = os.fork()
                except BaseException:
                    os.close(read_fd)
                    os.close(write_fd)
                    raise
                if child == 0:
                    os.close(read_fd)
                    stage = 'start'
                    pam_status = None
                    try:
                        pam = ctypes.CDLL('libpam.so.0')
                        class Conversation(ctypes.Structure):
                            _fields_ = [('conv', ctypes.c_void_p), ('data', ctypes.c_void_p)]
                        pam.pam_start_confdir.argtypes = [ctypes.c_char_p, ctypes.c_char_p,
                            ctypes.POINTER(Conversation), ctypes.c_char_p, ctypes.POINTER(ctypes.c_void_p)]
                        for callback in ('pam_open_session', 'pam_close_session', 'pam_setcred', 'pam_end'):
                            getattr(pam, callback).argtypes = [ctypes.c_void_p, ctypes.c_int]
                        handle = ctypes.c_void_p()
                        conversation = Conversation()
                        user = account.pw_name.encode()
                        guest.require(pam.pam_start_confdir(service.name.encode(), user,
                            ctypes.byref(conversation), os.fsencode(directory), ctypes.byref(handle)) == 0,
                            'kiosk-namespace:pam-start')
                        stage = 'establish-credentials'
                        guest.require(pam.pam_setcred(handle, 2) == 0, 'kiosk-namespace:pam-setcred')
                        stage = 'open'
                        pam_status = pam.pam_open_session(handle, 0)
                        guest.require(pam_status == 0, 'kiosk-namespace:pam-open')
                        stage = 'namespace'
                        guest.require((os.readlink('/proc/self/ns/mnt') != parent_namespace) == (not kiosk),
                                      'kiosk-namespace:open-namespace')
                        stage = 'init'
                        guest.require(initialized.exists() == (not kiosk), 'kiosk-namespace:init-callback')
                        stage = 'instance'
                        guest.require(bool(list(instances.iterdir())) == (not kiosk),
                                      'kiosk-namespace:instance-created')
                        stage = 'close'
                        guest.require(pam.pam_close_session(handle, 0) == 0, 'kiosk-namespace:pam-close')
                        guest.require(not list(instances.iterdir()), 'kiosk-namespace:instance-not-cleaned')
                        current_poly = poly.stat()
                        guest.require((current_poly.st_dev, current_poly.st_ino) ==
                            (original_poly.st_dev, original_poly.st_ino), 'kiosk-namespace:close-mount')
                        stage = 'delete-credentials'
                        guest.require(pam.pam_setcred(handle, 4) == 0, 'kiosk-namespace:pam-delete-credentials')
                        guest.require(pam.pam_end(handle, 0) == 0, 'kiosk-namespace:pam-end')
                        os._exit(0)
                    except BaseException as error:
                        category = str(error) if isinstance(error, guest.GuestError) else 'internal'
                        os.write(write_fd, json.dumps({'stage': stage, 'category': category,
                            'pam_status': pam_status}).encode())
                        os._exit(1)
                os.close(write_fd)
                status, data = wait_first_exec(child, read_fd, armed=False)
                if data:
                    diagnostic = json.loads(data)
                    for key in ('stage', 'category', 'pam_status'):
                        record('onpc.kiosk.namespace.' + role + '.failed-' + key, diagnostic[key])
                if status != 0:
                    guest.commands.run(['journalctl', '-b', '--no-pager', '-n', '100',
                        '--grep=pam_namespace|onpc-namespace|avc:'], timeout=15,
                        check=False, merge_stderr=False)
                guest.require(status == 0, 'kiosk-namespace:callbacks:' + role)
                guest.require(os.readlink('/proc/self/ns/mnt') == parent_namespace and
                              not list(instances.iterdir()), 'kiosk-namespace:parent-isolation')
                record('onpc.kiosk.namespace.' + role + '.open-init-close-setcred', True)
                if initialized.exists():
                    initialized.unlink()
        finally:
            current = configuration.stat()
            guest.require((current.st_dev, current.st_ino) == (identity.st_dev, identity.st_ino)
                          and configuration.read_text() == contents,
                          'kiosk-namespace:configuration-replaced')
            configuration.unlink()


def native_package_rows(backend, rows):
    """Keep distro binary and source build identities in a finite schema."""
    guest.require(backend in ('apparmor', 'selinux'), 'kiosk-native:backend')
    names = ('package', 'version', 'architecture', 'source_package', 'source_version') if backend == 'apparmor' else (
             'package', 'version', 'architecture', 'source_rpm')
    result = []
    for line in rows.splitlines():
        fields = line.split('\t')
        guest.require(len(fields) == len(names) and all(
            re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9.+:~_-]*', value) for value in fields),
            'kiosk-native:package-identity-format')
        result.append(dict(zip(names, fields)))
    guest.require(result and len({item['package'] for item in result}) == len(result),
                  'kiosk-native:package-identity-set')
    return result


def record_native_packages(config, record):
    """Capture installed distro inputs before the matrix changes any bytes."""
    backend = config['backend']
    guest.require(backend in ('apparmor', 'selinux'), 'kiosk-native:backend')
    library = Path('/usr/lib/x86_64-linux-gnu' if backend == 'apparmor' else '/usr/lib64')
    # The installed preparer owns finite alternatives, substitutions and the
    # versioned systemd library-directory inventory. Reuse its actual records.
    preparation = runpy.run_path('/usr/libexec/oh-no-parent-control-kiosk-confinement')
    measured = {Path(entry.get('source', entry['path'])): entry['sha256']
                for entry in preparation['inventory'](config)
                if not entry.get('source', entry['path']).startswith('/usr/libexec/oh-no-parent-control-')}
    paths = set(measured)
    paths.update(Path(entry['path']) for entry in config.get('preserved_executables', []))
    required = [('/usr/libexec/gdm-session-worker', '/usr/lib/gdm3/gdm-session-worker'),
                ('/usr/lib/systemd/systemd-executor',),
                (str(library / 'libpam.so.0'),),
                (str(library / 'security/pam_namespace.so'),),
                (str(library / 'security/pam_selinux.so'),),
                (str(library / 'libselinux.so.1'),)]
    if backend == 'apparmor':
        required.append((str(library / 'libapparmor.so.1'),))
        optional = library / 'security/pam_cgfs.so'
        if os.path.lexists(optional):
            paths.add(preparation['trusted'](optional, symlinks=True))
    for alternatives in required:
        present = {Path(path).resolve(strict=True) for path in alternatives if Path(path).exists()}
        guest.require(len(present) == 1, 'kiosk-native:required-input-missing-or-ambiguous')
        paths.update(present)
    canonical = sorted({path.resolve(strict=True) for path in paths})
    files = []
    for path in canonical:
        guest.require(path.is_relative_to('/usr') and path.is_file(), 'kiosk-native:file-location')
        for item in (path, *path.parents):
            info = item.stat()
            guest.require(info.st_uid == 0 and not info.st_mode & 0o022, 'kiosk-native:file-ownership')
        digest = guest.sha(path)
        guest.require(path not in measured or measured[path] == digest, 'kiosk-native:inventory-changed')
        files.append({'path': str(path), 'sha256': digest})
    operands = [item['path'] for item in files]
    if backend == 'apparmor':
        ownership = guest.run(['dpkg-query', '-S', *operands])
        packages = sorted({line.rsplit(': ', 1)[0] for line in ownership.splitlines()})
        guest.require(packages and all(re.fullmatch(r'[a-z0-9][a-z0-9+.-]*(?::[a-z0-9]+)?', value)
                                      for value in packages), 'kiosk-native:package-owner-format')
        rows = guest.run(['dpkg-query', '-W', '-f=${binary:Package}\t${Version}\t${Architecture}\t'
                          '${source:Package}\t${source:Version}\n', *packages])
    else:
        packages = sorted(set(guest.run(['rpm', '-qf', '--qf', '%{NAME}\n', *operands]).splitlines()))
        guest.require(packages and all(re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9+._-]*', value)
                                      for value in packages), 'kiosk-native:package-owner-format')
        rows = guest.run(['rpm', '-q', '--qf', '%{NAME}\t%{EPOCHNUM}:%{VERSION}-%{RELEASE}\t'
                          '%{ARCH}\t%{SOURCERPM}\n', *packages])
    identities = native_package_rows(backend, rows)
    guest.require({item['package'] for item in identities} == set(packages),
                  'kiosk-native:package-query-incomplete')
    record('onpc.kiosk.native.packages', json.dumps(identities, sort_keys=True))
    record('onpc.kiosk.native.files', json.dumps(files, sort_keys=True))
    return files


def verify_loader_admission_refusal(config, record, *, defer_drain=False):
    """A native held admission excludes the real policy/attestation writer."""
    from system_kiosk_accounts import owned_bytes
    from system_kiosk_admission import held_account
    integration = '/usr/libexec/oh-no-parent-control-kiosk-confinement-integration'
    state = Path('/var/lib/oh-no-parent-control/kiosk-confinement.json')
    preparation = runpy.run_path('/usr/libexec/oh-no-parent-control-kiosk-confinement')
    if not defer_drain:
        guest.run([integration, 'load'], timeout=90)
    preparation['enforcing'](config)
    before = owned_bytes(state, private=True)
    pam = guest.pam_service_state()
    if not defer_drain:
        record('onpc.kiosk.loader.allowed-before-admission', True)
    with held_account(record) as pid:
        holder = PROC / str(pid)
        identity = process_identity(holder)
        guest.require(identity[2] == ('0',) * 4, 'kiosk-loader:holder-not-root')
        output = guest.commands.run([integration, 'load'], timeout=90,
                                    check=False, merge_stderr=True)
        status = guest.commands.last_returncode
        record('onpc.kiosk.loader.held-admission-result', json.dumps({
            'status': status, 'output': output.decode(errors='replace')}, sort_keys=True))
        guest.require(type(status) is int and status != 0 and b'kiosk-admissions-active' in output,
                      'kiosk-loader:held-admission-not-refused')
        guest.require(process_identity(holder) == identity and
                      owned_bytes(state, private=True) == before and
                      guest.pam_service_state() == pam,
                      'kiosk-loader:refusal-changed-admission-state')
        preparation['enforcing'](config)
        record('onpc.kiosk.loader.held-admission-preserved', hashlib.sha256(before).hexdigest())
    digest = hashlib.sha256(before).hexdigest()
    if defer_drain:
        # Real GDM and manager PAM handles retain their own lifetime leases.
        # Public exit alone must not be mistaken for every handle draining.
        record('onpc.kiosk.loader.drain-deferred-to-retirement', True)
    else:
        verify_loader_admission_drained(config, record, digest, pam)
    return digest


def verify_loader_admission_drained(config, record, expected_state_sha256, expected_pam):
    """Complete the same loader cycle only after every owned handle has ended."""
    from system_kiosk_accounts import owned_bytes
    guest.require(isinstance(expected_state_sha256, str) and
                  re.fullmatch(r'[a-f0-9]{64}', expected_state_sha256) is not None,
                  'kiosk-loader:invalid-drain-checkpoint')
    integration = '/usr/libexec/oh-no-parent-control-kiosk-confinement-integration'
    state = Path('/var/lib/oh-no-parent-control/kiosk-confinement.json')
    guest.run([integration, 'load'], timeout=90)
    guest.require(hashlib.sha256(owned_bytes(state, private=True)).hexdigest() == expected_state_sha256
                  and guest.pam_service_state() == expected_pam,
                  'kiosk-loader:drained-load-changed-admission-state')
    preparation = runpy.run_path('/usr/libexec/oh-no-parent-control-kiosk-confinement')
    preparation['enforcing'](config)
    record('onpc.kiosk.loader.allowed-after-admission', True)


def verify_execution_boundary(record):
    """Verify native execution while the installed MAC boundary stays enforcing."""
    guest.guard()
    guest.enable_diagnostics()
    config = json.loads(Path('/usr/share/oh-no-parent-control/confinement/config.json').read_text())
    native_files = record_native_packages(config, record)
    account = pwd.getpwnam('oh-no-parent-control')
    unit = f'user@{account.pw_uid}.service'
    guest.require(account.pw_shell == '/usr/sbin/nologin' and guest.run([
        'busctl', '--system', 'get-property', 'org.freedesktop.Accounts',
        f'/org/freedesktop/Accounts/User{account.pw_uid}', 'org.freedesktop.Accounts.User',
        'SystemAccount']) == 'b false', 'kiosk-confinement:greeter-classification')
    record('onpc.kiosk.nologin-account-visible-after-reboot', True)
    wait_kiosk_inactive(account)
    verify_loader_admission_refusal(config, record)
    guest.run(['systemctl', 'start', unit], timeout=75)
    invocation = guest.run(['systemctl', 'show', '--value', '--property=InvocationID', unit])
    try:
        pid = manager_pid(unit)
        backend = json.loads(Path('/usr/share/oh-no-parent-control/confinement/config.json').read_text())['backend']
        attribute = 'attr/apparmor/current' if backend == 'apparmor' else 'attr/current'
        label = (Path('/proc') / str(pid) / attribute).read_text().strip().rstrip('\0')
        expected = ('onpc-kiosk-manager (enforce)' if backend == 'apparmor'
                    else 'system_u:system_r:onpc_kiosk_manager_t:s0')
        guest.require(label == expected, 'kiosk-confinement:manager-label')
        record('onpc.kiosk.boundary.backend', backend)
        # First prove that the manager can successfully run a required native
        # service, so an unavailable bus/manager cannot count as denial.
        positive = ['/usr/bin/systemd-run', '--user', '--wait', '--collect', '--pipe',
                    '--unit=onpc-confinement-positive', '/usr/bin/systemctl', '--version']
        guest.require(b'systemd ' in user_command(account, positive), 'kiosk-confinement:positive-service')
        integration = '/usr/libexec/oh-no-parent-control-kiosk-confinement-integration'
        refusal = guest.commands.run([integration, 'check-remove'], check=False,
                                     timeout=30, merge_stderr=True)
        guest.require(guest.commands.last_returncode != 0 and any(reason in refusal for reason in
                      (b'kiosk-processes-active', b'kiosk-admissions-active')),
                      'kiosk-confinement:active-removal-not-refused')
        record('onpc.kiosk.active-removal-refused', True)
        if backend == 'apparmor':
            for service, properties in (
                ('oh-no-parent-control-wellbeing.service', {'NoNewPrivileges': 'no'}),
                ('wireplumber.service', {'NoNewPrivileges': 'no', 'LockPersonality': 'no',
                                         'MemoryDenyWriteExecute': 'no', 'SystemCallFilter': '~',
                                         'SystemCallArchitectures': ''}),
                ('pipewire.service', {'NoNewPrivileges': 'yes', 'LockPersonality': 'yes',
                                      'MemoryDenyWriteExecute': 'yes', 'DropInPaths': ''}),
            ):
                for property_name, value in properties.items():
                    observed = user_command(account, ['/usr/bin/systemctl', '--user', 'show',
                        '--value', '--property=' + property_name, service]).decode().strip()
                    guest.require(observed == value,
                                  'kiosk-confinement:effective-unit-setting:' + property_name)
            record('onpc.kiosk.effective-unit-overrides', True)
        denied = (
            ['/bin/sh', '-c', 'exit 0'],
            ['/usr/bin/python3', '-c', 'pass'],
            ['/usr/bin/gjs', '-c', 'void 0'],
            ['/usr/bin/gnome-shell', '--version'],
            ['/usr/bin/gnome-session', '--version'],
            ['/usr/bin/wireplumber', '--version'],
        )
        for index, command in enumerate(denied):
            user_command(account, command)
            record('onpc.kiosk.manager-input-positive.' + str(index), True)
            require_service_denial(account, backend, f'onpc-confinement-deny-{index}.service',
                                   command, record)
            record('onpc.kiosk.manager-denied.' + str(index), True)
        verify_user_inputs(account, backend, record)
        verify_updates(account, unit, backend, record)
        # GDM's saved-session metadata is deliberately irrelevant here: test
        # the executable selected after final PAM admission, including FDs.
        with tempfile.TemporaryDirectory(prefix='kiosk-confinement-', dir=guest.PAYLOAD) as temporary:
            directory = Path(temporary)
            verify_pam_lifecycle(account, unit, backend, directory, record, native_files=native_files)
            config = Path('/usr/share/oh-no-parent-control/confinement/config.json')
            with appended_probe(config, b'\n'):
                status, data = first_exec(account, directory,
                    ['/usr/libexec/gdm-wayland-session', '--help'], armed=False)
                guest.require(status == 125 and json.loads(data)['pam'] != 0,
                              'kiosk-confinement:stale-manager-admitted')
            guest.require(manager_pid(unit) == pid, 'kiosk-confinement:stale-manager-restarted')
            record('onpc.kiosk.stale-manager-denied-without-restart', True)
            status, data = first_exec(account, directory, ['/usr/libexec/gdm-wayland-session', '--help'])
            record('onpc.kiosk.positive-final-exec.status', status)
            if data:
                detail = json.loads(data)
                for key in ('pam', 'exec_errno'):
                    if type(detail.get(key)) is int:
                        record('onpc.kiosk.positive-final-exec.' + key, detail[key])
            guest.require(status == 0 and data == b'', 'kiosk-confinement:positive-final-exec')
            loader = '/usr/lib64/ld-linux-x86-64.so.2' if backend == 'selinux' else '/usr/lib/x86_64-linux-gnu/ld-linux-x86-64.so.2'
            cases = [(command, None) for command in denied]
            cases += [([loader, '/usr/bin/true'], None),
                      (['/usr/bin/true'], 'file'), (['/usr/bin/true'], 'memfd')]
            for index, (command, fd_mode) in enumerate(cases):
                status, data = first_exec(account, directory, command, fd_mode=fd_mode)
                guest.require(status == 126 and json.loads(data)['exec_errno'] in (errno.EACCES, errno.EPERM),
                              'kiosk-confinement:final-exec-not-denied')
                record('onpc.kiosk.final-exec-denied.' + str(index), True)
    finally:
        # Stop only the instance started here, never a replacement invocation.
        guest.require(guest.run(['systemctl', 'show', '--value', '--property=InvocationID', unit]) == invocation,
                      'kiosk-confinement:manager-identity-changed')
        guest.run(['systemctl', 'stop', unit], timeout=75)
    guest.run([integration, 'check-remove'], timeout=30)
    record('onpc.kiosk.inactive-removal-admitted', True)
    return account, backend


def verify(record):
    """Complete matrix, including deliberate policy-loss refusal/recovery."""
    account, backend = verify_execution_boundary(record)
    # Removing AppArmor policy detaches profiles from live processes. Faults
    # therefore run only after the explicitly owned manager has stopped.
    with tempfile.TemporaryDirectory(prefix='kiosk-admission-', dir=guest.PAYLOAD) as temporary:
        verify_admission_faults(account, Path(temporary), backend, record)


if __name__ == '__main__':
    if sys.argv[1:] == ['prepare-required-ancestor']:
        prepare_required_ancestor()
    elif sys.argv[1:] == ['verify-required-refusal']:
        verify_required_refusal()
    elif sys.argv[1:] == ['verify-required-gdm-refusal']:
        verify_required_gdm_refusal()
    elif sys.argv[1:] == ['restore-required-ancestor']:
        restore_required_ancestor()
    elif sys.argv[1:] == ['cleanup-required-ancestor']:
        cleanup_required_ancestor()
    elif sys.argv[1:] == ['prepare-siblings']:
        prepare_siblings()
    elif sys.argv[1:] == ['cleanup-siblings']:
        cleanup_siblings()
    elif sys.argv[1:] == ['census']:
        print(json.dumps(census(), sort_keys=True))
    elif len(sys.argv) == 3 and sys.argv[1] == 'bwrap-exec':
        request = json.loads(sys.argv[2])
        guest.require(set(request) == {'backend', 'uid', 'gid', 'namespace', 'generation',
            'arguments', 'proof_fd'} and request['backend'] == 'selinux' and
            all(type(request[name]) is int and request[name] > 2 for name in
                ('uid', 'gid', 'namespace', 'proof_fd')) and
            re.fullmatch(r'[a-f0-9]{64}\n', request['generation']) is not None and
            isinstance(request['arguments'], list) and request['arguments'] and
            request['arguments'][0] == '/usr/bin/bwrap' and
            all(isinstance(value, str) for value in request['arguments']),
            'kiosk-bwrap:caller-request')
        bwrap_probe_child(request)
    elif len(sys.argv) == 3 and sys.argv[1] == 'pam-lifecycle':
        request = json.loads(sys.argv[2])
        guest.require(set(request) == {'backend', 'executor_release', 'helper_release', 'events'} and
                      request['backend'] in ('apparmor', 'selinux') and
                      all(type(request[name]) is int and request[name] > 2 for name in
                          ('executor_release', 'helper_release', 'events')),
                      'kiosk-lifecycle:arguments')
        guest.guard()
        if request['backend'] == 'selinux':
            guest.require(lifecycle_label('selinux') == caller_identity('systemd-user')[0],
                          'kiosk-lifecycle:caller-context')
        lifecycle_executor(request)
    else:
        guest.require(len(sys.argv) == 3 and sys.argv[1] == 'first-exec',
                      'kiosk-confinement:arguments')
        request = json.loads(sys.argv[2])
        guest.require(set(request) in ({'command', 'directory', 'fd_mode', 'service', 'armed',
                                      'result_fd', 'diagnostic_fd', 'expected_selinux'},
                                     {'command', 'directory', 'fd_mode', 'service', 'armed',
                                      'result_fd', 'diagnostic_fd', 'expected_selinux', 'witness'}),
                      'kiosk-confinement:caller-request')
        result_fd = request.pop('result_fd')
        diagnostic_fd = request.pop('diagnostic_fd')
        guest.require(all(type(fd) is int and fd > 2 for fd in (result_fd, diagnostic_fd)) and
                      result_fd != diagnostic_fd,
                      'kiosk-confinement:caller-result-descriptor')
        try:
            # Only fd 2 remains available to native preparation subprocesses;
            # original reporting channels must not survive the actual exec.
            try:
                os.set_inheritable(result_fd, False)
                os.set_inheritable(diagnostic_fd, False)
                os.dup2(diagnostic_fd, 2)
            finally:
                os.close(diagnostic_fd)
            guest.guard(expected_selinux=request.pop('expected_selinux'))
            context, _ = caller_identity(request['service'])
            guest.require(Path('/proc/self/attr/current').read_text().strip().rstrip('\0') == context,
                          'kiosk-confinement:caller-context')
            status, data = first_exec(pwd.getpwnam('oh-no-parent-control'),
                Path(request.pop('directory')), request.pop('command'), **request)
            result = ('onpc-first-exec:' + json.dumps({'status': status, 'data': data.hex()})).encode()
            guest.require(len(result) <= 4096, 'kiosk-confinement:caller-result-size')
            guest.require(os.write(result_fd, result) == len(result),
                          'kiosk-confinement:caller-result-write')
        finally:
            os.close(result_fd)
