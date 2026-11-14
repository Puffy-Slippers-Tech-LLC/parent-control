"""Shared VM configuration: validate known fields and ignore unknown attributes.

Loading never accesses libvirt or VM disks.
"""

from dataclasses import dataclass
import argparse
import json
import math
import os
from pathlib import Path
import re
import stat
import subprocess
import sys


CONFIG = Path(__file__).resolve().parents[2] / 'config/environment.json'
FIXTURE_ROOT = Path(__file__).resolve().parents[1] / 'fixtures'
URI = 'qemu:///system'
STATE_ROOT = Path('/Data/virt-manager/oh-no-parent-control-baseline-state')
VARIABLE = 'ONPC_TEST_VM'
ROOT = Path(__file__).resolve().parents[2]
HOST_IDENTITY = Path('/usr/local/libexec/onpc-vm-host')


@dataclass(frozen=True)
class HostConfig:
    name: str = 'local'
    enabled: bool = True
    transport: str = 'local'
    max_compute_unit: float = 1
    backup_root: Path | None = None
    ssh_port: int | None = None
    disk_concurrency: int = 1


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
    compute_unit: float = 1
    vm_tags: frozenset[str] = frozenset()

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
                        max_compute_unit=document.get('max_compute_unit', document.get('concurrency', 1)),
                        **({'backup_root': document['backup_root']} if 'backup_root' in document else {}))]
    else:
        if any(key in document for key in ('concurrency', 'max_compute_unit', 'backup_root')):
            raise ValueError('vm-config:max_compute_unit and backup_root belong to hosts')
        entries = document['hosts']
    if not isinstance(entries, list) or not entries:
        raise ValueError('vm-config:hosts must be a nonempty array')
    hosts = {}
    for entry in entries:
        if (not isinstance(entry, dict) or
                not {'name', 'enabled', 'transport', 'max_compute_unit'} <= set(entry)):
            raise ValueError('vm-config:host fields')
        name = validate_name(entry['name'])
        if name in hosts:
            raise ValueError('vm-config:duplicate-host')
        if entry['enabled'] not in ('true', 'false'):
            raise ValueError('vm-config:host enabled must be the string true or false')
        compute = compute_unit(entry['max_compute_unit'], 'host max_compute_unit')
        disk_concurrency = entry.get('disk_concurrency', 1)
        if type(disk_concurrency) is not int or disk_concurrency < 1:
            raise ValueError('vm-config:host disk_concurrency must be a positive integer')
        transport = entry['transport']
        port = entry.get('ssh_port')
        if transport not in ('local', 'ssh'):
            raise ValueError('vm-config:host transport must be local or ssh')
        if 'ssh_port' in entry and (type(port) is not int or not 1 <= port <= 65535):
            raise ValueError('vm-config:ssh_port must be an integer between 1 and 65535')
        root = absolute_path(entry['backup_root'], 'backup_root') if 'backup_root' in entry else None
        if 'virt-manager' in entry:
            absolute_path(entry['virt-manager'], 'virt-manager')
        hosts[name] = HostConfig(name, entry['enabled'] == 'true', transport, compute, root, port,
                                 disk_concurrency)
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
    vm = require_available(vm)
    return require_local(vm) if os.geteuid() == 0 else vm


def require_local(vm, path=None):
    if vm.host.name != execution_host(path):
        raise ValueError(f'vm-config:VM belongs to another host: {vm.host.name}; '
                         'refusing local VM access')
    return vm


def installed_host():
    """Only setup's root-owned assignment may identify a nonlocal VM host."""
    try:
        info = HOST_IDENTITY.lstat()
    except FileNotFoundError:
        return None
    if (not stat.S_ISREG(info.st_mode) or info.st_uid != 0
            or info.st_mode & 0o022 or info.st_size > 64):
        raise ValueError('vm-config:unsafe installed VM host identity; repair through ./setup.sh')
    value = HOST_IDENTITY.read_text(encoding='ascii')
    name = validate_name(value.removesuffix('\n'))
    if value != name + '\n':
        raise ValueError('vm-config:invalid installed VM host identity')
    return name


def execution_host(path=None):
    """Identify the VM backend's physical host, independently of source branch."""
    document = read_document(path, validate_agent=False)
    hosts = host_registry(document)
    branches = branch_registry(document)
    installed = installed_host()
    origin = remote_origin()
    if origin is not None:
        storage = branches.get(origin['storage_branch'])
        if (origin['branch'] not in branches or storage is None
                or storage['host'] != origin['host']
                or storage['repo_root'] != origin['storage_root']):
            raise ValueError('vm-config:remote source placement differs from controller registry')
        if installed is not None and installed != origin['host']:
            raise ValueError('vm-config:refusing local VM access; transferred destination '
                             'differs from installed VM host')
        return origin['host']
    if installed is not None:
        if installed not in hosts:
            raise ValueError('vm-config:installed VM host is absent from config/environment.json')
        return installed
    # Historical hosts without an installed assignment retain their workstation
    # identity. Public dispatch resolves branch placement separately.
    return next((host.name for host in hosts.values()
                 if host.transport == 'local'), None)


def remote_origin():
    """Read the private placement receipt in a transferred source directory.

    Installed helpers have already authenticated the caller and validated the
    source root. This is source metadata, never a replacement for VM UUID pins,
    checkout receipts, journal identity or the caller's Polkit authorization.
    """
    path = ROOT / '.onpc-remote-source.json'
    try:
        descriptor = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    except FileNotFoundError:
        return None
    with os.fdopen(descriptor) as stream:
        info = os.fstat(stream.fileno())
        caller = int(os.environ.get('PKEXEC_UID', str(os.geteuid())))
        if (not stat.S_ISREG(info.st_mode) or info.st_nlink != 1 or info.st_size > 4096
                or info.st_uid != caller or stat.S_IMODE(info.st_mode) != 0o400):
            raise ValueError('vm-config:unsafe remote source receipt')
        value = json.load(stream)
    required = {'branch', 'host', 'storage_branch', 'storage_root'}
    if (not isinstance(value, dict) or not required <= set(value)
            or set(value) - required - {'controller_root', 'source_identity',
                                        'package_revision', 'package_epoch'}
            or any(not isinstance(value[key], str) or not value[key] for key in required)):
        raise ValueError('vm-config:invalid remote source receipt')
    if 'controller_root' in value:
        absolute_path(value['controller_root'], 'remote controller root')
    if 'source_identity' in value:
        source = value['source_identity']
        if (not isinstance(source, dict) or set(source) != {'digest', 'generation'}
                or not isinstance(source['digest'], str)
                or re.fullmatch('[0-9a-f]{64}', source['digest']) is None
                or type(source['generation']) is not int or source['generation'] < 0):
            raise ValueError('vm-config:invalid remote source identity')
    if 'package_revision' in value or 'package_epoch' in value:
        if (not isinstance(value.get('package_revision'), str)
                or re.fullmatch('[0-9a-f]{40,64}', value['package_revision']) is None
                or type(value.get('package_epoch')) is not int or value['package_epoch'] < 0):
            raise ValueError('vm-config:invalid remote package metadata')
    return value


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
            not {'family', 'package_format', 'fixture_path', 'vm_tags', 'vms'} <= set(document) or
            not isinstance(document['vms'], list)):
        raise ValueError('vm-config:family fields')
    parse_vm_tags(document['vm_tags'])
    compute_unit(document.get('compute_unit', 1), 'family compute_unit')
    if 'iso' in document:
        pattern = document['iso']
        if (not isinstance(pattern, str) or not pattern.endswith('.iso') or
                '/' in pattern or '\\' in pattern or
                any(ord(char) < 32 for char in pattern)):
            raise ValueError('vm-config:iso must be an ISO filename pattern without directories')
    for field in ('family', 'id'):
        if field not in document:
            continue
        value = document[field]
        if (not isinstance(value, str) or not value or value.startswith('-') or value != value.strip()
                or ',' in value or any(ord(char) < 32 for char in value)):
            raise ValueError(f'vm-config:family {field} must be a nonempty selector '
                             'without leading hyphens, commas or surrounding whitespace')
    if document['package_format'] not in ('deb', 'rpm'):
        raise ValueError('vm-config:package_format must explicitly be deb or rpm')
    value = document['fixture_path']
    if (not isinstance(value, str) or not value or value.startswith('/') or
            any(ord(char) < 32 for char in value) or
            any(part in {'', '.', '..'} for part in value.split('/'))):
        raise ValueError('vm-config:fixture_path; use a relative directory without traversal')
    return document


def parse_vm_tags(value):
    """Parse exact routing tokens; an explicit VM value replaces family tags."""
    if not isinstance(value, str):
        raise ValueError('vm-config:vm_tags must be a nonempty comma-separated string')
    tags = [tag.strip() for tag in value.split(',')]
    if (any(not re.fullmatch(r'[a-z0-9]+(?:-[a-z0-9]+)*', tag) for tag in tags)
            or len(tags) != len(set(tags))):
        raise ValueError('vm-config:vm_tags must contain unique nonempty tag tokens')
    return frozenset(tags)


def compute_unit(value, field='compute_unit'):
    if (type(value) not in (int, float) or value <= 0
            or type(value) is float and not math.isfinite(value)):
        raise ValueError(f'vm-config:{field} must be a positive finite number')
    return value


def absolute_path(value, field):
    if (not isinstance(value, str) or not value.startswith('/') or value == '/' or
            any(ord(char) < 32 for char in value) or
            any(part in {'', '.', '..'} for part in value.split('/')[1:])):
        raise ValueError(f'vm-config:{field}; use an absolute path without traversal')
    return Path(value)


def backup_root(path=None, *, vm=None):
    hosts = host_registry(read_document(path, validate_agent=False))
    host = hosts[vm.host.name] if vm is not None else hosts.get(execution_host(path))
    if host is None or host.backup_root is None:
        raise ValueError('vm-config:backup_root is required for VM backup/restore')
    return host.backup_root


def configuration(path=None):
    return parse_configuration(read_document(path, validate_agent=False))


def parse_configuration(document):
    """Validate VM identities together in the shared selector namespace."""
    hosts = host_registry(document)
    result = {}
    anchors = set()
    ids = set()
    families = set()
    family_ids = set()
    for family in document['families']:
        validate_family(family)
        if family['family'] in families:
            raise ValueError('vm-config:duplicate-family')
        families.add(family['family'])
        if 'id' in family:
            if family['id'] in family_ids:
                raise ValueError('vm-config:duplicate-family-id')
            family_ids.add(family['id'])
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
    selectors = [value.casefold() for value in (*result, *ids, *families, *family_ids)]
    if len(selectors) != len(set(selectors)):
        raise ValueError('vm-config:ambiguous-id-name-or-family; '
                         'VM IDs, VM names, family IDs and family names must be unique ignoring case')
    if {'all', 'all-enabled'} & set(selectors):
        raise ValueError('vm-config:VM names and family IDs/names cannot use reserved selectors all or all-enabled')
    return len([vm for vm in result.values() if vm.enabled and vm.host.enabled]), result


def registry(path=None):
    return configuration(path)[1]


def resolve(name, configured):
    """Resolve a selector against this read of the registry, never a cached map."""
    if name is None:
        raise ValueError('vm-config: --vm NAME_OR_ID is required')
    validate_name(name)
    selector = name.casefold()
    for vm in configured.values():
        if selector == vm.name.casefold() or selector == vm.id:
            return vm
    raise ValueError('vm-config:unknown-vm; choose a name or id in config/environment.json')


def family_selectors(document):
    """Index family names and optional IDs from a validated registry document."""
    return {family[field].casefold(): family
            for family in document['families']
            for field in ('family', 'id') if field in family}


def execution(name=None, path=None, *, remote=None):
    """Only VMs whose own flag and host flag are true may be acquired."""
    document = read_document(path, validate_agent=False)
    _, configured = parse_configuration(document)
    selectors = family_selectors(document)
    families = {family['family']: [] for family in document['families']}
    for vm in configured.values():
        families[vm.family].append(vm)
    branch = current_branch() if any(vm.owning_branch for vm in configured.values()) else None
    if name is None or name.casefold() in ('all-enabled', 'all'):
        vms = tuple(vm for vm in configured.values()
                    if vm.host.enabled and vm.enabled and (not vm.owning_branch or vm.owning_branch == branch))
    else:
        # Resolve the whole request before work, deduplicating aliases in order.
        selected = {}
        for value in name.split(','):
            value = value.casefold()
            if value in selectors:
                matches = (vm for vm in families[selectors[value]['family']]
                           if not vm.owning_branch or vm.owning_branch == branch)
            else:
                matches = (resolve(value, configured),)
            for vm in matches:
                if vm.enabled and vm.host.enabled:
                    require_branch(vm, branch)
                    selected[vm.name] = vm
        vms = tuple(selected.values())
    if not vms:
        raise ValueError('vm-config:no online enabled VMs available for this selection/branch in config/environment.json')
    for vm in vms:
        require_available(vm)
        if not (os.geteuid() != 0 if remote is None else remote):
            require_local(vm, path)
    return len(vms), vms


def snap_tests_enabled(path=None):
    """One switch for Snap preparation, baseline readiness and test selection."""
    value = read_document(path, validate_agent=False).get('snap_tests_enabled', True)
    if type(value) is not bool:
        raise ValueError('vm-config:snap_tests_enabled must be a boolean')
    return value


def current_branch():
    """Read this checkout's branch; detached HEAD or unavailable Git matches none."""
    # Privileged backup/restore helpers must read Git as their authenticated
    # caller, retaining Git's ownership check for a user-owned checkout.
    origin = remote_origin()
    if origin is not None:
        return origin['branch']
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
                    hosts[host_name], compute_unit(document.get('compute_unit', family.get('compute_unit', 1)),
                                                  'VM compute_unit'),
                    parse_vm_tags(document.get('vm_tags', family['vm_tags'])))


def load(name=None, path=None, *, local=None):
    # Availability gates new work, never metadata needed for owned cleanup.
    vm = resolve(name, registry(path))
    return require_local(vm, path) if (os.geteuid() == 0 if local is None else local) else vm


def selected(*, required=True, local=None):
    name = os.environ.get(VARIABLE)
    if name is None and not required:
        return None
    return load(name, **({'local': local} if local is not None else {}))


def select(name, path=None, *, local=None):
    """Bind this controller and its imported adapters to an explicit selection."""
    configured = load(name, path, **({'local': local} if local is not None else {}))
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


HOST_HELP = ('--host NAME[,NAME...] optionally limits the VM selection to those configured hosts '
             '(e.g. myserver or local,myserver); omitted: no host filter. Single-VM tools still '
             'require --vm. This does not change controller placement.')


def host_arguments(argv, *, single=False, path=None):
    """Intersect VM targets with a host list, preserving opaque command arguments.

    Single-target maintenance resolves metadata only: observations and owned
    recovery must remain possible after availability or branch flags change.
    Its existing caller remains responsible for admission and ownership checks.
    """
    remaining, hosts = [], []
    tokens = iter(argv)
    for token in tokens:
        if token == '--':
            remaining.extend((token, *tokens))
            break
        if token == '--host':
            hosts.append(next(tokens, None))
        elif token.startswith('--host='):
            hosts.append(token.partition('=')[2])
        else:
            remaining.append(token)
    if not hosts:
        return remaining
    if len(hosts) != 1:
        raise ValueError('vm-config:duplicate --host')
    host = hosts[0]
    if not host or host.startswith('-'):
        raise ValueError('vm-config: --host requires a value')
    controls = remaining[:remaining.index('--')] if '--' in remaining else remaining
    if any(option in controls for option in ('--help', '-h')):
        return remaining
    if '--host-only' in controls:
        raise ValueError('vm-config: --host cannot be combined with --host-only')
    host_names = set(host.split(','))
    if not host_names <= host_registry(read_document(path, validate_agent=False)).keys():
        raise ValueError('vm-config:unknown host; choose a host name in config/environment.json')
    insertion = next((index for index, value in enumerate(controls)
                      if value == '--vm' or value.startswith('--vm=')), None)
    remaining, selector = extract_selector(remaining)
    vms = (load(selector, path, local=False),) if single else execution(selector, path)[1]
    names = [vm.name for vm in vms if vm.host.name in host_names]
    if not names:
        raise ValueError(f'vm-config:no selected VMs on host {host}')
    boundary = remaining.index('--') if '--' in remaining else len(remaining)
    # Keep an explicit selector in place, before argparse REMAINDER commands
    # and after any subcommand that owns the --vm option.
    insertion = boundary if insertion is None else insertion
    return [*remaining[:insertion], '--vm', ','.join(names), *remaining[insertion:]]


def add_host_argument(parser):
    parser.add_argument('--host', metavar='NAME', help=HOST_HELP)


def parse_vm_arguments(parser, argv=None, *, single=False):
    """Use the same host filter for argparse-based VM tools and their help."""
    add_host_argument(parser)
    try:
        argv = host_arguments(sys.argv[1:] if argv is None else argv, single=single)
    except ValueError as error:
        parser.error(str(error))
    return parser.parse_args(argv)


def extract(argv, *, required=True, path=None, local=None):
    """Consume one --vm name or ID and bind its canonical name."""
    remaining, name = extract_selector(host_arguments(argv, single=True, path=path))
    controls = remaining[:remaining.index('--')] if '--' in remaining else remaining
    if name is None and (not required or any(value in ('--help', '-h') for value in controls)):
        return remaining, None
    placement = {'local': local} if local is not None else {}
    if '--list' in controls:
        placement['local'] = False
    configured = select(name, path, **placement)
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
