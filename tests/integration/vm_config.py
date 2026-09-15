"""Shared test VM configuration; loading it never accesses libvirt or VM disks."""

from dataclasses import dataclass
import json
from pathlib import Path
import re


CONFIG = Path(__file__).resolve().parents[2] / 'config/test-vm.json'
URI = 'qemu:///system'
STATE_ROOT = Path('/Data/virt-manager/oh-no-parent-control-baseline-state')


@dataclass(frozen=True)
class VMConfig:
    name: str
    disk_anchor: Path

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


def load(path=CONFIG):
    try:
        document = json.loads(path.read_text(encoding='utf-8'), object_pairs_hook=unique_keys)
    except (OSError, UnicodeError, json.JSONDecodeError) as error:
        raise ValueError('vm-config:unreadable; check config/test-vm.json') from error
    if not isinstance(document, dict) or set(document) != {'name', 'disk_anchor'}:
        raise ValueError('vm-config:fields')
    name = document['name']
    # The configured domain name is also the prepared guest's static hostname.
    if (not isinstance(name, str) or len(name) > 63 or
            not all(re.fullmatch(r'[a-z0-9](?:[a-z0-9-]*[a-z0-9])?', label)
                    for label in name.split('.'))):
        raise ValueError('vm-config:name; use a valid lowercase hostname')
    value = document['disk_anchor']
    if (not isinstance(value, str) or not value.startswith('/') or
            any(ord(char) < 32 for char in value) or
            any(part in {'', '.', '..'} for part in value.split('/')[1:])):
        raise ValueError('vm-config:disk-anchor; use an absolute image path without traversal')
    return VMConfig(name, Path(value))
