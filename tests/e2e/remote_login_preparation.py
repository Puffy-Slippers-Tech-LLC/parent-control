"""Isolated system RDP readiness; no RDP authentication or desktop claim.

The guest program travels over the existing private, guarded transport. Secrets
and original provider files stay in guest memory and never enter runner output.
"""

import json
import grp
import os
from pathlib import Path
import pwd
import re
import secrets
import socket
import stat
import sys
import time


UNIT = 'gnome-remote-desktop.service'
CONFIG_UNIT = 'gnome-remote-desktop-configuration.service'
LIMIT = 120
PORT = 3399
BOOTSTRAP = '''import json,sys
packet = json.load(sys.stdin)
namespace = {'__name__': 'remote_preparation_guest'}
exec(compile(packet.pop('program'), '<remote-preparation>', 'exec'), namespace)
try:
    print(json.dumps(namespace['attempt'](packet), sort_keys=True))
except Exception as error:
    namespace['report_failure'](error)
    sys.exit(1)
'''


def require(condition, code):
    if not condition:
        raise RuntimeError('remote-preparation:' + code)


def report_failure(error):
    """Retain the original safe category if restoration also refuses."""
    seen = set()
    while error is not None and id(error) not in seen and len(seen) < 8:
        seen.add(id(error))
        code = str(error)
        if not re.fullmatch(r'remote-preparation:[a-z-]+', code):
            code = 'remote-preparation:operation-failed'
        print(code, file=sys.stderr)
        frame = error.__traceback__
        while frame:
            if frame.tb_frame.f_code.co_filename == '<remote-preparation>':
                print('remote-preparation:line-' + str(frame.tb_lineno), file=sys.stderr)
            frame = frame.tb_next
        error = error.__cause__ or error.__context__


def identity(info):
    return (info.st_dev, info.st_ino, info.st_mode, info.st_uid, info.st_gid,
            info.st_nlink, info.st_size, info.st_mtime_ns)


def safe_permissions(info, private_owner):
    return not info.st_mode & 0o002 and (not info.st_mode & 0o020 or
        private_owner == (info.st_uid, info.st_gid))


def snapshot(path, *, private_owner=None):
    """Pin a small ordinary file, with no links or writable foreign parents."""
    for parent in path.parents:
        if not parent.exists():
            continue
        info = parent.lstat()
        require(stat.S_ISDIR(info.st_mode)
                and (safe_permissions(info, private_owner) or info.st_mode & stat.S_ISVTX),
                'unsafe-parent')
    try:
        fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    except FileNotFoundError:
        require(not path.is_symlink(), 'unsafe-file')
        return None
    with os.fdopen(fd, 'rb') as stream:
        info = os.fstat(stream.fileno())
        require(stat.S_ISREG(info.st_mode) and info.st_nlink == 1
                and safe_permissions(info, private_owner) and info.st_size <= 65536, 'unsafe-file')
        data = stream.read(65537)
        require(len(data) <= 65536 and identity(info) == identity(path.lstat())
                == identity(os.fstat(stream.fileno())), 'file-changed')
        return (identity(info), data)


def restore_file(path, before, expected, *, private_owner=None):
    """Restore only the exact last owned file, preserving foreign replacements."""
    require(snapshot(path, private_owner=private_owner) == expected, 'restore-collision')
    if before == expected:
        return
    if before is None:
        if expected is not None:
            path.unlink()
        return
    metadata, data = before
    flags = os.O_WRONLY | os.O_NOFOLLOW
    if expected is None:
        flags |= os.O_CREAT | os.O_EXCL
    fd = os.open(path, flags, stat.S_IMODE(metadata[2]))
    with os.fdopen(fd, 'wb') as stream:
        if expected is not None:
            require(identity(os.fstat(stream.fileno())) == expected[0], 'restore-collision')
        stream.write(data)
        stream.truncate()
        stream.flush()
        os.fsync(stream.fileno())
        os.fchown(stream.fileno(), metadata[3], metadata[4])
        os.fchmod(stream.fileno(), stat.S_IMODE(metadata[2]))
    restored = snapshot(path, private_owner=private_owner)
    require(restored[1] == data and restored[0][2:6] == metadata[2:6], 'restore-readback')


def settings(text):
    """Parse the public C-locale status; do not return or print credential values."""
    require('RDP:\n' in text, 'status-format')
    section = text.split('RDP:\n', 1)[1].split('\nVNC:', 1)[0]
    fields = {line.strip().partition(':')[0]: line.strip().partition(':')[2].strip()
              for line in section.splitlines() if ':' in line}
    require(all(key in fields for key in ('Status', 'Port', 'TLS certificate',
            'TLS key', 'Username', 'Password')), 'status-fields')
    require(fields['Status'] in ('enabled', 'disabled')
            and fields['Port'].isdecimal(), 'status-values')
    for key in ('TLS key', 'TLS certificate', 'Username', 'Password'):
        if fields[key] == '(null)':
            fields[key] = ''
    return fields


def attempt(packet):
    sys.path.insert(0, '/var/tmp/onpc-system-input')
    import system_guest as guest
    guest.guard()
    require(packet == {}, 'packet')
    return _prepare_provider(guest)


def _prepare_provider(guest):
    """Shared preparation body; the installed/maintenance caller owns its VM guard."""
    # Never enable command diagnostics here: status and stdin contain secrets.
    require(guest.commands.directory is None, 'private-command-required')
    os.environ['LC_ALL'] = 'C'
    os.umask(0o077)
    account = pwd.getpwnam('gnome-remote-desktop')
    group = grp.getgrgid(account.pw_gid)
    require(group.gr_name == account.pw_name and not set(group.gr_mem) - {account.pw_name}
            and all(user.pw_gid != account.pw_gid or user.pw_uid == account.pw_uid
                    for user in pwd.getpwall()), 'provider-private-group')
    private_owner = (account.pw_uid, account.pw_gid)

    def capture(path):
        return snapshot(path, private_owner=private_owner)

    def restore_owned(path, before, expected):
        return restore_file(path, before, expected, private_owner=private_owner)
    home = Path(account.pw_dir)
    require(home.is_absolute() and home.resolve() == home, 'provider-home')
    run = guest.run

    def systemctl(*args):
        return run(['systemctl', '--no-ask-password', *args], timeout=LIMIT)

    def service_state(unit=UNIT):
        raw = systemctl('show', unit, '--property=ActiveState', '--property=UnitFileState')
        return dict(line.split('=', 1) for line in raw.splitlines())

    def sessions():
        return run(['loginctl', 'list-sessions', '--no-legend', '--no-pager'])

    original_service = service_state()
    require(original_service['ActiveState'] in ('active', 'inactive'), 'service-state')
    require(original_service['UnitFileState'] in ('enabled', 'disabled'), 'service-enablement')
    original_configuration = service_state(CONFIG_UNIT)
    # An active configuration service may belong to an administrator's settings
    # operation. Do not interrupt it or capture files while it can write them.
    require(original_configuration['ActiveState'] == 'inactive',
            'foreign-configuration-service')
    original_sessions = sessions()
    original_network = systemctl('show', UNIT, '--property=IPAddressAllow',
                                 '--property=IPAddressDeny')
    require(systemctl('is-active', 'gdm.service') == 'active', 'gdm-not-ready')
    # Never stop a provider carrying somebody else's remote session.
    for row in original_sessions.splitlines():
        session_id = row.split()[0]
        require(re.fullmatch(r'[A-Za-z0-9_-]+', session_id), 'session-id')
        properties = dict(line.split('=', 1) for line in run([
            'loginctl', 'show-session', session_id, '--property=Remote',
            '--property=Type']).splitlines())
        require(not (properties.get('Remote') == 'yes'
                     and properties.get('Type') in ('wayland', 'x11')), 'foreign-remote-session')

    def listener_inodes():
        found = set()
        for name in ('tcp', 'tcp6'):
            for line in (Path('/proc/net') / name).read_text().splitlines()[1:]:
                columns = line.split()
                if columns[3] == '0A' and int(columns[1].rsplit(':', 1)[1], 16) == PORT:
                    found.add(columns[9])
        return found

    def require_provider_listener():
        pid = systemctl('show', UNIT, '--property=MainPID', '--value')
        require(pid.isdecimal() and int(pid) > 1, 'provider-process')
        fds = Path('/proc') / pid / 'fd'
        sockets = set()
        for fd in fds.iterdir():
            try:
                target = os.readlink(fd)
            except FileNotFoundError:
                continue
            match = re.fullmatch(r'socket:\[([0-9]+)\]', target)
            if match:
                sockets.add(match[1])
        listening = listener_inodes()
        require(bool(listening) and listening <= sockets, 'listener-owner')

    original_listener = listener_inodes()
    if original_listener:
        require(original_service['ActiveState'] == 'active', 'foreign-listener')
        require_provider_listener()

    fedora = Path('/etc/fedora-release').exists()
    packages = ['gnome-remote-desktop', 'freerdp' if fedora else 'freerdp-x11',
                'openssl', 'gdm' if fedora else 'gdm3', 'gnome-shell']
    versions = run(['rpm', '-q', '--queryformat', '%{NAME}=%{VERSION}-%{RELEASE}\n', *packages]
                   if fedora else ['dpkg-query', '-W', '-f=${Package}=${Version}\n', *packages])
    require(len(versions.splitlines()) == len(packages), 'package-readiness')
    client = '/usr/bin/xfreerdp'
    client_version = run([client, '/version'])
    client_help = run([client, '/help'])
    require('FreeRDP version 3.' in client_version
            and all(flag in client_help for flag in ('/v:', '/u:', '/p:', '/cert:',
                                                     'redirect', '/from-stdin')), 'client-readiness')
    require(any(re.fullmatch(r'gnome-remote-desktop=50\..+', row)
                for row in versions.splitlines()), 'provider-version')

    data = home / '.local/share/gnome-remote-desktop'
    created = []
    for directory in (home / '.local', home / '.local/share', data):
        if not directory.exists():
            directory.mkdir(mode=0o700)
            os.chown(directory, account.pw_uid, account.pw_gid)
            created.append((directory, directory.stat()))
        info = directory.lstat()
        require(stat.S_ISDIR(info.st_mode) and info.st_uid == account.pw_uid
                and safe_permissions(info, private_owner), 'provider-directory')
    files = [data / name for name in ('grd.conf', 'credentials.ini', 'rdp-credentials.priv')]
    files.append(Path('/etc/gnome-remote-desktop/grd.conf'))
    before = {path: capture(path) for path in files}
    require(all(value is None or value[0][3:5] in ((0, 0), private_owner)
                for value in before.values()), 'configuration-owner')
    expected = dict(before)
    token = secrets.token_hex(12)
    tls = data / ('onpc-' + token)
    dropdir = Path('/run/systemd/system') / (UNIT + '.d')
    drop = dropdir / ('90-onpc-' + token + '.conf')
    drop_created = not dropdir.exists()
    tls_files = {}
    tls_identity = None
    drop_state = None
    dropdir_identity = None
    original = None
    original_tls = {}
    result = None

    def owned_command(argv, *, input=None, provider_transition=False):
        labels = ('settings', 'credentials', 'sealed-credentials', 'system-settings')
        for path, label in zip(files, labels):
            current = capture(path)
            if current != expected[path]:
                same_bytes = (current is not None and expected[path] is not None
                              and current[1] == expected[path][1])
                phase = argv[3] if argv[:3] == ['grdctl', '--system', 'rdp'] else 'status'
                require(False, 'configuration-changed-' + label +
                        ('-identity' if same_bytes else '-bytes') + '-before-' + phase)
        try:
            return guest.commands.run(argv, input=input, timeout=LIMIT,
                                      merge_stderr=False).decode().strip()
        finally:
            if provider_transition:
                # GRD 50 activates its separate configuration daemon on both
                # server start and stop. Its asynchronous unit notifications
                # persist cached settings, so join that writer before recording
                # our transition's files or restoring the original bytes.
                systemctl('stop', CONFIG_UNIT)
                require(service_state(CONFIG_UNIT) == original_configuration,
                        'configuration-service-restoration')
            for path in files:
                expected[path] = capture(path)

    def grd(*args, input=None):
        return owned_command(['grdctl', '--system', *args], input=input)

    def provider(action):
        return owned_command(['systemctl', '--no-ask-password', action, UNIT],
                             provider_transition=True)

    try:
        original = settings(grd('status'))
        original_tls = {Path(original[key]): capture(Path(original[key]))
                        for key in ('TLS key', 'TLS certificate') if original[key]}
        provider('stop')
        tls.mkdir(mode=0o700)
        os.chown(tls, account.pw_uid, account.pw_gid)
        tls_identity = tls.stat()
        key, cert = tls / 'tls.key', tls / 'tls.crt'
        try:
            owned_command(['runuser', '--user', account.pw_name, '--', 'openssl', 'req',
                '-new', '-newkey', 'rsa:3072', '-nodes', '-x509', '-days', '1',
                '-subj', '/CN=onpc-remote.invalid', '-addext', 'subjectAltName=IP:127.0.0.1',
                '-keyout', str(key), '-out', str(cert)])
        finally:
            for path in (key, cert):
                if path.exists():
                    require(not path.is_symlink(), 'tls-link')
                    os.chmod(path, 0o600)
                    tls_files[path] = capture(path)
                    require(tls_files[path][0][3:5] == (account.pw_uid, account.pw_gid), 'tls-owner')
        if fedora:
            run(['restorecon', '-RF', str(tls)])
        as_provider = ['runuser', '--user', account.pw_name, '--', 'openssl']
        key_public = run([*as_provider, 'pkey', '-in', str(key), '-pubout'])
        cert_public = run([*as_provider, 'x509', '-in', str(cert), '-pubkey', '-noout'])
        require(key_public == cert_public, 'tls-pair')
        run([*as_provider, 'verify', '-CAfile', str(cert), '-verify_ip', '127.0.0.1', str(cert)])
        if drop_created:
            dropdir.mkdir(mode=0o755)
            dropdir_identity = dropdir.stat()
        # Public systemd network policy confines this listener to the guest's
        # loopback. No firewall, host network or persistent service file changes.
        require(systemctl('show', UNIT, '--property=IPAddressAllow', '--value') == '',
                'foreign-network-policy')
        require(capture(drop) is None, 'dropin-collision')
        with drop.open('x') as stream:
            stream.write('[Service]\nIPAddressDeny=any\nIPAddressAllow=localhost\n')
        drop_state = capture(drop)
        systemctl('daemon-reload')
        grd('rdp', 'set-port', str(PORT))
        grd('rdp', 'set-tls-key', str(key))
        grd('rdp', 'set-tls-cert', str(cert))
        # grdctl creates a buffered reader for each prompt. Supply its public
        # username argument and only one private password line on stdin.
        username, password = 'onpc-remote-readiness', secrets.token_urlsafe(32)
        grd('rdp', 'set-credentials', username, input=(password + '\n').encode())
        grd('rdp', 'enable')
        provider('start')
        deadline = time.monotonic() + LIMIT
        while True:
            require(time.monotonic() < deadline, 'listener-timeout')
            try:
                with socket.create_connection(('127.0.0.1', PORT), timeout=1):
                    break
            except OSError:
                time.sleep(0.25)
        ready = settings(grd('status', '--show-credentials'))
        require(ready['Status'] == 'enabled' and ready['Port'] == str(PORT)
                and ready['TLS key'] == str(key) and ready['TLS certificate'] == str(cert)
                and ready['Username'] == username and ready['Password'] == password,
                'provider-readback')
        require_provider_listener()
        # The same listener must reject a non-loopback source, independently
        # verifying the effective policy rather than trusting its saved text.
        addresses = json.loads(run(['ip', '-j', '-4', 'address', 'show', 'scope', 'global']))
        ips = [a['local'] for interface in addresses for a in interface['addr_info']
               if a['family'] == 'inet']
        require(bool(ips), 'isolation-probe-address')
        for address in ips:
            try:
                with socket.create_connection((address, PORT), timeout=2):
                    raise RuntimeError('remote-preparation:listener-not-isolated')
            except OSError:
                pass
        result = dict(packages=versions.splitlines(), client_version=client_version,
            endpoint='127.0.0.1:3399', system_provider_ready=True,
            tls_pair_verified=True, client_ready=True, nonloopback_refused=True,
            listener_owner_verified=True,
            authentication_exercised=False, stage_timeout_seconds=LIMIT)
    finally:
        # Public provider restoration precedes exact restoration of the owned
        # serialized files (including initially absent and opaque TPM inputs).
        provider('stop')
        if original is not None:
            grd('rdp', 'disable')
            grd('rdp', 'set-port', original['Port'])
            # There is no public unset-TLS operation. Initially empty fields
            # and opaque original credentials return with their exact files
            # below, after removing the temporary credential through grdctl.
            if original['TLS key']:
                grd('rdp', 'set-tls-key', original['TLS key'])
            if original['TLS certificate']:
                grd('rdp', 'set-tls-cert', original['TLS certificate'])
            grd('rdp', 'clear-credentials')
            if original['Status'] == 'enabled':
                grd('rdp', 'enable')
            provider('stop')
        for path in files:
            restore_owned(path, before[path], expected[path])
            expected[path] = capture(path)
        if drop_state is not None:
            restore_owned(drop, None, drop_state)
        if drop_created and dropdir.exists():
            current = dropdir.lstat()
            require(dropdir_identity is not None and
                    (current.st_dev, current.st_ino) ==
                    (dropdir_identity.st_dev, dropdir_identity.st_ino), 'dropin-directory-changed')
            dropdir.rmdir()
        systemctl('daemon-reload')
        if original_service['UnitFileState'] == 'disabled':
            systemctl('disable', UNIT)
        else:
            systemctl('enable', UNIT)
        if original_service['ActiveState'] == 'active':
            provider('start')
            for path in files:
                restore_owned(path, before[path], expected[path])
        for path, state in tls_files.items():
            restore_owned(path, None, state)
        if tls_identity is not None:
            require((tls.stat().st_dev, tls.stat().st_ino) ==
                    (tls_identity.st_dev, tls_identity.st_ino), 'tls-directory-changed')
            tls.rmdir()
        for directory, info in reversed(created):
            current = directory.lstat()
            require((current.st_dev, current.st_ino) == (info.st_dev, info.st_ino),
                    'directory-changed')
            directory.rmdir()
        require(service_state() == original_service, 'service-restoration')
        require(service_state(CONFIG_UNIT) == original_configuration,
                'configuration-service-restoration')
        require(systemctl('show', UNIT, '--property=IPAddressAllow',
                          '--property=IPAddressDeny') == original_network, 'network-restoration')
        require(sessions() == original_sessions, 'sessions-changed')
        if not original_listener:
            require(not listener_inodes(), 'listener-restoration')
        for path, value in original_tls.items() if original is not None else ():
            require(capture(path) == value, 'original-tls-changed')
        for path in files:
            after = capture(path)
            require((after is None and before[path] is None) or
                    (after is not None and before[path] is not None and
                     after[1] == before[path][1] and after[0][2:6] == before[path][0][2:6]),
                    'configuration-restoration')
    require(result is not None, 'readiness-missing')
    result['owned_restoration_verified'] = True
    return result


def qualify(transport, lease):
    import watch_activity
    histories = []
    for _ in range(2):
        lease.guard()
        with watch_activity.operation('Checking isolated remote sign-in readiness and restoring its settings'):
            raw = transport.call(['env', 'ONPC_EXPECTED_RUN=' + lease.state['run'],
                '/usr/bin/python3', '-I', '-c', BOOTSTRAP],
                input=json.dumps({'program': Path(__file__).read_text()}).encode(), timeout=600)
        lease.guard()
        require(type(raw) is bytes and 0 < len(raw) <= 16384, 'response-bound')
        result = json.loads(raw)
        require(result.get('system_provider_ready') is True
                and result.get('owned_restoration_verified') is True
                and result.get('authentication_exercised') is False, 'response')
        histories.append(result)
    return {'histories': histories, 'reapplied_after_restoration': True}
