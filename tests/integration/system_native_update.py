"""Finite installed native A -> B history inside the runner's public station.

The runner owns GDM entry/cancel, transport, reboot and the attempt allocation.
This module never installs prerequisites or stops the station's user manager.
"""

from contextlib import contextmanager
import ctypes
import hashlib
import json
import os
from pathlib import Path
import pwd
import re
import select
import signal
import shutil
import stat
import sys
import time
import traceback

import native_transaction as native
import system_guest as guest
import system_kiosk_confinement as confinement


CONFIG = Path('/usr/share/oh-no-parent-control/confinement/config.json')
RUNTIME = Path('/run/oh-no-parent-control-confinement')
GENERATION = 'usr/share/oh-no-parent-control/confinement/generation'
BOOT = Path('/proc/sys/kernel/random/boot_id')


def private():
    path = guest.PAYLOAD / 'private'
    path.mkdir(mode=0o700, exist_ok=True)
    info = path.lstat()
    guest.require(stat.S_ISDIR(info.st_mode) and info.st_uid == info.st_gid == 0 and
                  stat.S_IMODE(info.st_mode) == 0o700, 'native-update:private-directory')
    return path


def read_private(path):
    descriptor = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    with os.fdopen(descriptor) as stream:
        info = os.fstat(stream.fileno())
        guest.require(stat.S_ISREG(info.st_mode) and info.st_nlink == 1 and
                      info.st_uid == info.st_gid == 0 and stat.S_IMODE(info.st_mode) == 0o600
                      and info.st_size <= 8 * 1024 * 1024, 'native-update:checkpoint-metadata')
        return json.load(stream)


def publish(name, value):
    """Append-only phase checkpoints preserve interrupted and failed evidence."""
    directory = private()
    descriptor = os.open(directory / name,
                         os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
    with os.fdopen(descriptor, 'w') as stream:
        json.dump(value, stream, sort_keys=True)
        stream.flush()
        os.fsync(stream.fileno())
    descriptor = os.open(directory, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
    try:
        os.fsync(descriptor)
    finally:
        os.close(descriptor)


def inputs():
    marker = guest.guard()
    selected = guest.PAYLOAD / 'selected-inputs.json'
    guest.require(guest.sha(selected) == marker['selected_inputs_sha256'],
                  'native-update:selected-inputs')
    directory = guest.PAYLOAD / 'native-transaction'
    manifest = json.loads((directory / 'native-inputs.json').read_text())
    selection, packages, paths = native.validate_manifest(manifest, directory)
    package_format = guest.package_path().suffix.removeprefix('.')
    binding = json.loads((guest.PAYLOAD / 'native-transaction-binding.json').read_text())
    expected = {'schema_version': 1, 'pair_id': manifest['pair_id'],
                'package_format': package_format,
                'native_manifest_sha256': guest.sha(directory / 'native-inputs.json'),
                'baseline_provenance_sha256': marker['baseline_sha256'],
                'selected_inputs_sha256': marker['selected_inputs_sha256']}
    guest.require(binding == expected and manifest['package_format'] == package_format,
                  'native-update:staged-binding')
    # The staging owner cryptographically verifies the finite bundle before
    # transfer. guard() verifies every transferred byte, including trust receipts.
    attempt = {key: marker[key] for key in ('run', 'machine_id', 'domain_uuid',
               'package_sha256', 'preparation_sha256', 'baseline_sha256',
               'selected_inputs_sha256')}
    attempt.update(native_binding_sha256=manifest['binding_sha256'],
                   native_manifest_sha256=expected['native_manifest_sha256'])
    return attempt, manifest, directory


def checkpoint(phase, binding):
    result = read_private(private() / ('native-update-' + phase + '.json'))
    guest.require(result.get('schema') == 1 and result.get('phase') == phase and
                  result.get('binding') == binding, 'native-update:checkpoint-attempt')
    return result


def save(phase, binding, **values):
    publish('native-update-' + phase + '.json',
            dict(schema=1, phase=phase, binding=binding, **values))


class GuestRunner:
    """Use existing bounded command ownership and private diagnostics."""
    @property
    def status_directory(self):
        return private()

    def run(self, arguments, *, timeout=120, pass_fds=()):
        from types import SimpleNamespace
        output = guest.commands.run(['/usr/bin/env', 'LC_ALL=C', 'LANG=C', *arguments],
                                    timeout=timeout, pass_fds=pass_fds,
                                    check=False, merge_stderr=True)
        return SimpleNamespace(returncode=guest.commands.last_returncode,
                               stdout=output.decode(errors='replace'), stderr='')


def preflight(binding, manifest, directory):
    return native.preflight('ubuntu' if manifest['package_format'] == 'deb' else 'fedora',
        manifest, directory, baseline_provenance=binding['baseline_sha256'],
        selected_input_sha256=binding['selected_inputs_sha256'], runner=GuestRunner())


def native_identity(manifest, phase):
    selection = manifest['selection']
    expected = manifest['packages'][phase]
    if manifest['package_format'] == 'deb':
        value = guest.run(['dpkg-query', '-W', '-f=${Package}\t${Version}\t${Architecture}',
                           selection['package']])
    else:
        value = guest.run(['rpm', '-q', '--queryformat',
                           '%{NAME}\t%{EPOCHNUM}:%{VERSION}-%{RELEASE}\t%{ARCH}',
                           selection['package']])
    guest.require(value.split('\t') == [expected['name'], expected['version'],
                                       expected['architecture']], 'native-update:native-version')
    executable = Path(selection['executable'])
    info = executable.lstat()
    guest.require(stat.S_ISREG(info.st_mode) and info.st_uid == info.st_gid == 0 and
                  stat.S_IMODE(info.st_mode) == 0o755 and
                  guest.sha(executable) == expected['executable']['sha256'],
                  'native-update:native-payload')
    return {'version': expected['version'], 'sha256': guest.sha(executable),
            'device': info.st_dev, 'inode': info.st_ino}


def unrelated_packages(receipt, package):
    installed = receipt['native_state']['installed']
    if isinstance(installed, dict):
        return {key: value for key, value in installed.items() if value['Package'] != package}
    return [value for value in installed if value['name'] != package]


def cache_result(manifest, triggers, *, started_ns=None):
    directory = Path(triggers['completion_path'])
    guest.require(directory.is_dir() and not directory.is_symlink(), 'native-update:man-cache')
    if not triggers['completion_required']:
        guest.require(manifest['package_format'] == 'deb' and
                      not Path('/var/lib/man-db/auto-update').exists(),
                      'native-update:disabled-cache-branch')
        return {'branch': 'verified-disabled'}
    name = 'bwrap' if manifest['package_format'] == 'deb' else 'xdg-dbus-proxy'
    arguments = ['whatis', '--exact', name]
    if started_ns is not None:
        arguments.extend(['-M', '/usr/share/man'])
    output = guest.run(arguments)
    guest.require(any(re.match(r'^' + re.escape(name) + r'\s+\(1\)', line)
                      for line in output.splitlines()), 'native-update:man-cache-result')
    databases = sorted(directory.rglob('index.db'))
    guest.require(databases, 'native-update:man-cache-database-missing')
    if started_ns is not None:
        # The Fedora unit masks mandb errors. An old whatis hit and unit success
        # alone could both survive a failed update; require a fresh database too.
        database = directory / 'index.db'
        guest.require(database.is_file() and not database.is_symlink(),
                      'native-update:man-cache-database-missing')
        guest.require(started_ns <= database.stat().st_mtime_ns <= time.time_ns(),
                      'native-update:man-cache-not-refreshed')
        databases = [database]
    return {'branch': 'completed', 'databases': [
        {'sha256': guest.sha(path), 'mtime_ns': path.stat().st_mtime_ns} for path in databases]}


def native_diagnostic(directory, name, value):
    descriptor = os.open(directory / name,
                         os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
    with os.fdopen(descriptor, 'w') as stream:
        stream.write(value)


def rpm_execution(output, triggers):
    """RPM 6.0.2 logs Lua entry, and shell entry/exit, through normal -vv."""
    observed = []
    for trigger in triggers['applicable']:
        owner = trigger['owner'].replace('-0:', '-', 1)
        for action in trigger['actions']:
            label = '%' + action['action'] + '(' + owner + ')'
            prefix = re.escape(label) + r': '
            if action['interpreter'] == '<lua>':
                starts = re.findall(prefix + r'running <lua> scriptlet\.', output)
                guest.require(len(starts) == 1, 'native-update:lua-trigger-not-observed')
            else:
                guest.require(action['interpreter'] == '/bin/sh' and
                              len(re.findall(prefix + r'scriptlet start', output)) == 1,
                              'native-update:shell-trigger-not-observed')
                starts = re.findall(prefix + r'execv\(/bin/sh\) pid (\d+)', output)
                exits = re.findall(prefix + r'waitpid\((\d+)\) rc (\d+) status ([0-9a-fA-F]+)', output)
                guest.require(len(starts) == len(exits) == 1 and int(starts[0]) > 0 and
                              exits[0][0] == exits[0][1] == starts[0] and
                              int(exits[0][2], 16) == 0,
                              'native-update:trigger-script-failed')
            observed.append({'owner': trigger['owner'], **action})
    # Matching unreviewed script executions must never disappear in debug noise.
    actual = re.findall(r'(%(?:transfiletrigger|filetrigger|trigger)(?:in|un|postun)\([^\n]+?\)):'
                        r' (?:running <lua> scriptlet\.|scriptlet start)', output)
    expected = ['%' + item['action'] + '(' + item['owner'].replace('-0:', '-', 1) + ')'
                for item in observed]
    guest.require(sorted(actual) == sorted(expected), 'native-update:unaccounted-trigger-execution')
    return observed


def loader_cache():
    path = Path('/etc/ld.so.cache')
    before = path.lstat()
    data = native.read_file(path)
    info = path.lstat()
    guest.require(info.st_uid == info.st_gid == 0 and stat.S_IMODE(info.st_mode) == 0o644,
                  'native-update:loader-cache-metadata')
    listing = guest.run(['/usr/bin/ldconfig', '-p'])
    guest.require('libc.so.6 ' in listing and 'libgio-2.0.so.0 ' in listing,
                  'native-update:loader-cache-result')
    fields = ('st_dev', 'st_ino', 'st_size', 'st_mtime_ns', 'st_ctime_ns')
    after = path.lstat()
    guest.require(tuple(getattr(before, key) for key in fields) ==
                  tuple(getattr(info, key) for key in fields) ==
                  tuple(getattr(after, key) for key in fields), 'native-update:loader-cache-changed')
    return {'sha256': hashlib.sha256(data).hexdigest(), 'device': info.st_dev,
            'inode': info.st_ino, 'mtime_ns': info.st_mtime_ns, 'ctime_ns': info.st_ctime_ns,
            'listing': listing}


def rpm_completion(triggers, before_cache, started_ns):
    environment = native.rpm_trigger_environment(Path('/'), GuestRunner())
    guest.require(environment == triggers['environment'], 'native-update:trigger-environment-drift')
    cache = loader_cache()
    ended_ns = time.time_ns()
    guest.require(started_ns <= cache['mtime_ns'] <= ended_ns and
                  started_ns <= cache['ctime_ns'] <= ended_ns and
                  cache['mtime_ns'] > before_cache['mtime_ns'] and
                  cache['listing'] == before_cache['listing'],
                  'native-update:loader-cache-not-refreshed')
    return {'filesystem': {'branch': environment['filesystem_branch'],
                           'links': environment['links']}, 'loader_cache': cache}


def rpm_service_execution(output, unit, started_us, boot):
    """Match fresh PID-1 start/done jobs even after inactive-unit collection."""
    boot = boot.replace('-', '')
    guest.require(re.fullmatch(r'[a-f0-9]{32}', boot) is not None, 'native-update:trigger-boot')
    starts, finished = {}, {}
    for line in output.splitlines():
        row = json.loads(line)
        if not (row.get('UNIT') == unit and row.get('JOB_TYPE') == 'start' and
                row.get('_PID') == '1' and row.get('_UID') == '0' and
                row.get('_SYSTEMD_UNIT') == 'init.scope' and row.get('_BOOT_ID') == boot):
            continue
        stamp = row.get('__MONOTONIC_TIMESTAMP', '')
        invocation, job = row.get('INVOCATION_ID', ''), row.get('JOB_ID', '')
        if not (isinstance(stamp, str) and stamp.isdecimal() and int(stamp) >= started_us and
                isinstance(invocation, str) and re.fullmatch(r'[a-f0-9]{32}', invocation) and
                isinstance(job, str) and job.isdecimal()):
            continue
        key = (invocation, job)
        if row.get('MESSAGE_ID') == '7d4958e842da4a758f6c1cdc7b36dcc5':
            guest.require(key not in starts, 'native-update:duplicate-trigger-start')
            starts[key] = int(stamp)
        elif row.get('MESSAGE_ID') == '39f53479d3a045ac8e11786248231fbf' and row.get('JOB_RESULT') == 'done':
            guest.require(key not in finished, 'native-update:duplicate-trigger-completion')
            finished[key] = int(stamp)
    # Each of the two native shell requests may start the unit, or coalesce.
    guest.require(len(starts) <= 2, 'native-update:extra-trigger-service-execution')
    if not starts or starts.keys() != finished.keys() or any(finished[key] < stamp for key, stamp in starts.items()):
        return None
    return [{'invocation': key[0], 'job': key[1], 'started_us': stamp, 'ended_us': finished[key]}
            for key, stamp in sorted(starts.items())]


def transaction(binding, manifest, directory, phase, before, record):
    """Exactly one supplied package; no repository or resolver repair route."""
    package = directory / manifest['packages'][phase]['path']
    triggers = before['native_state']['triggers']
    started = time.time()
    started_ns = time.time_ns()
    monotonic_started = int(time.monotonic() * 1000000)
    boot = BOOT.read_text().strip()
    diagnostic = private() / 'native-update-output'
    diagnostic.mkdir(mode=0o700, exist_ok=True)
    if manifest['package_format'] == 'rpm':
        before_cache = loader_cache()
        native_diagnostic(diagnostic, phase + '-triggers-before.txt', json.dumps(
            {'triggers': triggers, 'loader_cache': before_cache}, sort_keys=True))
    if manifest['package_format'] == 'deb':
        arguments = ['dpkg', '--install', str(package)]
    else:
        arguments = ['rpm', '-vv', '--upgrade', '--oldpackage', '--replacepkgs', str(package)]
    result = GuestRunner().run(arguments, timeout=180)
    # Native output is private and collected through the existing redactor.
    native_diagnostic(diagnostic, phase + '.txt', result.stdout)
    guest.require(result.returncode == 0, 'native-update:native-transaction-failed')
    if manifest['package_format'] == 'deb':
        guest.require('Processing triggers for man-db ' in result.stdout,
                      'native-update:man-db-trigger-not-observed')
    else:
        execution = rpm_execution(result.stdout, triggers['transactions'][phase])
        completion = rpm_completion(triggers, before_cache, started_ns)
        native_diagnostic(diagnostic, phase + '-native-triggers.txt', json.dumps(
            {'execution': execution, 'completion': completion}, sort_keys=True))
        deadline = time.monotonic() + 90
        state, execution, wait_error, journal_execution = {}, {}, None, None
        try:
            while True:
                try:
                    state = native.rpm_trigger_idle(GuestRunner())
                    execution = dict(line.split('=', 1) for line in guest.run(['systemctl', 'show',
                        triggers['completion_unit'],
                        '--property=ExecMainStartTimestampMonotonic,ExecMainExitTimestampMonotonic,ExecMainStatus'
                        ]).splitlines())
                    evidence = guest.run(['journalctl', '--no-pager', '--output=json',
                        '--since=@' + str(started), '-u', triggers['completion_unit']], timeout=30)
                    journal_execution = rpm_service_execution(
                        evidence, triggers['completion_unit'], monotonic_started, boot)
                    if journal_execution:
                        break
                except ValueError as error:
                    wait_error = type(error).__name__
                guest.require(time.monotonic() < deadline, 'native-update:trigger-timeout')
                time.sleep(0.25)
        finally:
            # Preserve the failed boundary before normal collection/cleanup.
            native_diagnostic(diagnostic, phase + '-trigger-wait.txt', json.dumps(
                {'state': state, 'execution': execution, 'error': wait_error,
                 'journal_execution': journal_execution}, sort_keys=True))
            failing = sys.exc_info()[0] is not None
            try:
                evidence = guest.run(['journalctl', '--no-pager', '--output=json',
                    '--since=@' + str(started), '-u', triggers['completion_unit']], timeout=30)
            except Exception as error:
                native_diagnostic(diagnostic, phase + '-trigger-journal-error.txt', type(error).__name__)
                if not failing:
                    raise
            else:
                native_diagnostic(diagnostic, phase + '-trigger-journal.txt', evidence)
        journal_execution = rpm_service_execution(evidence, triggers['completion_unit'], monotonic_started, boot)
        guest.require(journal_execution is not None, 'native-update:trigger-completion-journal')
        record('onpc.native-update.' + phase + '.trigger-execution', json.dumps(journal_execution, sort_keys=True))
        record('onpc.native-update.' + phase + '.trigger-state', json.dumps(state, sort_keys=True))
    identity = native_identity(manifest, phase)
    after = preflight(binding, manifest, directory)
    guest.require(unrelated_packages(before, manifest['selection']['package']) ==
                  unrelated_packages(after, manifest['selection']['package']),
                  'native-update:unrelated-native-changes')
    guest.require(after['native_state']['triggers']['applicable'] == triggers['applicable'],
                  'native-update:trigger-owner-drift')
    cache = cache_result(manifest, triggers, **({'started_ns': started_ns}
                        if manifest['package_format'] == 'rpm' else {}))
    descriptor = os.open(diagnostic / (phase + '-cache.txt'),
                         os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
    with os.fdopen(descriptor, 'w') as stream:
        json.dump(cache, stream, sort_keys=True)
    record('onpc.native-update.' + phase + '.cache', json.dumps(cache, sort_keys=True))
    record('onpc.native-update.' + phase + '.native', json.dumps(identity, sort_keys=True))
    return after


def establish_old(record=lambda *_: None):
    binding, manifest, directory = inputs()
    guest.before_install()  # Product-free gate before the deliberate downgrade.
    guest.enable_diagnostics()
    guest.require(not (private() / 'native-update-intent.json').exists(),
                  'native-update:attempt-already-started')
    diagnostic = private() / 'native-update-output'
    diagnostic.mkdir(mode=0o700, exist_ok=True)
    try:
        before = preflight(binding, manifest, directory)
        # A complete installed RPM inventory exceeds the small checkpoint limit
        # on the supported baseline. Keep every receipt byte in native evidence,
        # and bind it from the checkpoint instead of duplicating it there.
        receipt = json.dumps(before, sort_keys=True)
        native_diagnostic(diagnostic, 'old-preflight.txt', receipt)
        save('intent', binding, boot=BOOT.read_text().strip(), preflight={
            'read_only': before['read_only'], 'path': 'native-update-output/old-preflight.txt',
            'sha256': hashlib.sha256(receipt.encode()).hexdigest(),
            'bytes': len(receipt.encode())})
        transaction(binding, manifest, directory, 'old', before, record)
        save('old', binding, boot=BOOT.read_text().strip(), native=native_identity(manifest, 'old'))
    except Exception:
        # The public dispatcher deliberately hides arbitrary exception text.
        # Preserve its cause in the existing private, redacted evidence route.
        try:
            native_diagnostic(diagnostic, 'old-failure.txt', traceback.format_exc())
        except Exception:
            pass  # Diagnostic failure must not replace the original exception.
        raise


def measured_record(manifest, preparation, config):
    source = manifest['selection']['executable']
    matches = [entry for entry in preparation['inventory'](config)
               if entry.get('source', entry['path']) == source]
    guest.require(len(matches) == 1, 'native-update:measured-record')
    entry = matches[0]
    if manifest['package_format'] == 'deb':
        guest.require(entry['role'] == 'bwrap-native' and entry['path'] ==
                      '/usr/libexec/oh-no-parent-control-kiosk-bwrap' and entry.get('source') == source,
                      'native-update:bwrap-substitution')
    else:
        guest.require(entry['role'] == 'service' and entry['path'] == source,
                      'native-update:proxy-measurement')
    return entry


def mapping(pid, account, backend, generation, executable, expected_role):
    process = confinement.PROC / str(pid)
    identity = confinement.process_identity(process)
    info = (process / 'exe').stat()
    attribute = 'attr/apparmor/current' if backend == 'apparmor' else 'attr/current'
    label = (process / attribute).read_text().strip().rstrip('\0')
    expected = ('onpc-kiosk-' + expected_role + ' (enforce)' if backend == 'apparmor' else
                'system_u:system_r:onpc_kiosk_' + expected_role.replace('-', '_') + '_t:s0')
    guest.require(identity[2] == (str(account.pw_uid),) * 4 and label == expected and
                  (process / 'root' / GENERATION).read_text() == generation and
                  os.readlink(process / 'ns/mnt') != os.readlink(confinement.PROC / '1/ns/mnt'),
                  'native-update:witness-boundary')
    digest = guest.sha(process / 'exe')
    guest.require(digest == executable['sha256'], 'native-update:witness-executable')
    maps = []
    for line in (process / 'maps').read_text().splitlines():
        fields = line.split(maxsplit=5)
        if len(fields) >= 5 and 'x' in fields[1] and int(fields[4]) == info.st_ino:
            major, minor = (int(value, 16) for value in fields[3].split(':'))
            if (major, minor) == (os.major(info.st_dev), os.minor(info.st_dev)):
                maps.append(fields[:5])
    guest.require(maps, 'native-update:retained-executable-mapping-missing')
    guest.require(confinement.process_identity(process) == identity,
                  'native-update:witness-lifecycle-changed')
    return {'pid': pid, 'identity': identity, 'namespace': os.readlink(process / 'ns/mnt'),
            'generation': generation, 'label': label, 'sha256': digest,
            'device': info.st_dev, 'inode': info.st_ino, 'mappings': maps}


def wait_read(descriptor, maximum=4096, *, until_eof=False):
    poll = select.poll()
    poll.register(descriptor, select.POLLIN | select.POLLHUP)
    deadline = time.monotonic() + 15
    data = b''
    while True:
        remaining = deadline - time.monotonic()
        guest.require(remaining > 0 and poll.poll(max(1, int(remaining * 1000))),
                      'native-update:witness-ready-timeout')
        part = os.read(descriptor, maximum + 1 - len(data))
        data += part
        guest.require(len(data) <= maximum, 'native-update:witness-ready-data')
        if not until_eof or not part:
            guest.require(bool(data), 'native-update:witness-ready-data')
            return data


def bwrap_setup_blocked(pid, descriptor, pipe_identity):
    """Ubuntu amd64: native bwrap's final one-byte block-fd read follows mounts."""
    process = confinement.PROC / str(pid)
    fields = (process / 'syscall').read_text().split()
    if not (len(fields) == 9 and fields[0] == '0' and
            int(fields[1], 0) == descriptor and int(fields[3], 0) == 1):
        return False
    info = (process / 'fd' / str(descriptor)).stat()
    guest.require(stat.S_ISFIFO(info.st_mode) and (info.st_dev, info.st_ino) == pipe_identity,
                  'native-update:setup-pipe-replaced')
    return True


def wait_mapping(pid, pidfd, account, backend, generation, executable, role, *, block_fd, pipe_identity):
    """Wait for the owned native setup barrier, not an early /proc/root view."""
    deadline = time.monotonic() + 15
    while True:
        guest.require(not confinement.exited(pidfd), 'native-update:witness-exited')
        if bwrap_setup_blocked(pid, block_fd, pipe_identity):
            result = mapping(pid, account, backend, generation, executable, role)
            guest.require(not confinement.exited(pidfd), 'native-update:witness-exited')
            return result
        guest.require(time.monotonic() < deadline,
                      'native-update:witness-mapping-ready-timeout')
        time.sleep(0.02)


def proxy_exec(request):
    """Same engineering app-entry route as the maintained bwrap probe.

    The root-private Python entrypoint enters app_t on a normal mount. Its
    app -> service transition then executes the real pinned proxy, including
    the policy's nosuid_transition grant on the private executable view.
    """
    guest.require(set(request) == {'uid', 'gid', 'namespace', 'generation', 'ready_fd'} and
                  all(type(request[key]) is int and request[key] > 2
                      for key in ('uid', 'gid', 'namespace', 'ready_fd')) and
                  re.fullmatch(r'[a-f0-9]{64}\n', request['generation']) is not None,
                  'native-update:proxy-worker-request')
    guest.require(confinement.lifecycle_label('selinux') ==
                  'system_u:system_r:onpc_kiosk_app_t:s0', 'native-update:proxy-app-entry')
    os.setgroups([])
    os.setgid(request['gid'])
    os.setuid(request['uid'])
    guest.require(confinement.process_identity(confinement.PROC / 'self')[2] ==
                  (str(request['uid']),) * 4 and
                  os.stat('/proc/self/ns/mnt').st_ino == request['namespace'] and
                  Path('/' + GENERATION).read_text() == request['generation'],
                  'native-update:proxy-app-boundary')
    os.execve('/usr/bin/xdg-dbus-proxy', ['/usr/bin/xdg-dbus-proxy',
        f'unix:path=/run/user/{request["uid"]}/bus',
        f'/run/user/{request["uid"]}/onpc-native-update-proxy', '--filter',
        '--fd=' + str(request['ready_fd'])], {'PATH': '/usr/bin:/bin', 'LANG': 'C'})


def enter_proxy(caller, request):
    """Enter the app role through the normal-mount private test entrypoint."""
    library = ctypes.CDLL('libselinux.so.1', use_errno=True)
    library.setexeccon.argtypes = [ctypes.c_char_p]
    guest.require(library.setexeccon(b'system_u:system_r:onpc_kiosk_app_t:s0') == 0,
                  'native-update:proxy-role-entry')
    os.execve(str(caller), [str(caller), '-B', str(Path(__file__).resolve()),
        'proxy-exec', json.dumps(request)], {'PATH': '/usr/bin:/bin', 'LANG': 'C'})


@contextmanager
def native_witness(account, boundary, manifest, record):
    """Retain a real native ELF, with a directly spawned, pidfd-owned lifetime."""
    backend = 'apparmor' if manifest['package_format'] == 'deb' else 'selinux'
    manager = confinement.PROC / str(boundary['pid'])
    descriptors = set()
    child = None
    pidfd = None
    sandbox_fd = None
    socket_path = Path(f'/run/user/{account.pw_uid}/onpc-native-update-proxy')
    socket_identity = None
    reaped = False
    try:
        def opened(descriptor):
            descriptors.add(descriptor)
            return descriptor

        def pipe():
            pair = os.pipe2(os.O_CLOEXEC)
            descriptors.update(pair)
            return pair

        def close(descriptor):
            os.close(descriptor)
            descriptors.remove(descriptor)

        manager_fd = opened(os.pidfd_open(boundary['pid']))
        namespace = opened(os.open(manager / 'ns/mnt', os.O_RDONLY | os.O_CLOEXEC))
        root = opened(os.open(manager / 'root', os.O_RDONLY | os.O_DIRECTORY | os.O_CLOEXEC))
        guest.require(not confinement.exited(manager_fd) and
                      confinement.manager_boundary(account, f'user@{account.pw_uid}.service', backend) == boundary,
                      'native-update:witness-manager-changed')
        guest.require(not os.path.lexists(socket_path), 'native-update:proxy-socket-collision')
        caller = private() / 'native-update-proxy-caller'
        if backend == 'selinux':
            with caller.open('xb') as output, Path('/usr/bin/python3').resolve().open('rb') as source:
                shutil.copyfileobj(source, output)
            caller.chmod(0o700)
            guest.run(['/usr/bin/chcon', '-t', 'onpc_kiosk_python_exec_t', str(caller)])
        ready_read, ready_write = pipe()
        release_read, release_write = pipe()
        proof_read, proof_write = pipe()
        child = os.fork()
        if child == 0:
            try:
                for descriptor in (ready_read, release_write, proof_read):
                    os.close(descriptor)
                os.setns(namespace, os.CLONE_NEWNS)
                os.fchdir(root)
                os.chroot('.')
                os.chdir('/')
                for descriptor in (namespace, root, manager_fd):
                    os.close(descriptor)
                os.set_inheritable(ready_write, True)
                if backend == 'apparmor':
                    os.set_inheritable(release_read, True)
                    arguments = ['/usr/bin/bwrap', '--info-fd', str(ready_write),
                        '--block-fd', str(release_read), '--die-with-parent', '--unshare-pid',
                        '--as-pid-1', '--ro-bind', '/usr', '/usr', '--ro-bind', '/etc', '/etc',
                        '--proc', '/proc', '--dev', '/dev', '--tmpfs', '/tmp',
                        '--symlink', 'usr/lib', '/lib', '--symlink', 'usr/lib64', '/lib64',
                        '--', '/usr/bin/xdg-dbus-proxy', '--version']
                    confinement.bwrap_probe_child(dict(backend=backend, uid=account.pw_uid,
                        gid=account.pw_gid, namespace=os.stat('/proc/self/ns/mnt').st_ino,
                        generation=boundary['generation'],
                        arguments=arguments, proof_fd=proof_write))
                else:
                    request = dict(uid=account.pw_uid, gid=account.pw_gid,
                        namespace=os.stat('/proc/self/ns/mnt').st_ino,
                        generation=boundary['generation'], ready_fd=ready_write)
                    enter_proxy(caller, request)
            except BaseException:
                os._exit(124)
        pidfd = os.pidfd_open(child)
        for descriptor in (ready_write, release_read, proof_write):
            close(descriptor)
        # Native bubblewrap writes info JSON in several writes, then closes
        # this FD. The proxy's one-byte sync FD instead stays open until exit.
        data = wait_read(ready_read, until_eof=backend == 'apparmor')
        if backend == 'apparmor':
            sandbox_pid = confinement.bwrap_child_pid(data)
            proof = json.loads(wait_read(proof_read))
            guest.require(proof == dict(uid=account.pw_uid,
                namespace=int(boundary['namespace'].split('[')[1].rstrip(']')),
                generation=boundary['generation'], role='onpc-kiosk-app (enforce)'),
                'native-update:bwrap-app-proof')
            # --info-fd identifies the sandbox child, never the native monitor.
            guest.require(sandbox_pid != child and
                          confinement.process_identity(confinement.PROC / str(sandbox_pid))[1] == child,
                          'native-update:bwrap-monitor-child')
            record('onpc.native-update.bwrap.sandbox-child', sandbox_pid)
            sandbox_fd = os.pidfd_open(sandbox_pid)
            pipe = os.fstat(release_write)
            wait_mapping(sandbox_pid, sandbox_fd, account, backend,
                         boundary['generation'], manifest['packages']['old']['executable'], 'bwrap',
                         block_fd=release_read, pipe_identity=(pipe.st_dev, pipe.st_ino))
            record('onpc.native-update.bwrap.setup-barrier', True)
        else:
            guest.require(data == b'x', 'native-update:proxy-ready-protocol')
            info = socket_path.lstat()
            guest.require(stat.S_ISSOCK(info.st_mode) and info.st_uid == account.pw_uid,
                          'native-update:proxy-socket-identity')
            socket_identity = (info.st_dev, info.st_ino)
        role = 'bwrap' if backend == 'apparmor' else 'service'
        expected = manifest['packages']['old']['executable']
        def snapshot():
            guest.require(not confinement.exited(pidfd) and not confinement.exited(manager_fd),
                          'native-update:witness-exited')
            result = {'monitor': mapping(child, account, backend, boundary['generation'], expected, role),
                      'owning_manager_unit': f'user@{account.pw_uid}.service',
                      'owning_manager_pid': boundary['pid']}
            if sandbox_fd is not None:
                guest.require(not confinement.exited(sandbox_fd), 'native-update:sandbox-exited')
                result['sandbox'] = mapping(sandbox_pid, account, backend,
                    boundary['generation'], expected, role)
            return result
        before = snapshot()
        guest.require(not confinement.exited(pidfd), 'native-update:witness-exited')
        record('onpc.native-update.mapping.before', json.dumps(before, sort_keys=True))
        yield snapshot
        guest.require(not confinement.exited(pidfd), 'native-update:witness-exited')
        if backend == 'apparmor':
            os.write(release_write, b'\n')
        else:
            # Native 0.1.6 dbus-proxy.c watches sync fd G_IO_ERR|G_IO_HUP;
            # closing the sole pipe reader calls flatpak_proxy_stop and exit(0).
            close(ready_read)
        status = confinement.lifecycle_wait(child, pidfd)
        reaped = True
        guest.require(status == 0,
                      'native-update:witness-retirement')
        record('onpc.native-update.witness-retired', True)
    finally:
        cleanup_witness(child, pidfd, reaped, socket_path, socket_identity,
                        account.pw_uid, descriptors, sandbox_fd)


def cleanup_witness(child, pidfd, reaped, socket_path, socket_identity, uid,
                    descriptors, sandbox_fd):
    """Preserve foreign sockets and close every owned FD even on refusal."""
    try:
        try:
            if child is not None and child != 0 and not reaped:
                try:
                    if pidfd is None:
                        os.kill(child, signal.SIGKILL)  # Direct, unreaped child.
                    else:
                        signal.pidfd_send_signal(pidfd, signal.SIGKILL)
                except ProcessLookupError:
                    pass
                os.waitpid(child, 0)
        finally:
            if socket_identity is not None and os.path.lexists(socket_path):
                info = socket_path.lstat()
                guest.require(stat.S_ISSOCK(info.st_mode) and info.st_uid == uid and
                              (info.st_dev, info.st_ino) == socket_identity,
                              'native-update:proxy-socket-replaced')
                socket_path.unlink()
    finally:
        # ExitStack attempts every close even if one fails.
        from contextlib import ExitStack
        with ExitStack() as closing:
            for descriptor in (*descriptors, pidfd, sandbox_fd):
                if descriptor is not None:
                    closing.callback(os.close, descriptor)


def policy_state(*, configure=False):
    from system_enforcement import call, native_paths, provision_native
    from system_assertions import account_state
    parent = pwd.getpwnam('onpc-parent-jamie').pw_uid
    child = pwd.getpwnam('onpc-child-riley').pw_uid
    if configure:
        provision_native('trusted-hard')
        call(parent, 'SetParentControl', '(ubu)', (child, True, 37))
        preferences = json.loads(call(parent, 'GetPreferences', '(u)', (child,))[0])
        target, _desktop, identifier = native_paths('trusted-hard')
        preferences['apps'][identifier] = dict(state='permanent', targets=[str(target)],
            patterns=[], user_saved_match_rule=False)
        call(parent, 'SetPreferences', '(us)', (child, json.dumps(preferences)))
    preferences = json.loads(call(parent, 'GetPreferences', '(u)', (child,))[0])
    guest.require(preferences['parent_control_enabled'] is True and
                  preferences['daily_time_limit_minutes'] == 37, 'native-update:child-policy')
    state = account_state(child)
    return {'parent': parent, 'child': child, 'preferences': preferences,
            'native': json.loads(json.dumps([state[0].decode() if state[0] else None, *state[1:]]))}


def controls(account, backend, record, stage):
    from system_kiosk_scope import ordinary_accounts, verify_vendor_pam
    verify_vendor_pam(record)
    for role, ordinary in ordinary_accounts().items():
        result = confinement.user_command(ordinary, ['/bin/sh', '-c', 'printf onpc-native-control'])
        guest.require(result == b'onpc-native-control', 'native-update:ordinary-execution')
        record('onpc.native-update.' + stage + '.ordinary.' + role, True)
    result = confinement.user_command(account, ['/usr/bin/systemd-run', '--user', '--wait',
        '--collect', '--pipe', '--unit=onpc-native-update-positive-' + stage,
        '/usr/bin/systemctl', '--version'])
    guest.require(b'systemd ' in result, 'native-update:allowed-service')
    confinement.require_service_denial(account, backend,
        'onpc-native-update-denied-' + stage + '.service', ['/bin/sh', '-c', 'exit 0'], record)
    from system_enforcement import observe_launch
    observe_launch(pwd.getpwnam('onpc-child-riley').pw_uid, False, variant='trusted-hard')
    observe_launch(pwd.getpwnam('onpc-child-jordan').pw_uid, True, variant='trusted-hard')


def stale_admission(account, record):
    """Bind exact preparation refusal text to this one real final-session call."""
    directory = private() / 'native-update-output'
    directory.mkdir(mode=0o700, exist_ok=True)
    path = directory / 'stale-admission.txt'
    descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
    original = os.dup(2)
    first_sequence = guest.commands.sequence
    try:
        os.dup2(descriptor, 2)
        status, data = confinement.first_exec(account, private(),
            ['/usr/libexec/gdm-wayland-session', '--help'], armed=False)
    finally:
        os.dup2(original, 2)
        os.close(original)
        os.close(descriptor)
    guest.require(status == 125 and json.loads(data).get('pam', 0) != 0,
                  'native-update:stale-manager-admitted')
    diagnostic = path.read_bytes()
    # Fedora's vendor-caller subprocess has its own owned Commands stderr.
    if guest.commands.directory is not None:
        for sequence in range(first_sequence + 1, guest.commands.sequence + 1):
            source = guest.commands.directory / f'command-{sequence:04d}-stderr.txt'
            if source.exists():
                diagnostic += source.read_bytes()
    guest.require(b'reason=stale-manager-reboot-required' in diagnostic or
                  b'reason=manager-generation-stale' in diagnostic,
                  'native-update:stale-manager-reason')
    record('onpc.native-update.admission', 'stale-manager-reboot-required')


def retain_upgrade(record):
    import runpy
    binding, manifest, directory = inputs()
    old = checkpoint('old', binding)
    guest.require(BOOT.read_text().strip() != old['boot'], 'native-update:initial-reboot-required')
    guest.installed()
    native_identity(manifest, 'old')  # make install/reboot must preserve selected A.
    guest.enable_diagnostics()
    guest.require(not (private() / 'native-update-retained-intent.json').exists(),
                  'native-update:retained-phase-already-started')
    account = pwd.getpwnam('oh-no-parent-control')
    unit = f'user@{account.pw_uid}.service'
    config = json.loads(CONFIG.read_text())
    backend = config['backend']
    preparation = runpy.run_path('/usr/libexec/oh-no-parent-control-kiosk-confinement')
    boundary = confinement.manager_boundary(account, unit, backend)
    measured = measured_record(manifest, preparation, config)
    guest.require(measured['sha256'] == manifest['packages']['old']['executable']['sha256'],
                  'native-update:old-inventory')
    policy = policy_state(configure=True)
    pam = guest.pam_service_state()
    before = preflight(binding, manifest, directory)
    save('retained-intent', binding, boot=BOOT.read_text().strip(), boundary=boundary,
         native_record=measured, policy=policy, pam=pam)
    controls(account, backend, record, 'before')
    with native_witness(account, boundary, manifest, record) as retained:
        original = retained()
        transaction(binding, manifest, directory, 'new', before, record)
        def unchanged():
            guest.require(retained() == original and
                          confinement.manager_boundary(account, unit, backend) == boundary,
                          'native-update:retained-process-changed')
            visible = confinement.PROC / str(boundary['pid']) / 'root' / measured['path'].lstrip('/')
            guest.require(guest.sha(visible) == measured['sha256'] and
                          guest.sha(Path(manifest['selection']['executable'])) != measured['sha256'],
                          'native-update:private-native-generation-changed')
            guest.require(guest.pam_service_state() == pam and policy_state() == policy,
                          'native-update:policy-or-pam-changed')
            preparation['enforcing'](config)
        unchanged()
        record('onpc.native-update.mapping.after', json.dumps(retained(), sort_keys=True))
        controls(account, backend, record, 'updated')
        # Real GDM final-session admission must refuse A without publishing B.
        generations = sorted(path.name for path in RUNTIME.iterdir()
                             if re.fullmatch(r'[a-f0-9]{64}', path.name))
        stale_admission(account, record)
        guest.require(sorted(path.name for path in RUNTIME.iterdir()
                      if re.fullmatch(r'[a-f0-9]{64}', path.name)) == generations,
                      'native-update:stale-admission-published-generation')
        unchanged()
        loader_state_sha256 = confinement.verify_loader_admission_refusal(
            config, record, defer_drain=True)
        unchanged()
        guest.require(guest.run(['systemctl', 'show', '--value', '--property=Type', unit]) ==
                      'notify-reload' and guest.run(['systemctl', 'show', '--value',
                      '--property=ReloadSignal', unit]) == '59', 'native-update:reexec-protocol')
        guest.run(['systemctl', 'reload', unit], timeout=75)
        unchanged()
        controls(account, backend, record, 'reexec')
        unchanged()
    save('updated', binding, boot=BOOT.read_text().strip(), boundary=boundary,
         native_record=measured, policy=policy, pam=pam, old_mapping=original,
         loader_state_sha256=loader_state_sha256)
    record('onpc.native-update.updated', 'native-B; retained-A; admission-refused; loader-excluded; reexec-safe')


def retired(record=lambda *_: None):
    """Called after public Cancel returns to GDM; never forces manager exit."""
    binding, manifest, _directory = inputs()
    state = checkpoint('updated', binding)
    guest.require(BOOT.read_text().strip() == state['boot'], 'native-update:retirement-boot')
    account = pwd.getpwnam('oh-no-parent-control')
    sessions = guest.run(['loginctl', 'list-sessions', '--no-legend', '--no-pager'])
    for line in sessions.splitlines():
        session = line.split()[0]
        values = dict(row.split('=', 1) for row in guest.run(['loginctl', 'show-session',
            session, '--property=User,Class,Type']).splitlines())
        guest.require(not (values.get('User') == str(account.pw_uid) and
            values.get('Class') == 'user' and values.get('Type') in ('wayland', 'x11')),
            'native-update:owned-graphical-session-still-active')
    unit = f'user@{account.pw_uid}.service'
    active = guest.run(['systemctl', 'show', '--value', '--property=ActiveState', unit])
    guest.require(active in ('inactive', 'active', 'deactivating'), 'native-update:retirement-state')
    if active == 'active':
        backend = json.loads(CONFIG.read_text())['backend']
        guest.require(json.loads(json.dumps(confinement.manager_boundary(account, unit, backend))) ==
                      state['boundary'], 'native-update:logout-replaced-manager')
    native_identity(manifest, 'new')
    save('retired', binding, boot=state['boot'], manager_state=active)
    record('onpc.native-update.normal-exit', active)


record_retired = retired


def loader_after_reboot(record=lambda *_: None):
    """All old PAM handles must retire before load, and before fresh admission."""
    binding, manifest, _directory = inputs()
    guest.enable_diagnostics()
    try:
        finish_loader_after_reboot(binding, manifest, record)
    except Exception:
        try:
            diagnostic = private() / 'native-update-output'
            diagnostic.mkdir(mode=0o700, exist_ok=True)
            native_diagnostic(diagnostic, 'loader-failure.txt', traceback.format_exc())
        except Exception:
            pass
        raise


def finish_loader_after_reboot(binding, manifest, record):
    retired_state = checkpoint('retired', binding)
    state = checkpoint('updated', binding)
    boot = BOOT.read_text().strip()
    guest.require(boot != retired_state['boot'], 'native-update:loader-reboot-required')
    # SSH precedes systemd's completed boot and the broker's prerequisites.
    # Reuse the established readiness boundary before any policy D-Bus read.
    guest.wait_for_boot()
    account = pwd.getpwnam('oh-no-parent-control')
    confinement.wait_kiosk_inactive(account)
    native_identity(manifest, 'new')
    def generations():
        return sorted(path.name for path in RUNTIME.iterdir()
                      if re.fullmatch(r'[a-f0-9]{64}', path.name)) if RUNTIME.exists() else []
    before_generations = generations()
    guest.require(state['boundary']['generation'].strip() not in before_generations,
                  'native-update:loader-old-generation')
    config = json.loads(CONFIG.read_text())
    confinement.verify_loader_admission_drained(
        config, record, state['loader_state_sha256'], state['pam'])
    guest.require(policy_state() == state['policy'] and
                  generations() == before_generations and
                  BOOT.read_text().strip() == boot,
                  'native-update:drained-loader-changed-generation-or-policy')
    save('loader-drained', binding, boot=boot, loader_state_sha256=state['loader_state_sha256'])


def fresh_after_reboot(record):
    import runpy
    binding, manifest, _directory = inputs()
    retired_state = checkpoint('retired', binding)
    state = checkpoint('updated', binding)
    guest.require(BOOT.read_text().strip() != retired_state['boot'], 'native-update:recovery-reboot-required')
    drained = checkpoint('loader-drained', binding)
    guest.require(drained['boot'] == BOOT.read_text().strip() and
                  drained['loader_state_sha256'] == state['loader_state_sha256'],
                  'native-update:loader-drain-required')
    guest.installed()
    native_identity(manifest, 'new')
    guest.require(policy_state() == state['policy'] and guest.pam_service_state() == state['pam'],
                  'native-update:reboot-policy-or-pam-changed')
    account = pwd.getpwnam('oh-no-parent-control')
    config = json.loads(CONFIG.read_text())
    backend = config['backend']
    preparation = runpy.run_path('/usr/libexec/oh-no-parent-control-kiosk-confinement')
    entry = measured_record(manifest, preparation, config)
    boundary = confinement.manager_boundary(account, f'user@{account.pw_uid}.service', backend)
    guest.require(boundary['generation'] != state['boundary']['generation'] and
                  entry['sha256'] == manifest['packages']['new']['executable']['sha256'],
                  'native-update:fresh-generation-not-B')
    visible = confinement.PROC / str(boundary['pid']) / 'root' / entry['path'].lstrip('/')
    guest.require(guest.sha(visible) == entry['sha256'] and
                  not (RUNTIME / state['boundary']['generation'].strip()).exists(),
                  'native-update:old-generation-survived-reboot')
    controls(account, backend, record, 'fresh')
    from system_enforcement import call
    reply = call(account.pw_uid, 'ListManagedUsers')
    guest.require(any(int(row[0]) == state['policy']['child'] for row in reply[0]),
                  'native-update:public-kiosk-broker')
    save('complete', binding, boot=BOOT.read_text().strip(), boundary=boundary)
    record('onpc.native-update.recovered', 'new-public-station; native-B; enforcing; public-broker; child-policy-preserved')


if __name__ == '__main__':
    guest.require(len(sys.argv) == 3 and sys.argv[1] == 'proxy-exec',
                  'native-update:worker-command')
    proxy_exec(json.loads(sys.argv[2]))
