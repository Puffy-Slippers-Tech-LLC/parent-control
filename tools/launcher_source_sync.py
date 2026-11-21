"""Noninteractive upstream synchronization shared by launcher admission and execution."""

from contextlib import contextmanager
import fcntl
import json
import os
from pathlib import Path
import signal
import subprocess

from host_dispatch import git, require_checkout


STATUS = 78
BOUNDARY_AGENT_ENV = 'ONPC_TEST_SYNC_UPSTREAM'
BOUNDARY_AGENT_ENV_KEYS = ('PATH', 'NVM_DIR', 'CODEX_HOME')


class SyncError(ValueError):
    """Execution cannot safely continue on the current checkout."""


class SyncBusy(ValueError):
    """Another owner is using the checkout."""


def _run(root, arguments, descriptors=(), *, control=None):
    command = ['git', *arguments]
    environment = dict(os.environ, GIT_TERMINAL_PROMPT='0')
    if control is None:
        return subprocess.run(command, cwd=root, text=True,
            stdin=subprocess.DEVNULL, capture_output=True, timeout=120,
            env=environment, pass_fds=descriptors, check=False)
    stdout, stderr = bytearray(), bytearray()
    status = control.run(command, cwd=root, env=environment, timeout=120,
        output=stdout.extend, stderr_output=stderr.extend,
        cancel_signal=signal.SIGTERM, pass_fds=descriptors)
    return subprocess.CompletedProcess(command, status,
        stdout.decode(errors='replace'), stderr.decode(errors='replace'))


def _check(result):
    if result.returncode:
        raise SyncError(result.stderr.strip() or result.stdout.strip()
                        or f'git exited with status {result.returncode}')


@contextmanager
def _git_transaction(root):
    from test_source import _lock
    common = Path(git(root, 'rev-parse', '--path-format=absolute', '--git-common-dir'))
    with _lock(common / 'onpc-worktree-propagation.lock') as descriptor:
        yield descriptor


def _upstream_pending(root, descriptors, control):
    # Follow the published tags attached to fetched source for the VM upgrade matrix.
    _check(_run(root, ['fetch'], descriptors, control=control))
    comparison = _run(root, ['merge-base', '--is-ancestor', '@{upstream}', 'HEAD'],
                      descriptors, control=control)
    if comparison.returncode != 1:
        _check(comparison)
    return comparison.returncode == 1


def pull(root, *, recovery=False, frozen=False, descriptors=(),
         before_change=lambda: None, control=None):
    try:
        pending = _upstream_pending(root, descriptors, control)
    finally:
        if control is not None and control.stopped.is_set():
            raise KeyboardInterrupt
    if not pending:
        return
    if frozen:
        raise SyncError('pushed source cannot be applied over a live owner or retained Git transaction')
    before_change()
    strategy = ['--ff-only'] if recovery else ['--no-rebase', '--ff', '--no-edit']
    if control is not None:
        import launcher_reload
        launcher_reload.check()
        if control.stopped.is_set():
            raise KeyboardInterrupt
    # Let an in-progress Git mutation finish while its transaction stays locked.
    _check(_run(root, ['pull', '--no-autostash', *strategy], descriptors))


def recover_pull(root, diagnostic, selection, profile, *, descriptors=(), boundary=False):
    """Resolve one pull failure and confirm the checkout contains its upstream."""
    from tempfile import TemporaryDirectory
    from agent_adapter import Delegation, SessionRequest, prepare_session
    from test_storage import scratch_directory

    model, effort = profile
    context = 'test bundle boundary' if boundary else 'controller startup'
    prompt = (f'Resolve only this {context} git pull failure in {root}. '
        'Read AGENTS.md. Preserve all local commits, edits, staged and untracked work. '
        'Resolve conflicts and complete the pull, including its merge commit if necessary. '
        'Do not reset, clean, discard work, push, change Git configuration, retry denied '
        'authentication, run jobs/tests/setup, or edit unrelated files. If safe recovery '
        f'is impossible, report the blocker and stop. Git diagnostic: {diagnostic}')
    control = None
    with TemporaryDirectory(prefix='launcher-pull-', dir=scratch_directory()) as temporary:
        run = Path(temporary)
        schema = run / 'response.schema.json'
        schema.write_text(json.dumps(dict(type='object', additionalProperties=False,
            properties=dict(status=dict(type='string', enum=['synced', 'blocked']),
                            summary=dict(type='string')), required=['status', 'summary'])))
        environment = dict(os.environ)
        if boundary:
            settings = json.loads(environment.pop(BOUNDARY_AGENT_ENV, '{}'))
            environment.update((name, settings[name]) for name in BOUNDARY_AGENT_ENV_KEYS if name in settings)
        session = prepare_session(SessionRequest(root=root, model=model, effort=effort,
            run=run, schema=schema, selection=selection,
            logical_tier='conflict_resolver',
            delegation=Delegation(enabled=False), standard_speed=True), environment)
        session.preflight()
        if boundary:
            from regression_process import Control
            control = Control()
            with (run / 'prompt.txt').open('w+', encoding='utf-8') as stream:
                stream.write(prompt)
                stream.seek(0)
                status = control.run(session.argv, cwd=session.cwd, env=session.environment,
                    stdin_file=stream, timeout=1200, cancel_signal=signal.SIGTERM, pass_fds=descriptors)
            if status == 130:
                raise KeyboardInterrupt
        else:
            status = subprocess.run(session.argv, cwd=session.cwd, env=session.environment,
                input=prompt, text=True, timeout=1200, pass_fds=descriptors, check=False).returncode
        response = run / 'agent-result.json'
        saved = json.loads(response.read_text()) if response.is_file() else {}
        if not isinstance(saved, dict):
            raise SyncError('pull recovery returned an invalid result')
        if status or saved.get('status') != 'synced':
            summary = saved.get('summary')
            if not isinstance(summary, str) or not summary:
                summary = f'exit status {status}' if status else 'no successful recovery result'
            raise SyncError('pull recovery failed: ' + summary)
    if git(root, 'diff', '--name-only', '--diff-filter=U'):
        raise SyncError('pull still has conflicts')
    for state in ('MERGE_HEAD', 'rebase-merge', 'rebase-apply', 'CHERRY_PICK_HEAD'):
        if (root / git(root, 'rev-parse', '--git-path', state)).exists():
            raise SyncError('pull left an unfinished Git operation')
    git(root, 'merge-base', '--is-ancestor', '@{upstream}', 'HEAD')
    # Confirm remote synchronization before admitting execution.
    pull(root, recovery=boundary, descriptors=descriptors, control=control)


def _pending_git(previous):
    """Git journals pin their original source base until their owner settles."""
    if previous is not None:
        from test_source import _read, MAX_RECORD_BYTES
        for filename in ('checkpoint.json', 'translation-state.json'):
            path = previous / filename
            saved = _read(path, max_bytes=MAX_RECORD_BYTES)
            if saved is not None:
                if any(saved.get(key) is not None for key in (
                        'commit_intent', 'pull_intent', 'worktree_propagation',
                        'upstream_pull')):
                    return True
    return False


def synchronize_checkout(root, branch, *, previous_runs=(), retained_start=False,
                         live=False, on_boundary_admitted=None):
    """Pull under shared source guards; report whether imports need replacing."""
    from test_source import SourceProtection, source_directory, finish_admission, _lock
    boundary = on_boundary_admitted is not None
    finish_admission()
    protection = SourceProtection(source_directory(root))
    # Share the propagation lock and source lease, so no pull runs over active
    # sessions/tests or another Git transaction. No stash or new journal needed.
    with _git_transaction(root) as transaction:
        try:
            fcntl.flock(transaction, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError as error:
            if live or boundary:
                return None
            raise SyncBusy('repository synchronization is busy; retry after it finishes') from error
        with _lock(protection.directory / 'source.lock') as source:
            with protection.state():
                try:
                    fcntl.flock(source, fcntl.LOCK_EX | fcntl.LOCK_NB)
                except BlockingIOError:
                    if not live:
                        return None
                    try:
                        # Independent host/VM controllers can start together
                        # when source is already current. Fetch-only admission
                        # needs no writer and cannot mutate active source.
                        fcntl.flock(source, fcntl.LOCK_SH | fcntl.LOCK_NB)
                    except BlockingIOError:
                        return None
                frozen = any(_pending_git(run) for run in previous_runs)
                recovery = frozen or retained_start
            if live:
                try:
                    pull(root, frozen=True, descriptors=(source, transaction))
                except (OSError, ValueError, subprocess.TimeoutExpired):
                    return None  # Attachment remains available; new jobs refuse.
                return False
            control = None
            if boundary:
                from regression_process import Control
                control = Control()
                require_checkout(root, branch)
                # The repository and source locks now guard mutation. Let control
                # commands reach the live owner while the pull or resolver runs.
                on_boundary_admitted()
            # Interrupted Git operations must retain their original recovery
            # journal; a second pull cannot safely supersede that transaction.
            for state in ('MERGE_HEAD', 'rebase-merge', 'rebase-apply', 'CHERRY_PICK_HEAD'):
                if (root / git(root, 'rev-parse', '--git-path', state)).exists():
                    raise ValueError('unfinished Git operation prevents controller source synchronization; '
                                     'source and recovery journals were preserved')
            head = git(root, 'rev-parse', 'HEAD')
            message = ('Git: checking upstream after test workers have joined.' if boundary else
                       'Git: synchronizing controller checkout with its upstream.')
            print(message, flush=True)
            pull_attempted = False
            selection = profile = None
            profile_error = None

            def before_pull():
                nonlocal pull_attempted, selection, profile, profile_error
                pull_attempted = True
                if not recovery:
                    from agent_adapter import resolve_profile, resolve_selection
                    try:
                        # Pin the profile before the pull can conflict with its config.
                        selection = resolve_selection(root)
                        profile = resolve_profile('conflict_resolver', selection=selection)
                    except ValueError as error:
                        profile_error = error

            try:
                pull(root, recovery=recovery, frozen=frozen, descriptors=(source, transaction),
                     before_change=before_pull, control=control)
            except (OSError, SyncError, subprocess.TimeoutExpired) as error:
                if control is not None and control.stopped.is_set():
                    raise KeyboardInterrupt from error
                if recovery:
                    raise ValueError('controller source synchronization failed; retained repair '
                                     'ownership, edits and checkpoints were preserved: ' + str(error)) from error
                if not pull_attempted:
                    raise
                if (not (root / git(root, 'rev-parse', '--git-path', 'MERGE_HEAD')).exists()
                        or not git(root, 'diff', '--name-only', '--diff-filter=U')):
                    raise
                if profile_error is not None:
                    raise SyncError(f'{error}; cannot start conflict resolution: {profile_error}') from error
                print('Git pull failed; starting the configured recovery session.', flush=True)
                recover_pull(root, str(error), selection, profile, boundary=boundary,
                             descriptors=(source, transaction))
            require_checkout(root, branch)
            return pull_attempted or head != git(root, 'rev-parse', 'HEAD')
