"""Private journals and in-memory libvirt doubles; never changes networking."""
from copy import deepcopy
import json
from types import SimpleNamespace
from unittest.mock import Mock
import xml.etree.ElementTree as ET

import pytest
from owned_commands import CommandError
import vm_internet as network
import vm_internet_qualification as qualification
from tests.support.vm_baseline import local_preparation_source

DOMAIN_UUID = 'aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee'
NETWORK_UUID = '11111111-2222-3333-4444-555555555555'
DOMAIN_XML = '''<domain><devices><interface type="network"><mac address="52:54:00:11:22:33"/>
<source network="default" bridge="virbr0"/><target dev="vnet7"/></interface></devices></domain>'''
NETWORK_XML = '''<network><bridge name="virbr0"/><ip address="192.168.122.1"/></network>'''


class Filter:
    def __init__(self, connection, xml):
        # Model libvirt's canonical read-back rather than echoing input XML.
        root = ET.fromstring(xml)
        if root.get('priority') == '0':
            del root.attrib['priority']
        for item in root.findall('rule/mac'):
            if item.get('protocolid') == '0x0800':
                item.set('protocolid', 'ipv4')
        xml = ET.tostring(root, encoding='unicode')
        self.connection, self.xml = connection, xml
    def name(self): return ET.fromstring(self.xml).get('name')
    def UUIDString(self): return ET.fromstring(self.xml).findtext('uuid')
    def XMLDesc(self, _): return self.xml
    def undefine(self):
        self.connection.filters.remove(self)
        self.connection.after('undefine')


class Binding:
    def __init__(self, connection, xml):
        self.connection, self.xml = connection, xml
    def portDev(self): return ET.fromstring(self.xml).find('portdev').get('name')
    def filterName(self): return ET.fromstring(self.xml).find('filterref').get('filter')
    def XMLDesc(self, _): return self.xml
    def delete(self):
        self.connection.bindings.remove(self)
        self.connection.after('delete')


class Connection:
    def __init__(self, domain):
        self.domain, self.filters, self.bindings = domain, [], []
        self.fail = None
        self.calls = []
        self.net_xml = NETWORK_XML
        self.net_uuid = NETWORK_UUID
        self.extra_domains = []
    def after(self, stage):
        self.calls.append(stage)
        if self.fail == stage:
            self.fail = None
            raise KeyboardInterrupt()
    def listAllNWFilters(self, _): return self.filters.copy()
    def listAllNWFilterBindings(self, _): return self.bindings.copy()
    def listAllDomains(self, _): return [self.domain, *self.extra_domains]
    def networkLookupByName(self, name):
        assert name == 'default'
        return SimpleNamespace(isActive=lambda: True, UUIDString=lambda: self.net_uuid,
                               XMLDesc=lambda _: self.net_xml)
    def nwfilterDefineXML(self, xml):
        result = Filter(self, xml)
        self.filters.append(result)
        self.after('define')
        return result
    def nwfilterBindingCreateXML(self, xml, _):
        result = Binding(self, xml)
        self.bindings.append(result)
        self.after('bind')
        return result


@pytest.fixture
def rig(tmp_path):
    domain = Mock()
    domain.UUIDString.return_value = DOMAIN_UUID
    domain.ID.return_value = 9
    domain.name.return_value = 'fixture-vm'
    domain.XMLDesc.return_value = DOMAIN_XML
    connection = Connection(domain)
    lease = SimpleNamespace(
        source=SimpleNamespace(domain=domain, connection=connection,
                               api=SimpleNamespace(VIR_DOMAIN_XML_INACTIVE=2)),
        state={'domain_uuid': DOMAIN_UUID, 'domain_id': 9, 'run': 'a' * 32,
               'phase': 'running', 'original_xml': DOMAIN_XML}, guard=Mock())
    journal = tmp_path / 'journal.json'
    def save(phase):
        lease.state['phase'] = phase
        journal.write_text(json.dumps(lease.state))
    lease.save = Mock(side_effect=save)
    transport = Mock(config={'domain_uuid': DOMAIN_UUID, 'domain_id': 9,
                             'run': 'a' * 32, 'hostname': '192.168.122.20'})
    transport.call.return_value = b'192.168.122.1\n'
    return lease, connection, transport, journal


def test_isolation_keeps_config_unchanged_and_restores_only_owned_resources(rig):
    lease, connection, transport, journal = rig
    unrelated = Filter(connection, '<filter name="foreign"><uuid>foreign</uuid></filter>')
    connection.filters.append(unrelated)
    network.InternetIsolation(lease).enter(transport)
    assert json.loads(journal.read_text())['internet_isolation']['phase'] == 'offline'
    assert connection.domain.XMLDesc(0) == DOMAIN_XML and connection.net_xml == NETWORK_XML
    network.restore(lease)
    assert connection.filters == [unrelated] and connection.bindings == []
    assert connection.calls == ['define', 'bind', 'delete', 'undefine']
    network.restore(lease)
    assert connection.calls == ['define', 'bind', 'delete', 'undefine']


@pytest.mark.parametrize('stage', ['define', 'bind', 'delete', 'undefine'])
def test_uncertain_mutation_recovers_from_durable_intent_without_replay(rig, stage):
    lease, connection, transport, journal = rig
    connection.fail = stage
    with pytest.raises(KeyboardInterrupt):
        network.InternetIsolation(lease).enter(transport)
        network.restore(lease)
    lease.state = json.loads(journal.read_text())
    before = connection.calls.copy()
    with pytest.raises(CommandError, match='uncertain-replay'):
        network.InternetIsolation(lease).enter(transport)
    assert connection.calls == before
    network.restore(lease)
    assert not connection.filters and not connection.bindings
    assert lease.state['internet_isolation']['phase'] == 'restored'
    assert connection.calls.count(stage) == 1


@pytest.mark.parametrize('write', [1, 2, 3, 4, 5])
def test_journal_failure_never_loses_external_resource_cleanup(rig, write):
    lease, connection, transport, journal = rig
    save = lease.save.side_effect
    writes = []
    def fail(phase):
        writes.append(phase)
        if len(writes) == write:
            raise OSError('durability')
        save(phase)
    lease.save.side_effect = fail
    with pytest.raises(OSError, match='durability'):
        network.InternetIsolation(lease).enter(transport)
        network.restore(lease)
    lease.save.side_effect = save
    if journal.exists():
        lease.state = json.loads(journal.read_text())
    network.restore(lease)
    assert not connection.filters and not connection.bindings


@pytest.mark.parametrize('fault', ['domain', 'instance', 'transport', 'mac', 'extra-nic',
                                  'network', 'tap', 'owner', 'controller'])
def test_wrong_entry_refuses_before_journal_or_mutation(rig, fault):
    lease, connection, transport, journal = rig
    if fault == 'domain': connection.domain.UUIDString.return_value = NETWORK_UUID
    elif fault == 'instance': connection.domain.ID.return_value = 10
    elif fault == 'transport': transport.config['run'] = 'b' * 32
    elif fault == 'mac': connection.domain.XMLDesc.return_value = DOMAIN_XML.replace('11:22:33', '11:22:44')
    elif fault == 'extra-nic': connection.domain.XMLDesc.return_value = DOMAIN_XML.replace('</devices>', '<interface/></devices>')
    elif fault == 'network': connection.domain.XMLDesc.return_value = DOMAIN_XML.replace('default', 'other')
    elif fault == 'tap': connection.domain.XMLDesc.return_value = DOMAIN_XML.replace('vnet7', 'eth0')
    elif fault == 'owner': lease.guard.side_effect = CommandError('lost-owner')
    else: transport.call.return_value = b'192.168.122.99\n'
    with pytest.raises(CommandError): network.InternetIsolation(lease).enter(transport)
    assert not journal.exists() and not connection.calls


@pytest.mark.parametrize('fault', ['filter', 'priority', 'binding', 'network-uuid', 'network-xml',
                                  'foreign-binding', 'foreign-domain', 'tap-reuse', 'journal'])
def test_changed_ownership_refuses_cleanup_without_touching_evidence(rig, fault):
    lease, connection, transport, journal = rig
    network.InternetIsolation(lease).enter(transport)
    record = lease.state['internet_isolation']
    if fault == 'filter': connection.filters[0].xml = connection.filters[0].xml.replace('dstportstart="22"', 'dstportstart="80"')
    elif fault == 'priority':
        root = ET.fromstring(connection.filters[0].xml)
        root.set('priority', '1')
        connection.filters[0].xml = ET.tostring(root, encoding='unicode')
    elif fault == 'binding': connection.bindings[0].xml = connection.bindings[0].xml.replace('fixture-vm', 'foreign')
    elif fault == 'network-uuid': connection.net_uuid = DOMAIN_UUID
    elif fault == 'network-xml': connection.net_xml += ' '
    elif fault == 'foreign-binding':
        connection.bindings.append(Binding(connection, connection.bindings[0].xml.replace('vnet7', 'vnet8')))
    elif fault == 'foreign-domain':
        connection.extra_domains.append(Mock(XMLDesc=Mock(return_value=DOMAIN_XML.replace('</interface>',
            '<filterref filter="' + record['name'] + '"/></interface>'))))
    elif fault == 'tap-reuse':
        connection.domain.ID.return_value = -1
        connection.extra_domains.append(Mock(ID=Mock(return_value=10), XMLDesc=Mock(return_value=DOMAIN_XML)))
    else: record['uuid'] = NETWORK_UUID
    before = journal.read_bytes(), connection.calls.copy()
    with pytest.raises(CommandError): network.restore(lease)
    assert (journal.read_bytes(), connection.calls) == before
    assert connection.filters and connection.bindings


def test_already_off_cleanup_removes_exact_orphan_and_filter(rig):
    lease, connection, transport, _ = rig
    network.InternetIsolation(lease).enter(transport)
    connection.domain.ID.return_value = -1
    network.restore(lease)
    assert not connection.filters and not connection.bindings


def test_off_cleanup_accepts_binding_already_retired_by_libvirt(rig):
    lease, connection, transport, _ = rig
    network.InternetIsolation(lease).enter(transport)
    connection.domain.ID.return_value = -1
    connection.bindings.clear()
    network.restore(lease)
    assert not connection.filters


def test_policy_only_allows_controller_inbound_ssh_and_exact_arp(rig):
    lease, connection, transport, _ = rig
    network.InternetIsolation(lease).enter(transport)
    root = ET.fromstring(connection.filters[0].xml)
    accepts = [rule for rule in root.findall('rule') if rule.get('action') == 'accept']
    assert [rule[0].tag for rule in accepts] == ['arp', 'arp', 'tcp']
    tcp = accepts[-1]
    assert tcp.get('direction') == 'in' and tcp.get('statematch') is None
    assert tcp[0].attrib == {'srcipaddr': '192.168.122.1', 'dstipaddr': '192.168.122.20', 'dstportstart': '22'}
    drops = [rule for rule in root.findall('rule') if rule.get('action') == 'drop']
    assert [rule[0].tag for rule in drops] == ['all', 'all-ipv6', 'mac']
    assert all(rule.get('direction') == 'inout' for rule in drops)
    assert not root.findall('filterref')


def probe_result(online):
    return {'ipv6_default_route': False, 'probes': [
        {'family': 4, 'address': address, 'protocol': protocol, 'reachable': online}
        for address in ('1.1.1.1', '8.8.8.8') for protocol in ('tcp', 'udp-dns')]}


@pytest.mark.parametrize('fault', [None, 'offline-reachable', 'online-unreachable', 'restore', 'ui'])
def test_fixed_sequence_checks_independent_results_and_unwinds_on_failure(rig, monkeypatch, fault):
    lease, connection, transport, _ = rig
    before, offline, after = probe_result(True), probe_result(False), probe_result(True)
    if fault == 'offline-reachable': offline['probes'][0]['reachable'] = True
    elif fault == 'online-unreachable': before['probes'][1]['reachable'] = False
    elif fault == 'restore': after['probes'][1]['reachable'] = False
    monkeypatch.setattr(qualification, 'internet_result', Mock(side_effect=[before, offline, after]))
    controller = Mock(side_effect=CommandError('ui:refused') if fault == 'ui' else None)
    monkeypatch.setattr(qualification, 'controller_result', controller)
    journey = SimpleNamespace(context=SimpleNamespace(lease=lease), transport=transport)
    if fault:
        with pytest.raises(CommandError): qualification.online_offline_online(journey, Mock())
    else:
        assert qualification.online_offline_online(journey, Mock())['interruption_cleanup']
        assert controller.call_count == 2
    assert not connection.bindings and not connection.filters
    assert len(connection.calls) == (0 if fault == 'online-unreachable' else 4)


@pytest.mark.parametrize('fault', [None, 'missing', 'extra', 'identity', 'boolean'])
def test_real_probe_decoder_refuses_incomplete_or_changed_results(fault):
    value = probe_result(True)
    if fault == 'missing': value['probes'].pop()
    elif fault == 'extra': value['private'] = 'no'
    elif fault == 'identity': value['probes'][0]['address'] = 'localhost'
    elif fault == 'boolean': value['probes'][0]['reachable'] = 1
    transport = Mock(call=Mock(return_value=json.dumps(value).encode()))
    if fault:
        with pytest.raises(CommandError): qualification.internet_result(transport)
    else: assert qualification.internet_result(transport) == value


def test_selector_and_installed_envelope_share_existing_worker(monkeypatch, tmp_path):
    import check_e2e_independent_network_management as selector
    import check_graphical_smoke as smoke
    import parent_setup_qualification as setup
    from fresh_desktop import PARENT_PLAN
    run = Mock(return_value=0)
    monkeypatch.setattr(selector, 'smoke', run)
    assert selector.main() == 0
    assert run.call_args.kwargs['independent_network'] is True
    with pytest.raises(CommandError, match='independent-network-prerequisites'):
        smoke.main(independent_network=True)
    journey = setup.IndependentNetworkQualification.journey(SimpleNamespace(directory=tmp_path), Mock())
    assert journey.plan.worker_mode == PARENT_PLAN.worker_mode
    assert journey.plan.screen_tags == PARENT_PLAN.screen_tags
    assert journey.actions == {'independent-network': qualification.qualify}
    assert setup.IndependentNetworkQualification.attach_installed_snapshot is setup.KioskEntryQualification.attach_installed_snapshot


@pytest.mark.parametrize('fault', [None, 'offline', 'progress'])
def test_real_journey_action_restores_and_refuses_later_reply(rig, monkeypatch, tmp_path, fault):
    import parent_setup_qualification as setup
    import installed_journey
    monkeypatch.setattr(installed_journey.session_control, 'observe',
                        Mock(return_value={'outcome': 'passed'}))
    lease, connection, transport, _ = rig
    context = SimpleNamespace(directory=tmp_path, lease=lease)
    progress = Mock(side_effect=OSError('storage') if fault == 'progress' else None)
    journey = setup.IndependentNetworkQualification.journey(context, progress)
    journey.steps = [{'stage': stage} for stage in journey.plan.stages[:-1]]
    assert journey.plan.stages[-1] == 'desktop'
    journey.transport = transport
    journey.boot = 'a' * 64
    journey.ui = SimpleNamespace(boot_proof=journey.boot,
        observe=lambda operation: {'operation': operation, 'outcome': 'passed'})
    offline = probe_result(fault == 'offline')
    monkeypatch.setattr(qualification, 'internet_result',
        Mock(side_effect=[probe_result(True), offline, probe_result(True)]))
    monkeypatch.setattr(qualification, 'controller_result', Mock(return_value={'observed': True}))
    (tmp_path / 'desktop.request.json').write_text(json.dumps(
        {'stage': 'desktop', 'screenshot': None}))
    if fault:
        with pytest.raises((CommandError, OSError)):
            journey.step(Mock())
        assert not (tmp_path / 'desktop.reply.json').exists()
        with pytest.raises(ValueError, match='previous-failure'):
            journey.step(Mock())
    else:
        journey.step(Mock())
        assert journey.steps[-1]['fixture']['interruption_cleanup']
        assert (tmp_path / 'desktop.reply.json').exists()
    assert not connection.filters and not connection.bindings


def test_outer_cleanup_invokes_network_cleanup_before_snapshot_transition(monkeypatch):
    import system_runner
    lease = object.__new__(system_runner.Lease)
    lease.state = {'phase': 'running'}
    lease.mutated = False
    calls = []
    monkeypatch.setattr(network, 'restore', lambda owned: calls.append('network'))
    lease.save = lambda phase: calls.append(phase)
    lease.finish()
    assert calls == ['network', 'complete']


@pytest.mark.parametrize('running', [True, False])
def test_reconstructed_outer_recovery_removes_canonical_owned_resources(
        rig, monkeypatch, running, local_preparation_source):
    import hashlib
    import system_runner as runner
    from unittest.mock import patch
    original, connection, transport, journal = rig
    network.InternetIsolation(original).enter(transport)
    original.state = json.loads(journal.read_text())
    source = original.source
    source.uuid = DOMAIN_UUID
    source.baseline = Mock(return_value='<snapshot/>')
    source.domain.autostart.return_value = False
    if not running:
        source.domain.ID.return_value = -1
        connection.bindings.clear()  # libvirt retires bindings with the guest.
    else:
        source.domain.XMLDesc.return_value = DOMAIN_XML.replace('</devices>',
            '<graphics type="vnc"><listen type="none"/></graphics></devices>')
    recovered = runner.Lease(source, Mock(), Mock(), directory=journal.parent,
                             graphics_type='vnc')
    baseline_state = {'phase': 'finalized', 'source': {
        'layout': {'disk': str(journal.parent / 'disk')}},
        'proof': 'proof', 'script_digest': 'digest', 'guest': 'guest'}
    state = {**original.state, 'schema_version': 1,
             'baseline_sha256': hashlib.sha256(runner.baseline.encode(baseline_state)).hexdigest()}
    journal.write_text(json.dumps(state))
    recovered.journal = journal
    recovered.capture = Mock()
    recovered.capture.read_state.return_value = baseline_state
    recovered.capture.verify_snapshot.return_value = 'proof'
    recovered.inspect = Mock(return_value='guest')
    recovered.guard = Mock()
    recovered.save = Mock(side_effect=lambda phase: journal.write_text(json.dumps(
        {**recovered.state, 'phase': phase})))
    recovered.finish = Mock()
    with patch.object(runner.os, 'open', return_value=42), patch.object(runner.os, 'close'), \
            patch.object(runner.fcntl, 'flock'), patch.object(runner.baseline, 'identity'), \
            patch.object(runner.baseline, 'domain_layout', return_value=baseline_state['source']['layout']), \
            patch.object(runner, 'isolated_xml'):
        recovered.recover_graphical_cleanup()
    assert recovered.fd is None
    assert not connection.filters and not connection.bindings
    assert recovered.state['internet_isolation']['phase'] == 'restored'
    assert recovered.finish.call_count == int(running)
    source.domain.create.assert_not_called()
