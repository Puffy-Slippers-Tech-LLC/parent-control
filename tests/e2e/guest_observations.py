"""Fixed guest observation programs; no caller-supplied code or arguments."""

# A boot identity is continuity evidence, not a supplied scenario label. Only
# its digest reaches the controller; raw machine identifiers remain in guest.
from vm_transport import BOOT_SHA256_PROBE as BOOT
from terminal_observations import SERIAL, VT6

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
# Fixed adapters below select the surface; callers cannot supply a terminal,
# account or service. The same other-user exclusion applies to every surface.
_PARENT_SESSION = '''import pwd,subprocess,time
expected = str(pwd.getpwnam('onpc-parent-jamie').pw_uid)
deadline = time.monotonic() + 90
def call(*args):
    check_active_terminal()
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
            '-p', 'Type', '-p', 'Remote', '-p', 'Service', '-p', 'User', '-p', 'TTY').splitlines())
        observer = (props.get('User') == '0' and props.get('Service') == 'sshd' and
                    props.get('Remote') == 'yes' and props.get('Type') not in ('wayland', 'x11'))
        if props.get('Class') not in ('user', 'user-early') or observer:
            continue
        parent = (props.get('User') == expected and props.get('Active') == 'yes' and
                  props.get('Remote') == 'no' and matches_surface(props))
        parents += int(parent)
        unexpected |= not parent
    if parents == 1 and not unexpected:
        check_active_terminal()
        print(session_result + '-ready')
        break
    time.sleep(0.5)
else:
    print(session_result + '-not-ready')
    raise SystemExit(1)
'''

PARENT_SESSION = '''def check_active_terminal():
    pass
def matches_surface(props):
    return props.get('Type') in ('wayland', 'x11') and props.get('Service') == 'gdm-password'
session_result = 'parent-session'
''' + _PARENT_SESSION

# These are read-only logind session gates, not shell-readiness or password
# recipient proofs. VT6 additionally refuses a foreground change during reads.
SERIAL_SESSION = SERIAL + '''def matches_surface(props):
    return (props.get('Type') == 'tty' and props.get('TTY') == 'ttyS0'
            and props.get('Service') == 'login')
session_result = 'serial-session'
''' + _PARENT_SESSION

VT6_SESSION = VT6 + '''def matches_surface(props):
    return (props.get('Type') == 'tty' and props.get('TTY') == 'tty6'
            and props.get('Service') == 'login')
session_result = 'vt6-session'
''' + _PARENT_SESSION


# Read terminal attributes and the exact systemd-owned login process, without
# consuming input or changing termios. A terminal needs its own selected-role
# and prompt evidence; the GDM masked-field needle cannot establish that.
# These probes independently establish the terminal's no-echo recipient.
_LOGIN_PASSWORD = '''import os,pathlib,stat,subprocess,termios
check_active_terminal()
pid = int(subprocess.run(['systemctl','show',terminal_unit,
                         '--property=MainPID','--value'], capture_output=True,
                        text=True, check=True, timeout=10).stdout.strip())
assert pid > 1
proc = pathlib.Path('/proc') / str(pid)
assert (proc/'exe').resolve() == pathlib.Path('/usr/bin/login')
args = (proc/'cmdline').read_bytes().split(b'\\0')
# util-linux intentionally wipes the supplied username before PAM. Identity
# selection is therefore asserted from the real terminal echo by the worker.
# Accept only the stock password-authenticated argv; refuse -f/autologin.
visible = [value for value in args if value]
assert visible and visible[0] in (b'/bin/login', b'/usr/bin/login', b'login')
assert visible[1:] in ([b'--'], [b'-p',b'--'])
def identity():
    check_active_terminal()
    fields = (proc/'stat').read_text().rpartition(') ')[2].split()
    assert len(fields) >= 20
    # Documented proc_pid_stat fields: pgrp, session, tty_nr, tpgid, starttime.
    assert [int(value) for value in fields[2:6]] == [pid,pid,terminal_device,pid]
    return fields[19]
starttime = identity()
fd = os.open(terminal_path, os.O_RDONLY | os.O_NONBLOCK | os.O_NOCTTY | os.O_NOFOLLOW)
try:
    device = os.fstat(fd)
    assert stat.S_ISCHR(device.st_mode) and device.st_rdev == terminal_device
    assert (proc/'fd/0').stat().st_rdev == device.st_rdev
    flags = termios.tcgetattr(fd)[3]
    assert flags & termios.ICANON and not flags & (termios.ECHO | termios.ECHONL)
    assert (proc/'exe').resolve() == pathlib.Path('/usr/bin/login')
    assert (proc/'cmdline').read_bytes().split(b'\\0') == args
    assert identity() == starttime
finally:
    os.close(fd)
'''

SERIAL_PASSWORD = SERIAL + _LOGIN_PASSWORD + "print('serial-password-safe')\n"
VT6_PASSWORD = VT6 + _LOGIN_PASSWORD + "print('vt6-password-safe')\n"

# Qualification-only readiness before typing the fixed, nonsecret fixture name.
# No password is exposed by this probe; the later login proof remains mandatory.
_GETTY = '''import stat,subprocess,termios,time
deadline = time.monotonic() + 30
while True:
    check_active_terminal()
    pid = int(subprocess.run(['systemctl','show',terminal_unit,
        '--property=MainPID','--value'],capture_output=True,text=True,
        check=True,timeout=10).stdout.strip())
    if pid > 1:
        break
    assert time.monotonic() < deadline
    time.sleep(0.2)
proc = pathlib.Path('/proc') / str(pid)
def identity():
    check_active_terminal()
    assert (proc/'exe').resolve() == pathlib.Path('/usr/sbin/agetty')
    fields = (proc/'stat').read_text().rpartition(') ')[2].split()
    assert len(fields) >= 20
    assert [int(value) for value in fields[2:6]] == [pid,pid,terminal_device,pid]
    return fields[19]
starttime = identity()
fd = os.open(terminal_path,os.O_RDONLY|os.O_NONBLOCK|os.O_NOCTTY|os.O_NOFOLLOW)
try:
    device = os.fstat(fd)
    assert stat.S_ISCHR(device.st_mode) and device.st_rdev == terminal_device
    assert (proc/'fd/0').stat().st_rdev == terminal_device
    flags = termios.tcgetattr(fd)[3]
    # agetty's reload-capable virtual-console prompt uses raw input and
    # userspace echo; other builds retain canonical input with kernel echo.
    # This gate permits only the fixed NONSECRET fixture name, never a password.
    # Mixed modes are not either supported prompt contract. login(1)'s later
    # canonical/no-echo password proof remains separate and unchanged.
    prompt_mode = flags & (termios.ICANON | termios.ECHO)
    assert prompt_mode in (0, termios.ICANON | termios.ECHO)
    assert identity() == starttime
finally:
    os.close(fd)
'''

VT6_GETTY = VT6 + _GETTY + "print('vt6-getty-ready')\n"

# The legacy fixed-token probes intentionally remain observation-local. These
# separate programs retain the same predicates but export bounded digests for
# the controller's ordered, cross-observation recipient gate. agetty execs
# login, preserving PID/starttime; executable identity is checked per phase,
# rather than hashed into the continuity identity. Raw process/boot data never
# leaves the guest. No worker-supplied identity, argument or program is accepted.
_RECIPIENT_BOOT = '''import hashlib,json,re
def read_boot():
    value = pathlib.Path('/proc/sys/kernel/random/boot_id').read_text()
    assert re.fullmatch(r'[0-9a-f]{8}(?:-[0-9a-f]{4}){3}-[0-9a-f]{12}\\n', value)
    # Match vm_transport.BOOT_SHA256_PROBE, including the kernel's newline.
    return hashlib.sha256(value.encode('ascii')).hexdigest()
recipient_boot = read_boot()
'''

_RECIPIENT_RESULT = '''# Recheck the selected unit, executable and process incarnation
# after the terminal checks; do not follow a replacement unit leader.
check_active_terminal()
assert int(subprocess.run(['systemctl','show',terminal_unit,
    '--property=MainPID','--value'],capture_output=True,text=True,
    check=True,timeout=10).stdout.strip()) == pid
assert (proc/'exe').resolve() == pathlib.Path(recipient_executable)
credentials = dict(line.split(':',1) for line in (proc/'status').read_text().splitlines())
assert [int(value) for value in credentials['Uid'].split()] == [0]*4
assert identity() == starttime
assert re.fullmatch(r'[0-9]{1,20}', starttime) and int(starttime) > 0
assert read_boot() == recipient_boot
check_active_terminal()
encoded = json.dumps([recipient_boot, terminal_unit, pid, starttime],
                     separators=(',', ':')).encode('ascii')
print(json.dumps({'probe': recipient_probe, 'boot_sha256': recipient_boot,
                  'recipient_sha256': hashlib.sha256(encoded).hexdigest()}, sort_keys=True))
'''

VT6_GETTY_IDENTITY = (VT6 + _RECIPIENT_BOOT + _GETTY +
    "recipient_probe = 'vt6-getty-identity'\nrecipient_executable = '/usr/sbin/agetty'\n" +
    _RECIPIENT_RESULT)
VT6_PASSWORD_IDENTITY = (VT6 + _RECIPIENT_BOOT + _LOGIN_PASSWORD +
    "recipient_probe = 'vt6-password-identity'\nrecipient_executable = '/usr/bin/login'\n" +
    _RECIPIENT_RESULT)
