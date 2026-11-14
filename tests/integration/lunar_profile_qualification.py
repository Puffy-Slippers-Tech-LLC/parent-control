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


def qualify(directory, assets, *, launch_quit=False, tray=False, denial=False,
            fixture_selection=None):
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
            if denial:
                # The unrelated allowed app uses the existing native fixture
                # provisioner; supplied vendor profiles remain read-only.
                installed_setup.InstalledSetup(directory, suite.verified, transport).provision(
                    lease.guard, fixture_selection=fixture_selection)
            result['profile'] = LunarProfile(transport, suite.verified).verify()
            result['target'] = suite.source.domain.name()
            result['installed_snapshot'] = lease.installed_name
            if denial:
                from calendar_fixture import preset_ordinary_daytime
                from lunar_denial import PLAN
                from native_fixtures import fixture_actions
                from policy_edits import AppPolicyJourney
                result['denial'] = run_journey(directory, lease, transport, suite.verified,
                    PLAN, {**fixture_actions(include_refusal=False),
                           'daytime-clock': preset_ordinary_daytime}, journey_class=AppPolicyJourney)
            elif launch_quit or tray:
                result['launcher'] = qualify_launch_quit(directory, lease, transport, suite.verified,
                                                       tray=tray)
    finally:
        suite.close()
    result['owned_baseline_restoration_verified'] = True
    return result


def qualify_launch_quit(directory, lease, transport, verified, *, tray=False):
    """Reuse guarded normal sign-in, with no unrelated movable fixtures."""
    from dataclasses import replace
    from fresh_desktop import STANDARD_PLAN
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
    return run_journey(directory, lease, transport, verified, plan, {label: exercise},
                       expected_operations=operations)


def run_journey(directory, lease, transport, verified, plan, actions, *, journey_class=None,
                expected_operations=None):
    """Keep Lunar's finite results inside the shared attached-worker envelope."""
    from desktop_session import run_attached
    from installed_journey import InstalledJourney

    def progress(stage, observed):
        if expected_operations is not None and stage == plan.stages[-1]:
            results = observed.get('fixture', [])
            system.require([value.get('operation') for value in results] == expected_operations
                           and all(value.get('outcome') == 'passed' for value in results),
                           plan.prefix + ':missing-results')

    worker = run_attached(directory, lease, transport, system.RunLedger(), plan,
        expected_inputs=verified.source_files, progress=progress, actions=actions,
        journey_type=journey_class or InstalledJourney, verified=verified, timeout=1800)
    return {'steps': worker['controller_observations'], 'worker': worker}


def main(*, assets, launch_quit=False, tray=False, denial=False, fixture_selection=None):
    def preflight():
        import prepare_vm
        system.require(os.geteuid() == 0, 'lunar-profile:root-required')
        system.require(prepare_vm.vm_config.selected().name == 'onpc-Ubuntu26.04-110',
                       'lunar-profile:target-not-qualified')
    if denial:
        from e2e_fixture_preparation import validate_input
        fixture_selection = validate_input(fixture_selection)
    label = ('lunar-denial' if denial else 'lunar-tray' if tray else
             'lunar-launch-quit' if launch_quit else 'lunar-profile')
    return run_qualification(label, lambda directory: qualify(
        directory, assets, launch_quit=launch_quit, tray=tray, denial=denial,
        fixture_selection=fixture_selection),
                             preflight=preflight)
