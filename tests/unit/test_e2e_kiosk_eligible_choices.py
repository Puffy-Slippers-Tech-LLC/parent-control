"""Owned account input, exact eligibility, and independent result guards."""

from dataclasses import FrozenInstanceError
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from accessible_ui import CHILD, EXISTING_CHILD, PARENT, OTHER_PARENT, UiError
from private_artifacts import EvidenceError
from tests.support.accessible_ui import Node, ui_for
from test_e2e_kiosk_entry import request_form
from ui_observations import RequestObservation, UiObservations


def accounts_form(field='child'):
    ui, _ = request_form()
    form = ui.find_id('kiosk-request-form')
    selector = ui.find_id(f'kiosk-{field}-selector')
    expected = (CHILD, EXISTING_CHILD) if field == 'child' else (PARENT, OTHER_PARENT)
    label = 'Child account' if field == 'child' else 'Approving parent'
    choices = Node(identity=f'kiosk-{field}-choices', states=('visible',), children=[
        Node(f'{label}: {name}', identity=f'kiosk-{field}-choice-{ui.fixture_uids[name]}')
        for name in expected])
    choices.parent = form
    form.children.append(choices)
    selector.states.add('sensitive')
    selector.action.do_action.side_effect = lambda _: choices.states.add('showing') or True

    def commit(_):
        selected = selector.children[0]
        selected.identity = f'kiosk-{field}-selected-{ui.fixture_uids[expected[0]]}'
        selected.name = expected[0]
        selector.description = f'Selected {label.casefold()}: {expected[0]}.'
        # Independent form read, with enabled availability after loading.
        for node in form.children:
            if node.identity == 'kiosk-screen-limit-notice':
                node.states.discard('showing')
            else:
                node.states.add('sensitive')
        choices.states.discard('showing')
        return True

    choices.children[0].action.do_action.side_effect = commit
    if field == 'approver':
        child = ui.find_id('kiosk-child-selector')
        child.children[0].identity = 'kiosk-child-selected-1001'
        child.description = f'Selected child account: {CHILD}.'
    return ui, selector, choices, expected


@pytest.mark.parametrize('field', ['child', 'approver'])
def test_selection_checks_exact_choices_and_reads_independent_enabled_result(field):
    ui, selector, choices, expected = accounts_form(field)
    operation = f'kiosk-{field}-select'
    result = ui.run(operation, '')
    observed = RequestObservation.from_request(result['request'], operation=operation)
    assert observed.child == 'fixture-child'
    assert observed.request_enabled
    selector.action.do_action.assert_called_once()
    choices.children[0].action.do_action.assert_called_once()
    choices.children[1].action.do_action.assert_not_called()
    with pytest.raises(FrozenInstanceError):
        observed.child = 'changed'


@pytest.mark.parametrize('fault', ['missing', 'extra', 'duplicate', 'wrong-label',
                                 'disabled', 'hidden', 'wrong-owner', 'wrong-surface'])
def test_bad_offered_set_never_commits(fault):
    ui, selector, choices, expected = accounts_form()
    target = choices.children[0]
    if fault == 'missing':
        choices.children.pop()
    elif fault == 'extra':
        choices.children.append(Node(identity='kiosk-child-choice-9999'))
    elif fault == 'duplicate':
        choices.children.append(Node(identity=target.identity))
    elif fault == 'wrong-label':
        target.name = 'Child account: wrong'
    elif fault in ('disabled', 'hidden'):
        target.states.discard('sensitive' if fault == 'disabled' else 'visible')
    elif fault == 'wrong-owner':
        ui.owner_pids = lambda: {999}
    else:
        ui.find_id('kiosk-request-window').identity = 'parent-window'
    with pytest.raises(UiError):
        ui.select_kiosk_account('child', CHILD, expected=expected)
    target.action.do_action.assert_not_called()


def test_wrong_or_absent_choice_refuses_before_any_input():
    ui, selector, choices, expected = accounts_form()
    for name in (PARENT, 'Missing account'):
        with pytest.raises(UiError, match='kiosk-account-choice'):
            ui.select_kiosk_account('child', name, expected=expected)
    selector.action.do_action.assert_not_called()


def test_overlay_disabled_child_selector_refuses_input():
    ui, selector, choices, expected = accounts_form()
    selector.states.discard('sensitive')
    with pytest.raises(UiError, match='kiosk-account-unavailable'):
        ui.select_kiosk_account('child', CHILD, expected=expected)
    selector.action.do_action.assert_not_called()


def test_uncertain_action_is_never_replayed():
    ui, selector, choices, expected = accounts_form()
    choices.children[0].action.do_action.side_effect = RuntimeError('lost reply')
    with pytest.raises(RuntimeError):
        ui.select_kiosk_account('child', CHILD, expected=expected)
    with pytest.raises(UiError, match='uncertain-input'):
        ui.select_kiosk_account('child', CHILD, expected=expected)
    selector.action.do_action.assert_called_once()
    choices.children[0].action.do_action.assert_called_once()


def test_successful_input_without_changed_selection_fails():
    ui, selector, choices, expected = accounts_form()
    commit = choices.children[0].action.do_action.side_effect
    def wrong(index):
        commit(index)
        selector.children[0].identity = 'kiosk-child-selected-1002'
        selector.description = f'Selected child account: {EXISTING_CHILD}.'
        return True
    choices.children[0].action.do_action.side_effect = wrong
    with pytest.raises(UiError, match='timeout:kiosk-request-form'):
        ui.select_kiosk_account('child', CHILD, expected=expected)
    choices.children[0].action.do_action.assert_called_once()
    with pytest.raises(UiError, match='uncertain-input'):
        ui.select_kiosk_account('child', CHILD, expected=expected)


def test_controller_validates_enabled_results_and_rejects_wrong_account():
    import json
    ui, *_ = accounts_form('approver')
    result = ui.run('kiosk-approver-select', '')
    observer = UiObservations(Mock())
    observer.call = Mock(return_value=(json.dumps(result).encode(), []))
    assert observer.observe('kiosk-approver-select') == result
    result['request']['approver'] = 'other-fixture-parent'
    observer.call.return_value = (json.dumps(result).encode(), [])
    with pytest.raises(EvidenceError, match='ui:request'):
        observer.observe('kiosk-approver-select')


def test_qualification_uses_shared_snapshot_and_guarded_envelope(tmp_path):
    import check_e2e_kiosk_eligible_choices as check
    from parent_setup_qualification import KioskEligibleChoicesQualification, KioskEntryQualification
    from kiosk_eligible_choices import PLAN
    context = SimpleNamespace(directory=tmp_path)
    journey = KioskEligibleChoicesQualification.journey(context, Mock())
    assert journey.plan is PLAN
    assert context.installed_snapshot == 'onpc-v1.1'
    assert KioskEligibleChoicesQualification.attach_installed_snapshot is KioskEntryQualification.attach_installed_snapshot
    assert str(check.ASSETS) == '/tmp/onpc-parent-setup-input'


@pytest.mark.parametrize('conflict', ['parent_toggle', 'kiosk_entry', 'license_viewer_provider'])
def test_qualification_refuses_conflicting_modes_before_vm_access(conflict):
    import check_graphical_smoke as smoke
    from owned_commands import CommandError
    with pytest.raises(CommandError, match='kiosk-eligible-choices-prerequisites'):
        smoke.main(assets='/unused', provision_credentials=True,
                   kiosk_eligible_choices=True, **{conflict: True})


def test_account_snapshot_rejects_incomplete_tree_before_input():
    ui, selector, choices, expected = accounts_form()
    choices.children.append(None)
    with pytest.raises(UiError):
        ui.select_kiosk_account('child', CHILD, expected=expected)
    selector.action.do_action.assert_not_called()


def test_account_snapshot_uses_one_complete_read_for_input_boundary():
    ui, selector, choices, expected = accounts_form()
    ui.nodes = Mock(wraps=ui.nodes)
    assert ui.kiosk_account_snapshot('child')[0] is selector
    assert ui.nodes.call_count == 1


WORKER = r'''
use strict;
use warnings;
use JSON::PP;
our @events;
BEGIN { $INC{'testapi.pm'} = 1; }
package testapi;
sub current_console { 'sut' }
sub reset_consoles { }
sub select_console { }
sub send_key { push @main::events, ['key', $_[0]] }
sub record_info { }
sub get_var { '1' }
sub get_required_var { 'fixture-only' }
sub type_password { push @main::events, ['secret'] }
sub console { bless {}, 'Console' }
sub power { push @main::events, ['power', $_[0]] }
sub check_shutdown { 1 }
package Console;
sub disable { }
package main;
require onpc_kiosk_eligible_choices;
my $ok = eval {
    onpc_kiosk_eligible_choices::run(sub {
        my ($stage) = @_;
        push @events, ['stage', $stage];
        die 'fixture:refused' if ($ENV{ONPC_TEST_REFUSE_STAGE} // '') eq $stage;
        return {observed => $stage, ui_focused => JSON::PP::true}
            if $stage =~ /(?:greeter|station-list|focused|picker-opened)\z/;
        return {observed => $stage, station_destination => 'default-request-form'}
            if $stage eq 'station-branch';
        return {observed => $stage};
    });
    1;
};
print encode_json({ok => $ok ? 1 : 0, events => \@events, error => "$@"});
'''


@pytest.mark.parametrize('refusal', [None, 'save-enabled', 'child-selected'])
def test_worker_order_stops_on_failed_public_result(monkeypatch, refusal):
    import json
    from tests.support.perl import run_perl
    from kiosk_eligible_choices import PLAN
    if refusal:
        monkeypatch.setenv('ONPC_TEST_REFUSE_STAGE', refusal)
    result = json.loads(run_perl(WORKER).stdout)
    stages = [event[1] for event in result['events'] if event[0] == 'stage']
    expected = list(PLAN.screen_tags)
    if refusal:
        assert not result['ok']
        assert stages == expected[:expected.index(refusal) + 1]
    else:
        assert result['ok'], result['error']
        assert stages == expected
        assert result['events'][-1] == ['power', 'off']
