"""Installed fixture proof and finite baseline child catalogue qualification."""
from copy import deepcopy
import hashlib
import os
from pathlib import Path
import sys
import time
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'tests/e2e'))
sys.path.insert(0, str(ROOT))

import e2e_fixture_preparation as preparation
import fixture_system_qualification as shared
import fixture_provision_qualification as proof
import installed_setup
from installed_journey import prepare_installed_setup
from parent_setup_qualification import KioskEntryQualification
from provenance import VerifiedInputs
from execution import open_source
from suite_lease import Suite
from vm_transport import Transport
from asset_transfer import AssetTransfer
from observation_transport import ReadOnlyObservations
from qualification_storage import run_qualification
import system_runner as system
from tools import fixture_execution, fixture_provision
from tools.test_storage import authenticated_input
from tests.fixtures import native_assets


def verify_consumers(context, vm, setup, result, previous):
    """Keep fixture consumers/readback independent of the catalogue UI history."""
    system.require(setup['child_fixture'] == {'verified': len(native_assets.ASSETS),
        'verified_files': len(native_assets.sources(alias=False)), 'child_role': 'child',
        'independent_readback': True}, 'fixture-e2e:child-consumer-not-verified')
    system.require(setup['activity_fixture'] == {
        'verified_files': len(native_assets.activity_sources()),
        'native_trust': True, 'independent_readback': True},
        'fixture-e2e:activity-consumer-not-verified')
    result['child_fixture'] = setup['child_fixture']
    result['activity_fixture'] = setup['activity_fixture']
    result['consumer_refusals'] = activity_readiness_refusals(
        vm, context.verified, previous)
    with installed_setup.timed_stage('fixture-consumer-final-audit'):
        final = proof.audit(vm, fixture_execution.verify(
            fixture_execution.Selection.from_record(context.fixture_selection)),
            preparation.ACTIVITY_SUBSETS)
    proof.verify_repeat(result['readback'], final)


def catalogue_journey(context, progress, result, previous):
    """Finite catalogue/save checks within the existing qualified Parent envelope."""
    from accessible_ui import MATCH_RULES
    from parent_toggle import ParentToggleJourney
    from ui_observations import SettingsObservation, compare_settings

    apps = {role: 'parent-app-' + hashlib.sha256(native_assets.desktop_id(role).encode()).hexdigest()[:16]
            for role, *_ in native_assets.ASSETS}

    class CatalogueJourney(ParentToggleJourney):
        def step(self, guard):
            self.current_guard = guard
            return super().step(guard)

        def observe_public(self, operation, *, child=None):
            self.current_guard()
            value = self.ui.observe(operation, **({'child': child} if child else {}))
            self.current_guard()
            return value

        def select(self, child, enabled):
            existing = child == 'existing'
            self.observe_public('existing-child-picker-opened' if existing else 'child-picker-opened')
            self.observe_public('existing-child-choice-highlighted' if existing else 'child-choice-highlighted')
            self.observe_public('access-screen', child=child)
            value = self.observe_public('existing-returned' if existing else 'parent-selected')
            compare_settings(SettingsObservation.from_settings(value['settings']),
                SettingsObservation('existing-fixture-child' if existing else 'fixture-child',
                                    enabled, ('0 minutes',)))
            self.observe_public('existing-apps' if existing else 'parent-apps-page')

        def rows(self, child, *, hard='allowed', soft='allowed'):
            expected = {apps[role]: (hard if role == 'H' else soft if role == 'S'
                        else 'allowed', match) for role, _, _, _, match in native_assets.ASSETS}
            deadline = time.monotonic() + 30
            while True:
                value = self.observe_public('existing-parent-app-rows' if child == 'existing'
                                            else 'parent-app-rows')['apps']['rows']
                actual = {row[0]: tuple(row[1:]) for row in value if row[0] in apps.values()}
                if actual == expected:
                    break
                system.require(time.monotonic() < deadline, 'fixture-e2e:catalogue-saved-rows')
                time.sleep(0.25)
            for role, operation, rule in (('A', 'match-row', MATCH_RULES[0]),
                    ('H', 'match-hard-row', MATCH_RULES[3]),
                    ('S', 'match-soft-row', MATCH_RULES[4])):
                system.require(self.observe_public(operation, child=child)['match'] ==
                    {'app': apps[role], 'rule': rule}, 'fixture-e2e:catalogue-default-rule')
            return sorted((identity, *values) for identity, values in actual.items())

        def check_settings(self, stage, observed):
            super().check_settings(stage, observed)
            if stage == 'setup-detached':
                verify_consumers(context, self.transport, observed['setup'], result, previous)
                result['assets'] = context.asset_transfer.observe(self.vm)
                result['worker_input_released'] = True
            elif stage == 'parent-selected':
                compare_settings(SettingsObservation.from_settings(observed['ui']['settings']),
                                 SettingsObservation('fixture-child', False, ('0 minutes',)))
                result['product_assertions_started'] = True
            elif stage == 'save-reopened':
                self.select('existing', False)
                jordan = self.rows('existing')
                self.select('child', True)
                initial = self.rows('child')
                self.observe_public('access-hard-permanent', child='child')
                self.observe_public('access-soft-conditional', child='child')
                self.select('existing', False)
                system.require(self.rows('existing') == jordan, 'fixture-e2e:jordan-policy-changed')
                self.select('child', True)
                saved = self.rows('child', hard='permanent', soft='conditional')
                self.observe_public('access-hard-allowed', child='child')
                self.observe_public('access-soft-allowed', child='child')
                self.select('existing', False)
                system.require(self.rows('existing') == jordan, 'fixture-e2e:jordan-policy-changed')
                self.select('child', True)
                system.require(self.rows('child') == initial, 'fixture-e2e:riley-policy-not-restored')
                self.observe_public('parent-screen-page')
                result['catalogue'] = {'riley_defaults': initial, 'riley_saved': saved,
                    'jordan_defaults': jordan, 'fresh_child_reselection': True,
                    'access_restored': True, 'default_matches_preserved': True}
                observed['catalogue'] = result['catalogue']
            elif stage == 'disabled-settings':
                compare_settings(SettingsObservation.from_settings(observed['ui']['settings']),
                                 SettingsObservation('fixture-child', False, ('0 minutes',)))
                balances = self.observe_public('time-explanation-reach-read')['time_explanation']
                system.require(all(balances[key]['seconds'] == 0
                    for key in ('daily', 'one_time', 'total')), 'fixture-e2e:restored-balances')
                result['catalogue']['controls_off'] = True
                result['catalogue']['restored_balances'] = balances

    return CatalogueJourney(context, progress)


def activity_readiness_refusals(vm, verified, previous):
    """Exercise the actual consumer guard without permitting a guest read."""
    from native_fixtures import NativeFixtures
    from private_artifacts import EvidenceError
    current = verified.fixture_prepared
    def forbidden(*_args, **_kwargs):
        raise system.Error('fixture-e2e:unready-consumer-released')
    guarded = SimpleNamespace(config=dict(vm.config), guard=vm.guard, call=forbidden)
    candidates = [
        ('missing', None, 'fixtures:readiness-required'),
        ('incompatible', {**current, 'subsets': ('native',), 'caller': None},
         'fixtures:e2e-profile-not-qualified')]
    if previous:
        candidates.append(('stale', {**current, **previous},
                           'fixture-provision:terminal-attempt'))
    result = {}
    try:
        for label, prepared, reason in candidates:
            verified.fixture_prepared = prepared
            try:
                NativeFixtures(guarded, verified, profile='activity').verify()
            except (ValueError, EvidenceError) as error:
                system.require(str(error) == reason, 'fixture-e2e:consumer-refusal-changed')
                result[label] = reason
            else:
                raise system.Error('fixture-e2e:unready-consumer-accepted')
    finally:
        verified.fixture_prepared = current
    return result


def selected_target():
    name = proof.prepare_vm.vm_config.selected().name
    system.require(name in proof.TARGETS, 'fixture-e2e:target-not-qualified')
    return name


def refused_inputs(context, selection):
    wrong = deepcopy(selection.record())
    wrong['target'] = 'fedora' if selection.target == 'ubuntu' else 'ubuntu'
    wrong['allocation'] = wrong['allocation'].replace(
        'runtime-' + selection.target + '-', 'runtime-' + wrong['target'] + '-')
    result = {}
    for label, value, reason in (
            ('missing', None, 'fixtures:execution-selection-required'),
            ('incompatible', wrong, 'fixtures:e2e-installed-target-not-qualified')):
        try:
            preparation.prepare(context['vm'], context['lease'], context['directory'], value)
        except ValueError as error:
            system.require(str(error) == reason, 'fixture-e2e:unexpected-refusal')
            result[label] = reason
        else:
            raise system.Error('fixture-e2e:invalid-input-released')
    system.require(not (context['directory'] / 'fixture-staging-intent.json').exists(),
                   'fixture-e2e:refusal-wrote-staging')
    return result


def observer(selection, manifest, result, previous, source):
    subsets = preparation.ACTIVITY_SUBSETS
    state = {}
    def observe(stage, context):
        vm, lease, directory = (context[key] for key in ('vm', 'lease', 'directory'))
        if stage == 'before':
            state['refusals'] = refused_inputs(context, selection)
            shared.wait_environment(vm, lease, directory)
            with installed_setup.timed_stage('fixture-clean-baseline-audit'):
                before = proof.audit(vm, manifest, subsets)
            system.require(before['installed'] and not before['files']
                and not before['unselected_present'] and not before['staging'],
                'fixture-e2e:capture-not-clean')
            state['before'] = before
            return
        system.require(stage == 'ready' and 'before' in state, 'fixture-e2e:observer-order')
        controller, receipt = context['controller'], context['receipt']
        with installed_setup.timed_stage('fixture-provisioned-readback-audit'):
            observed = proof.audit(vm, manifest, subsets)
        members = proof.validate_readback(observed, manifest, subsets,
                                         receipt.binding, installed=True)
        proof.unchanged_policy(state['before'], observed)
        with installed_setup.timed_stage('fixture-runtime-witnesses'):
            witnesses = proof.runtime_witnesses(vm, members, observed['accounts'], selection.target,
                only=(native_assets.executable_path('A'), native_assets.ACTIVITY_EXECUTABLE))
        edit = shared.source_edit_proof(source, selection, manifest)
        # Runtime launches preserve the audited fixture/native policy state;
        # the source-edit proof changes only host scratch. Compare the exact
        # repeat with the validated observation, covering those operations too
        # without another full native-database audit (atime is not compared).
        with installed_setup.timed_stage('fixture-repeat-provision-and-audit'):
            final = proof.repeat_provision(vm, controller, receipt, selection, manifest,
                subsets, observed, attempt_id=preparation.attempt_id(directory), prefix='fixture-e2e')
        proof.unchanged_policy(state['before'], final)
        if previous:
            try:
                previous['controller'].require_ready(previous['receipt'])
            except ValueError as error:
                system.require(str(error) == 'fixture-provision:terminal-attempt',
                               'fixture-e2e:unexpected-stale-refusal')
            else:
                raise system.Error('fixture-e2e:stale-readiness-accepted')
            result['prior_generation_refused'] = True
        previous.update(controller=controller, receipt=receipt)
        result.update(binding=receipt.binding, readback=final, refusals=state['refusals'],
            runtime_witnesses=witnesses, host_edit=edit, repeat_without_writes=True,
            selected_input_unchanged=True, worker_input_released=False,
            product_assertions_started=False)
        result.update(domain_id=lease.state['domain_id'],
                      credential_rebind_verified=lease.installed_online and
                      lease.online_pending is False and lease.online_bootstrap is None)
        (directory / 'fixture-preparation-result.json').write_bytes(system.baseline.encode(result))
    return observe


def run_history(suite, directory, assets, selection, observe, mode, *, result, previous):
    """Actual Suite online branch and KioskEntry's separate offline attachment."""
    lease = suite.lease
    with lease:
        if lease.__dict__.get('_fixture_provision_state') is not None:
            fixture_provision.reset_after_restore(lease)
        suite.snapshot_mode = mode
        suite.prepared = False
        if mode == 'online':
            suite.prepare_case({'preconditions': ['installed-digest-verified-product']},
                               directory, assets, {}, root=ROOT)
        else:
            suite.prepare_installed(directory, assets, {}, root=ROOT, overwrite=False, mode=mode)
            lease.restore_installed = False
            lease.stop()
            lease.prepare()
            qualification = object.__new__(KioskEntryQualification)
            qualification.directory, qualification.assets = directory, assets
            qualification.commands, qualification.result = suite.commands, {}
            qualification.attach_installed_snapshot(lease)
        host_key = system.bootstrap(suite.commands, lease, directory, suite.guestfs,
                                    e2e_installed=True)
        lease.save('isolated')
        verified = VerifiedInputs(lease=lease, assets=assets, root=ROOT, package_only=True)
        suite.verified = verified
        # The two attachment routes protect different restore/credential
        # boundaries, but start with the same fresh product state. Exercise
        # catalogue saves once; the offline route retains the complete fixture
        # preparation and consumer checks without another graphical worker.
        if mode == 'online':
            from app_snapshot import snapshot_name
            from fixture_credentials import FixtureCredentials
            import e2e_worker
            credentials = FixtureCredentials()
            result['fixture_credentials'] = credentials.provision(
                lease, verified, directory, suite.guestfs, suite.commands)
            context = SimpleNamespace(directory=directory, verified=verified, lease=lease,
                commands=suite.commands, host_key=host_key,
                fixture_selection=selection.record(), fixture_subsets=preparation.ACTIVITY_SUBSETS,
                fixture_caller=preparation.ACTIVITY_CALLER, fixture_observer=observe,
                asset_transfer=AssetTransfer(verified),
                installed_snapshot=snapshot_name(system.package_version(suite.commands,
                    assets / ('package.' + system.package_format(lease.capture.state['guest'])))))
            def progress(_stage, _observed):
                (directory / 'fixture-preparation-result.json').write_bytes(
                    system.baseline.encode(result))
            journey = catalogue_journey(context, progress, result, previous)
            def failed(_category, _code):
                journey.collect_failure()
            result['worker_evidence'] = e2e_worker.run_distribution(
                directory, lease, lease.ledger, expected_inputs=verified.source_files,
                observe=lambda: None, guarded_observe=journey.step, validate=journey.validate,
                on_failure=failed, timeout=1800, credentials=credentials)
            result['matched_screens'] = journey.validate()
            system.require(result['worker_evidence']['shutdown_verified'] is True,
                           'fixture-e2e:worker-shutdown-unverified')
            return result['assets']
        lease.start()
        hostname = system.address(suite.source)
        (directory / 'known-hosts').write_text(f'{hostname} {host_key}\n')
        vm = Transport({'directory': str(directory), 'hostname': hostname,
            'domain_uuid': suite.source.uuid, 'domain_id': lease.view.domain_id,
            'run': lease.state['run']}, suite.commands, guard=lambda _: lease.guard(), lease=lease)
        vm.probe_ready()
        context = SimpleNamespace(directory=directory, verified=verified, lease=lease,
                                  fixture_selection=selection.record(),
                                  fixture_subsets=preparation.ACTIVITY_SUBSETS,
                                  fixture_caller=preparation.ACTIVITY_CALLER,
                                  asset_transfer=AssetTransfer(verified))
        prepared = prepare_installed_setup(context, vm, lease.guard, observer=observe)
        verify_consumers(context, vm, prepared, result, previous)
        assets_receipt = context.asset_transfer.observe(ReadOnlyObservations(vm))
        verified.fixture_prepared['controller'].require_ready(verified.fixture_prepared['receipt'])
        return assets_receipt


def qualify_pinned(directory, assets, selection, manifest, source):
    suite = Suite(open_source)
    result = {'target': selected_target(), 'selection': selection.record(),
              'subsets': list(preparation.ACTIVITY_SUBSETS),
              'caller': preparation.ACTIVITY_CALLER,
              'attempts': []}
    private = directory / 'private'
    private.mkdir(mode=0o700)
    suite.commands = system.EvidenceCommands(private)
    suite.commands.directory = private
    try:
        source_assets = system.artifact_source(assets)
        proof.preflight_source(source_assets)
        ledger = system.RunLedger()
        suite.acquire(ledger)
        previous = {}
        for index, mode in enumerate(('online', 'offline')):
            history = directory / ('history-' + str(index + 1) + '-' + mode)
            history.mkdir(mode=0o700)
            system.stage_assets(source_assets, history / 'assets', suite.commands, package_only=True)
            installed_setup.stage(history, history / 'assets', {},
                bundle=suite.input_bundle(ROOT), package_only=True)
            attempt = {'app_snapshot_mode': mode,
                       'restore_owner': 'Suite.prepare_case' if mode == 'online' else
                                        'KioskEntryQualification.attach_installed_snapshot'}
            observe = observer(selection, manifest, attempt, previous, source)
            prior = dict(previous)
            with installed_setup.timed_stage('fixture-history-' + mode):
                attempt['assets'] = run_history(suite, history, history / 'input', selection,
                            observe, mode, result=attempt, previous=prior)
            system.require(suite.lease.state['phase'] == 'complete'
                and suite.lease.view.snapshot()[1] and suite.lease.view.domain_id is None,
                'fixture-e2e:attempt-cleanup-incomplete')
            attempt['owned_restoration_verified'] = True
            result['attempts'].append(attempt)
            (directory / 'attempt-results.json').write_bytes(system.baseline.encode(result))
        for first, second in zip(result['attempts'], result['attempts'][1:]):
            a, b = first['binding'], second['binding']
            system.require((second['app_snapshot_mode'] == 'online' or
                            a['boot_sha256'] != b['boot_sha256'])
                and a['attempt_id'] != b['attempt_id']
                and first['domain_id'] != second['domain_id'] and a['vm_uuid'] == b['vm_uuid']
                and a['manifest_sha256'] == b['manifest_sha256']
                and a['content_identity'] == b['content_identity'],
                'fixture-e2e:fresh-readiness-required')
    finally:
        suite.close()
    result['owned_baseline_restoration_verified'] = True
    return result


def qualify(directory, assets, selection, source_selection):
    target = proof.TARGETS[selected_target()]
    selection = fixture_execution.Selection.from_record(
        preparation.validate_input(selection, target=target))
    source_selection = fixture_execution.validate_source_selection(source_selection, selection)
    with authenticated_input(selection.record()):
        with authenticated_input(source_selection) as source:
            manifest = fixture_execution.verify(selection)
            fixture_provision.authenticated_bundle(selection)
            shared.source_edit_proof(source, selection, manifest)
            return qualify_pinned(directory, assets, selection, manifest, source)


def main(*, assets, selection, source_selection):
    def preflight():
        system.require(os.geteuid() == 0, 'fixture-e2e:root-required')
        selected_target()

    return run_qualification('fixture-e2e',
        lambda directory: qualify(directory, assets, selection, source_selection),
        preflight=preflight)
