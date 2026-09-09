"""Fixed read-only installation probes; customer input owns package changes.

These establish package state, not authenticated input, notice visibility,
payload integrity or readiness. The journey must compare the returned package
digest to VerifiedInputs and separately retain those remaining assertions.
"""

COMMON = '''import hashlib,json,pathlib,stat,subprocess
package = 'oh-no-parent-control'
def call(*args):
    result = subprocess.run(args, capture_output=True, text=True, check=True, timeout=15)
    assert len(result.stdout) <= 4194304
    return result.stdout
def regular(path):
    p = pathlib.Path(path)
    s = p.lstat()
    assert p.resolve() == p and stat.S_ISREG(s.st_mode)
    assert s.st_uid == s.st_gid == 0 and s.st_nlink == 1
    assert not stat.S_IMODE(s.st_mode) & 0o022
    return p
def reboot_packages():
    p = pathlib.Path('/run/reboot-required.pkgs')
    # lexists semantics: dangling symlinks must fail, not look absent.
    try:
        p.lstat()
    except FileNotFoundError:
        return []
    raw = regular(str(p)).read_text()
    assert len(raw) <= 65536
    return raw.splitlines()
'''

# Query the complete package database successfully instead of interpreting a
# failed single-package query (which could be a database error) as absence.
# Residual package/config state also disqualifies the clean baseline.
ABSENT = COMMON + '''rows = call('/usr/bin/dpkg-query', '-W', '-f=${Package}\\t${db:Status-Status}\\n').splitlines()
assert rows
for row in rows:
    fields = row.split('\\t')
    assert len(fields) == 2 and all(fields)
    assert fields[0] != package
for name in ('/usr/lib/oh-no-parent-control', '/etc/oh-no-parent-control',
             '/var/lib/oh-no-parent-control', '/usr/bin/oh-no-parent-control',
             '/usr/bin/oh-no-parent-control-parent',
             '/usr/libexec/oh-no-parent-control-broker'):
    try:
        pathlib.Path(name).lstat()
    except FileNotFoundError:
        continue
    raise AssertionError('product-payload-present')
assert package not in reboot_packages()
print('package-absent')
'''

INSTALLED = COMMON + '''asset = regular('/var/lib/onpc-e2e-assets/package.deb')
expected = [call('/usr/bin/dpkg-deb', '-f', str(asset), field).strip()
            for field in ('Package', 'Version', 'Architecture')]
assert expected[0] == package and all(expected)
assert all('\\n' not in value and '\\t' not in value for value in expected)
actual = call('/usr/bin/dpkg-query', '-W',
              '-f=${Package}\\t${Version}\\t${Architecture}\\t${Status}\\n', package)
assert actual == '\\t'.join([*expected, 'install ok installed']) + '\\n'
regular('/run/reboot-required')
assert package in reboot_packages()
h = hashlib.sha256()
with asset.open('rb') as stream:
    for block in iter(lambda: stream.read(1048576), b''): h.update(block)
print(json.dumps({'package_sha256': h.hexdigest(), 'installed_identity_verified': True,
                  'product_reboot_required': True}, sort_keys=True))
'''

# This setup observation runs before the worker types the install command.
# Only fixed implementation/path fields and a numeric Ubuntu package version
# leave the guest; unfamiliar implementations and read errors fail closed.
SUDO_IMPLEMENTATION = COMMON + '''import re
executable = pathlib.Path('/usr/bin/sudo').resolve(strict=True)
assert executable == pathlib.Path('/usr/lib/cargo/bin/sudo')
regular(str(executable))
assert call('/usr/bin/dpkg-query', '-S', str(executable)) == 'sudo-rs: /usr/lib/cargo/bin/sudo\\n'
row = call('/usr/bin/dpkg-query', '-W',
           '-f=${binary:Package}\\t${Version}\\t${db:Status-Status}\\n', 'sudo-rs')
fields = row.rstrip('\\n').split('\\t')
assert len(fields) == 3 and fields[0] == 'sudo-rs' and fields[2] == 'installed'
assert row == '\\t'.join(fields) + '\\n'
assert re.fullmatch(r'0\\.2\\.[0-9]{1,3}-[0-9]{1,3}ubuntu[0-9]{1,3}(?:\\.[0-9]{1,3}){0,2}', fields[1])
print(json.dumps({'implementation': 'sudo-rs', 'package_version': fields[1],
                  'executable': str(executable)}, sort_keys=True))
'''

# Follow the stock getty/login's direct shell child and its foreground group,
# never a host-wide process search. util-linux login detaches its own terminal
# before forking a child which creates a new session and acquires the terminal.
# This is a separate boundary from login(1): a visible prompt alone does not
# prove who will consume a password. No command or process identity is supplied
# by the worker. sudo may be the distribution's alternatives-managed binary.
SUDO_PASSWORD_STAGES = (
    'fixture-identity', 'getty-leader', 'getty-session', 'getty-terminal',
    'getty-executable', 'getty-credentials', 'getty-child', 'parent-ancestry',
    'foreground-distinct', 'foreground-session', 'parent-session',
    'parent-terminal', 'parent-foreground', 'sudo-command', 'sudo-binary',
    'sudo-executable', 'parent-executable', 'sudo-credentials',
    'parent-credentials', 'parent-stdin', 'sudo-stdin', 'process-continuity',
    'terminal-open', 'terminal-device', 'terminal-attributes', 'terminal-echo',
    'terminal-echo-enabled-stopped', 'terminal-echo-enabled-running',
    'terminal-echo-enabled-terminal-drain', 'terminal-echo-enabled-terminal-read',
    'terminal-echo-enabled-poll', 'terminal-echo-enabled-futex',
    'terminal-echo-enabled-wait-woken', 'terminal-echo-enabled-other',
    'terminal-echo-enabled-unavailable',
) + tuple('getty-' + phase + '-' + check
          for phase in ('initial', 'recipient', 'continuity')
          for check in ('file-stat', 'file-type', 'file-owner', 'file-writable',
                        'exe-resolve', 'exe-mismatch', 'credentials')) + tuple(
    'terminal-echo-enabled-' + wait + '-syscall-' + call + '-queue-' + queue + '-echo-' + echo
    for wait in ('stopped', 'running', 'terminal-drain', 'terminal-read', 'poll',
                 'futex', 'wait-woken', 'other', 'zero', 'unavailable')
    for call in ('running', 'outside', 'other', 'unavailable', 'unsupported',
                 'read', 'write', 'poll', 'futex', 'ioctl', 'ioctl-drain')
    for queue in ('empty', 'pending', 'unavailable')
    for echo in ('characters', 'newline', 'both'))

_SUDO_PASSWORD_BODY = '''import array,fcntl,os,pathlib,pwd,stat,subprocess,termios
stage = 'fixture-identity'
uid = pwd.getpwnam('onpc-parent-jamie').pw_uid
assert uid > 0
stage = 'getty-leader'
leader = int(subprocess.run(['systemctl','show','serial-getty@ttyS0.service',
                            '--property=MainPID','--value'], capture_output=True,
                           text=True, check=True, timeout=10).stdout.strip())
assert leader > 1
device = os.makedev(4,64)
def process(pid):
    p = pathlib.Path('/proc') / str(pid)
    fields = (p/'stat').read_text().rpartition(') ')[2].split()
    assert len(fields) >= 20
    return p, fields
stage = 'getty-session'
root, root_fields = process(leader)
assert int(root_fields[3]) == leader
stage = 'getty-terminal'
assert [int(v) for v in root_fields[4:6]] == [0,-1]
def ids(p):
    rows = dict(line.split(':',1) for line in (p/'status').read_text().splitlines())
    return [int(v) for v in rows['Uid'].split()]
def login_identity(phase):
    global stage
    prefix = 'getty-' + phase + '-'
    stage = prefix + 'file-stat'
    executable = pathlib.Path('/usr/bin/login')
    info = executable.stat()
    stage = prefix + 'file-type'
    assert stat.S_ISREG(info.st_mode)
    stage = prefix + 'file-owner'
    assert info.st_uid == info.st_gid == 0
    stage = prefix + 'file-writable'
    assert not stat.S_IMODE(info.st_mode) & 0o022
    stage = prefix + 'exe-resolve'
    actual = (root/'exe').resolve(strict=True)
    stage = prefix + 'exe-mismatch'
    assert actual == executable
    stage = prefix + 'credentials'
    assert ids(root) == [0]*4
login_identity('initial')
stage = 'getty-child'
children_path = root/'task'/str(leader)/'children'
children = children_path.read_text().split()
assert len(children) == 1
shell = int(children[0])
assert shell > 1 and shell != leader
parent, parent_fields = process(shell)
stage = 'parent-ancestry'
assert int(parent_fields[1]) == leader
stage = 'parent-session'
assert [int(v) for v in parent_fields[2:4]] == [shell,shell]
stage = 'parent-terminal'
assert int(parent_fields[4]) == device
stage = 'foreground-distinct'
pid = int(parent_fields[5])
assert pid > 1 and pid not in (leader,shell)
stage = 'foreground-session'
proc, fields = process(pid)
assert [int(v) for v in fields[2:6]] == [pid,shell,device,pid]
stage = 'parent-foreground'
assert int(fields[1]) == shell
expected_args = [b'/usr/bin/sudo',b'-k',b'-p',b'\\nONPC-INSTALL-PASSWORD: ',b'--',
                 b'/usr/bin/apt-get',b'install',b'-y',
                 b'/var/lib/onpc-e2e-assets/package.deb',b'']
def snapshot(phase):
    global stage
    login_identity(phase)
    stage = 'sudo-command'
    assert (proc/'cmdline').read_bytes().split(b'\\0') == expected_args
    stage = 'sudo-binary'
    executable = pathlib.Path('/usr/bin/sudo').resolve(strict=True)
    info = executable.stat()
    assert stat.S_ISREG(info.st_mode) and info.st_uid == info.st_gid == 0
    assert not stat.S_IMODE(info.st_mode) & 0o022
    stage = 'sudo-executable'
    assert (proc/'exe').resolve(strict=True) == executable
    stage = 'parent-executable'
    assert (parent/'exe').resolve(strict=True) == pathlib.Path('/usr/bin/bash')
    stage = 'sudo-credentials'
    assert ids(proc) == [uid,0,0,0]
    stage = 'parent-credentials'
    assert ids(parent) == [uid]*4
    def serial_stdin(p):
        info = (p/'fd/0').stat()
        assert stat.S_ISCHR(info.st_mode) and info.st_rdev == device
    stage = 'parent-stdin'
    serial_stdin(parent)
    stage = 'sudo-stdin'
    serial_stdin(proc)
    stage = 'process-continuity'
    assert children_path.read_text().split() == children
    current = [process(value)[1] for value in (leader,pid,shell)]
    for before, after in zip((root_fields,fields,parent_fields), current):
        assert before[1:6] == after[1:6] and before[19] == after[19]
snapshot('recipient')
stage = 'terminal-open'
fd = os.open('/dev/ttyS0', os.O_RDONLY | os.O_NONBLOCK | os.O_NOCTTY | os.O_NOFOLLOW)
try:
    stage = 'terminal-device'
    info = os.fstat(fd)
    assert stat.S_ISCHR(info.st_mode) and info.st_rdev == device
    stage = 'terminal-attributes'
    flags = termios.tcgetattr(fd)[3]
    if flags & termios.ECHO:
        # ECHONL echoes only the separately sent Enter, never the printable
        # password. sudo-rs deliberately retains it during hidden input.
        # Character echo remains forbidden; exact prompt/recipient proof,
        # continuity, capture sealing and terminal refusal are separate gates.
        echo = ('both' if flags & termios.ECHO and flags & termios.ECHONL
                else 'characters' if flags & termios.ECHO else 'newline')
        # Advisory refusal detail only: never expose raw process state, wait
        # symbols, exception text or terminal bytes. Follow only the recipient
        # already proved above and recheck identity before accepting the detail.
        stage = 'terminal-echo-enabled-unavailable'
        state = process(pid)[1][0]
        detail = 'unavailable'
        try:
            wait = (proc/'wchan').read_text().strip()
            detail = {'0': 'zero', 'tty_wait_until_sent': 'terminal-drain',
                      'n_tty_read': 'terminal-read',
                      'n_tty_wait_for_input': 'terminal-read',
                      'do_poll': 'poll', 'do_sys_poll': 'poll',
                      'futex_wait_queue': 'futex', 'futex_wait': 'futex',
                      'wait_woken': 'wait-woken'}.get(wait, 'other')
        except Exception:
            pass
        if state in ('T', 't'):
            detail = 'stopped'
        elif state == 'R':
            detail = 'running'
        # Read only the proved process. Never emit register values, addresses,
        # fd numbers, syscall numbers or output bytes. Unknown ABI stays unknown.
        call = 'unavailable'
        try:
            values = (proc/'syscall').read_text().split()
            if values == ['running']:
                call = 'running'
            elif len(values) == 3 and values[0] == '-1':
                call = 'outside'
            elif len(values) == 9:
                number = int(values[0])
                call = 'unsupported'
                with (proc/'exe').open('rb') as binary:
                    header = binary.read(20)
                # ELF64, little endian, EM_X86_64; no compat syscall decoding.
                if (os.uname().machine == 'x86_64' and len(header) == 20
                        and header[:6] == bytes([127,69,76,70,2,1])
                        and header[18:20] == bytes([62,0])):
                    call = {0: 'read', 1: 'write', 7: 'poll', 16: 'ioctl',
                            202: 'futex', 271: 'poll'}.get(number, 'other')
                    if number == 16 and int(values[2], 16) in (termios.TCSETSW, termios.TCSETSF):
                        target = (proc/'fd'/str(int(values[1], 16))).stat()
                        if stat.S_ISCHR(target.st_mode) and target.st_rdev == device:
                            call = 'ioctl-drain'
        except Exception:
            call = 'unavailable'
        queue = 'unavailable'
        try:
            count = array.array('i', [0])
            fcntl.ioctl(fd, termios.TIOCOUTQ, count, True)
            if count[0] >= 0:
                queue = 'pending' if count[0] else 'empty'
        except Exception:
            pass
        snapshot('continuity')
        stage = ('terminal-echo-enabled-' + detail + '-syscall-' + call
                 + '-queue-' + queue + '-echo-' + echo)
        raise AssertionError
    snapshot('continuity')
finally:
    os.close(fd)
print('install-password-safe')
'''

# Return only a fixed first-failing condition, including read/race failures.
# A refusal exits the guest probe normally solely so the guarded transport can
# collect it; the controller MUST reject it before authorizing any input.
# Never serialize exceptions, argv, identities or authentication terminal data.
SUDO_PASSWORD = ("stage = 'fixture-identity'\ntry:\n"
                 + ''.join('    ' + line + '\n' for line in _SUDO_PASSWORD_BODY.splitlines())
                 + "except Exception:\n    print('install-password-rejected:' + stage)\n")
