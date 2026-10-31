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

# Same independent tree oracle, with package metadata from dpkg-deb rather
# than any delivered manifest. No installation or expected host values enter.
UPGRADE_ASSETS = ASSETS.replace("print(json.dumps({'files':len(files),'sha256':hashlib.sha256(encoded).hexdigest()},sort_keys=True))", '''import subprocess
packages={}
for label,name in (('current','package.deb'),('previous','previous/package.deb')):
    values=subprocess.run(['/usr/bin/dpkg-deb','-f',str(root/name),'Package','Version','Architecture'],
                          check=True,capture_output=True,text=True,timeout=30).stdout.splitlines()
    fields=dict(row.split(': ',1) for row in values)
    assert set(fields)=={'Package','Version','Architecture'}
    assert fields['Package']=='oh-no-parent-control' and fields['Architecture']=='amd64'
    assert 0<len(fields['Version'])<=128
    packages[label]={'name':fields['Package'],'version':fields['Version'],
                     'architecture':fields['Architecture'],'sha256':files[name]}
assert packages['previous']['version']=='1.2+ppa1~ubuntu26.04.1'
assert packages['current']['sha256']!=packages['previous']['sha256']
subprocess.run(['/usr/bin/dpkg','--compare-versions',packages['current']['version'],'gt',
                packages['previous']['version']],check=True,capture_output=True,timeout=30)
print(json.dumps({'files':len(files),'sha256':hashlib.sha256(encoded).hexdigest(),
                  'packages':packages},sort_keys=True))''')

# Separate fixed RPM probe; the caller selects it from its verified package
# alias, already matched to the VM's explicit package_format declaration.
UPGRADE_ASSETS_RPM = ASSETS.replace("print(json.dumps({'files':len(files),'sha256':hashlib.sha256(encoded).hexdigest()},sort_keys=True))", '''import re,subprocess
assert 'package.rpm' in files and 'previous/package.rpm' in files
assert 'package.deb' not in files and 'previous/package.deb' not in files
packages={}
for label,name in (('current','package.rpm'),('previous','previous/package.rpm')):
    values=subprocess.run(['/usr/bin/rpm','-qp','--queryformat',
                          '%{NAME}\\n%{EPOCHNUM}:%{VERSION}-%{RELEASE}\\n%{ARCH}\\n',str(root/name)],
                          check=True,capture_output=True,text=True,timeout=30).stdout.splitlines()
    assert len(values)==3 and all(value and '\\t' not in value for value in values)
    assert values[0]=='oh-no-parent-control' and values[2]=='x86_64'
    assert 0<len(values[1])<=128
    packages[label]={'name':values[0],'version':values[1],
                     'architecture':values[2],'sha256':files[name]}
assert packages['previous']['version']=='0:1.3-0.1.dev.fc44'
assert packages['current']['sha256']!=packages['previous']['sha256']
versions=[re.fullmatch(r'([0-9]+):([A-Za-z0-9][A-Za-z0-9._+~^]*)-([A-Za-z0-9][A-Za-z0-9._+~^]*)',
                      packages[label]['version']) for label in ('current','previous')]
assert all(versions)
for current,previous in zip(versions[0].groups(),versions[1].groups()):
    comparison=subprocess.run(['/usr/bin/rpm','--eval',
        '%{lua:print(rpm.vercmp("'+current+'","'+previous+'"))}'],
        check=True,capture_output=True,text=True,timeout=30).stdout.strip()
    if comparison=='1':
        break
    assert comparison=='0'
else:
    raise AssertionError('RPM upgrade must be newer')
print(json.dumps({'files':len(files),'sha256':hashlib.sha256(encoded).hexdigest(),
                  'packages':packages},sort_keys=True))''')


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
    assert (proc/'exe').resolve() == pathlib.Path('/usr/sbin/agetty').resolve(strict=True)
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

# Advisory feasibility probes, before and after one console selection. Linux's
# public VC devices expose logical text independently of framebuffer pixels:
# https://docs.kernel.org/admin-guide/devices.html (character major 7).
# Never export text, cursor positions or account names, and never use this
# observation as a recipient proof or authorization to enter credentials.
_VT6_PROVIDER_DIAGNOSTIC = '''import errno,json,os,pathlib,re,stat,sys
active_path = pathlib.Path('/sys/class/tty/tty0/active')

def inspect(path, minor, unicode):
    fd = None
    try:
        fd = os.open(path, os.O_RDONLY | os.O_NONBLOCK | os.O_NOFOLLOW | os.O_CLOEXEC)
        before = os.fstat(fd)
        if not (stat.S_ISCHR(before.st_mode) and before.st_uid == 0
                and before.st_rdev == os.makedev(7, minor)):
            return 'invalid', 'unavailable'
        raw = os.pread(fd, 65540 if unicode else 4, 0)
        after = os.fstat(fd)
        current = os.stat(path, follow_symlinks=False)
        fields = ('st_dev', 'st_ino', 'st_mode', 'st_uid', 'st_gid', 'st_rdev')
        if any(getattr(info, key) != getattr(before, key)
               for info in (after, current) for key in fields):
            return 'invalid', 'unavailable'
        if unicode:
            if not raw or len(raw) > 65536 or len(raw) % 4:
                return 'invalid', 'unavailable'
            text = raw.decode('utf-32-le' if sys.byteorder == 'little' else 'utf-32-be')
            kind = 'login' if text.rstrip().endswith('login:') else 'other' if text.strip() else 'blank'
            return 'readable', kind
        return ('readable' if len(raw) == 4 else 'invalid'), 'unavailable'
    except UnicodeError:
        return 'invalid', 'unavailable'
    except OSError as error:
        return {errno.ENOENT: 'missing', errno.ENXIO: 'unallocated',
                errno.EACCES: 'denied', errno.EPERM: 'denied',
                errno.EOPNOTSUPP: 'unsupported', errno.ENODATA: 'unsupported',
                errno.ELOOP: 'invalid'}.get(error.errno, 'error'), 'unavailable'
    finally:
        if fd is not None:
            os.close(fd)

def snapshot():
    active_before = active_path.read_text().strip()
    assert re.fullmatch(r'tty[1-9][0-9]?', active_before)
    unicode_status, text_state = inspect('/dev/vcsu6', 70, True)
    attribute_status, _ = inspect('/dev/vcsa6', 134, False)
    return {'active_vt6': active_before == 'tty6',
        'active_unchanged': active_path.read_text().strip() == active_before,
        'unicode_status': unicode_status, 'attribute_status': attribute_status,
        'login_prompt_present': text_state == 'login', 'text_state': text_state}
'''

VT6_PROVIDER_DIAGNOSTIC = _VT6_PROVIDER_DIAGNOSTIC + '''print(json.dumps(snapshot(), sort_keys=True))
'''

# Selecting an unused virtual console can start its getty asynchronously.
# Wait only for public logical text; never send a key again or enter a name.
VT6_SELECTED_PROVIDER_DIAGNOSTIC = _VT6_PROVIDER_DIAGNOSTIC + '''import time
deadline = time.monotonic() + 10
while True:
    result = snapshot()
    if (result['active_vt6'] and result['active_unchanged']
            and result['login_prompt_present']) or time.monotonic() >= deadline:
        break
    time.sleep(0.2)
print(json.dumps(result, sort_keys=True))
'''

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
assert (proc/'exe').resolve() == pathlib.Path(recipient_executable).resolve(strict=True)
credentials = dict(line.split(':',1) for line in (proc/'status').read_text().splitlines())
assert [int(value) for value in credentials['Uid'].split()] == [0]*4
assert identity() == starttime
assert re.fullmatch(r'[0-9]{1,20}', starttime) and int(starttime) > 0
assert read_boot() == recipient_boot
check_active_terminal()
encoded = json.dumps([recipient_boot, terminal_unit, pid, starttime],
                     separators=(',', ':')).encode('ascii')
result = {'probe': recipient_probe, 'boot_sha256': recipient_boot,
          'recipient_sha256': hashlib.sha256(encoded).hexdigest()}
if 'logical_prompt' in globals():
    result['logical_prompt'] = logical_prompt
print(json.dumps(result, sort_keys=True))
'''

VT6_GETTY_IDENTITY = (VT6 + _RECIPIENT_BOOT + _GETTY +
    "recipient_probe = 'vt6-getty-identity'\nrecipient_executable = '/usr/sbin/agetty'\n" +
    _RECIPIENT_RESULT)
VT6_PASSWORD_IDENTITY = (VT6 + _RECIPIENT_BOOT + _LOGIN_PASSWORD +
    "recipient_probe = 'vt6-password-identity'\nrecipient_executable = '/usr/bin/login'\n" +
    _RECIPIENT_RESULT)

# External Linux console adapter. Read logical Unicode cells, never pixels or
# cursor coordinates. Exact prompt/fixture echo and unchanged device identity
# supplement the same process, foreground, boot and no-echo checks above.
# Only safe prompt tags and recipient digests leave the guest.
_VT6_LOGICAL_TEXT = '''import stat,sys,time
def console_text():
    check_active_terminal()
    path = '/dev/vcsu6'
    fd = os.open(path, os.O_RDONLY | os.O_NONBLOCK | os.O_NOFOLLOW | os.O_CLOEXEC)
    try:
        before = os.fstat(fd)
        assert stat.S_ISCHR(before.st_mode) and before.st_uid == 0
        assert before.st_rdev == os.makedev(7, 70)
        raw = os.pread(fd, 65540, 0)
        assert 0 < len(raw) <= 65536 and len(raw) % 4 == 0
        text = raw.decode('utf-32-le' if sys.byteorder == 'little' else 'utf-32-be')
        fields = ('st_dev', 'st_ino', 'st_mode', 'st_uid', 'st_gid', 'st_rdev')
        for current in (os.fstat(fd), os.stat(path, follow_symlinks=False)):
            assert all(getattr(current, key) == getattr(before, key) for key in fields)
        check_active_terminal()
        return ' '.join(text.split())
    finally:
        os.close(fd)

def verify_console_prompt(kind):
    assert kind in ('login', 'password')
    suffix = ' login:' if kind == 'login' else ' login: onpc-parent-jamie Password:'
    deadline = time.monotonic() + 10
    while True:
        text = console_text()
        if text.endswith(suffix):
            # A second complete fresh read rejects a changing console. No
            # input, focus change or recipient replacement occurs in this wait.
            assert console_text() == text
            return
        assert time.monotonic() < deadline
        time.sleep(0.2)
'''

VT6_GETTY_TEXT_IDENTITY = (VT6 + _RECIPIENT_BOOT + _GETTY + _VT6_LOGICAL_TEXT +
    "logical_prompt = 'login'\nverify_console_prompt(logical_prompt)\n"
    "recipient_probe = 'vt6-getty-identity'\nrecipient_executable = '/usr/sbin/agetty'\n" +
    _RECIPIENT_RESULT)
VT6_PASSWORD_TEXT_IDENTITY = (VT6 + _RECIPIENT_BOOT + _VT6_LOGICAL_TEXT +
    "logical_prompt = 'password'\nverify_console_prompt(logical_prompt)\n" + _LOGIN_PASSWORD +
    "verify_console_prompt(logical_prompt)\n"
    "recipient_probe = 'vt6-password-identity'\nrecipient_executable = '/usr/bin/login'\n" +
    _RECIPIENT_RESULT)

# Advisory only: diagnose prompt expiry across a slow host provenance check.
# Read only the selected unit; never terminal content, argv or account records.
# Digests remain private to the transport parser and cannot advance its gate.
VT6_LOGIN_DIAGNOSTIC = VT6 + _RECIPIENT_BOOT + '''import subprocess
check_active_terminal()
config = pathlib.Path('/etc/login.defs').read_text()
assert len(config) <= 131072
values = [line.split('#', 1)[0].split()[1:] for line in config.splitlines()
          if line.split('#', 1)[0].split()[:1] == ['LOGIN_TIMEOUT']]
assert len(values) <= 1
assert not values or (len(values[0]) == 1 and re.fullmatch(r'[0-9]{1,5}', values[0][0]))
timeout = int(values[0][0]) if values else 60
assert 0 <= timeout <= 86400
version = subprocess.run(['/usr/bin/login', '--version'], capture_output=True,
                         text=True, check=True, timeout=10).stdout
match = re.fullmatch(r'login from util-linux ([0-9]+(?:\\.[0-9]+){1,2})\\n', version)
assert match is not None
pid = int(subprocess.run(['systemctl', 'show', terminal_unit,
    '--property=MainPID', '--value'], capture_output=True, text=True,
    check=True, timeout=10).stdout.strip())
assert pid > 1
proc = pathlib.Path('/proc') / str(pid)
starttime = (proc/'stat').read_text().rpartition(') ')[2].split()[19]
assert re.fullmatch(r'[0-9]{1,20}', starttime)
executable = {pathlib.Path('/usr/bin/login'): 'login',
              pathlib.Path('/usr/sbin/agetty'): 'agetty'}.get((proc/'exe').resolve(), 'other')
assert (proc/'stat').read_text().rpartition(') ')[2].split()[19] == starttime
assert read_boot() == recipient_boot
check_active_terminal()
encoded = json.dumps([recipient_boot, terminal_unit, pid, starttime],
                     separators=(',', ':')).encode('ascii')
print(json.dumps({'executable': executable, 'login_timeout_seconds': timeout,
    'timeout_source': 'login.defs' if values else 'default', 'login_version': match[1],
    'recipient_sha256': hashlib.sha256(encoded).hexdigest()}, sort_keys=True))
'''

# Follow only the selected login's direct child, using the same detached-login /
# new-shell-session semantics as the sudo observer. This proves lineage and
# foreground ownership, deliberately NOT Bash command-input readiness.
VT6_SHELL_LINEAGE = VT6 + _RECIPIENT_BOOT + '''import pwd,stat,subprocess
uid = pwd.getpwnam('onpc-parent-jamie').pw_uid
assert uid > 0
def leader():
    check_active_terminal()
    value = int(subprocess.run(['systemctl','show',terminal_unit,
        '--property=MainPID','--value'],capture_output=True,text=True,
        check=True,timeout=10).stdout.strip())
    assert value > 1
    return value
def process(value):
    path = pathlib.Path('/proc') / str(value)
    fields = (path/'stat').read_text().rpartition(') ')[2].split()
    assert len(fields) >= 20 and fields[0] in ('R', 'S')
    assert re.fullmatch(r'[0-9]{1,20}', fields[19]) and int(fields[19]) > 0
    return path, fields
def executable(path, expected, owner):
    binary = pathlib.Path(expected)
    info = binary.stat()
    assert stat.S_ISREG(info.st_mode) and info.st_uid == info.st_gid == 0
    assert not stat.S_IMODE(info.st_mode) & 0o022
    assert (path/'exe').resolve(strict=True) == binary
    credentials = dict(line.split(':',1) for line in (path/'status').read_text().splitlines())
    assert [int(value) for value in credentials['Uid'].split()] == [owner]*4
pid = leader()
proc, before_login = process(pid)
children_path = proc/'task'/str(pid)/'children'
children = children_path.read_text().split()
assert len(children) == 1
shell_pid = int(children[0])
assert shell_pid > 1 and shell_pid != pid
shell, before_shell = process(shell_pid)
def snapshot():
    assert leader() == pid
    executable(proc, '/usr/bin/login', 0)
    executable(shell, '/usr/bin/bash', uid)
    current_login = process(pid)[1]
    current_shell = process(shell_pid)[1]
    # login remains root in its original session, with no controlling terminal.
    assert [int(v) for v in current_login[2:6]] == [pid,pid,0,-1]
    assert [int(v) for v in current_shell[1:6]] == [
        pid,shell_pid,shell_pid,terminal_device,shell_pid]
    assert int(current_shell[19]) >= int(current_login[19])
    for before, after in ((before_login,current_login), (before_shell,current_shell)):
        assert before[1:6] == after[1:6] and before[19] == after[19]
    assert children_path.read_text().split() == children
    assert not (shell/'task'/str(shell_pid)/'children').read_text().split()
    assert (shell/'cmdline').read_bytes() == b'-bash\\0'
    for descriptor in ('0', '1', '2'):
        info = (shell/'fd'/descriptor).stat()
        assert stat.S_ISCHR(info.st_mode) and info.st_rdev == terminal_device
    check_active_terminal()
snapshot()
fd = os.open(terminal_path, os.O_RDONLY | os.O_NONBLOCK | os.O_NOCTTY | os.O_NOFOLLOW)
try:
    info = os.fstat(fd)
    assert stat.S_ISCHR(info.st_mode) and info.st_rdev == terminal_device
    # The SSH observer does not own this controlling terminal. tcgetpgrp on
    # its descriptor therefore refuses with ENOTTY; snapshot reads the pinned
    # shell's kernel tty/pgrp/session/tpgid fields instead, before and after open.
    snapshot()
    assert read_boot() == recipient_boot
    check_active_terminal()
finally:
    os.close(fd)
encoded = json.dumps([recipient_boot, terminal_unit, pid, before_login[19]],
                     separators=(',', ':')).encode('ascii')
recipient_digest = hashlib.sha256(encoded).hexdigest()
shell_digest = hashlib.sha256(json.dumps([recipient_boot, terminal_unit,
    pid, before_login[19], shell_pid, before_shell[19]],
    separators=(',', ':')).encode('ascii')).hexdigest()
'''

VT6_SHELL_IDENTITY = VT6_SHELL_LINEAGE + '''
print(json.dumps({'probe': 'vt6-shell-identity', 'boot_sha256': recipient_boot,
    'recipient_sha256': recipient_digest, 'shell_sha256': shell_digest}, sort_keys=True))
'''
