"""Scripted test orchestration. Each repair is a fresh, ephemeral Codex process.

Only the worker owns loop state. Observers may disappear at any time. A small
subprocess supervisor retains the owner lock and watches its parent's pipe, so
even SIGKILL of the worker cancels the current operation before releasing it.
"""

import argparse
import json
import os
from pathlib import Path
import re
import shutil
import signal
import subprocess
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent))
from regression_session import FRAME_DIRECTORY, busy, lock
from test_commands import suite_inventory
from detached_launcher import (
    Stopped, atomic, private_directory, current_run, environment, agent_command,
    compact_log, TAIL_BYTES,
)
import detached_launcher


DEFAULT_EFFORT = 'high'
APP_EFFORT = 'high'
STALE_RETENTION = 'retention: previous owner did not finish; preserve evidence for recovery'


def available_models():
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
              and isinstance(entry.get('priority'), int)
              and not isinstance(entry.get('priority'), bool)
              and isinstance(entry.get('supported_reasoning_levels'), list)
              and any(isinstance(level, dict) and level.get('effort') == 'high'
                      for level in entry['supported_reasoning_levels'])]
    sol = [entry for entry in listed
           if re.fullmatch(r'gpt-(\d+(?:\.\d+)*)-sol', entry['slug'])]
    if not sol:
        raise ValueError('Codex model catalog has no listed high-reasoning Sol model')
    newest_sol = max(sol, key=lambda entry: tuple(
        int(part) for part in entry['slug'][4:-4].split('.')))
    strongest = min(listed, key=lambda entry: entry['priority'])
    return newest_sol['slug'], strongest['slug']


def repair_prompt(prompt, *, app_issue=None):
    instructions = (
        'Classify the failure from the evidence as a test issue, an app issue, or '
        'uncertain before editing. If it is a test issue, fix it in this session '
        'and return status "test_fixed". If it is an app issue, make no edits and return '
        'status "app_issue" with a concise reason. If classification remains '
        'uncertain, make no edits and return status "uncertain" with the competing '
        'explanations. The launcher will start a stronger agent for either of the '
        'last two statuses. '
        if app_issue is None else
        'The first session classified this as an app issue or uncertain and ended. '
        'Recheck the classification using the original failure evidence, then fix '
        'the root cause in this checkout. Return status "fixed" after a repair. '
        f'Its classification was: {app_issue}\n\n')
    return (prompt + '\n\n'
            'This is one independent repair attempt in tools/fix-tests. '
            + instructions + 'Preserve unrelated work. Follow AGENTS.md '
            'and docs/Approval-Tools.md. Do not change expected product behavior or weaken, '
            'skip or delete tests to obtain a pass. Report any missing authority or '
            'prerequisite using status "blocked" in the final result. '
            'The script owns test execution: finish after classification or repair; '
            'do not launch tests, fix-tests, background jobs or other agent sessions. '
            'Do not read or resume previous Codex sessions, histories, memories or repair '
            'transcripts. Use only this failure handoff and the current repository.\n')


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


def category_inventory(output):
    inventory = json.loads(output)
    if not isinstance(inventory, dict) or not inventory:
        raise ValueError('run-tests returned no implemented leaf categories')
    for category, spec in inventory.items():
        if (not isinstance(category, str) or not category or category.startswith('-')
                or not isinstance(spec, dict) or not isinstance(spec.get('args'), list)
                or not all(isinstance(arg, str) for arg in spec['args'])):
            raise ValueError('invalid run-tests category inventory')
    # The runner owns eligibility. Order the available leaves without requiring
    # an unimplemented category just to satisfy a positional check.
    return {category: inventory[category] for category in (
        *(name for name in ('unit', 'ui') if name in inventory),
        *(name for name in inventory if name not in ('unit', 'ui', 'system', 'e2e')),
        *(name for name in ('system', 'e2e') if name in inventory))}


def category_status(category, categories):
    try:
        index = categories.index(category)
    except ValueError:
        return None
    return (f'\033[1;36mRunning category [{category}] '
            f'({index + 1}/{len(categories)})\033[0m')


def run_loop(categories, test, repair, check_stop, *, selected=False, round_changed=lambda _: None):
    """No session objects or past prompts survive a repair/category iteration."""
    def finish_category(category, failure):
        while failure is not None:
            check_stop()
            repair(failure['prompt'])
            check_stop()
            failure = test(category)

    round_changed(1)
    for category in categories:
        check_stop()
        finish_category(category, test(category))
    round_changed(2)
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
        command = [str(root / 'tools/run-tests'), '--stop-on-error', category,
                   *json.loads(test_args)]
    elif kind == 'recovery':
        command = [str(root / 'tools/cleanup-e2e')]
    else:
        command = agent_command(root, model, effort, run)
    return detached_launcher.supervise(root, run, owner, kind, command)


def worker(root, run, owner, model, effort, app_model, requested='[]'):
    from launcher_progress import publish_progress, read_progress, repair_progress
    signal.signal(signal.SIGHUP, signal.SIG_IGN)
    round_number = 1
    operation = 0

    def round_changed(number):
        nonlocal round_number
        round_number = number

    def progress(category, status):
        nonlocal operation
        operation += 1
        index = categories.index(category) + 1 if category in categories else 1
        total = len(categories) if category in categories else 1
        summary = f'Round {round_number}: Category: {category} ({index}/{total})'
        previous = repair_progress(run, read_progress(run))
        if status == 'fixing errors' and previous:
            summary = previous[-1]['lines'][0]
        publish_progress(run, str(operation), [summary, 'Status: ' + status])

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
                print('fix-tests: interrupted test ownership found; recovering both retention scopes.',
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

    def repair(prompt):
        progress('', 'fixing errors')
        print(f'\nfix-tests: classify and repair ({model}, {effort})', flush=True)
        (run / 'prompt.txt').write_text(repair_prompt(prompt), encoding='utf-8')
        # Truncate only our own last reply; an agent crash cannot reuse it.
        (run / 'agent-result.json').write_text('')
        status = execute('agent')
        if status:
            raise ValueError(f'repair agent exited with status {status}; inspect the output before restarting')
        result = json.loads((run / 'agent-result.json').read_text())
        if not isinstance(result, dict):
            raise ValueError('repair agent did not return a result object')
        if result.get('status') in ('app_issue', 'uncertain'):
            classification = result['status'] + ': ' + str(result.get('summary', ''))
            print(f'\nfix-tests: app review ({app_model}, {APP_EFFORT}); {classification}',
                  flush=True)
            (run / 'prompt.txt').write_text(
                repair_prompt(prompt, app_issue=classification), encoding='utf-8')
            (run / 'agent-result.json').write_text('')
            status = execute('agent', agent_model=app_model, agent_effort=APP_EFFORT)
            if status:
                raise ValueError(f'app review agent exited with status {status}; '
                                 'inspect the output before restarting')
            result = json.loads((run / 'agent-result.json').read_text())
            if not isinstance(result, dict):
                raise ValueError('app review agent did not return a result object')
            if result.get('status') != 'fixed':
                raise ValueError('repair blocked: ' + str(result.get('summary', 'no repair result')))
        elif result.get('status') != 'test_fixed':
            raise ValueError('repair blocked: ' + str(result.get('summary', 'no repair result')))

    status = 1
    try:
        try:
            from launcher_render import AgentRenderer  # Check before expensive tests.
        except ImportError as error:
            raise ValueError('agent rendering requires the setup-provided python3-rich package') from error
        agent_command(root, model, effort)  # Fail before running expensive tests.
        listing = subprocess.run([str(root / 'tools/run-tests'), '--list'], cwd=root,
                                 env=environment(), capture_output=True, text=True, check=True)
        requested = json.loads(requested)
        inventory = suite_inventory(requested, inventory=category_inventory(listing.stdout))
        categories = list(inventory)
        print('fix-tests: category pass, then ' +
              ('selected leaf passes' if requested else 'complete all passes') +
              ' until success', flush=True)
        print('fix-tests: categories: ' + ', '.join(categories), flush=True)
        run_loop(categories, test, repair, check_stop, selected=bool(requested),
                 round_changed=round_changed)
        print('\nfix-tests: ' + ('all selected categories passed.' if requested else
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


def select(root, *, stop=False, model=None, effort=DEFAULT_EFFORT, categories=()):
    legacy = root / 'artifacts/fix-tests'
    if (legacy / 'owner').exists():
        with lock(legacy / 'owner') as owner:
            if busy(owner):
                run = current_run(legacy)
                if run is None:
                    raise ValueError('active legacy fix-tests owner has no readable run record')
                if stop:
                    (run / 'cancel').touch(mode=0o600)
                return run, False
    def command(run, owner):
        default_model, app_model = available_models()
        return ['/usr/bin/python3', '-IBu', str(Path(__file__).resolve()),
                '--worker', str(root), str(run), str(owner), model or default_model,
                effort, app_model, json.dumps(categories)]

    return detached_launcher.select(root, 'fix-tests', command, stop=stop)


def follow(run, stream=None):
    return detached_launcher.follow(run, stream, label='fix-tests')


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__, allow_abbrev=False)
    parser.add_argument('--stop', action='store_true', help='stop the active run, like Ctrl+C')
    parser.add_argument('--model', help='initial repair model (default: latest available Sol)')
    parser.add_argument('--effort', choices=('low', 'medium', 'high', 'xhigh'),
                        default=DEFAULT_EFFORT, help='reasoning effort (default: high)')
    parser.add_argument('categories', nargs='*', metavar='CATEGORY',
                        help='leaf categories, host (or host-builds), or all; accepts "unit ui"; '
                             'omitting categories preserves the full regression loop')
    args = parser.parse_args(argv)
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
        run, started = select(root, stop=requested, model=args.model, effort=args.effort,
                              categories=args.categories)
        if run is None:
            print('fix-tests: no active launcher.')
            return 0
        if requested:
            cancel()
        print(f'fix-tests: {"started" if started else "attached to"} {run.name}; log: {run / "output"}', flush=True)
        print('Closing the terminal detaches. Ctrl+C or tools/fix-tests --stop cancels.', flush=True)
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
