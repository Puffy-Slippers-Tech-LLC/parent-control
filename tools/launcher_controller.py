"""Reloadable public controller admission and branch/host dispatch policy."""

import json
import os
from contextlib import nullcontext
from pathlib import Path
import subprocess
import sys

from host_dispatch import git as _git, require_checkout as _local_checkout, ssh_command, tool_host


DESTINATION = 'ONPC_LAUNCHER_DESTINATION'
BRANCH_HELP = ('--branch NAME selects a config/environment.json branch; default: '
               'this launcher\'s default_branch, then the current checkout branch.')
_pending_startup = None
_CONTROLS = ('--help', '-h', '--list', '--check', '--collect-only', '--stop',
             '--cancel-stop', '--add-session', '--reload', '--reset',
             '--reconcile', '--review-ownership')


def _pending_git(previous):
    """Git journals pin their original source base until their owner settles."""
    if previous is not None:
        from test_source import _read, IMPACT_MAX_BYTES
        for filename in ('checkpoint.json', 'translation-state.json'):
            path = previous / filename
            saved = _read(path, max_bytes=IMPACT_MAX_BYTES)
            if saved is not None:
                if any(saved.get(key) is not None for key in (
                        'commit_intent', 'pull_intent', 'worktree_propagation',
                        'upstream_pull', 'git_reconciliation')):
                    return True
    return False


def require_startup_sync():
    """Never start a job if early synchronization could not obtain ownership."""
    if _pending_startup is not None:
        raise ValueError('controller source synchronization is busy; retry after '
                         'the active checkout owner finishes')


def _early_sync(root, name, branch, arguments):
    """Synchronize before workflow imports; live owners retain attachment only."""
    if any(arg.split('=', 1)[0] in _CONTROLS for arg in arguments):
        return False
    from contextlib import ExitStack
    import fcntl
    from detached_launcher import lock, busy, current_run, private_directory
    from test_source import finish_admission
    from test_storage import directory

    finish_admission()
    kinds = {'fix-tests': ('fix-tests', 'fix-tests-host'),
             'run-tests': ('sessions', 'sessions-host'),
             'run-unit-tests': ('sessions-host',),
             'write-e2e': ('write-e2e', 'plans'),
             'execute-plan': ('plans',), 'sync-whatsnew': ('sync-whatsnew',)}
    with ExitStack() as locks:
        previous_runs = []
        repair_runs = []
        retained_start = False
        live = False
        # Exclude replacement of this controller family. Other families retain
        # independent scheduling under the shared source lease/generation guard.
        for kind in kinds.get(name, ()):
            try:
                base = directory(kind, root=root, create=False)
            except FileNotFoundError:
                continue
            scopes = ([path for path in sorted(base.iterdir())
                       if len(path.name) == 64 and all(c in '0123456789abcdef' for c in path.name)]
                      if kind == 'plans' else [base])
            if kind == 'sessions':
                scopes.extend(sorted(base.glob('vm-*')))
            for scope in scopes:
                private_directory(scope)
                gate = locks.enter_context(lock(scope / 'gate'))
                try:
                    fcntl.flock(gate, fcntl.LOCK_EX | fcntl.LOCK_NB)
                except BlockingIOError:
                    return None
                previous = current_run(scope)
                owner_path = (previous / 'owner' if kind.startswith('sessions') and previous
                              else scope / 'owner')
                owner = locks.enter_context(lock(owner_path))
                live |= busy(owner)
                retained_start |= (scope / 'pending-start.json').exists()
                if previous is not None:
                    previous_runs.append(previous)
                    if name == 'fix-tests' and kind in ('fix-tests', 'fix-tests-host'):
                        repair_runs.append(previous)
        return _startup_sync(root, branch, arguments, previous_runs=previous_runs,
                             repair_runs=repair_runs, retained_start=retained_start, live=live)


def _pull(root, *, recovery=False, frozen=False, descriptors=(), before_change=lambda: None):
    def execute(arguments):
        result = subprocess.run(['git', *arguments], cwd=root, text=True,
            stdin=subprocess.DEVNULL, capture_output=True, timeout=120,
            env=dict(os.environ, GIT_TERMINAL_PROMPT='0'), pass_fds=descriptors, check=False)
        if result.returncode:
            raise ValueError(result.stderr.strip() or result.stdout.strip())

    execute(['fetch', '--no-tags'])
    try:
        _git(root, 'merge-base', '--is-ancestor', '@{upstream}', 'HEAD')
        return  # Already synchronized; no source invalidation or mutation.
    except ValueError as error:
        if frozen:
            raise ValueError('pushed source cannot be applied over a retained Git transaction; '
                             'finish its recorded recovery before synchronizing') from error
    # Durable invalidation precedes Git, including if this controller dies and
    # the descriptor-owning Git child finishes the update after its death.
    before_change()
    execute(['pull', '--no-autostash', *(['--ff-only'] if recovery else [])])


def _recover_pull(root, diagnostic, selection, profile, *, descriptors=()):
    from tempfile import TemporaryDirectory
    from agent_adapter import Delegation, SessionRequest, prepare_session
    from test_storage import scratch_directory
    model, effort = profile
    prompt = (f'Resolve only this controller startup git pull failure in {root}. '
        'Read AGENTS.md. Preserve all local commits, edits, staged and untracked work. '
        'Resolve conflicts and complete the pull, including its merge commit if necessary. '
        'Do not reset, clean, discard work, push, change Git configuration, retry denied '
        'authentication, run jobs/tests/setup, or edit unrelated files. If safe recovery '
        f'is impossible, report the blocker and stop. Git diagnostic: {diagnostic}')
    with TemporaryDirectory(prefix='startup-pull-', dir=scratch_directory()) as temporary:
        run = Path(temporary)
        schema = run / 'response.schema.json'
        schema.write_text(json.dumps(dict(type='object', additionalProperties=False,
            properties=dict(status=dict(type='string', enum=['synced', 'blocked']),
                            summary=dict(type='string')), required=['status', 'summary'])))
        session = prepare_session(SessionRequest(root=root, model=model, effort=effort,
            run=run, schema=schema, selection=selection,
            delegation=Delegation(enabled=False), standard_speed=True),
            dict(os.environ))
        session.preflight()
        result = subprocess.run(session.argv, cwd=session.cwd, env=session.environment,
                                input=prompt, text=True, timeout=1200, pass_fds=descriptors, check=False)
        response = run / 'agent-result.json'
        saved = json.loads(response.read_text()) if response.is_file() else {}
        if result.returncode or saved.get('status') != 'synced':
            raise ValueError('startup pull recovery failed; job was not started: '
                             + saved.get('summary', 'No successful recovery result.'))
    if _git(root, 'diff', '--name-only', '--diff-filter=U'):
        raise ValueError('startup pull still has conflicts; job was not started')
    for state in ('MERGE_HEAD', 'rebase-merge', 'rebase-apply', 'CHERRY_PICK_HEAD'):
        if (root / _git(root, 'rev-parse', '--git-path', state)).exists():
            raise ValueError('startup pull left an unfinished Git operation; job was not started')
    _git(root, 'merge-base', '--is-ancestor', '@{upstream}', 'HEAD')
    # An agent can exit successfully after reporting a network/auth blocker.
    # Confirm real remote synchronization before admitting the job.
    _pull(root, descriptors=descriptors)


def _startup_sync(root, branch, arguments, *, previous_runs=(), repair_runs=(), retained_start=False,
                  live=False):
    """Pull under shared source guards; report whether imports need replacing."""
    if any(arg.split('=', 1)[0] in _CONTROLS for arg in arguments):
        return
    import fcntl
    from test_source import SourceProtection, source_directory, finish_admission, _lock, _read, IMPACT_MAX_BYTES
    finish_admission()
    protection = SourceProtection(source_directory(root))
    common = Path(_git(root, 'rev-parse', '--path-format=absolute', '--git-common-dir'))
    # Share the propagation lock and source lease, so no pull runs over active
    # sessions/tests or another Git transaction. No stash or new journal needed.
    with _lock(common / 'onpc-worktree-propagation.lock') as transaction:
        try:
            fcntl.flock(transaction, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError as error:
            if live:
                return None
            raise ValueError('repository synchronization is busy; retry after it finishes') from error
        with _lock(protection.directory / 'repair-owner') as source:
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
                pending = protection.owner()
                if pending is not None and not live:
                    if ('--resume' not in arguments
                            or pending not in {str(run.resolve()) for run in repair_runs}):
                        raise ValueError('retained repair source requires its original --resume; '
                                         'source and checkpoints were preserved')
                    saved = _read(Path(pending) / 'checkpoint.json', {}, max_bytes=IMPACT_MAX_BYTES)
                    if not saved.get('active_ticket'):
                        raise ValueError('retained source writer has no matching active repair ticket')
                frozen = any(_pending_git(run) for run in previous_runs)
                recovery = ('--resume' in arguments or frozen or retained_start or pending is not None
                            or bool(protection.impact_holds()))
            if live:
                try:
                    _pull(root, frozen=True, descriptors=(source, transaction))
                except (OSError, ValueError, subprocess.TimeoutExpired):
                    return None  # Attachment remains available; new jobs refuse.
                return False
            # Interrupted Git operations must retain their original recovery
            # journal; a second pull cannot safely supersede that transaction.
            for state in ('MERGE_HEAD', 'rebase-merge', 'rebase-apply', 'CHERRY_PICK_HEAD'):
                if (root / _git(root, 'rev-parse', '--git-path', state)).exists():
                    raise ValueError('unfinished Git operation prevents controller source synchronization; '
                                     'source and recovery journals were preserved')
            head = _git(root, 'rev-parse', 'HEAD')
            print('Git: synchronizing controller checkout with its upstream.', flush=True)
            invalidated = False
            selection = profile = None
            def invalidate():
                nonlocal invalidated, selection, profile
                if not invalidated:
                    if not recovery:
                        from agent_adapter import resolve_profile, resolve_selection
                        selection = resolve_selection(root)
                        # Pin recovery before a mutating ordinary pull can put
                        # its code into conflict. No-op/repair sync needs no CLI.
                        selection.adapter()
                        profile = resolve_profile('conflict_resolver', effort='low', selection=selection)
                    with protection.state():
                        protection.advance_generation(source)
                    invalidated = True
            try:
                _pull(root, recovery=recovery, frozen=frozen, descriptors=(source, transaction),
                      before_change=invalidate)
            except (OSError, ValueError, subprocess.TimeoutExpired) as error:
                if recovery:
                    raise ValueError('controller source synchronization failed; retained repair '
                                     'ownership, edits and checkpoints were preserved: ' + str(error)) from error
                print('Git pull failed; starting a low-effort recovery session.', flush=True)
                invalidate()
                _recover_pull(root, str(error), selection, profile, descriptors=(source, transaction))
            _local_checkout(root, branch)
            return invalidated or head != _git(root, 'rev-parse', 'HEAD')


def _remote(host, branch, arguments):
    """Dispatch admission through SSH and return its startup status."""
    # OpenSSH passes a command string to the remote shell. Quote every token,
    # including the Python bootstrap and opaque user arguments, exactly once.
    # Use the established destination marker rather than importing a new helper
    # from the server: an older checkout with controller admission can receive it.
    # The destination consumes this PID-bound marker and verifies Git itself.
    bootstrap = '''import json, os, sys
from pathlib import Path
root = Path(sys.argv[1]).resolve()
branch, name = sys.argv[2:4]
command = root / 'tools' / name
if Path(name).name != name or not command.is_file() or command.is_symlink():
    sys.exit('launcher: launcher is missing from configured checkout')
os.chdir(root)
os.environ['ONPC_LAUNCHER_DESTINATION'] = json.dumps(dict(
    root=str(root), branch=branch, launcher=name, pid=os.getpid()))
os.execve('/usr/bin/python3', ['/usr/bin/python3', '-IBu', str(command),
          *sys.argv[4:]], dict(os.environ))
'''
    destination = ['/usr/bin/python3', '-IBu', '-c', bootstrap,
                   branch['repo_root'], branch['name'],
                   Path(sys.argv[0]).name, *arguments]
    # The destination verifies its checkout before resolving agent selection.
    # Native adapters prepare their own environment only for agent operations;
    # help, observation and stop must work without a coding CLI or NVM.
    command = ssh_command(host, destination)
    sys.stdout.flush()
    sys.stderr.flush()
    return subprocess.run(command, check=False).returncode


def dispatch(entry):
    global _pending_startup
    root = Path(__file__).resolve().parents[1]
    name = Path(sys.argv[0]).name
    arguments, selected = [], None
    pinned_branch = None
    synced = False
    tokens = iter(sys.argv[1:])
    for token in tokens:
        if token == '--':
            arguments.extend([token, *tokens])
            break
        if token == '--branch' or token.startswith('--branch='):
            if selected is not None:
                raise ValueError('specify --branch only once')
            selected = next(tokens, '') if token == '--branch' else token.partition('=')[2]
            if not selected or selected.startswith('-'):
                raise ValueError('--branch requires a configured branch name')
        else:
            arguments.append(token)

    # Exec preserves PID. A legacy destination can ignore this marker without
    # letting its later child commands accidentally inherit a pinned route.
    forwarded = json.loads(os.environ.pop(DESTINATION, 'null'))
    if forwarded is not None and forwarded['pid'] == os.getpid():
        if (forwarded['root'] != str(root) or forwarded['launcher'] != name
                or selected not in (None, forwarded['branch'])):
            raise ValueError('forwarded launcher destination changed')
        pinned_branch = forwarded['branch']
        synced = forwarded.get('synced', False)
        if pinned_branch is not None:
            _local_checkout(root, pinned_branch)
    elif (name == 'run-tests' and selected is None
          and (os.environ.get('ONPC_LAUNCHER_CONTROLLER_ROOT') == str(root)
               or os.environ.get('ONPC_RUNNER_INVOCATION')
               or len(arguments) > 1 and arguments[1] == '--unattended')):
        # Internal inventory calls, repair attempts and category children belong
        # to this checkout's controller. Reapplying the public default can verify
        # another checkout instead of the repair (or fail ownership guards).
        pass
    else:
        from vm_selection import vm_config
        path = root / 'config/environment.json'
        if path.exists() or selected is not None:
            # Dispatch and agent-free inspection use branch metadata only.
            # The destination resolves its live selection after dispatch.
            document = vm_config.read_document(path, validate_agent=False)
            owner = tool_host(root, document)
            defaults = vm_config.launcher_registry(document)
            # Plans B/C are independent of the original write-e2e owner and its
            # configured default checkout. Explicit branch routing still wins.
            default_branch = (None if name == 'write-e2e' and
                              any(flag in arguments for flag in ('--planb', '--planc'))
                              else defaults.get(name, {}).get('default_branch'))
            selected = selected or default_branch
            selected = selected or _git(root, 'symbolic-ref', '--quiet', '--short', 'HEAD')
            pinned_branch = selected
            branch = vm_config.branch_registry(document).get(selected)
            if branch is None:
                raise ValueError('--branch must name a branch in config/environment.json')
            else:
                host = vm_config.host_registry(document)[branch['host']]
                if host.name != owner.name:
                    from test_source import leave_checkout
                    leave_checkout()
                    return _remote(host, branch, arguments)
                destination = Path(branch['repo_root']).resolve()
                _local_checkout(destination, selected)
                if destination != root:
                    command = destination / 'tools' / name
                    if not command.is_file() or command.is_symlink():
                        raise ValueError(f'launcher is missing from configured checkout: {command}')
                    sys.stdout.flush()
                    sys.stderr.flush()
                    from test_source import leave_checkout
                    leave_checkout()
                    env = dict(os.environ)
                    env[DESTINATION] = json.dumps(dict(root=str(destination), branch=selected,
                                                       launcher=name, pid=os.getpid()))
                    os.chdir(destination)
                    os.execve('/usr/bin/python3', ['/usr/bin/python3', '-IBu', str(command),
                              *arguments], env)

    if pinned_branch is not None and not synced:
        _pending_startup = (pinned_branch, arguments)
        changed = _early_sync(root, name, pinned_branch, arguments)
        if changed is not None:
            _pending_startup = None
        if changed:
            # Refresh all controller imports and pin placement across exec.
            from test_source import leave_checkout
            leave_checkout()
            env = dict(os.environ)
            env[DESTINATION] = json.dumps(dict(root=str(root), branch=pinned_branch,
                launcher=name, pid=os.getpid(), synced=True))
            sys.stdout.flush()
            sys.stderr.flush()
            os.chdir(root)
            os.execve('/usr/bin/python3', ['/usr/bin/python3', '-IBu',
                      str(root / 'tools' / name), *arguments], env)
    import test_source
    # Restore only the source admission released from the test/repair wrappers.
    # Plan/translation controls retain their existing agent-free recovery path.
    # A repair controller must reach recovery or report its blocker promptly;
    # waiting behind a retained impact hold cannot make an idle repair advance.
    admission = (test_source.admission(root, arguments, repair=name == 'fix-tests',
                                      wait=name != 'fix-tests')
                 if name in ('run-tests', 'run-unit-tests', 'fix-tests') else nullcontext())
    with admission:
        return _entry(root, name, pinned_branch, arguments, entry)


def _entry(root, name, pinned_branch, arguments, entry):
    global _pending_startup
    from vm_selection import HOST_HELP, host_arguments
    arguments = host_arguments(arguments)
    sys.argv[1:] = arguments
    if any(arg in ('--help', '-h') for arg in arguments):
        print(BRANCH_HELP, flush=True)
        print(HOST_HELP, flush=True)
        if name == 'write-e2e' and any(flag in arguments for flag in ('--planb', '--planc')):
            print('--planb/--planc default to the current checkout branch; --branch overrides it.', flush=True)
    import test_source
    try:
        return entry()
    except test_source.RestartExecution:
        # Every controller/reset/resource context has unwound. Preserve the
        # resolved destination even if a source change altered branch defaults.
        test_source.finish_admission()
        arguments = [arg for arg in arguments if arg not in ('--reload', '--reset')]
        temporary = test_source.VARIABLE not in test_source.environment()
        with test_source.startup(root, arguments, repair=name == 'fix-tests', fresh=True):
            from launcher_reload import replace
            inherited = test_source.environment()
            if temporary:
                os.environ[test_source.IMPORTS] = inherited[test_source.VARIABLE]
            os.environ[DESTINATION] = json.dumps(dict(root=str(root), branch=pinned_branch,
                                                       launcher=name, pid=os.getpid()))
            try:
                replace(['/usr/bin/python3', '-IBu', str(root / 'tools' / name), *arguments], ())
            finally:
                if temporary:
                    os.environ.pop(test_source.IMPORTS, None)
                os.environ.pop(DESTINATION, None)
    finally:
        _pending_startup = None


def run(entry):
    def admitted():
        try:
            import test_source
            root = Path(__file__).resolve().parents[1]
            # Bootstrap only reads placement/ownership metadata. It must remain
            # available behind retained repair holds; workflow imports below
            # still require their normal admission after synchronization.
            bootstrap = (['--help'] if any(arg.split('=', 1)[0] in _CONTROLS
                                         for arg in sys.argv[1:]) else ['--resume'])
            with test_source.admission(root, bootstrap, repair=True):
                return dispatch(entry)
        except (OSError, ValueError, subprocess.TimeoutExpired) as error:
            print(f'launcher: {error}', file=sys.stderr)
            return 2

    try:
        status = admitted()
    except SystemExit as error:
        if error.code:
            print('\033[31mLauncher command failed.\033[0m', file=sys.stderr, flush=True)
        raise
    if status:
        print('\033[31mLauncher command failed.\033[0m', file=sys.stderr, flush=True)
    return status
