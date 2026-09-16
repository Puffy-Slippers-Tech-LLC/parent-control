"""Real owned-process cancellation; unrelated sentinels must survive."""

import os
from pathlib import Path
import signal
import subprocess
import sys
import io
from types import SimpleNamespace

import pytest

from regression_process import Control
from regression_schedule import Job, run_jobs


@pytest.mark.parametrize('stage', ['Discovery', 'Cleanup prerequisites', 'Host UI',
                                  'Publishing', 'Package builds', 'Installed-system', 'E2E'])
def test_aggregate_signal_warning_precedes_cleanup_and_survives_redraw(tmp_path, monkeypatch, stage):
    import regression
    (tmp_path / 'docs/TestAutomation/Evidence/test-all-runs').mkdir(parents=True)
    script = tmp_path / 'owned.py'
    script.write_text("import sys\nprint('ready', flush=True)\n"
                      "assert sys.stdin.readline() == 'STOP\\n'\n"
                      "print('cleanup complete', flush=True)\n")
    stream = io.StringIO()
    observed = bytearray()
    notices = []

    def execute(run):
        run.dashboard.stream = stream
        item = regression.Category(stage, 1, state='Running')
        run.categories.append(item)

        def output(data):
            observed.extend(data)
            if b'ready' in data:
                signal.raise_signal(signal.SIGINT)
                signal.raise_signal(signal.SIGINT)

        def tick():
            run.dashboard.draw(force=True)
            if run.control.interrupted:
                notice = run.dashboard.render(0)[-1]
                assert notice.startswith('\033[31;1mTests interrupted.')
                assert 'please wait for cleanup to finish' in notice
                notices.append(b'cleanup complete' not in observed)

        status = run.control.run([sys.executable, str(script)], cwd=tmp_path,
                                 env=os.environ.copy(), output=output, cooperative=True, tick=tick)
        assert status == 130 and b'cleanup complete' in observed

    monkeypatch.setattr(regression.Run, 'run', execute)
    assert regression.main(tmp_path) == 130
    assert any(notices), 'warning must be visible before cleanup finishes'
    assert 'Shutdown finished; see cleanup results above.' in stream.getvalue()


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


def test_quiet_child_dashboard_failure_waits_for_cooperative_cleanup(tmp_path):
    marker = tmp_path / 'cleaned'
    script = tmp_path / 'child.py'
    script.write_text(f'''import pathlib,sys
assert sys.stdin.readline() == 'STOP\\n'
pathlib.Path({str(marker)!r}).write_text('cleaned')
''')
    def broken():
        raise OSError('terminal unavailable')
    with pytest.raises(OSError, match='terminal unavailable'):
        Control().run([sys.executable, str(script)], cwd=tmp_path, env=os.environ.copy(),
                      cooperative=True, tick=broken)
    assert marker.read_text() == 'cleaned'


def test_cancelled_controller_never_starts_another_child(tmp_path):
    control = Control()
    control.stop()
    assert control.run(['/missing/command'], cwd=tmp_path, env={}) == 130


def test_failed_pidfd_acquisition_reaps_the_spawned_child(tmp_path, monkeypatch):
    children = []
    popen = subprocess.Popen
    def record(*args, **kwargs):
        child = popen(*args, **kwargs)
        children.append(child)
        return child
    def refused(_):
        raise OSError('descriptor exhausted')
    monkeypatch.setattr(subprocess, 'Popen', record)
    monkeypatch.setattr(os, 'pidfd_open', refused)
    with pytest.raises(OSError, match='descriptor exhausted'):
        Control().run([sys.executable, '-c', 'import time; time.sleep(30)'], cwd=tmp_path, env={})
    assert len(children) == 1 and children[0].returncode is not None


@pytest.mark.parametrize('slots', [2, 3, 4])
def test_parallel_interrupt_collects_all_cleanups_without_touching_sentinel(tmp_path, slots):
    script = tmp_path / 'owned.py'
    script.write_text('''import signal,time
def stop(*_):
    raise KeyboardInterrupt
signal.signal(signal.SIGINT, stop)
try:
    print('ready', flush=True)
    time.sleep(30)
finally:
    print('cleaned', flush=True)
''')
    control = Control()
    ready, cleaned, ended = set(), set(), set()
    sentinel = subprocess.Popen([sys.executable, '-c', 'import time; time.sleep(30)'])
    sentinel_fd = os.pidfd_open(sentinel.pid)

    class Capacity:
        reason = 'worker capacity reached'

        def allows(self, candidate, active):
            return len(active) < slots

    class Execution:
        def __init__(self, job):
            self.name = job.kind
            self.data = b''

        def output(self, data):
            self.data += data
            if b'ready' in self.data:
                ready.add(self.name)
            if b'cleaned' in self.data:
                cleaned.add(self.name)
            if len(ready) == slots:
                control.stop()

        def finish(self, status):
            assert status == 130
            ended.add(self.name)

        def close(self):
            pass

    def command(argv, output):
        return control.run(argv, cwd=tmp_path, env=os.environ.copy(), output=output)

    try:
        run_jobs([Job(str(i), None, [sys.executable, str(script)]) for i in range(slots + 1)],
                 control=control, begin=Execution, run_command=command, admission=Capacity())
        assert ready == cleaned == ended == {str(i) for i in range(slots)}
        assert sentinel.poll() is None
    finally:
        signal.pidfd_send_signal(sentinel_fd, signal.SIGTERM)
        sentinel.wait(timeout=5)
        os.close(sentinel_fd)


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


def test_nested_prompt_ownership_guard_keeps_each_command_artifact_identity(tmp_path):
    from owned_commands import Commands
    commands = Commands()
    commands.directory = tmp_path
    calls = []
    def guard(data):
        calls.append(data)
        commands.progress = None
        try:
            assert commands.run(['/usr/bin/printf', 'guard-output']) == b'guard-output'
        finally:
            commands.progress = guard
    commands.progress = guard
    assert commands.run(['/usr/bin/printf', 'prompt-event']) == b'prompt-event'
    assert calls == [b'prompt-event']
    assert (tmp_path / 'command-0001.txt').read_bytes() == b'prompt-event'
    assert (tmp_path / 'command-0002.txt').read_bytes() == b'guard-output'


@pytest.mark.parametrize('boundary', ['publish', 'build-a', 'build-b', 'compare'])
def test_build_chain_cancellation_drains_companion_and_never_starts_successor(tmp_path, boundary):
    script = tmp_path / 'owned-build.py'
    script.write_text("import sys\n"
                      "print('ready', flush=True)\n"
                      "if sys.argv[1] == sys.argv[2] or sys.argv[1] == 'companion':\n"
                      "    assert sys.stdin.readline() == 'STOP\\n'\n"
                      "print('cleaned', flush=True)\n")
    keys = ['publish', 'build-a', 'build-b', 'compare']
    control = Control()
    ready, cleaned, started = set(), set(), []

    class Execution:
        def __init__(self, job):
            self.key, self.data = job.key, b''
            started.append(self.key)

        def output(self, data):
            self.data += data
            if b'ready' in self.data:
                ready.add(self.key)
            if b'cleaned' in self.data:
                cleaned.add(self.key)
            if {boundary, 'companion'} <= ready:
                control.stop()

        def finish(self, status):
            assert self.key in cleaned
            assert status == (130 if self.key in (boundary, 'companion') else 0)

        def close(self):
            pass

    jobs = [Job(key, None, [sys.executable, str(script), key, boundary], key=key,
                requires=(keys[index - 1],) if index else ()) for index, key in enumerate(keys)]
    jobs.append(Job('companion', None, [sys.executable, str(script), 'companion', boundary],
                    key='companion', estimate=100))
    run_jobs(jobs, control=control, begin=Execution,
             admission=SimpleNamespace(reason='capacity', allows=lambda _, active: len(active) < 2),
             run_command=lambda argv, output: control.run(argv, cwd=tmp_path, env=os.environ.copy(),
                                                         output=output, cooperative=True))
    assert set(started) == cleaned == {'companion', *keys[:keys.index(boundary) + 1]}
