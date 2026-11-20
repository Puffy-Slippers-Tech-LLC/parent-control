"""Reconnectable test owner; terminals only observe its durable output."""

import fcntl
import json
import os
from pathlib import Path
import signal
import stat
import subprocess
import sys
import threading
import time
import uuid
from contextlib import ExitStack, nullcontext

sys.path.insert(0, str(Path(__file__).resolve().parent))
import test_source
if __name__ == '__main__':
    _source_imports = test_source.startup(Path(__file__).resolve().parents[1], sys.argv[1:])
    _source_imports.__enter__()

import test_activity
import test_launcher
from launcher_source_sync import BOUNDARY_AGENT_ENV, BOUNDARY_AGENT_ENV_KEYS

_startup = threading.RLock()

from detached_launcher import FRAME_DIRECTORY, atomic, busy, durable_json, lock

if __name__ == '__main__':
    _source_imports.__exit__(None, None, None)
    test_source.finish_imports(Path(__file__).resolve().parents[1])


class SessionOutput:
    def __init__(self, run, stream):
        self.run, self.stream = run, stream
        self.last_frame = None

    def __getattr__(self, name):
        return getattr(self.stream, name)

    def frame(self, lines):
        if lines == self.last_frame:
            return
        # A final frame can be cleared before the observer's next poll. Keep
        # the latest nonempty publication at the producer, where none are lost.
        if lines:
            atomic(self.run / 'test-frame.json', lines)
        temporary = self.run / 'frame.tmp'
        temporary.write_text(json.dumps(lines))
        temporary.replace(self.run / 'frame.json')
        self.last_frame = list(lines)

    def controller(self, key, lines):
        from launcher_progress import publish_progress
        publish_progress(self.run, key, lines)


def prepare(root, *, host_only=False, vm_name=None):
    from test_storage import directory as storage_directory
    directory = storage_directory('sessions-host' if host_only else 'sessions', root=root)
    if vm_name is not None and not host_only:
        directory = directory / ('vm-' + vm_name)
    for parent in (directory, *directory.parents):
        if parent.is_symlink():
            raise ValueError('aggregate session path contains a symlink')
    directory.mkdir(parents=True, exist_ok=True, mode=0o700)
    info = directory.stat()
    if info.st_uid != os.geteuid() or stat.S_IMODE(info.st_mode) != 0o700:
        raise ValueError('unsafe aggregate session directory')
    return directory


def current_session(directory):
    current = directory / 'current.json'
    try:
        record = json.loads(current.read_text())
        name = record.get('run') if isinstance(record, dict) else None
    except (OSError, ValueError):
        return None, False
    if not isinstance(name, str) or len(name) != 32 or any(c not in '0123456789abcdef' for c in name):
        return None, False
    run = directory / name
    if not run.is_dir():
        return None, False
    with lock(run / 'owner') as owner:
        return run, busy(owner)


def repair_supervisor():
    from test_results import REPAIR_QUEUE
    observer = os.environ.get(FRAME_DIRECTORY)
    return Path(observer) if observer and os.environ.get(REPAIR_QUEUE) == '1' else None


def select(root, argv, *, reload=False, watch=None, implicit_default=False, resume_request=None):
    # Activity descriptor state is process-local. Concurrent callers in this
    # process serialize only startup; detached host/VM workers remain independent.
    from test_commands import is_inspection
    if is_inspection(argv):
        return None, False
    from test_reset import startup
    test_source.finish_admission()
    with startup(root), _startup:
        try:
            with test_source.admission(root, ['--reload'] if reload else argv, wait=False):
                return _select(root, argv, reload=reload, watch=watch,
                               implicit_default=implicit_default, resume_request=resume_request)
        except (test_source.SourceBusy, test_activity.ActivityBusy) as error:
            from launcher_queue import REPLAY
            if os.environ.get(REPLAY):
                from launcher_controller import RetryQueuedStartup
                raise RetryQueuedStartup(str(error)) from error
            raise


def _select(root, argv, *, reload=False, watch=None, implicit_default=False, resume_request=None):
    from test_commands import host_only_request, includes_host_request, is_inspection, validate
    from test_results import REPAIR_QUEUE, VARIABLE
    # Inspection never attaches, waits for locks, or consumes an unread result.
    if is_inspection(argv):
        return None, False
    requested = list(argv) or ['all']
    host_only = host_only_request(requested)
    # Each scope discovers and starts its own worker; mixed runs reserve both
    # activity locks without inspecting or consuming another scope's results.
    from vm_selection import vm_config
    _, selector = vm_config.extract_selector(requested)
    vms = vm_config.execution(selector)[1] if selector is not None and not host_only else ()
    session_vm = vms[0].name if len(vms) == 1 else None
    if resume_request is not None and not os.environ.get(VARIABLE):
        session_vm = resume_request.get('session_vm', session_vm)
    directory = prepare(root, host_only=host_only,
                        vm_name=session_vm)
    test_source.finish_admission()
    with lock(directory / 'gate') as gate, ExitStack() as source, ExitStack() as capacity:
        fcntl.flock(gate, fcntl.LOCK_EX)
        source.enter_context(test_source.startup(root, ['--reload'] if reload else argv, wait=False))
        run, active = current_session(directory)
        expected_watch_run = os.environ.get('ONPC_WATCH_RUN')
        if expected_watch_run is not None and (not active or str(run) != expected_watch_run):
            raise ValueError('Watch launcher changed or stopped; refresh before trying again.')
        from detached_launcher import WORKFLOW_DIRECTORY
        from launcher_queue import Submission, retire_completed
        submission = None
        if (not reload and '--stop' not in argv and not any(os.environ.get(name) for name in (
                FRAME_DIRECTORY, WORKFLOW_DIRECTORY, VARIABLE, 'ONPC_RUNNER_INVOCATION',
                'ONPC_LAUNCHER_CONTROLLER_ROOT')) and os.environ.get('MAKELEVEL', '0') in ('', '0')):
            submission = Submission.public(root, directory)
            if submission is not None:
                receipt = submission.admit(run, active)
                if receipt is not None:
                    return receipt, False
        if reload and not active:
            test_source.restart_execution()
        if active:
            if os.environ.get(VARIABLE) and '--stop' not in argv and not reload:
                # Repair needs its requested execution, never another caller's
                # result. The caller waits outside this startup gate.
                return run, False
            from vm_selection import extract_execution as extract
            _, requested_vm = extract(requested, required=False)
            record = json.loads((directory / 'current.json').read_text())
            if not host_only and '--stop' not in argv:
                from vm_pool import check_attachment
                check_attachment(record)
            _, active_vm = extract(record['argv'], required=False)
            if active_vm is not None and requested_vm != active_vm:
                raise ValueError('vm-config: active run requires its original --vm NAME')
            original = record.get('vm_requested', record.get('vm_batch'))
            if original is not None and requested_vm is not None and active_vm is None:
                if requested_vm != ','.join(original['vms']):
                    raise ValueError('vm-config: active run requires its original VM queue')
            if watch:
                import watch_control
                value = watch_control.save(run, watch)
                print('run-tests: Watch SSH {ssh}; view {view} requested.'.format(
                    **{key: 'on' if enabled else 'off' for key, enabled in value.items()}), flush=True)
            if '--stop' in argv:
                (run / 'cancel').touch(mode=0o600)
            elif reload:
                from launcher_reload import request
                request(run)
                print('run-tests: reload requested; continuing the same run.', flush=True)
            return run, False
        if '--stop' in argv:
            return None, False
        from launcher_controller import require_startup_sync
        require_startup_sync()
        current = directory / 'current.json'
        if run is not None:
            result = run / 'result'
            try:
                broken = not result.exists() or int(result.read_text()) != 0
            except (ValueError, OSError):
                broken = True
            if broken and not (run / 'delivered').exists():
                print(f'Previous test owner is idle; preserving its incomplete/failed output in {run}.',
                      file=sys.stderr, flush=True)
        # Validate the request against the current checkout before execution.
        # Idle invocations with no arguments start the complete aggregate.
        if implicit_default:
            requested = vm_config.filter_vm_hosts(requested, use_defaults=True)
        validate(root, requested)
        if submission is None:
            retire_completed(directory)
        admitted = None
        original = None
        if not host_only:
            from vm_selection import BATCH, selected
            configured_vms = vm_config.registry()
            batch = BATCH in os.environ
            targets = ([configured_vms[name] for name in json.loads(os.environ[BATCH])['vms']]
                       if batch else [selected()])
            original = dict(vms=[vm.name for vm in targets])
            if not batch:
                # Explicit artifact preparation bypasses the test-group engine.
                # Its single VM retains the existing standalone reservation.
                import host_compute
                exact = False
                if '--resume' in requested and run is not None:
                    targets, exact = host_compute.resume_selection(targets, run)
                admitted = capacity.enter_context(host_compute.launch(targets, exact=exact))
        # Persist the actual selected guest, not an ID whose mapping may change
        # while this run is active. New public selectors still read current JSON.
        from vm_selection import extract_execution as extract
        requested, configured = extract(requested, required=False)
        worker_argv = [*requested, '--vm', configured] if configured is not None else requested
        # A default queue stays in the shared session namespace. The worker
        # still receives its canonical targets even if host defaults change.
        record_argv = requested if implicit_default else worker_argv
        # Keep host-only ownership independent of standalone VM preparation.
        # Pass its actual locked descriptor, never a PID-based ownership guess.
        # VM checkout happens in the lifetime owner, before checkout-local
        # bookkeeping. Startup holds only this session directory's gate.
        with (test_activity.activity(root, host_only=True) if host_only else nullcontext()):
            import test_retention
            store = test_retention.Store(directory / 'retention')
            with store.execution_session():
                run = directory / uuid.uuid4().hex
                run.mkdir(mode=0o700)
                test_retention.retain(run)
            with lock(run / 'owner') as owner, (run / 'output').open('xb') as output:
                fcntl.flock(owner, fcntl.LOCK_EX)
                from test_storage import scratch_descriptors
                from detached_launcher import atomic
                if admitted is None:
                    atomic(run / 'admitted-vms.json', [])
                else:
                    host_compute.save_admitted(run, admitted)
                command = ['/usr/bin/python3', '-u', '-B', str(Path(__file__).resolve()),
                           str(root), str(run), str(owner), *worker_argv]
                # Publish before spawning: terminal loss immediately after
                # Popen must not leave a live worker without reconnect metadata.
                temporary = directory / 'current.tmp'
                from vm_selection import BATCH
                from detached_launcher import owner_record, WORKFLOW_DIRECTORY
                # Display provenance only; this grants no execution or input authority.
                record = owner_record(run, launcher='run-tests', argv=record_argv,
                    watch_visibility=False,
                    observer=os.environ.get(FRAME_DIRECTORY) or os.environ.get(WORKFLOW_DIRECTORY),
                    vm_requested=original,
                    vm_batch=json.loads(os.environ[BATCH]) if BATCH in os.environ and not host_only else None)
                from detached_launcher import nested_operation, WORKFLOW_DIRECTORY
                environment = test_launcher.environment(root)
                from test_progress import SELECTION
                if repair_supervisor() is not None and SELECTION in os.environ:
                    environment[SELECTION] = os.environ[SELECTION]
                # Only independent runs and the repair scheduler's test pass
                # may update source. Nested validation owns its working edits.
                if os.environ.get(REPAIR_QUEUE) == '1' or not any(
                        os.environ.get(name) for name in ('ONPC_LAUNCHER_CONTROLLER_ROOT',
                            'ONPC_RUNNER_INVOCATION', VARIABLE, WORKFLOW_DIRECTORY)):
                    environment[BOUNDARY_AGENT_ENV] = json.dumps({
                        name: os.environ[name] for name in BOUNDARY_AGENT_ENV_KEYS if name in os.environ})
                import watch_control
                watch_control.initialize(run, watch or {}, inherit=bool(watch_control.environment()),
                                         record='--record' in requested)
                environment[watch_control.VARIABLE] = str(watch_control.target(run))
                if test_source.VARIABLE in environment and test_source.WRITER not in environment:
                    environment[test_source.IMPORTS] = environment[test_source.VARIABLE]
                from launcher_reload import ReloadRequest
                ReloadRequest(run).inherit(environment, supervisor=repair_supervisor())
                # Registration belongs to this public invocation. Test fixtures
                # and further runner workers must not claim the agent's owner.
                environment.pop(WORKFLOW_DIRECTORY, None)
                from launcher_queue import REPLAY
                environment.pop(REPLAY, None)
                with nested_operation(root, run):
                    from test_checkpoint import request_record
                    remembered = [arg for arg in worker_argv
                                  if arg not in ('--resume', '--resume-case-only', '--resume-area-only')
                                  and not arg.startswith('--resume-case=')]
                    if not host_only and configured is None:
                        remembered.extend(('--vm', ','.join(original['vms'])))
                    selection_record = {'argv': remembered, 'session_vm': session_vm}
                    replay = submission is not None and submission.replay is not None
                    descriptors = (*test_activity.descriptors(), owner, *scratch_descriptors())
                    if submission is not None:
                        durable_json(current, record)
                    else:
                        temporary.write_text(json.dumps(record))
                        temporary.replace(current)
                    if not replay:
                        request_record(root, 'run-tests', selection_record)
                    with (submission.starting(run) if submission is not None else nullcontext()):
                        subprocess.Popen(command, cwd=root, env=environment,
                                         stdin=subprocess.DEVNULL, stdout=output, stderr=subprocess.STDOUT,
                                         start_new_session=True,
                                         pass_fds=descriptors)
                    if replay:
                        try:
                            request_record(root, 'run-tests', selection_record)
                        except (OSError, ValueError) as error:
                            print(f'run-tests: could not save selection for bare --resume: {error}',
                                  file=sys.stderr)
        return run, True


def follow(run, stream=None):
    """Forward owned test output to a supervisor and preserve its verdict."""
    import codecs
    from detached_launcher import atomic
    from watch_output import JsonReader, snapshot
    stream = stream or sys.stdout
    from detached_launcher import WORKFLOW_DIRECTORY
    direct = os.environ.get(FRAME_DIRECTORY)
    destination = direct or os.environ.get(WORKFLOW_DIRECTORY)
    destination = Path(destination) if destination else None
    decoder = codecs.getincrementaldecoder('utf-8')(errors='replace')
    reader = JsonReader()
    forwarded = None
    forwarded_totals = None
    try:
        with lock(run / 'owner') as owner, ExitStack() as files:
            try:
                output = files.enter_context((run / 'output').open('rb'))
            except OSError:
                output = None
            while True:
                active = busy(owner)
                if destination is not None:
                    try:
                        steps = snapshot(run / 'controller.json', steps=True, reader=reader)
                        lines = snapshot(run / 'frame.json', reader=reader)
                        if not direct and destination.parent.name in ('fix-tests', 'fix-tests-host'):
                            from launcher_render import clean
                            lines = [line for line in lines if not clean(line).startswith('Overall - ')]
                        if steps is not None and (steps, lines) != forwarded:
                            atomic(destination / 'frame.json', lines)
                            forwarded = (steps, lines)
                        # Only the direct runner owns overall repair totals.
                        # Read its retained publication independently of live
                        # frames, which may already have been cleared.
                        if direct:
                            totals = snapshot(run / 'test-frame.json', reader=reader) or lines
                            if totals and totals != forwarded_totals:
                                atomic(destination / 'test-frame.json', totals)
                                forwarded_totals = totals
                    except (OSError, ValueError, KeyError, TypeError):
                        pass
                data = b''
                if output is not None:
                    try:
                        if output.tell() > os.fstat(output.fileno()).st_size:
                            output.seek(0)
                            decoder.reset()
                        data = output.read(65536)
                    except OSError:
                        output = None
                if data:
                    stream.write(decoder.decode(data))
                    stream.flush()
                    continue
                if not active:
                    stream.write(decoder.decode(b'', final=True))
                    stream.flush()
                    from test_results import PENDING_STATUS
                    try:
                        status = int((run / 'result').read_text())
                    except (OSError, ValueError):
                        status = PENDING_STATUS
                    if status == PENDING_STATUS:
                        print('Test owner stopped without a clear final result; work remains pending.',
                              file=stream, flush=True)
                    (run / 'delivered').touch(mode=0o600)
                    return status
                time.sleep(.1)
    finally:
        if destination is not None:
            atomic(destination / 'frame.json', [])


def main(root, argv, *, reload=False, reset=False, watch=None, implicit_default=False, resume_request=None):
    run = None
    requested = False

    def cancel(*_):
        nonlocal requested
        requested = True
        if isinstance(run, Path):
            (run / 'cancel').touch(mode=0o600)

    previous = signal.signal(signal.SIGINT, cancel)
    try:
        def start():
            return select(root, argv, **({'reload': True} if reload else {}),
                          **({'watch': watch} if watch else {}),
                          **({'resume_request': resume_request} if resume_request is not None else {}),
                          **({'implicit_default': True} if implicit_default else {}))
        if reset:
            from test_reset import reset as reset_state
            from launcher_queue import reset_gate
            from test_commands import host_only_request, validate
            from vm_selection import vm_config
            if implicit_default:
                argv = vm_config.filter_vm_hosts(argv, use_defaults=True)
            validate(root, argv or ['all'])
            _, selector = vm_config.extract_selector(argv)
            with reset_gate(root, exclusive=True) as lease:
                run, started = reset_state(root, lambda: test_source.restart_execution(reset_lease=os.dup(lease)),
                                           host_only=host_only_request(argv or ['all']), selector=selector)
        else:
            run, started = start()
        from launcher_queue import Receipt
        if isinstance(run, Receipt):
            return run.report('run-tests', sys.stdout)
        from test_results import VARIABLE
        if os.environ.get(VARIABLE) and '--stop' not in argv and not reload:
            from launcher_reload import STATUS as RELOAD_STATUS, unaccepted
            supervisor = repair_supervisor()
            while run is not None and not started:
                waiting, run = run, None
                print('run-tests: waiting for the active test session before starting selected work.',
                      file=sys.stderr, flush=True)
                with lock(waiting / 'owner') as owner:
                    while busy(owner) and not requested:
                        time.sleep(.1)
                if requested:
                    return 130
                if supervisor is not None and unaccepted(supervisor) is not None:
                    return RELOAD_STATUS
                run, started = start()
        if run is None:
            from test_commands import is_inspection
            if '--stop' in argv and not is_inspection(argv):
                print('run-tests: no active run to stop.', file=sys.stderr, flush=True)
                return 0
            from test_commands import _main
            return _main(argv)
        if requested:
            cancel()
        # Automation must receive the test verdict before accepting work or
        # starting the next Make recipe. MAKELEVEL is exported by Make itself.
        # Independent public launchers only acknowledge controller admission.
        from detached_launcher import WORKFLOW_DIRECTORY
        if (os.environ.get(FRAME_DIRECTORY) or os.environ.get('ONPC_RUNNER_INVOCATION')
                or os.environ.get(WORKFLOW_DIRECTORY)
                or os.environ.get('MAKELEVEL', '0') not in ('', '0')):
            print(f'{"Started" if started else "Attached to"} run-tests session: {run.name}',
                  file=sys.stderr, flush=True)
            return follow(run)
        from detached_launcher import report_start
        return report_start(run, label='run-tests', started=started,
                            stop='--stop' in argv, reload=reload)
    finally:
        signal.signal(signal.SIGINT, previous)


def record_result(run, status, *, interrupted=False):
    if interrupted:
        durable_json(run / 'interrupted.json', True)
    durable_json(run / 'result', status)


def worker(root, argv, run, owner, *, reloading=False):
    # setsid in Popen disconnects the controlling terminal before this exec.
    signal.signal(signal.SIGHUP, signal.SIG_IGN)
    if (run / 'cancel').exists():
        record_result(run, 130)
        os.close(owner)
        return 130
    with test_source.reader(root):
        import regression_process
        import test_io
        import launcher_reload
        from test_storage import scratch_descriptors
    from launcher_control import watching, CancellationEvent
    regression_process.session_stop = CancellationEvent(run)
    regression_process.session_interrupted = False
    # Keep cancellation cooperative through recorder startup, publication and
    # final result storage, after the inner category controllers have exited.
    with watching(run) as reload_request, regression_process.Control().installed(), test_io.low_io(), \
            ExitStack() as resources:
        try:
            return owned_worker(root, argv, run, owner, resources=resources, reloading=reloading)
        except launcher_reload.ReloadRequested:
            status = launcher_reload.STATUS if reload_request.supervisor_pending() else 130
            try:
                if regression_process.session_stop.is_set():
                    status = 130
                elif status != launcher_reload.STATUS:
                    if BOUNDARY_AGENT_ENV in os.environ:
                        from launcher_controller import synchronize_reload
                        resources.close()
                        synchronize_reload(root, run)
                        if regression_process.session_stop.is_set():
                            return 130
                    options = argv if '--resume' in argv else ['--resume', *argv]
                    print('run-tests: reloading controller; completed work retained.', flush=True)
                    os.environ.update(test_activity.environment(reloading=True))
                    with test_source.reader(root) as source:
                        temporary = test_source.WRITER not in test_source.environment()
                        if temporary:
                            os.environ[test_source.IMPORTS] = str(source)
                        try:
                            launcher_reload.replace(['/usr/bin/python3', '-IBu', str(Path(__file__).resolve()),
                                str(root), str(run), str(owner), '--reload-worker', *options],
                                (owner, *test_activity.descriptors(reloading=True), *scratch_descriptors()))
                        finally:
                            if temporary:
                                os.environ.pop(test_source.IMPORTS, None)
            except KeyboardInterrupt:
                status = 130
            except (OSError, ValueError) as error:
                status = 1
                print(f'run-tests: controller reload failed: {error}; resume the retained run.', flush=True)
            finally:
                try:
                    resources.close()
                except (OSError, ValueError) as error:
                    status = 1
                    print(f'Test runner lifetime cleanup failed: {error}', file=sys.stderr, flush=True)
                try:
                    record_result(run, status, interrupted=regression_process.session_interrupted)
                finally:
                    os.close(owner)
            return status


def owned_worker(root, argv, run, owner, *, resources=None, reloading=False):
    if resources is None:
        with ExitStack() as resources:
            return owned_worker(root, argv, run, owner, resources=resources, reloading=reloading)
    import regression_process
    from launcher_reload import ReloadRequested, STATUS as RELOAD_STATUS, check as check_reload
    status = 1
    continuing = reloading
    reloading = False
    media = None
    original = sys.stdout
    sys.stdout = SessionOutput(run, original)
    try:
        if not regression_process.session_stop.is_set():
            check_reload()
        with test_source.reader(root, stopped=regression_process.session_stop.is_set):
            from test_commands import _main, selections, host_only_selection, host_only_request, includes_host_request
            from test_recovery import before_run
            from vm_pool import selected_reservation
            from vm_selection import BATCH
            from vm_recording import recording
            # The batch enters its own finite source admissions. Import its
            # controller here before releasing this initialization lease.
            if BATCH in os.environ and not host_only_request(argv):
                import vm_test_queue
        resources.enter_context(selected_reservation(enabled=not host_only_request(argv),
                                stopped=regression_process.session_stop))
        resources.enter_context(test_activity.activity(root, host_only=host_only_request(argv),
                                includes_host=includes_host_request(root, argv)))
        # A batch delegates source admission to each finite VM attempt; a
        # standalone owner keeps its admitted selection through owned cleanup.
        if BATCH not in os.environ or host_only_request(argv):
            resources.enter_context(test_source.reader(root, stopped=regression_process.session_stop.is_set))
        # Lifetime resources stay open until replacement or final owned cleanup.
        categories = [kind for kind, _ in selections(root, argv)] if argv else []
        sys.stdout.controller('preparing', [
            f'Category: {categories[0] if categories else "all"} (1/{len(categories) or 1}) | Preparing tests'])
        from vm_selection import BATCH
        checkpoint = None
        if BATCH not in os.environ or host_only_selection([(kind, []) for kind in categories]):
            from test_checkpoint import Checkpoint
            checkpoint = Checkpoint(root, selections(root, argv or ['all']), resume='--resume' in argv)
            replay = [arg.partition('=')[2] for arg in argv if arg.startswith('--resume-case=')]
            if replay:
                if len(categories) != 1:
                    raise ValueError('case retry requires one category')
                checkpoint.retry(categories[0], replay[0], area='--resume-area-only' in argv)
            before_run(root, argv, categories=categories)
        with recording(root, enabled='--record' in argv and BATCH not in os.environ
                       and not host_only_selection([(kind, []) for kind in categories]), run=run) as media:
            from test_progress import repair_selection
            accounting = repair_selection()
            status = _main(argv, detached=True, **({'checkpoint': checkpoint} if checkpoint else {}),
                           **({'accounting': accounting} if accounting is not None else {}),
                           **({'reloading': True} if continuing else {}),
                           **({'upstream_run': run} if BOUNDARY_AGENT_ENV in os.environ else {}))
    except ReloadRequested:
        reloading, status = True, RELOAD_STATUS
    except KeyboardInterrupt:
        status = 130
    except Exception as error:
        print(f'Test runner infrastructure failed: {type(error).__name__}: {error}',
              file=sys.stderr, flush=True)
        status = 1
    finally:
        if status in (0, RELOAD_STATUS) and regression_process.session_stop.is_set():
            status = 130
        if media is not None:
            media.write_index(run, status)
        sys.stdout.flush()
        sys.stderr.flush()
        sys.stdout = original
        if reloading and status != RELOAD_STATUS:
            reloading = False
        if not reloading:
            try:
                resources.close()
            except (OSError, ValueError) as error:
                status = 1
                print(f'Test runner lifetime cleanup failed: {error}', file=sys.stderr, flush=True)
            for variable in (test_activity.VARIABLE, test_activity.HOST_VARIABLE,
                             test_activity.COMPATIBILITY_VARIABLE):
                if variable in os.environ:
                    os.close(int(os.environ.pop(variable)))
            record_result(run, status, interrupted=regression_process.session_interrupted)
            os.close(owner)
    if reloading:
        raise ReloadRequested()
    return status


if __name__ == '__main__':
    options = sys.argv[4:]
    reloading = options[:1] == ['--reload-worker']
    sys.exit(worker(Path(sys.argv[1]), options[1:] if reloading else options,
                    Path(sys.argv[2]), int(sys.argv[3]), reloading=reloading))
