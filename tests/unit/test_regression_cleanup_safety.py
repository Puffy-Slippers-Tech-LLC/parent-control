"""Real owned-process cancellation; unrelated sentinels must survive."""

import os
from pathlib import Path
import signal
import subprocess
import sys

import pytest

from regression_process import Control


def test_interrupt_waits_for_owned_cleanup_and_preserves_unrelated_process(tmp_path):
    child = tmp_path / 'child.py'
    child.write_text('''import signal,time
def stop(*_):
    raise KeyboardInterrupt
signal.signal(signal.SIGINT, stop)
print('ready', flush=True)
try:
    time.sleep(30)
finally:
    time.sleep(.1)
    print('cleanup complete', flush=True)
''')
    sentinel = subprocess.Popen([sys.executable, '-c', 'import time; time.sleep(30)'])
    sentinel_fd = os.pidfd_open(sentinel.pid)
    control = Control()
    output = bytearray()
    def receive(data):
        output.extend(data)
        if b'ready' in output:
            control.stop()
            control.stop()  # Repeated interrupts never abort the finally block.
    try:
        assert control.run([sys.executable, str(child)], cwd=tmp_path, env=os.environ.copy(),
                           output=receive) == 130
        assert b'cleanup complete' in output
        assert sentinel.poll() is None
    finally:
        signal.pidfd_send_signal(sentinel_fd, signal.SIGTERM)
        sentinel.wait(timeout=5)
        os.close(sentinel_fd)


def test_report_sink_failure_still_cancels_and_reaps_child(tmp_path):
    marker = tmp_path / 'cleaned'
    script = tmp_path / 'child.py'
    script.write_text(f'''import pathlib,time
try:
    print('ready', flush=True)
    time.sleep(30)
finally:
    pathlib.Path({str(marker)!r}).write_text('cleaned')
''')
    def broken(_):
        raise OSError('report disk full')
    with pytest.raises(OSError, match='disk full'):
        Control().run([sys.executable, str(script)], cwd=tmp_path, env=os.environ.copy(), output=broken)
    assert marker.read_text() == 'cleaned'


def test_cooperative_stop_reaches_nested_controller_and_waits_for_cleanup(tmp_path):
    root = Path(__file__).resolve().parents[2]
    worker = tmp_path / 'worker.py'
    worker.write_text(f'''import os,sys
sys.path.insert(0, {str(root / 'tools')!r})
from regression_process import Control
with Control().installed(pipe=True) as control:
    status = control.run([sys.executable, '-c',
        "import time; print('ready',flush=True); time.sleep(30)"],
        cwd={str(tmp_path)!r}, env=os.environ.copy())
    print('controller cleanup complete', flush=True)
    sys.exit(status)
''')
    control = Control()
    output = bytearray()
    def receive(data):
        output.extend(data)
        if b'ready' in output:
            control.stop()
    assert control.run([sys.executable, str(worker)], cwd=tmp_path, env=os.environ.copy(),
                       output=receive, cooperative=True) == 130
    assert b'controller cleanup complete' in output


def test_cancelled_controller_never_starts_another_child(tmp_path):
    control = Control()
    control.stop()
    assert control.run(['/missing/command'], cwd=tmp_path, env={}) == 130


def test_guest_command_events_arrive_before_exit_and_survive_interrupt(tmp_path):
    from owned_commands import Commands
    marker = tmp_path / 'ready'
    script = tmp_path / 'worker.py'
    script.write_text(f'''import pathlib,time
try:
    print('immediate event', flush=True)
    time.sleep(30)
finally:
    pathlib.Path({str(marker)!r}).write_text('cleaned')
''')
    calls = []
    def interrupt(data):
        calls.append(data)
        assert not marker.exists()
        raise KeyboardInterrupt
    commands = Commands()
    commands.directory = tmp_path
    commands.progress = interrupt
    with pytest.raises(KeyboardInterrupt):
        commands.run([sys.executable, str(script)])
    assert marker.read_text() == 'cleaned'
    assert (tmp_path / 'command-0001.txt').read_bytes().startswith(b'immediate event\n')
    assert calls == [b'immediate event\n']
