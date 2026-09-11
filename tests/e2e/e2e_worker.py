"""Guarded generalhw execution shared with the qualified smoke.

The caller owns the prepared lease and its outer restoration. This module owns
only the callback server and recorded worker. It exports structured diagnostics,
never raw worker logs, variables or screenshots. It is not a customer runner.
"""

import hashlib
import json
import os
from pathlib import Path
import re
import stat
import struct
import sys
import time

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'tests/integration'))
from graphical_lease import Adapter, CallbackServer, lifecycle_variables
from graphical_worker import Worker
from graphical_serial import SerialConsole
from owned_commands import require
sys.path.pop(0)

from evidence import FailureLedger
from private_artifacts import PrivateCollector
from secret_variables import SecretVariables

DISTRIBUTION = ROOT / 'tests/integration/graphical_smoke'
# Keep the backend's exit policy; controller validation separately rejects all
# missing/failed/softfailed module results. Upstream's module-derived exit
# option can overwrite an earlier backend error with passing module results.
COMMAND = ('/usr/bin/isotovideo',)


def validate_needles(files):
    """Bounded public PNG/JSON pairs, frozen with the executable distribution.

    This checks the asset contract, not visual semantics. A reviewed real
    empty/focused/masked prompt and live positive/negative matches are still
    required before password input is enabled for a surface.
    """
    names = {name for name in files if name.startswith('needles/')}
    for name in names:
        require(re.fullmatch(r'needles/onpc-(?:(gdm|polkit|lock)-(parent|child|other-parent|other-child)'
                             r'-(masked-password|account)|gdm-parent-installed-account|vt6-parent-password)\.(png|json)', name),
                'e2e:needle-name')
        require(name.rsplit('.', 1)[0] + ('.png' if name.endswith('.json') else '.json') in names,
                'e2e:needle-pair')
    for name in sorted(names):
        if not name.endswith('.json'):
            continue
        png = files[name[:-5] + '.png']
        require(len(png) >= 24 and png[:16] == b'\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR',
                'e2e:needle-png')
        width, height = struct.unpack('!II', png[16:24])
        require(640 <= width <= 4096 and 480 <= height <= 2160, 'e2e:needle-size')
        try:
            document = json.loads(files[name])
        except (ValueError, UnicodeError):
            require(False, 'e2e:needle-json')
        require(type(document) is dict and set(document) == {'tags', 'area'}
                and document['tags'] == [Path(name).stem]
                and type(document['area']) is list and 1 <= len(document['area']) <= 8,
                'e2e:needle-schema')
        if name == 'needles/onpc-vt6-parent-password.json':
            # Fixed baseline pixels, including the complete selected login and
            # blank challenge. Only its six-pixel terminal cursor cell may blink.
            # This exception must not enable exclusions on generic secret tags.
            require((width, height) == (1024, 768)
                    and document['area'] == [
                        {'xpos': 0, 'ypos': 0, 'width': 1024, 'height': 768,
                         'type': 'match', 'match': 100},
                        {'xpos': 0, 'ypos': 48, 'width': 228, 'height': 32,
                         'type': 'match', 'match': 100},
                        {'xpos': 198, 'ypos': 16, 'width': 30, 'height': 16,
                         'type': 'match', 'match': 100},
                        {'xpos': 60, 'ypos': 64, 'width': 6, 'height': 16,
                         'type': 'exclude'}]
                    and all(type(value) is int for area in document['area']
                            for key, value in area.items() if key != 'type'),
                    'e2e:vt6-needle-layout')
            continue
        for area in document['area']:
            require(type(area) is dict and set(area) - {'click_point'} == {'xpos', 'ypos', 'width', 'height',
                                                       'type', 'match'}
                    and area['type'] == 'match'
                    and all(type(area[key]) is int for key in ('xpos', 'ypos', 'width', 'height', 'match'))
                    and 99 <= area['match'] <= 100
                    and 0 <= area['xpos'] < width and 0 <= area['ypos'] < height
                    and 1 <= area['width'] <= width - area['xpos']
                    and 1 <= area['height'] <= height - area['ypos'], 'e2e:needle-area')
            if 'click_point' in area:
                point = area['click_point']
                require(name.endswith('-account.json') and not name.endswith('-installed-account.json')
                        and len(document['area']) == 1
                        and type(point) is dict and set(point) == {'xpos', 'ypos'}
                        and all(type(point[key]) is int for key in ('xpos', 'ypos'))
                        and 0 < point['xpos'] < area['width']
                        and 0 < point['ypos'] < area['height'], 'e2e:needle-click-point')


def distribution_inputs():
    """Freeze maintained Perl and validated needle pairs, including local edits.

    No arbitrary worker variables, extra schedule, checkpoints, executable
    overrides or credential input are accepted at this boundary.
    """
    require(DISTRIBUTION.resolve() == DISTRIBUTION, 'e2e:distribution-path')
    result = {}
    for path in sorted(DISTRIBUTION.rglob('*')):
        metadata = path.lstat()
        require(not stat.S_ISLNK(metadata.st_mode), 'e2e:distribution-symlink')
        if stat.S_ISDIR(metadata.st_mode):
            continue
        require(stat.S_ISREG(metadata.st_mode) and metadata.st_nlink == 1
                and (path.suffix == '.pm' or (path.parent == DISTRIBUTION / 'needles'
                                              and path.suffix in ('.json', '.png')))
                and metadata.st_size <= 1024 * 1024,
                'e2e:distribution-file')
        fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
        with os.fdopen(fd, 'rb') as stream:
            opened = os.fstat(stream.fileno())
            require((opened.st_dev, opened.st_ino) == (metadata.st_dev, metadata.st_ino),
                    'e2e:distribution-replaced')
            data = stream.read(1024 * 1024 + 1)
        require(len(data) <= 1024 * 1024, 'e2e:distribution-size')
        result[path.relative_to(DISTRIBUTION).as_posix()] = data
        require(len(result) <= 128, 'e2e:distribution-size')
    require('main.pm' in result and 'tests/smoke.pm' in result, 'e2e:distribution-incomplete')
    validate_needles(result)
    return result


def stage_distribution(directory, expected_inputs):
    """Copy frozen bytes only if they match the controller's earlier input map."""
    files = distribution_inputs()
    prefix = DISTRIBUTION.relative_to(ROOT).as_posix() + '/'
    actual = {prefix + name: hashlib.sha256(data).hexdigest() for name, data in files.items()}
    require(actual == {key: value for key, value in expected_inputs.items()
                       if key.startswith(prefix)}, 'e2e:distribution-inputs-changed')
    destination = directory / 'distribution'
    destination.mkdir(mode=0o700)
    for name, data in files.items():
        path = destination / name
        path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
        fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
        with os.fdopen(fd, 'wb') as stream:
            stream.write(data)
    (destination / 'needles').mkdir(mode=0o700, exist_ok=True)
    return hashlib.sha256(json.dumps(actual, sort_keys=True).encode()).hexdigest()


def variables(directory, server, run, *, serial=False):
    return {
        'BACKEND': 'generalhw', 'DISTRI': 'onpc-smoke',
        'CASEDIR': str(directory / 'distribution'),
        'WORKER_HOSTNAME': '127.0.0.1', 'GENERAL_HW_VNC_IP': '127.0.0.1',
        'GENERAL_HW_VNC_PORT': 5900, 'GENERAL_HW_NO_SERIAL': 1,
        # The stock generalhw SOL grabber remains disabled. This is a separate
        # public bidirectional console using controller-owned private pipes.
        'ONPC_SERIAL_SMOKE': int(serial),
        # Qualified public rgb888 path; the pinned client's 16-bit changed
        # ZRLE rectangles do not decode this QEMU display correctly.
        'GENERAL_HW_VNC_DEPTH': 32, 'NOVIDEO': 1,
        **lifecycle_variables(server.path, run),
    }


def run_distribution(directory, lease, ledger, *, expected_inputs, observe, validate,
                     timeout=600, on_failure=None, credentials=None, serial=False,
                     guarded_observe=None):
    """Run fixed trusted code against an existing isolated lease, then retain reports.

    observe/validate are controller functions, never supplied by the guest or
    CLI. Validation must reconcile actual module results and completed stages.
    A zero worker exit alone cannot pass. Final VM/host/source restoration and
    full inventory EvidenceContract acceptance remain the outer owner's job.
    on_failure is a trusted controller hook for durable scenario checkpoints;
    a broken hook cannot prevent either resource's cleanup or replace the error.
    """
    require(type(timeout) in (int, float) and 0 < timeout <= 1800, 'e2e:timeout')
    require(type(serial) is bool and (not serial or credentials is not None), 'e2e:serial-credentials')
    require(isinstance(lease.state['run'], str)
            and re.fullmatch(r'[0-9a-f]{32}', lease.state['run']), 'e2e:run')
    directory = Path(directory)
    metadata = directory.lstat()
    require(directory.is_absolute() and directory.resolve() == directory
            and stat.S_ISDIR(metadata.st_mode) and metadata.st_uid == os.geteuid()
            and stat.S_IMODE(metadata.st_mode) == 0o700, 'e2e:private-directory')
    # Adapter validates the held lease, its instance, graphics and off state
    # before storage, callbacks or worker construction.
    adapter = Adapter(lease)
    run_id = 'worker-' + lease.state['run']
    started = time.monotonic()
    failures = FailureLedger()
    server = worker = None
    first_error = None
    result = {'schema_version': 1, 'run_id': run_id, 'scope': 'credential-free-worker',
              'outcome': 'failed', 'distribution_sha256': None,
              'raw_capture': 'private-not-approved-for-export',
              'backend_exit_status': None, 'backend_failure_artifact': None,
              'lifecycle': [], 'shutdown_verified': False,
              'worker_stopped': False, 'callback_closed': False}
    # Credentials may come only from completed, same-lease provisioning. The
    # credential qualification performs GDM input; all raw output stays private.
    if credentials is not None:
        from fixture_credentials import FixtureCredentials
        require(type(credentials) is FixtureCredentials, 'e2e:fixture-credentials')
    secrets = credentials.worker_secrets(lease) if credentials is not None else SecretVariables()
    if credentials is not None:
        result['scope'] = 'fixture-secret-worker'
    with PrivateCollector(run_id=run_id, secrets=secrets.registered_secrets) as collector:
        result['evidence_directory'] = str(collector.path)
        def fail(category, code, error):
            nonlocal first_error
            first_error = first_error or error
            failures.record(category, code, monotonic_seconds=time.monotonic() - started)
            ledger.fail_outcome(category, 'e2e:' + code)
            if on_failure is not None:
                try:
                    on_failure(category, code)
                except BaseException:
                    failures.record('collection', 'scenario-checkpoint-failed',
                                    monotonic_seconds=time.monotonic() - started)
                    ledger.fail_outcome('collection', 'e2e:scenario-checkpoint-failed')

        def save(name):
            result.update(failures=failures.snapshot(), first_failure=failures.first_failure,
                          duration_seconds=time.monotonic() - started)
            collector.save_report(name, result)

        try:
            result['distribution_sha256'] = stage_distribution(directory, expected_inputs)
            server = CallbackServer(adapter, directory)
            if serial:
                adapter.serial = SerialConsole(adapter, directory)
            secrets.stage(directory, variables(directory, server, lease.state['run'], serial=serial))
            worker = Worker(directory, server.path, lease.state['run'], list(COMMAND))
            def guard_current_worker():
                adapter.revalidate()
                require(worker.poll() is None and worker.ready and worker.result is None,
                        'e2e:input-worker-not-running')
                # The worker executes this frozen private distribution. Recheck
                # its bytes before authorizing input after blocking observations.
                prefix = DISTRIBUTION.relative_to(ROOT).as_posix() + '/'
                for key, digest in expected_inputs.items():
                    if key.startswith(prefix):
                        path = directory / 'distribution' / key.removeprefix(prefix)
                        require(not path.is_symlink() and path.resolve().is_relative_to(
                            directory / 'distribution') and
                            hashlib.sha256(path.read_bytes()).hexdigest() == digest,
                            'e2e:input-distribution-changed')
            deadline = time.monotonic() + timeout
            while time.monotonic() < deadline:
                # Revalidate even when no callback is queued or the worker exits.
                adapter.revalidate()
                status = worker.poll()
                if status is not None:
                    result['backend_exit_status'] = status
                    # This upstream termination artifact is evidence of a fatal
                    # backend/isotovideo error even when the process exits zero.
                    # Presence alone refuses; never parse/export its raw message
                    # or follow a link (including a dangling link) to its target.
                    result['backend_failure_artifact'] = os.path.lexists(directory / 'base_state.json')
                    require(status == 0, 'e2e:backend-failed')
                    require(not result['backend_failure_artifact'], 'e2e:backend-failure-artifact')
                    validate()
                    events = adapter.events
                    require(adapter.phase == 'stopped' and 'poweron' in events
                            and 'poweroff' in events[events.index('poweron') + 1:]
                            and 'status-off' in events[events.index('poweroff') + 1:],
                            'e2e:shutdown-unverified')
                    lease.guard(off=True)
                    result['shutdown_verified'] = True
                    result['outcome'] = 'passed'
                    break
                server.serve_once()
                # Lifecycle callbacks run synchronously on the lease owner's
                # thread. Let an owned stop finish, but do not dispatch another
                # observation/input step if it consumed the remaining budget.
                require(time.monotonic() < deadline, 'e2e:deadline')
                if guarded_observe is not None:
                    require(not serial, 'e2e:guarded-observer-surface')
                    guarded_observe(guard_current_worker)
                elif serial:
                    adapter.serial.step()
                    observe(adapter.serial)
                else:
                    observe()
            else:
                require(False, 'e2e:deadline')
        except BaseException as error:
            fail('infrastructure', 'worker-interrupted' if isinstance(error, KeyboardInterrupt)
                 else 'worker-execution-failed', error)
        finally:
            result['lifecycle'] = list(adapter.events)
            # Persist the original failure before cleanup can fail or interrupt.
            try:
                save('worker-before-cleanup')
            except BaseException as error:
                fail('collection', 'worker-report-failed', error)
            with ledger.measure('cleanup'):
                for resource, key in ((worker, 'worker_stopped'), (server, 'callback_closed')):
                    try:
                        if resource is not None:
                            resource.close()
                        result[key] = True
                    except BaseException as error:
                        fail('cleanup', 'worker-cleanup-failed' if key == 'worker_stopped'
                             else 'callback-cleanup-failed', error)
            result['outcome'] = 'failed' if failures.snapshot() else result['outcome']
            try:
                save('worker-result')
                collector.verify([])
            except BaseException as error:
                fail('collection', 'worker-report-failed', error)
            # Fixed codes only. The path is a generated private artifact locator.
            print('e2e-worker: evidence=' + str(collector.path), file=sys.stderr, flush=True)
    if first_error is not None:
        raise first_error
    return result
