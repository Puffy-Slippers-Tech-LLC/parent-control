"""Public request-station entry and immutable form observation contracts."""

import json
from dataclasses import FrozenInstanceError
from pathlib import Path

import pytest

from accessible_ui import EXTERNAL_PROVIDER_CONTRACTS, PRODUCT, UiError
from private_artifacts import EvidenceError
from tests.support.accessible_ui import Node, ui_for
from tests.support.paths import ROOT
from tests.support.perl import run_perl
from ui_observations import RequestObservation
from installed_journey import InstalledJourney


def station_greeter(*rows, recipient=None, field=None, list_showing=True):
    children = list(rows) if list_showing else []
    if recipient is not None:
        children.append(recipient)
    if field is not None:
        children.append(field)
    application = Node('GNOME Shell', 'application', children=children)
    return ui_for(Node(role='desktop frame', children=[application]))


def test_station_observer_does_not_wait_for_session_services(monkeypatch):
    from types import SimpleNamespace
    import accessible_ui

    def forbidden(*_args, **_kwargs):
        pytest.fail('station observation must wait for the public form')

    monkeypatch.setattr(accessible_ui, 'session_environment', forbidden)
    assert accessible_ui.observation_environment(
        SimpleNamespace(pw_uid=1234), 'kiosk-request-form') == {
            'XDG_RUNTIME_DIR': '/run/user/1234',
            'DBUS_SESSION_BUS_ADDRESS': 'unix:path=/run/user/1234/bus',
        }


def test_kiosk_qualification_stays_on_public_gui_not_backend_buses():
    session = (ROOT / 'data/systemd/user/gnome-session@oh-no-parent-control.target.d'
               / 'session.conf').read_text()
    app = (ROOT / 'data/systemd/user/oh-no-parent-control-app.service').read_text()
    observer = (ROOT / 'tests/e2e/accessible_ui.py').read_text()
    units = ROOT / 'data/systemd/user'
    assert not (units / 'oh-no-parent-control-at-spi.service').exists()
    assert not (units / 'oh-no-parent-control-at-spi-registry.service').exists()
    assert 'oh-no-parent-control-at-spi' not in session
    assert 'oh-no-parent-control-at-spi' not in app
    assert 'GTK_A11Y' not in app
    assert 'wait_atspi_address' not in observer
    assert 'at-spi2-registryd' not in observer
    assert 'org.a11y.atspi.Registry' not in observer
    assert 'GetAddress' not in observer
    assert 'StartServiceByName' not in observer
    assert 'kiosk_request_form' in observer
    assert 'get_accessible_id' in observer


def test_kiosk_qualification_reuses_the_prepared_app_snapshot(tmp_path):
    from contextlib import nullcontext
    from types import SimpleNamespace
    from unittest.mock import Mock

    import check_e2e_kiosk_entry as check
    from parent_setup_qualification import KioskEntryQualification

    assert check.ASSETS == Path('/tmp/onpc-parent-setup-input')
    context = SimpleNamespace(directory=tmp_path)
    KioskEntryQualification.journey(context, lambda *_: None)
    assert context.installed_snapshot == 'onpc-v1.1'
    assert not hasattr(context, 'install_current_package')

    qualification = KioskEntryQualification.__new__(KioskEntryQualification)
    qualification.assets = tmp_path
    qualification.commands = Mock()
    qualification.commands.run.return_value = b'1.1+ppa1~ubuntu26.04.1\n'
    (tmp_path / 'package.deb').write_bytes(b'fixture')
    snap = Mock()
    lease = Mock()
    lease.source.domain.snapshotLookupByName.return_value = snap
    lease.source.api.VIR_DOMAIN_SNAPSHOT_REVERT_FORCE = 4
    lease.state = {'run': 'a' * 32}
    lease.test_xml = '<domain/>'
    lease.snapshot_status.return_value = nullcontext()
    qualification.attach_installed_snapshot(lease)
    lease.source.domain.snapshotLookupByName.assert_called_once_with('onpc-v1.1', 0)
    lease.source.domain.revertToSnapshot.assert_called_once_with(snap, 4)
    lease.source.connection.defineXML.assert_called_once_with('<domain/>')
    lease.guard.assert_called_once_with(off=True)


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


def test_kiosk_request_form_returns_only_the_fixed_public_projection():
    ui, durations = request_form()
    result = ui.run('kiosk-request-form', '')
    observation = RequestObservation.from_request(result['request'])
    assert observation == RequestObservation(
        surface='kiosk', form_count=1, child='existing-fixture-child',
        approver='other-fixture-parent', duration_seconds=1800, custom_text=None,
        allow_soft=False, child_selector_enabled=True, approver_selector_enabled=False,
        duration_enabled=False, soft_choice_enabled=False, request_enabled=False,
        cancel_enabled=True, message='screen-limit-disabled', mute=None)
    assert all(button.action.do_action.call_count == 0 for button in durations)


def test_station_positive_form_observation_permits_no_prompt_without_prompt_ids():
    ui, durations = request_form()
    ui.provider_contracts = EXTERNAL_PROVIDER_CONTRACTS
    result = ui.run('kiosk-request-form', '')
    RequestObservation.from_request(result['request'])
    assert ui.prompt_session == 'station'
    assert all(button.action.do_action.call_count == 0 for button in durations)


@pytest.mark.parametrize('identity', ['kiosk-child-selector', 'kiosk-approver-selector',
                                    'kiosk-request-submit', 'kiosk-screen-limit-notice',
                                    'kiosk-duration-1800'])
def test_station_never_borrows_a_control_from_another_surface(identity):
    ui, _ = request_form()
    form = ui.find_id('kiosk-request-form')
    target = next(node for node in form.children if node.identity == identity)
    form.children.remove(target)
    ui.api.get_desktop(0).children.append(Node(identity='unrelated-window', children=[target]))
    with pytest.raises(UiError, match='timeout:kiosk-request-form'):
        ui.kiosk_request_form()


def test_station_refuses_incomplete_form_even_when_required_controls_exist():
    ui, _ = request_form()
    ui.find_id('kiosk-request-form').children.append(Node(states=('defunct',)))
    with pytest.raises(UiError, match='stale-request-form'):
        ui.kiosk_request_form()


@pytest.mark.parametrize('role', ['window', 'dialog'])
def test_station_form_accepts_public_window_roles_with_the_same_required_contents(role):
    ui, _ = request_form()
    ui.find_id('kiosk-request-form').role = role
    RequestObservation.from_request(ui.run('kiosk-request-form', '')['request'])


def test_station_form_targets_controls_only_by_public_id():
    ui, _ = request_form()
    for node in ui.find_id('kiosk-request-form').children:
        if node.identity and node.identity != 'kiosk-screen-limit-notice':
            node.name = 'Changed visual label'
            node.role = 'changed-role'
    observation = RequestObservation.from_request(
        ui.run('kiosk-request-form', '')['request'])
    assert observation.child == 'existing-fixture-child'
    assert observation.duration_seconds == 1800


@pytest.mark.parametrize('fault', ['missing', 'wrong-uid', 'duplicate', 'wrong-description'])
@pytest.mark.parametrize('namespace', ['child', 'approver'])
def test_selected_account_requires_uid_identity_before_description(namespace, fault):
    ui, _ = request_form()
    selector = ui.find_id(f'kiosk-{namespace}-selector')
    if fault == 'missing':
        selector.children.clear()
    elif fault == 'wrong-uid':
        selector.children[0].identity = f'kiosk-{namespace}-selected-9000'
    elif fault == 'duplicate':
        selector.children.append(Node(identity=selector.children[0].identity))
    else:
        selector.description = 'Selected account: wrong person.'
    with pytest.raises(UiError):
        ui.kiosk_request_form()


def test_station_timeout_reports_only_registered_public_control_ids(capsys):
    ui = ui_for(Node('Unrelated private title', 'application', children=[
        Node('Unrelated private label', 'label')]))
    with pytest.raises(UiError, match='ui:timeout:kiosk-request-form'):
        ui.run('kiosk-request-form', '')
    output = capsys.readouterr().err
    assert 'Unrelated private' not in output
    assert not any(json.loads(output)['public_ids'].values())


def test_station_observer_refreshes_an_empty_public_tree_after_session_entry():
    from unittest.mock import Mock

    ui, _ = request_form()
    ready = ui.api.get_desktop(0)
    ui.api.get_desktop = Mock(return_value=Node(role='desktop frame'))
    ui.reset_observer = Mock(side_effect=lambda: setattr(ui.api.get_desktop, 'return_value', ready))
    ui.timeout = 1
    result = ui.run('kiosk-request-form', '')
    RequestObservation.from_request(result['request'])
    ui.reset_observer.assert_called_once_with()


def test_station_observer_never_refreshes_away_a_visible_form_mismatch():
    from unittest.mock import Mock

    ui, _ = request_form(fault='wrong-duration')
    ui.reset_observer = Mock()
    with pytest.raises(UiError, match='ui:kiosk-duration-selection'):
        ui.run('kiosk-request-form', '')
    ui.reset_observer.assert_not_called()


def test_installed_journey_keeps_the_validated_request_observation_immutable(tmp_path):
    journey = InstalledJourney(type('Context', (), {'directory': tmp_path})(), lambda *_: None,
                               __import__('kiosk_entry').PLAN)
    value = request_form()[0].run('kiosk-request-form', '')['request']
    journey.check_request('request-form', {'ui': {'request': value}})
    assert isinstance(journey.request_observations['request-form'], RequestObservation)
    with pytest.raises(FrozenInstanceError):
        journey.request_observations['request-form'].request_enabled = True


@pytest.mark.parametrize('fault', [
    'wrong-duration', 'multiple-durations', 'checked-not-pressed', 'duration-enabled',
    'request-enabled', 'custom-visible', 'missing-message',
    'mute-present', 'duplicate-form',
])
def test_kiosk_request_form_refuses_changed_or_ambiguous_state(fault):
    ui, _ = request_form(fault=fault)
    ui.timeout = 0
    with pytest.raises((UiError, EvidenceError)):
        RequestObservation.from_request(ui.run('kiosk-request-form', '')['request'])


def test_station_greeter_navigation_and_wrong_entry_are_independent():
    station = Node('oh-no-parent-control', 'push button',
                   states=('showing', 'visible', 'sensitive'))
    parent = Node('Jamie (Parent)', 'push button')
    ui = station_greeter(parent, station)
    assert ui.run('gdm-station-list', '')['focused'] is True
    assert ui.run('gdm-station-focused', '')['outcome'] == 'passed'

    field = Node('Password', 'password text',
                 states=('showing', 'visible', 'sensitive', 'focused'))
    field.get_text_iface = lambda: (_ for _ in ()).throw(AssertionError('password read'))
    prompt = station_greeter(recipient=Node('Jamie (Parent)', 'label'), field=field,
                             list_showing=False)
    assert prompt.run('gdm-station-wrong-entry-refused', '')['outcome'] == 'passed'


def test_station_display_name_and_username_on_one_row_are_one_target():
    parent = Node('Jamie (Parent)', 'push button')
    station = Node('Oh No! Parent Control', 'push button',
                   states=('showing', 'visible', 'sensitive', 'focused'))
    ui = station_greeter(parent, station)
    assert ui.run('gdm-station-focused', '')['outcome'] == 'passed'


def test_unnamed_station_row_uses_exact_nested_labels_only_to_bind_its_button():
    parent = Node('Jamie (Parent)', 'push button')
    labels = [Node('Oh No! Parent Control', 'label'),
              Node('oh-no-parent-control', 'label')]
    station = Node('', 'push button', children=labels,
                   states=('showing', 'visible', 'sensitive', 'focused'))
    ui = station_greeter(parent, station)
    assert ui.run('gdm-station-focused', '')['outcome'] == 'passed'
    for label in labels:
        label.component.grab_focus.assert_not_called()
        label.action.do_action.assert_not_called()


RUN = r'''
use strict;
use warnings;
use JSON::PP;
our @events;
our $destination = shift // 'default-request-form';
BEGIN { $INC{'testapi.pm'} = 1; }
package testapi;
sub current_console { 'sut' }
sub reset_consoles { push @main::events, ['reset'] }
sub select_console { push @main::events, ['console', $_[0]] }
sub record_info { push @main::events, ['stage', $_[0]] }
sub send_key { push @main::events, ['key', $_[0]] }
sub console { bless {}, 'Console' }
sub power { push @main::events, ['power', $_[0]] }
sub check_shutdown { 1 }
package Console;
sub disable { push @main::events, ['disable'] }
package main;
require onpc_kiosk_entry;
my $ok = eval {
    onpc_kiosk_entry::run(sub {
        my ($stage) = @_;
        push @events, ['exchange', $stage];
        return {ui_focused => 1} if $stage eq 'station-list';
        return {ui_focused => 1} if $stage eq 'installed-greeter';
        return {station_destination => $destination} if $stage eq 'station-branch';
        return {observed => $stage};
    });
    1;
};
print encode_json({ok => $ok ? 1 : 0, events => \@events});
'''


def test_station_worker_uses_one_wrong_route_then_one_passwordless_route():
    result = json.loads(run_perl(RUN).stdout)
    assert result['ok']
    exchanges = [event[1] for event in result['events'] if event[0] == 'exchange']
    assert exchanges == [
        'installed-greeter', 'wrong-parent-focused', 'wrong-entry-refused',
        'station-list', 'station-focused', 'station-branch', 'request-form']
    keys = [event[1] for event in result['events'] if event[0] == 'key']
    assert keys == ['ret', 'esc', 'ret']
    assert not any(event[0] == 'secret' for event in result['events'])
    assert result['events'][-3:] == [
        ['disable'], ['power', 'off'], ['stage', 'shutdown']]


@pytest.mark.parametrize('destination', ['greeter-controls', '', 'desktop'])
def test_station_worker_never_activates_an_unresolved_session_choice(destination):
    result = json.loads(run_perl(RUN, destination).stdout)
    assert not result['ok']
    assert [event[1] for event in result['events'] if event[0] == 'key'] == ['ret', 'esc', 'ret']
    assert result['events'][-1] == ['exchange', 'station-branch']


def test_station_default_branch_requires_owned_window_and_form_ids():
    ui, _ = request_form()
    ui.branch_owner = 'station'
    assert ui.run('station-entry-branch', '')['branch'] == {
        'destination': 'default-request-form', 'controls': []}
    ui.find_id('kiosk-request-form').identity = ''
    with pytest.raises(UiError, match='station-default-destination'):
        ui.run('station-entry-branch', '')


@pytest.mark.parametrize('fault', [
    None, 'wrong-session', 'duplicate-window', 'duplicate-form',
    'hidden-window', 'hidden-form', 'stale',
])
def test_station_default_entry_requires_one_fresh_owned_destination(fault):
    ui, _ = request_form()
    ui.branch_owner = 'greeter' if fault == 'wrong-session' else 'station'
    desktop = ui.api.get_desktop(0)
    window = ui.find_id('kiosk-request-window')
    form = ui.find_id('kiosk-request-form')
    if fault == 'duplicate-window':
        desktop.children.append(Node(identity='kiosk-request-window'))
    elif fault == 'duplicate-form':
        form.parent.children.append(Node(identity='kiosk-request-form'))
    elif fault == 'hidden-window':
        window.states.discard('showing')
    elif fault == 'hidden-form':
        form.states.discard('showing')
    elif fault == 'stale':
        form.states.add('defunct')
    if fault:
        with pytest.raises(UiError):
            ui.run('station-default-entry', '')
    else:
        assert ui.run('station-default-entry', '')['entry'] == {
            'destination': 'default-request-form'}


@pytest.mark.parametrize('destination', [
    'greeter-controls', 'desktop', '', None,
])
def test_station_default_entry_transport_rejects_every_unsupported_branch(destination):
    from types import SimpleNamespace
    from unittest.mock import Mock
    from ui_observations import UiObservations

    result = {'operation': 'station-default-entry', 'outcome': 'passed',
              'interface': 'AT-SPI', 'entry': {'destination': destination}}
    transport = SimpleNamespace(call=Mock(return_value=json.dumps(result).encode()))
    with pytest.raises(EvidenceError, match='ui:station-default-entry'):
        UiObservations(transport).observe('station-default-entry')


def test_station_default_entry_transport_accepts_only_the_bound_default():
    from types import SimpleNamespace
    from unittest.mock import Mock
    from ui_observations import UiObservations

    result = {'operation': 'station-default-entry', 'outcome': 'passed',
              'interface': 'AT-SPI',
              'entry': {'destination': 'default-request-form'}}
    transport = SimpleNamespace(call=Mock(return_value=json.dumps(result).encode()))
    assert UiObservations(transport).observe('station-default-entry') == result


@pytest.mark.parametrize('fault', [None, 'unknown-destination', 'extra', 'unresolved-default', 'private-label', 'invalid-state'])
def test_station_branch_transport_only_accepts_bounded_sanitized_evidence(fault):
    from types import SimpleNamespace
    from unittest.mock import Mock
    from ui_observations import UiObservations

    control = {'label': 'session-chooser', 'role': 'push button',
               'public_id_present': False, 'sensitive': True, 'focused': False}
    branch = {'destination': 'greeter-controls', 'controls': [control]}
    result = {'operation': 'station-entry-branch', 'outcome': 'passed',
              'interface': 'AT-SPI', 'branch': branch}
    if fault == 'unknown-destination':
        branch['destination'] = 'desktop'
    elif fault == 'extra':
        branch['extra'] = 'private'
    elif fault == 'unresolved-default':
        branch['destination'] = 'default-request-form'
    elif fault == 'private-label':
        control['label'] = 'Private unexpected label'
    elif fault == 'invalid-state':
        control['focused'] = 1
    transport = SimpleNamespace(call=Mock(return_value=json.dumps(result).encode()))
    if fault:
        with pytest.raises(EvidenceError):
            UiObservations(transport).observe('station-entry-branch')
    else:
        assert UiObservations(transport).observe('station-entry-branch') == result


@pytest.mark.parametrize('streamed', [True, False])
def test_large_standalone_observer_uses_guarded_stdin_not_one_exec_argument(tmp_path, monkeypatch, streamed):
    from types import SimpleNamespace
    from unittest.mock import Mock
    import ui_observations
    import vm_transport

    source = '# Standalone fixture source\n' + '# padded\n' * 40000
    source_path = tmp_path / 'tests/e2e/accessible_ui.py'
    source_path.parent.mkdir(parents=True)
    source_path.write_text(source)
    data = tmp_path / 'data'
    data.mkdir()
    (data / 'app.json').write_text('{"version": "1.1"}')
    monkeypatch.setattr(ui_observations.system, 'ROOT', tmp_path)
    result = {'operation': 'gdm-focused', 'outcome': 'passed', 'interface': 'AT-SPI'}
    raw = json.dumps(result).encode()

    def call(argv, **kwargs):
        assert argv == ['/usr/bin/python3', '-I', '-', 'gdm-focused', '1.1']
        assert kwargs['input'] == source.encode()
        assert len(kwargs['input']) > 128 * 1024
        config = {'directory': str(tmp_path), 'run': 'a' * 32, 'domain_uuid': 'b' * 32}
        assert len(vm_transport.remote(config, argv).encode()) < 4096
        if streamed:
            kwargs['on_output'](raw + b'\n')
        return raw

    transport = SimpleNamespace(call=Mock(side_effect=call), commands=SimpleNamespace(progress=None))
    assert ui_observations.UiObservations(
        transport, system_prompt=Mock() if streamed else None).observe('gdm-focused') == result
    transport.call.assert_called_once()


@pytest.mark.parametrize('fault', [None, 'wrong-owner', 'duplicate', 'password', 'wrong-recipient', 'stale'])
def test_station_branch_observes_public_controls_without_action_or_private_labels(fault):
    chooser = Node('Select Session', 'push button')
    choice = Node('Oh No! Parent Control', 'radio menu item')
    private = Node('Private unexpected text', 'push button')
    recipient = Node('oh-no-parent-control', 'label')
    ui = station_greeter(chooser, choice, private, recipient)
    ui.branch_owner = 'greeter'
    app = ui.api.get_desktop(0).children[0]
    if fault == 'wrong-owner':
        app.name = 'Other application'
    elif fault == 'duplicate':
        app.children.append(Node('Select Session', 'push button'))
    elif fault == 'password':
        app.children.append(Node('Password', 'password text'))
    elif fault == 'wrong-recipient':
        recipient.name = 'Jamie (Parent)'
    elif fault == 'stale':
        choice.states.add('defunct')
    if fault:
        with pytest.raises(UiError):
            ui.run('station-entry-branch', '')
    else:
        branch = ui.run('station-entry-branch', '')['branch']
        assert branch['destination'] == 'greeter-controls'
        assert {control['label'] for control in branch['controls']} == {'session-chooser', 'station', 'unresolved'}
        assert 'Private' not in json.dumps(branch)
    for control in (chooser, choice, private):
        control.action.do_action.assert_not_called()
        control.component.grab_focus.assert_not_called()


@pytest.mark.parametrize('owner', ['greeter', 'station', 'other', 'duplicate'])
def test_station_branch_connection_rejects_wrong_or_ambiguous_active_owner(monkeypatch, owner):
    from types import SimpleNamespace
    import accessible_ui

    def call(argv, **_kwargs):
        if argv[1] == 'list-sessions':
            return SimpleNamespace(stdout='c1\nc2\n' if owner == 'duplicate' else 'c1\n')
        kind = 'greeter' if owner == 'greeter' else 'user'
        uid = 61234 if owner == 'greeter' else 1000 if owner == 'other' else 1234
        return SimpleNamespace(stdout=f'Class={kind}\nActive=yes\nRemote=no\nType=wayland\nSeat=seat0\nUser={uid}')
    monkeypatch.setattr(accessible_ui.subprocess, 'run', call)
    monkeypatch.setattr(accessible_ui.pwd, 'getpwnam', lambda _: SimpleNamespace(pw_uid=1234))
    monkeypatch.setattr(accessible_ui.pwd, 'getpwuid', lambda uid: SimpleNamespace(pw_uid=uid))
    if owner in ('other', 'duplicate'):
        with pytest.raises(UiError):
            accessible_ui.greeter_account(station_branch=True)
    else:
        account, observed = accessible_ui.greeter_account(station_branch=True)
        assert observed == owner
        assert account.pw_uid == (61234 if owner == 'greeter' else 1234)
