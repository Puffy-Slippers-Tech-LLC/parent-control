"""Private tree, account, decoder and recorder doubles; waited Perl, no VM."""
from copy import deepcopy
from dataclasses import replace
import json
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock

import pytest
import accessible_ui as public
import check_e2e_overlay_language as selector
import check_graphical_smoke as smoke
import overlay_language as language
from private_artifacts import EvidenceError
from owned_commands import CommandError
from tests.support.accessible_ui import Node, ui_for
from tests.support.e2e_kiosk import WORKER, request_form
from tests.support.perl import run_perl
from tests.support.paths import ROOT
from tests.support.e2e_evidence import attempt
from tests.support.e2e_recording import session
from ui_observations import UiObservations, OPERATION_LABELS


def test_declared_session_operations_reach_the_guarded_transport():
    import session_control
    for operation in language.PLAN.screen_tags.values():
        if not operation.startswith('system:'):
            continue
        binding = operation[7:]
        expected = {'operation': binding, 'outcome': 'passed', 'interface': 'system session',
                    'source_retained': True, 'destination': 'greeter'}
        transport = SimpleNamespace(call=Mock(return_value=json.dumps(expected).encode()))
        assert session_control.observe(transport, binding) == expected
        transport.call.assert_called_once()
        assert transport.call.call_args.args[0][-1] == binding


def chooser_value(selected='en', initial=False):
    text = language.CHOOSER[selected]
    return {'initial': initial, 'checked': selected.lower(),
        'choices': {key: value[0] for key, value in language.CHOOSER.items()},
        'heading': text[1], 'save': text[2], 'save_label': text[2], 'save_description': text[3]}


def chooser_tree(initial=False):
    choices = [Node(text[0], identity='language-choice-' + key.lower(),
                    states=('visible', 'sensitive', *(('checked',) if key == 'en' else ())))
               for key, text in language.CHOOSER.items()]
    controls = choices + [Node('Choose your language', identity='language-title'),
        Node('Save', identity='language-continue', description='Save your language preference.',
             children=[Node('Save', 'label')]), Node('Cancel', identity='language-cancel')]
    dialog = Node(identity='language-dialog', children=controls)
    window = Node(identity='kiosk-request-window', children=[dialog,
        Node(identity='kiosk-language-loading' if initial else 'kiosk-language-ready'),
        Node(public.CHILD, 'label', identity='kiosk-child-selected-1001')])
    ui = ui_for(window)
    ui.api.get_desktop(0).identity = public.CHILD_APPLICATION
    ui.require_child_overlay_session = Mock()
    return ui, window, dialog, controls


def request_value():
    return dict(surface='child-overlay', form_count=1, child='fixture-child', approver='other-fixture-parent',
        duration_seconds=1800, custom_text=None, allow_soft=False, child_selector_enabled=False,
        approver_selector_enabled=True, duration_enabled=True, soft_choice_enabled=True,
        request_enabled=True, cancel_enabled=True, message='', mute=None)


def form_value(selected='en'):
    text = language.FORM[selected]
    return {'request': request_value(), 'texts': dict(zip(language.TEXT_IDS, (*text[:3], text[4], text[6]))),
        'labels': {language.TEXT_IDS[3]: text[3], language.TEXT_IDS[4]: text[5]}, 'chooser_absent': True}


def policy_value(daily=1800):
    return {'settings': {'child': 'fixture-child', 'limit_enabled': True, 'allowance': ['30 minutes']},
        'balances': {'daily': daily, 'one_time': 0, 'total': daily},
        'rows': [[f'parent-app-{index:016x}', 'allowed', 'precise'] for index in range(128)]}


def test_registration_installed_envelope_and_shared_fragments(monkeypatch, tmp_path):
    import e2e_worker
    import tools.test_commands as commands
    from tools.test_storage import named_input
    from parent_setup_qualification import OverlayLanguageQualification, KioskEntryQualification
    from journey_blocks import language_selection, overlay_entry
    launch = Mock(return_value=0)
    monkeypatch.setattr(selector, 'smoke', launch)
    assert selector.main() == 0
    launch.assert_called_once_with(assets=selector.ASSETS, provision_credentials=True, overlay_language=True)
    assert selector.ASSETS == named_input(package_source=True)
    assert OverlayLanguageQualification.attach_installed_snapshot is KioskEntryQualification.attach_installed_snapshot
    assert OverlayLanguageQualification.journey(SimpleNamespace(directory=tmp_path), Mock()).plan is language.PLAN
    monkeypatch.setattr(commands.os.path, 'lexists', lambda _: False)
    monkeypatch.setattr(commands, 'allocate_artifact_output', Mock(return_value=str(selector.ASSETS)))
    assert commands.qualification_artifact_command(Path.cwd(), 'integration', ['check_e2e_overlay_language'])[-1] == str(selector.ASSETS)
    assert set(language.PLAN.phases) == set(language.PLAN.stages)
    assert language.SCREENS['direct-form'] == 'ui:overlay-language-initial'
    assert language.SCREENS['initial-form'] == 'ui:overlay-language-form-en'
    assert all(tag[3:] in public.OPERATIONS and tag[3:] in OPERATION_LABELS
               for tag in language.SCREENS.values() if tag.startswith('ui:'))
    assert (public.OVERLAY_LANGUAGE_OPERATIONS - {'overlay-language-wrong-entry'}) <= public.CHILD_DESKTOP_OPERATIONS
    assert not public.OVERLAY_LANGUAGE_OPERATIONS & public.KIOSK_SESSION_OPERATIONS
    distribution = e2e_worker.distribution_inputs()
    assert b'overlay_language' in distribution['tests/smoke.pm']
    assert b'sub overlay_language' in distribution['lib/onpc_request_flow.pm']
    assert language_selection('unrelated', 'he', surface='overlay') == {
        'unrelated-open': 'ui:overlay-language-open', 'unrelated-choose': 'ui:overlay-language-choose-he'}
    assert overlay_entry('unrelated', 'command', form_operation='overlay-language-initial')['unrelated-form'] == 'ui:overlay-language-initial'


@pytest.mark.parametrize('refuse', ['', 'setup-detached'])
def test_actual_smoke_dispatch_preserves_setup_handshake(monkeypatch, refuse):
    source = (ROOT / 'tests/integration/graphical_smoke/tests/smoke.pm').read_text()
    if refuse: monkeypatch.setenv('ONPC_TEST_REFUSE_STAGE', refuse)
    # Load the entire dispatcher, replacing only external imports and rendezvous.
    # The actual run branch decides order and forwards the real declared values.
    program = r'''
use strict;
use warnings;
use JSON::PP;
our @events;
BEGIN { $INC{'testapi.pm'} = 1; $INC{'basetest.pm'} = 1; }
package basetest;
sub new { bless {}, shift }
package testapi;
sub import { no strict 'refs'; *{caller() . '::console'} = \&console; }
sub console { push @main::events, ['console', $_[0]]; bless {}, 'Console' }
package Console;
sub disable { push @main::events, ['disabled']; }
package main;
my $source = decode_json(SOURCE_JSON);
while ($source =~ /use (onpc_\w+)/g) { $INC{"$1.pm"} = 1; }
eval 'package DispatchProbe;' . $source;
die $@ if $@;
{
    no warnings 'redefine';
    *DispatchProbe::exchange = sub {
        push @events, ['stage', $_[0]];
        die 'fixture:refused' if $_[0] eq ($ENV{ONPC_TEST_REFUSE_STAGE} // '');
        return {overlay_language => JSON::PP::true, invocations => ['finite'],
                challenge_bindings => {login => ['child', 'one', 'two']}};
    };
    *onpc_request_flow::overlay_language = sub {
        push @events, ['worker', $_[1], $_[2]];
        die 'fixture:callback' unless ref($_[0]) eq 'CODE';
    };
}
my $ok = eval { DispatchProbe::run(); 1; };
print encode_json({ok => $ok ? 1 : 0, events => \@events, error => "$@"});
'''
    # Preserve JSON escapes inside a literal Perl string; no shell evaluation.
    literal = "'" + json.dumps(source).replace('\\', '\\\\').replace("'", "\\'") + "'"
    result = json.loads(run_perl(program.replace('SOURCE_JSON', literal)).stdout)
    expected = [['stage', 'ready'], ['console', 'sut'], ['disabled'], ['stage', 'setup-detached']]
    if not refuse: expected.append(['worker', ['finite'], {'login': ['child', 'one', 'two']}])
    assert result['events'] == expected
    assert bool(result['ok']) is (not refuse), result['error']


@pytest.mark.parametrize('name', ['check_e2e_overlay_language', 'check_e2e_overlay_language.py'])
def test_valid_existing_inputs_are_preserved(monkeypatch, name):
    import tools.test_commands as commands
    validate, allocate = Mock(), Mock()
    monkeypatch.setattr(commands.os.path, 'lexists', lambda _: True)
    monkeypatch.setattr(commands, 'artifact_path', validate)
    monkeypatch.setattr(commands, 'allocate_artifact_output', allocate)
    assert commands.qualification_artifact_command(Path.cwd(), 'integration', [name]) is None
    validate.assert_called_once_with(str(selector.ASSETS))
    allocate.assert_not_called()


@pytest.mark.parametrize('extra', [{}, {'parent_language': True}, {'kiosk_language': True}, {'challenges': True}])
def test_mode_refuses_before_vm(extra):
    args = {'assets': 'inputs', 'provision_credentials': True, **extra} if extra else {}
    with pytest.raises(CommandError, match='overlay-language-prerequisites'):
        smoke.main(overlay_language=True, **args)


@pytest.mark.parametrize('initial', [True, False])
@pytest.mark.parametrize('fault', ['', 'duplicate', 'missing', 'unchecked', 'multiple', 'stale',
    'owner', 'station', 'parent', 'wrong-child', 'hidden-child', 'duplicate-child', 'account'])
def test_child_owned_chooser_refuses_before_any_input(initial, fault):
    ui, window, dialog, controls = chooser_tree(initial)
    if fault == 'duplicate': dialog.children.append(Node(identity='language-title'))
    if fault == 'missing': dialog.children.remove(controls[3])
    if fault == 'unchecked': controls[0].states.discard('checked')
    if fault == 'multiple': controls[1].states.add('checked')
    if fault == 'stale': controls[0].states.add('defunct')
    if fault == 'owner': ui.owner_pids = lambda: {999}
    if fault == 'station': ui.api.get_desktop(0).identity = public.KIOSK_APPLICATION
    if fault == 'parent': ui.api.get_desktop(0).identity = public.PARENT_APPLICATION
    if fault == 'wrong-child': window.children[-1].identity = 'kiosk-child-selected-1002'
    if fault == 'hidden-child': window.children[-1].states.discard('showing')
    if fault == 'duplicate-child': window.children.append(Node(identity='kiosk-child-selected-1001'))
    if fault == 'account': ui.require_child_overlay_session.side_effect = public.UiError('ui:overlay-account')
    ui.complete_request_language_setup = Mock(side_effect=AssertionError('automatic startup'))
    if fault:
        with pytest.raises(public.UiError): ui.read_overlay_language(initial=initial)
    else:
        assert ui.read_overlay_language(initial=initial) == chooser_value(initial=initial)
        with pytest.raises(public.UiError): ui.read_kiosk_language(initial=initial)
    ui.complete_request_language_setup.assert_not_called()
    for control in controls: control.action.do_action.assert_not_called()


@pytest.mark.parametrize('operation', ['overlay-language-choose-de', 'overlay-language-save', 'overlay-language-cancel'])
def test_stale_ambiguous_and_uncertain_input_is_not_replayed(operation):
    ui, _window, dialog, controls = chooser_tree()
    controls[0].states.add('defunct')
    with pytest.raises(public.UiError): ui.overlay_language_operation(operation)
    for control in controls: control.action.do_action.assert_not_called()
    controls[0].states.discard('defunct')
    dialog.children.append(Node(identity='language-choice-de'))
    with pytest.raises(public.UiError): ui.overlay_language_operation(operation)
    for control in controls: control.action.do_action.assert_not_called()
    dialog.children.pop()
    target = next(node for node in controls if node.identity == {
        'overlay-language-choose-de': 'language-choice-de', 'overlay-language-save': 'language-continue',
        'overlay-language-cancel': 'language-cancel'}[operation])
    target.states.add('showing')
    target.action.do_action.return_value = False
    with pytest.raises(public.UiError): ui.overlay_language_operation(operation)
    assert ui.input_uncertain
    with pytest.raises(public.UiError): ui.overlay_language_operation(operation)
    target.action.do_action.assert_called_once()


def test_real_session_guard_rejects_wrong_uid_and_requires_active_session(monkeypatch):
    ui, *_ = chooser_tree()
    ui.require_child_overlay_session = public.AccessibleUI.require_child_overlay_session.__get__(ui)
    monkeypatch.setattr(public.pwd, 'getpwnam', lambda _: SimpleNamespace(pw_uid=1001))
    active = Mock()
    monkeypatch.setattr(public, 'require_active_launch_session', active)
    monkeypatch.setattr(public.os, 'getuid', lambda: 1002)
    monkeypatch.setattr(public.os, 'geteuid', lambda: 1002)
    with pytest.raises(public.UiError, match='overlay-account'): ui.read_overlay_language()
    active.assert_not_called()
    monkeypatch.setattr(public.os, 'getuid', lambda: 1001)
    monkeypatch.setattr(public.os, 'geteuid', lambda: 1001)
    ui.read_overlay_language()
    active.assert_called()


@pytest.mark.parametrize('selected', language.CHOOSER)
def test_actual_overlay_form_reader_and_separate_visible_text(selected):
    ui, _ = request_form()
    ui.api.get_desktop(0).identity = public.CHILD_APPLICATION
    ui.require_child_overlay_session = Mock()
    form = ui.find_id('kiosk-request-form')
    form.children.remove(ui.find_id('kiosk-screen-limit-notice'))
    for node in form.children: node.states.add('sensitive')
    child = ui.find_id('kiosk-child-selector')
    child.states.discard('sensitive')
    child.children[0].identity = 'kiosk-child-selected-1001'
    child.children[0].name = public.CHILD
    template = {'en': 'Selected account: %s.', 'de': 'Ausgewähltes Konto: %s.',
                'zh-Hans': '已选择的账户：%s。', 'he': 'החשבון שנבחר: %s.'}[selected]
    ui.find_id('kiosk-approver-selector').description = template % public.OTHER_PARENT
    child.description = template % public.CHILD
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
    assert ui.kiosk_language_form(selected, overlay=True) == form_value(selected)
    ui.complete_request_language_setup.assert_not_called()
    for node in form.children: node.action.do_action.assert_not_called()


@pytest.mark.parametrize('operation,key,value', [
    ('overlay-language-initial', 'language', chooser_value(initial=True)),
    ('overlay-language-form-de', 'language_form', form_value('de')),
    ('overlay-language-policy', 'language_policy', policy_value()),
])
@pytest.mark.parametrize('fault', ['', 'extra', 'invalid', 'oversize'])
def test_real_decoder_stream_and_terminal_latch(operation, key, value, fault):
    value = deepcopy(value)
    if fault == 'extra': value['extra'] = True
    if key == 'language':
        if fault == 'invalid': value['checked'] = 'unknown'
        if fault == 'oversize': value['heading'] = 'x' * 513
    if key == 'language_form':
        if fault == 'invalid': value['request']['surface'] = 'kiosk'
        if fault == 'oversize': value['texts']['kiosk-request-submit'] = 'x' * 513
    if key == 'language_policy':
        if fault == 'invalid': value['balances']['one_time'] = True
        if fault == 'oversize': value['rows'].extend(value['rows'] * 30)
    payload = dict(operation=operation, outcome='passed', interface='AT-SPI', **{key: value})
    raw = json.dumps(payload, ensure_ascii=False).encode()
    def deliver(*args, **kwargs):
        if kwargs.get('on_output') is not None:
            diagnostic = {'event': 'kiosk-form-observation', 'phase': 'public-tree', 'status': 'reading',
                'elapsed_ms': 0, 'tree': 'unread', 'public_ids': {}, 'tree_reads': 0,
                'nodes_read': 0, 'incomplete_reads': 0, 'query_errors': 0}
            if key == 'language_form': kwargs['on_output']((json.dumps(diagnostic, sort_keys=True) + '\n').encode())
            for index in range(0, len(raw), 37): kwargs['on_output'](raw[index:index + 37])
            kwargs['on_output'](b'\n')
        return raw
    transport = SimpleNamespace(call=Mock(side_effect=deliver), commands=SimpleNamespace(progress=None))
    observer = UiObservations(transport)
    if fault:
        with pytest.raises(EvidenceError): observer.observe(operation)
        with pytest.raises(EvidenceError, match='previous-failure'): observer.observe('overlay-language-save')
        transport.call.assert_called_once()
    else:
        assert observer.observe(operation) == payload


@pytest.mark.parametrize('stage,fault', [('direct-form', ''), ('direct-form', 'meaning'),
    ('initial-form', ''), ('initial-form', 'visible'), ('initial-form', 'request'),
    ('policy-after', ''), ('policy-after', 'policy'), ('policy-after', 'grant'),
    ('initial-form', 'storage'), ('initial-form', 'replay')])
def test_actual_recorder_refuses_before_reply_and_freezes_projection(tmp_path, stage, fault):
    journey = language.OverlayLanguageJourney(SimpleNamespace(directory=tmp_path), Mock())
    journey.boot = 'a' * 64
    journey.steps = [{'stage': s} for s in journey.plan.stages[:journey.plan.stages.index(stage)]]
    key = 'language' if stage == 'direct-form' else 'language_form' if stage == 'initial-form' else 'language_policy'
    value = chooser_value(initial=True) if key == 'language' else form_value() if key == 'language_form' else policy_value(1733)
    if stage == 'policy-after':
        journey.policy_projection = deepcopy({key: val for key, val in policy_value().items() if key != 'balances'})
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


@pytest.mark.parametrize('fault', ['', *language.SCREENS])
def test_complete_real_worker_order_titles_and_refusal_stop(monkeypatch, fault):
    if fault: monkeypatch.setenv('ONPC_TEST_REFUSE_STAGE', fault)
    worker = WORKER.replace('onpc_kiosk_eligible_choices', 'onpc_request_flow')
    worker = worker.replace('onpc_request_flow::run', 'onpc_request_flow::overlay_language')
    worker = worker.replace('sub record_info { }', "sub record_info { push @main::events, ['title', $_[0]] }")
    worker = worker.replace('return {observed => $stage};', r'''
        my %proofs = (
            'recipient-qualified' => ['parent-login', 'parent', 'qualified'],
            'recipient-rechecked' => ['parent-login', 'parent', 'rechecked'],
            'fresh-child-recipient-qualified' => ['child-login', 'child', 'qualified'],
            'fresh-child-recipient-rechecked' => ['child-login', 'child', 'rechecked'],
            'return-qualified' => ['return-parent', 'parent', 'qualified'],
            'return-rechecked' => ['return-parent', 'parent', 'rechecked']);
        if (exists $proofs{$stage}) {
            my ($id, $role, $check) = @{$proofs{$stage}};
            return {observed => $stage, challenge => {id => $id, role => $role,
                surface => 'gdm', check => $check}};
        }
        return {observed => $stage};''')
    challenges = '{' + ', '.join('"' + key + '" => ' + json.dumps(list(value))
                               for key, value in language.PLAN.challenges.items()) + '}'
    worker = worker.replace('    });', '    }, ' + json.dumps(list(language.PLAN.invocations)) + ', ' + challenges + ');')
    result = json.loads(run_perl(worker).stdout)
    expected = list(language.SCREENS)
    if fault: expected = expected[:expected.index(fault) + 1]
    assert bool(result['ok']) == (not fault), result['error']
    assert [event[1] for event in result['events'] if event[0] == 'stage'] == expected
    assert [event[1] for event in result['events'] if event[0] == 'title' and event[1] != 'shutdown'] == [
        'overlay-language-' + stage for stage in expected]
    assert ['power', 'off'] in result['events'] if not fault else ['power', 'off'] not in result['events']


@pytest.mark.parametrize('fault', ['', 'meaning', 'durability'])
def test_real_recorder_entry_constructor_and_failure_stop(session, tmp_path, monkeypatch, fault):
    import installed_journey
    import session_control
    expected = session.payload['assertions'][0]
    tags = {'entry-start': 'system:parent-command-context', 'entry-one': 'system:parent-command-context',
            'entry-two': 'system:parent-command-context', 'chooser': 'ui:overlay-language-initial'}
    plan = replace(language.PLAN, screen_tags=tags, invocations=(), challenges={},
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
        assert isinstance(journey, language.OverlayLanguageJourney) and journey.plan is plan
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
    monkeypatch.setattr(language.OverlayLanguageJourney, 'validate', lambda _: [])
    if fault:
        with pytest.raises((EvidenceError, OSError)):
            installed_journey.record_installed_journey(recorder, context, plan, actions={},
                journey_type=language.OverlayLanguageJourney)
        assert not (context.directory / 'chooser.reply.json').exists()
    else:
        installed_journey.record_installed_journey(recorder, context, plan, actions={},
            journey_type=language.OverlayLanguageJourney)
