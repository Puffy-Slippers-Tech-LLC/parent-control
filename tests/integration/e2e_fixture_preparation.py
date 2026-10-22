"""The qualified native closure after installed E2E restore and SSH rebind."""
from tools import fixture_execution, fixture_manifest, fixture_provision
from system_fixture_preparation import attempt_id, register_staging
import xml.etree.ElementTree as ET

SUBSETS = ('native',)


def online_restore(lease):
    memory = ET.fromstring(lease.installed_xml).find('memory')
    return memory is not None and memory.get('snapshot') == 'internal'


def selection_record(value, target='ubuntu'):
    if value is None:
        raise ValueError('fixtures:execution-selection-required')
    selection = fixture_execution.Selection.from_record(
        value.record() if isinstance(value, fixture_execution.Selection) else value)
    if selection.target != target:
        raise ValueError('fixtures:e2e-installed-target-not-qualified')
    return selection.record()


def validate_input(value):
    record = selection_record(value)
    fixture_execution.verify(record)
    return record


def prepare(vm, lease, directory, selection):
    guest = lease.capture.state['guest']
    if guest.get('fixture_boundary') != 'clean' or guest.get('ubuntu_version') != '26.04':
        raise ValueError('fixtures:e2e-installed-target-not-qualified')
    record = validate_input(selection)
    if (lease.online_pending is not False or not lease.installed_name
            or (online_restore(lease) and lease.online_bootstrap is not None)
            or (not online_restore(lease) and lease._restored_name != lease.installed_name)):
        raise ValueError('fixtures:e2e-installed-restored-rebound-required')
    identity = attempt_id(directory)
    controller = fixture_provision.Provisioner(lease, vm,
        register_staging=lambda path: register_staging(directory, lease, identity, path))
    receipt = controller.provision(record, SUBSETS, attempt_id=identity)
    controller.require_ready(receipt)
    return {'vm': vm, 'lease': lease, 'directory': directory,
            'controller': controller, 'receipt': receipt}


def asset_hashes(selection):
    """Bind legacy public observation keys to the selected runtime bytes."""
    manifest = fixture_execution.verify(selection_record(selection))
    declarations = fixture_manifest.declarations()
    from tests.fixtures import native_assets
    destinations = native_assets.source_destinations('@other@')
    return {source: next(manifest['members'][key]['sha256']
                        for key, item in declarations.items()
                        if item['destination'] == destination)
            for source, (destination, _mode) in destinations.items()}
