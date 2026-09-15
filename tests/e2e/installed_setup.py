"""Package-bound installed setup, before any customer action or secret input."""

import json
from pathlib import Path
import shutil

import system_runner as system
from private_artifacts import require


def stage(directory, assets, selection):
    """Bind the existing installed payload and fixed helper bytes before bootstrap."""
    destination = directory / 'input'
    require(not destination.exists(), 'setup:input-exists')
    shutil.copytree(assets, destination)
    files = {}
    for relative in ('tests/integration/system_guest.py', 'tests/integration/owned_commands.py'):
        target = Path(relative).name
        shutil.copyfile(system.ROOT / relative, destination / target)
        files[target] = {'source': relative, 'sha256': system.baseline.digest(destination / target)}
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

    def run(self, guard):
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
        require(inventory['package.deb'] == self.verified.inputs['package_sha256'],
                'setup:package-changed')
        selection = json.loads((payload / 'selected-inputs.json').read_bytes())
        for target, entry in selection['files'].items():
            require(inventory[target] == entry['sha256'] ==
                    self.verified.source_files[entry['source']], 'setup:helper-changed')
        self.transport.copy(False, str(payload) + '/', system.PAYLOAD + '/')
        run = self.verified.lease.state['run']
        guard()
        self.transport.call(system.guest_command(run, 'install-setup'), timeout=1200)
        guard()
        self.transport.reboot()
        guard()
        self.transport.call(system.guest_command(run, 'verify-setup'), timeout=660)
        self.verified.recheck()
        return {'package_verified': True, 'setup_reboot_verified': True}
