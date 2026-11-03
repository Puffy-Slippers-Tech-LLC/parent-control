"""Reloadable public controller admission and branch/host dispatch policy."""

import json
import os
from pathlib import Path
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
    """Future SSH controller transport; never fall back to local execution."""
    raise ValueError(f'SSH controller launch is not implemented: host {host.name}, '
                     f'branch {branch["name"]}, checkout {branch["repo_root"]}')


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
          and (os.environ.get('ONPC_RUNNER_INVOCATION')
               or len(arguments) > 1 and arguments[1] == '--unattended')):
        # Repair attempts and category children already belong to this
        # checkout's controller. Reapplying the public default can verify
        # another checkout instead of the repair (or fail ownership guards).
        pass
    else:
        from vm_selection import vm_config
        path = root / 'config/environment.json'
        if path.exists() or selected is not None:
            document = vm_config.read_document(path)
            defaults = vm_config.launcher_registry(document)
            explicit = selected is not None
            selected = selected or defaults.get(name, {}).get('default_branch')
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
