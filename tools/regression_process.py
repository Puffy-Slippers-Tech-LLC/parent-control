"""Owned subprocess cancellation and streaming for unattended regression runs."""

from contextlib import contextmanager
import os
import selectors
import signal
import subprocess
import sys
import threading


# Only the detached test owner installs this event. Its nested storage and
# command controllers must observe the same terminal-independent cancellation.
session_stop = None


class Control:
    """Latch cancellation and signal only a directly spawned child's pidfd.

    Privileged dispatchers receive STOP/EOF on inherited stdin. Their parent
    waits until the child finishes its guarded cleanup, including VM restore.
    """

    def __init__(self):
        self.stopped = session_stop if session_stop is not None else threading.Event()
        self.interrupted = False

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
        if output is None:
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
            return 130 if self.stopped.is_set() else status if status >= 0 else 128 - status
        finally:
            os.close(descriptor)
            child.stdout.close()
            if child.stdin is not None:
                child.stdin.close()


def safety_command(root):
    import test_launcher as host
    targets = host.selection(root, ['tests/unit/test_*cleanup_safety.py',
                                    'tests/unit/test_graphical_lease.py'])
    return ['/usr/bin/python3', '-B', '-m', 'pytest', '-p', 'no:cacheprovider', '-v', '--', *targets]


def host_run(root, category, argv, *, pipe=True):
    import test_launcher as host
    import test_activity
    with Control().installed(pipe=pipe) as control:
        command = host.pytest_command(root, argv, category)
        env = host.test_environment(root)
        env['PYTHONUNBUFFERED'] = '1'
        if pipe:
            env['ONPC_REGRESSION_EVENTS'] = '1'
        targets = command[command.index('--') + 1:] if '--' in command else []
        cleanup = category == 'unit' and targets and all(
            target.partition('::')[0].endswith(('cleanup_safety.py', '/test_graphical_lease.py'))
            for target in targets)
        if category == 'ui' or cleanup:
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
    if category in ('fixtures', 'artifacts') and (not argv or argv == ['build']):
        directory = test_retention.allocate(tempfile.mkdtemp, prefix=f'onpc-test-{category}-', dir='/tmp')
        commands[0] += ['--output', directory]
        print('run-tests: output=' + directory, flush=True)
    if category == 'child-gjs':
        directory = test_retention.allocate(tempfile.mkdtemp, prefix='onpc-gjs-coverage-', dir='/tmp')
        for command in commands:
            command[1:1] = ['--coverage-prefix=' + str(root / 'child'),
                           '--coverage-output=' + directory]
    with Control().installed(pipe=pipe) as control:
        if category == 'e2e' and '--list' not in argv and not any(
                value.startswith('--artifacts=') for value in commands[0]):
            directory = test_retention.allocate(tempfile.mkdtemp, prefix='onpc-test-artifacts-', dir='/tmp')
            print('run-tests: output=' + directory, flush=True)
            status = control.run(test_commands.python_file(
                root, 'tools/build_test_artifacts.py', '--output', directory), cwd=root, env=env)
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
