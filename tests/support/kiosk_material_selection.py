"""Private retained-material selection fixtures shared by kiosk tests."""
import hashlib
import json
import os
from types import SimpleNamespace

import pytest

from tests.support.kiosk_material import private_store


@pytest.fixture
def material_scene(private_store, monkeypatch):
    fixture, helper = private_store, private_store.helper
    retained = fixture.store / 'manager'
    retained.mkdir(mode=0o755)
    required = {'/usr/bin/native': b'\x7fELFnative-original',
                '/usr/lib/helper': b'\x7fELFhelper-original',
                '/usr/bin/script': b'#!/usr/bin/python3\noriginal'}
    for path, data in required.items():
        for root in (fixture.host, retained):
            target = root / path.lstrip('/')
            target.parent.mkdir(mode=0o755, parents=True, exist_ok=True)
            target.write_bytes(data)
            target.chmod(0o755)
    for root in (fixture.host, retained):
        for path in root.rglob('*'):
            if path.is_dir():
                path.chmod(0o755)
    digest = lambda path: hashlib.sha256(required[path]).hexdigest()
    native = [dict(role='service', path='/usr/bin/native', sha256=digest('/usr/bin/native'))]
    preserved = [dict(path='/usr/lib/helper', sha256=digest('/usr/lib/helper'),
                      mode=0o755, uid=0, gid=0, label=None)]
    specs = {'/usr/bin/script': dict(kind='file', role='script')}
    proofs = [('directory', '/', '-'), ('directory', '/usr', '-'),
              ('directory', '/usr/bin', '-'), ('directory', '/usr/lib', '-'),
              *[('file', path, '-') for path in sorted(required)]]
    config = dict(backend='apparmor', executables=[], preserved_executables=[],
                  runtime_inputs=specs)
    config_bytes, policy_bytes = json.dumps(config, sort_keys=True).encode(), b'policy-original'
    attestation = ' '.join(hashlib.sha256(data).hexdigest()
                           for data in (config_bytes, policy_bytes)) + '\n'

    def measure():
        # This normalized projection is supplied by the receipt owner. These
        # selection tests separately stub current-host verification, while all
        # retained inode/content/trust observations remain real descriptor work.
        runtime, runtime_assertions = helper.measure_runtime_inputs(specs, 'apparmor')
        native_records = [dict(entry, size=len(required[entry['path']]), mode=0o755,
                               label=None) for entry in native]
        preserved_records = [dict(entry, size=len(required[entry['path']]))
                             for entry in preserved]
        record = dict(format=1, backend='apparmor',
                      config=hashlib.sha256(config_bytes).hexdigest(),
                      policy=hashlib.sha256(policy_bytes).hexdigest(),
                      native=native_records, preserved=preserved_records,
                      runtime=runtime, proofs=[list(proof) for proof in proofs])
        return dict(record=record, digest=helper.material_digest(record),
                    config=config, native=native_records, preserved=preserved_records,
                    runtime=runtime, proofs=record['proofs'], assertions={},
                    runtime_assertions=runtime_assertions)

    layout = [dict(path='/usr/bin', kind='tree'), dict(path='/usr/lib', kind='tree'),
              *[dict(path=path, kind='file') for path in sorted(required)]]
    pins = {}
    opened = []

    def pin(path, kind):
        flags = os.O_CLOEXEC | os.O_NOFOLLOW
        flags |= os.O_PATH if kind == 'link' else os.O_RDONLY
        if kind in ('tree', 'directory'):
            flags |= os.O_DIRECTORY
        fd = os.open(retained / path.lstrip('/'), flags)
        opened.append(fd)
        pins[path] = dict(fd=fd, identity=helper.file_identity(helper.os.fstat(fd))[:2])

    pin('/usr', 'tree')
    for entry in layout:
        pin(entry['path'], entry['kind'])
    scene = SimpleNamespace(fixture=fixture, helper=helper, retained=retained,
                            required=required, layout=layout, pins=pins, pin=pin,
                            measure=measure, proofs=proofs, config_bytes=config_bytes,
                            policy_bytes=policy_bytes, attestation=attestation)
    try:
        yield scene
    finally:
        for fd in opened:
            os.close(fd)


def selected_scene(scene, monkeypatch):
    snapshot = scene.measure()
    calls = []
    monkeypatch.setattr(scene.helper, 'verify_required_material', lambda value: calls.append(value))

    def select():
        result = scene.helper.select_retained_material(
            snapshot, snapshot['record'], scene.layout, scene.pins)
        assert calls[-1] is snapshot
        assert result['material'] == snapshot['digest']
        return result

    return snapshot, select

