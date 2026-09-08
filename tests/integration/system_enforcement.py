"""Native enforcement witnesses, used only inside the guarded installed guest."""

import errno
import json
import os
from pathlib import Path
import pwd
import shutil
import sys

import system_guest as guest
from system_caller import drop_identity

TARGET = Path('/opt/onpc-test-fixtures-command/native-fixture')
DESKTOP_ID = 'com.puffyslippers.ONPCTest.Command.desktop'
DESKTOP = Path('/usr/share/applications') / DESKTOP_ID
RULES = Path('/etc/fapolicyd/rules.d/89-oh-no-parent-control.rules')
COMPILED_RULES = Path('/etc/fapolicyd/compiled.rules')
IDENTITY = b'ONPC_TEST_LAUNCH_IDENTITY_VERIFIED\n'
READY = b'ONPC_TEST_APPLICATION_READY\n'
DENIED = b'ONPC_TEST_EXEC_DENIED\n'
CATALOG_PREFIX = 'com.puffyslippers.ONPCTest.Catalog.'


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
    # Refuse existing symlinks, non-directories and collisions before any write.
    # Never chmod/chown an existing account directory or overwrite a launcher.
    for directory in (*directories.values(), root.parent):
        for ancestor in (directory, *directory.parents):
            guest.require(not ancestor.is_symlink() and
                          (not ancestor.exists() or ancestor.is_dir()), 'catalog:unsafe-directory')
    for role, name, _ in catalog_entries():
        path = directories[role] / f'{CATALOG_PREFIX}{name}.desktop'
        guest.require(not path.exists() and not path.is_symlink(), 'catalog:fixture-collision')
    root.mkdir(mode=0o755)
    root.chmod(0o755)
    for role, directory in directories.items():
        for path in reversed((directory, *directory.parents)):
            if not path.exists():
                path.mkdir(mode=0o755)
                path.chmod(0o755)
                if role != 'system':
                    entry = identities[role]
                    os.chown(path, entry.pw_uid, entry.pw_gid)
    for role, name, hidden in catalog_entries():
        target = root / f'{role}-{name}'
        shutil.copyfile(TARGET, target)
        target.chmod(0o755)
        guest.require(guest.sha(target) == guest.sha(TARGET), 'catalog:fixture-copy-digest')
        path = directories[role] / f'{CATALOG_PREFIX}{name}.desktop'
        with path.open('x', encoding='utf-8') as stream:
            stream.write('[Desktop Entry]\nType=Application\n'
                         f'Name=ONPC {role} {name}\nExec="{target}"\nTerminal=false\n'
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
                    'ChildOnly' if role == 'child' else 'OtherOnly': role}
        if role == 'other':
            expected['Masked'] = 'system'
        selected = [row for row in rows if row[0].startswith(CATALOG_PREFIX)]
        guest.require(len(selected) == len(expected) and
                      {row[0] for row in selected} == {
                          f'{CATALOG_PREFIX}{name}.desktop' for name in expected},
                      'catalog:scope-membership')
        for name, source in expected.items():
            row = next(row for row in selected if row[0] == f'{CATALOG_PREFIX}{name}.desktop')
            guest.require(row[1] == f'ONPC {source} {name}' and
                          row[4] == [str(root / f'{source}-{name}')], 'catalog:selected-target')
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


def provision_native():
    guest.guard()
    guest.enable_diagnostics()
    guest.require(not TARGET.parent.exists() and not TARGET.parent.is_symlink() and
                  not DESKTOP.exists() and not DESKTOP.is_symlink(),
                  'enforcement:fixture-collision')
    source = guest.PAYLOAD / 'fixtures/native/onpc-test-application'
    guest.require(source.is_file() and not source.is_symlink(), 'enforcement:fixture-missing')
    # The input guard verifies the transferred source. Never copy the fixture
    # image's placeholder home directory onto an actual account.
    # The guarded controller uses a private umask. Set traversability explicitly
    # on this newly owned directory so Unix DAC does not mimic policy denial.
    TARGET.parent.mkdir(mode=0o755)
    TARGET.parent.chmod(0o755)
    shutil.copyfile(source, TARGET)
    TARGET.chmod(0o755)
    DESKTOP.write_text('[Desktop Entry]\nType=Application\nName=ONPC Command Fixture\n'
                       f'Exec={TARGET}\nTerminal=false\n')
    DESKTOP.chmod(0o644)
    guest.require(guest.sha(TARGET) == guest.sha(source), 'enforcement:fixture-copy-digest')
    # Existing baseline accounts; no account lifecycle work is part of this case.
    accounts = {role: pwd.getpwnam(name).pw_uid for role, name in (
        ('child', 'onpc-child-riley'), ('other', 'onpc-child-jordan'),
        ('parent', 'onpc-parent-jamie'))}
    guest.require(len(set(accounts.values())) == 3, 'enforcement:fixture-identities')
    print('onpc-system: stage=native-enforcement-fixture outcome=ready', flush=True)
    return accounts


def launch_as(uid):
    """One directly owned PID becomes the one-shot fixture; no child to discover."""
    guest.guard()
    drop_identity(uid)
    sys.stdout.buffer.write(IDENTITY)
    sys.stdout.buffer.flush()
    try:
        os.execv(str(TARGET), [str(TARGET)])
    except OSError as error:
        if error.errno not in (errno.EACCES, errno.EPERM):
            raise guest.GuestError('enforcement:exec-failed') from None
        sys.stdout.buffer.write(DENIED)
        sys.stdout.buffer.flush()
        return 77


def observe_launch(uid, allowed):
    raw = guest.commands.run(
        ['/usr/bin/python3', '-B', str(guest.PAYLOAD / 'system_enforcement.py')],
        input=json.dumps({'uid': uid}).encode(), timeout=30, check=False, merge_stderr=False)
    expected = IDENTITY + (READY if allowed else DENIED)
    guest.require(raw == expected and guest.commands.last_returncode == (0 if allowed else 77),
                  'enforcement:expected-allow' if allowed else 'enforcement:expected-denial')


def record_rules(stage, uid, blocked, record):
    # Keep the actual source and compiled rules in the existing private text
    # diagnostics, including on assertion failure; public properties use roles.
    expected = f'deny_syslog perm=execute uid={uid} : path={TARGET}'
    texts = []
    for label, path in (('source', RULES), ('compiled', COMPILED_RULES)):
        guest.require(path.is_file() and not path.is_symlink(), 'enforcement:rules-missing')
        raw = path.read_bytes()
        (guest.commands.directory / f'native-{stage}-{label}.txt').write_bytes(raw)
        texts.append(raw.decode().splitlines())
        record(f'onpc.native.{stage}.{label}.sha256', guest.sha(path))
    guest.require(all((expected in lines) == blocked for lines in texts),
                  'enforcement:rule-state')


def native_policy_transition(accounts, record):
    """Allow, hard-deny and allow again, with an independent UID at every step."""
    guest.guard()
    record('onpc.native.fixture.sha256', guest.sha(TARGET))
    parent, child, other = (accounts[role] for role in ('parent', 'child', 'other'))
    applications = call(parent, 'ListApplications', '(u)', (child,))[0]
    matches = [row for row in applications if row[0] == DESKTOP_ID]
    guest.require(len(matches) == 1 and matches[0][4] == [str(TARGET)],
                  'enforcement:catalog-target')
    original = call(parent, 'GetPreferences', '(u)', (child,))[0]
    preferences = json.loads(original)
    guest.require(not preferences['apps'] and not preferences['parent_control_enabled'],
                  'enforcement:requires-clean-policy')
    other_before = call(parent, 'GetPreferences', '(u)', (other,))[0]
    try:
        for stage, blocked in (('allowed', False), ('hard', True), ('restored', False)):
            preferences['apps'] = ({DESKTOP_ID: {
                'state': 'permanent', 'targets': [str(TARGET)], 'patterns': [],
                'user_saved_match_rule': False}} if blocked else {})
            call(parent, 'SetPreferences', '(us)', (child, json.dumps(preferences)))
            record_rules(stage, child, blocked, record)
            observe_launch(child, not blocked)
            record(f'onpc.native.{stage}.child', 'denied' if blocked else 'allowed')
            observe_launch(other, True)
            record(f'onpc.native.{stage}.other', 'allowed')
            guest.require(call(parent, 'GetPreferences', '(u)', (other,))[0] == other_before,
                          'enforcement:other-preferences-changed')
            print(f'onpc-system: stage=native-{stage} outcome=passed', flush=True)
    finally:
        # This is the scenario's policy restoration. Outer VM baseline cleanup
        # remains authoritative on failure; never hide the original exception.
        failed = sys.exc_info()[0] is not None
        try:
            call(parent, 'SetPreferences', '(us)', (child, original))
            guest.require(call(parent, 'GetPreferences', '(u)', (child,))[0] == original,
                          'enforcement:policy-restore-mismatch')
        except Exception:
            record('onpc.native.policy-restoration', 'failed')
            if not failed:
                raise
        else:
            record('onpc.native.policy-restoration', 'passed')


def main():
    try:
        request = json.load(sys.stdin)
        guest.require(isinstance(request, dict) and set(request) == {'uid'},
                      'enforcement:launch-request')
        return launch_as(request['uid'])
    except (guest.GuestError, OSError, ValueError, KeyError, TypeError):
        print('onpc-system: stage=native-launch outcome=failed', file=sys.stderr)
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
