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


@pytest.mark.parametrize('returncode,stderr,stdout,out_markers,err_markers', [
    (0, b'private output', b'', [], []),
    (203, b'', b'', [], []),
    (203, b'', b'Permission denied: private path', ['permission-denied'], []),
    (126, b'Permission denied: private path', b'', [], ['permission-denied']),
    (1, b'No such file or directory: private path', b'', [], ['missing-file']),
    (1, b'Failed to connect to bus: private address', b'', [], ['bus-unavailable']),
    (203, b'Permission denied: private path', b'x' * 65538, [], ['permission-denied']),
])
def test_blocked_launch_failure_retains_private_safe_result_without_replay(
        monkeypatch, returncode, stderr, stdout, out_markers, err_markers):
    ui = ui_for(Node())
    monkeypatch.setattr(accessible_ui, 'require_active_launch_session', Mock())
    ui.require_child_overlay_session = Mock()
    ui.desktop_result = Mock()
    ui.handle_system_prompt = Mock()
    ui.native_app_closed = Mock(return_value=True)
    ui.wait = lambda predicate, *_args, **_kwargs: predicate()
    submit = Mock(return_value=SimpleNamespace(
        returncode=returncode, stdout=stdout, stderr=stderr))
    monkeypatch.setattr(accessible_ui.subprocess, 'run', submit)
    journal = Mock(return_value={'status': 'read', 'entries': 0, 'exec_errors': []})
    monkeypatch.setattr(accessible_ui, 'native_execution_journal_diagnostic', journal)

    with pytest.raises(UiError, match='^ui:native-execution-denial$') as caught:
        ui.native_launch_command(child=accessible_ui.CHILD, blocked=True)
    diagnostic = accessible_ui.adapter_failure_diagnostic(caught.value)
    assert diagnostic['native_execution_result'] == {
        'returncode': returncode, 'stdout_bytes': min(len(stdout), 65537),
        'stderr_bytes': len(stderr), 'stdout_markers': out_markers,
        'stderr_markers': err_markers,
    }
    assert 'private' not in json.dumps(diagnostic)
    assert diagnostic['native_execution_journal'] == journal.return_value
    journal.assert_called_once()
    unit = journal.call_args.args[0]
    assert '--unit=' + unit in submit.call_args.args[0]
    assert ui.native_app_closed.call_count == 1  # No post-failure observation/input.
    ui.desktop_result.assert_called_once_with(accessible_ui.CHILD, 'success')
    ui.require_child_overlay_session.assert_called_once_with()
    assert ui.input_uncertain
    with pytest.raises(UiError, match='uncertain-input'):
        ui.native_launch_command(child=accessible_ui.CHILD, blocked=True)
    assert submit.call_count == 1


@pytest.mark.parametrize('errno,expected', [
    ('1', 'operation-not-permitted'), ('2', 'missing-file'),
    ('8', 'invalid-executable'), ('13', 'permission-denied'),
    ('20', 'invalid-directory'), ('private value', 'other'),
    (['13'], 'other'), (None, 'other'),
])
def test_native_journal_binds_one_launch_and_exports_only_closed_errors(monkeypatch, errno, expected):
    unit = 'onpc-test-native-' + 'a' * 32 + '.service'
    entry = {'USER_UNIT': unit, 'ERRNO': errno,
             'EXECUTABLE': '/opt/onpc-test-fixtures/Applications/Exact Fixture.AppImage',
             'MESSAGE': unit + ': Failed at step EXEC spawning '
                        '/opt/onpc-test-fixtures/Applications/Exact Fixture.AppImage: private error',
             'private-field': 'private value'}
    entries = [entry, {**entry, 'USER_UNIT': 'other.service'},
               {**entry, 'EXECUTABLE': '/private/other'},
               {**entry, 'MESSAGE': unit + ': Failed at step CHDIR spawning '
                                   '/opt/onpc-test-fixtures/Applications/Exact Fixture.AppImage: private error'}]
    read = Mock(return_value=SimpleNamespace(
        stdout=b'\n'.join(json.dumps(value).encode() for value in entries), stderr=b''))
    monkeypatch.setattr(accessible_ui.subprocess, 'run', read)
    result = accessible_ui.native_execution_journal_diagnostic(unit)
    assert result == {'status': 'read', 'entries': 4, 'exec_errors': [expected]}
    read.assert_called_once_with([
        '/usr/bin/journalctl', '--user', '--boot', '--unit=' + unit,
        '--lines=16', '--output=json', '--no-pager', '--quiet',
    ], stdin=accessible_ui.subprocess.DEVNULL, capture_output=True, check=True, timeout=5)
    assert 'private' not in json.dumps(result)


@pytest.mark.parametrize('changed', [
    {'USER_UNIT': 'other.service'},
    {'USER_UNIT': None},
    {'EXECUTABLE': '/private/other'},
    {'EXECUTABLE': None},
    {'MESSAGE': 'Failed at step EXEC spawning '
                '/opt/onpc-test-fixtures/Applications/Exact Fixture.AppImage: private error'},
    {'MESSAGE': 'other.service: Failed at step EXEC spawning '
                '/opt/onpc-test-fixtures/Applications/Exact Fixture.AppImage: private error'},
    {'MESSAGE': 'onpc-test-native-' + 'a' * 32 + '.service: Failed at step EXEC spawning '
                '/private/other: private error'},
    {'MESSAGE': None},
    {'MESSAGE': ['private error']},
])
def test_native_journal_rejects_unattributed_permission_errors(monkeypatch, changed):
    unit = 'onpc-test-native-' + 'a' * 32 + '.service'
    entry = {'USER_UNIT': unit, 'ERRNO': '13',
             'EXECUTABLE': '/opt/onpc-test-fixtures/Applications/Exact Fixture.AppImage',
             'MESSAGE': unit + ': Failed at step EXEC spawning '
                        '/opt/onpc-test-fixtures/Applications/Exact Fixture.AppImage: private error',
             **changed}
    read = Mock(return_value=SimpleNamespace(stdout=json.dumps(entry).encode(), stderr=b''))
    monkeypatch.setattr(accessible_ui.subprocess, 'run', read)
    assert accessible_ui.native_execution_journal_diagnostic(unit) == {
        'status': 'read', 'entries': 1, 'exec_errors': []}
    assert read.call_count == 1


@pytest.mark.parametrize('errno,window,expected_error', [
    ('13', False, None), ('1', False, None),
    ('13', True, 'ui:native-blocked-window'),
    ('2', False, 'ui:native-execution-denial'),
    ('8', False, 'ui:native-execution-denial'),
    ('20', False, 'ui:native-execution-denial'),
    (None, False, 'ui:native-execution-denial'),
])
def test_blocked_launch_reads_executor_error_and_still_requires_no_window(
        monkeypatch, errno, window, expected_error):
    ui = ui_for(Node())
    ui.timing = Mock()
    monkeypatch.setattr(accessible_ui, 'require_active_launch_session', Mock())
    ui.require_child_overlay_session = Mock()
    ui.desktop_result = Mock()
    ui.handle_system_prompt = Mock()
    ui.native_app_closed = Mock(side_effect=[True, not window, not window])
    monkeypatch.setattr(accessible_ui.time, 'monotonic', Mock(side_effect=[0, 1, 2]))

    def wait(predicate, *_args, **_kwargs):
        if not predicate():
            assert predicate()
    ui.wait = wait

    def execute(argv, **_kwargs):
        if argv[0] == '/usr/bin/systemd-run':
            return SimpleNamespace(returncode=203, stdout=b'', stderr=b'')
        assert argv[0] == '/usr/bin/journalctl'
        unit = next(arg.removeprefix('--unit=') for arg in argv if arg.startswith('--unit='))
        entry = {'USER_UNIT': unit, 'ERRNO': errno,
                 'EXECUTABLE': '/opt/onpc-test-fixtures/Applications/Exact Fixture.AppImage',
                 'MESSAGE': unit + ': Failed at step EXEC spawning '
                            '/opt/onpc-test-fixtures/Applications/Exact Fixture.AppImage: private error'}
        return SimpleNamespace(stdout=json.dumps(entry).encode(), stderr=b'')
    run = Mock(side_effect=execute)
    monkeypatch.setattr(accessible_ui.subprocess, 'run', run)

    if expected_error:
        with pytest.raises(UiError, match='^' + expected_error + '$'):
            ui.native_launch_command(child=accessible_ui.CHILD, blocked=True)
    else:
        ui.native_launch_command(child=accessible_ui.CHILD, blocked=True)
    if expected_error:
        ui.timing.assert_not_called()
    else:
        ui.timing.assert_called_once_with({
            'event': 'ui-native-execution-denial', 'source': 'journal',
            'error': 'permission-denied' if errno == '13' else 'operation-not-permitted'})
    assert run.call_count == 2  # One launch, one read; never another launch.
    launch_unit = next(arg for arg in run.call_args_list[0].args[0] if arg.startswith('--unit='))
    assert launch_unit in run.call_args_list[1].args[0]
    assert ui.native_app_closed.call_count == (1 if expected_error == 'ui:native-execution-denial'
                                              else 2 if window else 3)
    assert ui.input_uncertain
    with pytest.raises(UiError, match='uncertain-input'):
        ui.native_launch_command(child=accessible_ui.CHILD, blocked=True)
    assert run.call_count == 2


@pytest.mark.parametrize('returncode,stdout,errors,status', [
    (0, b'', ['permission-denied'], 'read'),
    (1, b'', ['permission-denied'], 'read'),
    (126, b'', ['permission-denied'], 'read'),
    (203, b'x' * 65537, ['permission-denied'], 'read'),
    (203, b'', [], 'read'),
    (203, b'', ['other'], 'read'),
    (203, b'', ['permission-denied', 'missing-file'], 'read'),
    (203, b'', ['permission-denied', 'permission-denied'], 'read'),
    (203, b'', ['permission-denied'], 'unavailable'),
    (203, b'', [], 'invalid'),
    (203, b'', [], 'oversized'),
])
def test_journal_does_not_replace_exit_output_or_unambiguous_denial_guards(
        monkeypatch, returncode, stdout, errors, status):
    ui = ui_for(Node())
    monkeypatch.setattr(accessible_ui, 'require_active_launch_session', Mock())
    ui.desktop_result = Mock()
    ui.handle_system_prompt = Mock()
    ui.native_app_closed = Mock(return_value=True)
    ui.wait = lambda predicate, *_args, **_kwargs: predicate()
    run = Mock(return_value=SimpleNamespace(returncode=returncode, stdout=stdout, stderr=b''))
    monkeypatch.setattr(accessible_ui.subprocess, 'run', run)
    journal = Mock(return_value={'status': status, 'entries': len(errors), 'exec_errors': errors})
    monkeypatch.setattr(accessible_ui, 'native_execution_journal_diagnostic', journal)
    with pytest.raises(UiError, match='^ui:native-execution-denial$'):
        ui.native_launch_command(blocked=True)
    run.assert_called_once()
    journal.assert_called_once()
    assert ui.native_app_closed.call_count == 1


@pytest.mark.parametrize('returncode,stderr', [
    (1, b'Permission denied'), (203, b'Operation not permitted'),
])
def test_stderr_denial_keeps_absence_check_without_journal_read(monkeypatch, returncode, stderr):
    ui = ui_for(Node())
    ui.timing = Mock()
    monkeypatch.setattr(accessible_ui, 'require_active_launch_session', Mock())
    ui.desktop_result = Mock()
    ui.handle_system_prompt = Mock()
    ui.native_app_closed = Mock(return_value=True)
    monkeypatch.setattr(accessible_ui.time, 'monotonic', Mock(side_effect=[0, 2]))
    ui.wait = lambda predicate, *_args, **_kwargs: predicate()
    run = Mock(return_value=SimpleNamespace(returncode=returncode, stdout=b'', stderr=stderr))
    monkeypatch.setattr(accessible_ui.subprocess, 'run', run)
    journal = Mock()
    monkeypatch.setattr(accessible_ui, 'native_execution_journal_diagnostic', journal)
    ui.native_launch_command(blocked=True)
    run.assert_called_once()
    journal.assert_not_called()
    assert ui.native_app_closed.call_count == 2
    ui.timing.assert_called_once_with({
        'event': 'ui-native-execution-denial', 'source': 'stderr',
        'error': 'permission-denied' if returncode == 1 else 'operation-not-permitted'})


@pytest.mark.parametrize('stdout,status', [
    (b'', 'read'), (b'private malformed log', 'invalid'),
    (b'[]', 'invalid'), (b'{}\n' * 17, 'oversized'), (b'x' * 65537, 'oversized'),
])
def test_native_journal_read_is_bounded_and_never_exports_raw_logs(monkeypatch, stdout, status):
    read = Mock(return_value=SimpleNamespace(stdout=stdout, stderr=b''))
    monkeypatch.setattr(accessible_ui.subprocess, 'run', read)
    result = accessible_ui.native_execution_journal_diagnostic(
        'onpc-test-native-' + 'a' * 32 + '.service')
    assert result == {'status': status, 'entries': 0, 'exec_errors': []}
    assert read.call_count == 1


@pytest.mark.parametrize('error', [OSError('private error'),
                                  accessible_ui.subprocess.TimeoutExpired('private command', 5)])
def test_native_journal_reader_failure_does_not_retry(monkeypatch, error):
    read = Mock(side_effect=error)
    monkeypatch.setattr(accessible_ui.subprocess, 'run', read)
    assert accessible_ui.native_execution_journal_diagnostic(
        'onpc-test-native-' + 'a' * 32 + '.service') == {
            'status': 'unavailable', 'entries': 0, 'exec_errors': []}
    assert read.call_count == 1


@pytest.mark.parametrize('invalid', [
    {'private-field': 'private value'}, {'status': 'private value'},
    {'entries': True}, {'entries': 17}, {'exec_errors': ['private value']},
    {'exec_errors': 'private value'}, {'exec_errors': ['permission-denied'] * 2},
])
def test_native_journal_export_refuses_unreviewed_values(invalid):
    error = UiError('ui:native-execution-denial')
    error.native_execution_journal = {
        'status': 'read', 'entries': 1, 'exec_errors': ['permission-denied'], **invalid}
    assert 'native_execution_journal' not in accessible_ui.adapter_failure_diagnostic(error)


def test_native_journal_refuses_unbound_unit_before_reading(monkeypatch):
    read = Mock()
    monkeypatch.setattr(accessible_ui.subprocess, 'run', read)
    assert accessible_ui.native_execution_journal_diagnostic('private unit') == {
        'status': 'unavailable', 'entries': 0, 'exec_errors': []}
    read.assert_not_called()


@pytest.mark.parametrize('invalid', [
    {'private-field': 'private value'},
    {'returncode': 'private code'},
    {'returncode': True},
    {'stdout_bytes': 65538},
    {'stderr_bytes': -1},
    {'stdout_markers': ['private output']},
    {'stderr_markers': ['private output']},
    {'stderr_markers': 'private output'},
])
def test_native_execution_diagnostic_refuses_unreviewed_values(invalid):
    error = UiError('ui:native-execution-denial')
    error.native_execution_result = {
        'returncode': 203, 'stdout_bytes': 0, 'stderr_bytes': 17,
        'stdout_markers': [], 'stderr_markers': ['permission-denied'], **invalid,
    }
    diagnostic = accessible_ui.adapter_failure_diagnostic(error)
    assert 'native_execution_result' not in diagnostic
    assert 'private' not in json.dumps(diagnostic)


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
