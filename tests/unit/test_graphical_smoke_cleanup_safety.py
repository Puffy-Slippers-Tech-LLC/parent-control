"""No live commands: controller refusal and cleanup ordering before VM use."""

from pathlib import Path
import sys
from unittest.mock import Mock, patch

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'integration'))
import check_graphical_smoke as smoke
import check_graphical_recovery as recovery
sys.path.pop(0)


@pytest.mark.parametrize('worker_fails', [False, True])
def test_worker_closes_before_callback_even_on_cleanup_failure(worker_fails):
    events = []
    def worker_close():
        events.append('worker')
        if worker_fails:
            raise RuntimeError('fixture failure')
    worker = Mock(close=worker_close)
    server = Mock(close=lambda: events.append('server'))
    ledger = smoke.runner.RunLedger()
    if worker_fails:
        with pytest.raises(RuntimeError, match='fixture failure'):
            smoke.close_backend(worker, server, ledger)
        assert ledger.outcomes['cleanup']['outcome'] == 'failed'
    else:
        smoke.close_backend(worker, server, ledger)
    assert events == ['worker', 'server']


def test_original_failure_survives_cleanup_failure():
    ledger = smoke.runner.RunLedger()
    worker, server = Mock(), Mock()
    worker.close.side_effect = RuntimeError('cleanup failure')
    with pytest.raises(ValueError, match='original failure'):
        try:
            raise ValueError('original failure')
        finally:
            smoke.close_backend(worker, server, ledger)
    server.close.assert_called_once()
    assert ledger.outcomes['cleanup']['outcome'] == 'failed'


@pytest.mark.parametrize('arguments,uid', [(['check', 'extra'], 0), (['check'], 1000)])
def test_invalid_invocation_refuses_before_files_commands_or_vm(arguments, uid):
    with patch.object(sys, 'argv', arguments), patch.object(smoke.os, 'geteuid', return_value=uid), \
            patch.object(smoke.tempfile, 'mkdtemp') as create, \
            patch.object(smoke.graphical_backend, 'check') as tools, \
            patch.object(smoke.runner.baseline, 'LibvirtSource') as source:
        with pytest.raises(RuntimeError, match='smoke:'):
            smoke.main()
    create.assert_not_called()
    tools.assert_not_called()
    source.assert_not_called()


def test_backend_poll_failure_still_closes_worker_and_callback(tmp_path):
    lease = Mock(state={'run': 'a' * 32})
    worker, server = Mock(), Mock(path=tmp_path / 'callback.sock')
    worker.poll.side_effect = RuntimeError('fixture backend failure')
    with patch.object(smoke, 'Adapter'), patch.object(smoke, 'CallbackServer', return_value=server), \
            patch.object(smoke, 'Worker', return_value=worker):
        with pytest.raises(RuntimeError, match='fixture backend failure'):
            smoke.run_backend(tmp_path, lease, Mock(), 'host-key', smoke.runner.RunLedger())
    worker.close.assert_called_once()
    server.close.assert_called_once()


def test_failed_observation_never_releases_graphical_input(tmp_path):
    import json
    (tmp_path / 'ready.request.json').write_text(json.dumps({'stage': 'ready', 'screenshot': None}))
    lease, vm = Mock(), Mock()
    lease.state = {'run': 'a' * 32}
    vm.call.return_value = b'not a greeter\n'
    controller = smoke.Smoke(tmp_path, lease, Mock(), 'host-key')
    with patch.object(smoke.runner, 'address', return_value='192.0.2.1'), \
            patch.object(smoke, 'Transport', return_value=vm):
        with pytest.raises(RuntimeError, match='greeter-observation-failed'):
            controller.step()
    assert controller.steps == []
    assert not (tmp_path / 'ready.reply.json').exists()


@pytest.mark.parametrize('change,category', [
    ({'phase': 'running'}, 'journal-identity'),
    ({'run': 'invalid'}, 'journal-identity'),
    ({'domain_uuid': 'replacement'}, 'journal-identity'),
    ({'domain_id': None}, 'journal-identity'),
    ({'domain_id': 18}, 'domain-replaced-or-off'),
    ({'baseline_sha256': '0' * 64}, 'journal-identity'),
    ({'extra': True}, 'journal-identity'),
    ({}, None),
])
def test_recovery_validates_recorded_identity_before_cleanup(tmp_path, change, category):
    import hashlib
    import json
    runner = smoke.runner
    source = Mock(uuid='recorded-uuid')
    source.domain.ID.return_value = 17
    source.domain.autostart.return_value = False
    lease = runner.Lease(source, Mock(), Mock(), directory=tmp_path, graphics_type='vnc')
    baseline_state = {'phase': 'finalized', 'source': {'layout': {'source_shares': []}}, 'proof': 'proof'}
    state = {'schema_version': 1, 'run': 'a' * 32, 'phase': 'cleanup-requested',
             'domain_uuid': source.uuid, 'domain_id': 17, 'original_xml': '<recorded/>',
             'baseline_sha256': hashlib.sha256(runner.baseline.encode(baseline_state)).hexdigest(), **change}
    lease.capture = Mock()
    lease.capture.read_state.return_value = baseline_state
    lease.capture.verify_snapshot.return_value = 'proof'
    lease.journal = Mock(read_bytes=lambda: json.dumps(state).encode())
    events = []
    lease.guard = Mock(side_effect=lambda: events.append('guard'))
    lease.finish = Mock(side_effect=lambda: events.append('finish'))
    with patch.object(runner.os, 'open', return_value=42), patch.object(runner.os, 'close') as close, \
            patch.object(runner.fcntl, 'flock'), patch.object(runner.baseline, 'identity'), \
            patch.object(runner.baseline, 'domain_layout', return_value=baseline_state['source']['layout']), \
            patch.object(runner, 'isolated_xml'):
        if category:
            with pytest.raises(RuntimeError, match=category):
                lease.recover_graphical_cleanup()
            lease.finish.assert_not_called()
            lease.guard.assert_not_called()
        else:
            lease.recover_graphical_cleanup()
            assert events == ['guard', 'finish']
            assert lease.view.run == state['run'] and lease.view.domain_id == 17
        assert lease.fd is None
        close.assert_called_once_with(42)
    source.shutdown.assert_not_called()
    source.domain.create.assert_not_called()


def test_recovery_requires_exclusive_lock_before_journal_or_controls(tmp_path):
    runner = smoke.runner
    lease = runner.Lease(Mock(), Mock(), Mock(), directory=tmp_path, graphics_type='vnc')
    lease.capture = Mock()
    lease.finish = Mock()
    with patch.object(runner.os, 'open', return_value=42), patch.object(runner.os, 'close'), \
            patch.object(runner.baseline, 'identity'), \
            patch.object(runner.fcntl, 'flock', side_effect=BlockingIOError):
        with pytest.raises(RuntimeError, match='busy-controller'):
            lease.recover_graphical_cleanup()
    lease.capture.read_state.assert_not_called()
    lease.finish.assert_not_called()


def test_recovery_entrypoint_refuses_unprivileged_use_before_files_or_vm():
    with patch.object(sys, 'argv', ['check']), patch.object(recovery.os, 'geteuid', return_value=1000), \
            patch.object(recovery.tempfile, 'mkdtemp') as create:
        with pytest.raises(RuntimeError, match='root-required'):
            recovery.main()
    create.assert_not_called()
