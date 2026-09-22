"""Reusable installation snapshot preparation under an existing suite lease."""
import re
import json
import xml.etree.ElementTree as ET

import system_runner as system


def input_identity(lease, assets, bundle):
    """Only installed state invalidates the cache; test payload is replaceable."""
    return json.dumps({'schema_version': 1,
        'package_sha256': system.baseline.digest(assets / 'package.deb'),
        'baseline_sha256': lease.state['baseline_sha256'],
        'recipe_sha256': bundle.digest('guest_install_recipe.py')},
        sort_keys=True, separators=(',', ':'))


def matches(xml, expected):
    try:
        return ET.fromstring(xml).findtext('description') == expected
    except (ET.ParseError, ValueError):
        return False


def snapshot_name(version):
    system.require(re.fullmatch(r'[0-9][A-Za-z0-9.+:~\-]*', version) is not None,
                   'suite:invalid-package-version')
    release = re.match(r'[0-9]+(?:\.[0-9]+)*', version).group()
    return 'onpc-v' + release


def preparation(message):
    system.log('appsnapshot: ' + message)
    if system.watch_progress is not None:
        system.watch_progress.suite_preparation(message)


def prepare(suite, directory, assets, selection, *, root, overwrite=True):
    """Ensure a current snapshot; overwrite forces even a matching rebuild."""
    from installed_setup import stage, InstalledSetup
    from provenance import VerifiedInputs
    from vm_transport import Transport
    system.require(type(overwrite) is bool, 'suite:invalid-overwrite')
    lease = suite.lease
    version = suite.commands.run(['dpkg-deb', '-f', str(assets / 'package.deb'),
                                  'Version']).decode().strip()
    name = snapshot_name(version)
    bundle = suite.input_bundle(root)
    expected = input_identity(lease, assets, bundle)
    if name in lease.source.domain.snapshotListNames(0) and not overwrite:
        # The lease is validated but not prepared yet; guard()'s snapshot XML
        # is initialized by prepare(). Revalidate acquisition ownership here.
        lease.capture.vm_ownership.check_owner()
        lease.capture.revalidate()
        xml = lease.source.domain.snapshotLookupByName(name, 0).getXMLDesc(0)
        if matches(xml, expected):
            preparation('Reusing current snapshot ' + name)
            return False
        preparation('Refreshing snapshot ' + name + ': installed inputs changed, unrecorded or incomplete')
    system.log('stage:suite-installation')
    preparation('Restoring onpc-baseline')
    lease.prepare()
    lease.installed_name = name
    lease.installed_inputs = expected
    lease.state['e2e_snapshot'] = name
    lease.save('isolated')
    # Restore first so deletion cannot leave the active disk on stale app state.
    if name in lease.source.domain.snapshotListNames(0):
        preparation('Deleting existing snapshot ' + name + ' (overwrite=true)')
        lease.delete_installed()
    else:
        preparation('No existing snapshot ' + name + '; preparing it')
    preparation('Installing app')
    setup = directory / 'suite-setup'
    setup.mkdir(mode=0o700)
    stage(setup, assets, selection, bundle=bundle)
    host_key = system.bootstrap(suite.commands, lease, setup, suite.guestfs)
    lease.save('isolated')
    verified = VerifiedInputs(lease=lease, assets=assets, root=root)
    suite.verified = verified
    lease.start()
    hostname = system.address(lease.source)
    (setup / 'known-hosts').write_text(f'{hostname} {host_key}\n')
    transport = Transport({'directory': str(setup), 'hostname': hostname,
        'domain_uuid': lease.source.uuid, 'domain_id': lease.view.domain_id,
        'run': lease.state['run']}, suite.commands, guard=lambda _: lease.guard())
    transport.probe_ready()
    # Install without rebooting: this disk-only snapshot's next boot activates
    # the package. Verify its installed bytes before the clean shutdown.
    InstalledSetup(setup, verified, transport).run(lease.guard, verify=False)
    transport.call(system.guest_command(lease.state['run'], 'verify-snapshot'), timeout=660)
    lease.guard()
    verified.recheck()
    lease.capture.retire_vm_ownership()
    lease.source.shutdown(lease.guard, requested=False)
    lease.guard(off=True)
    lease.close_watch()
    preparation('Taking snapshot ' + name)
    lease.create_installed()
    # A completed snapshot is reusable across runs, including interrupted runs.
    lease.state.pop('e2e_snapshot', None)
    lease.save('isolated')
    suite.prepared = True
    if system.watch_progress is not None:
        system.watch_progress.suite_prepared()
    return True
