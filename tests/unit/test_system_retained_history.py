"""Canonical composition with private receipts and explicit transport/UI doubles."""

from contextlib import contextmanager
import json
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

import system_runner as runner
import system_snapshots
import system_kiosk_ambient_history as ambient
import system_kiosk_required_history as required
from tests.support.modules import load_module


@pytest.mark.parametrize('case,phase,numeric', [
    (runner.RETAINED_AMBIENT_CASE, runner.RETAINED_AMBIENT_PHASE, 293),
    (runner.RETAINED_REQUIRED_CASE, runner.RETAINED_REQUIRED_PHASE, 294)])
def test_exact_registered_history_freezes_complete_closure_and_independent_attempt(tmp_path, case, phase, numeric):
    selection = runner.resolve_selection('enforcement', case)
    assert selection.phases == (phase,)
    assert [item.case_id for item in selection.executions] == [case]
    assert runner.identity_for_case('enforcement', case).numeric_id == numeric
    assert system_snapshots.attempts(selection) == [(selection, True)]
    runner.stage_selected_inputs(selection, tmp_path)
    inputs = json.loads((tmp_path / 'selected-inputs.json').read_bytes())
    sources = {value['source'] for value in inputs['files'].values()}
    for name in ('system_kiosk_ambient_history', 'system_kiosk_required_history', 'system_kiosk_scope',
                 'system_kiosk_confinement', 'system_native_update', 'system_guest',
                 'system_wellbeing_qualification'):
        assert 'tests/integration/' + name + '.py' in sources
    assert inputs['host_files'] == runner.retained_history_host_inputs()
    assert set(runner.KIOSK_ACTIVATION_HOST_INPUTS) <= set(inputs['host_files'])
    assert all(inputs['host_files'][value['source']] == value['sha256'] for value in
               inputs['files'].values() if value['source'] in inputs['host_files'])


@pytest.mark.parametrize('name', ['ambient', 'required'])
@pytest.mark.parametrize('failure', [False, True])
def test_case_dispatch_keeps_actual_verifier_and_failure(monkeypatch, name, failure):
    import sys
    error = RuntimeError('original-history-failure')
    verify = Mock(side_effect=error if failure else None)
    monkeypatch.setitem(sys.modules, 'system_kiosk_' + name + '_history', SimpleNamespace(verify_history=verify))
    module = load_module('private_retained_case_' + name, runner.ROOT / 'tests/system/test_enforcement.py')
    case = getattr(module, 'test_kiosk_retained_' + name + '_history')
    record = Mock()
    if failure:
        with pytest.raises(RuntimeError) as caught:
            case(record)
        assert caught.value is error
    else:
        case(record)
    verify.assert_called_once_with(record)


@pytest.fixture
def composition(tmp_path, monkeypatch):
    import kiosk_entry
    events = []
    lease = SimpleNamespace(state={'run': 'fixture'}, guard=Mock(), save=lambda value: events.append(value))
    inputs = tmp_path / 'input'
    inputs.mkdir()
    (inputs / 'selected-inputs.json').write_text(json.dumps({'host_files': {'fixture': 'a' * 64}}))
    monkeypatch.setattr(runner, 'retained_history_host_inputs', lambda: {'fixture': 'a' * 64})

    def call(arguments, **options):
        assert options['timeout'] in (180, 300)
        if 'collect' in arguments:
            events.append('collect')
        else:
            events.append(tuple(arguments[arguments.index('-B') + 2:]))
        return ''
    vm = SimpleNamespace(call=call, copy=lambda *args: events.append('copy'),
                         reboot=lambda: events.append('reboot'))

    @contextmanager
    def station(vm, lease, *, receipt):
        events.append('entry')
        receipt['station_confirmed'] = True
        try:
            yield receipt
        finally:
            receipt['normal_exit'] = True
            events.append('exit')

    @contextmanager
    def manager(vm, lease, *, receipt, checkpoint):
        events.append('manager-start')
        receipt.update(entries=[], original='actual-original')
        checkpoint(receipt)
        def check():
            events.append('manager-check')
            return 'actual-original'
        @contextmanager
        def visit():
            entry = {}
            receipt['entries'].append(entry)
            with station(vm, lease, receipt=entry):
                yield entry
        try:
            yield SimpleNamespace(station=visit, check=check)
        finally:
            events.append('manager-cleanup')
            receipt['cleanup_complete'] = True
            checkpoint(receipt)

    def refused(vm, lease, verify, *, receipt):
        events.append('public-refusal')
        verify()
        receipt['safe_return'] = True
    monkeypatch.setattr(runner, 'owned_retained_manager', manager)
    monkeypatch.setattr(kiosk_entry, 'native_update_station', station)
    monkeypatch.setattr(kiosk_entry, 'observe_station_refusal', refused)
    monkeypatch.setattr(runner, 'run_pytest', lambda *args: events.append('pytest'))
    return tmp_path, vm, lease, events


def test_ambient_has_separate_entries_one_original_manager_no_reboot_and_owned_cleanup(composition):
    directory, vm, lease, events = composition
    runner.run_retained_phase(vm, lease, directory, None, runner.RETAINED_AMBIENT_PHASE)
    assert events.count('manager-start') == events.count('manager-cleanup') == 1
    assert events.count('entry') == events.count('exit') == len(ambient.STEPS)
    assert 'reboot' not in events
    assert [value[1] for value in events if isinstance(value, tuple) and value[0] == 'observe'] == list(ambient.STEPS)
    assert events.index('manager-cleanup') < events.index(('cleanup',)) < events.index('pytest')
    snapshots = sorted((directory / 'guest-results').glob('retained-ambient-checkpoint-*.json'))
    result = json.loads(snapshots[-1].read_bytes())
    assert result['passed'] and result['host_inputs_unchanged']
    assert result['branches'] == list(ambient.STEPS)
    assert all(path.stat().st_mode & 0o777 == 0o600 for path in snapshots)


def test_each_required_branch_keeps_refusal_restoration_cleanup_reboot_reentry_together(composition):
    directory, vm, lease, events = composition
    runner.run_retained_phase(vm, lease, directory, None, runner.RETAINED_REQUIRED_PHASE)
    assert events.count('manager-start') == events.count('manager-cleanup') == len(required.BRANCHES)
    assert events.count('reboot') == events.count('public-refusal') == len(required.BRANCHES)
    for branch in required.BRANCHES:
        start = events.index(('prepare', branch))
        stop = events.index(('complete', branch))
        segment = events[start:stop]
        assert segment.index(('mutate', branch)) < segment.index(('refusal', branch))
        assert segment.index(('public-refusal', branch)) < segment.index(('cleanup',))
        assert segment.index('manager-cleanup') < segment.index('collect') < segment.index('reboot')
        assert segment.index('reboot') < segment.index('entry')
    assert events[-1] == 'pytest'


def test_changed_frozen_host_inputs_refuse_before_guest_or_public_input(composition, monkeypatch):
    directory, vm, lease, events = composition
    monkeypatch.setattr(runner, 'retained_history_host_inputs', lambda: {'fixture': 'b' * 64})
    with pytest.raises(runner.Error, match='host-inputs-changed'):
        runner.run_retained_phase(vm, lease, directory, None, runner.RETAINED_AMBIENT_PHASE)
    assert not events


def test_ambient_first_failure_survives_failed_recovery_without_another_visit(composition):
    directory, vm, lease, events = composition
    original = vm.call
    error = RuntimeError('original observation')
    def call(arguments, **options):
        result = original(arguments, **options)
        if arguments[-2:] == ['observe', 'empty-added']:
            raise error
        if arguments[-1] == 'cleanup':
            raise RuntimeError('cleanup refusal')
        return result
    vm.call = call
    with pytest.raises(RuntimeError) as caught:
        runner.run_retained_phase(vm, lease, directory, None, runner.RETAINED_AMBIENT_PHASE)
    assert caught.value is error
    assert events.count('entry') == 2 and 'pytest' not in events
    snapshots = sorted((directory / 'guest-results').glob('retained-ambient-checkpoint-*.json'))
    result = json.loads(snapshots[-1].read_bytes())
    assert 'original observation' in result['first_failure']
    assert any('cleanup refusal' in value for value in result['cleanup_failures'])


def test_original_failure_survives_final_source_reader_failure(composition, monkeypatch):
    directory, vm, lease, events = composition
    original = vm.call
    error = RuntimeError('original observation')
    def call(arguments, **options):
        result = original(arguments, **options)
        if arguments[-2:] == ['observe', 'initial']:
            def fail():
                raise ValueError('source replaced')
            monkeypatch.setattr(runner, 'retained_history_host_inputs', fail)
            raise error
        return result
    vm.call = call
    with pytest.raises(RuntimeError) as caught:
        runner.run_retained_phase(vm, lease, directory, None, runner.RETAINED_AMBIENT_PHASE)
    assert caught.value is error
    assert any('checkpoint-failed' in note for note in error.__notes__)
    snapshots = sorted((directory / 'guest-results').glob('retained-ambient-checkpoint-*.json'))
    result = json.loads(snapshots[-1].read_bytes())
    assert 'original observation' in result['first_failure']
    assert any('source replaced' in value for value in result['cleanup_failures'])


@pytest.mark.parametrize('cut', ['prepare', 'mutate', 'refusal', 'public-refusal',
                                'cleanup', 'collect', 'reboot', 'complete'])
def test_required_failure_keeps_first_error_and_stops_the_history(composition, cut):
    directory, vm, lease, events = composition
    original = vm.call
    error = RuntimeError('required cut ' + cut)

    def call(arguments, **options):
        result = original(arguments, **options)
        if ((cut == 'collect' and 'collect' in arguments) or
                (cut not in ('collect', 'reboot') and
                 (arguments[-2:] == [cut, required.BRANCHES[0]] or
                  cut == 'cleanup' and arguments[-1] == cut))):
            raise error
        return result
    vm.call = call
    if cut == 'reboot':
        def reboot():
            events.append('reboot')
            raise error
        vm.reboot = reboot
    with pytest.raises(RuntimeError) as caught:
        runner.run_retained_phase(vm, lease, directory, None, runner.RETAINED_REQUIRED_PHASE)
    assert caught.value is error
    assert events.count('manager-start') == events.count('manager-cleanup') == 1
    assert ('cleanup',) in events
    assert ('prepare', required.BRANCHES[1]) not in events and 'pytest' not in events
    assert events.count('entry') == (2 if cut == 'complete' else 1)
    snapshots = sorted((directory / 'guest-results').glob('retained-required-checkpoint-*.json'))
    result = json.loads(snapshots[-1].read_bytes())
    assert result['first_failure'] == 'RuntimeError: required cut ' + cut
    assert result['managers'][0]['cleanup_complete']


def test_required_original_refusal_survives_failed_restoration(composition):
    directory, vm, lease, events = composition
    original = vm.call
    first = RuntimeError('original required refusal')

    def call(arguments, **options):
        result = original(arguments, **options)
        if arguments[-2:] == ['refusal', required.BRANCHES[0]]:
            raise first
        if arguments[-1] == 'cleanup':
            raise RuntimeError('restoration refused')
        return result
    vm.call = call
    with pytest.raises(RuntimeError) as caught:
        runner.run_retained_phase(vm, lease, directory, None, runner.RETAINED_REQUIRED_PHASE)
    assert caught.value is first
    assert 'reboot' not in events and events.count('entry') == 1
    snapshots = sorted((directory / 'guest-results').glob('retained-required-checkpoint-*.json'))
    result = json.loads(snapshots[-1].read_bytes())
    assert 'original required refusal' in result['first_failure']
    assert any('restoration refused' in value for value in result['cleanup_failures'])
