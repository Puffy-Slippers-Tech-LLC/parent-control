"""Reusable installation snapshot preparation under an existing suite lease."""
import re
from contextlib import nullcontext
import json
import time
import xml.etree.ElementTree as ET

import system_runner as system
import package_content


def mode_mismatch(xml, mode, *, now=None):
    """Use libvirt's saved state and host UTC creation time, not guest time."""
    try:
        root = ET.fromstring(xml)
        memory = root.find('memory')
        online = memory is not None and memory.get('snapshot') == 'internal'
        if online != (mode == 'online'):
            return 'snapshot mode changed'
        if online:
            if root.findtext('state') != 'running':
                return 'online snapshot is not running'
            created = int(root.findtext('creationTime', ''))
            age = (time.time() if now is None else now) - created
            if created <= 0 or age < 0:
                return 'invalid online snapshot creation time'
            if age > 24 * 60 * 60:
                return 'online snapshot is more than 24 hours old'
        domain = root.find('domain')
        if domain is None:
            return 'missing snapshot console configuration'
        # Older isolation left host shares attached. Their backend state
        # depends on live host files outside the guest disk/RAM snapshot.
        # Refresh those online snapshots before attempting a memory restore;
        # offline snapshots are isolated again before boot, and recorded
        # owners must remain recoverable through the existing cleanup route.
        if online and domain.findall('devices/filesystem'):
            return 'online snapshot contains host filesystem sharing'
        try:
            system.validate_private_vnc(domain)
            system.validate_host_sharing(domain)
        except system.Error:
            return 'snapshot console configuration changed'
        if domain.find('devices/graphics').get('type') != 'spice':
            return 'snapshot console configuration changed'
        if not domain.findall('devices/channel'):
            return 'snapshot display-agent channel missing'
        if domain.find('devices/graphics/clipboard').get('copypaste') != system.clipboard_policy():
            return 'snapshot clipboard configuration changed'
        return None
    except (ET.ParseError, ValueError, TypeError):
        return 'missing or invalid snapshot metadata'


def input_identity(lease, assets, bundle, commands):
    """Only installed state invalidates the cache; test payload is replaceable."""
    package = assets / ('package.' + system.package_format(lease.capture.state['guest']))
    return json.dumps({'schema_version': 2,
        'package_sha256': system.baseline.digest(package),
        'package_content_sha256': package_content.digest(package, commands),
        'baseline_sha256': lease.state['baseline_sha256'],
        'recipe_sha256': bundle.digest('guest_install_recipe.py')},
        sort_keys=True, separators=(',', ':'))


def mismatch(xml, expected):
    """Separate archive integrity from installed equivalence; accept v1 exactly."""
    try:
        previous = json.loads(ET.fromstring(xml).findtext('description'))
        current = json.loads(expected)
        keys = {'schema_version', 'package_sha256', 'baseline_sha256', 'recipe_sha256'}
        if not isinstance(previous, dict) or type(previous.get('schema_version')) is not int:
            return 'missing or invalid snapshot metadata'
        version = previous['schema_version']
        if version == 2:
            keys.add('package_content_sha256')
        if (version not in (1, 2) or set(previous) != keys
                or any(not isinstance(previous[key], str)
                       or re.fullmatch('[0-9a-f]{64}', previous[key]) is None
                       for key in keys - {'schema_version'})):
            return 'missing or invalid snapshot metadata'
        for key, reason in (('baseline_sha256', 'baseline changed'),
                            ('recipe_sha256', 'installation recipe changed')):
            if previous[key] != current[key]:
                return reason
        if version == 1:
            if previous['package_sha256'] != current['package_sha256']:
                return 'legacy snapshot has no content fingerprint for this archive'
        elif previous['package_content_sha256'] != current['package_content_sha256']:
            return 'package contents changed'
        return None
    except (ET.ParseError, ValueError, TypeError, KeyError):
        return 'missing or invalid snapshot metadata'


def matches(xml, expected):
    return mismatch(xml, expected) is None


def snapshot_name(version):
    system.require(re.fullmatch(r'[0-9][A-Za-z0-9.+:~\-]*', version) is not None,
                   'suite:invalid-package-version')
    release = re.match(r'[0-9]+(?:\.[0-9]+)*', version).group()
    return 'onpc-v' + release


def preparation(message):
    system.log('appsnapshot: ' + message)
    if system.watch_progress is not None:
        system.watch_progress.suite_preparation(message)


def prepare(suite, directory, assets, selection, *, root, overwrite=True, mode='offline'):
    """Ensure a current snapshot; overwrite forces even a matching rebuild."""
    from installed_setup import stage, InstalledSetup
    from provenance import VerifiedInputs
    from vm_transport import Transport
    system.require(type(overwrite) is bool, 'suite:invalid-overwrite')
    system.require(mode in ('online', 'offline'), 'suite:invalid-snapshot-mode')
    lease = suite.lease
    package = assets / ('package.' + system.package_format(lease.capture.state['guest']))
    system.require(package.is_file(), 'suite:package-platform-mismatch')
    version = system.package_version(suite.commands, package)
    name = snapshot_name(version)
    bundle = suite.input_bundle(root)
    with system.operation('Comparing app package contents'):
        expected = input_identity(lease, assets, bundle, suite.commands)
    if name in lease.source.domain.snapshotListNames(0) and not overwrite:
        # The lease is validated but not prepared yet; guard()'s snapshot XML
        # is initialized by prepare(). Revalidate acquisition ownership here.
        lease.capture.vm_ownership.check_owner()
        lease.capture.revalidate()
        xml = lease.source.domain.snapshotLookupByName(name, 0).getXMLDesc(0)
        mode_reason = mode_mismatch(xml, mode)
        reason = mode_reason or mismatch(xml, expected)
        if mode_reason is not None:
            overwrite = True
        if reason is None and mode == 'online':
            from online_snapshot import load
            if load(lease.source, name, xml) is None:
                reason = 'online snapshot credentials missing'
        if reason is None:
            if json.loads(ET.fromstring(xml).findtext('description'))['schema_version'] == 1:
                preparation('Recording content fingerprint for existing snapshot ' + name)
                lease.record_installed_inputs(name, xml, expected)
            preparation('Reusing current snapshot ' + name)
            return False
        preparation('Refreshing snapshot ' + name + ': ' + reason)
    system.log('stage:suite-installation')
    preparation('Restoring ' + system.baseline.SNAPSHOT)
    lease.prepare()
    lease.installed_name = name
    lease.installed_inputs = expected
    lease.state['e2e_snapshot'] = name
    lease.save('isolated')
    # Restore first so deletion cannot leave the active disk on stale app state.
    if name in lease.source.domain.snapshotListNames(0):
        preparation('Deleting existing snapshot ' + name +
                    (' (overwrite=true)' if overwrite else ' (installed inputs changed)'))
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
    # Online snapshots capture activated services after a verified reboot.
    # Offline snapshots retain the original install/verify/shutdown sequence.
    InstalledSetup(setup, verified, transport).run(lease.guard, verify=mode == 'online')
    transport.call(system.guest_command(lease.state['run'], 'verify-snapshot'), timeout=660)
    lease.guard()
    verified.recheck()
    lease.capture.retire_vm_ownership()
    if mode == 'offline':
        lease.source.shutdown(lease.guard, requested=False)
        lease.guard(off=True)
    preparation('Taking snapshot ' + name)
    from online_snapshot import disconnected_network, publish
    with disconnected_network(lease) if mode == 'online' else nullcontext():
        lease.create_installed(mode=mode)
        if mode == 'online':
            publish(lease, setup, host_key)
    # A completed snapshot is reusable across runs, including interrupted runs.
    lease.state.pop('e2e_snapshot', None)
    lease.save('running' if mode == 'online' else 'isolated')
    suite.prepared = True
    if system.watch_progress is not None:
        system.watch_progress.suite_prepared()
    return True
