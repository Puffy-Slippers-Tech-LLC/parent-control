"""Owned subprocess cancellation and streaming for unattended regression runs."""

from contextlib import contextmanager
from pathlib import Path
import json
import os
import selectors
import signal
import subprocess
import sys
import threading
import time
import math


# Only the detached test owner installs this event. Its nested storage and
# command controllers must observe the same terminal-independent cancellation.
session_stop = None


FRAME_PREFIX = 'ONPC_CLEANUP_FRAME '


class PipeFrameOutput:
    """Carry live frames through dispatcher pipes without terminal escapes."""

    def __init__(self, stream):
        self.stream = stream
        self.live = False

    def __getattr__(self, name):
        return getattr(self.stream, name)

    def frame(self, lines):
        # Only the session observer owns a terminal. Preserve the complete
        # dashboard for its existing replaceable-frame channel.
        self.stream.write(FRAME_PREFIX + json.dumps(lines) + '\n')
        self.stream.flush()
        self.live = bool(lines)

    def write(self, value):
        # Do not let the observer redraw a stale frame over the final summary.
        if value and self.live:
            self.frame([])
        return self.stream.write(value)


class PipeFrameReader:
    """Separate nested frames from ordinary output across arbitrary reads."""

    def __init__(self, stream):
        self.stream = stream
        self.pending = b''
        self.dashboard = None
        if not hasattr(stream, 'frame'):
            from regression import Dashboard
            self.dashboard = Dashboard([], stream=stream)

    def frame(self, lines):
        if self.dashboard is None:
            self.stream.frame(lines)
        elif lines and self.stream.isatty():
            self.dashboard.draw_lines(lines)
        else:
            self.dashboard.restore_terminal()

    def write(self, data):
        if self.dashboard is not None:
            self.dashboard.restore_terminal()
        self.stream.buffer.write(data)
        self.stream.buffer.flush()

    def __call__(self, data):
        self.pending += data
        while b'\n' in self.pending:
            line, self.pending = self.pending.split(b'\n', 1)
            prefix = FRAME_PREFIX.encode()
            if line.startswith(prefix):
                self.frame(json.loads(line[len(prefix):]))
            else:
                self.write(line + b'\n')

    def finish(self):
        if self.pending:
            self.write(self.pending)
            self.pending = b''
        if self.dashboard is not None:
            self.dashboard.restore_terminal()


class Control:
    """Latch cancellation and signal only a directly spawned child's pidfd.

    Privileged dispatchers receive STOP/EOF on inherited stdin. Their parent
    waits until the child finishes its guarded cleanup, including VM restore.
    UI timeouts additionally retire the child's private process group, keeping
    its leader unreaped until output draining and bounded cleanup finish.
    """

    def __init__(self):
        self.stopped = session_stop if session_stop is not None else threading.Event()
        self.interrupted = False
        self.pipe = False

    def stop(self, *_):
        self.stopped.set()

    def interrupt(self, *_):
        # Signal handlers only latch state. The coordinator renders the notice;
        # repeated Ctrl+C never interrupts a child's cleanup or terminal write.
        if not self.interrupted:
            self.interrupted = True
            self.stop()

    @contextmanager
    def installed(self, *, pipe=False):
        self.pipe = pipe
        previous = {sig: signal.signal(sig, self.interrupt)
                    for sig in (signal.SIGINT, signal.SIGTERM)}
        if pipe:
            def listen():
                os.read(sys.stdin.fileno(), 1)
                self.stop()
            threading.Thread(target=listen, daemon=True).start()
        try:
            yield self
        finally:
            for sig, handler in previous.items():
                signal.signal(sig, handler)

    def run(self, command, *, cwd, env, output=None, cooperative=False, tick=None,
            timeout=None, kill_after=30.0, cancel_signal=signal.SIGINT,
            stderr_output=None, **kwargs):
        # The installed dispatcher loads this file before adding the validated
        # checkout tools directory for its deferred imports.
        import test_activity
        bounded_group = timeout is not None
        if bounded_group and (cooperative or not math.isfinite(timeout) or timeout <= 0
                              or not math.isfinite(kill_after) or kill_after <= 0):
            raise ValueError('invalid owned UI timeout')
        if cancel_signal not in (signal.SIGINT, signal.SIGTERM):
            raise ValueError('invalid owned cancellation signal')
        if self.stopped.is_set():
            return 130
        frames = None
        # Pipe workers (including the privileged dispatcher) relay frames;
        # the outer caller renders them or publishes to its session observer.
        if output is None and (not self.pipe or hasattr(sys.stdout, 'frame')):
            frames = PipeFrameReader(sys.stdout)
            output = frames
        elif output is None:
            def output(data):
                sys.stdout.buffer.write(data)
                sys.stdout.buffer.flush()
        from test_storage import scratch_descriptors
        kwargs.setdefault('pass_fds', (*test_activity.descriptors(), *scratch_descriptors()))
        child = subprocess.Popen(command, cwd=cwd, env=env,
                                 stdin=subprocess.PIPE if cooperative else subprocess.DEVNULL,
                                 stdout=subprocess.PIPE,
                                 stderr=subprocess.PIPE if stderr_output is not None else subprocess.STDOUT,
                                 start_new_session=True, **kwargs)
        try:
            descriptor = os.pidfd_open(child.pid)
        except BaseException:
            # Popen still owns this unreaped child. Do not abandon it if the
            # kernel refuses another descriptor (for example under FD pressure).
            if cooperative:
                try:
                    child.stdin.write(b'STOP\n')
                    child.stdin.flush()
                except BrokenPipeError:
                    pass
            else:
                if bounded_group:
                    os.killpg(child.pid, signal.SIGTERM)
                else:
                    child.send_signal(signal.SIGINT)
            if bounded_group:
                limit = time.monotonic() + kill_after
                while time.monotonic() < limit:
                    if os.waitid(os.P_PID, child.pid, os.WEXITED | os.WNOHANG | os.WNOWAIT) is not None:
                        break
                    time.sleep(.01)
                # Keep the Popen child unreaped until its whole private group
                # is retired, even when pidfd allocation itself failed.
                os.killpg(child.pid, signal.SIGKILL)
                # A pipe holder outside that group need not exit with it.
                # No pidfd is available to drive draining; close our reader
                # and wait only for the explicitly spawned, killed child.
                child.stdout.close()
                if child.stderr is not None:
                    child.stderr.close()
                child.wait()
            else:
                child.communicate()
            raise
        sent = False
        output_error = None
        deadline = time.monotonic() + timeout if bounded_group else None
        retirement = None
        timed_out = forced = child_exited = False
        reaped = False

        def signal_group(sig):
            # start_new_session made this explicitly spawned child its group
            # leader. Keep it unreaped until pipes and group cleanup finish:
            # the zombie/pidfd receipt prevents leader/PID reuse throughout.
            try:
                os.killpg(child.pid, sig)
            except ProcessLookupError:
                pass

        def emit(data, sink=None):
            nonlocal output_error
            if output_error is None:
                try:
                    (output if sink is None else sink)(data)
                except BaseException as error:
                    output_error = error
                    self.stop()

        try:
            with selectors.DefaultSelector() as poller:
                poller.register(child.stdout, selectors.EVENT_READ)
                if child.stderr is not None:
                    poller.register(child.stderr, selectors.EVENT_READ)
                if bounded_group:
                    poller.register(descriptor, selectors.EVENT_READ)
                while poller.get_map() or (not bounded_group and child.poll() is None):
                    now = time.monotonic()
                    if self.stopped.is_set() and not sent:
                        sent = True
                        if cooperative:
                            try:
                                child.stdin.write(b'STOP\n')
                                child.stdin.flush()
                            except BrokenPipeError:
                                pass
                        else:
                            if bounded_group:
                                # Keep fixture services alive while pytest
                                # runs its ordinary KeyboardInterrupt cleanup.
                                try:
                                    signal.pidfd_send_signal(descriptor, cancel_signal)
                                except ProcessLookupError:
                                    pass
                                retirement = now + kill_after
                            else:
                                try:
                                    signal.pidfd_send_signal(descriptor, cancel_signal)
                                except ProcessLookupError:
                                    pass
                    if bounded_group and not sent and now >= deadline:
                        sent = timed_out = True
                        retirement = now + kill_after
                        emit(b'UI worker deadline reached; terminating its owned process group.\n')
                        signal_group(signal.SIGTERM)
                    if retirement is not None and not forced and now >= retirement:
                        forced = True
                        emit(b'UI worker cleanup deadline reached; killing its owned process group.\n')
                        signal_group(signal.SIGKILL)
                    for key, _ in poller.select(0.1):
                        if bounded_group and key.fd == descriptor:
                            child_exited = True
                            poller.unregister(descriptor)
                            continue
                        data = os.read(key.fd, 65536)
                        if not data:
                            poller.unregister(key.fileobj)
                        else:
                            emit(data, stderr_output if key.fileobj is child.stderr else None)
                    if bounded_group and forced and child_exited and poller.get_map():
                        # The killed leader has exited, but EOF is not a death
                        # receipt: another session may still hold the writer.
                        # Finish the bounded drain without signalling that
                        # unowned session, and retain the leader until the
                        # final group signal below has completed.
                        emit(b'UI output pipe remained open after cleanup; closing its reader.\n')
                        for key in list(poller.get_map().values()):
                            poller.unregister(key.fileobj)
                            key.fileobj.close()
                    if bounded_group and child_exited and poller.get_map() and retirement is None:
                        # A descendant can retain stdout after pytest dies.
                        # Retire its still-pinned group, never wait forever for
                        # pipe EOF or reap the leader before signalling it.
                        retirement = time.monotonic() + kill_after
                        signal_group(signal.SIGTERM)
                    if tick is not None and output_error is None:
                        try:
                            tick()
                        except BaseException as error:
                            output_error = error
                            self.stop()
                if bounded_group:
                    # Worker exit and pipe EOF are confirmed, but a service
                    # with redirected output could still outlive it. Retire
                    # this private session before releasing the leader receipt.
                    signal_group(signal.SIGKILL)
                status = child.wait()
                reaped = True
            if output_error is not None:
                raise output_error
            if frames is not None:
                frames.finish()
            return (130 if self.stopped.is_set() else
                    137 if timed_out and forced else 124 if timed_out else
                    125 if forced else status if status >= 0 else 128 - status)
        except BaseException:
            if bounded_group and not reaped and child.returncode is None:
                # Selector/read failures must not abandon the owned child.
                # Never use its numeric group after wait() released the leader.
                signal_group(signal.SIGKILL)
                child.stdout.close()
                if child.stderr is not None:
                    child.stderr.close()
                child.wait()
            raise
        finally:
            os.close(descriptor)
            child.stdout.close()
            if child.stderr is not None:
                child.stderr.close()
            if child.stdin is not None:
                child.stdin.close()


def safety_command(root):
    """Run the shared cleanup gate coordinator as the unprivileged caller."""
    import test_activity
    descriptors = test_activity.descriptors()
    inherited = ([] if not descriptors else ['--activity-fd=' + str(descriptors[0])])
    return ['/usr/bin/python3', '-IB', str(root / 'tools/regression_process.py'),
            '--cleanup-prerequisites', *inherited]


def cleanup_main(root=None, *, activity_fd=None):
    """Give privileged dispatchers the aggregate's parallel cleanup gate."""
    import regression
    import test_activity
    from test_launcher import cleanup_environment
    from regression_selection import CLEANUP_SELECTION
    root = root or Path(__file__).resolve().parents[1]
    # VM selections own the VM activity lock. Cleanup workers use the separate
    # host lock, then inherit it through the ordinary aggregate commands. A
    # host launcher can instead pass its already-owned descriptor explicitly.
    previous = dict(os.environ)
    os.environ.clear()
    os.environ.update(cleanup_environment())
    if activity_fd is not None:
        os.environ[test_activity.VARIABLE] = str(activity_fd)
    output = sys.stdout
    sys.stdout = PipeFrameOutput(output)
    try:
        with test_activity.activity(root, host_only=True if activity_fd is None else None):
            if test_activity.cleanup_verified(root):
                print('run-tests: cleanup qualification reused from owned activity', flush=True)
                return 0
            from e2e_startup_cache import qualified_cleanup
            return qualified_cleanup(root, lambda: regression.retained_main(
                root, selections=[(CLEANUP_SELECTION, [])]))
    finally:
        sys.stdout = output
        os.environ.clear()
        os.environ.update(previous)


def host_run(root, category, argv, *, pipe=True):
    import test_launcher as host
    with Control().installed(pipe=pipe) as control:
        command = host.pytest_command(root, argv, category)
        env = host.test_environment(root)
        env['PYTHONUNBUFFERED'] = '1'
        if pipe:
            env['ONPC_REGRESSION_EVENTS'] = '1'
        if category in ('unit', 'ui'):
            env['ONPC_REGRESSION_INVENTORY'] = '1'
        if category == 'ui':
            import test_retention
            env.update(test_retention.environment())
        bounded = (dict(timeout=host.ui_timeout(argv), kill_after=host.UI_KILL_AFTER)
                   if category == 'ui' else {})
        return control.run(command, cwd=root, env=env, **bounded)


def category_run(root, category, argv, *, pipe=True):
    import tempfile
    import test_retention
    import test_commands
    import test_launcher as host
    commands, _ = test_commands.plan(root, category, argv)
    if category in ('integration', 'system', 'e2e'):
        from vm_selection import extract
        argv, _ = extract(argv, required=False)
    env = host.environment(root)
    env['PYTHONUNBUFFERED'] = '1'
    if category in ('fixture-runtime', 'coverage'):
        env = host.test_environment(root)
        if pipe:
            env['ONPC_REGRESSION_EVENTS'] = '1'
        env['PYTHONUNBUFFERED'] = '1'
    if category == 'coverage':
        directory = test_retention.allocate(tempfile.mkdtemp, prefix='onpc-coverage-', dir='/tmp')
        command = commands[0]
        command.insert(command.index('--'), '--cov-report=xml:' + directory + '/coverage.xml')
        env['COVERAGE_FILE'] = directory + '/.coverage'
        print('run-tests: output=' + directory, flush=True)
    if category in ('fixtures', 'artifacts') and (not argv or argv in (['build'], ['prepare'])):
        directory = test_retention.allocate(tempfile.mkdtemp, prefix=f'onpc-test-{category}-', dir='/tmp')
        commands[0] += ['--output', directory]
        print('run-tests: output=' + directory, flush=True)
    elif category == 'artifacts' and argv[:2] == ['build', '--output']:
        directory = test_commands.allocate_artifact_output(argv[2])
        print('run-tests: output=' + directory, flush=True)
    if category == 'child-gjs':
        directory = test_retention.allocate(tempfile.mkdtemp, prefix='onpc-gjs-coverage-', dir='/tmp')
        for command in commands:
            command[1:1] = ['--coverage-prefix=' + str(root / 'child'),
                           '--coverage-output=' + directory]
    with Control().installed(pipe=pipe) as control:
        preparation = test_commands.qualification_artifact_command(root, category, argv)
        if preparation is not None:
            status = control.run(preparation, cwd=root, env=env)
            if status:
                return status
        if category == 'e2e' and '--list' not in argv and not any(
                value.startswith('--artifacts=') for value in commands[0]):
            from vm_selection import arguments as vm_arguments
            directory = test_retention.allocate(tempfile.mkdtemp, prefix='onpc-test-artifacts-', dir='/tmp')
            print('run-tests: output=' + directory, flush=True)
            status = control.run(test_commands.python_file(
                root, 'tools/vm_artifacts.py', '--output', directory,
                *vm_arguments()), cwd=root, env=env)
            if status:
                return status
            commands, _ = test_commands.plan(root, category, [*argv, '--artifacts=' + directory])
        for command in commands:
            privileged = command[0] == '/usr/bin/pkexec'
            if privileged:
                from dev_privileges import check
                check(command[1])
                command = [command[0], '--disable-internal-agent', '--keep-cwd', command[1],
                           '--unattended', *command[2:]]
                if category in ('system', 'e2e') and test_retention.token() is not None:
                    command.insert(4, '--retention-run=' + test_retention.token())
            status = control.run(command, cwd=root, env=env, cooperative=privileged)
            if status:
                return status
        return 0


if __name__ == '__main__':
    # The cleanup entry uses -I so caller PYTHONPATH/user-site packages cannot
    # change its imports or cause alternate cache identities between routes.
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    arguments = sys.argv[1:]
    descriptor = None
    if len(arguments) == 2 and arguments[1].startswith('--activity-fd='):
        value = arguments[1].partition('=')[2]
        if value.isdecimal() and int(value) >= 3:
            descriptor = int(value)
            arguments = arguments[:1]
    if arguments != ['--cleanup-prerequisites']:
        print('cleanup coordinator: invalid arguments', file=sys.stderr)
        sys.exit(2)
    sys.exit(cleanup_main(activity_fd=descriptor))
