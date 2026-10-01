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
    result = {'operation': operation, 'outcome': 'passed', 'interface': 'AT-SPI', key: value}
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
            'operation': tag[3:], 'outcome': 'passed', 'interface': 'AT-SPI'}}
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
