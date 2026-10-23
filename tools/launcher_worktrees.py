"""Shared, resumable propagation of pushed launcher commits to configured branches.

Destination edits live in an identity-recorded stash throughout the merge. Conflict
resolution runs unattended in the destination, never in the task's checkout.
"""

import fcntl
from contextlib import contextmanager
import json
import os
from pathlib import Path
import signal
import stat
import subprocess
import sys
import threading
import time
import uuid

sys.path.insert(0, str(Path(__file__).resolve().parent))

import detached_launcher as launcher
from launcher_git import git_output, worktree_fingerprint


_held = threading.local()


@contextmanager
def transaction_lock(root, run, *, git=git_output):
    """One reentrant source-closeout/propagation owner across all worktrees."""
    common = Path(_run(git, root, 'rev-parse', '--path-format=absolute', '--git-common-dir'))
    held = getattr(_held, 'paths', set())
    if str(common) in held:
        yield
        return
    with launcher.lock(common / 'onpc-worktree-propagation.lock') as lock:
        while True:
            try:
                fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
                break
            except BlockingIOError:
                if (run / 'cancel').exists():
                    raise launcher.Stopped()
                time.sleep(0.1)
        _held.paths = held | {str(common)}
        try:
            yield
        finally:
            _held.paths = held


def configured_targets(root, *, git=git_output):
    path = root / 'config/worktree.json'
    if not path.exists():
        return []
    if path.is_symlink() or not path.is_file():
        raise ValueError('worktree configuration must be a regular file')
    config = json.loads(path.read_text())
    names = config.get('worktrees') if isinstance(config, dict) else None
    if (not isinstance(names, list) or any(not isinstance(name, str) or not name
            or name.startswith('-') or '\x00' in name for name in names)
            or len(set(names)) != len(names)):
        raise ValueError('config/worktree.json needs unique branch names in worktrees')
    records = git(root, 'worktree', 'list', '--porcelain', '-z').stdout.split('\0\0')
    branches = {}
    for record in records:
        fields = dict(field.split(' ', 1) for field in record.split('\0') if ' ' in field)
        if 'branch' in fields and 'worktree' in fields:
            branches[fields['branch'].removeprefix('refs/heads/')] = Path(fields['worktree']).resolve()
    targets = []
    for name in names:
        if name not in branches:
            raise ValueError(f'configured worktree branch is not checked out: {name}')
        if branches[name] != root.resolve():
            targets.append(dict(path=str(branches[name]), branch=name))
    return targets


def _run(git, root, *args):
    result = git(root, *args, check=False)
    if result.returncode:
        raise ValueError(f'worktree propagation {root}: git {args[0]} failed: '
                         + (result.stderr or result.stdout).strip())
    return result.stdout.strip()


def _head(git, root):
    return _run(git, root, 'rev-parse', '--verify', 'HEAD')


def _stashes(git, root):
    result = git(root, 'stash', 'list', '--format=%H%x00%gs').stdout
    return [line.split('\0', 1) for line in result.splitlines() if '\0' in line]


def _idle(git, root):
    for name in ('MERGE_HEAD', 'CHERRY_PICK_HEAD', 'REVERT_HEAD', 'rebase-merge', 'rebase-apply'):
        path = Path(_run(git, root, 'rev-parse', '--git-path', name))
        if (path if path.is_absolute() else root / path).exists():
            raise ValueError(f'worktree propagation found an existing Git operation in {root}: {name}')


def _identity(git, root, target):
    branch = _run(git, root, 'symbolic-ref', '--quiet', '--short', 'HEAD')
    upstream = _run(git, root, 'rev-parse', '--abbrev-ref', '--symbolic-full-name', '@{upstream}')
    if branch != target['branch'] or upstream != target['upstream']:
        raise ValueError('worktree propagation branch/upstream changed; retained stash is preserved')


def _expect_head(git, root, expected, phase):
    actual = _head(git, root)
    if actual != expected:
        raise ValueError(f'destination HEAD changed during {phase}: expected {expected}, found {actual}; '
                         'reconcile the retained transaction before continuing; stash is preserved')


def _active_snapshot(git, root, paths=None):
    if paths is None:
        paths = set(filter(None, git(root, 'diff', '--no-renames', '--name-only', '-z', 'HEAD').stdout.split('\0')))
        paths.update(filter(None, git(root, 'diff', '--cached', '--no-renames', '--name-only', '-z',
                                      'HEAD').stdout.split('\0')))
        paths.update(filter(None, git(root, 'ls-files', '--others', '--exclude-standard', '-z').stdout.split('\0')))
    paths = sorted(paths)
    if not paths:
        return {}
    entries = git(root, '--literal-pathspecs', 'ls-files', '--stage', '-z', '--', *paths).stdout
    index = {}
    for entry in filter(None, entries.split('\0')):
        metadata, path = entry.split('\t', 1)
        index.setdefault(path, []).append(metadata)
    result = {}
    for path in paths:
        file = root / path
        result[path] = dict(content=worktree_fingerprint(file), index=index.get(path, []),
                           mode=stat.S_IMODE(file.lstat().st_mode) if os.path.lexists(file) else None)
    return result


def _verify_restored(git, root, target):
    """Unchanged merge inputs must restore byte-for-byte, including their index."""
    changed = set(filter(None, git(root, 'diff', '--no-renames', '--name-only', '-z',
                                  target['head'], target['merged_head']).stdout.split('\0')))
    expected = {path: value for path, value in target.get('active', {}).items() if path not in changed}
    # Git retains executable bits, but a stash checkout can replace an owner's
    # private 0600 file with the checkout's default 0644 permissions.
    for path, value in expected.items():
        file = root / path
        if (value['content'].startswith('file:') and os.path.lexists(file)
                and stat.S_ISREG(file.lstat().st_mode)
                and worktree_fingerprint(file) == value['content']):
            file.chmod(value['mode'])
    if _active_snapshot(git, root, expected) != expected:
        raise ValueError('destination active work or staging was not restored; preserving its stash')


def _merge(git, root, target, incoming, resolve):
    merge = git(root, 'rev-parse', '--verify', 'MERGE_HEAD', check=False)
    if merge.returncode == 0 and merge.stdout.strip() != incoming:
        raise ValueError('worktree propagation encountered an unrelated pending merge')
    if merge.returncode:
        if git(root, 'merge-base', '--is-ancestor', incoming, 'HEAD', check=False).returncode == 0:
            return
        if git(root, 'status', '--porcelain', '--untracked-files=all').stdout:
            raise ValueError('destination changed while its active work was stashed; preserving it')
        result = git(root, 'merge', '--no-edit', '--no-autostash', incoming, check=False)
        if result.returncode and not git(root, 'diff', '--name-only', '--diff-filter=U', '-z').stdout:
            raise ValueError('worktree propagation merge failed: ' + result.stderr.strip())
    if git(root, 'diff', '--name-only', '--diff-filter=U', '-z').stdout:
        before = _head(git, root)
        resolve(root, 'merge', dict(target, incoming=incoming))
        if _head(git, root) != before:
            raise ValueError('conflict resolver changed HEAD; controller owns merge commits')
    if git(root, 'diff', '--name-only', '--diff-filter=U', '-z').stdout:
        raise ValueError('automatic worktree resolution left unresolved merge conflicts')
    if git(root, 'rev-parse', '--verify', 'MERGE_HEAD', check=False).returncode == 0:
        _run(git, root, 'commit', '--no-edit')
    if git(root, 'merge-base', '--is-ancestor', incoming, 'HEAD', check=False).returncode:
        raise ValueError('destination does not contain the propagated commit')
    if git(root, 'status', '--porcelain', '--untracked-files=all').stdout:
        raise ValueError('merge left uncommitted changes before stash restoration')


def propagate(root, run, state, commit, *, git=git_output, resolve=None):
    """Finish every destination before caller grants completion; save each write intent."""
    root, run = Path(root), Path(run)
    transaction = state.get('worktree_propagation')
    if transaction is None:
        targets = configured_targets(root, git=git)
        if not targets:
            return
        if (not commit or (_head(git, root) != commit
                           and state.get('commit_intent', {}).get('commit') != commit)):
            raise ValueError('worktree propagation requires the exact pushed completion commit')
        transaction = state['worktree_propagation'] = dict(commit=commit, targets=targets)
        launcher.atomic(run / 'checkpoint.json', state)
    if (transaction['commit'] != commit
            or git(root, 'merge-base', '--is-ancestor', commit, 'HEAD', check=False).returncode):
        raise ValueError('worktree propagation source commit changed')
    resolve = resolve or (lambda target, phase, details: resolve_conflicts(
        target, run, phase, dict(details, source_root=str(root.resolve()))))
    with transaction_lock(root, run, git=git):
        def save():
            launcher.atomic(run / 'checkpoint.json', state)
        for target in transaction['targets']:
            destination = Path(target['path'])
            if target.get('phase') == 'done':
                continue
            actual = configured_targets(root, git=git)
            if not any(item['path'] == target['path'] and item['branch'] == target['branch'] for item in actual):
                raise ValueError('configured destination changed during worktree propagation')
            if 'phase' not in target:
                _idle(git, destination)
                target.update(phase='stash', head=_head(git, destination),
                    upstream=_run(git, destination, 'rev-parse', '--abbrev-ref',
                                  '--symbolic-full-name', '@{upstream}'),
                    marker='onpc-propagation-' + uuid.uuid4().hex,
                    active=_active_snapshot(git, destination))
                save()
            _identity(git, destination, target)
            if target['phase'] == 'stash':
                if _head(git, destination) != target['head']:
                    raise ValueError('destination HEAD changed before propagation stash')
                found = [oid for oid, subject in _stashes(git, destination) if subject.endswith(target['marker'])]
                if not found and git(destination, 'status', '--porcelain', '--untracked-files=all').stdout:
                    _run(git, destination, 'stash', 'push', '-u', '-m', target['marker'])
                    found = [oid for oid, subject in _stashes(git, destination) if subject.endswith(target['marker'])]
                    if len(found) != 1:
                        raise ValueError('could not identify destination active-work stash')
                target.update(stash=found[0] if found else None, phase='fetch')
                save()
            if target['phase'] == 'fetch':
                _run(git, destination, 'fetch')
                target.update(upstream_commit=_run(git, destination, 'rev-parse', '--verify', '@{upstream}'),
                              phase='upstream')
                save()
            if target['phase'] == 'upstream':
                _merge(git, destination, target, target['upstream_commit'], resolve)
                target['phase'] = 'merge'
                save()
            if target['phase'] == 'merge':
                _merge(git, destination, target, commit, resolve)
                target.update(phase='restore', merged_head=_head(git, destination))
                save()
            _expect_head(git, destination, target['merged_head'], 'propagation restoration/push')
            if target['phase'] in ('restore', 'restoring'):
                stash = target['stash']
                if stash:
                    interrupted = target['phase'] == 'restoring'
                    target['phase'] = 'restoring'
                    save()  # Never blindly reapply a stash after an interrupted write.
                    applied = None if interrupted else git(destination, 'stash', 'apply', '--index', stash, check=False)
                    if interrupted or applied.returncode:
                        resolve(destination, 'restore', target)
                    _identity(git, destination, target)
                    _expect_head(git, destination, target['merged_head'], 'stash restoration')
                    if git(destination, 'diff', '--name-only', '--diff-filter=U', '-z').stdout:
                        raise ValueError('automatic stash restoration left unresolved conflicts')
                _verify_restored(git, destination, target)
                target['phase'] = 'push'
                save()  # Stash remains available until restored work and push are recorded.
            if target['phase'] == 'push':
                _run(git, destination, 'push')
                target['phase'] = 'drop'
                save()
            if target['phase'] == 'drop':
                for index, (oid, subject) in enumerate(_stashes(git, destination)):
                    if oid == target['stash'] and subject.endswith(target['marker']):
                        _run(git, destination, 'stash', 'drop', f'stash@{{{index}}}')
                        break
                target['phase'] = 'done'
                save()
            print(f"Propagated {commit[:12]} to {target['branch']} and pushed.", flush=True)


def resolve_conflicts(root, run, phase, details, *, git=git_output):
    """Continue bounded unattended turns instead of asking a developer to merge."""
    details = dict(details)
    expected = details['merged_head'] if phase == 'restore' else _head(git, root)
    for attempt in range(1, 6):
        _identity(git, root, details)
        _expect_head(git, root, expected, f'{phase} conflict resolution')
        print(f'Automatically resolving {phase} conflicts in {root} (turn {attempt}/5).', flush=True)
        result = _resolve_once(root, run, phase, details)
        # A continue result may describe a concurrent commit rather than more
        # conflict work. Never send another turn against stale transaction inputs,
        # or infer that the resolver authored an observed HEAD change.
        _identity(git, root, details)
        _expect_head(git, root, expected, f'{phase} conflict resolution')
        if result.get('status') == 'resolved' and result.get('cleanup_complete') is True:
            return
        details['previous_resolution'] = result.get('summary', 'Resolution incomplete.')
    raise ValueError('automatic worktree resolution exhausted its turns; retained stash and transaction preserved')


def _resolve_once(root, run, phase, details):
    """Use the maintained supervised agent route without a developer question."""
    session = launcher.private_directory(run / 'worktree-resolution')
    # Inspect the previous owned test inventory before reusing this child on
    # another turn or destination. Keep its authenticated checkout for cleanup.
    previous = session / 'propagation-owner.json'
    if previous.exists():
        recorded = launcher._start_record(previous)
        launcher.finish_nested(Path(recorded['destination']), session)
    source_info = run.stat()
    owner_info = (run.parent / 'owner').stat()
    launcher._publish_start(previous, dict(root=details['source_root'], run=str(run),
        destination=str(root.resolve()), identity=[source_info.st_dev, source_info.st_ino],
        owner_identity=[owner_info.st_dev, owner_info.st_ino]))
    schema = dict(type='object', additionalProperties=False,
        properties=dict(status=dict(type='string', enum=['resolved', 'continue']),
                        summary=dict(type='string'), cleanup_complete=dict(type='boolean')),
        required=['status', 'summary', 'cleanup_complete'])
    (session / 'response.schema.json').write_text(json.dumps(schema))
    (session / 'prompt.txt').write_text(f"""Resolve only this worktree propagation {phase} conflict unattended.
Read destination AGENTS.md and the shared propagation contract in
{details['source_root']}/docs/Execution-Plans.md (the source checkout).
Destination: {root}
Transaction: {json.dumps(details)}
No developer questions or approval waits. Inspect all three Git stages and the
stash's HEAD, index and untracked parents as applicable. Combine the incoming
committed change with the destination's own work, preserving both intentions.
Never choose ours/theirs wholesale, discard active work, reset/clean, force-push,
change configuration, commit or push. The controller owns merge commits/pushes.
For a merge: edit and stage only conflicted paths, leaving no unmerged entries.
For restore: inspect whether stash apply --index partially ran or completed;
finish restoration exactly once, applying without --index if necessary, resolve
conflicts, and restore the stash's original staged/unstaged distinction, including
partially staged files and untracked files. Destination active work must remain
uncommitted; never include it in a merge commit. Do not drop the recorded stash.
Preserve unrelated files and all other stashes. Check affected combined behavior
with the lowest effective maintained validation. Finish owned cleanup. Return
resolved only after the conflict and restoration work is complete; otherwise
return continue with exact remaining work. No other task or launcher execution.
""")
    (session / 'agent-result.json').unlink(missing_ok=True)
    launcher.atomic(session / 'nested.json', [])
    (session / 'nested-closed').unlink(missing_ok=True)
    with launcher.lock(session / 'owner') as owner:
        fcntl.flock(owner, fcntl.LOCK_EX)
        command = ['/usr/bin/python3', '-IBu', str(Path(__file__).resolve()),
                   '--resolve', str(root), str(session), str(owner)]
        with subprocess.Popen(command, cwd=root, env=launcher.environment(), stdin=subprocess.PIPE,
                pass_fds=(owner, *launcher.scratch_descriptors()), start_new_session=True) as child:
            signalled = False
            while True:
                try:
                    status = child.wait(timeout=0.2)
                    break
                except subprocess.TimeoutExpired:
                    if (run / 'cancel').exists() and not signalled:
                        child.send_signal(signal.SIGTERM)
                        signalled = True
        launcher.finish_nested(root, session)
        if (run / 'cancel').exists():
            raise launcher.Stopped()
        if status:
            raise ValueError('automatic worktree conflict resolver failed; retained stash and transaction preserved')
    return json.loads((session / 'agent-result.json').read_text())


if __name__ == '__main__':
    _, root, session, owner = sys.argv[1:]
    root, session, owner = Path(root), Path(session), int(owner)
    command = launcher.agent_command(root, 'gpt-6.1-sol', 'high', session,
                                    schema=session / 'response.schema.json')
    command[-1:-1] = ['-c', 'shell_environment_policy.set.ONPC_WORKFLOW_DIRECTORY='
                     + json.dumps(str(session))]
    sys.exit(launcher.supervise(root, session, owner, 'agent', command, nested=True))
