"""Collector cleanup can signal only its pinned child, never user viewers."""

import signal
import fcntl
import os
import json
import subprocess
import threading
import xml.etree.ElementTree as ET
from unittest.mock import Mock, patch

import pytest

import e2e_watch as watch
from tests.support.vm_baseline import rig
from tests.support.vm_runner import lease_rig


def publication(tmp_path, name, run):
    item = watch.Publication.__new__(watch.Publication)
    item.run, item.vm_name, item.directory = run, name, tmp_path
    item.server = Mock()
    item.path = tmp_path / (run + '.sock')
    item.path.touch()
    item.identity = item.path.stat().st_ino
    item.current = tmp_path / ('current-' + name.encode('ascii').hex() + '.json')
    return item


def test_closing_one_vm_publication_preserves_other_vm_and_replacement(tmp_path):
    first = publication(tmp_path, 'First-VM', 'a' * 32)
    other = publication(tmp_path, 'Second-VM', 'b' * 32)
    replacement = publication(tmp_path, 'First-VM', 'c' * 32)
    first.publish()
    other.publish()
    replacement.publish()
    first.close()
    assert json.loads(other.current.read_text()) == {
        'run': other.run, 'vm': other.vm_name, 'checkout': str(watch.ROOT)}
    assert json.loads(replacement.current.read_text()) == {
        'run': replacement.run, 'vm': replacement.vm_name, 'checkout': str(watch.ROOT)}
    assert other.path.exists() and replacement.path.exists()
    other.close()
    assert not other.current.exists() and not other.path.exists()
    assert replacement.current.exists()
    replacement.close()
    assert not replacement.current.exists() and not replacement.path.exists()


def test_old_checkout_cannot_remove_another_checkouts_vm_registration(tmp_path, monkeypatch):
    original = publication(tmp_path, 'First-VM', 'a' * 32)
    original.publish()
    registration = json.loads(original.current.read_text())
    registration['checkout'] = str(tmp_path / 'different checkout')
    original.current.write_text(json.dumps(registration))
    original.close()
    assert json.loads(original.current.read_text()) == registration
    assert not original.path.exists()


def test_publication_keeps_its_bound_vm_when_ambient_selection_changes(tmp_path, monkeypatch):
    import vm_config
    selected = Mock(side_effect=AssertionError('Publisher must retain its own VM binding'))
    item = publication(tmp_path, 'Original-VM', 'a' * 32)
    monkeypatch.setattr(vm_config, 'selected', selected)
    try:
        item.publish()
        assert json.loads(item.current.read_text())['vm'] == 'Original-VM'
    finally:
        item.close()
    selected.assert_not_called()


def test_shared_display_disables_incompatible_gl_and_is_repeatable():
    root = ET.fromstring('''<domain><devices>
      <graphics type="spice"><listen type="none"/>
        <gl enable="yes" rendernode="/dev/dri/renderD128"/></graphics>
      <video><model type="virtio"><acceleration accel3d="yes" accel2d="no"/></model></video>
      <disk type="file"/>
    </devices></domain>''')
    watch.display_endpoint(root)
    first = ET.tostring(root)
    assert root.find('devices/graphics/gl').attrib == {'enable': 'no'}
    assert root.find('devices/video/model/acceleration').get('accel3d') == 'no'
    assert root.find('devices/graphics/listen').get('type') == 'none'
    assert root.find('devices/disk').get('type') == 'file'
    assert len(root.findall('devices/graphics')) == 2
    watch.display_endpoint(root)
    assert ET.tostring(root) == first


def handle():
    item = watch.Observer.__new__(watch.Observer)
    item.display, item.listener, item.control = Mock(), Mock(), Mock()
    item.child, item.pidfd, item.publication = Mock(pid=12345), 42, Mock()
    item.thread = None
    item.stop = threading.Event()
    return item


@pytest.mark.parametrize('expired', [False, True])
def test_cleanup_revokes_owned_sockets_before_pinned_signal(expired):
    item = handle()
    child = item.child
    child.wait.side_effect = [subprocess.TimeoutExpired('collector', 2), 0]
    events = []
    for peer in (item.display, item.listener, item.control):
        peer.shutdown.side_effect = lambda *_: events.append('revoke')
    def send(*_):
        assert events == ['revoke'] * 3
        if expired:
            raise ProcessLookupError
    with patch.object(watch.signal, 'pidfd_send_signal', side_effect=send) as pinned, \
            patch.object(watch.os, 'kill') as raw, patch.object(watch.os, 'close') as close:
        item.close()
    pinned.assert_called_once_with(42, signal.SIGKILL)
    raw.assert_not_called()
    child.kill.assert_not_called()
    child.terminate.assert_not_called()
    close.assert_called_once_with(42)


def test_unrecorded_identity_never_signals_numeric_pid():
    item = handle()
    item.pidfd = None
    item.child.wait.side_effect = subprocess.TimeoutExpired('collector', 2)
    with patch.object(watch.signal, 'pidfd_send_signal') as pinned, \
            patch.object(watch.os, 'kill') as raw:
        with pytest.raises(ValueError, match='unrecorded-collector'):
            item.close()
    pinned.assert_not_called()
    raw.assert_not_called()


def test_unfinished_cleanup_retains_identity():
    item = handle()
    item.child.wait.side_effect = subprocess.TimeoutExpired('collector', 2)
    with patch.object(watch.signal, 'pidfd_send_signal'), patch.object(watch.os, 'close') as close:
        with pytest.raises(subprocess.TimeoutExpired):
            item.close()
    assert item.pidfd == 42
    close.assert_not_called()


def test_failed_pin_closes_gate_without_authorizing_attachment():
    display = Mock()
    local, remote, listener, listener_remote = Mock(), Mock(), Mock(), Mock()
    for fd, peer in enumerate((display, local, remote, listener, listener_remote), 100):
        peer.fileno.return_value = fd
    with patch.object(watch, 'Publication') as publisher, \
            patch.object(watch.socket, 'socketpair', side_effect=[(local, remote), (listener, listener_remote)]), \
            patch.object(watch.subprocess, 'Popen') as spawn, \
            patch.object(watch.os, 'pidfd_open', side_effect=OSError), \
            patch.object(watch.signal, 'pidfd_send_signal') as send:
        publisher.return_value.server.fileno.return_value = 200
        with pytest.raises(OSError):
            watch.Observer(display, 1000, 'a' * 32)
    local.sendall.assert_not_called()
    local.close.assert_called_once()
    spawn.return_value.wait.assert_called_once_with(timeout=2)
    send.assert_not_called()


def test_optional_failure_keeps_automation_running():
    adapter = Mock(run='a' * 32)
    with patch.dict(watch.os.environ, {'PKEXEC_UID': '1000'}), \
            patch.object(watch, 'Observer', side_effect=ValueError('unavailable')):
        assert watch.start(adapter) is None
    adapter.open_display.assert_called_once_with()
    adapter.close_display.assert_not_called()
    adapter.lease.stop.assert_not_called()


@pytest.mark.parametrize('failed', [False, True])
def test_baseline_feed_spans_preparation_and_closes_after_lock_release(rig, monkeypatch, failed):
    capture = rig.capture()
    observer = Mock()
    def begin(owner):
        assert owner.commands.lock_fd is not None
        owner.watch = observer
    def prepare(owner):
        assert owner.watch is observer
        observer.close.assert_not_called()
        if failed:
            raise RuntimeError('preparation-failed')
    def closed():
        assert capture.commands.lock_fd is None
        # Establish actual OS lock release, rather than just cleared metadata.
        fd = os.open(capture.lock_path, os.O_RDWR | os.O_NOFOLLOW)
        try:
            fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        finally:
            os.close(fd)
    monkeypatch.setattr(watch, 'begin', begin)
    observer.close.side_effect = closed
    capture.prepare_guest = prepare
    if failed:
        with pytest.raises(RuntimeError, match='preparation-failed'):
            capture.run()
    else:
        capture.run()
    observer.close.assert_called_once()
    assert capture.watch is None


@pytest.mark.parametrize('graphics', ['vnc', 'spice'])
@pytest.mark.parametrize('failure', [None, 'body', 'close'])
def test_every_lease_observes_start_and_owns_cleanup(lease_rig, graphics, failure):
    lease, _ = lease_rig
    observer = Mock(finished=threading.Event())
    lease.view.graphics_type = graphics
    def begin(owner):
        owner.watch = observer
    with patch.dict(watch.os.environ, {'PKEXEC_UID': '1000'}), \
            patch.object(watch, 'begin', side_effect=begin), \
            patch.object(watch, 'DisplayAdapter') as adapter, \
            patch.object(watch, 'start', side_effect=AssertionError('Must reuse the lease feed')):
        lease.__enter__()
        lease.prepare()
        try:
            lease.start()
            assert lease.watch is observer
            adapter.assert_called_once_with(lease.source, lease.view.domain_id,
                                            lease.guard, lease.state['run'], lease=lease)
            if failure == 'close':
                observer.close.side_effect = RuntimeError('collector-cleanup-failed')
                with pytest.raises(RuntimeError, match='collector-cleanup-failed'):
                    lease.close_watch()
                assert lease.watch is observer  # Retain identity for retry.
                observer.close.side_effect = None
            elif failure == 'body':
                with pytest.raises(RuntimeError, match='body-failed'):
                    try:
                        raise RuntimeError('body-failed')
                    finally:
                        lease.close_watch()
                assert lease.watch is None
            lease.stop()
            if failure is None:
                assert lease.watch is observer
                observer.close.assert_not_called()
                lease.start()
                assert lease.watch is observer
                assert observer.attach_display.call_count == 2
            def closed():
                assert lease.fd is None, 'Feed must remain connected until actual lock release'
            observer.close.side_effect = closed
        finally:
            lease.finish()
            lease.release()
        assert lease.watch is None
        observer.close.assert_called()


def test_failed_shared_start_cannot_swallow_collector_cleanup_failure():
    lease = Mock(watch=None, watch_detached=False, state={'run': 'a' * 32})
    with patch.dict(watch.os.environ, {'PKEXEC_UID': '1000'}), \
            patch.object(watch.os, 'geteuid', return_value=0), \
            patch.object(watch, 'DisplayAdapter'), patch.object(watch, 'begin',
                side_effect=RuntimeError('collector-cleanup-failed')):
        with pytest.raises(RuntimeError, match='collector-cleanup-failed'):
            watch.attach(lease)
