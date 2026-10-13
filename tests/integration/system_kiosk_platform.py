"""Bounded installed distro/plugin/API qualification, separate from journeys."""

import json
import os
from pathlib import Path
import pwd
import re
import stat
import tempfile
import time
from contextlib import ExitStack, contextmanager

import system_guest as guest
from system_kiosk_confinement import manager_pid, process_identity, user_command


LUA_PROBE = '''import ctypes, json, os, sys
os.chdir(sys.argv[2])
lua = ctypes.CDLL(sys.argv[1])
lua.luaL_newstate.restype = ctypes.c_void_p
lua.luaL_openlibs.argtypes = [ctypes.c_void_p]
lua.luaL_loadstring.argtypes = [ctypes.c_void_p, ctypes.c_char_p]
lua.luaL_loadstring.restype = ctypes.c_int
lua.lua_pcallk.argtypes = [ctypes.c_void_p, ctypes.c_int, ctypes.c_int, ctypes.c_int,
                         ctypes.c_ssize_t, ctypes.c_void_p]
lua.lua_pcallk.restype = ctypes.c_int
lua.lua_tolstring.argtypes = [ctypes.c_void_p, ctypes.c_int, ctypes.c_void_p]
lua.lua_tolstring.restype = ctypes.c_char_p
lua.lua_close.argtypes = [ctypes.c_void_p]
state = lua.luaL_newstate()
assert state
try:
    lua.luaL_openlibs(state)
    assert lua.luaL_loadstring(state, b'return require("onpc_platform_canary")') == 0
    result = lua.lua_pcallk(state, 0, 1, 0, 0, None)
    value = lua.lua_tolstring(state, -1, None) or b''
    print(json.dumps({'loaded': result == 0 and value == b'onpc-platform-canary',
                      'missing': result != 0 and b'not found' in value}))
finally:
    lua.lua_close(state)
'''


@contextmanager
def runtime_fixture(account):
    """Small deliberate user-runtime inputs; reports stay in runner storage.

    Hold the root-owned directory descriptor across all writes. Its user-owned
    parent cannot redirect privileged writes through a renamed entry. The
    caller stops its owned manager before this context cleans these inputs.
    """
    parent = Path('/run/user') / str(account.pw_uid)
    directory = Path(tempfile.mkdtemp(prefix='onpc-platform-', dir=parent))
    fd = os.open(directory, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
    info = os.fstat(fd)
    identity = info.st_dev, info.st_ino
    files = {}
    try:
        guest.require(info.st_uid == 0 and stat.S_IMODE(info.st_mode) == 0o700,
                      'platform:fixture-root-ownership')
        os.fchmod(fd, 0o755)

        def write(name, data, *, owner=None):
            guest.require(Path(name).name == name and name not in files, 'platform:fixture-name')
            child = os.open(name, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW,
                            0o600, dir_fd=fd)
            try:
                current = os.fstat(child)
                files[name] = current.st_dev, current.st_ino
                with os.fdopen(child, 'wb', closefd=False) as stream:
                    stream.write(data)
                os.fchmod(child, 0o644)
                if owner is not None:
                    os.fchown(child, owner.pw_uid, owner.pw_gid)
            finally:
                os.close(child)
            return directory / name

        yield directory, write
    finally:
        try:
            current = directory.lstat()
            guest.require((current.st_dev, current.st_ino) == identity,
                          'platform:fixture-directory-replaced')
            guest.require(set(os.listdir(fd)) == set(files), 'platform:foreign-fixture-entry')
            for name, expected in files.items():
                current = os.stat(name, dir_fd=fd, follow_symlinks=False)
                guest.require((current.st_dev, current.st_ino) == expected,
                              'platform:fixture-file-replaced')
            for name in files:
                os.unlink(name, dir_fd=fd)
            directory.rmdir()
        finally:
            os.close(fd)


def environment(process):
    entries = (process / 'environ').read_bytes().split(b'\0')
    return dict(entry.decode().split('=', 1) for entry in entries if entry)


def native_mappings(process):
    paths = set()
    for line in (process / 'maps').read_text().splitlines():
        fields = line.split(None, 5)
        if len(fields) == 6 and 'x' in fields[1] and fields[5].startswith('/'):
            guest.require(not fields[5].endswith(' (deleted)'), 'platform:deleted-native-map')
            paths.add(Path(fields[5]))
    return sorted(paths)


def trusted_native(path, process=None):
    """Review actual mapped bytes and every resolved storage ancestor."""
    canonical = path.resolve(strict=True)
    guest.require(canonical.is_relative_to('/usr'), 'platform:foreign-native-map')
    for item in (canonical, *canonical.parents):
        info = item.lstat()
        guest.require(info.st_uid == 0 and not info.st_mode & 0o022,
                      'platform:untrusted-native-storage')
    guest.require(stat.S_ISREG(canonical.stat().st_mode), 'platform:native-file-type')
    with canonical.open('rb') as stream:
        guest.require(stream.read(4) == b'\x7fELF', 'platform:native-file-format')
    digest = guest.sha(canonical)
    if process is not None:
        # Do not resolve the procfs magic root: resolving it would silently
        # reopen the host /usr instead of the running process's mount view.
        visible = process / 'root' / path.relative_to('/')
        guest.require(guest.sha(visible) == digest, 'platform:namespace-native-drift')
        for line in (process / 'maps').read_text().splitlines():
            fields = line.split(None, 5)
            if len(fields) == 6 and fields[5] == str(path) and 'x' in fields[1]:
                guest.require(guest.sha(process / 'map_files' / fields[0]) == digest,
                              'platform:mapped-native-drift')
    return {'path': str(canonical), 'sha256': digest}


def audio_snapshot(account, backend):
    pid = user_command(account, ['systemctl', '--user', 'show', 'wireplumber.service',
                                '--value', '--property=MainPID']).decode().strip()
    guest.require(re.fullmatch(r'[1-9][0-9]*', pid), 'platform:audio-pid')
    process = Path('/proc') / pid
    expected = ('onpc-kiosk-audio (enforce)' if backend == 'apparmor'
                else 'system_u:system_r:onpc_kiosk_audio_t:s0')
    guest.require((process / 'attr/current').read_text().strip().rstrip('\0') == expected,
                  'platform:audio-label')
    values = environment(process)
    for name, value in {
        'WIREPLUMBER_CONFIG_DIR': '/etc/wireplumber:/usr/share/wireplumber',
        'WIREPLUMBER_DATA_DIR': '/usr/share/wireplumber', 'LUA_PATH': '', 'LUA_CPATH': '',
    }.items():
        guest.require(values.get(name) == value, 'platform:audio-environment:' + name)
    for name in ('WIREPLUMBER_MODULE_DIR', 'PIPEWIRE_MODULE_DIR', 'PIPEWIRE_CONFIG_DIR', 'SPA_PLUGIN_DIR',
                 'LUA_PATH_5_4', 'LUA_CPATH_5_4', 'LUA_PATH_5_5', 'LUA_CPATH_5_5',
                 'LD_PRELOAD', 'LD_LIBRARY_PATH', 'XDG_CONFIG_HOME', 'XDG_DATA_HOME'):
        guest.require(name not in values, 'platform:audio-injection:' + name)
    mappings = native_mappings(process)
    libraries = [path for path in mappings if path.name.startswith(('liblua5.', 'liblua-5.'))]
    guest.require(len(libraries) == 1, 'platform:actual-lua-library')
    return process, process_identity(process), values, libraries[0], mappings


def package_inventory(backend, record, mappings):
    root = Path('/usr/lib/x86_64-linux-gnu' if backend == 'apparmor' else '/usr/lib64')
    files = sorted({str(path.resolve(strict=True)) for path in mappings} | {
        str(root / 'pipewire-0.3' / name) for name in (
            'libpipewire-module-metadata.so', 'libpipewire-module-filter-chain.so')})
    if backend == 'apparmor':
        ownership = guest.run(['dpkg-query', '-S', *files])
        packages = sorted({line.rsplit(': ', 1)[0] for line in ownership.splitlines()})
        rows = guest.run(['dpkg-query', '-W', '-f=${binary:Package}\t${Version}\t'
                          '${source:Package}\t${source:Version}\n', *packages])
        verification = guest.run(['dpkg', '--verify', *packages])
    else:
        packages = sorted(set(guest.run(['rpm', '-qf', '--qf', '%{NAME}\n', *files]).splitlines()))
        rows = guest.run(['rpm', '-q', '--qf', '%{NAME}\t%{VERSION}-%{RELEASE}\t%{SOURCERPM}\n',
                          *packages])
        verification = guest.run(['rpm', '-V', *packages])
    guest.require(not verification, 'platform:modified-distro-package')
    record('onpc.platform.packages', rows)
    scripts = sorted(Path('/usr/share/wireplumber/scripts').rglob('*.lua'))
    guest.require(scripts, 'platform:shipped-scripts-missing')
    record('onpc.platform.script-inputs', json.dumps([
        {'path': str(path), 'sha256': guest.sha(path)} for path in scripts], sort_keys=True))


def verify_lua(account, library, directory, values, record, write):
    write('onpc_platform_canary.lua', b'return "onpc-platform-canary"\n')
    for restricted in (False, True):
        selected = dict(values)
        if not restricted:
            selected.pop('LUA_PATH')
            selected.pop('LUA_CPATH')
        result = user_command(account, ['/usr/bin/env', '-i',
            *(name + '=' + value for name, value in selected.items()),
            '/usr/bin/python3', '-I', '-c', LUA_PROBE, str(library), str(directory)])
        guest.require(json.loads(result) == {'loaded': not restricted, 'missing': restricted},
                      'platform:actual-lua-default-search')
    record('onpc.platform.actual-lua-cwd-denied', True)


def hostile_audio_startup(account, directory, record, write):
    # Exercise the manager's real environment API and vendor service. The
    # fixture belongs to this manager attempt; refuse preexisting variables.
    names = ('WIREPLUMBER_CONFIG_DIR', 'WIREPLUMBER_DATA_DIR', 'WIREPLUMBER_MODULE_DIR',
             'PIPEWIRE_CONFIG_DIR', 'PIPEWIRE_MODULE_DIR', 'SPA_PLUGIN_DIR',
             'XDG_CONFIG_HOME', 'XDG_DATA_HOME', 'LUA_PATH_5_4', 'LUA_CPATH_5_4',
             'LUA_PATH_5_5', 'LUA_CPATH_5_5')
    original = user_command(account, ['systemctl', '--user', 'show-environment']).decode()
    present = {line.split('=', 1)[0] for line in original.splitlines()}
    guest.require(not present.intersection(names), 'platform:preexisting-startup-variables')
    write('wireplumber.conf', b'onpc-invalid-untrusted-configuration\n')
    write('client.conf', b'onpc-invalid-untrusted-configuration\n')
    invocation = user_command(account, ['systemctl', '--user', 'show', 'wireplumber.service',
                                       '--value', '--property=InvocationID'])
    try:
        user_command(account, ['systemctl', '--user', 'set-environment',
                               *(name + '=' + str(directory) for name in names)])
        guest.require(user_command(account, ['systemctl', '--user', 'show', 'wireplumber.service',
                      '--value', '--property=InvocationID']) == invocation,
                      'platform:audio-instance-before-restart')
        user_command(account, ['systemctl', '--user', 'restart', 'wireplumber.service'])
        record('onpc.platform.hostile-startup-exercised', True)
    finally:
        user_command(account, ['systemctl', '--user', 'unset-environment', *names])
        restored = user_command(account, ['systemctl', '--user', 'show-environment']).decode()
        guest.require(not {line.split('=', 1)[0] for line in restored.splitlines()}.intersection(names),
                      'platform:startup-environment-cleanup')


def audit_denial(text, backend, pid, path):
    """Require the actual live audio PID, exact owned inode path and enforcing denial."""
    for line in text.splitlines():
        if not re.search(r'\bpid=' + re.escape(str(pid)) + r'\b', line):
            continue
        if backend == 'apparmor':
            if all(token in line for token in (
                    'apparmor="DENIED"', 'operation="file_mmap"',
                    'profile="onpc-kiosk-audio"', 'name="' + str(path) + '"',
                    'denied_mask="m"')):
                return True
        elif all(token in line for token in (
                'avc:  denied', '{ execute }', 'path="' + str(path) + '"')):
            fields = dict(re.findall(r'\b(scontext|tclass|permissive)=([^\s]+)', line))
            if fields == {'scontext': 'system_u:system_r:onpc_kiosk_audio_t:s0',
                          'tclass': 'file', 'permissive': '0'}:
                return True
    return False


def audio_journal(pid, cursor):
    return guest.run(['journalctl', '-b', '_PID=' + str(pid), '-n', '150',
                      '--after-cursor=' + cursor, '--no-pager', '-o', 'cat'])


def kernel_audit(backend):
    if backend == 'apparmor':
        return guest.run(['journalctl', '-b', '-k', '-n', '500', '--no-pager', '-o', 'cat'])
    # Fedora auditd owns AVC storage; the journal alone omits these records.
    with Path('/var/log/audit/audit.log').open('rb') as stream:
        stream.seek(0, os.SEEK_END)
        stream.seek(max(0, stream.tell() - 4 * 1024 * 1024))
        return stream.read().decode(errors='replace')


def wait_for(predicate, category):
    deadline = time.monotonic() + 10
    while True:
        if predicate():
            return
        guest.require(time.monotonic() < deadline, category)
        time.sleep(0.1)


def settle_kernel_audit(backend):
    if backend == 'apparmor':
        # Without auditd, kauditd_printk_skb shares printk's rate limiter.
        # Startup/connection denials can consume its burst. Space the single
        # probe; never change audit settings or retry a missing denial.
        interval = int(Path('/proc/sys/kernel/printk_ratelimit').read_text())
        guest.require(0 <= interval <= 30, 'platform:audit-interval-out-of-bounds')
        if interval:
            time.sleep(interval + 1)


def verify_native_api(account, backend, process, identity, directory, record, write):
    root = Path('/usr/lib/x86_64-linux-gnu' if backend == 'apparmor' else '/usr/lib64')
    source = root / 'pipewire-0.3/libpipewire-module-metadata.so'
    trusted_native(source)
    target = write('onpc-platform-ladspa.so', source.read_bytes(), owner=account)
    guest.require(guest.sha(source) == guest.sha(target), 'platform:copied-native-bytes')
    # A genuine distro ELF, including its dependencies, must load before denial
    # counts. No compiler, added guest dependency or production exec route.
    user_command(account, ['/usr/bin/python3', '-I', '-c',
                          'import ctypes,sys;ctypes.CDLL(sys.argv[1])', str(target)])
    metadata = user_command(account, ['pw-metadata', '-n', 'sm-objects']).decode()
    key = 'onpc-platform-' + directory.name
    guest.require('Found "sm-objects" metadata ' in metadata and key not in metadata,
                  'platform:metadata-precondition')
    cursor = guest.run(['journalctl', '-b', '-n', '0', '--show-cursor', '--no-pager', '-o', 'cat'])
    guest.require(cursor.startswith('-- cursor: ') and '\n' not in cursor, 'platform:journal-cursor')
    cursor = cursor.removeprefix('-- cursor: ')
    try:
        for plugin in (source, target):
            if plugin == target:
                settle_kernel_audit(backend)
            value = {'type': 'pw-module', 'name': 'libpipewire-module-filter-chain', 'args': {
                'library.filter-path': 'false', 'filter.graph': {'nodes': [{
                    'type': 'ladspa', 'name': 'onpc', 'plugin': str(plugin), 'label': 'onpc'}]}}}
            user_command(account, ['pw-metadata', '-n', 'sm-objects', '0', key,
                                   json.dumps(value), 'Spa:String:JSON'])
            observed = user_command(account, ['pw-metadata', '-n', 'sm-objects']).decode()
            guest.require(key in observed and str(plugin) in observed,
                          'platform:metadata-request-not-observed')
            if plugin == source:
                # dlsym's missing LADSPA symbol proves the trusted ELF was
                # actually loaded through this same native API before attack.
                wait_for(lambda: any(str(source) in line and
                         'undefined symbol: ladspa_descriptor' in line
                         for line in audio_journal(process.name, cursor).splitlines()),
                         'platform:trusted-native-api-not-observed')
                record('onpc.platform.trusted-native-api-positive', True)
            else:
                def observed_denial():
                    for line in kernel_audit(backend).splitlines():
                        if audit_denial(line, backend, process.name, target):
                            record('onpc.platform.native-api-audit', line)
                            return True
                    return False

                wait_for(observed_denial, 'platform:native-api-map-denial-not-observed')
                guest.require(target not in native_mappings(process), 'platform:user-native-mapped')
                record('onpc.platform.native-api-map-denied', True)
            guest.require(process_identity(process) == identity, 'platform:audio-instance-changed')
    finally:
        user_command(account, ['pw-metadata', '-n', 'sm-objects', '-d', '0', key])
        guest.require(key not in user_command(account, ['pw-metadata', '-n', 'sm-objects']).decode(),
                      'platform:metadata-cleanup')


def verify_service_api(account, backend, record):
    profile = ('AppArmorProfile=unconfined' if backend == 'apparmor'
               else 'SELinuxContext=unconfined_u:unconfined_r:unconfined_t:s0')
    expected = 231 if backend == 'apparmor' else 229
    for index, (setting, command, status) in enumerate((
        (profile, ['/usr/bin/systemctl', '--version'], expected),
        (profile.replace('=', '=-', 1), ['/bin/sh', '-c', 'exit 0'], 203),
    )):
        user_command(account, ['systemd-run', '--user', '--wait', '--collect', '--pipe',
            '--unit=onpc-platform-profile-' + str(index), '--property=' + setting,
            *command], check=False)
        actual = guest.commands.last_returncode
        # Even when the service asks to ignore a profile-setting error, the
        # forbidden executable remains subject to the existing kernel boundary.
        guest.require(actual == status, 'platform:service-profile-escape')
        record('onpc.platform.service-profile-denied.' + str(index), actual)


def verify(record):
    guest.guard()
    guest.enable_diagnostics()
    backend = json.loads(Path('/usr/share/oh-no-parent-control/confinement/config.json').read_text())['backend']
    account = pwd.getpwnam('oh-no-parent-control')
    unit = f'user@{account.pw_uid}.service'
    guest.require(guest.run(['systemctl', 'show', unit, '--value', '--property=ActiveState'])
                  in ('inactive', 'failed'), 'platform:manager-already-active')
    # The manager creates /run/user/UID. Unwind services before their runtime
    # inputs, including when fixture acquisition or a qualification check fails.
    with ExitStack() as inputs, ExitStack() as services:
        guest.run(['systemctl', 'start', unit], timeout=75)
        invocation = guest.run(['systemctl', 'show', unit, '--value', '--property=InvocationID'])

        def stop_manager():
            guest.require(guest.run(['systemctl', 'show', unit, '--value', '--property=InvocationID'])
                          == invocation, 'platform:manager-instance-changed')
            guest.run(['systemctl', 'stop', unit], timeout=75)

        services.callback(stop_manager)
        directory, write = inputs.enter_context(runtime_fixture(account))
        manager = Path('/proc') / str(manager_pid(unit))
        manager_identity = process_identity(manager)
        manager_label = (manager / 'attr/current').read_text()
        expected = ('onpc-kiosk-manager (enforce)' if backend == 'apparmor'
                    else 'system_u:system_r:onpc_kiosk_manager_t:s0')
        guest.require(manager_label.strip().rstrip('\0') == expected, 'platform:manager-label')
        positive = user_command(account, ['systemd-run', '--user', '--wait', '--collect', '--pipe',
            '--unit=onpc-platform-positive', '/usr/bin/systemctl', '--version'])
        guest.require(b'systemd ' in positive, 'platform:service-api-positive')
        user_command(account, ['systemctl', '--user', 'start', 'wireplumber.service'])
        hostile_audio_startup(account, directory, record, write)
        process, identity, values, library, mappings = audio_snapshot(account, backend)
        package_inventory(backend, record, mappings)
        record('onpc.platform.native-inputs', json.dumps([trusted_native(path, process) for path in mappings],
                                                       sort_keys=True))
        record('onpc.platform.actual-lua-library', str(library))
        verify_lua(account, library, directory, values, record, write)
        verify_native_api(account, backend, process, identity, directory, record, write)
        verify_service_api(account, backend, record)
        guest.require(process_identity(manager) == manager_identity and
                      (manager / 'attr/current').read_text() == manager_label,
                      'platform:manager-boundary-changed')
        guest.require(audio_snapshot(account, backend)[1] == identity, 'platform:audio-restarted')
        record('onpc.platform.boundaries-preserved', True)
    record('onpc.platform.owned-manager-stopped', True)
