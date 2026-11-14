"""Qualify FIX05 after the ordinary guarded installed-snapshot restore."""
import os
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'tests/e2e'))
sys.path.insert(0, str(ROOT))

from execution import open_source
import installed_setup
from lunar_profile import LunarProfile
from provenance import VerifiedInputs, preflight_source
from qualification_storage import run_qualification
from suite_lease import Suite
import system_runner as system


def qualify(directory, assets):
    suite = Suite(open_source)
    private = directory / 'private'
    private.mkdir(mode=0o700)
    suite.commands.directory = private
    result = {}
    try:
        system.stage_assets(system.artifact_source(assets), directory / 'assets',
                            suite.commands, package_only=True)
        preflight_source(directory / 'assets', package_only=True)
        installed_setup.stage(directory, directory / 'assets',
                              {'scope': 'lunar-profile'}, bundle=suite.input_bundle(ROOT),
                              package_only=True)
        assets = directory / 'input'
        _, _, lease = suite.acquire(system.RunLedger())
        with lease:
            suite.prepare_case({'preconditions': ['installed-digest-verified-product']},
                               directory, assets, {'scope': 'lunar-profile'}, root=ROOT)
            host_key = system.bootstrap(suite.commands, lease, directory, suite.guestfs,
                                        e2e_installed=True)
            suite.verified = VerifiedInputs(lease=lease, assets=assets, root=ROOT, package_only=True)
            transport = suite.start_transport(directory, host_key)
            result['profile'] = LunarProfile(transport, suite.verified).verify()
            result['target'] = suite.source.domain.name()
            result['installed_snapshot'] = lease.installed_name
    finally:
        suite.close()
    result['owned_baseline_restoration_verified'] = True
    return result


def main(*, assets):
    def preflight():
        import prepare_vm
        system.require(os.geteuid() == 0, 'lunar-profile:root-required')
        system.require(prepare_vm.vm_config.selected().name == 'onpc-Ubuntu26.04-110',
                       'lunar-profile:target-not-qualified')
    return run_qualification('lunar-profile', lambda directory: qualify(directory, assets),
                             preflight=preflight)
