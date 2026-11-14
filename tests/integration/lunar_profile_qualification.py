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


def qualify(directory, assets, *, launch_quit=False, tray=False):
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
            if launch_quit or tray:
                result['launcher'] = qualify_launch_quit(directory, lease, transport, suite.verified,
                                                       tray=tray)
    finally:
        suite.close()
    result['owned_baseline_restoration_verified'] = True
    return result


def qualify_launch_quit(directory, lease, transport, verified, *, tray=False):
    """Reuse guarded normal sign-in, with no unrelated movable fixtures."""
    from dataclasses import replace
    from types import SimpleNamespace
    import e2e_worker
    from fixture_credentials import FixtureCredentials
    from fresh_desktop import STANDARD_PLAN
    from installed_journey import InstalledJourney
    from ui_observations import UiObservations

    initial = ('observer-ready', 'quit', 'closed', 'launch', 'opened')
    # The app-presence slice needs no launcher-feature exercise. Preserve the
    # existing Settings regression only for its separate launch/Quit selector.
    independent_actions = (('snapshot', 'quit', 'closed') if tray else (
        'opened', 'settings', 'settings-opened', 'quit', 'closed'))
    operations = ['lunar-' + action for action in initial + independent_actions]

    def exercise(journey, guard):
        results = []
        ui = UiObservations(transport)
        ui.boot_guard = journey.boot
        for action in initial:
            guard()
            results.append(ui.observe('lunar-' + action))
        # A fresh consumer accepts the independently supplied usable launcher;
        # no launch history, window cache or process result supplies readiness.
        independent = UiObservations(transport)
        independent.boot_guard = journey.boot
        original = results[-1]['lunar']
        for action in independent_actions:
            guard()
            value = independent.observe('lunar-' + action)
            results.append(value)
            if tray and action == 'snapshot':
                current = value['lunar']
                system.require(current == original,
                               'lunar-tray:launcher-replaced')
        guard()
        return results

    label = 'lunar-tray' if tray else 'lunar-launch-quit'
    plan = replace(STANDARD_PLAN, stage_actions={'desktop': label})
    context = SimpleNamespace(directory=directory, lease=lease, verified=verified)
    credentials = FixtureCredentials()
    credentials.provision_online(lease, transport)
    steps = []

    def progress(stage, observed):
        steps.append(observed)

    journey = InstalledJourney(context, progress, plan,
        actions={label: exercise}, transport=transport)

    def validate():
        system.require(not journey.failed and [step['stage'] for step in steps] == list(plan.stages),
                       label + ':incomplete-journey')
        results = steps[-1].get('fixture', [])
        system.require([value.get('operation') for value in results] == operations
                       and all(value.get('outcome') == 'passed' for value in results),
                       label + ':missing-results')

    def observe(guard):
        journey.step(guard)
        return len(steps) == len(plan.stages)

    worker = e2e_worker.run_distribution(directory, lease, system.RunLedger(),
        expected_inputs=verified.source_files, observe=lambda: None,
        validate=validate, guarded_observe=observe, credentials=credentials,
        attached=True, timeout=1800)
    validate()
    return {'steps': steps, 'worker': worker}


def main(*, assets, launch_quit=False, tray=False):
    def preflight():
        import prepare_vm
        system.require(os.geteuid() == 0, 'lunar-profile:root-required')
        system.require(prepare_vm.vm_config.selected().name == 'onpc-Ubuntu26.04-110',
                       'lunar-profile:target-not-qualified')
    label = 'lunar-tray' if tray else 'lunar-launch-quit' if launch_quit else 'lunar-profile'
    return run_qualification(label, lambda directory: qualify(
        directory, assets, launch_quit=launch_quit, tray=tray),
                             preflight=preflight)
