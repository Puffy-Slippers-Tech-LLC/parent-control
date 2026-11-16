"""Optional UI capture lifetime owned by the private compositor fixture."""

import json
import os
from pathlib import Path
import socket
import subprocess
import sys
import tempfile
import threading
import time

from tools import test_retention, watch_control


def stop_child(child):
    """Signal only this unreaped direct Popen child, never a discovered PID."""
    if child.poll() is None:
        child.terminate()
        try:
            child.wait(timeout=5)
        except subprocess.TimeoutExpired:
            child.kill()
            child.wait(timeout=5)


class Observer:
    def __init__(self, session, *, branch='UI tests'):
        self.child = None
        self.control = None
        self.log = None
        self.services = []
        self.stop = threading.Event()
        self.lock = threading.Lock()
        self.metadata = None
        self.session, self.branch = session, branch
        self.thread = None
        self.cleanup_error = None
        runtime = Path(session.environment['XDG_RUNTIME_DIR'])
        if (runtime != Path(session.temporary_root) / 'runtime'
                or runtime.parent.parent != Path('/tmp')
                or not runtime.parent.name.startswith('dogtail-hermetic-')
                or runtime.resolve() != runtime or runtime.stat().st_uid != os.getuid()
                or session.environment['DBUS_SESSION_BUS_ADDRESS'] != session.bus_address):
            raise ValueError('UI watch requires the fixture-owned private session')
        self.runtime = runtime
        # One fixture-owned supervisor stays available for live enable, including
        # fixtures born with observation off. It never touches test input or APIs.
        self.thread = threading.Thread(target=self._follow, name='ui-watch', daemon=True)
        self.thread.start()

    def _start(self):
        root = Path(__file__).resolve().parents[2]
        runtime, session = self.runtime, self.session
        directory = Path(test_retention.allocate(
            tempfile.mkdtemp, prefix='onpc-ui-watch-', dir='/var/tmp'))
        self.log_path = directory / 'capture.log'
        print(f'UI watch diagnostics: {self.log_path}', flush=True)
        local, remote = socket.socketpair(socket.AF_UNIX, socket.SOCK_SEQPACKET)
        local.setblocking(False)
        with self.lock:
            self.control = local
        try:
            self.log = self.log_path.open('wb')
            environment = dict(session.environment, PIPEWIRE_RUNTIME_DIR=str(runtime),
                               PIPEWIRE_REMOTE='pipewire-0', PYTHONDONTWRITEBYTECODE='1',
                               ONPC_UI_WATCH_BRANCH=self.branch,
                               **watch_control.environment())
            # No host PipeWire, portal, loader or input connection is forwarded.
            for name in ('PIPEWIRE_CORE', 'PIPEWIRE_CONFIG_DIR', 'PIPEWIRE_CONFIG_NAME',
                         'PIPEWIRE_CONFIG_PREFIX', 'WIREPLUMBER_CONFIG_DIR',
                         'WIREPLUMBER_DATA_DIR', 'LD_PRELOAD', 'LD_LIBRARY_PATH'):
                environment.pop(name, None)
            if (runtime / 'pipewire-0').exists():
                raise ValueError('Refusing an unowned capture service')
            self.services.append(subprocess.Popen(
                ['pipewire'], env=environment, stdin=subprocess.DEVNULL,
                stdout=self.log, stderr=subprocess.STDOUT))
            deadline = time.monotonic() + 3
            while not (runtime / 'pipewire-0').is_socket():
                if self.services[0].poll() is not None or time.monotonic() >= deadline:
                    raise ValueError('Private PipeWire did not start; see capture.log')
                time.sleep(.02)
            self.services.append(subprocess.Popen(
                ['wireplumber', '--profile=policy'], env=environment, stdin=subprocess.DEVNULL,
                stdout=self.log, stderr=subprocess.STDOUT))
            self.child = subprocess.Popen(
                [sys.executable, '-B', str(root / 'tools/ui_watch_capture.py'),
                 str(remote.fileno())], env=environment, pass_fds=(remote.fileno(),),
                stdin=subprocess.DEVNULL, stdout=self.log, stderr=subprocess.STDOUT,
            )
        except BaseException:
            self._stop_capture()
            raise
        finally:
            remote.close()

    def _follow(self):
        attempted = False
        try:
            while not self.stop.is_set():
                enabled = watch_control.enabled('view')
                if enabled and not attempted:
                    attempted = True
                    try:
                        self._start()
                        with self.lock:
                            self._send_metadata()
                    except (OSError, ValueError) as error:
                        print(f'UI watch unavailable ({type(error).__name__}); tests continue.', flush=True)
                elif not enabled and attempted:
                    self._stop_capture()
                    attempted = False
                self.stop.wait(.25)
        except BaseException as error:
            self.cleanup_error = error
        finally:
            try:
                self._stop_capture()
            except BaseException as error:
                self.cleanup_error = error

    def update(self, nodeid, phase):
        from tools.ui_watch_transport import label
        with self.lock:
            self.metadata = {'test': label(nodeid), 'phase': label(phase, 32)}
            self._send_metadata()

    def _send_metadata(self):
        try:
            if self.metadata is not None and self.control is not None:
                self.control.send(json.dumps(self.metadata).encode())
        except (OSError, AttributeError):
            pass  # Never wait for capture or retry a test action.

    def close(self):
        self.stop.set()
        if self.thread is not None:
            self.thread.join()
            self.thread = None
        if self.cleanup_error is not None:
            raise self.cleanup_error

    def _stop_capture(self):
        with self.lock:
            if self.control is not None:
                self.control.close()  # EOF requests collector-owned cleanup.
                self.control = None
        if self.child is not None:
            try:
                self.child.wait(timeout=8)
            except subprocess.TimeoutExpired:
                stop_child(self.child)
            self.record_exit('collector', self.child)
            self.child = None
        for index, service in reversed(tuple(enumerate(self.services))):
            stop_child(service)
            self.record_exit(f'private service {index}', service)
        self.services.clear()
        if self.log is not None:
            self.log.close()
            self.log = None

    def record_exit(self, role, child):
        if self.log is not None:
            try:
                self.log.write(f'UI watch {role} exited: status={child.returncode}\n'.encode())
                self.log.flush()
            except OSError:
                pass  # Optional diagnostics must never prevent owned cleanup.


def start(session, *, branch='UI tests'):
    try:
        return Observer(session, branch=branch)
    except (OSError, ValueError) as error:
        print(f'UI watch unavailable ({type(error).__name__}); tests continue.', flush=True)
        return None
