"""Repair-specific Git close-out after launcher-owned case verification."""

import json

import detached_launcher as launcher
from launcher_git import (closeout_lock, commit_push_propagate, git_output, stage_task, validate_closeout_ownership,
                          validate_pull_identity, worktree_fingerprint, worktree_snapshot,
                          session_changes)


def validated_fingerprint(path):
    try:
        mode = path.lstat().st_mode
    except FileNotFoundError:
        mode = None
    return dict(content=worktree_fingerprint(path), mode=mode)


class RepairCommits:
    def __init__(self, root, run):
        self.root, self.run = root, run
        self.guard = lambda: None
        path = run / 'checkpoint.json'
        self.state = json.loads(path.read_text()) if path.exists() else {'repairs': {}}

    def save(self):
        launcher.atomic(self.run / 'checkpoint.json', self.state)

    @staticmethod
    def key(target):
        return json.dumps(list(target))

    def begin(self, target, args=()):
        key = self.key(target)
        if key not in self.state['repairs']:
            self.state['repairs'][key] = dict(
                failure=list(target), args=list(args), stage_paths=[], stage_baseline=worktree_snapshot(self.root),
                stage_candidates=[],
                protected_staged=list(filter(None, git_output(
                    self.root, 'diff', '--cached', '--name-only', '-z').stdout.split('\0'))))
            self.save()
        elif self.state['repairs'][key]['args'] != list(args):
            raise ValueError('pending repair selectors changed; resume the original selection')

    def capture_session(self, target, before):
        entry = self.state['repairs'][self.key(target)]
        entry['stage_candidates'] = list(dict.fromkeys([
            *entry['stage_candidates'], *session_changes(self.root, before)]))
        self.save()

    def validate_paths(self, target, result):
        entry = self.state['repairs'][self.key(target)]
        missing = set(entry['stage_candidates']) - set(entry['stage_paths']) - set(result.get('stage_paths', []))
        if missing:
            raise ValueError('repair omitted changed files from stage_paths: ' + ', '.join(sorted(missing)))

    def record(self, target, result):
        entry = self.state['repairs'][self.key(target)]
        entry['stage_paths'] = list(dict.fromkeys([*entry['stage_paths'], *result.get('stage_paths', [])]))
        entry['status'] = result['status']
        entry['verification_case'] = result.get('verification_case')
        entry.pop('verified_case', None)
        entry['verification_after'] = self.state.get('runner_attempt', {}).get('invocation')
        entry['fingerprints'] = {path: validated_fingerprint(self.root / path)
                                 for path in entry['stage_paths']}
        self.save()

    def verified(self, target, *, attempt=None):
        key = self.key(target)
        entry = self.state['repairs'].get(key)
        if entry is None:  # The loop can report the same pass again at category completion.
            return
        if attempt is not None:
            entry['verification_attempt'] = attempt
        self.state['pending'] = key
        self.save()  # Retain acceptance before staging, committing or pushing.
        self.finish_pending()

    def finish_pending(self):
        with closeout_lock(self.root, self.run, self.state):
            self._finish_pending()

    def validate_ownership(self, entry):
        # A diagnostic for another case can leave edits that this repair builds
        # on. Prove that exact baseline belongs to this launcher, tracing back
        # to a clean start; a reported path alone is not ownership evidence.
        scope = dict(entry, stage_baseline=dict(entry['stage_baseline']))
        recovered = []
        provenance = list(self.state['repairs'].values())
        from fix_tests_queue import parent_run
        parent = parent_run(self.run)
        if parent is not None and (parent / 'checkpoint.json').exists():
            # Legacy batch repairs can share diagnostic edits across VMs. The
            # migration retains their original ownership records in the parent.
            provenance.extend(json.loads((parent / 'checkpoint.json').read_text()).get('repairs', {}).values())
        for path in entry['stage_paths']:
            if path not in scope['stage_baseline']:
                continue
            owners = [other for other in provenance
                      if other.get('status') in ('diagnostic_ready', 'fixed', 'test_fixed')
                      and path in other['stage_paths'] and path in other['stage_candidates']
                      and path not in other['protected_staged'] and path in other.get('fingerprints', {})]
            owned = set()
            while True:
                before = set(owned)
                for other in owners:
                    baseline = other['stage_baseline'].get(path)
                    if baseline is None or baseline in owned:
                        owned.add(other['fingerprints'][path]['content'])
                if owned == before:
                    break
            if scope['stage_baseline'][path] in owned:
                del scope['stage_baseline'][path]
                recovered.append(path)
        # Keep the original checkpoints as provenance for later repairs/restart.
        # In particular, never release pre-existing staged work through this path.
        validate_closeout_ownership(self.root, entry['stage_paths'], scope)
        if recovered:
            print('fix-tests: recovered launcher-owned overlap: ' + ', '.join(recovered), flush=True)

    def _finish_pending(self):
        key = self.state.get('pending')
        if key is None:
            return
        self.guard()
        entry = self.state['repairs'][key]
        if entry.get('pending_response') is not None:
            raise ValueError('retained repair response needs current validation before Git close-out')
        # verified() recorded the completed case before this Git transaction.
        # Later edits and report rotation do not invalidate that recorded pass.
        identity, _ = validate_pull_identity(self.root, self.state)
        if 'pull_intent' not in self.state:
            # Reuse shared branch/upstream recovery guards, without pulling or
            # changing the source that the repair launcher just validated.
            self.state['pull_intent'] = identity
            self.save()
        paths = entry['stage_paths']
        if self.state.get('commit_intent') is None:
            self.validate_ownership(entry)
            self.save()
            paths = stage_task(self.root, paths)
        else:
            paths = self.state['commit_intent']['paths']
        category, case, vm = entry['failure']
        message = f'TA: Fixed {category} {case or "infrastructure"}' + (f' on {vm}' if vm else '')
        commit = commit_push_propagate(self.root, self.run, self.state, paths, message, git=git_output)
        print(f'fix-tests: committed and pushed verified repair: {commit}', flush=True)
        self.state['last_commit'] = commit
        queued = self.state.get('queued_failure')
        if queued is not None:
            from fix_tests import failure_target
            if failure_target(queued['failure'], queued['category']) == tuple(entry['failure']):
                self.state.pop('queued_failure')
        del self.state['repairs'][key]
        for field in ('pending', 'commit_intent', 'pull_intent', 'worktree_propagation'):
            self.state.pop(field, None)
        self.save()

    def require_complete(self):
        if any(entry.get('pending_response') is not None for entry in self.state['repairs'].values()):
            raise ValueError('retained repair response has not been validated by this controller')
        if any(entry.get('status') in ('fixed', 'test_fixed') for entry in self.state['repairs'].values()):
            raise ValueError('repair case has no confirmed pass; retained Git close-out needs verification')
