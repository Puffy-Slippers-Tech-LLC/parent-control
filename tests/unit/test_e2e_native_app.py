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
            'operation': 'native-command-launch', 'outcome': 'passed', 'interface': 'AT-SPI'}
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


@pytest.mark.parametrize('fault', ['', 'logout', 'command', 'opened', 'submit', 'submitted', 'close'])
def test_actual_worker_order_markers_and_no_later_input_after_failure(fault, tmp_path):
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
sub send_key { die 'command qualifier must not type a launch' }
sub type_string { die 'command qualifier must not type a command' }
package main;
require onpc_app_rows;
no warnings 'redefine';
*onpc_parent::sign_in = sub {
    my ($journey, $account) = @_;
    push @events, ['account', $account];
    $journey->seen('installed-greeter');
    $journey->seen($_) for ($account eq 'parent'
        ? qw(parent-focused recipient-qualified recipient-rechecked)
        : qw(standard-focused standard-recipient-qualified standard-recipient-rechecked));
    return $journey->seen('desktop');
};
*onpc_journey::finish = sub { push @events, ['finish'] };
my $ok = eval {
    onpc_app_rows::native_app(sub {
        my ($stage) = @_;
        push @events, ['seen', $stage];
        die 'refused' if $fault ne '' && $stage eq ($fault eq 'logout' ? 'logout' : 'first-' . $fault);
        return {};
    }); 1;
};
print encode_json({ok => $ok ? 1 : 0, error => $@, events => \@events});
''', fault).stdout)
    events = result['events']
    assert bool(result['ok']) == (not fault), result['error']
    if fault:
        assert ['finish'] not in events
        assert not any(event[0] == 'seen' and event[1].startswith('repeat-') for event in events)
        if fault == 'command':
            assert ['seen', 'first-opened'] not in events
        if fault == 'logout':
            assert ['account', 'other-child'] not in events
    else:
        assert [event[1] for event in events if event[0] == 'seen'] == list(PLAN.screen_tags)
        assert [event[1] for event in events if event[0] == 'account'] == ['parent', 'other-child']
        assert events[-1] == ['finish']
        details = [{'title': event[1], 'result': 'ok'}
                   for event in events if event[0] == 'marker']
        observations = [{'stage': stage, 'ui' if tag.startswith('ui:') else 'system': {
            'operation': tag[3:] if tag.startswith('ui:') else tag[7:],
            'outcome': 'passed', 'interface': 'AT-SPI' if tag.startswith('ui:') else 'system session'}}
            for stage, tag in PLAN.screen_tags.items()]
        results = tmp_path / 'testresults'
        results.mkdir()
        evidence = results / 'result-smoke.json'
        evidence.write_text(json.dumps({'result': 'ok', 'details': details}))
        assert [item['stage'] for item in matched_screens(tmp_path, PLAN, observations)] == list(PLAN.screen_tags)
        for invalid in (details[:-1], details + [details[-1]],
                        [details[1], details[0], *details[2:]]):
            evidence.write_text(json.dumps({'result': 'ok', 'details': invalid}))
            with pytest.raises(EvidenceError):
                matched_screens(tmp_path, PLAN, observations)
