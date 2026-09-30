"""Rename only the idle pinned VM's single image to its configured VM name.

Internal snapshots are metadata-redefined, never deleted or restored. A private
journal preserves exact rollback inputs and refuses interrupted transactions.
The caller updates the checkout's disk_anchor after successful completion.
"""

import copy
import os
from pathlib import Path
import stat
import tempfile
import xml.etree.ElementTree as ET

import system_runner as runner
from vm_control import acquire_idle, same_xml
from watch_activity import operation


def save_private(lease, name, data):
    base = runner.baseline
    base.require(lease.capture.private_directory() == lease.capture.directory_identity,
                 'guard:directory-changed')
    fd, temporary = tempfile.mkstemp(prefix='.disk-rename-', dir=lease.directory)
    with os.fdopen(fd, 'wb') as stream:
        stream.write(base.encode(data))
        stream.flush()
        os.fsync(stream.fileno())
    os.replace(temporary, lease.directory / name)
    base.sync_directory(lease.directory)


def disk_xml(xml, old, new, expected_uuid, *, snapshot=False):
    """Change only the single internal image reference on this exact UUID."""
    base = runner.baseline
    base.require('<!' not in xml, 'vm-control:disk-xml')
    root = ET.fromstring(xml)
    domains = root.findall('domain') + root.findall('inactiveDomain') if snapshot else [root]
    base.require(bool(domains), 'vm-control:disk-domain-missing')
    for domain in domains:
        base.require(domain.tag == 'domain' or domain.tag == 'inactiveDomain', 'vm-control:disk-domain')
        base.require(len(domain.findall('uuid')) == 1 and domain.findtext('uuid') == expected_uuid,
                     'vm-control:disk-uuid')
        disks = [disk for disk in domain.findall('devices/disk') if disk.get('device') == 'disk']
        base.require(len(disks) == 1, 'vm-control:disk-count')
        disk = disks[0]
        sources = disk.findall('source')
        base.require(disk.get('type') == 'file' and len(sources) == 1 and
                     sources[0].get('file') == str(old) and
                     disk.find('driver') is not None and disk.find('driver').get('type') == 'qcow2' and
                     not any(disk.find(key) is not None for key in
                             ('mirror', 'dataStore', 'encryption', 'auth')) and
                     not disk.findall('backingStore/source'), 'vm-control:disk-layout')
        sources[0].set('file', str(new))
    if snapshot:
        memory = root.find('memory')
        base.require(memory is not None and memory.get('snapshot') in ('no', 'internal'),
                     'vm-control:disk-external-memory')
        base.require(all(disk.get('snapshot') in ('no', 'internal') and len(disk) == 0
                         for disk in root.findall('disks/disk')), 'vm-control:disk-external-snapshot')
    return ET.tostring(root, encoding='unicode')


def move_image(old, new, expected):
    """Same-directory move with exclusive destination creation and stable inode.

Link/unlink uses public filesystem APIs and never overwrites a destination.
An interrupted two-link phase remains recorded and refuses ordinary controllers.
"""
    base = runner.baseline
    base.require(old.parent == new.parent and base.identity(old) == expected,
                 'vm-control:disk-source-changed')
    descriptor = os.open(old.parent, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
    try:
        os.link(old.name, new.name, src_dir_fd=descriptor, dst_dir_fd=descriptor,
                follow_symlinks=False)
        os.fsync(descriptor)
        for name in (old.name, new.name):
            info = os.stat(name, dir_fd=descriptor, follow_symlinks=False)
            base.require(stat.S_ISREG(info.st_mode) and info.st_nlink == 2 and
                         (info.st_dev, info.st_ino) == (expected['device'], expected['inode']),
                         'vm-control:disk-link-changed')
        os.unlink(old.name, dir_fd=descriptor)
        os.fsync(descriptor)
    finally:
        os.close(descriptor)
    base.require(base.identity(new) == {**expected, 'path': str(new)} and not os.path.lexists(old),
                 'vm-control:disk-move-result')


def snapshots(source):
    return sorted((item.getName(), item.getXMLDesc(0)) for item in source.domain.listAllSnapshots(0))


def guard(lease):
    source = lease.source
    base = runner.baseline
    base.require(source.connection.getURI() == 'qemu:///system' and
                 source.domain.UUIDString() == source.uuid and source.domain.name() == base.DOMAIN and
                 source.domain.ID() == -1 and not source.domain.autostart() and
                 not source.domain.hasManagedSaveImage(0), 'vm-control:disk-identity')
    base.require(lease.capture.private_directory() == lease.capture.directory_identity,
                 'guard:directory-changed')
    if lease.capture.vm_ownership is not None:
        lease.capture.vm_ownership.check_owner()


def rename_disk(lease):
    base = runner.baseline
    with operation('VM maintenance: rename disk to VM name'):
        acquire_idle(lease)
        source, capture = lease.source, lease.capture
        guard(lease)
        original_state = copy.deepcopy(capture.state)
        chain = original_state['source']['chain']
        old = capture.anchor
        base.require(len(chain) == 1 and chain[0]['path'] == str(old) and
                     original_state['source']['layout']['disk'] == str(old),
                     'vm-control:disk-rename-requires-single-image')
        base.guest_contract.vm_config.validate_name(base.DOMAIN)
        new = old.with_name(base.DOMAIN + '.qcow2')
        base.require(new != old, 'vm-control:disk-already-named')
        base.canonical(old.parent)
        base.require(not os.path.lexists(new), 'vm-control:disk-destination-exists')
        # Refuse shared disks rather than changing another guest's resources.
        for domain in source.connection.listAllDomains(0):
            if domain.UUIDString() == source.uuid:
                continue
            for flags in (0, source.api.VIR_DOMAIN_XML_INACTIVE):
                xml = domain.XMLDesc(flags)
                base.require('<!' not in xml, 'vm-control:disk-other-domain-xml')
                base.require(not any(node.get('file') in (str(old), str(new))
                                     for node in ET.fromstring(xml).iter('source')),
                             'vm-control:disk-shared')
        original_xml = source.domain.XMLDesc(source.api.VIR_DOMAIN_XML_INACTIVE)
        expected_xml = disk_xml(original_xml, old, new, source.uuid)
        originals = snapshots(source)
        expected = [(name, disk_xml(xml, old, new, source.uuid, snapshot=True))
                    for name, xml in originals]
        validated = [(name, disk_xml(capture.proven_snapshot_xml(xml), old, new,
                                    source.uuid, snapshot=True)) for name, xml in originals]
        current = source.domain.snapshotCurrent(0).getName() if source.domain.hasCurrentSnapshot(0) else None
        identity = base.identity(old)
        record = {'phase': 'requested', 'domain_uuid': source.uuid, 'old_path': str(old), 'new_path': str(new),
                  'original_xml': original_xml, 'original_state': original_state,
                  'snapshots': originals, 'renamed_snapshots': expected, 'validated_snapshots': validated,
                  'current_snapshot': current}
        journal = 'disk-rename-' + lease.ownership_run + '.json'
        save_private(lease, journal, record)

        def redefine(values):
            for name, xml in values:
                guard(lease)
                flags = source.api.VIR_DOMAIN_SNAPSHOT_CREATE_REDEFINE
                if name == current:
                    flags |= source.api.VIR_DOMAIN_SNAPSHOT_CREATE_CURRENT
                source.domain.snapshotCreateXML(xml, flags)
                base.require(same_xml(source.domain.snapshotLookupByName(name, 0).getXMLDesc(0), xml),
                             'vm-control:disk-snapshot-result')

        try:
            capture.revalidate(off=True)
            guard(lease)
            base.require(source.domain.XMLDesc(source.api.VIR_DOMAIN_XML_INACTIVE) == original_xml and
                         snapshots(source) == originals, 'vm-control:disk-source-changed')
            # End the attested interval before the recorded path transition.
            capture.retire_vm_ownership()
            capture.vm_ownership = None
            move_image(old, new, identity)
            guard(lease)
            source.connection.defineXML(expected_xml)
            source.domain = source.connection.lookupByUUIDString(source.uuid)
            guard(lease)
            base.require(same_xml(source.domain.XMLDesc(source.api.VIR_DOMAIN_XML_INACTIVE), expected_xml),
                         'vm-control:disk-domain-result')
            redefine(expected)
            base.require([(name, ET.canonicalize(xml, strip_text=True)) for name, xml in snapshots(source)] ==
                         [(name, ET.canonicalize(xml, strip_text=True)) for name, xml in expected],
                         'vm-control:disk-snapshot-set-changed')
            base.require((source.domain.snapshotCurrent(0).getName() if source.domain.hasCurrentSnapshot(0)
                          else None) == current, 'vm-control:disk-current-snapshot-changed')
            record['phase'] = 'references-updated'
            save_private(lease, journal, record)
            capture.anchor = new
            capture.state = copy.deepcopy(original_state)
            capture.state['source']['layout']['disk'] = str(new)
            capture.state['source']['chain'][0]['path'] = str(new)
            # Legacy digests are a chain-ordered list; the bytes and order stay
            # unchanged, and ordinary backing verification never hashes them.
            capture.revalidate(off=True)
            capture.begin_vm_ownership(lease)
            capture.verify_snapshot()
            save_private(lease, 'phase.json', capture.state)
            record['phase'] = 'complete'
            save_private(lease, journal, record)
        except BaseException:
            # Revert only exact owned XML/inodes; an unexpected replacement
            # leaves the pending record as an explicit recovery blocker.
            guard(lease)
            capture.retire_vm_ownership()
            capture.vm_ownership = None
            actual = source.domain.XMLDesc(source.api.VIR_DOMAIN_XML_INACTIVE)
            base.require(same_xml(actual, original_xml) or same_xml(actual, expected_xml),
                         'vm-control:disk-rollback-domain-changed')
            known = dict(originals)
            replacements = dict(expected)
            base.require({name for name, _ in snapshots(source)} == set(known),
                         'vm-control:disk-rollback-snapshot-set')
            for name, xml in snapshots(source):
                base.require(same_xml(xml, known[name]) or same_xml(xml, replacements[name]),
                             'vm-control:disk-rollback-snapshot-changed')
            if os.path.lexists(old):
                old_info = old.lstat()
                base.require(stat.S_ISREG(old_info.st_mode) and
                             (old_info.st_dev, old_info.st_ino) == (identity['device'], identity['inode']),
                             'vm-control:disk-rollback-file-changed')
                if os.path.lexists(new):
                    new_info = new.lstat()
                    if (new_info.st_dev, new_info.st_ino) == (identity['device'], identity['inode']):
                        base.require(stat.S_ISREG(new_info.st_mode) and old_info.st_nlink == new_info.st_nlink == 2,
                                     'vm-control:disk-rollback-link-changed')
                        new.unlink()
                        base.sync_directory(new.parent)
                base.require(base.identity(old) == identity, 'vm-control:disk-rollback-file-changed')
            elif os.path.lexists(new):
                move_image(new, old, {**identity, 'path': str(new)})
            else:
                base.require(False, 'vm-control:disk-rollback-file-missing')
            source.connection.defineXML(original_xml)
            source.domain = source.connection.lookupByUUIDString(source.uuid)
            redefine(originals)
            capture.anchor, capture.state = old, original_state
            save_private(lease, 'phase.json', original_state)
            # Do not clear latched failures from verification; restore metadata
            # using the pure proof check, then report the original failure.
            capture.revalidate(off=True)
            base.require(same_xml(source.domain.XMLDesc(source.api.VIR_DOMAIN_XML_INACTIVE), original_xml),
                         'vm-control:disk-rollback-result')
            base.require(capture._verify_snapshot() == original_state['proof'],
                         'vm-control:disk-rollback-proof')
            record['phase'] = 'rolled-back'
            save_private(lease, journal, record)
            raise
