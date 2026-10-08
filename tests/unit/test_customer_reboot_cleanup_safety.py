"""Planned reboot authority, durable intent, boot continuity and fresh login."""

from dataclasses import replace
import json
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

import check_e2e_customer_reboot as check
import check_graphical_smoke as smoke
import customer_reboot as reboot
import installed_journey as journeys
import session_control
from owned_commands import CommandError
from private_artifacts import EvidenceError
from tests.support.desktop_session import RUN_PROBE
from tests.support.perl import run_perl


BEFORE, AFTER = 'a' * 64, 'b' * 64


def boundary(tmp_path, monkeypatch, stage='reboot-requested'):
    progress = Mock()
    journey = reboot.CustomerRebootJourney(SimpleNamespace(directory=tmp_path,
        product_free=True, asset_transfer=Mock()), progress)
    journey.steps = [{'stage': item} for item in reboot.PLAN.stages[:reboot.PLAN.stages.index(stage)]]
    journey.boot = BEFORE
    journey.transport = Mock()
    journey.vm = SimpleNamespace(read=Mock(return_value={'boot_sha256': BEFORE}),
        wait_boot_change=Mock(return_value={'previous_boot_sha256': BEFORE,
            'boot_sha256': AFTER, 'boot_changed': True}))
    journey.ui = Mock()
    monkeypatch.setattr(session_control, 'observe', Mock(return_value={
        'operation': 'parent-command-context', 'outcome': 'passed'}))
    (tmp_path / (stage + '.request.json')).write_text(json.dumps({'stage': stage, 'screenshot': None}))
    return journey, progress


def test_fixed_launcher(monkeypatch):
    launch = Mock(return_value=0)
    monkeypatch.setattr(check, 'smoke', launch)
    assert check.main() == 0
    launch.assert_called_once_with(assets=check.ASSETS, provision_credentials=True, customer_reboot=True)


@pytest.mark.parametrize('extra', [{}, {'install': True}, {'product_free_entry': True},
    {'package_authority': True}, {'package_install': True}, {'challenges': True}])
def test_exclusive_product_free_entry(extra):
    kwargs = dict(assets=check.ASSETS, provision_credentials=True, **extra) if extra else {}
    with pytest.raises(CommandError): smoke.main(customer_reboot=True, **kwargs)


@pytest.mark.parametrize('transition', [('missing', 'reboot-installed-greeter'),
    ('package-result', 'reboot-installed-greeter'), ('reboot-requested', 'reboot-desktop'),
    ['reboot-requested', 'reboot-installed-greeter']])
def test_only_adjacent_declared_command_and_gdm_transition_allowed(transition):
    with pytest.raises(EvidenceError, match='reboot-plan'):
        replace(reboot.PLAN, reboot_transition=transition)


@pytest.mark.parametrize('fault', ['', 'transport', 'guard', 'boot', 'context', 'intent'])
def test_submission_records_intent_before_one_input_and_never_replays(tmp_path, monkeypatch, fault):
    journey, progress = boundary(tmp_path, monkeypatch)
    def submit(boot):
        assert boot == BEFORE
        assert json.loads((tmp_path / 'customer-reboot-intent.json').read_text()) == {
            'stage': 'reboot-requested', 'previous_boot_sha256': BEFORE}
        if fault == 'transport': raise TimeoutError()
    journey.transport.request_customer_reboot.side_effect = submit
    if fault == 'boot': journey.vm.read.return_value = {'boot_sha256': AFTER}
    if fault == 'context': session_control.observe.side_effect = EvidenceError('wrong-context')
    if fault == 'intent': (tmp_path / 'customer-reboot-intent.json').write_text('preserve')
    guard = Mock(side_effect=EvidenceError('lost-owner') if fault == 'guard' else None)
    if fault:
        with pytest.raises((EvidenceError, TimeoutError, FileExistsError)): journey.step(guard)
        with pytest.raises(EvidenceError, match='previous-failure'): journey.step(Mock())
        assert not (tmp_path / 'reboot-requested.reply.json').exists()
    else:
        journey.step(guard)
        assert (tmp_path / 'reboot-requested.reply.json').exists()
        assert progress.call_args.args[1]['reboot']['submitted']
        with pytest.raises(EvidenceError): journey.submit_reboot(Mock())
    assert journey.transport.request_customer_reboot.call_count == (fault in ('', 'transport'))


def test_live_wrong_entry_probe_refuses_reboot_before_transport(tmp_path, monkeypatch):
    journey, _ = boundary(tmp_path, monkeypatch, 'wrong-entry')
    result = reboot.refuse_reboot(journey, Mock())
    assert result['reboot_refused'] is True
    journey.transport.request_customer_reboot.assert_not_called()
    assert not (tmp_path / 'customer-reboot-intent.json').exists()


@pytest.mark.parametrize('fault', ['', 'unsubmitted', 'unchanged', 'changed-again', 'gdm', 'durability'])
def test_new_boot_requires_fresh_gdm_and_durable_result(tmp_path, monkeypatch, fault):
    journey, progress = boundary(tmp_path, monkeypatch, 'reboot-installed-greeter')
    stale = journey.ui
    fresh = Mock()
    fresh.boot_proof = 'c' * 64 if fault == 'changed-again' else AFTER
    fresh.observe.return_value = {'operation': 'gdm-list', 'outcome': 'passed'}
    monkeypatch.setattr(journeys, 'UiObservations', Mock(return_value=fresh))
    journey.reboot_submitted = fault != 'unsubmitted'
    journey.vm.read.return_value = {'boot_sha256': 'c' * 64 if fault == 'changed-again' else AFTER}
    if fault == 'unchanged': journey.vm.wait_boot_change.side_effect = EvidenceError('unchanged')
    if fault == 'gdm': fresh.observe.side_effect = EvidenceError('no-gdm')
    if fault == 'durability': progress.side_effect = OSError('storage failed')
    if fault:
        with pytest.raises((EvidenceError, OSError)): journey.step(Mock())
        assert not (tmp_path / 'reboot-installed-greeter.reply.json').exists()
        with pytest.raises(EvidenceError, match='previous-failure'): journey.step(Mock())
    else:
        journey.step(Mock())
        observed = progress.call_args.args[1]
        assert observed['boot_transition']['boot_sha256'] == AFTER
        assert observed['assertion']['id'] == 'changed-boot-usable-gdm'
        assert journey.boot == AFTER
        fresh.observe.assert_called_once_with('gdm-list')
    stale.observe.assert_not_called()
    journey.transport.request_customer_reboot.assert_not_called()


def test_unexpected_later_reboot_still_refuses(tmp_path, monkeypatch):
    journey, _ = boundary(tmp_path, monkeypatch, 'reboot-parent-focused')
    journey.reboot_submitted = journey.reboot_observed = True
    journey.vm.read.return_value = {'boot_sha256': AFTER}
    journey.ui.observe.side_effect = EvidenceError('ui:boot-changed')
    with pytest.raises(EvidenceError, match='boot-changed'): journey.step(Mock())
    journey.vm.wait_boot_change.assert_not_called()
    journey.ui.observe.assert_called_once_with('gdm-focused')
    assert journey.ui.boot_guard == BEFORE
    journey.vm.read.assert_not_called()


@pytest.mark.parametrize('fault', ['', 'reboot-requested', 'reboot-installed-greeter',
    'reboot-recipient-rechecked', 'reboot-desktop'])
def test_worker_uses_two_fresh_secret_proofs_and_stops_on_refusal(fault):
    source = RUN_PROBE.replace('require onpc_desktop_session;', 'require onpc_customer_reboot;')
    source = source.replace('onpc_desktop_session::run', 'onpc_customer_reboot::run')
    source = source.replace('}, $action);', "}, [qw(reboot-installed-greeter reboot-parent-focused "
        "reboot-recipient-qualified reboot-recipient-rechecked reboot-desktop)], "
        "{'after-reboot' => ['parent', 'reboot-recipient-qualified', 'reboot-recipient-rechecked']});")
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
    expected = list(reboot.PLAN.screen_tags)
    stages = [event[1] for event in result['events'] if event[0] == 'stage']
    assert stages == (expected[:expected.index(fault) + 1] if fault else expected)
    if not fault:
        assert result['events'].count(['secret']) == 2
        assert result['events'][-1] == ['power', 'off']


@pytest.mark.parametrize('surface', ['parent', 'overlay', 'kiosk'])
@pytest.mark.parametrize('fault', ['', 'input', 'boot', 'intent', 'proof'])
def test_modal_reboot_intent_and_single_use(tmp_path, monkeypatch, surface, fault):
    journey, progress = boundary(tmp_path, monkeypatch)
    journey.plan = replace(reboot.PLAN,
        screen_tags={**reboot.PLAN.screen_tags, 'reboot-requested': 'ui:restart-' + surface + '-read'},
        modal_reboots={'reboot-requested': surface})
    journey.ui.boot_proof = BEFORE if fault != 'proof' else AFTER
    journey.ui.observe.return_value = {'operation': 'restart-' + surface + '-read', 'outcome': 'passed'}
    def activate(selected):
        assert selected == surface
        assert journey.reboot_submitted
        assert json.loads((tmp_path / 'customer-reboot-intent.json').read_text()) == {
            'stage': 'reboot-requested', 'previous_boot_sha256': BEFORE,
            'route': 'ApplicationUI', 'surface': surface}
        if fault == 'input':
            raise TimeoutError()
        return {'surface': surface, 'status': 'acknowledged'}
    journey.ui.submit_restart.side_effect = activate
    if fault == 'boot': journey.vm.read.return_value = {'boot_sha256': AFTER}
    if fault == 'intent': (tmp_path / 'customer-reboot-intent.json').write_text('preserve')
    if fault:
        with pytest.raises((EvidenceError, TimeoutError, FileExistsError)):
            journey.step(Mock())
        assert not (tmp_path / 'reboot-requested.reply.json').exists()
    else:
        journey.step(Mock())
        assert progress.call_args.args[1]['reboot']['status'] == 'acknowledged'
    with pytest.raises(EvidenceError): journey.submit_reboot(Mock())
    assert journey.ui.submit_restart.call_count == (fault in ('', 'input'))
    journey.transport.request_customer_reboot.assert_not_called()


@pytest.mark.parametrize('binding', [{'missing': 'parent'}, {'reboot-requested': 'foreign'},
                                   {'reboot-requested': 'parent'}])
def test_modal_route_requires_matching_read_stage(binding):
    with pytest.raises(EvidenceError, match='reboot-plan'):
        replace(reboot.PLAN, modal_reboots=binding)


@pytest.mark.parametrize('fault', ['', 'disconnect', 'prequalified-disconnect', 'malformed',
    'wrong-boot', 'wrong-surface', 'replayed', 'partial', 'refusal', 'missing-receipt', 'owner'])
def test_modal_terminal_transport_preserves_qualified_uncertainty(fault):
    from ui_observations import UiObservations
    transport = Mock()
    transport.commands.last_returncode = 255 if 'disconnect' in fault else 1 if fault == 'refusal' else 0
    ui = UiObservations(transport)
    ui.boot_guard = BEFORE
    ready = {'event': 'restart-input-qualified', 'surface': 'kiosk', 'boot_sha256': BEFORE}
    receipt = {'surface': 'kiosk', 'status': 'acknowledged', 'boot_sha256': BEFORE}
    if fault == 'wrong-boot': ready['boot_sha256'] = AFTER
    if fault == 'wrong-surface': ready['surface'] = 'parent'
    raw = json.dumps(ready).encode() + b'\n'
    if fault not in ('disconnect', 'prequalified-disconnect', 'missing-receipt'):
        raw += json.dumps(receipt).encode() + b'\n'
    if fault == 'prequalified-disconnect': raw = b''
    if fault == 'malformed': raw = b'{}\n'
    if fault == 'replayed': raw += json.dumps(receipt).encode() + b'\n'
    if fault == 'partial': raw = raw[:-1]
    def execute(argv, **kwargs):
        if fault == 'owner': raise EvidenceError('ownership-lost')
        assert kwargs['check'] is False
        for offset in range(0, len(raw), 7): kwargs['on_output'](raw[offset:offset + 7])
    transport.call.side_effect = execute
    if fault in ('', 'disconnect'):
        value = json.loads(ui.restart_call(['fixed'], 'restart-kiosk-reboot', input=b'fixed'))
        assert value == {'surface': 'kiosk', 'boot_sha256': BEFORE,
                         'status': 'uncertain' if fault else 'acknowledged'}
    else:
        with pytest.raises(EvidenceError): ui.restart_call(['fixed'], 'restart-kiosk-reboot', input=b'fixed')
    transport.call.assert_called_once()


def test_modal_submission_cannot_retry_after_any_transport_failure():
    from ui_observations import UiObservations
    ui = UiObservations(Mock())
    ui.boot_guard = ui.boot_proof = BEFORE
    ui._observe = Mock(side_effect=TimeoutError())
    with pytest.raises(TimeoutError): ui.submit_restart('kiosk')
    with pytest.raises(EvidenceError): ui.submit_restart('kiosk')
    ui._observe.assert_called_once_with('restart-kiosk-reboot')


def test_restart_selector_and_generated_preparation(monkeypatch):
    from pathlib import Path
    import check_e2e_restart_notice as selector
    import tools.test_commands as commands
    launch = Mock(return_value=0)
    monkeypatch.setattr(selector, 'smoke', launch)
    assert selector.main() == 0
    launch.assert_called_once_with(assets=selector.ASSETS, provision_credentials=True, restart_notice=True)
    from tools.test_storage import named_input
    assert str(selector.ASSETS) == str(named_input(package_source=True))
    monkeypatch.setattr(commands.os.path, 'lexists', lambda _: False)
    allocate = Mock(return_value=str(selector.ASSETS))
    monkeypatch.setattr(commands, 'allocate_artifact_output', allocate)
    command = commands.qualification_artifact_command(Path.cwd(), 'integration', ['check_e2e_restart_notice'])
    assert command[-1] == str(selector.ASSETS)
    assert 'tools/build_test_artifacts.py' in command[2]
    allocate.assert_called_once_with(str(selector.ASSETS))


@pytest.mark.parametrize('extra', [{}, {'customer_reboot': True}, {'chinese_current_install': True},
                                   {'parent_rtl': True}, {'kiosk_entry': True}])
def test_restart_selector_exclusive_gate(extra):
    import check_e2e_restart_notice as selector
    kwargs = dict(assets=selector.ASSETS, provision_credentials=True, **extra) if extra else {}
    with pytest.raises(CommandError): smoke.main(restart_notice=True, **kwargs)


@pytest.mark.parametrize('fault', ['', 'parent-notice', 'parent-close', 'overlay-reentry',
                                  'reboot-requested', 'reboot-greeter', 'postboot-riley-selected',
                                  'postboot-riley-configured', 'postboot-jamie-selected',
                                  'postboot-jamie-configured', 'usable-overlay', 'usable-kiosk'])
def test_restart_worker_exact_composition_and_refusal(fault):
    import restart_notice
    plan = restart_notice.PLAN
    source = RUN_PROBE.replace('require onpc_desktop_session;', 'require onpc_customer_reboot;')
    source = source.replace('onpc_desktop_session::run', 'onpc_customer_reboot::restart_notice')
    declared = ','.join(repr(stage) for stage in plan.invocations)
    challenges = ','.join(repr(key) + '=>[' + ','.join(repr(value) for value in values) + ']'
                          for key, values in plan.challenges.items())
    source = source.replace('}, $action);', '}, [' + declared + '], {' + challenges + '});')
    source = source.replace('sub record_info { }', "sub record_info { push @main::events, ['title', $_[0]]; }")
    source = source.replace("push @events, ['stage', $_[0]];", """
        push @events, ['stage', $_[0]];
            die 'fixed refusal' if $_[0] eq $action;
            return {observed => $_[0], ui_focused => 1}
                if $_[0] =~ /^(?:child-|return-).*installed-greeter$/;
            return {observed => $_[0], station_destination =>
            $_[0] eq 'station-branch' ? 'default-request-form' : 'initial-request-window'}
            if $_[0] =~ /station-branch$/;
        my ($id, $role) = $_[0] =~ /^child-return-/ ? ('child-return', 'child') :
            $_[0] =~ /^child-/ ? ('child', 'child') : ('return', 'parent');
        return {observed => $_[0], challenge => {id => $id, role => $role,
            surface => 'gdm', check => $_[0] =~ /rechecked$/ ? 'rechecked' : 'qualified'}}
            if $_[0] =~ /^(?:child-|return-).*recipient-(?:qualified|rechecked)$/;
    """)
    result = json.loads(run_perl(source, fault).stdout)
    assert bool(result['ok']) == (not fault)
    stages = [event[1] for event in result['events'] if event[0] == 'stage']
    expected = list(plan.screen_tags)
    assert stages == (expected[:expected.index(fault) + 1] if fault else expected)
    assert [event[1] for event in result['events'] if event[0] == 'title' and event[1] != 'shutdown'] == [
        plan.prefix + '-' + stage for stage in stages]
    if not fault:
        assert [event for event in result['events'] if event[0] != 'title'][-1] == ['power', 'off']
        assert result['events'][-1] == ['title', 'shutdown']
        assert result['events'].count(['secret']) == 4


@pytest.mark.parametrize('surface', ['parent', 'kiosk', 'overlay'])
@pytest.mark.parametrize('fault', ['', 'missing', 'duplicate', 'wrong-owner', 'language',
                                  'policy', 'disabled', 'not-modal'])
def test_restart_public_id_owner_and_input_refusals(monkeypatch, surface, fault):
    import accessible_ui as adapter
    import restart_notice
    from tests.support.accessible_ui import Node, ui_for
    controls = [Node(identity=identity, name=text, role='label' if identity.endswith('message') else 'button')
                for identity, text in restart_notice.NOTICE.items()]
    if fault == 'disabled': controls[-1].states.remove('sensitive')
    modal = Node(identity='update-required-dialog', children=controls,
                 states=('visible', 'showing', 'sensitive', *(() if fault == 'not-modal' else ('modal',))))
    children = [] if fault == 'missing' else [modal]
    if fault == 'duplicate': children.append(Node(identity='update-required-dialog'))
    if fault == 'language': children.append(Node(identity='language-dialog'))
    if surface == 'parent':
        if fault == 'policy': children.append(Node(identity='parent-window'))
    else:
        children.append(Node(identity='kiosk-result-child-1001'))
        if fault == 'policy': children.append(Node(identity='kiosk-request-form'))
        children = [Node(identity='kiosk-request-window', children=children)]
    app = {'parent': adapter.PARENT_APPLICATION, 'kiosk': adapter.KIOSK_APPLICATION,
           'overlay': adapter.CHILD_APPLICATION}[surface]
    if fault == 'wrong-owner': app = adapter.KIOSK_APPLICATION if surface == 'parent' else adapter.PARENT_APPLICATION
    ui = ui_for(Node(identity=app, children=children))
    monkeypatch.setattr(ui, 'require_child_overlay_session', lambda: None)
    ui._invoke_target = Mock()
    if fault in ('missing', 'wrong-owner'):
        assert ui.restart_notice(surface, wait=False) is None
        with pytest.raises(adapter.UiError, match='restart-missing'): ui.restart_action(surface, 'close')
    elif fault:
        with pytest.raises(adapter.UiError): ui.restart_action(surface, 'close')
    else:
        assert ui.restart_notice(surface, wait=False) == {'surface': surface, 'texts': restart_notice.NOTICE,
                                                        'modal': True, 'policy_blocked': True}
        ui.restart_action(surface, 'close')
        if surface == 'parent':
            ui.restart_operation('parent', 'wrong-owner')
    assert ui._invoke_target.call_count == (not fault)


@pytest.mark.parametrize('stage', ['parent-notice', 'parent-reentry', 'overlay-notice',
                                 'overlay-reentry', 'kiosk-notice', 'kiosk-reentry', 'reboot-requested'])
@pytest.mark.parametrize('wrong_text', [False, True])
def test_restart_installed_text_comparison_precedes_durable_reply(tmp_path, stage, wrong_text):
    import restart_notice
    progress = Mock()
    journey = restart_notice.RestartNoticeJourney(SimpleNamespace(directory=tmp_path,
        product_free=True, asset_transfer=Mock()), progress)
    journey.steps = [{'stage': item} for item in journey.plan.stages[:journey.plan.stages.index(stage)]]
    journey.boot = BEFORE
    journey.transport = Mock()
    journey.vm = SimpleNamespace(read=Mock(return_value={'boot_sha256': BEFORE}))
    journey.ui = Mock(boot_proof=BEFORE)
    journey.ui.submit_restart.return_value = {'surface': 'kiosk', 'status': 'acknowledged'}
    texts = dict(restart_notice.NOTICE)
    if wrong_text:
        texts['update-required-message'] = 'Unrelated restart request'
    journey.ui.observe.return_value = {'restart': {'texts': texts}}
    (tmp_path / (stage + '.request.json')).write_text(json.dumps({'stage': stage, 'screenshot': None}))
    if wrong_text:
        with pytest.raises(EvidenceError, match='installed-instructions'):
            journey.step(Mock())
        assert not (tmp_path / (stage + '.reply.json')).exists()
        journey.ui.submit_restart.assert_not_called()
    else:
        journey.step(Mock())
        assert (tmp_path / (stage + '.reply.json')).is_file()


def test_restart_decoder_and_actual_isolated_payload():
    import subprocess
    import sys
    import restart_notice
    from ui_observations import UiObservations
    transport = Mock()
    value = {'operation': 'restart-parent-read', 'outcome': 'passed',
             'interface': 'ApplicationUI+external-provider', 'boot_sha256': BEFORE,
             'restart': {'surface': 'parent', 'texts': restart_notice.NOTICE,
                         'modal': True, 'policy_blocked': True}}
    transport.call.return_value = json.dumps(value).encode()
    ui = UiObservations(transport)
    ui.boot_guard = BEFORE
    assert ui.observe('restart-parent-read')['restart'] == value['restart']
    payload = transport.call.call_args.kwargs['input']
    process = subprocess.run([sys.executable, '-I', '-', 'invalid-operation', '1.0'], input=payload,
                             capture_output=True, timeout=30)
    assert process.returncode != 0 and b'ui:arguments' in process.stderr
    assert b'ModuleNotFoundError' not in process.stderr
    value['restart']['surface'] = 'kiosk'
    transport.call.return_value = json.dumps(value).encode()
    with pytest.raises(EvidenceError, match='restart-response'): ui.observe('restart-parent-read')


@pytest.mark.parametrize('surface', ['parent', 'kiosk', 'overlay'])
@pytest.mark.parametrize('modal_present', [False, True])
def test_restart_postboot_usability_requires_complete_modal_absence(monkeypatch, surface, modal_present):
    import accessible_ui as adapter
    from tests.support.accessible_ui import Node, ui_for
    controls = ([Node(identity='parent-language-ready'), Node(identity='parent-child-selector')]
                if surface == 'parent' else [Node(identity='kiosk-language-ready'),
                    Node(identity='kiosk-request-form', children=[Node(identity='kiosk-request-submit'),
                        Node(identity='kiosk-child-selected-1001')])])
    if modal_present:
        controls.append(Node(identity='update-required-dialog'))
    window = Node(identity='parent-window' if surface == 'parent' else 'kiosk-request-window',
                  children=controls)
    app = {'parent': adapter.PARENT_APPLICATION, 'kiosk': adapter.KIOSK_APPLICATION,
           'overlay': adapter.CHILD_APPLICATION}[surface]
    ui = ui_for(Node(identity=app, children=[window]))
    ui.fixture_uids = {adapter.CHILD: 1001}
    monkeypatch.setattr(ui, 'require_child_overlay_session', lambda: None)
    ui._invoke_target = Mock()
    if modal_present:
        with pytest.raises(adapter.UiError):
            ui.restart_usable(surface)
    else:
        ui.restart_usable(surface)
    ui._invoke_target.assert_not_called()


def test_restart_plan_every_leaf_registered():
    import accessible_ui
    import restart_notice
    for tag in restart_notice.PLAN.screen_tags.values():
        assert tag[3:] in accessible_ui.OPERATIONS if tag.startswith('ui:') else tag[7:] in session_control.BINDINGS


def test_restart_enabled_request_preparation_follows_reboot():
    import restart_notice
    from journey_blocks import custom_child_selection
    from ui_observations import SettingsObservation
    plan = restart_notice.PLAN
    stages = list(plan.screen_tags)
    for prefix, child, identity in (('postboot-riley', 'child', 'fixture-child'),
                                     ('postboot-jamie', 'existing', 'existing-fixture-child')):
        selection = custom_child_selection(prefix, child)
        configured = prefix + '-configured'
        assert {stage: plan.screen_tags[stage] for stage in selection} == selection
        assert plan.screen_tags[configured] == 'ui:time-explanation-setup-thirty-read'
        assert plan.child_bindings[configured] == child
        assert plan.settings_checks[prefix + '-selected'] == SettingsObservation(
            identity, False, ('0 minutes',))
        assert stages.index('missing-notice-refused') < stages.index(prefix + '-open')
        assert stages.index(prefix + '-selected') < stages.index(configured)
        assert stages.index(configured) < stages.index('return-parent-logout')
    assert stages.index('return-parent-logout') < stages.index('usable-overlay-launch')
    assert stages.index('usable-overlay') < stages.index('usable-kiosk')
