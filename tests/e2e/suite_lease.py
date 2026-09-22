"""Fresh baseline cases under one invocation's uninterrupted VM ownership.

Baseline metadata audits bracket the suite. Between cases libvirt discards the
recorded guest directly into the next case's off snapshot. A suite-owned installed
snapshot avoids repeated installation; no case's product state reaches another.
Case results remain candidates until the final audit and actual lock release succeed.
"""

from pathlib import Path
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
        self.installed_inputs = None
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
        with self.snapshot_status('Taking', self.installed_name):
            snap = self.source.domain.snapshotCreateXML(ET.tostring(root, encoding='unicode'), 0)
        self.installed_xml = snap.getXMLDesc(0)
        if self.installed_inputs is not None:
            # Publish freshness only after libvirt acknowledges snapshot creation.
            # Interrupted creation leaves an unmarked snapshot that cannot be reused.
            self.guard(off=True)
            root = ET.fromstring(self.installed_xml)
            system.require(root.findtext('name') == self.installed_name,
                           'suite:snapshot-name-changed')
            description = root.find('description')
            if description is None:
                description = ET.SubElement(root, 'description')
            description.text = self.installed_inputs
            with self.snapshot_status('Recording inputs for', self.installed_name):
                snap = self.source.domain.snapshotCreateXML(
                    ET.tostring(root, encoding='unicode'),
                    self.source.api.VIR_DOMAIN_SNAPSHOT_CREATE_REDEFINE)
            self.installed_xml = snap.getXMLDesc(0)
            system.require(ET.fromstring(self.installed_xml).findtext('description') ==
                           self.installed_inputs, 'suite:snapshot-inputs-not-recorded')
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
        self.capture.vm_ownership.check_owner()
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
        protected = self.capture.vm_ownership
        if not protected.closed:
            protected.check()
        # This is the acquisition identity, not a new byte audit. Invocation
        # acceptance always waits for audit() after the last case or failure.
        return self.capture.state['proof']

    @system.observed('Preparing an isolated VM attempt')
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

    @system.observed('Stopping the VM and restoring its snapshot')
    def stop(self):
        """Revert directly; never wait for ACPI or destroy a discovered guest."""
        self.guard()
        if self._restored:
            self.guard(off=True)
            return
        system.require(not self._reset_attempted, 'suite:restore-already-attempted')
        self._reset_attempted = True
        self.capture.retire_vm_ownership()
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
        with self.snapshot_status('Restoring', name):
            self.source.domain.revertToSnapshot(snap, self.source.api.VIR_DOMAIN_SNAPSHOT_REVERT_FORCE)
        self.view.run = None
        self.view.domain_id = None
        self.guard(off=True)
        self.close_watch()
        # generalhw still owes its final status-off callback. Preserve the run
        # tag until it closes, without booting or modifying restored disk data.
        self.source.connection.defineXML(self.test_xml)
        self.view.run = self.state['run']
        self.state['domain_id'] = None
        self.guard(off=True)
        self.save('isolated')
        self._restored = True
        self._restored_name = name

    def stop_by_restore(self):
        self.stop()

    @system.observed('Restoring the VM and verifying cleanup')
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

    @system.observed('Verifying VM cleanup and retained snapshots')
    def audit(self, *, validate=None, retain_installed=False):
        """No acceptance or next invocation can bypass this final metadata audit."""
        if not self._held:
            return
        try:
            system.require(self._case_released and self.state['phase'] == 'complete',
                           'suite:cleanup-incomplete')
            if not self.mutated:
                return
            if self._restored_name != self.capture.state['proof']['name']:
                self.restore_installed = False
                self._restored = self._reset_attempted = False
                self.finish()
            self._fast = False
            self.guard(off=True)
            system.log('stage:restored-baseline-verification')
            system.require(self.capture.read_state() == self.capture.state, 'baseline:changed')
            system.require(self.capture.verify_snapshot(boundary='restoration') ==
                           self.capture.state['proof'], 'cleanup:baseline-changed')
            system.require(self.inspect(Path(self.capture.state['source']['layout']['disk']),
                                        self.capture.state['script_digest']) == self.capture.state['guest'],
                           'cleanup:guest-changed')
            self.guard(off=True)
            if validate is not None:
                # Source/asset preservation is checked after the metadata audit,
                # while ownership is still held.
                self._fast = True
                validate()
            if retain_installed:
                # The standalone tool leaves the powered-off app state ready.
                # Audit the outer baseline first, then restore the exact snapshot
                # created here while ownership and metadata checks still apply.
                self._fast = True
                self.restore_installed = True
                self._restored = self._reset_attempted = False
                self.finish()
                # Commit retention only after restoration and provenance checks.
                # Incomplete snapshot creation keeps its cleanup obligation.
                self.state.pop('e2e_snapshot', None)
                self.save('complete')
        finally:
            self._fast = False
            self._held = False
            super().release()


class Suite:
    """Lazily acquire after preflight; close even when preparation fails."""
    def __init__(self, opener):
        self.opener = opener
        self.commands = Commands()
        self.source = self.guestfs = self.lease = None
        self.host_before = None
        self.verified = None
        self.backend_checked = self.credentials_checked = False
        self.prepared = False
        self.next_case = None
        self._input_bundle = None

    def input_bundle(self, root):
        if self._input_bundle is None:
            from installed_setup import inputs
            self._input_bundle = inputs(root)
        return self._input_bundle

    def prepare_installed(self, directory, assets, selection, *, root, overwrite=True):
        from app_snapshot import prepare
        return prepare(self, directory, assets, selection, root=root, overwrite=overwrite)

    def prepare_case(self, case, directory, assets, selection, *, root):
        if not self.prepared:
            created = self.prepare_installed(directory, assets, selection, root=root, overwrite=False)
            if not created:
                from app_snapshot import snapshot_name
                version = self.commands.run(['dpkg-deb', '-f', str(assets / 'package.deb'),
                                             'Version']).decode().strip()
                self.lease.installed_name = snapshot_name(version)
                self.lease.installed_xml = self.lease.source.domain.snapshotLookupByName(
                    self.lease.installed_name, 0).getXMLDesc(0)
                self.lease.prepare()
                self.prepared = True
                if system.watch_progress is not None:
                    system.watch_progress.suite_prepared()
            self.lease.restore_installed = needs_installed(case)
            self.lease.stop()
        expected = (self.lease.installed_name if needs_installed(case)
                    else self.lease.capture.state['proof']['name'])
        system.require(expected is not None and self.lease._restored_name == expected,
                       'suite:case-snapshot-not-restored')
        self.lease.prepare()
        self.lease.restore_installed = needs_installed(self.next_case)

    def acquire(self, ledger):
        if self.source is None:
            self.host_before = system.host_fingerprint(self.commands)
            self.source, self.guestfs = self.opener()
            self.lease = SuiteLease(self.source, self.commands,
                lambda disk, digest: system.baseline.inspect_guest(self.guestfs, disk, digest),
                ledger=ledger, graphics_type='vnc')
        self.lease.ledger = ledger
        return self.source, self.guestfs, self.lease

    def close(self, *, retain_installed=False):
        try:
            if self.lease is not None:
                options = {'retain_installed': True} if retain_installed else {}
                self.lease.audit(validate=self.verified.recheck if self.verified is not None else None,
                                 **options)
        finally:
            try:
                if self.host_before is not None:
                    system.require(system.host_fingerprint(self.commands) == self.host_before,
                                   'execution:host-changed')
            finally:
                if self.source is not None:
                    self.source.close()
