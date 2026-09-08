"""Native enforcement witnesses, used only inside the guarded installed guest."""

import errno
import json
import os
from pathlib import Path
import pwd
import shutil
import stat
import sys

import system_guest as guest
from system_caller import drop_identity

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
    raw = guest.commands.run(
        ['/usr/bin/python3', '-B', str(guest.PAYLOAD / 'system_caller.py')],
        input=json.dumps({'uid': uid, 'operations': [
            {'kind': 'call', 'method': method, 'signature': signature, 'args': args}]}).encode(),
        timeout=180, merge_stderr=False)
    reply = json.loads(raw)
    guest.require(reply.get('uid') == uid and len(reply.get('replies', [])) == 1,
                  'enforcement:caller-reply')
    result = reply['replies'][0]
    guest.require('result' in result, 'enforcement:broker-call-failed')
    return result['result']


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


def native_policy_transition(accounts, record, variant='command'):
    """Hard/soft denial in both screen-time states, with UID isolation throughout."""
    guest.guard()
    target, desktop, desktop_id = native_paths(variant)
    guest.require(variant in ('command', 'whitespace', 'pattern', 'retention'),
                  'enforcement:fixture-variant')
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
