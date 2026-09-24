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

import test_activity
import test_launcher


from detached_launcher import FRAME_DIRECTORY, lock, busy


class SessionOutput:
    def __init__(self, run, stream):
        self.run, self.stream = run, stream

    def __getattr__(self, name):
        return getattr(self.stream, name)

    def frame(self, lines):
        temporary = self.run / 'frame.tmp'
        temporary.write_text(json.dumps(lines))
        temporary.replace(self.run / 'frame.json')

    def controller(self, key, lines):
        from launcher_progress import publish_progress
        publish_progress(self.run, key, lines)


def prepare(root, *, host_only=False):
    from test_storage import directory as storage_directory
    directory = storage_directory('sessions-host' if host_only else 'sessions', root=root)
    for parent in (directory, *directory.parents):
        if parent.is_symlink():
            raise ValueError('aggregate session path contains a symlink')
    directory.mkdir(parents=True, exist_ok=True, mode=0o700)
    info = directory.stat()
    if info.st_uid != os.geteuid() or stat.S_IMODE(info.st_mode) != 0o700:
        raise ValueError('unsafe aggregate session directory')
    return directory


def select(root, argv):
    from test_commands import host_only_request, is_inspection, validate
    # Inspection never attaches, waits for locks, or consumes an unread result.
    if is_inspection(argv):
        return None, False
    requested = list(argv) or ['all']
    host_only = host_only_request(requested)
    directory = prepare(root, host_only=host_only)
    with lock(directory / 'gate') as gate:
        fcntl.flock(gate, fcntl.LOCK_EX)
        current = directory / 'current.json'
        if current.exists():
            record = json.loads(current.read_text())
            name = record['run']
            if len(name) != 32 or any(c not in '0123456789abcdef' for c in name):
                raise ValueError('invalid aggregate session identity')
            run = directory / name
            with lock(run / 'owner') as owner:
                active = busy(owner)
            result = run / 'result'
            try:
                broken = not result.exists() or int(result.read_text()) != 0
            except (ValueError, OSError):
                broken = True
            if active or (not (run / 'delivered').exists() and (not argv or not broken)):
                return run, False
            if broken and not (run / 'delivered').exists():
                print(f'Previous test owner is idle; preserving its incomplete/failed output in {run}.',
                      file=sys.stderr, flush=True)
        # Reconnection wins over new execution arguments, including invalid
        # selections. Validate only when starting a new run, under the same gate.
        # Idle invocations with no arguments start the complete aggregate.
        validate(root, requested)
        # Keep host-only ownership independent of standalone VM preparation.
        # Pass its actual locked descriptor, never a PID-based ownership guess.
        with test_activity.activity(root, host_only=host_only):
            run = directory / uuid.uuid4().hex
            run.mkdir(mode=0o700)
            import test_retention
            with test_retention.Store(directory / 'retention').session():
                test_retention.retain(run)
            with lock(run / 'owner') as owner, (run / 'output').open('xb') as output:
                fcntl.flock(owner, fcntl.LOCK_EX)
                command = ['/usr/bin/python3', '-u', '-B', str(Path(__file__).resolve()),
                           str(root), str(run), str(owner), *requested]
                # Publish before spawning: terminal loss immediately after
                # Popen must not leave a live worker without reconnect metadata.
                temporary = directory / 'current.tmp'
                temporary.write_text(json.dumps({'run': run.name, 'argv': requested}))
                temporary.replace(current)
                from test_storage import scratch_descriptors
                from detached_launcher import nested_operation, WORKFLOW_DIRECTORY
                environment = test_launcher.environment(root)
                # Registration belongs to this public invocation. Test fixtures
                # and further runner workers must not claim the agent's owner.
                environment.pop(WORKFLOW_DIRECTORY, None)
                with nested_operation(root, run):
                    subprocess.Popen(command, cwd=root, env=environment,
                                     stdin=subprocess.DEVNULL, stdout=output, stderr=subprocess.STDOUT,
                                     start_new_session=True,
                                     pass_fds=(*test_activity.descriptors(), owner, *scratch_descriptors()))
        return run, True


def follow(run, stream=None):
    from detached_launcher import follow_output, atomic
    from launcher_render import LauncherDisplay
    stream = stream or sys.stdout
    # A supervising fix-tests process retains frames separately from its log.
    # Only the final observer knows whether (and how large) its terminal is.
    destination = os.environ.get(FRAME_DIRECTORY)
    display = LauncherDisplay(stream)
    try:
        return follow_output(run, stream, display, label='run-tests',
                             test_session=True, destination=Path(destination) if destination else None,
                             owner_busy=lambda owner: busy(owner))
    finally:
        display.close()
        if destination:
            atomic(Path(destination) / 'frame.json', [])


def main(root, argv):
    run = None
    requested = False

    def cancel(*_):
        nonlocal requested
        requested = True
        if run is not None:
            (run / 'cancel').touch(mode=0o600)

    previous = signal.signal(signal.SIGINT, cancel)
    try:
        run, started = select(root, argv)
        if run is None:
            from test_commands import _main
            return _main(argv)
        if requested:
            cancel()
        if not started:
            print('WARNING: A previous run is in the background or has an unread result; '
                  'ignoring all new arguments and attaching to it.', file=sys.stderr, flush=True)
        # Install cancellation before advertising readiness to a supervisor.
        print(f'{"Started" if started else "Attached to"} run-tests session: {run.name}',
              file=sys.stderr, flush=True)
        print('Closing this terminal detaches; invoke tools/run-tests again to attach.',
              file=sys.stderr, flush=True)
        return follow(run)
    finally:
        signal.signal(signal.SIGINT, previous)


def worker(root, argv, run, owner):
    # setsid in Popen disconnects the controlling terminal before this exec.
    signal.signal(signal.SIGHUP, signal.SIG_IGN)
    import regression_process
    regression_process.session_stop = threading.Event()
    finished = threading.Event()

    def cancellation():
        while not finished.wait(0.1):
            if (run / 'cancel').exists():
                regression_process.session_stop.set()
                return

    watcher = threading.Thread(target=cancellation, daemon=True)
    watcher.start()
    status = 1
    original = sys.stdout
    sys.stdout = SessionOutput(run, original)
    try:
        from test_commands import _main, selections
        with test_activity.activity(root):
            from test_recovery import before_run
            categories = [kind for kind, _ in selections(root, argv)] if argv else []
            sys.stdout.controller('preparing', [
                f'Category: {categories[0] if categories else "all"} (1/{len(categories) or 1}) | Preparing tests'])
            before_run(root, argv, categories=categories)
            status = _main(argv, detached=True)
    finally:
        finished.set()
        watcher.join()
        sys.stdout.flush()
        sys.stderr.flush()
        sys.stdout = original
        os.close(int(os.environ[test_activity.VARIABLE]))
        (run / 'result').write_text(str(status))
        os.close(owner)
    return status


if __name__ == '__main__':
    sys.exit(worker(Path(sys.argv[1]), sys.argv[4:], Path(sys.argv[2]), int(sys.argv[3])))
