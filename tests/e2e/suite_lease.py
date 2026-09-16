"""Fresh baseline cases under one invocation's uninterrupted VM ownership.

Expensive baseline audits bracket the suite. Between cases libvirt discards the
recorded guest directly into the next case's off snapshot. A suite-owned installed
snapshot avoids repeated installation; no case's product state reaches another.
Case results remain candidates until the final audit and actual lock release succeed.
"""

from pathlib import Path
import re
import xml.etree.ElementTree as ET

import system_runner as system
from owned_commands import Commands


def needs_installed(case):
    return case is not None and 'installed-digest-verified-product' in case['preconditions']


class SuiteLease(system.Lease):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._held = False
        self._case_released = False
        self._fast = False
        self._restored = False
        self._reset_attempted = False
        self._failed = False
        self.installed_name = None
        self.installed_xml = None
        self.restore_installed = False
        self._restored_name = None

    def delete_installed(self):
        """Only the exact version owned by this invocation; never descendants."""
        if self.installed_name is None:
            return
        self.delete_suite_snapshot()
        self.installed_xml = None

    def create_installed(self):
        system.log('stage:suite-installed-snapshot')
        self.guard(off=True)
        # Save the ordinary inactive configuration, just like onpc-baseline.
        # Restores remove sharing again before any boot.
        self.source.connection.defineXML(self.original_xml)
        self.view.run = None
        self.view.domain_id = None
        self.state['domain_id'] = None
        self.guard(off=True)
        root = ET.Element('domainsnapshot')
        ET.SubElement(root, 'name').text = self.installed_name
        ET.SubElement(root, 'memory', snapshot='no')
        snap = self.source.domain.snapshotCreateXML(ET.tostring(root, encoding='unicode'), 0)
        self.installed_xml = snap.getXMLDesc(0)
        self.source.connection.defineXML(self.test_xml)
        self.view.run = self.state['run']
        self.save('isolated')

    @property
    def attempt_released(self):
        return self._case_released

    def __enter__(self):
        if not self._held:
            super().__enter__()
            self._held = True
        else:
            system.require(self._case_released and not self._failed and
                           self.state['phase'] == 'complete', 'suite:previous-case-incomplete')
            self.guard(off=True)
        self._case_released = False
        self.finalize = None
        return self

    def guard(self, *, off=False):
        if not self._fast:
            return super().guard(off=off)
        # Keep live ownership/instance, isolation, path and snapshot identity
        # checks. Re-running qemu-img on the entire chain belongs to the audits.
        self.capture.backing_verification.check_owner()
        layout, is_off = self.view.snapshot()
        system.require(layout == self.capture.state['source']['layout'], 'guard:source-changed')
        system.require(not off or is_off, 'guard:source-running')
        system.require(self.capture.private_directory() == self.capture.directory_identity,
                       'guard:directory-changed')
        for item in self.capture.state['source']['chain']:
            system.require(system.baseline.identity(item['path']) ==
                           {key: item[key] for key in ('path', 'device', 'inode')},
                           'guard:source-changed')
        system.require(self.source.baseline() == self.snapshot_xml,
                       'baseline:snapshot-metadata-changed')

    def verify_baseline(self):
        if not self._fast:
            return super().verify_baseline()
        self.guard()
        if self.capture.verification_failure is not None:
            raise self.capture.verification_failure
        protected = self.capture.backing_verification
        if not protected.closed:
            protected.check()
        # This is the acquisition identity, not a new byte audit. Invocation
        # acceptance always waits for audit() after the last case or failure.
        return self.capture.state['proof']

    def prepare(self):
        if not self._fast:
            super().prepare()
            self._fast = True
        else:
            system.require(self._restored, 'suite:baseline-not-restored')
            self.guard(off=True)
            self.source.connection.defineXML(self.test_xml)
            self.view.run = self.state['run']
            self.view.domain_id = None
            self.state['domain_id'] = None
            self.guard(off=True)
            self.save('isolated')
        # Provisioning may now modify the active disk, even without a boot.
        self._restored = False
        self._reset_attempted = False

    def stop(self):
        """Revert directly; never wait for ACPI or destroy a discovered guest."""
        self.guard()
        if self._restored:
            self.guard(off=True)
            return
        system.require(not self._reset_attempted, 'suite:restore-already-attempted')
        self._reset_attempted = True
        self.capture.retire_backing_verification()
        self.guard()
        if not self.view.snapshot()[1]:
            system.require(self.view.domain_id is not None, 'cleanup:unowned-domain')
        self.save('cleanup-requested')
        name = self.installed_name if self.restore_installed else self.capture.state['proof']['name']
        expected = self.installed_xml if self.restore_installed else self.snapshot_xml
        system.require(name is not None and expected is not None, 'suite:installed-snapshot-missing')
        # Lookup failure is terminal: no fallback installation or baseline.
        snap = self.source.domain.snapshotLookupByName(name, 0)
        system.require(snap.getXMLDesc(0) == expected, 'suite:snapshot-metadata-changed')
        # FORCE permits replacing QEMU when the saved XML differs. The saved
        # baseline is off: do not boot until shares have been removed again.
        self.source.domain.revertToSnapshot(snap, self.source.api.VIR_DOMAIN_SNAPSHOT_REVERT_FORCE)
        self.view.run = None
        self.view.domain_id = None
        self.guard(off=True)
        # generalhw still owes its final status-off callback. Preserve the run
        # tag until it closes, without booting or modifying restored disk data.
        self.source.connection.defineXML(self.test_xml)
        self.view.run = self.state['run']
        self.state['domain_id'] = None
        self.guard(off=True)
        self.save('isolated')
        self._restored = True
        self._restored_name = name

    def finish(self):
        if not self._fast:
            return super().finish()
        self.stop()
        self.source.connection.defineXML(self.original_xml)
        self.view.run = None
        self.guard(off=True)
        self.save('complete')

    def release(self):
        if not self._held:
            return super().release()
        self._case_released = True
        self._failed = self.state['phase'] != 'complete' or any(
            value['outcome'] == 'failed' for value in self.ledger.outcomes.values())
        # The suite retains the actual lock, including through case reporting.

    def audit(self, *, validate=None):
        """No acceptance or next invocation can bypass this final full audit."""
        if not self._held:
            return
        try:
            system.require(self._case_released and self.state['phase'] == 'complete',
                           'suite:cleanup-incomplete')
            if self._restored_name != self.capture.state['proof']['name']:
                self.restore_installed = False
                self._restored = self._reset_attempted = False
                self.finish()
            self.delete_installed()
            self._fast = False
            self.guard(off=True)
            system.log('stage:restored-baseline-verification')
            system.require(self.capture.read_state() == self.capture.state, 'baseline:changed')
            system.require(self.capture.verify_snapshot(force_bytes=True, boundary='restoration') ==
                           self.capture.state['proof'], 'cleanup:baseline-changed')
            system.require(self.inspect(Path(self.capture.state['source']['layout']['disk']),
                                        self.capture.state['script_digest']) == self.capture.state['guest'],
                           'cleanup:guest-changed')
            self.guard(off=True)
            if validate is not None:
                # Source/asset preservation is checked after the slow audit,
                # while ownership is still held. Its baseline checkpoint can
                # use the proof just audited rather than scanning twice.
                self._fast = True
                validate()
        finally:
            self._fast = False
            self._held = False
            super().release()


class Suite:
    """Lazily acquire after preflight; close even when preparation fails."""
    def __init__(self, opener, *, verify_backing_bytes=True):
        self.opener, self.verify_backing_bytes = opener, verify_backing_bytes
        self.commands = Commands()
        self.source = self.guestfs = self.lease = None
        self.host_before = None
        self.verified = None
        self.backend_checked = self.credentials_checked = False
        self.prepared = False
        self.next_case = None

    def prepare_installed(self, directory, assets, selection, *, root):
        """Always rebuild once, before the first case (including clean cases)."""
        from installed_setup import stage, InstalledSetup
        from provenance import VerifiedInputs
        from vm_transport import Transport
        lease = self.lease
        system.log('stage:suite-installation')
        lease.prepare()
        version = self.commands.run(['dpkg-deb', '-f', str(assets / 'package.deb'),
                                     'Version']).decode().strip()
        system.require(re.fullmatch(r'[0-9][A-Za-z0-9.+:~\-]*', version) is not None,
                       'suite:invalid-package-version')
        lease.installed_name = 'onpc-' + version
        lease.state['e2e_snapshot'] = lease.installed_name
        lease.save('isolated')
        lease.delete_installed()  # prepare() restored baseline before deletion.
        setup = directory / 'suite-setup'
        setup.mkdir(mode=0o700)
        stage(setup, assets, selection)
        host_key = system.bootstrap(self.commands, lease, setup, self.guestfs)
        lease.save('isolated')
        verified = VerifiedInputs(lease=lease, assets=assets, root=root)
        self.verified = verified
        lease.start()
        hostname = system.address(lease.source)
        (setup / 'known-hosts').write_text(f'{hostname} {host_key}\n')
        transport = Transport({'directory': str(setup), 'hostname': hostname,
            'domain_uuid': lease.source.uuid, 'domain_id': lease.view.domain_id,
            'run': lease.state['run']}, self.commands, guard=lambda _: lease.guard())
        transport.probe_ready()
        InstalledSetup(setup, verified, transport).run(lease.guard, verify=False)
        # Actual shutdown here only; case transitions retain direct reverts.
        lease.capture.retire_backing_verification()
        lease.source.shutdown(lease.guard, requested=False)
        lease.guard(off=True)
        lease.create_installed()
        self.prepared = True

    def prepare_case(self, case, directory, assets, selection, *, root):
        if not self.prepared:
            self.prepare_installed(directory, assets, selection, root=root)
            self.lease.restore_installed = needs_installed(case)
            self.lease.stop()
        self.lease.prepare()
        self.lease.restore_installed = needs_installed(self.next_case)

    def acquire(self, ledger):
        if self.source is None:
            self.host_before = system.host_fingerprint(self.commands)
            self.source, self.guestfs = self.opener()
            self.lease = SuiteLease(self.source, self.commands,
                lambda disk, digest: system.baseline.inspect_guest(self.guestfs, disk, digest),
                ledger=ledger, graphics_type='vnc', verify_backing_bytes=self.verify_backing_bytes)
        self.lease.ledger = ledger
        return self.source, self.guestfs, self.lease

    def close(self):
        try:
            if self.lease is not None:
                self.lease.audit(validate=self.verified.recheck if self.verified is not None else None)
        finally:
            try:
                if self.host_before is not None:
                    system.require(system.host_fingerprint(self.commands) == self.host_before,
                                   'execution:host-changed')
            finally:
                if self.source is not None:
                    self.source.close()
