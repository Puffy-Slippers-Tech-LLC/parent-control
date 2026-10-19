"""Preparation intent uses private files, anonymous FDs and process-local alarms.

No mounts, product installation, bus, services, privileged helper or host policy
is used. Current material's established private fixture retains real inode,
hash, membership and trust checks. Native admission/publication is not claimed.
"""
from contextlib import nullcontext
import fcntl
import importlib.util
import os
import signal
import stat
import sys
import time
from types import SimpleNamespace

import pytest

from tests.support.paths import ROOT
from tests.unit.test_kiosk_material_selection import material_scene, selected_scene
from tests.unit.test_kiosk_pin_storage import private_store
from tests.unit.test_kiosk_required_material import material_host
from tools import kiosk_preparation_input, kiosk_view_receipt as receipt


def load_service(helper, monkeypatch):
    monkeypatch.setitem(sys.modules, 'kiosk_confinement', helper)
    monkeypatch.setitem(sys.modules, 'kiosk_view_receipt', receipt)
    monkeypatch.setitem(sys.modules, 'kiosk_preparation_input', kiosk_preparation_input)
    spec = importlib.util.spec_from_file_location('private_kiosk_preparation_service',
                                                ROOT / 'tools/kiosk_preparation_service.py')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    monkeypatch.setattr(module, 'os', helper.os)
    return module


def deadline():
    return time.monotonic_ns() + 10_000_000_000


def test_result_record_is_sealed_readonly_and_descriptor_owned(private_store, monkeypatch):
    service = load_service(private_store.helper, monkeypatch)
    before = len(os.listdir('/proc/self/fd'))
    data = service._canonical(dict(format=1, plan={'source': 'original'}), deadline())
    with service._record(data, deadline()) as fd:
        assert os.read(fd, len(data) + 1) == data
        assert not os.get_inheritable(fd)
        assert fcntl.fcntl(fd, fcntl.F_GETFL) & os.O_ACCMODE == os.O_RDONLY
        assert fcntl.fcntl(fd, fcntl.F_GET_SEALS) & fcntl.F_SEAL_WRITE
        with pytest.raises(OSError):
            os.write(fd, b'changed')
    assert len(os.listdir('/proc/self/fd')) == before


def test_absolute_deadline_expires_inside_legacy_work_and_restores_handler(private_store, monkeypatch):
    service = load_service(private_store.helper, monkeypatch)
    original = signal.getsignal(signal.SIGALRM)
    with pytest.raises(TimeoutError, match='preparation-deadline'):
        with service._deadline(deadline()):
            # Deterministic delivery exercises legacy walks without sleeps.
            signal.raise_signal(signal.SIGALRM)
    assert signal.getsignal(signal.SIGALRM) == original
    assert signal.getitimer(signal.ITIMER_REAL) == (0.0, 0.0)
    with pytest.raises(TimeoutError):
        with service._deadline(time.monotonic_ns() - 1):
            pytest.fail('expired budget entered work')


def test_service_refuses_existing_alarm_without_clobbering_owner(private_store, monkeypatch):
    service = load_service(private_store.helper, monkeypatch)
    original = signal.getsignal(signal.SIGALRM)
    signal.setitimer(signal.ITIMER_REAL, 30)
    try:
        with pytest.raises(ValueError, match='preparation-existing-timer'):
            with service._deadline(deadline()):
                pytest.fail('existing timer was replaced')
        assert signal.getitimer(signal.ITIMER_REAL)[0] > 20
        assert signal.getsignal(signal.SIGALRM) == original
    finally:
        signal.setitimer(signal.ITIMER_REAL, 0)


def test_skeleton_has_fresh_empty_files_and_preserves_absence(private_store, monkeypatch):
    helper = private_store.helper
    service = load_service(helper, monkeypatch)
    fd = os.open(private_store.store, os.O_RDONLY | os.O_DIRECTORY | os.O_CLOEXEC)
    layout = [dict(path='/usr/bin', kind='tree'), dict(path='/usr/bin/native', kind='file'),
              dict(path='/usr/masked', kind='empty-directory'), dict(path='/usr/missing', kind='absent'),
              dict(path='/usr/alias', kind='link', link='/original/source')]
    try:
        service.make_skeleton(fd, layout, 'apparmor', deadline())
        tree = private_store.store / 'tree'
        assert (tree / 'bin/native').read_bytes() == b''
        assert stat.S_IMODE((tree / 'bin/native').stat().st_mode) == 0o644
        assert (tree / 'masked').is_dir()
        assert not (tree / 'missing').exists()
        assert os.readlink(tree / 'alias') == '/original/source'
        assert sorted(str(path.relative_to(tree)) for path in tree.rglob('*')) == [
            'alias', 'bin', 'bin/native', 'masked']
        with pytest.raises(ValueError, match='preparation-target-not-empty'):
            service.make_skeleton(fd, layout, 'apparmor', deadline())
    finally:
        os.close(fd)


@pytest.mark.parametrize('layout', [
    [dict(path='/usr/../escape', kind='file')],
    [dict(path='/usr/alias', kind='link', link='target'), dict(path='/usr/alias/file', kind='file')],
    [dict(path='/usr/item', kind='file', foreign=1)],
    [dict(path='/usr/item', kind='file'), dict(path='/usr/item', kind='file')],
])
def test_bad_skeleton_domain_is_refused_before_tree_creation(private_store, monkeypatch, layout):
    service = load_service(private_store.helper, monkeypatch)
    fd = os.open(private_store.store, os.O_RDONLY | os.O_DIRECTORY | os.O_CLOEXEC)
    try:
        with pytest.raises(ValueError):
            service.make_skeleton(fd, layout, 'apparmor', deadline())
        assert not list(private_store.store.iterdir())
    finally:
        os.close(fd)


def source_view(scene, snapshot):
    """Independent real inode observations in the selected native V shape."""
    nodes = []
    records = {item['path']: item for name in ('native', 'preserved', 'runtime')
               for item in snapshot[name]}
    layout = {'/usr': dict(path='/usr', kind='tree'),
              **{node['path']: node for node in scene.layout},
              '/usr/absent': dict(path='/usr/absent', kind='absent'),
              '/usr/masked': dict(path='/usr/masked', kind='empty-directory')}
    for index, (path, entry) in enumerate(sorted(layout.items())):
        kind = entry['kind']
        node = dict.fromkeys(receipt.NODE_FIELDS, 0)
        node.update(path=path, kind=kind, source_index=index * 3, sha256='-', label='-', link='-',
                    source_class='ambient', role='ambient', acquisition='none')
        if kind not in ('absent', 'empty-directory'):
            info = scene.helper.os.fstat(scene.pins[path]['fd'])
            node.update(required=1, source_class='skeleton', role='skeleton', acquisition='initial',
                        origin_device=info.st_dev, origin_inode=info.st_ino, device=info.st_dev,
                        inode=info.st_ino, size=info.st_size, mtime_ns=info.st_mtime_ns,
                        ctime_ns=info.st_ctime_ns, mode=info.st_mode, uid=0, gid=0,
                        nlink=info.st_nlink, mountpoint=1)
            if kind == 'file':
                source_class = ('native' if path in {item['path'] for item in snapshot['native']} else
                                'vendor' if path in {item['path'] for item in snapshot['preserved']}
                                else 'runtime')
                role = records[path].get('role', 'vendor') if source_class == 'native' else (
                    'vendor' if source_class == 'vendor' else 'data')
                node.update(source_class=source_class, role=role, sha256=records[path]['sha256'])
        nodes.append(node)
    return dict(format=2, kind='V', role='manager', backend='apparmor', material=snapshot['digest'],
                source='-', acquisition='a' * 64, nodes=nodes, coverage=[])


@pytest.mark.parametrize('fault', [None, 'slots', 'view', 'material', 'noncanonical'])
def test_retained_plan_binds_original_view_slots_and_clone(material_scene, monkeypatch, fault):
    scene = material_scene
    service = load_service(scene.helper, monkeypatch)
    snapshot, _ = selected_scene(scene, monkeypatch)
    view = source_view(scene, snapshot)
    view_bytes = receipt.encode_receipt(view)
    view_digest = receipt.receipt_digest(view)
    slots = dict(format=1, material=snapshot['digest'], source=view_digest,
                 slots={node['path']: node['source_index'] for node in view['nodes']})
    if fault == 'slots':
        slots['slots']['/usr/bin/native'] += 1
    if fault == 'noncanonical':
        view_bytes = view_bytes.replace(b'\t0\t', b'\t00\t', 1)
    with service._record(view_bytes, deadline()) as view_fd, service._record(
            service._canonical(slots, deadline()), deadline()) as slots_fd:
        selection = SimpleNamespace(backend='apparmor', material=bytes.fromhex(snapshot['digest']),
            view=bytes.fromhex(view_digest), descriptors=dict(source_view_receipt=view_fd,
            source_slots=slots_fd, source_usr=scene.pins['/usr']['fd']))
        if fault in ('view', 'material'):
            setattr(selection, fault, bytes(32))
        if fault:
            with pytest.raises(ValueError):
                service.retained_plan(snapshot, selection, deadline())
            return
        plan = service.retained_plan(snapshot, selection, deadline())
        assert plan['source_slots'] == slots['slots']
        assert plan['source_nodes'] == view['nodes']
        assert plan['sources']['/usr/bin/native']['index'] == slots['slots']['/usr/bin/native']
        assert dict(path='/usr/masked', kind='empty-directory') in plan['layout']
        assert '/usr/absent' not in plan['sources']
        assert not {'view', 'invocation', 'ready'} & plan.keys()


@pytest.mark.parametrize('send_failure', [False, True])
def test_manager_response_transfers_only_successfully_sent_copy_ticket(material_host, monkeypatch,
                                                                      send_failure):
    scene, helper = material_host, material_host.helper
    service = load_service(helper, monkeypatch)
    snapshot = scene.measure()
    target = scene.fixture.store / 'invocation'
    target.mkdir(mode=0o700)
    target_fd = os.open(target, os.O_RDONLY | os.O_DIRECTORY | os.O_CLOEXEC)
    observed = {}

    class Exchange:
        def __init__(self, channel, *, role, deadline_ns):
            observed['deadline'] = deadline_ns

        def send_measurement(self, **kwargs):
            assert service._read(kwargs['material_receipt'], deadline()) == receipt.material_canonical(
                snapshot['record'])

        def receive_selection(self):
            return nullcontext(SimpleNamespace(backend='apparmor', view=bytes(32),
                material=bytes.fromhex(snapshot['digest']), descriptors={'target_root': target_fd}))

        def send_result(self, result_receipt, *, copy_directory):
            observed['result'] = service._json(result_receipt, deadline())
            observed['copy'] = os.dup(copy_directory)
            if send_failure:
                raise OSError('injected-send-failure')

    monkeypatch.setattr(service, 'PreparationExchange', Exchange)
    configuration = (scene.payload / 'config.json').read_bytes()
    monkeypatch.setattr(service, 'measure', lambda role, deadline_ns: (snapshot, configuration))
    monkeypatch.setattr(helper, 'RUNTIME', scene.fixture.store)
    budget = deadline()
    try:
        if send_failure:
            with pytest.raises(OSError, match='injected-send-failure'):
                service.serve(object(), role='manager', deadline_ns=budget)
            assert list(scene.fixture.store.iterdir()) == [target]
        else:
            service.serve(object(), role='manager', deadline_ns=budget)
            result = observed['result']
            assert observed['deadline'] == budget
            assert set(result) == {'format', 'role', 'backend', 'material', 'source', 'plan', 'ticket'}
            assert result['source'] == '-'
            scratch = scene.fixture.store / result['ticket']['name']
            assert scratch.is_dir()
            assert not {'ready', 'V', 'I'} & {path.name for path in scratch.iterdir()}
            assert os.fstat(observed['copy']).st_ino == scratch.stat().st_ino
            assert (target / 'tree/bin/native').read_bytes() == b''
            helper.reclaim_runtime_scratch(scene.fixture.store, result['ticket'])
    finally:
        os.close(target_fd)
        if 'copy' in observed:
            os.close(observed['copy'])
