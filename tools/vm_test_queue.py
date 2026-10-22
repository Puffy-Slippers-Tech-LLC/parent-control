"""Finite configured VM queue; workers use the maintained guarded controllers."""

import json
import os
from contextlib import contextmanager
from pathlib import Path
import sys
import tempfile
import threading
import uuid

# Workers use isolated Python; restore only this checkout's sibling modules.
if __name__ == '__main__':
    sys.path.insert(0, str(Path(__file__).resolve().parent))

import test_activity
import test_launcher
import test_retention
from regression_process import Control, FRAME_PREFIX
from vm_selection import BATCH, VARIABLE, vm_config
from vm_queue import dispatch


def worker_cleanup(root, target, status, proofs, invocation):
    """Only a verified worker closure can report its cleanup to the batch."""
    if not proofs:
        return 'pending'
    import evidence_identity as logical
    from runner_evidence import resolve_reference
    expected = 'interrupted' if status == 130 else 'failed' if status else 'passed'
    for proof in proofs:
        records = proof['records']
        if not records:
            raise ValueError('runner evidence: worker closure has no records')
        for record in records:
            logical._record(record)
            references = [reference for reference in proof['references']
                          if reference['record_id'] == record['record_id']]
            if not references or references[0]['closure_sha256'] != record['closure_sha256']:
                raise ValueError('runner evidence: worker closure changed')
            resolve_reference(root, references[0])
        terminal = records[-1]
        if terminal['context']['check'] != 'report' or terminal['status'] != expected:
            raise ValueError('runner evidence: worker result does not match its closure')
        if not any(record['context']['target'] == target for record in records):
            raise ValueError('runner evidence: worker target does not match its closure')
        inputs = [member for member in terminal['members'] if member['role'] == 'input'
                  and member['sha256'] == terminal['context']['inputs_sha256']]
        if not inputs:
            raise ValueError('runner evidence: worker selection is missing')
        reference = next(reference for reference in proof['references']
                         if reference['member_id'] == inputs[0]['member_id'])
        payload = json.loads(resolve_reference(root, reference))
        if payload['invocation'] != json.loads(json.dumps(invocation)) or invocation['target'] != target:
            raise ValueError('runner evidence: worker invocation does not match its selection')
    states = [proof['records'][-1]['cleanup']['state'] for proof in proofs]
    return 'failed' if 'failed' in states else 'pending' if 'pending' in states else 'complete'


@contextmanager
def batch_evidence(root, store, vms, selection):
    """Retain a truthful partial terminal closure if join processing fails."""
    from runner_evidence import ReportEvidence
    evidence = Path(test_retention.allocate(tempfile.mkdtemp, prefix='onpc-vm-queue-'))
    captured = ReportEvidence(root, evidence, store=store, workflow='vm-test-queue')
    captured.terminal_attempted = False
    try:
        yield evidence, captured
    except BaseException as error:
        # dispatch drains its owned pool before raising. Nothing here signals a
        # child or adopts a worker's independently owned allocation.
        if not captured.terminal_attempted:
            try:
                failure = evidence / 'runner-error.json'
                with failure.open('x', encoding='utf-8') as stream:
                    os.fchmod(stream.fileno(), 0o600)
                    json.dump(dict(error=type(error).__name__, detail=str(error)[:4096],
                                   selection=selection, targets=[vm.name for vm in vms]), stream)
                    stream.flush()
                    os.fsync(stream.fileno())
                members = [dict(path=failure, role='result')]
                members.extend(dict(path=evidence / name, role='command' if name.endswith('.log') else 'result')
                    for name in ('results.json', 'failure.json', *(vm.name + '.log' for vm in vms))
                    if (evidence / name).exists())
                captured.terminal_attempted = True
                receipt = captured.finalize(
                    categories=[dict(target=vm.name, selection=selection) for vm in vms],
                    status='interrupted' if isinstance(error, KeyboardInterrupt) else 'failed',
                    cleanup='pending', members=members)
                print('Runner evidence: ' + json.dumps(receipt, separators=(',', ':')), flush=True)
            except BaseException as capture_error:
                print('VM queue capture failed; original evidence remains required: '
                      + type(capture_error).__name__ + ': ' + str(capture_error)[:2048],
                      file=sys.stderr, flush=True)
        raise


def split(root, argv):
    from test_commands import execution_arguments, selections, AGGREGATES
    args, stop = execution_arguments(argv or ['all'])
    selected = selections(root, args)
    if len(selected) == 1 and selected[0][0] in AGGREGATES:
        selected = [('host', []), ('system', []), ('e2e', [])]
    host = [(kind, options) for kind, options in selected if kind not in ('system', 'e2e', 'integration')]
    guests = [(kind, options) for kind, options in selected if kind in ('system', 'e2e', 'integration')]
    def flatten(groups):
        result = [*(['--resume'] if '--resume' in argv else []),
                  *[arg for arg in argv if arg.startswith('--resume-case=')],
                  *(['--stop-on-error'] if stop else []),
                  *(value for kind, options in groups for value in (kind, *options))]
        if '--continue-on-errors' in args and all(kind in ('host', 'system', 'e2e') and not options
                                                for kind, options in groups):
            result.append('--continue-on-errors')
        return result
    return flatten(host) if host else [], flatten(guests)


def run(root, argv):
    from test_commands import _main, selections
    from test_checkpoint import Checkpoint
    snapshot = json.loads(os.environ[BATCH])
    configured = vm_config.registry()
    vms = tuple(configured[name] for name in snapshot['vms'])
    host_args, guest_args = split(root, argv)
    # Reset the entire requested queue before any category can fail or stop.
    # Queued VMs must not inherit older passes merely because they never start.
    guest_selection = selections(root, guest_args)
    for vm in vms:
        Checkpoint(root, guest_selection, resume='--resume' in argv, binding=vm.name)
    if host_args:
        status = _main(host_args, detached=True, checkpoint=Checkpoint(
            root, selections(root, host_args), resume='--resume' in host_args))
        if status:
            return status
    with Control().installed() as control:
        # Recovery is serial and finishes before any live VM attempt starts.
        for vm in vms:
            environment = test_launcher.environment(root)
            environment.pop(BATCH, None)
            environment[VARIABLE] = vm.name
            command = ['/usr/bin/python3', '-IBu', str(Path(__file__).resolve()),
                       '--recover', vm.name]
            status = control.run(command, cwd=root, env=environment, cooperative=True)
            if status:
                return status
        store = test_retention.Store(test_activity.retention_path(root))
        from runner_evidence import recover_pending
        recover_pending(root, store)
        with store.session() as batch_run, batch_evidence(root, store, vms, guest_selection) as (evidence, captured):
            # Named inputs are VM-bound. Each worker prepares them inside its
            # own retention session, before its independent guest execution.
            # A batch-owned allocation would conflict with that VM's old claim
            # after an interrupted input was removed and recreated.
            output_lock = threading.Lock()
            frames = {}
            invocations = {vm.name: dict(batch_run=batch_run, attempt=uuid.uuid4().hex,
                                        target=vm.name, selection=guest_selection) for vm in vms}

            def publish_frames():
                if hasattr(sys.stdout, 'frame'):
                    sys.stdout.frame([f'VM queue | concurrency {snapshot["concurrency"]}',
                                      *(line for name in snapshot['vms']
                                        for line in ([f'VM: {name}', *frames.get(name, ['Queued'])]))])

            def execute(vm):
                environment = test_launcher.environment(root)
                environment.pop(BATCH, None)
                # A worker starts its own retention session, never another VM's.
                environment.pop(test_retention.VARIABLE, None)
                environment[VARIABLE] = vm.name
                environment['ONPC_RUNNER_INVOCATION'] = json.dumps(invocations[vm.name], separators=(',', ':'))
                command = ['/usr/bin/python3', '-IBu', str(Path(__file__).resolve()),
                           '--execute', vm.name, *guest_args]
                pending = b''
                handoffs = []
                worker_evidence = []
                with (evidence / (vm.name + '.log')).open('xb') as log:
                    os.fchmod(log.fileno(), 0o600)
                    def output(data):
                        nonlocal pending
                        log.write(data)
                        log.flush()
                        pending += data
                        while b'\n' in pending:
                            line, pending = pending.split(b'\n', 1)
                            value = line.decode('utf-8', errors='replace')
                            if value.startswith('Failure handoff: '):
                                handoffs.append(value.removeprefix('Failure handoff: '))
                            if value.startswith('Runner evidence: '):
                                worker_evidence.append(json.loads(value.removeprefix('Runner evidence: ')))
                            with output_lock:
                                if value.startswith(FRAME_PREFIX):
                                    frames[vm.name] = json.loads(value[len(FRAME_PREFIX):])
                                    publish_frames()
                                else:
                                    print(f'[{vm.name}] {value}', flush=True)
                    status = control.run(command, cwd=root, env=environment,
                                         output=output, cooperative=True)
                    if pending:
                        with output_lock:
                            print(f'[{vm.name}] ' + pending.decode('utf-8', errors='replace'), flush=True)
                return {'status': status, 'handoffs': handoffs, 'evidence': worker_evidence}

            results = dispatch(vms, snapshot['concurrency'], execute, control.stopped)
            categories = []
            failures = []
            for vm in vms:
                result = results[vm.name]
                vm_categories = []
                vm_failures = []
                if isinstance(result, dict):
                    for path in result['handoffs']:
                        handoff = json.loads(Path(path).read_text())
                        vm_categories.extend(handoff['categories'])
                        vm_failures.extend(dict(item, vm=vm.name)
                                           for item in handoff.get('failures', []))
                if (result['status'] if isinstance(result, dict) else result) != 0:
                    if not vm_categories:
                        vm_categories.extend(kind for kind, _ in selections(root, guest_args)
                                             if kind in ('system', 'e2e'))
                    for category in dict.fromkeys(vm_categories):
                        if not any(item['category'] == category for item in vm_failures):
                            vm_failures.append(dict(category=category, case='', vm=vm.name))
                categories.extend(vm_categories)
                failures.extend(vm_failures)
            (evidence / 'results.json').write_text(json.dumps(results, indent=2))
            (evidence / 'results.json').chmod(0o600)
            failed = any((result['status'] if isinstance(result, dict) else result) != 0
                         for result in results.values())
            if hasattr(sys.stdout, 'frame'):
                sys.stdout.frame([])
            if failed and not control.stopped.is_set():
                prompt = f'Investigate the VM failures in {evidence / "results.json"} and adjacent VM logs. Preserve expected behavior and all unrelated work.'
                handoff = evidence / 'failure.json'
                handoff.write_text(json.dumps({'prompt': prompt, 'categories': list(dict.fromkeys(categories)),
                                              'failures': failures}))
                handoff.chmod(0o600)
                print(f'Failure handoff: {handoff}', flush=True)
            print(f'VM results: {evidence / "results.json"}', flush=True)
            # Workers finish their own records under their own journals. The
            # batch retains those references and its exact join result, without
            # adopting the workers' allocation or cleanup ownership.
            cleanup_states = []
            for vm in vms:
                result = results[vm.name]
                status = result['status'] if isinstance(result, dict) else result
                worker_proof = result.get('evidence', []) if isinstance(result, dict) else []
                cleanup_state = worker_cleanup(root, vm.name, status, worker_proof, invocations[vm.name])
                cleanup_states.append(cleanup_state)
                captured.command(dict(
                    check='worker:' + vm.name, target=vm.name,
                    selection=guest_selection, argv=guest_args,
                    status='interrupted' if status == 130 else 'failed' if status else 'passed',
                    exit_status=status, cleanup=cleanup_state,
                    provenance='worker-join', worker_evidence=worker_proof,
                    log=str(evidence / (vm.name + '.log')) if (evidence / (vm.name + '.log')).exists() else None))
            members = [dict(path=evidence / 'results.json', role='result')]
            members.extend(dict(path=evidence / (vm.name + '.log'), role='command')
                           for vm in vms if (evidence / (vm.name + '.log')).exists())
            if failed and not control.stopped.is_set():
                members.append(dict(path=evidence / 'failure.json', role='result'))
            captured.terminal_attempted = True
            receipt = captured.finalize(
                categories=results,
                status='interrupted' if control.stopped.is_set() else 'failed' if failed else 'passed',
                cleanup=('failed' if 'failed' in cleanup_states else
                         'pending' if 'pending' in cleanup_states else 'complete'), members=members)
            print('Runner evidence: ' + json.dumps(receipt, separators=(',', ':')), flush=True)
            return 130 if control.stopped.is_set() else 1 if failed else 0


def worker(argv):
    mode, name, *args = argv
    if mode not in ('--recover', '--execute'):
        raise ValueError('private VM queue entry only')
    vm_config.select(name)
    os.environ.pop(BATCH, None)
    root = Path(__file__).resolve().parents[1]
    from regression_process import PipeFrameOutput
    sys.stdout = PipeFrameOutput(sys.stdout)
    with test_activity.activity(root), Control().installed(pipe=True) as control:
        # Nested aggregate controllers observe the same parent cancellation.
        import regression_process
        regression_process.session_stop = control.stopped
        if mode == '--recover':
            from test_recovery import cleanup
            return cleanup(root)
        from test_commands import _main
        from test_checkpoint import Checkpoint
        from test_commands import selections
        checkpoint = Checkpoint(root, selections(root, args), resume='--resume' in args)
        replay = [arg.partition('=')[2] for arg in args if arg.startswith('--resume-case=')]
        if replay:
            groups = selections(root, args)
            if len(groups) != 1:
                raise ValueError('case retry requires one category')
            checkpoint.event(groups[0][0], dict(kind='failure', nodeid=replay[0]), set())
        return _main([*args, '--vm', name], detached=True, checkpoint=checkpoint)


if __name__ == '__main__':
    sys.exit(worker(sys.argv[1:]))
