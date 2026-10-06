"""Host-safe regression for the UI launcher's owned-process cleanup."""

import subprocess
import signal
import os
import sys
import io
import re
import select
import threading
from contextlib import redirect_stdout
from types import SimpleNamespace
from unittest.mock import Mock

import pytest
from tests.support import preview


@pytest.mark.parametrize('cause', ['cancel', 'deadline', 'leader-exits', 'pidfd-refused'])
@pytest.mark.parametrize('stream', ['stdout', 'stderr'])
def test_ui_pipe_retirement_does_not_depend_on_another_session_exiting(
        tmp_path, monkeypatch, cause, stream):
    from regression_process import Control
    code = '''import os,signal,subprocess,sys,time
signal.signal(signal.SIGINT, signal.SIG_IGN)
signal.signal(signal.SIGTERM, signal.SIG_IGN)
subprocess.Popen([sys.executable, '-c',
    "import os,sys,time; print('holder=' + str(os.getpid()), file=sys.STREAM, flush=True); time.sleep(30)"],
    start_new_session=True)
END
'''.replace('STREAM', stream).replace('END', 'os._exit(0)' if cause == 'leader-exits'
                                     else 'time.sleep(30)')
    control, observed = Control(), bytearray()
    done, rescued = threading.Event(), threading.Event()
    pins, rescuers, children = [], [], []
    pin, popen = os.pidfd_open, subprocess.Popen

    def record(*args, **kwargs):
        child = popen(*args, **kwargs)
        children.append(child)
        return child
    monkeypatch.setattr(subprocess, 'Popen', record)

    def receive(data):
        observed.extend(data)
        match = re.search(rb'holder=(\d+)\n', observed)
        if match and not pins:
            pins.append(pin(int(match[1])))
            def rescue():
                if not done.wait(2):
                    rescued.set()
                    signal.pidfd_send_signal(pins[0], signal.SIGKILL)
            rescuers.append(threading.Thread(target=rescue))
            rescuers[0].start()
            if cause == 'cancel':
                control.stop()

    if cause == 'pidfd-refused':
        def refuse(pid):
            assert pid == children[0].pid
            # Readiness pins the holder before faulting the leader receipt.
            pipe = children[0].stdout if stream == 'stdout' else children[0].stderr
            while not pins:
                receive(os.read(pipe.fileno(), 65536))
            raise OSError('receipt refused')
        monkeypatch.setattr(os, 'pidfd_open', refuse)
    try:
        options = dict(output=receive, stderr_output=receive, timeout=.2 if cause == 'deadline' else 5,
                       kill_after=.1)
        if cause == 'pidfd-refused':
            with pytest.raises(OSError, match='receipt refused'):
                control.run([sys.executable, '-c', code], cwd=tmp_path, env=os.environ.copy(), **options)
        else:
            status = control.run([sys.executable, '-c', code], cwd=tmp_path,
                                 env=os.environ.copy(), **options)
            assert status == {'cancel': 130, 'deadline': 137, 'leader-exits': 125}[cause]
            assert b'closing its reader' in observed
        assert pins and not rescued.is_set(), 'controller required rescue to finish pipe draining'
        assert children[0].returncode is not None
        poller = select.poll()
        poller.register(pins[0], select.POLLIN)
        assert not poller.poll(0), 'controller signalled the outside-group pipe holder'
    finally:
        done.set()
        for rescuer in rescuers:
            rescuer.join(3)
        for descriptor in pins:
            try:
                signal.pidfd_send_signal(descriptor, signal.SIGKILL)
            except ProcessLookupError:
                pass
            os.close(descriptor)


def test_ui_selector_failure_still_retires_and_reaps_its_leader(tmp_path, monkeypatch):
    import regression_process
    children = []
    popen = subprocess.Popen
    def record(*args, **kwargs):
        child = popen(*args, **kwargs)
        children.append(child)
        return child
    monkeypatch.setattr(subprocess, 'Popen', record)
    selector = Mock()
    selector.__enter__ = Mock(return_value=selector)
    selector.__exit__ = Mock(return_value=False)
    selector.register.side_effect = OSError('selector refused')
    monkeypatch.setattr(regression_process.selectors, 'DefaultSelector', lambda: selector)
    with pytest.raises(OSError, match='selector refused'):
        regression_process.Control().run([sys.executable, '-c', 'import time; time.sleep(30)'],
            cwd=tmp_path, env=os.environ.copy(), output=lambda data: None, timeout=1, kill_after=.1)
    assert len(children) == 1 and children[0].returncode is not None


@pytest.mark.parametrize('fault', ['finish', 'wait'])
def test_ui_output_finalization_never_signals_an_already_reaped_group(tmp_path, monkeypatch, fault):
    import regression_process
    frames = Mock(finish=Mock(side_effect=OSError('finalization refused') if fault == 'finish' else None))
    monkeypatch.setattr(regression_process, 'PipeFrameReader', lambda output: frames)
    children = []
    popen, killpg = subprocess.Popen, os.killpg
    def record(*args, **kwargs):
        child = popen(*args, **kwargs)
        if fault == 'wait':
            wait = child.wait
            def failed_wait(*args, **kwargs):
                wait(*args, **kwargs)
                raise OSError('finalization refused')
            child.wait = failed_wait
        children.append(child)
        return child
    def signal_group(pid, sig):
        assert pid == children[0].pid and children[0].returncode is None
        killpg(pid, sig)
    monkeypatch.setattr(subprocess, 'Popen', record)
    monkeypatch.setattr(os, 'killpg', signal_group)
    with pytest.raises(OSError, match='finalization refused'):
        regression_process.Control().run([sys.executable, '-c', 'pass'],
            cwd=tmp_path, env=os.environ.copy(), timeout=1, kill_after=.1)
    assert children[0].returncode == 0


@pytest.mark.parametrize('cause', ['deadline', 'cancel', 'leader-exits', 'quiet-descendant',
                                  'pidfd-refused'])
def test_ui_timeout_reaps_an_unresponsive_worker_and_preserves_foreign_child(
        tmp_path, monkeypatch, cause):
    import test_launcher
    from regression_process import Control
    ui = tmp_path / 'tests/ui/test_stalled.py'
    ui.parent.mkdir(parents=True)
    script = '''import signal,subprocess,sys,time
def test_stalled():
    signal.signal(signal.SIGINT, signal.SIG_IGN)
    signal.signal(signal.SIGTERM, signal.SIG_IGN)
    child = subprocess.Popen([sys.executable, '-c',
        "import os,signal,time; signal.signal(signal.SIGINT, signal.SIG_IGN); "
        "signal.signal(signal.SIGTERM, signal.SIG_IGN); "
        "print('owned child ready ' + str(os.getpid()), flush=True); time.sleep(30)"],
        stdout=subprocess.PIPE, text=True)
    print(child.stdout.readline(), end='', flush=True)
    print('worker ready', flush=True)
    while True:
        time.sleep(.01)
'''
    if cause in ('leader-exits', 'quiet-descendant'):
        script = script.replace('while True:\n        time.sleep(.01)', 'import os; os._exit(0)')
    if cause == 'quiet-descendant':
        script = script.replace('stdout=subprocess.PIPE, text=True',
                                'stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, text=True')
    ui.write_text(script)
    python = tmp_path / '.venv/onpc-ui-tests/bin/python'
    python.parent.mkdir(parents=True)
    python.symlink_to(sys.executable)
    monkeypatch.setattr(test_launcher, 'UI_KILL_AFTER', .2)
    command = test_launcher.pytest_command(tmp_path,
        ['--timeout', '2s' if cause == 'deadline' else '20s', '-s', str(ui.relative_to(tmp_path))], 'ui')
    sentinel = subprocess.Popen([sys.executable, '-c', 'import time; time.sleep(30)'])
    descriptor = os.pidfd_open(sentinel.pid)
    spawned = []
    popen = subprocess.Popen
    def record(*args, **kwargs):
        child = popen(*args, **kwargs)
        spawned.append(child)
        return child
    monkeypatch.setattr(subprocess, 'Popen', record)
    control = Control()
    observed = bytearray()
    descendant = None
    pin = os.pidfd_open
    def receive(data):
        nonlocal descendant
        observed.extend(data)
        ready = re.search(rb'owned child ready ([0-9]+)\n', observed)
        if ready and descendant is None:
            descendant = pin(int(ready[1]))
        if cause == 'cancel' and descendant is not None:
            control.stop()
    try:
        def run():
            return control.run(command, cwd=tmp_path, env=os.environ.copy(), output=receive,
                               timeout=2 if cause == 'deadline' else 20, kill_after=.2)
        if cause == 'pidfd-refused':
            def refuse(pid):
                assert pid == spawned[0].pid
                # Establish the descendant's receipt and observe worker readiness
                # before faulting the controller's pidfd acquisition. The two
                # flushed readiness messages can arrive in separate pipe reads;
                # refusal cleanup closes the reader without draining later output.
                while descendant is None or b'worker ready\n' not in observed:
                    receive(os.read(spawned[0].stdout.fileno(), 65536))
                raise OSError('receipt unavailable')
            monkeypatch.setattr(os, 'pidfd_open', refuse)
            with pytest.raises(OSError, match='receipt unavailable'):
                run()
            status = 'refused'
        else:
            status = run()
        assert status == {'deadline': 137, 'cancel': 130, 'leader-exits': 125,
                          'quiet-descendant': 0, 'pidfd-refused': 'refused'}[cause], observed.decode()
        assert b'worker ready' in observed
        assert len(spawned) == 1 and spawned[0].returncode is not None
        assert sentinel.poll() is None
        assert descendant is not None
        poller = select.poll()
        poller.register(descendant, select.POLLIN)
        assert poller.poll(2000), 'owned UI descendant survived timeout group cleanup'
    finally:
        if descendant is not None:
            try:
                signal.pidfd_send_signal(descendant, signal.SIGKILL)
            except ProcessLookupError:
                pass
            os.close(descendant)
        try:
            signal.pidfd_send_signal(descriptor, signal.SIGTERM)
        except ProcessLookupError:
            pass
        sentinel.wait(timeout=5)
        os.close(descriptor)


def test_ui_timeout_handoff_enters_repair_and_completes_three_rounds(tmp_path, monkeypatch):
    import fix_tests
    import regression
    import test_launcher
    import test_retention
    ui = tmp_path / 'tests/ui/test_timeout.py'
    ui.parent.mkdir(parents=True)
    ui.write_text('''import json,signal,time
def test_timeout():
    print('ONPC-TEST-EVENT ' + json.dumps({'kind': 'collection', 'total': 1,
        'nodeids': ['tests/ui/test_timeout.py::test_timeout']}), flush=True)
    signal.signal(signal.SIGINT, signal.SIG_IGN)
    signal.signal(signal.SIGTERM, signal.SIG_IGN)
    while True:
        time.sleep(.01)
''')
    python = tmp_path / '.venv/onpc-ui-tests/bin/python'
    python.parent.mkdir(parents=True)
    python.symlink_to(sys.executable)
    monkeypatch.setattr(test_launcher, 'UI_KILL_AFTER', .2)
    preserved = Mock()
    monkeypatch.setattr(test_retention, 'preserve_for_recovery', preserved)
    attempts, repairs, rounds, reports = [], [], [], []
    output = io.StringIO()

    def execute(run):
        reports.append(run.report.directory)
        item = regression.Category('UI timeout', 1, retry_category='ui')
        run.categories[:] = [item]
        run.dashboard.stream = output
        execution = regression.Execution(run, item, events=True)
        try:
            command = test_launcher.pytest_command(tmp_path,
                ['--timeout', '2s', '-s', 'tests/ui/test_timeout.py'], 'ui')
            status = run.control.run(command, cwd=tmp_path, env=os.environ.copy(),
                                     output=execution.output, timeout=2, kill_after=.2)
            execution.finish(status)
        finally:
            execution.close()
    monkeypatch.setattr(regression.Run, 'run', execute)

    def test(category):
        assert category == 'ui'
        attempts.append(category)
        output.seek(0)
        output.truncate()
        with redirect_stdout(output):
            status = regression.retained_main(tmp_path, host_only=True)
        if not status:
            return None
        (tmp_path / 'last-test.log').write_text(output.getvalue())
        if status == 130:
            # retained_main temporarily owns pytest's signal handlers. Forward
            # an outer cancellation after owned cleanup, rather than asking
            # for a timeout-failure handoff that an interrupted run cannot have.
            raise KeyboardInterrupt('synthetic UI run interrupted')
        value = fix_tests.handoff(tmp_path)
        assert value['categories'] == ['ui']
        assert 'test infrastructure failed' in (reports[-1] / 'report.md').read_text()
        return value

    def repair(prompt, **kwargs):
        repairs.append(prompt)
        ui.write_text('''import json
def test_timeout():
    for event in ({'kind': 'collection', 'total': 1,
                   'nodeids': ['tests/ui/test_timeout.py::test_timeout']},
                  {'kind': 'finished', 'nodeid': 'tests/ui/test_timeout.py::test_timeout'}):
        print('ONPC-TEST-EVENT ' + json.dumps(event), flush=True)
''')
        return {'summary': 'repaired synthetic worker'}

    fix_tests.run_loop(['ui'], test, repair, lambda: None, selected=True, rounds=3,
                       round_changed=rounds.append)
    assert len(attempts) == 4 and len(repairs) == 1
    assert rounds == [1, 2, 3]
    preserved.assert_called_once()

    # Reproduce the outer stop arriving while the nested controller owns the
    # signal handler. Cancellation must reach pytest without starting repair.
    def interrupted(run):
        run.control.interrupt()
        execute(run)

    cancelled_handoff = Mock(wraps=fix_tests.handoff)
    monkeypatch.setattr(regression.Run, 'run', interrupted)
    monkeypatch.setattr(fix_tests, 'handoff', cancelled_handoff)
    with pytest.raises(KeyboardInterrupt, match='synthetic UI run interrupted'):
        test('ui')
    cancelled_handoff.assert_not_called()
    assert len(repairs) == 1
    preserved.assert_called_once()


def test_native_preview_crash_retains_traceback_after_owned_cleanup(tmp_path, monkeypatch):
    scripts = tmp_path / "tests" / "ui"
    scripts.mkdir(parents=True)
    script = scripts / "crash_probe.py"
    script.write_text(
        "import os, resource\n"
        "resource.setrlimit(resource.RLIMIT_CORE, (0, 0))\n"
        "def crash_preview():\n"
        "    os.abort()\n"
        "crash_preview()\n", encoding="utf-8")
    monkeypatch.setattr(preview, "ROOT", tmp_path)
    session = SimpleNamespace(environment={"PYTHONFAULTHANDLER": ""})
    with preview.preview_applications(session, tmp_path) as launch:
        process, log = launch("crash_probe")
        assert process.wait(timeout=10) == -signal.SIGABRT
    trace = log.read_text(encoding="utf-8")
    assert "Fatal Python error: Aborted" in trace
    assert str(script) in trace and "in crash_preview" in trace


@pytest.mark.parametrize("exited, stubborn", [(False, False), (False, True), (True, False)])
def test_ui_cleanup_signals_only_recorded_launches(tmp_path, monkeypatch, exited, stubborn):
    owned = Mock()
    owned.poll.return_value = 0 if exited else None
    if stubborn:
        owned.wait.side_effect = [subprocess.TimeoutExpired("preview", 5), 0]
    unrelated = Mock()
    popen = Mock(return_value=owned)
    monkeypatch.setattr(preview.subprocess, "Popen", popen)
    with preview.preview_applications(SimpleNamespace(environment={}), tmp_path) as launch:
        process, _log = launch("request_component_preview", wait_for_application=False)
        assert process is owned
    assert owned.terminate.call_count == (0 if exited else 1)
    assert owned.kill.call_count == (1 if stubborn else 0)
    assert unrelated.mock_calls == []
    assert popen.call_count == 1
    assert popen.call_args.kwargs["stdout"].closed


def test_failed_spawn_closes_its_log(tmp_path, monkeypatch):
    popen = Mock(side_effect=OSError("spawn refused"))
    monkeypatch.setattr(preview.subprocess, "Popen", popen)
    with preview.preview_applications(SimpleNamespace(environment={}), tmp_path) as launch:
        with pytest.raises(OSError, match="spawn refused"):
            launch("parent_preview")
        assert popen.call_args.kwargs["stdout"].closed


def test_failed_discovery_still_reaps_owned_preview(tmp_path, monkeypatch):
    process = Mock(poll=Mock(return_value=None))
    monkeypatch.setattr(preview.subprocess, "Popen", Mock(return_value=process))
    session = Mock(environment={})
    identify = Mock(side_effect=RuntimeError("not visible"))
    with pytest.raises(RuntimeError, match="not visible"):
        with preview.preview_applications(session, tmp_path) as launch:
            launch("parent_preview")
            identify("parent-window")
    session.wait_for_app.assert_not_called()
    process.terminate.assert_called_once()
    process.wait.assert_called_once_with(timeout=5)


def test_name_based_discovery_refuses_before_launch(tmp_path, monkeypatch):
    popen = Mock()
    monkeypatch.setattr(preview.subprocess, "Popen", popen)
    session = Mock(environment={})
    with preview.preview_applications(session, tmp_path) as launch:
        with pytest.raises(ValueError, match="public automation ID"):
            launch("parent_preview", wait_for_application=True)
    popen.assert_not_called()
    session.wait_for_app.assert_not_called()


def test_readiness_owners_include_only_live_explicit_launches(tmp_path, monkeypatch):
    process = Mock(pid=123, poll=Mock(return_value=None))
    monkeypatch.setattr(preview.subprocess, "Popen", Mock(return_value=process))
    with preview.preview_applications(SimpleNamespace(environment={}), tmp_path) as launch:
        assert launch.owner_pids() == frozenset()
        owned, log_path = launch("parent_preview")
        assert owned is process and log_path == tmp_path / "parent_preview.log"
        assert launch.owner_pids() == {123}
        process.poll.return_value = 0
        assert launch.owner_pids() == frozenset()


def test_cleanup_failure_does_not_abandon_other_owned_previews(tmp_path, monkeypatch):
    first = Mock(poll=Mock(return_value=None))
    second = Mock(poll=Mock(return_value=None), terminate=Mock(side_effect=OSError("cleanup refused")))
    popen = Mock(side_effect=[first, second])
    monkeypatch.setattr(preview.subprocess, "Popen", popen)
    with pytest.raises(BaseExceptionGroup, match="cleanup failed"):
        with preview.preview_applications(SimpleNamespace(environment={}), tmp_path) as launch:
            launch("parent_preview", wait_for_application=False)
            launch("kiosk_preview", wait_for_application=False)
    first.terminate.assert_called_once()
    first.wait.assert_called_once_with(timeout=5)
    assert all(call.kwargs["stdout"].closed for call in popen.call_args_list)


@pytest.mark.parametrize('forced', [False, True])
def test_interrupted_preview_wait_reaps_every_owner_before_cancelling(
        tmp_path, monkeypatch, forced):
    cancellation = KeyboardInterrupt('preview cleanup interrupted')
    first = Mock(poll=Mock(return_value=None))
    second = Mock(poll=Mock(return_value=None))
    second.wait.side_effect = ([subprocess.TimeoutExpired('preview', 5)] if forced else []) + [
        cancellation, 0]
    popen = Mock(side_effect=[first, second])
    monkeypatch.setattr(preview.subprocess, 'Popen', popen)
    with pytest.raises(KeyboardInterrupt) as caught:
        with preview.preview_applications(SimpleNamespace(environment={}), tmp_path) as launch:
            launch('parent_preview')
            launch('kiosk_preview')
    assert caught.value is cancellation
    second.terminate.assert_called_once()
    assert second.kill.call_count == int(forced)
    assert second.wait.call_count == 2 + int(forced)
    assert 0 <= second.wait.call_args.kwargs['timeout'] <= 5
    first.terminate.assert_called_once()
    first.wait.assert_called_once_with(timeout=5)
    assert all(call.kwargs['stdout'].closed for call in popen.call_args_list)


def test_repeated_preview_wait_interrupts_preserve_the_original_deadline(tmp_path, monkeypatch):
    cancellation = KeyboardInterrupt('first cancellation')
    process = Mock(poll=Mock(return_value=None))
    process.wait.side_effect = [cancellation, KeyboardInterrupt('second cancellation'),
                               subprocess.TimeoutExpired('preview', 0), 0]
    popen = Mock(return_value=process)
    monkeypatch.setattr(preview.subprocess, 'Popen', popen)
    monkeypatch.setattr(preview, 'time', SimpleNamespace(
        monotonic=Mock(side_effect=[100, 103, 106, 106])))
    with pytest.raises(KeyboardInterrupt) as caught:
        with preview.preview_applications(SimpleNamespace(environment={}), tmp_path) as launch:
            launch('parent_preview')
    assert caught.value is cancellation
    assert [call.kwargs['timeout'] for call in process.wait.call_args_list] == [5, 2, 0, 5]
    process.terminate.assert_called_once()
    process.kill.assert_called_once()
    assert popen.call_args.kwargs['stdout'].closed


def test_preview_cancellation_keeps_other_cleanup_failures_as_evidence(tmp_path, monkeypatch):
    cancellation = KeyboardInterrupt('preview cleanup interrupted')
    failure = OSError('cleanup refused')
    first = Mock(poll=Mock(return_value=None), terminate=Mock(side_effect=failure))
    second = Mock(poll=Mock(return_value=None))
    second.wait.side_effect = [cancellation, 0]
    popen = Mock(side_effect=[first, second])
    monkeypatch.setattr(preview.subprocess, 'Popen', popen)
    with pytest.raises(KeyboardInterrupt) as caught:
        with preview.preview_applications(SimpleNamespace(environment={}), tmp_path) as launch:
            launch('parent_preview')
            launch('kiosk_preview')
    assert caught.value is cancellation
    assert caught.value.__cause__.exceptions == (failure,)
    first.terminate.assert_called_once()
    assert second.wait.call_count == 2
    assert all(call.kwargs['stdout'].closed for call in popen.call_args_list)
