"""Synthetic request-station forms and worker for related E2E unit cases."""

from accessible_ui import CHILD, EXISTING_CHILD, OTHER_PARENT, PARENT, PRODUCT
from tests.support.accessible_ui import Node, ui_for


def request_form(*, fault=None):
    child = Node(
        'Child account', 'push button', identity='kiosk-child-selector',
        description='Selected child account: Jordan (Child).',
        children=[Node('Jordan (Child)', 'label', identity='kiosk-child-selected-1002')],
    )
    approver = Node(
        'Approving parent', 'push button', states=('showing', 'visible'),
        identity='kiosk-approver-selector',
        description='Selected approving parent: Casey (Parent).',
        children=[Node('Casey (Parent)', 'label', identity='kiosk-approver-selected-1010')],
    )
    durations = []
    duration_values = (300, 900, 1800, 3600, 7200, 14400, 0, 'custom')
    for label, value in zip(
            ('5 minutes', '15 minutes', '30 minutes', '1 hour', '2 hours',
             '4 hours', 'Rest of the day', 'Custom value'), duration_values):
        states = ['showing', 'visible']
        if label == '30 minutes':
            states.append('pressed')
        durations.append(Node(
            'Request ' + label, 'toggle button', states=states,
            identity=f'kiosk-duration-{value}',
        ))
    allow_soft = Node(
        'Allow soft blocked apps', 'switch', states=('showing', 'visible'),
        identity='kiosk-soft-apps-toggle',
    )
    request = Node(
        'Request access', 'push button', states=('showing', 'visible'),
        identity='kiosk-request-submit',
    )
    cancel = Node('Cancel request', 'push button', identity='kiosk-request-cancel')
    notice = Node(
        'Screen limit is not enabled in Parent App', 'label',
        identity='kiosk-screen-limit-notice',
    )
    children = [child, approver, *durations, allow_soft, request, cancel, notice]
    if fault == 'wrong-duration':
        durations[2].states.remove('pressed')
        durations[1].states.add('pressed')
    elif fault == 'multiple-durations':
        durations[1].states.add('pressed')
    elif fault == 'checked-not-pressed':
        durations[2].states.remove('pressed')
        durations[2].states.add('checked')
    elif fault == 'duration-enabled':
        durations[2].states.add('sensitive')
    elif fault == 'request-enabled':
        request.states.add('sensitive')
    elif fault == 'custom-visible':
        children.append(Node(
            'Custom duration in minutes', 'entry',
            identity='kiosk-custom-duration',
        ))
    elif fault == 'missing-message':
        children.remove(notice)
    elif fault == 'mute-present':
        children.append(Node(
            'Mute request sounds', 'switch', identity='kiosk-mute-button',
        ))
    elif fault == 'duplicate-form':
        children.append(Node(identity='kiosk-request-form'))
    form = Node(PRODUCT, 'frame', children=children, identity='kiosk-request-form')
    return ui_for(Node(identity='kiosk-request-window', children=[form])), tuple(durations)


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


def disabled_accounts_form():
    ui, selector, choices, expected = accounts_form()

    def commit(_):
        selector.children[0].identity = 'kiosk-child-selected-1001'
        selector.children[0].name = CHILD
        selector.description = f'Selected child account: {CHILD}.'
        choices.states.discard('showing')
        return True

    choices.children[0].action.do_action.side_effect = commit
    return ui, selector, choices, expected


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
