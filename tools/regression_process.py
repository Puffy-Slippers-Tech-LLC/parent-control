"""Owned subprocess cancellation and streaming for unattended regression runs."""

from contextlib import contextmanager
import os
import selectors
import signal
import subprocess
import sys
import threading


class Control:
    """Latch cancellation and signal only a directly spawned child's pidfd.

    Privileged dispatchers receive STOP/EOF on inherited stdin. Their parent
    waits until the child finishes its guarded cleanup, including VM restore.
    """

    def __init__(self):
        self.stopped = threading.Event()

    def stop(self, *_):
        self.stopped.set()

    @contextmanager
    def installed(self, *, pipe=False):
        previous = {sig: signal.signal(sig, self.stop)
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

    def run(self, command, *, cwd, env, output=None, cooperative=False, **kwargs):
        if self.stopped.is_set():
            return 130
        if output is None:
            def output(data):
                sys.stdout.buffer.write(data)
                sys.stdout.buffer.flush()
        child = subprocess.Popen(command, cwd=cwd, env=env,
                                 stdin=subprocess.PIPE if cooperative else subprocess.DEVNULL,
                                 stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                                 start_new_session=True, **kwargs)
        descriptor = os.pidfd_open(child.pid)
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
    return ['/usr/bin/python3', '-B', '-m', 'pytest', '-p', 'no:cacheprovider', '-q', '--', *targets]


def host_run(root, category, argv):
    import test_launcher as host
    with Control().installed(pipe=True) as control:
        command = host.pytest_command(root, argv, category)
        env = host.environment(root)
        env.update(ONPC_REGRESSION_EVENTS='1', PYTHONUNBUFFERED='1')
        if category != 'unit' and '--collect-only' not in command:
            status = control.run(safety_command(root), cwd=root, env=host.environment(root))
            if status:
                return status
        return control.run(command, cwd=root, env=env)


def category_run(root, category, argv):
    import tempfile
    import test_commands
    import test_launcher as host
    commands, safety = test_commands.plan(root, category, argv)
    env = host.environment(root)
    env['PYTHONUNBUFFERED'] = '1'
    if category == 'fixture-runtime':
        env['ONPC_REGRESSION_EVENTS'] = '1'
    if category in ('fixtures', 'artifacts') and (not argv or argv == ['build']):
        directory = tempfile.mkdtemp(prefix=f'onpc-test-{category}-', dir='/tmp')
        commands[0] += ['--output', directory]
        print('run-tests: output=' + directory, flush=True)
    if category == 'child-gjs':
        directory = tempfile.mkdtemp(prefix='onpc-gjs-coverage-', dir='/tmp')
        for command in commands:
            command[1:1] = ['--coverage-prefix=' + str(root / 'child'),
                           '--coverage-output=' + directory]
    with Control().installed(pipe=True) as control:
        if safety:
            status = control.run(safety_command(root), cwd=root, env=host.environment(root))
            if status:
                return status
        for command in commands:
            privileged = command[0] == '/usr/bin/pkexec'
            if privileged:
                from dev_privileges import check
                check(command[1])
                command = [command[0], '--disable-internal-agent', command[1],
                           '--unattended', *command[2:]]
            status = control.run(command, cwd=root, env=env, cooperative=privileged)
            if status:
                return status
        return 0
