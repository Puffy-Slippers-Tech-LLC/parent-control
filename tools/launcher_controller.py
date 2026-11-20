"""Reloadable public controller admission and branch/host dispatch policy."""

import json
import os
from contextlib import ExitStack, nullcontext
from dataclasses import dataclass, field
from pathlib import Path
import subprocess
import sys

from host_dispatch import git as _git, require_checkout as _local_checkout, ssh_command, tool_host
from launcher_source_sync import SyncBusy, SyncError, synchronize_checkout as _startup_sync


DESTINATION = 'ONPC_LAUNCHER_DESTINATION'
BRANCH_HELP = ('--branch NAME selects a config/environment.json branch; default: '
               'this launcher\'s default_branch, then the current checkout branch.')
_pending_startup = None
_public_invocation = None
_QUEUE_CONTROLS = ('--queue-list', '--queue-cancel')
_CONTROLS = ('--help', '-h', '--list', '--check', '--collect-only', '--stop',
             '--cancel-stop', '--add-session', '--reload', '--reset',
             '--reconcile', '--review-ownership', *_QUEUE_CONTROLS)
_NO_NEW_JOB = tuple(flag for flag in _CONTROLS if flag not in ('--reload', '--reset'))
_TEST_LAUNCHERS = ('run-tests', 'run-unit-tests', 'run-ui-tests')
_OWNER_KINDS = ('fix-tests', 'fix-tests-host', 'sessions', 'sessions-host',
                'plans', 'sync-whatsnew')


@dataclass
class Invocation:
    name: str
    public_argv: list
    branch: str | None
    arguments: list
    options: list
    fresh: bool
    reset_lease: int | None
    resolved: dict = field(default_factory=dict)


def public_arguments(launcher):
    """Return caller parameters before host/VM resolution for this controller."""
    if _public_invocation is not None and _public_invocation.name == launcher:
        return list(_public_invocation.public_argv)
    return None


def queue_invocation():
    invocation = _public_invocation
    if invocation is None:
        return None
    name, options, fresh = invocation.name, invocation.options, invocation.fresh
    controls = _CONTROLS
    if name == 'fix-tests':
        # Repair --reset only discards remembered results. The test runner's
        # checkout-wide reset remains a separate control before it starts.
        controls = tuple(flag for flag in controls if flag != '--reset')
        fresh |= '--reset' in options
    if (invocation.branch is None or os.environ.get('ONPC_WATCH_RUN')
            or any(arg.partition('=')[0] in controls for arg in options)):
        return None
    recovery = 'reset' if invocation.reset_lease is not None else (
        'fresh' if fresh else 'resume' if '--resume' in options else None)
    return invocation, recovery


def remembered_request(load):
    """Snapshot an implicit resume selection when a public launch is queued."""
    if _public_invocation is None:
        return load()
    from launcher_queue import replay_options
    replay = replay_options()
    request = replay['resume'] if 'resume' in replay else load()
    _public_invocation.resolved['resume'] = request
    return request


class RetryQueuedStartup(RuntimeError):
    """A queued launch may try again after a competing owner releases source."""


def require_startup_sync():
    """Never start a job if early synchronization could not obtain ownership."""
    if _pending_startup is not None:
        from launcher_queue import REPLAY
        detail = 'controller source synchronization is busy; retry after the active checkout owner finishes'
        if os.environ.get(REPLAY):
            raise RetryQueuedStartup(detail)
        raise SyncBusy(detail)


def _early_sync(root, branch, arguments, *, boundary_run=None, defer_if_live=False):
    """Check live owners before synchronizing at startup or a joined boundary."""
    if os.environ.get('ONPC_WATCH_RUN'):
        if (Path(sys.argv[0]).name not in ('run-tests', 'fix-tests') or not any(
                arg.partition('=')[0] in ('--watch-ssh', '--watch-view') for arg in arguments)):
            raise ValueError('watch: invalid launcher control invocation')
        return False  # A Watch control must never start or synchronize a new job.
    if any(arg.split('=', 1)[0] in _NO_NEW_JOB for arg in arguments):
        return False
    from contextlib import ExitStack
    import fcntl
    from detached_launcher import lock, busy, current_run, private_directory
    from test_source import finish_admission
    from test_storage import directory
    from test_results import REPAIR_QUEUE, VARIABLE as REPAIR_RESULTS

    finish_admission()
    repair_run = None
    if (boundary_run is not None and os.environ.get(REPAIR_QUEUE) == '1'
            and os.environ.get(REPAIR_RESULTS)):
        repair_run = Path(os.environ[REPAIR_RESULTS]).parent.parent
    with ExitStack() as locks:
        previous_runs = []
        retained_start = False
        live = False
        # Source is checkout-wide. Every launcher observes the same owners,
        # including detached repairs that do not hold a source reader lease.
        for kind in _OWNER_KINDS:
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
                if not (previous is not None and (
                        (previous == boundary_run and kind.startswith(('sessions', 'fix-tests')))
                        or (previous == repair_run and kind.startswith('fix-tests')))):
                    live |= busy(owner)
                # Repair resume retains results, never historical startup/Git
                # transactions. Its live owner still protects active edits.
                retained_start |= not kind.startswith('fix-tests') and (scope / 'pending-start.json').exists()
                if previous is not None and not kind.startswith('fix-tests'):
                    previous_runs.append(previous)
        if live and defer_if_live:
            return None
        return _startup_sync(root, branch, previous_runs=previous_runs,
                             retained_start=retained_start, live=live,
                             on_boundary_admitted=locks.close if boundary_run is not None else None)


def synchronize_boundary(root, branch, run, *, defer_if_live=False):
    """Synchronize at a joined boundary when the checkout is available."""
    try:
        _local_checkout(root, branch)
        return _early_sync(root, branch, [], boundary_run=run, defer_if_live=defer_if_live) is not None
    except (OSError, ValueError, subprocess.TimeoutExpired) as error:
        raise SyncError(str(error)) from error


def synchronize_reload(root, run):
    """Handle the current reload before restarting the joined worker."""
    import launcher_reload
    previous = launcher_reload.current
    launcher_reload.current = None
    try:
        branch = _git(root, 'symbolic-ref', '--quiet', '--short', 'HEAD')
        if not synchronize_boundary(root, branch, run):
            raise SyncError('checkout synchronization is busy; resume after the other checkout owner finishes')
    finally:
        launcher_reload.current = previous


def _remote(host, branch, arguments, public_argv):
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
public_argv = json.loads(sys.argv[4])
command = root / 'tools' / name
if Path(name).name != name or not command.is_file() or command.is_symlink():
    sys.exit('launcher: launcher is missing from configured checkout')
os.chdir(root)
os.environ['ONPC_LAUNCHER_DESTINATION'] = json.dumps(dict(
    root=str(root), branch=branch, launcher=name, pid=os.getpid(), public_argv=public_argv))
os.execve('/usr/bin/python3', ['/usr/bin/python3', '-IBu', str(command),
          *sys.argv[5:]], dict(os.environ))
'''
    destination = ['/usr/bin/python3', '-IBu', '-c', bootstrap,
                   branch['repo_root'], branch['name'],
                   Path(sys.argv[0]).name, json.dumps(public_argv), *arguments]
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
    public_argv = list(sys.argv[1:])
    arguments, selected = [], None
    pinned_branch = None
    reset_lease = None
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
        reset_lease = forwarded.get('reset_lease')
        if reset_lease is not None:
            from launcher_queue import reset_path
            if (type(reset_lease) is not int or reset_lease < 3
                    or not os.path.samestat(os.fstat(reset_lease), reset_path(root).stat(follow_symlinks=False))):
                raise ValueError('Invalid checkout reset handoff.')
        public_argv = forwarded.get('public_argv', public_argv)
        synced = forwarded.get('synced', False)
        if pinned_branch is not None:
            _local_checkout(root, pinned_branch)
    elif (name in _TEST_LAUNCHERS and selected is None
          and (os.environ.get('ONPC_LAUNCHER_CONTROLLER_ROOT') == str(root)
               or os.environ.get('ONPC_RUNNER_INVOCATION')
               or os.environ.get('ONPC_TEST_RESULT_DIRECTORY'))):
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
            default_branch = defaults.get(name, {}).get('default_branch')
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
                    return _remote(host, branch, arguments, public_argv)
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
                                                       launcher=name, pid=os.getpid(), public_argv=public_argv))
                    os.chdir(destination)
                    os.execve('/usr/bin/python3', ['/usr/bin/python3', '-IBu', str(command),
                              *arguments], env)

    if pinned_branch is not None and not synced:
        _pending_startup = (pinned_branch, arguments)
        changed = _early_sync(root, pinned_branch, arguments)
        if changed is not None:
            _pending_startup = None
        if changed:
            # Refresh all controller imports and pin placement across exec.
            from test_source import leave_checkout
            leave_checkout()
            env = dict(os.environ)
            env[DESTINATION] = json.dumps(dict(root=str(root), branch=pinned_branch,
                launcher=name, pid=os.getpid(), synced=True, public_argv=public_argv,
                reset_lease=reset_lease))
            sys.stdout.flush()
            sys.stderr.flush()
            os.chdir(root)
            os.execve('/usr/bin/python3', ['/usr/bin/python3', '-IBu',
                      str(root / 'tools' / name), *arguments], env)
    import test_source
    # Ordinary tests retain live import admission. Repairs work directly from
    # the selected checkout and own their execution through the detached owner.
    queue_control = any(arg.partition('=')[0] in _QUEUE_CONTROLS for arg in arguments)
    admission = (test_source.admission(root, arguments)
                 if name in _TEST_LAUNCHERS and not queue_control else nullcontext())
    with admission:
        return _entry(root, name, pinned_branch, arguments, entry, public_argv=public_argv,
                      reset_lease=reset_lease)


def _entry(root, name, pinned_branch, arguments, entry, *, public_argv=None, reset_lease=None):
    global _pending_startup, _public_invocation
    from vm_selection import vm_config
    original_arguments = list(arguments)
    split = arguments.index('--') if '--' in arguments else len(arguments)
    options, forwarded = arguments[:split], arguments[split:]
    if any(arg.partition('=')[0] in _QUEUE_CONTROLS for arg in options):
        from launcher_queue import cancel, tickets
        if arguments == ['--queue-list']:
            for row in tickets(root, name, on_error=lambda error: print(error, file=sys.stderr)):
                state = 'paused' if row['paused'] else 'waiting'
                print(f"{row['id']}  {state}  {row['command']}")
                if row['error']:
                    print(row['error'])
        elif len(arguments) == 2 and arguments[0] == '--queue-cancel':
            cancel(root, arguments[1], name)
            print(f'Removed queued ticket {arguments[1]}.')
        else:
            raise ValueError('Use --queue-list or --queue-cancel TICKET with an optional --branch.')
        return 0
    fresh = '--start-fresh' in options
    if fresh and any(arg.partition('=')[0] in (*_CONTROLS, '--resume') for arg in options):
        raise ValueError('--start-fresh requires a new run command.')
    request_arguments = [arg for arg in options if arg != '--start-fresh'] + forwarded
    vm_test_launcher = name in ('run-tests', 'fix-tests')
    arguments = vm_config.host_arguments(request_arguments) if name == 'execute-plan' else request_arguments
    sys.argv[1:] = arguments
    if any(arg in ('--help', '-h') for arg in arguments):
        print(BRANCH_HELP, flush=True)
        print('--queue-list lists waiting jobs, --queue-cancel TICKET removes one, '
              'and --start-fresh explicitly starts a new run after interruption.', flush=True)
        if vm_test_launcher or name == 'execute-plan':
            print(vm_config.host_help(), flush=True)
    import test_source
    previous_invocation = _public_invocation
    _public_invocation = Invocation(name, original_arguments if public_argv is None else public_argv,
                                    pinned_branch, request_arguments, options, fresh, reset_lease)
    if reset_lease is not None:
        os.set_inheritable(reset_lease, False)
    try:
        return entry()
    except test_source.RestartExecution as restart:
        # Every controller/reset/resource context has unwound. Preserve the
        # resolved destination even if a source change altered branch defaults.
        with ExitStack() as leases:
            handoff_lease = restart.reset_lease if restart.reset_lease is not None else reset_lease
            if restart.reset_lease is not None:
                leases.callback(os.close, restart.reset_lease)
            test_source.finish_admission()
            arguments = [arg for arg in original_arguments if arg not in ('--reload', '--reset')]
            temporary = test_source.VARIABLE not in test_source.environment()
            leases.enter_context(test_source.startup(root, arguments))
            from launcher_reload import replace
            inherited = test_source.environment()
            if temporary:
                os.environ[test_source.IMPORTS] = inherited[test_source.VARIABLE]
            os.environ[DESTINATION] = json.dumps(dict(root=str(root), branch=pinned_branch,
                launcher=name, pid=os.getpid(), reset_lease=handoff_lease,
                public_argv=[arg for arg in _public_invocation.public_argv if arg not in ('--reload', '--reset')]))
            try:
                replace(['/usr/bin/python3', '-IBu', str(root / 'tools' / name), *arguments],
                        (handoff_lease,) if handoff_lease is not None else ())
            finally:
                if temporary:
                    os.environ.pop(test_source.IMPORTS, None)
                os.environ.pop(DESTINATION, None)
    finally:
        _pending_startup = None
        _public_invocation = previous_invocation
        if reset_lease is not None:
            os.close(reset_lease)


def run(entry):
    from launcher_reload import STATUS as RELOAD_STATUS

    def admitted():
        import test_source
        try:
            root = Path(__file__).resolve().parents[1]
            # Bootstrap reads placement metadata. Ordinary workflow imports
            # retain live source admission after any synchronization.
            bootstrap = (['--help'] if any(arg.split('=', 1)[0] in _CONTROLS
                                         for arg in sys.argv[1:]) else ['--resume'])
            with test_source.admission(root, bootstrap):
                return dispatch(entry)
        except (RetryQueuedStartup, SyncBusy, test_source.SourceBusy) as error:
            from launcher_queue import REPLAY, RETRY
            print(f'launcher: {error}', file=sys.stderr)
            return RETRY if os.environ.get(REPLAY) else 2
        except (OSError, ValueError, subprocess.TimeoutExpired) as error:
            print(f'launcher: {error}', file=sys.stderr)
            return 2

    try:
        status = admitted()
    except SystemExit as error:
        if error.code:
            print('\033[31mLauncher command failed.\033[0m', file=sys.stderr, flush=True)
        raise
    if status and not (status == RELOAD_STATUS and Path(sys.argv[0]).name == 'run-tests'):
        print('\033[31mLauncher command failed.\033[0m', file=sys.stderr, flush=True)
    return status
