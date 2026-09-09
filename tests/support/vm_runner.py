"""Shared installed-runner identities, JUnit builders and simulated leases.

All VM operations are mocks. The baseline fixture uses only temporary files.
"""

from unittest.mock import Mock
import xml.etree.ElementTree as ET

import pytest
import system_runner as runner
from tests.support.vm_baseline import xml as baseline_xml


UUID = 'f95890e1-88e7-4779-8ae3-53fdcc34330a'
RUN = 'a' * 32


def xml():
    return f'''<domain type="kvm"><name>ubuntu26.04</name><uuid>{UUID}</uuid><devices>
      <disk type="file" device="disk"><driver type="qcow2"/><source file="/image"/><target dev="vda"/></disk>
      <filesystem type="mount"><driver type="virtiofs"/><source dir="/Data"/><target dir="Data"/></filesystem>
      <interface type="network"><source network="default"/></interface>
      <channel type="spicevmc"/><redirdev type="spicevmc"/>
      <graphics type="spice"/><console type="pty"/>
    </devices></domain>'''


INVENTORIES = {
    'package': (
        'test_installed_package',
        'test_first_install_requests_reboot',
        'test_reboot_applies_installation',
    ),
    'authorization': (
        'test_method_role_matrix[ListManagedUsers-child1]',
        'test_real_selected_parent_authentication[child1]',
    ),
    'enforcement': ('test_native_command_policy_is_uid_scoped',
                    'test_native_whitespace_policy_is_uid_scoped',
                    'test_native_future_pattern_is_uid_scoped',
                    'test_native_missing_launcher_retains_policy',
                    'test_native_catalog_is_selected_child_scoped'),
    'session': ('test_kiosk_expiry_graphical_runtime',),
}


def write_junit_results(directory, selection, fault=None):
    output = directory / 'guest-results'
    output.mkdir()
    for phase in selection.phases:
        executions = list(runner.phase_executions(selection, phase))
        if fault == 'missing' and phase == selection.phases[-1]:
            executions.pop()
        if fault == 'extra' and phase == selection.phases[-1]:
            executions.append(runner.CaseExecution(phase, executions[0].area, 'test_unexpected', False))
        if fault == 'duplicate' and phase == selection.phases[-1]:
            executions.append(executions[0])
        suite = ET.Element('testsuite', tests=str(len(executions)), failures='0', errors='0', skipped='0')
        for index, execution in enumerate(executions):
            classname = runner.AREA_SOURCES[execution.area].stem
            if fault == 'identity' and phase == selection.phases[-1] and index == 0:
                classname = 'test_unregistered'
            case = ET.SubElement(suite, 'testcase', classname=classname, name=execution.case_id)
            if fault in {'failure', 'skipped'} and phase == selection.phases[-1] and index == 0:
                suite.set('failures' if fault == 'failure' else 'skipped', '1')
                ET.SubElement(case, fault)
        ET.ElementTree(suite).write(output / f'{phase}.xml', encoding='utf-8')


@pytest.fixture
def lease_rig(rig):
    rig.capture().run()
    source = rig.source
    original = baseline_xml(rig.top)
    original = original.replace('</devices>', '<interface type="network"><source network="default"/></interface></devices>')
    current = {'xml': original, 'id': -1}
    source.api = Mock(VIR_DOMAIN_XML_INACTIVE=2)
    source.uuid = UUID
    source.domain = Mock()
    source.connection = Mock()
    source.domain.XMLDesc.side_effect = lambda *_: current['xml']
    source.domain.ID.side_effect = lambda: current['id']
    source.domain.autostart.return_value = False
    source.connection.lookupByName.return_value = source.domain

    def define(value):
        current['xml'] = value
        source.layout = runner.baseline.domain_layout(value, UUID)
    source.connection.defineXML.side_effect = define

    def start():
        source.off, current['id'] = False, 71
    source.domain.create.side_effect = start
    snapshot = source.domain.snapshotLookupByName.return_value
    snapshot.getXMLDesc.side_effect = lambda *_: source.baseline_xml

    def restore(*_):
        source.off, current['id'] = True, -1
        define(original)
    source.domain.revertToSnapshot.side_effect = restore
    source.domain.destroyFlags.side_effect = restore
    return runner.Lease(source, rig.commands, rig.inspect, directory=rig.directory, anchor=rig.anchor), current
