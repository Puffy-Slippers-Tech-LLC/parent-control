"""Public request-station entry and immutable form observation contracts."""

import json
from dataclasses import FrozenInstanceError
from pathlib import Path

import pytest

from accessible_ui import PRODUCT, UiError
from private_artifacts import EvidenceError
from tests.support.accessible_ui import Node, ui_for
from tests.support.paths import ROOT
from tests.support.perl import run_perl
from ui_observations import RequestObservation
from installed_journey import InstalledJourney


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
    )
    approver = Node(
        'Approving parent', 'push button', states=('showing', 'visible'),
        identity='kiosk-approver-selector',
        description='Selected approving parent: Casey (Parent).',
    )
    durations = []
    duration_values = (300, 900, 1800, 3600, 7200, 14400, 0, 'custom')
    for label, value in zip(
            ('5 minutes', '15 minutes', '30 minutes', '1 hour', '2 hours',
             '4 hours', 'Rest of the day', 'Custom value'), duration_values):
        states = ['showing', 'visible']
        if label == '30 minutes':
            states.append('checked')
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
        durations[2].states.remove('checked')
        durations[1].states.add('checked')
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
    return ui_for(Node(
        PRODUCT, 'frame', children=children, identity='kiosk-request-form',
    )), tuple(durations)


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


@pytest.mark.parametrize('role', ['window', 'dialog'])
def test_station_form_accepts_public_window_roles_with_the_same_required_contents(role):
    ui, _ = request_form()
    ui.api.get_desktop(0).role = role
    RequestObservation.from_request(ui.run('kiosk-request-form', '')['request'])


def test_station_form_targets_controls_only_by_public_id():
    ui, _ = request_form()
    for node in ui.api.get_desktop(0).children:
        if node.identity and node.identity != 'kiosk-screen-limit-notice':
            node.name = 'Changed visual label'
            node.role = 'changed-role'
    observation = RequestObservation.from_request(
        ui.run('kiosk-request-form', '')['request'])
    assert observation.child == 'existing-fixture-child'
    assert observation.duration_seconds == 1800


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
    'wrong-duration', 'request-enabled', 'custom-visible', 'missing-message',
    'mute-present', 'duplicate-form',
])
def test_kiosk_request_form_refuses_changed_or_ambiguous_state(fault):
    ui, _ = request_form(fault=fault)
    ui.timeout = 0
    with pytest.raises((UiError, EvidenceError)):
        RequestObservation.from_request(ui.run('kiosk-request-form', '')['request'])


def test_station_greeter_navigation_and_wrong_entry_are_independent():
    station = Node('oh-no-parent-control', 'push button', states=('visible', 'sensitive'))
    parent = Node('Jamie (Parent)', 'push button')
    ui = ui_for(Node(children=[parent, station]))
    assert ui.run('gdm-station-list', '')['navigation'] == ['home', 'down']
    station.states.add('showing')
    with pytest.raises(UiError, match='gdm-account-focus'):
        ui.run('gdm-station-focused', '')
    station.states.add('focused')
    assert ui.run('gdm-station-focused', '')['outcome'] == 'passed'

    field = Node('Password', 'password text',
                 states=('showing', 'visible', 'sensitive', 'focused'))
    field.get_text_iface = lambda: (_ for _ in ()).throw(AssertionError('password read'))
    prompt = ui_for(Node(children=[Node('Jamie (Parent)', 'label'), field]))
    assert prompt.run('gdm-station-wrong-entry-refused', '')['outcome'] == 'passed'


def test_station_display_name_and_username_on_one_row_are_one_target():
    station = Node('Oh No! Parent Control', 'push button',
                   children=[Node('oh-no-parent-control', 'label')],
                   states=('showing', 'visible', 'sensitive', 'focused'))
    ui = ui_for(Node(children=[station]))
    assert ui.run('gdm-station-focused', '')['outcome'] == 'passed'


def test_unnamed_station_row_with_display_name_and_username_labels_is_one_target():
    station = Node('', 'push button',
                   children=[Node('Oh No! Parent Control', 'label'),
                             Node('oh-no-parent-control', 'label')],
                   states=('showing', 'visible', 'sensitive', 'focused'))
    ui = ui_for(Node(children=[station]))
    assert ui.run('gdm-station-focused', '')['outcome'] == 'passed'


RUN = r'''
use strict;
use warnings;
use JSON::PP;
our @events;
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
        return {ui_keys => ['home', 'down']} if $stage eq 'station-list';
        return {ui_keys => ['home']} if $stage eq 'installed-greeter';
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
        'station-list', 'station-focused', 'request-form']
    keys = [event[1] for event in result['events'] if event[0] == 'key']
    assert keys == ['home', 'ret', 'esc', 'home', 'down', 'ret']
    assert not any(event[0] == 'secret' for event in result['events'])
    assert result['events'][-1] == ['power', 'off']
