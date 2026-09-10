"""No live commands: controller refusal and cleanup ordering before VM use."""

import json
import sys
from unittest.mock import Mock, patch

import pytest

import check_graphical_smoke as smoke
import check_graphical_recovery as recovery
from tests.support.vm_baseline import local_preparation_source


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
    tmp_path.chmod(0o700)
    with patch.object(smoke.e2e_worker, 'Adapter', return_value=Mock(events=[])), \
            patch.object(smoke.e2e_worker, 'CallbackServer', return_value=server), \
            patch.object(smoke.e2e_worker, 'Worker', return_value=worker):
        with pytest.raises(RuntimeError, match='fixture backend failure'):
            smoke.run_backend(tmp_path, lease, Mock(), 'host-key', smoke.runner.RunLedger(), smoke.inputs())
    worker.close.assert_called_once()
    server.close.assert_called_once()


def test_stale_artifacts_refuse_before_connection_or_lease(tmp_path):
    def stage(_source, destination, _commands):
        destination.mkdir()
    with patch.object(smoke.os, 'geteuid', return_value=0), \
            patch.object(smoke.os, 'getegid', return_value=0), \
            patch.object(smoke.runner.baseline.guest_contract, 'CHECKOUT', smoke.ROOT), \
            patch.object(smoke.os, 'umask'), patch.object(smoke.signal, 'signal'), \
            patch.object(smoke.tempfile, 'mkdtemp', return_value=str(tmp_path)), \
            patch.object(smoke, 'inputs', return_value={}), \
            patch.object(smoke.graphical_backend, 'check', return_value={}), \
            patch.object(smoke, 'schedule_preflight'), \
            patch.object(smoke.runner, 'artifact_source', return_value=tmp_path), \
            patch.object(smoke.runner, 'stage_assets', side_effect=stage), \
            patch.object(smoke, 'preflight_source', side_effect=smoke.EvidenceError(
                'provenance:package-source-mismatch')), \
            patch.object(smoke.importlib, 'import_module') as imports, \
            patch.object(smoke.runner.baseline, 'LibvirtSource') as source, \
            patch.object(smoke.runner, 'Lease') as lease:
        assert smoke.main(assets=tmp_path) == 1
    imports.assert_not_called()
    source.assert_not_called()
    lease.assert_not_called()
    result = json.loads((tmp_path / 'result.json').read_text())
    assert result['category'] == 'provenance:package-source-mismatch'
    assert result['lease_phase'] is None
    assert result['outcomes']['infrastructure']['outcome'] == 'failed'


def test_failed_observation_never_releases_graphical_input(tmp_path):
    import json
    (tmp_path / 'ready.request.json').write_text(json.dumps({'stage': 'ready', 'screenshot': None}))
    lease, vm = Mock(), Mock()
    vm.config = {}
    lease.state = {'run': 'a' * 32}
    vm.call.return_value = b'not a greeter\n'
    controller = smoke.Smoke(tmp_path, lease, Mock(), 'host-key')
    with patch.object(smoke.runner, 'address', return_value='192.0.2.1'), \
            patch.object(smoke, 'Transport', return_value=vm):
        with pytest.raises(smoke.EvidenceError, match='observation:invalid-output'):
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
def test_recovery_validates_recorded_identity_before_cleanup(tmp_path, change, category,
                                                          local_preparation_source):
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


def test_recovery_requires_exclusive_lock_before_journal_or_controls(tmp_path, local_preparation_source):
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


@pytest.fixture
def qualification(tmp_path, local_preparation_source):
    with smoke.PrivateCollector(run_id='qualification-test', secrets=['private-canary'],
                                parent=tmp_path) as collector:
        ledger = smoke.runner.RunLedger()
        result = {'outcome': 'failed', 'steps': []}
        controller = smoke.Qualification(tmp_path, Mock(), ledger, collector, result, 'host')
        controller.verified = Mock(inputs={'source_sha256': 'a' * 64}, source_files={'file': 'digest'})
        lease = smoke.runner.Lease(Mock(), Mock(), Mock(), ledger=ledger,
                                   finalize=controller.finalize)
        lease.fd, lease.state = 42, {'phase': 'isolated'}
        lease.prepare, lease.guard, lease.save = Mock(), Mock(), Mock()

        def finish():
            lease.state['phase'] = 'complete'

        def release():
            lease.fd = None

        lease.finish, lease.release = Mock(side_effect=finish), Mock(side_effect=release)
        with patch.object(smoke.runner.Lease, '__enter__', return_value=lease), \
                patch.object(smoke, 'VerifiedInputs', return_value=controller.verified), \
                patch.object(smoke.runner, 'bootstrap', return_value='host-key'), \
                patch.object(smoke.runner, 'host_fingerprint', return_value='host'):
            yield controller, lease


def reports(controller):
    return [json.loads(path.read_text()) for path in sorted(controller.collector.path.glob('event-*.json'))]


def test_install_recipient_refusal_is_durable_without_completed_step(qualification):
    controller, _ = qualification
    controller.install = True
    transport = Mock(config={'run': 'fixture'})
    transport.call.return_value = b'install-password-rejected:foreground-distinct\n'
    observer = smoke.ReadOnlyObservations(transport, on_diagnostic=lambda condition:
        controller.progress('install-password', {'recipient_refusal': condition}))
    with pytest.raises(smoke.EvidenceError, match='probe-failed'):
        observer.read('install-password')
    report = reports(controller)[-1]
    assert report['event'] == 'stage-rejected'
    assert report['active_stage'] == 'install-password'
    assert report['result']['installation_diagnostic'] == {'recipient_refusal': 'foreground-distinct'}
    assert report['result']['steps'] == []
    controller.failure('infrastructure', 'worker-execution-failed')
    assert reports(controller)[-1]['result']['installation_diagnostic'] == {
        'recipient_refusal': 'foreground-distinct'}


@pytest.mark.parametrize('fault', [None, 'bootstrap', 'worker', 'interrupt', 'cleanup',
                                  'provenance', 'host', 'report', 'late-source'])
def test_live_controller_ordering_and_retained_diagnostics(qualification, fault):
    controller, lease = qualification
    original = KeyboardInterrupt('private-canary') if fault == 'interrupt' else RuntimeError('private-canary')
    rechecks = []

    def recheck():
        rechecks.append((lease.fd, lease.state['phase']))
        assert lease.fd == 42
        if fault == 'provenance' and len(rechecks) == 2:
            raise original
        if fault == 'late-source' and len(rechecks) == 3:
            raise original

    controller.verified.recheck.side_effect = recheck

    def backend(*args, **kwargs):
        assert args[-1] == controller.verified.source_files
        assert rechecks == [(42, 'isolated')]
        for stage in smoke.STAGES:
            kwargs['progress'](stage, None)
            if fault in ('worker', 'interrupt') and stage == 'selected':
                controller.ledger.fail_outcome('infrastructure', 'e2e:worker-execution-failed')
                kwargs['on_failure']('infrastructure', 'worker-execution-failed')
                raise original
            kwargs['progress'](stage, {'stage': stage, 'sha256': 'b' * 64})
            assert reports(controller)[-1]['event'] == 'stage-observed'
        return {'worker_evidence': {'outcome': 'passed'}}

    if fault == 'bootstrap':
        lease.prepare.side_effect = original
    if fault == 'cleanup':
        lease.finish.side_effect = original
    old_save = controller.collector.save_report

    def save(name, data):
        if fault == 'report' and data.get('event') == 'after-cleanup':
            raise original
        return old_save(name, data)

    with patch.object(smoke, 'run_backend', side_effect=backend) as run, \
            patch.object(controller.collector, 'save_report', side_effect=save), \
            patch.object(smoke.runner, 'host_fingerprint', return_value='changed' if fault == 'host' else 'host'):
        if fault:
            with pytest.raises(BaseException) as caught:
                with lease:
                    controller.execute(lease, Mock())
            if fault != 'host':
                assert caught.value is original
        else:
            with lease:
                controller.execute(lease, Mock())
            assert controller.result['outcome'] == 'passed'
            assert controller.result['preservation'] == {'source': True, 'host': True}
            assert rechecks == [(42, 'isolated'), (42, 'complete'), (42, 'complete')]
    lease.finish.assert_called_once()
    lease.release.assert_called_once()
    docs = reports(controller)
    assert 'private-canary' not in json.dumps(docs)
    assert any(d['event'] == 'before-cleanup' for d in docs)
    assert docs[-1]['result']['outcome'] == ('failed' if fault else 'passed')
    if fault in ('provenance', 'late-source'):
        assert docs[-1]['result']['preservation']['source'] is False
    if fault in ('worker', 'interrupt'):
        before = next(d for d in docs if d['event'] == 'before-cleanup')
        assert before['active_stage'] == 'selected'
        assert [s['stage'] for s in before['result']['steps']] == ['ready', 'gdm']
        assert before['outcomes']['infrastructure']['outcome'] == 'failed'
    if fault == 'bootstrap':
        run.assert_not_called()


@pytest.mark.parametrize('late', [False, True])
@pytest.mark.parametrize('code', ['source-changed', 'assets-changed', 'baseline-state-changed',
    'baseline-proof-changed', 'baseline-identity-changed', 'file-replaced',
    'tree-changed', 'unknown-private-canary'])
def test_final_provenance_keeps_safe_specific_cause_through_cleanup(qualification, late, code):
    controller, lease = qualification
    controller.result['worker_evidence'] = {'outcome': 'passed'}
    error = smoke.EvidenceError('provenance:' + code)
    controller.verified.recheck.side_effect = [None, error] if late else [error]
    with pytest.raises(smoke.EvidenceError) as caught:
        with lease:
            pass
    assert caught.value is error
    expected = 'provenance:' + (code if code != 'unknown-private-canary' else 'recheck-failed')
    final = reports(controller)[-1]
    assert final['event'] == 'finalization-rejected'
    assert final['result']['final_provenance_refusal'] == expected
    assert final['result']['preservation'] == {'source': False, 'host': True}
    assert final['result']['outcome'] == 'failed'
    assert 'private-canary' not in json.dumps(reports(controller))
    lease.finish.assert_called_once()
    lease.release.assert_called_once()
    assert lease.fd is None


def test_stage_checkpoint_failure_prevents_guest_acknowledgement(tmp_path):
    (tmp_path / 'ready.request.json').write_text(json.dumps({'stage': 'ready', 'screenshot': None}))
    vm = Mock()
    vm.config = {}
    vm.call.return_value = b'greeter-ready\n'
    progress = Mock(side_effect=[None, OSError('private-canary')])
    controller = smoke.Smoke(tmp_path, Mock(state={'run': 'a' * 32}), Mock(), 'host-key', progress)
    with patch.object(smoke.runner, 'address', return_value='192.0.2.1'), \
            patch.object(smoke, 'Transport', return_value=vm):
        with pytest.raises(OSError):
            controller.step()
    assert progress.call_count == 2
    assert not (tmp_path / 'ready.reply.json').exists()


def test_transfer_failure_is_durable_and_prevents_worker_with_one_outer_cleanup(qualification):
    controller, lease = qualification
    controller.assets = controller.directory / 'assets'
    transfer = Mock()
    transfer.provision.side_effect = smoke.EvidenceError('transfer:copied-digest-mismatch')
    with patch.object(smoke, 'AssetTransfer', return_value=transfer), \
            patch.object(smoke, 'run_backend') as run:
        with pytest.raises(smoke.EvidenceError, match='copied-digest-mismatch'):
            with lease:
                controller.execute(lease, Mock())
    run.assert_not_called()
    lease.finish.assert_called_once()
    lease.release.assert_called_once()
    docs = reports(controller)
    assert 'asset-transfer-started' in [d['event'] for d in docs]
    assert 'asset-transfer-verified' not in [d['event'] for d in docs]
    assert docs[-1]['result']['outcome'] == 'failed'
    assert docs[-1]['outcomes']['infrastructure']['category'] == 'transfer:copied-digest-mismatch'


def test_booted_asset_refusal_prevents_first_graphical_action(tmp_path):
    (tmp_path / 'ready.request.json').write_text(json.dumps({'stage': 'ready', 'screenshot': None}))
    transfer = Mock()
    transfer.observe.side_effect = smoke.EvidenceError('transfer:booted-assets-mismatch')
    controller = smoke.Smoke(tmp_path, Mock(state={'run': 'a' * 32}), Mock(), 'host-key',
                             transfer=transfer)
    with patch.object(smoke.runner, 'address', return_value='192.0.2.1'), \
            patch.object(smoke, 'Transport', return_value=Mock(config={})):
        with pytest.raises(smoke.EvidenceError, match='booted-assets-mismatch'):
            controller.step()
    assert not (tmp_path / 'ready.reply.json').exists()
    assert not controller.steps


@pytest.mark.parametrize('fault', ['capture', 'observation', None])
def test_authentication_stage_requires_safe_capture_and_real_session(tmp_path, fault):
    (tmp_path / 'authenticated.request.json').write_text(json.dumps({
        'stage': 'authenticated', 'screenshot': 'smoke-1.png' if fault == 'capture' else None}))
    controller = smoke.Smoke(tmp_path, Mock(), Mock(), 'host-key', authenticate=True)
    controller.steps = [{'stage': stage} for stage in smoke.STAGES]
    controller.vm = Mock()
    controller.vm.read.return_value = {'fixture_role': 'parent', 'active_local_graphical_session': True,
                                       'unexpected_user_session': False}
    if fault == 'observation':
        controller.vm.read.side_effect = smoke.EvidenceError('observation:probe-failed')
    if fault:
        with pytest.raises(smoke.EvidenceError if fault == 'observation' else RuntimeError):
            controller.step()
        assert not (tmp_path / 'authenticated.reply.json').exists()
        assert len(controller.steps) == len(smoke.STAGES)
    else:
        controller.step()
        assert (tmp_path / 'authenticated.reply.json').exists()
        assert len(controller.steps) == len(smoke.AUTH_STAGES)
    if fault == 'capture':
        controller.vm.read.assert_not_called()
    else:
        controller.vm.read.assert_called_once_with('parent-session')


def test_credential_worker_cannot_pass_without_authentication_stage(tmp_path):
    controller = Mock(steps=list(smoke.STAGES), stages=smoke.AUTH_STAGES)
    def worker(*args, **kwargs):
        kwargs['validate']()
    with patch.object(smoke, 'Smoke', return_value=controller), \
            patch.object(smoke.e2e_worker, 'run_distribution', side_effect=worker), \
            patch.object(smoke, 'module_result') as module:
        with pytest.raises(RuntimeError, match='missing-stages'):
            smoke.run_backend(tmp_path, Mock(), Mock(), 'host-key', smoke.runner.RunLedger(), {},
                              credentials=Mock())
    module.assert_not_called()
