"""Repair-specific Git close-out after launcher-owned case verification."""

import json

import detached_launcher as launcher
from launcher_git import (closeout_lock, finish_commit, git_output, propagate_worktrees, stage_task, validate_closeout_ownership,
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
        entry['fingerprints'] = {path: validated_fingerprint(self.root / path)
                                 for path in entry['stage_paths']}
        self.save()

    def verified(self, target):
        key = self.key(target)
        entry = self.state['repairs'].get(key)
        if entry is None:  # The loop can report the same pass again at category completion.
            return
        self.state['pending'] = key
        self.save()  # Retain acceptance before staging, committing or pushing.
        self.finish_pending()

    def finish_pending(self):
        with closeout_lock(self.root, self.run, self.state):
            self._finish_pending()

    def _finish_pending(self):
        key = self.state.get('pending')
        if key is None:
            return
        entry = self.state['repairs'][key]
        identity, _ = validate_pull_identity(self.root, self.state)
        if 'pull_intent' not in self.state:
            # Reuse shared branch/upstream recovery guards, without pulling or
            # changing the source that the repair launcher just validated.
            self.state['pull_intent'] = identity
            self.save()
        paths = entry['stage_paths']
        def check_files():
            if any(validated_fingerprint(self.root / path) != entry['fingerprints'][path]
                   for path in entry['stage_paths']):
                raise ValueError('validated repair files changed; revalidate before Git close-out')
        check_files()
        if self.state.get('commit_intent') is None:
            validate_closeout_ownership(self.root, paths, entry)
            self.save()
            paths = stage_task(self.root, paths)
        else:
            paths = self.state['commit_intent']['paths']
        check_files()
        category, case, vm = entry['failure']
        message = f'TA: Fixed {category} {case or "infrastructure"}' + (f' on {vm}' if vm else '')
        commit = finish_commit(self.root, self.run, self.state, paths, message)
        validate_pull_identity(self.root, self.state)
        pushed = git_output(self.root, 'push', check=False)
        if pushed.returncode:
            raise ValueError('repair push failed: ' + pushed.stderr.strip())
        propagate_worktrees(self.root, self.run, self.state, commit, git=git_output)
        print(f'fix-tests: committed and pushed verified repair: {commit}', flush=True)
        del self.state['repairs'][key]
        for field in ('pending', 'commit_intent', 'pull_intent', 'worktree_propagation'):
            self.state.pop(field, None)
        self.save()

    def require_complete(self):
        if any(entry.get('status') in ('fixed', 'test_fixed') for entry in self.state['repairs'].values()):
            raise ValueError('repair case has no confirmed pass; retained Git close-out needs verification')
