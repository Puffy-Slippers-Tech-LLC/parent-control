"""Run-owned libvirt tap filter; never changes guest or shared network settings.

Binding creation/deletion are the public libvirt nwfilter APIs. Durable intent
precedes each mutation; recovery only removes exact recorded resources.
"""
import ipaddress
import re
import uuid
import xml.etree.ElementTree as ET

from owned_commands import require
from watch_activity import observed


def signature(xml):
    def node(item):
        attrs = dict(item.attrib)
        if item.tag == 'filter' and attrs.get('priority') == '0':
            del attrs['priority']  # libvirt omits the default root priority.
        if item.tag == 'mac' and 'protocolid' in attrs:
            value = attrs['protocolid']
            attrs['protocolid'] = str(0x0800 if value == 'ipv4' else int(value, 0))
        return item.tag, tuple(sorted(attrs.items())), (item.text or '').strip(), tuple(map(node, item))
    return node(ET.fromstring(xml))


def filter_xml(record):
    root = ET.Element('filter', name=record['name'], chain='root', priority='0')
    ET.SubElement(root, 'uuid').text = record['uuid']
    def rule(protocol, direction, priority, **attrs):
        item = ET.SubElement(root, 'rule', action='accept', direction=direction,
                             priority=str(priority))
        ET.SubElement(item, protocol, **attrs)
    host, guest = record['controller'], record['guest']
    # Only the host bridge and this guest may resolve each other. No DNS,
    # host proxy, guest-initiated SSH, or broad established-flow exemption.
    rule('arp', 'in', 100, arpsrcipaddr=host, arpdstipaddr=guest)
    rule('arp', 'out', 100, arpsrcipaddr=guest, arpdstipaddr=host)
    rule('tcp', 'in', 200, srcipaddr=host, dstipaddr=guest, dstportstart='22')
    # Default state matching emits replies only for host-initiated SSH.
    # No outbound TCP accept is required or permitted.
    for protocol in ('all', 'all-ipv6'):
        ET.SubElement(ET.SubElement(root, 'rule', action='drop', direction='inout',
                                   priority='900'), protocol)
    # Deny other Ethernet protocols/encapsulation; ARP accepted above.
    ET.SubElement(ET.SubElement(root, 'rule', action='drop', direction='inout',
                               priority='1000'), 'mac', match='no', protocolid='0x0800')
    return ET.tostring(root, encoding='unicode')


def binding_xml(record, domain_uuid):
    root = ET.Element('filterbinding')
    owner = ET.SubElement(root, 'owner')
    ET.SubElement(owner, 'name').text = record['domain_name']
    ET.SubElement(owner, 'uuid').text = domain_uuid
    ET.SubElement(root, 'portdev', name=record['tap'])
    ET.SubElement(root, 'mac', address=record['mac'])
    reference = ET.SubElement(root, 'filterref', filter=record['name'])
    ET.SubElement(reference, 'parameter', name='MAC', value=record['mac'])
    return ET.tostring(root, encoding='unicode')


def fresh_domain(lease):
    lease.guard()
    # virDomain.ID() is cached in the handle, including across snapshot revert.
    # Resolve the pinned identity without adopting a replacement instance ID.
    domain = lease.source.connection.lookupByUUIDString(lease.state['domain_uuid'])
    require(domain.UUIDString() == lease.state['domain_uuid'], 'internet:domain-identity')
    return domain


def network_configuration(xml):
    root = ET.fromstring(xml)
    require(root.tag == 'network', 'internet:network-xml')
    opening = re.match(r'<network\b[^>]*>', xml)
    require(opening is not None, 'internet:network-xml')
    if 'connections' not in root.attrib:
        return xml
    require(re.fullmatch(r'[0-9]+', root.get('connections')), 'internet:network-xml')
    # Only the read-only root interface count may change. Preserve every other
    # byte, including nested attributes, metadata and trailing whitespace.
    normalized, count = re.subn(r'\s+connections\s*=\s*([\'\"])[0-9]+\1',
                               '', opening.group(), count=1)
    require(count == 1, 'internet:network-xml')
    return normalized + xml[opening.end():]


def network_identity(lease, *, running, restored_original=False, domain=None):
    lease.guard()
    domain = fresh_domain(lease) if domain is None else domain
    require(domain.UUIDString() == lease.state['domain_uuid'] and
            (not running or domain.ID() == lease.state['domain_id'] >= 0),
            'internet:domain-identity')
    xml = domain.XMLDesc(0)
    require(not restored_original or (not running and xml == lease.state['original_xml']),
            'internet:original-configuration-changed')
    root = ET.fromstring(xml)
    nics = root.findall('devices/interface')
    require(len(nics) == 1 and nics[0].get('type') == 'network', 'internet:nic-layout')
    nic = nics[0]
    source, mac, target = nic.find('source'), nic.find('mac'), nic.find('target')
    require(source is not None and source.get('network') == 'default'
            and (restored_original or not nic.findall('filterref')) and mac is not None
            and re.fullmatch(r'(?:[0-9a-f]{2}:){5}[0-9a-f]{2}', mac.get('address', '')),
            'internet:nic-identity')
    original = ET.fromstring(lease.state['original_xml']).findall('devices/interface')
    require(len(original) == 1 and original[0].find('mac') is not None and
            original[0].find('mac').attrib == mac.attrib and
            original[0].find('source').get('network') == 'default', 'internet:nic-replaced')
    net = lease.source.connection.networkLookupByName('default')
    require(net.isActive(), 'internet:network-inactive')
    net_xml = net.XMLDesc(0)
    network = ET.fromstring(net_xml)
    bridge = network.find('bridge')
    require(bridge is not None and bridge.get('name') and
            (not running or (source.get('bridge') == bridge.get('name') and
                target is not None and re.fullmatch(r'vnet[0-9]+', target.get('dev', '')))),
            'internet:network-identity')
    return {'domain_name': domain.name(), 'mac': mac.get('address'),
            'network_uuid': net.UUIDString(), 'network_xml': net_xml,
            'bridge': bridge.get('name'),
            'tap': target.get('dev') if target is not None else None}


def resources(lease, record):
    connection = lease.source.connection
    filters = connection.listAllNWFilters(0)
    matches = [item for item in filters
               if item.name() == record['name'] or item.UUIDString() == record['uuid']]
    require(len(matches) <= 1, 'internet:filter-collision')
    owned = matches[0] if matches else None
    if owned is not None:
        require(owned.name() == record['name'] and owned.UUIDString() == record['uuid']
                and signature(owned.XMLDesc(0)) == signature(filter_xml(record)),
                'internet:filter-changed')
    bindings = connection.listAllNWFilterBindings(0)
    matches = [item for item in bindings if item.portDev() == record['tap']]
    require(len(matches) <= 1, 'internet:binding-collision')
    binding = matches[0] if matches else None
    if binding is not None:
        require(owned is not None and signature(binding.XMLDesc(0)) ==
                signature(binding_xml(record, lease.state['domain_uuid'])),
                'internet:binding-changed')
    require(all(item.portDev() == record['tap'] or item.filterName() != record['name']
                for item in bindings), 'internet:foreign-reference')
    # A foreign configured domain must never gain a reference to our filter.
    for domain in connection.listAllDomains(0):
        for flags in (0, lease.source.api.VIR_DOMAIN_XML_INACTIVE):
            require(not any(item.get('filter') == record['name'] for item in
                            ET.fromstring(domain.XMLDesc(flags)).findall('devices/interface/filterref')),
                    'internet:domain-reference')
    return owned, binding


def validate_record(lease, record):
    require(type(record) is dict and set(record) == {
        'name', 'uuid', 'controller', 'guest', 'domain_name', 'mac', 'network_uuid',
        'network_xml', 'bridge', 'tap', 'phase'} and
        record['name'] == 'onpc-internet-' + lease.state['run'] and
        record['uuid'] == str(uuid.uuid5(uuid.UUID(lease.state['domain_uuid']), lease.state['run'])) and
        record['phase'] in ('define-requested', 'bind-requested', 'offline',
                            'restore-requested', 'restored'), 'internet:journal')
    require(all(type(record[key]) is str for key in record), 'internet:journal')
    require(re.fullmatch(r'vnet[0-9]+', record['tap']) and
            re.fullmatch(r'(?:[0-9a-f]{2}:){5}[0-9a-f]{2}', record['mac']), 'internet:journal')
    for key in ('controller', 'guest'):
        address = ipaddress.ip_address(record[key])
        require(address.version == 4 and address.is_private and not address.is_loopback,
                'internet:journal')
    domain = fresh_domain(lease)
    running = domain.ID() != -1
    current = network_identity(lease, running=running,
        restored_original=not running and record['phase'] == 'restored' and
        domain.XMLDesc(0) == lease.state['original_xml'], domain=domain)
    require(network_configuration(current['network_xml']) ==
            network_configuration(record['network_xml']), 'internet:identity-changed')
    require(all(current[key] == record[key] for key in current
                if key != 'network_xml' and (key != 'tap' or running)), 'internet:identity-changed')
    if not running:
        # A stale tap name may have been reused. Never delete its new binding
        # or manipulate an interface now attached to any other running guest.
        for domain in lease.source.connection.listAllDomains(0):
            if domain.ID() != -1:
                require(not any(item.get('dev') == record['tap'] for item in
                                ET.fromstring(domain.XMLDesc(0)).findall('devices/interface/target')),
                        'internet:tap-reused')


class InternetIsolation:
    def __init__(self, lease):
        self.lease = lease

    @observed('Removing Internet access from the owned VM')
    def enter(self, transport):
        lease = self.lease
        require('internet_isolation' not in lease.state, 'internet:uncertain-replay')
        require(all(transport.config.get(key) == lease.state[key]
                    for key in ('domain_uuid', 'domain_id', 'run')), 'internet:transport-identity')
        identity = network_identity(lease, running=True)
        raw = transport.call(['/usr/bin/python3', '-c',
            'import os; print(os.environ["SSH_CONNECTION"].split()[0])'])
        controller = raw.decode('ascii').strip()
        guest = transport.config['hostname']
        network = ET.fromstring(identity['network_xml'])
        require(controller in [item.get('address') for item in network.findall('ip')
                               if item.get('family', 'ipv4') == 'ipv4'],
                'internet:controller-address')
        for address in (controller, guest):
            value = ipaddress.ip_address(address)
            require(value.version == 4 and value.is_private and not value.is_loopback,
                    'internet:address')
        record = {**identity, 'controller': controller, 'guest': guest,
                  'name': 'onpc-internet-' + lease.state['run'],
                  'uuid': str(uuid.uuid5(uuid.UUID(lease.state['domain_uuid']), lease.state['run'])),
                  'phase': 'define-requested'}
        require(resources(lease, record) == (None, None), 'internet:resource-exists')
        lease.state['internet_isolation'] = record
        lease.save(lease.state['phase'])
        validate_record(lease, record)
        lease.source.connection.nwfilterDefineXML(filter_xml(record))
        require(resources(lease, record)[0] is not None, 'internet:filter-missing')
        record['phase'] = 'bind-requested'
        lease.save(lease.state['phase'])
        validate_record(lease, record)
        lease.source.connection.nwfilterBindingCreateXML(
            binding_xml(record, lease.state['domain_uuid']), 0)
        require(resources(lease, record)[1] is not None, 'internet:binding-missing')
        record['phase'] = 'offline'
        lease.save(lease.state['phase'])
        validate_record(lease, record)

    def __enter__(self):
        return self

    def __exit__(self, *_):
        restore(self.lease)


@observed('Restoring the owned VM Internet connection')
def restore(lease):
    if lease.state is None:
        return  # No attempt acquired; no Internet resource can have been created.
    record = lease.state.get('internet_isolation')
    if record is None:
        return
    validate_record(lease, record)
    owned, binding = resources(lease, record)
    if record['phase'] == 'restored':
        require(owned is None and binding is None, 'internet:restored-resource-reappeared')
        return
    record['phase'] = 'restore-requested'
    lease.save(lease.state['phase'])
    validate_record(lease, record)
    if binding is not None:
        binding.delete()
    owned, binding = resources(lease, record)
    require(binding is None, 'internet:binding-remained')
    validate_record(lease, record)
    if owned is not None:
        owned.undefine()
    require(resources(lease, record) == (None, None), 'internet:resource-remained')
    record['phase'] = 'restored'
    lease.save(lease.state['phase'])
