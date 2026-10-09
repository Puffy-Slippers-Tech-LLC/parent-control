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
from watch_output import Output, TerminalWriter, TAIL_BYTES, JsonReader
from watch_viewer import viewer_entries


def test_viewer_vm_ids_are_numeric_and_duplicate_checkouts_follow_the_controller():
    entries = {
        ('main', 'ui-first'): ('ui', 'UI first', True, True),
        ('main', 'vm-ten'): ('idle ten', 'Ten', False, False),
        ('main', 'vm-two'): ('unlocked two', 'Two', True, False),
        ('main', 'vm-legacy'): ('legacy', 'Legacy', True, True),
        ('worktree', 'ui-second'): ('ui', 'UI second', True, True),
        ('worktree', 'vm-ten'): ('active ten', 'Ten', True, True),
        ('worktree', 'vm-two'): ('controller two', 'Two', True, True),
    }
    ids = {entry: ('10' if entry[1] == 'vm-ten' else 2)
           for entry in entries if entry[1] in ('vm-ten', 'vm-two')}
    selected = viewer_entries(entries, vm_ids=ids)
    assert list(selected) == [('main', 'ui-first'), ('worktree', 'ui-second'),
                             ('worktree', 'vm-two'), ('worktree', 'vm-ten'),
                             ('main', 'vm-legacy')]
    assert selected['worktree', 'vm-two'][0] == 'controller two'
    assert list(viewer_entries(entries, scope='main', vm_ids=ids)) == [
        ('main', 'ui-first'), ('main', 'vm-two'), ('main', 'vm-ten'), ('main', 'vm-legacy')]
    entries['worktree', 'vm-two'] = ('idle two', 'Two', False, False)
    selected = viewer_entries(entries, vm_ids=ids)
    assert selected['main', 'vm-two'][0] == 'unlocked two'
    assert ('worktree', 'vm-two') not in selected


def test_viewer_legacy_vm_order_is_stable_when_all_sources_are_idle():
    entries = {('worktree', 'vm-z'): ('z', 'Z', False, False),
               ('main', 'vm-a'): ('a', 'A', False, False),
               ('main', 'vm-z'): ('duplicate z', 'Z', False, False)}
    assert list(viewer_entries(entries)) == [('worktree', 'vm-z'), ('main', 'vm-a')]


def test_combined_view_omits_idle_retired_worktree_vm_but_keeps_live_controllers():
    entries = {('main', 'vm-new'): ('new', 'Renamed-VM', False, False),
               ('worktree', 'vm-old'): ('old', 'Retired-VM', False, False)}
    assert list(viewer_entries(entries, current_vms={'vm-new'})) == [('main', 'vm-new')]
    assert list(viewer_entries(entries, scope='worktree', current_vms={'vm-new'})) == [('worktree', 'vm-old')]
    entries['worktree', 'vm-old'] = ('live', 'Retired-VM', True, True)
    assert list(viewer_entries(entries, current_vms={'vm-new'})) == [('main', 'vm-new'), ('worktree', 'vm-old')]


@contextmanager
def running(root, kind, text=b'first\n'):
    base = directory(kind, root=root)
    run = base / ('a' * 32)
    run.mkdir(mode=0o700)
    (base / 'current.json').write_text(json.dumps({'run': run.name}))
    (run / 'output').write_bytes(text)
    # Logs inherit the runner's umask inside its owner-private directory.
    (run / 'output').chmod(0o664)
    owner = base / 'owner' if kind in ('fix-tests', 'fix-tests-host') else run / 'owner'
    with owner.open('wb') as lock:
        owner.chmod(0o600)
        fcntl.flock(lock, fcntl.LOCK_EX)
        yield run


def test_idle_observer_does_not_create_storage(tmp_path):
    assert Output(tmp_path).poll() == ('', False, False, b'')
    assert not list(tmp_path.iterdir())


def test_unchanged_json_skips_payload_reads_and_cached_values_stay_private(tmp_path, monkeypatch):
    import watch_output
    reader = JsonReader()
    path = tmp_path / 'frame.json'
    path.write_text('[{"lines":["original"]}]')
    original = watch_output.open_private
    reads = []

    @contextmanager
    def tracked(path):
        with original(path) as stream:
            proxy = Mock(wraps=stream)
            proxy.read.side_effect = lambda count: reads.append(count) or stream.read(count)
            yield proxy

    monkeypatch.setattr(watch_output, 'open_private', tracked)
    reader.read(path)[0]['lines'][0] = 'display-only change'
    for _ in range(20):
        assert reader.read(path) == [{'lines': ['original']}]
    assert len(reads) == 1
    path.write_text('[{"lines":["modified"]}]')
    assert reader.read(path) == [{'lines': ['modified']}]
    replacement = tmp_path / 'replacement'
    replacement.write_text('[{"lines":["replaced"]}]')
    replacement.replace(path)
    assert reader.read(path) == [{'lines': ['replaced']}]
    assert len(reads) == 3
    path.unlink()
    with pytest.raises(FileNotFoundError):
        reader.read(path)
    path.symlink_to(replacement)
    with pytest.raises(ValueError, match='symlink'):
        reader.read(path)


@pytest.mark.parametrize('replacement', ['hardlink', 'oversized', 'invalid'])
def test_cached_json_still_refuses_changed_unsafe_or_invalid_files(tmp_path, replacement):
    path = tmp_path / 'frame.json'
    path.write_text('["safe"]')
    reader = JsonReader()
    assert reader.read(path) == ['safe']
    if replacement == 'hardlink':
        os.link(path, tmp_path / 'alias')
    else:
        path.write_text(' ' * 65537 if replacement == 'oversized' else '{')
    with pytest.raises(ValueError):
        reader.read(path)


def test_cached_json_rechecks_limits_and_same_size_edits_with_restored_mtime(tmp_path):
    path = tmp_path / 'frame.json'
    path.write_text('["first"]')
    reader = JsonReader()
    assert reader.read(path) == ['first']
    before = path.stat()
    with pytest.raises(ValueError, match='oversized'):
        reader.read(path, limit=4)
    path.write_text('["other"]')
    os.utime(path, ns=(before.st_atime_ns, before.st_mtime_ns))
    assert reader.read(path) == ['other']


def test_checkout_discovery_reads_branches_spaces_and_detached_worktrees(tmp_path):
    from watch_checkouts import worktrees, checkout, identity
    root = tmp_path / 'main checkout'
    other = tmp_path / 'worktree checkout'
    for path in (root, other):
        (path / 'tools').mkdir(parents=True)
        (path / 'tools/watch').touch()
    environment = {**os.environ, 'GIT_CONFIG_GLOBAL': '/dev/null',
                   'GIT_CONFIG_SYSTEM': '/dev/null'}
    def git(*arguments):
        return subprocess.run(['git', '-C', str(root), *arguments], env=environment,
                              check=True, capture_output=True, timeout=5)
    git('init', '-b', 'main')
    git('-c', 'user.name=Fixture', '-c', 'user.email=fixture@example.invalid',
        'commit', '--allow-empty', '-m', 'Fixture')
    # The other fixture marker exists outside Git's tracked payload.
    other.rename(tmp_path / 'markers')
    git('worktree', 'add', '-b', 'worktree', str(other))
    (other / 'tools').mkdir()
    (other / 'tools/watch').touch()
    assert worktrees(root) == {root: 'main', other: 'worktree'}
    git('-C', str(other), 'checkout', '--detach')
    discovered = worktrees(other)
    assert discovered[root] == 'main' and discovered[other].startswith('detached ')
    link = tmp_path / 'alias'
    link.symlink_to(root, target_is_directory=True)
    with pytest.raises(ValueError, match='invalid checkout'):
        checkout(link)
    assert identity(root) != identity(other)


def test_checkout_discovery_is_bounded_off_the_renderer_and_stops(tmp_path, monkeypatch):
    import threading
    import time
    import watch_checkouts as watcher
    root = tmp_path / 'checkout'
    (root / 'tools').mkdir(parents=True)
    (root / 'tools/watch').touch()
    (root / '.git').mkdir()
    entered, release = threading.Event(), threading.Event()
    def inspect(path):
        assert path == root
        entered.set()
        assert release.wait(2)
        return {root: 'main'}
    monkeypatch.setattr(watcher, 'worktrees', inspect)
    discovery = watcher.Discovery(root)
    try:
        assert entered.wait(2)
        assert discovery.poll() is None
        release.set()
        deadline = time.monotonic() + 2
        result = None
        while result is None and time.monotonic() < deadline:
            result = discovery.poll()
            time.sleep(.005)
        assert result == {root: 'main'}
        assert discovery.updates.maxsize == 1
    finally:
        release.set()
        discovery.close()
        discovery.thread.join(3)
    assert not discovery.thread.is_alive()


def test_checkout_discovery_refreshes_vm_names_and_ids_off_the_renderer(tmp_path, monkeypatch):
    import threading
    import time
    import watch_checkouts as watcher
    root = tmp_path / 'checkout'
    (root / 'tools').mkdir(parents=True)
    (root / 'tools/watch').touch()
    (root / '.git').mkdir()
    (root / 'config').mkdir()
    config = root / 'config/test-vm.json'
    def write(name, identifier):
        config.write_text(json.dumps({'vms': [{'name': name, 'id': identifier,
                                             'disk_anchor': '/unused/disk.qcow2'}]}))
    write('Old-VM', '2')
    monkeypatch.setattr(watcher, 'worktrees', lambda _: {root: 'main'})
    discovery = watcher.Discovery(root)
    def wait_for(name):
        deadline = time.monotonic() + 3
        while time.monotonic() < deadline:
            values = discovery.poll_vms()
            if values is not None and set(values[root]) == {name}:
                return values[root][name]
            time.sleep(.01)
        pytest.fail('registry refresh did not reach the current VM name')
    try:
        assert wait_for('Old-VM').id == '2'
        write('New-VM', '7')
        assert wait_for('New-VM').id == '7'
        assert discovery.vm_updates.maxsize == 1
    finally:
        discovery.close()
        discovery.thread.join(3)
    assert not discovery.thread.is_alive()


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


@pytest.mark.parametrize('kind', ['fix-tests', 'fix-tests-host'])
def test_fix_tests_has_priority_over_nested_run_tests(tmp_path, kind):
    observer = Output(tmp_path)
    with running(tmp_path, 'sessions-host', b'tests\n'):
        assert observer.poll()[0] == 'run-tests'
        with running(tmp_path, kind, b'repair\n'):
            assert observer.poll() == ('fix-tests', True, True, b'repair\n')
        assert observer.poll() == ('run-tests', True, True, b'tests\n')


@pytest.mark.parametrize('kind', ['fix-tests', 'fix-tests-host'])
def test_cancel_only_requests_shutdown_of_the_displayed_live_run(tmp_path, kind):
    observer = Output(tmp_path)
    assert not observer.cancel()
    with running(tmp_path, 'sessions-host') as run:
        assert not observer.cancel()  # A newly discovered run was not displayed yet.
        observer.poll()
        assert observer.cancel()
        assert (run / 'cancel').exists()
        with running(tmp_path, kind) as repair:
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
    import vm_selection
    monkeypatch.setattr(vm_selection, 'registry', Mock(return_value={'first': Mock(), 'second': Mock()}))
    monkeypatch.setattr(viewer.os, 'getuid', lambda: 1000)
    monkeypatch.setattr(viewer.Path, 'read_text', lambda _: 'unconfined\n')
    monkeypatch.setattr(viewer, 'run_viewer', Mock(side_effect=AssertionError('must detach')))
    launch = Mock(return_value=Mock(returncode=0))
    monkeypatch.setattr(viewer.subprocess, 'run', launch)
    assert viewer.main([]) == 0
    command = launch.call_args.args[0]
    assert '--wait' not in command and '--pipe' not in command
    assert command[-1] == '--desktop-session' and '--vm' not in command
    vm_selection.registry.assert_called_once_with()


def test_detached_entry_opens_viewer_once(monkeypatch):
    import watch_viewer as viewer
    import vm_selection
    monkeypatch.setattr(vm_selection, 'registry', Mock(return_value={'first': Mock(), 'second': Mock()}))
    monkeypatch.setattr(viewer.os, 'getuid', lambda: 1000)
    monkeypatch.setattr(viewer.Path, 'read_text', lambda _: 'unconfined\n')
    run = Mock(return_value=0)
    monkeypatch.setattr(viewer, 'run_viewer', run)
    monkeypatch.setattr(viewer.subprocess, 'run', Mock(side_effect=AssertionError('must not recurse')))
    assert viewer.main(['--desktop-session']) == 0
    run.assert_called_once_with()
    vm_selection.registry.assert_called_once_with()


def test_make_watch_delegates_to_this_checkout_and_returns(tmp_path):
    root = tmp_path / 'worktree with spaces'
    (root / 'tools').mkdir(parents=True)
    source = Path(__file__).resolve().parents[2]
    (root / 'Makefile').write_bytes((source / 'Makefile').read_bytes())
    (root / 'tools/vm_selection.py').write_bytes((source / 'tools/vm_selection.py').read_bytes())
    (root / 'tests/integration').mkdir(parents=True)
    (root / 'tests/integration/vm_config.py').write_bytes(
        (source / 'tests/integration/vm_config.py').read_bytes())
    (root / 'config').mkdir()
    (root / 'config/test-vm.json').write_text(json.dumps({'vms': [
        {'name': 'watch-test', 'disk_anchor': '/unused/watch-test.qcow2'}]}))
    launcher = root / 'tools/watch'
    launcher.write_text('#!/bin/sh\n[ "$#" = "0" ] || exit 2\n'
                        'printf "watcher launched\\n"\n')
    launcher.chmod(0o755)
    result = subprocess.run(['make', '--no-print-directory', 'watch'], cwd=root,
                            capture_output=True, text=True, timeout=5)
    assert result.returncode == 0, result.stderr
    assert result.stdout == 'watcher launched\n'
    for argument in ('VM=watch-test', 'VM='):
        refused = subprocess.run(['make', '--no-print-directory', 'watch', argument], cwd=root,
                                 capture_output=True, text=True, timeout=5)
        assert refused.returncode != 0 and 'VM parameter refused' in refused.stderr
