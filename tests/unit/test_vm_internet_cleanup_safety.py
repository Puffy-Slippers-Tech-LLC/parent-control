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
    def lookupByUUIDString(self, identity):
        assert identity == DOMAIN_UUID
        return self.domain
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
        source=SimpleNamespace(domain=domain, connection=connection, uuid=DOMAIN_UUID,
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


@pytest.mark.parametrize('count', ['1', '0', None])
def test_shutdown_connection_count_is_not_network_configuration(rig, count):
    lease, connection, transport, journal = rig
    connection.net_xml = NETWORK_XML.replace('<network>', "<network connections='2'>")
    network.InternetIsolation(lease).enter(transport)
    original = lease.state['internet_isolation']['network_xml']
    connection.domain.ID.return_value = -1
    connection.net_xml = NETWORK_XML if count is None else NETWORK_XML.replace(
        '<network>', "<network connections='" + count + "'>")
    network.restore(lease)
    assert not connection.filters and not connection.bindings
    assert json.loads(journal.read_text())['internet_isolation']['network_xml'] == original


@pytest.mark.parametrize('fault', ['instance', 'uuid', 'configuration', 'nested',
                                  'text', 'whitespace', 'malformed', 'root', 'reappeared'])
def test_fresh_domain_and_network_configuration_refuse_changed_identity(rig, fault):
    lease, connection, transport, journal = rig
    network.InternetIsolation(lease).enter(transport)
    stale = lease.source.domain
    fresh = Mock(ID=Mock(return_value=-1), UUIDString=Mock(return_value=DOMAIN_UUID),
                 XMLDesc=Mock(return_value=DOMAIN_XML))
    fresh.name.return_value = 'fixture-vm'
    connection.domain = fresh
    if fault == 'instance': fresh.ID.return_value = 10
    elif fault == 'uuid': fresh.UUIDString.return_value = NETWORK_UUID
    elif fault == 'configuration': connection.net_xml = NETWORK_XML.replace('virbr0', 'virbr1')
    elif fault == 'nested': connection.net_xml = NETWORK_XML.replace('<bridge ', '<bridge connections="1" ')
    elif fault == 'text': connection.net_xml = NETWORK_XML.replace('</network>', '<metadata>changed</metadata></network>')
    elif fault == 'whitespace': connection.net_xml += ' '
    elif fault == 'malformed': connection.net_xml = '<network'
    elif fault == 'root': connection.net_xml = NETWORK_XML.replace('network', 'other')
    else: lease.state['internet_isolation']['phase'] = 'restored'
    before = journal.read_bytes(), connection.calls.copy()
    with pytest.raises((CommandError, ET.ParseError)):
        network.restore(lease)
    assert (journal.read_bytes(), connection.calls) == before
    assert connection.filters and connection.bindings
    assert stale.ID() == 9


@pytest.mark.parametrize('callback', [True, False])
def test_snapshot_restoration_refreshes_stale_handle_before_final_network_audit(
        rig, callback, local_preparation_source):
    from contextlib import nullcontext
    import system_runner as runner
    initial, connection, transport, journal = rig
    connection.net_xml = NETWORK_XML.replace('<network>', "<network connections='2'>")
    network.InternetIsolation(initial).enter(transport)
    network.restore(initial)
    stale = initial.source.domain
    off_xml = DOMAIN_XML.replace(' bridge="virbr0"', '').replace('<target dev="vnet7"/>', '')
    fresh = Mock(ID=Mock(return_value=-1), UUIDString=Mock(return_value=DOMAIN_UUID),
                 XMLDesc=Mock(return_value=off_xml))
    fresh.name.return_value = 'fixture-vm'
    initial.source.api.VIR_DOMAIN_SNAPSHOT_REVERT_FORCE = 4
    snap = Mock(getXMLDesc=Mock(return_value='<snapshot/>'))
    stale.snapshotLookupByName.return_value = snap
    def revert(*_):
        connection.domain = fresh
        stale.XMLDesc.return_value = off_xml  # ID remains cached at 9.
        connection.net_xml = NETWORK_XML.replace('<network>', "<network connections='1'>")
    stale.revertToSnapshot.side_effect = revert
    connection.defineXML = Mock()
    lease = runner.Lease(initial.source, Mock(), Mock(return_value='guest'),
                         directory=journal.parent, graphics_type='vnc')
    lease.state = initial.state
    lease.original_xml = off_xml
    lease.state['original_xml'] = off_xml
    lease.save = initial.save
    lease.guard = Mock()
    lease.capture = Mock(state={'proof': {'name': 'baseline'}, 'source': {
        'layout': {'disk': str(journal.parent / 'disk')}}, 'script_digest': 'digest', 'guest': 'guest'})
    lease.capture.verify_snapshot.return_value = lease.capture.state['proof']
    lease.ownership_run = None
    lease.snapshot_xml = '<snapshot/>'
    lease.snapshot_status = lambda *_: nullcontext()
    lease.view.domain_id = 9
    lease.mutated = True
    if callback:
        lease.stop_by_restore()
    else:
        lease.restore()
        lease.restored_by_callback = True
    lease.finish()
    assert stale.ID() == 9 and lease.source.domain is fresh
    assert lease.state['domain_id'] == 9  # Never rewrite the expected instance.
    assert lease.state['phase'] == 'complete'
    assert not connection.filters and not connection.bindings
    assert connection.calls == ['define', 'bind', 'delete', 'undefine']
    connection.defineXML.assert_called_once_with(off_xml)
    fresh.create.assert_not_called()


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


@pytest.mark.parametrize('fault', [None, 'entry', 'offline', 'input', 'result',
                                  'window', 'recovery', 'guard'])
def test_offline_parent_controls_preserve_results_identity_and_owned_unwind(rig, monkeypatch, fault):
    import offline_controls as shared
    from public_connectivity_controls import CONTROLS, qualify
    lease, connection, transport, _ = rig
    before, offline, after = probe_result(True), probe_result(False), probe_result(True)
    if fault == 'offline': offline['probes'][0]['reachable'] = True
    if fault == 'recovery': after['probes'][0]['reachable'] = False
    monkeypatch.setattr(shared, 'internet_result', Mock(side_effect=[before, offline, after]))
    endpoint = {'binding': 'parent', 'pid': 42,
                'endpoint': [':1.20', '/window/1'], 'active': True}
    calls = []

    def observe(name):
        calls.append(name)
        if fault == 'entry' and name == 'parent-save-disabled':
            raise CommandError('ui:parent-save-response')
        if name == 'switch-parent-before':
            value = deepcopy(endpoint)
            if fault == 'window' and calls.count(name) == 3:
                value['endpoint'][1] = '/window/2'
            return {'outcome': 'passed', 'window': value}
        if name.startswith('parent-toggle-'):
            assert lease.state['internet_isolation']['phase'] == 'offline'
            if fault == 'input': raise CommandError('ui:uncertain-input')
            return {'outcome': 'passed', 'toggle': {'state': name.endswith('enabled')}}
        value = deepcopy(CONTROLS[0 if name.endswith('enabled') else 1][2])
        if fault == 'result' and name == 'parent-save-enabled': value['result'] = 'saving'
        return {'outcome': 'passed', 'save': value}

    guard = Mock()
    if fault == 'guard':
        def guarded():
            if lease.state.get('internet_isolation', {}).get('phase') == 'offline':
                raise InterruptedError('cancelled')
        guard.side_effect = guarded
    journey = SimpleNamespace(context=SimpleNamespace(lease=lease),
                              transport=transport, ui=SimpleNamespace(observe=observe))
    if fault:
        with pytest.raises((CommandError, ValueError, InterruptedError)):
            qualify(journey, guard)
    else:
        result = qualify(journey, guard)
        assert result['online_after'] == result['online_before']
        assert [item['result']['save']['limit_enabled'] for item in result['controls']] == [True, False]
        assert calls == ['parent-save-disabled', 'switch-parent-before',
                         'switch-parent-before', 'parent-toggle-enabled', 'parent-save-enabled',
                         'switch-parent-before', 'switch-parent-before', 'parent-toggle-disabled',
                         'parent-save-disabled', 'switch-parent-before', 'switch-parent-before']
        endpoint['endpoint'][1] = '/later-mutation'
        assert result['window']['endpoint'][1] == '/window/1'
    if fault in ('input', 'result', 'window', 'guard', 'offline'):
        assert 'parent-toggle-disabled' not in calls
    assert not connection.filters and not connection.bindings
    assert len(connection.calls) == (0 if fault == 'entry' else 4)


@pytest.mark.parametrize('fault', [None, 'result', 'storage'])
def test_connectivity_composition_runs_through_real_recorder_before_reply(rig, monkeypatch, tmp_path, fault):
    import offline_controls as shared
    import parent_setup_qualification as setup
    from public_connectivity_controls import CONTROLS, PLAN
    lease, connection, transport, _ = rig
    context = SimpleNamespace(directory=tmp_path, lease=lease)
    progress = Mock(side_effect=OSError('storage') if fault == 'storage' else None)
    journey = setup.PublicConnectivityControlsQualification.journey(context, progress)
    stage = 'wrong-child-refused'
    journey.steps = [{'stage': item} for item in PLAN.stages[:PLAN.stages.index(stage)]]
    journey.transport = transport
    journey.boot = 'a' * 64
    endpoint = {'binding': 'parent', 'pid': 42, 'endpoint': [':1.20', '/window/1'], 'active': True}
    def observe(name):
        if name == 'parent-save-wrong-child-refused':
            return {'outcome': 'passed', 'save': {'refusal': 'wrong-child'}}
        if name == 'switch-parent-before': return {'outcome': 'passed', 'window': endpoint}
        if name.startswith('parent-toggle-'): return {'outcome': 'passed'}
        if fault == 'result' and name == 'parent-save-enabled': raise ValueError('save failed')
        return {'outcome': 'passed', 'save': CONTROLS[0 if name.endswith('enabled') else 1][2]}
    journey.ui = SimpleNamespace(boot_proof=journey.boot, observe=observe)
    monkeypatch.setattr(shared, 'internet_result',
                        Mock(side_effect=[probe_result(True), probe_result(False), probe_result(True)]))
    (tmp_path / (stage + '.request.json')).write_text(json.dumps({'stage': stage, 'screenshot': None}))
    if fault:
        with pytest.raises((ValueError, OSError)): journey.step(Mock())
        assert not (tmp_path / (stage + '.reply.json')).exists()
        with pytest.raises(ValueError, match='previous-failure'): journey.step(Mock())
    else:
        journey.step(Mock())
        assert journey.steps[-1]['fixture']['controls'][0]['result']['save']['limit_enabled']
        assert (tmp_path / (stage + '.reply.json')).exists()
    assert not connection.filters and not connection.bindings


@pytest.mark.parametrize('changed_window', [False, True])
def test_offline_controls_support_independent_single_input_bindings(rig, monkeypatch, changed_window):
    import offline_controls as shared
    from private_artifacts import EvidenceError
    lease, connection, transport, _ = rig
    monkeypatch.setattr(shared, 'internet_result', Mock(side_effect=[
        probe_result(True), probe_result(False), probe_result(True)]))
    endpoint = {'binding': 'parent', 'pid': 42,
                'endpoint': [':1.20', '/window/1'], 'active': True}
    expected = {'saved': True}
    calls = []

    def observe(name):
        calls.append(name)
        if name == 'owned-window':
            value = deepcopy(endpoint)
            if changed_window and calls.count(name) == 3:
                value['pid'] = 43
            return {'outcome': 'passed', 'window': value}
        if name == 'normal-input':
            assert lease.state['internet_isolation']['phase'] == 'offline'
        return {'outcome': 'passed', 'save': expected}

    journey = SimpleNamespace(context=SimpleNamespace(lease=lease),
                              transport=transport, ui=SimpleNamespace(observe=observe))
    def run():
        return shared.offline_controls(journey, Mock(), entry='declared-entry',
            controls=(('normal-input', 'saved-result', expected),), window='owned-window')
    if changed_window:
        with pytest.raises(EvidenceError, match='window-changed'):
            run()
    else:
        assert len(run()['controls']) == 1
    assert calls == ['declared-entry', 'owned-window', 'owned-window',
                     'normal-input', 'saved-result', 'owned-window',
                     *([] if changed_window else ['owned-window'])]
    assert not connection.filters and not connection.bindings


def test_connectivity_selector_uses_qualified_ui17_envelope_and_worker(monkeypatch, tmp_path):
    import check_e2e_operate_public_connectivity_controls as selector
    import check_graphical_smoke as smoke
    import parent_setup_qualification as setup
    from parent_toggle import PLAN as toggle
    from public_connectivity_controls import PLAN, qualify
    run = Mock(return_value=0)
    monkeypatch.setattr(selector, 'smoke', run)
    assert selector.main() == 0
    assert run.call_args.kwargs == {'assets': selector.ASSETS, 'provision_credentials': True,
                                  'parent_toggle': True, 'public_connectivity_controls': True}
    for options in ({}, {'assets': tmp_path, 'provision_credentials': True},
                    {'assets': tmp_path, 'provision_credentials': True,
                     'parent_toggle': True, 'independent_network': True}):
        with pytest.raises(CommandError, match='public-connectivity-controls-prerequisites'):
            smoke.main(public_connectivity_controls=True, **options)
    journey = setup.PublicConnectivityControlsQualification.journey(SimpleNamespace(directory=tmp_path), Mock())
    assert journey.plan is PLAN
    assert PLAN.worker_mode == toggle.worker_mode
    assert PLAN.screen_tags == toggle.screen_tags
    assert journey.actions == {'offline-parent-controls': qualify}
    assert setup.PublicConnectivityControlsQualification.prepare_context is setup.ParentToggleQualification.prepare_context


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


@pytest.mark.parametrize('mode', ['running', 'off', 'restored-original'])
def test_reconstructed_outer_recovery_removes_canonical_owned_resources(
        rig, monkeypatch, mode, local_preparation_source):
    import hashlib
    import system_runner as runner
    from unittest.mock import patch
    original, connection, transport, journal = rig
    running = mode == 'running'
    if mode == 'restored-original':
        original.state['original_xml'] = DOMAIN_XML.replace('</interface>',
            '<filterref filter="unrelated-original"/></interface>')
    network.InternetIsolation(original).enter(transport)
    if mode == 'restored-original':
        network.restore(original)
        connection.domain.XMLDesc.return_value = original.state['original_xml']
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
    if mode == 'restored-original':
        assert source.domain.XMLDesc(0) == original.state['original_xml']
        assert connection.calls == ['define', 'bind', 'delete', 'undefine']
    source.domain.create.assert_not_called()


@pytest.mark.parametrize('fault', [None, 'eof', 'timeout', 'oversized'])
def test_dns_probe_reads_fragmented_tcp_frames_with_bounded_failure(monkeypatch, capsys, fault):
    import socket
    import struct
    import subprocess
    response = b'\x19\x3a\x81\x00' + b'\x00' * 8
    class Peer:
        def __init__(self, family, kind):
            self.kind = kind
            self.frame = struct.pack('!H', 4097 if fault == 'oversized' else len(response)) + response
        def __enter__(self): return self
        def __exit__(self, *_): pass
        def settimeout(self, timeout): assert 0 < timeout <= 3
        def connect(self, address): pass
        def sendall(self, data): pass
        def send(self, data): pass
        def recv(self, count):
            if self.kind == socket.SOCK_DGRAM: return response
            if fault == 'timeout': raise TimeoutError()
            if fault == 'eof' and len(self.frame) < len(response): return b''
            chunk, self.frame = self.frame[:1], self.frame[1:]
            return chunk
    monkeypatch.setattr(socket, 'socket', Peer)
    monkeypatch.setattr(subprocess, 'check_output', lambda args: b'[]')
    exec(qualification.PROBE, {})
    result = json.loads(capsys.readouterr().out)
    assert [item['reachable'] for item in result['probes']] == [fault is None, True] * 2
