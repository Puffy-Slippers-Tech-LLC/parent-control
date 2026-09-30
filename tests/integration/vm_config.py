"""Shared test VM configuration; loading it never accesses libvirt or VM disks."""

from dataclasses import dataclass
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


def registry(path=CONFIG):
    try:
        document = json.loads(path.read_text(encoding='utf-8'), object_pairs_hook=unique_keys)
    except (OSError, UnicodeError, json.JSONDecodeError) as error:
        raise ValueError('vm-config:unreadable; check config/test-vm.json') from error
    if (not isinstance(document, dict) or set(document) != {'vms'} or
            not isinstance(document['vms'], list) or not document['vms']):
        raise ValueError('vm-config:fields')
    result = {}
    anchors = set()
    for entry in document['vms']:
        configured = validate_entry(entry)
        if configured.name in result or configured.disk_anchor in anchors:
            raise ValueError('vm-config:duplicate-vm-or-disk')
        result[configured.name] = configured
        anchors.add(configured.disk_anchor)
    return result


def validate_entry(document):
    if not isinstance(document, dict) or set(document) != {'name', 'disk_anchor'}:
        raise ValueError('vm-config:fields')
    name = validate_name(document['name'])
    value = document['disk_anchor']
    if (not isinstance(value, str) or not value.startswith('/') or
            any(ord(char) < 32 for char in value) or
            any(part in {'', '.', '..'} for part in value.split('/')[1:])):
        raise ValueError('vm-config:disk-anchor; use an absolute image path without traversal')
    return VMConfig(name, Path(value))


def load(name=None, path=CONFIG):
    if name is None:
        raise ValueError('vm-config: --vm NAME is required')
    validate_name(name)
    configured = registry(path)
    if name not in configured:
        raise ValueError('vm-config:unknown-vm; choose a name in config/test-vm.json')
    return configured[name]


def selected(*, required=True):
    name = os.environ.get(VARIABLE)
    if name is None and not required:
        return None
    return load(name)


def select(name, path=CONFIG):
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


def extract(argv, *, required=True, path=CONFIG):
    """Consume one literal --vm option, rejecting duplicates and unknown names."""
    remaining, names = [], []
    iterator = iter(argv)
    for value in iterator:
        if value == '--vm':
            names.append(next(iterator, None))
        elif value.startswith('--vm='):
            names.append(value.partition('=')[2])
        else:
            remaining.append(value)
    if len(names) > 1:
        raise ValueError('vm-config:duplicate --vm')
    if not names and (not required or any(value in ('--help', '-h') for value in remaining)):
        return remaining, None
    configured = select(names[0] if names else None, path)
    return remaining, configured
