"""Package-bound installed setup, before any customer action or secret input."""

import json
from pathlib import Path
import shutil

import system_runner as system
from private_artifacts import require
from guest_inputs import Bundle


def inputs(root):
    return Bundle(root, [('Makefile', 'install-source/Makefile'),
        *[(relative, Path(relative).name) for relative in (
        'tests/integration/system_guest.py', 'tests/integration/e2e_dynamic_account.py',
        'tests/integration/system_kiosk_confinement.py',
        'tests/integration/system_kiosk_feedback.py',
        'tests/integration/system_wellbeing_qualification.py',
        'tests/integration/wellbeing_probe.py')]])


def stage(directory, assets, selection, *, bundle=None):
    """Bind the existing installed payload and fixed helper bytes before bootstrap."""
    destination = directory / 'input'
    require(not destination.exists(), 'setup:input-exists')
    if assets == directory / 'assets':
        # This is the attempt's already frozen private copy. Transfer ownership
        # to its input directory instead of retaining a second complete bundle.
        assets.rename(destination)
    else:
        shutil.copytree(assets, destination)
    bundle = bundle if bundle is not None else inputs(system.ROOT)
    files = bundle.stage(destination)
    identity = {'schema_version': 1, 'scope': 'e2e-installed-setup',
                'selection': selection, 'files': files}
    (destination / 'selected-inputs.json').write_bytes(system.baseline.encode(identity))
    inventory = {p.relative_to(destination).as_posix(): system.baseline.digest(p)
                 for p in sorted(destination.rglob('*'))
                 if p.is_file() and p.name != 'transfer-sha256.json'}
    (destination / 'transfer-sha256.json').write_bytes(system.baseline.encode(inventory))
    return system.baseline.digest(destination / 'selected-inputs.json')


class InstalledSetup:
    """One setup attempt; caller must detach graphics before install/reboot."""

    def __init__(self, directory, verified, transport):
        self.directory, self.verified, self.transport = directory, verified, transport
        self.attempted = False

    def provision(self, guard):
        """Refresh this attempt's guarded helpers, including on reused snapshots."""
        require(not self.attempted, 'setup:already-attempted')
        self.attempted = True
        guard()
        self.verified.recheck()
        payload = self.directory / 'input'
        inventory = json.loads((payload / 'transfer-sha256.json').read_bytes())
        require(inventory == {p.relative_to(payload).as_posix(): system.baseline.digest(p)
                              for p in sorted(payload.rglob('*'))
                              if p.is_file() and p.name != 'transfer-sha256.json'},
                'setup:payload-changed')
        package = 'package.' + system.package_format(self.verified.lease.capture.state['guest'])
        require(inventory[package] == self.verified.inputs['package_sha256'],
                'setup:package-changed')
        selection = json.loads((payload / 'selected-inputs.json').read_bytes())
        for target, entry in selection['files'].items():
            require(inventory[target] == entry['sha256'], 'setup:helper-changed')
        self.transport.copy(False, str(payload) + '/', system.PAYLOAD + '/')
        guard()
        self.verified.recheck()

    def run(self, guard, *, verify=True):
        """Install and verify after reboot, or stage a powered-off suite snapshot."""
        self.provision(guard)
        run = self.verified.lease.state['run']
        # Execute the frozen recipe whose digest identifies the snapshot.
        recipe = {}
        path = self.directory / 'input/guest_install_recipe.py'
        exec(compile(path.read_bytes(), str(path), 'exec'), recipe)
        # Suite snapshots shut down after package verification. Their next boot
        # supplies the required restart; live feature setup needs it here.
        try:
            recipe['prepare'](self.transport,
                system.guest_command(run, 'install-setup' if verify else 'install-suite'), guard,
                reboot=verify)
            if verify:
                self.transport.call(system.guest_command(run, 'verify-setup'), timeout=660)
        except Exception as error:
            # Package commands keep their streams in the guest's existing
            # private stage artifacts. Preserve them before the caller restores
            # its baseline, including standalone snapshot preparation failures.
            try:
                guard()
                self.transport.copy(True, system.PAYLOAD + '/private/',
                                    str(self.directory / 'guest-private') + '/')
            except Exception:
                error.add_note('setup:diagnostics-unavailable')
            raise
        self.verified.recheck()
        return {'package_verified': verify, 'setup_reboot_verified': verify}
