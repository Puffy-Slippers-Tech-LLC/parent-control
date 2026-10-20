"""Independent material records for private kiosk component probes."""
import hashlib
import json
from pathlib import Path

import pytest


PAYLOAD = '/usr/share/oh-no-parent-control/confinement'


def _hash(data):
    return hashlib.sha256(data).hexdigest()


def proofs(files, links=()):
    members = {'/': ('directory', '-')}
    for path in files:
        for parent in Path(path).parents:
            members[str(parent)] = ('directory', '-')
        members[path] = ('file', '-')
    for path, target in links:
        for parent in Path(path).parents:
            members[str(parent)] = ('directory', '-')
        members[path] = ('link', target)
    return [[kind, path, target] for path, (kind, target) in sorted(members.items())]


@pytest.fixture
def material_case(tmp_path):
    config = dict(backend='apparmor', domains=['manager'],
                  executables=[dict(role='manager', paths=['/usr/bin/tool'], optional=False)],
                  preserved_executables=[], reserved_directories=[],
                  runtime_inputs={'/usr/bin/script': dict(kind='file', role='script')})
    config_bytes = json.dumps(config, indent=2).encode() + b'\n'
    policy_bytes, native_bytes, script_bytes = b'trusted policy\n', b'\x7fELF independent native\n', b'#!/usr/bin/python3\n'
    record = dict(format=1, backend='apparmor', config=_hash(config_bytes), policy=_hash(policy_bytes),
                  native=[dict(role='manager', path='/usr/bin/tool', sha256=_hash(native_bytes),
                               size=len(native_bytes), source_label=None, mode=0o755, label=None)],
                  preserved=[], runtime=[dict(path='/usr/bin/script', kind='file', role='script',
                       sha256=_hash(script_bytes), size=len(script_bytes), mode=0o755, label=None)],
                  payload=[dict(path=PAYLOAD + '/config.json', sha256=_hash(config_bytes),
                                size=len(config_bytes), mode=0o644, label=None),
                           dict(path=PAYLOAD + '/onpc-kiosk.apparmor', sha256=_hash(policy_bytes),
                                size=len(policy_bytes), mode=0o644, label=None)])
    files = {'/usr/bin/tool': native_bytes, '/usr/bin/script': script_bytes,
             PAYLOAD + '/config.json': config_bytes, PAYLOAD + '/onpc-kiosk.apparmor': policy_bytes}
    record['proofs'] = proofs(files)
    return dict(record=record, config=config, config_bytes=config_bytes, policy_bytes=policy_bytes,
                files=files, directory=tmp_path)
