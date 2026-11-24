"""Shared validation of internal VM snapshot metadata and guarded replacement."""

import xml.etree.ElementTree as ET


def read_internal_snapshot(xml, name, identity, require):
    require(isinstance(xml, str) and '<!' not in xml, 'snapshot-xml')
    root = ET.fromstring(xml)
    require(root.tag == 'domainsnapshot' and root.findtext('name') == name, 'snapshot-name')
    memory = root.find('memory')
    require(memory is None or memory.get('snapshot') in ('no', 'internal'), 'external-snapshot-memory')
    require(all(disk.get('snapshot') in ('no', 'internal')
                for disk in root.findall('disks/disk')), 'external-snapshot-disk')
    for domain in root.findall('domain') + root.findall('inactiveDomain'):
        require(domain.findtext('uuid') == identity, 'snapshot-uuid')
    return root


def replacement_snapshots(virsh, identity, disk, target):
    """Accept only snapshots wholly contained in the disk being replaced."""
    def require(condition, detail):
        if not condition:
            raise ValueError(f'VM replacement refused: {detail}')

    names = sorted(virsh('snapshot-list', identity, '--name').splitlines())
    snapshots = {}
    for name in filter(None, names):
        require(name not in snapshots, 'duplicate-snapshot')
        xml = virsh('snapshot-dumpxml', '--domain', identity, '--snapshotname', name)
        root = read_internal_snapshot(xml, name, identity, require)
        memory = root.find('memory')
        require(memory is None or not memory.get('file'), 'snapshot-memory-file')
        domains = root.findall('domain') + root.findall('inactiveDomain')
        require(bool(domains), 'snapshot-domain-missing')
        for domain in domains:
            disks = domain.findall('devices/disk[@device="disk"]')
            require(len(disks) == 1 and disks[0].get('type') == 'file' and
                    disks[0].find('source') is not None and disks[0].find('source').get('file') == str(disk),
                    'snapshot-disk-outside-replacement')
            saved_target = disks[0].find('target')
            require(saved_target is not None and saved_target.get('dev') == target and
                    disks[0].find('backingStore/source') is None, 'snapshot-disk-layout')
        require(all(len(item) == 0 and (item.get('snapshot') == 'no' or item.get('name') == target)
                    for item in root.findall('disks/disk')), 'snapshot-disk-target')
        snapshots[name] = xml
    return snapshots


def undefine_for_replacement(virsh, identity, disk, target, snapshots):
    """Remove the pinned domain and metadata. Its caller erases the QCOW2."""
    if replacement_snapshots(virsh, identity, disk, target) != snapshots:
        raise ValueError('Existing VM snapshots changed while waiting; overwrite refused')
    if virsh('domid', identity).strip() != '-':
        raise ValueError('Existing VM is active; overwrite refused')
    options = ('--snapshots-metadata',) if snapshots else ()
    virsh('undefine', identity, *options)
