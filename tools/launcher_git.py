"""Shared literal-path Git close-out and identity-checked commit recovery."""

import hashlib
import os
from pathlib import Path
import subprocess

import detached_launcher as launcher


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


def worktree_snapshot(root):
    """Fingerprint unstaged and untracked files without including existing index work."""
    result = subprocess.run(
        ['git', 'ls-files', '--modified', '--deleted', '--others',
         '--exclude-standard', '-z'], cwd=root, env=launcher.environment(),
        capture_output=True, check=True)
    snapshot = {}
    for raw in result.stdout.split(b'\0'):
        if not raw:
            continue
        name = os.fsdecode(raw)
        if name.startswith('output/'):
            continue
        path = root / name
        if path.is_symlink():
            fingerprint = 'link:' + os.readlink(path)
        elif path.is_file():
            digest = hashlib.sha256()
            with path.open('rb') as source:
                for block in iter(lambda: source.read(1024 * 1024), b''):
                    digest.update(block)
            fingerprint = 'file:' + digest.hexdigest()
        else:
            fingerprint = 'deleted'
        snapshot[name] = fingerprint
    return snapshot


def session_changes(root, before):
    after = worktree_snapshot(root)
    return [name for name, fingerprint in after.items()
            if before.get(name) != fingerprint]


def git_output(root, *arguments, check=True):
    return subprocess.run(['git', *arguments], cwd=root, env=launcher.environment(),
                          capture_output=True, text=True, check=check)


def finish_commit(root, run, state, paths, message, *, git=None):
    """Checkpoint commit intent before writing Git, and recognize a completed write."""
    git = git or git_output
    head = git(root, 'rev-parse', '--verify', 'HEAD', check=False)
    parent = head.stdout.strip() if head.returncode == 0 else None
    intent = state.get('commit_intent')
    if intent is not None:
        if intent['message'] != message or intent['paths'] != paths:
            raise ValueError('completion commit scope changed; inspect retained checkpoint')
        if parent != intent['parent']:
            # A worker may die after Git commits but before the checkpoint is saved.
            # Only the exact immediate commit and unchanged owned files earn credit.
            subject = git(root, 'log', '-1', '--format=%s').stdout.strip()
            parents = git(root, 'log', '-1', '--format=%P').stdout.strip()
            changed = git(root, 'diff-tree', '--root', '--no-commit-id',
                                 '--name-only', '-r', '-z', 'HEAD').stdout.split('\0')
            matches = (not paths or (
                git(root, '--literal-pathspecs', 'ls-files', '--stage', '-z',
                           '--', *paths).stdout == intent['entries']
                and not git(root, '--literal-pathspecs', 'status', '--porcelain',
                                   '--untracked-files=all', '--ignored', '-z', '--', *paths).stdout))
            if (subject != message or parents != (intent['parent'] or '')
                    or not set(filter(None, changed)).issubset(paths) or not matches):
                raise ValueError('HEAD changed outside pending completion commit; inspect checkpoint')
            return parent
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
            raise ValueError('owned files changed after staging; inspect pending commit')
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
