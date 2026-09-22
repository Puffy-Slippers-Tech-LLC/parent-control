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

    def run(self, command, *, cwd, env, output=None, cooperative=False, tick=None, **kwargs):
        # The installed dispatcher loads this file before adding the validated
        # checkout tools directory for its deferred imports.
        import test_activity
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
        kwargs.setdefault('pass_fds', test_activity.descriptors())
        child = subprocess.Popen(command, cwd=cwd, env=env,
                                 stdin=subprocess.PIPE if cooperative else subprocess.DEVNULL,
                                 stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
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
                child.send_signal(signal.SIGINT)
            child.communicate()
            raise
        sent = False
        output_error = None
        try:
            with selectors.DefaultSelector() as poller:
                poller.register(child.stdout, selectors.EVENT_READ)
                while poller.get_map() or child.poll() is None:
                    if self.stopped.is_set() and not sent:
                        sent = True
                        if cooperative:
                            try:
                                child.stdin.write(b'STOP\n')
                                child.stdin.flush()
                            except BrokenPipeError:
                                pass
                        else:
                            try:
                                signal.pidfd_send_signal(descriptor, signal.SIGINT)
                            except ProcessLookupError:
                                pass
                    for key, _ in poller.select(0.1):
                        data = os.read(key.fd, 65536)
                        if not data:
                            poller.unregister(key.fileobj)
                        elif output_error is None:
                            try:
                                output(data)
                            except BaseException as error:
                                output_error = error
                                self.stop()
                    if tick is not None and output_error is None:
                        try:
                            tick()
                        except BaseException as error:
                            output_error = error
                            self.stop()
                status = child.wait()
            if output_error is not None:
                raise output_error
            if frames is not None:
                frames.finish()
            return 130 if self.stopped.is_set() else status if status >= 0 else 128 - status
        finally:
            os.close(descriptor)
            child.stdout.close()
            if child.stdin is not None:
                child.stdin.close()


def safety_command(root):
    """Run the shared cleanup gate coordinator as the unprivileged caller."""
    import test_activity
    descriptors = test_activity.descriptors()
    inherited = ([] if not descriptors else ['--activity-fd=' + str(descriptors[0])])
    return ['/usr/bin/python3', '-B', str(root / 'tools/regression_process.py'),
            '--cleanup-prerequisites', *inherited]


def cleanup_main(root=None, *, activity_fd=None):
    """Give privileged dispatchers the aggregate's parallel cleanup gate."""
    import regression
    import test_activity
    from regression_selection import CLEANUP_SELECTION
    root = root or Path(__file__).resolve().parents[1]
    # VM selections own the VM activity lock. Cleanup workers use the separate
    # host lock, then inherit it through the ordinary aggregate commands. A
    # host launcher can instead pass its already-owned descriptor explicitly.
    previous = os.environ.get(test_activity.VARIABLE)
    if activity_fd is not None:
        os.environ[test_activity.VARIABLE] = str(activity_fd)
    output = sys.stdout
    sys.stdout = PipeFrameOutput(output)
    try:
        with test_activity.activity(root, host_only=True if activity_fd is None else None):
            from e2e_startup_cache import qualified_cleanup
            return qualified_cleanup(root, lambda: regression.retained_main(
                root, selections=[(CLEANUP_SELECTION, [])]))
    finally:
        sys.stdout = output
        if previous is None:
            os.environ.pop(test_activity.VARIABLE, None)
        else:
            os.environ[test_activity.VARIABLE] = previous


def host_run(root, category, argv, *, pipe=True):
    import test_launcher as host
    import test_activity
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
        if category != 'unit' and '--collect-only' not in command:
            if test_activity.cleanup_verified(root):
                print('run-tests: reusing passed aggregate cleanup prerequisites; source verified',
                      flush=True)
            else:
                status = control.run(safety_command(root), cwd=root, env=host.test_environment(root))
                if status:
                    return status
        return control.run(command, cwd=root, env=env)


def category_run(root, category, argv, *, pipe=True):
    import tempfile
    import test_retention
    import test_commands
    import test_launcher as host
    import test_activity
    commands, safety = test_commands.plan(root, category, argv)
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
            directory = test_retention.allocate(tempfile.mkdtemp, prefix='onpc-test-artifacts-', dir='/tmp')
            print('run-tests: output=' + directory, flush=True)
            status = control.run(test_commands.python_file(
                root, 'tools/build_test_artifacts.py', '--reuse', '--output', directory), cwd=root, env=env)
            if status:
                return status
            commands, safety = test_commands.plan(root, category, [*argv, '--artifacts=' + directory])
        if safety:
            if category == 'fixture-runtime' and test_activity.cleanup_verified(root):
                print('run-tests: reusing passed aggregate cleanup prerequisites; source verified',
                      flush=True)
            else:
                status = control.run(safety_command(root), cwd=root, env=host.test_environment(root))
                if status:
                    return status
        for command in commands:
            privileged = command[0] == '/usr/bin/pkexec'
            if privileged:
                from dev_privileges import check
                check(command[1])
                command = [command[0], '--disable-internal-agent', command[1],
                           '--unattended', *command[2:]]
                if category in ('system', 'e2e') and test_retention.token() is not None:
                    command.insert(3, '--retention-run=' + test_retention.token())
            status = control.run(command, cwd=root, env=env, cooperative=privileged)
            if status:
                return status
        return 0


if __name__ == '__main__':
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
