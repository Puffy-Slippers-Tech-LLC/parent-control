"""One unchanged child-to-station su attempt and its ordinary-account control.

The guest half is streamed through the installed envelope. Command output and
journal rows remain in its existing private diagnostics, never in the reply.
"""

import hashlib
from contextlib import contextmanager
import json
import os
from pathlib import Path
import pwd
import re
import select
import stat
import sys
import time
import uuid


ACCOUNT = 'oh-no-parent-control'
SU = '/usr/bin/su'
CALLER = """import json, os, sys
from pathlib import Path
if len(sys.argv) == 3:
    fd = int(sys.argv[2])
    os.dup2(fd, 0)
    os.close(fd)
fields = Path('/proc/self/stat').read_text().rsplit(')', 1)[1].split()
print(json.dumps(dict(pid=os.getpid(), starttime=fields[19],
    uid=os.getresuid(), gid=os.getresgid())), flush=True)
argv = ['/usr/bin/su', '--login', sys.argv[1]]
if len(sys.argv) == 3:
    argv += ['--command', '/usr/bin/id -u']
os.execv(argv[0], argv)
"""
BOOTSTRAP = """import json, sys
packet = json.load(sys.stdin)
namespace = {'__name__': 'su_route_guest'}
exec(compile(packet.pop('program'), '<su-route>', 'exec'), namespace)
try:
    print(json.dumps(namespace['attempt'](packet), sort_keys=True))
except Exception as error:
    code = str(error)
    if not namespace['re'].fullmatch(r'su-route:[a-z-]+', code):
        code = 'su-route:operation-failed'
    print(code, file=sys.stderr)
    sys.exit(1)
"""


def require(value, code):
    if not value:
        raise RuntimeError('su-route:' + code)


def identity(info):
    return (info.st_dev, info.st_ino, info.st_mode, info.st_uid,
            info.st_gid, info.st_nlink, info.st_size, info.st_mtime_ns)


def pin(path):
    """Keep hashes private, including the unchanged shadow and PAM contents."""
    path = path.resolve(strict=True)
    fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    with os.fdopen(fd, 'rb') as stream:
        info = os.fstat(stream.fileno())
        require(stat.S_ISREG(info.st_mode) and info.st_uid == 0
                and info.st_nlink == 1 and not info.st_mode & 0o022
                and info.st_size <= 1024 * 1024, 'configuration-file')
        data = stream.read(1024 * 1024 + 1)
        require(len(data) <= 1024 * 1024 and identity(info) ==
                identity(os.fstat(stream.fileno())) == identity(path.stat()),
                'configuration-race')
        return (str(path), identity(info), hashlib.sha256(data).hexdigest())


def configuration():
    files = [Path('/etc/passwd'), Path('/etc/shadow')]
    files.extend(sorted(Path('/etc/pam.d').iterdir()))
    require(2 < len(files) <= 128, 'configuration-bound')
    return [(str(path), pin(path)) for path in files]


def station_processes(uid):
    result = []
    for path in Path('/proc').iterdir():
        if not path.name.isdecimal():
            continue
        try:
            status = dict(line.split(':', 1) for line in
                          (path / 'status').read_text().splitlines() if ':' in line)
            if str(uid) in status['Uid'].split():
                fields = (path / 'stat').read_text().rsplit(')', 1)[1].split()
                result.append((int(path.name), fields[19]))
        except (FileNotFoundError, ProcessLookupError):
            continue
    return sorted(result)


def station_sessions(guest, uid):
    result = []
    for line in guest.run(['loginctl', 'list-sessions', '--no-legend', '--no-pager']).splitlines():
        fields = line.split()
        require(len(fields) >= 2 and re.fullmatch(r'[A-Za-z0-9_-]+', fields[0]),
                'session-row')
        if fields[1] == str(uid):
            result.append(fields[0])
    return result


@contextmanager
def native_observation(guest):
    """Observe the installed native account callback without changing PAM."""
    root = Path('/sys/kernel/tracing')
    require(root.is_dir() and (root / 'uprobe_events').exists()
            and Path('/usr/bin/readelf').is_file()
            and os.uname().machine == 'x86_64', 'native-observer-unavailable')
    command = (['dpkg-query', '-L', ACCOUNT] if Path('/usr/bin/dpkg-query').exists()
               else ['rpm', '-ql', ACCOUNT])
    modules = [Path(line) for line in guest.run(command).splitlines()
               if line.endswith('/pam_oh_no_parent_control.so')]
    require(len(modules) == 1 and modules[0].is_absolute()
            and modules[0].resolve(strict=True) == modules[0]
            and stat.S_ISREG(modules[0].lstat().st_mode), 'native-module')
    module = modules[0]
    saved = pin(module)
    symbols = guest.run(['/usr/bin/readelf', '--dyn-syms', '--wide', str(module)])
    values = [int(row.split()[1], 16) for row in symbols.splitlines()
              if row.split() and row.split()[-1] == 'pam_sm_acct_mgmt'
              and row.split()[3] == 'FUNC' and row.split()[6] != 'UND']
    require(len(values) == 1, 'native-symbol')
    segments = guest.run(['/usr/bin/readelf', '--program-headers', '--wide', str(module)])
    offsets = [int(row.split()[1], 16) + values[0] - int(row.split()[2], 16)
               for row in segments.splitlines() if row.split() and row.split()[0] == 'LOAD'
               and int(row.split()[2], 16) <= values[0]
               < int(row.split()[2], 16) + int(row.split()[4], 16)]
    require(len(offsets) == 1, 'native-offset')
    group = 'onpc_su_' + uuid.uuid4().hex
    instance = root / 'instances' / group
    registered = {}

    def definitions():
        return [line for line in (root / 'uprobe_events').read_text().splitlines()
                if line.split()[0].split(':', 1)[-1].startswith(group + '/')]

    def control(path, value):
        # tracefs rejects append and truncation can erase foreign events.
        fd = os.open(path, os.O_WRONLY | os.O_NOFOLLOW)
        try:
            data = (value + '\n').encode('ascii')
            require(os.write(fd, data) == len(data), 'native-control-write')
        finally:
            os.close(fd)

    require(not definitions(), 'native-group-collision')
    instance.mkdir()
    owned = (instance.stat().st_dev, instance.stat().st_ino, instance.stat().st_uid)
    try:
        control(instance / 'tracing_on', '0')
        control(instance / 'trace_clock', 'mono')
        control(instance / 'buffer_size_kb', '64')
        for event, prefix, fetch in [('enter', 'p', 'argc=%dx:s32'),
                                     ('leave', 'r', 'result=$retval:s32')]:
            control(root / 'uprobe_events',
                    f'{prefix}:{group}/{event} {module}:0x{offsets[0]:x} {fetch}')
            rows = [row for row in definitions()
                    if row.split()[0] == f'{prefix}:{group}/{event}']
            require(len(rows) == 1, 'native-registration')
            registered[event] = rows[0]
            require(rows[0].split()[1].rsplit(':', 1)[0] == str(module)
                    and int(rows[0].split()[1].rsplit(':', 1)[1], 16) == offsets[0]
                    and rows[0].split()[2:] == [fetch], 'native-definition')
            control(instance / 'events' / group / event / 'enable', '1')
        control(instance / 'tracing_on', '1')
        yield instance
    finally:
        current = instance.stat()
        require((current.st_dev, current.st_ino, current.st_uid) == owned,
                'native-instance-changed')
        control(instance / 'tracing_on', '0')
        remaining = set(registered.values())
        require(set(definitions()) == remaining, 'native-probe-changed')
        for event, definition in reversed(list(registered.items())):
            require(set(definitions()) == remaining, 'native-probe-changed')
            control(instance / 'events' / group / event / 'enable', '0')
            control(root / 'uprobe_events', f'-:{group}/{event}')
            remaining.remove(definition)
        require(not definitions(), 'native-probe-remains')
        instance.rmdir()
        require(not instance.exists() and not (root / 'events' / group).exists()
                and pin(module) == saved, 'native-restoration')


def caller_record(raw, child):
    require(type(raw) is bytes and len(raw) <= 65536, 'caller-response')
    caller = json.loads(raw.splitlines()[0])
    require(set(caller) == {'pid', 'starttime', 'uid', 'gid'}
            and type(caller['pid']) is int and caller['pid'] > 1
            and type(caller['starttime']) is str and caller['starttime'].isdecimal()
            and caller['uid'] == [child.pw_uid] * 3
            and caller['gid'] == [child.pw_gid] * 3, 'caller-credentials')
    return caller


def journal_messages(guest, boot, cursor, caller, finished):
    guest.run(['journalctl', '--sync'], timeout=15)
    raw = guest.run(['journalctl', '--no-pager', '--boot=' + boot,
        '--after-cursor=' + cursor, '_PID=' + str(caller['pid']),
        '--output=json', '--lines=256'], timeout=15)
    require(len(raw) <= 1024 * 1024, 'journal-bound')
    rows = [json.loads(line) for line in raw.splitlines()]
    require(len(rows) < 256 and all(row.get('_BOOT_ID') == boot
            and row.get('_PID') == str(caller['pid']) for row in rows), 'journal-binding')
    messages = [row['MESSAGE'] for row in rows if row.get('_EXE') == SU
                and int(caller['starttime']) * 1000000 // os.sysconf('SC_CLK_TCK')
                    <= int(row['__MONOTONIC_TIMESTAMP']) <= finished
                and type(row.get('MESSAGE')) is str]
    services = {match[1] for message in messages for match in
                re.finditer(r'pam_[a-zA-Z0-9_]+\(([a-zA-Z0-9_-]+):', message)}
    require(len(services) <= 1, 'ambiguous-pam-service')
    return messages, next(iter(services), None)


def ordinary_positive(guest, user_command, child, ordinary, executable, password,
                      boot, cursor, service):
    readfd, writefd = os.pipe()
    pidfd = None
    output = {'stdout': b'', 'stderr': b''}
    attempted = False

    def observe(data, stream):
        nonlocal attempted, pidfd, writefd
        output[stream] += data
        require(len(output[stream]) <= 65536, 'ordinary-output-bound')
        if attempted or b'\n' not in output['stdout'] or b'Password:' not in output['stderr']:
            return
        caller = caller_record(output['stdout'], child)
        pidfd = os.pidfd_open(caller['pid'])
        process = Path('/proc') / str(caller['pid'])
        poll = select.poll()
        poll.register(pidfd, select.POLLIN)
        expected = [SU, '--login', ordinary.pw_name, '--command', '/usr/bin/id -u']
        fields = (process / 'stat').read_text().rsplit(')', 1)[1].split()
        status = dict(line.split(':', 1) for line in
                      (process / 'status').read_text().splitlines() if ':' in line)
        require(not poll.poll(0) and fields[19] == caller['starttime']
                and status['Uid'].split() == [str(child.pw_uid), '0', '0', '0']
                and os.readlink(process / 'exe') == SU
                and (process / 'cmdline').read_bytes().split(b'\0') ==
                    [value.encode() for value in expected] + [b'']
                and pwd.getpwnam(child.pw_name) == child
                and pwd.getpwnam(ordinary.pw_name) == ordinary
                and identity(Path(SU).stat()) == identity(executable)
                and not poll.poll(0), 'ordinary-secret-recipient')
        attempted = True  # An uncertain write is never replayed.
        token = password.encode('ascii') + b'\n'
        require(os.write(writefd, token) == len(token), 'ordinary-private-input')
        os.close(writefd)
        writefd = None

    try:
        raw = user_command(child, ['/usr/bin/python3', '-I', '-c', CALLER,
                           ordinary.pw_name, str(readfd)], check=False, timeout=45,
                           pass_fds=(readfd,), on_output=observe)
        status = guest.commands.last_returncode
        finished = time.monotonic_ns() // 1000
        caller = caller_record(raw, child)
        require(attempted and status == 0
                and raw.splitlines()[1:] == [str(ordinary.pw_uid).encode()],
                'ordinary-positive-failed')
        _, ordinary_service = journal_messages(guest, boot, cursor, caller, finished)
        require(ordinary_service == service, 'ordinary-pam-service')
        return {'attempted': True, 'secret_recipient_verified': True,
                'single_use_input': True, 'exit_status': status,
                'ordinary_uid_observed': True, 'pam_service': ordinary_service}
    finally:
        for fd in (readfd, writefd, pidfd):
            if fd is not None:
                os.close(fd)


def attempt(packet):
    sys.path.insert(0, '/var/tmp/onpc-system-input')
    import system_guest as guest
    from system_kiosk_confinement import user_command
    guest.guard()
    guest.enable_diagnostics()
    require(set(packet) == {'binding', 'password'} and type(packet['password']) is str
            and 0 < len(packet['password']) <= 256
            and all(32 <= ord(char) <= 126 for char in packet['password']), 'private-packet')
    binding = packet['binding']
    require(set(binding) == {'username', 'uid', 'ordinary_username', 'ordinary_uid'}
            and type(binding['username']) is str
            and type(binding['uid']) is int and binding['uid'] > 0, 'child-binding')
    child = pwd.getpwnam(binding['username'])
    require(child.pw_uid == binding['uid'] and child.pw_gid > 0
            and child.pw_shell == '/bin/bash'
            and child.pw_dir == '/home/' + binding['username'], 'child-identity')
    station = pwd.getpwnam(ACCOUNT)
    ordinary = pwd.getpwnam(binding['ordinary_username'])
    require(type(binding['ordinary_uid']) is int
            and ordinary.pw_uid == binding['ordinary_uid']
            and ordinary.pw_uid > 0 and ordinary.pw_uid not in (child.pw_uid, station.pw_uid)
            and ordinary.pw_shell == '/bin/bash'
            and ordinary.pw_dir == '/home/' + ordinary.pw_name, 'ordinary-identity')
    require(station.pw_uid > 0 and station.pw_uid != child.pw_uid
            and station.pw_shell == '/usr/sbin/nologin', 'station-identity')
    executable = Path(SU).stat()
    require(stat.S_ISREG(executable.st_mode) and executable.st_uid == 0
            and executable.st_mode & stat.S_ISUID
            and not executable.st_mode & 0o022, 'su-executable')
    before = configuration()
    require(not station_sessions(guest, station.pw_uid)
            and not station_processes(station.pw_uid), 'station-already-active')
    boot = Path('/proc/sys/kernel/random/boot_id').read_text().strip().replace('-', '')
    latest = json.loads(guest.run(['journalctl', '--no-pager', '--boot=' + boot,
                                 '--lines=1', '--output=json'], timeout=15))
    cursor = latest.get('__CURSOR')
    require(type(cursor) is str and 0 < len(cursor) <= 1024
            and '\n' not in cursor, 'journal-cursor')
    with native_observation(guest) as observation:
        raw = user_command(child, ['/usr/bin/python3', '-I', '-c', CALLER, ACCOUNT],
                           input=b'\n', check=False, timeout=45, merge_stderr=True)
        status = guest.commands.last_returncode
        finished = time.monotonic_ns() // 1000
        caller = caller_record(raw, child)
        trace = (observation / 'trace').read_text()
        require(len(trace) <= 1024 * 1024, 'native-trace-bound')
    # Observation resources are gone before either control or public restoration.
    start = int(caller['starttime']) * 1000000 // os.sysconf('SC_CLK_TCK')
    events = []
    for line in trace.splitlines():
        match = re.search(r'-(\d+)\s+\[\d+\].*?\s(\d+\.\d+):\s+'
                          r'(enter|leave):.*?\b(argc|result)=(-?\d+)\b', line)
        if match and int(match[1]) == caller['pid']:
            seconds, fraction = match[2].split('.')
            stamp = int(seconds) * 1000000 + int(fraction.ljust(6, '0')[:6])
            require(start <= stamp <= finished, 'native-attempt-time')
            events.append((match[3], match[4], int(match[5])))
    native = status != 0 and events == [('enter', 'argc', 1), ('leave', 'result', 6)]
    final_authentication_failure = any(line.endswith(b'su: Authentication failure')
                                     for line in raw.splitlines()[1:])
    messages, service = journal_messages(guest, boot, cursor, caller, finished)
    authentication = status != 0 and final_authentication_failure and any(
        re.search(r'pam_unix\(' + re.escape(service or '')
        + r':auth\): authentication failure;', message)
        and re.search(r'\buid=' + str(child.pw_uid) + r'\b', message)
        and re.search(r'\beuid=0\b', message)
        and re.search(r'\buser=' + re.escape(ACCOUNT) + r'(?:\s|$)', message)
        for message in messages)
    account = any(re.search(r'pam_[a-zA-Z0-9_]+\('
                  + re.escape(service or '') + r':account\)', message)
                  for message in messages)
    native = native and service in ('su', 'su-l')
    require(not station_sessions(guest, station.pw_uid)
            and not station_processes(station.pw_uid), 'station-created-session-or-process')
    positive = {'attempted': False}
    if native:
        positive = ordinary_positive(guest, user_command, child, ordinary,
                                     executable, packet['password'], boot, cursor, service)
    time.sleep(.5)
    sessions = station_sessions(guest, station.pw_uid)
    processes = station_processes(station.pw_uid)
    require(not sessions and not processes, 'station-created-session-or-process')
    require(configuration() == before and pwd.getpwnam(ACCOUNT) == station
            and pwd.getpwnam(binding['username']) == child
            and pwd.getpwnam(ordinary.pw_name) == ordinary
            and identity(Path(SU).stat()) == identity(executable), 'configuration-changed')
    guest.guard()
    return {'route': 'su --login', 'caller_role': 'child', 'caller': caller,
        'executable': SU if messages else None, 'pam_service': service,
        'journal_boot_bound': True, 'journal_cursor_bound': True,
        'exit_status': status, 'authentication_refusal_observed': authentication,
        'su_authentication_failure_observed': final_authentication_failure,
        'pam_account_observed': account or native, 'native_account_refusal_observed': native,
        'native_argc': 1 if native else None, 'native_return': 6 if native else None,
        'native_observation_removed': True,
        'result': 'qualified' if native else 'authentication-preempted'
                  if authentication and not account else 'account-witness-missing',
        'qualified': native, 'ordinary_positive_attempted': positive['attempted'],
        'ordinary_positive': positive,
        'station_sessions_before': 0, 'station_sessions_after': len(sessions),
        'station_processes_before': 0, 'station_processes_after': len(processes),
        'credentials_shell_pam_unchanged': True, 'product_configuration_mutated': False}


def qualify(transport, lease):
    """Private finite route control, followed by caller-owned public restoration."""
    import watch_activity
    from fixture_credentials import ACCOUNTS
    from test_account_password import read_password
    child = ACCOUNTS['child']
    accepted = lease.capture.state['guest']['accounts'][child.username]
    require(accepted['role'] == 'standard', 'child-role')
    ordinary = ACCOUNTS['other-child']
    ordinary_accepted = lease.capture.state['guest']['accounts'][ordinary.username]
    require(ordinary_accepted['role'] == 'standard'
            and ordinary_accepted['uid'] != accepted['uid'], 'ordinary-role')
    binding = {'username': child.username, 'uid': accepted['uid'],
               'ordinary_username': ordinary.username, 'ordinary_uid': ordinary_accepted['uid']}
    password = read_password()
    watch_activity.secret(password)
    packet = {'program': Path(__file__).read_text(), 'binding': binding, 'password': password}
    lease.guard()
    with watch_activity.operation('Invoking one real child-to-station su login'):
        raw = transport.call(['env', 'ONPC_EXPECTED_RUN=' + lease.state['run'],
            '/usr/bin/python3', '-I', '-c', BOOTSTRAP],
            input=json.dumps(packet).encode('ascii'), timeout=180)
    lease.guard()
    require(type(raw) is bytes and 0 < len(raw) <= 65536, 'response-bound')
    result = json.loads(raw)
    require(type(result['qualified']) is bool and result['result'] in
            ('qualified', 'authentication-preempted', 'account-witness-missing')
            and result['qualified'] == (result['result'] == 'qualified')
            and result['native_observation_removed'] is True
            and (not result['qualified'] or
                 result['native_account_refusal_observed'] is True
                 and result['ordinary_positive']['ordinary_uid_observed'] is True),
            'attempt-response')
    return result
