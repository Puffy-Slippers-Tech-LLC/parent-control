"""Private public-tree/transport/recorder doubles and waited Perl; no VM owners."""
from copy import deepcopy
import json
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock

import pytest
import accessible_ui as public
import check_e2e_kiosk_language as selector
import check_graphical_smoke as smoke
import kiosk_language as language
from private_artifacts import EvidenceError
from owned_commands import CommandError
from tests.support.accessible_ui import Node, ui_for
from tests.support.e2e_kiosk import WORKER, request_form
from tests.support.perl import run_perl
from tests.support.e2e_evidence import attempt
from tests.support.e2e_recording import session
from ui_observations import UiObservations, OPERATION_LABELS


def chooser_value(selected='en', initial=False, identity=False):
    text = language.CHOOSER[selected]
    result = {'initial': initial, 'checked': selected.lower(),
        'choices': {key: value[0] for key, value in language.CHOOSER.items()},
        'heading': text[1], 'save': text[2], 'save_label': text[2], 'save_description': text[3]}
    if identity:
        result['identity'] = {'chooser': 'a' * 32, 'session': 'b' * 64}
    return result


def chooser_tree(initial=False):
    choices = [Node(text[0], identity='language-choice-' + key.lower(),
                    states=('visible', 'sensitive', *(('checked',) if key == 'en' else ())))
               for key, text in language.CHOOSER.items()]
    controls = choices + [Node('Choose your language', identity='language-title'),
        Node('Save', identity='language-continue', description='Save your language preference.',
             children=[Node('Save', 'label')]), Node('Cancel', identity='language-cancel'),
        Node(identity='language-list', value='en', choices=language.CHOOSER)]
    dialog = Node(identity='language-dialog', children=controls, value='a' * 32)
    window = Node(identity='kiosk-request-window', children=[dialog,
        Node(identity='kiosk-language-loading' if initial else 'kiosk-language-ready'),
        Node(public.EXISTING_CHILD, 'label', identity='kiosk-child-selected-1002')])
    return ui_for(window), window, dialog, controls


def request_value():
    return dict(surface='kiosk', form_count=1, child='existing-fixture-child', approver='fixture-parent',
        duration_seconds=1800, custom_text=None, allow_soft=False, child_selector_enabled=True,
        approver_selector_enabled=True, duration_enabled=True, soft_choice_enabled=True,
        request_enabled=True, cancel_enabled=True, message='', mute=None)


def form_value(selected='en'):
    text = language.FORM[selected]
    return {'request': request_value(), 'texts': dict(zip(language.TEXT_IDS, (*text[:3], text[4], text[6]))),
        'labels': {language.TEXT_IDS[3]: text[3], language.TEXT_IDS[4]: text[5]}, 'chooser_absent': True}


def policy_value():
    return {'settings': {'child': 'existing-fixture-child', 'limit_enabled': True, 'allowance': ['0 minutes']},
        'balances': {'daily': 0, 'one_time': 0, 'total': 0},
        'rows': [[f'parent-app-{index:016x}', 'allowed', 'precise'] for index in range(128)]}


def test_registered_selector_snapshot_worker_and_shared_fragment(monkeypatch, tmp_path):
    import e2e_worker
    import tools.test_commands as commands
    from tools.test_storage import named_input
    from vm_selection import arguments
    from parent_setup_qualification import KioskLanguageQualification, KioskEntryQualification
    from journey_blocks import language_selection
    import parent_language
    launch = Mock(return_value=0)
    monkeypatch.setattr(selector, 'smoke', launch)
    assert selector.main() == 0
    launch.assert_called_once_with(assets=selector.ASSETS, provision_credentials=True, kiosk_language=True)
    assert selector.ASSETS == named_input(package_source=True)
    assert KioskLanguageQualification.attach_installed_snapshot is KioskEntryQualification.attach_installed_snapshot
    assert KioskLanguageQualification.journey(SimpleNamespace(directory=tmp_path), Mock()).plan is language.PLAN
    monkeypatch.setattr(commands.os.path, 'lexists', lambda _: False)
    monkeypatch.setattr(commands, 'allocate_artifact_output', Mock(return_value=str(selector.ASSETS)))
    assert commands.qualification_artifact_command(Path.cwd(), 'integration', ['check_e2e_kiosk_language']) == commands.python_file(
        Path.cwd(), 'tools/vm_artifacts.py', '--output', str(selector.ASSETS), *arguments())
    assert set(language.PLAN.phases) == set(language.PLAN.stages)
    assert all(tag[3:] in public.OPERATIONS and tag[3:] in OPERATION_LABELS
               for tag in language.SCREENS.values() if tag.startswith('ui:'))
    distribution = e2e_worker.distribution_inputs()
    assert b'kiosk_language' in distribution['tests/smoke.pm']
    assert b'sub kiosk_language' in distribution['lib/onpc_request_flow.pm']
    independent = language_selection('unrelated', 'he', surface='kiosk')
    assert independent == {'unrelated-open': 'ui:kiosk-language-open',
        'unrelated-choose': 'ui:kiosk-language-choose-he'}
    assert parent_language.selection('other', 'de') == language_selection('other', 'de', surface='parent')


@pytest.mark.parametrize('name', ['check_e2e_kiosk_language', 'check_e2e_kiosk_language.py'])
def test_valid_existing_inputs_are_preserved(monkeypatch, name):
    import tools.test_commands as commands
    from vm_selection import arguments
    validate, allocate = Mock(), Mock()
    monkeypatch.setattr(commands.os.path, 'lexists', lambda _: True)
    monkeypatch.setattr(commands, 'artifact_path', validate)
    monkeypatch.setattr(commands, 'allocate_artifact_output', allocate)
    # Existing inputs still need pinned-baseline verification without replacement.
    assert commands.qualification_artifact_command(Path.cwd(), 'integration', [name]) == commands.python_file(
        Path.cwd(), 'tools/vm_artifacts.py', '--candidate', str(selector.ASSETS),
        '--output', str(selector.ASSETS), *arguments())
    validate.assert_called_once_with(str(selector.ASSETS))
    allocate.assert_not_called()


@pytest.mark.parametrize('extra', [{}, {'parent_language': True}, {'chinese_native_auth': True}, {'parent_toggle': True}])
def test_mode_refuses_before_vm(extra):
    args = {'assets': 'inputs', 'provision_credentials': True, **extra} if extra else {}
    with pytest.raises(CommandError, match='kiosk-language-prerequisites'):
        smoke.main(kiosk_language=True, **args)


@pytest.mark.parametrize('initial', [True, False])
@pytest.mark.parametrize('fault', ['', 'duplicate', 'missing', 'empty-value', 'multiple-values',
                                  'duplicate-choice', 'stale', 'owner', 'surface', 'entry'])
def test_shared_kiosk_chooser_is_owned_complete_and_input_free(initial, fault):
    ui, window, dialog, controls = chooser_tree(initial)
    if fault == 'duplicate': dialog.children.append(Node(identity='language-title'))
    if fault == 'missing': dialog.children.remove(controls[3])
    if fault == 'empty-value': controls[-1].value = ''
    if fault == 'multiple-values': controls[-1].value = ['en', 'de']
    if fault == 'duplicate-choice': controls[-1].choices.append('en')
    if fault == 'stale': controls[0].states.add('defunct')
    if fault == 'owner': ui.owner_pids = lambda: {999}
    if fault == 'surface': ui.application_ids = (public.PARENT_APPLICATION,)
    if fault == 'entry': window.children[1].identity = 'kiosk-language-ready' if initial else 'kiosk-language-loading'
    ui.complete_request_language_setup = Mock(side_effect=AssertionError('automatic startup'))
    if fault:
        with pytest.raises(public.UiError): ui.read_kiosk_language(initial=initial)
    else:
        assert ui.read_kiosk_language(initial=initial) == chooser_value(initial=initial)
    ui.complete_request_language_setup.assert_not_called()
    for control in controls: control.action.do_action.assert_not_called()


def test_kiosk_reader_refuses_overlay_and_wrong_entry_before_action():
    ui, window, dialog, controls = chooser_tree()
    ui.application_ids = (public.CHILD_APPLICATION,)
    with pytest.raises(public.UiError): ui.read_kiosk_language()
    for control in controls: control.action.do_action.assert_not_called()
    ui = ui_for(Node(identity='parent-window'))
    assert ui.kiosk_language_operation('kiosk-language-wrong-entry') == {'refused': True}
    ui.open_language_preferences = Mock(side_effect=AssertionError('input'))
    ui.open_language_preferences.assert_not_called()


@pytest.mark.parametrize('fault', ['', 'chooser', 'session', 'choice', 'missing'])
def test_pause_reacquires_same_initial_chooser_before_save(fault):
    journey = language.KioskLanguageJourney(SimpleNamespace(), Mock())
    original = chooser_value(initial=True, identity=True)
    journey.check_settings('initial-language', {'ui': {'language': original}})
    retained = deepcopy(original)
    if fault in ('chooser', 'session'):
        retained['identity'][fault] = 'c' * (32 if fault == 'chooser' else 64)
    if fault == 'choice': retained['checked'] = 'de'
    if fault == 'missing': retained.pop('identity')
    if fault:
        with pytest.raises(EvidenceError, match='language:(paused-chooser-replaced|missing-chooser-identity)'):
            journey.check_settings('initial-retained', {'ui': {'language': retained}})
        assert 'initial-save' not in journey.language_captures
    else:
        journey.check_settings('initial-retained', {'ui': {'language': retained}})
        original['identity']['chooser'] = 'd' * 32
        assert journey.initial_chooser['identity']['chooser'] == 'a' * 32


@pytest.mark.parametrize('cancel', [False, True])
def test_initial_pause_reuses_guarded_time03_and_original_budget(monkeypatch, cancel):
    import real_interval
    clock = [100.0]
    monkeypatch.setattr(real_interval.time, 'monotonic', lambda: clock[0])
    monkeypatch.setattr(real_interval.time, 'sleep', lambda duration: clock.__setitem__(0, clock[0] + duration))
    journey = language.KioskLanguageJourney(SimpleNamespace(), Mock())
    def guard():
        if cancel and clock[0] >= 101:
            raise EvidenceError('cancelled')
        return 1900
    action = journey.actions[language.PLAN.stage_actions['initial-language']]
    if cancel:
        with pytest.raises(EvidenceError, match='cancelled'): action(journey, guard)
        assert clock[0] < 190
    else:
        assert action(journey, guard) >= 90
        assert clock[0] == 190
    stages = list(language.SCREENS)
    assert stages[stages.index('initial-language'):stages.index('initial-save') + 1] == [
        'initial-language', 'initial-retained', 'initial-save']


@pytest.mark.parametrize('fault', ['', 'chooser', 'session', 'extra', 'operation'])
def test_optional_initial_identity_decoder_is_bounded(fault):
    value = chooser_value(initial=True, identity=True)
    operation = 'kiosk-language-initial-identity'
    if fault == 'chooser': value['identity']['chooser'] = 'x' * 33
    if fault == 'session': value['identity']['session'] = True
    if fault == 'extra': value['identity']['pid'] = 100
    if fault == 'operation':
        operation = 'kiosk-language-read'
        value['initial'] = False
    payload = dict(operation=operation, outcome='passed', interface='ApplicationUI+external-provider', language=value)
    raw = json.dumps(payload).encode() + b'\n'
    def deliver(*args, **kwargs):
        if kwargs.get('on_output') is not None:
            kwargs['on_output'](raw)
        return raw
    transport = SimpleNamespace(call=Mock(side_effect=deliver), commands=SimpleNamespace(progress=None))
    observer = UiObservations(transport)
    if fault:
        with pytest.raises(EvidenceError, match='ui:language-identity'): observer.observe(operation)
        with pytest.raises(EvidenceError, match='previous-failure'): observer.observe('kiosk-language-save')
        transport.call.assert_called_once()
    else:
        assert observer.observe(operation) == payload


@pytest.mark.parametrize('fault', ['', 'missing', 'wrong-child', 'duplicate', 'hidden', 'stale'])
@pytest.mark.parametrize('identity', [False, True])
def test_initial_operation_checks_selected_kiosk_child_without_startup_input(monkeypatch, fault, identity):
    monkeypatch.setattr(public.os, 'getuid', lambda: 1003)
    monkeypatch.setattr(public.os, 'geteuid', lambda: 1003)
    monkeypatch.setattr(public.pwd, 'getpwnam', lambda _: SimpleNamespace(pw_uid=1003))
    monkeypatch.setattr(public.session_control, 'sessions', Mock(return_value={'owned': 'session'}))
    monkeypatch.setattr(public.session_control, 'entry_identity', Mock(return_value='b' * 64))
    ui, window, _dialog, controls = chooser_tree(initial=True)
    selected = window.children[-1]
    if fault == 'missing': window.children.remove(selected)
    if fault == 'wrong-child': selected.identity = 'kiosk-child-selected-1001'
    if fault == 'duplicate': window.children.append(Node(identity=selected.identity))
    if fault == 'hidden': selected.states.discard('showing')
    if fault == 'stale': selected.states.add('defunct')
    ui.complete_request_language_setup = Mock(side_effect=AssertionError('automatic startup'))
    operation = 'kiosk-language-initial-identity' if identity else 'kiosk-language-initial'
    if fault:
        with pytest.raises(public.UiError): ui.kiosk_language_operation(operation)
    else:
        value = ui.kiosk_language_operation(operation)
        assert value == {'language': chooser_value(initial=True, identity=identity)}
        if identity:
            language.KioskLanguageJourney(SimpleNamespace(), Mock()).check_settings(
                'initial-language', {'ui': value})
        else:
            # Exercise a real existing consumer with the actual producer shape.
            from kiosk_language_restoration import KioskLanguageRestorationJourney
            KioskLanguageRestorationJourney(SimpleNamespace(), Mock()).check_settings(
                'initial-language', {'ui': value})
            public.session_control.entry_identity.assert_not_called()
    ui.complete_request_language_setup.assert_not_called()
    for control in controls: control.action.do_action.assert_not_called()


@pytest.mark.parametrize('next_read', ['valid', 'owner', 'stale'])
def test_kiosk_stale_chooser_reacquisition_keeps_deadline_and_no_input(monkeypatch, next_read):
    ui, window, dialog, controls = chooser_tree()
    stale = Node(identity='retired', states=('defunct',))
    dialog.children.append(stale)
    ui.timeout = 1
    clock = [0]
    monkeypatch.setattr(public.time, 'monotonic', lambda: clock[0])
    def advance(_):
        clock[0] += .5
        if next_read != 'stale' and stale in dialog.children:
            dialog.children.remove(stale)
            if next_read == 'owner': ui.owner_pids = lambda: {999}
    monkeypatch.setattr(public.time, 'sleep', advance)
    if next_read == 'valid':
        assert ui.read_kiosk_language() == chooser_value()
    else:
        with pytest.raises(public.UiError): ui.read_kiosk_language()
    assert clock[0] <= 1 and ui._observation_cache is None
    for control in controls: control.action.do_action.assert_not_called()


@pytest.mark.parametrize('fault', ['', 'saving', 'wrong-child', 'allowance'])
def test_public_policy_reader_projects_actual_balances_and_retains_settings(fault):
    selected = Node(identity='parent-child-selected-1002', children=[Node(public.EXISTING_CHILD, 'label')])
    picker = Node(identity='parent-child-selector', value='1002', choices=('1001', '1002'),
                  children=[selected])
    toggle = Node(identity='parent-screen-limit-toggle', states=('visible', 'showing', 'sensitive', 'checked'))
    allowance = Node(identity='parent-daily-limit-selector', children=[Node(
        '15 minutes' if fault == 'allowance' else '0 minutes', 'label')])
    root = Node(identity='parent-window', children=[picker, toggle, allowance,
        Node(identity='parent-app-search')])
    ui = ui_for(root)
    ui.parent = Mock(return_value=root)
    ui.reveal_id = Mock()
    ui.activate_id = Mock()
    policy = policy_value()
    ui.parent_save_snapshot = Mock(wraps=ui.parent_save_snapshot)
    if fault == 'saving': picker.states.discard('sensitive')
    if fault == 'wrong-child':
        selected.identity = 'parent-child-selected-1001'
        picker.value = '1001'
    ui.reach_time_explanation = Mock(return_value={key: {'seconds': value}
        for key, value in policy['balances'].items()})
    ui.app_rows = Mock(return_value=policy['rows'])
    if fault in ('saving', 'wrong-child'):
        with pytest.raises(public.UiError): ui.kiosk_language_policy()
        ui.reach_time_explanation.assert_not_called()
        ui.app_rows.assert_not_called()
        return
    value = ui.kiosk_language_policy()
    payload = dict(operation='kiosk-language-policy', outcome='passed', interface='ApplicationUI+external-provider', language_policy=value)
    transport = SimpleNamespace(call=Mock(return_value=json.dumps(payload).encode()),
                                commands=SimpleNamespace(progress=None))
    observed = UiObservations(transport).observe('kiosk-language-policy')
    journey = language.KioskLanguageJourney(SimpleNamespace(), Mock())
    if fault == 'allowance':
        assert value['settings']['allowance'] == ['15 minutes']
        with pytest.raises(EvidenceError, match='language:declared-policy'):
            journey.check_settings('policy-before', {'ui': observed})
    else:
        assert value == policy
        journey.check_settings('policy-before', {'ui': observed})
        assert journey.policy_projection == policy
    assert ui.parent_save_snapshot.call_count == 2
    ui.reach_time_explanation.assert_called_once_with(public.EXISTING_CHILD)
    ui.app_rows.assert_called_once_with(public.EXISTING_CHILD)
    assert [call.args for call in ui.activate_id.call_args_list] == [
        ('parent-page-screen-limits',), ('parent-page-app-limits',), ('parent-page-screen-limits',)]


@pytest.mark.parametrize('fault', ['', 'wrong-child', 'save', 'changed-policy'])
def test_public_policy_restoration_keeps_jordan_binding_and_readback(fault):
    ui, _window, _dialog, _controls = chooser_tree()
    ui.activate_id = Mock()
    ui.parent = Mock(return_value=object())
    ui.parent_save_snapshot = Mock(side_effect=public.UiError('ui:wrong-child')
        if fault == 'wrong-child' else None)
    ui.set_toggle = Mock(side_effect=public.UiError('ui:save') if fault == 'save' else None)
    restored = policy_value()
    restored['settings']['limit_enabled'] = False
    if fault == 'changed-policy': restored['rows'][0][1] = 'blocked'
    ui.kiosk_language_policy = Mock(return_value=restored)
    if fault in ('wrong-child', 'save'):
        with pytest.raises(public.UiError): ui.run('kiosk-language-policy-restored', '1.0')
        ui.kiosk_language_policy.assert_not_called()
        if fault == 'wrong-child': ui.set_toggle.assert_not_called()
        return
    value = ui.run('kiosk-language-policy-restored', '1.0')
    ui.parent_save_snapshot.assert_called_once_with(public.EXISTING_CHILD, True)
    ui.set_toggle.assert_called_once_with('parent-screen-limit-toggle', False, root=ui.parent.return_value)
    ui.kiosk_language_policy.assert_called_once_with(child=public.EXISTING_CHILD, enabled=False)
    journey = language.KioskLanguageJourney(SimpleNamespace(), Mock())
    journey.check_settings('policy-before', {'ui': {'language_policy': policy_value()}})
    journey.check_settings('policy-after', {'ui': {'language_policy': policy_value()}})
    if fault:
        with pytest.raises(EvidenceError, match='language:policy-restoration'):
            journey.check_settings('restore-policy', {'ui': value})
    else:
        journey.check_settings('restore-policy', {'ui': value})
        assert journey.policy_projection['settings']['limit_enabled'] is True


@pytest.mark.parametrize('operation', ['kiosk-language-choose-de', 'kiosk-language-save', 'kiosk-language-cancel'])
def test_stale_or_uncertain_input_is_never_repeated(operation):
    ui, window, dialog, controls = chooser_tree()
    controls[0].states.add('defunct')
    with pytest.raises(public.UiError): ui.kiosk_language_operation(operation)
    for control in controls: control.action.do_action.assert_not_called()
    controls[0].states.discard('defunct')
    target = next(node for node in controls if node.identity == {
        'kiosk-language-choose-de': 'language-list', 'kiosk-language-save': 'language-continue',
        'kiosk-language-cancel': 'language-cancel'}[operation])
    target.states.add('showing')
    if operation == 'kiosk-language-choose-de':
        target.setValue.side_effect = public.UiError('ui:lost-reply')
    else:
        target.action.do_action.return_value = False
    with pytest.raises(public.UiError): ui.kiosk_language_operation(operation)
    assert ui.input_uncertain
    with pytest.raises(public.UiError): ui.kiosk_language_operation(operation)
    if operation == 'kiosk-language-choose-de':
        target.setValue.assert_called_once_with('de')
        target.action.do_action.assert_not_called()
    else:
        target.action.do_action.assert_called_once()


@pytest.mark.parametrize('selected', language.CHOOSER)
def test_actual_form_reader_uses_general_request_projection_and_separate_text(selected):
    ui, _ = request_form()
    form = ui.find_id('kiosk-request-form')
    form.children.remove(ui.find_id('kiosk-screen-limit-notice'))
    for node in form.children: node.states.add('sensitive')
    parent = ui.find_id('kiosk-approver-selector')
    parent.children[0].identity = 'kiosk-approver-selected-1000'
    parent.value = '1000'
    parent.children[0].name = public.PARENT
    template = {'en': 'Selected account: %s.', 'de': 'Ausgewähltes Konto: %s.',
                'zh-Hans': '已选择的账户：%s。', 'he': 'החשבון שנבחר: %s.'}[selected]
    parent.description = template % public.PARENT
    ui.find_id('kiosk-child-selector').description = template % public.EXISTING_CHILD
    text = language.FORM[selected]
    for identity, name in zip(language.TEXT_IDS, (*text[:3], text[4], text[6])):
        existing = next((node for node in form.children if node.identity == identity), None)
        if existing is None:
            existing = Node(identity=identity); existing.parent = form; form.children.append(existing)
        existing.name = name
        if identity in language.TEXT_IDS[3:]:
            label = Node(text[3 if identity.endswith('submit') else 5], 'label')
            label.parent = existing; existing.children.append(label)
    ui.complete_request_language_setup = Mock(side_effect=AssertionError('automatic setup'))
    assert ui.kiosk_language_form(selected) == form_value(selected)
    ui.complete_request_language_setup.assert_not_called()
    for node in form.children: node.action.do_action.assert_not_called()


@pytest.mark.parametrize('operation,key,value', [
    ('kiosk-language-initial', 'language', chooser_value(initial=True)),
    ('kiosk-language-form-de', 'language_form', form_value('de')),
    ('kiosk-language-policy', 'language_policy', policy_value()),
])
@pytest.mark.parametrize('fault', ['', 'extra', 'invalid', 'oversize'])
def test_real_decoder_bounds_refusals_and_terminal_latch(operation, key, value, fault):
    value = deepcopy(value)
    if fault == 'extra': value['extra'] = True
    if key == 'language':
        if fault == 'invalid': value['checked'] = 'unknown'
        if fault == 'oversize': value['heading'] = 'x' * 513
    if key == 'language_form':
        if fault == 'invalid': value['request']['approver'] = 'other-fixture-parent'
        if fault == 'oversize': value['texts']['kiosk-request-submit'] = 'x' * 513
    if key == 'language_policy':
        if fault == 'invalid': value['balances']['one_time'] = True
        if fault == 'oversize': value['rows'].extend(value['rows'] * 30)
    payload = dict(operation=operation, outcome='passed', interface='ApplicationUI+external-provider', **{key: value})
    raw = json.dumps(payload, ensure_ascii=False).encode()
    def deliver(*args, **kwargs):
        if kwargs.get('on_output') is not None:
            # Real decoder receives arbitrary SSH chunks, including split UTF-8.
            for index in range(0, len(raw), 37): kwargs['on_output'](raw[index:index + 37])
            kwargs['on_output'](b'\n')
        return raw
    transport = SimpleNamespace(call=Mock(side_effect=deliver), commands=SimpleNamespace(progress=None))
    observer = UiObservations(transport)
    if fault:
        with pytest.raises(EvidenceError): observer.observe(operation)
        with pytest.raises(EvidenceError, match='previous-failure'): observer.observe('kiosk-language-save')
        transport.call.assert_called_once()
    else:
        assert observer.observe(operation) == payload


@pytest.mark.parametrize('stage,fault', [('initial-language', ''), ('initial-language', 'meaning'),
    ('initial-retained', ''), ('initial-retained', 'chooser'), ('initial-retained', 'session'),
    ('initial-retained', 'missing-identity'),
    ('initial-form', ''), ('initial-form', 'visible'), ('initial-form', 'request'),
    ('policy-after', ''), ('policy-after', 'policy'), ('policy-after', 'grant'),
    ('initial-form', 'storage'), ('initial-form', 'replay')])
def test_real_recorder_refuses_before_durable_reply_and_freezes_projection(tmp_path, stage, fault):
    journey = language.KioskLanguageJourney(SimpleNamespace(directory=tmp_path), Mock())
    journey.actions = {'real-interval': Mock(return_value=90)}
    journey.boot = 'a' * 64
    journey.steps = [{'stage': s} for s in journey.plan.stages[:journey.plan.stages.index(stage)]]
    key = 'language' if stage in ('initial-language', 'initial-retained') else 'language_form' if stage == 'initial-form' else 'language_policy'
    value = chooser_value(initial=True, identity=True) if key == 'language' else form_value() if key == 'language_form' else policy_value()
    if stage == 'initial-retained':
        journey.initial_chooser = deepcopy(value)
        if fault in ('chooser', 'session'):
            value['identity'][fault] = 'c' * (32 if fault == 'chooser' else 64)
        if fault == 'missing-identity': value.pop('identity')
    if stage == 'policy-after': journey.policy_projection = deepcopy(value)
    if fault == 'meaning': value['heading'] = 'wrong'
    if fault == 'visible': value['labels']['kiosk-request-submit'] = 'wrong'
    if fault == 'request':
        journey.request_projection = deepcopy(value['request']); value['request']['allow_soft'] = True
    if fault == 'policy': value['rows'][0][1] = 'permanent'
    if fault == 'grant': value['balances']['one_time'] = 1
    if fault == 'storage': journey.progress.side_effect = OSError('storage')
    if fault == 'replay': journey.language_captures.add(stage)
    journey.ui = SimpleNamespace(boot_proof=journey.boot, observe=Mock(return_value={key: value}))
    (tmp_path / (stage + '.request.json')).write_text(json.dumps({'stage': stage, 'screenshot': None}))
    if fault:
        with pytest.raises((EvidenceError, OSError)): journey.step(Mock())
        assert not (tmp_path / (stage + '.reply.json')).exists()
        with pytest.raises(EvidenceError, match='previous-failure'): journey.step(Mock())
    else:
        journey.step(Mock())
        assert (tmp_path / (stage + '.reply.json')).exists()
        if key == 'language_form':
            value['request']['allow_soft'] = True
            assert journey.request_projection['allow_soft'] is False
        if key == 'language_policy':
            value['rows'][0][1] = 'permanent'
            assert journey.policy_projection['rows'][0][1] == 'allowed'


def test_real_startup_steps_reply_before_any_language_capture(tmp_path, monkeypatch):
    import installed_journey
    import installed_setup
    context = SimpleNamespace(directory=tmp_path, installed_snapshot='installed-test',
        host_key='public-host-key', verified=Mock(), commands=Mock(),
        lease=SimpleNamespace(source=SimpleNamespace(uuid='vm-identity'),
            view=SimpleNamespace(domain_id=1), state={'run': 'attempt'}, guard=Mock()))
    transport = Mock()
    setup = Mock()
    monkeypatch.setattr(installed_journey.system, 'address', Mock(return_value='test-host'))
    monkeypatch.setattr(installed_journey, 'Transport', Mock(return_value=transport))
    monkeypatch.setattr(installed_journey, 'ReadOnlyObservations', Mock())
    monkeypatch.setattr(installed_setup, 'InstalledSetup', Mock(return_value=setup))
    progress = Mock()
    journey = language.KioskLanguageJourney(context, progress)
    for stage in ('ready', 'setup-detached'):
        (tmp_path / (stage + '.request.json')).write_text(json.dumps({'stage': stage, 'screenshot': None}))
        journey.step(Mock())
    assert json.loads((tmp_path / 'ready.reply.json').read_bytes()) == {
        'kiosk_language': True, 'invocations': list(language.PLAN.invocations),
        'challenge_bindings': {key: list(value) for key, value in language.PLAN.challenges.items()}}
    assert json.loads((tmp_path / 'setup-detached.reply.json').read_bytes()) == {'setup_complete': True}
    assert [step['stage'] for step in journey.steps] == ['ready', 'setup-detached']
    assert journey.steps[1]['setup'] == {'installed_snapshot': 'installed-test'}
    assert progress.call_count == 2 and not journey.failed
    assert journey.language_captures == set()
    assert journey.request_projection is journey.policy_projection is None
    transport.probe_ready.assert_called_once_with(timeout=180)
    setup.provision.assert_called_once()


@pytest.mark.parametrize('fault', ['', 'meaning', 'durability'])
def test_real_recorder_entry_forwards_plan_and_stops_before_reply(session, tmp_path, monkeypatch, fault):
    from dataclasses import replace
    import installed_journey
    import session_control
    expected = session.payload['assertions'][0]
    tags = {'entry-start': 'system:parent-command-context', 'entry-one': 'system:parent-command-context',
            'entry-two': 'system:parent-command-context', 'chooser': 'ui:kiosk-language-initial'}
    plan = replace(language.PLAN, screen_tags=tags, invocations=(), challenges={},
        stage_actions={},
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
        assert isinstance(journey, language.KioskLanguageJourney) and journey.plan is plan
        journey.steps = [{'stage': 'ready'}, {'stage': 'setup-detached'}]
        journey.boot = 'a' * 64
        journey.vm = SimpleNamespace(read=Mock(return_value={'boot_sha256': journey.boot}))
        value = chooser_value(initial=True)
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
    monkeypatch.setattr(language.KioskLanguageJourney, 'validate', lambda _: [])
    if fault:
        with pytest.raises((EvidenceError, OSError)):
            installed_journey.record_installed_journey(recorder, context, plan, actions={},
                journey_type=language.KioskLanguageJourney)
        assert not (context.directory / 'chooser.reply.json').exists()
    else:
        installed_journey.record_installed_journey(recorder, context, plan, actions={},
            journey_type=language.KioskLanguageJourney)


@pytest.mark.parametrize('fault', ['', *language.SCREENS])
def test_complete_real_worker_sequence_and_refusal_stop(monkeypatch, fault):
    if fault: monkeypatch.setenv('ONPC_TEST_REFUSE_STAGE', fault)
    worker = WORKER.replace('onpc_kiosk_eligible_choices', 'onpc_request_flow')
    worker = worker.replace('onpc_request_flow::run', 'onpc_request_flow::kiosk_language')
    worker = worker.replace('sub record_info { }', "sub record_info { push @main::events, ['title', $_[0]] }")
    worker = worker.replace("if $stage eq 'station-branch';", "if $stage =~ /(?:initial|renewed)-station-branch$/;")
    worker = worker.replace("station_destination => 'default-request-form'", "station_destination => 'initial-request-window'")
    worker = worker.replace('return {observed => $stage};', r'''
        if ($stage eq 'return-qualified' || $stage eq 'return-rechecked') {
            return {observed => $stage, challenge => {id => 'return-parent', role => 'parent',
                surface => 'gdm', check => $stage eq 'return-qualified' ? 'qualified' : 'rechecked'}};
        }
        return {observed => $stage};''')
    worker = worker.replace('    });', '    }, ' + json.dumps(list(language.PLAN.invocations)) +
        ', {"return-parent" => ["parent", "return-qualified", "return-rechecked"]});')
    result = json.loads(run_perl(worker).stdout)
    expected = list(language.SCREENS)
    if fault: expected = expected[:expected.index(fault) + 1]
    assert bool(result['ok']) == (not fault), result['error']
    assert [event[1] for event in result['events'] if event[0] == 'stage'] == expected
    assert [event[1] for event in result['events'] if event[0] == 'title' and event[1] != 'shutdown'] == [
        'kiosk-language-' + stage for stage in expected]
    assert ['power', 'off'] in result['events'] if not fault else ['power', 'off'] not in result['events']
