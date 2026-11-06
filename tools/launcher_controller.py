"""Reloadable public controller admission and branch/host dispatch policy."""

import json
import os
from pathlib import Path
import shlex
import subprocess
import sys


DESTINATION = 'ONPC_LAUNCHER_DESTINATION'
BRANCH_HELP = ('--branch NAME selects a config/environment.json branch; default: '
               'this launcher\'s default_branch, then the current checkout branch.')


def _git(root, *args):
    result = subprocess.run(['git', '-C', str(root), *args], text=True,
                            stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False)
    if result.returncode:
        raise ValueError(f'cannot identify launcher checkout at {root}: {result.stderr.strip()}')
    return result.stdout.strip()


def _local_checkout(root, branch):
    if (not root.is_dir()
            or Path(_git(root, 'rev-parse', '--show-toplevel')).resolve() != root.resolve()
            or _git(root, 'symbolic-ref', '--quiet', '--short', 'HEAD') != branch):
        raise ValueError(f'configured checkout {root} must have branch {branch} checked out')


def _remote(host, branch, arguments):
    """Let SSH carry the terminal and exit status; never execute locally."""
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
    # SSH commands skip interactive shell setup. NVM's usual .bashrc entry
    # sits below its interactive-only guard, hiding both Codex and its Node
    # interpreter. Load NVM's selected default only when Codex is not on PATH;
    # do not source the whole interactive rc file or hard-code a Node version.
    remote = shlex.join(['/bin/bash', '-c', '''if ! command -v codex >/dev/null 2>&1; then
    export NVM_DIR="${NVM_DIR:-$HOME/.nvm}"
    if [ -s "$NVM_DIR/nvm.sh" ]; then
        . "$NVM_DIR/nvm.sh"
    fi
fi
exec "$@"
''', 'onpc-launcher', *destination])
    command = ['ssh', '-t' if sys.stdin.isatty() and sys.stdout.isatty() else '-T',
               '-o', 'BatchMode=yes', '-o', 'StrictHostKeyChecking=yes',
               '-o', 'IgnoreUnknown=UseKeychain', '-o', 'ConnectTimeout=10',
               '-o', 'ServerAliveInterval=30', '-o', 'ServerAliveCountMax=3',
               '-p', str(host.ssh_port), host.name, remote]
    sys.stdout.flush()
    sys.stderr.flush()
    os.execvp(command[0], command)


def dispatch(entry):
    root = Path(__file__).resolve().parents[1]
    name = Path(sys.argv[0]).name
    arguments, selected = [], None
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
        _local_checkout(root, forwarded['branch'])
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
            document = vm_config.read_document(path)
            defaults = vm_config.launcher_registry(document)
            explicit = selected is not None
            # Plans B/C are independent of the original write-e2e owner and its
            # configured default checkout. Explicit branch routing still wins.
            default_branch = (None if name == 'write-e2e' and
                              any(flag in arguments for flag in ('--planb', '--planc'))
                              else defaults.get(name, {}).get('default_branch'))
            selected = selected or default_branch
            configured = selected is not None
            selected = selected or _git(root, 'symbolic-ref', '--quiet', '--short', 'HEAD')
            branch = vm_config.branch_registry(document).get(selected)
            if branch is None:
                if explicit or configured:
                    raise ValueError('--branch must name a branch in config/environment.json')
                # Unregistered checkouts still run on their own current branch.
            else:
                host = vm_config.host_registry(document)[branch['host']]
                if host.transport != 'local':
                    return _remote(host, branch, arguments)
                destination = Path(branch['repo_root']).resolve()
                _local_checkout(destination, selected)
                if destination != root:
                    command = destination / 'tools' / name
                    if not command.is_file() or command.is_symlink():
                        raise ValueError(f'launcher is missing from configured checkout: {command}')
                    sys.stdout.flush()
                    sys.stderr.flush()
                    env = dict(os.environ)
                    env[DESTINATION] = json.dumps(dict(root=str(destination), branch=selected,
                                                       launcher=name, pid=os.getpid()))
                    os.chdir(destination)
                    os.execve('/usr/bin/python3', ['/usr/bin/python3', '-IBu', str(command),
                              *arguments], env)

    sys.argv[1:] = arguments
    if any(arg in ('--help', '-h') for arg in arguments):
        print(BRANCH_HELP, flush=True)
        if name == 'write-e2e' and any(flag in arguments for flag in ('--planb', '--planc')):
            print('--planb/--planc default to the current checkout branch; --branch overrides it.', flush=True)
    return entry()


def run(entry):
    from launcher_bootstrap import run as bootstrap_run

    def admitted():
        try:
            return dispatch(entry)
        except (OSError, ValueError) as error:
            print(f'launcher: {error}', file=sys.stderr)
            return 2

    return bootstrap_run(admitted)
