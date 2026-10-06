"""Private public-tree/decoder/recorder doubles and waited Perl; no live owners."""
from copy import deepcopy
from dataclasses import replace
import json
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock

import pytest
import accessible_ui as public
import check_e2e_chinese_native_auth as selector
import check_graphical_smoke as smoke
import chinese_native_auth as auth
import installed_journey
import session_control
from owned_commands import CommandError
from private_artifacts import EvidenceError
from tests.support.accessible_ui import Node, ui_for
from tests.support.e2e_kiosk import request_form, WORKER
from tests.support.perl import run_perl
from tests.support.e2e_evidence import attempt
from tests.support.e2e_recording import session
from ui_observations import UiObservations


def native_tree():
    # Independent mate-polkit 1.26.1 zh_CN catalogue projection. Its dialog
    # selects the super-user explanation for one identity other than the
    # agent's user (Jamie authenticates in the station-owned kiosk session).
    # Do not derive the fixture from the adapter's expected strings: doing so
    # hid the original same-user versus other-user explanation defect.
    texts = {
        'recipient': 'onpc-parent-jamie 的密码(P)：',
        'message': '允许 Jordan (Child) 访问吗？\n请求时长：1 分钟、15 秒。\n'
                   '在本次授权期间允许使用可临时解除封锁的应用。',
        'cancel': '取消(C)', 'authenticate': '授权(A)',
        'explanation': '一个程序正试图执行一个需要特权的动作。要求授权为超级用户来执行该动作。',
    }
    field = Node(role='password text', states=('showing', 'visible', 'sensitive', 'focused'))
    field.get_text_iface = lambda: SimpleNamespace(length=0)
    field.get_child_count = Mock(side_effect=AssertionError('protected descendants'))
    field.get_description = Mock(side_effect=AssertionError('protected description'))
    labels = {key: Node(texts[key], 'label') for key in ('message', 'recipient', 'explanation')}
    cancel, submit = (Node(texts[key], 'push button') for key in ('cancel', 'authenticate'))
    dialog = Node(role='dialog', children=[*labels.values(), field, cancel, submit])
    agent = Node('mate-polkit', 'application', children=[dialog])
    desktop = Node(role='desktop frame', children=[agent])
    ui = ui_for(desktop)
    ui.api.Text = SimpleNamespace(get_character_count=lambda text: text.length)
    ui.mate_agent_pid = Mock(return_value=100)
    ui.mate_challenge_identity = Mock(return_value='a' * 64)
    ui.mate_agent_identity = Mock(return_value='b' * 64)
    ui.mate_provider_metadata = Mock(return_value={'version': '1.26.1-6', 'locale': 'zh_CN.UTF-8',
                                                  'keyboard': [['xkb', 'us']]})
    return ui, field, labels, cancel, submit, agent, dialog


def prompt_receipt(identity='a' * 64, agent='b' * 64, opening=True):
    return {'challenge_id': identity, 'agent_id': agent, 'texts': public.chinese_mate_texts(),
        'provider': {'version': '1.26.1-6', 'locale': 'zh_CN.UTF-8', 'keyboard': [['xkb', 'us']]},
        'child': 'existing-fixture-child', 'approver': 'fixture-parent', 'duration_seconds': 75,
        'allow_soft': True, 'rejected_proofs': list(public.CHINESE_MATE_REFUSALS) if opening else []}


def initial():
    return {'kind': 'form', 'child': 'other-fixture-child', 'texts': deepcopy(auth.FORM),
            'default_chinese': None, 'input_free': True}


def test_selector_snapshot_and_automatic_inputs(monkeypatch, tmp_path):
    from parent_setup_qualification import ChineseNativeAuthQualification, KioskEntryQualification
    import tools.test_commands as commands
    launch = Mock(return_value=0)
    monkeypatch.setattr(selector, 'smoke', launch)
    assert selector.main() == 0
    launch.assert_called_once_with(assets=selector.ASSETS, provision_credentials=True, chinese_native_auth=True)
    journey = ChineseNativeAuthQualification.journey(SimpleNamespace(directory=tmp_path), Mock())
    assert journey.plan is auth.PLAN
    assert ChineseNativeAuthQualification.attach_installed_snapshot is KioskEntryQualification.attach_installed_snapshot
    monkeypatch.setattr(commands.os.path, 'lexists', lambda _: False)
    allocate = Mock(return_value=str(selector.ASSETS))
    monkeypatch.setattr(commands, 'allocate_artifact_output', allocate)
    command = commands.qualification_artifact_command(Path.cwd(), 'integration', ['check_e2e_chinese_native_auth'])
    assert command[-1] == str(selector.ASSETS)
    allocate.assert_called_once_with(str(selector.ASSETS))


@pytest.mark.parametrize('extra', [{}, {'chinese_kiosk_lifecycle': True}, {'kiosk_approved_flow': True},
    {'challenges': True}, {'install': True}, {'fresh_desktop': 'parent'}, {'approval_flow': 'rejection'}])
def test_exclusive_mode_refuses_before_vm(extra):
    args = {'assets': 'inputs', 'provision_credentials': True, **extra} if extra else {}
    with pytest.raises(CommandError): smoke.main(chinese_native_auth=True, **args)


@pytest.mark.parametrize('fault', ['', 'recipient', 'message', 'explanation', 'authenticate', 'cancel',
    'hidden', 'disabled', 'unfocused', 'nonempty', 'stale', 'owner', 'multiple', 'replacement'])
def test_actual_chinese_prompt_guard_and_refusals(fault):
    ui, field, labels, cancel, submit, agent, dialog = native_tree()
    if fault in labels: labels[fault].name = 'English or incorrect request'
    if fault == 'authenticate': submit.name = 'Authenticate'
    if fault == 'cancel': cancel.name = 'Cancel'
    if fault == 'hidden': field.states.discard('showing'); field.states.discard('visible')
    if fault == 'disabled': field.states.discard('sensitive')
    if fault == 'unfocused': field.states.discard('focused')
    if fault == 'nonempty': field.get_text_iface = lambda: SimpleNamespace(length=1)
    if fault == 'stale': field.states.add('defunct')
    if fault == 'owner': agent.get_process_id = lambda: 999
    if fault == 'multiple':
        second = Node(role='password text'); second.parent = dialog; dialog.children.append(second)
    challenge = (agent, dialog, cancel, field) if fault == 'replacement' else None
    if fault:
        with pytest.raises(public.UiError): ui.mate_prompt(100, language='zh-Hans', challenge=challenge)
    else:
        proof = ui.mate_prompt(100, language='zh-Hans')
        assert proof == (agent, dialog, field, cancel)
        assert ui.mate_prompt_refusals(100, proof, language='zh-Hans') == list(public.CHINESE_MATE_REFUSALS)
        with pytest.raises(public.UiError): ui.mate_prompt(100)
    cancel.action.do_action.assert_not_called(); submit.action.do_action.assert_not_called()
    field.get_child_count.assert_not_called(); field.get_description.assert_not_called()


@pytest.mark.parametrize('explanation', [
    '一个程序正试图执行一个需要特权的动作。要求授权以执行该动作。',
    '一个程序正试图执行一个需要特权的动作。要求授权为下列用户之一来执行该动作。',
])
def test_chinese_kiosk_refuses_other_native_explanation_branches(explanation):
    ui, field, labels, cancel, submit, _, _ = native_tree()
    ui.expected_mate_challenge = 'a' * 64
    labels['explanation'].name = explanation
    with pytest.raises(public.UiError, match='ui:mate-native-explanation'):
        ui.kiosk_mate_approval('chinese-mate-qualified')
    assert ui.input_uncertain
    cancel.action.do_action.assert_not_called(); submit.action.do_action.assert_not_called()
    field.get_child_count.assert_not_called(); field.get_description.assert_not_called()


@pytest.mark.parametrize('fault', ['', 'replacement', 'locale', 'uncertain', 'missing-success'])
def test_guarded_chinese_approval_same_challenge_and_single_submission(fault):
    ui, field, labels, cancel, submit, _, _ = native_tree()
    ui.expected_mate_challenge = 'c' * 64 if fault == 'replacement' else 'a' * 64
    if fault == 'locale': ui.mate_provider_metadata.return_value['locale'] = 'en_US.UTF-8'
    if fault in ('replacement', 'locale'):
        with pytest.raises(public.UiError): ui.kiosk_mate_approval('chinese-mate-rechecked')
        submit.action.do_action.assert_not_called()
        return
    assert ui.kiosk_mate_approval('chinese-mate-rechecked') == prompt_receipt(opening=False)
    field.get_text_iface = lambda: SimpleNamespace(length=12)
    submit.action.do_action.return_value = fault != 'uncertain'
    ui.kiosk_approval_success = Mock(return_value={'approved': True, 'form_success': True},
        side_effect=public.UiError('missing-public-result') if fault == 'missing-success' else None)
    if fault:
        with pytest.raises(public.UiError): ui.kiosk_mate_approval('chinese-mate-submit-success')
    else:
        assert ui.kiosk_mate_approval('chinese-mate-submit-success') == {'approved': True, 'form_success': True}
        ui.kiosk_approval_success.assert_called_once_with(immediate=False, language='zh-Hans')
    with pytest.raises(public.UiError): ui.kiosk_mate_approval('chinese-mate-submit-success')
    submit.action.do_action.assert_called_once(); cancel.action.do_action.assert_not_called()


def test_nondefault_chinese_request_uses_public_identity_and_translation():
    ui, durations = request_form()
    form = ui.find_id('kiosk-request-form')
    form.children.remove(ui.find_id('kiosk-screen-limit-notice'))
    for node in form.children: node.states.add('sensitive')
    child = ui.find_id('kiosk-child-selector')
    child.description = '已选择的账户：Jordan (Child)。'
    approver = ui.find_id('kiosk-approver-selector')
    approver.children[0].identity = 'kiosk-approver-selected-1000'
    approver.description = '已选择的账户：Jamie (Parent)。'
    durations[2].states.discard('pressed'); durations[-1].states.add('pressed')
    custom = Node(identity='kiosk-custom-duration', states=('showing', 'visible', 'sensitive', 'editable'))
    custom.get_text_iface = lambda: SimpleNamespace(value='1.25')
    ui.api.Text = SimpleNamespace(get_character_count=lambda text: len(text.value),
                                  get_text=lambda text, a, b: text.value[a:b])
    status = Node('获批后预计可用时间：1分钟 15秒', 'label', identity='kiosk-request-status')
    for node in (custom, status): node.parent = form; form.children.append(node)
    soft = ui.find_id('kiosk-soft-apps-toggle')
    soft.action.do_action.side_effect = lambda _: soft.states.add('checked') or True
    result = ui.run('chinese-fraction-soft-select', '')
    observer = UiObservations(SimpleNamespace())
    observer.call = Mock(return_value=(json.dumps(result).encode(), []))
    assert observer.observe('chinese-fraction-soft-select') == result
    assert result['valid_choice']['request']['child'] == 'existing-fixture-child'
    assert result['valid_choice']['estimate']['seconds'] == 75
    assert 'text-chinese-kiosk-fraction-focus' in public.KIOSK_SESSION_OPERATIONS
    ui.find_id('kiosk-request-submit').action.do_action.assert_not_called()


@pytest.mark.parametrize('title', ['请求已获批准', 'Request approved', '请求已被拒绝'])
def test_actual_chinese_public_approval_result(title):
    label = Node(title, 'label', identity='kiosk-result-title')
    page = Node(identity='kiosk-result-page', children=[label])
    window = Node(identity='kiosk-request-window', children=[page])
    ui = ui_for(Node(role='application', identity=public.KIOSK_APPLICATION, children=[window]))
    ui.system_prompt_kind = Mock(return_value=None)
    if title == '请求已获批准':
        assert ui.kiosk_approval_success(language='zh-Hans') == {'approved': True, 'form_success': True}
    else:
        with pytest.raises(public.UiError, match='ui:kiosk-approval-result'):
            ui.kiosk_approval_success(language='zh-Hans')


@pytest.mark.parametrize('fault', ['', 'reused', 'wrong-text', 'wrong-child', 'wrong-locale', 'intervening', 'early-reentry'])
def test_real_decoder_two_fresh_challenges_and_terminal_refusal(fault):
    observer = UiObservations(SimpleNamespace())
    count = 0
    def call(argv, operation, **options):
        nonlocal count
        value = {'operation': operation, 'outcome': 'passed', 'interface': 'ApplicationUI+external-provider'}
        if operation in public.CHINESE_MATE_ORDER:
            if operation.endswith('open'): count += 1
            if operation.endswith('submit-success'):
                value['approval'] = {'approved': True, 'form_success': True}
            else:
                value['approval'] = prompt_receipt('a' * 64 if count == 1 or fault == 'reused' else 'c' * 64,
                    'b' * 64 if count == 1 else 'd' * 64, operation.endswith('open'))
                if fault == 'wrong-text': value['approval']['texts']['authenticate'] = 'Authenticate'
                if fault == 'wrong-child': value['approval']['child'] = 'fixture-child'
                if fault == 'wrong-locale': value['approval']['provider']['locale'] = 'en_US.UTF-8'
        if operation == 'chinese-persisted-form': value['initial'] = initial()
        if len(argv) == 7: value['boot_sha256'] = 'e' * 64
        return json.dumps(value, ensure_ascii=False).encode(), []
    observer.call = Mock(side_effect=call)
    if fault == 'early-reentry':
        with pytest.raises(EvidenceError): observer.observe('chinese-persisted-form')
        observer.call.assert_not_called(); return
    if fault in ('wrong-text', 'wrong-child', 'wrong-locale'):
        with pytest.raises(EvidenceError): observer.observe('chinese-mate-open')
        with pytest.raises(EvidenceError): observer.observe('chinese-mate-qualified')
        assert observer.call.call_count == 1; return
    observer.observe('chinese-mate-open')
    if fault == 'intervening':
        with pytest.raises(EvidenceError): observer.observe('desktop')
        with pytest.raises(EvidenceError): observer.observe('chinese-mate-qualified')
        assert observer.call.call_count == 1; return
    for operation in public.CHINESE_MATE_ORDER[1:]: observer.observe(operation)
    observer.observe('gdm-station-returned')
    observer.observe('chinese-persisted-form')
    if fault == 'reused':
        with pytest.raises(EvidenceError, match='challenge-replay'): observer.observe('chinese-mate-open')
    else:
        for operation in public.CHINESE_MATE_ORDER: observer.observe(operation)
        assert {'a' * 64, 'c' * 64} <= observer.challenges


@pytest.mark.parametrize('fault', ['', *auth.PLAN.screen_tags])
def test_real_worker_order_titles_and_no_input_after_refusal(monkeypatch, fault):
    if fault: monkeypatch.setenv('ONPC_TEST_REFUSE_STAGE', fault)
    worker = WORKER.replace('onpc_kiosk_eligible_choices', 'onpc_request_flow')
    worker = worker.replace('onpc_request_flow::run', 'onpc_request_flow::chinese_native_auth')
    worker = worker.replace("$stage eq 'station-branch'", "$stage =~ /station-branch\\z/")
    worker = worker.replace('sub record_info { }', "sub record_info { push @main::events, ['title', $_[0]] }\nsub type_string { push @main::events, ['text', $_[0]] }")
    result = json.loads(run_perl(worker).stdout)
    expected = list(auth.PLAN.screen_tags)
    if fault: expected = expected[:expected.index(fault) + 1]
    assert bool(result['ok']) == (not fault), result['error']
    assert [event[1] for event in result['events'] if event[0] == 'stage'] == expected
    assert [event[1] for event in result['events'] if event[0] == 'title' and event[1] != 'shutdown'] == [
        'chinese-native-auth-' + stage for stage in expected]
    if not fault: assert result['events'].count(['secret']) == 3


@pytest.mark.parametrize('stage', ['first-approval-qualified', 'first-approval-rechecked',
                                 'second-approval-qualified', 'second-approval-rechecked'])
def test_real_chinese_worker_mismatched_receipt_refuses_secret(stage):
    worker = WORKER.replace('onpc_kiosk_eligible_choices', 'onpc_request_flow')
    worker = worker.replace('onpc_request_flow::run', 'onpc_request_flow::chinese_native_auth')
    worker = worker.replace("$stage eq 'station-branch'", "$stage =~ /station-branch\\z/")
    worker = worker.replace('sub record_info { }', "sub record_info { }\nsub type_string { }")
    worker = worker.replace('return {observed => $stage};',
        "return {observed => $stage eq '" + stage + "' ? 'wrong-receipt' : $stage};")
    result = json.loads(run_perl(worker).stdout)
    assert not result['ok'] and 'secret:input-failed' in result['error']
    assert result['events'].count(['secret']) == (1 if stage.startswith('first') else 2)
    assert [event[1] for event in result['events'] if event[0] == 'stage'] == list(
        auth.PLAN.screen_tags)[:list(auth.PLAN.screen_tags).index(stage) + 1]


@pytest.mark.parametrize('fault', ['', 'same-agent', 'same-challenge', 'changed', 'storage'])
def test_real_recorder_step_compares_fresh_agent_before_durable_reply(tmp_path, fault):
    journey = auth.ChineseNativeAuthJourney(SimpleNamespace(directory=tmp_path), Mock())
    journey.native_challenges['first-approval-open'] = deepcopy(prompt_receipt())
    value = prompt_receipt('c' * 64, 'd' * 64)
    if fault == 'same-agent': value['agent_id'] = 'b' * 64
    if fault == 'same-challenge': value['challenge_id'] = 'a' * 64
    stage = 'second-approval-open'
    journey.steps = [{'stage': name} for name in journey.plan.stages[:journey.plan.stages.index(stage)]]
    journey.boot = 'e' * 64
    journey.ui = SimpleNamespace(boot_proof=journey.boot, observe=Mock(return_value={'approval': value}))
    if fault == 'changed':
        stage = 'first-approval-rechecked'
        journey.steps = [{'stage': name} for name in journey.plan.stages[:journey.plan.stages.index(stage)]]
        value['rejected_proofs'] = []
    if fault == 'storage': journey.progress.side_effect = OSError('storage')
    (tmp_path / (stage + '.request.json')).write_text(json.dumps({'stage': stage, 'screenshot': None}))
    if fault:
        with pytest.raises((EvidenceError, OSError)): journey.step(Mock())
        assert not (tmp_path / (stage + '.reply.json')).exists()
    else:
        journey.step(Mock())
        assert (tmp_path / (stage + '.reply.json')).exists()
        value['provider']['locale'] = 'changed'
        assert journey.native_challenges[stage]['provider']['locale'] == 'zh_CN.UTF-8'


def test_distribution_inputs_keep_worker_provenance_bounds():
    import e2e_worker
    inputs = e2e_worker.distribution_inputs()
    assert 'lib/onpc_request_flow.pm' in inputs and 'lib/onpc_password.pm' in inputs
    assert all(tag[3:] in public.OPERATIONS for tag in auth.PLAN.screen_tags.values() if tag.startswith('ui:'))


@pytest.mark.parametrize('refuse', [False, True])
def test_installed_asset_checkpoint_verifies_without_package_transfer(tmp_path, monkeypatch, refuse):
    """An installed snapshot has no product-free FIX04 package command input."""
    verify = Mock(side_effect=EvidenceError('native:unavailable') if refuse else None,
                  return_value={'independent_readback': True, 'unchanged_state': True})
    journey = auth.ChineseNativeAuthJourney(SimpleNamespace(directory=tmp_path), Mock(),
                                            actions={'native-verify': verify})
    stage = 'chinese-assets'
    journey.steps = [{'stage': name} for name in journey.plan.stages[:journey.plan.stages.index(stage)]]
    journey.boot = 'e' * 64
    journey.ui = SimpleNamespace(boot_proof=journey.boot,
        observe=Mock(return_value={'operation': 'parent-selected', 'outcome': 'passed',
                                  'settings': {'child': 'fixture-child', 'limit_enabled': False,
                                               'allowance': ['0 minutes']}}))
    journey.vm = SimpleNamespace(read=Mock(return_value={'boot_sha256': journey.boot}))
    journey.transport = Mock()
    package_context = Mock(side_effect=FileNotFoundError('no FIX04 package on installed entry'))
    monkeypatch.setattr(session_control, 'observe', package_context)
    (tmp_path / (stage + '.request.json')).write_text(json.dumps({'stage': stage, 'screenshot': None}))
    if refuse:
        with pytest.raises(EvidenceError, match='native:unavailable'):
            journey.step(Mock())
        assert not (tmp_path / (stage + '.reply.json')).exists()
    else:
        journey.step(Mock())
        assert (tmp_path / (stage + '.reply.json')).exists()
    verify.assert_called_once()
    journey.ui.observe.assert_called_once_with('parent-selected')
    package_context.assert_not_called()


@pytest.mark.parametrize('fault', ['', 'meaning', 'durability'])
def test_real_recorder_entry_constructor_and_guard_before_reply(session, tmp_path, monkeypatch, fault):
    expected = session.payload['assertions'][0]
    tags = {'entry-start': 'system:parent-command-context', 'entry-one': 'system:parent-command-context',
            'entry-two': 'system:parent-command-context', 'translated-form': 'ui:chinese-language-save'}
    plan = replace(auth.PLAN, screen_tags=tags, phases={'ready': 'setup', 'setup-detached': 'setup',
        'entry-start': 'start', 'entry-one': 'step-1', 'entry-two': 'step-2', 'translated-form': expected['step_id']},
        stage_actions={}, assertions_after={'translated-form': expected['assertion_id']})
    context = SimpleNamespace(directory=tmp_path / 'journey', product_free=True, asset_transfer=Mock(),
        verified=SimpleNamespace(inputs={}), credentials=Mock(), lease=Mock(), guestfs=Mock(), commands=Mock())
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
        assert isinstance(journey, auth.ChineseNativeAuthJourney)
        journey.steps = [{'stage': 'ready'}, {'stage': 'setup-detached'}]
        journey.boot = 'a' * 64
        journey.vm = SimpleNamespace(read=Mock(return_value={'boot_sha256': journey.boot}))
        value = initial()
        if fault == 'meaning': value['texts']['kiosk-request-submit'] = 'Request'
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
    monkeypatch.setattr(auth.ChineseNativeAuthJourney, 'validate', lambda _: [])
    if fault:
        with pytest.raises((EvidenceError, OSError)):
            installed_journey.record_installed_journey(recorder, context, plan, actions={},
                                                      journey_type=auth.ChineseNativeAuthJourney)
        assert not (context.directory / 'translated-form.reply.json').exists()
    else:
        installed_journey.record_installed_journey(recorder, context, plan, actions={},
                                                  journey_type=auth.ChineseNativeAuthJourney)
