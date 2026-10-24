"""Scripted test orchestration. Each repair is a fresh Codex process and thread.

Only the worker owns loop state. Observers may disappear at any time. A small
subprocess supervisor retains the owner lock and watches its parent's pipe, so
even SIGKILL of the worker cancels the current operation before releasing it.
"""

import argparse
import base64
import fcntl
import json
import os
from pathlib import Path
import re
import shutil
import shlex
import signal
import subprocess
import sys
import uuid

sys.path.insert(0, str(Path(__file__).resolve().parent))
from regression_session import FRAME_DIRECTORY, busy, lock
from test_commands import host_only_selection, repair_inventory as requested_inventory
from test_checkpoint import RESUME_SELECTION_MISMATCH
from detached_launcher import (
    Stopped, atomic, private_directory, current_run, environment, agent_command,
    compact_log, TAIL_BYTES,
)
import detached_launcher
from launcher_question import BLOCKER_INSTRUCTIONS, validate_blocker, wait_for_answer
from launcher_runtime import (SessionResultRejected, TaskBudget, TaskLimitReached, add_options,
                              read_session_result, retain_result_rejection, result_recovery_instructions,
                              validate_session_result, warn_remaining)


DEFAULT_MODEL = 'gpt-6.1-sol'
DEFAULT_EFFORT = 'medium'
APP_MODEL = 'gpt-6.1-sol'
APP_EFFORT = 'high'
REPAIR_TIERS = ((DEFAULT_MODEL, DEFAULT_EFFORT), (APP_MODEL, APP_EFFORT),
                (DEFAULT_MODEL, 'xhigh'), (DEFAULT_MODEL, 'max'))
UNIT_REPAIR_TIERS = tuple((DEFAULT_MODEL, effort) for effort in ('low', 'medium', 'high', 'xhigh'))
MAX_REPAIR_SESSIONS = 5
STALE_RETENTION = 'retention: previous owner did not finish; preserve evidence for recovery'


class ControllerReload(Exception):
    """The child-free worker must replace its imported decision code."""


def reload_controller(root, run, owner, *options):
    """Keep the run and its owner/scratch leases across a fresh interpreter."""
    descriptors = (owner, *detached_launcher.scratch_descriptors())
    inherited = {fd: os.get_inheritable(fd) for fd in descriptors}
    try:
        for fd in descriptors:
            os.set_inheritable(fd, True)
        sys.stdout.flush()
        sys.stderr.flush()
        os.execv('/usr/bin/python3', ['/usr/bin/python3', '-IBu', str(Path(__file__).resolve()),
                 '--reload-worker', str(root), str(run), str(owner), *options])
    finally:
        for fd, value in inherited.items():
            os.set_inheritable(fd, value)


def reattach_label(run):
    """Print the selected workflow scope and its saved canonical VM selector."""
    label = 'fix-tests host' if run.parent.name == 'fix-tests-host' else 'fix-tests vm'
    binding = run / 'vm.json'
    vm = json.loads(binding.read_text())['vm'] if binding.exists() else None
    if isinstance(vm, dict):
        vm = ','.join(vm['vms'])
    return label + (' --vm ' + shlex.quote(vm) if isinstance(vm, str) else '')


def repair_tiers(category=''):
    return UNIT_REPAIR_TIERS if category == 'unit' else REPAIR_TIERS


def initial_model(model=None, effort=None, *, category=''):
    model = model or DEFAULT_MODEL
    if model != DEFAULT_MODEL:
        raise ValueError('fix-tests model must be gpt-6.1-sol')
    return model, effort or repair_tiers(category)[0][1]


def available_models(model=None, effort=None, *, categories=('',)):
    model, _ = initial_model(model, effort)
    codex = shutil.which('codex')
    if codex is None:
        raise ValueError('Codex CLI is missing; install and authenticate it before running fix-tests')
    catalog = subprocess.run([codex, 'debug', 'models'], env=environment(),
                             capture_output=True, text=True, check=True)
    response = json.loads(catalog.stdout)
    models = response.get('models') if isinstance(response, dict) else None
    if not isinstance(models, list):
        raise ValueError('Codex returned an invalid model catalog')
    listed = [entry for entry in models if isinstance(entry, dict)
              and entry.get('visibility') == 'list'
              and isinstance(entry.get('slug'), str)
              and isinstance(entry.get('supported_reasoning_levels'), list)]
    required = []
    for category in categories:
        candidate = initial_model(model, effort, category=category)
        required.extend([candidate, *repair_tiers(category)[1:]])
        while next_tier(*candidate, category=category) != candidate:
            candidate = next_tier(*candidate, category=category)
            required.append(candidate)
    for required_model, required_effort in dict.fromkeys(required):
        if not any(entry['slug'] == required_model and any(
                isinstance(level, dict) and level.get('effort') == required_effort
                for level in entry['supported_reasoning_levels']) for entry in listed):
            raise ValueError(f'Codex model catalog has no listed {required_model} '
                             f'with {required_effort} reasoning')
    return model, APP_MODEL


def next_tier(model, effort, *, category=''):
    """Raise capability without lowering an explicit model or reasoning override."""
    efforts = ('none', 'minimal', 'low', 'medium', 'high', 'xhigh', 'max', 'ultra')
    if model == DEFAULT_MODEL:
        for tier in repair_tiers(category)[1:]:
            if efforts.index(effort) < efforts.index(tier[1]):
                return tier
    return model, effort


def repair_command(root, model, effort, run=None):
    command = agent_command(root, model, effort, run)
    command[-1:-1] = ['-c', 'service_tier="default"', '-c', 'features.fast_mode=false']
    return command


def record_usage(run, metadata, usage=None, *, event='turn'):
    """CLI counters and verification outcomes, not estimates of plan consumption."""
    fields = ('input_tokens', 'cached_input_tokens', 'output_tokens', 'reasoning_output_tokens')
    counters = {key: usage[key] for key in fields
                if isinstance(usage, dict) and type(usage.get(key)) is int and usage[key] >= 0}
    record = dict(metadata, event=event)
    if event in ('turn', 'missing_usage'):
        record.update(reported_scope='cli_turn', usage=counters or None)
    try:
        with lock(run / 'agent-usage.jsonl') as descriptor:
            fcntl.flock(descriptor, fcntl.LOCK_EX | fcntl.LOCK_NB)
            os.lseek(descriptor, 0, os.SEEK_END)
            with os.fdopen(os.dup(descriptor), 'w', encoding='utf-8') as stream:
                stream.write(json.dumps(record) + '\n')
    except (OSError, ValueError) as error:
        print(f'fix-tests: could not retain usage: {error}', file=sys.stderr, flush=True)


def repair_prompt(prompt, *, app_issue=None, developer_answers=(), blocker_summary=None, category=''):
    from vm_selection import execution_instructions
    prompt += '\n' + execution_instructions()
    ladder = ('Low to Medium, then High, then xHigh' if category == 'unit'
              else 'Medium to High, then xHigh, then Max')
    instructions = (
        'Classify the failure from the evidence as a test issue, an app issue, or '
        'uncertain before editing. If it is a test issue, fix it in this session '
        'and return status "test_fixed". If it is an app issue, make no edits and return '
        'status "app_issue" with a concise reason. If classification remains '
        'uncertain, make no corrective edits and return status "uncertain" with the competing '
        'explanations. Unresolved security, concurrency, ownership or difficult diagnosis '
        'also requires "uncertain" before editing; do not guess a mechanical fix. '
        'The launcher escalates these outcomes to the next available stronger tier. '
        if app_issue is None else
        'An earlier session supplied a repair or diagnostic handoff, classification, or stall. '
        'Recheck the classification using the original failure evidence, then fix '
        'the root cause in this checkout. Return status "fixed" after a repair. '
        'When a previous repair failed verification, identify what it taught you before '
        'editing again. If the same issue remains and there is no new evidence supporting a '
        'different correction, make no speculative corrective edits. Use "diagnostic_ready" '
        'for a useful instrumentation experiment, or "stalled" when no useful authorized '
        'next step exists, with the unresolved question and evidence paths. '
        f'Its handoff was: {app_issue}\n\n')
    decisions = ('\nDeveloper instructions for this run (apply only to their stated scope):\n'
                 + json.dumps(developer_answers, ensure_ascii=False) + '\n'
                 if developer_answers else '')
    continuation = ('\nPrevious attempt paused with this handoff:\n' + blocker_summary + '\n'
                    'Recheck the blocked prerequisite; an answer alone is not evidence it passed.\n'
                    if blocker_summary else '')
    return (prompt + '\n\n'
            'This is one independent repair attempt in tools/fix-tests. '
            + instructions + 'Preserve unrelated work. Follow AGENTS.md '
            'and docs/Approval-Tools.md and tests/README.md#handling-test-failures. '
            'Apply docs/Mandates/Test-Scope-Mandate.md before adding or restoring coverage; '
            'do not recreate excluded non-product tests for stale selectors or repair histories. '
            'Current product behavior alone never proves a test is wrong. For a behavioral '
            'mismatch, preserve evidence and identify the test, expected versus actual results '
            'and authoritative requirement. Before accepting changed behavior or altering '
            'expectations, return status "blocked" to ask the developer to confirm intended '
            'behavior, unless that exact behavior change is already explicitly authorized. '
            'Do not weaken, skip or delete tests to obtain a pass. Automatic test edits must '
            'address proven mechanical test, fixture or harness defects while preserving the intended check. '
            'Report missing authority or prerequisites requiring developer action using status "blocked" in the final '
            'result; the launcher pauses for developer instructions instead of failing. '
            'Missing prerequisites, permissions and preparation failures need their maintained '
            'repair or blocker route; they do not by themselves justify higher model effort. '
            + BLOCKER_INSTRUCTIONS +
            'Use summary as a concise standalone repair handoff: cause, changed paths, '
            'evidence, unresolved hypotheses and required verification. Read applicable '
            'contract sections and complete relevant functions with their callers/shared state; '
            'expand when evidence requires it. Reuse unchanged context within this session. '
            'Keep searches and diagnostic output scoped, without reducing required checks '
            'or understanding. All repair tiers use GPT-6.1 Sol. '
            'When evidence is insufficient for a correction but a useful authorized experiment '
            'exists, you may add bounded, relevant instrumentation that preserves behavior, '
            'assertions, validation guards and privacy. Return status "diagnostic_ready", not '
            'a repair claim. Its summary must state the hypothesis, changed paths, expected '
            'observations, evidence location and how to interpret the result. The launcher '
            'reruns only the original authorized selectors and returns the evidence in a fresh '
            'session within the same five-session budget. Never supply commands or request '
            'nested launchers or uncontrolled retries. Diagnostic edits are allowed before '
            'a proven corrective edit; uncertainty alone must not close this evidence-gathering path. '
            'Return "stalled" only when no useful authorized next step exists at this tier. '
            f'Stalls and same-case failed repairs escalate GPT-6.1 Sol {ladder}; '
            'a final-tier stall stops early. Blockers are never '
            'bypassed by escalation. The script owns test execution: finish after classification, diagnostics or repair; '
            'do not launch tests, fix-tests, background jobs or other agent sessions, '
            'except the shared mandatory backend_reviewer for core backend changes. '
            'Do not stage, commit or push; the launcher commits and pushes each repair '
            'only after confirming its failing case passed. Return stage_paths containing '
            'the explicit checkout-relative files owned by this repair, including diagnostic '
            'edits and deletions; use an empty list when no files changed. Never include '
            'unrelated work or output artifacts. '
            'Include in summary the concrete new evidence supporting this correction or newly '
            'exposed failure. Rewording a diagnosis, editing code or rerunning a test is not '
            'diagnostic progress. Each failing case has at most five agent sessions in this run, '
            'including classification and blocker continuations; failed verification, switching '
            'cases and later verification rounds do not renew that case budget. '
            'Do not read or resume previous Codex sessions, histories, memories or repair '
            'transcripts. Use only this failure handoff and the current repository.\n'
            + decisions + continuation)


def validate_result(result):
    if (not isinstance(result, dict)
            or set(result) - {'status', 'summary', 'blocker', 'stage_paths'}
            or result.get('status') not in ('test_fixed', 'fixed', 'blocked', 'app_issue', 'uncertain', 'stalled', 'diagnostic_ready')
            or not isinstance(result.get('summary'), str) or not result['summary'].strip()):
        raise ValueError('repair agent did not return a valid result object')
    paths = result.get('stage_paths', [])
    if (not isinstance(paths, list) or any(
            not isinstance(path, str) or not path or '\x00' in path
            or Path(path).is_absolute() or '..' in Path(path).parts or '.git' in Path(path).parts
            or Path(path).parts[:1] == ('output',) or path != Path(path).as_posix()
            or path == '.' for path in paths)):
        raise ValueError('stage_paths must contain explicit checkout files')
    if result['status'] == 'blocked':
        validate_blocker(result.get('blocker'))
    elif result.get('blocker') is not None:
        raise ValueError('only a blocked result may ask a question')


def read_tail(path):
    with path.open('rb') as stream:
        stream.seek(max(0, stream.seek(0, os.SEEK_END) - TAIL_BYTES))
        return stream.read().decode('utf-8', errors='replace')


def handoff(run, *, root=None):
    lines = read_tail(run / 'last-test.log').splitlines()
    paths = [line.removeprefix('Failure handoff: ') for line in lines
             if line.startswith('Failure handoff: ')]
    if not paths:
        errors = [line for line in lines if line.startswith('Test runner infrastructure failed: ')]
        detail = ('; ' + errors[-1][:2000]) if errors else ''
        raise ValueError('test runner did not produce a failure handoff' + detail + '; see last-test.log')
    from repair_evidence import read_failure
    value = read_failure(paths[-1])
    if (not isinstance(value, dict) or not isinstance(value.get('prompt'), str)
            or not value['prompt'].strip() or not isinstance(value.get('categories'), list)):
        raise ValueError('invalid test failure handoff')
    if root is not None:
        from repair_evidence import capture
        try:
            context = capture(root, run / f'failure-evidence-{uuid.uuid4().hex}.json',
                              paths[-1], read_tail(run / 'last-test.log'))
        except (OSError, ValueError, subprocess.TimeoutExpired):
            value['prompt'] += '\nOptional diagnostic copy unavailable; use the current runner output.'
        else:
            value['prompt'] += ('\nRetained private failure context (bounded log tails): '
                                + context + '\nRead this copy if the original report has rotated.')
    return value


def failure_target(failure, category):
    """Use runner-owned identities; older/non-case failures share a scoped fallback."""
    targets = failure.get('failures', [])
    if (not isinstance(targets, list) or any(
            not isinstance(item, dict) or set(item) != {'category', 'case', 'vm'}
            or any(not isinstance(item[key], str) for key in ('category', 'case', 'vm'))
            or not item['category'] for item in targets)):
        raise ValueError('invalid failure identities in test handoff')
    matching = [item for item in targets if item['category'] == category]
    target = matching[0] if matching else dict(category=category, case='', vm='')
    return tuple(target[key] for key in ('category', 'case', 'vm'))


def verification_outcome(failure, target):
    if failure is None:
        return True
    first = failure_target(failure, target[0])  # Validate every runner identity.
    reported = {tuple(item[key] for key in ('category', 'case', 'vm'))
                for item in failure.get('failures', [])}
    return False if target in reported or target == first else None


def category_inventory(output):
    inventory = json.loads(output)
    if not isinstance(inventory, dict) or not inventory:
        raise ValueError('run-tests returned no implemented leaf categories')
    for category, spec in inventory.items():
        if (not isinstance(category, str) or not category or category.startswith('-')
                or not isinstance(spec, dict) or not isinstance(spec.get('args'), list)
                or not all(isinstance(arg, str) for arg in spec['args'])):
            raise ValueError('invalid run-tests category inventory')
    # Preserve the runner's authoritative order and metadata.
    return inventory


def category_status(category, categories):
    try:
        index = categories.index(category)
    except ValueError:
        return None
    return (f'\033[1;36mRunning category [{category}] '
            f'({index + 1}/{len(categories)})\033[0m')


def run_loop(categories, test, repair, check_stop, *, selected=False, round_changed=lambda _: None,
             verified=lambda _repair, _passed: None, rounds=1, resume_test=None, completed=(), start_round=1,
             verification_started=lambda _completed: None,
             task_started=lambda: None, task_completed=lambda: None, outcome=verification_outcome,
             continuation=None):
    """Keep each case's latest repair handoff until its category passes."""
    def finish_category(category, failure):
        saved = continuation if continuation is not None else {}
        if saved.get('category') != category:
            saved.clear()
            saved.update(category=category, trigger=failure, failure=failure, phase='repair',
                         handoffs=[], prompts=[])
        handoffs = {tuple(key): value for key, value in saved['handoffs']}
        prompts = {tuple(key): value for key, value in saved['prompts']}
        failure = saved['failure']
        def remember(phase):
            saved.update(phase=phase, failure=failure,
                         handoffs=[[list(key), value] for key, value in handoffs.items()],
                         prompts=[[list(key), value] for key, value in prompts.items()])
        def diagnostic(value):
            return isinstance(value, dict) and value.get('status') == 'diagnostic_ready'

        while failure is not None or any(diagnostic(value) for value in handoffs.values()):
            check_stop()
            target = (failure_target(failure, category) if failure is not None else
                      next(key for key, value in handoffs.items() if diagnostic(value)))
            prompt = failure['prompt'] if failure is not None else prompts[target]
            prompts[target] = prompt
            # A later return to this exact case resolves an earlier unknown outcome.
            if saved['phase'] == 'repair':
                old = handoffs.get(target)
                if isinstance(old, dict) and old.get('verification') is None and failure is not None:
                    old['verification'] = False
                    old['evidence'] = failure
                    verified(old, False)
                remember('repair')
                previous = repair(prompt, failure_key=target,
                                  **({'previous': handoffs[target]} if target in handoffs else {}))
                handoffs[target] = previous
                remember('test')
            else:
                previous = handoffs[target]
            check_stop()
            # A non-case failure has no identity to invalidate in the saved
            # checkpoint. Replay its original category selection so diagnostics
            # and repairs cannot be certified by already completed passes.
            failure = (resume_test(category, retry_case=target[1], retry_vm=target[2], fresh=not target[1])
                       if resume_test else test(category))
            passed = outcome(failure, target)
            if isinstance(previous, dict):
                previous['verification'] = passed
                previous['evidence'] = failure
            verified(previous, passed)
            if failure is None:
                for key, value in handoffs.items():
                    if key != target and isinstance(value, dict):
                        value['verification'] = outcome(None, key)
                        value['evidence'] = None
                        verified(value, value['verification'])
                # Completed repairs need no further session; diagnostics always
                # return their observations for interpretation, even after a pass.
                handoffs = {key: value for key, value in handoffs.items() if diagnostic(value)}
            remember('repair')
        saved.clear()

    def initial_test(category):
        if continuation and continuation.get('category') == category:
            return continuation['trigger']
        if continuation and category == 'all':
            # Finish the interrupted leaf before the next whole clean pass.
            return dict(continuation['trigger'], categories=[continuation['category']])
        return test(category)

    if start_round == 1:
        round_changed(1)
        for category in categories:
            if category in completed:
                continue
            check_stop()
            task_started()
            finish_category(category, initial_test(category))
            task_completed()
    for number in range(max(2, start_round), rounds + 1):
        round_changed(number)
        verify_round(categories, initial_test, finish_category, check_stop, selected=selected,
                     completed=completed if number == start_round else (),
                     resume_test=resume_test, verification_started=verification_started,
                     task_started=task_started, task_completed=task_completed)


def verify_round(categories, test, finish_category, check_stop, *, selected, completed=(),
                 resume_test=None, verification_started=lambda _completed: None,
                 task_started=lambda: None, task_completed=lambda: None):
    """Repeat verification and repairs until this round has a clean pass."""
    if not selected and all(category in completed for category in categories):
        return
    if selected:
        # A later repair can break an earlier leaf. Require a whole selected
        # pass without repairs before finishing, never widening to all.
        while True:
            verification_started(completed)
            clean = True
            for category in categories:
                if category in completed:
                    continue
                check_stop()
                task_started()
                failure = test(category)
                if failure is not None:
                    clean = False
                    finish_category(category, failure)
                task_completed()
            if clean:
                return
            completed = ()
    while True:
        verification_started(completed)
        completed = ()
        check_stop()
        task_started()
        failure = test('all')
        if failure is None:
            task_completed()
            return
        failed = failure['categories']
        if not failed or any(category not in categories for category in failed):
            raise ValueError('aggregate failure has no runnable retry category; inspect its handoff')
        # Parallel companions can report more than one failure before cleanup.
        # Each category is repaired against fresh evidence after the first one.
        for index, category in enumerate(dict.fromkeys(failed)):
            check_stop()
            finish_category(category, failure if index == 0 else
                            (resume_test(category) if resume_test else test(category)))


def supervise(root, run, owner, kind, category, model, effort, test_args='[]'):
    if kind == 'test':
        from vm_selection import execution_arguments, selected
        vm_args = execution_arguments() if selected(required=False) is not None else []
        declaration = json.loads(test_args)
        options = declaration['args'] if isinstance(declaration, dict) else declaration
        if isinstance(declaration, dict) and declaration.get('vm'):
            vm_args = ['--vm', declaration['vm']]
        resume = '--resume' in options
        command = [str(root / 'tools/run-tests'), *(['--resume'] if resume else []),
                   '--stop-on-error', category, *[arg for arg in options if arg != '--resume'], *vm_args]
        os.environ['ONPC_RUNNER_INVOCATION'] = json.dumps(declaration['invocation']
            if isinstance(declaration, dict) else dict(
            repair_run=str(run), attempt=uuid.uuid4().hex,
            selection=[[category, [arg for arg in options if arg not in ('--resume', '--resume-case-only')
                                   and not arg.startswith('--resume-case=')]]]))
    elif kind == 'recovery':
        from vm_selection import execution_arguments, execution_binding
        options = execution_arguments() if execution_binding() is not None else ['--host-only']
        command = [str(root / 'tools/cleanup-e2e'), *options]
    else:
        from launcher_chat import read_state
        command = repair_command(root, model, effort, run)
        metadata = dict(json.loads(test_args), phase=category, model=model,
                        effort=effort, speed='standard')
        metadata.setdefault('session_id', uuid.uuid4().hex)
        reported = False

        def on_usage(usage):
            nonlocal reported
            reported = True
            record_usage(run, metadata, usage)

        status = detached_launcher.supervise(root, run, owner, kind, command, on_usage=on_usage,
                                              task=read_state(run).get('task_id'))
        if not reported:
            record_usage(run, metadata, event='missing_usage')
        record_usage(run, dict(metadata, exit_status=status), event='session_end')
        return status
    return detached_launcher.supervise(root, run, owner, kind, command)


def worker(root, run, owner, model, effort, app_model, requested='[]', rounds='1', resume='false', *, reloading=False):
    from vm_pool import selected_reservation
    from test_commands import host_only_request
    selected = json.loads(requested)
    status = 1
    reload = False
    try:
        with selected_reservation(enabled=not host_only_request(selected),
                                  stopped=lambda: (run / 'cancel').exists()):
            status = reserved_worker(root, run, owner, model, effort, app_model, requested, rounds, resume,
                                     reloading=reloading)
    except ControllerReload:
        reload = True
    except KeyboardInterrupt:
        status = 130
    except (OSError, ValueError) as error:
        print(f'fix-tests: {error}', file=sys.stderr, flush=True)
    finally:
        if reload and not (run / 'cancel').exists():
            try:
                reload_controller(root, run, owner, model, effort, app_model, requested, rounds, 'true')
            except OSError as error:
                print(f'fix-tests: controller reload failed: {error}; resume the retained run.',
                      file=sys.stderr, flush=True)
        elif reload:
            status = 130
        budget = TaskBudget(run)
        budget.close()
        atomic(run / 'result.json', {'status': status, 'tasks': budget.read()['completed']})
        os.close(owner)
    return status


def reserved_worker(root, run, owner, model, effort, app_model, requested='[]', rounds='1', resume='false', *, reloading=False):
    from launcher_progress import publish_progress, publish_repair_status, read_progress, repair_progress
    signal.signal(signal.SIGHUP, signal.SIG_IGN)
    round_number = 1
    developer_answers = []
    case_sessions = {}
    case_results = {}
    case_tiers = {}
    checkpoint = None
    resuming = resume == 'true'
    pending = None
    verifying_fix = False
    active_task = None
    budget = TaskBudget(run)
    from fix_tests_git import RepairCommits
    from repair_evidence import controller_sources
    commits = None
    sources = controller_sources()
    latest_attempt = None
    restart_continuation = None
    loop_state = {}
    repair_context = None
    test_replay = None
    task_inflight = False

    def check_controller(*, continuation=None):
        current = controller_sources()
        if current != sources:
            continuation = continuation or restart_continuation
            if continuation is not None and commits.key(tuple(continuation['failure'][name]
                    for name in ('category', 'case', 'vm'))) not in commits.state['repairs']:
                continuation = None  # The authorized repair already closed.
            commits.state['controller_restart'] = dict(expected=sources, actual=current,
                sessions={commits.key(key): value for key, value in case_sessions.items()},
                runtime=dict(loop=loop_state, repair=repair_context, test=test_replay,
                    results={commits.key(key): value for key, value in case_results.items()},
                    tiers={commits.key(key): value for key, value in case_tiers.items()},
                    answers=developer_answers, task_inflight=task_inflight,
                    task=active_task))
            if continuation is not None:
                commits.state['controller_restart']['continuation'] = continuation
            commits.save()
            print('fix-tests: repair controller sources changed; exact handoff retained. '
                  'Reloading automatically in the same run.', flush=True)
            raise ControllerReload()

    def task_started():
        nonlocal task_inflight
        if not task_inflight and not budget.admit():
            raise TaskLimitReached()
        task_inflight = True

    def task_completed():
        nonlocal task_inflight
        budget.complete()
        task_inflight = False

    def round_changed(number):
        nonlocal round_number
        round_number = number
        if checkpoint is not None:
            if number > checkpoint.state.get('round', 1):
                for entry in checkpoint.state['categories'].values():
                    entry['complete'] = False
            checkpoint.state['round'] = number
            checkpoint.save()

    def progress(category, status, *, model=None, effort=None):
        nonlocal active_task
        publish_repair_status(run, round_number, category, categories, status,
                              model=model, effort=effort)
        key = read_progress(run)[-1]['key']
        active_task = f'{round_number}:{category}'
        update_task_info(run, active_task, {})
        atomic(run / 'chat-state.json', {'task_id': active_task, 'progress_key': key})

    def panel(value):
        if active_task is not None:
            update_task_info(run, active_task, value)

    def failed(category):
        panel({'last_error': f'The {category} checks did not pass.'})

    def verification_started(completed):
        # A repair requires another whole clean pass. Persist the new pass's
        # queued work before it starts, so cancellation cannot reuse old passes.
        for kind in categories:
            if kind not in completed:
                checkpoint.entry(kind)['complete'] = False
        checkpoint.save()

    def cancel(*_):
        (run / 'cancel').touch(mode=0o600)

    for sig in (signal.SIGINT, signal.SIGTERM):
        signal.signal(sig, cancel)

    def check_stop():
        if (run / 'cancel').exists():
            raise Stopped()

    def execute(kind, category='', options=(), *, agent_model=None, agent_effort=None, vm=None):
        nonlocal latest_attempt, test_replay
        check_stop()
        check_controller()
        if test_replay is not None:
            replay, test_replay = test_replay, None
            def selectors(values):
                return [arg for arg in values if arg not in ('--resume', '--resume-case-only') and not arg.startswith('--resume-case=')]
            if (kind != replay['kind'] or category != replay['category']
                    or selectors(options) != selectors(replay['options']) or vm != replay.get('vm')):
                raise ValueError('retained controller operation differs from the original selection')
            return replay['status']
        invocation = dict(repair_run=str(run), attempt=uuid.uuid4().hex,
                          selection=[[category, [arg for arg in options if arg not in ('--resume', '--resume-case-only')
                                                 and not arg.startswith('--resume-case=')]]]) if kind == 'test' else None
        arguments = dict(args=options, invocation=invocation, vm=vm) if kind == 'test' else options
        command = ['/usr/bin/python3', '-IBu', str(Path(__file__).resolve()),
                   '--supervise', str(root), str(run), str(owner), kind, category,
                   agent_model or model, agent_effort or effort or DEFAULT_EFFORT,
                   json.dumps(arguments)]
        # The supervisor inherits ownership, but the test/agent does not. Its
        # stdin pipe is a liveness lease, not an interactive agent conversation.
        with subprocess.Popen(command, cwd=root, env=environment(), stdin=subprocess.PIPE,
                              pass_fds=(owner, *detached_launcher.scratch_descriptors()), start_new_session=True) as child:
            status = child.wait()
        if kind == 'test':
            latest_attempt = dict(category=category, selectors={
                name: spec['args'] for name, spec in inventory.items()},
                run=str(run), invocation=invocation, status=status)
            commits.state['runner_attempt'] = latest_attempt
            commits.save()
        sys.stdout.flush()
        compact_log(run / 'output', writer_fd=1)
        if (run / 'last-test.log').exists():
            compact_log(run / 'last-test.log')
        check_stop()
        if kind != 'agent':
            test_replay = dict(kind=kind, category=category, options=list(options), status=status, vm=vm)
            check_controller()
            test_replay = None
        return status

    def test(category, *, resume=False, retry_case='', retry_vm='', fresh=False):
        nonlocal pending, verifying_fix
        # A stopped source guard owns an unvalidated response, not permission
        # to skip its repair handoff because a later test happens to pass.
        for entry in commits.state['repairs'].values():
            response = entry.get('pending_response')
            if response is not None and category in ('all', entry['failure'][0]):
                return response['failure']
        checking_fix = verifying_fix
        verifying_fix = False
        # Close each validated repair before executing the remaining selection.
        # Retained status also restores this boundary after controller restart.
        repaired = next((entry for entry in commits.state['repairs'].values()
                         if entry['failure'] == [category, retry_case, retry_vm]
                         and entry.get('status') in ('fixed', 'test_fixed')), None) if retry_case else None
        focused = repaired is not None
        verification_vm = (retry_vm or None) if focused else None
        checking_fix = checking_fix or focused
        resume = not fresh and (resume or (resuming and (category == pending or
                            (category == 'all' and pending is not None and round_number > 1))))
        pending = category
        if checkpoint is not None:
            for kind in categories if category == 'all' else (category,):
                if checkpoint.entry(kind) is not None:
                    checkpoint.entry(kind)['complete'] = False
            checkpoint.state['pending'] = category
            checkpoint.save()
        def run_requested(requested, options, description, *, vm=None):
            while True:
                status = execute('test', requested, options, vm=vm)
                # run-tests consumes an active/unread predecessor before honoring
                # new arguments. Its result must never count as our requested run.
                with (run / 'last-test.log').open('rb') as stream:
                    attached = b'Attached to run-tests session:' in stream.read(8192)
                if not attached:
                    return status
                print(f'fix-tests: previous run-tests output delivered; starting {description}.',
                      flush=True)

        recovered = False
        if test_replay is not None and test_replay['kind'] == 'recovery':
            recovery_status = execute('recovery')
            if recovery_status:
                failure = handoff(run, root=root)
                failed(category)
                return failure
            recovered = True
        while True:
            atomic(run / 'test-controller.json', [])
            progress(category, 'Running tests')
            info = task_info(run, active_task)
            checking_fix = checking_fix or info.get('status') == 'Testing fix, previous error point passed'
            if checking_fix:
                panel({'status': 'Testing fix, previous error point not reached yet'})
            status_line = category_status(category, categories)
            print(f'\nfix-tests: running {category}', flush=True)
            options = [*inventory.get(category, {}).get('args', []), *(['--resume'] if resume else []),
                       *(['--resume-case=' + retry_case] if resume and retry_case else []),
                       *(['--resume-case-only'] if resume and focused else [])]
            status = run_requested(category, options,
                                   'the repaired case' if focused else 'the requested category', vm=verification_vm)
            previous = repair_progress(run, read_progress(run))
            publish_progress(run, previous[-1]['key'], previous[-1]['lines'])
            if status == 0:
                if checking_fix:
                    panel({'status': 'Testing fix, previous error point passed'})
                if focused and resume:
                    close_verified(category=category)
                    if commits.key(tuple(repaired['failure'])) in commits.state['repairs']:
                        raise ValueError('repair case has no confirmed pass; remaining cases were not started')
                    focused, verification_vm, checking_fix = False, None, False
                    retry_case = ''
                    resume = True
                    print('fix-tests: repair close-out complete; resuming remaining cases.', flush=True)
                    continue
                if checkpoint is not None:
                    for kind in categories if category == 'all' else (category,):
                        if checkpoint.entry(kind) is not None:
                            checkpoint.entry(kind)['complete'] = True
                    checkpoint.state['pending'] = None
                    checkpoint.save()
                pending = None
                close_verified(category=category)
                if status_line is not None:
                    print(status_line, flush=True)
                return None
            mismatch = 'Test runner infrastructure failed: ValueError: ' + RESUME_SELECTION_MISMATCH
            if (resume and host_only_selection([(category, [])])
                    and mismatch in read_tail(run / 'last-test.log').splitlines()):
                # Another public invocation can replace the scope's checkpoint
                # while an agent repairs a failure. Its passes cannot be reused;
                # replay our unchanged selectors once without saved progress.
                # VM/mixed requests span stores not all validated on refusal.
                print('fix-tests: runner checkpoint selection changed; replaying the requested '
                      'category from the start with its original selectors.', flush=True)
                resume = False
                continue
            if STALE_RETENTION in read_tail(run / 'last-test.log'):
                if recovered:
                    raise ValueError('test runner remained stale after automatic recovery; '
                                     'see last-test.log')
                from vm_selection import execution_binding
                scope = 'both retention scopes' if execution_binding() is not None else 'host retention'
                print(f'fix-tests: interrupted test ownership found; recovering {scope}.',
                      flush=True)
                recovery_status = execute('recovery')
                if recovery_status:
                    if status_line is not None:
                        print(status_line, flush=True)
                    failure = handoff(run, root=root)
                    failed(category)
                    return failure
                recovered = True
                continue
            if status_line is not None:
                print(status_line, flush=True)
            failure = handoff(run, root=root)
            close_verified(category=category)
            failed(category)
            return failure

    def repair(prompt, *, failure_key, previous=None):
        from contextlib import nullcontext
        from vm_pool import reservation
        with (reservation(failure_key[2]) if failure_key[2] else nullcontext()):
            return repair_owned(prompt, failure_key=failure_key, previous=previous)

    def repair_owned(prompt, *, failure_key, previous=None):
        nonlocal verifying_fix, restart_continuation, repair_context
        commits.begin(failure_key, inventory[failure_key[0]]['args'])
        entry = commits.state['repairs'][commits.key(failure_key)]
        failure_prompt = prompt
        replay = entry.get('pending_response')
        diagnostic = previous is not None and previous.get('status') == 'diagnostic_ready'
        classification = ((('diagnostic evidence: ' if diagnostic else 'verification_failed: ')
                           + previous['summary']) if previous else None)
        repair_id = previous['repair_id'] if previous else uuid.uuid4().hex
        attempt = previous['attempt'] + 1 if previous else 1
        blocker_summary = None
        continuation = commits.state.get('controller_restart', {}).get('continuation')
        if continuation is not None and continuation['failure'] == dict(zip(('category', 'case', 'vm'), failure_key)):
            blocker_summary = continuation['result']['summary']
        result_recovery = None
        target = dict(zip(('category', 'case', 'vm'), failure_key))
        category = target['category']
        initial = initial_model(model, effort or None, category=category)
        if diagnostic:
            prompt += ('\nLauncher-owned diagnostic execution outcome: '
                       + json.dumps(dict(passed=previous.get('verification'),
                                         evidence=previous.get('evidence'),
                                         retained=previous.get('evidence_path'))) + '\n'
                       'Interpret these observations before claiming a correction. A passing '
                       'diagnostic run alone does not prove the original cause was repaired.\n')
        prompt += ('\nRepair only this runner-identified failure; other cases have independent '
                   'budgets. Read the full report for context, preserve the requested selectors, '
                   'and leave test execution to the launcher:\n' + json.dumps(target) + '\n')
        if repair_context is not None and repair_context['failure'] == target:
            restored = repair_context
            prompt, failure_prompt = restored['prompt'], restored['failure_prompt']
            classification, repair_id, attempt = restored['classification'], restored['repair_id'], restored['attempt']
            blocker_summary, result_recovery = restored['blocker_summary'], restored['result_recovery']
            previous = None  # Escalation was already applied before the reload.

        def retain_stop(reason):
            atomic(run / 'repair-stop.json', dict(reason=reason, failure=target,
                   sessions=case_sessions.get(failure_key, 0), prompt=prompt,
                   result=case_results.get(failure_key)))

        def check_budget():
            sessions = case_sessions.get(failure_key, 0)
            if sessions >= MAX_REPAIR_SESSIONS:
                retain_stop('session_limit')
                record_usage(run, dict(repair_id=repair_id, sessions=sessions, failure=target),
                             event='session_limit')
                raise ValueError(f'repair session limit reached ({sessions}/{MAX_REPAIR_SESSIONS}); '
                                 f'failure: {json.dumps(target)}. '
                                 'no further agent was started. Retained failure: last-test.log; '
                                 'case handoff: repair-stop.json.')

        def escalate(reason, *, classification_only=False):
            current = case_tiers.get(failure_key, initial)
            # Classification transfers to at least the category's second tier;
            # an explicit stronger initial selection already meets that boundary.
            boundary = repair_tiers(category)[1][1]
            stronger = ('medium', 'high', 'xhigh', 'max', 'ultra')
            following = (current if classification_only and current[1] in stronger[stronger.index(boundary):]
                         else next_tier(*current, category=category))
            if following == current:
                return False
            case_tiers[failure_key] = following
            record_usage(run, dict(repair_id=repair_id, failure=target, reason=reason,
                                   from_model=current[0], from_effort=current[1],
                                   model=following[0], effort=following[1]), event='tier_transition')
            print(f'fix-tests: escalating {current} to {following}: {reason}', flush=True)
            return True

        if previous and not diagnostic and previous.get('verification') is False:
            escalate('same_case_verification_failed')

        while True:
            check_stop()
            repair_context = dict(failure=target, prompt=prompt, failure_prompt=failure_prompt,
                classification=classification, repair_id=repair_id, attempt=attempt,
                blocker_summary=blocker_summary, result_recovery=result_recovery)
            check_controller()
            replaying = replay is not None and 'response' in replay
            if replaying:
                metadata = replay['session']
                status = replay['exit_status']
                if metadata['failure'] != target:
                    raise ValueError('retained repair response identity changed')
                if replay['response'] is None:
                    (run / 'agent-result.json').unlink(missing_ok=True)
                else:
                    (run / 'agent-result.json').write_bytes(
                        base64.b64decode(replay['response'], validate=True))
                (run / 'prompt.txt').write_text(replay['prompt'], encoding='utf-8')
                sessions = case_sessions.get(failure_key, 0)
                repair_id, attempt = metadata['repair_id'], metadata['attempt']
                phase = replay['phase']
                classification = replay['classification']
                case_tiers[failure_key] = (replay['model'], replay['effort'])
                progress(category, 'validating retained response', model=replay['model'], effort=replay['effort'])
                replay = None  # Validation itself spends no model session.
            else:
                check_budget()
                sessions = case_sessions.get(failure_key, 0) + 1
                agent_model, agent_effort = case_tiers.setdefault(failure_key, initial)
                progress(category, 'fixing errors', model=agent_model, effort=agent_effort)
                # Aggregate failures can enter a leaf repair before its own test.
                task = active_task
                if not task_info(run, task).get('last_error'):
                    failed(category)
                phase = 'repair review' if classification else 'classify and repair'
                print(f'\nfix-tests: {phase} ({agent_model}, {agent_effort}); '
                      f'case session {sessions}/{MAX_REPAIR_SESSIONS}', flush=True)
                (run / 'prompt.txt').write_text(
                    repair_prompt(prompt + f'\nThis is case session {sessions}/{MAX_REPAIR_SESSIONS}; '
                                  f'{MAX_REPAIR_SESSIONS - sessions} further agent sessions remain. '
                                  'A diagnostic execution after the last session can retain evidence, '
                                  'but cannot start another interpretation session in this run.\n',
                                  app_issue=classification, developer_answers=developer_answers,
                                  blocker_summary=blocker_summary, category=category)
                    + task_info_instructions(run, task)
                    + '\nThe launcher owns verification and its testing statuses. Report your '
                      'investigation/fixing status through LAUNCHER_STATUS; finish with the required '
                      'repair result so the launcher can run the original checks.\n'
                    + result_recovery_instructions(result_recovery), encoding='utf-8')
                # An agent crash cannot reuse an earlier reply.
                (run / 'agent-result.json').write_text('')
                case_sessions[failure_key] = sessions
                metadata = dict(repair_id=repair_id, attempt=attempt, round=round_number,
                                repair_session=sessions, failure=target,
                                session_id=uuid.uuid4().hex)
                commits.state['session_counts'] = {
                    commits.key(key): value for key, value in case_sessions.items()}
                commits.save()
                from launcher_git import worktree_snapshot
                before = worktree_snapshot(root)
                status = execute('agent', phase, metadata,
                                 agent_model=agent_model, agent_effort=agent_effort)
                commits.capture_session(failure_key, before)
                if status == 0:
                    from plan_evidence import _read
                    try:
                        response = base64.b64encode(_read(run / 'agent-result.json')).decode('ascii')
                    except FileNotFoundError:
                        response = None
                    entry['pending_response'] = dict(response=response,
                        prompt=(run / 'prompt.txt').read_text(encoding='utf-8'), session=metadata,
                        exit_status=status, phase=phase, model=agent_model, effort=agent_effort,
                        classification=classification,
                        failure=dict(prompt=failure_prompt, categories=[category], failures=[target]))
                else:
                    # Preserve the failed turn, without making its transport
                    # failure a response replay loop in explicitly fresh runs.
                    entry.pop('pending_response', None)
                commits.save()
            check_controller()
            if status:
                raise ValueError(f'repair agent exited with status {status}; '
                                 'inspect the output before restarting')
            try:
                result = read_session_result(run)
                def validate(value):
                    validate_result(value)
                    commits.validate_paths(failure_key, value)
                validate_session_result(result, validate)
            except SessionResultRejected as error:
                result_recovery = retain_result_rejection(run, error, label='fix-tests')
                check_controller()
                entry.pop('pending_response', None)
                commits.save()
                continue
            result_recovery = None
            commits.record(failure_key, result)
            entry.pop('pending_response', None)
            commits.save()
            case_results[failure_key] = result
            record_usage(run, dict(metadata, phase=phase, result=result['status']),
                         event='result_replay' if replaying else 'result')
            if result['status'] == 'blocked':
                check_budget()
                progress_row = repair_progress(run, read_progress(run))[-1]
                answer = wait_for_answer(
                    run, result['blocker'], uuid.uuid4().hex, progress_row['key'],
                    label=reattach_label(run), heading=progress_row['lines'][0])
                if answer is None:
                    raise Stopped()
                developer_answers.append(answer)
                atomic(run / 'developer-answers.json', developer_answers)
                blocker_summary = result['summary']
                restart_continuation = dict(failure=target, result=result,
                    answers=developer_answers, prompt=prompt, session=metadata)
                repair_context['blocker_summary'] = blocker_summary
                check_controller(continuation=restart_continuation)
                print('Answer received. Continuing this repair.', flush=True)
                continue
            if result['status'] in ('app_issue', 'uncertain', 'stalled'):
                initial_classification = not classification and result['status'] != 'stalled'
                classification = result['status'] + ': ' + result['summary']
                raised = escalate(result['status'], classification_only=initial_classification)
                if raised or initial_classification:
                    continue
                retain_stop('stalled')
                raise ValueError('repair stalled; no further repair or test was started. '
                                 'Retained case handoff: repair-stop.json. ' + result['summary'])
            if result['status'] not in ('fixed', 'test_fixed', 'diagnostic_ready'):
                raise ValueError('unexpected repair result: ' + result['summary'])
            verifying_fix = result['status'] != 'diagnostic_ready'
            repair_context = None
            return dict(repair_id=repair_id, attempt=attempt, sessions=sessions,
                        failure=target, status=result['status'], summary=result['summary'])

    def verified(repair, passed):
        event = 'diagnostic_execution' if repair['status'] == 'diagnostic_ready' else 'verification'
        observation = dict(repair_id=repair['repair_id'], attempt=repair['attempt'],
                           failure=repair['failure'], passed=passed,
                           outcome='passed' if passed is True else 'failed' if passed is False
                           else 'unknown_or_not_executed', evidence=repair.get('evidence'))
        if event == 'diagnostic_execution':
            # Small, bounded evidence snapshots live with the launcher's private
            # retained control files, never in disposable agent scratch.
            path = run / f'diagnostic-{repair["repair_id"]}-{repair["attempt"]}-{uuid.uuid4().hex}.json'
            atomic(path, dict(observation, output_tail=read_tail(run / 'last-test.log'),
                              bounded_tails=True, may_be_truncated=True))
            repair['evidence_path'] = str(path)
            observation['evidence_path'] = str(path)
        record_usage(run, observation, event=event)
        if event == 'verification' and passed is True:
            check_stop()
            commits.verified(tuple(repair['failure'][key] for key in ('category', 'case', 'vm')),
                             attempt=latest_attempt)

    def outcome(failure, target):
        result = verification_outcome(failure, target)
        if result is False:
            return result
        if not target[1]:
            return result
        # A different failure is not a pass. Require the runner's validated,
        # teardown-complete case checkpoint, scoped to the original selectors
        # and the exact VM (host cases use the empty binding).
        from test_checkpoint import Checkpoint
        category, case, vm = target
        saved = Checkpoint(root, [(category, inventory[category]['args'])],
                           resume=True, binding=vm)
        return True if case in saved.passed(category) else None

    def close_verified(*, category=None):
        for entry in list(commits.state['repairs'].values()):
            target = tuple(entry['failure'])
            if category is not None and category not in ('all', target[0]):
                continue
            if target[0] not in inventory or inventory[target[0]]['args'] != entry['args']:
                raise ValueError('pending repair selectors changed; resume the original selection')
            if entry.get('pending_response') is not None:
                continue  # Current response validation precedes any acceptance.
            if entry.get('status') in ('fixed', 'test_fixed'):
                passed = (outcome(None, target) if target[1] else
                          checkpoint.complete(target[0]) and outcome(None, target))
                if passed is True:
                    check_stop()
                    commits.verified(target, attempt=latest_attempt)

    status = 1
    limited = False
    reload = False
    try:
        try:
            from launcher_render import AgentRenderer  # Check before expensive tests.
            from launcher_chat import task_info, task_info_instructions, update_task_info
        except ImportError as error:
            raise ValueError('agent rendering requires the setup-provided python3-rich package') from error
        repair_command(root, model, effort or DEFAULT_EFFORT)  # Fail before running expensive tests.
        listing = subprocess.run([str(root / 'tools/run-tests'), '--list'], cwd=root,
                                 env=environment(), capture_output=True, text=True, check=True)
        requested = json.loads(requested)
        inventory = requested_inventory(root, requested, inventory=category_inventory(listing.stdout))
        categories = list(inventory)
        from test_checkpoint import Checkpoint
        checkpoint = Checkpoint(root, [(name, spec['args']) for name, spec in inventory.items()],
                                resume=resuming, namespace='fix-tests')
        pending = checkpoint.state.get('pending')
        completed = [kind for kind in categories if checkpoint.complete(kind)]
        start_round = checkpoint.state.get('round', 1) if resuming else 1
        if start_round > int(rounds):
            raise ValueError('resume round exceeds --rounds; retain the original round count')
        rounds = int(rounds)
        commits = RepairCommits(root, run)
        if reloading:
            # An automatic replacement is the same run, with the same allowances.
            saved = commits.state['controller_restart']
            runtime = saved['runtime']
            case_sessions = {tuple(json.loads(key)): value for key, value in saved['sessions'].items()}
            case_results = {tuple(json.loads(key)): value for key, value in runtime['results'].items()}
            case_tiers = {tuple(json.loads(key)): tuple(value) for key, value in runtime['tiers'].items()}
            developer_answers = runtime['answers']
            loop_state = runtime['loop']
            repair_context, test_replay = runtime['repair'], runtime['test']
            task_inflight, active_task = runtime['task_inflight'], runtime['task']
            atomic(run / 'developer-answers.json', developer_answers)
        continuation = commits.state.get('controller_restart', {}).get('continuation')
        if continuation is not None:
            restart_continuation = continuation
            developer_answers = continuation['answers']
            atomic(run / 'developer-answers.json', developer_answers)
        latest_attempt = commits.state.get('runner_attempt')
        commits.guard = check_controller
        commits.state['controller_sources'] = sources
        commits.save()
        check_stop()
        commits.finish_pending()  # Retry accepted Git work before tests or another agent.
        # Only an explicit resume may recover a pass left before the verification
        # callback. A fresh run must execute its categories first: another run
        # may have replaced the shared runner checkpoint since this repair stopped.
        # Retained repairs still close out against their new category results.
        if resuming and not reloading:
            close_verified()
        for entry in commits.state['repairs'].values():
            category = entry['failure'][0]
            if (entry.get('status') in ('fixed', 'test_fixed') or entry.get('pending_response') is not None) and category in completed:
                completed.remove(category)  # Its exact repaired case still needs proof.
        if loop_state.get('category') in completed:
            completed.remove(loop_state['category'])
        if task_inflight and active_task is not None:
            task_category = active_task.partition(':')[2]
            if task_category in completed or task_category == 'all' and len(completed) == len(categories):
                task_completed()
        remaining_current = len(categories) - len(completed)
        if start_round > 1 and not requested:
            remaining_current = int(remaining_current > 0)  # A complete verification pass is one task.
        remaining = remaining_current + max(0, rounds - max(1, start_round)) * (
            len(categories) if requested else 1)
        budget.update(lambda value: value.update(remaining=remaining + value['completed']))
        warn_remaining(budget.read()['tasks'], remaining, label='fix-tests')
        print(f'fix-tests: category pass, then {rounds - 1} verification round(s)', flush=True)
        print('fix-tests: categories: ' + ', '.join(categories), flush=True)
        if resuming:
            print(f'fix-tests: resuming round {start_round}; retaining passed categories: '
                  + (', '.join(completed) or '(none)') + '.', flush=True)
        run_loop(categories, test, repair, check_stop, selected=bool(requested), rounds=rounds,
                 round_changed=round_changed,
                 completed=completed, resume_test=lambda category, **options: test(category, resume=True, **options),
                 start_round=start_round, verification_started=verification_started,
                 task_started=task_started, task_completed=task_completed,
                 verified=verified, outcome=outcome, continuation=loop_state)
        commits.require_complete()
        print('\nfix-tests: ' + ('all selected categories passed.' if requested else
              'all categories passed.' if rounds == 1 else
              'all categories and the complete regression passed.'), flush=True)
        status = 0
    except TaskLimitReached:
        print('\nfix-tests: task limit reached; remaining work is saved for --resume.', flush=True)
        limited = True
        status = 0
    except Stopped:
        print('\nfix-tests: stopped; owned operation cleanup finished.', flush=True)
        status = 130
    except ControllerReload:
        reload = True
        raise
    except (OSError, ValueError, subprocess.SubprocessError) as error:
        panel({'last_error': str(error)})
        print(f'\nfix-tests: {error}', file=sys.stderr, flush=True)
    finally:
        previous = repair_progress(run, read_progress(run))
        if previous and not reload:
            lines = previous[-1]['lines']
            lines[-1] = 'Status: ' + ('Task limit reached' if limited else
                                     {0: 'Complete', 130: 'Stopped'}.get(status, 'Blocked'))
            publish_progress(run, previous[-1]['key'], lines)
    return status


def select(root, *, stop=False, model=None, effort=None, categories=(), rounds=1, resume=False, tasks=None):
    from vm_selection import execution_binding, check_binding, save_binding
    from test_commands import repair_host_only_request
    name = execution_binding()
    retained_git = None
    legacy = root / 'artifacts/fix-tests'
    if (legacy / 'owner').exists():
        with lock(legacy / 'owner') as owner:
            if busy(owner):
                run = current_run(legacy)
                if run is None:
                    raise ValueError('active legacy fix-tests owner has no readable run record')
                check_binding(run, name)
                if stop:
                    (run / 'cancel').touch(mode=0o600)
                return run, False
    def command(run, owner):
        nonlocal retained_git
        # Read before shared retention can retire the previous run allocation.
        previous = current_run(run.parent)
        if previous is not None and (previous / 'checkpoint.json').exists():
            retained_git = json.loads((previous / 'checkpoint.json').read_text())
            if not retained_git['repairs'] and retained_git.get('pending') is None:
                retained_git = None  # Completed history stays with its original run.
            else:
                # Keep active decisions and Git ownership, not historical reports.
                attempts = retained_git.pop('runner_attempts', [])
                if attempts and 'runner_attempt' not in retained_git:
                    retained_git['runner_attempt'] = {
                        key: value for key, value in attempts[-1].items() if key != 'handoffs'}
                retained_git.pop('turns', None)
                for entry in retained_git['repairs'].values():
                    entry.pop('turns', None)
                    entry.pop('failure_attempts', None)
                    if entry.get('verification_attempt'):
                        entry['verification_attempt'].pop('handoffs', None)
                    if entry.get('pending_response'):
                        entry['pending_response'].pop('turn', None)
        selected_model, _ = initial_model(model, effort)
        listing = subprocess.run([str(root / 'tools/run-tests'), '--list'], cwd=root,
                                 env=environment(), capture_output=True, text=True, check=True)
        inventory = requested_inventory(root, categories, inventory=category_inventory(listing.stdout))
        default_model, app_model = available_models(selected_model, effort, categories=inventory)
        return ['/usr/bin/python3', '-IBu', str(Path(__file__).resolve()),
                '--worker', str(root), str(run), str(owner), default_model,
                effort or '', app_model, json.dumps(categories), str(rounds), *(['true'] if resume else [])]

    kind = 'fix-tests-host' if repair_host_only_request(root, categories) else 'fix-tests'
    def started(run):
        if retained_git is not None:
            atomic(run / 'checkpoint.json', retained_git)
        TaskBudget(run).initialize(tasks)
        save_binding(run, name)
        from test_checkpoint import request_record
        request_record(root, 'fix-tests', dict(categories=list(categories), rounds=rounds,
                                             vm=name))
    def attached(run):
        check_binding(run, name, stopping=stop)
        if tasks is not None:
            budget = TaskBudget(run)
            limit = budget.set_limit(tasks)
            if 'remaining' in budget.read():
                warn_remaining(limit, budget.read()['remaining'], label='fix-tests')
            print(f"fix-tests: limits now tasks={limit if limit is not None else 'all'}", flush=True)
    return detached_launcher.select(root, kind, command, stop=stop,
        on_attach=attached,
        on_start=started)


def follow(run, stream=None):
    return detached_launcher.follow(run, stream, label='fix-tests')


def stop_all(root):
    """Cancel this checkout's repair owners before waiting for any cleanup."""
    runs = []
    legacy = root / 'artifacts/fix-tests'
    if (legacy / 'owner').exists():
        with lock(legacy / 'owner') as owner:
            if busy(owner):
                run = current_run(legacy)
                if run is None:
                    raise ValueError('active legacy fix-tests owner has no readable run record')
                (run / 'cancel').touch(mode=0o600)
                runs.append(run)
    for kind in ('fix-tests-host', 'fix-tests'):
        run, _ = detached_launcher.select(root, kind, None, stop=True)
        if run is not None:
            runs.append(run)
    if not runs:
        print('fix-tests: no active launcher.')
        return 0
    status = 0
    for run in runs:
        print(f'fix-tests: stopping {run.name}; log: {run / "output"}', flush=True)
        status = follow(run) or status
    return status


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__, allow_abbrev=False)
    from vm_selection import SELECTOR_HELP
    parser.add_argument('--vm', help=SELECTOR_HELP)
    add_options(parser, stop_help='stop active runs in this checkout; categories or --vm narrow the scope')
    parser.add_argument('--resume', action='store_true',
                        help='resume passed categories and the failed/interrupted test checkpoint')
    parser.add_argument('--model', help='repair model (only gpt-6.1-sol is supported)')
    parser.add_argument('--rounds', type=int, metavar='X',
                        help='run round 1 once, then round 2 X-1 times (default: 1)')
    parser.add_argument('--effort', choices=('low', 'medium', 'high', 'xhigh', 'max'),
                        help='initial reasoning effort (default: low for unit, medium otherwise; unit escalates through medium, high and xhigh; other categories through high, xhigh and max)')
    parser.epilog = ('Pass categories and arguments as for run-tests, e.g. e2e --id 6 '
                     'or unit tests/unit/test_fix_tests.py -q. Launcher options are recognized '
                     'anywhere and removed from the forwarded arguments. '
                     'Omitting categories selects every leaf. Host and VM workflows have '
                     'separate sessions; attach using the same scope. Bare --stop cancels both scopes.')
    args, categories = parser.parse_known_args(argv)
    root = Path(__file__).resolve().parents[1]
    if args.resume and not categories and not args.stop:
        from test_checkpoint import request_record
        previous_request = request_record(root, 'fix-tests')
        if previous_request is not None:
            categories = previous_request['categories']
            if args.rounds is None:
                args.rounds = previous_request['rounds']
            if args.vm is None:
                binding = previous_request['vm']
                args.vm = ','.join(binding['vms']) if isinstance(binding, dict) else binding
    args.categories = categories
    if args.rounds is None:
        args.rounds = 1
    if args.rounds < 1:
        parser.error('--rounds must be a positive integer')
    run = None
    requested = args.stop

    def cancel(*_):
        nonlocal requested
        requested = True
        if run is not None:
            (run / 'cancel').touch(mode=0o600)

    previous = signal.signal(signal.SIGINT, cancel)
    try:
        if args.stop and not args.categories and args.vm is None:
            return stop_all(root)
        from vm_selection import execution_selection
        from test_commands import repair_host_only_request
        host_only = repair_host_only_request(root, args.categories)
        if args.stop and args.vm is None:
            from vm_selection import VARIABLE, BATCH
            os.environ.pop(VARIABLE, None)
            os.environ.pop(BATCH, None)
        elif args.vm is not None:
            execution_selection(args.vm)
        elif not host_only:
            execution_selection()
        else:
            from vm_selection import VARIABLE, BATCH
            os.environ.pop(VARIABLE, None)
            os.environ.pop(BATCH, None)
        requested_inventory(root, args.categories)
        run, started = select(root, stop=requested, model=args.model, effort=args.effort,
                              categories=args.categories, rounds=args.rounds,
                              **({'tasks': args.tasks} if args.tasks is not None else {}),
                              **({'resume': True} if args.resume else {}))
        if run is None:
            print('fix-tests: no active launcher.')
            return 0
        if requested:
            cancel()
        print(f'fix-tests: {"started" if started else "attached to"} {run.name}; log: {run / "output"}', flush=True)
        print(f'Closing the terminal detaches. Ctrl+C or tools/{reattach_label(run)} --stop cancels.', flush=True)
        return follow(run)
    except BrokenPipeError:
        return 0  # The detached owner continues independently.
    except (OSError, ValueError) as error:
        print(f'fix-tests: {error}', file=sys.stderr)
        return 2
    finally:
        signal.signal(signal.SIGINT, previous)


if __name__ == '__main__':
    mode, root, run, owner, *options = sys.argv[1:]
    if mode in ('--worker', '--reload-worker'):
        sys.exit(worker(Path(root), Path(run), int(owner), *options, reloading=mode == '--reload-worker'))
    if mode == '--supervise':
        sys.exit(supervise(Path(root), Path(run), int(owner), *options))
    raise SystemExit('private fix-tests worker entry point')
