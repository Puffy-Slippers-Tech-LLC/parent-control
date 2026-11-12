"""Shared literal-path Git close-out and identity-checked commit recovery."""

from contextlib import nullcontext
from functools import partial
import fcntl
import hashlib
import json
import os
from pathlib import Path
import re
import signal
import stat
import subprocess
import sys
import time
import uuid

sys.path.insert(0, str(Path(__file__).resolve().parent))

import detached_launcher as launcher
from agent_adapter import AgentSelection, resolve_profile, resolve_selection


class _OperationSelection:
    """Resolve lazily once, only if this Git operation needs an agent."""

    def __init__(self, root, selection):
        self.root, self.selection = root, selection

    def get(self):
        if self.selection is None:
            self.selection = resolve_selection(self.root)
        return self.selection


def _operation_selection(root, selection):
    return selection if isinstance(selection, _OperationSelection) else _OperationSelection(root, selection)


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
The original unstaged stage_baseline fingerprints still apply. Preserve unrelated
staged work; the commit skill reviews task ownership before committing.
Inspect the reported paths against the retained baseline, current HEAD and index.
Remove an unrelated path from stage_paths only if this task needs no change to it.
If the developer explicitly authorizes shared-hunk review, use the documented
--review-ownership control route with --check, then --approve and its exact token.
This permits only commit-skill review; preserve the original baseline and exclude
all unrelated hunks. Changed review inputs require a fresh explicit approval.
Do not drop a required task edit to avoid the guard. Never clear or rewrite the
ownership checkpoint, adopt unrelated unstaged work, stage or commit that
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
    git = git_for_run(git or git_output, run)
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
    """Validate explicit task files; the commit skill owns staging."""
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
    return [path for path in paths if path in tracked or os.path.lexists(root / path)]


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


def ownership_review_snapshot(root, run, state):
    """Pin permission to review shared hunks, without releasing their baseline."""
    paths, _, _ = _ownership_status(root,
        state.get('git_reconciliation', {}).get('ownership_paths', []), state)
    if not paths or not state.get('task_id'):
        raise ValueError('ownership review needs an unfinished ownership reconciliation')
    stage_task(root, paths)
    identity, head = validate_pull_identity(root, state)
    working = {}
    for path in paths:
        entry = root / path
        try:
            mode = entry.lstat().st_mode
        except FileNotFoundError:
            mode = None
        working[path] = dict(fingerprint=worktree_fingerprint(entry), mode=mode)
    index = subprocess.run(['git', 'ls-files', '--stage', '-z'], cwd=root,
                           env=launcher.environment(), capture_output=True, check=True).stdout
    return dict(root=str(root.resolve()), run=str(run.resolve()), task_id=state['task_id'], task=state['task'],
                plan_queue=state['plan_queue'], **identity, head=head,
                baseline={path: state['stage_baseline'][path] for path in paths},
                protected_staged=state['protected_staged'], working=working,
                index_sha256=hashlib.sha256(index).hexdigest())


def ownership_review_token(snapshot):
    return hashlib.sha256(json.dumps(snapshot, sort_keys=True).encode()).hexdigest()


def approved_ownership_review(root, run, state):
    paths, _, _ = _ownership_status(root,
        state.get('git_reconciliation', {}).get('ownership_paths', []), state)
    if not paths:
        return None
    path = run / 'ownership-review.json'
    if not path.exists():
        return None
    info = path.lstat()
    if (not stat.S_ISREG(info.st_mode) or info.st_uid != os.geteuid()
            or info.st_nlink != 1 or info.st_size > 65536):
        raise ValueError('unsafe ownership review receipt; preserve the retained run')
    review = json.loads(path.read_text())
    current = ownership_review_snapshot(root, run, state)
    saved = review.get('snapshot', {})
    # Clean paths need no exception. Retiring one cannot invalidate approval
    # for unchanged remaining overlaps, or release their original fingerprints.
    reduced = dict(saved, baseline={name: value for name, value in saved.get('baseline', {}).items()
                                   if name in paths},
                   working={name: value for name, value in saved.get('working', {}).items()
                            if name in paths})
    if (review.get('approval') != ownership_review_token(saved) or reduced != current):
        raise OwnershipReconciliationRequired(current['baseline'])
    return review


def _ownership_status(root, paths, state):
    baseline = state['stage_baseline']
    protected = set(state['protected_staged'])
    overlap = set()
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
    return overlap, released, clean_paths


def validate_closeout_ownership(root, paths, state, *, run=None):
    """Protect unstaged baseline work before the skill reviews commit ownership."""
    overlap, released, clean_paths = _ownership_status(root, paths, state)
    if overlap:
        review = approved_ownership_review(root, run, state) if run is not None else None
        if review is None or not overlap.issubset(review['snapshot']['baseline']):
            raise OwnershipReconciliationRequired(overlap)
        # Approval permits only a supervised hunk-ownership review. Keep every
        # original fingerprint, including suspended copies, for the commit skill.

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


def uncommitted_skill_intent(root, run, state, *, git=None):
    """Only journaled, verified Git progress may outlive a review snapshot."""
    intent = state.get('commit_intent')
    if intent is None:
        return True
    if intent.get('engine') != 'skill':
        raise ValueError('ownership review requires a supported commit intent')
    git = git or git_output
    progress = run / 'commit-skill' / intent['session'] / 'progress.json'
    previous = json.loads(progress.read_text()) if progress.exists() else {}
    commit = previous.get('source_commit')
    if commit:
        if (not re.fullmatch('[0-9a-f]{40}', commit) or commit == intent['parent']
                or git(root, 'merge-base', '--is-ancestor', intent['parent'], commit, check=False).returncode
                or git(root, 'merge-base', '--is-ancestor', commit, 'HEAD', check=False).returncode):
            raise GitReconciliationRequired('commit journal does not identify preserved source progress')
        return False
    if git(root, 'rev-parse', '--verify', 'HEAD').stdout.strip() != intent['parent']:
        raise GitReconciliationRequired('unjournaled source HEAD changed; reconcile before reviewing ownership')
    return True


GIT_RETRY_WINDOW = 3 * 60 * 60
GIT_RETRY_INITIAL = 30
GIT_RETRY_CAP = 5 * 60


def transient_git_failure(diagnostic):
    """Retry transport outages, never authorization, conflicts or push races."""
    diagnostic = diagnostic.lower()
    if any(text in diagnostic for text in (
            'permission denied', 'access denied', 'authentication failed',
            'authorization failed', 'repository not found', 'could not read username',
            'terminal prompts disabled', 'operation not permitted', 'approval denied',
            'after three hours')):
        return False
    if re.search(r'\b(?:http(?:/[0-9.]+)?(?: error)?|returned error:)\s+(?:401|403)\b',
                 diagnostic):
        return False
    return any(text in diagnostic for text in (
        'could not resolve host', 'could not resolve hostname',
        'temporary failure in name resolution', 'failed to connect',
        'connection refused', 'connection reset', 'connection timed out',
        'connection closed by remote host', 'network is unreachable',
        'remote end hung up unexpectedly', 'unexpected disconnect',
        'tls connection was non-properly terminated', 'ssl connection timeout',
        'http 500', 'http 502', 'http 503', 'http 504',
        'returned error: 500', 'returned error: 502', 'returned error: 503',
        'returned error: 504', 'internal server error', 'bad gateway',
        'service unavailable', 'gateway timeout', 'git transport timed out'))


def retry_git_transport(operation, *, deadline=None, cancelled=None):
    """Retry the same recoverable operation for three hours from first failure.

    Operations receive the deadline so an in-flight retry cannot extend it.
    Exceptions unrelated to transport are passed straight to existing recovery.
    """
    delay = GIT_RETRY_INITIAL
    while True:
        if cancelled is not None and cancelled():
            raise launcher.Stopped()
        if deadline is not None and time.monotonic() >= deadline:
            raise ValueError('Git transport recovery expired after three hours; retain Git progress')
        try:
            return operation(deadline)
        except (subprocess.CalledProcessError, ValueError) as error:
            diagnostic = (str(error) + '\n' + (error.stderr or '') + '\n'
                          + (error.stdout or '') if isinstance(error, subprocess.CalledProcessError)
                          else str(error))
            if not transient_git_failure(diagnostic):
                raise
            now = time.monotonic()
            if deadline is None:
                deadline = now + GIT_RETRY_WINDOW
            remaining = deadline - now
            if remaining <= 0:
                raise ValueError('Git transport still unavailable after three hours: '
                                 + diagnostic) from error
            pause = min(delay, remaining)
            print(f'Git transport unavailable; retrying in {pause:.0f}s '
                  f'({remaining:.0f}s remaining in three-hour window).', flush=True)
            wake = time.monotonic() + pause
            while time.monotonic() < wake:
                if cancelled is not None and cancelled():
                    raise launcher.Stopped()
                time.sleep(min(1, max(0, wake - time.monotonic())))
            if time.monotonic() >= deadline:
                raise ValueError('Git transport still unavailable after three hours: '
                                 + diagnostic) from error
            delay = min(delay * 2, GIT_RETRY_CAP)


def git_output(root, *arguments, check=True, retry_deadline=None, cancelled=None):
    network = arguments[0] in ('fetch', 'pull', 'push', 'ls-remote')
    operation = arguments[0] if arguments[0] in (
        'fetch', 'pull', 'push', 'ls-remote', 'merge', 'commit') else None
    if arguments[:2] in (('stash', 'push'), ('stash', 'apply'), ('stash', 'drop'),
                         ('worktree', 'add'), ('worktree', 'remove')):
        operation = ' '.join(arguments[:2])
    label = f'Git: {operation} in {Path(root).name}'

    def execute(deadline):
        timeout = max(.001, deadline - time.monotonic()) if deadline is not None else None
        if operation:
            print(f'{label}: running.', flush=True)
        try:
            result = subprocess.run(['git', *arguments], cwd=root,
                env=dict(launcher.environment(), LC_ALL='C', GIT_TERMINAL_PROMPT='0'),
                stdin=subprocess.DEVNULL, capture_output=True, text=True,
                timeout=timeout if network else None)
        except subprocess.TimeoutExpired as error:
            if operation:
                print(f'{label}: timed out.', flush=True)
            raise ValueError('Git transport timed out') from error
        if operation:
            outcome = 'completed' if result.returncode == 0 else f'exit status {result.returncode}'
            print(f'{label}: {outcome}.', flush=True)
        if network and result.returncode and transient_git_failure(result.stderr + result.stdout):
            result.check_returncode()
        return result

    result = (retry_git_transport(execute, deadline=retry_deadline, cancelled=cancelled)
              if network else execute(None))
    if check:
        result.check_returncode()
    return result


def git_for_run(git, run, *, deadline=None):
    """Carry run cancellation and the outage deadline through shared Git calls."""
    if git is git_output or isinstance(git, partial) and git.func is git_output:
        return partial(git_output, cancelled=lambda: (run / 'cancel').exists(),
                       retry_deadline=deadline)
    return git


def closeout_lock(root, run, state):
    """Serialize source Git writes with reverse-direction destination updates."""
    if not (root / 'config/environment.json').exists() and not state.get('worktree_propagation'):
        return nullcontext()
    from launcher_worktrees import transaction_lock
    return transaction_lock(root, run)


def commit_push_propagate(root, run, state, paths, message, *, git=None, selection=None):
    """Use $commit for launcher close-outs and their journaled recovery."""
    git = git or git_output
    selection = _operation_selection(root, selection)
    try:
        with closeout_lock(root, run, state):
            intent = state.get('commit_intent')
            if intent is None and state.get('worktree_propagation'):
                raise ValueError('pending propagation has no commit intent; retain it for Git reconciliation')
            if intent is not None and intent.get('engine') != 'skill':
                raise ValueError('unsupported commit checkpoint; preserve the checkpoint and saved work '
                                 'for explicit Git reconciliation before resuming')
            return retry_git_transport(lambda deadline: _commit_with_skill(
                root, run, state, paths, message, git=git, retry_deadline=deadline,
                selection=selection),
                cancelled=lambda: (run / 'cancel').exists())
    except (OSError, ValueError, subprocess.SubprocessError) as error:
        if state.get('task_id'):
            from launcher_chat import update_task_info
            try:
                update_task_info(run, state['task_id'], {
                    'last_error': 'Saving completed work failed: ' + str(error),
                    'status': 'Investigating'})
            except (OSError, ValueError) as status_error:
                print(f'Could not update the task panel: {status_error}', file=sys.stderr)
        raise


def _commit_with_skill(root, run, state, paths, message, *, git, retry_deadline=None, selection=None):
    """Keep acceptance in the controller and Git ownership in the commit skill."""
    from launcher_worktrees import commit_skill_targets
    git = git_for_run(git, run, deadline=retry_deadline)
    skill = root / '.agents/skills/commit/SKILL.md'
    if not skill.is_file():
        raise ValueError('commit skill is missing: ' + str(skill))
    identity, head = validate_pull_identity(root, state, git=git)
    targets = commit_skill_targets(root, git=git)
    intent = state.get('commit_intent')
    review = None
    if ((state.get('git_reconciliation', {}).get('ownership_paths')
         or intent is not None and intent.get('ownership_review'))
            and uncommitted_skill_intent(root, run, state, git=git)):
        validate_closeout_ownership(root, paths, state, run=run)
        review = approved_ownership_review(root, run, state)
        if intent is not None:
            intent['ownership_review'] = review
            launcher.atomic(run / 'checkpoint.json', state)
    if intent is None:
        intent = state['commit_intent'] = dict(
            engine='skill', session=uuid.uuid4().hex, parent=head, paths=list(paths), message=message,
            **identity, targets=targets, ownership_review=review)
        launcher.atomic(run / 'checkpoint.json', state)
    if (intent['paths'] != list(paths) or intent['message'] != message
            or any(intent[key] != identity[key] for key in identity)
            or intent['targets'] != targets):
        raise ValueError('commit skill scope or branch destinations changed; retain the checkpoint')
    sessions = launcher.private_directory(run / 'commit-skill')
    session = launcher.private_directory(sessions / intent['session'])
    receipt = session / 'progress.json'
    previous = json.loads(receipt.read_text()) if receipt.exists() else {}
    result_path = session / 'agent-result.json'
    if previous and result_path.exists():
        result = json.loads(result_path.read_text())
        if result.get('status') == 'complete':
            return _verify_skill_completion(root, run, state, intent, targets, previous,
                                            previous, git=git)
    schema = dict(type='object', additionalProperties=False,
        properties=dict(status=dict(type='string', enum=['complete', 'blocked']),
                        summary=dict(type='string')),
        required=['status', 'summary'])
    (session / 'response.schema.json').write_text(json.dumps(schema))
    (session / 'prompt.txt').write_text(f"""Use $commit, reading {skill}, to close out this accepted launcher task.
The user authorized the full skill workflow. Do not start another launcher.
The controller holds the repository Git transaction lock. Do not acquire it
again or invoke private launcher Git helpers. Perform Git operations directly.
On a transient Git network/service failure, journal progress and return blocked
with the exact Git diagnostic. The controller owns timed outage retries using
this same journal; never create a second completion commit. Permission or
authentication denials are blockers, not outage evidence.
Accepted task scope and original branch identity:
{json.dumps(intent, indent=2)}
Session ownership and acceptance context (read only): {run / 'checkpoint.json'}
Only the listed task paths are candidates, not proof of hunk ownership. Preserve
all unrelated staged, unstaged and untracked work, including within those files.
An ownership_review in the intent authorizes reviewing only its exact shared
file snapshots. It does not authorize adopting or committing pre-existing work.
The original stage_baseline remains authoritative. Identify the task's hunks
from its finite deliverable and source changes; omit unrelated candidate files
and unrelated hunks in shared files. If those boundaries cannot be established,
return blocked without staging or committing ambiguous work. Do not remove or
rewrite the ownership baseline or treat this review approval as ownership.
Before source ownership calculations, read docs/Approval-Tools.md section
"Source hunk ownership with existing grants", linked from the commit skill.
This applies to source fingerprint comparisons as well as destination snapshots.
Do not use ad hoc host interpreters, including read-only python3 -c calculations
or interpreter heredocs: they require approval and block unattended close-out.
When only a baseline hash is retained, reconstruct the text with only identified
task hunks undone in a unique caller-owned /tmp file using native apply_patch,
then compare it with direct sha256sum. Preserve the working file, index and
checkpoint; a mismatch leaves ownership unresolved. Follow the documented route
before execution, never as a retry around an actual policy denial.
For hunk-only staging, use direct git apply --cached [OPTIONS] PATCH commands
with --cached immediately after apply, from the intended checkout working
directory. This approved index-only route also supports --check and --reverse;
it preserves working files. Do not wrap Git in shells/interpreters or use global
options before its subcommand. A read-only index.lock error on another command
shape may be sandbox routing; inspect its exact argv against the existing grant
before reporting a host filesystem failure. An actual denial remains a blocker.
The task has already passed its checks and cleanup. Preserve that acceptance;
do not repeat unchanged checks, implement another task or change expectations.
Quote every Git revision and path operand as one literal shell argument, including
ancestry expressions such as 'HEAD^1', 'HEAD~1', 'stash@{{0}}' and '<stash-id>^2'.
For example, inspect a saved index with git diff '<stash-id>^1' '<stash-id>^2' --stat.
Codex treats unquoted ^ and ~ as possible shell expansion, so the enclosing
shell command can miss the existing Git prefix grant even on Bash.
An argv-only execpolicy check does not validate the command tool's shell parsing.
Do not add allow rules or shell wrappers to compensate for malformed quoting.
Record the exact failed command and diagnostic if a correctly shaped command is
denied; preserve the accepted result and saved work rather than bypassing policy.
Use the suggested commit message. For merge or saved-work restoration conflicts,
follow the skill's automatic conflict-resolution procedure, including its
dedicated resolver and bounded continuation. Conflict resolution may edit the
affected product, plan or test files and run the lowest effective affected checks
through maintained launchers, including required VM validation under the existing
VM authorization and ownership rules. This narrow exception applies to conflicts
in the source and every destination, including an interrupted restoration in the
previous journal. Preserve both intentions and all unrelated work, and revalidate
accepted inputs changed by resolution before continuing Git close-out. Keep
destination active edits out of completion/merge commits and restore their index
state. Journal the resolution and affected validation results. A conflict alone
is not a blocker; continue automatically within the skill's attempt limit.
Stop blocked if resolution is exhausted, intent or ownership remains ambiguous,
validation needs an unauthorized behavior change, or permissions/prerequisites
prevent progress. Never bypass a denial or weaken acceptance.

Durable recovery journal: {receipt}
Previous journal: {json.dumps(previous)}
Maintain this JSON journal with exact commit IDs, branch/upstream identities,
per-destination progress and any stash identities before and after Git writes.
Record the source commit as source_commit immediately after committing, before
pushing. Record the exact successfully pushed source HEAD as pushed_head before
any destination write. Once pushed_head is recorded, it is immutable: resume
unfinished destinations with that same commit and never create another task
commit. Inspect Git and the journal after an interruption before replaying any
write. If a write cannot be identified safely, stop blocked and preserve work.
Restore saved work with its index state; retain recoverable stashes on failure.
For dirty destination snapshots, follow docs/Approval-Tools.md section
"Destination work snapshots with existing grants", linked from the commit skill.
Use its existing direct readers; do not construct ad hoc host interpreter probes.
Return complete only after every configured destination is pushed and the source
checkout is back on its original branch. Otherwise return blocked with the exact
blocker and completed destinations. Do not modify the controller checkpoint.
""")
    result_path.unlink(missing_ok=True)
    with launcher.lock(session / 'owner') as owner:
        fcntl.flock(owner, fcntl.LOCK_EX)
        selected = _operation_selection(root, selection).get()
        launcher.atomic(session / 'intent.json', dict(intent, agent_selection=selected.record()))
        command = ['/usr/bin/python3', '-IBu', str(Path(__file__).resolve()),
                   '--commit-skill', str(root), str(session), str(owner)]
        from test_source import descriptors as source_descriptors
        with subprocess.Popen(command, cwd=root, env=launcher.environment(), stdin=subprocess.PIPE,
                pass_fds=(owner, *launcher.scratch_descriptors(), *source_descriptors()),
                start_new_session=True) as child:
            signalled = False
            expired = False
            while True:
                try:
                    status = child.wait(timeout=0.2)
                    break
                except subprocess.TimeoutExpired:
                    expired = retry_deadline is not None and time.monotonic() >= retry_deadline
                    if ((run / 'cancel').exists() or expired) and not signalled:
                        child.send_signal(signal.SIGTERM)
                        signalled = True
        if expired:
            raise ValueError('Git transport retry window expired after three hours; '
                             'resume the retained Git journal')
        if (run / 'cancel').exists():
            raise launcher.Stopped()
        if status:
            raise ValueError('commit skill session failed; resume the retained Git journal')
    result = json.loads(result_path.read_text())
    if result.get('status') != 'complete':
        raise ValueError('commit skill blocked: ' + result.get('summary', 'inspect retained session'))
    progress = json.loads(receipt.read_text())
    return _verify_skill_completion(root, run, state, intent, targets, progress, previous,
                                    git=git)


def _verify_skill_completion(root, run, state, intent, targets, progress, previous, *, git):
    """Retry independent verification without replaying a completed skill session."""
    from launcher_worktrees import commit_skill_targets

    commit = progress.get('pushed_head', '')
    if (not isinstance(commit, str) or len(commit) != 40
            or any(char not in '0123456789abcdef' for char in commit)
            or previous.get('pushed_head', commit) != commit
            or intent.get('pushed_head', commit) != commit):
        raise ValueError('commit skill did not retain the exact pushed source HEAD')
    validate_pull_identity(root, state, git=git)
    if git(root, 'merge-base', '--is-ancestor', commit, 'HEAD', check=False).returncode:
        raise ValueError('commit skill source HEAD no longer contains the pushed commit')
    if git(root, 'merge-base', '--is-ancestor', intent['parent'], commit, check=False).returncode:
        raise ValueError('commit skill pushed HEAD does not preserve the original source history')
    if commit_skill_targets(root, git=git) != targets:
        raise ValueError('commit skill destination identities changed during close-out')
    # Pin identity before network verification can fail. This records no
    # completion credit; the caller still requires every remote check to pass.
    intent['pushed_head'] = commit
    launcher.atomic(run / 'checkpoint.json', state)
    # Independently verify every remote branch, rather than trusting the agent's
    # completion text or remote-tracking refs left by an earlier fetch.
    for target in targets:
        fetched = git(root, 'fetch', '--no-tags', target['remote'], target['ref'], check=False)
        label = f"{target['branch']} ({target['remote']} {target['ref']})"
        if fetched.returncode:
            raise ValueError(f'commit skill verification fetch failed for {label} '
                             f'(exit {fetched.returncode}): '
                             + (fetched.stderr or fetched.stdout).strip())
        contains = git(root, 'merge-base', '--is-ancestor', commit, 'FETCH_HEAD', check=False)
        if contains.returncode == 1:
            raise ValueError(f'commit skill remote branch {label} does not contain '
                             f'pushed commit {commit}; retain the Git journal')
        if contains.returncode:
            raise ValueError(f'commit skill ancestry verification failed for {label} '
                             f'(exit {contains.returncode}): '
                             + (contains.stderr or contains.stdout).strip())
    intent.update(commit=commit, pushed_head=commit)
    launcher.atomic(run / 'checkpoint.json', state)
    return commit


if __name__ == '__main__':
    mode, root, session, owner = sys.argv[1:]
    if mode != '--commit-skill':
        raise SystemExit('private commit skill supervisor entry point')
    root, session, owner = Path(root), Path(session), int(owner)
    intent = json.loads((session / 'intent.json').read_text())
    selection = (AgentSelection.from_record(intent['agent_selection'], root=root)
                 if 'agent_selection' in intent else resolve_selection(root))
    model, effort = resolve_profile('commit_helper', selection=selection)
    command = launcher.agent_command(root, model, effort, session,
        schema=session / 'response.schema.json', selection=selection, logical_tier='commit_helper',
        extra_directories=tuple(Path(target['path']) for target in intent['targets'] if target.get('path')))
    command.preflight()
    sys.exit(launcher.supervise(root, session, owner, 'agent', command))
