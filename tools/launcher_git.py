"""Shared literal-path Git close-out and identity-checked commit recovery."""

import hashlib
from contextlib import nullcontext
import json
import os
from pathlib import Path
import stat
import subprocess

import detached_launcher as launcher


class GitReconciliationRequired(ValueError):
    """The current task needs a coordinator before Git close-out can proceed."""


class OwnershipReconciliationRequired(GitReconciliationRequired):
    """Reported close-out paths still contain protected pre-existing work."""

    def __init__(self, paths):
        self.paths = sorted(paths)
        super().__init__('close-out overlaps pre-existing work: ' + ', '.join(self.paths))


def reconciliation_instructions(state):
    if not state.get('git_reconciliation'):
        return ''
    accepted = state['git_reconciliation'].get('accepted_result', {})
    evidence = {key: accepted[key] for key in ('checks', 'cleanup_complete', 'stage_paths', 'handoff')
                if key in accepted}
    if state['git_reconciliation'].get('ownership_paths'):
        return f"""
Git ownership reconciliation takes priority before completing this same task:
{state['git_reconciliation']['reason']}
Retained acceptance evidence and close-out scope:
{json.dumps(evidence, indent=2)}
The original stage_baseline fingerprints and protected_staged paths still apply.
Inspect the reported paths against the retained baseline, current HEAD and index.
Remove an unrelated path from stage_paths only if this task needs no change to it.
Do not drop a required task edit to avoid the guard. Never clear or rewrite the
ownership checkpoint, adopt uncommitted pre-existing work, stage or commit that
work, or discard changes. A later commit touching a path alone does not prove
that its captured contents were committed. If ownership cannot be established,
restore the task's unchecked row, brief and pointer and return blocked with the
exact paths and the decision or original-owner action needed to proceed.
Re-run acceptance whose inputs changed; reuse only unaffected evidence. Retain
the same task, targets and cleanup requirements. Leave completion commits and
pushes to the controller; no task completion credit has been granted.
"""
    return f"""
Git reconciliation takes priority before completing this same task:
{state['git_reconciliation']['reason']}
The retained task already passed acceptance before Git close-out. Inspect current
edits and upstream changes, reconcile them with the task and resolve merge conflicts.
Retained acceptance evidence and close-out scope:
{json.dumps(evidence, indent=2)}
Preserve unrelated staged, unstaged and untracked work; never discard changes,
force-push, rewrite published history or choose ours/theirs wholesale.
For this reconciliation only, you may use the necessary Git inspection, fetch,
pull, path-scoped staging/stash and merge-completion commands. Complete an
upstream merge commit if necessary, but leave the task completion commit and push
to the controller. Use the current branch and its configured upstream without
changing Git configuration. Disable automatic stashing on pulls. Record any
temporary stash identity and restore it, including its original index state,
before reporting completion. Do not stash unrelated work.
Recheck the retained task's scope, queue, targets and cleanup. Re-run acceptance
whose inputs changed; reuse only unaffected evidence. Restore the task's unchecked
row, brief and pointer if returning an incomplete result. Never select another
task or weaken acceptance to finish this reconciliation.
"""


def validate_pull_identity(root, state, *, git=None):
    """Retain the branch and upstream through merge, commit and push recovery."""
    git = git or git_output
    branch = git(root, 'symbolic-ref', '--quiet', '--short', 'HEAD', check=False)
    upstream = git(root, 'rev-parse', '--abbrev-ref', '--symbolic-full-name', '@{upstream}', check=False)
    head = git(root, 'rev-parse', '--verify', 'HEAD', check=False)
    if branch.returncode or upstream.returncode or head.returncode:
        raise ValueError('completion pull needs a current branch, HEAD and configured upstream; '
                         + (branch.stderr + upstream.stderr + head.stderr).strip())
    identity = dict(branch=branch.stdout.strip(), upstream=upstream.stdout.strip())
    reconciliation = state.get('git_reconciliation', {})
    if any(key in reconciliation and reconciliation[key] != value for key, value in identity.items()):
        raise GitReconciliationRequired('branch or upstream changed during Git reconciliation; '
                                        'restore the retained identity without adopting another owner\'s work')
    intent = state.get('pull_intent')
    if intent is not None and any(intent[key] != value for key, value in identity.items()):
        raise GitReconciliationRequired('branch or upstream changed during completion pull; '
                                        'restore the retained identity without adopting another owner\'s work')
    return identity, head.stdout.strip()


def pull_before_commit(root, run, state, *, git=None):
    """Pull before a new commit; checkpoint updates needing fresh acceptance.

    No autostash: a dirty-file refusal leaves caller and concurrent work in
    place for a scoped coordinator reconciliation. Never pull during recovery
    of an existing commit intent, whose exact immediate parent must be retained.
    """
    git = git or git_output
    identity, head = validate_pull_identity(root, state, git=git)
    intent = state.get('pull_intent')
    if state.get('commit_intent') is not None:
        if intent is None:
            raise ValueError('pending completion commit has no retained branch/upstream identity; '
                             'inspect its checkpoint before manual Git close-out')
        return
    if intent is None:
        intent = state['pull_intent'] = dict(identity, head=head)
        launcher.atomic(run / 'checkpoint.json', state)
    if head != intent['head']:
        raise GitReconciliationRequired('Upstream pull changed HEAD; reconcile and revalidate the accepted task.')
    # Explicitly override merge.autoStash; preserving unrelated index work is
    # more important than silently moving the entire dirty checkout to a stash.
    pulled = git(root, 'pull', '--no-rebase', '--ff', '--no-edit', '--no-autostash', check=False)
    conflicts = git(root, 'diff', '--name-only', '--diff-filter=U', '-z').stdout
    merge = git(root, 'rev-parse', '--verify', 'MERGE_HEAD', check=False)
    after = git(root, 'rev-parse', '--verify', 'HEAD').stdout.strip()
    validate_pull_identity(root, state, git=git)
    if conflicts or (merge.returncode == 0 and merge.stdout.strip()) or after != intent['head']:
        raise GitReconciliationRequired('Upstream pull requires reconciliation and renewed acceptance.\n'
                                        + pulled.stderr.strip())
    if pulled.returncode:
        diagnostic = pulled.stderr.strip()
        if ('would be overwritten by merge' in diagnostic
                or 'Please commit your changes or stash them' in diagnostic):
            raise GitReconciliationRequired('Pull needs scoped reconciliation of local task edits.\n' + diagnostic)
        raise ValueError('completion pull failed: ' + diagnostic)


def stage_task(root, paths, *, required_paths=()):
    """Stage only explicit reported files; never interpret Git pathspec magic."""
    paths = list(dict.fromkeys(paths))
    if not set(required_paths).issubset(paths):
        raise ValueError('completed task must include plan and queue in stage_paths')
    for value in paths:
        path = Path(value)
        if (not value or '\x00' in value or path.is_absolute() or '..' in path.parts
                or '.git' in path.parts or path.parts[:1] == ('output',)
                or value != path.as_posix() or path == Path('.')
                or (root / path).is_dir()
                or any(parent.is_symlink() for parent in (root / path).parents if parent != root)):
            raise ValueError('stage_paths must contain explicit checkout files')
    indexed = subprocess.run(
        ['git', '--literal-pathspecs', 'ls-files', '--cached', '-z', '--', *paths],
        cwd=root, env=launcher.environment(), capture_output=True, check=True)
    tracked = {os.fsdecode(path) for path in indexed.stdout.split(b'\0') if path}
    # A temporary brief can be created and removed before ever entering the
    # index. It has no deletion to stage. Keep indexed deletions and symlinks.
    paths = [path for path in paths if path in tracked or os.path.lexists(root / path)]
    if not paths:
        return []
    result = subprocess.run(['git', '--literal-pathspecs', 'add', '--', *paths], cwd=root,
                            env=launcher.environment(), capture_output=True, text=True)
    if result.returncode:
        raise ValueError('task staging failed: ' + result.stderr.strip())
    return paths


def worktree_fingerprint(path):
    if path.is_symlink():
        return 'link:' + os.readlink(path)
    if path.is_file():
        digest = hashlib.sha256()
        with path.open('rb') as source:
            for block in iter(lambda: source.read(1024 * 1024), b''):
                digest.update(block)
        return 'file:' + digest.hexdigest()
    return 'deleted'


def worktree_snapshot(root):
    """Fingerprint unstaged and untracked files without including existing index work."""
    result = subprocess.run(
        ['git', 'ls-files', '--modified', '--deleted', '--others',
         '--exclude-standard', '-z'], cwd=root, env=launcher.environment(),
        capture_output=True, check=True)
    return {os.fsdecode(raw): worktree_fingerprint(root / os.fsdecode(raw))
            for raw in result.stdout.split(b'\0') if raw and not raw.startswith(b'output/')}


def session_changes(root, before):
    after = worktree_snapshot(root)
    return [name for name, fingerprint in after.items()
            if before.get(name) != fingerprint]


def committed_fingerprints(root, paths):
    """Read a baseline's committed bytes with two Git processes, regardless of size.

    Read blobs as bytes, including binary files and symlink targets. A retained
    dirty baseline may have been committed by another workflow since capture.
    Tree names are NUL-delimited; only object IDs enter the cat-file protocol.
    """
    result = dict.fromkeys(paths, 'deleted')
    if not result:
        return result
    tree = subprocess.run(['git', 'ls-tree', '-rtz', 'HEAD'], cwd=root,
                          env=launcher.environment(), capture_output=True, check=True).stdout
    entries = {}
    for entry in tree.split(b'\0'):
        if not entry:
            continue
        metadata, name = entry.split(b'\t', 1)
        path = os.fsdecode(name)
        if path not in result:
            continue
        mode, kind, identity = metadata.split()
        if kind != b'blob' or mode not in (b'100644', b'100755', b'120000'):
            result[path] = None
            continue
        # Legacy checkpoints omit executable mode. Require the current file to
        # prove that mode, even when core.filemode or assume-unchanged hides it.
        if mode != b'120000':
            try:
                current = (root / path).lstat()
            except FileNotFoundError:
                current = None
            if (current is None or not stat.S_ISREG(current.st_mode)
                    or bool(current.st_mode & stat.S_IXUSR) != (mode == b'100755')):
                result[path] = None
                continue
        entries[path] = mode, identity
    identities = list(dict.fromkeys(identity for _, identity in entries.values()))
    contents = {}
    if identities:
        data = subprocess.run(['git', 'cat-file', '--batch'], cwd=root,
                              env=launcher.environment(), input=b'\n'.join(identities) + b'\n',
                              capture_output=True, check=True).stdout
        offset = 0
        for identity in identities:
            end = data.index(b'\n', offset)
            found, kind, size = data[offset:end].split()
            size = int(size)
            offset = end + 1
            content = data[offset:offset + size]
            if (found != identity or kind != b'blob' or len(content) != size
                    or data[offset + size:offset + size + 1] != b'\n'):
                raise ValueError('invalid committed blob response')
            contents[identity] = content
            offset += size + 1
        if offset != len(data):
            raise ValueError('unexpected committed blob response')
    for path, (mode, identity) in entries.items():
        content = contents[identity]
        result[path] = ('link:' + os.fsdecode(content) if mode == b'120000'
                        else 'file:' + hashlib.sha256(content).hexdigest())
    return result


def validate_closeout_ownership(root, paths, state):
    """Protect pending work without pinning clean files to an old baseline."""
    baseline = state['stage_baseline']
    protected = set(state['protected_staged'])
    overlap = set(paths) & protected
    released = {}
    clean_paths = set()
    committed_paths = committed_fingerprints(root, set(baseline) - protected)
    indexed = (set(filter(None, git_output(root, 'diff', '--cached', '--no-renames', '--name-only', '-z',
                                          'HEAD').stdout.split('\0')))
               if committed_paths else set())
    for path in baseline:
        if path not in protected:
            committed = committed_paths[path]
            clean = (committed is not None
                     and worktree_fingerprint(root / path) == committed
                     and path not in indexed)
            if clean:
                clean_paths.add(path)
            if clean or (path in paths and committed == baseline[path]):
                released[path] = baseline[path]
            elif path in paths:
                overlap.add(path)
    if overlap:
        raise OwnershipReconciliationRequired(overlap)

    def retire(saved):
        # Release clean paths before the next task edits them, including inherited
        # copies. For dirty paths, retire only the proven committed fingerprint.
        for field in ('stage_baseline', 'replan_baseline'):
            if field in saved:
                saved[field] = {path: value for path, value in saved[field].items()
                                if path not in clean_paths
                                and (path not in released or released[path] != value)}
        for consumer in saved.get('suspended_tasks', {}).values():
            retire(consumer)

    retire(state)  # The caller checkpoints this before any Git write.


def git_output(root, *arguments, check=True):
    return subprocess.run(['git', *arguments], cwd=root,
                          env=dict(launcher.environment(), LC_ALL='C', GIT_TERMINAL_PROMPT='0'),
                          stdin=subprocess.DEVNULL, capture_output=True, text=True, check=check)


def closeout_lock(root, run, state):
    """Serialize source Git writes with reverse-direction destination updates."""
    if not (root / 'config/worktree.json').exists() and not state.get('worktree_propagation'):
        return nullcontext()
    from launcher_worktrees import transaction_lock
    return transaction_lock(root, run)


def propagate_worktrees(root, run, state, commit, *, git=None):
    """Shared post-push boundary for ordinary plans, E2E and verified repairs."""
    if not (root / 'config/worktree.json').exists() and not state.get('worktree_propagation'):
        return
    from launcher_worktrees import propagate
    propagate(root, run, state, commit, git=git or git_output)


def finish_commit(root, run, state, paths, message, *, git=None):
    """Checkpoint commit intent before writing Git, and recognize a completed write."""
    git = git or git_output
    head = git(root, 'rev-parse', '--verify', 'HEAD', check=False)
    parent = head.stdout.strip() if head.returncode == 0 else None
    intent = state.get('commit_intent')
    if intent is not None:
        if intent['message'] != message or intent['paths'] != paths:
            raise ValueError('completion commit scope changed; inspect retained checkpoint')
        recorded = intent.get('commit') or state.get('worktree_propagation', {}).get('commit')
        if parent != intent['parent'] or recorded:
            # A worker may die after Git commits but before the checkpoint is saved.
            # Once recorded, verify that immutable commit rather than later task
            # edits. Older propagation checkpoints already pin the same identity.
            commit = recorded or parent
            if git(root, 'merge-base', '--is-ancestor', commit, 'HEAD', check=False).returncode:
                raise ValueError('HEAD changed outside pending completion commit; inspect checkpoint')
            subject = git(root, 'log', '-1', '--format=%s', commit).stdout.strip()
            parents = git(root, 'log', '-1', '--format=%P', commit).stdout.strip()
            changed = git(root, 'diff-tree', '--root', '--no-commit-id',
                                 '--name-only', '-r', '-z', commit).stdout.split('\0')
            tree = (git(root, '--literal-pathspecs', 'ls-tree', '-r', '-z', commit,
                        '--', *paths).stdout if paths else '')
            entries = ''
            for entry in filter(None, tree.split('\0')):
                metadata, path = entry.split('\t', 1)
                mode, _kind, identity = metadata.split()
                entries += f'{mode} {identity} 0\t{path}\0'
            matches = entries == intent['entries']
            # The immutable commit proves this write. Later index/worktree
            # edits belong to their owner and cannot invalidate that commit.
            if (subject != message or parents != (intent['parent'] or '')
                    or not set(filter(None, changed)).issubset(paths) or not matches):
                raise ValueError('HEAD changed outside pending completion commit; inspect checkpoint')
            if intent.get('commit') != commit:
                intent['commit'] = commit
                launcher.atomic(run / 'checkpoint.json', state)
            return commit
    else:
        entries = (git(root, '--literal-pathspecs', 'ls-files', '--stage', '-z',
                             '--', *paths).stdout if paths else '')
        state['commit_intent'] = {'parent': parent, 'message': message, 'paths': paths,
                                  'entries': entries}
        launcher.atomic(run / 'checkpoint.json', state)
    if paths:
        entries = git(root, '--literal-pathspecs', 'ls-files', '--stage', '-z',
                             '--', *paths).stdout
        if (entries != state['commit_intent']['entries']
                or git(root, '--literal-pathspecs', 'diff', '--quiet', '--',
                              *paths, check=False).returncode != 0):
            # No commit was written. Reuse the ordinary reconciliation loop to
            # inspect current edits and renew acceptance before staging again.
            state.pop('commit_intent')
            launcher.atomic(run / 'checkpoint.json', state)
            raise GitReconciliationRequired('Owned files changed after staging; reconcile and revalidate the task.')
    # --only prevents unrelated pre-staged files from entering either commit.
    # An audit with no edits still records its completed checkpoint as an empty commit.
    arguments = ['--literal-pathspecs', 'commit', '--only', '--allow-empty', '-m', message]
    if paths:
        arguments += ['--', *paths]
    result = git(root, *arguments, check=False)
    if result.returncode:
        raise ValueError('completion commit failed: ' + result.stderr.strip())
    # Verify the same committed write on the normal path as on recovery; hooks
    # must not silently change the validated content or include unrelated files.
    return finish_commit(root, run, state, paths, message, git=git)
