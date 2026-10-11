"""Native grid composition, public app activity and no input after refusal.

Parallelism: private in-memory trees, mocked transport, pytest scratch files and
caller-owned Perl subprocesses only; no shared VM, display, paths, caches or sockets.
"""
import json
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

import accessible_ui
from accessible_ui import UiError
import check_e2e_native_grid_usable as check
import check_graphical_smoke as smoke
from native_grid_usable import PLAN, NativeGridJourney
from owned_commands import CommandError
from installed_journey import matched_screens
from parent_setup_qualification import KioskEntryQualification, NativeGridQualification
from private_artifacts import EvidenceError
from tests.support.accessible_ui import Node, ui_for
from tests.support.perl import run_perl
from ui_observations import UiObservations, OPERATION_LABELS


def native_tree():
    scope = 'onpc-fixture-native-primary'
    nodes = {control: Node(value, 'label', identity=scope + '-' + control)
             for control, value in {
                 'status': 'Ready', 'draft': 'ONPC fixture draft',
                 'submitted': 'No submitted draft', 'score': 'Moves: 0; token: 0',
                 'submit': 'Submit draft', 'close': 'Close'}.items()}
    nodes['draft'].get_text_iface = lambda: nodes['draft']
    surface = Node(identity=scope, children=nodes.values())
    surface.states.add('active')
    owner = Node(role='application', identity='com.puffyslippers.ONPCFixture.native.primary',
                 children=[surface])
    root = Node(role='desktop', children=[owner])
    ui = ui_for(Node())
    ui.api.get_desktop = lambda _: root
    ui.api.Text = SimpleNamespace(get_character_count=lambda n: len(n.name),
                                 get_text=lambda n, a, b: n.name[a:b])
    return ui, root, surface, nodes


@pytest.mark.parametrize('fault', [None, 'owner', 'duplicate', 'inactive', 'disabled',
                                 'uncertain', 'wrong-instance'])
def test_actual_owned_submit_guard_and_independent_readback(fault):
    ui, root, surface, nodes = native_tree()
    nodes['submit'].action.do_action.side_effect = lambda _: (
        setattr(nodes['submitted'], 'name', 'ONPC fixture draft') or True)
    if fault == 'owner': root.children[0].identity = 'unrelated.application'
    if fault == 'duplicate': surface.children.append(Node(identity=nodes['submit'].identity))
    if fault == 'inactive': surface.states.remove('active')
    if fault == 'disabled': nodes['submit'].states.remove('sensitive')
    if fault == 'uncertain': ui.input_uncertain = True
    instance = 'secondary' if fault == 'wrong-instance' else 'primary'
    if fault:
        with pytest.raises(UiError): ui.native_app_submit(instance)
        nodes['submit'].action.do_action.assert_not_called()
    else:
        before = ui.native_app_operation('native-opened')
        ui.native_app_operation('native-submit')
        nodes['submit'].action.do_action.assert_called_once()
        after = ui.native_app_operation('native-submitted')
        assert before['submitted'] == 'No submitted draft'
        assert after == {**before, 'submitted': 'ONPC fixture draft'}


def test_action_success_cannot_replace_effect_and_uncertain_action_cannot_replay():
    ui, root, surface, nodes = native_tree()
    ui.native_app_submit()
    with pytest.raises(UiError): ui.native_app_operation('native-submitted')
    nodes['submit'].action.do_action.assert_called_once()
    ui, root, surface, nodes = native_tree()
    nodes['submit'].action.do_action.side_effect = LookupError('uncertain')
    with pytest.raises(LookupError): ui.native_app_submit()
    with pytest.raises(UiError, match='ui:uncertain-input'): ui.native_app_submit()
    nodes['submit'].action.do_action.assert_called_once()


@pytest.mark.parametrize('fault', [None, 'missing-owner', 'inactive', 'changed-draft'])
def test_native_open_diagnostic_preserves_actual_public_result_without_input(fault):
    ui, root, surface, nodes = native_tree()
    if fault == 'missing-owner': root.children[0].identity = 'foreign'
    if fault == 'inactive': surface.states.remove('active')
    if fault == 'changed-draft': nodes['draft'].name = 'private draft'
    ui.native_open_diagnostic = {'event': 'ui-native-public-observation', 'complete_reads': 0}
    with ui.observation():
        result = ui.native_app_snapshot('No submitted draft', pending=True)
    diagnostic = ui.native_open_diagnostic
    assert bool(result) == (fault is None)
    assert diagnostic['complete_reads'] == 1
    assert diagnostic['owner_count'] == (0 if fault == 'missing-owner' else 1)
    assert diagnostic['ids']['window'] == diagnostic['ids']['draft'] == 1
    assert diagnostic['resolved_window'] == (fault != 'missing-owner')
    assert diagnostic['active_window'] == (fault not in ('missing-owner', 'inactive'))
    if fault in (None, 'changed-draft'):
        assert diagnostic['activity_matches'] == {
            'draft': fault is None, 'submitted': True, 'score': True}
    assert 'private' not in json.dumps(diagnostic)
    nodes['submit'].action.do_action.assert_not_called()


@pytest.mark.parametrize('fault', ['recovered', 'persistent', 'owner', 'activity',
                                 'prompt', 'delivery'])
def test_submit_reacquires_complete_preflight_and_preserves_refusals(monkeypatch, fault):
    from gi.repository import Gio, GLib
    ui, root, _surface, nodes = native_tree()
    ui.query_errors = (GLib.Error,)
    ui.timeout = 1
    clock = [0]
    monkeypatch.setattr(accessible_ui.time, 'monotonic', lambda: clock[0])
    monkeypatch.setattr(accessible_ui.time, 'sleep', lambda _seconds: clock.__setitem__(0, clock[0] + .5))
    error = Gio.DBusError.new_for_dbus_error(
        'org.freedesktop.DBus.Error.ServiceUnknown', 'vanished provider')
    reads = []
    count = root.get_child_count

    def children():
        reads.append(True)
        nodes['submit'].action.do_action.assert_not_called()
        if len(reads) == 1 or fault == 'persistent':
            raise error
        if fault == 'owner':
            root.children[0].identity = 'unrelated.application'
        if fault == 'activity':
            nodes['submitted'].name = 'unexpected activity'
        return count()

    root.get_child_count = children
    if fault == 'prompt':
        ui.handle_system_prompt = Mock(side_effect=UiError('ui:prompt'))
    if fault == 'delivery':
        nodes['submit'].action.do_action.side_effect = error
    elif fault == 'recovered':
        nodes['submit'].action.do_action.side_effect = lambda _: (
            setattr(nodes['submitted'], 'name', 'ONPC fixture draft') or True)

    if fault in ('persistent', 'owner', 'activity', 'prompt'):
        expected = {'persistent': 'ui:timeout:native-submit-ready',
                    'owner': 'ui:native-entry', 'activity': 'ui:native-activity',
                    'prompt': 'ui:prompt'}[fault]
        with pytest.raises(UiError, match=expected):
            ui.native_app_submit()
        nodes['submit'].action.do_action.assert_not_called()
    elif fault == 'delivery':
        with pytest.raises(GLib.Error) as caught:
            ui.native_app_submit()
        assert caught.value is error
        with pytest.raises(UiError, match='ui:uncertain-input'):
            ui.native_app_submit()
        nodes['submit'].action.do_action.assert_called_once()
    else:
        ui.native_app_submit()
        nodes['submit'].action.do_action.assert_called_once()
        root.get_child_count = count
        assert ui.native_app_operation('native-submitted')['submitted'] == 'ONPC fixture draft'
    assert len(reads) >= 2


@pytest.mark.parametrize('binding', ['overlay-cancel', 'direct-unlock', 'retained-unlock'])
def test_resume_reads_already_submitted_activity_through_real_decoder(binding):
    from overlay_cancel import PLAN as cancel_plan
    from desktop_session import CHILD_UNLOCK_PLAN, RETAINED_UNLOCK_PLAN
    plan, stage = {
        'overlay-cancel': (cancel_plan, 'resumed-opened'),
        'direct-unlock': (CHILD_UNLOCK_PLAN, 'resume-opened'),
        'retained-unlock': (RETAINED_UNLOCK_PLAN, 'resume-opened'),
    }[binding]
    ui, _root, surface, nodes = native_tree()
    surface.bus, surface.path = ':1.50', '/accessible/1'
    surface.get_process_id = lambda: 123
    ui.require_child_overlay_session = Mock()
    nodes['submitted'].name = 'ONPC fixture draft'
    # One read suffices to expose the former initial-state predicate mismatch.
    ui.wait = lambda predicate, *_args, **_kwargs: predicate()
    def call(argv, **_kwargs):
        return json.dumps(ui.run(argv[3], '')).encode()
    observer = UiObservations(SimpleNamespace(call=call))
    result = observer.observe(plan.screen_tags[stage][3:])
    assert result['activity']['state']['submitted'] == 'ONPC fixture draft'
    nodes['submit'].action.do_action.assert_not_called()


@pytest.mark.parametrize('operation', ['native-resubmit', 'overlay-native-resubmit'])
@pytest.mark.parametrize('fault', [None, 'initial-state', 'draft', 'owner', 'duplicate',
                                 'inactive', 'disabled', 'prompt', 'uncertain', 'delivery'])
def test_deliberate_resubmission_keeps_owned_state_and_single_input_guards(operation, fault):
    ui, root, surface, nodes = native_tree()
    ui.require_child_overlay_session = Mock()
    nodes['submitted'].name = 'ONPC fixture draft'
    if fault == 'initial-state': nodes['submitted'].name = 'No submitted draft'
    if fault == 'draft': nodes['draft'].name = 'changed'
    if fault == 'owner': root.children[0].identity = 'foreign'
    if fault == 'duplicate': surface.children.append(Node(identity=nodes['submit'].identity))
    if fault == 'inactive': surface.states.remove('active')
    if fault == 'disabled': nodes['submit'].states.remove('sensitive')
    if fault == 'prompt': ui.handle_system_prompt = Mock(side_effect=UiError('ui:prompt'))
    if fault == 'uncertain': ui.input_uncertain = True
    if fault == 'delivery': nodes['submit'].action.do_action.side_effect = LookupError('uncertain')
    if fault:
        with pytest.raises((UiError, LookupError)): ui.run(operation, '')
        assert nodes['submit'].action.do_action.call_count == (1 if fault == 'delivery' else 0)
        if fault == 'delivery':
            with pytest.raises(UiError, match='ui:uncertain-input'): ui.run(operation, '')
            nodes['submit'].action.do_action.assert_called_once()
    else:
        raw = json.dumps(ui.run(operation, '')).encode()
        observer = UiObservations(SimpleNamespace(call=Mock(return_value=raw)))
        assert observer.observe(operation)['outcome'] == 'passed'
        nodes['submit'].action.do_action.assert_called_once()
        ui.input_uncertain = False  # Separate independent observation process.
        assert ui.run(operation.replace('resubmit', 'submitted'), '')['activity']['submitted'] == 'ONPC fixture draft'


def test_initial_submission_still_refuses_already_submitted_activity():
    ui, _root, _surface, nodes = native_tree()
    nodes['submitted'].name = 'ONPC fixture draft'
    with pytest.raises(UiError, match='ui:native-activity'): ui.native_app_submit()
    nodes['submit'].action.do_action.assert_not_called()


@pytest.mark.parametrize('operation', ['native-opened', 'native-submitted', 'native-grid'])
@pytest.mark.parametrize('fault', [None, 'wrong', 'extra'])
def test_real_controller_decoder_requires_exact_public_result(operation, fault):
    activity = {'draft': 'ONPC fixture draft', 'submitted':
                'No submitted draft' if operation == 'native-opened' else 'ONPC fixture draft',
                'score': 'Moves: 0; token: 0'}
    provider = {'version': '50.1-0ubuntu1.2', 'locale': 'en_US.UTF-8',
                'keyboard': [['xkb', 'us']]}
    key, value = ('provider', provider) if operation == 'native-grid' else ('activity', activity)
    if fault == 'wrong': value['locale' if key == 'provider' else 'submitted'] = 'wrong'
    if fault == 'extra': value['private'] = 'canary'
    result = {'operation': operation, 'outcome': 'passed', 'interface': 'ApplicationUI+external-provider', key: value}
    transport = SimpleNamespace(call=Mock(return_value=json.dumps({**result,
                                'boot_sha256': 'b' * 64}).encode()))
    observer = UiObservations(transport)
    observer.boot_guard = ''
    # Provider metadata accepts finite observed tuples, but rejects added fields;
    # public activity must equal the caller's finite projection exactly.
    if fault == 'extra' or fault == 'wrong' and key == 'activity':
        with pytest.raises((EvidenceError, UiError)): observer.observe(operation)
    else:
        assert observer.observe(operation) == result


def test_registration_guard_snapshot_and_standard_account_binding(monkeypatch):
    assert issubclass(NativeGridQualification, KioskEntryQualification)
    context = SimpleNamespace()
    assert isinstance(NativeGridQualification.journey(context, Mock()), NativeGridJourney)
    assert context.installed_snapshot.startswith('onpc-v')
    assert {tag[3:] for tag in PLAN.screen_tags.values()} <= accessible_ui.OPERATIONS
    assert accessible_ui.NATIVE_APP_OPERATIONS <= accessible_ui.STANDARD_OPERATIONS
    assert accessible_ui.NATIVE_APP_OPERATIONS <= OPERATION_LABELS.keys()
    assets = object()
    monkeypatch.setattr(check, 'named_input', lambda **kwargs: assets)
    calls = []
    monkeypatch.setattr(check, 'smoke', lambda **kwargs: calls.append(kwargs) or 0)
    assert check.main() == 0
    assert calls == [{'assets': assets, 'provision_credentials': True, 'native_grid_usable': True}]
    for changes in ({}, {'assets': assets, 'provision_credentials': True, 'parent_toggle': True}):
        with pytest.raises(CommandError, match='smoke:native-grid-prerequisites'):
            smoke.main(native_grid_usable=True, **changes)


@pytest.mark.parametrize('fault', ['', 'uncertain', 'opened', 'submit', 'submitted', 'close'])
def test_actual_worker_matches_plan_and_stops_before_later_input(fault, tmp_path):
    result = json.loads(run_perl(r'''
use strict;
use warnings;
use JSON::PP;
our @events;
our $fault = shift @ARGV;
BEGIN { $INC{'testapi.pm'} = 1; $INC{'onpc_gdm.pm'} = 1; }
package onpc_gdm;
sub reattach_functional { }
package testapi;
sub record_info { push @main::events, ['marker', $_[0]] }
sub type_string { push @main::events, ['query', $_[0]] }
sub send_key {
    push @main::events, ['key', $_[0]];
    die 'uncertain' if $main::fault eq 'uncertain' && $_[0] eq 'ret';
}
package main;
require onpc_app_rows;
no warnings 'redefine';
*onpc_parent::sign_in = sub {
    die 'wrong account' unless $_[1] eq 'other-child';
    $_[0]->seen($_) for qw(installed-greeter standard-focused standard-recipient-qualified standard-recipient-rechecked);
    return $_[0]->seen('desktop');
};
*onpc_journey::finish = sub { push @events, ['finish'] };
my $ok = eval {
    onpc_app_rows::native_grid_usable(sub {
        my ($stage) = @_;
        push @events, ['seen', $stage];
        die 'refused' if $fault ne '' && $stage eq 'first-' . $fault;
        return {};
    }); 1;
};
print encode_json({ok => $ok ? 1 : 0, error => $@, events => \@events});
''', fault).stdout)
    events = result['events']
    assert bool(result['ok']) == (not fault), result['error']
    assert events.count(['key', 'ret']) == (1 if fault else 2)
    if not fault:
        assert [event[1] for event in events if event[0] == 'seen'] == list(PLAN.screen_tags)
        assert events.count(['query', accessible_ui.NATIVE_PRODUCT]) == 2
        assert events[-1] == ['finish']
        # Reconcile real worker titles, rather than synthesizing them from PLAN.
        # Ordered callbacks alone cannot prove that final evidence is complete.
        details = [{'title': event[1], 'result': 'ok'}
                   for event in events if event[0] == 'marker']
        observations = [{'stage': stage, 'ui': {
            'operation': tag[3:], 'outcome': 'passed', 'interface': 'ApplicationUI+external-provider'}}
            for stage, tag in PLAN.screen_tags.items()]
        results = tmp_path / 'testresults'
        results.mkdir()
        evidence = results / 'result-smoke.json'
        evidence.write_text(json.dumps({'result': 'ok', 'details': details}))
        assert [item['stage'] for item in matched_screens(tmp_path, PLAN, observations)] == list(PLAN.screen_tags)
        # Preserve complete, fresh and ordered evidence requirements.
        for invalid in (details[:-1], details + [details[-1]],
                        [details[1], details[0], *details[2:]],
                        [{**item, 'title': item['title'].replace('native-grid-usable-', 'native-grid-')}
                         for item in details]):
            evidence.write_text(json.dumps({'result': 'ok', 'details': invalid}))
            with pytest.raises(EvidenceError):
                matched_screens(tmp_path, PLAN, observations)
        evidence.write_text(json.dumps({'result': 'ok', 'details': details}))
        with pytest.raises(EvidenceError):
            matched_screens(tmp_path, PLAN, observations[:-1])
    else:
        assert ['finish'] not in events
        assert not any(event[0] == 'seen' and event[1].startswith('repeat-') for event in events)


def test_riley_grid_registration_decoder_and_real_recorder_startup(tmp_path, monkeypatch):
    from unittest.mock import MagicMock
    import check_e2e_riley_native_grid as riley_check
    from riley_native_grid import PLAN as plan, RileyNativeGridJourney
    from installed_journey import record_installed_journey
    from parent_setup_qualification import RileyNativeGridQualification
    from journey_blocks import native_usable_app

    context = SimpleNamespace(directory=tmp_path, credentials=Mock(), lease=Mock(),
                              verified=SimpleNamespace(inputs={}), guestfs=Mock(), commands=Mock())
    assert isinstance(RileyNativeGridQualification.journey(context, Mock()), RileyNativeGridJourney)
    assert context.installed_snapshot.startswith('onpc-v')
    assert {tag[3:] for tag in plan.screen_tags.values() if tag.startswith('ui:')} <= accessible_ui.OPERATIONS
    assert accessible_ui.OVERLAY_NATIVE_OPERATIONS <= OPERATION_LABELS.keys()
    assert native_usable_app('grid', child='child')['app-grid'] == 'ui:overlay-native-grid'
    assets = object()
    monkeypatch.setattr(riley_check, 'named_input', Mock(return_value=assets))
    monkeypatch.setattr(riley_check, 'smoke', Mock(return_value=0))
    assert riley_check.main() == 0
    riley_check.named_input.assert_called_once_with(vm_source=True, fixture_source=True)
    riley_check.smoke.assert_called_once_with(assets=assets, provision_credentials=True, riley_native_grid=True)
    for changes in ({}, {'assets': assets, 'provision_credentials': True, 'native_grid_usable': True}):
        with pytest.raises(CommandError, match='riley-native-grid-prerequisites'):
            smoke.main(riley_native_grid=True, **changes)
    provider = {'version': '50.1', 'locale': 'en_US.UTF-8', 'keyboard': [['xkb', 'us']]}
    for operation in ('overlay-native-grid', 'overlay-native-grid-refusals'):
        raw = json.dumps({'operation': operation, 'outcome': 'passed',
                          'interface': 'ApplicationUI+external-provider', 'provider': provider}).encode()
        assert UiObservations(SimpleNamespace(call=Mock(return_value=raw))).observe(operation)['provider'] == provider
    recorder = MagicMock(assertion=Mock())
    context.recorder = recorder
    def worker(**options):
        journey = options['guarded_observe'].__self__
        assert type(journey) is RileyNativeGridJourney and journey.plan is plan
        assert set(journey.actions) == {'native-refuse', 'native-verify'}
        assert options['validate'].__self__ is journey and options['authenticate'] is True
        raise EvidenceError('synthetic-worker-stop')
    context.run_worker = Mock(side_effect=worker)
    with pytest.raises(EvidenceError, match='synthetic-worker-stop'):
        record_installed_journey(recorder, context, plan, journey_type=RileyNativeGridJourney)
    context.run_worker.assert_called_once()
    recorder.assertion.assert_not_called()


@pytest.mark.parametrize('fault', ['', 'allowance-configured', 'wrong-account-refused',
    'repeat-parent-desktop', 'switch-user', 'gdm-switched',
    'first-search-ready', 'first-search-focused', 'first-search-entered', 'first-app-grid',
    'uncertain', 'first-opened', 'first-submit', 'first-submitted', 'first-close',
    'repeat-refusals', 'repeat-app-grid', 'repeat-opened'])
def test_riley_actual_worker_order_markers_and_no_fallback(fault, tmp_path):
    from riley_native_grid import PLAN as plan
    result = json.loads(run_perl(r'''
use strict; use warnings; use JSON::PP;
our @events; our $fault = shift @ARGV;
BEGIN { $INC{'testapi.pm'}=1; }
package testapi;
sub record_info { push @main::events, ['marker', $_[0]] }
sub type_string { push @main::events, ['query', $_[0]] }
sub send_key { push @main::events, ['key', $_[0]];
    die 'uncertain' if $main::fault eq 'uncertain' && $_[0] eq 'ret'; }
package main;
require onpc_app_rows;
require onpc_desktop_session;
no warnings 'redefine';
*onpc_gdm::reattach_functional = sub {};
*onpc_gdm::sign_in_challenge = sub {
    my($j,$binding,$list,$focus,$desktop)=@_;
    $j->seen($list); $j->seen($focus);
    $j->seen($_) for @{$j->{challenges}{$binding}}[1,2];
    return $j->seen($desktop);
};
*onpc_parent::launch = sub {$_[0]->seen('parent-command'); $_[0]->seen('parent-window');};
*onpc_parent::select_child = sub {
    die 'wrong child' unless $_[1] eq 'child';
    $_[0]->seen('child-choice-highlighted'); return $_[0]->seen('parent-selected');
};
*onpc_journey::finish = sub {push @events, ['finish']};
my $declared=decode_json(shift @ARGV); my $challenges=decode_json(shift @ARGV);
my $ok=eval {onpc_app_rows::riley_native_grid(sub {
    my($stage)=@_; push @events, ['seen',$stage];
    die 'refused' if $fault ne '' && $stage eq $fault;
    return {};
}, $declared, $challenges); 1;};
print encode_json({ok=>$ok?1:0,error=>$@,events=>\@events});
''', fault, json.dumps(plan.invocations), json.dumps(plan.challenges)).stdout)
    events = result['events']
    assert bool(result['ok']) == (not fault), result['error']
    assert not any(event == ['seen', 'first-command'] or event == ['seen', 'repeat-command'] for event in events)
    expected_launches = (2 if not fault or fault == 'repeat-opened' else
                         1 if fault == 'uncertain' or (fault.startswith('repeat-') and fault != 'repeat-parent-desktop') or fault in
                         ('first-opened', 'first-submit', 'first-submitted', 'first-close') else 0)
    assert events.count(['key', 'ret']) == expected_launches
    if not fault:
        assert events.count(['key', 'ret']) == 2
        assert events.count(['query', accessible_ui.NATIVE_PRODUCT]) == 2
        assert [event[1] for event in events if event[0] == 'seen'] == list(plan.screen_tags)
        details = [{'title': event[1], 'result': 'ok'} for event in events if event[0] == 'marker']
        observations = [{'stage': stage, 'ui': {'operation': tag[3:], 'outcome': 'passed',
            'interface': 'ApplicationUI+external-provider'}} for stage, tag in plan.screen_tags.items()]
        for observation in observations:
            tag = plan.screen_tags[observation['stage']]
            if tag.startswith('system:'):
                observation['system'] = {'operation': tag[7:], 'outcome': 'passed'}
                del observation['ui']
            if plan.challenge_at(observation['stage']) is not None:
                observation['challenge'] = plan.challenge_at(observation['stage'])
        results = tmp_path / 'testresults'
        results.mkdir()
        (results / 'result-smoke.json').write_text(json.dumps({'result': 'ok', 'details': details}))
        assert [item['stage'] for item in matched_screens(tmp_path, plan, observations)] == list(plan.screen_tags)
        assert events[-1] == ['finish']
    else:
        assert ['finish'] not in events
        if fault != 'uncertain':
            assert [event[1] for event in events if event[0] == 'seen'] == list(plan.screen_tags)[:list(plan.screen_tags).index(fault) + 1]


def test_riley_grid_account_and_result_refuse_before_unrelated_discovery(monkeypatch):
    ui = ui_for(Node())
    discovery = Mock(side_effect=AssertionError('discovery must not run'))
    ui.shell_search_snapshot = discovery
    ui.require_child_overlay_session = Mock(side_effect=UiError('ui:overlay-account'))
    with pytest.raises(UiError, match='ui:overlay-account'):
        ui.run('overlay-native-grid', '')
    discovery.assert_not_called()
    ui.require_child_overlay_session = Mock()
    for product, uncertain, expected in (('ONPC Hard Fixture', False, 'ui:search-binding'),
                                        (accessible_ui.NATIVE_PRODUCT, True, 'ui:uncertain-input')):
        ui.input_uncertain = uncertain
        with pytest.raises(UiError, match=expected): ui.focus_search_result(product)
        discovery.assert_not_called()


@pytest.mark.parametrize('route', ['semantic', 'ids'])
@pytest.mark.parametrize('fault', ['incomplete', 'departed', 'persistent', 'missing',
                                  'ambiguous', 'delivery'])
def test_grid_final_recipient_reacquires_only_reads_before_single_focus(monkeypatch, route, fault):
    from gi.repository import Gio, GLib
    ui = ui_for(Node())
    ui.provider_contracts['gnome-shell']['application_id'] = '' if route == 'semantic' else 'test-shell'
    ui.handle_system_prompt = Mock()
    ui.search_query = Mock(return_value=True)
    ui.query_errors = (GLib.Error,)
    ui.timeout = 1
    clock = [0]
    monkeypatch.setattr(accessible_ui.time, 'monotonic', lambda: clock[0])
    monkeypatch.setattr(accessible_ui.time, 'sleep', lambda _: clock.__setitem__(0, clock[0] + .5))
    target = Node(accessible_ui.NATIVE_PRODUCT, 'button')
    departed = Gio.DBusError.new_for_dbus_error(
        'org.freedesktop.DBus.Error.ServiceUnknown', 'departed provider')
    reads = []

    def fresh(*_args):
        reads.append(True)
        if not target.component.grab_focus.called:
            if len(reads) == 2 or fault == 'persistent' and len(reads) >= 2:
                if fault in ('departed', 'persistent'):
                    raise departed
                if fault == 'incomplete':
                    raise UiError('ui:incomplete-tree')
                if fault == 'missing':
                    return None
                if fault == 'ambiguous':
                    raise UiError('ui:shell-result-ambiguous')
        return target

    if route == 'semantic':
        ui.launchable_result = Mock(side_effect=fresh)
    else:
        ui.launchable_result = Mock(return_value=target)
        # Count the initial result proof and the independent final ID recheck.
        ui.launchable_result.side_effect = lambda _product: (fresh() if not reads else target)
        ui.fresh_owned_target = Mock(side_effect=fresh)
    if fault == 'delivery':
        target.component.grab_focus.side_effect = departed
    if fault in ('persistent', 'missing', 'ambiguous'):
        expected = {'persistent': 'ui:timeout:parent-search-recipient',
                    'missing': 'ui:search-result-stale', 'ambiguous': 'ui:shell-result-ambiguous'}[fault]
        with pytest.raises(UiError, match=expected):
            ui.focus_search_result(accessible_ui.NATIVE_PRODUCT)
        target.component.grab_focus.assert_not_called()
    elif fault == 'delivery':
        with pytest.raises(GLib.Error) as caught:
            ui.focus_search_result(accessible_ui.NATIVE_PRODUCT)
        assert caught.value is departed
        with pytest.raises(UiError, match='ui:uncertain-input'):
            ui.focus_search_result(accessible_ui.NATIVE_PRODUCT)
        target.component.grab_focus.assert_called_once()
    else:
        ui.focus_search_result(accessible_ui.NATIVE_PRODUCT)
        target.component.grab_focus.assert_called_once()
        assert len(reads) >= 3 and not ui.input_uncertain


@pytest.mark.parametrize('fault', ['departed', 'incomplete', 'persistent', 'query', 'focus', 'ambiguous'])
def test_grid_refusal_comparison_reacquires_whole_reads_without_refocusing(monkeypatch, fault):
    from gi.repository import Gio, GLib
    ui = ui_for(Node())
    ui.provider_contracts['gnome-shell']['application_id'] = ''
    ui.handle_system_prompt = Mock()
    ui.query_errors = (GLib.Error,)
    ui.timeout = 1
    clock = [0]
    monkeypatch.setattr(accessible_ui.time, 'monotonic', lambda: clock[0])
    monkeypatch.setattr(accessible_ui.time, 'sleep', lambda _: clock.__setitem__(0, clock[0] + .5))
    target = Node(accessible_ui.NATIVE_PRODUCT, 'button')
    departed = Gio.DBusError.new_for_dbus_error(
        'org.freedesktop.DBus.Error.ServiceUnknown', 'departed provider')
    queries = []

    def query(_product):
        queries.append(True)
        if len(queries) == 1:
            return True
        target.component.grab_focus.assert_called_once()
        if len(queries) == 2 or fault == 'persistent':
            if fault in ('departed', 'persistent'):
                raise departed
            if fault == 'incomplete':
                raise UiError('ui:incomplete-tree')
            if fault == 'query':
                return False
            if fault == 'focus':
                target.states.discard('focused')
            if fault == 'ambiguous':
                raise UiError('ui:shell-result-ambiguous')
        return True

    ui.search_query = Mock(side_effect=query)
    ui.launchable_result = Mock(return_value=target)
    if fault in ('persistent', 'query', 'focus', 'ambiguous'):
        expected = {'persistent': 'ui:timeout:native-refusal-entry',
                    'query': 'ui:native-refusal-query', 'focus': 'ui:native-refusal-focus',
                    'ambiguous': 'ui:shell-result-ambiguous'}[fault]
        with pytest.raises(UiError, match=expected):
            ui.native_app_operation('native-grid-refusals', child=accessible_ui.CHILD)
    else:
        ui.native_app_operation('native-grid-refusals', child=accessible_ui.CHILD)
        assert len(queries) == 3
    target.component.grab_focus.assert_called_once()
    target.action.do_action.assert_not_called()
    assert not ui.input_uncertain


@pytest.mark.parametrize('operation', ['native-grid', 'overlay-native-grid',
                                     'native-grid-refusals', 'overlay-native-grid-refusals'])
def test_grid_metadata_uses_the_same_complete_read_reacquisition(monkeypatch, operation):
    from gi.repository import Gio, GLib
    ui = ui_for(Node())
    ui.query_errors = (GLib.Error,)
    ui.native_app_operation = Mock()
    ui.require_child_overlay_session = Mock()
    owner = Node(role='application')
    metadata = {'version': '50.5', 'locale': 'en_US.UTF-8', 'keyboard': [['xkb', 'us']]}
    ui._shell_provider_metadata = Mock(return_value=metadata)
    ui.shell_search_snapshot = Mock(side_effect=[
        Gio.DBusError.new_for_dbus_error('org.freedesktop.DBus.Error.ServiceUnknown', 'departed'),
        (owner, [], {}, {})])
    ui.timeout = 1
    monkeypatch.setattr(accessible_ui.time, 'sleep', lambda _: None)
    assert ui.run(operation, '')['provider'] == metadata
    assert ui.shell_search_snapshot.call_count == 2
    ui.native_app_operation.assert_called_once()
