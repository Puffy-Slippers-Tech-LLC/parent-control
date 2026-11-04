"""Interactive, caller-owned SSH and Watch configuration; use setup.sh."""

import ipaddress
import json
import os
from pathlib import Path
import re
import shlex
import shutil
import stat
import subprocess
import sys
import tempfile


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'tests/integration'))
import vm_config
sys.path.pop(0)


def prompt(label, default=''):
    value = input(f'{label}' + (f' [{default}]' if default else '') + ': ').strip()
    return value or default


def private_directory(path):
    # Do not follow links or adopt someone else's configuration directory.
    for parent in reversed((path, *path.parents)):
        if parent.is_symlink():
            raise ValueError('configuration path contains a symbolic link')
    path.mkdir(mode=0o700, parents=True, exist_ok=True)
    if path.stat().st_uid != os.getuid():
        raise ValueError('configuration directory belongs to another account')
    path.chmod(0o700)


def read_private(path):
    if path.is_symlink():
        raise ValueError('refusing symbolic-link configuration file')
    if not path.exists():
        return None
    info = path.stat()
    if not stat.S_ISREG(info.st_mode) or info.st_uid != os.getuid() or info.st_nlink != 1:
        raise ValueError('configuration file is not a caller-owned regular file')
    return path.read_text()


def write_private(path, text):
    read_private(path)
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(mode='w', dir=path.parent, delete=False) as stream:
            temporary = Path(stream.name)
            stream.write(text)
        read_private(path)
        os.replace(temporary, path)
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)


def run(argv, *, step, **kwargs):
    print(f'Setup: {step}...', flush=True)
    try:
        return subprocess.run(argv, check=True, **kwargs)
    except subprocess.CalledProcessError as error:
        # Command arguments can contain private connection details.
        raise ValueError(f'{step} failed (exit status {error.returncode}); '
                         'see command output above. Local files retained for retry') from None
    except OSError as error:
        raise ValueError(f'{step} could not start: {error.strerror}') from None


def main():
    if os.geteuid() == 0 or not sys.stdin.isatty():
        raise ValueError('run ./setup.sh --connect-server interactively as your desktop user')
    for program in ('ssh', 'ssh-keygen', 'ssh-copy-id'):
        if shutil.which(program) is None:
            raise ValueError(f'{program} is missing; run ./setup.sh for client prerequisites')
    editor = next((name for name in ('code', 'code-insiders', 'codium') if shutil.which(name)), None)
    if editor is None:
        raise ValueError('install VS Code (or Codium) before configuring its Watch workspace')

    document = vm_config.read_document(ROOT / 'config/environment.json')
    servers = [host for host in vm_config.host_registry(document).values()
               if host.name != 'local' and host.transport == 'ssh']
    if not servers:
        raise ValueError('add an SSH host and its branches to config/environment.json first')
    selected = servers[0]
    if len(servers) > 1:
        print('Configured servers (including hosts disabled for VM scheduling):')
        for server in servers:
            print('  ' + server.name)
        name = prompt('Select server', selected.name)
        selected = next((server for server in servers if server.name == name), None)
        if selected is None:
            raise ValueError('select a server name from the configured list')
    alias = selected.name
    branches = [branch for branch in vm_config.branch_registry(document).values()
                if branch['host'] == selected.name]
    if not branches:
        raise ValueError('add at least one branch checkout for this server to config/environment.json')
    remote_root = branches[0]['repo_root']
    port = selected.ssh_port
    print(f'Using configured server {alias}, SSH port {port}.')
    print('Configured remote checkouts:')
    for branch in branches:
        print(f"  {branch['name']}: {branch['repo_root']}")
    print('Watch starts from the first checkout and discovers the other registered Git worktrees.')
    print('Server setup lists the registered worktrees and checks Codex login and Git access.')
    print('Connection details stay in your home directory, outside Git.')
    ssh_dir = Path.home() / '.ssh'
    private_directory(ssh_dir)
    profiles = ssh_dir / 'onpc'
    private_directory(profiles)
    profile = profiles / f'{alias}.conf'
    previous = read_private(profile)
    defaults = {}
    if previous:
        for line in previous.splitlines():
            fields = line.split()
            if len(fields) == 2:
                defaults[fields[0]] = fields[1]
    print('Use the account and one reachable address from the ./setup.sh --server connection summary.')
    host = prompt('Server address or hostname', defaults.get('HostName', ''))
    try:
        ipaddress.ip_address(host)
    except ValueError:
        if not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9.-]*', host):
            raise ValueError('enter a plain IP address or hostname')
    user = prompt('Server login username', defaults.get('User', ''))
    if not re.fullmatch(r'[A-Za-z_][A-Za-z0-9_.-]*', user):
        raise ValueError('enter a plain login username')
    workspace_dir = Path.home() / '.config' / 'onpc'
    private_directory(workspace_dir)
    workspace = workspace_dir / f'{alias}.code-workspace'
    old_workspace = read_private(workspace)
    if old_workspace:
        saved = json.loads(old_workspace)

    # Preflight existing SSH configuration before generating or replacing files.
    config = ssh_dir / 'config'
    original = read_private(config) or ''
    # Reset the included Host context so leading global options in the original
    # file still apply to every host.
    # macOS configurations commonly use UseKeychain; Linux OpenSSH rejects it
    # unless IgnoreUnknown appears first. Preserve the existing option for Macs.
    include = 'IgnoreUnknown UseKeychain\nInclude ~/.ssh/onpc/*.conf\nHost *\n'
    if previous is None:
        resolved = run(['ssh', '-G', '-o', 'IgnoreUnknown=UseKeychain', alias],
                       step='checking local SSH configuration',
                       text=True, stdout=subprocess.PIPE).stdout
        hostname = next((line.split(maxsplit=1)[1] for line in resolved.splitlines()
                         if line.startswith('hostname ')), alias)
        if hostname != alias:
            raise ValueError('configured host alias already exists outside the managed profiles; reconcile local SSH configuration first')
    key = profiles / f'{alias}_ed25519'
    read_private(key)
    read_private(Path(str(key) + '.pub'))
    if not key.exists():
        # Let OpenSSH request a passphrase; never store or copy private keys.
        run(['ssh-keygen', '-t', 'ed25519', '-f', str(key), '-C', 'ONPC remote client'],
            step='creating the client SSH key')
    elif not Path(str(key) + '.pub').exists():
        raise ValueError('existing client key lacks its public key; repair it before retrying')
    text = (f'Host {alias}\n    HostName {host}\n    User {user}\n    Port {port}\n'
            f'    IdentityFile "{key}"\n    IdentitiesOnly yes\n'
            '    StrictHostKeyChecking ask\n    ServerAliveInterval 30\n'
            '    ServerAliveCountMax 3\n')
    write_private(profile, text)
    # Put the include before Host/Match sections; preserve the rest byte-for-byte.
    if not original.startswith(include):
        write_private(config, include + original)

    print('Compare the SSH fingerprint with the ./setup.sh --server connection summary before accepting it.')
    print('SSH may request the server password and your client key passphrase.')
    run(['ssh-copy-id', '-i', str(key) + '.pub', '-o', 'StrictHostKeyChecking=ask', alias],
        step='authorizing the client public key on the server')
    print('Setup: verifying noninteractive SSH access...', flush=True)
    result = subprocess.run(['ssh', '-o', 'BatchMode=yes', '-o', 'StrictHostKeyChecking=yes',
                             alias, 'true'], check=False)
    if result.returncode:
        raise ValueError(f'noninteractive SSH verification failed (exit status {result.returncode}); '
                         'see SSH output above. If the client key is locked, run '
                         + shlex.join(['ssh-add', str(key)]) + ', then rerun this setup')
    # Check the actual Watch prerequisite without starting any test or agent.
    probe = ('test -f ' + shlex.quote(remote_root + '/tools/watch_webview.py')
             + ' && command -v python3 >/dev/null')
    run(['ssh', '-o', 'BatchMode=yes', '-o', 'StrictHostKeyChecking=yes', alias, probe],
        step='checking the remote checkout and Python 3')
    data = {'folders': [{'path': str(ROOT)}], 'settings': {'onpc.watch.sources': [
        {'id': 'local', 'label': 'This computer', 'transport': 'local'},
        {'id': re.sub(r'[^A-Za-z0-9_-]', '_', alias), 'label': alias,
         'transport': 'ssh', 'host': alias, 'root': remote_root},
    ]}}
    if old_workspace:
        saved['folders'] = data['folders']
        saved.setdefault('settings', {})['onpc.watch.sources'] = data['settings']['onpc.watch.sources']
        data = saved
    write_private(workspace, json.dumps(data, indent=2) + '\n')
    print('Client access verified. Open the private Watch workspace:')
    print('  ' + editor + ' ' + shlex.quote(str(workspace)))
    print('Then use ONPC: Watch. Repeating this setup reuses the client key and profile.')
    print('Resolve any action-needed items in the server setup summary before starting fix-tests.')
    print('Launch remotely with:')
    print('  ssh -t ' + shlex.quote(alias) + ' ' + shlex.quote(
        'cd ' + shlex.quote(remote_root) + ' && tools/fix-tests unit'))


if __name__ == '__main__':
    try:
        main()
    except (ValueError, OSError, EOFError, KeyboardInterrupt) as error:
        # Avoid echoing server addresses or remote command arguments into logs.
        if isinstance(error, ValueError):
            message = str(error)
        elif isinstance(error, OSError):
            message = f'local file or program operation failed: {error.strerror}; local files retained for retry'
        elif isinstance(error, EOFError):
            message = 'input ended before setup completed; rerun ./setup.sh --connect-server in a terminal'
        else:
            message = 'connection setup cancelled; local files retained for retry'
        print('setup: ' + message, file=sys.stderr)
        sys.exit(1)
