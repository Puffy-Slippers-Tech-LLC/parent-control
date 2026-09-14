"""Native enforcement witnesses, used only inside the guarded installed guest."""

import errno
import json
import os
from pathlib import Path
import pwd
import re
import shutil
import stat
import sys
import threading
import time

import system_guest as guest
from system_caller import drop_identity
from system_assertions import call as broker_call, accepted

TARGET = Path('/opt/onpc-test-fixtures-command/native-fixture')
DESKTOP_ID = 'com.puffyslippers.ONPCTest.Command.desktop'
DESKTOP = Path('/usr/share/applications') / DESKTOP_ID
SPACE_TARGET = Path('/opt/onpc-test-fixtures-whitespace/native fixture')
SPACE_DESKTOP_ID = 'com.puffyslippers.ONPCTest.Whitespace.desktop'
SPACE_DESKTOP = Path('/usr/share/applications') / SPACE_DESKTOP_ID
PATTERN_TARGET = Path('/opt/onpc-test-fixtures-pattern/Versioned-1.AppImage')
PATTERN_DESKTOP_ID = 'com.puffyslippers.ONPCTest.Pattern.desktop'
PATTERN_DESKTOP = Path('/usr/share/applications') / PATTERN_DESKTOP_ID
RETENTION_TARGET = Path('/opt/onpc-test-fixtures-retention/native-fixture')
RETENTION_DESKTOP_ID = 'com.puffyslippers.ONPCTest.Retention.desktop'
RETENTION_DESKTOP = Path('/usr/share/applications') / RETENTION_DESKTOP_ID
RULES = Path('/etc/fapolicyd/rules.d/89-oh-no-parent-control.rules')
COMPILED_RULES = Path('/etc/fapolicyd/compiled.rules')
FAPOLICYD = Path('/usr/sbin/fapolicyd')
IDENTITY = b'ONPC_TEST_LAUNCH_IDENTITY_VERIFIED\n'
READY = b'ONPC_TEST_APPLICATION_READY\n'
DENIED = b'ONPC_TEST_EXEC_DENIED\n'
CATALOG_PREFIX = 'com.puffyslippers.ONPCTest.Catalog.'
CATALOG_COMMAND = 'onpc-test-catalog-relative'
CATALOG_PARENT_COMMAND = 'onpc-test-catalog-parent-only'
CATALOG_SYSTEM_COMMAND = 'onpc-test-catalog-system'
CATALOG_FALLBACK_COMMAND = 'onpc-test-catalog-fallback'
CATALOG_LOCAL_BIN = Path('/usr/local/bin')
CATALOG_SYSTEM_BIN = Path('/usr/bin')


def catalog_entries():
    # A shared ID has distinct targets at every scope. The hidden child entry
    # must mask the system entry, while changing child must restore visibility.
    return (
        ('system', 'Shared', False), ('child', 'Shared', False),
        ('parent', 'Shared', False), ('child', 'ChildOnly', False),
        ('other', 'OtherOnly', False), ('parent', 'ParentOnly', False),
        ('system', 'Masked', False), ('child', 'Masked', True),
    )


def provision_catalog(accounts):
    """Install isolated launchers; the outer guest baseline owns file cleanup."""
    guest.guard()
    guest.enable_diagnostics()
    identities = {role: pwd.getpwuid(uid) for role, uid in accounts.items()}
    guest.require(set(identities) == {'child', 'other', 'parent'} and
                  len(set(accounts.values())) == 3 and
                  all(entry.pw_uid == accounts[role] and entry.pw_uid > 0
                      for role, entry in identities.items()), 'catalog:fixture-identities')
    directories = {'system': DESKTOP.parent}
    for role, entry in identities.items():
        home = Path(entry.pw_dir)
        guest.require(home.is_absolute() and home != Path('/') and home.is_dir(),
                      'catalog:fixture-home')
        directories[role] = home / '.local/share/applications'
    root = TARGET.parent / 'catalog'
    guest.require(TARGET.is_file() and not TARGET.is_symlink(), 'catalog:fixture-missing')
    guest.require(not root.exists() and not root.is_symlink(), 'catalog:fixture-collision')
    launchers = [(role, name, hidden, str(root / f'{role}-{name}'), None)
                 for role, name, hidden in catalog_entries()]
    targets = [('system', root / f'{role}-{name}')
               for role, name, _ in catalog_entries()]
    # A single system launcher must resolve to a different account's binary
    # when selection changes. The child's bin copy is a lower-priority decoy.
    for role, directory, command in (
            ('child', '.local/bin', CATALOG_COMMAND),
            ('child', 'bin', CATALOG_COMMAND),
            ('other', 'bin', CATALOG_COMMAND),
            ('parent', '.local/bin', CATALOG_COMMAND),
            ('parent', '.local/bin', CATALOG_PARENT_COMMAND),
            ('parent', '.local/bin', CATALOG_SYSTEM_COMMAND),
            ('parent', '.local/bin', CATALOG_FALLBACK_COMMAND)):
        targets.append((role, Path(identities[role].pw_dir) / directory / command))
    # Path must beat both children's binaries, which in turn beat the fixed
    # system search. Separate commands witness system precedence and fallback.
    desktop_path = root / 'desktop path'
    targets.extend((('system', desktop_path / CATALOG_COMMAND),
                    ('system', CATALOG_LOCAL_BIN / CATALOG_COMMAND),
                    ('system', CATALOG_LOCAL_BIN / CATALOG_SYSTEM_COMMAND),
                    ('system', CATALOG_SYSTEM_BIN / CATALOG_SYSTEM_COMMAND),
                    ('system', CATALOG_SYSTEM_BIN / CATALOG_FALLBACK_COMMAND)))
    launchers.extend((('system', 'Relative', False, CATALOG_COMMAND, None),
                      ('system', 'RelativeUnavailable', False, CATALOG_PARENT_COMMAND, None),
                      ('system', 'DesktopPath', False, CATALOG_COMMAND, desktop_path),
                      ('system', 'SystemPreferred', False, CATALOG_SYSTEM_COMMAND, None),
                      ('system', 'SystemFallback', False, CATALOG_FALLBACK_COMMAND, None)))
    owned_directories = [*directories.items(),
                         *((role, target.parent) for role, target in targets)]
    # Refuse existing symlinks, non-directories and collisions before any write.
    # Never chmod/chown an existing account directory or overwrite a launcher.
    for _, directory in owned_directories:
        for ancestor in (directory, *directory.parents):
            guest.require(not ancestor.is_symlink() and
                          (not ancestor.exists() or ancestor.is_dir()), 'catalog:unsafe-directory')
    for role, name, _, _, _ in launchers:
        path = directories[role] / f'{CATALOG_PREFIX}{name}.desktop'
        guest.require(not path.exists() and not path.is_symlink(), 'catalog:fixture-collision')
    for _, target in targets:
        guest.require(not target.exists() and not target.is_symlink(), 'catalog:fixture-collision')
    # The fallback witness needs this higher-priority candidate to stay absent.
    absent = CATALOG_LOCAL_BIN / CATALOG_FALLBACK_COMMAND
    guest.require(not absent.exists() and not absent.is_symlink(), 'catalog:fixture-collision')
    for role, directory in owned_directories:
        for path in reversed((directory, *directory.parents)):
            if not path.exists():
                path.mkdir(mode=0o755)
                path.chmod(0o755)
                if role != 'system':
                    entry = identities[role]
                    os.chown(path, entry.pw_uid, entry.pw_gid)
    for role, target in targets:
        with TARGET.open('rb') as source, target.open('xb') as destination:
            shutil.copyfileobj(source, destination)
        target.chmod(0o755)
        guest.require(guest.sha(target) == guest.sha(TARGET), 'catalog:fixture-copy-digest')
        if role != 'system':
            entry = identities[role]
            os.chown(target, entry.pw_uid, entry.pw_gid)
    for role, name, hidden, command, working_directory in launchers:
        path = directories[role] / f'{CATALOG_PREFIX}{name}.desktop'
        with path.open('x', encoding='utf-8') as stream:
            stream.write('[Desktop Entry]\nType=Application\n'
                         f'Name=ONPC {role} {name}\nExec="{command}"\nTerminal=false\n'
                         + (f'Path={working_directory}\n' if working_directory else '')
                         + ('Hidden=true\n' if hidden else ''))
        path.chmod(0o644)
        if role != 'system':
            entry = identities[role]
            os.chown(path, entry.pw_uid, entry.pw_gid)
    print('onpc-system: stage=native-catalog-fixture outcome=ready', flush=True)


def observe_catalog(accounts, record):
    """Read through the installed broker as parent, switching selected child."""
    guest.guard()
    root = TARGET.parent / 'catalog'
    for stage, role in (('child', 'child'), ('other', 'other'), ('child-again', 'child')):
        rows = call(accounts['parent'], 'ListApplications', '(u)', (accounts[role],))[0]
        expected = {'Shared': role if role == 'child' else 'system',
                    'ChildOnly' if role == 'child' else 'OtherOnly': role,
                    'Relative': 'system', 'DesktopPath': 'system',
                    'SystemPreferred': 'system', 'SystemFallback': 'system'}
        if role == 'other':
            expected['Masked'] = 'system'
        selected = [row for row in rows if row[0].startswith(CATALOG_PREFIX)]
        guest.require(len(selected) == len(expected) and
                      {row[0] for row in selected} == {
                          f'{CATALOG_PREFIX}{name}.desktop' for name in expected},
                      'catalog:scope-membership')
        for name, source in expected.items():
            row = next(row for row in selected if row[0] == f'{CATALOG_PREFIX}{name}.desktop')
            target = root / f'{source}-{name}'
            if name == 'Relative':
                home = Path(pwd.getpwuid(accounts[role]).pw_dir)
                target = home / ('.local/bin' if role == 'child' else 'bin') / CATALOG_COMMAND
            elif name == 'DesktopPath':
                target = root / 'desktop path' / CATALOG_COMMAND
            elif name == 'SystemPreferred':
                target = CATALOG_LOCAL_BIN / CATALOG_SYSTEM_COMMAND
            elif name == 'SystemFallback':
                target = CATALOG_SYSTEM_BIN / CATALOG_FALLBACK_COMMAND
            guest.require(row[1] == f'ONPC {source} {name}' and
                          row[4] == [str(target)], 'catalog:selected-target')
        system = [row for row in rows if row[0] == DESKTOP_ID]
        guest.require(len(system) == 1 and system[0][4] == [str(TARGET)], 'catalog:system-target')
        record(f'onpc.catalog.{stage}', 'passed')
        print(f'onpc-system: stage=catalog-{stage} outcome=passed', flush=True)


def call(uid, method, signature='()', args=()):
    reply = broker_call(uid, method, signature, args, category='enforcement:caller-reply')
    return accepted(reply, category='enforcement:broker-call-failed')


def native_paths(variant):
    # Requests select maintained fixtures, never caller-supplied executable paths.
    paths = {
        'command': (TARGET, DESKTOP, DESKTOP_ID),
        'whitespace': (SPACE_TARGET, SPACE_DESKTOP, SPACE_DESKTOP_ID),
        'pattern': (PATTERN_TARGET, PATTERN_DESKTOP, PATTERN_DESKTOP_ID),
        'retention': (RETENTION_TARGET, RETENTION_DESKTOP, RETENTION_DESKTOP_ID),
        'pattern-future': (PATTERN_TARGET.with_name('Versioned-2.AppImage'),
                           PATTERN_DESKTOP, PATTERN_DESKTOP_ID),
        'pattern-unrelated': (PATTERN_TARGET.with_name('Unrelated.AppImage'),
                              PATTERN_DESKTOP, PATTERN_DESKTOP_ID),
    }
    guest.require(isinstance(variant, str) and variant in paths,
                  'enforcement:fixture-variant')
    return paths[variant]


def provision_native(variant='command'):
    guest.guard()
    target, desktop, _ = native_paths(variant)
    guest.require(variant in ('command', 'whitespace', 'pattern', 'retention'),
                  'enforcement:fixture-variant')
    guest.enable_diagnostics()
    guest.require(not target.parent.exists() and not target.parent.is_symlink() and
                  not desktop.exists() and not desktop.is_symlink(),
                  'enforcement:fixture-collision')
    source = guest.PAYLOAD / 'fixtures/native/onpc-test-application'
    guest.require(source.is_file() and not source.is_symlink(), 'enforcement:fixture-missing')
    # The input guard verifies the transferred source. Never copy the fixture
    # image's placeholder home directory onto an actual account.
    # The guarded controller uses a private umask. Set traversability explicitly
    # on this newly owned directory so Unix DAC does not mimic policy denial.
    target.parent.mkdir(mode=0o755)
    target.parent.chmod(0o755)
    shutil.copyfile(source, target)
    target.chmod(0o755)
    desktop.write_text('[Desktop Entry]\nType=Application\nName=ONPC Native Fixture\n'
                       f'Exec="{target}"\nTerminal=false\n')
    desktop.chmod(0o644)
    guest.require(guest.sha(target) == guest.sha(source), 'enforcement:fixture-copy-digest')
    if variant == 'pattern':
        unrelated, _, _ = native_paths('pattern-unrelated')
        shutil.copyfile(source, unrelated)
        unrelated.chmod(0o755)
        guest.require(guest.sha(unrelated) == guest.sha(source),
                      'enforcement:fixture-copy-digest')
    # Existing baseline accounts; no account lifecycle work is part of this case.
    accounts = {role: pwd.getpwnam(name).pw_uid for role, name in (
        ('child', 'onpc-child-riley'), ('other', 'onpc-child-jordan'),
        ('parent', 'onpc-parent-jamie'))}
    guest.require(len(set(accounts.values())) == 3, 'enforcement:fixture-identities')
    print('onpc-system: stage=native-enforcement-fixture outcome=ready', flush=True)
    return accounts


def provision_future():
    """Create the next version only after the scenario witnesses active rules."""
    guest.guard()
    target, _, _ = native_paths('pattern-future')
    guest.require(PATTERN_TARGET.parent.is_dir() and not PATTERN_TARGET.parent.is_symlink() and
                  PATTERN_TARGET.is_file() and not PATTERN_TARGET.is_symlink() and
                  not target.exists() and not target.is_symlink(),
                  'enforcement:future-fixture-collision')
    # Exclusive creation preserves unexpected files, including dangling symlinks.
    with target.open('xb') as output, PATTERN_TARGET.open('rb') as source:
        shutil.copyfileobj(source, output)
    target.chmod(0o755)
    guest.require(guest.sha(target) == guest.sha(PATTERN_TARGET),
                  'enforcement:fixture-copy-digest')


def remove_retention_launcher(identity):
    """Remove only the fixed guest fixture witnessed before policy activation."""
    guest.guard()
    desktop = RETENTION_DESKTOP
    current = desktop.lstat()
    guest.require(not desktop.parent.is_symlink() and stat.S_ISREG(current.st_mode) and
                  current.st_nlink == 1 and all(
                      getattr(current, field) == getattr(identity, field) for field in (
                          'st_dev', 'st_ino', 'st_mode', 'st_nlink', 'st_uid', 'st_gid',
                          'st_size', 'st_mtime_ns', 'st_ctime_ns')),
                  'enforcement:launcher-identity-changed')
    desktop.unlink()
    guest.require(not desktop.exists() and not desktop.is_symlink(),
                  'enforcement:launcher-removal-failed')


def launch_as(uid, variant='command'):
    """One directly owned PID becomes the one-shot fixture; no child to discover."""
    guest.guard()
    target, _, _ = native_paths(variant)
    drop_identity(uid)
    sys.stdout.buffer.write(IDENTITY)
    sys.stdout.buffer.flush()
    try:
        os.execv(str(target), [str(target)])
    except OSError as error:
        if error.errno not in (errno.EACCES, errno.EPERM):
            raise guest.GuestError('enforcement:exec-failed') from None
        sys.stdout.buffer.write(DENIED)
        sys.stdout.buffer.flush()
        return 77


def observe_launch(uid, allowed, variant='command'):
    native_paths(variant)
    raw = guest.commands.run(
        ['/usr/bin/python3', '-B', str(guest.PAYLOAD / 'system_enforcement.py')],
        input=json.dumps({'uid': uid, 'variant': variant}).encode(),
        timeout=30, check=False, merge_stderr=False)
    expected = IDENTITY + (READY if allowed else DENIED)
    guest.require(raw == expected and guest.commands.last_returncode == (0 if allowed else 77),
                  'enforcement:expected-allow' if allowed else 'enforcement:expected-denial')


def record_rules(stage, uid, blocked, record, variant='command'):
    # Keep the actual source and compiled rules in the existing private text
    # diagnostics, including on assertion failure; public properties use roles.
    target, _, _ = native_paths(variant)
    clause = (f'sha256hash={guest.sha(target)}' if variant == 'whitespace' else
              f'path={target}')
    expected = f'deny_syslog perm=execute uid={uid} : {clause}'
    texts = []
    for label, path in (('source', RULES), ('compiled', COMPILED_RULES)):
        guest.require(path.is_file() and not path.is_symlink(), 'enforcement:rules-missing')
        raw = path.read_bytes()
        (guest.commands.directory / f'native-{variant}-{stage}-{label}.txt').write_bytes(raw)
        texts.append(raw.decode().splitlines())
        record(f'onpc.native.{variant}.{stage}.{label}.sha256', guest.sha(path))
    guest.require(all((expected in lines) == blocked for lines in texts),
                  'enforcement:rule-state')
    if variant == 'pattern':
        unrelated, _, _ = native_paths('pattern-unrelated')
        future, _, _ = native_paths('pattern-future')
        allow = f'allow perm=execute uid={uid} : path={unrelated}'
        deny = f'deny_syslog perm=execute uid={uid} : dir={target.parent}/'
        future_deny = f'deny_syslog perm=execute uid={uid} : path={future}'
        guest.require(all((deny in lines) == blocked and (allow in lines) == blocked
                          and future_deny not in lines
                          and (not blocked or lines.index(allow) < lines.index(deny))
                          for lines in texts), 'enforcement:pattern-rule-state')
    return tuple(tuple(lines) for lines in texts)


def record_execution_backend(record):
    """Identify the installed dependency; this does not witness live policy."""
    version = guest.run(
        ['dpkg-query', '-W', '-f=${Version}', 'fapolicyd'], timeout=10)
    guest.require(re.fullmatch(r'[0-9][A-Za-z0-9.+:~\-]{0,127}', version) is not None,
                  'enforcement:backend-version')
    # Validate before publishing command-derived text. Never put arbitrary
    # command output, paths supplied by an account, or rule data in properties.
    digest = guest.sha(FAPOLICYD)
    record('onpc.enforcement.fapolicyd.package-version', version)
    record('onpc.enforcement.fapolicyd.executable.sha256', digest)


def _lose_probe_sender(client):
    """Test-only transport fault, reusing the retained client's bounded close.

    Do not mark the client logically closing: model external transport loss
    while retaining its original connection and callbacks for the adapter.
    An interrupted/late close is collected on the next call to this helper.
    """
    client._context.push_thread_default()
    try:
        if client._pending is None and not client._connection.is_closed():
            client._start_close()
        client._wait(time.monotonic() + 2)
        return client._pending is None and client._connection.is_closed()
    finally:
        client._context.pop_thread_default()


def native_probe_lifecycle(record, *, refuse_admission=False, lose_sender=False):
    """Qualify the installed adapter against systemd; never claim policy receipt.

    The failure case validates the real waiting peer, then withholds admission.
    Recovery owns that same attempt; no stop/kill, replacement adapter or replay.
    The outer guarded controller retains diagnostics and restores the testbed if
    bounded recovery cannot settle it.
    """
    guest.guard()
    guest.enable_diagnostics()
    record_execution_backend(record)
    version = guest.run(['dpkg-query', '-W', '-f=${Version}', 'systemd'], timeout=10)
    guest.require(re.fullmatch(r'[0-9][A-Za-z0-9.+:~\-]{0,127}', version) is not None,
                  'probe:manager-version')
    record('onpc.probe.systemd.package-version', version)
    record('onpc.probe.systemd.executable.sha256', guest.sha(Path('/usr/lib/systemd/systemd')))
    previous_path = sys.path[:]
    sys.path[:0] = ['/usr/lib/oh-no-parent-control', '/usr/lib/oh-no-parent-control/broker']
    try:
        from oh_no_parent_control import execution_probe as probe
        from gi.repository import Gio
    finally:
        sys.path[:] = previous_path

    root = Path('/run/oh-no-parent-control/probes')
    metadata = root.lstat()
    guest.require(stat.S_ISDIR(metadata.st_mode) and metadata.st_uid == 0 and
                  stat.S_IMODE(metadata.st_mode) == 0o700, 'probe:runtime-provisioning')

    class RefusingProbe(probe.ExecutionProbe):
        binding_observed = False

        def _admission_binding(self, *args):
            super()._admission_binding(*args)
            self.binding_observed = True
            raise probe.ChannelRefused('installed qualification withholds admission')

    class LostSenderProbe(probe.ExecutionProbe):
        sender_lost = False

        def _release(self, result):
            if not self.sender_lost:
                # Never discard the pin until the complete native observation
                # is copied. Earlier-loss refusal is qualified locally only.
                if not (result.create_outcome == 'replied' and result.terminal_observed and
                        result.native_verified and result.admission is not None):
                    return super()._release(result)
                self.sender_lost = _lose_probe_sender(self._client)
                if not self.sender_lost:
                    return result
            return super()._release(result)

    connection = Gio.bus_get_sync(Gio.BusType.SYSTEM, None)
    adapter_type = (RefusingProbe if refuse_admission else
                    LostSenderProbe if lose_sender else probe.ExecutionProbe)
    adapter = adapter_type(connection)
    result = None
    try:
        result = adapter.run_native()
        # Publish bounded enums/booleans and adapter-owned coordinates only.
        record('onpc.probe.initial.outcome', result.outcome)
        record('onpc.probe.initial.create-error-name', result.create_error_name)
        record('onpc.probe.initial.cleanup-complete', result.cleanup_complete)
        record('onpc.probe.initial.native-verified', result.native_verified)
        record('onpc.probe.initial.terminal-observed', result.terminal_observed)
        record('onpc.probe.initial.channel-result', result.channel_result)
        record('onpc.probe.unit', result.unit)
        record('onpc.probe.manager', result.manager)
        record('onpc.probe.job', result.job)
        guest.require(result.generation is not None, 'probe:generation-missing')
        record('onpc.probe.witness.sha256', result.generation.sha256)
        guest.require(not result.executed, 'probe:receipt-promoted')
        if refuse_admission:
            guest.require(adapter.binding_observed and not result.native_verified and
                          result.admission is None and result.channel_result == '',
                          'probe:expected-admission-refusal')
            guest.require(adapter.pending is not None and not result.cleanup_complete,
                          'probe:expected-retained-attempt')
            guest.require(adapter._generation.verify() == result.generation,
                          'probe:retained-witness')
        else:
            guest.require(result.native_verified and result.outcome == 'identity-unproven' and
                          result.channel_result == 'executed' and result.terminal_observed and
                          result.admission is not None and
                          result.admission.peer.invocation == result.invocation,
                          'probe:expected-native-witness')
    finally:
        deadline = time.monotonic() + 20
        while adapter.pending is not None and time.monotonic() < deadline:
            recovered = adapter.recover()
            if recovered is not None:
                result = recovered
            if adapter.pending is not None:
                time.sleep(0.05)
        record('onpc.probe.cleanup-complete', adapter.pending is None)
        if adapter.pending is not None:
            # Keep exact owned coordinates in private JUnit evidence. The outer
            # controller, not a guessed unit-name operation, owns VM recovery.
            record('onpc.probe.pending.unit', adapter.pending.unit)
            record('onpc.probe.pending.job', adapter.pending.job)
            record('onpc.probe.pending.create-error-name', adapter.pending.create_error_name)
        guest.require(adapter.pending is None, 'probe:cleanup-incomplete')
    if lose_sender:
        record('onpc.probe.sender-lost', adapter.sender_lost)
        guest.require(adapter.sender_lost and not connection.is_closed(), 'probe:sender-loss-missing')
    guest.require(result is not None and result.cleanup_complete and result.client_closed and
                  result.reference_released and not result.executed, 'probe:cleanup-evidence')
    record('onpc.probe.effective-job-timeout-usec', result.job_timeout_usec)
    guest.require(result.job_timeout_usec == 4_000_000, 'probe:effective-job-timeout')
    guest.require(not Path(result.generation.directory).exists(), 'probe:generation-not-collected')
    current = root.lstat()
    guest.require((current.st_dev, current.st_ino, current.st_mode, current.st_uid, current.st_gid) ==
                  (metadata.st_dev, metadata.st_ino, metadata.st_mode, metadata.st_uid, metadata.st_gid),
                  'probe:runtime-root-changed')


def _broker_storage_identity():
    raw = guest.run(['systemctl', 'show', guest.BROKER,
                     '--property=MainPID,InvocationID,ActiveState,ProtectSystem,RuntimeDirectoryPreserve'],
                    timeout=10)
    fields = dict(line.split('=', 1) for line in raw.splitlines() if '=' in line)
    guest.require(fields.get('ActiveState') == 'active' and
                  fields.get('ProtectSystem') == 'strict' and
                  fields.get('RuntimeDirectoryPreserve') == 'yes' and
                  re.fullmatch(r'[1-9][0-9]{0,9}', fields.get('MainPID', '')) is not None and
                  re.fullmatch(r'[0-9a-f]{32}', fields.get('InvocationID', '')) is not None,
                  'probe:broker-storage-identity')
    return fields['MainPID'], fields['InvocationID']


def _in_broker_mount(operation):
    """Read-pin the guarded broker namespace; never signal its discovered PID.

    Unshare filesystem state in a dedicated joined thread before setns/chroot.
    No caller thread changes namespace/root, even if the operation fails. The
    retained root FD prevents absolute paths from using the old root mount.
    This qualifies mount restrictions, not the broker's capabilities/seccomp.
    """
    guest.guard()
    identity = _broker_storage_identity()
    descriptors = []
    try:
        namespace = os.open(f'/proc/{identity[0]}/ns/mnt', os.O_RDONLY | os.O_CLOEXEC)
        descriptors.append(namespace)
        root = os.open(f'/proc/{identity[0]}/root', os.O_RDONLY | os.O_DIRECTORY | os.O_CLOEXEC)
        descriptors.append(root)
        guest.require(_broker_storage_identity() == identity, 'probe:broker-replaced')
        expected = os.fstat(namespace).st_ino
        guest.require(expected != os.stat('/proc/thread-self/ns/mnt').st_ino,
                      'probe:broker-mount-not-isolated')
        results, errors = [], []

        def worker():
            try:
                os.unshare(os.CLONE_FS)
                os.setns(namespace, os.CLONE_NEWNS)
                os.fchdir(root)
                os.chroot('.')
                os.chdir('/')
                guest.require(os.stat('/proc/thread-self/ns/mnt').st_ino == expected,
                              'probe:broker-mount-mismatch')
                guest.require(os.statvfs('/usr').f_flag & os.ST_RDONLY,
                              'probe:strict-mount-not-readonly')
                results.append(operation())
            except BaseException as error:
                errors.append(error)

        thread = threading.Thread(target=worker, name='onpc-probe-storage')
        thread.start()
        try:
            thread.join()
        finally:
            # Do not close descriptors or hand off while the owned worker lives.
            while thread.is_alive():
                thread.join()
        if errors:
            raise errors[0]
        guest.require(len(results) == 1, 'probe:storage-worker-result')
        guest.require(_broker_storage_identity() == identity, 'probe:broker-replaced')
        return results[0], identity
    finally:
        for descriptor in reversed(descriptors):
            os.close(descriptor)


def native_probe_storage_lifecycle(record):
    """Preserve one exact owner across stop/start and restart; never adopt residue."""
    guest.guard()
    guest.enable_diagnostics()
    previous_path = sys.path[:]
    sys.path[:0] = ['/usr/lib/oh-no-parent-control', '/usr/lib/oh-no-parent-control/broker']
    try:
        from oh_no_parent_control.probe_generation import ProbeGeneration
    finally:
        sys.path[:] = previous_path
    # Retain before prepare, including partial creation and worker failure.
    owner, fresh = ProbeGeneration(), ProbeGeneration()
    try:
        identity, broker = _in_broker_mount(owner.prepare)
        record('onpc.probe.storage.witness.sha256', identity.sha256)
        record('onpc.probe.storage.generation', identity.token)
        guest.require(not owner.close(settled=False) and owner.verify() == identity,
                      'probe:unsettled-storage-not-retained')
        guest.require(_broker_storage_identity() == broker, 'probe:broker-replaced')
        guest.run(['systemctl', 'stop', guest.BROKER], timeout=20)
        guest.require(guest.run(['systemctl', 'show', guest.BROKER,
                                 '--property=ActiveState', '--value'], timeout=10) == 'inactive',
                      'probe:broker-not-stopped')
        guest.require(owner.verify() == identity, 'probe:storage-lost-on-stop')
        record('onpc.probe.storage.stop-preserved', True)
        guest.run(['systemctl', 'start', guest.BROKER], timeout=30)
        preserved, started = _in_broker_mount(owner.verify)
        guest.require(preserved == identity and started[1] != broker[1],
                      'probe:storage-start-identity')
        guest.run(['systemctl', 'restart', guest.BROKER], timeout=30)
        preserved, restarted = _in_broker_mount(owner.verify)
        guest.require(preserved == identity and restarted[1] != started[1],
                      'probe:storage-restart-identity')
        other, current = _in_broker_mount(fresh.prepare)
        guest.require(current == restarted and other.token != identity.token and
                      owner.verify() == identity, 'probe:storage-residue-adopted')
        record('onpc.probe.storage.restart-preserved', True)
        record('onpc.probe.storage.fresh-independent', True)
    finally:
        # These owners never dispatch a unit or open a channel: settlement is
        # certain after the worker joins. No recursive cleanup or broker-PID kill.
        fresh_closed = owner_closed = False
        try:
            try:
                fresh_closed = fresh.close(settled=True)
            finally:
                owner_closed = owner.close(settled=True)
        finally:
            record('onpc.probe.storage.cleanup-complete', fresh_closed and owner_closed)
        guest.require(fresh_closed and owner_closed, 'probe:storage-cleanup-incomplete')
    guest.require(_broker_storage_identity() == restarted, 'probe:broker-replaced')


def native_policy_transition(accounts, record, variant='command'):
    """Hard/soft denial in both screen-time states, with UID isolation throughout."""
    guest.guard()
    target, desktop, desktop_id = native_paths(variant)
    guest.require(variant in ('command', 'whitespace', 'pattern', 'retention'),
                  'enforcement:fixture-variant')
    record_execution_backend(record)
    prefix = f'onpc.native.{variant}'
    record(f'{prefix}.fixture.sha256', guest.sha(target))
    parent, child, other = (accounts[role] for role in ('parent', 'child', 'other'))
    applications = call(parent, 'ListApplications', '(u)', (child,))[0]
    matches = [row for row in applications if row[0] == desktop_id]
    guest.require(len(matches) == 1 and matches[0][4] == [str(target)],
                  'enforcement:catalog-target')
    original = call(parent, 'GetPreferences', '(u)', (child,))[0]
    preferences = json.loads(original)
    guest.require(not preferences['apps'] and not preferences['parent_control_enabled'],
                  'enforcement:requires-clean-policy')
    other_before = call(parent, 'GetPreferences', '(u)', (other,))[0]
    original_limit = preferences['daily_time_limit_minutes']
    screen_time_attempted = False
    future_created = False
    launcher_identity = desktop.lstat() if variant == 'retention' else None
    if variant == 'pattern':
        future, _, _ = native_paths('pattern-future')
        guest.require(not future.exists() and not future.is_symlink(),
                      'enforcement:future-fixture-collision')
    try:
        # Clear and witness the hard denial before testing soft policy so stale
        # hard rules cannot satisfy the conditional-policy assertion.
        for stage, app_state in (('allowed', None), ('hard', 'permanent'),
                                 ('restored', None), ('soft', 'conditional'),
                                 ('soft-restored', None), ('enabled-allowed', None),
                                 ('enabled-hard', 'permanent'), ('enabled-restored', None),
                                 ('enabled-soft', 'conditional'), ('enabled-soft-restored', None)):
            enabled = stage.startswith('enabled-')
            if enabled and not screen_time_attempted:
                # SetPreferences deliberately cannot toggle screen-time control.
                # Mark before calling: even a failed reply can follow a write.
                screen_time_attempted = True
                call(parent, 'SetParentControl', '(ubu)', (child, True, original_limit))
                toggled = json.loads(call(parent, 'GetPreferences', '(u)', (child,))[0])
                guest.require(toggled['parent_control_enabled'] is True and
                              toggled['daily_time_limit_minutes'] == original_limit and
                              toggled['apps'] == preferences['apps'],
                              'enforcement:screen-time-readback')
            preferences['parent_control_enabled'] = enabled
            blocked = app_state is not None
            preferences['apps'] = ({desktop_id: {
                'state': app_state, 'targets': [str(target)],
                'patterns': [str(target.with_name('Versioned-*.AppImage'))] if variant == 'pattern' else [],
                'user_saved_match_rule': variant == 'pattern'}} if blocked else {})
            call(parent, 'SetPreferences', '(us)', (child, json.dumps(preferences)))
            saved = json.loads(call(parent, 'GetPreferences', '(u)', (child,))[0])
            guest.require(saved['parent_control_enabled'] is enabled and
                          saved['daily_time_limit_minutes'] == original_limit and
                          saved['apps'] == preferences['apps'],
                          'enforcement:policy-readback')
            rules_before = record_rules(stage, child, blocked, record, variant=variant)
            if variant == 'retention' and stage == 'hard':
                remove_retention_launcher(launcher_identity)
                applications = call(parent, 'ListApplications', '(u)', (child,))[0]
                guest.require(all(row[0] != desktop_id for row in applications),
                              'enforcement:launcher-still-listed')
                record(f'{prefix}.missing.catalog', 'absent')
                retained = json.loads(call(parent, 'GetPreferences', '(u)', (child,))[0])
                guest.require(retained == saved, 'enforcement:missing-policy-lost')
                # Exercise the public save's catalog reconciliation, not just
                # persistence before the next write. The executable stays put.
                call(parent, 'SetPreferences', '(us)', (child, json.dumps(retained)))
                retained = json.loads(call(parent, 'GetPreferences', '(u)', (child,))[0])
                guest.require(retained == saved, 'enforcement:missing-policy-lost')
                record_rules('missing', child, True, record, variant=variant)
                record(f'{prefix}.missing.saved-policy', 'retained')
            if variant == 'pattern' and stage == 'hard':
                provision_future()
                future_created = True
                record(f'{prefix}.future.fixture.sha256', guest.sha(future))
            observe_launch(child, not blocked, variant=variant)
            record(f'{prefix}.{stage}.child', 'denied' if blocked else 'allowed')
            observe_launch(other, True, variant=variant)
            record(f'{prefix}.{stage}.other', 'allowed')
            if variant == 'pattern':
                for launch_variant in ('pattern-unrelated', 'pattern-future'):
                    if launch_variant == 'pattern-future' and not future_created:
                        continue
                    allowed = launch_variant == 'pattern-unrelated' or not blocked
                    observe_launch(child, allowed, variant=launch_variant)
                    record(f'{prefix}.{stage}.{launch_variant}.child',
                           'allowed' if allowed else 'denied')
                    observe_launch(other, True, variant=launch_variant)
                    record(f'{prefix}.{stage}.{launch_variant}.other', 'allowed')
                if stage == 'hard':
                    rules_after = record_rules('hard-future', child, True, record, variant=variant)
                    guest.require(rules_after == rules_before, 'enforcement:future-rules-changed')
                    record(f'{prefix}.future.unchanged-rules', 'passed')
            guest.require(call(parent, 'GetPreferences', '(u)', (other,))[0] == other_before,
                          'enforcement:other-preferences-changed')
            print(f'onpc-system: stage=native-{variant}-{stage} outcome=passed', flush=True)
    finally:
        # This is the scenario's policy restoration. Outer VM baseline cleanup
        # remains authoritative on failure; never hide the original exception.
        failed = sys.exc_info()[0] is not None
        restoration_error = None
        if screen_time_attempted:
            try:
                call(parent, 'SetParentControl', '(ubu)', (child, False, original_limit))
            except Exception as error:
                restoration_error = error
        # Restore app choices even if disabling screen time failed. The full
        # preference readback must still reject a retained enabled state.
        try:
            call(parent, 'SetPreferences', '(us)', (child, original))
            guest.require(call(parent, 'GetPreferences', '(u)', (child,))[0] == original,
                          'enforcement:policy-restore-mismatch')
            guest.require(call(parent, 'GetPreferences', '(u)', (other,))[0] == other_before,
                          'enforcement:other-preferences-changed')
        except Exception as error:
            restoration_error = restoration_error or error
        if restoration_error is not None:
            record(f'{prefix}.policy-restoration', 'failed')
            if not failed:
                raise restoration_error
        else:
            record(f'{prefix}.policy-restoration', 'passed')


def main():
    try:
        request = json.load(sys.stdin)
        guest.require(isinstance(request, dict) and set(request) == {'uid', 'variant'},
                      'enforcement:launch-request')
        return launch_as(request['uid'], request['variant'])
    except (guest.GuestError, OSError, ValueError, KeyError, TypeError):
        print('onpc-system: stage=native-launch outcome=failed', file=sys.stderr)
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
