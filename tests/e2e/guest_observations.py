"""Fixed guest observation programs; no caller-supplied code or arguments."""

# Fixed read-only probe. Only a count and digest leave the guest; no paths,
# account data, source contents, or guest-supplied expected identities.
ASSETS = '''import hashlib,json,pathlib,stat
root=pathlib.Path('/var/lib/onpc-e2e-assets')
assert root.resolve()==root
files={}
directories=set()
for p in [root,*sorted(root.rglob('*'))]:
    s=p.lstat()
    assert s.st_uid==s.st_gid==0 and p.resolve()==p
    if stat.S_ISDIR(s.st_mode):
        assert stat.S_IMODE(s.st_mode)==493
        directories.add(p.relative_to(root).as_posix())
        continue
    assert stat.S_ISREG(s.st_mode) and s.st_nlink==1 and stat.S_IMODE(s.st_mode)==420
    h=hashlib.sha256()
    with p.open('rb') as stream:
        for block in iter(lambda: stream.read(1048576),b''): h.update(block)
    files[p.relative_to(root).as_posix()]=h.hexdigest()
expected_directories={'.'}
for name in files:
    expected_directories.update(p.as_posix() for p in pathlib.PurePosixPath(name).parents)
assert directories==expected_directories
encoded=(json.dumps(files,sort_keys=True,indent=2)+'\\n').encode()
print(json.dumps({'files':len(files),'sha256':hashlib.sha256(encoded).hexdigest()},sort_keys=True))
'''


# All session names and identifiers stay inside this guest process. This is a
# read-only corroboration, never a replacement for graphical input/screens.
GREETER = '''import json,subprocess,time
def call(*args):
    return subprocess.run(args, capture_output=True, text=True, check=True, timeout=10).stdout
deadline = time.monotonic() + 90
while time.monotonic() < deadline:
    active = call('systemctl', 'is-active', 'display-manager').strip() == 'active'
    user_session = False
    greeter = False
    for row in call('loginctl', 'list-sessions', '--no-legend', '--no-pager').splitlines():
        session = row.split()[0]
        props = dict(line.split('=', 1) for line in call(
            'loginctl', 'show-session', session, '-p', 'Class', '-p', 'Active', '-p', 'Type',
            '-p', 'Remote', '-p', 'Service', '-p', 'User').splitlines())
        # Our root SSH observation creates its own logind user session. Only
        # that non-graphical observation identity is excluded from this gate.
        observer = (props.get('User') == '0' and props.get('Service') == 'sshd' and
                    props.get('Remote') == 'yes' and props.get('Type') not in ('wayland', 'x11'))
        user_session |= props.get('Class') in ('user', 'user-early') and not observer
        greeter |= props.get('Class') == 'greeter' and props.get('Active') == 'yes' and props.get('Type') in ('wayland', 'x11')
    if active and greeter and not user_session:
        print('greeter-ready')
        break
    time.sleep(0.5)
else:
    print(json.dumps({'display_manager_active': active, 'active_graphical_greeter': greeter,
                      'unexpected_user_session': user_session}, sort_keys=True))
    raise SystemExit(1)
'''


# Canonical fixture login only. Resolve its real guest UID, never a preview UID.
# This probe cannot start a session or accept an SSH/TTY session as a GUI login.
PARENT_SESSION = '''import pwd,subprocess,time
expected = str(pwd.getpwnam('onpc-parent-jamie').pw_uid)
deadline = time.monotonic() + 90
def call(*args):
    remaining = deadline - time.monotonic()
    assert remaining > 0
    return subprocess.run(args, capture_output=True, text=True, check=True,
                          timeout=min(10, remaining)).stdout
while time.monotonic() < deadline:
    rows = call('loginctl', 'list-sessions', '--no-legend', '--no-pager').splitlines()
    assert len(rows) <= 32
    parents = 0
    unexpected = False
    for row in rows:
        props = dict(line.split('=', 1) for line in call(
            'loginctl', 'show-session', row.split()[0], '-p', 'Class', '-p', 'Active',
            '-p', 'Type', '-p', 'Remote', '-p', 'Service', '-p', 'User').splitlines())
        observer = (props.get('User') == '0' and props.get('Service') == 'sshd' and
                    props.get('Remote') == 'yes' and props.get('Type') not in ('wayland', 'x11'))
        if props.get('Class') not in ('user', 'user-early') or observer:
            continue
        parent = (props.get('User') == expected and props.get('Active') == 'yes' and
                  props.get('Remote') == 'no' and props.get('Type') in ('wayland', 'x11') and
                  props.get('Service') == 'gdm-password')
        parents += int(parent)
        unexpected |= not parent
    if parents == 1 and not unexpected:
        print('parent-session-ready')
        break
    time.sleep(0.5)
else:
    print('parent-session-not-ready')
    raise SystemExit(1)
'''
