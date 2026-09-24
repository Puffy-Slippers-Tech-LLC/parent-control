"""Fixed system session operations over the owned VM's guarded SSH transport.

This module is also sent on stdin to the guest. It accepts fixture roles and
operation names only. It never observes or changes private product state.
"""

import json
import grp
import hashlib
import os
from pathlib import Path
import pwd
import re
import stat
import subprocess
import sys
import time


ACCOUNTS = {'parent': 'onpc-parent-jamie', 'standard': 'onpc-child-jordan'}
BINDINGS = {role + '-' + action: (role, action)
            for role in ACCOUNTS for action in ('switch-user', 'logout', 'lock', 'return-greeter')}
BINDINGS.update({'parent-command-context': ('parent', 'command-context'),
                 'parent-command-refused': ('parent', 'command-refused')})
LABELS = {'switch-user': 'Switching to the greeter',
          'logout': 'Logging out the fixture desktop', 'lock': 'Locking the fixture desktop',
          'return-greeter': 'Returning from the locked fixture session to the greeter'}
LABELS.update({'command-context': 'Verifying the administrator package command context',
               'command-refused': 'Checking command refusal outside the fixture desktop'})


class SessionError(RuntimeError):
    pass


def require(value, code):
    if not value:
        raise SessionError('session:' + code)


def call(argv):
    return subprocess.run(argv, stdin=subprocess.DEVNULL, capture_output=True,
                          text=True, check=True, timeout=15).stdout


def session_ids():
    rows = call(['/usr/bin/loginctl', 'list-sessions', '--no-legend', '--no-pager']).splitlines()
    require(len(rows) <= 32, 'session-bound')
    identities = []
    for row in rows:
        fields = row.split()
        require(len(fields) >= 2 and re.fullmatch(r'[a-zA-Z0-9]+', fields[0]), 'session-row')
        identity = fields[0]
        require(identity not in identities, 'duplicate-session')
        identities.append(identity)
    return identities


def sessions():
    result = {}
    for identity in session_ids():
        try:
            raw = call(['/usr/bin/loginctl', 'show-session', identity, '--no-pager',
                        '-p', 'User', '-p', 'Active', '-p', 'Remote', '-p', 'Class',
                        '-p', 'Type', '-p', 'Seat', '-p', 'LockedHint'])
        except subprocess.CalledProcessError:
            # Logout can remove a session between list and show. Confirm that
            # disappearance through a fresh read; never repeat the action.
            require(identity not in session_ids(), 'session-read')
            continue
        pairs = [line.split('=', 1) for line in raw.splitlines()]
        require(all(len(pair) == 2 for pair in pairs), 'session-properties')
        props = dict(pairs)
        require(len(props) == len(pairs) and set(props) == {
            'User', 'Active', 'Remote', 'Class', 'Type', 'Seat', 'LockedHint'}, 'session-properties')
        result[identity] = props
    return result


def local_graphical(props):
    return (props['Remote'] == 'no' and props['Seat'] == 'seat0'
            and props['Type'] in ('wayland', 'x11'))


def source_session(current, uid, *, locked=False):
    active = [(identity, props) for identity, props in current.items()
              if local_graphical(props) and props['Active'] == 'yes']
    require(len(active) == 1, 'active-session')
    identity, props = active[0]
    require(props['User'] == str(uid) and props['Class'] in ('user', 'user-early'), 'source-owner')
    require(props['LockedHint'] == ('yes' if locked else 'no'),
            'source-unlocked' if locked else 'source-locked')
    owned = [key for key, item in current.items() if local_graphical(item)
             and item['User'] == str(uid) and item['Class'] in ('user', 'user-early')]
    require(owned == [identity], 'ambiguous-source')
    return identity


def environment(account):
    runtime = Path('/run/user') / str(account.pw_uid)
    info = runtime.lstat()
    require(stat.S_ISDIR(info.st_mode) and info.st_uid == account.pw_uid, 'runtime-owner')
    info = (runtime / 'bus').lstat()
    require(stat.S_ISSOCK(info.st_mode) and info.st_uid == account.pw_uid, 'bus-owner')
    return {'HOME': account.pw_dir, 'USER': account.pw_name, 'LANG': 'C.UTF-8',
            'PATH': '/usr/bin:/bin', 'XDG_RUNTIME_DIR': str(runtime),
            'DBUS_SESSION_BUS_ADDRESS': 'unix:path=' + str(runtime / 'bus')}


def submit(action):
    """One selected route. Failure is uncertain input; there is no fallback."""
    require(action in LABELS, 'action')
    if action == 'logout':
        call(['/usr/bin/gnome-session-quit', '--logout', '--no-prompt'])
        return
    # Resolve the switching dependency before the first mutation.
    if action in ('switch-user', 'return-greeter'):
        import gi
        gi.require_version('Gdm', '1.0')
        from gi.repository import Gdm
        require(callable(Gdm.goto_login_session_sync), 'switch-api')
    # A lock/denial result must be observed before return-greeter. Preserve
    # that already locked session; no unlock, extra Lock or Shell navigation.
    if action != 'return-greeter':
        call(['/usr/bin/gdbus', 'call', '--session', '--dest', 'org.gnome.ScreenSaver',
              '--object-path', '/org/gnome/ScreenSaver', '--method', 'org.gnome.ScreenSaver.Lock'])
    if action in ('switch-user', 'return-greeter'):
        # GDM resolves the calling process's seat. An SSH process belongs to a
        # remote session even after setuid; the desktop user's service manager
        # runs this fixed command outside that remote session so GDM resolves
        # the sole graphical session we validated above.
        call(['/usr/bin/systemd-run', '--user', '--quiet', '--collect', '--wait',
              '--pipe', '--service-type=exec', '/usr/bin/python3', '-I', '-c',
              'import gi; gi.require_version("Gdm", "1.0"); '
              'from gi.repository import Gdm; '
              'raise SystemExit(0 if Gdm.goto_login_session_sync(None) else 1)'])


def destination(current, source, uid, action):
    """Independent system readback; product results are observed by the caller."""
    original = current.get(source)
    if original is not None:
        require(original['User'] == str(uid) and local_graphical(original)
                and original['Class'] in ('user', 'user-early'), 'source-replaced')
    if action == 'lock':
        require(original is not None, 'source-lost')
        return original['LockedHint'] == 'yes' and original['Active'] == 'yes'
    active = [props for props in current.values()
              if local_graphical(props) and props['Active'] == 'yes']
    require(len(active) <= 1, 'ambiguous-destination')
    greeter = bool(active and active[0]['Class'] == 'greeter')
    if action in ('switch-user', 'return-greeter'):
        require(original is not None, 'source-lost')
        return greeter and original['Active'] == 'no' and original['LockedHint'] == 'yes'
    return greeter and original is None


def execute(binding):
    require(binding in BINDINGS and os.geteuid() == 0, 'binding')
    role, action = BINDINGS[binding]
    account = pwd.getpwnam(ACCOUNTS[role])
    require(account.pw_uid >= 1000, 'fixture-identity')
    if action == 'command-refused':
        current = sessions()
        active = [props for props in current.values()
                  if local_graphical(props) and props['Active'] == 'yes']
        require(len(active) == 1 and active[0]['Class'] == 'greeter', 'expected-greeter')
        try:
            source_session(current, account.pw_uid)
        except SessionError as error:
            require(str(error) == 'session:source-owner', 'unexpected-refusal')
            return {'operation': binding, 'outcome': 'passed',
                    'interface': 'system session', 'wrong_entry_refused': True}
        require(False, 'wrong-entry-accepted')
    locked = action == 'return-greeter'
    source = source_session(sessions(), account.pw_uid, locked=locked)
    env = environment(account)
    administrator_gid = grp.getgrnam('sudo').gr_gid if action == 'command-context' else None
    os.initgroups(account.pw_name, account.pw_gid)
    os.setgid(account.pw_gid)
    os.setuid(account.pw_uid)
    os.environ.clear()
    os.environ.update(env)
    # Recheck after changing identity, immediately before the single submission.
    require(source_session(sessions(), account.pw_uid, locked=locked) == source, 'source-changed')
    if action == 'command-context':
        require(os.geteuid() == account.pw_uid and administrator_gid in os.getgroups(),
                'administrator-authority')
        # Read the FIX04 package as the bound desktop administrator, without
        # installing it or invoking a privileged product helper.
        path = Path('/var/lib/onpc-e2e-assets/package.deb')
        require(path.parent.resolve() == path.parent, 'package-parent')
        parent = path.parent.stat()
        require(parent.st_uid == 0 and not parent.st_mode & 0o022, 'package-parent')
        fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
        with os.fdopen(fd, 'rb') as stream:
            before = os.fstat(stream.fileno())
            require(stat.S_ISREG(before.st_mode) and before.st_uid == 0
                    and before.st_nlink == 1 and not before.st_mode & 0o022,
                    'package-owner')
            digest = hashlib.file_digest(stream, 'sha256').hexdigest()
            def identity(info):
                return (info.st_dev, info.st_ino, info.st_mode, info.st_uid, info.st_gid,
                        info.st_nlink, info.st_size, info.st_mtime_ns, info.st_ctime_ns)
            require(identity(os.fstat(stream.fileno())) == identity(before)
                    and identity(path.lstat()) == identity(before),
                    'package-changed')
        require(source_session(sessions(), account.pw_uid) == source, 'source-changed')
        return {'operation': binding, 'outcome': 'passed', 'interface': 'system session',
                'administrator': True, 'package_sha256': digest}
    submit(action)
    deadline = time.monotonic() + 45
    while not destination(sessions(), source, account.pw_uid, action):
        require(time.monotonic() < deadline, 'destination-timeout')
        time.sleep(.2)
    return {'operation': binding, 'outcome': 'passed', 'interface': 'system session',
            'source_retained': action != 'logout',
            'destination': 'locked' if action == 'lock' else 'greeter'}


def observe(transport, binding):
    """Shared controller leaf; the transport already binds the owned VM/attempt."""
    import watch_activity
    require(binding in BINDINGS, 'binding')
    role, action = BINDINGS[binding]
    with watch_activity.operation(LABELS[action] + ' [' + role + ']'):
        raw = transport.call(['/usr/bin/python3', '-I', '-', binding],
                             input=Path(__file__).read_bytes(), timeout=90)
    require(type(raw) is bytes and 0 < len(raw) <= 1024, 'response-bound')
    result = json.loads(raw)
    if action == 'command-refused':
        require(result == {'operation': binding, 'outcome': 'passed',
                           'interface': 'system session', 'wrong_entry_refused': True}, 'response')
        return result
    if action == 'command-context':
        require(type(result) is dict and set(result) == {
            'operation', 'outcome', 'interface', 'administrator', 'package_sha256'}
            and result['operation'] == binding and result['outcome'] == 'passed'
            and result['interface'] == 'system session' and result['administrator'] is True
            and type(result['package_sha256']) is str
            and re.fullmatch('[0-9a-f]{64}', result['package_sha256']), 'response')
        return result
    require(result == {'operation': binding, 'outcome': 'passed',
                       'interface': 'system session', 'source_retained': action != 'logout',
                       'destination': 'locked' if action == 'lock' else 'greeter'}, 'response')
    return result


if __name__ == '__main__':
    try:
        require(len(sys.argv) == 2, 'arguments')
        print(json.dumps(execute(sys.argv[1]), sort_keys=True))
    except SessionError as error:
        print(str(error), file=sys.stderr)
        sys.exit(1)
    except Exception:
        # Neither account names nor command output belongs in shared evidence.
        print('session:operation-failed', file=sys.stderr)
        sys.exit(1)
