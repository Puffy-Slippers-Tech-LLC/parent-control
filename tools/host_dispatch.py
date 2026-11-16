"""Host-relative routing and noninteractive SSH for development tools.

Registry transport labels describe the original workstation layout. Locality
always compares the executing tool/controller host with the destination host.
SSH aliases, credentials and trusted keys remain private OpenSSH configuration.
"""

from pathlib import Path
import os
import shlex
import subprocess


def git(root, *args):
    result = subprocess.run(['git', '-C', str(root), *args], text=True,
                            stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False)
    if result.returncode:
        raise ValueError(f'cannot identify tool checkout at {root}: {result.stderr.strip()}')
    return result.stdout.strip()


def require_checkout(root, branch):
    root = Path(root)
    if (not root.is_dir()
            or Path(git(root, 'rev-parse', '--show-toplevel')).resolve() != root.resolve()
            or git(root, 'symbolic-ref', '--quiet', '--short', 'HEAD') != branch):
        raise ValueError(f'configured checkout {root} must have branch {branch} checked out')


def tool_host(root, document=None):
    """A public tool runs from a registered Git branch, independently of flags."""
    from vm_selection import vm_config
    document = (vm_config.read_document(Path(root) / 'config/environment.json', validate_agent=False)
                if document is None else document)
    origin = vm_config.remote_origin() if Path(root) == vm_config.ROOT else None
    if origin is not None:
        return vm_config.host_registry(document)[vm_config.execution_host()]
    name = (vm_config.current_branch() if Path(root) == vm_config.ROOT else
            git(root, 'symbolic-ref', '--quiet', '--short', 'HEAD'))
    branch = vm_config.branch_registry(document).get(name)
    if branch is None:
        raise ValueError(f'tool branch {name!r} must be registered in config/environment.json')
    host = vm_config.host_registry(document)[branch['host']]
    return host


def ssh_command(host, argv):
    """Quote an argv exactly once for OpenSSH's remote shell; never prompt."""
    if not argv:
        raise ValueError('host-dispatch: a destination command is required')
    command = ['ssh', '-T', '-o', 'BatchMode=yes', '-o', 'StrictHostKeyChecking=yes',
               '-o', 'IgnoreUnknown=UseKeychain', '-o', 'ConnectTimeout=15',
               '-o', 'ServerAliveInterval=30', '-o', 'ServerAliveCountMax=3']
    if host.ssh_port is not None:
        command += ['-p', str(host.ssh_port)]
    return [*command, '--', host.name, shlex.join(str(arg) for arg in argv)]


def ssh_environment(environment):
    """Use the client's authentication agent only for the SSH client process."""
    result = dict(environment)
    if 'SSH_AUTH_SOCK' in os.environ:
        result['SSH_AUTH_SOCK'] = os.environ['SSH_AUTH_SOCK']
    return result


def artifact_reader(root, vm, argv):
    """Read on the artifact host without capturing or admitting checkout source."""
    if argv[:1] not in (['list'], ['stat'], ['read'], ['tail']):
        raise ValueError('artifacts requires list, stat, read or tail')
    return remote_inspection(root, vm, '/usr/local/libexec/onpc-test-artifacts', argv)


def remote_inspection(root, vm, program, argv):
    """Use an installed authenticated reader without capturing working source."""
    from vm_selection import vm_config
    document = vm_config.read_document(Path(root) / 'config/environment.json', validate_agent=False)
    if vm.host.name == tool_host(root, document).name:
        return None
    anchor = next((item['repo_root'] for item in vm_config.branch_registry(document).values()
                   if item['host'] == vm.host.name), None)
    if anchor is None:
        raise ValueError(f'no configured storage checkout on {vm.host.name}')
    # The installed reader authenticates the SSH account and confines every path.
    # Descriptor aliases and source fences belong to execution, not inspection.
    command = ssh_command(vm.host, ['/usr/bin/env', '-C', anchor,
        '/usr/bin/pkexec', '--disable-internal-agent', '--keep-cwd',
        program, *argv])
    try:
        return subprocess.run(command, cwd=root, check=False, timeout=60).returncode
    except subprocess.TimeoutExpired as error:
        raise ValueError('remote inspection timed out on ' + vm.host.name) from error


def vm_tool(root, vm, tool, options, *, stdin_file=None, wait_on_cancel=False):
    """Run a public VM tool on its host using this checkout's working source.

    Return None for local work so the caller keeps its existing implementation.
    The destination public tool retains selection, ownership and helper checks.
    """
    if vm.host.name == tool_host(root).name:
        return None
    if tool == 'test-vm' and options == ['--vm', vm.name, 'probe', 'memory']:
        return remote_inspection(root, vm, '/usr/local/libexec/onpc-test-runner',
                                 ['vm', '--vm', vm.name, 'probe', 'memory'])
    from regression_process import Control
    from remote_sources import RemoteVM
    import test_launcher
    with Control().installed() as control:
        return RemoteVM(root, vm).run(control,
            ['/usr/bin/python3', '-IBu', str(Path(root) / 'tools' / tool), *options],
            env=test_launcher.environment(root), stdin_file=stdin_file,
            wait_on_cancel=wait_on_cancel)
