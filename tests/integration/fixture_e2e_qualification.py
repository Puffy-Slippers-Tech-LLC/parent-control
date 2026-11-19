"""Verify installed fixture integrity and consumer readiness after each restore."""
from copy import deepcopy
import os
from pathlib import Path
import sys
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
from asset_transfer import AssetTransfer
from observation_transport import ReadOnlyObservations
from qualification_storage import run_qualification
import system_runner as system
from tools import fixture_execution, fixture_provision
from tools.test_storage import authenticated_input
from tests.fixtures import native_assets


def verify_consumers(context, vm, setup, result, previous):
    """Verify the fixtures through the actual consumers and audit for writes."""
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


def activity_readiness_refusals(vm, verified, previous):
    """Exercise the actual consumer guard without permitting a guest read."""
    from native_fixtures import NativeFixtures
    from private_artifacts import EvidenceError
    current = verified.fixture_prepared
    def forbidden(*_args, **_kwargs):
        raise system.Error('fixture-e2e:unready-consumer-released')
    guarded = SimpleNamespace(config=dict(vm.config), guard=vm.guard, call=forbidden)
    if previous:
        candidates = [('stale', {**current, **previous}, 'fixture-provision:terminal-attempt')]
    else:
        candidates = [
            ('missing', None, 'fixtures:readiness-required'),
            ('incompatible', {**current, 'subsets': ('native',), 'caller': None},
             'fixtures:e2e-profile-not-qualified')]
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


def observer(selection, manifest, result, previous, *, mode):
    subsets = preparation.ACTIVITY_SUBSETS
    state = {}
    def observe(stage, context):
        vm, lease, directory = (context[key] for key in ('vm', 'lease', 'directory'))
        if stage == 'before':
            if mode == 'online':
                result['refusals'] = refused_inputs(context, selection)
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
        # Both attachments use the same provisioner and guards. Prove its
        # idempotency on the online route and keep a fresh readback on each.
        if mode == 'online':
            with installed_setup.timed_stage('fixture-repeat-provision-and-audit'):
                observed = proof.repeat_provision(vm, controller, receipt, selection, manifest,
                    subsets, observed, attempt_id=preparation.attempt_id(directory), prefix='fixture-e2e')
            result['repeat_without_writes'] = True
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
        result.update(binding=receipt.binding, readback=observed,
            runtime_witnesses=witnesses, selected_input_unchanged=True)
        result.update(domain_id=lease.state['domain_id'], credential_rebind_verified=lease.installed_online)
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
        vm = suite.start_transport(directory, host_key)
        system.require(lease.installed_online == (mode == 'online')
                       and lease.online_pending is False and lease.online_bootstrap is None,
                       'fixture-e2e:restore-transport-not-bound')
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


def qualify_pinned(directory, assets, selection, manifest, source, edit):
    suite = Suite(open_source)
    result = {'target': selected_target(), 'selection': selection.record(),
              'subsets': list(preparation.ACTIVITY_SUBSETS),
              'caller': preparation.ACTIVITY_CALLER,
              'host_edit': edit, 'attempts': []}
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
            observe = observer(selection, manifest, attempt, previous, mode=mode)
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
        online, offline = result['attempts']
        a, b = online['binding'], offline['binding']
        system.require(a['boot_sha256'] != b['boot_sha256'] and a['attempt_id'] != b['attempt_id']
            and online['domain_id'] != offline['domain_id'] and a['vm_uuid'] == b['vm_uuid']
            and a['manifest_sha256'] == b['manifest_sha256']
            and a['content_identity'] == b['content_identity'], 'fixture-e2e:fresh-readiness-required')
        system.require(shared.source_edit_proof(source, selection, manifest) == edit,
                       'fixture-e2e:source-proof-changed')
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
            edit = shared.source_edit_proof(source, selection, manifest)
            return qualify_pinned(directory, assets, selection, manifest, source, edit)


def main(*, assets, selection, source_selection):
    def preflight():
        system.require(os.geteuid() == 0, 'fixture-e2e:root-required')
        selected_target()

    return run_qualification('fixture-e2e',
        lambda directory: qualify(directory, assets, selection, source_selection),
        preflight=preflight)
