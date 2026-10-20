"""Private preparation-plan inputs shared by kiosk component probes."""
from copy import deepcopy
import hashlib
import os
from pathlib import Path

import pytest

from tools import kiosk_confinement as preparation, kiosk_view_receipt as receipt


def identity(path):
    s = path.lstat()
    return [s.st_dev, s.st_ino, s.st_size, s.st_mtime_ns, s.st_ctime_ns,
            s.st_mode, s.st_uid, s.st_gid]


@pytest.fixture
def initial_case(material_case):
    case = material_case
    host = case['directory'] / 'host'
    host.mkdir(mode=0o755)
    for path, body in case['files'].items():
        target = host / path.lstrip('/')
        target.parent.mkdir(mode=0o755, parents=True, exist_ok=True)
        for p in target.parents:
            if p == host:
                break
            p.chmod(0o755)
        target.write_bytes(body)
        target.chmod(0o755 if path in ('/usr/bin/tool', '/usr/bin/script') else 0o644)
    parent = case['directory'] / 'copies'
    parent.mkdir(mode=0o700)
    scratch = parent / ('.runtime-' + 'a' * 32)
    scratch.mkdir(mode=0o700)
    runtime = sorted([*deepcopy(case['record']['runtime']),
                      *(dict(row, kind='file', role='asset') for row in case['record']['payload'])],
                     key=lambda r: r['path'])
    native_copies, runtime_copies = [], []
    for group, records in ((native_copies, case['record']['native']), (runtime_copies, runtime)):
        for index, record in enumerate(records):
            name = ('native-' if group is native_copies else '') + str(index)
            target = scratch / name
            target.write_bytes(case['files'][record['path']])
            target.chmod(record['mode'])
            group.append(dict(index=index, name=name, identity=identity(target)))
    manifest = dict(format=1, backend='apparmor', records=runtime, copies=runtime_copies)
    manifest_bytes = preparation.runtime_canonical(manifest)
    (scratch / 'runtime.json').write_bytes(manifest_bytes)
    (scratch / 'runtime.json').chmod(0o600)
    fd = os.open(scratch, os.O_RDONLY | os.O_DIRECTORY)
    try:
        mount = next(line.split()[1] for line in Path(f'/proc/self/fdinfo/{fd}').read_text().splitlines()
                     if line.startswith('mnt_id:'))
    finally:
        os.close(fd)
    runtime_receipt = dict(manifest, root=identity(scratch)[:2], mount=mount,
        manifest=hashlib.sha256(manifest_bytes).hexdigest(), manifest_identity=identity(scratch / 'runtime.json'))
    layout = [dict(path=path, kind='tree' if kind == 'directory' else kind)
              for kind, path, link in case['record']['proofs'] if path.startswith('/usr/')]
    native_map = {r['path']: (i, r, native_copies[i]) for i, r in enumerate(case['record']['native'])}
    runtime_map = {r['path']: (i, r, runtime_copies[i]) for i, r in enumerate(runtime)}
    sources = {}
    for slot, row in enumerate([dict(path='/usr', kind='tree'), *layout]):
        path = row['path']
        source = dict(kind=row['kind'], required=True, source_index=slot, source_class='skeleton')
        if row['kind'] == 'file':
            index, record, copied = (native_map if path in native_map else runtime_map)[path]
            source.update(source_class='native' if path in native_map else
                          'runtime' if path == '/usr/bin/script' else 'payload', index=index,
                          assertion=identity(host / path.lstrip('/')), record=deepcopy(record),
                          name=copied['name'], copy_identity=copied['identity'])
            if path in native_map:
                source['path'] = path
        sources[path] = source
    plan = dict(format=1, backend='apparmor', material=receipt.material_digest(case['record']),
                layout=layout, sources=sources, runtime=runtime_receipt, proofs=case['record']['proofs'],
                native=dict(records=case['record']['native'], copies=native_copies))
    ticket = dict(format=1, name=scratch.name, root=identity(scratch)[:2], parent=identity(parent)[:2],
                  members={p.name: identity(p)[:2] for p in scratch.iterdir()})
    case.update(host=host, scratch=scratch, result=dict(format=1, role='manager', backend='apparmor',
        material=plan['material'], source='-', plan=plan, ticket=ticket))
    return case

