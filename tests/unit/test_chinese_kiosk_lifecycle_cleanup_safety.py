"""Private UI/API/transport/recorder files and waited Perl, no live resources."""
import copy
from dataclasses import replace
import json
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock

import pytest
import accessible_ui
import account_language
import check_e2e_chinese_kiosk_lifecycle as selector
import check_graphical_smoke as smoke
import chinese_kiosk_lifecycle as lifecycle
import chinese_current_install as current
import check_e2e_chinese_current_install as current_selector
import installed_journey
import session_control
from owned_commands import CommandError
from private_artifacts import EvidenceError
from ui_observations import UiObservations
from tests.support.accessible_ui import Node, ui_for
from tests.support.desktop_session import RUN_PROBE
from tests.support.perl import run_perl
from tests.support.e2e_evidence import attempt
from tests.support.e2e_recording import session


def initial(kind):
    return {'kind': kind, 'child': 'other-fixture-child', 'input_free': True,
            'default_chinese': True if kind == 'language' else None,
            'texts': copy.deepcopy(lifecycle.NOTICE if kind == 'notice' else
                {**lifecycle.FORM, **(lifecycle.CHOOSER if kind == 'language' else {})})}


def tree(kind):
    form = Node(identity='kiosk-request-form', children=[
        Node(identity='kiosk-child-selected-1002'),
        *[Node(name=text, identity=identity) for identity, text in lifecycle.FORM.items()]])
    children = [form]
    if kind == 'notice':
        children.append(Node(identity='kiosk-result-child-1002'))
        children.append(Node(identity='update-required-dialog', children=[
            Node(name=text, identity=identity) for identity, text in lifecycle.NOTICE.items()]))
    elif kind == 'language':
        children.append(Node(identity='language-dialog', children=[
            *[Node(name=text, identity=identity) for identity, text in lifecycle.CHOOSER.items()],
            Node(identity='language-choice-zh-hans', states=('visible', 'sensitive', 'checked'))]))
    else:
        children.append(Node(identity='kiosk-language-ready'))
    window = Node(identity='kiosk-request-window', children=children)
    return ui_for(window), window, form


def owner(tmp_path, plan=lifecycle.PLAN, actions=None):
    context = SimpleNamespace(directory=tmp_path, product_free=True, asset_transfer=Mock(),
        verified=SimpleNamespace(upgrade_inputs={'packages': {}}, recheck=Mock()))
    return lifecycle.ChineseKioskJourney(context, Mock(), plan, actions=actions)


def test_selector_missing_generated_assets_and_shared_envelope(monkeypatch):
    import tools.test_commands as launchers
    from parent_setup_qualification import ChineseKioskLifecycleQualification, ProductFreeEntryQualification
    launch = Mock(return_value=0)
    monkeypatch.setattr(selector, 'smoke', launch)
    assert selector.main() == 0
    launch.assert_called_once_with(assets=selector.ASSETS, provision_credentials=True, chinese_kiosk_lifecycle=True)
    assert issubclass(ChineseKioskLifecycleQualification, ProductFreeEntryQualification)
    assert ChineseKioskLifecycleQualification.upgrade_assets
    monkeypatch.setattr(launchers.os.path, 'lexists', lambda _: False)
    monkeypatch.setattr(launchers, 'allocate_artifact_output', Mock(return_value=str(selector.ASSETS)))
    command = launchers.qualification_artifact_command(Path.cwd(), 'integration',
        ['check_e2e_chinese_kiosk_lifecycle'])
    assert '--upgrade-inputs' in command and command[-1] == str(selector.ASSETS)


def test_current_selector_prepares_only_source_bound_current_inputs(monkeypatch):
    import tools.test_commands as launchers
    from parent_setup_qualification import ChineseCurrentInstallQualification, ProductFreeEntryQualification
    launch = Mock(return_value=0)
    monkeypatch.setattr(current_selector, 'smoke', launch)
    assert current_selector.main() == 0
    launch.assert_called_once_with(assets=current_selector.ASSETS,
        provision_credentials=True, chinese_current_install=True)
    assert issubclass(ChineseCurrentInstallQualification, ProductFreeEntryQualification)
    assert not ChineseCurrentInstallQualification.upgrade_assets
    monkeypatch.setattr(launchers.os.path, 'lexists', lambda _: False)
    monkeypatch.setattr(launchers, 'allocate_artifact_output', Mock(return_value=str(current_selector.ASSETS)))
    command = launchers.qualification_artifact_command(Path.cwd(), 'integration',
        ['check_e2e_chinese_current_install'])
    assert '--upgrade-inputs' not in command and command[-1] == str(current_selector.ASSETS)


@pytest.mark.parametrize('extra', [{}, {'package_upgrade': True}, {'chinese_kiosk_lifecycle': True},
    {'desktop_language': True}, {'challenges': True}, {'install': True},
    {'fresh_desktop': 'parent'}, {'approval_flow': 'rejection'}])
def test_current_install_exclusive_gate(extra):
    args = {'assets': 'inputs', 'provision_credentials': True, **extra} if extra else {}
    with pytest.raises(CommandError): smoke.main(chinese_current_install=True, **args)


def test_current_declared_system_and_ui_operations_are_registered():
    from ui_observations import OPERATION_LABELS
    for operation in current.PLAN.screen_tags.values():
        if operation.startswith('ui:'):
            assert operation[3:] in OPERATION_LABELS
            continue
        binding = operation[7:]
        _, action = session_control.BINDINGS[binding]
        expected = {'operation': binding, 'outcome': 'passed', 'interface': 'system session'}
        expected.update({'administrator': True, 'package_sha256': 'a' * 64}
            if action == 'command-context' else
            {'source_retained': action != 'logout', 'destination': 'greeter'})
        transport = SimpleNamespace(call=Mock(return_value=json.dumps(expected).encode()))
        assert session_control.observe(transport, binding) == expected
        transport.call.assert_called_once()


@pytest.mark.parametrize('fault', ['', 'dual-inputs', 'wrong-version', 'durability'])
def test_current_install_result_comparison_precedes_durable_reply(tmp_path, monkeypatch, fault):
    context = SimpleNamespace(directory=tmp_path, product_free=True, asset_transfer=Mock(),
        verified=SimpleNamespace(upgrade_inputs={'packages': {}} if fault == 'dual-inputs' else None,
                                 inputs={'package_sha256': 'a' * 64}, recheck=Mock()))
    if fault == 'dual-inputs':
        with pytest.raises(EvidenceError, match='single-package-required'):
            current.ChineseCurrentInstallJourney(context, Mock())
        return
    progress = Mock(side_effect=OSError('storage') if fault == 'durability' else None)
    journey = current.ChineseCurrentInstallJourney(context, progress)
    stage = 'package-result'
    journey.steps = [{'stage': s} for s in journey.plan.stages[:journey.plan.stages.index(stage)]]
    journey.boot = 'b' * 64
    journey.vm = SimpleNamespace(read=Mock(return_value={'boot_sha256': journey.boot}))
    journey.transport = Mock()
    journey.transport.config = {'run': 'owned', 'domain_uuid': 'vm'}
    result = Mock(return_value={'independent_readback': True},
                  side_effect=EvidenceError('package-install:installed-version') if fault == 'wrong-version' else None)
    monkeypatch.setattr(current, 'observe_current_install', result)
    monkeypatch.setattr(current, 'refuse_input', Mock())
    monkeypatch.setattr(session_control, 'observe', Mock(return_value={'outcome': 'passed'}))
    journey.package, journey.install_entry = Mock(), {'version': None}
    (tmp_path / (stage + '.request.json')).write_text(json.dumps({'stage': stage, 'screenshot': None}))
    if fault:
        with pytest.raises((EvidenceError, OSError)): journey.step(Mock())
        assert not (tmp_path / (stage + '.reply.json')).exists()
    else:
        journey.step(Mock())
        result.assert_called_once_with(journey.package, journey.install_entry)
        assert (tmp_path / (stage + '.reply.json')).exists()
        assert progress.call_args.args[1]['assertion']['id'] == 'latest-install-version-notice-same-boot'


@pytest.mark.parametrize('extra', [{}, {'package_upgrade': True}, {'desktop_language': True},
    {'challenges': True}, {'install': True}, {'fresh_desktop': 'parent'}, {'approval_flow': 'rejection'}])
def test_exclusive_lifecycle_gate(extra):
    args = {'assets': 'inputs', 'provision_credentials': True, **extra} if extra else {}
    with pytest.raises(CommandError): smoke.main(chinese_kiosk_lifecycle=True, **args)


@pytest.mark.parametrize('kind', ['notice', 'language', 'form'])
@pytest.mark.parametrize('fault', ['', 'child', 'duplicate', 'stale', 'owner', 'incomplete'])
def test_initial_public_reader_has_no_setup_input_and_refuses_wrong_evidence(kind, fault):
    ui, window, form = tree(kind)
    ui.complete_language_setup = Mock(side_effect=AssertionError('premature language setup'))
    selected = window.children[1] if kind == 'notice' else form.children[0]
    prefix = 'kiosk-result-child-' if kind == 'notice' else 'kiosk-child-selected-'
    if fault == 'child': selected.identity = prefix + '1001'
    if fault == 'duplicate':
        parent = window if kind == 'notice' else form
        duplicate = Node(identity=prefix + '1002'); duplicate.parent = parent
        parent.children.append(duplicate)
    if fault == 'stale': form.states.add('defunct')
    if fault == 'owner': window.parent.identity = accessible_ui.PARENT_APPLICATION
    if fault == 'incomplete': form.get_child_count = lambda: 10001
    if fault:
        with pytest.raises(accessible_ui.UiError): ui.initial_kiosk_presentation(kind)
    else:
        assert ui.initial_kiosk_presentation(kind) == initial(kind)
    ui.complete_language_setup.assert_not_called()
    assert all(node.action.do_action.call_count == 0 for node in form.children)


def test_english_chooser_cannot_displace_notice():
    ui, _, _ = tree('language')
    with pytest.raises(accessible_ui.UiError, match='notice-displaced'):
        ui.initial_kiosk_presentation('notice')


@pytest.mark.parametrize('fault', ['', 'locale', 'uncertain'])
def test_notice_close_fresh_proof_single_use_and_result(fault):
    ui, window, _ = tree('notice')
    dialog = window.children[-1]
    button = dialog.children[1]
    if fault == 'locale': dialog.children[0].name = 'Restart in English'
    def close(_):
        if fault == 'uncertain': return False
        window.children.remove(dialog)
        result = Node(identity='kiosk-result-action'); result.parent = window
        window.children.append(result)
        return True
    button.action.do_action.side_effect = close
    if fault:
        with pytest.raises(accessible_ui.UiError): ui.close_initial_notice()
        assert button.action.do_action.call_count == int(fault == 'uncertain')
        if fault == 'uncertain':
            with pytest.raises(accessible_ui.UiError): ui.close_initial_notice()
            assert button.action.do_action.call_count == 1
    else:
        assert ui.close_initial_notice() == initial('notice')
        assert button.action.do_action.call_count == 1 and not ui.input_uncertain


@pytest.mark.parametrize('fault', ['', 'default', 'multiple'])
def test_chooser_default_observed_without_candidate_input(fault):
    ui, window, _ = tree('language')
    chooser = window.children[-1]
    candidate = chooser.children[-1]
    if fault == 'default':
        candidate.states.remove('checked')
        english = Node(identity='language-choice-en', states=('visible', 'checked'))
        english.parent = chooser; chooser.children.append(english)
    if fault == 'multiple':
        english = Node(identity='language-choice-en', states=('visible', 'checked'))
        english.parent = chooser; chooser.children.append(english)
    if fault == 'multiple':
        with pytest.raises(accessible_ui.UiError, match='initial-selection'): ui.initial_kiosk_presentation('language')
    else:
        assert ui.initial_kiosk_presentation('language')['default_chinese'] == (fault != 'default')
    candidate.action.do_action.assert_not_called()


@pytest.mark.parametrize('operation', ['kiosk-initial-notice', 'kiosk-initial-language', 'kiosk-initial-form'])
@pytest.mark.parametrize('fault', ['', 'extra', 'child', 'large', 'kind'])
def test_real_controller_decoder_bounds_shape_and_realistic_output(operation, fault):
    kind = operation.removeprefix('kiosk-initial-')
    value = initial(kind)
    if fault == 'extra': value['private'] = 'forbidden'
    if fault == 'child': value['child'] = 'fixture-child'
    if fault == 'kind': value['kind'] = 'wrong'
    if fault == 'large': value['texts'][next(iter(value['texts']))] = 'x' * 513
    result = {'operation': operation, 'outcome': 'passed', 'interface': 'AT-SPI', 'initial': value}
    raw = (json.dumps(result, ensure_ascii=False) + '\n').encode()
    def call(argv, **options):
        for offset in range(0, len(raw), 7): options['on_output'](raw[offset:offset + 7])
        return raw
    transport = SimpleNamespace(call=Mock(side_effect=call), commands=SimpleNamespace(progress=None))
    ui = UiObservations(transport)
    if fault:
        with pytest.raises(EvidenceError): ui.observe(operation)
    else:
        assert ui.observe(operation) == result
        assert b'initial_kiosk_presentation' in transport.call.call_args.kwargs['input']


@pytest.mark.parametrize('operation', ['kiosk-initial-notice-close', 'kiosk-initial-notice-return',
                                     'kiosk-initial-language-cancel'])
def test_premature_modal_input_refused_before_transport(operation):
    transport = SimpleNamespace(call=Mock())
    with pytest.raises(EvidenceError, match='initial-input-order'):
        UiObservations(transport).observe(operation)
    transport.call.assert_not_called()


@pytest.mark.parametrize('fault', ['', 'boot', 'context', 'unobserved-first', 'uncertain', 'storage'])
def test_second_reboot_is_separately_consumed_and_durable(tmp_path, monkeypatch, fault):
    journey = owner(tmp_path)
    stage = 'second-reboot-requested'
    journey.steps = [{'stage': s} for s in journey.plan.stages[:journey.plan.stages.index(stage)]]
    journey.boot = 'b' * 64
    journey.reboot_submitted = True
    journey.reboot_observed = fault != 'unobserved-first'
    journey.vm = SimpleNamespace(read=Mock(return_value={'boot_sha256': 'c' * 64 if fault == 'boot' else journey.boot}))
    journey.transport = Mock()
    def submit(boot):
        assert json.loads((tmp_path / 'customer-reboot-2-intent.json').read_text()) == {
            'stage': stage, 'previous_boot_sha256': boot}
        if fault == 'uncertain': raise TimeoutError()
    journey.transport.request_customer_reboot.side_effect = submit
    monkeypatch.setattr(session_control, 'observe', Mock(return_value={'outcome': 'passed'},
        side_effect=EvidenceError('wrong-context') if fault == 'context' else None))
    if fault == 'storage': (tmp_path / 'customer-reboot-2-intent.json').touch()
    (tmp_path / (stage + '.request.json')).write_text(json.dumps({'stage': stage, 'screenshot': None}))
    if fault:
        with pytest.raises((EvidenceError, TimeoutError, FileExistsError)): journey.step(Mock())
        assert not (tmp_path / (stage + '.reply.json')).exists()
    else:
        journey.step(Mock())
        assert (tmp_path / (stage + '.reply.json')).exists()
    with pytest.raises(EvidenceError): journey.submit_reboot(Mock())
    assert journey.transport.request_customer_reboot.call_count == int(fault in ('', 'uncertain'))


@pytest.mark.parametrize('fault', ['', 'not-submitted', 'same-boot', 'third-boot', 'gdm', 'durability'])
def test_second_changed_boot_invalidates_ui_and_gates_reply(tmp_path, monkeypatch, fault):
    journey = owner(tmp_path)
    stage = 'second-reboot-greeter'
    journey.steps = [{'stage': s} for s in journey.plan.stages[:journey.plan.stages.index(stage)]]
    journey.boot = 'b' * 64
    journey.reboot_submitted = journey.reboot_observed = True
    if fault != 'not-submitted': journey.additional_reboots_submitted.add(1)
    stale = journey.ui = Mock()
    changed = 'b' * 64 if fault == 'same-boot' else 'c' * 64
    journey.vm = SimpleNamespace(wait_boot_change=Mock(return_value={
        'boot_changed': True, 'previous_boot_sha256': journey.boot, 'boot_sha256': changed}))
    fresh = Mock(boot_proof='d' * 64 if fault == 'third-boot' else changed)
    fresh.observe = Mock(return_value={'outcome': 'passed'},
        side_effect=EvidenceError('no-gdm') if fault == 'gdm' else None)
    monkeypatch.setattr(installed_journey, 'UiObservations', Mock(return_value=fresh))
    if fault == 'durability': journey.progress.side_effect = OSError('storage')
    (tmp_path / (stage + '.request.json')).write_text(json.dumps({'stage': stage, 'screenshot': None}))
    if fault:
        with pytest.raises((EvidenceError, OSError)): journey.step(Mock())
        assert not (tmp_path / (stage + '.reply.json')).exists()
    else:
        journey.step(Mock())
        assert journey.boot == changed and 1 in journey.additional_reboots_observed
        fresh.observe.assert_called_once_with('gdm-list')
    stale.observe.assert_not_called()


@pytest.mark.parametrize('transition', [(('second-reboot-requested', 'initial-form'),),
    (('reboot-requested', 'reboot-installed-greeter'),), ['second-reboot-requested', 'second-reboot-greeter']])
def test_additional_transition_must_be_adjacent_ordered_and_unique(transition):
    with pytest.raises(EvidenceError, match='reboot-plan'):
        replace(lifecycle.PLAN, additional_reboot_transitions=transition)


@pytest.mark.parametrize('plan,method,fault', [
    (plan, method, fault) for plan, method in (
        (lifecycle.PLAN, 'run_chinese'), (current.PLAN, 'run_chinese_current'))
    for fault in ('', *plan.screen_tags)])
def test_actual_worker_order_titles_and_refusal_before_later_input(plan, method, fault):
    source = RUN_PROBE.replace('require onpc_desktop_session;', 'require onpc_customer_reboot;')
    source = source.replace('onpc_desktop_session::run', 'onpc_customer_reboot::' + method)
    declarations = json.dumps(list(plan.invocations))
    challenges = json.dumps(plan.challenges)
    source = source.replace('}, $action);', f"}}, decode_json(q~{declarations}~), decode_json(q~{challenges}~));")
    source = source.replace("push @events, ['stage', $_[0]];", """
        push @events, ['stage', $_[0]];
        die 'refusal' if $_[0] eq $action;
        return {observed => $_[0], ui_focused => 1} if $_[0] =~ /(?:greeter|list)$/;
        return {observed => $_[0], station_destination => 'initial-request-window'} if $_[0] =~ /station-branch$/;
        my %bindings = ('reboot' => ['after-reboot', 'parent'], 'language-standard' => ['chinese-child', 'other-child'],
            'upgrade' => ['upgrade-parent', 'parent'], 'install' => ['install-parent', 'parent'],
            'return' => ['return-parent', 'parent']);
        for my $prefix (keys %bindings) {
            if ($_[0] =~ /^$prefix-recipient-/) {
                return {observed => $_[0], challenge => {id => $bindings{$prefix}[0], role => $bindings{$prefix}[1],
                    surface => 'gdm', check => $_[0] =~ /rechecked$/ ? 'rechecked' : 'qualified'}};
            }
        }
    """)
    source = source.replace('sub record_info { }', "sub record_info { push @main::events, ['title', $_[0]]; }")
    result = json.loads(run_perl(source, fault).stdout)
    assert bool(result['ok']) == (not fault)
    expected = list(plan.screen_tags)
    if fault: expected = expected[:expected.index(fault) + 1]
    assert [event[1] for event in result['events'] if event[0] == 'stage'] == expected
    assert [event[1] for event in result['events'] if event[0] == 'title' and event[1] != 'shutdown'] == [
        plan.prefix + '-' + stage for stage in expected]
    if not fault:
        assert result['events'].count(['secret']) == 1 + len(plan.challenges)
        assert ['power', 'off'] in result['events']


@pytest.mark.parametrize('fault', ['', 'changed', 'missing', 'replay', 'mutated-original'])
def test_initial_capture_comparisons_are_immutable_and_operation_bound(tmp_path, fault):
    journey = owner(tmp_path)
    first = initial('notice')
    journey.check_settings('initial-notice', {'ui': {'initial': first}})
    if fault == 'mutated-original': first['texts'].clear()
    if fault == 'missing': journey.initial_captures.clear()
    if fault == 'replay':
        with pytest.raises(EvidenceError, match='capture-replay'):
            journey.check_settings('initial-notice', {'ui': {'initial': initial('notice')}})
        return
    value = initial('notice')
    if fault == 'changed': value['texts']['update-required-close'] = 'Close'
    if fault in ('changed', 'missing'):
        with pytest.raises(EvidenceError): journey.check_settings('initial-notice-close', {'ui': {'initial': value}})
    else:
        journey.check_settings('initial-notice-close', {'ui': {'initial': value}})
        assert journey.initial_captures['ui:kiosk-initial-notice']['texts'] == lifecycle.NOTICE


@pytest.mark.parametrize('kind', ['historical', 'current'])
@pytest.mark.parametrize('fault', ['', 'meaning', 'durability'])
def test_real_recorder_constructor_and_comparison_before_durable_reply(session, tmp_path, monkeypatch, fault, kind):
    declared = lifecycle.PLAN if kind == 'historical' else current.PLAN
    journey_type = lifecycle.ChineseKioskJourney if kind == 'historical' else current.ChineseCurrentInstallJourney
    expected = session.payload['assertions'][0]
    tags = {'entry-start': 'system:parent-command-context', 'entry-one': 'system:parent-command-context',
            'entry-two': 'system:parent-command-context', 'renamed-notice': 'ui:kiosk-initial-notice'}
    plan = replace(declared, screen_tags=tags, phases={'ready': 'setup', 'setup-detached': 'setup',
        'entry-start': 'start', 'entry-one': 'step-1', 'entry-two': 'step-2', 'renamed-notice': expected['step_id']},
        stage_actions={}, assertions_after={'renamed-notice': expected['assertion_id']},
        invocations=(), challenges={}, reboot_transition=(), additional_reboot_transitions=(), advance_after={})
    context = SimpleNamespace(directory=tmp_path / 'journey', product_free=True, asset_transfer=Mock(),
        verified=SimpleNamespace(inputs={}, upgrade_inputs={'packages': {}} if kind == 'historical' else None),
        credentials=Mock(), lease=Mock(), guestfs=Mock(), commands=Mock())
    context.directory.mkdir()
    recorder = session.recorder
    recorder.begin_case('E2E-001/gdm-observation')
    real_save = session.collector.save_report
    def save(name, report):
        if fault == 'durability' and report.get('event') == 'observation' and report.get('active_step') == expected['step_id']:
            raise OSError('storage failed')
        return real_save(name, report)
    monkeypatch.setattr(session.collector, 'save_report', save)
    monkeypatch.setattr(session_control, 'observe', Mock(return_value={'outcome': 'passed'}))
    def worker(**options):
        journey = options['guarded_observe'].__self__
        assert isinstance(journey, journey_type)
        journey.steps = [{'stage': 'ready'}, {'stage': 'setup-detached'}]
        journey.boot = 'a' * 64
        journey.vm = SimpleNamespace(read=Mock(return_value={'boot_sha256': journey.boot}))
        value = initial('notice')
        if fault == 'meaning': value['texts']['update-required-close'] = 'Close'
        journey.ui = SimpleNamespace(boot_proof=journey.boot,
            observe=Mock(return_value={'outcome': 'passed', 'initial': value}))
        journey.transport = Mock()
        for stage in tags:
            (context.directory / (stage + '.request.json')).write_text(json.dumps({'stage': stage, 'screenshot': None}))
            options['guarded_observe'](Mock())
            assert (context.directory / (stage + '.reply.json')).exists()
        for assertion in session.payload['assertions'][1:]:
            ref = recorder.artifact('synthetic-' + assertion['assertion_id'],
                {'visible': 'screen', 'backend': 'backend', 'other_user': 'other-user'}[assertion['kind']],
                b'explicit synthetic result', reviewed=True)
            recorder.assertion(assertion['assertion_id'], artifact_ids=[ref])
        return dict(outcome='passed', shutdown_verified=True, worker_stopped=True, callback_closed=True)
    context.run_worker = worker
    monkeypatch.setattr(journey_type, 'validate', lambda _: [])
    if fault:
        with pytest.raises((EvidenceError, OSError)):
            installed_journey.record_installed_journey(recorder, context, plan, actions={}, journey_type=journey_type)
        assert not (context.directory / 'renamed-notice.reply.json').exists()
    else:
        installed_journey.record_installed_journey(recorder, context, plan, actions={}, journey_type=journey_type)


def test_installed_account_read_does_not_accept_product_free_receipt():
    receipt = {'accounts': {'1002': {'name': session_control.ACCOUNTS['standard'], 'language': 'en'}},
        'target_uid': '1002', 'sessions': {}, 'system_locale': [], 'observer_locale': {}, 'product_free': True}
    transport = SimpleNamespace(config={'run': 'owned'}, guard=Mock(),
        call=Mock(return_value=(json.dumps(receipt, sort_keys=True) + '\n').encode()))
    controller = account_language.AccountLanguage(transport, SimpleNamespace(recheck=Mock()), product_free=False)
    with pytest.raises(EvidenceError, match='read-schema'): controller.read()
    assert transport.call.call_args.args[0][3] == 'read-installed'


@pytest.mark.parametrize('language', ['zh_CN', 'zh_CN.UTF-8'])
@pytest.mark.parametrize('fault', ['', 'other-account', 'file', 'boot', 'version', 'readback',
                                 'missing-renewal', 'wrong-language', 'wrong-confirmation', 'identity'])
def test_renewed_upgrade_entry_preserves_everything_but_declared_language_and_session(tmp_path, monkeypatch, fault, language):
    journey = owner(tmp_path)
    before = {'boot': 'b' * 64, 'version': 'genuine-old', 'session': '7', 'packages': {'old': 'digest'},
        'preserved': {'accounts': {'1002': {'language': 'en'}, '1000': {'language': 'en'}},
                      'files': {'witness': 'digest'}, 'system_locale': ['LANG=en']}}
    current = copy.deepcopy(before)
    current['session'] = '9'
    current['preserved']['accounts']['1002']['language'] = language
    journey.activated_entry = copy.deepcopy(before)
    journey.language_uid = '1002'
    journey.language_confirmation = {'confirmed_language': 'zh_CN'}
    journey.chinese_desktop = None if fault == 'missing-renewal' else {'locale': 'zh_CN.UTF-8'}
    journey.boot = before['boot']
    journey.transport = Mock()
    if fault == 'other-account': current['preserved']['accounts']['1000']['language'] = 'zh_CN'
    if fault == 'file': current['preserved']['files']['witness'] = 'changed'
    if fault == 'boot': current['boot'] = 'c' * 64
    if fault == 'version': current['version'] = 'current-too-soon'
    if fault == 'wrong-language': current['preserved']['accounts']['1002']['language'] = 'zh_TW.UTF-8'
    if fault == 'wrong-confirmation': journey.language_confirmation['confirmed_language'] = 'en'
    if fault == 'identity': current['preserved']['accounts']['1002']['identity'] = 'replaced'
    second = copy.deepcopy(current)
    if fault == 'readback': second['session'] = '10'
    command = SimpleNamespace(read_identity=Mock(side_effect=[current, second]))
    monkeypatch.setattr(lifecycle, 'PackageCommand', Mock(return_value=command))
    if fault:
        with pytest.raises(EvidenceError): lifecycle.language_upgrade_entry(journey, Mock())
        assert journey.activated_entry == before
    else:
        assert lifecycle.language_upgrade_entry(journey, Mock())['preservation_verified']
        assert journey.activated_entry == current
        current['preserved']['files'].clear()
        assert journey.activated_entry['preserved']['files'] == before['preserved']['files']


@pytest.mark.parametrize('fault', ['', 'uncertain', 'preservation'])
def test_installed_setting_reuses_single_setter_and_refuses_replay(tmp_path, monkeypatch, fault):
    journey = owner(tmp_path)
    journey.activated_entry = {'real': 'activation'}
    journey.transport = Mock()
    before = {'target_uid': '1002', 'accounts': {'1002': {'language': 'en'}}}
    controller = SimpleNamespace(identity={'run': 'owned'}, read=Mock(return_value=before),
        command=Mock(return_value={'wrong_account_refused': True, 'undeclared_locale_refused': True}),
        submit=Mock(side_effect=TimeoutError() if fault == 'uncertain' else None),
        confirm=Mock(return_value={'confirmed_language': 'zh_CN'},
                     side_effect=EvidenceError('changed-account') if fault == 'preservation' else None))
    monkeypatch.setattr(lifecycle, 'AccountLanguage', Mock(return_value=controller))
    if fault:
        with pytest.raises((TimeoutError, EvidenceError)): lifecycle.set_account_language(journey, Mock())
    else:
        assert lifecycle.set_account_language(journey, Mock())['confirmed_language'] == 'zh_CN'
    with pytest.raises(EvidenceError, match='setting-replay'): lifecycle.set_account_language(journey, Mock())
    controller.submit.assert_called_once_with(lifecycle.ROLE, lifecycle.LOCALE, controller.identity)


@pytest.mark.parametrize('language,name,passes', [('en', 'Activities', True),
    ('zh-Hans', '活动', True), ('zh-Hans', 'Activities', False), ('en', '活动', False)])
def test_chinese_desktop_requires_actual_public_translated_shell_control(language, name, passes):
    panel = Node(name, 'toggle button')
    shell = Node('gnome-shell', 'application', children=[panel])
    ui = ui_for(Node(role='desktop frame', children=[shell]))
    result = ui.shell_desktop_observation(no_prompt=True, language=language)
    assert (result is not None) == passes
    panel.action.do_action.assert_not_called()


@pytest.mark.parametrize('fault', ['', 'absent', 'no-package'])
def test_installed_account_guest_mode_requires_real_package_and_state(monkeypatch, fault):
    import account_language_guest as guest
    import pwd
    user = pwd.struct_passwd(('onpc-child-jordan', 'x', 1002, 1002, '', '/synthetic', '/bin/bash'))
    api = Mock(resolve=Mock(return_value=(guest.ROOT + '/User1002', 'en')))
    monkeypatch.setattr(guest.os, 'geteuid', lambda: 0)
    monkeypatch.setattr(guest, 'accounts', lambda: [user])
    monkeypatch.setattr(guest.pwd, 'getpwnam', lambda _: user)
    monkeypatch.setattr(guest.os.path, 'lexists', lambda _: fault != 'absent')
    monkeypatch.setattr(guest.sessions, 'call', lambda _: '' if fault == 'no-package' else 'oh-no-parent-control\n')
    monkeypatch.setattr(guest.sessions, 'sessions', lambda: {})
    monkeypatch.setattr(guest, 'system_locale', lambda: ['LANG=en'])
    if fault:
        with pytest.raises(guest.LanguageError, match='installed-product-required'):
            guest.execute('read-installed', guest.ROLE, guest.LOCALE, api)
    else:
        assert guest.execute('read-installed', guest.ROLE, guest.LOCALE, api)['product_free'] is False
        with pytest.raises(guest.LanguageError, match='product-state-present'):
            guest.execute('read', guest.ROLE, guest.LOCALE, api)
