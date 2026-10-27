"""Package-bound installed setup, before any customer action or secret input."""

import json
from pathlib import Path
import shutil

import system_runner as system
from private_artifacts import require
from guest_inputs import Bundle


def inputs(root):
    return Bundle(root, [('Makefile', 'install-source/Makefile'),
        # Guest enforcement helpers use these maintained flat fixture aliases.
        ('tests/fixtures/baseline_environment.py', 'baseline_environment.py'),
        ('tests/fixtures/baseline_assets.py', 'baseline_assets.py'),
        ('tests/fixtures/native_assets.py', 'native_assets.py'),
        ('tests/fixtures/native_trust.py', 'native_trust.py'),
        *[(relative, Path(relative).name) for relative in (
        'tests/integration/system_guest.py', 'tests/integration/e2e_dynamic_account.py',
        'tests/integration/system_kiosk_confinement.py',
        'tests/integration/system_kiosk_lease_variation.py',
        'tests/integration/system_kiosk_feedback.py',
        'tests/integration/system_wellbeing_qualification.py',
        'tests/integration/wellbeing_probe.py')]])


def snapshot_inputs(bundle):
    """Select installation helpers from the caller's already frozen inputs.

    Snapshot preparation needs no fixture declarations or scenario workers.
    Keep its package recipe and guarded guest entry point, including their
    transitive imports, without reading replacement bytes from the checkout.
    """
    return Bundle(bundle.root, [('Makefile', 'install-source/Makefile'),
        ('tests/integration/system_guest.py', 'system_guest.py')],
        frozen={bundle.sources[target]: data for target, data in bundle.files.items()})


def stage(directory, assets, selection, *, bundle=None, snapshot=False, package_only=False):
    """Bind the existing installed payload and fixed helper bytes before bootstrap."""
    destination = directory / 'input'
    require(not destination.exists(), 'setup:input-exists')
    if package_only:
        from build_test_artifacts import verify
        require(not snapshot and not (assets / 'fixtures').exists(), 'setup:package-only-scope')
        verify(assets, package_only=True)
    bundle = bundle if bundle is not None else inputs(system.ROOT)
    if snapshot:
        # Clean captures retain the package and installation metadata,
        # never artifact fixtures, their build sources or unused guest helpers.
        packages = [name for name in ('package.deb', 'package.rpm')
                    if (assets / name).is_file() and not (assets / name).is_symlink()]
        require(len(packages) == 1 and not any(
            (assets / name).exists() or (assets / name).is_symlink()
            for name in {'package.deb', 'package.rpm'} - set(packages)),
            'setup:snapshot-platform')
        bundle = snapshot_inputs(bundle)
        destination.mkdir(mode=0o700)
        for name in (*packages, 'installed-files.json'):
            shutil.copyfile(assets / name, destination / name)
    elif assets == directory / 'assets':
        # This is the attempt's already frozen private copy. Transfer ownership
        # to its input directory instead of retaining a second complete bundle.
        assets.rename(destination)
    else:
        shutil.copytree(assets, destination)
    files = bundle.stage(destination)
    identity = {'schema_version': 1, 'scope': 'e2e-installed-setup',
                'selection': selection, 'files': files}
    (destination / 'selected-inputs.json').write_bytes(system.baseline.encode(identity))
    inventory = {p.relative_to(destination).as_posix(): system.baseline.digest(p)
                 for p in sorted(destination.rglob('*'))
                 if p.is_file() and p != destination / 'transfer-sha256.json'}
    (destination / 'transfer-sha256.json').write_bytes(system.baseline.encode(inventory))
    if package_only:
        for path in destination.rglob('*'):
            path.chmod(0o700 if path.is_dir() else 0o600)
    return system.baseline.digest(destination / 'selected-inputs.json')


class InstalledSetup:
    """One setup attempt; caller must detach graphics before install/reboot."""

    def __init__(self, directory, verified, transport):
        self.directory, self.verified, self.transport = directory, verified, transport
        self.attempted = False

    def provision(self, guard, *, fixture_selection=None, observer=None,
                  fixture_subsets=('native',), fixture_caller=None):
        """Refresh this attempt's guarded helpers, including on reused snapshots."""
        require(not self.attempted, 'setup:already-attempted')
        self.attempted = True
        guard()
        if fixture_selection is not None:
            from e2e_fixture_preparation import qualified_subsets, validate_input
            qualified_subsets(fixture_subsets, caller=fixture_caller)
            fixture_selection = validate_input(fixture_selection)
        self.verified.recheck()
        payload = self.directory / 'input'
        inventory = json.loads((payload / 'transfer-sha256.json').read_bytes())
        require(inventory == {p.relative_to(payload).as_posix(): system.baseline.digest(p)
                              for p in sorted(payload.rglob('*'))
                              if p.is_file() and p != payload / 'transfer-sha256.json'},
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
        if fixture_selection is not None:
            from e2e_fixture_preparation import prepare
            context = {'vm': self.transport, 'lease': self.verified.lease,
                       'directory': self.directory}
            if observer is not None:
                observer('before', context)
            options = ({'subsets': fixture_subsets, 'caller': fixture_caller}
                       if fixture_subsets != ('native',) else {})
            prepared = prepare(self.transport, self.verified.lease, self.directory,
                               fixture_selection, **options)
            if observer is not None:
                observer('ready', prepared)
            self.verified.fixture_selection = fixture_selection
            self.verified.fixture_prepared = prepared
            return prepared

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
