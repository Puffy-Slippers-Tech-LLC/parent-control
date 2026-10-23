"""Private Git worktrees/remotes; bounded waited children, no live services or agents."""

import fcntl
import json
import os
from pathlib import Path
import subprocess
from types import SimpleNamespace

import pytest

import launcher_worktrees as propagation


@pytest.fixture
def trees(tmp_path):
    root = tmp_path / 'main checkout'
    root.mkdir()
    def git(root, *args, check=True):
        return subprocess.run(['git', *args], cwd=root, capture_output=True, text=True,
            check=check, timeout=10, env=dict(os.environ, LC_ALL='C'))
    git(root, 'init', '-qb', 'main')
    git(root, 'config', 'user.name', 'Propagation test')
    git(root, 'config', 'user.email', 'propagation@example.invalid')
    (root / 'config').mkdir()
    (root / 'config/worktree.json').write_text(json.dumps(dict(worktrees=['main', 'worktree'])))
    (root / '.gitignore').write_text('run/\n')
    for name in ('shared', 'staged', 'partial', 'unstaged', 'reversed'):
        (root / name).write_text('base\n')
    git(root, 'add', '.')
    git(root, 'commit', '-qm', 'baseline')
    remote = tmp_path / 'remote.git'
    git(root, 'init', '--bare', '-q', str(remote))
    git(root, 'remote', 'add', 'origin', str(remote))
    git(root, 'push', '-qu', 'origin', 'main')
    other = tmp_path / 'other checkout'
    git(root, 'worktree', 'add', '-qb', 'worktree', str(other))
    git(other, 'push', '-qu', 'origin', 'worktree')
    run = root / 'run'
    run.mkdir()
    def change(root, path, content):
        (root / path).write_text(content)
        git(root, 'add', '--', path)
        git(root, 'commit', '-qm', 'task change')
        git(root, 'push', '-q')
        return git(root, 'rev-parse', 'HEAD').stdout.strip()
    return SimpleNamespace(root=root, other=other, remote=remote, run=run, git=git, change=change)


@pytest.mark.parametrize('reverse', [False, True])
def test_symmetric_propagation_preserves_index_worktree_untracked_and_other_stash(trees, reverse):
    f = trees
    source, destination = (f.other, f.root) if reverse else (f.root, f.other)
    (destination / 'unstaged').write_text('older stash\n')
    f.git(destination, 'stash', 'push', '-qm', 'unrelated existing stash')
    older = f.git(destination, 'rev-parse', 'stash@{0}').stdout
    (destination / 'staged').write_text('staged active work\n')
    (destination / 'staged').chmod(0o600)
    (destination / 'partial').write_text('partially staged\n')
    (destination / 'reversed').write_text('staged but reversed in worktree\n')
    f.git(destination, 'add', '--', 'staged', 'partial', 'reversed')
    (destination / 'reversed').write_text('base\n')
    (destination / 'partial').write_text('partially staged plus unstaged\n')
    (destination / 'unstaged').write_text('unstaged active work\n')
    (destination / 'untracked').write_bytes(b'\x00active untracked\xff')
    before_index = f.git(destination, 'diff', '--cached', '--binary').stdout
    before_work = f.git(destination, 'diff', '--binary').stdout
    before_status = f.git(destination, 'status', '--porcelain', '-z').stdout
    commit = f.change(source, 'shared', 'completed task\n')
    state = {}
    propagation.propagate(source, f.run, state, commit, git=f.git,
        resolve=lambda *_: pytest.fail('nonconflicting work required a resolver'))
    assert f.git(destination, 'rev-parse', 'HEAD').stdout.strip() == commit
    assert f.git(destination, 'rev-parse', '@{upstream}').stdout.strip() == commit
    assert f.git(destination, 'diff', '--cached', '--binary').stdout == before_index
    assert f.git(destination, 'diff', '--binary').stdout == before_work
    assert f.git(destination, 'status', '--porcelain', '-z').stdout == before_status
    assert (destination / 'staged').stat().st_mode & 0o777 == 0o600
    assert (destination / 'untracked').read_bytes() == b'\x00active untracked\xff'
    assert f.git(destination, 'rev-parse', 'stash@{0}').stdout == older
    assert state['worktree_propagation']['targets'][0]['phase'] == 'done'


@pytest.mark.parametrize('concurrent_commit', [False, True])
def test_merge_conflicts_are_resolved_automatically_before_active_work_returns(trees, concurrent_commit):
    f = trees
    f.change(f.other, 'shared', 'other committed work\n')
    (f.other / 'unstaged').write_text('keep destination active work\n')
    commit = f.change(f.root, 'shared', 'main committed work\n')
    calls = []
    def resolve(root, phase, details):
        calls.append(phase)
        assert (root / 'unstaged').read_text() == 'base\n'
        assert details['stash']
        (root / 'shared').write_text('main committed work\nother committed work\n')
        f.git(root, 'add', '--', 'shared')
        if concurrent_commit:
            # Another owner can finish the pending merge during resolution.
            f.git(root, 'commit', '--no-edit')
    propagation.propagate(f.root, f.run, {}, commit, git=f.git, resolve=resolve)
    assert calls == ['merge']
    assert f.git(f.other, 'merge-base', '--is-ancestor', commit, 'HEAD').returncode == 0
    assert (f.other / 'unstaged').read_text() == 'keep destination active work\n'
    assert f.git(f.other, 'show', 'HEAD:unstaged').stdout == 'base\n'
    assert f.git(f.other, 'rev-parse', 'HEAD').stdout == f.git(f.other, 'rev-parse', '@{upstream}').stdout
    assert bool(f.git(f.other, 'stash', 'list').stdout) == concurrent_commit


def test_stash_conflict_uses_resolver_and_keeps_active_work_uncommitted(trees):
    f = trees
    (f.other / 'shared').write_text('destination active work\n')
    commit = f.change(f.root, 'shared', 'completed main work\n')
    calls = []
    def resolve(root, phase, details):
        calls.append(phase)
        assert details['stash']
        # --index can fail before applying anything; the resolver inspects and
        # applies once without index in that case, then combines both changes.
        if not f.git(root, 'diff', '--name-only', '--diff-filter=U').stdout:
            f.git(root, 'stash', 'apply', details['stash'], check=False)
        (root / 'shared').write_text('completed main work\ndestination active work\n')
        f.git(root, 'add', '--', 'shared')
        f.git(root, 'restore', '--staged', '--', 'shared')
    propagation.propagate(f.root, f.run, {}, commit, git=f.git, resolve=resolve)
    assert calls == ['restore']
    assert f.git(f.other, 'show', 'HEAD:shared').stdout == 'completed main work\n'
    assert (f.other / 'shared').read_text() == 'completed main work\ndestination active work\n'
    assert f.git(f.other, 'diff', '--cached').stdout == ''
    assert not f.git(f.other, 'stash', 'list').stdout


@pytest.mark.parametrize('boundary', ['stash', 'merge', 'apply', 'push', 'drop'])
def test_interrupted_writes_resume_without_duplicate_merge_or_lost_work(trees, boundary):
    f = trees
    (f.other / 'unstaged').write_text('active destination work\n')
    commit = f.change(f.root, 'shared', 'completed task\n')
    interrupted = False
    def git(root, *args, **kwargs):
        nonlocal interrupted
        result = f.git(root, *args, **kwargs)
        matches = dict(stash=args[:2] == ('stash', 'push'), merge=args[:1] == ('merge',),
                       apply=args[:2] == ('stash', 'apply'), push=args == ('push',),
                       drop=args[:2] == ('stash', 'drop'))
        if root == f.other and matches[boundary] and not interrupted:
            interrupted = True
            raise OSError('interrupted after Git write')
        return result
    with pytest.raises(OSError, match='after Git write'):
        propagation.propagate(f.root, f.run, {}, commit, git=git)
    saved = json.loads((f.run / 'checkpoint.json').read_text())
    if boundary == 'merge':
        # Other work can advance the source while this transaction is retained.
        f.change(f.root, 'shared', 'later source task\n')
    source_head = f.git(f.root, 'rev-parse', 'HEAD').stdout
    def resolve(root, phase, details):
        assert phase == 'restore'
        assert (root / 'unstaged').read_text() == 'active destination work\n'
    propagation.propagate(f.root, f.run, saved, commit, git=f.git, resolve=resolve)
    assert f.git(f.root, 'rev-parse', 'HEAD').stdout == source_head
    assert f.git(f.other, 'rev-parse', 'HEAD').stdout.strip() == commit
    assert f.git(f.other, 'rev-parse', '@{upstream}').stdout.strip() == commit
    assert (f.other / 'unstaged').read_text() == 'active destination work\n'
    assert not f.git(f.other, 'stash', 'list').stdout


def test_propagation_starts_from_verified_completion_after_source_advances(trees):
    f = trees
    commit = f.change(f.root, 'shared', 'completed task\n')
    later = f.change(f.root, 'shared', 'later task\n')
    with pytest.raises(ValueError, match='exact pushed completion commit'):
        propagation.propagate(f.root, f.run, {}, commit, git=f.git)
    state = dict(commit_intent=dict(commit=commit))
    propagation.propagate(f.root, f.run, state, commit, git=f.git)
    assert f.git(f.root, 'rev-parse', 'HEAD').stdout.strip() == later
    assert f.git(f.other, 'rev-parse', 'HEAD').stdout.strip() == commit
    assert f.git(f.other, 'rev-parse', '@{upstream}').stdout.strip() == commit
    assert state['worktree_propagation']['targets'][0]['phase'] == 'done'


def test_rewritten_destination_before_merge_preserves_original_stash(trees, monkeypatch):
    f = trees
    (f.other / 'unstaged').write_text('saved destination work\n')
    commit = f.change(f.root, 'shared', 'completed task\n')
    atomic = propagation.launcher.atomic
    def interrupt(path, state):
        atomic(path, state)
        if state['worktree_propagation']['targets'][0].get('phase') == 'fetch':
            raise OSError('interrupted before fetch')
    monkeypatch.setattr(propagation.launcher, 'atomic', interrupt)
    with pytest.raises(OSError, match='before fetch'):
        propagation.propagate(f.root, f.run, {}, commit, git=f.git)
    monkeypatch.setattr(propagation.launcher, 'atomic', atomic)
    saved = json.loads((f.run / 'checkpoint.json').read_text())
    target, = saved['worktree_propagation']['targets']
    tree = f.git(f.other, 'rev-parse', 'HEAD^{tree}').stdout.strip()
    unrelated = f.git(f.other, 'commit-tree', tree, '-m', 'Unrelated replacement history').stdout.strip()
    f.git(f.other, 'reset', '--soft', unrelated)
    upstream = f.git(f.other, 'rev-parse', '@{upstream}').stdout
    with pytest.raises(ValueError, match='destination HEAD changed during propagation merge'):
        propagation.propagate(f.root, f.run, saved, commit, git=f.git,
                              resolve=lambda *_: pytest.fail('unrelated history reached the resolver'))
    assert f.git(f.other, 'rev-parse', '@{upstream}').stdout == upstream
    assert f.git(f.other, 'rev-parse', 'stash@{0}').stdout.strip() == target['stash']
    assert f.git(f.other, 'show', target['stash'] + ':unstaged').stdout == 'saved destination work\n'


def test_all_configured_destinations_and_source_exclusion(trees):
    f = trees
    third = f.other.parent / 'third'
    f.git(f.root, 'worktree', 'add', '-qb', 'third', str(third))
    f.git(third, 'push', '-qu', 'origin', 'third')
    config = f.root / 'config/worktree.json'
    config.write_text(json.dumps(dict(worktrees=['main', 'worktree', 'third'])))
    f.git(f.root, 'add', '--', 'config/worktree.json')
    f.git(f.root, 'commit', '-qm', 'configure third')
    commit = f.change(f.root, 'shared', 'all targets\n')
    state = {}
    propagation.propagate(f.root, f.run, state, commit, git=f.git)
    assert [item['branch'] for item in state['worktree_propagation']['targets']] == ['worktree', 'third']
    for destination in (f.other, third):
        assert f.git(destination, 'rev-parse', '@{upstream}').stdout.strip() == commit


@pytest.mark.parametrize('defect', ['missing', 'duplicate', 'detached', 'operation', 'upstream', 'busy'])
def test_preflight_refuses_without_touching_destination_work(trees, defect):
    f = trees
    config = f.root / 'config/worktree.json'
    if defect == 'missing': config.write_text(json.dumps(dict(worktrees=['main', 'absent'])))
    if defect == 'duplicate': config.write_text(json.dumps(dict(worktrees=['main', 'worktree', 'worktree'])))
    if defect == 'detached': f.git(f.other, 'checkout', '--detach', '-q')
    if defect == 'upstream': f.git(f.other, 'branch', '--unset-upstream')
    if defect == 'operation':
        path = f.git(f.other, 'rev-parse', '--git-path', 'MERGE_HEAD').stdout.strip()
        Path(path).write_text(f.git(f.other, 'rev-parse', 'HEAD').stdout)
    (f.other / 'unstaged').write_text('untouched active work\n')
    commit = f.change(f.root, 'shared', 'source work\n')
    common = Path(f.git(f.root, 'rev-parse', '--path-format=absolute', '--git-common-dir').stdout.strip())
    with propagation.launcher.lock(common / 'onpc-worktree-propagation.lock') as lock:
        if defect == 'busy':
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
            (f.run / 'cancel').touch()
        with pytest.raises(propagation.launcher.Stopped if defect == 'busy' else ValueError):
            propagation.propagate(f.root, f.run, {}, commit, git=f.git)
    assert (f.other / 'unstaged').read_text() == 'untouched active work\n'
    assert not f.git(f.other, 'stash', 'list').stdout


def test_incomplete_resolution_continues_unattended_without_questions(trees, monkeypatch):
    replies = iter([dict(status='continue', summary='one path remains', cleanup_complete=True),
                    dict(status='resolved', summary='combined both intentions', cleanup_complete=True)])
    calls = []
    def turn(root, run, phase, details):
        calls.append(dict(details))
        return next(replies)
    monkeypatch.setattr(propagation, '_resolve_once', turn)
    propagation.resolve_conflicts(trees.other, trees.run, 'merge',
        dict(branch='worktree', upstream='origin/worktree'), git=trees.git)
    assert len(calls) == 2 and calls[1]['previous_resolution'] == 'one path remains'


@pytest.mark.parametrize('result,committed_path', [('continue', 'staged'), ('resolved', 'shared')])
def test_descendant_head_continues_resolution_and_preserves_stash(trees, monkeypatch, result, committed_path):
    f = trees
    (f.other / 'shared').write_text('destination active work\n')
    commit = f.change(f.root, 'shared', 'source completion\n')
    upstream = f.git(f.other, 'rev-parse', '@{upstream}').stdout
    calls = []
    def turn(root, run, phase, details):
        calls.append(phase)
        assert phase == 'restore'
        if len(calls) > 1:
            return dict(status='resolved', summary='Concurrent commit retained', cleanup_complete=True)
        # Another owner can advance the branch, including restored active work.
        # Observing a descendant does not identify its author.
        (root / 'shared').write_text('source completion\ndestination active work\n')
        f.git(root, 'add', '--', 'shared')
        f.git(root, 'restore', '--staged', '--', 'shared')
        (root / committed_path).write_text('later committed work\n')
        f.git(root, 'add', '--', committed_path)
        f.git(root, 'commit', '-qm', 'advance destination during resolution')
        return dict(status=result, summary='HEAD advanced; reconciliation needed', cleanup_complete=True)
    monkeypatch.setattr(propagation, '_resolve_once', turn)
    def resolve(root, phase, details):
        propagation.resolve_conflicts(root, f.run, phase, details, git=f.git)
    propagation.propagate(f.root, f.run, {}, commit, git=f.git, resolve=resolve)
    assert calls == ['restore'] * (2 if result == 'continue' else 1)
    assert f.git(f.other, 'rev-parse', '@{upstream}').stdout != upstream
    saved = json.loads((f.run / 'checkpoint.json').read_text())
    target, = saved['worktree_propagation']['targets']
    assert target['phase'] == 'done' and target['merged_head'] == commit
    assert target['preserve_stash'] is True
    assert f.git(f.other, 'rev-parse', 'stash@{0}').stdout.strip() == target['stash']
    assert f.git(f.other, 'show', target['stash'] + ':shared').stdout == 'destination active work\n'


def test_source_closeout_lock_is_reentrant_for_its_propagation(trees):
    f = trees
    commit = f.change(f.root, 'shared', 'source work\n')
    with propagation.transaction_lock(f.root, f.run, git=f.git):
        propagation.propagate(f.root, f.run, {}, commit, git=f.git)
    assert f.git(f.other, 'rev-parse', '@{upstream}').stdout.strip() == commit


@pytest.mark.parametrize('defect', [None, 'head', 'branch', 'stash', 'unrelated-head', 'active'])
def test_explicit_reviewed_propagation_recovery_preserves_stash_and_checkpoint(trees, monkeypatch, defect):
    import plan_launcher as workflow
    import test_storage

    f = trees
    spec = workflow.PlanWorkflow('test-plan', 'docs/plan.md')
    storage = f.run / 'plans'
    monkeypatch.setattr(test_storage, 'directory', lambda *_, **__: storage)
    namespace = workflow.launcher.private_directory(storage / workflow.plan_namespace(spec.plan))
    run = workflow.launcher.private_directory(namespace / ('a' * 32))
    workflow.launcher.atomic(namespace / 'current.json', dict(run=run.name))
    (f.other / 'unstaged').write_text('original destination edits\n')
    commit = f.change(f.root, 'shared', 'source completion\n')
    def interrupted_git(root, *args, **kwargs):
        result = f.git(root, *args, **kwargs)
        if root == f.other and args[:2] == ('stash', 'apply'):
            raise OSError('interrupted restoration')
        return result
    with pytest.raises(OSError, match='interrupted restoration'):
        propagation.propagate(f.root, run, {}, commit, git=interrupted_git)
    # A separately reviewed commit includes the restored work, then new active
    # edits arrive. Recovery must neither replay nor discard either set.
    f.git(f.other, 'add', '--', 'unstaged')
    f.git(f.other, 'commit', '-qm', 'reviewed restored work')
    head = f.git(f.other, 'rev-parse', 'HEAD').stdout.strip()
    (f.other / 'partial').write_text('new active work\n')
    f.git(f.other, 'add', '--', 'partial')
    state = json.loads((run / 'checkpoint.json').read_text())
    state.update(in_flight=defect == 'active', pending_completion={'task_id': 'old'}, total_sessions=7)
    target, = state['worktree_propagation']['targets']
    if defect == 'head':
        head = commit
    elif defect == 'branch':
        target['branch'] = 'changed'
    elif defect == 'stash':
        target['stash'] = '0' * 40
    elif defect == 'unrelated-head':
        target['merged_head'] = f.git(f.root, 'rev-parse', target['stash']).stdout.strip()
    workflow.launcher.atomic(run / 'checkpoint.json', state)
    workflow.launcher.atomic(run / 'result.json', dict(status=2, tasks=0))
    raw = (run / 'checkpoint.json').read_bytes()
    status = f.git(f.other, 'status', '--porcelain').stdout
    stashes = f.git(f.other, 'stash', 'list').stdout
    if defect:
        message = {'head': 'destination HEAD changed', 'branch': 'configured destination changed',
                   'stash': 'original propagation stash is missing',
                   'unrelated-head': 'must retain the source and destination commits',
                   'active': 'finish the retained session'}[defect]
        with pytest.raises(ValueError, match=message):
            workflow.reconcile_plan(f.root, spec, run.name, propagation_head=head)
        assert (run / 'checkpoint.json').read_bytes() == raw
        assert not list(run.glob('checkpoint-before-propagation-reconcile-*'))
    else:
        assert workflow.reconcile_plan(f.root, spec, run.name,
            propagation_head=head, check=True)['checked']
        assert (run / 'checkpoint.json').read_bytes() == raw
        assert not list(run.glob('checkpoint-before-propagation-reconcile-*'))
        assert workflow.reconcile_plan(f.root, spec, run.name, propagation_head=head)['reconciled']
        backup, = run.glob('checkpoint-before-propagation-reconcile-*')
        assert json.loads(backup.read_text())['checkpoint_utf8'].encode() == raw
        saved = json.loads((run / 'checkpoint.json').read_text())
        assert saved['pending_completion'] == state['pending_completion']
        assert saved['total_sessions'] == 7
        assert saved['worktree_propagation']['targets'][0]['reconciliation']['previous_head'] == commit
        assert workflow.reconcile_plan(f.root, spec, run.name, propagation_head=head)['reconciled']
        assert list(run.glob('checkpoint-before-propagation-reconcile-*')) == [backup]
        propagation.propagate(f.root, run, saved, commit, git=f.git,
            resolve=lambda *_: pytest.fail('reviewed recovery replayed stash restoration'))
        assert f.git(f.other, 'rev-parse', '@{upstream}').stdout.strip() == head
        assert saved['worktree_propagation']['targets'][0]['phase'] == 'done'
    assert f.git(f.other, 'status', '--porcelain').stdout == status
    assert f.git(f.other, 'stash', 'list').stdout == stashes


@pytest.mark.parametrize('repair', [False, True])
def test_missing_active_work_returns_to_resolver_before_push_or_stash_retirement(trees, repair):
    f = trees
    (f.other / 'shared').write_text('conflicting active work\n')
    (f.other / 'unstaged').write_text('unrelated active work\n')
    commit = f.change(f.root, 'shared', 'completed task\n')
    calls = []
    def resolve(root, phase, details):
        assert phase == 'restore'
        calls.append(details)
        (root / 'shared').write_text('completed task\nconflicting active work\n')
        f.git(root, 'add', '--', 'shared')
        f.git(root, 'restore', '--staged', '--', 'shared')
        f.git(root, 'restore', '--staged', '--', 'unstaged')
        (root / 'unstaged').write_text('unrelated active work\n' if repair and len(calls) == 2 else 'base\n')
    if repair:
        propagation.propagate(f.root, f.run, {}, commit, git=f.git, resolve=resolve)
        assert f.git(f.other, 'rev-parse', '@{upstream}').stdout.strip() == commit
        assert (f.other / 'unstaged').read_text() == 'unrelated active work\n'
    else:
        with pytest.raises(propagation.RestorationRequired, match="'unstaged' \\(content\\)"):
            propagation.propagate(f.root, f.run, {}, commit, git=f.git, resolve=resolve)
        assert f.git(f.other, 'rev-parse', '@{upstream}').stdout.strip() != commit
    assert len(calls) == 2 and 'previous_resolution' in calls[1]
    assert 'onpc-propagation-' in f.git(f.other, 'stash', 'list').stdout


@pytest.mark.parametrize('phase', ['push', 'drop'])
@pytest.mark.parametrize('path', ['unstaged', 'shared'])
def test_restart_rechecks_restoration_at_unchanged_head_before_retiring_stash(trees, monkeypatch, phase, path):
    f = trees
    (f.other / path).write_text('saved destination work\n')
    commit = f.change(f.root, 'shared', 'completed task\n')
    expected = ('completed task\n' if path == 'shared' else '') + 'saved destination work\n'
    def restore(root, *_):
        (root / path).write_text(expected)
        f.git(root, 'add', '--', path)
        f.git(root, 'restore', '--staged', '--', path)
    atomic = propagation.launcher.atomic
    def interrupt(path, state):
        atomic(path, state)
        if state['worktree_propagation']['targets'][0].get('phase') == phase:
            raise OSError('interrupted before stash retirement')
    monkeypatch.setattr(propagation.launcher, 'atomic', interrupt)
    with pytest.raises(OSError, match='before stash retirement'):
        propagation.propagate(f.root, f.run, {}, commit, git=f.git, resolve=restore)
    monkeypatch.setattr(propagation.launcher, 'atomic', atomic)
    saved = json.loads((f.run / 'checkpoint.json').read_text())
    target, = saved['worktree_propagation']['targets']
    (f.other / path).write_text('completed task\n' if path == 'shared' else 'base\n')
    calls = []
    def resolve(root, kind, details):
        assert kind == 'restore' and details['stash'] == target['stash']
        assert path in details['previous_resolution']
        calls.append(kind)
        restore(root)
    propagation.propagate(f.root, f.run, saved, commit, git=f.git, resolve=resolve)
    assert calls == ['restore'] and target['phase'] == 'done'
    assert (f.other / path).read_text() == expected
    assert f.git(f.other, 'rev-parse', 'stash@{0}').stdout.strip() == target['stash']


@pytest.mark.parametrize('phase, damage', [
    ('restore', None), ('push', None), ('drop', None), ('push', 'rewrite'), ('push', 'missing-stash'),
    ('restore', 'operation'),
])
def test_descendant_restart_never_replays_or_retires_the_recovery_stash(trees, monkeypatch, phase, damage):
    f = trees
    (f.other / 'unstaged').write_text('saved destination work\n')
    commit = f.change(f.root, 'shared', 'completed task\n')
    atomic = propagation.launcher.atomic
    def interrupt(path, state):
        atomic(path, state)
        if state['worktree_propagation']['targets'][0].get('phase') == phase:
            raise OSError('interrupted at restoration boundary')
    monkeypatch.setattr(propagation.launcher, 'atomic', interrupt)
    with pytest.raises(OSError, match='restoration boundary'):
        propagation.propagate(f.root, f.run, {}, commit, git=f.git)
    monkeypatch.setattr(propagation.launcher, 'atomic', atomic)
    saved = json.loads((f.run / 'checkpoint.json').read_text())
    # A later owner has already included the saved work and extended it.
    head = f.change(f.other, 'unstaged', 'saved destination work\nlater committed work\n')
    (f.other / 'unstaged').write_text('new concurrent edits\n')
    if damage:
        target, = saved['worktree_propagation']['targets']
        if damage == 'rewrite':
            f.git(f.other, 'reset', '--soft', target['head'])
        elif damage == 'missing-stash':
            f.git(f.other, 'stash', 'drop', 'stash@{0}')
        else:
            Path(f.git(f.other, 'rev-parse', '--git-path', 'MERGE_HEAD').stdout.strip()).write_text(head + '\n')
        upstream = f.git(f.other, 'rev-parse', '@{upstream}').stdout
        with pytest.raises(ValueError, match='destination HEAD changed|original propagation stash is missing|existing Git operation'):
            propagation.propagate(f.root, f.run, saved, commit, git=f.git,
                                  resolve=lambda *_: pytest.fail('unsafe state reached the resolver'))
        assert f.git(f.other, 'rev-parse', '@{upstream}').stdout == upstream
        assert (f.other / 'unstaged').read_text() == 'new concurrent edits\n'
        return
    calls = []
    def git(root, *args, **kwargs):
        assert not (root == f.other and args[:2] == ('stash', 'apply'))
        return f.git(root, *args, **kwargs)
    def resolve(root, kind, details):
        calls.append(kind)
        checkpoint = json.loads((f.run / 'checkpoint.json').read_text())
        assert checkpoint['worktree_propagation']['targets'][0]['phase'] == 'restoring'
    propagation.propagate(f.root, f.run, saved, commit, git=git, resolve=resolve)
    assert calls == ['restore']
    target, = saved['worktree_propagation']['targets']
    assert target['phase'] == 'done' and target['preserve_stash'] is True
    assert (f.other / 'unstaged').read_text() == 'new concurrent edits\n'
    assert f.git(f.other, 'rev-parse', 'HEAD').stdout.strip() == head
    assert f.git(f.other, 'rev-parse', 'stash@{0}').stdout.strip() == target['stash']


def test_real_supervisor_runs_destination_resolver_with_a_private_agent_double(trees, monkeypatch):
    f = trees
    binary = f.root / 'private-bin'
    binary.mkdir()
    agent = binary / 'codex'
    agent.write_text('''#!/usr/bin/python3
import json
import os
from pathlib import Path
import sys
args = sys.argv[1:]
assert args[args.index('--ask-for-approval') + 1] == 'never'
assert args[args.index('--model') + 1] == 'gpt-6.1-sol'
assert Path(args[args.index('--cd') + 1]).resolve() == Path.cwd()
assert 'Resolve only this worktree propagation merge conflict unattended' in sys.stdin.read()
assert os.environ.get('ONPC_WORKFLOW_DIRECTORY')
destination = Path(args[args.index('--output-last-message') + 1])
destination.write_text(json.dumps(dict(status='resolved', summary='Private agent completed', cleanup_complete=True)))
''')
    agent.chmod(0o755)
    monkeypatch.setenv('PATH', str(binary) + os.pathsep + os.environ['PATH'])
    with propagation.launcher.lock(f.run.parent / 'owner') as owner:
        fcntl.flock(owner, fcntl.LOCK_EX)
        result = propagation._resolve_once(f.other, f.run, 'merge', dict(source_root=str(f.root)))
    assert result['status'] == 'resolved'
    session = f.run / 'worktree-resolution'
    assert (session / 'nested-closed').exists()
    record = propagation.launcher._start_record(session / 'propagation-owner.json')
    assert record['destination'] == str(f.other)


@pytest.mark.parametrize('defect', [None, 'checkout', 'source', 'owner', 'transaction', 'closed'])
def test_destination_tests_require_the_live_identity_bound_propagation_owner(tmp_path, monkeypatch, defect):
    import test_storage
    launcher = propagation.launcher
    source_root = tmp_path / 'source'
    destination = tmp_path / 'destination'
    source_root.mkdir()
    destination.mkdir()
    def directory(kind, *, root):
        return root / kind
    monkeypatch.setattr(test_storage, 'directory', directory)
    namespace = launcher.private_directory(source_root / 'plans' / ('a' * 64))
    run = launcher.private_directory(namespace / ('b' * 32))
    session = launcher.private_directory(run / 'worktree-resolution')
    child = launcher.private_directory(destination / 'sessions-host' / ('c' * 32))
    launcher.atomic(namespace / 'current.json', dict(run=run.name))
    launcher.atomic(run / 'checkpoint.json', dict(worktree_propagation=dict(
        targets=[dict(path=str(destination), phase='merge')])))
    launcher.atomic(session / 'nested.json', [])
    with launcher.lock(namespace / 'owner') as source_owner, launcher.lock(session / 'owner') as owner:
        fcntl.flock(source_owner, fcntl.LOCK_EX)
        fcntl.flock(owner, fcntl.LOCK_EX)
        info, owned = run.stat(), os.fstat(source_owner)
        record = dict(root=str(source_root), run=str(run), destination=str(destination),
                      identity=[info.st_dev, info.st_ino], owner_identity=[owned.st_dev, owned.st_ino])
        if defect == 'checkout': record['destination'] = str(source_root)
        if defect == 'source': record['identity'][1] += 1
        if defect == 'owner': record['owner_identity'][1] += 1
        if defect == 'transaction': launcher.atomic(run / 'checkpoint.json', {})
        if defect == 'closed': (session / 'nested-closed').touch()
        launcher._publish_start(session / 'propagation-owner.json', record)
        monkeypatch.setenv(launcher.WORKFLOW_DIRECTORY, str(session))
        if defect:
            with pytest.raises(ValueError):
                with launcher.nested_operation(destination, child):
                    pytest.fail('invalid resolver started a test')
            assert json.loads((session / 'nested.json').read_text()) == []
        else:
            with launcher.nested_operation(destination, child):
                pass
            entry, = json.loads((session / 'nested.json').read_text())
            assert entry == dict(path=str(child), device=child.stat().st_dev, inode=child.stat().st_ino)
