"""Reusable installation snapshot preparation under an existing suite lease."""
import re

import system_runner as system


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
    """Create the version snapshot, or leave an existing match untouched."""
    from installed_setup import stage, InstalledSetup
    from provenance import VerifiedInputs
    from vm_transport import Transport
    system.require(type(overwrite) is bool, 'suite:invalid-overwrite')
    lease = suite.lease
    version = suite.commands.run(['dpkg-deb', '-f', str(assets / 'package.deb'),
                                  'Version']).decode().strip()
    name = snapshot_name(version)
    if name in lease.source.domain.snapshotListNames(0) and not overwrite:
        preparation('Keeping existing snapshot ' + name + ' (overwrite=false); no changes')
        return False
    system.log('stage:suite-installation')
    preparation('Restoring onpc-baseline')
    lease.prepare()
    lease.installed_name = name
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
    stage(setup, assets, selection)
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
    from e2e_watch import running_display
    with running_display(lease):
        transport.probe_ready()
        InstalledSetup(setup, verified, transport).run(lease.guard, verify=False)
    lease.capture.retire_backing_verification()
    lease.source.shutdown(lease.guard, requested=False)
    lease.guard(off=True)
    preparation('Taking snapshot ' + name)
    lease.create_installed()
    # A completed snapshot is reusable across runs, including interrupted runs.
    lease.state.pop('e2e_snapshot', None)
    lease.save('isolated')
    suite.prepared = True
    if system.watch_progress is not None:
        system.watch_progress.suite_prepared()
    return True
