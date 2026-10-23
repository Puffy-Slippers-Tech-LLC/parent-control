"""Qualified E2E native closure after owned restoration and SSH readiness."""
from tools import fixture_execution, fixture_manifest, fixture_provision
from system_fixture_preparation import attempt_id, guest_target, register_staging
import xml.etree.ElementTree as ET

SUBSETS = ('native',)


def online_restore(lease):
    memory = ET.fromstring(lease.installed_xml).find('memory')
    return memory is not None and memory.get('snapshot') == 'internal'


def selection_record(value, target=None, *, product_free=False):
    if value is None:
        raise ValueError('fixtures:execution-selection-required')
    selection = fixture_execution.Selection.from_record(
        value.record() if isinstance(value, fixture_execution.Selection) else value)
    if (selection.target not in (('ubuntu',) if product_free else ('ubuntu', 'fedora'))
            or (target is not None and selection.target != target)):
        raise ValueError('fixtures:e2e-' + ('product-free' if product_free else 'installed')
                         + '-target-not-qualified')
    return selection.record()


def validate_input(value, target=None, *, product_free=False):
    record = selection_record(value, target=target, product_free=product_free)
    fixture_execution.verify(record)
    return record


def require_product_free_restore(lease):
    """Only the qualified Ubuntu empty baseline may release graphical input."""
    if guest_target(lease.capture.state['guest']) != 'ubuntu':
        raise ValueError('fixtures:e2e-product-free-target-not-qualified')
    if (getattr(lease, 'online_pending', False) is True
            or (getattr(lease, 'installed_name', None) is not None
                and getattr(lease, '_restored_name', None) != lease.capture.state['proof']['name'])):
        raise ValueError('fixtures:e2e-product-free-baseline-required')


def prepare(vm, lease, directory, selection, *, product_free=False):
    guest = lease.capture.state['guest']
    target = guest_target(guest)
    if product_free:
        require_product_free_restore(lease)
    elif target is None:
        raise ValueError('fixtures:e2e-installed-target-not-qualified')
    record = validate_input(selection, target=target, product_free=product_free)
    if not product_free and (lease.online_pending is not False or not lease.installed_name
            or (online_restore(lease) and lease.online_bootstrap is not None)
            or (not online_restore(lease) and lease._restored_name != lease.installed_name)):
        raise ValueError('fixtures:e2e-installed-restored-rebound-required')
    identity = attempt_id(directory)
    controller = fixture_provision.Provisioner(lease, vm,
        register_staging=lambda path: register_staging(directory, lease, identity, path))
    receipt = controller.provision(record, SUBSETS, attempt_id=identity)
    controller.require_ready(receipt)
    return {'vm': vm, 'lease': lease, 'directory': directory,
            'controller': controller, 'receipt': receipt,
            **({'product_free': True} if product_free else {})}


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
