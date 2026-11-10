"""Shared VM configuration: validate known fields and ignore unknown attributes.

Loading never accesses libvirt or VM disks.
"""

from dataclasses import dataclass
import argparse
import json
import os
from pathlib import Path
import re
import subprocess
import sys


CONFIG = Path(__file__).resolve().parents[2] / 'config/environment.json'
FIXTURE_ROOT = Path(__file__).resolve().parents[1] / 'fixtures'
URI = 'qemu:///system'
STATE_ROOT = Path('/Data/virt-manager/oh-no-parent-control-baseline-state')
VARIABLE = 'ONPC_TEST_VM'
ROOT = Path(__file__).resolve().parents[2]


@dataclass(frozen=True)
class HostConfig:
    name: str = 'local'
    enabled: bool = True
    transport: str = 'local'
    concurrency: int = 1
    backup_root: Path | None = None
    ssh_port: int = 22


@dataclass(frozen=True)
class VMConfig:
    name: str
    disk_anchor: Path
    enabled: bool = False
    id: str | None = None
    package_format: str | None = None
    family: str | None = None
    fixture_path: str | None = None
    owning_branch: str = ''
    host: HostConfig = HostConfig()

    def require_build_target(self):
        # Standalone helpers can import vm_config before adding the checkout.
        sys.path.insert(0, str(ROOT))
        try:
            from tools.build_targets import from_family
            return from_family(self.family, self.require_package_format())
        finally:
            sys.path.pop(0)

    def require_package_format(self):
        # Consumers must never infer a format from a VM or family name.
        if self.package_format not in ('deb', 'rpm'):
            raise ValueError('vm-config:package_format must explicitly be deb or rpm for ' + self.name)
        return self.package_format

    @property
    def hostname(self):
        return self.name.lower()

    @property
    def baseline_directory(self):
        # Each configured name has its own provenance. Never adopt the old
        # unscoped phase.json or another VM's accepted snapshot automatically.
        return STATE_ROOT / self.name


def unique_keys(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError('vm-config:duplicate-key')
        result[key] = value
    return result


def validate_name(name):
    # Preserve the libvirt display name's case; hostname consumers normalize it.
    if (not isinstance(name, str) or not name or len(name) > 63 or
            not all(re.fullmatch(r'[A-Za-z0-9](?:[A-Za-z0-9-]*[A-Za-z0-9])?', label)
                    for label in name.split('.'))):
        raise ValueError('vm-config:name; use hostname labels without traversal')
    return name


def read_document(path=None, *, validate_agent=True):
    path = CONFIG if path is None else path
    try:
        document = json.loads(path.read_text(encoding='utf-8'), object_pairs_hook=unique_keys)
    except (OSError, UnicodeError, json.JSONDecodeError) as error:
        raise ValueError('vm-config:unreadable; check config/environment.json') from error
    if (not isinstance(document, dict) or not {'families'} <= set(document) or
            not isinstance(document['families'], list) or not document['families']):
        raise ValueError('vm-config:fields')
    if validate_agent and 'agent' in document and document['agent'] not in ('codex', 'claude'):
        raise ValueError('vm-config:agent must be exactly codex or claude')
    if 'backup_root' in document:
        absolute_path(document['backup_root'], 'backup_root')
    host_registry(document)
    branch_registry(document)
    launcher_registry(document)
    return document


def launcher_registry(document):
    """Optional launcher defaults reference the shared branch placement registry."""
    branches = branch_registry(document)
    entries = document.get('launchers', [])
    if not isinstance(entries, list):
        raise ValueError('vm-config:launchers must be an array')
    launchers = {}
    for entry in entries:
        if not isinstance(entry, dict) or 'name' not in entry:
            raise ValueError('vm-config:launcher requires name')
        name = validate_name(entry['name'])
        if name in launchers:
            raise ValueError('vm-config:duplicate launcher')
        branch = entry.get('default_branch')
        if 'default_branch' in entry and (not isinstance(branch, str) or branch not in branches):
            raise ValueError('vm-config:launcher default_branch must name a configured branch')
        launchers[name] = dict(entry)
    return launchers


def branch_registry(document):
    """Branch placement is independent of VM/host online scheduling flags."""
    hosts = host_registry(document)
    entries = document.get('branches', [])
    if not isinstance(entries, list):
        raise ValueError('vm-config:branches must be an array')
    branches, locations = {}, set()
    for entry in entries:
        if not isinstance(entry, dict) or not {'name', 'host', 'repo_root'} <= set(entry):
            raise ValueError('vm-config:branch requires name, host and repo_root')
        name = entry['name']
        if (not isinstance(name, str) or not name or name.startswith(('-', '/'))
                or name.endswith(('/', '.')) or any(c.isspace() or ord(c) < 32 for c in name)
                or any(c in name for c in '~^:?*[\\') or '..' in name or '@{' in name
                or any(part.startswith('.') or part.endswith('.lock') or not part
                       for part in name.split('/')) or name == '@'):
            raise ValueError('vm-config:invalid branch name')
        host = entry['host']
        if not isinstance(host, str) or host not in hosts:
            raise ValueError('vm-config:branch needs a configured host')
        path = absolute_path(entry['repo_root'], 'branch repo_root')
        location = (host, str(path))
        if name in branches or location in locations:
            raise ValueError('vm-config:duplicate branch or host checkout')
        branches[name] = dict(entry)
        locations.add(location)
    return branches


def host_registry(document):
    """Validate tracked host metadata without contacting any host.

    Older single-host registries remain readable for retained archives/fixtures.
    SSH aliases resolve privately through the caller's OpenSSH configuration.
    """
    if 'hosts' not in document:
        entries = [dict(name='local', enabled='true', transport='local',
                        concurrency=document.get('concurrency', 1),
                        **({'backup_root': document['backup_root']} if 'backup_root' in document else {}))]
    else:
        if 'concurrency' in document or 'backup_root' in document:
            raise ValueError('vm-config:concurrency and backup_root belong to hosts')
        entries = document['hosts']
    if not isinstance(entries, list) or not entries:
        raise ValueError('vm-config:hosts must be a nonempty array')
    hosts = {}
    for entry in entries:
        if (not isinstance(entry, dict) or
                not {'name', 'enabled', 'transport', 'concurrency'} <= set(entry)):
            raise ValueError('vm-config:host fields')
        name = validate_name(entry['name'])
        if name in hosts:
            raise ValueError('vm-config:duplicate-host')
        if entry['enabled'] not in ('true', 'false'):
            raise ValueError('vm-config:host enabled must be the string true or false')
        concurrency = entry['concurrency']
        if type(concurrency) is not int or concurrency < 1:
            raise ValueError('vm-config:host concurrency must be a positive integer')
        transport = entry['transport']
        port = entry.get('ssh_port', 22)
        if transport not in ('local', 'ssh'):
            raise ValueError('vm-config:host transport must be local or ssh')
        if type(port) is not int or not 1 <= port <= 65535:
            raise ValueError('vm-config:ssh_port must be an integer between 1 and 65535')
        if transport == 'local' and 'ssh_port' in entry:
            raise ValueError('vm-config:local host cannot have ssh_port')
        root = absolute_path(entry['backup_root'], 'backup_root') if 'backup_root' in entry else None
        if 'virt-manager' in entry:
            absolute_path(entry['virt-manager'], 'virt-manager')
        hosts[name] = HostConfig(name, entry['enabled'] == 'true', transport, concurrency, root, port)
    if sum(host.transport == 'local' for host in hosts.values()) > 1:
        raise ValueError('vm-config:only one local host is allowed')
    return hosts


def require_available(vm):
    if not vm.host.enabled:
        raise ValueError(f'vm-config:host {vm.host.name} is offline (VM {vm.name})')
    if not vm.enabled:
        raise ValueError(f'vm-config:VM {vm.name} is offline (enabled is false)')
    return vm


def require_online(vm):
    return require_local(require_available(vm))


def require_local(vm):
    if vm.host.transport != 'local':
        raise ValueError(f'vm-config:SSH host execution is not implemented: {vm.host.name}; '
                         'refusing local VM access')
    return vm


def fixture_targets(path=None):
    """Adapt directory recipes to the existing finite fixture builder targets."""
    targets = {}
    for vm in registry(path).values():
        root = FIXTURE_ROOT.resolve()
        directory = (root / vm.fixture_path).resolve()
        if not directory.is_relative_to(root) or not directory.is_dir():
            raise ValueError('vm-config:fixture_path must name a directory under tests/fixtures')
        while True:
            recipe = directory / 'recipe.json'
            if recipe.exists():
                if not recipe.resolve().is_relative_to(root):
                    raise ValueError('vm-config:fixture recipe escapes tests/fixtures')
                try:
                    document = json.loads(recipe.read_text(encoding='utf-8'),
                                          object_pairs_hook=unique_keys)
                except (OSError, UnicodeError, json.JSONDecodeError) as error:
                    raise ValueError('vm-config:unreadable fixture recipe') from error
                if (not isinstance(document, dict) or set(document) != {'target'} or
                        document['target'] not in ('ubuntu', 'fedora')):
                    raise ValueError('vm-config:fixture recipe target must be ubuntu or fedora')
                targets[vm.name] = document['target']
                break
            if directory == root:
                raise ValueError('vm-config:fixture_path has no recipe.json')
            directory = directory.parent
    return targets


def validate_family(document):
    if (not isinstance(document, dict) or
            not {'family', 'package_format', 'fixture_path', 'vms'} <= set(document) or
            not isinstance(document['vms'], list)):
        raise ValueError('vm-config:family fields')
    family = document['family']
    if 'iso' in document:
        pattern = document['iso']
        if (not isinstance(pattern, str) or not pattern.endswith('.iso') or
                '/' in pattern or '\\' in pattern or
                any(ord(char) < 32 for char in pattern)):
            raise ValueError('vm-config:iso must be an ISO filename pattern without directories')
    if not isinstance(family, str) or not family.strip() or any(ord(char) < 32 for char in family):
        raise ValueError('vm-config:family must be a nonempty literal string')
    if document['package_format'] not in ('deb', 'rpm'):
        raise ValueError('vm-config:package_format must explicitly be deb or rpm')
    value = document['fixture_path']
    if (not isinstance(value, str) or not value or value.startswith('/') or
            any(ord(char) < 32 for char in value) or
            any(part in {'', '.', '..'} for part in value.split('/'))):
        raise ValueError('vm-config:fixture_path; use a relative directory without traversal')
    return document


def absolute_path(value, field):
    if (not isinstance(value, str) or not value.startswith('/') or value == '/' or
            any(ord(char) < 32 for char in value) or
            any(part in {'', '.', '..'} for part in value.split('/')[1:])):
        raise ValueError(f'vm-config:{field}; use an absolute path without traversal')
    return Path(value)


def backup_root(path=None, *, vm=None):
    hosts = host_registry(read_document(path, validate_agent=False))
    host = hosts[vm.host.name] if vm is not None else next(
        (host for host in hosts.values() if host.transport == 'local'), None)
    if host is None or host.backup_root is None:
        raise ValueError('vm-config:backup_root is required for VM backup/restore')
    return host.backup_root


def configuration(path=None):
    document = read_document(path, validate_agent=False)
    hosts = host_registry(document)
    concurrency = sum(host.concurrency for host in hosts.values() if host.enabled)
    result = {}
    anchors = set()
    ids = set()
    families = set()
    for family in document['families']:
        validate_family(family)
        if family['family'] in families:
            raise ValueError('vm-config:duplicate-family')
        families.add(family['family'])
        for entry in family['vms']:
            configured = validate_entry(entry, family, hosts, explicit_hosts='hosts' in document)
            anchor = (configured.host.name, configured.disk_anchor)
            if configured.name in result or anchor in anchors:
                raise ValueError('vm-config:duplicate-vm-or-disk')
            result[configured.name] = configured
            anchors.add(anchor)
            if configured.id is not None:
                if configured.id in ids:
                    raise ValueError('vm-config:duplicate-id')
                ids.add(configured.id)
    for vm in result.values():
        if vm.id in result and result[vm.id] != vm:
            raise ValueError('vm-config:ambiguous-id-or-name')
    return concurrency, result


def registry(path=None):
    return configuration(path)[1]


def resolve(name, configured):
    """Resolve a selector against this read of the registry, never a cached map."""
    if name is None:
        raise ValueError('vm-config: --vm NAME_OR_ID is required')
    validate_name(name)
    for vm in configured.values():
        if name == vm.name or name == vm.id:
            return vm
    raise ValueError('vm-config:unknown-vm; choose a name or id in config/environment.json')


def execution(name=None, path=None):
    """Only VMs whose own flag and host flag are true may be acquired."""
    _, configured = configuration(path)
    branch = current_branch() if any(vm.owning_branch for vm in configured.values()) else None
    if name is None or name in ('all-enabled', 'all'):
        vms = tuple(vm for vm in configured.values()
                    if vm.host.enabled and vm.enabled and (not vm.owning_branch or vm.owning_branch == branch))
    else:
        # Resolve the whole request before work, deduplicating aliases in order.
        vms = tuple({vm.name: vm for vm in
                     (resolve(value, configured) for value in name.split(','))}.values())
        vms = tuple(vm for vm in vms if vm.enabled and vm.host.enabled)
        for vm in vms:
            require_branch(vm, branch)
    if not vms:
        raise ValueError('vm-config:no online enabled VMs available for this selection/branch in config/environment.json')
    for vm in vms:
        require_online(vm)
    # Only the single local host can execute today. Offline/unselected host
    # capacity must not increase its worker limit.
    return min(vms[0].host.concurrency, len(vms)), vms


def current_branch():
    """Read this checkout's branch; detached HEAD or unavailable Git matches none."""
    # Privileged backup/restore helpers must read Git as their authenticated
    # caller, retaining Git's ownership check for a user-owned checkout.
    caller = int(os.environ.get('PKEXEC_UID', '0')) if os.geteuid() == 0 else 0
    try:
        result = subprocess.run(['git', 'symbolic-ref', '--quiet', 'HEAD'], cwd=ROOT,
                                capture_output=True, text=True, check=False,
                                **({'user': caller} if caller > 0 else {}))
    except OSError:
        return None
    ref = result.stdout.strip()
    if not result.returncode and ref.startswith('refs/heads/'):
        return ref.removeprefix('refs/heads/')
    return None


def require_branch(vm, branch):
    if vm.owning_branch and vm.owning_branch != branch:
        raise ValueError(f'vm-config:VM {vm.name} is reserved for branch {vm.owning_branch!r}; '
                         f'current branch is {branch!r}')


def validate_entry(document, family, hosts=None, *, explicit_hosts=False):
    if (not isinstance(document, dict) or
            not {'name', 'disk_anchor'} <= set(document)):
        raise ValueError('vm-config:fields')
    name = validate_name(document['name'])
    hosts = {'local': HostConfig()} if hosts is None else hosts
    host_name = document.get('host', None if explicit_hosts else 'local')
    if not isinstance(host_name, str) or host_name not in hosts:
        raise ValueError('vm-config:VM host must name a configured host')
    value = document['disk_anchor']
    absolute_path(value, 'disk-anchor')
    enabled = document.get('enabled', 'false')
    if enabled not in ('true', 'false'):
        raise ValueError('vm-config:enabled must be the string true or false')
    owning_branch = document.get('owning_branch', '')
    if (not isinstance(owning_branch, str)
            or any(char.isspace() or ord(char) < 32 for char in owning_branch)):
        raise ValueError('vm-config:owning_branch must be an empty string or a branch name')
    identifier = document.get('id')
    if 'id' in document:
        if type(identifier) is int:
            identifier = str(identifier)
        if not isinstance(identifier, str) or not re.fullmatch(r'[1-9][0-9]*', identifier):
            raise ValueError('vm-config:id must be a positive decimal integer or string')
    return VMConfig(name, Path(value), enabled == 'true', identifier,
                    family['package_format'], family['family'], family['fixture_path'], owning_branch,
                    hosts[host_name])


def load(name=None, path=None):
    # Availability gates new work, never metadata needed for owned cleanup.
    return require_local(resolve(name, registry(path)))


def selected(*, required=True):
    name = os.environ.get(VARIABLE)
    if name is None and not required:
        return None
    return load(name)


def select(name, path=None):
    """Bind this controller and its imported adapters to an explicit selection."""
    configured = load(name, path)
    os.environ[VARIABLE] = configured.name
    guest = sys.modules.get('prepare_vm')
    if guest is not None:
        guest.VM, guest.HOSTNAME = configured, configured.hostname
    baseline = sys.modules.get('prepare_baseline')
    if baseline is not None:
        baseline.DOMAIN = configured.name
        baseline.ANCHOR = configured.disk_anchor
        baseline.BASELINES = configured.baseline_directory
    return configured


def arguments():
    return ['--vm', selected().name]


def extract_selector(argv):
    """Consume the optional selector without changing single-VM consumers."""
    remaining, names = [], []
    iterator = iter(argv)
    for value in iterator:
        if value == '--':
            # Guest command arguments belong to the guest, including --vm and
            # --help. Never reinterpret them as host VM selection options.
            remaining.extend((value, *iterator))
            break
        elif value == '--vm':
            names.append(next(iterator, None))
        elif value.startswith('--vm='):
            names.append(value.partition('=')[2])
        else:
            remaining.append(value)
    if len(names) > 1:
        raise ValueError('vm-config:duplicate --vm')
    if names and (not names[0] or names[0].startswith('--')):
        raise ValueError('vm-config: --vm requires a value')
    return remaining, names[0] if names else None


def extract(argv, *, required=True, path=None):
    """Consume one --vm name or ID and bind its canonical name."""
    remaining, name = extract_selector(argv)
    controls = remaining[:remaining.index('--')] if '--' in remaining else remaining
    if name is None and (not required or any(value in ('--help', '-h') for value in controls)):
        return remaining, None
    configured = select(name, path)
    return remaining, configured


def guest_command_arguments(argv):
    """Parse only host controls before the explicit guest argument boundary."""
    if '--' not in argv:
        raise ValueError('vm-probe: use exec [--timeout SECONDS] -- COMMAND [ARG ...]')
    boundary = argv.index('--')
    parser = argparse.ArgumentParser(add_help=False, allow_abbrev=False)
    parser.add_argument('--timeout', type=int, default=120)
    parser.add_argument('--stdin', action='store_true')
    try:
        options = parser.parse_args(argv[:boundary])
    except SystemExit as error:
        raise ValueError('vm-probe: invalid host options') from error
    command = argv[boundary + 1:]
    if (not 1 <= options.timeout <= 86400 or not command or
            not command[0] or command[0].startswith('-') or
            any('\0' in arg for arg in command)):
        raise ValueError('vm-probe: invalid timeout or guest command')
    return options.timeout, command, options.stdin
