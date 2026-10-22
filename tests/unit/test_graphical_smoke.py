"""Focused smoke evidence/sequence regressions; no VM use."""

import json
import subprocess
import sys
from unittest.mock import Mock, patch

import pytest

import check_graphical_smoke as smoke


from tests.support.screens import png
from tests.support.e2e_evidence import worker_evidence


@pytest.mark.parametrize('wrapper,scope,flags', [
    ('check_parent_setup.py', 'installed-parent-setup-qualification', {}),
    ('check_parent_input.py', 'installed-parent-input-qualification', {'parent_input': True}),
    ('check_parent_standard_input.py', 'installed-standard-input-qualification',
     {'parent_standard_input': True}),
])
@pytest.mark.parametrize('refused', [False, True])
def test_parent_bootstrap_aliases_share_preparation_before_installed_setup(
        tmp_path, monkeypatch, wrapper, scope, flags, refused):
    import runpy
    import parent_setup_qualification as qualification
    import system_fixture_preparation as preparation
    from tools import test_storage

    # Execute each actual wrapper, preserving its flags and named artifact input.
    captured = []
    monkeypatch.setattr(test_storage, 'named_input', lambda: tmp_path / 'assets')
    monkeypatch.setattr(smoke, 'main', lambda **kwargs: captured.append(kwargs) or 0)
    with pytest.raises(SystemExit) as stopped:
        runpy.run_path(str(smoke.ROOT / 'tests/integration' / wrapper), run_name='__main__')
    assert stopped.value.code == 0
    assert captured == [{'assets': tmp_path / 'assets', 'provision_credentials': True,
                         'parent_setup': True, **flags}]

    # All wrappers select this exact baseline class. Exercise its real detached
    # worker callback, with only VM, producer and installation operations doubled.
    controller = qualification.ParentSetupQualification(tmp_path, Mock(), Mock(), Mock(),
        {'scope': scope}, {}, assets=tmp_path / 'assets', credentials=Mock())
    controller.fixture_selection = {'frozen': 'execution-owner'}
    controller.checkpoint = Mock()
    verified = Mock(inputs={}, source_files={})
    monkeypatch.setattr(smoke, 'VerifiedInputs', Mock(return_value=verified))
    bootstrap = Mock(return_value='host-key')
    monkeypatch.setattr(smoke.runner, 'bootstrap', bootstrap)
    monkeypatch.setattr(smoke.runner, 'address', lambda *args, **kwargs: 'guest')
    events = []
    vm = Mock()
    vm.probe_ready.side_effect = lambda **kwargs: events.append('ssh-ready')
    monkeypatch.setattr(smoke, 'Transport', Mock(return_value=vm))
    provisioner = Mock()
    provisioner.require_ready.side_effect = lambda receipt: events.append('guard-ready')
    setup = Mock()
    setup.run.side_effect = lambda guard: events.append('setup-input') or {'package_verified': True}
    monkeypatch.setattr(smoke.installed_setup, 'InstalledSetup', Mock(return_value=setup))

    def prepare(transport, lease, directory, record):
        assert transport is vm and directory == tmp_path
        assert record == {'frozen': 'execution-owner'}
        events.append('provision')
        if refused:
            raise ValueError('fixture-input-refused')
        return {'controller': provisioner, 'receipt': 'fresh'}

    monkeypatch.setattr(preparation, 'prepare', prepare)

    def worker(*args, **kwargs):
        for stage in ('ready', 'setup-detached'):
            (tmp_path / (stage + '.request.json')).write_text(json.dumps(
                {'stage': stage, 'screenshot': None}))
            kwargs['guarded_observe'](Mock())
        return {'outcome': 'passed'}

    monkeypatch.setattr(smoke.e2e_worker, 'run_distribution', worker)
    lease = Mock(state={'run': 'owned-run'})
    if refused:
        with pytest.raises(ValueError, match='fixture-input-refused'):
            controller.execute(lease, Mock())
        assert events == ['ssh-ready', 'provision']
        setup.run.assert_not_called()
        assert not (tmp_path / 'setup-detached.reply.json').exists()
    else:
        controller.execute(lease, Mock())
        assert events == ['ssh-ready', 'provision', 'guard-ready', 'setup-input']
    assert bootstrap.call_args.kwargs == {'system_product_free': True}
    smoke.VerifiedInputs.assert_called_once_with(lease=lease, assets=tmp_path / 'assets',
                                                 package_only=True)
    vm.copy.assert_not_called()
    vm.call.assert_not_called()


def test_standalone_qualification_imports_without_inherited_checkout_path(tmp_path):
    program = ('import sys; sys.path.insert(0, ' + repr(str(smoke.ROOT / 'tests/integration')) +
               '); import check_graphical_smoke')
    result = subprocess.run([sys.executable, '-I', '-B', '-c', program],
                            cwd=tmp_path, capture_output=True, text=True, timeout=30)
    assert result.returncode == 0, result.stderr


@pytest.mark.parametrize('fault', [None, 'seal', 'result', 'interrupt'])
def test_functional_serial_password_ack_waits_for_recording_seal(tmp_path, monkeypatch, fault):
    events = []
    class Protection:
        def __enter__(self):
            assert not (tmp_path / 'serial-password.reply.json').exists()
            events.append('sealed')
            if fault == 'seal':
                raise RuntimeError('encoder unavailable')

        def __exit__(self, kind, value, traceback):
            events.append('unsealed' if kind is None else 'retained')
    monkeypatch.setattr(smoke, 'protect_capture', lambda **_: Protection())
    controller = smoke.Smoke(tmp_path, Mock(), Mock(), 'host-key', serial=True,
                             authenticate=True, functional=True, progress=Mock())
    controller.steps = [{'stage': stage} for stage in smoke.FUNCTIONAL_SERIAL_STAGES[
        :smoke.FUNCTIONAL_SERIAL_STAGES.index('serial-password')]]
    controller.vm = Mock(read=Mock(return_value={'terminal_echo_disabled': True}))
    port = Mock(pending_in=b'')
    (tmp_path / 'serial-password.request.json').write_text(json.dumps(
        {'stage': 'serial-password', 'screenshot': None}))
    if fault == 'seal':
        with pytest.raises(RuntimeError):
            controller.step(port)
        assert not (tmp_path / 'serial-password.reply.json').exists()
    else:
        controller.step(port)
        assert (tmp_path / 'serial-password.reply.json').exists()
        assert events == ['sealed']
        (tmp_path / 'serial-authenticated.request.json').write_text(json.dumps(
            {'stage': 'serial-authenticated', 'screenshot': None}))
        if fault == 'result':
            controller.vm.read.side_effect = RuntimeError('session absent')
        elif fault == 'interrupt':
            controller.lease.guard.side_effect = KeyboardInterrupt()
        else:
            controller.vm.read.return_value = {'active_local_serial_session': True}
        if fault:
            with pytest.raises(KeyboardInterrupt if fault == 'interrupt' else RuntimeError):
                controller.step(port)
            assert not (tmp_path / 'serial-authenticated.reply.json').exists()
            assert events == ['sealed', 'retained']
        else:
            controller.step(port)
            assert (tmp_path / 'serial-authenticated.reply.json').exists()
            assert events == ['sealed', 'unsealed']
    if fault:
        assert 'unsealed' not in events and controller._failed


@pytest.mark.parametrize('name', ['../private', '/tmp/image.png', 'vars.json', 'smoke-a.png'])
def test_collector_refuses_unexpected_paths(tmp_path, name):
    with pytest.raises(RuntimeError, match='invalid-screenshot-name'):
        smoke.screenshot(tmp_path, name)


def test_collector_refuses_symlink(tmp_path):
    path = png(tmp_path)
    (path.parent / 'smoke-2.png').symlink_to(path)
    with pytest.raises(RuntimeError, match='screenshot-path'):
        smoke.screenshot(tmp_path, 'smoke-2.png')


@pytest.mark.parametrize('size', [(0, 768), (1024, 0), (8192, 768)])
def test_collector_refuses_unexpected_dimensions(tmp_path, size):
    png(tmp_path, width=size[0], height=size[1])
    with pytest.raises(RuntimeError, match='screen-size'):
        smoke.screenshot(tmp_path, 'smoke-1.png')


def test_evidence_contains_only_dimensions_and_digest(tmp_path):
    png(tmp_path, suffix=b'synthetic private canary')
    result = smoke.screenshot(tmp_path, 'smoke-1.png')
    assert set(result) == {'width', 'height', 'sha256'}
    assert result['width'] == 1024 and result['height'] == 768
    assert 'canary' not in json.dumps(result)


def test_unchanged_selection_refuses_acknowledgement(tmp_path):
    png(tmp_path)
    controller = smoke.Smoke(tmp_path, Mock(), Mock(), 'host-key')
    controller.steps = [{'stage': 'ready'}, {'stage': 'gdm', **smoke.screenshot(tmp_path, 'smoke-1.png')}]
    (tmp_path / 'selected.request.json').write_text(json.dumps({'stage': 'selected', 'screenshot': 'smoke-1.png'}))
    with pytest.raises(RuntimeError, match='unchanged-screen'):
        controller.step()
    assert not (tmp_path / 'selected.reply.json').exists()


@pytest.mark.parametrize('fault', [None, 'ui', 'storage', 'ownership'])
def test_functional_selection_is_fresh_durable_and_never_replayed(tmp_path, fault):
    controller = smoke.Smoke(tmp_path, Mock(), Mock(), 'host-key', serial=True,
                             authenticate=True, functional=True, progress=Mock())
    controller.steps = [{'stage': 'ready'}, {'stage': 'gdm'}, {'stage': 'focused'}]
    controller.vm = Mock()
    result = {'operation': 'gdm-product-free-select-parent', 'outcome': 'passed',
              'interface': 'ApplicationUI+external-provider'}
    controller.ui = Mock(observe=Mock(return_value=result))
    (tmp_path / 'selected.request.json').write_text(json.dumps({'stage': 'selected', 'screenshot': None}))
    if fault == 'ui': controller.ui.observe.side_effect = RuntimeError('missing prompt')
    if fault == 'storage':
        controller.progress.side_effect = lambda stage, observed: (
            (_ for _ in ()).throw(OSError('storage')) if observed else None)
    if fault == 'ownership': controller.lease.guard.side_effect = [None, RuntimeError('lost lease')]
    if fault:
        with pytest.raises((RuntimeError, OSError)): controller.step()
        assert not (tmp_path / 'selected.reply.json').exists()
        with pytest.raises(RuntimeError, match='previous-failure'): controller.step()
    else:
        controller.step()
        assert json.loads((tmp_path / 'selected.reply.json').read_text()) == {'ui': result}
        controller.progress.assert_called_with('selected', {'stage': 'selected', 'ui': result})
    controller.ui.observe.assert_called_once_with('gdm-product-free-select-parent')


def test_functional_list_publishes_direct_focus_without_positional_navigation(tmp_path):
    controller = smoke.Smoke(tmp_path, Mock(), Mock(), 'host-key', serial=True,
                             authenticate=True, functional=True, progress=Mock())
    controller.steps = [{'stage': 'ready'}]
    controller.vm = Mock()
    result = {'operation': 'gdm-product-free-list', 'outcome': 'passed',
              'interface': 'ApplicationUI+external-provider', 'focused': True}
    controller.ui = Mock(observe=Mock(return_value=result))
    (tmp_path / 'gdm.request.json').write_text(json.dumps(
        {'stage': 'gdm', 'screenshot': None}))

    controller.step()

    assert json.loads((tmp_path / 'gdm.reply.json').read_text()) == {
        'ui': result, 'ui_focused': True}
    controller.ui.observe.assert_called_once_with('gdm-product-free-list')


@pytest.mark.parametrize('capture', [None, 'smoke-1.png'])
def test_return_requires_independent_greeter_before_ack_and_keeps_capture_sealed(tmp_path, capture):
    events = []
    controller = smoke.Smoke(tmp_path, Mock(), Mock(), 'host-key', serial=True,
        progress=lambda stage, observed: events.append((stage, observed)))
    controller.steps = [{'stage': stage} for stage in smoke.SERIAL_STAGES[:-1]]
    controller.vm = Mock(read=Mock(return_value={'unexpected_user_session': False}))
    (tmp_path / 'gdm-return.request.json').write_text(json.dumps(
        {'stage': 'gdm-return', 'screenshot': capture}))
    if capture is not None:
        with pytest.raises(RuntimeError, match='authentication-capture-refused'):
            controller.step()
        assert not (tmp_path / 'gdm-return.reply.json').exists()
        controller.vm.read.assert_not_called()
    else:
        controller.step()
        controller.vm.read.assert_called_once_with('greeter')
        assert events[-1] == ('gdm-return', {'stage': 'gdm-return', 'unexpected_user_session': False})
        assert (tmp_path / 'gdm-return.reply.json').exists()


def test_functional_return_uses_the_product_free_list_binding(tmp_path):
    controller = smoke.Smoke(tmp_path, Mock(), Mock(), 'host-key', serial=True,
                             authenticate=True, functional=True, progress=Mock())
    controller.steps = [{'stage': stage} for stage in smoke.FUNCTIONAL_SERIAL_STAGES[:-1]]
    controller.vm = Mock(read=Mock(return_value={'unexpected_user_session': False}))
    result = {'operation': 'gdm-product-free-returned', 'outcome': 'passed',
              'interface': 'ApplicationUI+external-provider'}
    controller.ui = Mock(observe=Mock(return_value=result))
    (tmp_path / 'gdm-return.request.json').write_text(json.dumps(
        {'stage': 'gdm-return', 'screenshot': None}))

    controller.step()

    controller.ui.observe.assert_called_once_with('gdm-product-free-returned')
    assert json.loads((tmp_path / 'gdm-return.reply.json').read_text())['ui'] == result


def test_generalhw_uses_documented_32_bit_vnc_depth(tmp_path):
    selected = smoke.e2e_worker.variables(tmp_path, Mock(path=tmp_path / 'callback.sock'), 'a' * 32)
    assert selected['GENERAL_HW_VNC_DEPTH'] == 32


def test_success_requires_all_stages_even_with_zero_backend_status(tmp_path, worker_evidence):
    worker, server = Mock(), Mock(path=tmp_path / 'callback.sock')
    worker.poll.return_value = 0
    tmp_path.chmod(0o700)
    with patch.object(smoke.e2e_worker, 'Adapter', return_value=Mock(events=[])), \
            patch.object(smoke.e2e_worker, 'CallbackServer', return_value=server), \
            patch.object(smoke.e2e_worker, 'Worker', return_value=worker):
        with pytest.raises(RuntimeError, match='missing-stages'):
            smoke.run_backend(tmp_path, Mock(state={'run': 'a' * 32}), Mock(), 'host-key',
                              smoke.runner.RunLedger(), smoke.inputs())
    worker.close.assert_called_once()
    server.close.assert_called_once()


def test_fixed_observation_is_valid_python_and_contains_no_guest_mutation():
    compile(smoke.OBSERVATION, '<fixed-observation>', 'exec')
    assert "'is-active'" in smoke.OBSERVATION and "'show-session'" in smoke.OBSERVATION
    assert 'capture_output=True' in smoke.OBSERVATION


@pytest.mark.parametrize('change,passed', [
    ({}, True), ({'Type': 'unspecified'}, True),
    ({'User': '1000'}, False), ({'Remote': 'no'}, False),
    ({'Service': 'login'}, False), ({'Type': 'wayland'}, False),
    ({'Type': 'x11', 'Active': 'no'}, False),
])
def test_greeter_observation_excludes_only_root_ssh_observer(change, passed, capsys):
    import subprocess
    import time
    observer = {'Class': 'user', 'Active': 'yes', 'Type': 'tty',
                'Remote': 'yes', 'Service': 'sshd', 'User': '0', **change}
    greeter = {'Class': 'greeter', 'Active': 'yes', 'Type': 'wayland',
               'Remote': 'no', 'Service': 'gdm-launch-environment', 'User': '123'}

    def call(args, **kwargs):
        if args[:2] == ('systemctl', 'is-active'):
            return Mock(stdout='active\n')
        if args[:2] == ('loginctl', 'list-sessions'):
            return Mock(stdout='1 private-canary\n2 private-canary\n')
        assert args[:2] == ('loginctl', 'show-session')
        props = greeter if args[2] == '1' else observer
        return Mock(stdout='\n'.join(f'{key}={value}' for key, value in props.items()))

    with patch.object(subprocess, 'run', side_effect=call), \
            patch.object(time, 'monotonic', side_effect=[0, 1, 100]), patch.object(time, 'sleep'):
        if passed:
            exec(smoke.OBSERVATION, {})
        else:
            with pytest.raises(SystemExit) as error:
                exec(smoke.OBSERVATION, {})
            assert error.value.code == 1
    output = capsys.readouterr().out
    if passed:
        assert output == 'greeter-ready\n'
    else:
        assert json.loads(output) == {'display_manager_active': True,
                                      'active_graphical_greeter': True,
                                      'unexpected_user_session': True}
    assert 'private-canary' not in output


@pytest.mark.parametrize('result', [
    {'result': 'fail'}, {'result': 'softfail'}, {'result': 'ok', 'dents': 1},
    {'result': 'ok', 'details': [{'result': 'fail'}]},
])
def test_module_failure_cannot_be_hidden_by_successful_stage_files(tmp_path, result):
    (tmp_path / 'testresults').mkdir()
    (tmp_path / 'testresults/result-smoke.json').write_text(json.dumps(result))
    with pytest.raises(RuntimeError, match='module-not-passed'):
        smoke.module_result(tmp_path)


def test_schedule_preflight_has_no_backend_or_lifecycle_configuration(tmp_path):
    commands = Mock(last_returncode=1)
    commands.run.return_value = (b'scheduling smoke tests/smoke.pm\n'
        b'Early exit has been requested with _EXIT_AFTER_SCHEDULE. Only evaluating test schedule.\n')
    smoke.schedule_preflight(tmp_path, commands)
    args = commands.run.call_args.args[0]
    assert '_EXIT_AFTER_SCHEDULE=1' in args
    assert '--exit-status-from-test-results' not in args
    assert not any(x.startswith(('BACKEND=', 'GENERAL_HW_')) for x in args)


@pytest.mark.parametrize('status,output', [(1, b'Compilation failed'), (0, b''),
    (1, b'scheduling smoke tests/smoke.pm\nCompilation failed')])
def test_schedule_failure_is_not_accepted_as_the_pinned_early_exit(tmp_path, status, output):
    commands = Mock(last_returncode=status)
    commands.run.return_value = output
    with pytest.raises(RuntimeError, match='schedule-preflight-failed'):
        smoke.schedule_preflight(tmp_path, commands)


@pytest.mark.parametrize('fault', [None, 'capture', 'observation', 'checkpoint'])
@pytest.mark.parametrize('refusal', [False, True])
def test_installation_drains_input_and_persists_each_proof_before_reply(tmp_path, fault, refusal):
    events = []
    verified = Mock(inputs={'package_sha256': 'a' * 64})
    transfer = Mock(verified=verified)
    boundary = smoke.InstallationBoundary(None, verified, transfer, refusal=refusal)
    def progress(stage, observed):
        assert not (tmp_path / f'{stage}.reply.json').exists()
        if observed == {'serial_input_drained': True}:
            events.append('drained-proof')
            return
        events.append('checkpoint' if observed else 'started')
        if observed and fault == 'checkpoint':
            raise RuntimeError('checkpoint-failed')
    controller = smoke.Smoke(tmp_path, Mock(), Mock(), 'host-key', progress, transfer,
                             authenticate=True, serial=True, installation=boundary)
    observations = {
        'boot': {'boot_sha256': 'b' * 64},
        'serial-session': {'active_local_serial_session': True},
        'package-absent': {'product_package_absent': True},
        'sudo-implementation': {'implementation': 'sudo-rs', 'package_version': '0.2.13-0ubuntu1.2'},
        'install-password': {'sudo_install_process_verified': True, 'terminal_echo_disabled': True},
        'install-refused': {'product_package_absent': True, 'core_payload_absent': True,
                            'product_reboot_required': False, 'install_process_absent': True},
        'package-installed': {'package_sha256': 'a' * 64, 'installed_identity_verified': True,
                              'product_reboot_required': True},
    }
    def read(name):
        events.append('observe')
        if fault == 'observation':
            raise RuntimeError('private-canary')
        return observations[name]
    controller.vm = Mock(read=Mock(side_effect=read))
    controller.steps = [{'stage': stage} for stage in smoke.INSTALL_STAGES[:6]]
    port = Mock(pending_in=b'pending', step=Mock(side_effect=lambda: events.append('drain')))
    for stage in boundary.stages:
        events.clear()
        (tmp_path / f'{stage}.request.json').write_text(json.dumps({
            'stage': stage, 'screenshot': 'smoke-1.png' if fault == 'capture' else None}))
        controller.step(port)
        assert events == ['drain']
        assert not (tmp_path / f'{stage}.reply.json').exists()
        port.pending_in = b''
        if fault:
            with pytest.raises((RuntimeError, smoke.EvidenceError)):
                controller.step(port)
            assert not (tmp_path / f'{stage}.reply.json').exists()
            if fault == 'capture':
                controller.vm.read.assert_not_called()
            return
        controller.step(port)
        assert events[:3] == ['drain', 'drain', 'started']
        assert events[-1] == 'checkpoint'
        reply = json.loads((tmp_path / f'{stage}.reply.json').read_text())
        assert reply['boot_sha256'] == 'b' * 64
        assert boundary.observer is controller.vm
        port.pending_in = b'pending'
    if refusal:
        assert controller.steps[-1]['install_process_absent']
        assert controller.steps[-2]['installation_refused']
    else:
        assert controller.steps[-1]['verified_package_digest']
    assert controller.stages[len(controller.steps):] == (
        ('serial-logout', 'gdm-return') if refusal else
        ('reboot-ready', 'reboot-requested', 'reboot-observed', 'gdm-return'))


@pytest.mark.parametrize('fault', [None, 'package', 'early-boot', 'session',
    'checkpoint', 'wait', 'second-boot', 'capture', 'reboot-command',
    'reboot-provenance', 'reboot-requested-boot', 'reboot-checkpoint', 'reboot-ack-checkpoint',
    'enforcement-failed', 'enforcement-boot', 'enforcement-second-boot',
    'broker-failed', 'broker-boot', 'broker-second-boot'])
def test_customer_reboot_orders_input_drain_observation_and_durable_ack(tmp_path, fault):
    events = []
    def progress(stage, observed):
        assert not (tmp_path / f'{stage}.reply.json').exists()
        if observed == {'serial_input_drained': True}:
            events.append('drained-proof')
            return
        if observed:
            events.append('checkpoint:' + stage)
            if fault == 'reboot-requested-boot' and stage == 'reboot-ready':
                controller.vm.read.side_effect = RuntimeError('boot-changed')
            if fault == 'checkpoint' or (fault == 'reboot-checkpoint' and stage == 'reboot-requested'):
                raise RuntimeError('checkpoint-failed')
            if fault == 'reboot-ack-checkpoint' and observed.get('reboot_requested'):
                raise RuntimeError('checkpoint-failed-after-input')
    transfer = Mock()
    boundary = Mock(transfer=transfer, refusal=False)
    boundary.observe_installed_layout.return_value = {
        'installed_files': 12, 'inventory_sha256': 'a' * 64,
        'installed_layout_verified': True, 'verified_inventory_digest': True}
    controller = smoke.Smoke(tmp_path, Mock(), Mock(), 'host-key', progress, transfer,
                             authenticate=True, serial=True, installation=boundary)
    controller.steps = [{'stage': stage} for stage in smoke.INSTALL_STAGES[:-4]]
    controller.steps[-1].update(verified_package_digest=fault != 'package',
        installed_identity_verified=True, product_reboot_required=True, boot_sha256='b' * 64)
    current_boot = 'c' * 64 if fault == 'early-boot' else 'b' * 64
    def read(name):
        nonlocal current_boot
        events.append('read:' + name)
        if name == 'boot':
            return {'boot_sha256': current_boot}
        if name == 'serial-session' and fault == 'session':
            raise RuntimeError('session-failed')
        if name == 'startup-enforcement':
            if fault == 'enforcement-failed':
                raise RuntimeError('enforcement-failed')
            if fault == 'enforcement-second-boot':
                current_boot = 'd' * 64
            return {'boot_sha256': ('d' if fault == 'enforcement-boot' else 'c') * 64,
                    'canary_before_graphical_start': True}
        if name == 'startup-broker':
            if fault == 'broker-failed':
                raise RuntimeError('broker-failed')
            if fault == 'broker-second-boot':
                current_boot = 'd' * 64
            return {'boot_sha256': ('d' if fault == 'broker-boot' else 'c') * 64,
                    'reconciliation_before_publication': True}
        return {'active_local_serial_session': True} if name == 'serial-session' else {
            'unexpected_user_session': False}
    def wait(boot, *, on_diagnostic):
        nonlocal current_boot
        assert boot == 'b' * 64
        assert (tmp_path / 'reboot-ready.reply.json').exists()
        assert (tmp_path / 'reboot-requested.reply.json').exists()
        assert events[-2:] == ['drain', 'drained-proof']
        events.append('wait')
        if fault == 'wait':
            raise RuntimeError('wait-failed')
        current_boot = 'd' * 64 if fault == 'second-boot' else 'c' * 64
        return {'boot_changed': True, 'previous_boot_sha256': boot, 'boot_sha256': 'c' * 64}
    controller.vm = Mock(read=Mock(side_effect=read), wait_boot_change=Mock(side_effect=wait))
    def reboot(boot):
        assert boot == 'b' * 64
        assert 'checkpoint:reboot-requested' in events
        assert not (tmp_path / 'reboot-requested.reply.json').exists()
        events.append('ssh-reboot')
        if fault == 'reboot-command':
            raise RuntimeError('reboot-command-failed')
    controller.transport = Mock(request_customer_reboot=Mock(side_effect=reboot))
    if fault == 'reboot-provenance':
        boundary.verified.recheck.side_effect = RuntimeError('source-changed')
    port = Mock(pending_in=b'', step=Mock(side_effect=lambda: events.append('drain')))
    failure_stage = ('reboot-requested' if fault and fault.startswith('reboot-') else
                     'gdm-return' if fault == 'second-boot' or fault and fault.startswith(('enforcement-', 'broker-')) else
                     'reboot-observed' if fault == 'wait' else 'reboot-ready')
    for stage in ('reboot-ready', 'reboot-requested', 'reboot-observed', 'gdm-return'):
        (tmp_path / f'{stage}.request.json').write_text(json.dumps({
            'stage': stage, 'screenshot': 'smoke-1.png' if fault == 'capture' else None}))
        if stage.startswith('reboot-'):
            port.pending_in = b'pending'
            before = list(events)
            controller.step(port)
            assert events == before + ['drain']
            assert not (tmp_path / f'{stage}.reply.json').exists()
            port.pending_in = b''
        if fault and stage == failure_stage:
            with pytest.raises(RuntimeError):
                controller.step(port)
            assert not (tmp_path / f'{stage}.reply.json').exists()
            with pytest.raises(RuntimeError, match='previous-failure'):
                controller.step(port)
            expected = int(fault in ('reboot-command', 'reboot-ack-checkpoint')
                           or stage in ('reboot-observed', 'gdm-return'))
            assert controller.transport.request_customer_reboot.call_count == expected
            return
        controller.step(port)
        assert events[-1] == 'checkpoint:' + stage
        assert (tmp_path / f'{stage}.reply.json').exists()
    assert controller.steps[-1]['customer_reboot_verified'] is True
    assert controller.steps[-1]['startup_enforcement']['canary_before_graphical_start'] is True
    assert controller.steps[-1]['installed_layout']['verified_inventory_digest'] is True
    boundary.observe_installed_layout.assert_called_once_with()
    assert boundary.verified.recheck.call_count == 2
    controller.transport.request_customer_reboot.assert_called_once_with('b' * 64)


def test_reboot_intent_is_durable_without_claiming_submission(tmp_path):
    result = {'steps': []}
    qualification = smoke.Qualification(tmp_path, Mock(), Mock(), Mock(), result, {}, install=True)
    qualification.checkpoint = Mock()
    qualification.progress('reboot-requested', {'stage': 'reboot-requested',
        'boot_sha256': 'b' * 64, 'reboot_request_pending': True})
    qualification.checkpoint.assert_called_once_with('reboot-request-intent')
    assert result['reboot_request_pending'] and result['steps'] == []
    qualification.progress('reboot-requested', {'stage': 'reboot-requested',
        'boot_sha256': 'b' * 64, 'reboot_requested': True})
    assert not result['reboot_request_pending']
    assert result['steps'][0]['reboot_requested'] is True


@pytest.mark.parametrize('invalid', [False, True])
def test_reboot_diagnostics_are_durable_but_never_complete_a_stage(tmp_path, invalid):
    result = {'steps': []}
    qualification = smoke.Qualification(tmp_path, Mock(), Mock(), Mock(), result, {}, install=True)
    qualification.checkpoint = Mock()
    qualification.progress('reboot-observed', {'serial_input_drained': True})
    assert result['reboot_input_drained'] is True
    report = {'old_boot': 3, 'ssh_unavailable': 2, 'changed_boot': 0,
              'outcome': 'private-canary' if invalid else 'readiness-timeout'}
    if invalid:
        with pytest.raises(RuntimeError, match='diagnostic-condition'):
            qualification.progress('reboot-observed', {'reboot_diagnostic': report})
        assert 'reboot_diagnostic' not in result
    else:
        qualification.progress('reboot-observed', {'reboot_diagnostic': report})
        assert result['reboot_diagnostic'] == report
        qualification.checkpoint.assert_called_with('reboot-probe-finished')
    assert result['steps'] == [] and qualification.active_stage == 'reboot-observed'


@pytest.mark.parametrize('serial,authenticate,transfer_present', [
    (False, True, True), (True, False, True), (True, True, False),
])
def test_installation_requires_credentials_serial_and_bound_assets(tmp_path, serial, authenticate,
                                                                 transfer_present):
    boundary = Mock()
    with pytest.raises(RuntimeError, match='installation-prerequisites'):
        smoke.Smoke(tmp_path, Mock(), Mock(), 'host-key',
                    transfer=boundary.transfer if transfer_present else None,
                    serial=serial, authenticate=authenticate, installation=boundary)
