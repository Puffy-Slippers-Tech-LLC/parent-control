"""Scripted test orchestration. Each repair is a fresh, ephemeral Codex process.

Only the worker owns loop state. Observers may disappear at any time. A small
subprocess supervisor retains the owner lock and watches its parent's pipe, so
even SIGKILL of the worker cancels the current operation before releasing it.
"""

import argparse
import fcntl
import json
import os
from pathlib import Path
import shutil
import shlex
import signal
import subprocess
import sys
import uuid

sys.path.insert(0, str(Path(__file__).resolve().parent))
from regression_session import FRAME_DIRECTORY, busy, lock
from test_commands import repair_inventory as requested_inventory
from detached_launcher import (
    Stopped, atomic, private_directory, current_run, environment, agent_command,
    compact_log, TAIL_BYTES,
)
import detached_launcher
from launcher_question import BLOCKER_INSTRUCTIONS, validate_blocker, wait_for_answer


DEFAULT_MODEL = 'gpt-6.1-sol'
DEFAULT_EFFORT = 'medium'
APP_MODEL = 'gpt-6.1-sol'
APP_EFFORT = 'high'
REPAIR_TIERS = ((DEFAULT_MODEL, DEFAULT_EFFORT), (APP_MODEL, APP_EFFORT),
                ('gpt-6-astra', 'high'), ('gpt-6-astra', 'xhigh'))
MAX_REPAIR_SESSIONS = 5
STALE_RETENTION = 'retention: previous owner did not finish; preserve evidence for recovery'


def reattach_label(run):
    """Print the selected workflow scope and its saved canonical VM selector."""
    label = 'fix-tests host' if run.parent.name == 'fix-tests-host' else 'fix-tests vm'
    binding = run / 'vm.json'
    vm = json.loads(binding.read_text())['vm'] if binding.exists() else None
    if isinstance(vm, dict):
        vm = ','.join(vm['vms'])
    return label + (' --vm ' + shlex.quote(vm) if isinstance(vm, str) else '')


def initial_model(model=None, effort=DEFAULT_EFFORT):
    model = model or DEFAULT_MODEL
    if model.endswith('-sol') and model != DEFAULT_MODEL:
        raise ValueError('Sol must be gpt-6.1-sol')
    return model, effort


def available_models(model=None, effort=DEFAULT_EFFORT):
    model, effort = initial_model(model, effort)
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
    required = [(model, effort), *REPAIR_TIERS[1:]]
    candidate = (model, effort)
    while next_tier(*candidate) != candidate:
        candidate = next_tier(*candidate)
        required.append(candidate)
    for required_model, required_effort in dict.fromkeys(required):
        if not any(entry['slug'] == required_model and any(
                isinstance(level, dict) and level.get('effort') == required_effort
                for level in entry['supported_reasoning_levels']) for entry in listed):
            raise ValueError(f'Codex model catalog has no listed {required_model} '
                             f'with {required_effort} reasoning')
    return model, APP_MODEL


def next_tier(model, effort):
    """Raise capability without lowering an explicit model or reasoning override."""
    efforts = ('none', 'minimal', 'low', 'medium', 'high', 'xhigh', 'max', 'ultra')
    if model == DEFAULT_MODEL:
        if efforts.index(effort) < efforts.index('high'):
            return APP_MODEL, APP_EFFORT
        return 'gpt-6-astra', effort
    if model == 'gpt-6-astra' and efforts.index(effort) < efforts.index('xhigh'):
        return model, 'high' if efforts.index(effort) < efforts.index('high') else 'xhigh'
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


def repair_prompt(prompt, *, app_issue=None, developer_answers=(), blocker_summary=None):
    from vm_selection import execution_instructions
    prompt += '\n' + execution_instructions()
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
            'or understanding. Prefer GPT-6.1 Sol High over Astra Low for difficult repairs. '
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
            'Stalls and same-case failed repairs escalate Sol Medium to Sol High, then Astra '
            'High, then Astra Extra High; a final-tier stall stops early. Blockers are never '
            'bypassed by escalation. The script owns test execution: finish after classification, diagnostics or repair; '
            'do not launch tests, fix-tests, background jobs or other agent sessions. '
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
            or set(result) - {'status', 'summary', 'blocker'}
            or result.get('status') not in ('test_fixed', 'fixed', 'blocked', 'app_issue', 'uncertain', 'stalled', 'diagnostic_ready')
            or not isinstance(result.get('summary'), str) or not result['summary'].strip()):
        raise ValueError('repair agent did not return a valid result object')
    if result['status'] == 'blocked':
        validate_blocker(result.get('blocker'))
    elif result.get('blocker') is not None:
        raise ValueError('only a blocked result may ask a question')


def read_tail(path):
    with path.open('rb') as stream:
        stream.seek(max(0, stream.seek(0, os.SEEK_END) - TAIL_BYTES))
        return stream.read().decode('utf-8', errors='replace')


def handoff(run):
    lines = read_tail(run / 'last-test.log').splitlines()
    paths = [line.removeprefix('Failure handoff: ') for line in lines
             if line.startswith('Failure handoff: ')]
    if not paths:
        raise ValueError('test runner did not produce a failure handoff; see last-test.log')
    value = json.loads(Path(paths[-1]).read_text())
    if (not isinstance(value, dict) or not isinstance(value.get('prompt'), str)
            or not value['prompt'].strip() or not isinstance(value.get('categories'), list)):
        raise ValueError('invalid test failure handoff')
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
             verified=lambda _repair, _passed: None, rounds=1):
    """Keep each case's latest repair handoff until its category passes."""
    def finish_category(category, failure):
        handoffs = {}
        prompts = {}
        def diagnostic(value):
            return isinstance(value, dict) and value.get('status') == 'diagnostic_ready'

        while failure is not None or any(diagnostic(value) for value in handoffs.values()):
            check_stop()
            target = (failure_target(failure, category) if failure is not None else
                      next(key for key, value in handoffs.items() if diagnostic(value)))
            prompt = failure['prompt'] if failure is not None else prompts[target]
            prompts[target] = prompt
            # A later return to this exact case resolves an earlier unknown outcome.
            old = handoffs.get(target)
            if isinstance(old, dict) and old.get('verification') is None and failure is not None:
                old['verification'] = False
                old['evidence'] = failure
                verified(old, False)
            previous = repair(prompt, failure_key=target,
                              **({'previous': handoffs[target]} if target in handoffs else {}))
            handoffs[target] = previous
            check_stop()
            failure = test(category)
            passed = verification_outcome(failure, target)
            if isinstance(previous, dict):
                previous['verification'] = passed
                previous['evidence'] = failure
            verified(previous, passed)
            if failure is None:
                for key, value in handoffs.items():
                    if key != target and isinstance(value, dict):
                        value['verification'] = True
                        value['evidence'] = None
                        verified(value, True)
                # Completed repairs need no further session; diagnostics always
                # return their observations for interpretation, even after a pass.
                handoffs = {key: value for key, value in handoffs.items() if diagnostic(value)}

    round_changed(1)
    for category in categories:
        check_stop()
        finish_category(category, test(category))
    for number in range(2, rounds + 1):
        round_changed(number)
        verify_round(categories, test, finish_category, check_stop, selected=selected)


def verify_round(categories, test, finish_category, check_stop, *, selected):
    """Repeat verification and repairs until this round has a clean pass."""
    if selected:
        # A later repair can break an earlier leaf. Require a whole selected
        # pass without repairs before finishing, never widening to all.
        while True:
            clean = True
            for category in categories:
                check_stop()
                failure = test(category)
                if failure is not None:
                    clean = False
                    finish_category(category, failure)
            if clean:
                return
    while True:
        check_stop()
        failure = test('all')
        if failure is None:
            return
        failed = failure['categories']
        if not failed or any(category not in categories for category in failed):
            raise ValueError('aggregate failure has no runnable retry category; inspect its handoff')
        # Parallel companions can report more than one failure before cleanup.
        # Each category is repaired against fresh evidence after the first one.
        for index, category in enumerate(dict.fromkeys(failed)):
            check_stop()
            finish_category(category, failure if index == 0 else test(category))


def supervise(root, run, owner, kind, category, model, effort, test_args='[]'):
    if kind == 'test':
        from vm_selection import execution_arguments, selected
        vm_args = execution_arguments() if selected(required=False) is not None else []
        command = [str(root / 'tools/run-tests'), '--stop-on-error', category,
                   *json.loads(test_args), *vm_args]
    elif kind == 'recovery':
        from vm_selection import execution_arguments, execution_binding
        options = execution_arguments() if execution_binding() is not None else ['--host-only']
        command = [str(root / 'tools/cleanup-e2e'), *options]
    else:
        command = repair_command(root, model, effort, run)
        metadata = dict(json.loads(test_args), phase=category, model=model,
                        effort=effort, speed='standard')
        metadata.setdefault('session_id', uuid.uuid4().hex)
        reported = False

        def on_usage(usage):
            nonlocal reported
            reported = True
            record_usage(run, metadata, usage)

        status = detached_launcher.supervise(root, run, owner, kind, command, on_usage=on_usage)
        if not reported:
            record_usage(run, metadata, event='missing_usage')
        record_usage(run, dict(metadata, exit_status=status), event='session_end')
        return status
    return detached_launcher.supervise(root, run, owner, kind, command)


def worker(root, run, owner, model, effort, app_model, requested='[]', rounds='1'):
    from launcher_progress import publish_progress, publish_repair_status, read_progress, repair_progress
    signal.signal(signal.SIGHUP, signal.SIG_IGN)
    round_number = 1
    developer_answers = []
    case_sessions = {}
    case_results = {}
    case_tiers = {}

    def round_changed(number):
        nonlocal round_number
        round_number = number

    def progress(category, status, *, model=None):
        publish_repair_status(run, round_number, category, categories, status, model=model)

    def cancel(*_):
        (run / 'cancel').touch(mode=0o600)

    for sig in (signal.SIGINT, signal.SIGTERM):
        signal.signal(sig, cancel)

    def check_stop():
        if (run / 'cancel').exists():
            raise Stopped()

    def execute(kind, category='', options=(), *, agent_model=None, agent_effort=None):
        check_stop()
        command = ['/usr/bin/python3', '-IBu', str(Path(__file__).resolve()),
                   '--supervise', str(root), str(run), str(owner), kind, category,
                   agent_model or model, agent_effort or effort,
                   json.dumps(options)]
        # The supervisor inherits ownership, but the test/agent does not. Its
        # stdin pipe is a liveness lease, not an interactive agent conversation.
        with subprocess.Popen(command, cwd=root, env=environment(), stdin=subprocess.PIPE,
                              pass_fds=(owner, *detached_launcher.scratch_descriptors()), start_new_session=True) as child:
            status = child.wait()
        sys.stdout.flush()
        compact_log(run / 'output', writer_fd=1)
        if (run / 'last-test.log').exists():
            compact_log(run / 'last-test.log')
        check_stop()
        return status

    def test(category):
        def run_requested(requested, options, description):
            while True:
                status = execute('test', requested, options)
                # run-tests consumes an active/unread predecessor before honoring
                # new arguments. Its result must never count as our requested run.
                with (run / 'last-test.log').open('rb') as stream:
                    attached = b'Attached to run-tests session:' in stream.read(8192)
                if not attached:
                    return status
                print(f'fix-tests: previous run-tests output delivered; starting {description}.',
                      flush=True)

        recovered = False
        while True:
            atomic(run / 'test-controller.json', [])
            progress(category, 'Running tests')
            status_line = category_status(category, categories)
            print(f'\nfix-tests: running {category}', flush=True)
            status = run_requested(category, inventory.get(category, {}).get('args', []),
                                   'the requested category')
            previous = repair_progress(run, read_progress(run))
            publish_progress(run, previous[-1]['key'], previous[-1]['lines'])
            if status == 0:
                if status_line is not None:
                    print(status_line, flush=True)
                return None
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
                    return handoff(run)
                recovered = True
                continue
            if status_line is not None:
                print(status_line, flush=True)
            return handoff(run)

    def repair(prompt, *, failure_key, previous=None):
        diagnostic = previous is not None and previous.get('status') == 'diagnostic_ready'
        classification = ((('diagnostic evidence: ' if diagnostic else 'verification_failed: ')
                           + previous['summary']) if previous else None)
        repair_id = previous['repair_id'] if previous else uuid.uuid4().hex
        attempt = previous['attempt'] + 1 if previous else 1
        blocker_summary = None
        target = dict(zip(('category', 'case', 'vm'), failure_key))
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
            current = case_tiers.get(failure_key, (model, effort))
            # Classification needs at least High, but an explicit stronger
            # initial selection already meets that boundary.
            following = (current if classification_only and current[1] in ('high', 'xhigh')
                         else next_tier(*current))
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
            check_budget()
            sessions = case_sessions.get(failure_key, 0) + 1
            agent_model, agent_effort = case_tiers.setdefault(failure_key, (model, effort))
            progress('', 'fixing errors', model=agent_model)
            phase = 'repair review' if classification else 'classify and repair'
            print(f'\nfix-tests: {phase} ({agent_model}, {agent_effort}); '
                  f'case session {sessions}/{MAX_REPAIR_SESSIONS}', flush=True)
            (run / 'prompt.txt').write_text(
                repair_prompt(prompt + f'\nThis is case session {sessions}/{MAX_REPAIR_SESSIONS}; '
                              f'{MAX_REPAIR_SESSIONS - sessions} further agent sessions remain. '
                              'A diagnostic execution after the last session can retain evidence, '
                              'but cannot start another interpretation session in this run.\n',
                              app_issue=classification, developer_answers=developer_answers,
                              blocker_summary=blocker_summary), encoding='utf-8')
            # An agent crash cannot reuse an earlier reply.
            (run / 'agent-result.json').write_text('')
            case_sessions[failure_key] = sessions
            metadata = dict(repair_id=repair_id, attempt=attempt, round=round_number,
                            repair_session=sessions, failure=target,
                            session_id=uuid.uuid4().hex)
            status = execute('agent', phase, metadata,
                             agent_model=agent_model, agent_effort=agent_effort)
            if status:
                raise ValueError(f'repair agent exited with status {status}; '
                                 'inspect the output before restarting')
            result = json.loads((run / 'agent-result.json').read_text())
            validate_result(result)
            case_results[failure_key] = result
            record_usage(run, dict(metadata, phase=phase, result=result['status']), event='result')
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
            atomic(path, dict(observation, output_tail=read_tail(run / 'last-test.log')))
            repair['evidence_path'] = str(path)
            observation['evidence_path'] = str(path)
        record_usage(run, observation, event=event)

    status = 1
    try:
        try:
            from launcher_render import AgentRenderer  # Check before expensive tests.
        except ImportError as error:
            raise ValueError('agent rendering requires the setup-provided python3-rich package') from error
        repair_command(root, model, effort)  # Fail before running expensive tests.
        listing = subprocess.run([str(root / 'tools/run-tests'), '--list'], cwd=root,
                                 env=environment(), capture_output=True, text=True, check=True)
        requested = json.loads(requested)
        inventory = requested_inventory(root, requested, inventory=category_inventory(listing.stdout))
        categories = list(inventory)
        rounds = int(rounds)
        print(f'fix-tests: category pass, then {rounds - 1} verification round(s)', flush=True)
        print('fix-tests: categories: ' + ', '.join(categories), flush=True)
        run_loop(categories, test, repair, check_stop, selected=bool(requested), rounds=rounds,
                 round_changed=round_changed,
                 verified=verified)
        print('\nfix-tests: ' + ('all selected categories passed.' if requested else
              'all categories passed.' if rounds == 1 else
              'all categories and the complete regression passed.'), flush=True)
        status = 0
    except Stopped:
        print('\nfix-tests: stopped; owned operation cleanup finished.', flush=True)
        status = 130
    except (OSError, ValueError, subprocess.SubprocessError) as error:
        print(f'\nfix-tests: {error}', file=sys.stderr, flush=True)
    finally:
        previous = repair_progress(run, read_progress(run))
        if previous:
            lines = previous[-1]['lines']
            lines[-1] = 'Status: ' + {0: 'Complete', 130: 'Stopped'}.get(status, 'Blocked')
            publish_progress(run, previous[-1]['key'], lines)
        atomic(run / 'result.json', {'status': status})
        os.close(owner)
    return status


def select(root, *, stop=False, model=None, effort=DEFAULT_EFFORT, categories=(), rounds=1):
    from vm_selection import execution_binding, check_binding, save_binding
    from test_commands import repair_host_only_request
    name = execution_binding()
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
        selected_model, selected_effort = initial_model(model, effort)
        default_model, app_model = available_models(selected_model, selected_effort)
        return ['/usr/bin/python3', '-IBu', str(Path(__file__).resolve()),
                '--worker', str(root), str(run), str(owner), default_model,
                selected_effort, app_model, json.dumps(categories), str(rounds)]

    kind = 'fix-tests-host' if repair_host_only_request(root, categories) else 'fix-tests'
    return detached_launcher.select(root, kind, command, stop=stop,
        on_attach=lambda run: check_binding(run, name, stopping=stop),
        on_start=lambda run: save_binding(run, name))


def follow(run, stream=None):
    return detached_launcher.follow(run, stream, label='fix-tests')


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__, allow_abbrev=False)
    from vm_selection import SELECTOR_HELP
    parser.add_argument('--vm', help=SELECTOR_HELP)
    parser.add_argument('--stop', action='store_true', help='stop the active run, like Ctrl+C')
    parser.add_argument('--model', help='initial repair model (default: gpt-6.1-sol)')
    parser.add_argument('--rounds', type=int, default=1, metavar='X',
                        help='run round 1 once, then round 2 X-1 times (default: 1)')
    parser.add_argument('--effort', choices=('low', 'medium', 'high', 'xhigh'),
                        default=DEFAULT_EFFORT, help='initial reasoning effort (default: medium; escalates through Sol high and Astra high/xhigh)')
    parser.epilog = ('Pass categories and arguments as for run-tests, e.g. e2e --id 6 '
                     'or unit tests/unit/test_fix_tests.py -q. Launcher options are recognized '
                     'anywhere and removed from the forwarded arguments. '
                     'Omitting categories selects every leaf. Host and VM workflows have '
                     'separate sessions; attach or stop using the same scope.')
    args, categories = parser.parse_known_args(argv)
    args.categories = categories
    if args.rounds < 1:
        parser.error('--rounds must be a positive integer')
    root = Path(__file__).resolve().parents[1]
    run = None
    requested = args.stop

    def cancel(*_):
        nonlocal requested
        requested = True
        if run is not None:
            (run / 'cancel').touch(mode=0o600)

    previous = signal.signal(signal.SIGINT, cancel)
    try:
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
                              categories=args.categories, rounds=args.rounds)
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
    if mode == '--worker':
        sys.exit(worker(Path(root), Path(run), int(owner), *options))
    if mode == '--supervise':
        sys.exit(supervise(Path(root), Path(run), int(owner), *options))
    raise SystemExit('private fix-tests worker entry point')
