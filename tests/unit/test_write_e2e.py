"""Task selection, handoff boundaries and fail-closed completion."""
from tests.support.vm_registry import vm_name

import subprocess
import json
import tomllib

import pytest

import write_e2e as workflow
from tests.support.write_e2e_fixtures import prepare, reply, prerequisite_writes


@pytest.mark.parametrize('phase', ['implement', 'live', 'recover'])
def test_sequential_adviser_config_preserves_coordinator_and_transport_boundaries(tmp_path, monkeypatch, phase):
    monkeypatch.setattr(workflow.launcher.shutil, 'which', lambda _: '/opt/codex')
    # Parse the actual CLI overrides as TOML, including a path containing spaces.
    adviser = tmp_path / 'adviser with spaces.toml'
    adviser.write_bytes(workflow.ADVISER_CONFIG.read_bytes())
    monkeypatch.setattr(workflow, 'ADVISER_CONFIG', adviser)
    command = workflow.session_command(tmp_path, phase)
    config = tomllib.loads('\n'.join(command[i + 1] for i, arg in enumerate(command) if arg == '-c'))
    assert command[command.index('--model') + 1] == 'gpt-6.1-sol'
    assert config['model_reasoning_effort'] == 'high'
    assert config['service_tier'] == 'default'
    assert config['features']['fast_mode'] is False
    assert config['features']['multi_agent'] is True
    assert config['features']['multi_agent_v2'] is False
    assert config['agents']['enabled'] is True
    assert config['agents']['max_concurrent_threads_per_session'] == 1
    assert config['agents']['max_depth'] == 1
    assert config['agents']['default_subagent_model'] == 'gpt-6-astra'
    assert config['agents']['default_subagent_reasoning_effort'] == 'high'
    assert config['agents']['e2e_adviser']['config_file'] == str(adviser)
    role = tomllib.loads(adviser.read_text())
    assert role['model'] == 'gpt-6-astra'
    assert role['service_tier'] == 'default' and role['features']['fast_mode'] is False
    assert 'model_reasoning_effort' not in role  # Inherit the bounded adviser's requested effort.
    assert role['sandbox_mode'] == 'read-only' and role['approval_policy'] == 'never'
    assert role['agents']['enabled'] is False
    assert role['features']['multi_agent'] is role['features']['multi_agent_v2'] is False
    assert role['features']['memories'] is False
    assert role['history']['persistence'] == 'none'
    assert 'Do not edit files, run tests/builds, control the VM' in role['developer_instructions']
    assert command[-1] == '-' and '--ephemeral' in command


@pytest.mark.parametrize('phase,attempts,model,effort', [
    ('implement', 0, 'gpt-6.1-sol', 'high'),
    ('live', 1, 'gpt-6.1-sol', 'high'),
    ('live', 2, 'gpt-6.1-sol', 'high'),
    ('recover', 0, 'gpt-6.1-sol', 'high'),
    ('recover', 2, 'gpt-6.1-sol', 'high'),
    ('recover', 5, 'gpt-6.1-sol', 'high'),
])
def test_command_and_prompt_keep_high_independent_of_attempt_count(tmp_path, monkeypatch,
                                                          phase, attempts, model, effort):
    monkeypatch.setattr(workflow.launcher.shutil, 'which', lambda _: '/opt/codex')
    command = workflow.session_command(tmp_path, phase, tmp_path, live_attempts=attempts)
    config = tomllib.loads('\n'.join(command[i + 1] for i, arg in enumerate(command) if arg == '-c'))
    assert command[command.index('--model') + 1] == model
    assert config['model_reasoning_effort'] == effort
    assert config['features']['multi_agent'] is True
    assert config['agents']['max_concurrent_threads_per_session'] == 1
    assert '--output-schema' in command and '--ephemeral' in command
    state = dict(workflow.fresh_state('001'), phase=phase, live_attempts=attempts,
                 task_sessions=20)  # Session count/preparation alone must not escalate.
    prompt = workflow.session_prompt(state)
    label = f'GPT-6.1-Sol {effort.title()}'
    assert f'You are the {label} coordinator' in prompt
    assert 'Consult before implementing such an unresolved\nrisky design' in prompt
    assert 'e2e_adviser agent' in prompt
    assert 'Prefer GPT-6.1-Sol High over Astra Low' in prompt
    assert 'Never use Sol High' not in prompt
    assert 'Leave investigation and repairs of this new failure to the next session' in prompt


@pytest.mark.parametrize('phase', ['live', 'recover'])
def test_follow_up_keeps_implementation_and_acceptance_with_sol_high(phase):
    state = dict(workflow.fresh_state('001'), phase=phase,
                 handoff='Legacy recommendation: continue with Astra High.')
    prompt = workflow.session_prompt(state)
    assert 'GPT-6.1-Sol High coordinator and implementer for this session' in prompt
    assert 'Prefer GPT-6.1-Sol High over Astra Low' in prompt
    assert 'Ignore model recommendations in older handoffs' in prompt
    assert 'or review to the e2e_adviser agent using GPT-6-Astra High only when' in prompt
    assert 'No parallel agents or overlapping work' in prompt
    assert 'close it before resuming your work' in prompt
    assert 'You alone implement the settled correction, run all validation' in prompt
    assert 'advice is not acceptance evidence' in prompt
    assert 'Leave investigation and repairs of this new failure to the next session' in prompt


def test_adviser_requires_evidence_and_retains_findings_across_handoffs():
    prompt = workflow.session_prompt(dict(workflow.fresh_state('001'), phase='recover',
        handoff='Prior question: ownership race. Finding: missing lease. Correction: hold the lease.'))
    for rule in ('failed verification without improving the explanation',
                 'conflicting evidence prevents', 'State the concrete escalation reason',
                 'alone do not justify Astra', 'another consultation requires materially new evidence',
                 'restart does not repeat the same consultation', 'No Extra High step is required'):
        assert rule in prompt
    assert 'Prior question: ownership race.' in prompt
    role = tomllib.loads(workflow.ADVISER_CONFIG.read_text())
    assert 'Do not repeat a prior\nconsultation without materially new evidence' in role['developer_instructions']


def test_usage_retains_only_reported_nonnegative_counters_without_estimated_billing(tmp_path):
    metadata = {'session': 1, 'task_id': '001', 'model': 'gpt-6.1-sol'}
    workflow.record_usage(tmp_path, metadata, {'input_tokens': 100, 'cached_input_tokens': 80,
                          'output_tokens': 20, 'reasoning_output_tokens': 12, 'unknown': 'private'})
    workflow.record_usage(tmp_path, dict(metadata, session=2),
                          {'input_tokens': True, 'output_tokens': -1, 'cached_input_tokens': '80'})
    workflow.record_usage(tmp_path, dict(metadata, session=3), None)
    records = [json.loads(line) for line in (tmp_path / 'agent-usage.jsonl').read_text().splitlines()]
    assert records[0] == dict(metadata, reported_scope='cli_turn', usage={
        'input_tokens': 100, 'cached_input_tokens': 80,
        'output_tokens': 20, 'reasoning_output_tokens': 12})
    assert records[1]['usage'] is records[2]['usage'] is None
    assert [record['session'] for record in records] == [1, 2, 3]


def test_usage_write_failure_does_not_interrupt_work(tmp_path, capsys):
    (tmp_path / 'agent-usage.jsonl').mkdir()
    workflow.record_usage(tmp_path, {'session': 1}, {'input_tokens': 100})
    assert 'could not retain token usage' in capsys.readouterr().err


def test_usage_refuses_a_replaced_destination(tmp_path, capsys):
    unrelated = tmp_path / 'unrelated'
    unrelated.write_text('preserve this')
    (tmp_path / 'agent-usage.jsonl').symlink_to(unrelated)
    workflow.record_usage(tmp_path, {'session': 1}, {'input_tokens': 100})
    assert unrelated.read_text() == 'preserve this'
    assert 'could not retain token usage' in capsys.readouterr().err


def test_usage_does_not_wait_for_another_writer(tmp_path, capsys):
    import fcntl
    with workflow.launcher.lock(tmp_path / 'agent-usage.jsonl') as owner:
        fcntl.flock(owner, fcntl.LOCK_EX)
        workflow.record_usage(tmp_path, {'session': 1}, {'input_tokens': 100})
    assert (tmp_path / 'agent-usage.jsonl').read_text() == ''
    assert 'could not retain token usage' in capsys.readouterr().err


@pytest.mark.parametrize(('seconds', 'expected'), [
    (29, '0 minutes'),
    (30, '1 minute'),
    (3599, '60 minutes'),
    (3600, '1 hour 0 minutes'),
    (5430, '1 hour 31 minutes'),
    (7200, '2 hours 0 minutes'),
])
def test_duration_format(seconds, expected):
    assert workflow.format_duration(seconds) == expected


@pytest.mark.parametrize(('seconds', 'expected'), [
    (29, '0m'), (30, '1m'), (720, '12m'), (3599, '60m'),
    (3600, '1h 0m'), (5430, '1h 31m'), (7200, '2h 0m'),
])
def test_compact_duration_format(seconds, expected):
    assert workflow.format_duration(seconds, short=True) == expected


@pytest.mark.parametrize(('phase', 'attempts', 'summary'), [
    ('implement', 0, 'Writing task code + host validation + first live VM test; close on success, hand off on failure'),
    ('recover', 0, 'Investigate/fix previous failure + host validation + live VM test 1; close on success, hand off on failure'),
    ('live', 0, 'Investigate/fix previous failure + host validation + live VM test 1; close on success, hand off on failure'),
    ('live', 2, 'Investigate/fix previous failure + host validation + live VM test 3; close on success, hand off on failure'),
])
def test_session_controller_reports_task_title_and_phase(tmp_path, phase, attempts, summary):
    from rich.text import Text
    prepare(tmp_path)
    state = dict(workflow.fresh_state('001'), phase=phase, live_attempts=attempts,
                 task_sessions=2)
    assert [Text.from_ansi(line).plain for line in workflow.session_progress(tmp_path, state, 5)] == [
        'Task 001: First', f'Session [2]: {summary} (gpt-6.1-sol high)']


def test_current_task_recap_refreshes_and_freezes_at_completion(tmp_path, monkeypatch):
    from rich.console import Console
    from rich.text import Text
    state = dict(workflow.fresh_state('001'), started_at=1000,
                 task_sessions=2, progress_keys=['1', '2'])
    steps = [{'key': '2', 'lines': ['Task 001: First', 'Session [2]: Working']}]
    workflow.launcher.atomic(tmp_path / 'checkpoint.json', state)
    monkeypatch.setattr(workflow.time, 'time', lambda: 1120)
    rendered = workflow.task_progress(tmp_path, steps)
    text = Text.from_ansi(rendered[-1]['lines'][0])
    assert text.plain == 'Task 001: First (sessions=2, duration=2m)'
    assert text.get_style_at_offset(Console(), 0).color.get_truecolor().hex == '#0066ff'
    assert text.get_style_at_offset(Console(), text.plain.index('sessions=')).color.get_truecolor().hex == '#0066ff'
    monkeypatch.setattr(workflow.time, 'time', lambda: 1180)
    assert Text.from_ansi(workflow.task_progress(tmp_path, steps)[-1]['lines'][0]).plain.endswith('duration=3m)')
    state.update(task_sessions=3)
    workflow.launcher.atomic(tmp_path / 'checkpoint.json', state)
    assert '(sessions=3,' in workflow.task_progress(tmp_path, steps)[-1]['lines'][0]
    state.update(phase='complete', completed_at=1180)
    workflow.launcher.atomic(tmp_path / 'checkpoint.json', state)
    monkeypatch.setattr(workflow.time, 'time', lambda: 1300)
    assert workflow.task_progress(tmp_path, steps)[-1]['lines'][0].endswith(
        f"duration={workflow.format_duration(180, short=True)})")
    assert steps[-1]['lines'][0] == 'Task 001: First'
    previous = dict(steps[0], key='1')
    rolling = workflow.task_progress(tmp_path, [previous, *steps])
    assert rolling[0]['lines'][0] == rolling[1]['lines'][0]
    completed = [{'key': 'complete-001', 'lines': ['Completed recap'], 'replaces': ['2']}]
    assert workflow.task_progress(tmp_path, completed) == completed


@pytest.mark.parametrize('prerequisite_started', [False, True])
def test_suspended_consumer_does_not_show_an_ongoing_session(tmp_path, prerequisite_started):
    from rich.console import Console
    from rich.text import Text
    prepare(tmp_path)
    consumer = dict(workflow.fresh_state('001'), task_sessions=2,
                    started_at=1000, progress_keys=['1', '2'])
    insert_prerequisite(tmp_path)
    selected = workflow.defer_to_prerequisite(tmp_path, consumer)
    completed = {'key': 'complete-previous', 'lines': ['Previously completed'],
                 'replaces': ['0']}
    steps = [completed, *[
        {'key': str(index), 'lines': workflow.session_progress(tmp_path, dict(consumer, task_sessions=index), index)}
        for index in (1, 2)]]
    if prerequisite_started:
        selected.update(started_at=1000, task_sessions=1, progress_keys=['3'])
        steps.append({'key': '3', 'lines': workflow.session_progress(tmp_path, selected, 3)})
    workflow.launcher.atomic(tmp_path / 'checkpoint.json', selected)
    original = json.dumps(steps)
    rendered = workflow.task_progress(tmp_path, steps)
    assert rendered[0] == completed
    assert len(rendered[1]['lines']) == 1
    suspended = Text.from_ansi(rendered[1]['lines'][0])
    assert suspended.plain == 'Task 001: First — Suspended for prerequisite'
    assert suspended.get_style_at_offset(Console(), 0).color.get_truecolor().hex == '#808080'
    assert suspended.get_style_at_offset(Console(), len(suspended.plain) - 1).color.get_truecolor().hex == '#808080'
    if prerequisite_started:
        for line in rendered[-1]['lines']:
            ongoing = Text.from_ansi(line)
            for offset in range(len(ongoing.plain)):
                assert ongoing.get_style_at_offset(Console(), offset).color.get_truecolor().hex == '#0066ff'
    assert sum('Session [' in line for step in rendered for line in step['lines']) == int(prerequisite_started)
    assert json.dumps(steps) == original
    # Resumption restores the original session display; the overlay is not durable.
    workflow.launcher.atomic(tmp_path / 'checkpoint.json', consumer)
    assert Text.from_ansi(workflow.task_progress(tmp_path, steps)[1]['lines'][1]).plain == Text.from_ansi(steps[1]['lines'][1]).plain


def test_final_handoff_uses_session_colors_and_preserves_saved_prompt(tmp_path, capsys):
    from rich.console import Console
    from rich.text import Text
    state = dict(workflow.fresh_state('024'),
                 summary='Checked `tools/watchvm`.',
                 handoff='Read [the guide](https://example.com/guide).\n\n'
                         '```bash\ntools/write-e2e --sessions 3\n```')
    workflow.save_handoff(tmp_path, state, 'stopped')
    output = capsys.readouterr().out
    rendered = Text.from_ansi(output)
    assert '• Task 024: stopped.' in rendered.plain
    assert 'Next session prompt:' in rendered.plain
    assert '```' not in rendered.plain and '`tools/watchvm`' not in rendered.plain
    for token, color in [('tools/watchvm', '#008000'), ('the guide', '#0066ff'),
                         ('tools/write-e2e', '#0066ff'), ('--sessions', '#ff0000')]:
        offset = rendered.plain.index(token)
        style = rendered.get_style_at_offset(Console(), offset)
        assert style.color.get_truecolor().hex == color
    saved = (tmp_path / 'handoff.txt').read_text()
    assert state['handoff'] in saved and '\x1b' not in saved
    assert json.loads((tmp_path / 'checkpoint.json').read_text()) == state


def test_implementation_prompt_preserves_requested_boundary():
    prompt = workflow.session_prompt(workflow.fresh_state('001'))
    assert prompt.startswith(workflow.INITIAL_PROMPT)
    assert 'Implement this task and complete host validation' in prompt
    assert "run this task's live VM acceptance" in prompt
    assert 'Leave investigation and repairs of this new failure to the next session' in prompt
    assert 'task_complete with live_result passed' in prompt
    assert 'The launcher owns staging' in prompt
    assert 'Do not analyze staged' in prompt
    assert 'Do not commit' in prompt
    assert 'tools/run-tests' in prompt


@pytest.mark.parametrize('phase', ['implement', 'live', 'recover'])
def test_missing_qualification_inputs_are_repaired_without_a_developer_question(phase):
    prompt = workflow.session_prompt(dict(workflow.fresh_state('030a'), phase=phase))
    assert 'tools/prepare-baseline --vm NAME --mode auto --y' in prompt
    assert 'omit it for manual work' in prompt
    assert 'prepare missing named inputs, then resume validation' in prompt
    assert 'in this session without asking the developer' in prompt
    assert 'A preparation failure before VM access is not a failed live VM attempt' in prompt
    assert 'Repair authorized preparation\ndefects and retry preparation' in prompt
    assert 'Do not ask whether to perform an already-authorized repair' in prompt
    assert 'unresolved product behavior/expectations, missing authority' in prompt
    assert 'Never infer permission to bypass a denied grant or overwrite unrelated inputs' in prompt
    assert 'If a prerequisite or unresolved blocker prevents' not in prompt


@pytest.mark.parametrize('phase', ['implement', 'live', 'recover'])
@pytest.mark.parametrize('attempts', [0, 1, 2])
def test_every_session_ends_at_validation_before_new_repairs(phase, attempts):
    state = dict(workflow.fresh_state('001'), phase=phase, live_attempts=attempts)
    prompt = workflow.session_prompt(state)
    validation = prompt.index("After host checks pass, run this task's live VM acceptance")
    if phase != 'implement':
        assert prompt.index('Start by investigating the previous VM validation error') < validation
        assert prompt.index('repair authorized defects') < validation
        assert prompt.index('complete host validation') < validation
    assert prompt.index('If live acceptance fails') > validation
    assert 'Leave investigation and repairs of this new failure to the next session' in prompt
    assert 'finish live VM validation\nwith a passed or failed result' in prompt
    assert 'Do not run live VM tests' not in prompt
    assert 'return ready_for_vm with live_result not_run' not in prompt


def test_only_latest_handoff_crosses_into_each_live_retry(tmp_path):
    prepare(tmp_path)
    state = workflow.fresh_state('001')
    _, before = workflow.queue_state(tmp_path)
    state = workflow.accept_result(tmp_path, state, reply(handoff='CURRENT HANDOFF'), before)
    prompt = workflow.session_prompt(state)
    assert 'Start by investigating the previous VM validation error' in prompt
    assert 'unstaged code (including new files)' in prompt
    assert 'CURRENT HANDOFF' in prompt
    state = workflow.accept_result(tmp_path, state, reply(live='failed', handoff='LATEST REPAIR'), before)
    prompt = workflow.session_prompt(state)
    assert state['live_attempts'] == 2
    assert 'Start by investigating the previous VM validation error' in prompt
    assert 'LATEST REPAIR' in prompt and 'CURRENT HANDOFF' not in prompt


@pytest.mark.parametrize('phase, in_flight', [('blocked', False), ('live', True), ('live', False)])
def test_task_restart_inherits_only_its_own_consumed_sessions(tmp_path, monkeypatch, phase, in_flight):
    prepare(tmp_path)
    previous = tmp_path / 'previous-run'
    previous.mkdir()
    state = dict(workflow.fresh_state('001'), phase=phase, in_flight=in_flight,
                 live_attempts=1, task_sessions=2, total_sessions=6,
                 handoff='Previous baseline requirement blocked setup.')
    (previous / 'checkpoint.json').write_text(json.dumps(state))
    monkeypatch.setattr(workflow.launcher, 'current_run', lambda _directory: previous)
    restarted = workflow.initial_state(tmp_path, tmp_path)
    expected = dict(state, total_sessions=2, task_session_limit=7)
    if in_flight:
        expected.update(phase='recover', in_flight=False, recovery_run=str(previous))
    assert restarted == expected
    prompt = workflow.session_prompt(restarted)
    if expected['phase'] == 'recover':
        assert 'current source/evidence' in prompt and workflow.PLAN in prompt
        assert "run this task's live VM acceptance" in prompt
        assert str(previous) in prompt
    assert workflow.queue_state(tmp_path)[0] == '001'


@pytest.mark.parametrize('blocker', [None, {}, {'explanation': 'x', 'question': 'q', 'options': ['a']},
                                    {'explanation': 'x', 'question': 'q', 'options': ['a', 'a']},
                                    {'explanation': 'x' * 2001, 'question': 'q', 'options': ['a', 'b']}])
def test_blocked_result_requires_a_bounded_actionable_question(tmp_path, blocker):
    prepare(tmp_path)
    _, before = workflow.queue_state(tmp_path)
    with pytest.raises(ValueError, match='concise explanation'):
        workflow.accept_result(tmp_path, workflow.fresh_state('001'), reply('blocked', blocker=blocker), before)


def test_user_answer_is_given_to_recovery_without_losing_handoff():
    state = dict(workflow.fresh_state('001'), phase='recover', handoff='Exact retained evidence.',
                 user_answer={'question': 'Which duration?', 'answer': 'Keep compact durations.'})
    prompt = workflow.session_prompt(state)
    assert 'Keep compact durations.' in prompt
    assert 'Exact retained evidence.' in prompt
    assert 'an answer alone is not evidence that it passed' in prompt


def test_only_first_current_question_answer_is_accepted(tmp_path):
    from launcher_question import submit
    question = dict(reply('blocked')['blocker'], id='current', answer=None)
    workflow.launcher.atomic(tmp_path / 'question.json', question)
    assert not submit(tmp_path, 'stale', 0)
    with pytest.raises(ValueError):
        submit(tmp_path, 'current', 3, ' ')
    with pytest.raises(ValueError):
        submit(tmp_path, 'current', -1)
    assert submit(tmp_path, 'current', 3, 'Keep the current format; review its checks.')
    assert not submit(tmp_path, 'current', 1)
    saved = json.loads((tmp_path / 'question.json').read_text())
    assert saved['answer'] == 'Keep the current format; review its checks.'


def test_simultaneous_observers_accept_exactly_one_answer(tmp_path):
    from concurrent.futures import ThreadPoolExecutor
    from launcher_question import submit
    workflow.launcher.atomic(tmp_path / 'question.json', dict(reply('blocked')['blocker'], id='q', answer=None))
    with ThreadPoolExecutor(max_workers=2) as pool:
        answers = list(pool.map(lambda option: submit(tmp_path, 'q', option), [0, 1]))
    assert sorted(answers) == [False, True]


@pytest.mark.parametrize('choice', [0, 1, 2])
def test_answer_transcript_preserves_selection_and_custom_text(tmp_path, monkeypatch, capsys, choice):
    from launcher_question import QuestionInput, submit
    from rich.text import Text

    state = dict(workflow.fresh_state('001'), blocker_id='q', blocker={
        'explanation': 'A decision is needed.', 'question': 'How should we continue?',
        'options': ['Repair', 'Review']})
    custom = 'Keep café and review the checks.'

    def answer(_delay):
        waiting = Text.from_ansi(capsys.readouterr().out).plain
        assert '1. Repair' in waiting
        assert '›' not in waiting
        assert submit(tmp_path, 'q', choice, custom)

    monkeypatch.setattr(workflow.time, 'sleep', answer)
    assert workflow.wait_for_answer(tmp_path, state, 'task')
    output = Text.from_ansi(capsys.readouterr().out).plain
    expected = custom if choice == 2 else ['Repair', 'Review'][choice]
    assert f'› {choice + 1}. {expected}' in output
    assert 'Answer submitted.' in output
    assert 'Waiting for your answer.' not in output
    assert state['user_answer']['answer'] == expected
    saved = json.loads((tmp_path / 'question.json').read_text())
    restored = QuestionInput(saved, lambda *_: pytest.fail('answered menu resubmitted'))
    assert restored.selected == choice
    assert restored.text == (custom if choice == 2 else '')
    restored.feed(b'1\r')
    assert restored.selected == choice


def test_restart_preserves_an_answer_before_owner_checkpoint(tmp_path, monkeypatch):
    prepare(tmp_path)
    previous = tmp_path / 'previous'
    previous.mkdir()
    state = dict(workflow.fresh_state('001'), phase='blocked', task_sessions=5, blocker_id='q')
    workflow.launcher.atomic(previous / 'checkpoint.json', state)
    workflow.launcher.atomic(previous / 'question.json', {
        'id': 'q', 'question': 'Which duration?', 'answer': 'Keep compact durations.'})
    monkeypatch.setattr(workflow.launcher, 'current_run', lambda _: previous)
    resumed = workflow.initial_state(tmp_path, tmp_path)
    assert resumed['phase'] == 'recover'
    assert resumed['user_answer']['answer'] == 'Keep compact durations.'
    assert not workflow.task_session_limit_reached(resumed)


@pytest.mark.parametrize('phase', ['implement', 'live', 'recover'])
@pytest.mark.parametrize('change', [
    {'task_id': '002'}, {'host_validated': False}, {'live_result': 'passed'},
    {'live_result': 'not_run'},
    {'handoff': ''}, {'status': 'made_up'}, {'host_validated': 'yes'},
])
def test_invalid_handoff_cannot_advance_in_any_session(tmp_path, phase, change):
    prepare(tmp_path)
    _, before = workflow.queue_state(tmp_path)
    with pytest.raises(ValueError):
        workflow.accept_result(tmp_path, dict(workflow.fresh_state('001'), phase=phase), reply(**change), before)


@pytest.mark.parametrize('phase', ['implement', 'live', 'recover'])
def test_completion_requires_live_success_and_queue_closeout(tmp_path, phase):
    prepare(tmp_path)
    state = dict(workflow.fresh_state('001'), phase=phase)
    _, before = workflow.queue_state(tmp_path)
    with pytest.raises(ValueError, match='completion'):
        workflow.accept_result(tmp_path, state, reply('task_complete', 'passed'), before)
    (tmp_path / workflow.QUEUE).write_text('| [x] | 001 | First |\n| [ ] | 002 | Second |\n')
    (tmp_path / workflow.PLAN).write_text('Next task: **002 — [Second](second.md)**.\n')
    result = workflow.accept_result(tmp_path, state, reply('task_complete', 'passed'), before)
    assert result['phase'] == 'complete'
    assert result['live_attempts'] == 1
    with pytest.raises(ValueError, match='completion'):
        workflow.accept_result(tmp_path, state, reply('task_complete', 'failed'), before)


@pytest.mark.parametrize('phase', ['implement', 'live', 'recover'])
def test_failed_vm_handoff_counts_attempt_without_advancing_queue(tmp_path, phase):
    prepare(tmp_path)
    state = dict(workflow.fresh_state('001'), phase=phase, live_attempts=2)
    _, before = workflow.queue_state(tmp_path)
    result = workflow.accept_result(tmp_path, state, reply(), before)
    assert result['phase'] == 'live' and result['live_attempts'] == 3
    assert workflow.queue_state(tmp_path) == ('001', before)


@pytest.mark.parametrize('phase', ['implement', 'live', 'recover'])
def test_blocked_host_validation_does_not_claim_vm_attempt(tmp_path, phase):
    prepare(tmp_path)
    _, before = workflow.queue_state(tmp_path)
    state = dict(workflow.fresh_state('001'), phase=phase, live_attempts=2)
    result = workflow.accept_result(tmp_path, state,
                                    reply('blocked', 'not_run', host_validated=False), before)
    assert result['phase'] == 'blocked' and result['live_attempts'] == 2
    assert workflow.queue_state(tmp_path) == ('001', before)


def test_queue_order_is_authoritative_and_deferred_tasks_are_excluded(tmp_path):
    prepare(tmp_path)
    (tmp_path / workflow.PLAN).write_text('Next task: **002 — [Second](second.md)**.\n')
    with pytest.raises(ValueError, match='first unchecked task 001'):
        workflow.queue_state(tmp_path)
    (tmp_path / workflow.QUEUE).write_text(
        '| [x] | 001 | First |\n| [x] | 002 | Second |\n'
        '## Deferred future work\n| [ ] | 999 | Deferred |\n')
    assert workflow.queue_state(tmp_path)[0] is None


def insert_prerequisite(root, no_dependencies='Baseline'):
    for name, content in prerequisite_writes(no_dependencies).items():
        path = root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content)


@pytest.mark.parametrize('no_dependencies', ['Baseline', '—', '-', ''])
def test_prerequisite_repair_suspends_consumer_without_acceptance_or_staging(tmp_path, no_dependencies):
    prepare(tmp_path)
    _, before = workflow.queue_state(tmp_path)
    state = dict(workflow.fresh_state('001'), task_sessions=3, live_attempts=2,
                 in_flight=True, stage_candidates=['partial.py'],
                 stage_baseline={'unrelated.py': 'original'}, progress_keys=['1'])
    insert_prerequisite(tmp_path, no_dependencies)
    selected = workflow.accept_result(tmp_path, state,
        reply('blocked', 'not_run', host_validated=False, handoff='Keep partial consumer work.'), before)
    assert selected['task_id'] == '000a' and selected['phase'] == 'implement'
    assert selected['task_sessions'] == selected['live_attempts'] == 0
    assert selected['stage_candidates'] == [] and not selected['in_flight']
    consumer = selected['suspended_tasks']['001']
    assert consumer['phase'] == 'recover' and not consumer['in_flight']
    assert consumer['task_sessions'] == 3 and consumer['live_attempts'] == 2
    assert consumer['stage_candidates'] == ['partial.py']
    assert consumer['stage_baseline'] == {'unrelated.py': 'original'}
    assert consumer['handoff'] == 'Keep partial consumer work.'
    assert workflow.select_task_state('001', selected) == consumer
    assert workflow.queue_state(tmp_path)[1] == {'000a': False, '001': False, '002': False}


@pytest.mark.parametrize('fault', ['unrelated', 'checked', 'missing-brief', 'forward-dependency',
                                  'unknown-dependency', 'mixed-baseline',
                                  'extra-row', 'reordered', 'live-failure'])
def test_prerequisite_exception_does_not_allow_skips_or_unrelated_queue_edits(tmp_path, fault):
    prepare(tmp_path)
    _, before = workflow.queue_state(tmp_path)
    insert_prerequisite(tmp_path)
    queue = tmp_path / workflow.QUEUE
    text = queue.read_text()
    if fault == 'unrelated':
        text = text.replace('| 000a | Consumer |', '| — | Consumer |')
    elif fault == 'checked':
        text = text.replace('| [ ] | 001 |', '| [x] | 001 |')
    elif fault == 'missing-brief':
        (tmp_path / 'docs/TestAutomation/E2E-Tasks/000a.md').unlink()
    elif fault == 'forward-dependency':
        text = text.replace('| Baseline | Setup |', '| 001 | Setup |')
    elif fault == 'unknown-dependency':
        text = text.replace('| Baseline | Setup |', '| missing | Setup |')
    elif fault == 'mixed-baseline':
        text = text.replace('| Baseline | Setup |', '| Baseline, 001 | Setup |')
    elif fault == 'extra-row':
        text += '| [ ] | extra | Extra | — | Extra |\n'
    elif fault == 'reordered':
        before = {'002': False, '001': False}
    queue.write_text(text)
    with pytest.raises(ValueError, match='incomplete task advanced'):
        workflow.accept_result(tmp_path, workflow.fresh_state('001'),
            reply('blocked', 'failed' if fault == 'live-failure' else 'not_run'), before)


@pytest.mark.parametrize('legacy', [False, True])
def test_restart_recovers_interrupted_prerequisite_insertion(tmp_path, monkeypatch, legacy):
    prepare(tmp_path)
    _, before = workflow.queue_state(tmp_path)
    previous = tmp_path / 'previous-run'
    previous.mkdir()
    state = dict(workflow.fresh_state('001'), in_flight=True, task_sessions=1,
                 stage_candidates=['partial.py'], handoff='Retained consumer work.', progress_keys=['1'])
    if not legacy:
        state['queue_before'] = before
    (previous / 'checkpoint.json').write_text(json.dumps(state))
    original_checkpoint = (previous / 'checkpoint.json').read_bytes()
    insert_prerequisite(tmp_path)
    monkeypatch.setattr(workflow.launcher, 'current_run', lambda _directory: previous)
    selected = workflow.initial_state(tmp_path, tmp_path)
    assert selected['task_id'] == '000a' and selected['phase'] == 'recover'
    assert selected['task_session_limit'] == 5 and selected['task_sessions'] == 0
    assert str(previous) in workflow.session_prompt(selected)
    consumer = selected['suspended_tasks']['001']
    assert consumer['task_sessions'] == 1 and consumer['stage_candidates'] == ['partial.py']
    assert 'progress_keys' not in consumer
    assert (previous / 'checkpoint.json').read_bytes() == original_checkpoint


def test_restart_still_refuses_unrelated_interrupted_queue_change(tmp_path, monkeypatch):
    prepare(tmp_path)
    previous = tmp_path / 'previous-run'
    previous.mkdir()
    (previous / 'checkpoint.json').write_text(json.dumps(dict(
        workflow.fresh_state('001'), in_flight=True)))
    insert_prerequisite(tmp_path)
    queue = tmp_path / workflow.QUEUE
    queue.write_text(queue.read_text().replace('| 000a | Consumer |', '| — | Consumer |'))
    monkeypatch.setattr(workflow.launcher, 'current_run', lambda _directory: previous)
    with pytest.raises(ValueError, match='interrupted task changed the queue'):
        workflow.initial_state(tmp_path, tmp_path)


def test_multiple_inserted_prerequisites_keep_consumer_across_launcher_boundaries(tmp_path, monkeypatch):
    prepare(tmp_path)
    _, before = workflow.queue_state(tmp_path)
    insert_prerequisite(tmp_path)
    queue = tmp_path / workflow.QUEUE
    queue.write_text(queue.read_text().replace(
        '| [ ] | 001 |', '| [ ] | 000b | [Second prerequisite](E2E-Tasks/000b.md) | 000a | Setup |\n| [ ] | 001 |'
    ).replace('| 000a | Consumer |', '| 000b | Consumer |'))
    (tmp_path / 'docs/TestAutomation/E2E-Tasks/000b.md').write_text('Qualify second prerequisite.\n')
    state = workflow.accept_result(tmp_path, dict(workflow.fresh_state('001'), task_sessions=2),
                                   reply('blocked', 'not_run'), before)
    previous = tmp_path / 'previous-run'
    previous.mkdir()
    state.update(phase='complete')
    (previous / 'checkpoint.json').write_text(json.dumps(state))
    queue.write_text(queue.read_text().replace('| [ ] | 000a |', '| [x] | 000a |'))
    (tmp_path / workflow.PLAN).write_text('Next task: **000b — Second prerequisite**.\n')
    monkeypatch.setattr(workflow.launcher, 'current_run', lambda _directory: previous)
    second = workflow.initial_state(tmp_path, tmp_path)
    assert second['task_id'] == '000b' and second['task_sessions'] == 0
    assert second['suspended_tasks']['001']['task_sessions'] == 2
    assert workflow.select_task_state('001', second)['task_sessions'] == 2


@pytest.mark.parametrize('task,prerequisites', [
    ('137bc', ('901a', '008zz', '650b')),
    ('007zz', ('850c', '120ab', '003q')),
])
@pytest.mark.parametrize('shape', ['single', 'chain', 'diamond', 'independent'])
@pytest.mark.parametrize('interrupted', [False, True])
def test_generic_prerequisite_graph_preserves_consumer_through_completion_and_restart(
        tmp_path, monkeypatch, task, prerequisites, shape, interrupted):
    docs = tmp_path / workflow.QUEUE
    docs.parent.mkdir(parents=True)
    briefs = docs.parent / 'E2E-Tasks'
    briefs.mkdir()

    def write_queue(rows, current):
        docs.write_text(
            '| Done | ID | Task | Requires tasks | Delivered scope | Minutes |\n'
            + ''.join(f'| [{"x" if done else " "}] | {key} | '
                      f'[Task](E2E-Tasks/{key}.md) | {requires} | Scope | 20–30 |\n'
                      for key, done, requires in rows)
            + '## Deferred future work\n| [ ] | 999 | Deferred | Baseline | Later | 20–30 |\n')
        (tmp_path / workflow.PLAN).write_text(f'Next task: **{current} — Task**.\n')
        for key, _, _ in rows:
            (briefs / f'{key}.md').write_text(f'# {key} — Task\n')

    original = [('950a', True, 'Baseline'), ('800b', True, '950a'),
                (task, False, '950a, 800b'), ('020q', False, task)]
    write_queue(original, task)
    _, before = workflow.queue_state(tmp_path)
    consumer = dict(workflow.fresh_state(task), in_flight=True, task_sessions=4,
                    live_attempts=2, stage_candidates=['partial.py'],
                    stage_baseline={'unrelated.py': 'original'}, queue_before=before,
                    handoff='Resume retained consumer work after its prerequisites.')
    previous = tmp_path / 'previous-run'
    previous.mkdir()
    checkpoint = previous / 'checkpoint.json'
    checkpoint.write_text(json.dumps(consumer))
    retained = checkpoint.read_bytes()
    monkeypatch.setattr(workflow.launcher, 'current_run', lambda _directory: previous)

    first, second, third = prerequisites
    graphs = {
        'single': [(first, 'Baseline')],
        'chain': [(first, 'Baseline'), (second, first), (third, second)],
        'diamond': [(first, 'Baseline'), (second, '950a'), (third, f'{first}, {second}')],
        'independent': [(first, 'Baseline'), (second, 'Baseline'), (third, '950a')],
    }
    graph = graphs[shape]
    required = ', '.join(key for key, _ in graph) if shape == 'independent' else graph[-1][0]
    rows = [*original[:2], *((key, False, requires) for key, requires in graph),
            (task, False, f'{required}, 800b'), original[-1]]
    write_queue(rows, first)
    selected = (workflow.initial_state(tmp_path, tmp_path) if interrupted else
                workflow.accept_result(tmp_path, consumer,
                    reply('blocked', 'not_run', task_id=task, host_validated=False,
                          handoff=consumer['handoff']), before))
    assert selected['task_id'] == first
    assert selected['phase'] == ('recover' if interrupted else 'implement')
    assert selected['task_sessions'] == selected['live_attempts'] == 0
    assert selected['stage_candidates'] == []
    assert checkpoint.read_bytes() == retained

    # Complete each prerequisite in table order, restarting at every boundary.
    # Task IDs deliberately differ from numeric order and from the original incident.
    for index, (key, _) in enumerate(graph):
        assert selected['task_id'] == key and selected['task_sessions'] == 0
        _, prior = workflow.queue_state(tmp_path)
        next_task = graph[index + 1][0] if index + 1 < len(graph) else task
        rows = [(identity, done or identity == key, requires) for identity, done, requires in rows]
        write_queue(rows, next_task)
        selected = workflow.accept_result(tmp_path, selected,
            reply('task_complete', 'passed', task_id=key), prior)
        checkpoint.write_text(json.dumps(selected))
        selected = workflow.initial_state(tmp_path, tmp_path)

    assert selected['task_id'] == task and selected['phase'] == 'recover'
    assert selected['task_sessions'] == 4 and selected['live_attempts'] == 2
    assert selected['stage_candidates'] == ['partial.py']
    assert selected['stage_baseline'] == {'unrelated.py': 'original'}
    assert selected['handoff'] == consumer['handoff']
    assert not selected['in_flight']
    assert all(workflow.queue_state(tmp_path)[1][key] == done for key, done in before.items())


@pytest.mark.parametrize('value', ['0', '-1', 'garbage', '1.5'])
@pytest.mark.parametrize('option', ['--sessions', '--tasks'])
def test_invalid_limit_refuses_before_spawn(tmp_path, value, option):
    with pytest.raises(SystemExit) as error:
        workflow.select(tmp_path, [option, value, '--vm', vm_name()])
    assert error.value.code == 2


def test_handoff_size_is_bounded_instead_of_accumulating_context(tmp_path):
    prepare(tmp_path)
    _, before = workflow.queue_state(tmp_path)
    with pytest.raises(ValueError, match='invalid'):
        workflow.accept_result(tmp_path, workflow.fresh_state('001'),
                               reply(handoff='x' * 16001), before)


def test_host_only_exception_can_close_without_a_vm_attempt(tmp_path):
    prepare(tmp_path)
    before = {'192': False, '002': False}
    (tmp_path / workflow.QUEUE).write_text('| [x] | 192 | Host only |\n| [ ] | 002 | Second |\n')
    (tmp_path / workflow.PLAN).write_text('Next task: **002 — [Second](second.md)**.\n')
    state = workflow.accept_result(tmp_path, workflow.fresh_state('192'),
                                   reply('task_complete', 'not_run', task_id='192'), before)
    assert state['phase'] == 'complete' and state['live_attempts'] == 0


def test_staging_preserves_unrelated_work_and_handles_deletions_and_literal_paths(tmp_path):
    prepare(tmp_path)
    subprocess.run(['git', 'init', '-q', str(tmp_path)], check=True)
    staged = tmp_path / 'already-staged.txt'
    staged.write_text('baseline')
    deleted = tmp_path / 'deleted.txt'
    deleted.write_text('remove this')
    subprocess.run(['git', 'add', '--', 'already-staged.txt', 'deleted.txt'], cwd=tmp_path, check=True)
    # A later unstaged edit in an unrelated path must remain unstaged.
    staged.write_text('unrelated unstaged edit')
    deleted.unlink()
    literal = tmp_path / ':special[1].py'
    literal.write_text('task code')
    brief = tmp_path / 'never-staged-brief.md'
    brief.write_text('temporary task instructions')
    brief.unlink()
    link = tmp_path / 'dangling-link'
    link.symlink_to('missing-target')
    paths = [workflow.PLAN, workflow.QUEUE, literal.name, deleted.name, brief.name, link.name]
    workflow.stage_task(tmp_path, paths)
    # Retrying close-out is safe even after the deletion left the index.
    workflow.stage_task(tmp_path, paths)
    baseline = subprocess.run(['git', 'show', ':already-staged.txt'], cwd=tmp_path,
                              capture_output=True, text=True, check=True)
    assert baseline.stdout == 'baseline' and staged.read_text() == 'unrelated unstaged edit'
    files = subprocess.run(['git', 'ls-files', '-z'], cwd=tmp_path,
                           capture_output=True, text=True, check=True).stdout.split(chr(0))
    assert literal.name in files and deleted.name not in files
    assert brief.name not in files and link.name in files
    assert workflow.PLAN in files and workflow.QUEUE in files


@pytest.mark.parametrize('legacy', [False, True])
def test_restart_stages_retained_completion_before_selecting_next_task(tmp_path, monkeypatch, legacy):
    prepare(tmp_path)
    subprocess.run(['git', 'init', '-q', str(tmp_path)], check=True)
    _, before = workflow.queue_state(tmp_path)
    result = reply('task_complete', 'passed', summary='Acceptance passed.', handoff='Implement task 002.')
    state = dict(workflow.fresh_state('001'), in_flight=True, queue_before=before,
                 worktree_before={}, stage_candidates=['owned.py'], task_sessions=4)
    if not legacy:
        state['pending_completion'] = result
    previous = tmp_path / 'previous-run'
    previous.mkdir()
    (previous / 'checkpoint.json').write_text(json.dumps(state))
    (previous / 'agent-result.json').write_text(json.dumps(result))
    retained = (previous / 'checkpoint.json').read_bytes()
    (tmp_path / workflow.QUEUE).write_text('| [x] | 001 | First |\n| [ ] | 002 | Second |\n')
    (tmp_path / workflow.PLAN).write_text('Next task: **002 — Second**.\n')
    (tmp_path / 'owned.py').write_text('task work')
    (tmp_path / 'unrelated.py').write_text('later work')
    monkeypatch.setattr(workflow.launcher, 'current_run', lambda _directory: previous)
    selected = workflow.initial_state(tmp_path, tmp_path)
    assert selected['task_id'] == '002' and selected['task_sessions'] == 0
    assert (previous / 'checkpoint.json').read_bytes() == retained
    files = subprocess.run(['git', 'ls-files', '-z'], cwd=tmp_path,
                           capture_output=True, text=True, check=True).stdout.split(chr(0))
    assert set(files) - {''} == {workflow.PLAN, workflow.QUEUE, 'owned.py'}


@pytest.mark.parametrize('fault', ['failed-live', 'wrong-task', 'other-task', 'staging'])
def test_retained_completion_cannot_bypass_acceptance_or_staging(tmp_path, monkeypatch, fault):
    prepare(tmp_path)
    _, before = workflow.queue_state(tmp_path)
    state = dict(workflow.fresh_state('001'), in_flight=True, queue_before=before)
    result = reply('task_complete', 'passed')
    if fault == 'failed-live':
        result['live_result'] = 'failed'
    elif fault == 'wrong-task':
        result['task_id'] = '002'
    state['pending_completion'] = result
    (tmp_path / workflow.QUEUE).write_text(
        '| [x] | 001 | First |\n| [' + ('x' if fault == 'other-task' else ' ') + '] | 002 | Second |\n')
    (tmp_path / workflow.PLAN).write_text('Next task: **002 — Second**.\n')
    staged = []

    def fail_staging(*args):
        staged.append(True)
        raise ValueError('staging refused')

    monkeypatch.setattr(workflow, 'stage_completion', fail_staging)
    with pytest.raises(ValueError):
        workflow.recover_completion(tmp_path, tmp_path, state)
    assert bool(staged) == (fault == 'staging')
    assert state['in_flight'] and state['phase'] == 'implement'


def test_pending_staging_handoff_uses_accepted_result(tmp_path):
    state = dict(workflow.fresh_state('001'), in_flight=True,
                 pending_completion=reply('task_complete', 'passed'),
                 summary='Acceptance passed.', handoff='Implement task 002.')
    workflow.save_handoff(tmp_path, state, 'staging failed', display=False)
    text = (tmp_path / 'handoff.txt').read_text()
    assert 'staging remains' in text and 'Implement task 002.' in text
    assert 'Recover interrupted task' not in text


@pytest.mark.parametrize('path', ['../outside', '/absolute', '.', 'docs', '.git/config', './file'])
def test_staging_refuses_nonfile_or_external_paths_before_git(tmp_path, path):
    prepare(tmp_path)
    with pytest.raises(ValueError, match='explicit checkout files'):
        workflow.stage_task(tmp_path, [workflow.PLAN, workflow.QUEUE, path])
