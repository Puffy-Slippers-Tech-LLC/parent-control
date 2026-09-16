"""Progress follows real recorder boundaries and cannot export worker secrets."""

import json
import os
import re
import socket
import threading
import time
from pathlib import Path
from unittest.mock import Mock

import pytest

import accessible_ui
import inventory
from e2e_watch_collector import receive_progress
from e2e_watch import Observer
from e2e_watch import ProgressPublication
from e2e_watch_protocol import Frames, progress_packet, read_frame
from e2e_watch_viewer import Feed, duration_text, progress_text
from tools.e2e_progress import Progress, operation_labels
from ui_observations import OPERATION_LABELS, UiObservations
from tests.support.paths import ROOT
from tests.support.perl import run_perl, LIB
from tests.support.e2e_evidence import attempt
from tests.support.e2e_recording import session


def cases():
    document, _ = inventory.read_json(ROOT / 'tests/e2e/scenarios.json')
    return inventory.resolve_selection(document, None, root=ROOT)['cases']


def test_count_includes_current_case_and_uses_selected_total():
    selected = cases()[:5]
    progress = Progress(selected)
    for index, case in enumerate(selected, 1):
        progress.case(case['case_id'])
        title, step, operation = progress_text({'progress': progress.snapshot()})
        assert title == f"[{index}/5] [{case['coverage_id']}]: {case['title']} - (0m/0m)"
        assert step == ''
        assert operation.startswith('Preparing VM: ')


@pytest.mark.parametrize('seconds, expected', [(0, '0m'), (59, '0m'), (60, '1m'),
    (3599, '59m'), (3600, '1h 0m'), (7261, '2h 1m')])
def test_elapsed_time_format(seconds, expected):
    assert duration_text(seconds) == expected


def test_operation_timer_ticks_and_groups_preparation_messages(monkeypatch):
    clock = Mock(return_value=10_000_000_000)
    monkeypatch.setattr('tools.e2e_progress.time.monotonic_ns', clock)
    progress = Progress(cases()[:2])
    progress.prepare(progress.cases[0]['case_id'])
    progress.step('Install')
    label = 'Installing and preparing the application'
    progress.operation(label)
    shown = json.loads(progress_packet(progress.snapshot()))
    for seconds, expected in ((0, '0s'), (1, '1s'), (59, '59s'),
                              (60, '1m 0s'), (61, '1m 1s'), (3601, '60m 1s')):
        assert progress_text({'progress': shown},
            now_ns=10_000_000_000 + seconds * 1_000_000_000)[2] == label + f' - ({expected})'
    clock.return_value += 65_000_000_000
    progress.operation('Opening About')
    assert progress_text({'progress': progress.snapshot()})[2] == 'Opening About - (0s)'
    progress.prepare_next()
    clock.return_value += 59_000_000_000
    progress.preparation_output('Cleanup')
    assert progress_text({'progress': progress.snapshot(display=True)})[2] == 'Preparing VM: Cleanup - (59s)'
    progress.prepare(progress.cases[1]['case_id'])
    clock.return_value += 2_000_000_000
    progress.preparation_output('Starting VM')
    assert progress_text({'progress': progress.snapshot()})[2] == 'Preparing VM: Starting VM - (1m 1s)'
    progress.step('Next case')
    assert progress_text({'progress': progress.snapshot()})[2] == ''


def test_next_case_visible_during_cleanup_and_preparation_without_resetting_total(monkeypatch):
    clock = Mock(return_value=10_000_000_000)
    monkeypatch.setattr('tools.e2e_progress.time.monotonic_ns', clock)
    progress = Progress(cases()[:2])
    first, second = progress.cases
    progress.prepare(first['case_id'])
    progress.step('First case')
    clock.return_value += 3600_000_000_000
    progress.prepare_next()
    line = 'check-system: [timing:stage=test duration_seconds=67.918]'
    progress.preparation_output(line)
    shown = progress.snapshot(display=True)
    assert shown['current'] == 2 and shown['step'] == ''
    assert shown['operation'] == 'Preparing VM: ' + line
    assert progress.snapshot()['current'] == 1  # Evidence still belongs to case one.
    clock.return_value += 120_000_000_000
    assert progress_text({'progress': shown})[0].endswith(' - (2m/1h 2m)')
    progress.prepare(second['case_id'])
    progress.case(second['case_id'])  # Recorder startup must not reset the clock.
    assert progress.snapshot()['case_started_ns'] == shown['case_started_ns']
    progress.step('Second case starts')
    progress.operation('Opening About')
    progress.preparation_output('late preparation output')
    assert progress.snapshot(display=True)['operation'] == 'Opening About'


def test_invocation_heartbeat_survives_without_display_and_expires(tmp_path, monkeypatch):
    # Model root ownership only; use real atomic files, the publisher thread,
    # bounded reader and monotonic expiry without touching the host registry.
    original_lstat, original_fstat = Path.lstat, os.fstat
    def root_owned(info):
        fields = list(info)
        fields[4] = 0
        return os.stat_result(fields)
    monkeypatch.setattr(Path, 'lstat', lambda path: root_owned(original_lstat(path)))
    monkeypatch.setattr(os, 'fstat', lambda fd: root_owned(original_fstat(fd)))
    monkeypatch.setattr(os, 'geteuid', lambda: 0)
    monkeypatch.setenv('PKEXEC_UID', str(os.getuid() or 1000))
    monkeypatch.setattr(os, 'getuid', lambda: int(os.environ['PKEXEC_UID']))
    monkeypatch.setattr('e2e_watch.BASE', tmp_path / 'watch')
    monkeypatch.setattr('e2e_watch_viewer.BASE', tmp_path / 'watch')
    progress = Progress(cases()[:2])
    progress.prepare(progress.cases[0]['case_id'])
    publisher = ProgressPublication(progress)
    feed = Feed()
    def wait_for(current):
        deadline = time.monotonic() + 3
        while time.monotonic() < deadline:
            value = feed.progress()
            if value and value['current'] == current:
                return value
            time.sleep(.01)
        pytest.fail('Invocation progress was not published')
    try:
        assert wait_for(1)['operation'].startswith('Preparing VM: ')
        progress.step('Current case')
        progress.prepare_next()
        progress.preparation_output('check-system: [stage:restored-baseline-verification]')
        assert wait_for(2)['operation'].startswith('Preparing VM: check-system: ')
        assert feed.memory is None
    finally:
        publisher.close()
    assert not publisher.thread.is_alive()
    value = json.loads(publisher.path.read_text())
    monkeypatch.setattr('e2e_watch_viewer.time.monotonic_ns',
                        lambda: value['updated_ns'] + 3_000_000_000)
    assert feed.progress() is None


def test_every_inventory_case_exposes_title_and_exact_step_descriptions():
    selected = cases()
    progress = Progress(selected)
    for case in selected:
        progress.case(case['case_id'])
        for phase in inventory.PHASES:
            for step in case['phases'][phase]:
                progress.step(step['description'])
                packet = progress_packet(progress.snapshot())
                assert json.loads(packet)['step'] == step['description']
    case = next(case for case in selected if case['coverage_id'] == 3)
    assert case['phases']['steps'][0]['description'].startswith('For both variants, reject the wrong-account prompt')


def test_recorder_publishes_description_before_step_body_and_checkpoint(session):
    recorder = session.recorder
    case = recorder.contract.plan['cases'][0]
    recorder.begin_case(case['case_id'])
    with recorder.step('setup'):
        assert recorder.progress.snapshot()['step'] == case['phases']['setup'][0]['description']
        report = json.loads((session.collector.path / 'event-000002.json').read_text())
        assert report['progress']['step'] == case['phases']['setup'][0]['description']


def test_worker_messages_are_bounded_allowlisted_and_cleared_at_step_boundary(tmp_path):
    progress = Progress(cases()[:1])
    progress.case(progress.cases[0]['case_id'])
    label = 'Selecting [Existing child] from the child selector'
    progress.follow_worker(tmp_path, operation_labels(LIB))
    path = tmp_path / 'watch-operation.json'
    path.write_text(json.dumps(dict(sequence=1, operation=label)))
    assert progress.snapshot()['operation'] == label
    progress.step('Next step')
    assert progress.snapshot()['operation'] == ''
    progress.operation('Checking the selected child')
    assert progress.snapshot()['operation'] == 'Checking the selected child'
    path.write_text(json.dumps(dict(sequence=2, operation=label)))
    assert progress.snapshot()['operation'] == label
    for invalid in (dict(sequence=3, operation='private-secret-canary'),
                    dict(sequence=True, operation=label), ['not-a-message'],
                    dict(sequence=3, operation=label, secret='private-secret-canary')):
        path.write_text(json.dumps(invalid))
        assert 'private-secret-canary' not in json.dumps(progress.snapshot())
        assert progress.snapshot()['operation'] == 'Checking the selected child'
    path.write_text('x' * 4096)
    assert progress.snapshot()['operation'] == 'Checking the selected child'
    path.unlink()
    path.symlink_to(tmp_path / 'missing')
    assert progress.snapshot()['operation'] == 'Checking the selected child'


def test_real_perl_operation_is_published_before_input_and_retained(tmp_path):
    (tmp_path / 'vars.json').write_text('{}')
    probe = r'''
use strict;
use warnings;
use JSON::PP;
chdir shift or die 'chdir';
BEGIN { $INC{'testapi.pm'} = 1; }
package testapi;
sub send_key {
    open(my $file, '<', 'watch-operation.json') or die 'missing progress before input';
    my $value = JSON::PP::decode_json(do { local $/; <$file> });
    die 'wrong operation' unless $value->{operation} eq 'Dismissing the password prompt';
}
sub current_console { 'sut' }
sub assert_screen { 1 }
package main;
require onpc_gdm;
onpc_gdm::dismiss_prompt();
'''
    result = run_perl(probe, str(tmp_path))
    assert 'ONPC-E2E-OPERATION' in result.stderr
    value = json.loads((tmp_path / 'watch-operation.json').read_text())
    assert value == dict(sequence=2, operation='Waiting for the greeter account list')


def test_new_worker_blocks_require_literal_nonsecret_operation_messages():
    # Bookkeeping helpers either do no customer operation or dispatch to blocks
    # which log it. New action blocks must opt into the shared progress contract.
    bookkeeping = {'onpc_journey::new', 'onpc_journey::seen',
                   'onpc_journey::consume_observation', 'onpc_journey::service_system_prompt',
                   'onpc_password::seal_capture'}
    for path in LIB.glob('*.pm'):
        if path.stem == 'onpc_progress':
            continue
        source = path.read_text()
        assert 'use onpc_progress ();' in source
        blocks = re.split(r'^sub (\w+) \{\n', source, flags=re.MULTILINE)
        for name, body in zip(blocks[1::2], blocks[2::2]):
            if name.startswith('_') or f'{path.stem}::{name}' in bookkeeping:
                continue
            assert re.match(r"    onpc_progress::operation\('[^'\n]+'\);", body), (path, name)
        assert not re.search(r'onpc_progress::operation\((?!\')', source)


def test_all_public_ui_operations_have_descriptions_and_publish_before_call(monkeypatch):
    assert set(OPERATION_LABELS) == accessible_ui.OPERATIONS
    progress = Progress(cases()[:1])
    progress.case(progress.cases[0]['case_id'])
    ui = UiObservations(None, progress=progress)
    def call(_argv, operation):
        assert progress.snapshot()['operation'] == OPERATION_LABELS[operation]
        return json.dumps(dict(operation=operation, outcome='passed', interface='AT-SPI')).encode(), []
    monkeypatch.setattr(ui, 'call', call)
    ui.observe('parent-window')


def test_controller_progress_crosses_actual_socket_and_read_only_frame_copy():
    progress = Progress(cases()[:5])
    progress.case(progress.cases[2]['case_id'])
    progress.step(progress.cases[2]['phases']['steps'][0]['description'])
    progress.operation('Selecting [Child user] from the child selector')
    frames = Frames('a' * 32)
    sender, receiver = socket.socketpair(socket.AF_UNIX, socket.SOCK_SEQPACKET)
    try:
        with sender, receiver:
            sender.send(progress_packet(progress.snapshot()))
            assert receive_progress(receiver, frames)
            _, meta, _, _ = read_frame(frames.memory)
            assert meta['state'] == 'waiting'  # Works even without display pixels.
            assert meta['progress'] == progress.snapshot()
            assert progress_text(meta)[0].startswith('[3/5] ')
    finally:
        frames.close()


def test_observer_monitor_forwards_changes_without_waiting_for_guest_frames():
    progress = Progress(cases()[:5])
    progress.case(progress.cases[2]['case_id'])
    sender, receiver = socket.socketpair(socket.AF_UNIX, socket.SOCK_SEQPACKET)
    observer = Observer.__new__(Observer)
    observer.control = sender
    observer.progress = progress
    observer.stop = threading.Event()
    observer.ready = threading.Event()
    observer.finished = threading.Event()
    observer.publication = Mock()
    observer._reap = Mock()  # No processes were spawned by this transport test.
    observer.cleanup_error = None
    sender.settimeout(.02)
    receiver.settimeout(2)
    thread = threading.Thread(target=observer._monitor)
    thread.start()
    try:
        with receiver:
            receiver.send(b'ready')
            assert json.loads(receiver.recv(3501))['current'] == 3
            progress.step('The next declared step')
            value = json.loads(receiver.recv(3501))
            assert value['step'] == 'The next declared step'
            progress.operation('Opening About')
            assert json.loads(receiver.recv(3501))['operation'] == 'Opening About'
    finally:
        observer.stop.set()
        thread.join(timeout=3)
        sender.close()
    assert not thread.is_alive() and observer.finished.is_set()
    assert observer.cleanup_error is None
    observer._reap.assert_called_once()


@pytest.mark.parametrize('text', ['x' * 20000, '\\"' * 20000, '界' * 20000, '\x00\n' * 20000])
def test_long_progress_fits_frame_header_without_breaking_utf8(text):
    value = dict(current=3, total=5, case_id='3', title=text, step=text, operation=text)
    packet = progress_packet(value)
    assert len(packet) <= 3500
    frames = Frames('a' * 32)
    try:
        frames.publish(progress=json.loads(packet))
        assert read_frame(frames.memory)[1]['progress'] == json.loads(packet)
    finally:
        frames.close()
