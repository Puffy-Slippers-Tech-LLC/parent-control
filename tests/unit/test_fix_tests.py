"""The scripting loop never resumes an agent or repeats composite categories."""
from tests.support.vm_registry import vm_name

import json
import io
import os
import tomllib
from contextlib import ExitStack
import fcntl
from pathlib import Path
from unittest.mock import Mock

import pytest

import fix_tests
import detached_launcher
import regression
import regression_selection
import test_commands
from tests.support.paths import ROOT


def failure(prompt, *categories):
    return {'prompt': prompt, 'categories': list(categories)}


def test_reload_preserves_owner_and_scratch_flags_on_exec_failure(tmp_path, monkeypatch):
    import fix_tests_queue as queue
    child = detached_launcher.private_directory(tmp_path / 'pipeline-repair')
    detached_launcher.atomic(child / 'pipeline.json', {'parent': str(tmp_path)})
    writer = queue.RepairGate(child, root=tmp_path)
    writer.acquire()
    writer.release(unfinished=True)
    detached_launcher.atomic(child / 'result.json', {'status': 75})
    gate = queue.RepairGate(tmp_path, root=tmp_path)
    # Ordinary imports still refuse the retained edits. Reload must use the
    # exact child writer, and exec failure must not clear its recovery fence.
    with pytest.raises(ValueError, match='unfinished case repair'):
        with gate.source():
            pytest.fail('unverified source admitted as a reader')
    with (tmp_path / 'owner').open('wb') as owner, (tmp_path / 'scratch').open('wb') as scratch:
        descriptors = (owner.fileno(), scratch.fileno())
        monkeypatch.setattr(detached_launcher, 'scratch_descriptors', lambda: (scratch.fileno(),))
        def fail(program, command):
            assert all(os.get_inheritable(fd) for fd in descriptors)
            source = int(os.environ[queue.STARTUP_SOURCE])
            assert os.get_inheritable(source)
            with detached_launcher.lock(gate.coordinator.source / 'repair-owner') as other:
                with pytest.raises(BlockingIOError):
                    fcntl.flock(other, fcntl.LOCK_SH | fcntl.LOCK_NB)
            assert command[3:7] == ['--reload-worker', str(tmp_path), str(tmp_path), str(owner.fileno())]
            raise OSError('synthetic exec failure')
        monkeypatch.setattr(fix_tests.os, 'execv', fail)
        with pytest.raises(OSError, match='synthetic exec failure'):
            fix_tests.reload_controller(tmp_path, tmp_path, owner.fileno(), 'model', 'low', gate=gate)
        assert all(not os.get_inheritable(fd) for fd in descriptors)
    assert queue.STARTUP_SOURCE not in os.environ
    assert json.loads((tmp_path / 'repair-pending.json').read_text()) == {'run': child.name}
    assert json.loads((gate.coordinator.source / 'repair-source-pending.json').read_text()) == {
        'run': str(child.resolve())}
    # Recovery can reacquire the same ticket after the failed exec.
    writer.acquire()
    writer.release()


def test_missing_handoff_reports_the_runner_infrastructure_error(tmp_path):
    (tmp_path / 'last-test.log').write_text(
        'Started run-tests session: example\n'
        'Test runner infrastructure failed: ValueError: invalid resume checkpoint\n')
    with pytest.raises(ValueError, match='ValueError: invalid resume checkpoint; see last-test.log'):
        fix_tests.handoff(tmp_path)


def test_failure_context_survives_original_report_and_command_removal(tmp_path):
    import repair_evidence
    storage = tmp_path / 'output/test-runs'
    queue = storage / 'host/allocations/onpc-vm-queue-example'
    report = storage / 'host/reports/example'
    private = storage / 'privileged/allocations/onpc-graphical-smoke-example/private'
    run = storage / 'host/fix-tests/example'
    for path in (queue, report, private, run):
        path.mkdir(parents=True)
    handoff = queue / 'failure.json'
    handoff.write_text(json.dumps(failure('original failure', 'e2e')))
    child_handoff = report / 'failure.json'
    child_handoff.write_text(json.dumps(failure('guest failure', 'e2e')))
    (queue / 'results.json').write_text(json.dumps({
        'guest': {'status': 1, 'handoffs': [str(child_handoff)]}}))
    category = report / 'category-003.log'
    category.write_text(json.dumps({'attempts': [{
        'outcome': 'failed', 'raw_directory': str(private.parent)}]}) + '\n')
    error = private / 'command-0153-stderr.txt'
    error.write_text('ui:timeout:toggle-state\noriginal read failure\n')
    (private / 'command-0153.txt').write_text('public operation result\n')
    (run / 'last-test.log').write_text(f'Failure handoff: {handoff}\n')

    result = fix_tests.handoff(run, root=tmp_path)
    saved, = run.glob('failure-evidence-*.json')
    assert str(saved) in result['prompt']
    evidence = json.loads(saved.read_text())
    assert evidence['read_failures'] == []
    assert not evidence['limit_reached']
    copies = {item['source']: item['tail'] for item in evidence['files']}
    assert copies[str(error)] == error.read_text()
    assert copies[str(child_handoff)] == child_handoff.read_text()
    # Model execution-journal retirement without rerunning or weakening a test.
    error.unlink()
    category.unlink()
    child_handoff.unlink()
    handoff.unlink()
    assert json.loads(saved.read_text()) == evidence


def test_failure_context_bounds_data_and_refuses_linked_sources(tmp_path, monkeypatch):
    import repair_evidence
    report = tmp_path / 'output/test-runs/host/reports/example'
    report.mkdir(parents=True)
    handoff = report / 'failure.json'
    handoff.write_text('{}')
    outside = tmp_path / 'unrelated-secret'
    outside.write_text('do not copy this')
    (report / 'category-001.log').symlink_to(outside)
    (report / 'category-002.log').write_text('x' * 100)
    monkeypatch.setattr(repair_evidence, 'MAX_BYTES', 32)
    saved = tmp_path / 'snapshot.json'
    repair_evidence.capture(tmp_path, saved, handoff, 'runner output')
    evidence = json.loads(saved.read_text())
    assert evidence['bounded_tails'] is True
    assert evidence['limit_reached']
    assert sum(len(item['tail'].encode()) for item in evidence['files']) <= 32
    partial = next(item for item in evidence['files']
                   if item['source'].endswith('category-002.log'))
    assert partial['tail'] == 'x' * 30
    assert partial['tail_limit_bytes'] == 30
    assert partial['may_be_truncated'] is True
    complete = next(item for item in evidence['files'] if item['source'] == str(handoff))
    assert complete['may_be_truncated'] is False
    assert any(item['source'].endswith('category-001.log')
               for item in evidence['read_failures'])
    assert 'do not copy this' not in saved.read_text()


def test_failure_context_uses_scoped_privileged_reader(tmp_path, monkeypatch):
    import repair_evidence
    report = tmp_path / 'output/test-runs/host/reports/example'
    report.mkdir(parents=True)
    handoff = report / 'failure.json'
    handoff.write_text('{}')
    original = repair_evidence.directory
    def refuse(path):
        if path == report:
            raise PermissionError()
        return original(path)
    monkeypatch.setattr(repair_evidence, 'directory', refuse)
    reader = Mock(return_value=type('Result', (), {'returncode': 0, 'stdout': b'{}'})())
    monkeypatch.setattr(repair_evidence.subprocess, 'run', reader)
    saved = tmp_path / 'snapshot.json'
    repair_evidence.capture(tmp_path, saved, handoff, '')
    assert reader.call_args_list[0].args[0] == [
        'pkexec', '--keep-cwd', '/usr/local/libexec/onpc-test-artifacts',
        'tail', str(handoff), '--bytes', str(repair_evidence.FILE_BYTES)]
    assert json.loads(saved.read_text())['files'][0]['tail'] == '{}'


def test_failure_context_does_not_retry_a_denied_reader(tmp_path, monkeypatch):
    import repair_evidence
    report = tmp_path / 'output/test-runs/host/reports/example'
    report.mkdir(parents=True)
    handoff = report / 'failure.json'
    handoff.write_text('{}')
    monkeypatch.setattr(repair_evidence, 'directory', Mock(side_effect=PermissionError()))
    reader = Mock(return_value=type('Result', (), {'returncode': 126})())
    monkeypatch.setattr(repair_evidence.subprocess, 'run', reader)
    saved = tmp_path / 'snapshot.json'
    repair_evidence.capture(tmp_path, saved, handoff, 'original failure')
    assert reader.call_count == 1
    evidence = json.loads(saved.read_text())
    assert evidence['read_failures']
    assert evidence['output_tail'] == 'original failure'


def test_optional_failure_copy_does_not_block_the_current_failure(tmp_path, monkeypatch):
    import repair_evidence
    path = tmp_path / 'failure.json'
    original = failure('Repair the actual failure', 'unit')
    path.write_text(json.dumps(original))
    (tmp_path / 'last-test.log').write_text(f'Failure handoff: {path}\n')
    monkeypatch.setattr(repair_evidence, 'capture', Mock(side_effect=OSError('copy unavailable')))
    result = fix_tests.handoff(tmp_path, root=tmp_path)
    assert result['categories'] == ['unit']
    assert result['prompt'].startswith(original['prompt'])
    assert 'Optional diagnostic copy unavailable' in result['prompt']


def test_current_failure_reader_refuses_missing_or_linked_sources(tmp_path):
    import repair_evidence
    path = tmp_path / 'failure.json'
    with pytest.raises(FileNotFoundError):
        repair_evidence.read_failure(path)
    source = tmp_path / 'source.json'
    source.write_text(json.dumps(failure('Actual failure', 'unit')))
    path.symlink_to(source)
    with pytest.raises(OSError):
        repair_evidence.read_failure(path)


@pytest.mark.parametrize('requested, expected', [
    ([], ['unit', 'ui', 'future-suite', 'system', 'e2e']),
    (['host'], ['unit', 'ui', 'future-suite']),
    (['vm'], ['system', 'e2e']),
    (['host', 'vm'], ['unit', 'ui', 'future-suite', 'system', 'e2e']),
    (['vm', 'host'], ['unit', 'ui', 'future-suite', 'system', 'e2e']),
    (['host-builds', 'unit', 'system'], ['unit', 'ui', 'future-suite', 'system']),
    (['ui', 'unit', 'ui'], ['unit', 'ui']),
    (['unit ui'], ['unit', 'ui']),
    (['all', 'host'], ['unit', 'ui', 'future-suite', 'system', 'e2e']),
])
def test_selected_inventory_expands_and_deduplicates(requested, expected):
    inventory = {name: {'args': ['--case', 'two words']} for name in
                 ('unit', 'ui', 'future-suite', 'system', 'e2e')}
    selected = fix_tests.requested_inventory(ROOT, requested, inventory=inventory)
    assert list(selected) == expected
    assert all(selected[name] is inventory[name] for name in expected)


@pytest.mark.parametrize('requested', [['typo'], ['unit', 'coverage'], [' ']])
def test_invalid_selection_is_refused(requested):
    with pytest.raises(ValueError):
        fix_tests.requested_inventory(ROOT, requested, inventory={'unit': {'args': []}})


def test_selected_rounds_reverify_earlier_leaves_after_repairs():
    pending = iter([
        ('unit', None), ('ui', failure('first ui', 'ui')), ('ui', None),
        ('unit', failure('unit regression', 'unit')), ('unit', None), ('ui', None),
        ('unit', None), ('ui', None),
    ])
    prompts = []

    def test(category):
        expected, result = next(pending)
        assert category == expected
        return result

    rounds = []
    fix_tests.run_loop(['unit', 'ui'], test, lambda prompt, **_: prompts.append(prompt), lambda: None, selected=True,
                       round_changed=rounds.append, rounds=2)
    assert rounds == [1, 2]
    assert list(pending) == []
    assert prompts == ['first ui', 'unit regression']


@pytest.mark.parametrize('options, expected', [([], 1), (['--rounds', '3'], 3)])
def test_cli_forwards_category_arguments(monkeypatch, options, expected):
    select = Mock(return_value=(None, False))
    monkeypatch.setattr(fix_tests, 'select', select)
    assert fix_tests.main(['unit', 'ui', *options]) == 0
    assert select.call_args.kwargs['categories'] == ['unit', 'ui']
    assert select.call_args.kwargs['rounds'] == expected
    assert select.call_args.kwargs['effort'] is None  # Keep per-category defaults until a failure is known.


@pytest.mark.parametrize('requested', [
    ['e2e', '--id', '6'],
    ['e2e', '--id', '5,6'],
    ['e2e', '--id=6'],
    ['e2e', '--scenario', 'E2E-004/terminal'],
    ['unit', 'tests/unit/test_fix_tests.py', '-q'],
    ['unit', '-k', 'component'],
    ['unit', '-k', 'unit or component', '--durations', '3', '--tb=short'],
    ['ui', '--timeout', '300s', '-m', 'not live_e2e'],
    ['static', 'all'],
])
def test_repair_selectors_match_runner_and_survive_cli(monkeypatch, requested):
    import vm_selection
    monkeypatch.setattr(vm_selection, 'execution_selection', Mock())
    select = Mock(return_value=(None, False))
    monkeypatch.setattr(fix_tests, 'select', select)
    assert fix_tests.main([*requested, '--rounds', '2']) == 0
    assert select.call_args.kwargs['categories'] == requested
    inventory = fix_tests.requested_inventory(ROOT, requested)
    assert list(inventory) == [requested[0]]
    assert inventory[requested[0]]['args'] == requested[1:]


@pytest.mark.parametrize('requested', [
    ['e2e', '--bogus'], ['e2e', '--id'], ['unit', '--collect-only'],
    ['host', '--continue-on-errors'],
])
def test_invalid_repair_selectors_do_not_start_launcher(monkeypatch, requested):
    select = Mock()
    monkeypatch.setattr(fix_tests, 'select', select)
    assert fix_tests.main(requested) == 2
    select.assert_not_called()


def test_multiple_focused_repair_categories_preserve_each_scope():
    requested = ['unit', 'tests/unit/test_fix_tests.py', '-q', 'e2e', '--id', '6']
    inventory = fix_tests.requested_inventory(ROOT, requested)
    assert list(inventory) == ['unit', 'e2e']
    assert inventory['unit']['args'] == requested[1:3]
    assert inventory['e2e']['args'] == ['--id', '6']


def test_runner_owns_validation_of_new_category_arguments(monkeypatch):
    options = ['--future-option', 'two words', '--future-flag']
    parse = Mock(return_value=[('unit', options)])
    monkeypatch.setattr(test_commands, 'selections', parse)
    inventory = fix_tests.requested_inventory(ROOT, ['unit', *options])
    parse.assert_called_once_with(ROOT, ['unit', *options])
    assert inventory['unit']['args'] == options


@pytest.mark.parametrize('vm_args', [[], ['--vm', vm_name()]])
def test_vm_selection_precedes_runner_argument_validation(monkeypatch, vm_args):
    import vm_selection
    monkeypatch.delenv(vm_selection.VARIABLE, raising=False)
    selection = Mock(wraps=vm_selection.execution_selection)
    monkeypatch.setattr(vm_selection, 'execution_selection', selection)
    launcher = Mock(return_value=(None, False))
    monkeypatch.setattr(fix_tests, 'select', launcher)
    assert fix_tests.main(['e2e', '--id', '6', *vm_args]) == 0
    selection.assert_called_once_with(*vm_args[1:])
    assert launcher.call_args.kwargs['categories'] == ['e2e', '--id', '6']


@pytest.mark.parametrize('categories', [['static', 'all'], ['unit ui']])
def test_host_selection_does_not_discover_vms(monkeypatch, categories):
    import vm_selection
    selection = Mock(side_effect=AssertionError('host-only request discovered VMs'))
    monkeypatch.setattr(vm_selection, 'execution_selection', selection)
    monkeypatch.setattr(fix_tests, 'select', Mock(return_value=(None, False)))
    assert fix_tests.main(categories) == 0
    selection.assert_not_called()


@pytest.mark.parametrize('active', [(), ('fix-tests-host',), ('fix-tests',),
                                   ('fix-tests-host', 'fix-tests'),
                                   ('legacy', 'fix-tests-host', 'fix-tests')])
def test_bare_stop_cancels_all_checkout_owners_before_waiting(tmp_path, monkeypatch, active):
    import test_storage
    import vm_selection

    root = tmp_path / 'checkout'
    monkeypatch.setattr(fix_tests, '__file__', str(root / 'tools/fix_tests.py'))
    monkeypatch.setattr(vm_selection, 'execution_selection',
                        Mock(side_effect=AssertionError('stop must not discover VMs')))
    monkeypatch.setattr(fix_tests, 'select',
                        Mock(side_effect=AssertionError('stop must not start or attach by category')))
    runs = {}
    with ExitStack() as owners:
        for kind in ('legacy', 'fix-tests-host', 'fix-tests', 'foreign'):
            if kind == 'legacy':
                directory = detached_launcher.private_directory(root / 'artifacts/fix-tests')
            else:
                directory = test_storage.directory(
                    'fix-tests-host' if kind == 'foreign' else kind,
                    root=tmp_path / 'other-checkout' if kind == 'foreign' else root)
            run = detached_launcher.private_directory(directory / ('a' * 32))
            detached_launcher.atomic(directory / 'current.json', {'run': run.name})
            runs[kind] = run
            if kind in active or kind == 'foreign':
                owner = owners.enter_context(detached_launcher.lock(directory / 'owner'))
                fcntl.flock(owner, fcntl.LOCK_EX)

        def follow(run):
            assert {kind for kind, path in runs.items() if (path / 'cancel').exists()} == set(active)
            assert run in [runs[kind] for kind in active]
            return 130

        observer = Mock(side_effect=follow)
        monkeypatch.setattr(fix_tests, 'follow', observer)
        assert fix_tests.main(['--stop']) == (130 if active else 0)
        assert observer.call_count == len(active)
        assert {kind for kind, path in runs.items() if (path / 'cancel').exists()} == set(active)


def test_rounds_repair_only_failed_categories_with_latest_prompt(capsys):
    pending = iter([
        ('unit', failure('unit first', 'unit')),
        ('unit', failure('unit second', 'unit')), ('unit', None),
        ('ui', None), ('system', None), ('e2e', None),
        ('all', failure('aggregate ui', 'ui')), ('ui', failure('ui only', 'ui')),
        ('ui', None), ('all', None),
    ])
    prompts, calls = [], []

    def test(category):
        expected, result = next(pending)
        assert category == expected
        calls.append(category)
        return result

    fix_tests.run_loop(['unit', 'ui', 'system', 'e2e'], test,
                       lambda prompt, **_: prompts.append(prompt), lambda: None, rounds=2)
    assert list(pending) == []
    assert calls.count('system') == calls.count('e2e') == 1
    assert prompts == ['unit first', 'unit second', 'aggregate ui', 'ui only']
    assert 'Running category' not in capsys.readouterr().out


def test_multiple_aggregate_failures_recheck_companions_before_repair():
    pending = iter([None, None, failure('both', 'unit', 'ui', 'unit'), None, None, None])
    calls, prompts = [], []

    def test(category):
        calls.append(category)
        return next(pending)

    fix_tests.run_loop(['unit', 'ui'], test, lambda prompt, **_: prompts.append(prompt), lambda: None, rounds=2)
    assert calls == ['unit', 'ui', 'all', 'unit', 'ui', 'all']
    assert prompts == ['both']


def test_cancellation_never_starts_an_agent_or_next_test():
    repair = Mock(side_effect=fix_tests.Stopped)
    test = Mock(return_value=failure('current', 'unit'))
    with pytest.raises(fix_tests.Stopped):
        fix_tests.run_loop(['unit', 'ui'], test, repair, lambda: None)
    test.assert_called_once_with('unit')
    repair.assert_called_once_with('current', failure_key=('unit', '', ''))


def test_unmapped_aggregate_failure_is_not_a_fabricated_category_pass():
    test = Mock(side_effect=[None, failure('infrastructure')])
    repair = Mock()
    with pytest.raises(ValueError, match='no runnable retry category'):
        fix_tests.run_loop(['unit'], test, repair, lambda: None, rounds=2)
    repair.assert_not_called()


def test_failed_verification_carries_only_latest_repair_until_category_passes():
    outcomes = iter([failure('one', 'unit'), failure('two', 'unit'),
                     failure('three', 'unit'), None, failure('new', 'ui'), None, None])
    calls, verified = [], []

    def repair(prompt, *, failure_key, previous=None):
        assert failure_key[0] in ('unit', 'ui')
        calls.append((prompt, previous))
        return prompt + ' repair summary'

    fix_tests.run_loop(['unit', 'ui'], lambda _: next(outcomes), repair, lambda: None,
                       verified=lambda summary, passed: verified.append((summary, passed)))
    assert calls == [('one', None), ('two', 'one repair summary'),
                     ('three', 'two repair summary'), ('new', None)]
    assert verified == [('one repair summary', False), ('two repair summary', False),
                        ('three repair summary', True), ('new repair summary', True)]


def test_case_handoffs_do_not_cross_cases_or_vms_or_aggregate_companions():
    def case(name, vm='guest-a'):
        return dict(category='e2e', case=name, vm=vm)
    identities = [case('A'), case('B'), case('A', 'guest-b'), case('A')]
    pending = iter([dict(prompt=str(index), categories=['e2e'],
                         failures=[dict(category='unit', case='unrelated', vm=''), identity])
                    for index, identity in enumerate(identities)] + [None])
    repairs = []
    def repair(prompt, *, failure_key, previous=None):
        repairs.append((failure_key, previous))
        return prompt
    fix_tests.run_loop(['e2e'], lambda _: next(pending), repair, lambda: None)
    assert repairs == [(('e2e', 'A', 'guest-a'), None), (('e2e', 'B', 'guest-a'), None),
                       (('e2e', 'A', 'guest-b'), None), (('e2e', 'A', 'guest-a'), '0')]


@pytest.mark.parametrize('targets', [None, {}, [None], [{'category': 'unit', 'case': 4, 'vm': ''}],
                                    [{'category': '', 'case': 'A', 'vm': ''}]])
def test_invalid_runner_failure_ids_are_refused(targets):
    with pytest.raises(ValueError, match='invalid failure identities'):
        fix_tests.failure_target({'failures': targets}, 'unit')


def test_verification_uses_all_reported_identities_but_never_infers_unreported_passes():
    failure = {'failures': [dict(category='e2e', case=case, vm=vm)
                            for case, vm in [('B', 'one'), ('A', 'one')]]}
    assert fix_tests.verification_outcome(failure, ('e2e', 'A', 'one')) is False
    assert fix_tests.verification_outcome(failure, ('e2e', 'A', 'two')) is None
    assert fix_tests.verification_outcome({'failures': []}, ('e2e', 'A', 'one')) is None
    assert fix_tests.verification_outcome(None, ('e2e', 'A', 'one')) is True


@pytest.mark.parametrize('result', [
    [], {'status': 'unknown', 'summary': 'x'},
    {'status': 'blocked', 'summary': 'x', 'blocker': None},
    {'status': 'blocked', 'summary': 'x', 'blocker': {
        'explanation': 'x', 'question': 'q', 'options': ['one']}},
    {'status': 'test_fixed', 'summary': 'x', 'blocker': {}},
    {'status': 'diagnostic_ready', 'summary': 'instrumentation', 'commands': ['tools/run-tests all']},
    {'status': 'diagnostic_ready', 'summary': '', 'blocker': None},
])
def test_malformed_results_cannot_trigger_repairs_or_default_answers(result):
    with pytest.raises(ValueError):
        fix_tests.validate_result(result)


def test_diagnostic_schema_and_prompt_allow_only_launcher_owned_execution():
    result = dict(status='diagnostic_ready', summary='Hypothesis, bounded paths and observations', blocker=None)
    fix_tests.validate_result(result)
    schema = json.loads((ROOT / 'tools/fix_tests_response.schema.json').read_text())
    assert result['status'] in schema['properties']['status']['enum']
    assert not schema['additionalProperties']
    prompt = fix_tests.repair_prompt('failure')
    for guard in ('diagnostic_ready', 'preserves behavior', 'validation guards',
                  'original authorized selectors', 'Never supply commands', 'five-session budget'):
        assert guard in prompt


def test_agent_transcript_records_turn_failure_for_supervisor():
    from launcher_render import AgentRenderer
    stream = io.StringIO()
    renderer = AgentRenderer(stream)
    failure = {'message': 'agent failed'}
    renderer.event({'type': 'turn.failed', 'error': failure})
    assert renderer.failure == failure


def test_command_output_cannot_inject_terminal_clear_sequences():
    from launcher_render import AgentRenderer
    from rich.text import Text
    stream = io.StringIO()
    renderer = AgentRenderer(stream)
    renderer.event({'type': 'item.completed', 'item': {
        'id': 'cmd', 'type': 'command_execution', 'command': 'example',
        'aggregated_output': '\033[2J[bold]failure[/bold]', 'exit_code': 2}})
    assert '\033[2J' not in stream.getvalue()
    assert '[bold]failure[/bold]' in Text.from_ansi(stream.getvalue()).plain


def test_successful_exploration_does_not_echo_sensitive_command_output():
    from launcher_render import AgentRenderer
    from rich.text import Text
    stream = io.StringIO()
    AgentRenderer(stream, full_command_output=True).event({'type': 'item.completed', 'item': {
        'id': 'secret', 'type': 'command_execution', 'command': 'cat secrets.txt',
        'aggregated_output': 'credential=private-token',
        'exit_code': 0}})
    assert 'credential=private-token' not in Text.from_ansi(stream.getvalue()).plain


def test_granular_inventory_order_excludes_every_duplicate_helper():
    inventory = test_commands.suite_inventory()
    assert list(inventory)[:2] == ['unit', 'ui']
    assert list(inventory)[-3:] == ['system', 'integration', 'e2e']
    helpers = {kind for kind, spec in test_commands.CATEGORIES.items()
               if not spec.leaf or not spec.implemented}
    assert set(inventory).isdisjoint(helpers)
    assert set(inventory) | helpers == set(test_commands.CATEGORIES)
    assert inventory['ui']['args'] == ['--timeout', '1800s', '-m', 'not live_e2e']
    for category, spec in inventory.items():
        test_commands.validate(ROOT, ['--stop-on-error', category, *spec['args'], '--vm', vm_name()])


def test_future_categories_follow_readiness_without_a_second_allowlist(monkeypatch):
    for name, spec in {
        'future-suite': test_commands.CategorySpec('New implemented suite'),
        'future-composite': test_commands.CategorySpec('Combined suites', leaf=False),
        'future-help': test_commands.CategorySpec('Inspection only', leaf=False),
        'future-pending': test_commands.CategorySpec('Waiting for implementation', implemented=False),
    }.items():
        monkeypatch.setitem(test_commands.CATEGORIES, name, spec)
    inventory = test_commands.suite_inventory()
    assert list(inventory)[-4:] == ['future-suite', 'system', 'integration', 'e2e']
    assert not {'future-composite', 'future-help', 'future-pending'} & inventory.keys()
    monkeypatch.setitem(test_commands.CATEGORIES, 'future-pending',
                        test_commands.CategorySpec('Now implemented'))
    assert 'future-pending' in test_commands.suite_inventory()
    assert 'future-help' in test_commands.usage()


def test_launcher_preserves_runner_inventory_order_and_arguments():
    inventory = {name: {'args': ['--selected', 'two words']} for name in
                 ('e2e', 'new-suite', 'ui', 'unit', 'system')}
    ordered = fix_tests.category_inventory(json.dumps(inventory))
    assert list(ordered) == list(inventory)
    assert ordered['new-suite']['args'] == ['--selected', 'two words']
    assert list(fix_tests.category_inventory('{"new-suite": {"args": []}}')) == ['new-suite']


def test_host_and_vm_partition_all_and_repair_uses_runner_definitions(monkeypatch):
    monkeypatch.setitem(test_commands.CATEGORIES, 'future-vm',
                        test_commands.CategorySpec('Future VM suite', scope='vm'))
    inventory = test_commands.suite_inventory()
    host = test_commands.suite_inventory(['host'])
    vm = test_commands.suite_inventory(['vm'])
    assert host.keys().isdisjoint(vm)
    assert host.keys() | vm.keys() == inventory.keys()
    assert 'future-vm' in vm and 'future-vm' not in host
    assert {spec['scope'] for spec in inventory.values()} == {'host', 'vm'}
    assert fix_tests.requested_inventory is test_commands.repair_inventory
    assert fix_tests.requested_inventory(ROOT, ['vm']) == vm
    assert fix_tests.requested_inventory(ROOT, ['host', 'vm']) == inventory


def test_category_scope_cannot_fall_between_host_and_vm():
    with pytest.raises(ValueError, match='scope must be host or vm'):
        test_commands.CategorySpec('Unclassified suite', scope='other')
    with pytest.raises(ValueError, match='scope must be host or vm'):
        test_commands.suite_inventory(['host'], inventory={'suite': {'args': [], 'scope': 'other'}})


@pytest.mark.parametrize('value', ['{}', '[]', '{"unit": {}}', '{"unit": {"args": "-x"}}'])
def test_invalid_category_inventory_is_refused(value):
    with pytest.raises(ValueError):
        fix_tests.category_inventory(value)


def test_new_category_failure_has_a_runnable_handoff(tmp_path, monkeypatch, capsys):
    monkeypatch.setitem(test_commands.CATEGORIES, 'future-suite',
                        test_commands.CategorySpec('New implemented suite'))
    monkeypatch.setattr(regression_selection, 'source_identity', lambda _: 'fixed')
    monkeypatch.setattr(regression, 'source_identity', lambda _: 'fixed')
    monkeypatch.setattr(regression.Control, 'run', lambda *_args, **_kwargs: 1)
    assert regression.retained_main(tmp_path, selections=[('future-suite', [])]) == 1
    output = capsys.readouterr().out
    report, = (tmp_path / 'output/test-runs/host/reports').iterdir()
    saved = json.loads((report / 'failure.json').read_text())
    assert saved['categories'] == ['future-suite']
    assert saved['prompt'] not in output
    (tmp_path / 'last-test.log').write_text(output)
    assert fix_tests.handoff(tmp_path) == saved


def test_stop_on_error_reaches_the_selected_coordinator(monkeypatch):
    run = Mock(return_value=7)
    monkeypatch.setattr(regression, 'main', run)
    assert test_commands._main(['--stop-on-error', 'unit'], detached=True) == 7
    run.assert_called_once_with(ROOT, selections=[('unit', [])], stop_on_error=True)
    with pytest.raises(ValueError):
        test_commands.validate(ROOT, ['--stop-on-error', 'all', '--continue-on-errors'])


def test_case_verification_runs_only_on_its_failing_vm(tmp_path, monkeypatch):
    import vm_selection

    monkeypatch.setenv('ONPC_RUNNER_INVOCATION', '{}')
    monkeypatch.setattr(vm_selection, 'selected', lambda **_: object())
    monkeypatch.setattr(vm_selection, 'execution_arguments', lambda: ['--vm', 'first,second'])
    execute = Mock(return_value=0)
    monkeypatch.setattr(detached_launcher, 'supervise', execute)
    invocation = dict(selection=[['e2e', ['--id=6']]])
    declaration = dict(args=['--id=6', '--resume', '--resume-case=case'],
                       invocation=invocation, vm='second')
    assert fix_tests.supervise(ROOT, tmp_path, 123, 'test', 'e2e', 'gpt-6.1-sol', 'medium',
                               json.dumps(declaration)) == 0
    command = execute.call_args.args[4]
    assert command == [str(ROOT / 'tools/run-tests'), '--resume', '--stop-on-error',
                       'e2e', '--id=6', '--resume-case=case', '--vm', 'second']
    assert json.loads(os.environ['ONPC_RUNNER_INVOCATION']) == invocation


@pytest.mark.parametrize('enabled', [False, True])
def test_selected_fail_fast_persists_failure_before_cancelling(tmp_path, monkeypatch, enabled):
    monkeypatch.setattr(regression, 'source_identity', lambda _: 'fixed')
    monkeypatch.setattr(regression_selection, 'source_identity', lambda _: 'fixed')
    observed = []

    def run_selected(run):
        item = run.categories[0]
        item.retry_category = 'unit'
        execution = regression.Execution(run, item, events=True)
        execution.output((regression.PREFIX + json.dumps(
            {'kind': 'failure', 'nodeid': 'test_one', 'when': 'call', 'detail': 'expected failure'}) + '\n').encode())
        observed.append(run.control.stopped.is_set())
        execution.finish(1)

    monkeypatch.setattr(regression_selection.SelectedRun, 'run', run_selected)
    status = regression.retained_main(tmp_path, selections=[('unit', [])], stop_on_error=enabled)
    assert status == (130 if enabled else 1)
    assert observed == [enabled]
    report, = (tmp_path / 'output/test-runs/host/reports').iterdir()
    handoff = json.loads((report / 'failure.json').read_text())
    assert handoff['categories'] == ['unit']
    assert str(report / 'report.md') in handoff['prompt']
    assert json.loads((report / 'progress.json').read_text())[0]['failures'] == 1


def test_bare_artifacts_includes_both_builds_and_comparison(tmp_path, monkeypatch):
    monkeypatch.setattr(regression_selection, 'source_identity', lambda _: 'fixed')
    commands = []

    def jobs(run, planned):
        for job in planned:
            command = job.command() if callable(job.command) else job.command
            commands.append(command[1:])
            job.item.state = 'Passed'
            if job.key in ('build-a', 'build-b'):
                run.artifacts[job.key] = '/tmp/onpc-' + job.key

    monkeypatch.setattr(regression.Run, 'host_jobs', jobs)
    report = regression.Report(tmp_path)
    try:
        run = regression_selection.SelectedRun(tmp_path, report, regression.Control(), [('artifacts', [])])
        run.run()
    finally:
        report.close()
    assert commands == [
        ['artifacts', '--unattended', 'build'], ['artifacts', '--unattended', 'build'],
        ['artifacts', '--unattended', 'compare', '/tmp/onpc-build-a', '/tmp/onpc-build-b']]
