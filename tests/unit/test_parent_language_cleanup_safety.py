"""Private chooser, decoder and recorder doubles; waited Perl, no live owners."""
from tools.test_storage import named_input
from copy import deepcopy
from dataclasses import replace
import json
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock

import pytest
import accessible_ui as public
import check_e2e_parent_language as selector
import check_e2e_parent_language_isolation as isolation_selector
import check_e2e_parent_rtl as rtl_selector
import check_e2e_parent_dialog_language as dialog_selector
import check_e2e_parent_hebrew_policy as hebrew_policy_selector
import check_graphical_smoke as smoke
import installed_journey
import parent_language as language
import session_control
from owned_commands import CommandError
from private_artifacts import EvidenceError
from tests.support.accessible_ui import Node, ui_for
from tests.support.perl import run_perl
from tests.support.e2e_kiosk import WORKER as AUTH_WORKER
from tests.support.e2e_evidence import attempt
from tests.support.e2e_recording import session
from ui_observations import UiObservations, OPERATION_LABELS


def chooser_value(selected='en', initial=False):
    text = language.TEXTS[selected]
    return {'initial': initial, 'checked': selected.lower(),
            'choices': {key: value[0] for key, value in language.TEXTS.items()},
            'heading': text[1], 'save': text[2], 'save_label': text[2], 'save_description': text[3]}


def state_value(selected='en'):
    return {'child': 'existing-fixture-child', 'limit_enabled': False, 'allowance_minutes': 0,
            'rows': [['parent-app-' + 'a' * 16, 'allowed', 'precise']],
            'management': language.TEXTS[selected][4],
            'management_labels': [language.MANAGEMENT_TITLES[selected]], 'chooser_absent': True}


def chooser_tree(*, initial=False, selected='en'):
    controls = [Node(value[0], identity='language-choice-' + key.lower(),
                     states=('visible', 'sensitive', *(('checked',) if key == selected else ())))
                for key, value in language.TEXTS.items()]
    text = language.TEXTS[selected]
    controls += [Node(text[1], identity='language-title'),
                 Node(text[2], identity='language-continue', description=text[3],
                      children=[Node(text[2], 'label')]),
                 Node(identity='language-cancel')]
    dialog = Node(identity='language-dialog', children=controls)
    marker = Node(identity='parent-language-loading' if initial else 'parent-language-ready')
    window = Node(identity='parent-window', children=[marker, dialog])
    return ui_for(window), window, dialog, controls


def test_rtl_selector_assets_and_worker_registration(monkeypatch, tmp_path):
    from parent_setup_qualification import ParentRtlQualification
    import e2e_worker
    import tools.test_commands as commands
    launch = Mock(return_value=0)
    monkeypatch.setattr(rtl_selector, 'smoke', launch)
    assert rtl_selector.main() == 0
    launch.assert_called_once_with(assets=rtl_selector.ASSETS, provision_credentials=True, parent_rtl=True)
    context = SimpleNamespace(directory=tmp_path)
    journey = ParentRtlQualification.journey(context, Mock())
    assert journey.plan is language.RTL_PLAN and context.installed_snapshot.startswith('onpc-v')
    monkeypatch.setattr(commands.os.path, 'lexists', lambda _: False)
    monkeypatch.setattr(commands, 'allocate_artifact_output', Mock(return_value=str(rtl_selector.ASSETS)))
    for name in ('check_e2e_parent_rtl', 'check_e2e_parent_rtl.py'):
        assert commands.qualification_artifact_command(Path.cwd(), 'integration', [name])[-1] == str(rtl_selector.ASSETS)
    assert all(tag[3:] in public.OPERATIONS and tag[3:] in OPERATION_LABELS
               for tag in language.RTL_SCREENS.values())
    distribution = e2e_worker.distribution_inputs()
    assert b'qualify_rtl' in distribution['lib/onpc_parent.pm']
    assert b'parent_rtl' in distribution['tests/smoke.pm']


@pytest.mark.parametrize('extra', [{}, {'parent_language': True}, {'fresh_desktop': 'parent'},
                                  {'approval_flow': 'cancel'}])
def test_rtl_mode_refuses_before_vm(extra):
    args = {'assets': 'inputs', 'provision_credentials': True, **extra} if extra else {}
    with pytest.raises(CommandError, match='parent-rtl-prerequisites'):
        smoke.main(parent_rtl=True, **args)


def test_dialog_selector_registration_decoder_and_distribution(monkeypatch, tmp_path):
    from parent_setup_qualification import ParentDialogLanguageQualification
    import e2e_worker
    import tools.test_commands as commands
    launch = Mock(return_value=0)
    monkeypatch.setattr(dialog_selector, 'smoke', launch)
    assert dialog_selector.main() == 0
    launch.assert_called_once_with(assets=dialog_selector.ASSETS, provision_credentials=True,
                                  parent_dialog_language=True)
    context = SimpleNamespace(directory=tmp_path)
    journey = ParentDialogLanguageQualification.journey(context, Mock())
    assert journey.plan is language.DIALOG_PLAN and context.installed_snapshot.startswith('onpc-v')
    monkeypatch.setattr(commands.os.path, 'lexists', lambda _: False)
    monkeypatch.setattr(commands, 'allocate_artifact_output', Mock(return_value=str(dialog_selector.ASSETS)))
    for name in ('check_e2e_parent_dialog_language', 'check_e2e_parent_dialog_language.py'):
        assert commands.qualification_artifact_command(Path.cwd(), 'integration', [name])[-1] == str(dialog_selector.ASSETS)
    assert all(tag[3:] in public.OPERATIONS and tag[3:] in OPERATION_LABELS
               for tag in language.DIALOG_SCREENS.values())
    distribution = e2e_worker.distribution_inputs()
    assert b'qualify_dialog_language' in distribution['lib/onpc_parent.pm']
    assert b'parent_dialog_language' in distribution['tests/smoke.pm']


@pytest.mark.parametrize('extra', [{}, {'parent_rtl': True}, {'fresh_desktop': 'parent'}])
def test_dialog_mode_refuses_before_vm(extra):
    args = {'assets': 'inputs', 'provision_credentials': True, **extra} if extra else {}
    with pytest.raises(CommandError, match='parent-dialog-language-prerequisites'):
        smoke.main(parent_dialog_language=True, **args)


@pytest.mark.parametrize('selected', ['en', 'he'])
@pytest.mark.parametrize('fault', ['', 'owner', 'duplicate', 'stale', 'logical', 'name', 'missing'])
def test_dialog_public_snapshot_refusals(selected, fault):
    controls = []
    for identity, expected in public.PARENT_DIALOG_TEXT[selected].items():
        if not identity.startswith('feedback-'): continue
        node = Node(expected, identity=identity)
        text = SimpleNamespace(get_character_count=lambda expected=expected: len(expected),
                               get_text=lambda _a, _b, expected=expected: expected)
        node.get_text_iface = lambda text=text: text
        controls.append(node)
    dialog = Node(identity='feedback-dialog', states=('showing', 'visible', 'sensitive', 'active'), children=controls)
    window = Node(identity='parent-window', children=[dialog])
    ui = ui_for(window)
    if fault == 'owner': ui.owner_pids = lambda: {999}
    if fault == 'duplicate': dialog.children.append(deepcopy(controls[0]))
    if fault == 'stale': controls[0].states.add('defunct')
    if fault == 'logical': controls[0].get_text_iface().get_text = lambda _a, _b: 'changed'
    if fault == 'name': controls[0].name = 'changed'
    if fault == 'missing': window.children.clear()
    if fault:
        with pytest.raises(public.UiError): ui.parent_dialog_presentation('feedback', selected)
    else:
        assert ui.parent_dialog_presentation('feedback', selected) == {
            'surface': 'feedback', 'language': selected,
            'labels': {key: value for key, value in public.PARENT_DIALOG_TEXT[selected].items() if key.startswith('feedback-')}}
    for node in controls: node.action.do_action.assert_not_called()


@pytest.mark.parametrize('fault', ['', 'extra', 'language', 'draft', 'replay', 'inherited'])
def test_dialog_decoder_and_real_recorder_step(tmp_path, fault):
    stage = 'hebrew-feedback-first-read'
    operation = language.DIALOG_SCREENS[stage][3:]
    value = {'surface': 'feedback', 'language': 'he',
             'labels': {key: text for key, text in public.PARENT_DIALOG_TEXT['he'].items() if key.startswith('feedback-')}}
    feedback = {'draft': 'synthetic-rtl', 'attachments': ['diagnostic-logs.zip'],
                'collection': 'ready', 'validation': 'none', 'controls': 'ready'}
    if fault == 'extra': value['private'] = True
    if fault == 'language': value['language'] = 'en'
    if fault == 'draft': feedback['draft'] = 'synthetic-first'
    payload = {'operation': operation, 'outcome': 'passed', 'interface': 'AT-SPI',
               'dialog_presentation': value, 'feedback': feedback}
    transport = SimpleNamespace(call=Mock(return_value=json.dumps(payload, ensure_ascii=False).encode()))
    observer = UiObservations(transport)
    if fault in ('extra', 'language', 'draft'):
        with pytest.raises(EvidenceError): observer.observe(operation)
        with pytest.raises(EvidenceError, match='previous-failure'): observer.observe(operation)
        transport.call.assert_called_once()
        return
    assert observer.observe(operation) == payload
    journey = language.ParentDialogLanguageJourney(SimpleNamespace(directory=tmp_path), Mock())
    journey.committed = 'en' if fault == 'inherited' else 'he'
    journey.steps = [{'stage': item} for item in journey.plan.stages[:journey.plan.stages.index(stage)]]
    journey.boot = 'a' * 64
    journey.ui = SimpleNamespace(boot_proof=journey.boot, observe=Mock(return_value=payload))
    if fault == 'replay': journey.language_captures.add(stage)
    (tmp_path / (stage + '.request.json')).write_text(json.dumps({'stage': stage, 'screenshot': None}))
    if fault:
        with pytest.raises(EvidenceError): journey.step(Mock())
        assert not (tmp_path / (stage + '.reply.json')).exists()
    else:
        journey.step(Mock())
        assert (tmp_path / (stage + '.reply.json')).exists()


@pytest.mark.parametrize('fault', ['', 'choice', 'text', 'extra', 'replay'])
def test_presentation_decoder_and_real_recorder_step(tmp_path, fault):
    stage = 'hebrew-choose'
    operation = 'parent-language-choose-he'
    value = chooser_value('he')
    if fault == 'choice': value['checked'] = 'en'
    if fault == 'text': value['heading'] = language.TEXTS['en'][1]
    if fault == 'extra': value['private'] = True
    payload = {'operation': operation, 'outcome': 'passed', 'interface': 'AT-SPI',
               'language': value}
    transport = SimpleNamespace(call=Mock(return_value=json.dumps(payload, ensure_ascii=False).encode()))
    observer = UiObservations(transport)
    if fault == 'extra':
        with pytest.raises(EvidenceError): observer.observe(operation)
        with pytest.raises(EvidenceError, match='previous-failure'): observer.observe(operation)
        transport.call.assert_called_once()
    else:
        assert observer.observe(operation) == payload
    journey = language.ParentRtlJourney(SimpleNamespace(directory=tmp_path), Mock())
    journey.committed, journey.candidate = 'en', 'he'
    journey.steps = [{'stage': item} for item in journey.plan.stages[:journey.plan.stages.index(stage)]]
    journey.boot = 'a' * 64
    journey.ui = SimpleNamespace(boot_proof=journey.boot, observe=Mock(return_value=payload))
    if fault == 'replay': journey.language_captures.add(stage)
    (tmp_path / (stage + '.request.json')).write_text(json.dumps({'stage': stage, 'screenshot': None}))
    if fault:
        with pytest.raises(EvidenceError): journey.step(Mock())
        assert not (tmp_path / (stage + '.reply.json')).exists()
    else:
        journey.step(Mock())
        assert (tmp_path / (stage + '.reply.json')).exists()


def test_selector_snapshot_assets_and_all_operation_registration(monkeypatch, tmp_path):
    from parent_setup_qualification import ParentLanguageQualification, KioskEntryQualification
    import e2e_worker
    import tools.test_commands as commands
    launch = Mock(return_value=0)
    monkeypatch.setattr(selector, 'smoke', launch)
    assert selector.main() == 0
    launch.assert_called_once_with(assets=selector.ASSETS, provision_credentials=True, parent_language=True)
    from tools.test_storage import named_input
    assert selector.ASSETS == named_input(package_source=True)
    assert selector.ASSETS == named_input()
    context = SimpleNamespace(directory=tmp_path)
    journey = ParentLanguageQualification.journey(context, Mock())
    assert journey.plan is language.PLAN and context.installed_snapshot.startswith('onpc-v')
    assert ParentLanguageQualification.attach_installed_snapshot is KioskEntryQualification.attach_installed_snapshot
    monkeypatch.setattr(commands.os.path, 'lexists', lambda _: False)
    monkeypatch.setattr(commands, 'allocate_artifact_output', Mock(return_value=str(selector.ASSETS)))
    command = commands.qualification_artifact_command(Path.cwd(), 'integration', ['check_e2e_parent_language'])
    assert command[-1] == str(selector.ASSETS)
    assert set(language.PLAN.phases) == set(language.PLAN.stages)
    assert all(tag[3:] in public.OPERATIONS and tag[3:] in OPERATION_LABELS
               for tag in language.PLAN.screen_tags.values())
    distribution = e2e_worker.distribution_inputs()
    assert b'parent_language' in distribution['tests/smoke.pm']
    assert b'qualify_language' in distribution['lib/onpc_parent.pm']
    assert language.PLAN.screen_tags['same-parent-window'] == 'ui:parent-language-state'


def test_isolation_selector_and_complete_registered_composition(monkeypatch, tmp_path):
    from parent_setup_qualification import ParentLanguageIsolationQualification
    import e2e_worker
    import tools.test_commands as commands
    launch = Mock(return_value=0)
    monkeypatch.setattr(isolation_selector, 'smoke', launch)
    assert isolation_selector.main() == 0
    launch.assert_called_once_with(assets=isolation_selector.ASSETS,
        provision_credentials=True, parent_language_isolation=True)
    context = SimpleNamespace(directory=tmp_path)
    journey = ParentLanguageIsolationQualification.journey(context, Mock())
    assert journey.plan is language.ISOLATION_PLAN
    assert context.installed_snapshot.startswith('onpc-v')
    monkeypatch.setattr(commands.os.path, 'lexists', lambda _: False)
    monkeypatch.setattr(commands, 'allocate_artifact_output', Mock(return_value=str(isolation_selector.ASSETS)))
    for name in ('check_e2e_parent_language_isolation', 'check_e2e_parent_language_isolation.py'):
        command = commands.qualification_artifact_command(Path.cwd(), 'integration', [name])
        assert command[-1] == str(isolation_selector.ASSETS)
    assert set(language.ISOLATION_PLAN.phases) == set(language.ISOLATION_PLAN.stages)
    assert all(tag[3:] in public.OPERATIONS and tag[3:] in OPERATION_LABELS
               for tag in language.ISOLATION_SCREENS.values())
    distribution = e2e_worker.distribution_inputs()
    assert b'qualify_language_isolation' in distribution['lib/onpc_parent.pm']
    assert b'parent_language_isolation' in distribution['tests/smoke.pm']


@pytest.mark.parametrize('extra', [{}, {'parent_language': True}, {'fresh_desktop': 'parent'},
                                  {'approval_flow': 'cancel'}])
def test_isolation_mode_refuses_before_vm(extra):
    args = {'assets': 'inputs', 'provision_credentials': True, **extra} if extra else {}
    with pytest.raises(CommandError, match='parent-language-isolation-prerequisites'):
        smoke.main(parent_language_isolation=True, **args)


@pytest.mark.parametrize('name', ['check_e2e_parent_language', 'check_e2e_parent_language.py',
    'check_e2e_parent_hebrew_policy', 'check_e2e_parent_hebrew_policy.py'])
@pytest.mark.parametrize('existing', [False, True])
def test_automatic_inputs_bind_current_source_and_preserve_existing(monkeypatch, name, existing):
    import tools.test_commands as commands
    from tools.test_storage import named_input
    expected = str(named_input(package_source=True))
    inspected = []
    monkeypatch.setattr(commands.os.path, 'lexists', lambda path: inspected.append(path) or existing)
    validate = Mock()
    allocate = Mock(return_value=expected)
    monkeypatch.setattr(commands, 'artifact_path', validate)
    monkeypatch.setattr(commands, 'allocate_artifact_output', allocate)
    command = commands.qualification_artifact_command(Path.cwd(), 'integration', [name])
    assert inspected == [expected]
    if existing:
        assert command is None
        validate.assert_called_once_with(expected)
        allocate.assert_not_called()
    else:
        assert command[-1] == expected
        allocate.assert_called_once_with(expected)
        validate.assert_not_called()


@pytest.mark.parametrize('extra', [{}, {'parent_toggle': True}, {'chinese_native_auth': True},
                                  {'fresh_desktop': 'parent'}, {'approval_flow': 'cancel'}])
def test_exclusive_mode_refuses_before_vm(extra):
    args = {'assets': 'inputs', 'provision_credentials': True, **extra} if extra else {}
    with pytest.raises(CommandError, match='parent-language-prerequisites'):
        smoke.main(parent_language=True, **args)


@pytest.mark.parametrize('initial', [False, True])
@pytest.mark.parametrize('fault', ['', 'duplicate', 'missing', 'unchecked', 'multiple', 'stale',
                                  'wrong-owner', 'wrong-frontend', 'wrong-entry'])
def test_actual_chooser_read_is_complete_owned_and_input_free(initial, fault):
    ui, window, dialog, controls = chooser_tree(initial=initial)
    if fault == 'duplicate': dialog.children.append(Node(identity='language-title'))
    if fault == 'missing': dialog.children.remove(controls[3])
    if fault == 'unchecked': controls[0].states.discard('checked')
    if fault == 'multiple': controls[1].states.add('checked')
    if fault == 'stale': controls[0].states.add('defunct')
    if fault == 'wrong-owner': ui.owner_pids = lambda: {999}
    if fault == 'wrong-frontend': ui.application_ids = (public.KIOSK_APPLICATION,)
    if fault == 'wrong-entry': window.children[0].identity = 'parent-language-ready' if initial else 'parent-language-loading'
    ui.complete_parent_language_setup = Mock(side_effect=AssertionError('automatic setup'))
    if fault:
        with pytest.raises(public.UiError): ui.read_parent_language(initial=initial)
    else:
        assert ui.read_parent_language(initial=initial) == chooser_value(initial=initial)
    for control in controls: control.action.do_action.assert_not_called()
    ui.complete_parent_language_setup.assert_not_called()


@pytest.mark.parametrize('initial', [False, True])
@pytest.mark.parametrize('next_read', ['valid', 'wrong-owner', 'duplicate', 'stale'])
def test_chooser_reacquires_stale_snapshot_with_original_deadline(monkeypatch, initial, next_read):
    ui, window, dialog, controls = chooser_tree(initial=initial)
    stale = Node(identity='retired-control', states=('defunct',))
    dialog.children.append(stale)
    ui.timeout = 1
    clock = [0]
    monkeypatch.setattr(public.time, 'monotonic', lambda: clock[0])
    snapshots = []
    read = ui.read_snapshot
    def capture(*args, **kwargs):
        value = read(*args, **kwargs)
        snapshots.append(value)
        return value
    ui.read_snapshot = capture
    def advance(_seconds):
        for control in controls:
            control.action.do_action.assert_not_called()
        clock[0] += .5
        if next_read != 'stale' and stale in dialog.children:
            dialog.children.remove(stale)
            if next_read == 'wrong-owner': ui.owner_pids = lambda: {999}
            if next_read == 'duplicate': dialog.children.append(Node(identity='language-title'))
    monkeypatch.setattr(public.time, 'sleep', advance)
    if next_read == 'valid':
        assert ui.read_parent_language(initial=initial) == chooser_value(initial=initial)
    else:
        error = {'wrong-owner': 'ui:wrong-owner', 'duplicate': 'ui:ambiguous-automation-id',
                 'stale': 'ui:language-stale'}[next_read]
        with pytest.raises(public.UiError, match=error):
            ui.read_parent_language(initial=initial)
    assert len(snapshots) == (3 if next_read == 'stale' else 2)
    assert snapshots[0][1] is not snapshots[1][1]
    assert stale in snapshots[0][0]
    assert (stale in snapshots[-1][0]) == (next_read == 'stale')
    assert ui._observation_cache is None
    assert clock[0] <= 1
    for control in controls:
        control.action.do_action.assert_not_called()


@pytest.mark.parametrize('operation', ['parent-language-choose-de', 'parent-language-save', 'parent-language-cancel'])
def test_stale_chooser_releases_no_language_input(operation):
    ui, window, dialog, controls = chooser_tree()
    controls[0].states.add('defunct')
    with pytest.raises(public.UiError, match='ui:language-stale'):
        ui.parent_language_operation(operation)
    for control in controls:
        control.action.do_action.assert_not_called()


@pytest.mark.parametrize('operation', ['parent-language-choose-de', 'parent-language-save', 'parent-language-cancel'])
def test_disabled_input_and_uncertain_response_never_replay(operation):
    ui, window, dialog, controls = chooser_tree()
    target = next(node for node in controls if node.identity == {
        'parent-language-choose-de': 'language-choice-de',
        'parent-language-save': 'language-continue', 'parent-language-cancel': 'language-cancel'}[operation])
    target.states.discard('sensitive')
    with pytest.raises(public.UiError): ui.parent_language_operation(operation)
    target.action.do_action.assert_not_called()
    target.states.add('sensitive'); target.states.add('showing')
    target.action.do_action.return_value = False
    with pytest.raises(public.UiError): ui.parent_language_operation(operation)
    assert ui.input_uncertain
    with pytest.raises(public.UiError): ui.parent_language_operation(operation)
    target.action.do_action.assert_called_once()


@pytest.mark.parametrize('fault', ['', 'choice', 'heading', 'extra', 'oversize', 'policy'])
def test_real_decoder_and_terminal_failure(fault):
    operation = 'parent-language-state' if fault == 'policy' else 'parent-language-initial'
    value = state_value() if fault == 'policy' else chooser_value(initial=True)
    key = 'language_state' if fault == 'policy' else 'language'
    if fault == 'choice': value['checked'] = 'private-choice'
    if fault == 'heading': value['heading'] = ''
    if fault == 'extra': value['extra'] = 'private'
    if fault == 'oversize': value['save_description'] = 'x' * 513
    if fault == 'policy': value['rows'][0][1] = 'unknown'
    payload = {'operation': operation, 'outcome': 'passed', 'interface': 'AT-SPI', key: value}
    transport = SimpleNamespace(call=Mock(return_value=json.dumps(payload, ensure_ascii=False).encode()))
    observer = UiObservations(transport)
    if fault:
        with pytest.raises(EvidenceError): observer.observe(operation)
        with pytest.raises(EvidenceError, match='previous-failure'): observer.observe('parent-language-save')
        transport.call.assert_called_once()
    else:
        assert observer.observe(operation) == payload


@pytest.mark.parametrize('fault', ['', 'not-list', 'too-many', 'oversize', 'not-text'])
def test_management_labels_decoder_bounds_and_realistic_policy_size(fault):
    value = state_value()
    value['rows'] = [[f'parent-app-{index:016x}', 'allowed', 'precise'] for index in range(128)]
    if fault == 'not-list': value['management_labels'] = 'Screen Time Limit'
    if fault == 'too-many': value['management_labels'] *= 65
    if fault == 'oversize': value['management_labels'] = ['x' * 513]
    if fault == 'not-text': value['management_labels'] = [True]
    payload = {'operation': 'parent-language-state', 'outcome': 'passed',
               'interface': 'AT-SPI', 'language_state': value}
    transport = SimpleNamespace(call=Mock(return_value=json.dumps(payload).encode()))
    observer = UiObservations(transport)
    if fault:
        with pytest.raises(EvidenceError, match='ui:language-state'):
            observer.observe('parent-language-state')
        with pytest.raises(EvidenceError, match='previous-failure'):
            observer.observe('parent-language-open')
        transport.call.assert_called_once()
    else:
        assert observer.observe('parent-language-state') == payload


@pytest.mark.parametrize('fault', ['', 'wrong-owner', 'duplicate', 'stale', 'hidden-label',
                                  'outside-page'])
def test_management_reader_uses_owned_page_and_only_visible_labels(fault):
    toggle = Node('Screen time limit', identity='parent-screen-limit-toggle')
    label = Node('Screen Time Limit', 'label')
    page = Node(identity='parent-screen-limits-page', children=[toggle, label])
    window = Node(identity='parent-window', children=[page])
    ui = ui_for(window)
    if fault == 'wrong-owner': ui.owner_pids = lambda: {999}
    if fault == 'duplicate': page.children.append(Node(identity='parent-screen-limit-toggle'))
    if fault == 'stale': label.states.add('defunct')
    if fault == 'hidden-label': label.states.discard('showing')
    if fault == 'outside-page':
        page.children.remove(toggle)
        window.children.append(toggle)
        toggle.parent = window
    if fault:
        with pytest.raises(public.UiError): ui.parent_language_management()
    else:
        assert ui.parent_language_management() == {
            'management': 'Screen time limit', 'management_labels': ['Screen Time Limit']}
    for node in (toggle, label, page, window):
        node.action.do_action.assert_not_called()


WORKER = r'''
use strict;
use warnings;
use JSON::PP;
our @events;
our $fault = shift @ARGV;
BEGIN { $INC{'testapi.pm'} = 1; $INC{'onpc_gdm.pm'} = 1; }
package onpc_gdm;
sub reattach_functional { }
package testapi;
sub record_info { push @main::events, ['title', $_[0]] }
sub send_key { push @main::events, ['key', $_[0]] }
package main;
require onpc_parent;
require onpc_journey;
no warnings 'redefine';
*onpc_parent::sign_in = sub { $_[0]->seen('desktop') };
*onpc_journey::finish = sub { push @events, ['finish'] };
my $ok = eval {
    onpc_parent::qualify_language(sub {
        my ($stage) = @_;
        push @events, ['seen', $stage];
        die 'refusal' if $fault eq $stage;
        return {observed => $stage};
    });
    1;
};
print encode_json({ok => $ok ? 1 : 0, error => $@, events => \@events});
'''


@pytest.mark.parametrize('fault', ['', *list(language.PLAN.screen_tags)[4:]])
def test_actual_worker_order_titles_and_no_later_input(fault):
    result = json.loads(run_perl(WORKER, fault).stdout)
    # Authentication has separate shared guard tests; this probe starts at its
    # independently supplied desktop proof and executes the real remaining recipe.
    stages = list(language.PLAN.screen_tags)[4:]
    expected = stages if not fault else stages[:stages.index(fault) + 1]
    assert [event[1] for event in result['events'] if event[0] == 'seen'] == expected
    assert [event[1] for event in result['events'] if event[0] == 'title'] == [
        'parent-language-' + stage for stage in expected]
    assert bool(result['ok']) == (not fault), result['error']
    assert (['finish'] in result['events']) == (not fault)
    assert [event for event in result['events'] if event[0] == 'key'] == (
        [['key', 'alt-f4']] if 'closed' in expected else [])


@pytest.mark.parametrize('fault', ['', *list(language.RTL_SCREENS)[4:]])
def test_rtl_worker_actual_order_and_no_keyboard_after_refusal(fault):
    worker = WORKER.replace('onpc_parent::qualify_language(', 'onpc_parent::qualify_rtl(')
    result = json.loads(run_perl(worker, fault).stdout)
    stages = list(language.RTL_SCREENS)[4:]
    expected = stages if not fault else stages[:stages.index(fault) + 1]
    assert [event[1] for event in result['events'] if event[0] == 'seen'] == expected
    assert [event[1] for event in result['events'] if event[0] == 'title'] == [
        'parent-rtl-' + stage for stage in expected]
    assert bool(result['ok']) == (not fault), result['error']
    assert (['finish'] in result['events']) == (not fault)
    keys = [['key', 'tab'] for index, stage in enumerate(expected)
            if stage.endswith(('-focus', '-refocus')) and index + 1 < len(expected)]
    assert [event for event in result['events'] if event[0] == 'key'] == keys


@pytest.mark.parametrize('fault', ['', 'feedback-empty', 'text-body-rtl-selected',
    'draft-seeded', 'hebrew-about-first-open', 'hebrew-about-first-read',
    'hebrew-feedback-first-open', 'hebrew-feedback-first-read', 'restored-feedback-first-read'])
def test_dialog_worker_actual_order_and_refusal(fault):
    worker = WORKER.replace('onpc_parent::qualify_language(', 'onpc_parent::qualify_dialog_language(')
    worker = worker.replace("sub send_key {", "sub type_string { push @main::events, ['type', $_[0]] }\nsub send_key {")
    result = json.loads(run_perl(worker, fault).stdout)
    stages = list(language.DIALOG_SCREENS)[4:]
    expected = stages if not fault else stages[:stages.index(fault) + 1]
    assert [event[1] for event in result['events'] if event[0] == 'seen'] == expected
    assert [event[1] for event in result['events'] if event[0] == 'title'] == [
        'parent-dialog-language-' + stage for stage in expected]
    assert bool(result['ok']) == (not fault), result['error']
    assert (['finish'] in result['events']) == (not fault)
    if not fault:
        typed = [event[1] for event in result['events'] if event[0] == 'type']
        assert typed == ['5e9', '5dc', '5d5', '5dd', ' Alex 75', 'rtl-check@example.invalid']
        assert len([event for event in result['events'] if event == ['key', 'alt-f4']]) == 7
        navigation = [event[1] for event in result['events']
                      if event[0] == 'key' and event[1] in ('tab', 'shift-tab')]
        assert navigation == []
    assert not any(event in (['key', 'ret'], ['key', 'spc']) for event in result['events']
                   if fault == 'feedback-empty')


@pytest.mark.parametrize('binding', ['body-rtl', 'reply-rtl'])
@pytest.mark.parametrize('fault', ['', 'selected', 'read'])
def test_dialog_host_text_block_uses_actual_worker_and_refuses_input(monkeypatch, binding, fault):
    from tests.support.gui_blocks import run_block
    from tests.support import keyboard
    events = []
    def observe(operation, _version):
        events.append(('observe', operation))
        if fault and operation.endswith('-' + fault): raise public.UiError('host:refusal')
        return {'operation': operation}
    ui = SimpleNamespace(run=observe, api=SimpleNamespace(StateType=SimpleNamespace(FOCUSED='focused', ACTIVE='active')))
    monkeypatch.setattr(keyboard, 'key_combo', lambda _ui, identity, keys, **kwargs: events.append(('key', identity, keys)))
    monkeypatch.setattr(keyboard, 'type_text', lambda _ui, identity, text, **kwargs: events.append(('text', identity, text, kwargs['interval'])))
    if fault:
        with pytest.raises(public.UiError, match='host:refusal'): run_block(ui, 'replace', binding)
        assert events[-1] == ('observe', 'text-' + binding + '-' + fault)
    else:
        run_block(ui, 'replace', binding)
    typed = [event for event in events if event[0] == 'text']
    if fault == 'selected': assert typed == []
    elif binding == 'body-rtl':
        assert typed == [('text', 'feedback-editor-input', value, pacing) for value, pacing in
                         [('5e9', 0), ('5dc', 0), ('5d5', 0), ('5dd', 0), (' Alex 75', .02)]]
        assert [event[2] for event in events if event[0] == 'key'] == [
            '<Control>a', *['<Control><Shift>u', 'Return'] * 4]
    else:
        assert typed == [('text', 'feedback-reply-email', 'rtl-check@example.invalid', .02)]


@pytest.mark.parametrize('fault', ['', *list(language.PLAN.screen_tags)[:4]])
def test_complete_worker_includes_fresh_authentication_and_refusal(monkeypatch, fault):
    if fault: monkeypatch.setenv('ONPC_TEST_REFUSE_STAGE', fault)
    worker = AUTH_WORKER.replace('onpc_kiosk_eligible_choices', 'onpc_parent')
    worker = worker.replace('onpc_parent::run', 'onpc_parent::qualify_language')
    worker = worker.replace('sub record_info { }', "sub record_info { push @main::events, ['title', $_[0]] }")
    result = json.loads(run_perl(worker).stdout)
    expected = list(language.PLAN.screen_tags)
    if fault: expected = expected[:expected.index(fault) + 1]
    assert bool(result['ok']) == (not fault), result['error']
    assert [event[1] for event in result['events'] if event[0] == 'stage'] == expected
    assert [event[1] for event in result['events'] if event[0] == 'title' and event[1] != 'shutdown'] == [
        'parent-language-' + stage for stage in expected]
    assert result['events'].count(['secret']) == (0 if fault else 1)


@pytest.mark.parametrize('fault', ['', *list(language.ISOLATION_SCREENS)[4:]])
def test_isolation_actual_worker_sequence_and_refusal(fault):
    worker = WORKER.replace('onpc_parent::qualify_language(', 'onpc_parent::qualify_language_isolation(')
    worker = worker.replace("return {observed => $stage};",
        "return {observed => $stage, ui_focused => JSON::PP::true};")
    result = json.loads(run_perl(worker, fault).stdout)
    stages = list(language.ISOLATION_SCREENS)[4:]
    expected = stages if not fault else stages[:stages.index(fault) + 1]
    assert [event[1] for event in result['events'] if event[0] == 'seen'] == expected
    assert [event[1] for event in result['events'] if event[0] == 'title'] == [
        'parent-language-isolation-' + stage for stage in expected]
    assert bool(result['ok']) == (not fault), result['error']
    assert (['finish'] in result['events']) == (not fault)
    keys = []
    for index, stage in enumerate(expected):
        if stage.endswith('-ready') and ('-setup-' in stage or stage.startswith(('riley-', 'jordan-', 'reopened-'))):
            if index + 1 < len(expected): keys.append(['key', 'spc'])
        elif stage.endswith('-focus'):
            if index + 1 < len(expected): keys.append(['key', 'ret'])
        elif stage == 'close-ready' and index + 1 < len(expected): keys.append(['key', 'alt-f4'])
    assert [event for event in result['events'] if event[0] == 'key'] == keys


@pytest.mark.parametrize('fault', ['', 'renamed-choose', 'renamed-state', 'renamed-reopen'])
def test_shared_language_roundtrip_supports_independent_invocation(fault):
    worker = WORKER.replace('onpc_parent::qualify_language(sub {',
        "onpc_parent::language_presentation_roundtrip(onpc_journey->new(prefix => 'independent', review => 0, exchange => sub {")
    worker = worker.replace('    });\n    1;', "    }), 'renamed');\n    1;")
    result = json.loads(run_perl(worker, fault).stdout)
    stages = ['renamed-' + suffix for suffix in ('open', 'choose',
        'save', 'state', 'reopen', 'cancel', 'preserved')]
    expected = stages if not fault else stages[:stages.index(fault) + 1]
    assert [event[1] for event in result['events'] if event[0] == 'seen'] == expected
    assert [event[1] for event in result['events'] if event[0] == 'title'] == [
        'independent-' + stage for stage in expected]
    assert bool(result['ok']) == (not fault), result['error']


def test_hebrew_policy_selector_and_complete_composition(monkeypatch, tmp_path):
    from parent_setup_qualification import ParentHebrewPolicyQualification
    import e2e_worker
    import tools.test_commands as commands
    launch = Mock(return_value=0)
    monkeypatch.setattr(hebrew_policy_selector, 'smoke', launch)
    assert hebrew_policy_selector.main() == 0
    launch.assert_called_once_with(assets=hebrew_policy_selector.ASSETS,
        provision_credentials=True, parent_hebrew_policy=True)
    context = SimpleNamespace(directory=tmp_path)
    journey = ParentHebrewPolicyQualification.journey(context, Mock())
    assert journey.plan is language.HEBREW_POLICY_PLAN
    assert context.installed_snapshot.startswith('onpc-v')
    monkeypatch.setattr(commands.os.path, 'lexists', lambda _: False)
    monkeypatch.setattr(commands, 'allocate_artifact_output',
                        Mock(return_value=str(hebrew_policy_selector.ASSETS)))
    for name in ('check_e2e_parent_hebrew_policy', 'check_e2e_parent_hebrew_policy.py'):
        assert commands.qualification_artifact_command(Path.cwd(), 'integration', [name])[-1] == str(hebrew_policy_selector.ASSETS)
    assert set(journey.plan.phases) == set(journey.plan.stages)
    assert all(tag[3:] in public.OPERATIONS and tag[3:] in OPERATION_LABELS
               for tag in journey.plan.screen_tags.values())
    distribution = e2e_worker.distribution_inputs()
    assert b'qualify_hebrew_policy' in distribution['lib/onpc_parent.pm']
    assert b'parent_hebrew_policy' in distribution['tests/smoke.pm']


@pytest.mark.parametrize('extra', [{}, {'parent_language': True}, {'parent_rtl': True},
                                  {'fresh_desktop': 'parent'}, {'approval_flow': 'cancel'}])
def test_hebrew_policy_mode_refuses_before_vm(extra):
    args = {'assets': 'inputs', 'provision_credentials': True, **extra} if extra else {}
    with pytest.raises(CommandError, match='parent-hebrew-policy-prerequisites'):
        smoke.main(parent_hebrew_policy=True, **args)


@pytest.mark.parametrize('fault', ['', *list(language.HEBREW_POLICY_SCREENS)[4:]])
def test_hebrew_policy_real_worker_order_titles_and_terminal_refusal(fault):
    worker = WORKER.replace('onpc_parent::qualify_language(', 'onpc_parent::qualify_hebrew_policy(')
    worker = worker.replace('return {observed => $stage};',
        'return {observed => $stage, ui_focused => JSON::PP::true};')
    result = json.loads(run_perl(worker, fault).stdout)
    stages = list(language.HEBREW_POLICY_SCREENS)[4:]
    expected = stages if not fault else stages[:stages.index(fault) + 1]
    assert [event[1] for event in result['events'] if event[0] == 'seen'] == expected
    assert [event[1] for event in result['events'] if event[0] == 'title'] == [
        'parent-hebrew-policy-' + stage for stage in expected]
    assert bool(result['ok']) == (not fault), result['error']
    assert (['finish'] in result['events']) == (not fault)
    keys = []
    for index, stage in enumerate(expected[:-1]):
        if stage == 'riley-setup-ready': keys.append(['key', 'spc'])
        elif stage == 'riley-setup-focus': keys.append(['key', 'ret'])
    assert [event for event in result['events'] if event[0] == 'key'] == keys


@pytest.mark.parametrize('fault', ['', 'uid', 'disabled', 'allowance', 'language', 'number', 'extra'])
def test_hebrew_policy_actual_decoder_terminal_refusal(fault):
    value = enabled_value(selected='he')
    if fault == 'uid': value['child'] = 'existing-fixture-child'
    if fault == 'disabled': value['limit_enabled'] = False
    if fault == 'allowance': value['allowance_minutes'] = 30
    if fault == 'language': value['balances']['daily']['text'] = '1h'
    if fault == 'number': value['balances']['daily']['seconds'] = 3599
    if fault == 'extra': value['balances']['private'] = True
    operation = 'parent-language-riley-enabled-he'
    payload = {'operation': operation, 'outcome': 'passed', 'interface': 'AT-SPI', 'language_state': value}
    observer = UiObservations(SimpleNamespace(call=Mock(return_value=json.dumps(payload).encode())))
    if fault:
        with pytest.raises(EvidenceError): observer.observe(operation)
        with pytest.raises(EvidenceError, match='previous-failure'): observer.observe(operation)
    else:
        assert observer.observe(operation) == payload


@pytest.mark.parametrize('stage,selected', [('english-entry-state', 'en'),
    ('english-entry-preserved', 'en'), ('hebrew-state', 'he'), ('hebrew-preserved', 'he'),
    ('english-return-state', 'en'), ('english-return-preserved', 'en')])
@pytest.mark.parametrize('fault', ['', 'uid', 'disabled', 'allowance', 'language', 'policy',
    'name', 'grant', 'unequal', 'elapsed', 'decrease', 'replay', 'missing-baseline'])
def test_hebrew_policy_real_recorder_preserves_immutable_baseline_before_reply(tmp_path, stage, selected, fault):
    journey = language.ParentHebrewPolicyJourney(SimpleNamespace(directory=tmp_path), Mock())
    baseline = enabled_value()
    if fault != 'missing-baseline':
        journey.check_settings('riley-before', {'ui': {'language_state': baseline}})
        baseline['app_names'][0][1] = 'mutated input'
        assert journey.public_captures['english'][0]['app_names'][0][1] == 'Fixture application'
    journey.committed = journey.candidate = selected
    journey.steps = [{'stage': item} for item in journey.plan.stages[:journey.plan.stages.index(stage)]]
    journey.boot = 'a' * 64
    value = enabled_value(selected=selected, elapsed=10)
    if fault == 'uid': value['child'] = 'existing-fixture-child'
    if fault == 'disabled': value['limit_enabled'] = False
    if fault == 'allowance': value['allowance_minutes'] = 30
    if fault == 'language': value['management'] = language.TEXTS['de'][4]
    if fault == 'policy': value['rows'][0][1] = 'permanent'
    if fault == 'name': value['app_names'][0][1] = 'changed app'
    if fault == 'grant': value['balances']['one_time']['seconds'] = 1
    if fault == 'unequal': value['balances']['total']['seconds'] = 3599
    if fault == 'elapsed': value['balances']['observed_monotonic_ns'] = 701 * 10**9
    if fault == 'decrease':
        value['balances']['daily']['seconds'] = value['balances']['total']['seconds'] = 3500
    if fault == 'replay': journey.language_captures.add(stage)
    journey.ui = SimpleNamespace(boot_proof=journey.boot, observe=Mock(return_value={'language_state': value}))
    (tmp_path / (stage + '.request.json')).write_text(json.dumps({'stage': stage, 'screenshot': None}))
    if fault:
        with pytest.raises(EvidenceError): journey.step(Mock())
        assert not (tmp_path / (stage + '.reply.json')).exists()
    else:
        journey.step(Mock())
        assert (tmp_path / (stage + '.reply.json')).exists()


def enabled_value(child='child', selected='en', elapsed=0):
    account = public.NAMED_CUSTOM_CHILDREN[child]
    value = state_value(selected)
    value.update(child=public.CHILD_IDENTITIES[account], account_name=account,
        limit_enabled=True, allowance_minutes=60,
        management_labels=sorted(language.ENABLED_LABELS[selected]),
        app_names=[[value['rows'][0][0], 'Fixture application']],
        balances={'child': public.CHILD_IDENTITIES[account], 'expanded': True,
                  'observed_monotonic_ns': (100 + elapsed) * 10**9})
    for key, seconds in (('daily', 3600), ('one_time', 0), ('total', 3600)):
        text = {'en': ('1h', '0m'), 'zh-Hans': ('1小时', '0分钟'),
                'he': ('1ש׳', '0דק׳')}[selected][not seconds]
        value['balances'][key] = public.duration_projection(text, language=selected)
    return value


@pytest.mark.parametrize('child', ['child', 'existing'])
@pytest.mark.parametrize('fault', ['', 'wrong-uid', 'wrong-label', 'duplicate', 'stale', 'open'])
def test_language_selection_proves_uid_and_closed_picker_without_english_settings(child, fault):
    account = public.NAMED_CUSTOM_CHILDREN[child]
    uid = 1001 if child == 'child' else 1002
    selected = Node(identity=f'parent-child-selected-{uid}', children=[Node(account, 'label')])
    if fault == 'wrong-uid': selected.identity = f'parent-child-selected-{uid + 10}'
    if fault == 'wrong-label': selected.children[0].name = 'wrong account'
    if fault == 'stale': selected.states.add('defunct')
    picker = Node(identity='parent-child-selector', children=[selected])
    if fault == 'duplicate': picker.children.append(deepcopy(selected))
    window = Node(identity='parent-window', children=[picker,
        Node(identity='parent-daily-limit-selector', children=[Node('1 小时', 'label')])])
    if fault == 'open': window.children.append(Node(identity='parent-child-popover'))
    ui = ui_for(window); ui.timeout = .05
    ui.settings = Mock(side_effect=AssertionError('English settings reader'))
    operation = f'parent-language-{"riley" if child == "child" else "jordan"}-selected'
    if fault:
        with pytest.raises(public.UiError): ui.parent_language_operation(operation)
    else:
        assert ui.parent_language_operation(operation) == {
            'child_selection': {'child': public.CHILD_IDENTITIES[account]}}
    ui.settings.assert_not_called()
    picker.action.do_action.assert_not_called()


@pytest.mark.parametrize('child', ['child', 'existing'])
@pytest.mark.parametrize('fault', ['', 'wrong-child', 'extra', 'missing', 'replay'])
def test_language_selection_decoder_and_recorder_refuse_before_reply(tmp_path, child, fault):
    name = 'riley' if child == 'child' else 'jordan'
    operation = f'parent-language-{name}-selected'
    value = {'child': public.CHILD_IDENTITIES[public.NAMED_CUSTOM_CHILDREN[child]]}
    if fault == 'wrong-child': value['child'] = 'wrong-child'
    if fault == 'extra': value['private'] = 'canary'
    payload = {'operation': operation, 'outcome': 'passed', 'interface': 'AT-SPI'}
    if fault != 'missing': payload['child_selection'] = value
    observer = UiObservations(SimpleNamespace(call=Mock(return_value=json.dumps(payload).encode())))
    if fault in ('wrong-child', 'extra', 'missing'):
        with pytest.raises(EvidenceError): observer.observe(operation)
        with pytest.raises(EvidenceError, match='previous-failure'): observer.observe(operation)
    else:
        assert observer.observe(operation) == payload
    journey = language.ParentLanguageIsolationJourney(SimpleNamespace(directory=tmp_path), Mock())
    stage = name + '-selected'
    journey.steps = [{'stage': item} for item in journey.plan.stages[:journey.plan.stages.index(stage)]]
    journey.boot = 'a' * 64
    journey.ui = SimpleNamespace(boot_proof=journey.boot, observe=Mock(return_value=payload))
    if fault == 'replay': journey.language_captures.add(stage)
    (tmp_path / (stage + '.request.json')).write_text(json.dumps({'stage': stage, 'screenshot': None}))
    if fault:
        with pytest.raises(EvidenceError): journey.step(Mock())
        assert not (tmp_path / (stage + '.reply.json')).exists()
    else:
        journey.step(Mock())
        assert (tmp_path / (stage + '.reply.json')).exists()


@pytest.mark.parametrize('child', ['child', 'existing'])
@pytest.mark.parametrize('fault', ['', 'account', 'names', 'grant', 'translated-number', 'extra', 'timestamp'])
def test_enabled_real_decoder_explicit_account_and_public_numbers(child, fault):
    name = 'riley' if child == 'child' else 'jordan'
    operation = f'parent-language-{name}-enabled-zh-hans'
    value = enabled_value(child, 'zh-Hans')
    if fault == 'account': value['child'] = 'wrong-child'
    if fault == 'names': value['app_names'][0][0] = 'parent-app-' + 'b' * 16
    if fault == 'grant': value['balances']['one_time']['seconds'] = 5
    if fault == 'translated-number': value['balances']['daily']['text'] = '1h'
    if fault == 'extra': value['balances']['private'] = 'no'
    if fault == 'timestamp': value['balances']['observed_monotonic_ns'] = True
    payload = {'operation': operation, 'outcome': 'passed', 'interface': 'AT-SPI', 'language_state': value}
    observer = UiObservations(SimpleNamespace(call=Mock(return_value=json.dumps(payload).encode())))
    if fault:
        with pytest.raises(EvidenceError): observer.observe(operation)
        with pytest.raises(EvidenceError, match='previous-failure'): observer.observe(operation)
    else:
        assert observer.observe(operation) == payload


@pytest.mark.parametrize('fault', ['', 'wrong-child', 'policy', 'name', 'mixed', 'missing-text',
                                  'grant', 'increase', 'elapsed', 'replay'])
@pytest.mark.parametrize('stage,child', [('riley-state', 'child'),
    ('prior-window', 'child'), ('same-parent-window', 'existing'),
    ('reopened-riley-state', 'child'), ('reopened-jordan-state', 'existing'),
    ('reopened-riley-return-state', 'child')])
def test_enabled_recorder_real_step_immutable_comparison_before_reply(tmp_path, fault, stage, child):
    journey = language.ParentLanguageIsolationJourney(SimpleNamespace(directory=tmp_path), Mock())
    baseline = enabled_value(child)
    journey.check_settings('riley-before' if child == 'child' else 'jordan-before',
                           {'ui': {'language_state': baseline}})
    baseline['app_names'][0][1] = 'mutated caller input'
    assert journey.policies[child]['app_names'][0][1] == 'Fixture application'
    journey.committed = journey.candidate = 'zh-Hans'
    journey.steps = [{'stage': value} for value in journey.plan.stages[:journey.plan.stages.index(stage)]]
    journey.boot = 'a' * 64
    value = enabled_value(child, 'zh-Hans', 10)
    if fault == 'wrong-child':
        value = enabled_value('existing' if child == 'child' else 'child', 'zh-Hans', 10)
    if fault == 'policy': value['rows'][0][1] = 'permanent'
    if fault == 'name': value['app_names'][0][1] = 'different application'
    if fault == 'mixed': value['management_labels'].append('Screen Time Limit')
    if fault == 'missing-text': value['management_labels'].remove('每日可用时间')
    if fault == 'grant': value['balances']['one_time']['seconds'] = 1
    if fault == 'increase': value['balances']['daily']['seconds'] = value['balances']['total']['seconds'] = 3603
    if fault == 'elapsed': value['balances']['observed_monotonic_ns'] = 701 * 10**9
    if fault == 'replay': journey.language_captures.add(stage)
    journey.ui = SimpleNamespace(boot_proof=journey.boot, observe=Mock(return_value={'language_state': value}))
    (tmp_path / (stage + '.request.json')).write_text(json.dumps({'stage': stage, 'screenshot': None}))
    if fault:
        with pytest.raises(EvidenceError): journey.step(Mock())
        assert not (tmp_path / (stage + '.reply.json')).exists()
    else:
        journey.step(Mock())
        assert (tmp_path / (stage + '.reply.json')).exists()


@pytest.mark.parametrize('allowance', ['0 minutes', '0 Minuten', '0 分钟', '0 דקות', '30 minutes', 'wrong'])
@pytest.mark.parametrize('selected_language,title', [
    ('en', 'Screen Time Limit'), ('de', 'Bildschirmzeit begrenzen'),
    ('zh-Hans', '限制屏幕时间'), ('he', 'מגבלת זמן מסך')])
def test_public_policy_projection_reads_translated_allowance_without_changing_settings(
        allowance, selected_language, title):
    from accessible_ui import EXISTING_CHILD
    selected = Node(identity='parent-child-selected-1002', children=[Node(EXISTING_CHILD, 'label')])
    picker = Node(identity='parent-child-selector', children=[selected])
    toggle = Node(language.TEXTS[selected_language][4], identity='parent-screen-limit-toggle')
    amount = Node(identity='parent-daily-limit-selector', states=('showing', 'visible'),
                  children=[Node(allowance, 'label')])
    screen = Node(identity='parent-page-screen-limits')
    apps = Node(identity='parent-page-app-limits')
    window = Node(identity='parent-window', children=[Node(identity='parent-language-ready'),
        picker, amount, screen, apps,
        Node(identity='parent-screen-limits-page', children=[toggle, Node(title, 'label')])])
    ui = ui_for(window)
    ui.app_rows = Mock(return_value=(('parent-app-' + 'a' * 16, 'allowed', 'precise'),))
    if allowance in ('30 minutes', 'wrong'):
        with pytest.raises(public.UiError, match='language-allowance'): ui.parent_language_state()
        apps.action.do_action.assert_not_called()
    else:
        assert ui.parent_language_state() == state_value(selected_language)
        ui.app_rows.assert_called_once_with(EXISTING_CHILD)
        assert screen.action.do_action.call_count == 2
        apps.action.do_action.assert_called_once()
    picker.action.do_action.assert_not_called()
    toggle.action.do_action.assert_not_called()
    amount.action.do_action.assert_not_called()


@pytest.mark.parametrize('child', ['child', 'existing'])
@pytest.mark.parametrize('selected_language', ['en', 'zh-Hans', 'he'])
@pytest.mark.parametrize('fault', ['', 'wrong-child', 'wrong-allowance', 'disabled', 'stale'])
def test_enabled_state_reader_requires_explicit_child_and_translated_allowance(child, selected_language, fault):
    if selected_language == 'he' and child != 'child':
        with pytest.raises(public.UiError, match='language-state-binding'):
            # The unqualified Jordan/Hebrew enabled binding remains refused.
            ui, *_ = chooser_tree()
            ui.language_save_completed = Mock()
            ui.parent_initial_selection = Mock(return_value='existing-fixture-child')
            ui.parent_language_state(child=public.EXISTING_CHILD, enabled=True, language='he')
        return
    account = public.NAMED_CUSTOM_CHILDREN[child]
    uid = 1001 if child == 'child' else 1002
    selected = Node(identity=f'parent-child-selected-{uid}', children=[Node(account, 'label')])
    if fault == 'wrong-child': selected.identity = 'parent-child-selected-' + str(1003 - (uid - 1000))
    picker = Node(identity='parent-child-selector', children=[selected])
    toggle = Node(language.TEXTS[selected_language][4], identity='parent-screen-limit-toggle',
                  states=('visible', 'showing', 'sensitive', 'checked'))
    if fault == 'disabled': toggle.states.remove('checked')
    label = {'en': '1 hour', 'zh-Hans': '1 小时', 'he': '1 שעה'}[selected_language]
    if fault == 'wrong-allowance': label = '30 minutes'
    amount = Node(identity='parent-daily-limit-selector', children=[Node(label, 'label')])
    screen, apps = Node(identity='parent-page-screen-limits'), Node(identity='parent-page-app-limits')
    page = Node(identity='parent-screen-limits-page', children=[toggle,
        *(Node(text, 'label') for text in sorted(language.ENABLED_LABELS[selected_language]))])
    window = Node(identity='parent-window', children=[Node(identity='parent-language-ready'),
        picker, amount, screen, apps, page,
        Node(identity='parent-app-limits-page', children=[Node(identity='parent-app-search')])])
    if fault == 'stale': selected.states.add('defunct')
    ui = ui_for(window); ui.timeout = .05
    value = enabled_value(child, selected_language)
    ui.app_rows = Mock(return_value=tuple(tuple(row) + (name[1],)
        for row, name in zip(value['rows'], value['app_names'])))
    ui.reach_time_explanation = Mock(return_value=value['balances'])
    if fault:
        with pytest.raises(public.UiError):
            ui.parent_language_state(child=account, enabled=True, language=selected_language)
        ui.app_rows.assert_not_called()
    else:
        result = ui.parent_language_state(child=account, enabled=True, language=selected_language)
        assert result == value
        ui.app_rows.assert_called_once_with(account, include_names=True)
        ui.reach_time_explanation.assert_called_once_with(account, language=selected_language)
    for node in (picker, toggle, amount): node.action.do_action.assert_not_called()


@pytest.mark.parametrize('fault', ['', 'text', 'checked', 'policy', 'visible-title', 'storage', 'replay'])
def test_real_recorder_step_validates_before_reply_and_freezes_policy(tmp_path, fault):
    journey = language.ParentLanguageJourney(SimpleNamespace(directory=tmp_path), Mock())
    stage = 'initial-state' if fault in ('policy', 'visible-title', '') else 'initial-language'
    journey.steps = [{'stage': value} for value in journey.plan.stages[:journey.plan.stages.index(stage)]]
    journey.boot = 'a' * 64
    value = state_value() if stage == 'initial-state' else chooser_value(initial=True)
    if fault == 'text': value['heading'] = 'wrong text'
    if fault == 'checked': value['checked'] = 'de'
    if fault == 'visible-title': value['management_labels'] = [value['management']]
    if fault == 'policy':
        journey.preservation = deepcopy(value)
        journey.preservation = {key: value[key] for key in ('child', 'limit_enabled', 'allowance_minutes', 'rows')}
        value = deepcopy(value); value['rows'][0][1] = 'permanent'
    if fault == 'replay': journey.language_captures.add(stage)
    if fault == 'storage': journey.progress.side_effect = OSError('storage')
    journey.ui = SimpleNamespace(boot_proof=journey.boot,
        observe=Mock(return_value={'language_state' if stage == 'initial-state' else 'language': value}))
    (tmp_path / (stage + '.request.json')).write_text(json.dumps({'stage': stage, 'screenshot': None}))
    if fault:
        with pytest.raises((EvidenceError, OSError)): journey.step(Mock())
        assert not (tmp_path / (stage + '.reply.json')).exists()
        with pytest.raises(EvidenceError, match='previous-failure'): journey.step(Mock())
    else:
        journey.step(Mock())
        assert (tmp_path / (stage + '.reply.json')).exists()
        value['rows'][0][1] = 'permanent'
        assert journey.preservation['rows'][0][1] == 'allowed'


@pytest.mark.parametrize('fault', ['', 'meaning', 'durability'])
@pytest.mark.parametrize('journey_type', [language.ParentLanguageJourney,
    language.ParentLanguageIsolationJourney, language.ParentRtlJourney,
    language.ParentHebrewPolicyJourney])
def test_real_recorder_entry_accepts_custom_plan_and_refuses_before_reply(
        session, tmp_path, monkeypatch, fault, journey_type):
    expected = session.payload['assertions'][0]
    tags = {'entry-start': 'system:parent-command-context', 'entry-one': 'system:parent-command-context',
            'entry-two': 'system:parent-command-context', 'chooser': 'ui:parent-language-initial'}
    plan = replace(language.PLAN, screen_tags=tags, invocations=(),
        phases={'ready': 'setup', 'setup-detached': 'setup', 'entry-start': 'start',
            'entry-one': 'step-1', 'entry-two': 'step-2', 'chooser': expected['step_id']},
        assertions_after={'chooser': expected['assertion_id']})
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
        assert type(journey) is journey_type and journey.plan is plan
        journey.steps = [{'stage': 'ready'}, {'stage': 'setup-detached'}]
        journey.boot = 'a' * 64
        journey.vm = SimpleNamespace(read=Mock(return_value={'boot_sha256': journey.boot}))
        value = chooser_value(initial=True)
        if fault == 'meaning': value['heading'] = 'incorrect'
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
    monkeypatch.setattr(journey_type, 'validate', lambda _: [])
    if fault:
        with pytest.raises((EvidenceError, OSError)):
            installed_journey.record_installed_journey(recorder, context, plan, actions={},
                                                      journey_type=journey_type)
        assert not (context.directory / 'chooser.reply.json').exists()
    else:
        installed_journey.record_installed_journey(recorder, context, plan, actions={},
                                                  journey_type=journey_type)
