"""No live commands: controller refusal and cleanup ordering before VM use."""

import json
import sys
from unittest.mock import Mock, patch

import pytest

import check_graphical_smoke as smoke
import check_graphical_recovery as recovery
import check_system_recovery as system_recovery
import fixture_credentials
from tests.support.vm_baseline import local_preparation_source


@pytest.fixture
def login_window():
    lease = Mock(fd=42, state={'phase': 'isolated', 'domain_id': None})
    lease.capture.state = {'source': {'layout': {'disk': '/fixture/active.qcow2'}}}
    verified = Mock(lease=lease)
    guestfs = Mock()
    g = guestfs.GuestFS.return_value
    g.inspect_os.return_value = ['/dev/fixture']
    g.inspect_get_mountpoints.return_value = {'/': '/dev/fixture'}
    g.realpath.side_effect = lambda path: path
    info = dict(st_mode=0o100644, st_uid=0, st_gid=0, st_nlink=1, st_ino=123, st_dev=4)
    g.lstatns.side_effect = lambda path: dict(info)
    contents = [b'# LOGIN_TIMEOUT 60\nLOGIN_RETRIES 3\n  LOGIN_TIMEOUT\t60 # bounded login\nOTHER value\n']
    g.filesize.side_effect = lambda path: len(contents[0])
    g.read_file.side_effect = lambda path: contents[0]
    g.write.side_effect = lambda path, data: contents.__setitem__(0, data)
    return lease, verified, guestfs, g, info, contents


def test_login_window_preserves_unrelated_bytes_and_metadata_and_closes(login_window):
    lease, verified, guestfs, g, info, contents = login_window
    original = contents[0]
    metadata = dict(info)
    result = fixture_credentials.provision_vt6_login_window(lease, verified, guestfs)
    assert contents[0] == original.replace(b'\t60 #', b'\t600 #')
    assert info == metadata
    assert result == {'login_timeout_seconds': 600, 'configuration': 'login.defs',
                      'readback_verified': True}
    g.add_drive_opts.assert_called_once_with('/fixture/active.qcow2', format='qcow2', readonly=False)
    g.set_network.assert_called_once_with(False)
    g.sync.assert_called_once()
    g.close.assert_called_once()
    fixture_credentials.provision_vt6_login_window(lease, verified, guestfs)
    assert g.write.call_count == 1  # Same prepared fixture is idempotent.


def test_login_window_full_guard_runs_outside_appliance_disk_lock(login_window):
    lease, verified, guestfs, g, _, _ = login_window
    opened = False
    guards = []

    def launch():
        nonlocal opened
        opened = True

    def close():
        nonlocal opened
        opened = False

    def guard(*, off):
        # Capture.inventory uses locking qemu-img info for a powered-off VM.
        # Its disk cannot be reopened while the libguestfs writer holds it.
        if opened:
            raise RuntimeError('command:failed')
        guards.append(off)

    g.launch.side_effect = launch
    g.close.side_effect = close
    lease.guard.side_effect = guard
    result = fixture_credentials.provision_vt6_login_window(lease, verified, guestfs)
    assert result['readback_verified'] is True
    assert guards == [True, True, True, True]
    assert not opened
    g.write.assert_called_once()


@pytest.mark.parametrize('fault', ['unowned', 'running', 'booted', 'different-lease', 'guard'])
def test_login_window_refuses_outside_held_offline_preparation(login_window, fault):
    lease, verified, guestfs, g, _, _ = login_window
    if fault == 'unowned':
        lease.fd = None
    elif fault == 'running':
        lease.state['phase'] = 'running'
    elif fault == 'booted':
        lease.state['domain_id'] = 7
    elif fault == 'different-lease':
        verified.lease = Mock()
    else:
        lease.guard.side_effect = RuntimeError('private-canary')
    expected = ('credential:login-window-lease-failed' if fault == 'guard'
                else 'credential:outside-provisioning')
    with pytest.raises(smoke.EvidenceError, match='^' + expected + '$'):
        fixture_credentials.provision_vt6_login_window(lease, verified, guestfs)
    guestfs.GuestFS.assert_not_called()
    g.write.assert_not_called()


@pytest.mark.parametrize('fault', ['symlink', 'owner', 'group', 'hardlink', 'writable',
    'special', 'missing', 'duplicate', 'malformed', 'unexpected-timeout', 'oversize', 'nul',
    'late-guard', 'before-write-metadata', 'partial-write', 'metadata-changed',
    'sync', 'close', 'interrupt'])
def test_login_window_unsafe_or_partial_preparation_refuses_and_closes(login_window, fault):
    lease, verified, guestfs, g, info, contents = login_window
    if fault == 'symlink':
        g.realpath.side_effect = lambda path: '/unexpected'
    elif fault in ('owner', 'group', 'hardlink', 'writable', 'special'):
        key, value = {'owner': ('st_uid', 1000), 'group': ('st_gid', 1000),
                      'hardlink': ('st_nlink', 2), 'writable': ('st_mode', 0o100666),
                      'special': ('st_mode', 0o020644)}[fault]
        info[key] = value
    elif fault in ('missing', 'duplicate', 'malformed', 'unexpected-timeout', 'oversize', 'nul'):
        contents[0] = {'missing': b'OTHER 60\n', 'duplicate': b'LOGIN_TIMEOUT 60\nLOGIN_TIMEOUT 60\n',
                       'malformed': b'LOGIN_TIMEOUT 60 junk\n', 'unexpected-timeout': b'LOGIN_TIMEOUT 0\n',
                       'oversize': b'x' * 65537, 'nul': b'LOGIN_TIMEOUT 60\n\x00'}[fault]
    elif fault == 'late-guard':
        lease.guard.side_effect = [None, None, RuntimeError('private-canary')]
    elif fault == 'before-write-metadata':
        changed = dict(info, st_ino=info['st_ino'] + 1)
        g.lstatns.side_effect = [dict(info), changed]
    elif fault == 'partial-write':
        g.write.side_effect = lambda path, data: contents.__setitem__(0, data[:5])
    elif fault == 'metadata-changed':
        def changed(path, data):
            contents[0] = data
            info['st_ino'] += 1
        g.write.side_effect = changed
    elif fault == 'interrupt':
        g.write.side_effect = KeyboardInterrupt('private-canary')
    else:
        getattr(g, fault).side_effect = RuntimeError('private-canary')
    with pytest.raises(KeyboardInterrupt if fault == 'interrupt' else smoke.EvidenceError) as error:
        fixture_credentials.provision_vt6_login_window(lease, verified, guestfs)
    assert 'private-canary' not in str(error.value)
    expected = {
        'symlink': 'login-path', 'owner': 'login-file', 'group': 'login-file',
        'hardlink': 'login-file', 'writable': 'login-file', 'special': 'login-file',
        'missing': 'login-setting', 'duplicate': 'login-setting', 'malformed': 'login-setting',
        'unexpected-timeout': 'login-setting', 'oversize': 'login-size', 'nul': 'login-content',
        'late-guard': 'login-window-close-failed', 'before-write-metadata': 'login-file-changed',
        'partial-write': 'login-write-failed',
        'metadata-changed': 'login-write-failed', 'sync': 'login-window-close-failed',
        'close': 'login-window-close-failed', 'interrupt': 'login-window-interrupted'}
    assert str(error.value) == 'credential:' + expected[fault]
    g.close.assert_called_once()
    if fault not in ('late-guard', 'partial-write', 'metadata-changed', 'sync', 'close', 'interrupt'):
        g.write.assert_not_called()


@pytest.mark.parametrize('method,boundary', [('launch', 'mount'), ('read_file', 'read'), ('write', 'write')])
def test_login_window_api_failure_keeps_boundary_without_private_exception(login_window, method, boundary):
    lease, verified, guestfs, g, _, _ = login_window
    getattr(g, method).side_effect = smoke.EvidenceError('private-canary')
    with pytest.raises(smoke.EvidenceError) as error:
        fixture_credentials.provision_vt6_login_window(lease, verified, guestfs)
    assert str(error.value) == 'credential:login-window-' + boundary + '-failed'
    g.close.assert_called_once()


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


@pytest.mark.parametrize('fault', [None, 'worker-exit', 'not-ready', 'backend-exit', 'distribution'])
def test_input_guard_binds_live_worker_and_staged_bytes_and_always_cleans(tmp_path, fault):
    lease = Mock(state={'run': 'a' * 32})
    worker, server = Mock(ready=True, result=None), Mock(path=tmp_path / 'callback.sock')
    worker.poll.return_value = None
    adapter = Mock(events=[])
    tmp_path.chmod(0o700)
    verified = []
    def observe(guard):
        if fault == 'worker-exit':
            worker.poll.return_value = 0
        elif fault == 'not-ready':
            worker.ready = False
        elif fault == 'backend-exit':
            worker.result = 0
        elif fault == 'distribution':
            (tmp_path / 'distribution/lib/onpc_vt6.pm').write_text('changed')
        guard()
        verified.append(True)
        raise RuntimeError('bounded test stop')
    with patch.object(smoke.e2e_worker, 'Adapter', return_value=adapter), \
            patch.object(smoke.e2e_worker, 'CallbackServer', return_value=server), \
            patch.object(smoke.e2e_worker, 'Worker', return_value=worker):
        with pytest.raises(RuntimeError):
            smoke.e2e_worker.run_distribution(tmp_path, lease, smoke.runner.RunLedger(),
                expected_inputs=smoke.inputs(), observe=Mock(), validate=Mock(),
                guarded_observe=observe)
    assert verified == ([] if fault else [True])
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
@pytest.mark.parametrize('graphics_type', ['vnc', 'spice'])
def test_recovery_validates_recorded_identity_before_cleanup(tmp_path, change, category, graphics_type,
                                                          local_preparation_source):
    import hashlib
    import json
    runner = smoke.runner
    source = Mock(uuid='recorded-uuid')
    source.domain.ID.return_value = 17
    source.domain.autostart.return_value = False
    source.domain.XMLDesc.return_value = (
        f'<domain><devices><graphics type="{graphics_type}"/></devices></domain>')
    lease = runner.Lease(source, Mock(), Mock(), directory=tmp_path, graphics_type=graphics_type)
    recover = (lease.recover_graphical_cleanup if graphics_type == 'vnc'
               else lease.recover_system_cleanup)
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
                recover()
            lease.finish.assert_not_called()
            lease.guard.assert_not_called()
        else:
            recover()
            assert events == ['guard', 'finish']
            assert lease.view.run == state['run'] and lease.view.domain_id == 17
        assert lease.fd is None
        close.assert_called_once_with(42)
    source.shutdown.assert_not_called()
    source.domain.create.assert_not_called()


@pytest.mark.parametrize('graphics_type', ['vnc', 'spice'])
def test_recovery_requires_exclusive_lock_before_journal_or_controls(tmp_path, graphics_type,
                                                                   local_preparation_source):
    runner = smoke.runner
    lease = runner.Lease(Mock(), Mock(), Mock(), directory=tmp_path, graphics_type=graphics_type)
    lease.capture = Mock()
    lease.finish = Mock()
    with patch.object(runner.os, 'open', return_value=42), patch.object(runner.os, 'close'), \
            patch.object(runner.baseline, 'identity'), \
            patch.object(runner.fcntl, 'flock', side_effect=BlockingIOError):
        with pytest.raises(RuntimeError, match='busy-controller'):
            if graphics_type == 'vnc':
                lease.recover_graphical_cleanup()
            else:
                lease.recover_system_cleanup()
    lease.capture.read_state.assert_not_called()
    lease.finish.assert_not_called()


@pytest.mark.parametrize('entrypoint', [recovery.main, system_recovery.main])
def test_recovery_entrypoint_refuses_unprivileged_use_before_files_or_vm(entrypoint):
    with patch.object(sys, 'argv', ['check']), patch.object(recovery.os, 'geteuid', return_value=1000), \
            patch.object(recovery.tempfile, 'mkdtemp') as create:
        with pytest.raises(RuntimeError, match='root-required'):
            entrypoint()
    create.assert_not_called()


@pytest.mark.parametrize('entrypoint', [recovery.main, system_recovery.main])
def test_recovery_entrypoint_refuses_arguments_before_files_or_vm(entrypoint):
    with patch.object(sys, 'argv', ['check', '--force']), \
            patch.object(recovery.tempfile, 'mkdtemp') as create, \
            patch.object(recovery.importlib, 'import_module') as load:
        with pytest.raises(RuntimeError, match='invalid-arguments'):
            entrypoint()
    create.assert_not_called()
    load.assert_not_called()


@pytest.mark.parametrize('graphics_type', ['vnc', 'spice'])
def test_recovery_refuses_wrong_lease_kind_before_lock_or_journal(graphics_type,
                                                              local_preparation_source):
    lease = smoke.runner.Lease(Mock(), Mock(), Mock(), graphics_type=graphics_type)
    lease.capture = Mock()
    recover = (lease.recover_system_cleanup if graphics_type == 'vnc'
               else lease.recover_graphical_cleanup)
    with pytest.raises(RuntimeError, match='invalid-lease'):
        recover()
    lease.capture.private_directory.assert_not_called()


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


@pytest.mark.parametrize('code', [*sorted(smoke.VT6_AUTH_REFUSALS), 'private-canary',
                                  'vt6-auth:capture-owner-refused private-canary', None])
def test_vt6_refusal_checkpoint_retains_only_fixed_codes_without_authorization(qualification, code):
    controller, _ = qualification
    controller.vt6_auth = True
    if code not in smoke.VT6_AUTH_REFUSALS:
        with pytest.raises(RuntimeError, match='diagnostic-condition'):
            controller.progress('vt6-password-screen', {'vt6_refusal': code})
        assert not reports(controller)
    else:
        controller.progress('vt6-password-screen', {'vt6_refusal': code})
        saved = reports(controller)[-1]
        assert saved['event'] == 'stage-rejected'
        assert saved['result']['vt6_refusal'] == {'stage': 'vt6-password-screen', 'code': code}
        assert saved['result']['steps'] == []


@pytest.mark.parametrize('fault', [None, 'private', 'timing', 'boolean'])
def test_vt6_timing_checkpoint_never_counts_as_authorization(qualification, fault):
    controller, _ = qualification
    controller.vt6_auth = True
    report = {'phase': 'inputs-before', 'recipient': {},
              'recheck_ms': {'source': 5, 'assets': 0, 'baseline': 68000}}
    if fault == 'private':
        report['recipient'] = {'private-canary': 'private-canary'}
    if fault == 'timing':
        report['recheck_ms']['baseline'] = 'private-canary'
    if fault == 'boolean':
        report['recheck_ms']['source'] = True
    if fault:
        with pytest.raises(RuntimeError, match='diagnostic-condition'):
            controller.progress('vt6-password-ready', {'vt6_diagnostic': report})
        assert not reports(controller)
    else:
        controller.progress('vt6-password-ready', {'vt6_diagnostic': report})
        saved = reports(controller)[-1]
        assert saved['event'] == 'terminal-diagnostic'
        assert saved['result']['vt6_diagnostics'] == [{'stage': 'vt6-password-ready', **report}]
        assert saved['result']['steps'] == []


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


@pytest.mark.parametrize('failure', [False, True])
def test_login_window_preparation_gates_worker_and_outer_restoration(qualification, failure):
    controller, lease = qualification
    controller.vt6_auth = True
    prepared = {'login_timeout_seconds': 600, 'configuration': 'login.defs', 'readback_verified': True}
    def backend(*args, **kwargs):
        assert controller.result['vt6_login_window'] == prepared
        assert 'login-window-preparation-verified' in [d['event'] for d in reports(controller)]
        return {'worker_evidence': {'outcome': 'passed'}}
    with patch.object(smoke, 'provision_vt6_login_window', return_value=prepared,
                      side_effect=smoke.EvidenceError('credential:login-window-failed')
                      if failure else None), patch.object(smoke, 'run_backend', side_effect=backend) as run:
        if failure:
            with pytest.raises(smoke.EvidenceError, match='login-window-failed'):
                with lease:
                    controller.execute(lease, Mock())
            run.assert_not_called()
            assert 'login-window-preparation-verified' not in [d['event'] for d in reports(controller)]
        else:
            with lease:
                controller.execute(lease, Mock())
            run.assert_called_once()
    lease.finish.assert_called_once()
    lease.release.assert_called_once()
    assert lease.fd is None
    assert reports(controller)[-1]['result']['outcome'] == ('failed' if failure else 'passed')


@pytest.mark.parametrize('vt6_auth,install,refusal,expected', [
    (True, False, False, 1800), (False, False, False, 600),
    (False, True, False, 960), (False, True, True, 600)])
def test_vt6_worker_uses_existing_finite_extended_budget(tmp_path, vt6_auth, install, refusal, expected):
    installation = Mock(refusal=refusal) if install else None
    with patch.object(smoke, 'Smoke', return_value=Mock(steps=[])), \
            patch.object(smoke.e2e_worker, 'run_distribution') as run:
        smoke.run_backend(tmp_path, Mock(), Mock(), 'host-key', smoke.runner.RunLedger(), {},
                          vt6_auth=vt6_auth, installation=installation)
    assert run.call_args.kwargs['timeout'] == expected


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
