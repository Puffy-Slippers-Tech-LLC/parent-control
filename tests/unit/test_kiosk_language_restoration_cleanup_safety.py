"""Private public trees/recorder files and waited Perl; no live VM or shared state."""
from copy import deepcopy
import json
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock

import pytest
import accessible_ui as public
import check_e2e_kiosk_language_restoration as selector
import check_graphical_smoke as smoke
import kiosk_language_restoration as recipe
from kiosk_language import CHOOSER, FORM, TEXT_IDS
from private_artifacts import EvidenceError
from owned_commands import CommandError
from tests.support.accessible_ui import Node, ui_for
from tests.support.e2e_kiosk import accounts_form, WORKER
from tests.support.e2e_recording import session
from tests.support.e2e_evidence import attempt
from tests.support.perl import run_perl
from ui_observations import UiObservations, OPERATION_LABELS


def translated_accounts(field='child', before='de', after='he'):
    ui, selector, choices, expected = accounts_form(field)
    form = ui.find_id('kiosk-request-form')
    form.children.remove(ui.find_id('kiosk-screen-limit-notice'))
    for node in form.children:
        node.states.add('sensitive')
    child = public.EXISTING_CHILD if field == 'child' else public.CHILD
    child_control = ui.find_id('kiosk-child-selector')
    child_control.description = public.ACCOUNT_LANGUAGE_LABELS[before][2] % child
    if field == 'child':
        parent = ui.find_id('kiosk-approver-selector')
        parent.children[0].identity = 'kiosk-approver-selected-1000'
        parent.children[0].name = public.PARENT
        parent.description = public.ACCOUNT_LANGUAGE_LABELS[before][2] % public.PARENT
    for choice, name in zip(choices.children, expected):
        choice.name = public.ACCOUNT_LANGUAGE_LABELS[before][0 if field == 'child' else 1] + ': ' + name
        label = Node(name, 'label'); label.parent = choice; choice.children.append(label)
    original = choices.children[0].action.do_action.side_effect
    def commit(index):
        original(index)
        selector.description = public.ACCOUNT_LANGUAGE_LABELS[after][2] % expected[0]
        child_control.description = public.ACCOUNT_LANGUAGE_LABELS[after][2] % (
            expected[0] if field == 'child' else child)
        ui.find_id('kiosk-approver-selector').description = public.ACCOUNT_LANGUAGE_LABELS[after][2] % public.PARENT
        return True
    choices.children[0].action.do_action.side_effect = commit
    return ui, selector, choices, expected, child


@pytest.mark.parametrize('field,before,after', [('child', 'de', 'he'), ('child', 'he', 'de'),
    ('approver', 'de', 'de'), ('approver', 'he', 'he')])
@pytest.mark.parametrize('fault', ['', 'owner', 'surface', 'child', 'missing-uid', 'duplicate-uid',
    'pre-language', 'post-language', 'offered-set', 'literal-name', 'stale', 'uncertain'])
def test_bound_selector_uses_independent_identity_language_and_terminal_result(field, before, after, fault):
    ui, selector, choices, expected, child = translated_accounts(field, before, after)
    if fault == 'owner': ui.owner_pids = lambda: {999}
    if fault == 'surface': ui.application_ids = (public.PARENT_APPLICATION,)
    if fault == 'child': child = public.CHILD if child == public.EXISTING_CHILD else public.EXISTING_CHILD
    if fault == 'missing-uid': ui.fixture_uids.pop(expected[0])
    if fault == 'duplicate-uid': ui.fixture_uids[expected[1]] = ui.fixture_uids[expected[0]]
    if fault == 'pre-language': before = 'en'
    if fault == 'post-language':
        original = choices.children[0].action.do_action.side_effect
        def wrong_result(index):
            original(index)
            selector.description = 'Selected account: wrong language.'
            return True
        choices.children[0].action.do_action.side_effect = wrong_result
    if fault == 'offered-set': choices.children.pop()
    if fault == 'literal-name': choices.children[0].children[0].name = 'Changed literal name'
    if fault == 'stale': selector.states.add('defunct')
    if fault == 'uncertain': ui.input_uncertain = True
    ui.complete_request_language_setup = Mock(side_effect=AssertionError('unexpected setup'))
    call = lambda: ui.select_kiosk_account(field, expected[0], expected=expected,
        child=child, language=before, result_language=after)
    if fault:
        with pytest.raises(public.UiError): call()
        if fault not in ('offered-set', 'literal-name', 'post-language'):
            selector.action.do_action.assert_not_called()
        if fault in ('offered-set', 'literal-name'):
            choices.children[0].action.do_action.assert_not_called()
        if fault in ('offered-set', 'literal-name', 'post-language', 'uncertain'):
            assert ui.input_uncertain
            with pytest.raises(public.UiError, match='uncertain-input'): call()
    else:
        value = call()
        assert value['child'] == public.CHILD_IDENTITIES[expected[0] if field == 'child' else child]
        assert value['approver'] == 'fixture-parent' and value['duration_seconds'] == 1800
        selector.action.do_action.assert_called_once()
        choices.children[0].action.do_action.assert_called_once()
    ui.complete_request_language_setup.assert_not_called()


def test_registration_inputs_shared_fragment_and_worker_distribution(monkeypatch, tmp_path):
    import e2e_worker
    import tools.test_commands as commands
    from tools.test_storage import named_input
    from parent_setup_qualification import KioskLanguageRestorationQualification, KioskEntryQualification
    from journey_blocks import language_selection
    launch = Mock(return_value=0)
    monkeypatch.setattr(selector, 'smoke', launch)
    assert selector.main() == 0
    launch.assert_called_once_with(assets=selector.ASSETS, provision_credentials=True, kiosk_language_restoration=True)
    assert selector.ASSETS == named_input(package_source=True)
    assert KioskLanguageRestorationQualification.attach_installed_snapshot is KioskEntryQualification.attach_installed_snapshot
    assert KioskLanguageRestorationQualification.journey(SimpleNamespace(directory=tmp_path), Mock()).plan is recipe.PLAN
    monkeypatch.setattr(commands.os.path, 'lexists', lambda _: False)
    monkeypatch.setattr(commands, 'allocate_artifact_output', Mock(return_value=str(selector.ASSETS)))
    for name in ('check_e2e_kiosk_language_restoration', 'check_e2e_kiosk_eligible_choices'):
        assert commands.qualification_artifact_command(Path.cwd(), 'integration', [name])[-1] == str(selector.ASSETS)
    monkeypatch.setattr(commands.os.path, 'lexists', lambda _: True)
    monkeypatch.setattr(commands, 'artifact_path', Mock())
    assert commands.qualification_artifact_command(Path.cwd(), 'integration', ['check_e2e_kiosk_language_restoration']) is None
    assert all(tag[3:] in public.OPERATIONS and tag[3:] in OPERATION_LABELS
               for tag in recipe.SCREENS.values() if tag.startswith('ui:'))
    assert set(recipe.PLAN.phases) == set(recipe.PLAN.stages)
    assert language_selection('independent', 'he', surface='kiosk', child='child') == {
        'independent-open': 'ui:kiosk-riley-language-open', 'independent-choose': 'ui:kiosk-riley-language-choose-he',
        'independent-candidate': 'ui:kiosk-riley-language-read'}
    bundle = e2e_worker.distribution_inputs()
    assert b'kiosk_language_restoration' in bundle['tests/smoke.pm']
    assert b'sub kiosk_language_restoration' in bundle['lib/onpc_request_flow.pm']


@pytest.mark.parametrize('extra', [{}, {'parent_language': True}, {'kiosk_language': True}, {'parent_toggle': True}])
def test_mode_refuses_before_vm(extra):
    args = {'assets': 'input', 'provision_credentials': True, **extra} if extra else {}
    with pytest.raises(CommandError, match='kiosk-language-restoration-prerequisites'):
        smoke.main(kiosk_language_restoration=True, **args)


def riley_chooser():
    choices = [Node(text[0], identity='language-choice-' + key.lower(),
        states=('visible', 'sensitive', *(('checked',) if key == 'he' else ())))
        for key, text in CHOOSER.items()]
    dialog = Node(identity='language-dialog', children=[*choices,
        Node(CHOOSER['he'][1], identity='language-title'),
        Node(CHOOSER['he'][2], identity='language-continue', description=CHOOSER['he'][3],
             children=[Node(CHOOSER['he'][2], 'label')])])
    selected = Node(public.CHILD, 'label', identity='kiosk-child-selected-1001')
    return ui_for(Node(identity='kiosk-request-window', children=[dialog, selected,
        Node(identity='kiosk-language-ready')])), selected


@pytest.mark.parametrize('fault', ['', 'wrong-child', 'duplicate', 'missing-uid', 'receipt'])
def test_nondefault_chooser_child_and_post_save_receipt(fault):
    ui, selected = riley_chooser()
    if fault == 'wrong-child': selected.identity = 'kiosk-child-selected-1002'
    if fault == 'duplicate': selected.parent.children.append(Node(identity=selected.identity))
    if fault == 'missing-uid': ui.fixture_uids.pop(public.CHILD)
    if fault == 'receipt':
        ui.save_language = Mock(side_effect=lambda _: setattr(selected, 'identity', 'kiosk-child-selected-1002'))
        with pytest.raises(public.UiError, match='initial-child'):
            ui.kiosk_language_operation('kiosk-riley-language-save')
        ui.save_language.assert_called_once()
        assert ui.input_uncertain
    elif fault:
        with pytest.raises(public.UiError): ui.read_kiosk_language(child=public.CHILD)
    else:
        assert ui.kiosk_language_operation('kiosk-riley-language-read') == {'language': chooser()}
    selected.action.do_action.assert_not_called()


def test_real_startup_forwards_mode_and_snapshot(tmp_path, monkeypatch):
    import installed_journey
    import installed_setup
    context = SimpleNamespace(directory=tmp_path, installed_snapshot='installed-test',
        host_key='public-host-key', verified=Mock(), commands=Mock(),
        lease=SimpleNamespace(source=SimpleNamespace(uuid='vm-identity'),
            view=SimpleNamespace(domain_id=1), state={'run': 'attempt'}, guard=Mock()))
    monkeypatch.setattr(installed_journey.system, 'address', Mock(return_value='test-host'))
    monkeypatch.setattr(installed_journey, 'Transport', Mock())
    monkeypatch.setattr(installed_journey, 'ReadOnlyObservations', Mock())
    monkeypatch.setattr(installed_setup, 'InstalledSetup', Mock())
    journey = recipe.KioskLanguageRestorationJourney(context, Mock())
    for stage in ('ready', 'setup-detached'):
        (tmp_path / (stage + '.request.json')).write_text(json.dumps({'stage': stage, 'screenshot': None}))
        journey.step(Mock())
    assert json.loads((tmp_path / 'ready.reply.json').read_bytes()) == {
        'kiosk_language_restoration': True, 'invocations': list(recipe.PLAN.invocations),
        'challenge_bindings': {key: list(value) for key, value in recipe.PLAN.challenges.items()}}
    assert journey.steps[1]['setup'] == {'installed_snapshot': 'installed-test'}


@pytest.mark.parametrize('fault', ['', 'meaning', 'durability'])
def test_real_recording_entry_receives_plan_and_failure_stops_reply(session, tmp_path, monkeypatch, fault):
    from dataclasses import replace
    import installed_journey
    import session_control
    expected = session.payload['assertions'][0]
    tags = {stage: 'system:parent-command-context' for stage in ('entry-start', 'entry-one', 'entry-two')}
    tags['chooser'] = 'ui:kiosk-riley-language-open'
    plan = replace(recipe.PLAN, screen_tags=tags, invocations=(), challenges={},
        phases={'ready': 'setup', 'setup-detached': 'setup', 'entry-start': 'start',
            'entry-one': 'step-1', 'entry-two': 'step-2', 'chooser': expected['step_id']},
        assertions_after={'chooser': expected['assertion_id']})
    context = SimpleNamespace(directory=tmp_path / 'journey', product_free=True, asset_transfer=Mock(),
        verified=SimpleNamespace(inputs={}), credentials=Mock(), lease=Mock(), guestfs=Mock(), commands=Mock())
    context.directory.mkdir()
    recorder = session.recorder
    recorder.begin_case('E2E-001/gdm-observation')
    save_report = session.collector.save_report
    def save(name, report):
        if fault == 'durability' and report.get('event') == 'observation' and report.get('active_step') == expected['step_id']:
            raise OSError('storage failed')
        return save_report(name, report)
    monkeypatch.setattr(session.collector, 'save_report', save)
    monkeypatch.setattr(session_control, 'observe', Mock(return_value={'outcome': 'passed'}))
    def worker(**options):
        journey = options['guarded_observe'].__self__
        assert isinstance(journey, recipe.KioskLanguageRestorationJourney) and journey.plan is plan
        journey.child, journey.committed[public.CHILD] = public.CHILD, 'he'
        journey.steps = [{'stage': 'ready'}, {'stage': 'setup-detached'}]
        journey.boot = 'a' * 64
        journey.vm = SimpleNamespace(read=Mock(return_value={'boot_sha256': journey.boot}))
        value = chooser()
        if fault == 'meaning': value['heading'] = 'wrong'
        journey.ui = SimpleNamespace(boot_proof=journey.boot,
            observe=Mock(return_value={'outcome': 'passed', 'language': value}))
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
    monkeypatch.setattr(recipe.KioskLanguageRestorationJourney, 'validate', lambda _: [])
    if fault:
        with pytest.raises((EvidenceError, OSError)):
            installed_journey.record_installed_journey(recorder, context, plan, actions={},
                journey_type=recipe.KioskLanguageRestorationJourney)
        assert not (context.directory / 'chooser.reply.json').exists()
    else:
        installed_journey.record_installed_journey(recorder, context, plan, actions={},
            journey_type=recipe.KioskLanguageRestorationJourney)


def chooser(language='he', initial=False):
    text = CHOOSER[language]
    return {'initial': initial, 'checked': language.lower(), 'choices': {key: item[0] for key, item in CHOOSER.items()},
        'heading': text[1], 'save': text[2], 'save_label': text[2], 'save_description': text[3]}


def request(child=public.CHILD, approver='fixture-parent'):
    return dict(surface='kiosk', form_count=1, child=public.CHILD_IDENTITIES[child], approver=approver,
        duration_seconds=1800, custom_text=None, allow_soft=False, child_selector_enabled=True,
        approver_selector_enabled=True, duration_enabled=True, soft_choice_enabled=True,
        request_enabled=True, cancel_enabled=True, message='', mute=None)


def language_form(language='he', child=public.CHILD, approver='fixture-parent'):
    text = FORM[language]
    return {'request': request(child, approver), 'texts': dict(zip(TEXT_IDS, (*text[:3], text[4], text[6]))),
        'labels': {TEXT_IDS[3]: text[3], TEXT_IDS[4]: text[5]}, 'chooser_absent': True}


@pytest.mark.parametrize('operation,key,value', [
    ('kiosk-riley-language-open', 'language', chooser()),
    ('kiosk-riley-language-form-he', 'language_form', language_form()),
    ('kiosk-riley-language-form-he-casey', 'language_form', language_form(approver='other-fixture-parent')),
    ('kiosk-language-form-de-casey', 'language_form', language_form('de', public.EXISTING_CHILD, 'other-fixture-parent')),
    ('kiosk-language-riley-restored', 'request', request()),
])
@pytest.mark.parametrize('fault', ['', 'extra', 'identity', 'oversize'])
def test_real_decoder_nondefault_child_approver_and_mismatched_result(operation, key, value, fault):
    value = deepcopy(value)
    if fault == 'extra': value['extra'] = True
    if fault == 'identity':
        if key == 'language': value['checked'] = 'unknown'
        else: (value['request'] if key == 'language_form' else value)['child'] = 'missing-child'
    if fault == 'oversize': value['unbounded'] = 'x' * 32768
    payload = dict(operation=operation, outcome='passed', interface='AT-SPI', **{key: value})
    raw = json.dumps(payload, ensure_ascii=False).encode()
    def deliver(*args, **kwargs):
        if kwargs.get('on_output'):
            for index in range(0, len(raw), 37): kwargs['on_output'](raw[index:index + 37])
            kwargs['on_output'](b'\n')
        return raw
    transport = SimpleNamespace(call=Mock(side_effect=deliver), commands=SimpleNamespace(progress=None))
    observer = UiObservations(transport)
    if fault:
        with pytest.raises(EvidenceError): observer.observe(operation)
        with pytest.raises(EvidenceError, match='previous-failure'): observer.observe('kiosk-riley-language-save')
        transport.call.assert_called_once()
    else:
        assert observer.observe(operation) == payload


@pytest.mark.parametrize('fault', ['', 'wrong-child', 'text', 'request', 'replay', 'storage'])
def test_real_recorder_comparison_and_receipt_stop_before_reply(tmp_path, fault):
    stage = 'hebrew-form'
    journey = recipe.KioskLanguageRestorationJourney(SimpleNamespace(directory=tmp_path), Mock())
    journey.child, journey.committed[public.CHILD] = public.CHILD, 'he'
    value = language_form()
    if fault == 'wrong-child': value['request']['child'] = 'existing-fixture-child'
    if fault == 'text': value['texts'][TEXT_IDS[0]] = 'Child'
    if fault == 'request': value['request']['allow_soft'] = True
    if fault == 'replay': journey.captures.add(stage)
    if fault == 'storage': journey.progress.side_effect = OSError('storage')
    index = journey.plan.stages.index(stage)
    journey.steps = [{'stage': item} for item in journey.plan.stages[:index]]
    journey.boot = 'a' * 64
    journey.ui = SimpleNamespace(boot_proof=journey.boot, observe=Mock(return_value={
        'operation': recipe.SCREENS[stage][3:], 'language_form': value}))
    (tmp_path / (stage + '.request.json')).write_text(json.dumps({'stage': stage, 'screenshot': None}))
    if fault:
        with pytest.raises((EvidenceError, OSError)): journey.step(Mock())
        assert not (tmp_path / (stage + '.reply.json')).exists()
    else:
        journey.step(Mock())
        assert (tmp_path / (stage + '.reply.json')).exists()
        value['request']['allow_soft'] = True
        assert journey.requests[public.CHILD]['allow_soft'] is False


@pytest.mark.parametrize('fault', ['', *recipe.SCREENS])
def test_actual_worker_order_titles_and_no_input_after_refusal(monkeypatch, fault):
    if fault: monkeypatch.setenv('ONPC_TEST_REFUSE_STAGE', fault)
    worker = WORKER.replace('onpc_kiosk_eligible_choices', 'onpc_request_flow')
    worker = worker.replace('onpc_request_flow::run', 'onpc_request_flow::kiosk_language_restoration')
    worker = worker.replace('sub record_info { }', "sub record_info { push @main::events, ['title', $_[0]] }")
    worker = worker.replace("if $stage eq 'station-branch';", "if $stage =~ /(?:initial|renewed)-station-branch$/;")
    worker = worker.replace("station_destination => 'default-request-form'", "station_destination => 'initial-request-window'")
    worker = worker.replace('return {observed => $stage};', r'''
        if ($stage eq 'return-qualified' || $stage eq 'return-rechecked') {
            return {observed => $stage, challenge => {id => 'return-parent', role => 'parent',
                surface => 'gdm', check => $stage eq 'return-qualified' ? 'qualified' : 'rechecked'}};
        }
        return {observed => $stage};''')
    worker = worker.replace('    });', '    }, ' + json.dumps(list(recipe.PLAN.invocations)) +
        ', {"return-parent" => ["parent", "return-qualified", "return-rechecked"]});')
    result = json.loads(run_perl(worker).stdout)
    expected = list(recipe.SCREENS)
    if fault: expected = expected[:expected.index(fault) + 1]
    assert bool(result['ok']) == (not fault), result['error']
    assert [event[1] for event in result['events'] if event[0] == 'stage'] == expected
    assert [event[1] for event in result['events'] if event[0] == 'title' and event[1] != 'shutdown'] == [
        'kiosk-language-restoration-' + stage for stage in expected]
    assert ['power', 'off'] in result['events'] if not fault else ['power', 'off'] not in result['events']
