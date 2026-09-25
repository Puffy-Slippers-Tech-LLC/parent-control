"""Task selection, handoff boundaries and fail-closed completion."""

import subprocess
import json

import pytest

import write_e2e as workflow
from tests.support.write_e2e_fixtures import prepare, reply


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
    ('recover', 0, 'Recovering interrupted work + host validation'),
    ('live', 0, 'Live VM test 1, fix errors if any + host validation'),
    ('live', 2, 'Live VM test 3, fix errors if any + host validation'),
])
def test_session_controller_reports_task_title_and_phase(tmp_path, phase, attempts, summary):
    from rich.text import Text
    prepare(tmp_path)
    state = dict(workflow.fresh_state('001'), phase=phase, live_attempts=attempts,
                 task_sessions=2)
    assert [Text.from_ansi(line).plain for line in workflow.session_progress(tmp_path, state, 5)] == [
        'Task 001: First', f'Session [2/5]: {summary}']


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
    assert "run this task's first live VM acceptance" in prompt
    assert 'Leave failure review and repairs to the next' in prompt
    assert 'task_complete with live_result passed' in prompt
    assert 'The launcher owns staging' in prompt
    assert 'Do not analyze staged' in prompt
    assert 'Do not commit' in prompt
    assert 'tools/run-tests' in prompt


def test_only_latest_handoff_crosses_into_first_live_then_retry(tmp_path):
    prepare(tmp_path)
    state = workflow.fresh_state('001')
    _, before = workflow.queue_state(tmp_path)
    state = workflow.accept_result(tmp_path, state, reply(handoff='CURRENT HANDOFF'), before)
    prompt = workflow.session_prompt(state)
    assert 'first live attempt failed' in prompt
    assert 'review the unstaged code' in prompt
    assert 'CURRENT HANDOFF' in prompt
    state = workflow.accept_result(tmp_path, state, reply(live='failed', handoff='LATEST REPAIR'), before)
    prompt = workflow.session_prompt(state)
    assert state['live_attempts'] == 2
    assert 'first live attempt has already happened' in prompt
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
        assert 'Do not run live VM tests' in prompt
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


@pytest.mark.parametrize('change', [
    {'task_id': '002'}, {'host_validated': False}, {'live_result': 'passed'},
    {'live_result': 'not_run'},
    {'handoff': ''}, {'status': 'made_up'}, {'host_validated': 'yes'},
])
def test_invalid_initial_handoff_cannot_advance(tmp_path, change):
    prepare(tmp_path)
    _, before = workflow.queue_state(tmp_path)
    with pytest.raises(ValueError):
        workflow.accept_result(tmp_path, workflow.fresh_state('001'), reply(**change), before)


@pytest.mark.parametrize('phase', ['implement', 'live'])
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


def test_queue_order_is_authoritative_and_deferred_tasks_are_excluded(tmp_path):
    prepare(tmp_path)
    (tmp_path / workflow.PLAN).write_text('Next task: **002 — [Second](second.md)**.\n')
    with pytest.raises(ValueError, match='first unchecked task 001'):
        workflow.queue_state(tmp_path)
    (tmp_path / workflow.QUEUE).write_text(
        '| [x] | 001 | First |\n| [x] | 002 | Second |\n'
        '## Deferred future work\n| [ ] | 999 | Deferred |\n')
    assert workflow.queue_state(tmp_path)[0] is None


@pytest.mark.parametrize('value', ['0', '-1', 'garbage', '1.5'])
@pytest.mark.parametrize('option', ['--sessions', '--tasks'])
def test_invalid_limit_refuses_before_spawn(tmp_path, value, option):
    with pytest.raises(SystemExit) as error:
        workflow.select(tmp_path, [option, value])
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
    workflow.stage_task(tmp_path, [workflow.PLAN, workflow.QUEUE, literal.name, deleted.name])
    baseline = subprocess.run(['git', 'show', ':already-staged.txt'], cwd=tmp_path,
                              capture_output=True, text=True, check=True)
    assert baseline.stdout == 'baseline' and staged.read_text() == 'unrelated unstaged edit'
    files = subprocess.run(['git', 'ls-files', '-z'], cwd=tmp_path,
                           capture_output=True, text=True, check=True).stdout.split(chr(0))
    assert literal.name in files and deleted.name not in files
    assert workflow.PLAN in files and workflow.QUEUE in files


@pytest.mark.parametrize('path', ['../outside', '/absolute', '.', 'docs', '.git/config', './file'])
def test_staging_refuses_nonfile_or_external_paths_before_git(tmp_path, path):
    prepare(tmp_path)
    with pytest.raises(ValueError, match='explicit checkout files'):
        workflow.stage_task(tmp_path, [workflow.PLAN, workflow.QUEUE, path])
