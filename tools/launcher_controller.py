"""Reloadable public controller admission and branch/host dispatch policy."""

import json
import os
from pathlib import Path
import subprocess
import sys

from host_dispatch import git as _git, require_checkout as _local_checkout, ssh_command, tool_host


DESTINATION = 'ONPC_LAUNCHER_DESTINATION'
BRANCH_HELP = ('--branch NAME selects a config/environment.json branch; default: '
               'this launcher\'s default_branch, then the current checkout branch.')
_pending_startup = None


def sync_startup(root, previous=None):
    """Run the public controller's sync only after detached start admission."""
    global _pending_startup
    pending, _pending_startup = _pending_startup, None
    if pending is not None:
        # Recovery owns the original source until its recorded transaction is
        # settled. Its existing safe pull boundary will synchronize afterward.
        if previous is not None:
            for filename in ('checkpoint.json', 'translation-state.json'):
                path = previous / filename
                if path.exists():
                    saved = json.loads(path.read_text())
                    if any(saved.get(key) for key in (
                            'commit_intent', 'pull_intent', 'pending_completion', 'pending',
                            'worktree_propagation', 'upstream_pull', 'git_reconciliation')):
                        print('Git: deferring startup pull to pending workflow recovery.', flush=True)
                        return
        branch, arguments = pending
        _startup_sync(root, branch, arguments)


def _pull(root):
    result = subprocess.run(['git', 'pull'], cwd=root, text=True,
        stdin=subprocess.DEVNULL, capture_output=True, timeout=120,
        env=dict(os.environ, GIT_TERMINAL_PROMPT='0'), check=False)
    if result.returncode:
        raise ValueError(result.stderr.strip() or result.stdout.strip())


def _recover_pull(root, diagnostic, selection, profile):
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
                                input=prompt, text=True, timeout=1200, check=False)
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
    _pull(root)


def _startup_sync(root, branch, arguments):
    """Pull before job startup; controller code keeps its explicit reload path."""
    controls = ('--help', '-h', '--list', '--check', '--collect-only', '--stop',
                '--cancel-stop', '--add-session', '--reload', '--reset',
                '--reconcile', '--review-ownership')
    if any(arg.split('=', 1)[0] in controls for arg in arguments):
        return
    import fcntl
    from test_source import SourceProtection, source_directory, finish_admission, _lock
    finish_admission()
    protection = SourceProtection(source_directory(root))
    common = Path(_git(root, 'rev-parse', '--path-format=absolute', '--git-common-dir'))
    # Share the propagation lock and source lease, so no pull runs over active
    # sessions/tests or another Git transaction. No stash or new journal needed.
    with _lock(common / 'onpc-worktree-propagation.lock') as transaction:
        try:
            fcntl.flock(transaction, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError as error:
            raise ValueError('repository synchronization is busy; retry after it finishes') from error
        with _lock(protection.directory / 'repair-owner') as source:
            with protection.state():
                try:
                    fcntl.flock(source, fcntl.LOCK_EX | fcntl.LOCK_NB)
                except BlockingIOError as error:
                    raise ValueError('checkout source is busy; retry after its owner finishes') from error
                if protection.owner() is not None or protection.impact_holds():
                    print('Git: deferring startup pull to retained repair recovery.', flush=True)
                    return
            from agent_adapter import resolve_profile, resolve_selection
            selection = resolve_selection(root)
            # Pin recovery code/profile before Git can put their source files
            # into conflict. This prepares no session on the successful path.
            selection.adapter()
            profile = resolve_profile('conflict_resolver', effort='low', selection=selection)
            print('Git: synchronizing controller checkout with its upstream.', flush=True)
            try:
                _pull(root)
            except (OSError, ValueError, subprocess.TimeoutExpired) as error:
                print('Git pull failed; starting a low-effort recovery session.', flush=True)
                _recover_pull(root, str(error), selection, profile)
            _local_checkout(root, branch)


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
        if forwarded['root'] != str(root) or forwarded['launcher'] != name or selected is not None:
            raise ValueError('forwarded launcher destination changed')
        pinned_branch = forwarded['branch']
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

    if pinned_branch is not None:
        _pending_startup = (pinned_branch, arguments)
    sys.argv[1:] = arguments
    if any(arg in ('--help', '-h') for arg in arguments):
        print(BRANCH_HELP, flush=True)
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
