"""Optional UI capture lifetime owned by the private compositor fixture."""

import json
import os
from pathlib import Path
import socket
import subprocess
import sys
import tempfile
import time

from tools import test_retention


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
        root = Path(__file__).resolve().parents[2]
        runtime = Path(session.environment['XDG_RUNTIME_DIR'])
        if (runtime != Path(session.temporary_root) / 'runtime'
                or runtime.parent.parent != Path('/tmp')
                or not runtime.parent.name.startswith('dogtail-hermetic-')
                or runtime.resolve() != runtime or runtime.stat().st_uid != os.getuid()
                or session.environment['DBUS_SESSION_BUS_ADDRESS'] != session.bus_address):
            raise ValueError('UI watch requires the fixture-owned private session')
        directory = Path(test_retention.allocate(
            tempfile.mkdtemp, prefix='onpc-ui-watch-', dir='/var/tmp'))
        self.log_path = directory / 'capture.log'
        print(f'UI watch diagnostics: {self.log_path}', flush=True)
        local, remote = socket.socketpair(socket.AF_UNIX, socket.SOCK_SEQPACKET)
        self.control = local
        self.control.setblocking(False)
        try:
            self.log = self.log_path.open('wb')
            environment = dict(session.environment, PIPEWIRE_RUNTIME_DIR=str(runtime),
                               PIPEWIRE_REMOTE='pipewire-0', PYTHONDONTWRITEBYTECODE='1',
                               ONPC_UI_WATCH_BRANCH=branch)
            # No host PipeWire, portal, loader or input connection is forwarded.
            for name in ('PIPEWIRE_CORE', 'PIPEWIRE_CONFIG_DIR', 'PIPEWIRE_CONFIG_NAME',
                         'PIPEWIRE_CONFIG_PREFIX', 'WIREPLUMBER_CONFIG_DIR',
                         'WIREPLUMBER_DATA_DIR', 'LD_PRELOAD', 'LD_LIBRARY_PATH'):
                environment.pop(name, None)
            if (runtime / 'pipewire-0').exists():
                raise ValueError('Refusing an unowned capture service')
            self.services.append(subprocess.Popen(
                ['pipewire'], env=environment, stdin=subprocess.DEVNULL,
                stdout=self.log, stderr=subprocess.STDOUT, start_new_session=True))
            deadline = time.monotonic() + 3
            while not (runtime / 'pipewire-0').is_socket():
                if self.services[0].poll() is not None or time.monotonic() >= deadline:
                    raise ValueError('Private PipeWire did not start; see capture.log')
                time.sleep(.02)
            self.services.append(subprocess.Popen(
                ['wireplumber', '--profile=policy'], env=environment, stdin=subprocess.DEVNULL,
                stdout=self.log, stderr=subprocess.STDOUT, start_new_session=True))
            self.child = subprocess.Popen(
                [sys.executable, '-B', str(root / 'tools/ui_watch_capture.py'),
                 str(remote.fileno())], env=environment, pass_fds=(remote.fileno(),),
                stdin=subprocess.DEVNULL, stdout=self.log, stderr=subprocess.STDOUT,
                start_new_session=True,
            )
        except BaseException:
            self.close()
            raise
        finally:
            remote.close()

    def update(self, nodeid, phase):
        from tools.ui_watch_transport import label
        try:
            self.control.send(json.dumps({'test': label(nodeid), 'phase': label(phase, 32)}).encode())
        except (OSError, AttributeError):
            pass  # Never wait for capture or retry a test action.

    def close(self):
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
