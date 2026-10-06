"""Native command session/input guards and actual worker/recorder composition.

Parallelism: process-local doubles, private pytest evidence and bounded, waited
Perl children. No live display, VM, bus, shared path or cache.
"""
import json
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

import accessible_ui
from accessible_ui import UiError
import check_e2e_native_app as check
import check_graphical_smoke as smoke
from native_app import PLAN, NativeAppJourney
from installed_journey import matched_screens
from owned_commands import CommandError
from parent_setup_qualification import KioskEntryQualification, NativeAppQualification
from private_artifacts import EvidenceError
from tests.support.accessible_ui import Node, ui_for
from tests.support.perl import run_perl
from ui_observations import OPERATION_LABELS


@pytest.mark.parametrize('fault', [None, 'session', 'desktop', 'window', 'prompt',
                                 'instance', 'uncertain', 'submission'])
def test_command_requires_child_desktop_and_never_replays(monkeypatch, fault):
    ui = ui_for(Node())
    monkeypatch.setattr(accessible_ui, 'require_active_launch_session',
                        Mock(side_effect=UiError('session') if fault == 'session' else None))
    ui.desktop_result = Mock(side_effect=UiError('desktop') if fault == 'desktop' else None)
    ui.native_app_closed = Mock(return_value=fault != 'window')
    ui.handle_system_prompt = Mock(side_effect=UiError('prompt') if fault == 'prompt' else None)
    ui.input_uncertain = fault == 'uncertain'
    submit = Mock(side_effect=TimeoutError() if fault == 'submission' else None)
    monkeypatch.setattr(accessible_ui.subprocess, 'run', submit)
    instance = 'secondary' if fault == 'instance' else 'primary'
    if fault:
        with pytest.raises((UiError, TimeoutError)):
            ui.native_launch_command(instance)
    else:
        # Actual registered operation, including its sanitized input-only reply.
        assert ui.run('native-command-launch', '') == {
            'operation': 'native-command-launch', 'outcome': 'passed', 'interface': 'ApplicationUI+external-provider'}
    if fault in (None, 'submission'):
        submit.assert_called_once_with([
            '/usr/bin/systemd-run', '--user', '--quiet', '--collect', '--service-type=exec',
            '/opt/onpc-test-fixtures/Applications/Exact Fixture.AppImage',
        ], stdin=accessible_ui.subprocess.DEVNULL, capture_output=True, check=True, timeout=15)
        with pytest.raises(UiError, match='uncertain-input'):
            ui.native_launch_command()
        assert submit.call_count == 1
    else:
        submit.assert_not_called()
    if fault not in ('instance', 'uncertain', 'session'):
        ui.desktop_result.assert_called_once_with(accessible_ui.EXISTING_CHILD, 'success')


@pytest.mark.parametrize('child', [accessible_ui.EXISTING_CHILD, accessible_ui.CHILD])
@pytest.mark.parametrize('failure', ['query', 'incomplete', 'persistent', 'window', 'submission'])
def test_launch_reacquires_complete_preflight_without_replaying_input(monkeypatch, child, failure):
    ui = ui_for(Node())
    ui.timeout = 1
    ui.query_errors = (LookupError,)
    monkeypatch.setattr(accessible_ui.time, 'sleep', lambda _seconds: None)
    # Two possible observations, then the original deadline expires.
    monkeypatch.setattr(accessible_ui.time, 'monotonic', Mock(side_effect=[0, .5, 1]))
    session = Mock()
    monkeypatch.setattr(accessible_ui, 'require_active_launch_session', session)
    ui.require_child_overlay_session = Mock()
    ui.desktop_result = Mock()
    ui.handle_system_prompt = Mock()
    first = UiError('ui:incomplete-tree') if failure == 'incomplete' else LookupError()
    second = LookupError() if failure == 'persistent' else failure != 'window'
    ui.native_app_closed = Mock(side_effect=[first, second])
    submit = Mock(side_effect=TimeoutError() if failure == 'submission' else None)
    monkeypatch.setattr(accessible_ui.subprocess, 'run', submit)

    if failure in ('persistent', 'window', 'submission'):
        expected = {'persistent': 'ui:timeout:native-launch-ready',
                    'window': 'ui:native-window-exists', 'submission': '^$'}[failure]
        with pytest.raises((UiError, TimeoutError), match=expected):
            ui.native_launch_command(child=child)
    else:
        ui.native_launch_command(child=child)

    assert session.call_count == ui.desktop_result.call_count == ui.native_app_closed.call_count == 2
    assert ui.require_child_overlay_session.call_count == (2 if child == accessible_ui.CHILD else 0)
    assert submit.call_count == (0 if failure in ('persistent', 'window') else 1)
    assert ui.input_uncertain == (submit.call_count == 1)
    if submit.call_count:
        with pytest.raises(UiError, match='uncertain-input'):
            ui.native_launch_command(child=child)
        assert submit.call_count == 1


def test_live_refusal_operation_preserves_desktop_without_submitting(monkeypatch):
    ui = ui_for(Node())
    ui.native_app_closed = Mock(return_value=True)
    submit = Mock()
    monkeypatch.setattr(accessible_ui.subprocess, 'run', submit)
    ui.native_app_operation('native-command-refusals')
    submit.assert_not_called()
    assert ui.input_uncertain is False
    assert ui.native_app_closed.call_count == 2


def test_registration_fixture_lifetime_and_exclusive_slice(monkeypatch):
    assert issubclass(NativeAppQualification, KioskEntryQualification)
    context = SimpleNamespace()
    journey = NativeAppQualification.journey(context, Mock())
    assert isinstance(journey, NativeAppJourney)
    assert context.installed_snapshot.startswith('onpc-v')
    assert set(journey.actions) == {'native-refuse', 'native-verify'}
    assert PLAN.stage_actions == {'installed-greeter': 'native-refuse', 'desktop': 'native-verify'}
    assert {tag[3:] for tag in PLAN.screen_tags.values() if tag.startswith('ui:')} <= accessible_ui.OPERATIONS
    assert accessible_ui.NATIVE_APP_OPERATIONS <= accessible_ui.STANDARD_OPERATIONS
    assert accessible_ui.NATIVE_APP_OPERATIONS <= OPERATION_LABELS.keys()
    assets = object()
    monkeypatch.setattr(check, 'named_input', Mock(return_value=assets))
    calls = []
    monkeypatch.setattr(check, 'smoke', lambda **kwargs: calls.append(kwargs) or 0)
    assert check.main() == 0
    check.named_input.assert_called_once_with(fixture_source=True)
    assert calls == [{'assets': assets, 'provision_credentials': True, 'native_app': True}]
    for changes in ({}, {'assets': assets, 'provision_credentials': True, 'native_grid_usable': True}):
        with pytest.raises(CommandError, match='smoke:native-app-prerequisites'):
            smoke.main(native_app=True, **changes)


@pytest.mark.parametrize('fault', ['', 'logout', 'command', 'opened', 'submit', 'submitted', 'close',
                                 'child-standard-recipient-qualified',
                                 'child-standard-recipient-rechecked', 'typing', 'challenge-role'])
def test_actual_worker_order_markers_and_no_later_input_after_failure(fault, tmp_path):
    result = json.loads(run_perl(r'''
use strict;
use warnings;
use JSON::PP;
our @events;
our $fault = shift @ARGV;
our $challenges = decode_json(shift @ARGV);
our $declared = decode_json(shift @ARGV);
BEGIN { $INC{'testapi.pm'} = 1; }
package testapi;
sub record_info { push @main::events, ['marker', $_[0]] }
sub current_console { 'sut' }
sub get_var { '1' }
sub get_required_var { 'synthetic-fixture-secret' }
sub type_password {
    push @main::events, ['password'];
    die 'synthetic-fixture-secret' if $main::fault eq 'typing';
}
sub send_key { die 'unexpected key' unless $_[0] eq 'ret'; push @main::events, ['key', $_[0]] }
sub type_string { die 'command qualifier must not type a command' }
package main;
require onpc_app_rows;
no warnings 'redefine';
*onpc_gdm::reattach_functional = sub { };
*onpc_journey::finish = sub { push @events, ['finish'] };
my $ok = eval {
    onpc_app_rows::native_app(sub {
        my ($stage) = @_;
        push @events, ['seen', $stage];
        die 'refused' if $fault ne '' && $stage eq (
            $fault eq 'logout' || $fault =~ /^child-/ ? $fault : 'first-' . $fault);
        my $reply = {observed => $stage, ($stage =~ /greeter$/ ? (ui_focused => JSON::PP::true) : ())};
        for my $id (keys %$challenges) {
            my ($role, $first, $second) = @{$challenges->{$id}};
            if ($stage eq $first || $stage eq $second) {
                $reply->{challenge} = {id => $id, role => $role, surface => 'gdm',
                    check => $stage eq $first ? 'qualified' : 'rechecked'};
                $reply->{challenge}{role} = 'parent' if $fault eq 'challenge-role'
                    && $id eq 'native-child-login';
                push @events, ['challenge', $stage, $reply->{challenge}];
            }
        }
        return $reply;
    }, $declared, $challenges); 1;
};
print encode_json({ok => $ok ? 1 : 0, error => $@, events => \@events});
''', fault, json.dumps(PLAN.challenges), json.dumps(PLAN.invocations)).stdout)
    events = result['events']
    assert bool(result['ok']) == (not fault), result['error']
    assert 'synthetic-fixture-secret' not in result['error']
    if fault:
        assert ['finish'] not in events
        assert not any(event[0] == 'seen' and event[1].startswith('repeat-') for event in events)
        if fault == 'command':
            assert ['seen', 'first-opened'] not in events
        if fault == 'logout':
            assert ['seen', 'child-installed-greeter'] not in events
        if fault.startswith('child-') or fault == 'challenge-role':
            assert sum(event[0] == 'password' for event in events) == 1
            assert ['seen', 'first-command'] not in events
    else:
        assert [event[1] for event in events if event[0] == 'seen'] == list(PLAN.screen_tags)
        assert sum(event[0] == 'password' for event in events) == 2
        assert events[-1] == ['finish']
        details = [{'title': event[1], 'result': 'ok'}
                   for event in events if event[0] == 'marker']
        observations = [{'stage': stage, 'ui' if tag.startswith('ui:') else 'system': {
            'operation': tag[3:] if tag.startswith('ui:') else tag[7:],
            'outcome': 'passed', 'interface': 'ApplicationUI+external-provider' if tag.startswith('ui:') else 'system session'}}
            for stage, tag in PLAN.screen_tags.items()]
        proofs = {event[1]: event[2] for event in events if event[0] == 'challenge'}
        for observation in observations:
            if observation['stage'] in proofs:
                observation['challenge'] = proofs[observation['stage']]
        results = tmp_path / 'testresults'
        results.mkdir()
        evidence = results / 'result-smoke.json'
        evidence.write_text(json.dumps({'result': 'ok', 'details': details}))
        assert [item['stage'] for item in matched_screens(tmp_path, PLAN, observations)] == list(PLAN.screen_tags)
        for invalid_proof in (None, {**proofs['child-standard-recipient-rechecked'],
                                    'id': 'parent-login'}):
            invalid_observations = [
                {**item, 'challenge': invalid_proof}
                if item['stage'] == 'child-standard-recipient-rechecked' else item
                for item in observations]
            with pytest.raises(EvidenceError, match='challenge-evidence'):
                matched_screens(tmp_path, PLAN, invalid_observations)
        for invalid in (details[:-1], details + [details[-1]],
                        [details[1], details[0], *details[2:]]):
            evidence.write_text(json.dumps({'result': 'ok', 'details': invalid}))
            with pytest.raises(EvidenceError):
                matched_screens(tmp_path, PLAN, observations)
