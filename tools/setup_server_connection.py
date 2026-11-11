"""Verify this checkout's configured Watch SSH sources; use setup.sh."""

import os
from pathlib import Path
import shlex
import shutil
import subprocess
import sys


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'tests/integration'))
import vm_config
sys.path.pop(0)


def run(argv, *, step):
    print(f'Setup: {step}...', flush=True)
    try:
        return subprocess.run(argv, check=True, stdin=subprocess.DEVNULL)
    except subprocess.CalledProcessError as error:
        # Command arguments can contain private connection details.
        raise ValueError(f'{step} failed (exit status {error.returncode}); '
                         'see command output above') from None
    except OSError as error:
        raise ValueError(f'{step} could not start: {error.strerror}') from None


def main():
    if os.geteuid() == 0:
        raise ValueError('run ./setup.sh --connect-server as your desktop user, without sudo')
    if shutil.which('ssh') is None:
        raise ValueError('ssh is missing; run ./setup.sh for client prerequisites')
    editor = next((name for name in ('code', 'code-insiders', 'codium') if shutil.which(name)), None)
    if editor is None:
        raise ValueError('install VS Code (or Codium) before setting up Watch')

    document = vm_config.read_document(ROOT / 'config/environment.json')
    servers = [host for host in vm_config.host_registry(document).values()
               if host.transport == 'ssh']
    if not servers:
        raise ValueError('add an SSH host and its branches to config/environment.json first')
    branches = vm_config.branch_registry(document)
    print('Checking all configured SSH hosts, including hosts disabled for VM scheduling.')
    print('SSH addresses, users, ports and keys are managed separately from this repository.')
    for server in servers:
        alias = server.name
        checkouts = [branch for branch in branches.values() if branch['host'] == alias]
        if not checkouts:
            raise ValueError(f'add a branch checkout for {alias} to config/environment.json')
        print(f'Using existing SSH configuration for {alias}.')
        for branch in checkouts:
            print(f"  {branch['name']}: {branch['repo_root']}")
        print(f'Setup: verifying noninteractive SSH access to {alias}...', flush=True)
        ssh = ['ssh', '-T', '-o', 'BatchMode=yes', '-o', 'StrictHostKeyChecking=yes',
               '-o', 'ConnectTimeout=15', '--', alias]
        result = subprocess.run([*ssh, 'true'], check=False, stdin=subprocess.DEVNULL)
        if result.returncode:
            raise ValueError(f'noninteractive SSH verification for {alias} failed '
                             f'(exit status {result.returncode}); see SSH output above. '
                             'Configure machine-to-machine SSH separately '
                             '(load a locked key with ssh-add if needed), then verify '
                             + shlex.join(['ssh', '-o', 'BatchMode=yes', alias, 'true'])
                             + ' before rerunning setup')
        # Watch uses the first checkout to discover the related Git worktrees.
        probe = ('test -f ' + shlex.quote(checkouts[0]['repo_root'] + '/tools/watch_webview.py')
                 + ' && command -v python3 >/dev/null')
        run([*ssh, probe], step=f'checking the Watch checkout and Python 3 on {alias}')
    print('All configured SSH hosts verified. Open this local checkout:')
    print('  ' + editor + ' ' + shlex.quote(str(ROOT)))
    print('Use ONPC: Watch to observe and manage local and remote launchers together.')
    print('Leave onpc.watch.sources empty (the default) to use config/environment.json.')
    print('After changing the registry, click Reconnect in Watch.')


if __name__ == '__main__':
    try:
        main()
    except (ValueError, OSError, KeyboardInterrupt) as error:
        # Avoid echoing server addresses or remote command arguments into logs.
        if isinstance(error, ValueError):
            message = str(error)
        elif isinstance(error, OSError):
            message = f'local file or program operation failed: {error.strerror}'
        else:
            message = 'connection check cancelled'
        print('setup: ' + message, file=sys.stderr)
        sys.exit(1)
