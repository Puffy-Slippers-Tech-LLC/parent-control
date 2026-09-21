#!/usr/bin/python3
"""Remove explicitly inventoried legacy qualification allocations, never a sweep.

The developer supplies artifacts/tmp-storage-cleanup.json after reviewing the
read-only check_tmp_storage inventory. All entries are audited before deletion.
"""

import hashlib
import json
import os
from pathlib import Path
import re
import runpy
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from tools import test_retention as retention


def cleanup(records, guard):
    if not isinstance(records, list) or not records or len(records) > 256:
        raise ValueError('cleanup: invalid inventory')
    paths = set()
    for record in records:
        if (not isinstance(record, dict) or set(record) != {'path', 'device', 'inode', 'mode'}
                or not isinstance(record['path'], str)
                or re.fullmatch(r'/tmp/onpc-(?:graphical-smoke|e2e-evidence|e2e-watch-check|system-recovery)-[a-z0-9_]{8}', record['path']) is None
                or record['mode'] != 0o700
                or any(type(record[key]) is not int or record[key] < 0
                       for key in ('device', 'inode', 'mode'))
                or record['path'] in paths):
            raise ValueError('cleanup: invalid allocation')
        paths.add(record['path'])
    guard(paths)
    for record in records:
        retention.remove(record, validate_only=True)
    for record in records:
        retention.remove(record)
        print('Removed ' + record['path'], flush=True)


def unused(paths):
    """Refuse references by live processes; never signal or stop a process."""
    def selected(value):
        return any(value == path or value.startswith(path + '/') for path in paths)
    for process in Path('/proc').iterdir():
        if not process.name.isdecimal():
            continue
        try:
            links = [process / 'cwd', process / 'root', *(process / 'fd').iterdir()]
            for link in links:
                try:
                    value = os.readlink(link).removesuffix(' (deleted)')
                except FileNotFoundError:
                    continue
                if selected(value):
                    raise ValueError('cleanup: allocation has a live process reference')
            if any(selected(arg) for arg in (process / 'cmdline').read_bytes().decode(
                    'utf-8', errors='replace').split('\0')):
                raise ValueError('cleanup: allocation has a live command reference')
        except (FileNotFoundError, ProcessLookupError):
            continue


def main():
    uid = int(os.environ.get('PKEXEC_UID', '0'))
    if len(sys.argv) != 1 or os.geteuid() != 0 or uid <= 0 or Path.cwd() != ROOT:
        raise ValueError('cleanup: authenticated dispatcher required')
    records = json.loads((ROOT / 'artifacts/tmp-storage-cleanup.json').read_text())
    checkout = hashlib.sha256(str(ROOT).encode()).hexdigest()[:16]
    store = retention.Store(Path('/var/tmp') / f'onpc-test-retention-root-{uid}-{checkout}')
    guard = runpy.run_path(str(ROOT / 'tools/onpc-test-runner'))['retention_guard']
    with store.opened() as fd, store.locked(fd, 'owner.lock', blocking=False):
        guard(ROOT)
        cleanup(records, unused)
    return 0


if __name__ == '__main__':
    sys.exit(main())
