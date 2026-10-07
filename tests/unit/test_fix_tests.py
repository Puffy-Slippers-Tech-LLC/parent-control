"""The scripting loop never resumes an agent or repeats composite categories."""
from tests.support.vm_registry import vm_name

import json
import io
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


def test_category_status_uses_the_discovered_inventory_position():
    categories = ['unit', 'future-suite', 'e2e']
    assert fix_tests.category_status('future-suite', categories) == (
        '\033[1;36mRunning category [future-suite] (2/3)\033[0m')
    assert fix_tests.category_status('all', categories) is None


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


@pytest.mark.parametrize('selected', [False, True])
@pytest.mark.parametrize('count', [1, 2, 3, 4])
def test_requested_round_count_and_progress(selected, count):
    test = Mock(return_value=None)
    numbers = []
    fix_tests.run_loop(['unit', 'ui'], test, Mock(), lambda: None,
                       selected=selected, rounds=count, round_changed=numbers.append)
    assert numbers == list(range(1, count + 1))
    assert [call.args[0] for call in test.call_args_list] == (
        ['unit', 'ui'] + (['unit', 'ui'] if selected else ['all']) * (count - 1))


@pytest.mark.parametrize('value', ['0', '-1', 'abc', '1.5'])
def test_invalid_round_count_is_refused(value):
    with pytest.raises(SystemExit) as error:
        fix_tests.main(['unit', '--rounds', value])
    assert error.value.code == 2


@pytest.mark.parametrize('options, expected', [([], 1), (['--rounds', '3'], 3)])
def test_cli_forwards_category_arguments(monkeypatch, options, expected):
    select = Mock(return_value=(None, False))
    monkeypatch.setattr(fix_tests, 'select', select)
    assert fix_tests.main(['unit', 'ui', *options]) == 0
    assert select.call_args.kwargs['categories'] == ['unit', 'ui']
    assert select.call_args.kwargs['rounds'] == expected


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


@pytest.mark.parametrize('argv', [
    ['--rounds', '3', '--model', 'gpt-6.1-sol', '--effort', 'high', 'unit', '-q'],
    ['unit', '-q', '--rounds', '3', '--model', 'gpt-6.1-sol', '--effort', 'high'],
    ['unit', '--rounds', '3', '-q', '--effort', 'high', '--model', 'gpt-6.1-sol'],
])
def test_launcher_options_are_removed_from_forwarded_arguments(monkeypatch, argv):
    select = Mock(return_value=(None, False))
    monkeypatch.setattr(fix_tests, 'select', select)
    assert fix_tests.main(argv) == 0
    assert select.call_args.kwargs == dict(stop=False, model='gpt-6.1-sol', effort='high',
                                          categories=['unit', '-q'], rounds=3)


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


def test_agent_is_ephemeral_sol_medium_standard_without_parent_context(monkeypatch):
    monkeypatch.setattr(fix_tests.shutil, 'which', lambda _: '/opt/codex')
    for key in ('CODEX_THREAD_ID', 'CODEX_PARENT_THREAD_ID', 'CODEX_SESSION_ID',
                'ONPC_TEST_ACTIVITY_FD', 'ONPC_TEST_HOST_ACTIVITY_FD', fix_tests.FRAME_DIRECTORY):
        monkeypatch.setenv(key, 'previous-context')
    command = fix_tests.repair_command(ROOT, fix_tests.DEFAULT_MODEL, fix_tests.DEFAULT_EFFORT)
    assert command[:5] == ['/opt/codex', '--ask-for-approval', 'never', 'exec', '--ephemeral']
    assert command[command.index('--model') + 1] == 'gpt-6.1-sol'
    assert 'model_reasoning_effort="medium"' in command
    assert 'service_tier="default"' in command and 'features.fast_mode=false' in command
    assert 'features.memories=false' in command and 'history.persistence="none"' in command
    assert 'agents.enabled=false' in command and 'features.multi_agent=false' in command
    assert 'features.multi_agent_v2=false' in command
    assert 'workspace-write' in command
    assert '--json' in command
    assert command[command.index('--color') + 1] == 'never'
    assert not {'resume', 'fork', '--last', '--ignore-rules', '--dangerously-bypass-approvals-and-sandbox'} & set(command)
    assert command[-1] == '-'
    assert 'previous-context' not in fix_tests.environment().values()
    assert fix_tests.repair_prompt('LATEST FAILURE').startswith('LATEST FAILURE\n')
    assert 'status "test_fixed"' in fix_tests.repair_prompt('LATEST FAILURE')
    assert 'status "uncertain"' in fix_tests.repair_prompt('LATEST FAILURE')


def test_model_catalog_requires_exact_sol_medium_and_high_efforts(monkeypatch):
    monkeypatch.setattr(fix_tests.shutil, 'which', lambda _: '/opt/codex')

    def entry(slug, priority, *, visibility='list', effort='low'):
        return {'slug': slug, 'priority': priority, 'visibility': visibility,
                'supported_reasoning_levels': [{'effort': effort}]}

    sol = entry('gpt-6.1-sol', 4, effort='medium')
    sol['supported_reasoning_levels'].append({'effort': 'high'})
    astra = entry('gpt-6-astra', 1, effort='high')
    astra['supported_reasoning_levels'].append({'effort': 'xhigh'})
    catalog = {'models': [sol, astra, entry('gpt-6-sol', 3),
                          entry('gpt-7-sol', 1, visibility='hide')]}
    run = Mock(return_value=Mock(stdout=json.dumps(catalog)))
    monkeypatch.setattr(fix_tests.subprocess, 'run', run)
    assert fix_tests.available_models() == ('gpt-6.1-sol', 'gpt-6.1-sol')
    assert run.call_args.args[0] == ['/opt/codex', 'debug', 'models']
    for replacement in (entry('gpt-6.1-sol', 2, effort='medium'),
                        dict(sol, visibility='hide'), entry('gpt-6-sol', 2)):
        catalog['models'][0] = replacement
        run.return_value.stdout = json.dumps(catalog)
        with pytest.raises(ValueError, match='gpt-6.1-sol with (medium|high) reasoning'):
            fix_tests.available_models()
    catalog['models'][0] = entry('gpt-6.1-sol', 4, effort='high')
    run.return_value.stdout = json.dumps(catalog)
    with pytest.raises(ValueError, match='gpt-6.1-sol with medium reasoning'):
        fix_tests.available_models()
    # An explicit High initial agent does not require Medium availability.
    assert fix_tests.available_models(effort='high') == ('gpt-6.1-sol', 'gpt-6.1-sol')
    for levels in ([], [{'effort': 'high'}], [{'effort': 'xhigh'}]):
        catalog['models'][1] = dict(astra, supported_reasoning_levels=levels)
        run.return_value.stdout = json.dumps(catalog)
        with pytest.raises(ValueError, match='gpt-6-astra'):
            fix_tests.available_models(effort='high')


@pytest.mark.parametrize('effort', ['high', 'xhigh'])
def test_sol_high_and_extra_high_preserve_requested_effort(effort):
    assert fix_tests.initial_model('gpt-6.1-sol', effort) == ('gpt-6.1-sol', effort)
    assert fix_tests.initial_model(None, effort) == ('gpt-6.1-sol', effort)


@pytest.mark.parametrize('model', ['gpt-6-sol', 'gpt-5.6-sol', 'gpt-7-sol'])
def test_other_sol_versions_are_refused(model):
    with pytest.raises(ValueError, match='Sol must be gpt-6.1-sol'):
        fix_tests.initial_model(model)


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


def test_usage_preserves_unknown_counters_and_never_interrupts_cleanup(tmp_path, capsys):
    fix_tests.record_usage(tmp_path, {'session_id': 'first'}, {
        'input_tokens': 0, 'output_tokens': -1, 'cached_input_tokens': True,
        'reasoning_output_tokens': 'unknown'})
    fix_tests.record_usage(tmp_path, {'session_id': 'second'}, event='missing_usage')
    rows = [json.loads(line) for line in (tmp_path / 'agent-usage.jsonl').read_text().splitlines()]
    assert rows[0]['usage'] == {'input_tokens': 0}
    assert rows[1]['usage'] is None and rows[1]['event'] == 'missing_usage'
    fix_tests.record_usage(tmp_path / 'absent', {}, {})
    assert 'could not retain usage' in capsys.readouterr().err


@pytest.mark.parametrize('classification', [None, 'app_issue: behavior changed'])
def test_every_repair_phase_preserves_the_behavior_confirmation_mandate(classification):
    from launcher_question import BLOCKER_INSTRUCTIONS
    prompt = fix_tests.repair_prompt(
        'original evidence', app_issue=classification,
        developer_answers=[{'question': 'Which behavior?', 'answer': 'Restore the specified behavior.'}],
        blocker_summary='Retained evidence: failure.json')
    assert 'Prefer GPT-6.1 Sol High over Astra Low' in prompt
    assert 'Never use Sol High' not in prompt
    if classification is None:
        assert 'before editing' in prompt
    else:
        assert 'Recheck the classification' in prompt
    assert 'expected versus actual results' in prompt
    assert 'return status "blocked" to ask the developer to confirm intended behavior' in prompt
    assert 'unless that exact behavior change is already explicitly authorized' in prompt
    assert 'Do not weaken, skip or delete tests' in prompt
    assert BLOCKER_INSTRUCTIONS in prompt
    assert 'Restore the specified behavior.' in prompt
    assert 'Retained evidence: failure.json' in prompt
    assert 'an answer alone is not evidence it passed' in prompt


def test_both_workflows_explain_decisions_without_requiring_technical_translation():
    import write_e2e
    from launcher_question import BLOCKER_INSTRUCTIONS
    prompts = [fix_tests.repair_prompt('failure'),
               write_e2e.session_prompt(write_e2e.fresh_state('017c'))]
    for prompt in prompts:
        assert 'tools/prepare-baseline --vm NAME --mode auto --y' in prompt
        assert 'omit it for manual work' in prompt
        assert '--mode manual --y only with explicit developer authorization' in prompt
        assert BLOCKER_INSTRUCTIONS in prompt
        assert 'Use everyday language and short sentences in ALL three fields' in prompt
        assert 'why you cannot finish' in prompt
        assert 'Each choice must say who does what and what happens' in prompt
        assert 'Do not offer two phrasings of the same repair' in prompt
        assert 'compare the exact command with the maintained grant' in prompt
        assert 'do not suggest administrator repair without evidence' in prompt
        assert 'expected result and observed result' in prompt


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


def test_agent_transcript_formats_markdown_and_code_across_byte_boundaries():
    from launcher_render import AgentRenderer
    from rich.text import Text
    stream = io.StringIO()
    renderer = AgentRenderer(stream)
    event = {'type': 'item.completed', 'item': {
        'id': 'message', 'type': 'agent_message',
        'text': '**Repair café**\n\n```python\ndef fixed():\n    return True\n```'}}
    encoded = json.dumps(event, ensure_ascii=False).encode()
    for byte in encoded:
        renderer.feed(bytes([byte]))
    assert stream.getvalue() == ''
    renderer.finish()  # EOF also renders a final event without a newline.
    rendered = Text.from_ansi(stream.getvalue())
    assert 'Repair café' in rendered.plain
    assert '**' not in rendered.plain and '```' not in rendered.plain
    assert 'def fixed():' in rendered.plain and 'return True' in rendered.plain
    code_start = rendered.plain.index('def fixed')
    assert any(span.start >= code_start and span.style.color for span in rendered.spans)
    assert '\ufffd' not in rendered.plain


def test_agent_transcript_preserves_activity_failures_and_unknown_events():
    from launcher_render import AgentRenderer
    from rich.text import Text
    stream = io.StringIO()
    renderer = AgentRenderer(stream)

    def emit(kind, item):
        renderer.feed((json.dumps({'type': kind, 'item': item}) + '\n').encode())

    command = {'id': 'cmd', 'type': 'command_execution', 'command': 'cat example.py'}
    emit('item.started', command)
    emit('item.updated', command)
    emit('item.completed', {**command, 'aggregated_output': 'failure details', 'exit_code': 2})
    emit('item.completed', {'type': 'file_change', 'status': 'completed', 'changes': [
        {'kind': 'update', 'path': 'example.py', 'diff': '-old\n+new'}]})
    emit('item.updated', {'type': 'todo_list', 'items': [
        {'text': 'Keep assertion', 'completed': True}]})
    emit('item.completed', {'type': 'mcp_tool_call', 'server': 'local', 'tool': 'read',
                            'result': {'content': [{'type': 'text', 'text': 'tool result'}]}})
    emit('item.completed', {'type': 'web_search', 'query': 'public docs'})
    emit('item.completed', {'type': 'agent_message', 'text': json.dumps({
        'status': 'blocked', 'summary': '**Missing prerequisite**'})})
    renderer.feed(b'{"type":"turn.failed","error":{"message":"agent failed"}}\n')
    renderer.feed(b'{"type":"future.event","detail":"keep unknown evidence"}\n')
    renderer.feed(b'{"type":"item.completed","item":null}\n')
    renderer.feed(b'plain diagnostic\npartial diagnostic')
    renderer.finish()
    text = Text.from_ansi(stream.getvalue()).plain
    assert text.count('Read example.py') == 1
    assert 'failure details' in text
    for expected in ('Exit 2', 'example.py', '-old', '+new',
                     'Keep assertion', 'tool result', 'public docs', 'Repair blocked',
                     'Missing prerequisite', 'agent failed', 'keep unknown evidence',
                     'null', 'plain diagnostic', 'partial diagnostic'):
        assert expected in text
    assert '\033[?1049' not in stream.getvalue()


@pytest.mark.parametrize('width', [40, 100])
def test_agent_transcript_separates_messages_and_interleaved_command_results(width):
    from launcher_render import AgentRenderer
    from rich.text import Text
    stream = io.StringIO()
    renderer = AgentRenderer(stream, width=width)
    commands = [dict(id=name, type='command_execution', command='cat ' + name)
                for name in ('first.py', 'second.py')]
    for command in commands:
        renderer.event({'type': 'item.started', 'item': command})
    renderer.event({'type': 'item.completed', 'item': {
        'type': 'agent_message', 'text': '**Checking results**'}})
    renderer.event({'type': 'item.completed', 'item': {
        **commands[1], 'aggregated_output': 'if fault:\n    raise EvidenceError()\n',
        'exit_code': 0}})
    renderer.event({'type': 'item.completed', 'item': {
        **commands[0], 'aggregated_output': '\033[2J[bold]failure[/bold]', 'exit_code': 2}})
    # Interleaved results repeat their command context, without panel chrome.
    plain = Text.from_ansi(stream.getvalue()).plain
    assert '╭' not in plain and 'Result ·' not in plain and '• Agent' not in plain
    assert 'Exit 2' in plain and 'Exit 0' not in plain
    assert 'Checking results' in plain
    for hidden in ('if fault:', 'EvidenceError'):
        assert hidden not in plain
    assert '[bold]failure[/bold]' in plain
    assert plain.count('Read first.py') == plain.count('Read second.py') == 2
    assert '**' not in plain and '\033[2J' not in stream.getvalue()
    assert all(len(line) <= width for line in plain.splitlines()), repr(plain)


def test_agent_transcript_renders_empty_completed_command_without_start_event():
    from launcher_render import AgentRenderer
    from rich.text import Text
    stream = io.StringIO()
    AgentRenderer(stream).event({'type': 'item.completed', 'item': {
        'id': 'empty', 'type': 'command_execution', 'command': 'true',
        'aggregated_output': '', 'exit_code': 0}})
    plain = Text.from_ansi(stream.getvalue()).plain
    assert plain.strip() == '• Ran true'
    assert '(no output)' not in plain


@pytest.mark.parametrize('width', [40, 60, 100])
@pytest.mark.parametrize('term', ['dumb', 'unknown', 'xterm-256color'])
def test_transcript_observer_preserves_message_alignment_at_terminal_width(monkeypatch, width, term):
    from launcher_render import AgentRenderer, TranscriptWriter
    from rich.text import Text
    monkeypatch.setenv('TERM', term)
    source = io.StringIO()
    paragraphs = [
        'The **launcher** output keeps wrapped text aligned beneath the first word '
        'while preserving café and 日本語 in the retained transcript.',
        'The next paragraph uses the same indentation and keeps its blank separator.',
    ]
    AgentRenderer(source).event({'type': 'item.completed', 'item': {
        'type': 'agent_message', 'text': '\n\n'.join(paragraphs)}})
    output = io.StringIO()
    monkeypatch.setattr(output, 'isatty', lambda: True)
    monkeypatch.setattr(output, 'fileno', lambda: 123)
    monkeypatch.setattr(detached_launcher.os, 'get_terminal_size',
                        lambda fd: detached_launcher.os.terminal_size((width, 24)))
    writer = TranscriptWriter(output)
    # Observer reads may split ANSI sequences or fall in the middle of a row.
    for char in source.getvalue():
        writer.write(char)
    writer.write('', final=True)
    rendered = Text.from_ansi(output.getvalue())
    lines = rendered.plain.splitlines()
    content = [line for line in lines if line.strip()]
    assert content[0].startswith('• The launcher')
    assert all(line.startswith('  ') and not line.startswith('   ')
               for line in content[1:]), repr(rendered.plain)
    assert all(Text(line).cell_len <= width for line in lines)
    assert ' '.join(rendered.plain.split()) == (
        '• ' + ' '.join(' '.join(paragraphs).replace('**', '').split()))
    next_paragraph = next(i for i, line in enumerate(lines) if 'The next paragraph' in line)
    assert not lines[next_paragraph - 1].strip()
    start = rendered.plain.index('launcher')
    assert any(span.start <= start < span.end and span.style.bold for span in rendered.spans)


def test_agent_transcript_hides_reasoning_but_keeps_user_facing_updates():
    from launcher_render import AgentRenderer
    from rich.text import Text
    stream = io.StringIO()
    renderer = AgentRenderer(stream)
    for kind in ('item.started', 'item.updated', 'item.completed'):
        renderer.event({'type': kind, 'item': {
            'type': 'reasoning', 'text': 'Internal deliberation'}})
    assert stream.getvalue() == ''
    renderer.event({'type': 'item.completed', 'item': {
        'type': 'agent_message', 'text': 'Checking the renderer.'}})
    assert 'Checking the renderer.' in Text.from_ansi(stream.getvalue()).plain


@pytest.mark.parametrize('command', ['example --check', "/bin/bash -lc 'example --check'"])
@pytest.mark.parametrize('output', ['', 'short result', '\n'.join(
    f'if value == {number}: return True' for number in range(30))])
@pytest.mark.parametrize('exit_code', [0, 2])
def test_command_output_is_compact_and_retained(tmp_path, command, output, exit_code):
    from launcher_render import AgentRenderer
    from rich.text import Text
    stream = io.StringIO()
    archive = tmp_path / 'agent-commands.log'
    renderer = AgentRenderer(stream, command_log=archive)
    for identity in ('first', 'second'):
        renderer.event({'type': 'item.completed', 'item': {
            'id': identity, 'type': 'command_execution', 'command': command,
            'aggregated_output': output, 'exit_code': exit_code}})
    rendered = Text.from_ansi(stream.getvalue())
    if output:
        assert output.splitlines()[0] in rendered.plain
    if len(output.splitlines()) > 3:
        assert '+27 lines (agent-commands.log)' in rendered.plain
        assert output.splitlines()[2] in rendered.plain
        assert output.splitlines()[3] not in rendered.plain
        assert output.splitlines()[-1] not in rendered.plain
    assert ('Exit 2' in rendered.plain) == (exit_code == 2)
    assert 'Exit 0' not in rendered.plain
    assert '/bin/bash' not in rendered.plain
    retained = archive.read_text()
    assert retained == ''.join(
        f'\nCommand {identity}: {command}\n{output}\nExit: {exit_code}\n'
        for identity in ('first', 'second'))


@pytest.mark.parametrize('separator', ['\n', '\r\n', '\r'])
def test_command_preview_bounds_multiline_status_output(separator):
    from launcher_render import AgentRenderer
    from rich.text import Text
    stream = io.StringIO()
    output = separator.join([
        'Session started', 'Reattach instructions', '│',
        '│  Arbitrary scheduler status', '│    Arbitrary work progress',
    ])
    AgentRenderer(stream).event({'type': 'item.completed', 'item': {
        'id': 'status', 'type': 'command_execution', 'command': 'example',
        'aggregated_output': output, 'exit_code': 0}})
    rendered = Text.from_ansi(stream.getvalue()).plain
    assert 'Session started' in rendered
    assert 'Reattach instructions' in rendered
    assert 'Arbitrary' not in rendered
    assert '+2 lines' in rendered


def test_command_markdown_output_is_hidden_without_archive():
    from launcher_render import AgentRenderer
    from rich.text import Text
    stream = io.StringIO()
    AgentRenderer(stream).event({'type': 'item.completed', 'item': {
        'id': 'docs', 'type': 'command_execution', 'command': 'cat README.md',
        'aggregated_output': '**Instructions**\n\n```python\ndef fixed():\n    return True\n```',
        'exit_code': 0}})
    rendered = Text.from_ansi(stream.getvalue())
    assert 'Instructions' not in rendered.plain and 'def fixed():' not in rendered.plain
    assert '**' not in rendered.plain and '```' not in rendered.plain
    assert '• Explored' in rendered.plain and 'Read README.md' in rendered.plain


def test_compact_command_colors_and_wrapping():
    from launcher_render import AgentRenderer
    from rich.color import Color
    from rich.text import Text
    stream = io.StringIO()
    renderer = AgentRenderer(stream, width=40)
    renderer.event({'type': 'item.completed', 'item': {
        'id': 'links', 'type': 'command_execution',
        'command': '/bin/bash -lc "tools/read-only links \'tests/README.md\'"',
        'aggregated_output': 'links: documents=1 checked=31 missing=0', 'exit_code': 0}})
    rendered = Text.from_ansi(stream.getvalue())
    assert '• Ran tools/read-only' in rendered.plain
    assert '└ links:' in rendered.plain
    assert all(len(line) <= 40 for line in rendered.plain.splitlines()), repr(rendered.plain)
    for word, color in [('tools/read-only', 'bright_blue'), ("'tests/README.md'", 'green'),
                        ('links: documents', 'bright_black')]:
        start = rendered.plain.index(word)
        assert any(span.start <= start < span.end and
                   span.style.color.get_truecolor() == Color.parse(color).get_truecolor()
                   for span in rendered.spans if span.style.color)


def test_consecutive_exploration_is_grouped_and_messages_break_the_group():
    from launcher_render import AgentRenderer
    from rich.color import Color
    from rich.text import Text
    stream = io.StringIO()
    renderer = AgentRenderer(stream, width=50)
    for identity, command in enumerate([
            "rg -n '^## |^###' 'docs/Approval-Tools.md'",
            "cat 'tools/launcher_render.py' 'tests/unit/test_fix_tests.py'",
            "sed -n '1,20p' 'tests/README.md'"]):
        item = {'id': str(identity), 'type': 'command_execution', 'command': command}
        renderer.event({'type': 'item.started', 'item': item})
        renderer.event({'type': 'item.completed', 'item': {
            **item, 'exit_code': 0, 'aggregated_output': 'hidden contents'}})
    rendered = Text.from_ansi(stream.getvalue())
    text = rendered.plain
    assert text.count('• Explored') == 1
    assert 'Search ^## |^### in Approval-Tools.md' in text
    assert 'Read launcher_render.py, test_fix_tests.py' in text
    assert '    Read README.md' in text
    assert 'hidden contents' not in text and 'tools/' not in text
    for word, color in [('└', 'bright_black'), ('Search', '#0066ff'),
                        ('^## |^###', '#24292f'), (' in ', 'bright_black'),
                        ('Approval-Tools.md', '#24292f'),
                        ('launcher_render.py', '#24292f'), ('README.md', '#24292f')]:
        start = text.index(word)
        expected = Color.parse(color).get_truecolor()
        assert all(rendered.get_style_at_offset(renderer.console, offset).color.get_truecolor()
                   == expected for offset in range(start, start + len(word)))
    renderer.event({'type': 'item.completed', 'item': {
        'type': 'agent_message', 'text': 'Checking.'}})
    renderer.event({'type': 'item.completed', 'item': {
        **item, 'id': 'next', 'exit_code': 0}})
    assert Text.from_ansi(stream.getvalue()).plain.count('• Explored') == 2


@pytest.mark.parametrize('command', ['cat file; touch other', 'rg word file && build',
                                    'cat $(command)', 'cat `command`'])
def test_compound_commands_are_not_hidden_as_exploration(command):
    from launcher_render import AgentRenderer
    assert AgentRenderer(io.StringIO()).exploration({'command': command}) is None


def test_diff_has_syntax_colors_line_numbers_and_changed_backgrounds():
    from launcher_render import AgentRenderer
    from rich.text import Text
    stream = io.StringIO()
    AgentRenderer(stream, width=40).event({'type': 'item.completed', 'item': {
        'type': 'file_change', 'status': 'completed', 'changes': [{
            'kind': 'update', 'path': 'example.py',
            'diff': '@@ -95,2 +70,2 @@\n-    return "old"\n+    return "new"\n     pass'}]}})
    text = Text.from_ansi(stream.getvalue())
    assert '95 - ' in text.plain and '70 + ' in text.plain and '71   ' in text.plain
    backgrounds = {span.style.bgcolor.get_truecolor() for span in text.spans if span.style.bgcolor}
    assert (255, 235, 233) in backgrounds and (218, 251, 225) in backgrounds
    assert any(span.style.color for span in text.spans
               if text.plain[span.start:span.end].strip() == 'return')


def test_follow_keeps_unicode_across_reads_and_reattaches_at_complete_lines(tmp_path, monkeypatch):
    run = tmp_path / 'run'
    run.mkdir()
    original = 'x' * 65535 + 'é\n\033[32mretained café\033[0m\n'
    (run / 'output').write_text(original)
    fix_tests.atomic(run / 'result.json', {'status': 0})
    output = io.StringIO()
    assert fix_tests.follow(run, output) == 0
    assert output.getvalue() == original
    monkeypatch.setattr(detached_launcher, 'TAIL_BYTES', len('é\n\033[32mretained café\033[0m\n'.encode()) - 1)
    output = io.StringIO()
    assert fix_tests.follow(run, output) == 0
    assert output.getvalue() == '\033[32mretained café\033[0m\n'


@pytest.mark.parametrize('tty', [False, True])
def test_follow_refreshes_retained_frames_and_preserves_logs(tmp_path, monkeypatch, tty):
    from launcher_progress import publish_progress
    monkeypatch.setenv('TERM', 'xterm-256color')
    run = tmp_path / 'run'
    run.mkdir()
    (run / 'output').write_text('category started\n')
    fix_tests.atomic(run / 'frame.json', ['Overall - 0%'])
    publish_progress(run, 'test', ['Round 1: Category: unit (1/4)', 'Status: Running tests'])
    fix_tests.atomic(run / 'test-controller.json', [
        {'key': 'unit', 'lines': ['Category: unit (1/1) | Overall - 0%']}])
    fix_tests.atomic(run / 'result.json', {'status': 0})
    monkeypatch.setattr(detached_launcher, 'current_run', lambda _: run)
    monkeypatch.setattr(detached_launcher, 'busy', lambda _: True)
    polls = 0

    def advance(_):
        nonlocal polls
        polls += 1
        if polls == 1:
            fix_tests.atomic(run / 'frame.json', ['Overall - 50%'])
            fix_tests.atomic(run / 'test-controller.json', [
                {'key': 'unit', 'lines': ['Category: unit (1/1) | Overall - 50%']}])
        elif polls == 3:
            fix_tests.atomic(run / 'frame.json', [])
            (run / 'output').write_text('category started\nfinal summary\n')
            monkeypatch.setattr(detached_launcher, 'busy', lambda _: False)

    monkeypatch.setattr(detached_launcher.time, 'sleep', advance)
    output = io.StringIO()
    monkeypatch.setattr(output, 'isatty', lambda: tty)
    assert fix_tests.follow(run, output) == 0
    text = output.getvalue()
    assert 'category started' in text and 'final summary' in text
    assert 'Overall - 0%' in text and 'Overall - 50%' in text
    from rich.text import Text
    assert 'Round 1: Category: unit (1/4) | Overall - 50%' in Text.from_ansi(text).plain
    assert 'Status: Running tests' in text
    if tty:
        assert text.count('\033[?1049h') == text.count('\033[?1049l') == 1
        assert text.index('final summary') < text.index('\033[?1049l')
    else:
        assert text.count('Overall - 50%') == 1
        assert '\033[?1049' not in text


def test_repair_status_replaces_failed_category_and_retry(tmp_path):
    from launcher_progress import publish_repair_status, read_progress

    categories = ['unit', 'e2e']
    publish_repair_status(tmp_path, 1, 'e2e', categories, 'Running tests')
    summary = 'Category: e2e (1/1) | Overall - 41% (9/1/24) | Shutdown finished'
    fix_tests.atomic(tmp_path / 'test-controller.json', [
        {'key': 'e2e', 'lines': [summary]}])
    for model, effort in fix_tests.REPAIR_TIERS:
        publish_repair_status(tmp_path, 1, '', categories, 'fixing errors',
                              model=model, effort=effort)
        steps = read_progress(tmp_path)
        assert len(steps) == 1
        assert steps[0]['lines'] == [
            'Round 1: Category: e2e (2/2) | ' + summary.partition(' | ')[2],
            f'Status: fixing errors ({model} {effort})']
    fix_tests.atomic(tmp_path / 'test-controller.json', [])
    publish_repair_status(tmp_path, 1, 'e2e', categories, 'Running tests')
    assert len(read_progress(tmp_path)) == 1
    assert read_progress(tmp_path)[0]['lines'] == [
        'Round 1: Category: e2e (2/2)', 'Status: Running tests']
    publish_repair_status(tmp_path, 2, 'all', categories, 'Running tests')
    assert len(read_progress(tmp_path)) == 2


def test_granular_inventory_order_excludes_every_duplicate_helper():
    inventory = test_commands.suite_inventory()
    assert list(inventory)[:2] == ['unit', 'ui']
    assert list(inventory)[-2:] == ['system', 'e2e']
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
    assert list(inventory)[-3:] == ['future-suite', 'system', 'e2e']
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


def test_new_category_failure_has_a_runnable_handoff(tmp_path, monkeypatch):
    monkeypatch.setitem(test_commands.CATEGORIES, 'future-suite',
                        test_commands.CategorySpec('New implemented suite'))
    monkeypatch.setattr(regression_selection, 'source_identity', lambda _: 'fixed')
    monkeypatch.setattr(regression, 'source_identity', lambda _: 'fixed')
    monkeypatch.setattr(regression.Control, 'run', lambda *_args, **_kwargs: 1)
    assert regression.retained_main(tmp_path, selections=[('future-suite', [])]) == 1
    report, = (tmp_path / 'output/test-runs/host/reports').iterdir()
    assert json.loads((report / 'failure.json').read_text())['categories'] == ['future-suite']


def test_stop_on_error_reaches_the_selected_coordinator(monkeypatch):
    run = Mock(return_value=7)
    monkeypatch.setattr(regression, 'main', run)
    assert test_commands._main(['--stop-on-error', 'unit'], detached=True) == 7
    run.assert_called_once_with(ROOT, selections=[('unit', [])], stop_on_error=True)
    with pytest.raises(ValueError):
        test_commands.validate(ROOT, ['--stop-on-error', 'all', '--continue-on-errors'])


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
