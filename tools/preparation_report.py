"""One live preparation row and one retained transcript per selected VM."""

import base64
from contextlib import ExitStack, contextmanager, suppress
from datetime import datetime, timezone
from itertools import count
import json
import os
from pathlib import Path
import sys
import tempfile
import threading


PHASES = {
    'queued': 'Queued',
    'remote': 'Connecting to VM host',
    'compute': 'Waiting for available compute capacity',
    'vm': 'Waiting for VM to become available',
    'source': 'Waiting for checkout to become available',
    'disk': 'Waiting for available disk slot',
    'check': 'Checking VM readiness',
    'recover': 'Checking for unfinished VM work',
    'refresh-baseline': 'Refreshing the VM baseline',
    'restore': 'Restoring snapshot onpc_baseline',
    'baseline-inputs': 'Preparing baseline inputs',
    'stage-guest': 'Preparing the guest for setup',
    'configure': 'Setting up the guest',
    'reboot': 'Restarting the guest and verifying startup',
    'baseline-snapshot': 'Saving snapshot onpc_baseline',
    'build': 'Building the product package',
    'install': 'Installing the product',
    'app-snapshot': 'Saving the app snapshot',
    'resume': 'Starting the VM from the app snapshot',
    'accept': 'Waiting for baseline acceptance',
    'refresh': 'Refreshing test tools and accepting the baseline',
    'confirm': 'Confirming host completion',
}

# Reuse the maintained worker diagnostics as stage boundaries. Only reviewed
# messages can reach the terminal. The complete worker stream goes to the log.
WORKER_PHASES = {
    b'Automatic recovery: checking the recorded VM and retained evidence.': 'recover',
    (b'VM readiness: baseline preparation required; automatically refreshing '
     b'the selected baseline and app snapshots before resuming tests.'): 'refresh-baseline',
    b'Preparation: Checking the baseline and app snapshot': 'check',
    b'Preparation: Building the product package': 'build',
    b'Preparation: Starting the VM from the app snapshot': 'resume',
    b'prepare-vm: [stage:restoring-baseline]': 'restore',
    b'prepare-vm: Preparing baseline artifacts; VM is powered off': 'baseline-inputs',
    b'prepare-vm: Staging baseline setup on disk; VM is powered off': 'stage-guest',
    b'prepare-vm: Starting the VM; waiting for guest setup and shutdown': 'configure',
    b'prepare-vm: Rebooting the updated guest and verifying the new boot': 'reboot',
    b'prepare-vm: [stage:snapshot-requested]': 'baseline-snapshot',
    b'check-system: [appsnapshot: Restoring onpc_baseline]': 'restore',
    b'check-system: [appsnapshot: Installing app]': 'install',
}
PREFIX = b'ONPC_PREPARATION '
LOG_LABEL = 'Preparation logs: '


def row_priority(line):
    if line.startswith('✗ '):
        return 0
    if line.startswith(LOG_LABEL):
        return 2
    if line.startswith('✓ ') or line.endswith('] Queued'):
        return 3
    return 1


class Lines:
    def __init__(self, receive, limit, *, overflow=lambda data: None):
        self.receive = receive
        self.limit = limit
        self.overflow = overflow
        self.pending = b''
        self.skipping = False

    def __call__(self, data):
        lines = (self.pending + data).split(b'\n')
        self.pending = lines.pop()
        if self.skipping and lines:
            self.overflow(lines.pop(0) + b'\n')
            self.skipping = False
        for line in lines:
            self.receive(line + b'\n')
        if len(self.pending) > self.limit:
            self.overflow(self.pending)
            self.pending = b''
            self.skipping = True

    def finish(self):
        if self.pending:
            pending, self.pending = self.pending, b''
            (self.overflow if self.skipping else self.receive)(pending)


class Report:
    def __init__(self, tool, vms, directory=None):
        self.directory = directory
        self.stream = sys.stdout
        self.color = self.stream.isatty() and os.environ.get('TERM') != 'dumb'
        self.lock = threading.Lock()
        self.output_error = None
        self.states = dict.fromkeys((vm.name for vm in vms), 'queued')
        self.ready = ('Baseline and app snapshot ready' if tool == 'prepare-vm'
                      else 'App snapshot ready')
        self.dashboard = None
        if directory is not None and (self.color or hasattr(self.stream, 'frame')):
            from regression import Dashboard
            self.dashboard = Dashboard([], stream=self.stream)
            relative = os.path.relpath(directory)
            self.log_location = LOG_LABEL + min((relative, str(directory)), key=len)

    @contextmanager
    def writing(self):
        try:
            yield
        except OSError as error:
            # A diagnostic sink cannot decide a VM operation's outcome.
            self.output_error = error

    def announce(self):
        if self.dashboard is not None:
            self.draw()
        else:
            with self.writing():
                print(LOG_LABEL + str(self.directory), file=self.stream, flush=True)

    def finish(self):
        if self.directory is not None:
            for name in self.states:
                self.update(name, 2)  # A queue that stopped before producing a result.
            with self.writing():
                rows = self.rows(color=self.color)
                if self.dashboard is not None:
                    size = self.dashboard.terminal_size
                    self.dashboard.restore_terminal()
                    if hasattr(self.stream, 'frame'):
                        self.stream.frame([])
                    if size is not None:
                        width = max(1, size.columns - 1)
                        rows = (self.dashboard.fit(row, width) for row in rows)
                for row in rows:
                    print(row, file=self.stream)
                if self.dashboard is not None:
                    print(LOG_LABEL + str(self.directory), file=self.stream)
                self.stream.flush()
        if self.output_error is not None:
            with suppress(OSError):
                print(f'Preparation report incomplete: {self.output_error}', file=sys.stderr, flush=True)

    def rows(self, *, color):
        for name, state in self.states.items():
            if isinstance(state, str):
                yield f'[{name}] {PHASES[state]}'
                continue
            icon = '✗' if state else '✓'
            message = 'Cancelled' if state == 130 else 'Preparation failed' if state else self.ready
            line = f'{icon} [{name}] {message}'
            yield f'\033[{31 if state else 32}m{line}\033[0m' if color else line

    def draw(self):
        if self.dashboard is not None:
            with self.writing():
                self.dashboard.draw_lines([*self.rows(color=True), self.log_location], priority=row_priority)

    def log(self, name, data, *, host=None):
        if self.directory is None:
            self.send(name, 'log', base64.b64encode(data).decode('ascii'))
        else:
            filename = f'{name}.log' if name is not None else f'hosts/{host}.log'
            with self.writing(), (self.directory / filename).open('ab') as log:
                log.write(data)

    def note(self, name, message, *, host=None):
        stamp = datetime.now(timezone.utc).isoformat(timespec='seconds')
        self.log(name, f'\n[{stamp}] {message}\n'.encode(), host=host)

    def send(self, name, kind, value):
        line = PREFIX.decode() + json.dumps([name, kind, value])
        with self.lock, self.writing():
            print(line, file=self.stream, flush=True)

    def update(self, name, state):
        """A row holds a stage until its worker returns an exit status."""
        with self.lock:
            previous = self.states[name]
            if isinstance(previous, int) or previous == state:
                return
            self.states[name] = state
            self.draw()
        if self.directory is None:
            self.send(name, 'state', state)
        elif isinstance(state, int):
            self.note(name, f'Preparation exited with status {state}')

    def worker_output(self, name):
        phase = 'check'

        def stage(line):
            nonlocal phase
            line = line.rstrip(b'\r\n')
            if line == b'host-disk: queued for host disk slot':
                self.update(name, 'disk')
            elif line == b'host-disk: disk slot admitted':
                self.update(name, phase)
            else:
                next_phase = WORKER_PHASES.get(line)
                if line.startswith(b'check-system: [appsnapshot: Taking snapshot '):
                    next_phase = 'app-snapshot'
                if next_phase:
                    phase = next_phase
                    self.update(name, phase)

        lines = Lines(stage, 4096)

        def output(data):
            self.log(name, data)
            lines(data)

        return output, lines.finish

    def remote_output(self, host, names):
        def diagnostics(data):
            self.log(None, data, host=host)

        def receive(line):
            if line.startswith(PREFIX):
                try:
                    name, kind, value = json.loads(line[len(PREFIX):])
                    if kind == 'log' and (name is None or name in names):
                        self.log(name, base64.b64decode(value, validate=True), host=host)
                        return
                    if kind == 'state' and name in names and (
                            type(value) is int or isinstance(value, str) and value in PHASES):
                        # Keep the last success pending when every VM passed.
                        # The SSH command must still confirm the host's result.
                        if value == 0 and all(self.states[other] == 0 for other in names if other != name):
                            value = 'confirm'
                        self.update(name, value)
                        return
                except (TypeError, ValueError):
                    pass  # Preserve malformed records with the transport diagnostics.
            diagnostics(line)

        # A 64 KiB controller read plus encoding fits in one record.
        return Lines(receive, 128 * 1024, overflow=diagnostics)


@contextmanager
def preparation_report(root, tool, vms, *, relay=False):
    with ExitStack() as owner:
        path = None
        if not relay:
            import test_retention
            from test_storage import directory

            # Independent invocations may queue concurrently, even for the same VM.
            state = directory('state', root=root)
            allocations = directory('allocations', root=root)
            inherited = test_retention.environment()
            for slot in count():
                store = test_retention.Store(state / f'retention-{tool}-{slot}')
                try:
                    owner.enter_context(store.execution_session())
                    break
                except test_retention.OwnerBusy:
                    continue
            path = Path(test_retention.allocate(tempfile.mkdtemp, dir=allocations,
                                               prefix='onpc-prep-'))
            # Keep the journal locked. Workers keep their original ownership.
            for name in (test_retention.VARIABLE, test_retention.OWNER_VARIABLE):
                os.environ.pop(name, None)
            os.environ.update(inherited)
            (path / 'hosts').mkdir()
        report = Report(tool, vms, path)
        owner.callback(report.finish)
        if path is not None:
            report.announce()
        yield report
