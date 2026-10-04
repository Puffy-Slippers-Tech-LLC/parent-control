"""Shared test VM configuration; loading it never accesses libvirt or VM disks."""

from dataclasses import dataclass
import argparse
import json
import os
from pathlib import Path
import re
import sys


CONFIG = Path(__file__).resolve().parents[2] / 'config/test-vm.json'
URI = 'qemu:///system'
STATE_ROOT = Path('/Data/virt-manager/oh-no-parent-control-baseline-state')
VARIABLE = 'ONPC_TEST_VM'


@dataclass(frozen=True)
class VMConfig:
    name: str
    disk_anchor: Path
    enabled: bool = False
    id: str | None = None
    clipboard: bool = False

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


def configuration(path=None):
    path = CONFIG if path is None else path
    try:
        document = json.loads(path.read_text(encoding='utf-8'), object_pairs_hook=unique_keys)
    except (OSError, UnicodeError, json.JSONDecodeError) as error:
        raise ValueError('vm-config:unreadable; check config/test-vm.json') from error
    if (not isinstance(document, dict) or set(document) not in ({'vms'}, {'vms', 'concurrency'}) or
            not isinstance(document['vms'], list) or not document['vms']):
        raise ValueError('vm-config:fields')
    concurrency = document.get('concurrency', 1)
    if type(concurrency) is not int or concurrency < 1:
        raise ValueError('vm-config:concurrency must be a positive integer')
    result = {}
    anchors = set()
    ids = set()
    for entry in document['vms']:
        configured = validate_entry(entry)
        if configured.name in result or configured.disk_anchor in anchors:
            raise ValueError('vm-config:duplicate-vm-or-disk')
        result[configured.name] = configured
        anchors.add(configured.disk_anchor)
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
    raise ValueError('vm-config:unknown-vm; choose a name or id in config/test-vm.json')


def execution(name=None, path=None):
    """Resolve a finite queue; explicit selections also admit disabled entries."""
    concurrency, configured = configuration(path)
    if name is None or name == 'all-enabled':
        vms = tuple(vm for vm in configured.values() if vm.enabled)
    elif name == 'all':
        vms = tuple(configured.values())
    else:
        # Resolve the whole request before work, deduplicating aliases in order.
        vms = tuple({vm.name: vm for vm in
                     (resolve(value, configured) for value in name.split(','))}.values())
    if not vms:
        raise ValueError('vm-config:no enabled VMs in config/test-vm.json')
    return min(concurrency, len(vms)), vms


def validate_entry(document):
    if (not isinstance(document, dict) or
            not {'name', 'disk_anchor'} <= set(document) or
            not set(document) <= {'name', 'disk_anchor', 'enabled', 'id', 'clipboard'}):
        raise ValueError('vm-config:fields')
    name = validate_name(document['name'])
    value = document['disk_anchor']
    if (not isinstance(value, str) or not value.startswith('/') or
            any(ord(char) < 32 for char in value) or
            any(part in {'', '.', '..'} for part in value.split('/')[1:])):
        raise ValueError('vm-config:disk-anchor; use an absolute image path without traversal')
    enabled = document.get('enabled', 'false')
    if enabled not in ('true', 'false'):
        raise ValueError('vm-config:enabled must be the string true or false')
    clipboard = document.get('clipboard', 'false')
    if clipboard not in ('true', 'false'):
        raise ValueError('vm-config:clipboard must be the string true or false')
    identifier = document.get('id')
    if 'id' in document:
        if type(identifier) is int:
            identifier = str(identifier)
        if not isinstance(identifier, str) or not re.fullmatch(r'[1-9][0-9]*', identifier):
            raise ValueError('vm-config:id must be a positive decimal integer or string')
    return VMConfig(name, Path(value), enabled == 'true', identifier, clipboard == 'true')


def load(name=None, path=None):
    return resolve(name, registry(path))


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
