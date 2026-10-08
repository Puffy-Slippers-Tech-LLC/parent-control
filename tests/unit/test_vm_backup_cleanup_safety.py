"""Disaster recovery against private files and libvirt doubles; no live VM access."""
import json
import hashlib
import os
import runpy
import shutil
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock
import xml.etree.ElementTree as ET

import pytest

import prepare_baseline as base
import vm_config
from tools import vm_backup as recovery
from tools import vm_backup_launcher as launcher
from tests.support.vm_baseline import UUID, rig
from tests.support.paths import ROOT


class LibvirtError(Exception):
    def __init__(self, code):
        self.code = code

    def get_error_code(self):
        return self.code


API = SimpleNamespace(libvirtError=LibvirtError, VIR_ERR_NO_DOMAIN=42, VIR_ERR_NO_NETWORK=43,
    VIR_DOMAIN_XML_INACTIVE=2, VIR_NETWORK_XML_INACTIVE=1, VIR_DOMAIN_SHUTOFF=5,
    VIR_DOMAIN_SNAPSHOT_CREATE_REDEFINE=1, VIR_DOMAIN_SNAPSHOT_CREATE_CURRENT=2,
    VIR_DOMAIN_SNAPSHOT_DELETE_METADATA_ONLY=2)


class Snapshot:
    def __init__(self, domain, name):
        self.domain, self.name = domain, name

    def getName(self):
        return self.name

    def getXMLDesc(self, flags):
        return self.domain.snapshots[self.name]

    def delete(self, flags):
        assert flags == API.VIR_DOMAIN_SNAPSHOT_DELETE_METADATA_ONLY
        self.domain.snapshots.pop(self.name)
        if self.domain.current == self.name:
            self.domain.current = None


class Domain:
    def __init__(self, source):
        self.source = source
        self.xml = ET.tostring(ET.fromstring(source.baseline_xml).find('domain'), encoding='unicode')
        self.snapshots = {base.SNAPSHOT: source.baseline_xml}
        self.current = base.SNAPSHOT
        self.identifier = -1
        self.automatic = False
        self.redefined = []

    def UUIDString(self):
        return UUID

    def ID(self):
        return self.identifier

    def name(self):
        return ET.fromstring(self.xml).findtext('name')

    def isPersistent(self):
        return True

    def state(self):
        return (API.VIR_DOMAIN_SHUTOFF if self.identifier == -1 else 1, 0)

    def hasManagedSaveImage(self, flags):
        return False

    def autostart(self):
        return self.automatic

    def setAutostart(self, value):
        self.automatic = value

    def XMLDesc(self, flags):
        return self.xml

    def listAllSnapshots(self, flags):
        return [Snapshot(self, name) for name in self.snapshots]

    def hasCurrentSnapshot(self, flags):
        return self.current is not None

    def snapshotCurrent(self, flags):
        return Snapshot(self, self.current)

    def snapshotListNames(self, flags):
        return list(self.snapshots)

    def snapshotLookupByName(self, name, flags):
        return Snapshot(self, name)

    def snapshotCreateXML(self, xml, flags):
        assert flags & API.VIR_DOMAIN_SNAPSHOT_CREATE_REDEFINE
        name = ET.fromstring(xml).findtext('name')
        self.snapshots[name] = xml
        self.redefined.append((name, flags))
        if flags & API.VIR_DOMAIN_SNAPSHOT_CREATE_CURRENT:
            self.current = name
        if name == base.SNAPSHOT:
            self.source.baseline_xml = xml
        return Snapshot(self, name)


class Connection:
    def __init__(self, domain):
        self.domain, self.present = domain, True
        self.definitions = []
        self.foreign = []
        self.networks = {}

    def getURI(self):
        return vm_config.URI

    def lookupByName(self, name):
        if not self.present:
            raise LibvirtError(API.VIR_ERR_NO_DOMAIN)
        assert name == self.domain.name()
        return self.domain

    def lookupByUUIDString(self, identity):
        if not self.present:
            raise LibvirtError(API.VIR_ERR_NO_DOMAIN)
        return self.domain

    def listAllDomains(self, flags):
        return ([self.domain] if self.present else []) + self.foreign

    def defineXML(self, xml):
        self.definitions.append(xml)
        self.domain.xml = xml
        self.domain.source.layout = base.domain_layout(xml, UUID)
        self.present = True
        return self.domain

    def networkLookupByName(self, name):
        if name not in self.networks:
            raise LibvirtError(API.VIR_ERR_NO_NETWORK)
        return self.networks[name]

    def networkLookupByUUIDString(self, identity):
        for network in self.networks.values():
            if ET.fromstring(network.xml).findtext('uuid') == identity:
                return network
        raise LibvirtError(API.VIR_ERR_NO_NETWORK)

    def networkDefineXML(self, xml):
        network = Network(xml, active=False, automatic=False)
        self.networks[ET.fromstring(xml).findtext('name')] = network
        return network


class Network:
    def __init__(self, xml, *, active=True, automatic=True):
        self.xml = xml
        self.active = active
        self.automatic = automatic

    def XMLDesc(self, flags):
        return self.xml

    def isPersistent(self):
        return True

    def isActive(self):
        return self.active

    def autostart(self):
        return self.automatic

    def setAutostart(self, value):
        self.automatic = value

    def create(self):
        assert not self.active
        self.active = True


@pytest.fixture
def backup_rig(rig, tmp_path, monkeypatch):
    config = tmp_path / 'test-vm.json'
    state_root = tmp_path / 'state'
    state_root.mkdir(mode=0o700)
    config.write_text(json.dumps({'backup_root': str(tmp_path / 'backups'), 'concurrency': 2,
        'vms': [{'id': '9', 'name': 'Backup-guest', 'disk_anchor': str(rig.anchor), 'enabled': 'true'},
                {'id': 12, 'name': 'Other-guest', 'disk_anchor': str(tmp_path / 'other.qcow2'), 'enabled': 'false'}]}))
    monkeypatch.setattr(vm_config, 'CONFIG', config)
    monkeypatch.setattr(vm_config, 'STATE_ROOT', state_root)
    vm = vm_config.select('9')
    rig.directory = vm.baseline_directory
    rig.capture = lambda: base.Capture(rig.source, rig.commands, rig.inspect,
                                      anchor=rig.anchor, directory=rig.directory)
    rig.source.off = True
    rig.capture().run()
    domain = Domain(rig.source)
    connection = Connection(domain)
    rig.source.domain, rig.source.connection, rig.source.uuid = domain, connection, UUID
    rig.source.close = Mock()
    monkeypatch.setattr(base, 'LibvirtSource', lambda api: rig.source)
    online = tmp_path / 'online'
    monkeypatch.setattr(recovery, 'online_directory', lambda identity, create=False: online)
    root = vm_config.backup_root()
    recovery.private_directory(root, create=True)
    return SimpleNamespace(**vars(rig), vm=vm, root=root, domain=domain, connection=connection, online=online)


def save(rig):
    recovery.backup(API, rig.vm, rig.root, rig.commands)
    return recovery.load_archive(rig.vm, rig.root)


def restore(rig):
    recovery.restore(rig.connection, API, rig.vm, rig.root, rig.commands)


@pytest.fixture
def network_rig(backup_rig):
    rig = backup_rig
    tree = ET.fromstring(rig.domain.xml)
    interface = ET.SubElement(tree.find('devices'), 'interface', type='network')
    ET.SubElement(interface, 'source', network='backup-network')
    rig.domain.xml = ET.tostring(tree, encoding='unicode')
    xml = '<network><name>backup-network</name><uuid>00000000-0000-0000-0000-000000000003</uuid><bridge name="virt-backup"/></network>'
    rig.connection.networks['backup-network'] = Network(xml)
    return rig


def test_backup_restores_deleted_domain_disks_and_rebinds_baseline(backup_rig):
    rig = backup_rig
    archive, manifest, latest = save(rig)
    original = {str(path): path.read_bytes() for path in (rig.top, rig.anchor)}
    old_state = recovery.read_json(rig.directory / 'phase.json')
    # Simulate lost host disks/libvirt definitions; preserve the offline archive.
    rig.top.unlink()
    rig.anchor.unlink()
    for path in rig.directory.iterdir():
        if path.name != '.lock':
            path.unlink()
    rig.connection.present = False
    rig.domain.snapshots.clear()
    rig.domain.current = None
    restore(rig)
    assert all(Path(path).read_bytes() == value for path, value in original.items())
    state = recovery.read_json(rig.directory / 'phase.json')
    assert state['source']['chain'] != old_state['source']['chain']
    assert state['operation'] == old_state['operation']
    assert state['proof'] == old_state['proof']
    assert state['guest'] == old_state['guest']
    capture = rig.capture()
    capture.directory_identity = capture.private_directory()
    capture.state = capture.read_state()
    capture.revalidate(off=True)
    assert capture.verify_snapshot() == old_state['proof']
    assert recovery.read_json(rig.directory / recovery.JOURNAL)['phase'] == 'complete'
    assert rig.domain.current == base.SNAPSHOT
    assert rig.domain.ID() == -1
    assert recovery.load_archive(rig.vm, rig.root)[2] == latest


def test_restore_corrupt_owned_disk_preserves_displaced_bytes_and_repeat(backup_rig):
    rig = backup_rig
    save(rig)
    expected = rig.top.read_bytes()
    rig.top.write_bytes(b'corrupted disk bytes')
    restore(rig)
    assert rig.top.read_bytes() == expected
    displaced = list(rig.top.parent.glob('.restore-vms-*.previous'))
    assert any(path.read_bytes() == b'corrupted disk bytes' for path in displaced)
    restore(rig)
    assert rig.top.read_bytes() == expected
    assert list(rig.directory.glob('.restore-vms-history-*.json'))


def test_lost_domain_with_proven_owned_disks_can_be_reconciled(backup_rig):
    rig = backup_rig
    save(rig)
    expected = rig.top.read_bytes()
    rig.top.write_bytes(b'corruption with lost libvirt definition')
    rig.connection.present = False
    restore(rig)
    assert rig.connection.present and rig.top.read_bytes() == expected


@pytest.mark.parametrize('kind', ['missing', 'new-uuid', 'conflict'])
def test_network_recovery_preserves_equivalent_definitions_and_refuses_conflicts(network_rig, kind):
    rig = network_rig
    xml = rig.connection.networks['backup-network'].xml
    save(rig)
    if kind == 'missing':
        rig.connection.networks.clear()
    elif kind == 'new-uuid':
        rig.connection.networks['backup-network'].xml = xml.replace('000000000003', '000000000004')
    else:
        rig.connection.networks['backup-network'].xml = xml.replace('virt-backup', 'unrelated-bridge')
    expected = rig.top.read_bytes()
    if kind == 'conflict':
        with pytest.raises(base.CaptureError, match='network-definition-collision'):
            restore(rig)
        assert not (rig.directory / recovery.JOURNAL).exists()
        assert rig.top.read_bytes() == expected
    else:
        restore(rig)
        actual = rig.connection.networks['backup-network']
        assert actual.active and actual.automatic
        assert actual.xml == (xml if kind == 'missing' else xml.replace('000000000003', '000000000004'))


@pytest.mark.parametrize('boundary', ['before-definition', 'defined', 'autostart', 'activated'])
def test_interrupted_network_creation_resumes_configuration(network_rig, monkeypatch, boundary):
    rig = network_rig
    save(rig)
    rig.connection.networks.clear()
    define = rig.connection.networkDefineXML
    automatic = Network.setAutostart
    activate = Network.create
    stopped = False
    def interrupt_once():
        nonlocal stopped
        if not stopped:
            stopped = True
            raise KeyboardInterrupt
    def defined(xml):
        if boundary == 'before-definition':
            interrupt_once()
        network = define(xml)
        if boundary == 'defined':
            interrupt_once()
        return network
    def autostart(network, value):
        automatic(network, value)
        if boundary == 'autostart':
            interrupt_once()
    def activated(network):
        activate(network)
        if boundary == 'activated':
            interrupt_once()
    monkeypatch.setattr(rig.connection, 'networkDefineXML', defined)
    monkeypatch.setattr(Network, 'setAutostart', autostart)
    monkeypatch.setattr(Network, 'create', activated)
    with pytest.raises(KeyboardInterrupt):
        restore(rig)
    journal = recovery.read_json(rig.directory / recovery.JOURNAL)
    assert journal['phase'] == 'metadata'
    assert journal['networks']['backup-network'] == {
        'uuid': '00000000-0000-0000-0000-000000000003', 'created': True}
    with pytest.raises(base.CaptureError, match='interrupted-vm-restore'):
        rig.capture().require_idle_attempt()
    restore(rig)
    assert recovery.read_json(rig.directory / recovery.JOURNAL)['phase'] == 'complete'
    network = rig.connection.networks['backup-network']
    assert network.active and network.automatic


@pytest.mark.parametrize('active,automatic', [(False, False), (False, True), (True, False), (True, True)])
def test_new_network_restores_archived_runtime_settings(network_rig, active, automatic):
    rig = network_rig
    network = rig.connection.networks['backup-network']
    network.active, network.automatic = active, automatic
    save(rig)
    rig.connection.networks.clear()
    restore(rig)
    restored = rig.connection.networks['backup-network']
    assert (restored.active, restored.automatic) == (active, automatic)


@pytest.mark.parametrize('kind', ['uuid', 'definition'])
def test_network_replacement_during_interrupted_restore_is_refused(network_rig, monkeypatch, kind):
    rig = network_rig
    save(rig)
    rig.connection.networks.clear()
    define = rig.connection.networkDefineXML
    def interrupted(xml):
        define(xml)
        raise KeyboardInterrupt
    monkeypatch.setattr(rig.connection, 'networkDefineXML', interrupted)
    with pytest.raises(KeyboardInterrupt):
        restore(rig)
    network = rig.connection.networks['backup-network']
    network.xml = (network.xml.replace('000000000003', '000000000004') if kind == 'uuid' else
                   network.xml.replace('virt-backup', 'unrelated-bridge'))
    with pytest.raises(base.CaptureError, match='network-journal-identity|network-definition-collision'):
        restore(rig)
    assert not network.active and not network.automatic
    assert recovery.read_json(rig.directory / recovery.JOURNAL)['phase'] == 'metadata'


def test_existing_network_preserves_runtime_settings_on_restore_retry(network_rig, monkeypatch):
    rig = network_rig
    save(rig)
    network = rig.connection.networks['backup-network']
    network.xml = network.xml.replace('000000000003', '000000000004')
    network.active = network.automatic = False
    define = rig.connection.defineXML
    def interrupted(xml):
        define(xml)
        raise KeyboardInterrupt
    monkeypatch.setattr(rig.connection, 'defineXML', interrupted)
    with pytest.raises(KeyboardInterrupt):
        restore(rig)
    monkeypatch.setattr(rig.connection, 'defineXML', define)
    restore(rig)
    assert not network.active and not network.automatic
    assert '000000000004' in network.xml


@pytest.mark.parametrize('phase', ['files', 'metadata'])
def test_older_restore_journals_reconcile_exact_archived_networks(network_rig, monkeypatch, phase):
    rig = network_rig
    save(rig)
    original = recovery.publish_file if phase == 'files' else rig.connection.defineXML
    def interrupted(*args, **kwargs):
        raise KeyboardInterrupt
    monkeypatch.setattr(recovery if phase == 'files' else rig.connection,
                        'publish_file' if phase == 'files' else 'defineXML', interrupted)
    with pytest.raises(KeyboardInterrupt):
        restore(rig)
    journal = recovery.read_json(rig.directory / recovery.JOURNAL)
    del journal['networks']
    recovery.atomic(rig.directory / recovery.JOURNAL, journal)
    monkeypatch.setattr(recovery if phase == 'files' else rig.connection,
                        'publish_file' if phase == 'files' else 'defineXML', original)
    if phase == 'metadata':
        network = rig.connection.networks['backup-network']
        network.active = network.automatic = False
    restore(rig)
    assert recovery.read_json(rig.directory / recovery.JOURNAL)['phase'] == 'complete'
    if phase == 'metadata':
        assert network.active and network.automatic


def assert_usable_baseline(rig):
    capture = rig.capture()
    capture.directory_identity = capture.private_directory()
    capture.require_idle_attempt()
    capture.state = capture.read_state()
    capture.revalidate(off=True)
    capture.verify_snapshot()
    return capture.state


@pytest.mark.parametrize('name', ['phase.json', 'system-run.json', 'vm-control.json',
                                  'rename-stale.json', 'disk-rename-stale.json'])
def test_restore_supersedes_corrupt_local_bookkeeping_without_losing_evidence(backup_rig, name):
    rig = backup_rig
    save(rig)
    path = rig.directory / name
    path.write_bytes(b'damaged bookkeeping')
    path.chmod(0o600)
    rig.connection.present = False
    rig.top.write_bytes(b'orphan disk with no usable provenance')
    restore(rig)
    assert_usable_baseline(rig)
    assert any(item.read_bytes() == b'damaged bookkeeping'
               for item in rig.directory.glob('.restore-vms-*'))
    assert rig.connection.present
    if name != 'phase.json':
        assert not path.exists()


@pytest.mark.parametrize('record', [b'broken {', b'\xff', b'{"phase":1,"phase":2}',
                                   b'{"schema_version":1,"phase":"files"}',
                                   b'{"phase":"metadata","uuid":"another-vm"}'])
def test_restore_preserves_and_supersedes_unusable_recovery_journal(backup_rig, record):
    rig = backup_rig
    save(rig)
    path = rig.directory / recovery.JOURNAL
    path.write_bytes(record)
    path.chmod(0o600)
    restore(rig)
    assert_usable_baseline(rig)
    assert any(item.read_bytes() == record for item in rig.directory.glob('.restore-vms-history-*'))


@pytest.mark.parametrize('boundary', ['intent', 'renamed', 'rebound'])
def test_reconciliation_interruption_resumes_without_adopting_stale_records(backup_rig, monkeypatch, boundary):
    rig = backup_rig
    save(rig)
    path = rig.directory / 'system-run.json'
    recovery.atomic(path, {'phase': 'running', 'domain_uuid': 'stale'})
    raw = path.read_bytes()
    atomic, rename = recovery.atomic, recovery.os.rename
    def published(destination, value):
        atomic(destination, value)
        if ((boundary == 'intent' and destination.name == recovery.JOURNAL and value.get('retired_records')) or
                (boundary == 'rebound' and destination.name == 'phase.json')):
            raise KeyboardInterrupt
    def renamed(source, destination):
        rename(source, destination)
        if boundary == 'renamed' and source == path:
            raise KeyboardInterrupt
    monkeypatch.setattr(recovery, 'atomic', published)
    monkeypatch.setattr(recovery.os, 'rename', renamed)
    with pytest.raises(KeyboardInterrupt):
        restore(rig)
    with pytest.raises(base.CaptureError, match='interrupted-vm-restore'):
        rig.capture().require_idle_attempt()
    monkeypatch.setattr(recovery, 'atomic', atomic)
    monkeypatch.setattr(recovery.os, 'rename', rename)
    restore(rig)
    assert_usable_baseline(rig)
    assert not path.exists()
    record = recovery.read_json(rig.directory / recovery.JOURNAL)['retired_records'][str(path)]
    assert Path(record['retained']).read_bytes() == raw


def test_restored_archive_attempts_are_retired_and_saved_credentials_reconciled(backup_rig):
    rig = backup_rig
    for name in ('system-run.json', 'vm-control.json'):
        recovery.atomic(rig.directory / name, {'phase': 'complete', 'domain_uuid': UUID})
    recovery.private_directory(rig.online, create=True)
    recovery.atomic(rig.online / 'credentials.json', {'key': 'archived'})
    save(rig)
    recovery.atomic(rig.online / 'credentials.json', {'key': 'stale'})
    recovery.atomic(rig.online / 'unarchived.json', {'owner': 'stale'})
    restore(rig)
    assert_usable_baseline(rig)
    assert recovery.read_json(rig.online / 'credentials.json') == {'key': 'archived'}
    assert not (rig.online / 'unarchived.json').exists()
    assert not any((rig.directory / name).exists() for name in ('system-run.json', 'vm-control.json'))
    # A second recovery keeps the original backup evidence usable.
    restore(rig)
    assert_usable_baseline(rig)


def test_restore_preserves_logical_baseline_hash_across_repeat_and_new_backup(backup_rig):
    rig = backup_rig
    original = hashlib.sha256(base.encode(recovery.read_json(rig.directory / 'phase.json'))).hexdigest()
    save(rig)
    restore(rig)
    state = assert_usable_baseline(rig)
    assert hashlib.sha256(base.encode(state)).hexdigest() != original
    assert base.baseline_sha256(state, rig.directory) == original
    assert save(rig)[1]['baseline_sha256'] == original
    restore(rig)
    assert base.baseline_sha256(assert_usable_baseline(rig), rig.directory) == original
    changed = dict(state, operation='f' * 32)
    assert base.baseline_sha256(changed, rig.directory) == hashlib.sha256(base.encode(changed)).hexdigest()


@pytest.mark.parametrize('kind', ['uuid', 'directory', 'digest'])
def test_restore_baseline_hash_binding_rejects_inconsistent_attestation(backup_rig, kind):
    rig = backup_rig
    save(rig)
    restore(rig)
    state = assert_usable_baseline(rig)
    journal = recovery.read_json(rig.directory / recovery.JOURNAL)
    if kind == 'uuid':
        journal['uuid'] = 'wrong'
    elif kind == 'directory':
        journal['directory']['inode'] += 1
    else:
        journal['baseline_identity']['original'] = 'invalid'
    recovery.atomic(rig.directory / recovery.JOURNAL, journal)
    with pytest.raises(base.CaptureError, match='restore-baseline-identity'):
        base.baseline_sha256(state, rig.directory)


def test_new_execution_and_helper_pins_accept_restored_baseline(backup_rig):
    import system_runner as runner
    rig = backup_rig
    tree = ET.fromstring(rig.domain.xml)
    interface = ET.SubElement(tree.find('devices'), 'interface', type='network')
    ET.SubElement(interface, 'source', network='default')
    rig.domain.xml = ET.tostring(tree, encoding='unicode')
    rig.connection.networks['default'] = Network('<network><name>default</name>'
        '<uuid>00000000-0000-0000-0000-000000000003</uuid></network>')
    original = base.baseline_sha256(recovery.read_json(rig.directory / 'phase.json'), rig.directory)
    save(rig)
    recovery.atomic(rig.directory / 'system-run.json', {'phase': 'running'})
    recovery.atomic(rig.directory / 'vm-control.json', {'phase': 'active', 'domain_uuid': 'stale'})
    restore(rig)
    rig.source.api = API
    lease = runner.Lease(rig.source, rig.commands, rig.inspect, directory=rig.directory, anchor=rig.anchor)
    try:
        lease.__enter__()
        assert lease.state['baseline_sha256'] == original
        assert lease.state['domain_uuid'] == UUID
        assert lease.state['phase'] == 'validated'
    finally:
        lease.release()
    helper = runpy.run_path(str(ROOT / 'tools/install_test_runner.py'))
    assert helper['pinned_vm_uuid'](rig.directory, owner=os.getuid()) == UUID


def test_corrupt_archive_fails_before_touching_local_vm(backup_rig):
    rig = backup_rig
    archive, manifest, _ = save(rig)
    image = next(item for item in manifest['files'] if item['area'] == 'disk')
    (archive / image['payload']).write_bytes(b'bad')
    before = rig.top.read_bytes()
    with pytest.raises(base.CaptureError, match='payload-checksum'):
        restore(rig)
    assert rig.top.read_bytes() == before
    assert not (rig.directory / recovery.JOURNAL).exists()
    assert not rig.connection.definitions


@pytest.mark.parametrize('kind', ['running', 'autostart', 'unfinished-run', 'unfinished-restore'])
def test_busy_or_unfinished_vm_cannot_be_backed_up(backup_rig, kind):
    rig = backup_rig
    if kind == 'running':
        rig.domain.identifier = 10
    elif kind == 'autostart':
        rig.domain.automatic = True
    elif kind == 'unfinished-run':
        recovery.atomic(rig.directory / 'system-run.json', {'phase': 'running'})
    else:
        recovery.atomic(rig.directory / recovery.JOURNAL, {'phase': 'files'})
    with pytest.raises(base.CaptureError):
        save(rig)
    assert not (rig.root / rig.vm.name / 'latest.json').exists()


def test_failed_backup_preserves_previous_complete_generation(backup_rig, monkeypatch):
    rig = backup_rig
    archive, _, latest = save(rig)
    previous_copy = recovery.copy_file
    def interrupted(source, destination, **kwargs):
        previous_copy(source, destination, **kwargs)
        raise KeyboardInterrupt
    monkeypatch.setattr(recovery, 'copy_file', interrupted)
    with pytest.raises(KeyboardInterrupt):
        save(rig)
    assert recovery.read_json(rig.root / rig.vm.name / 'latest.json') == latest
    assert archive.exists()


@pytest.mark.parametrize('boundary', ['copied', 'displaced', 'published', 'metadata'])
def test_interrupted_restore_resumes_its_recorded_transaction(backup_rig, monkeypatch, boundary):
    rig = backup_rig
    save(rig)
    expected = rig.top.read_bytes()
    rig.top.write_bytes(b'old data')
    rename = recovery.os.rename
    copy_file = recovery.copy_file
    define = rig.connection.defineXML
    stopped = False
    def interrupt_once():
        nonlocal stopped
        if not stopped:
            stopped = True
            raise KeyboardInterrupt
    def renamed(source, destination):
        rename(source, destination)
        if ((boundary == 'displaced' and str(destination).endswith('.previous')) or
                (boundary == 'published' and Path(destination) == rig.top)):
            interrupt_once()
    def copied(source, destination, **kwargs):
        copy_file(source, destination, **kwargs)
        if boundary == 'copied':
            interrupt_once()
    def defined(xml):
        result = define(xml)
        if boundary == 'metadata':
            interrupt_once()
        return result
    monkeypatch.setattr(recovery.os, 'rename', renamed)
    monkeypatch.setattr(recovery, 'copy_file', copied)
    monkeypatch.setattr(rig.connection, 'defineXML', defined)
    with pytest.raises(KeyboardInterrupt):
        restore(rig)
    assert recovery.read_json(rig.directory / recovery.JOURNAL)['phase'] != 'complete'
    with pytest.raises(base.CaptureError, match='interrupted-vm-restore'):
        rig.capture().require_idle_attempt()
    restore(rig)
    assert rig.top.read_bytes() == expected
    assert recovery.read_json(rig.directory / recovery.JOURNAL)['phase'] == 'complete'


def test_destination_replacement_during_interrupted_restore_is_refused(backup_rig, monkeypatch):
    rig = backup_rig
    save(rig)
    publish = recovery.publish_file
    def interrupted(*args, **kwargs):
        raise KeyboardInterrupt
    monkeypatch.setattr(recovery, 'publish_file', interrupted)
    with pytest.raises(KeyboardInterrupt):
        restore(rig)
    rig.top.rename(rig.top.with_suffix('.foreign'))
    rig.top.write_bytes(b'foreign replacement')
    monkeypatch.setattr(recovery, 'publish_file', publish)
    with pytest.raises(base.CaptureError, match='destination-replaced'):
        restore(rig)
    assert rig.top.read_bytes() == b'foreign replacement'


def test_symlink_and_hardlink_inputs_are_never_copied(tmp_path):
    source = tmp_path / 'source'
    source.write_bytes(b'private data')
    link = tmp_path / 'link'
    link.symlink_to(source)
    with pytest.raises(base.CaptureError):
        recovery.copy_file(link, tmp_path / 'destination')
    link.unlink()
    os.link(source, link)
    with pytest.raises(base.CaptureError):
        recovery.copy_file(source, tmp_path / 'destination')
    assert not (tmp_path / 'destination').exists()


def test_sparse_copy_preserves_bytes_without_inflating_holes(tmp_path):
    source = tmp_path / 'source'
    with source.open('wb') as stream:
        stream.write(b'head')
        stream.seek(8 * 1024 * 1024)
        stream.write(b'tail')
    target = tmp_path / 'copy'
    recovery.copy_file(source, target)
    assert recovery.checksum(source) == recovery.checksum(target)
    assert target.stat().st_size == source.stat().st_size
    assert target.stat().st_blocks <= source.stat().st_blocks + 16


@pytest.mark.parametrize('selector,names', [(None, 'Backup-guest,Other-guest'),
    ('all-enabled', 'Backup-guest'), ('9,Backup-guest,12', 'Backup-guest,Other-guest')])
def test_backup_prepares_whole_queue_before_serial_backup(backup_rig, monkeypatch, selector, names):
    monkeypatch.setattr(launcher, 'check', Mock())
    run = Mock(return_value=SimpleNamespace(returncode=0))
    monkeypatch.setattr(launcher.subprocess, 'run', run)
    assert launcher.main('backup', [] if selector is None else ['--vm', selector]) == 0
    assert run.call_count == 2
    assert run.call_args_list[0].args[0] == [str(launcher.ROOT / 'tools/prepare-baseline'),
                                           '--vm', names, '--mode', 'auto', '--y']
    assert run.call_args_list[1].args[0][-3:] == ['backupvms', '--vm', names]


def test_preparation_failure_never_starts_backup(backup_rig, monkeypatch):
    monkeypatch.setattr(launcher, 'check', Mock())
    run = Mock(return_value=SimpleNamespace(returncode=7))
    monkeypatch.setattr(launcher.subprocess, 'run', run)
    assert launcher.main('backup', []) == 7
    assert run.call_count == 1


def test_restore_refreshes_helper_pins_only_after_success(backup_rig, monkeypatch):
    monkeypatch.setattr(launcher, 'check', Mock())
    run = Mock(side_effect=[SimpleNamespace(returncode=0), SimpleNamespace(returncode=0)])
    monkeypatch.setattr(launcher.subprocess, 'run', run)
    assert launcher.main('restore', ['--vm', '9']) == 0
    assert run.call_args_list[0].args[0][-3:] == ['restorevms', '--vm', 'Backup-guest']
    assert run.call_args_list[1].args[0] == [str(launcher.ROOT / 'setup.sh'), '--test-tools-only']


@pytest.mark.parametrize('value', ['relative', '/', '/path/../backup', '/path//backup', None])
def test_backup_root_validation_is_shared_with_other_registry_consumers(tmp_path, value):
    config = tmp_path / 'registry.json'
    config.write_text(json.dumps({'backup_root': value, 'vms': [{'name': 'Guest', 'disk_anchor': '/disk'}]}))
    with pytest.raises(ValueError, match='backup_root'):
        vm_config.registry(config)


def test_optional_backup_root_preserves_old_registries(tmp_path):
    config = tmp_path / 'registry.json'
    config.write_text(json.dumps({'vms': [{'name': 'Guest', 'disk_anchor': '/disk'}]}))
    assert vm_config.registry(config)['Guest'].name == 'Guest'
    with pytest.raises(ValueError, match='backup_root is required'):
        vm_config.backup_root(config)


def test_restore_keeps_original_snapshot_definitions_before_replacing_metadata(backup_rig):
    rig = backup_rig
    save(rig)
    tree = ET.fromstring(rig.source.baseline_xml)
    tree.find('name').text = 'later-manual-snapshot'
    later = ET.tostring(tree, encoding='unicode')
    rig.domain.snapshots['later-manual-snapshot'] = later
    rig.domain.current = 'later-manual-snapshot'
    restore(rig)
    assert rig.domain.snapshotListNames(0) == [base.SNAPSHOT]
    journal = recovery.read_json(rig.directory / recovery.JOURNAL)
    assert {'name': 'later-manual-snapshot', 'xml': later} in journal['previous_snapshots']


@pytest.mark.parametrize('kind', ['uuid', 'running', 'symlink', 'shared-disk', 'shared-backing'])
def test_restore_refuses_foreign_or_active_destinations_before_mutation(backup_rig, monkeypatch, kind):
    rig = backup_rig
    save(rig)
    if kind == 'uuid':
        monkeypatch.setattr(rig.domain, 'UUIDString', lambda: '00000000-0000-0000-0000-000000000001')
    elif kind == 'running':
        rig.domain.identifier = 12
    elif kind == 'symlink':
        rig.top.rename(rig.top.with_suffix('.original'))
        rig.top.symlink_to(rig.top.with_suffix('.original'))
    else:
        path = rig.top
        if kind == 'shared-backing':
            path = rig.top.with_suffix('.foreign')
            path.write_bytes(b'foreign overlay')
            rig.commands.run = Mock(return_value=base.encode({'backing-filename': str(rig.anchor)}))
        foreign = Mock()
        foreign.UUIDString.return_value = '00000000-0000-0000-0000-000000000001'
        foreign.XMLDesc.return_value = f'<domain><devices><disk><source file="{path}"/></disk></devices></domain>'
        foreign.listAllSnapshots.return_value = []
        foreign.hasCurrentSnapshot.return_value = False
        rig.connection.foreign = [foreign]
    before = rig.top.read_bytes()
    with pytest.raises(base.CaptureError):
        restore(rig)
    assert rig.top.read_bytes() == before
    assert not rig.connection.definitions
    assert not (rig.directory / recovery.JOURNAL).exists()


@pytest.mark.parametrize('kind', ['top', 'parent', 'backing', 'snapshot'])
def test_missing_disks_of_other_inactive_domains_do_not_block_recovery(backup_rig, kind):
    rig = backup_rig
    save(rig)
    expected = rig.top.read_bytes(), rig.anchor.read_bytes()
    rig.top.unlink()
    rig.anchor.unlink()
    missing = rig.top.parent / 'other-missing.qcow2'
    if kind == 'parent':
        missing = missing / 'absent-parent' / 'other.qcow2'
    foreign = Mock()
    foreign.UUIDString.return_value = '00000000-0000-0000-0000-000000000001'
    foreign.ID.return_value = -1
    foreign.listAllSnapshots.return_value = []
    foreign.hasCurrentSnapshot.return_value = False
    if kind == 'backing':
        top = rig.top.with_suffix('.foreign')
        top.write_bytes(b'foreign image with a missing backing file')
        rig.commands.run = Mock(return_value=base.encode({'backing-filename': str(missing)}))
        xml = f'<domain><devices><disk><source file="{top}"/></disk></devices></domain>'
    else:
        xml = f'<domain><devices><disk><source file="{missing}"/></disk></devices></domain>'
    if kind == 'snapshot':
        snapshot = Mock()
        snapshot.getName.return_value = 'old-foreign-snapshot'
        snapshot.getXMLDesc.return_value = f'<domainsnapshot>{xml}</domainsnapshot>'
        foreign.listAllSnapshots.return_value = [snapshot]
        xml = '<domain><devices/></domain>'
    foreign.XMLDesc.return_value = xml
    rig.connection.foreign = [foreign]
    restore(rig)
    assert (rig.top.read_bytes(), rig.anchor.read_bytes()) == expected
    assert not missing.exists()
    assert recovery.read_json(rig.directory / recovery.JOURNAL)['phase'] == 'complete'
    if kind == 'backing':
        assert top.read_bytes() == b'foreign image with a missing backing file'


def test_foreign_disk_reference_added_during_copy_refuses_publication(backup_rig, monkeypatch):
    rig = backup_rig
    save(rig)
    rig.top.write_bytes(b'local disk before restoration')
    before = rig.top.read_bytes()
    copy = recovery.copy_file

    def copied(source, destination, **kwargs):
        copy(source, destination, **kwargs)
        if destination.parent == rig.top.parent and '.new-' in destination.name:
            foreign = Mock()
            foreign.UUIDString.return_value = '00000000-0000-0000-0000-000000000001'
            foreign.XMLDesc.return_value = (
                f'<domain><devices><disk><source file="{rig.top}"/></disk></devices></domain>')
            foreign.listAllSnapshots.return_value = []
            foreign.hasCurrentSnapshot.return_value = False
            rig.connection.foreign = [foreign]

    monkeypatch.setattr(recovery, 'copy_file', copied)
    with pytest.raises(base.CaptureError, match='disk-used-by-another-domain'):
        restore(rig)
    assert rig.top.read_bytes() == before
    assert not list(rig.top.parent.glob('.restore-vms-*.previous'))
    assert not rig.connection.definitions
    monkeypatch.setattr(recovery, 'copy_file', copy)
    rig.connection.foreign = []
    restore(rig)
    assert_usable_baseline(rig)


@pytest.mark.parametrize('kind', ['active', 'shared', 'xml-backing', 'symlink', 'parent-symlink'])
def test_missing_foreign_images_do_not_weaken_collision_and_path_guards(backup_rig, kind):
    rig = backup_rig
    save(rig)
    before = rig.top.read_bytes()
    missing = rig.top.parent / 'other-missing.qcow2'
    foreign = Mock()
    foreign.UUIDString.return_value = '00000000-0000-0000-0000-000000000001'
    foreign.ID.return_value = 10 if kind == 'active' else -1
    foreign.listAllSnapshots.return_value = []
    foreign.hasCurrentSnapshot.return_value = False
    if kind == 'shared':
        rig.top.unlink()
        missing = rig.top
    elif kind == 'symlink':
        link = missing.with_suffix('.link')
        link.symlink_to(missing)
        missing = link
    elif kind == 'parent-symlink':
        parent = rig.top.parent / 'foreign-link'
        parent.symlink_to(rig.top.parent, target_is_directory=True)
        missing = parent / missing.name
    backing = f'<backingStore><source file="{rig.anchor}"/></backingStore>' if kind == 'xml-backing' else ''
    foreign.XMLDesc.return_value = f'<domain><devices><disk><source file="{missing}"/>{backing}</disk></devices></domain>'
    rig.connection.foreign = [foreign]
    with pytest.raises(base.CaptureError):
        restore(rig)
    assert not rig.top.exists() if kind == 'shared' else rig.top.read_bytes() == before
    assert not rig.connection.definitions
    assert not (rig.directory / recovery.JOURNAL).exists()


def test_archive_traversal_cannot_write_outside_registered_destinations(backup_rig):
    rig = backup_rig
    archive, manifest, latest = save(rig)
    record = next(item for item in manifest['files'] if item['area'] == 'state')
    record['relative'] = '../outside'
    recovery.atomic(archive / 'manifest.json', manifest)
    latest['sha256'] = recovery.checksum(archive / 'manifest.json')
    recovery.atomic(rig.root / rig.vm.name / 'latest.json', latest)
    before = rig.top.read_bytes()
    with pytest.raises(base.CaptureError, match='archive-path'):
        restore(rig)
    assert rig.top.read_bytes() == before
    assert not rig.connection.definitions


def test_vm_lease_refuses_contention_and_closes_owned_descriptors(backup_rig):
    commands = base.Commands()
    with recovery.lease(backup_rig.vm, commands):
        descriptor = commands.lock_fd
        assert descriptor is not None
        with pytest.raises(base.CaptureError, match='busy-controller'):
            with recovery.lease(backup_rig.vm, base.Commands()):
                pytest.fail('second controller acquired the VM')
    assert commands.lock_fd is None and commands.compatibility_fd is None
    with pytest.raises(OSError):
        os.fstat(descriptor)


@pytest.mark.parametrize('action', ['backupvms', 'restorevms'])
def test_scoped_setup_dispatcher_accepts_only_registered_queue(action, backup_rig, tmp_path):
    helper = runpy.run_path(str(ROOT / 'tools/onpc-setup'))
    checkout = tmp_path / 'checkout'
    (checkout / 'config').mkdir(parents=True)
    (checkout / 'tools').mkdir()
    (checkout / 'config/test-vm.json').write_bytes(vm_config.CONFIG.read_bytes())
    (checkout / 'tools/vm_backup.py').write_text('')
    command = helper['command'](checkout, [action, '--vm', '9,12,Backup-guest'])
    assert command == ['/usr/bin/python3', '-B', str(checkout / 'tools/vm_backup.py'),
                       'backup' if action == 'backupvms' else 'restore', '--vm', 'Backup-guest,Other-guest']
    for args in ([action, '--path', '/etc'], [action, '--vm', 'Unknown'], [action, '--vm', '9', '--vm', '12']):
        with pytest.raises(ValueError):
            helper['command'](checkout, args)


def test_moving_backup_root_does_not_invalidate_preparation_proof(tmp_path):
    import prepare_vm as guest
    for relative in guest.SCRIPT_FILES:
        path = tmp_path / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes((ROOT / relative).read_bytes())
    before = guest.preparation_digest(tmp_path)
    config = tmp_path / 'config/test-vm.json'
    document = json.loads(config.read_text())
    document['backup_root'] = '/replacement-drive/backups'
    config.write_text(json.dumps(document))
    assert guest.preparation_digest(tmp_path) == before


def test_helper_pinning_refuses_unfinished_restore_and_handles_unprepared_vm(tmp_path):
    helper = runpy.run_path(str(ROOT / 'tools/install_test_runner.py'))
    directory = tmp_path / 'baseline'
    directory.mkdir(mode=0o700)
    recovery.atomic(directory / recovery.JOURNAL, {'phase': 'files'})
    with pytest.raises(ValueError, match='unfinished-or-unsafe-vm-restore'):
        helper['pinned_vm_uuid'](directory, owner=os.getuid())
    recovery.atomic(directory / recovery.JOURNAL, {'phase': 'complete'})
    assert helper['pinned_vm_uuid'](directory, owner=os.getuid()) is None


@pytest.mark.skipif(shutil.which('qemu-img') is None, reason='qemu-img host prerequisite is unavailable')
def test_real_qcow2_internal_snapshot_survives_archive_copy(tmp_path):
    # Finite, waited qemu-img children; no libvirt domain, VM or system mutation.
    commands = base.Commands()
    source, copied = tmp_path / 'source.qcow2', tmp_path / 'copy.qcow2'
    commands.run(['qemu-img', 'create', '-f', 'qcow2', str(source), '16M'])
    commands.run(['qemu-img', 'snapshot', '-c', base.SNAPSHOT, str(source)])
    before = commands.info(source)
    recovery.copy_file(source, copied)
    after = commands.info(copied)
    assert before['snapshots'] == after['snapshots']
    assert recovery.checksum(source) == recovery.checksum(copied)
    commands.run(['qemu-img', 'check', '-f', 'qcow2', str(copied)])
