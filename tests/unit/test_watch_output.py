"""Observer private-file refusal, cancellation ownership and terminal input safety."""

from contextlib import contextmanager
import fcntl
import json
import os
from unittest.mock import Mock

import pytest

from test_storage import directory
from watch_output import Output, TerminalWriter, JsonReader


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
