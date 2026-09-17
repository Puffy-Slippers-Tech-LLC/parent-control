"""Reconnectable test owner; terminals only observe its durable output."""

from contextlib import contextmanager
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


class SessionOutput:
    def __init__(self, run, stream):
        self.run, self.stream = run, stream

    def __getattr__(self, name):
        return getattr(self.stream, name)

    def frame(self, lines):
        temporary = self.run / 'frame.tmp'
        temporary.write_text(json.dumps(lines))
        temporary.replace(self.run / 'frame.json')


@contextmanager
def lock(path):
    fd = os.open(path, os.O_RDWR | os.O_CREAT | os.O_NOFOLLOW, 0o600)
    try:
        info = os.fstat(fd)
        if (not stat.S_ISREG(info.st_mode) or info.st_uid != os.geteuid()
                or stat.S_IMODE(info.st_mode) != 0o600 or info.st_nlink != 1):
            raise ValueError('unsafe aggregate session lock')
        yield fd
    finally:
        os.close(fd)


def busy(fd):
    try:
        fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except BlockingIOError:
        return True
    fcntl.flock(fd, fcntl.LOCK_UN)
    return False


def prepare(root):
    directory = root / 'artifacts/test-sessions'
    for parent in (directory, *directory.parents):
        if parent.is_symlink():
            raise ValueError('aggregate session path contains a symlink')
    directory.mkdir(parents=True, exist_ok=True, mode=0o700)
    info = directory.stat()
    if info.st_uid != os.geteuid() or stat.S_IMODE(info.st_mode) != 0o700:
        raise ValueError('unsafe aggregate session directory')
    return directory


def select(root, argv):
    directory = prepare(root)
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
        # Reconnection wins over all new arguments, including help and invalid
        # selections. Validate only when starting a new run, under the same gate.
        from test_commands import validate
        validate(root, argv)
        # The regular activity lock also excludes older runners and other tests.
        # Pass its actual locked descriptor, never a PID-based ownership guess.
        with test_activity.activity(root):
            run = directory / uuid.uuid4().hex
            run.mkdir(mode=0o700)
            with lock(run / 'owner') as owner, (run / 'output').open('xb') as output:
                fcntl.flock(owner, fcntl.LOCK_EX)
                command = ['/usr/bin/python3', '-u', '-B', str(Path(__file__).resolve()),
                           str(root), str(run), str(owner), *argv]
                # Publish before spawning: terminal loss immediately after
                # Popen must not leave a live worker without reconnect metadata.
                temporary = directory / 'current.tmp'
                temporary.write_text(json.dumps({'run': run.name, 'argv': argv}))
                temporary.replace(current)
                subprocess.Popen(command, cwd=root, env=test_launcher.environment(root),
                                 stdin=subprocess.DEVNULL, stdout=output, stderr=subprocess.STDOUT,
                                 start_new_session=True,
                                 pass_fds=(*test_activity.descriptors(), owner))
        return run, True


def follow(run, stream=None):
    from regression import Dashboard
    stream = stream or sys.stdout
    dashboard = Dashboard([], stream=stream)
    last_frame = None
    try:
        with (run / 'output').open(encoding='utf-8', errors='replace') as output:
            with lock(run / 'owner') as owner:
                while True:
                    active = busy(owner)
                    text = output.read()
                    if text:
                        dashboard.restore_terminal()
                        stream.write(text)
                        stream.flush()
                    if not active:
                        dashboard.restore_terminal()
                        result = run / 'result'
                        status = int(result.read_text()) if result.exists() else 1
                        if not result.exists():
                            stream.write('\nTest owner stopped without a final result; run is incomplete.\n')
                        stream.flush()
                        (run / 'delivered').touch(mode=0o600)
                        return status
                    frame = run / 'frame.json'
                    if frame.exists():
                        lines = json.loads(frame.read_text())
                        if stream.isatty() or lines != last_frame:
                            dashboard.draw_lines(lines)
                            last_frame = lines
                    time.sleep(0.2)
    finally:
        dashboard.restore_terminal()


def main(root, argv):
    run, started = select(root, argv)
    if not started:
        print('WARNING: A previous run is in the background or has an unread result; '
              'ignoring all new arguments and attaching to it.', file=sys.stderr, flush=True)
    print(f'{"Started" if started else "Attached to"} run-tests session: {run.name}',
          file=sys.stderr, flush=True)
    print('Closing this terminal detaches; invoke tools/run-tests again to attach.',
          file=sys.stderr, flush=True)
    requested = False

    def cancel(*_):
        nonlocal requested
        if not requested:
            requested = True
            (run / 'cancel').touch(mode=0o600)

    previous = signal.signal(signal.SIGINT, cancel)
    try:
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
            categories = ([kind for kind, _ in selections(root, argv)]
                          if argv and not argv[0].startswith('-') else [])
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
