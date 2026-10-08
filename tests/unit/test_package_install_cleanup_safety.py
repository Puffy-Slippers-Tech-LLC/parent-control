"""LIFE04 composition refuses replay and incomplete or non-durable results."""

import json
from types import SimpleNamespace
from unittest.mock import MagicMock, Mock

import pytest

import check_e2e_package_command as check
import check_graphical_smoke as smoke
import package_install as install
import session_control
from owned_commands import CommandError
from private_artifacts import EvidenceError
from tests.support.desktop_session import RUN_PROBE
from tests.support.package_command import boundary
from tests.support.perl import run_perl


def test_fixed_launcher(monkeypatch):
    launch = Mock(return_value=0)
    monkeypatch.setattr(check, 'smoke', launch)
    assert check.main() == 0
    launch.assert_called_once_with(assets=check.ASSETS, provision_credentials=True,
                                  package_install=True)


@pytest.mark.parametrize('extra', [{}, {'install': True}, {'product_free_entry': True},
    {'package_authority': True}, {'challenges': True}, {'fresh_desktop': 'parent'}])
def test_exclusive_empty_baseline_required(extra):
    kwargs = dict(assets=check.ASSETS, provision_credentials=True, **extra) if extra else {}
    with pytest.raises(CommandError):
        smoke.main(package_install=True, **kwargs)


@pytest.mark.parametrize('fault', ['', 'transport', 'guard'])
def test_composition_never_resubmits_after_uncertain_input(monkeypatch, fault):
    command = boundary(monkeypatch)
    monkeypatch.setattr(install, 'PackageCommand', Mock(return_value=command))
    journey = SimpleNamespace(package=None, transport=command.transport,
        context=SimpleNamespace(verified=command.verified))
    guard = Mock(side_effect=[None, EvidenceError('lost-owner')] if fault == 'guard' else None)
    if fault == 'transport': command.transport.call.side_effect = TimeoutError()
    if fault:
        with pytest.raises((TimeoutError, EvidenceError)):
            install.submit_install(journey, guard)
    else:
        assert install.submit_install(journey, guard) == {'submitted': True}
    with pytest.raises(EvidenceError, match='package-install:replay'):
        install.submit_install(journey, Mock())
    assert command.transport.call.call_count == 1


@pytest.mark.parametrize('fault', ['', 'missing', 'failed', 'notice', 'durability'])
def test_result_checkpoint_requires_public_success_before_durable_ack(tmp_path, monkeypatch, fault):
    command = boundary(monkeypatch)
    progress = Mock(side_effect=OSError('evidence unavailable') if fault == 'durability' else None)
    journey = install.PackageInstallJourney(SimpleNamespace(directory=tmp_path,
        product_free=True, asset_transfer=Mock(), verified=command.verified), progress)
    monkeypatch.setattr(install, 'PackageCommand', Mock(return_value=command))
    journey.transport = command.transport
    journey.vm = SimpleNamespace(read=Mock(return_value={'boot_sha256': 'b' * 64}))
    if fault != 'missing': install.submit_install(journey, Mock())
    if fault == 'failed': command.receipt = (command.receipt[0], 1)
    if fault == 'notice': command.receipt = (b'command submitted\n', 0)
    journey.steps = [{'stage': stage} for stage in install.PLAN.stages[:-1]]
    monkeypatch.setattr(session_control, 'observe', Mock(return_value={'outcome': 'passed'}))
    (tmp_path / 'package-result.request.json').write_text(json.dumps(
        {'stage': 'package-result', 'screenshot': None}))
    if fault:
        with pytest.raises((EvidenceError, OSError)): journey.step(Mock())
        assert not (tmp_path / 'package-result.reply.json').exists()
        with pytest.raises(EvidenceError, match='previous-failure'): journey.step(Mock())
    else:
        journey.step(Mock())
        assert (tmp_path / 'package-result.reply.json').exists()
        observed = progress.call_args.args[1]
        assert observed['package']['exit_status'] == 0
        assert observed['assertion']['id'] == 'install-completed-with-reboot-notice'


@pytest.mark.parametrize('fault', ['', 'wrong-entry', 'command-context',
                                   'package-submitted', 'package-result'])
def test_worker_stops_at_failed_checkpoint(fault):
    source = RUN_PROBE.replace('require onpc_desktop_session;', 'require onpc_package_install;')
    source = source.replace('onpc_desktop_session::run', 'onpc_package_install::run')
    source = source.replace('}, $action);', '});')
    source = source.replace("push @events, ['stage', $_[0]];",
        "push @events, ['stage', $_[0]]; die 'fixed failure' if $_[0] eq $action;")
    result = json.loads(run_perl(source, fault).stdout)
    assert bool(result['ok']) == (not fault)
    stages = [event[1] for event in result['events'] if event[0] == 'stage']
    expected = list(install.PLAN.screen_tags)
    assert stages == (expected[:expected.index(fault) + 1] if fault else expected)
    if not fault: assert result['events'][-1] == ['power', 'off']


def test_unrelated_selector_and_missing_input_preparation(monkeypatch):
    from pathlib import Path
    import check_e2e_unrelated_reboot_request as selector
    import tools.test_commands as commands
    from tools.test_storage import named_input
    launch = Mock(return_value=0)
    monkeypatch.setattr(selector, 'smoke', launch)
    assert selector.main() == 0
    launch.assert_called_once_with(assets=selector.ASSETS, provision_credentials=True,
                                 unrelated_reboot_request=True)
    assert str(selector.ASSETS) == str(named_input(package_source=True))
    monkeypatch.setattr(commands.os.path, 'lexists', lambda _: False)
    allocate = Mock(return_value=str(selector.ASSETS))
    monkeypatch.setattr(commands, 'allocate_artifact_output', allocate)
    prepared = commands.qualification_artifact_command(Path.cwd(), 'integration',
        ['check_e2e_unrelated_reboot_request'])
    assert prepared[-1] == str(selector.ASSETS) and 'tools/build_test_artifacts.py' in prepared[2]
    allocate.assert_called_once_with(str(selector.ASSETS))


@pytest.mark.parametrize('extra', [{}, {'customer_reboot': True}, {'restart_notice': True},
    {'install': True}, {'kiosk_entry': True}])
def test_unrelated_selector_refuses_incompatible_modes(extra):
    kwargs = dict(assets=check.ASSETS, provision_credentials=True, **extra) if extra else {}
    with pytest.raises(CommandError): smoke.main(unrelated_reboot_request=True, **kwargs)


@pytest.mark.parametrize('fault', ['', 'unrelated-context', 'unrelated-submitted', 'unrelated-result',
                                  'reboot-installed-greeter'])
def test_unrelated_worker_plan_titles_and_refusal(fault):
    import unrelated_reboot
    plan = unrelated_reboot.PLAN
    source = RUN_PROBE.replace('require onpc_desktop_session;', 'require onpc_customer_reboot;')
    source = source.replace('onpc_desktop_session::run', 'onpc_customer_reboot::unrelated_request')
    declared = ','.join(repr(stage) for stage in plan.invocations)
    challenges = ','.join(repr(key) + '=>[' + ','.join(repr(value) for value in values) + ']'
                          for key, values in plan.challenges.items())
    source = source.replace('}, $action);', '}, [' + declared + '], {' + challenges + '});')
    source = source.replace('sub record_info { }', "sub record_info { push @main::events, ['title', $_[0]]; }")
    source = source.replace("push @events, ['stage', $_[0]];", """
        push @events, ['stage', $_[0]];
        die 'fixed refusal' if $_[0] eq $action;
        return {observed => $_[0], ui_focused => 1} if $_[0] eq 'reboot-installed-greeter';
        return {observed => $_[0], challenge => {id => 'after-reboot', role => 'parent',
            surface => 'gdm', check => $_[0] =~ /rechecked$/ ? 'rechecked' : 'qualified'}}
            if $_[0] =~ /^reboot-recipient-/;
    """)
    result = json.loads(run_perl(source, fault).stdout)
    assert bool(result['ok']) == (not fault)
    stages = [event[1] for event in result['events'] if event[0] == 'stage']
    expected = list(plan.screen_tags)
    assert stages == (expected[:expected.index(fault) + 1] if fault else expected)
    assert [event[1] for event in result['events'] if event[0] == 'title' and event[1] != 'shutdown'] == [
        plan.prefix + '-' + stage for stage in stages]
    if not fault: assert result['events'][-1] == ['title', 'shutdown']


def unrelated_boundary(tmp_path, monkeypatch, stage):
    import unrelated_reboot
    from parent_setup_qualification import UnrelatedRebootQualification
    progress = Mock()
    context = SimpleNamespace(directory=tmp_path, product_free=True, asset_transfer=Mock(), verified=Mock())
    journey = UnrelatedRebootQualification.journey(context, progress)
    assert isinstance(journey, unrelated_reboot.UnrelatedRebootJourney)
    journey.steps = [{'stage': item} for item in journey.plan.stages[:journey.plan.stages.index(stage)]]
    journey.transport = Mock()
    journey.vm = SimpleNamespace(read=Mock(return_value={'boot_sha256': 'b' * 64}))
    journey.boot = 'b' * 64
    journey.reboot_observed = True
    journey.package = Mock()
    monkeypatch.setattr(session_control, 'observe', Mock(return_value={'outcome': 'passed'}))
    (tmp_path / (stage + '.request.json')).write_text(json.dumps({'stage': stage, 'screenshot': None}))
    return journey, progress


@pytest.mark.parametrize('fault', ['', 'completion', 'identity', 'boot', 'request', 'durability'])
def test_unrelated_result_requires_independent_preservation_and_request_before_reply(tmp_path, monkeypatch, fault):
    journey, progress = unrelated_boundary(tmp_path, monkeypatch, 'unrelated-result')
    before = {'version': 'current', 'boot': 'b' * 64, 'session': '7', 'packages': {'current': 'a' * 64}}
    journey.unrelated_entry = before
    changed = {**before, **({'version': 'wrong'} if fault == 'identity' else
                           {'boot': 'c' * 64} if fault == 'boot' else {})}
    import package_command
    command = journey.unrelated_package = Mock(binding=package_command.UNRELATED, entry=before)
    command.read_identity.return_value = changed
    command.read_result.return_value = {'exit_status': 0}
    command.read_unrelated.return_value = {'system_reboot_required': True}
    if fault == 'completion': command.read_result.side_effect = EvidenceError('failed-command')
    if fault == 'request': command.read_unrelated.side_effect = EvidenceError('missing-request')
    if fault == 'durability': progress.side_effect = OSError('storage-failed')
    if fault:
        with pytest.raises((EvidenceError, OSError)): journey.step(Mock())
        assert not (tmp_path / 'unrelated-result.reply.json').exists()
        with pytest.raises(EvidenceError): journey.step(Mock())
    else:
        journey.step(Mock())
        assert (tmp_path / 'unrelated-result.reply.json').exists()
        value = progress.call_args.args[1]['unrelated_package']
        assert value['product_identity_unchanged'] and value['system']['system_reboot_required']


@pytest.mark.parametrize('fault', ['', 'activation', 'product', 'entry', 'durability'])
def test_unrelated_entry_independently_qualifies_clean_activation(tmp_path, monkeypatch, fault):
    import unrelated_reboot
    journey, progress = unrelated_boundary(tmp_path, monkeypatch, 'unrelated-context')
    command = Mock()
    command.package_identities.return_value = {'current': {'version': 'current'}}
    command.read_identity.return_value = {'version': 'wrong' if fault == 'product' else 'current',
                                          'boot': journey.boot}
    command.read_unrelated.return_value = {'system_reboot_required': False}
    monkeypatch.setattr(install, 'PackageCommand', Mock(return_value=command))
    if fault == 'activation': journey.reboot_observed = False
    if fault == 'entry': command.read_unrelated.side_effect = EvidenceError('preexisting-request')
    if fault == 'durability': progress.side_effect = OSError('storage-failed')
    if fault:
        with pytest.raises((EvidenceError, OSError)): journey.step(Mock())
        assert not (tmp_path / 'unrelated-context.reply.json').exists()
    else:
        journey.step(Mock())
        command.read_unrelated.assert_called_once_with(entry=True)
    journey.transport.call.assert_not_called()


def test_unrelated_plan_leaves_have_registered_operations():
    import accessible_ui
    import unrelated_reboot
    for tag in unrelated_reboot.PLAN.screen_tags.values():
        assert tag[3:] in accessible_ui.OPERATIONS if tag.startswith('ui:') else tag[7:] in session_control.BINDINGS


@pytest.mark.parametrize('fault', ['', 'transport', 'guard'])
def test_unrelated_shared_submission_retains_consumption_and_qualification_refusals(monkeypatch, fault):
    import package_command
    import unrelated_reboot
    command = boundary(monkeypatch)
    command.read_identity = Mock(return_value={'version': 'current'})
    command.package_identities = Mock(return_value={'current': {'version': 'current'}})
    command.read_unrelated = Mock()
    monkeypatch.setattr(install, 'PackageCommand', Mock(return_value=command))
    monkeypatch.setattr(unrelated_reboot, 'PackageCommand', Mock(return_value=command))
    journey = SimpleNamespace(unrelated_package=None, transport=command.transport,
        context=SimpleNamespace(verified=command.verified))
    guard = Mock(side_effect=[None, EvidenceError('lost-owner')] if fault == 'guard' else None)
    if fault == 'transport': command.transport.call.side_effect = TimeoutError()
    if fault:
        with pytest.raises((EvidenceError, TimeoutError)): unrelated_reboot.qualify_submission(journey, guard)
    else:
        value = unrelated_reboot.qualify_submission(journey, guard)
        assert value['refusals'] == ['unregistered', 'artifact', 'vm', 'attempt', 'replay']
    with pytest.raises(EvidenceError, match='replay'): install.submit_unrelated(journey, Mock())
    assert journey.unrelated_package is command and command.transport.call.call_count == 1


@pytest.mark.parametrize('fault', ['', 'provision', 'observation'])
def test_unrelated_installed_engine_real_recorder_provisions_after_restore(tmp_path, monkeypatch, fault):
    import asset_transfer
    import installed_journey
    import installed_setup
    plan = installed_journey.JourneyPlan(prefix='independent-unrelated', worker_mode='independent_unrelated',
        screen_tags={stage: 'system:parent-command-context' for stage in ('entry', 'submission', 'result')},
        phases={stage: 'setup' for stage in ('ready', 'setup-detached', 'entry', 'submission', 'result')},
        stage_actions={'submission': 'unrelated-package'})
    transfer = Mock()
    monkeypatch.setattr(asset_transfer, 'AssetTransfer', Mock(return_value=transfer))
    recorder = MagicMock()
    context = SimpleNamespace(directory=tmp_path, installed_snapshot='onpc-current', credentials=Mock(),
        verified=SimpleNamespace(inputs={}), lease=Mock(), guestfs=Mock(), commands=Mock(), host_key='key')
    context.lease.state = {'run': 'a' * 32}
    events = []
    transport = Mock()
    setup = Mock()
    setup.provision.side_effect = lambda guard: events.append('helpers')
    def provision(*args):
        events.append('assets')
        if fault == 'provision': raise EvidenceError('transfer-failed')
    def observe(*args):
        events.append('observation')
        if fault == 'observation': raise EvidenceError('observation-failed')
        return {'files': 2, 'sha256': 'a' * 64}
    transfer.provision_installed.side_effect = provision
    transfer.observe.side_effect = observe
    monkeypatch.setattr(installed_journey.system, 'address', Mock(return_value='guest'))
    monkeypatch.setattr(installed_journey, 'Transport', Mock(return_value=transport))
    monkeypatch.setattr(installed_setup, 'InstalledSetup', Mock(return_value=setup))
    vm = Mock()
    monkeypatch.setattr(installed_journey, 'ReadOnlyObservations', Mock(return_value=vm))
    def worker(**options):
        current = options['guarded_observe'].__self__
        assert isinstance(current, install.UnrelatedPackageJourney)
        assert current.plan is plan
        assert current.actions == {'unrelated-package': install.submit_unrelated}
        assert current.unrelated_entry_stage == 'entry'
        assert current.unrelated_result_stage == 'result'
        assert options['authenticate'] is True and options['timeout'] == 3600
        transfer.provision.assert_not_called()
        transfer.provision_installed.assert_not_called()
        assert context.asset_transfer is transfer and not getattr(context, 'product_free', False)
        events.append('restored')
        for stage in ('ready', 'setup-detached'):
            (tmp_path / (stage + '.request.json')).write_text(json.dumps({'stage': stage, 'screenshot': None}))
            if stage == 'setup-detached' and fault:
                with pytest.raises(EvidenceError): current.step(Mock())
                assert not (tmp_path / (stage + '.reply.json')).exists()
                with pytest.raises(EvidenceError): current.step(Mock())
                if fault == 'provision': transfer.observe.assert_not_called()
                break
            current.step(Mock())
        transfer.provision_installed.assert_called_once_with(context.lease, transport)
        assert events == (['restored', 'helpers', 'assets'] if fault == 'provision' else
                          ['restored', 'helpers', 'assets', 'observation'])
        if not fault:
            transfer.observe.assert_called_once_with(vm)
            assert json.loads((tmp_path / 'setup-detached.reply.json').read_text()) == {'setup_complete': True}
        raise RuntimeError('synthetic-worker-start')
    context.run_worker = worker
    with pytest.raises(RuntimeError, match='synthetic-worker-start'):
        installed_journey.record_installed_journey(recorder, context, plan, timeout=3600,
            actions={'unrelated-package': install.submit_unrelated},
            journey_type=install.unrelated_journey(entry='entry', result='result'))
    context.credentials.provision.assert_called_once()


@pytest.mark.parametrize('fault', ['', 'missing', 'identity', 'mutated-capture', 'request', 'durability'])
def test_unrelated_shared_engine_renamed_endpoints_and_immutable_entry(tmp_path, monkeypatch, fault):
    from installed_journey import JourneyPlan
    plan = JourneyPlan(prefix='independent-unrelated', worker_mode='independent_unrelated',
        screen_tags={stage: 'system:parent-command-context' for stage in ('entry', 'submission', 'result')},
        phases={stage: 'step-1' for stage in ('ready', 'setup-detached', 'entry', 'submission', 'result')},
        stage_actions={'submission': 'unrelated-package'})
    context = SimpleNamespace(directory=tmp_path, verified=Mock(), installed_snapshot=None)
    progress = Mock(side_effect=OSError('storage-failed') if fault == 'durability' else None)
    journey = install.unrelated_journey(entry='entry', result='result')(
        context, progress, plan, actions={'unrelated-package': install.submit_unrelated})
    journey.reboot_observed = True
    journey.boot = 'b' * 64
    journey.transport = Mock()
    journey.vm = SimpleNamespace(read=Mock(return_value={'boot_sha256': journey.boot}))
    before = {'version': 'current', 'boot': journey.boot, 'session': '7',
              'preserved': {'accounts': {'1000': {'language': 'en'}}}}
    command = Mock()
    command.package_identities.return_value = {'current': {'version': 'current'}}
    command.read_identity.return_value = before
    command.read_unrelated.return_value = {'system_reboot_required': False}
    monkeypatch.setattr(install, 'PackageCommand', Mock(return_value=command))
    journey.check_settings('entry', {})
    assert journey.unrelated_entry == before and journey.unrelated_entry is not before
    if fault == 'mutated-capture': before['preserved']['accounts']['1000']['language'] = 'changed'
    if fault == 'identity': command.read_identity.return_value = {**before, 'version': 'changed'}
    if fault == 'request': command.read_unrelated.side_effect = EvidenceError('missing-request')
    from package_command import UNRELATED
    command.binding, command.entry = UNRELATED, journey.unrelated_entry
    journey.unrelated_package = None if fault == 'missing' else command
    journey.steps = [{'stage': stage} for stage in plan.stages[:-1]]
    monkeypatch.setattr(session_control, 'observe', Mock(return_value={'outcome': 'passed'}))
    (tmp_path / 'result.request.json').write_text(json.dumps({'stage': 'result', 'screenshot': None}))
    if fault:
        with pytest.raises((EvidenceError, OSError)): journey.step(Mock())
        assert not (tmp_path / 'result.reply.json').exists()
        with pytest.raises(EvidenceError): journey.step(Mock())
    else:
        journey.step(Mock())
        assert (tmp_path / 'result.reply.json').exists()
        assert progress.call_args.args[1]['unrelated_package']['product_identity_unchanged']
        with pytest.raises(EvidenceError): journey.check_settings('result', {})
