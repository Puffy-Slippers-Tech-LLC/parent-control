"""Observer priority, output continuity and refusal without modifying runners."""

from contextlib import contextmanager
import fcntl
import json
import os
from pathlib import Path
import subprocess
from unittest.mock import Mock

import pytest

from test_storage import directory
from tests.support.terminal_screen import Terminal
from watch_output import Output, TerminalWriter, TAIL_BYTES


@contextmanager
def running(root, kind, text=b'first\n'):
    base = directory(kind, root=root)
    run = base / ('a' * 32)
    run.mkdir(mode=0o700)
    (base / 'current.json').write_text(json.dumps({'run': run.name}))
    (run / 'output').write_bytes(text)
    # Logs inherit the runner's umask inside its owner-private directory.
    (run / 'output').chmod(0o664)
    owner = base / 'owner' if kind == 'fix-tests' else run / 'owner'
    with owner.open('wb') as lock:
        owner.chmod(0o600)
        fcntl.flock(lock, fcntl.LOCK_EX)
        yield run


def test_idle_observer_does_not_create_storage(tmp_path):
    assert Output(tmp_path).poll() == ('', False, False, b'')
    assert not list(tmp_path.iterdir())


@pytest.mark.parametrize('kind', ['sessions', 'sessions-host'])
def test_follows_live_output_then_drains_and_retains_completion(tmp_path, kind):
    observer = Output(tmp_path)
    with running(tmp_path, kind) as run:
        before = sorted(run.iterdir())
        assert observer.poll() == ('run-tests', True, True, b'first\n')
        assert observer.poll() == ('run-tests', True, False, b'')
        with (run / 'output').open('ab') as stream:
            stream.write('second\n'.encode())
        assert observer.poll() == ('run-tests', True, False, b'second\n')
        assert sorted(run.iterdir()) == before
        with (run / 'output').open('ab') as stream:
            stream.write(b'finished\n')
    assert observer.poll() == ('run-tests', False, False, b'finished\n')
    assert observer.poll() == ('run-tests', False, False, b'')
    assert not (run / 'delivered').exists() and not (run / 'cancel').exists()


def test_fix_tests_has_priority_over_nested_run_tests(tmp_path):
    observer = Output(tmp_path)
    with running(tmp_path, 'sessions-host', b'tests\n'):
        assert observer.poll()[0] == 'run-tests'
        with running(tmp_path, 'fix-tests', b'repair\n'):
            assert observer.poll() == ('fix-tests', True, True, b'repair\n')
        assert observer.poll() == ('run-tests', True, True, b'tests\n')


def test_cancel_only_requests_shutdown_of_the_displayed_live_run(tmp_path):
    observer = Output(tmp_path)
    assert not observer.cancel()
    with running(tmp_path, 'sessions-host') as run:
        assert not observer.cancel()  # A newly discovered run was not displayed yet.
        observer.poll()
        assert observer.cancel()
        assert (run / 'cancel').exists()
        with running(tmp_path, 'fix-tests') as repair:
            assert not observer.cancel()  # Priority changed before the next frame.
            assert not (repair / 'cancel').exists()
            observer.poll()
            assert observer.cancel()
            assert (repair / 'cancel').exists()
    assert not observer.cancel()


def test_live_dashboard_uses_shared_rendering_without_repeating_unchanged_frames(tmp_path):
    observer = Output(tmp_path)
    with running(tmp_path, 'fix-tests') as run:
        (run / 'controller.json').write_text(json.dumps([
            dict(key='1:unit', lines=['Round 1: Category: unit (1/4)', 'Status: Running tests'])]))
        (run / 'test-controller.json').write_text(json.dumps([
            dict(key='unit', lines=['Category: unit | Overall - 50%'])]))
        frame = run / 'frame.json'
        frame.write_text(json.dumps(['Overall - 50%', '\x1b[32mRunning unit tests\x1b[0m']))
        before = {path.name: path.read_bytes() for path in run.iterdir()}
        first = observer.poll()[3]
        assert b'Round 1: Category: unit (1/4) | Overall - 50%' in first
        assert b'\x1b[32mRunning unit tests\x1b[0m' in first
        assert first.count(b'Overall - 50%') == 1
        assert observer.poll()[3] == b''
        assert {path.name: path.read_bytes() for path in run.iterdir()} == before
        frame.write_text(json.dumps(['Next case']))
        assert observer.poll()[3] == b'Next case\n'
        frame.write_text('{"invalid":"frame"}')
        assert observer.poll()[3] == b''
        frame.unlink()
        frame.symlink_to(run / 'output')
        assert observer.poll()[3] == b''


def test_dashboard_waits_for_complete_log_line(tmp_path):
    observer = Output(tmp_path)
    with running(tmp_path, 'sessions-host', b'partial \xe2') as run:
        (run / 'frame.json').write_text('["Progress"]')
        assert observer.poll()[3] == b'partial \xe2'
        assert observer.poll()[3] == b''
        with (run / 'output').open('ab') as stream:
            stream.write(b'\x9c\x93\n')
        assert observer.poll()[3] == b'\x9c\x93\nProgress\n'


def test_embedded_dashboard_replaces_ticking_frames_and_reflows(tmp_path, monkeypatch):
    screen = Terminal(width=70, height=18)
    monkeypatch.setenv('TERM', 'dumb')  # The VTE widget owns terminal capabilities.
    observer = Output(tmp_path, terminal_size=lambda: screen.size)
    with running(tmp_path, 'sessions-host') as run:
        (run / 'controller.json').write_text(json.dumps([
            dict(key='unit', lines=['Category: unit (1/1)'])]))
        for elapsed in range(6):
            (run / 'frame.json').write_text(json.dumps([
                'Unassigned host work — waiting for a branch and headroom',
                f'[Running] Unit and contracts - {elapsed}s',
                'Join host branches — waiting for host work']))
            screen.write(observer.poll()[3].decode())
            visible = screen.visible()
            assert visible.count('Category: unit') == 1
            assert visible.count('Unassigned host work') == 1
            assert visible.count('[Running] Unit and contracts') == 1
            assert f'contracts - {elapsed}s' in visible
            assert not screen.scrollback
        assert observer.poll()[3] == b''
        screen.resize(44, 12)
        screen.write(observer.poll()[3].decode())
        assert screen.visible().count('[Running] Unit and contracts') == 1
        assert 'contracts - 5s' in screen.visible()
        with (run / 'output').open('ab') as stream:
            stream.write(b'next log line\n')
        screen.write(observer.poll()[3].decode())
        assert 'next log line' in screen.visible()
    screen.write(observer.poll()[3].decode())
    assert '[Running]' not in screen.visible()
    assert 'next log line' in screen.visible()


def test_embedded_log_survives_invalid_progress_and_supports_scrollback(tmp_path):
    screen = Terminal(width=60, height=10)
    observer = Output(tmp_path, terminal_size=lambda: screen.size)
    with running(tmp_path, 'sessions-host', b'') as run:
        (run / 'frame.json').write_text('{"invalid":"frame"}')
        (run / 'output').write_bytes(b''.join(f'line {i}\n'.encode() for i in range(30)))
        screen.write(observer.poll()[3].decode())
        assert 'line 29' in screen.visible()
        observer.scroll(20)
        screen.write(observer.poll()[3].decode())
        assert 'line 5\n' in screen.visible()
        observer.scroll(-100)
        screen.write(observer.poll()[3].decode())
        assert 'line 29' in screen.visible()
        with (run / 'output').open('ab') as stream:
            stream.write(b'partial \xe2')
        screen.write(observer.poll()[3].decode())
        with (run / 'output').open('ab') as stream:
            stream.write(b'\x9c\x93\n')
        screen.write(observer.poll()[3].decode())
        assert 'partial ✓' in screen.visible()


def test_bounded_tail_truncation_and_replaced_log(tmp_path):
    observer = Output(tmp_path)
    with running(tmp_path, 'fix-tests', b'old\n' * TAIL_BYTES + b'new\n') as run:
        value = observer.poll()
        assert len(value[3]) <= TAIL_BYTES and value[3].endswith(b'new\n')
        (run / 'output').write_bytes(b'compacted\n')
        assert observer.poll() == ('fix-tests', True, True, b'compacted\n')
        (run / 'replacement').write_bytes(b'replaced\n')
        (run / 'replacement').replace(run / 'output')
        assert observer.poll() == ('fix-tests', True, True, b'replaced\n')


@pytest.mark.parametrize('bad', ['symlink', 'fifo', 'traversal', 'oversized', 'missing-owner'])
def test_invalid_publications_are_not_followed_or_repaired(tmp_path, bad):
    with running(tmp_path, 'sessions-host') as run:
        if bad == 'traversal':
            (run.parent / 'current.json').write_text('{"run":"../outside"}')
        elif bad == 'oversized':
            (run.parent / 'current.json').write_bytes(b' ' * 5000)
        elif bad == 'missing-owner':
            (run / 'owner').unlink()
        else:
            (run / 'output').unlink()
            if bad == 'fifo':
                os.mkfifo(run / 'output')
            else:
                (tmp_path / 'private').write_text('must not display')
                (run / 'output').symlink_to(tmp_path / 'private')
        assert Output(tmp_path).poll()[3] == b''
        assert not (run / 'cancel').exists()
        if bad == 'missing-owner':
            assert not (run / 'owner').exists()


def test_terminal_stream_keeps_colors_wrap_and_split_crlf_without_escape_payloads():
    terminal = Mock()
    writer = TerminalWriter(terminal)
    writer.feed(b'first\r', reset=True)
    writer.feed(b'\n\x1b[32mPASS\x1b[0m\n\x1b]52;c;')
    writer.feed(b'clipboard-secret\x07tail\n')
    assert b''.join(call.args[0] for call in terminal.feed.call_args_list) == (
        b'first\r\n\x1b[32mPASS\x1b[0m\r\ntail\r\n')
    terminal.reset.assert_called_once_with(True, True)


def test_normal_launch_returns_after_service_exec_without_waiting_for_window(monkeypatch):
    import watch_viewer as viewer
    monkeypatch.setattr(viewer.os, 'getuid', lambda: 1000)
    monkeypatch.setattr(viewer.Path, 'read_text', lambda _: 'unconfined\n')
    monkeypatch.setattr(viewer, 'run_viewer', Mock(side_effect=AssertionError('must detach')))
    launch = Mock(return_value=Mock(returncode=0))
    monkeypatch.setattr(viewer.subprocess, 'run', launch)
    assert viewer.main([]) == 0
    command = launch.call_args.args[0]
    assert '--wait' not in command and '--pipe' not in command
    assert command[-1] == '--desktop-session'


def test_detached_entry_opens_viewer_once(monkeypatch):
    import watch_viewer as viewer
    monkeypatch.setattr(viewer.os, 'getuid', lambda: 1000)
    monkeypatch.setattr(viewer.Path, 'read_text', lambda _: 'unconfined\n')
    run = Mock(return_value=0)
    monkeypatch.setattr(viewer, 'run_viewer', run)
    monkeypatch.setattr(viewer.subprocess, 'run', Mock(side_effect=AssertionError('must not recurse')))
    assert viewer.main(['--desktop-session']) == 0
    run.assert_called_once_with()


def test_make_watch_delegates_to_this_checkout_and_returns(tmp_path):
    root = tmp_path / 'worktree with spaces'
    (root / 'tools').mkdir(parents=True)
    source = Path(__file__).resolve().parents[2]
    (root / 'Makefile').write_bytes((source / 'Makefile').read_bytes())
    launcher = root / 'tools/watch'
    launcher.write_text('#!/bin/sh\nprintf "watcher launched\\n"\n')
    launcher.chmod(0o755)
    result = subprocess.run(['make', '--no-print-directory', 'watch'], cwd=root,
                            capture_output=True, text=True, timeout=5)
    assert result.returncode == 0, result.stderr
    assert result.stdout == 'watcher launched\n'
