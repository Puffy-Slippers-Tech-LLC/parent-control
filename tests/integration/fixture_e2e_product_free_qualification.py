"""Preparation-only proof of the real product-free graphical entry boundaries."""
from copy import deepcopy
import os
from pathlib import Path
import sys
import tempfile
import traceback
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'tests/e2e'))
sys.path.insert(0, str(ROOT))

import e2e_fixture_preparation as preparation
import fixture_system_qualification as shared
import fixture_provision_qualification as proof
import installed_setup
from installed_journey import prepare_product_free_setup
from parent_setup_qualification import (GdmProductFreeQualification,
    ProductFreeEntryQualification, PackageInstallQualification, UpgradeAssetsQualification)
from provenance import VerifiedInputs, preflight_source
from build_test_artifacts import verify_upgrade
from execution import open_source
from suite_lease import Suite
from vm_transport import Transport
from observation_transport import ReadOnlyObservations
from qualification_storage import allocate, session
import system_runner as system
from tools import fixture_execution, fixture_manifest, fixture_provision
from tools.test_storage import authenticated_input
from tests.fixtures import native_assets


def selected_target():
    name = proof.prepare_vm.vm_config.selected().name
    system.require(name == 'onpc-Ubuntu26.04',
                   'fixture-e2e-product-free:target-not-qualified')
    return name


def refuse_previous(previous, result):
    if not previous:
        return
    try:
        previous['controller'].require_ready(previous['receipt'])
    except ValueError as error:
        system.require(str(error) == 'fixture-provision:terminal-attempt',
                       'fixture-e2e-product-free:unexpected-stale-refusal')
    else:
        raise system.Error('fixture-e2e-product-free:stale-readiness-accepted')
    result['prior_generation_refused'] = True


def refused_inputs(context, selection):
    wrong = deepcopy(selection.record())
    wrong['target'] = 'fedora'
    wrong['allocation'] = wrong['allocation'].replace('runtime-ubuntu-', 'runtime-fedora-')
    result = {}
    for label, value, reason in (
            ('missing', None, 'fixtures:execution-selection-required'),
            ('incompatible', wrong, 'fixtures:e2e-product-free-target-not-qualified')):
        try:
            preparation.prepare(context['vm'], context['lease'], context['directory'], value,
                                product_free=True)
        except ValueError as error:
            system.require(str(error) == reason,
                           'fixture-e2e-product-free:unexpected-refusal')
            result[label] = reason
        else:
            raise system.Error('fixture-e2e-product-free:invalid-input-released')
    system.require(not (context['directory'] / 'fixture-staging-intent.json').exists(),
                   'fixture-e2e-product-free:refusal-wrote-staging')
    return result


def no_input_payload(vm):
    """Neither reusable bytes nor the customer package were copied before SSH."""
    for path in (system.PAYLOAD, '/var/lib/onpc-e2e-assets'):
        vm.call(['/usr/bin/test', '!', '-e', path], timeout=30, attempts=1)


def observer(selection, manifest, result, previous, source):
    state = {}

    def observe(stage, context):
        vm, lease, directory = (context[key] for key in ('vm', 'lease', 'directory'))
        if stage == 'before':
            no_input_payload(vm)
            shared.wait_environment(vm, lease, directory)
            before = proof.audit(vm, manifest, preparation.SUBSETS)
            system.require(not before['installed'] and not before['files']
                and not before['unselected_present'] and not before['staging']
                and before['preserved']['@attempt-trust'] is None,
                'fixture-e2e-product-free:capture-not-clean')
            state['refusals'] = refused_inputs(context, selection)
            proof.verify_repeat(before, proof.audit(vm, manifest, preparation.SUBSETS))
            no_input_payload(vm)
            state['before'] = before
            return
        system.require(stage == 'ready' and 'before' in state,
                       'fixture-e2e-product-free:observer-order')
        controller, receipt = context['controller'], context['receipt']
        observed = proof.audit(vm, manifest, preparation.SUBSETS)
        members = proof.validate_readback(observed, manifest, preparation.SUBSETS,
                                         receipt.binding, installed=False)
        system.require(receipt.binding['attempt_id'] == preparation.attempt_id(directory),
                       'fixture-e2e-product-free:unbound-readiness')
        proof.unchanged_policy(state['before'], observed)
        witnesses = proof.runtime_witnesses(vm, members, observed['accounts'], selection.target,
                                           only=(native_assets.executable_path('A'),))
        before_repeat = proof.audit(vm, manifest, preparation.SUBSETS)
        edit = shared.source_edit_proof(source, selection, manifest)
        system.require(fixture_execution.verify(selection) == manifest,
                       'fixture-e2e-product-free:selected-input-changed')
        repeated = controller.provision(selection, preparation.SUBSETS,
                                       attempt_id=preparation.attempt_id(directory))
        controller.require_ready(repeated)
        system.require(repeated == receipt, 'fixture-e2e-product-free:version-switched')
        final = proof.audit(vm, manifest, preparation.SUBSETS)
        proof.verify_repeat(before_repeat, final)
        proof.unchanged_policy(state['before'], final)
        refuse_previous(previous, result)
        controller.require_ready(receipt)
        previous.update(controller=controller, receipt=receipt)
        result.update(binding=receipt.binding, readback=final, refusals=state['refusals'],
            runtime_witnesses=witnesses, host_edit=edit, repeat_without_writes=True,
            selected_input_unchanged=True, no_preboot_payload=True,
            product_absent=True, worker_input_released=False,
            customer_package_input_released=False, product_assertions_started=False,
            domain_id=lease.state['domain_id'])
        (directory / 'fixture-preparation-result.json').write_bytes(system.baseline.encode(result))
    return observe


def empty_observer(result, previous):
    # This path uses only the finite declaration, never a selected native bundle.
    declaration = {'members': {key: {name: value for name, value in member.items()
                                    if name != 'source'}
                               for key, member in fixture_manifest.declarations().items()},
                   'absences': fixture_manifest.ABSENCES}
    state = {}

    def observe(stage, context):
        vm, directory = context['vm'], context['directory']
        system.require(stage in ('before', 'empty'),
                       'fixture-e2e-product-free:empty-observer-order')
        no_input_payload(vm)
        audit = proof.audit(vm, declaration, ())
        system.require(not audit['installed'] and not audit['files']
            and not audit['unselected_present'] and not audit['staging']
            and not audit['trust_entries'] and not audit['admissions']
            and audit['preserved']['@attempt-trust'] is None,
            'fixture-e2e-product-free:empty-entry-not-clean')
        if stage == 'before':
            system.require(not state, 'fixture-e2e-product-free:empty-observer-order')
            state['before'] = audit
            return
        system.require('before' in state, 'fixture-e2e-product-free:empty-observer-order')
        proof.verify_repeat(state['before'], audit)
        refuse_previous(previous, result)
        system.require(not (directory / 'fixture-staging-intent.json').exists(),
                       'fixture-e2e-product-free:empty-staging')
        result.update(readback=audit, selection=None, native_input_required=False,
            no_preboot_payload=True, empty_without_writes=True, product_absent=True,
            worker_input_released=False, customer_package_input_released=False,
            product_assertions_started=False)
        (directory / 'fixture-preparation-result.json').write_bytes(system.baseline.encode(result))
    return observe


def run_history(suite, directory, qualification_class, selection, observe):
    """Use the smoke's actual context preparation and the journey's shared seam."""
    lease = suite.lease
    with lease:
        if lease.__dict__.get('_fixture_provision_state') is not None:
            fixture_provision.reset_after_restore(lease)
        lease.prepare()
        host_key = system.bootstrap(suite.commands, lease, directory, suite.guestfs,
                                   observation_only=True, e2e_product_free=True)
        lease.guard(off=True)
        lease.save('isolated')
        empty = qualification_class is GdmProductFreeQualification
        verified = VerifiedInputs(lease=lease, assets=None if empty else directory / 'input',
            root=ROOT, **({} if empty else {'package_only': True,
                                          'upgrade': qualification_class.upgrade_assets}))
        suite.verified = verified
        qualification = object.__new__(qualification_class)
        qualification.directory, qualification.assets = directory, verified.assets
        qualification.commands, qualification.result = suite.commands, {}
        qualification.verified, qualification.guestfs = verified, suite.guestfs
        qualification.fixture_selection = None if empty else selection.record()
        context = SimpleNamespace(directory=directory, verified=verified, lease=lease,
            commands=suite.commands, host_key=host_key,
            fixture_selection=qualification.fixture_selection, product_free=True)
        qualification.prepare_context(context)
        lease.start()
        hostname = system.address(suite.source)
        (directory / 'known-hosts').write_text(f'{hostname} {host_key}\n')
        vm = Transport({'directory': str(directory), 'hostname': hostname,
            'domain_uuid': suite.source.uuid, 'domain_id': lease.view.domain_id,
            'run': lease.state['run']}, suite.commands, guard=lambda _: lease.guard(), lease=lease)
        vm.probe_ready()
        prepared = prepare_product_free_setup(context, vm, lease.guard, observer=observe)
        if empty:
            system.require(prepared is None and not hasattr(verified, 'fixture_prepared'),
                           'fixture-e2e-product-free:empty-native-dependency')
            return None
        assets = context.asset_transfer.observe(ReadOnlyObservations(vm))
        prepared['controller'].require_ready(prepared['receipt'])
        return {'inventory': assets, 'preparation': qualification.result}


def qualify_pinned(directory, assets, selection, manifest, source):
    suite = Suite(open_source)
    result = {'target': selected_target(), 'selection': selection.record(), 'attempts': []}
    private = directory / 'private'
    private.mkdir(mode=0o700)
    suite.commands = system.EvidenceCommands(private)
    suite.commands.directory = private
    try:
        source_assets = system.artifact_source(assets)
        proof.preflight_source(source_assets / 'current')
        verify_upgrade(source_assets, repository=ROOT)
        ledger = system.RunLedger()
        suite.acquire(ledger)
        previous = {}
        for index, qualification_class in enumerate((ProductFreeEntryQualification,
                PackageInstallQualification, UpgradeAssetsQualification, GdmProductFreeQualification)):
            history = directory / ('history-' + str(index + 1))
            history.mkdir(mode=0o700)
            empty = qualification_class is GdmProductFreeQualification
            if empty:
                (history / 'input').mkdir(mode=0o700)
                (history / 'input/selected-inputs.json').write_bytes(system.baseline.encode({
                    'schema_version': 1, 'scope': 'fixture-e2e-product-free-empty'}))
            else:
                if qualification_class.upgrade_assets:
                    system.stage_upgrade_assets(source_assets, history / 'assets', suite.commands,
                                                package_only=True)
                else:
                    system.stage_assets(source_assets / 'current', history / 'assets', suite.commands,
                                        package_only=True)
                preflight_source(history / 'assets', upgrade=qualification_class.upgrade_assets,
                                 package_only=True)
                installed_setup.stage(history, history / 'assets', {},
                    bundle=suite.input_bundle(ROOT), package_only=True)
            attempt = {'restore_owner': 'SuiteLease.prepare',
                       'preparation_owner': qualification_class.__name__ + '.prepare_context',
                       'closure': 'empty' if empty else 'native'}
            observe = (empty_observer(attempt, previous) if empty else
                       observer(selection, manifest, attempt, previous, source))
            attempt['assets'] = run_history(suite, history, qualification_class, selection, observe)
            system.require(suite.lease.state['phase'] == 'complete'
                and suite.lease.view.snapshot()[1] and suite.lease.view.domain_id is None,
                'fixture-e2e-product-free:attempt-cleanup-incomplete')
            attempt['owned_restoration_verified'] = True
            result['attempts'].append(attempt)
            (directory / 'attempt-results.json').write_bytes(system.baseline.encode(result))
        native = [attempt for attempt in result['attempts'] if attempt['closure'] == 'native']
        for first, second in zip(native, native[1:]):
            a, b = first['binding'], second['binding']
            system.require(a['boot_sha256'] != b['boot_sha256']
                and a['attempt_id'] != b['attempt_id'] and first['domain_id'] != second['domain_id']
                and a['vm_uuid'] == b['vm_uuid'] and a['manifest_sha256'] == b['manifest_sha256']
                and a['content_identity'] == b['content_identity'],
                'fixture-e2e-product-free:fresh-readiness-required')
    finally:
        suite.close()
    result['owned_baseline_restoration_verified'] = True
    return result


def qualify(directory, assets, selection, source_selection):
    selected_target()
    selection = fixture_execution.Selection.from_record(
        preparation.validate_input(selection, target='ubuntu', product_free=True))
    source_selection = fixture_execution.validate_source_selection(source_selection, selection)
    with authenticated_input(selection.record()):
        with authenticated_input(source_selection) as source:
            manifest = fixture_execution.verify(selection)
            fixture_provision.authenticated_bundle(selection)
            shared.source_edit_proof(source, selection, manifest)
            return qualify_pinned(directory, assets, selection, manifest, source)


def main(*, assets, selection, source_selection):
    directory = None
    try:
        system.require(os.geteuid() == 0, 'fixture-e2e-product-free:root-required')
        selected_target()
        os.umask(0o077)
        with session():
            directory = Path(allocate(tempfile.mkdtemp, prefix='onpc-fixture-e2e-product-free-'))
            result = qualify(directory, assets, selection, source_selection)
            (directory / 'result.json').write_bytes(system.baseline.encode(result))
        print('fixture-e2e-product-free: passed; evidence=' + str(directory), flush=True)
        return 0
    except (Exception, KeyboardInterrupt) as error:
        if directory is not None:
            (directory / 'controller-error.txt').write_text(traceback.format_exc())
        print('fixture-e2e-product-free: ' + system.error_category(error), file=sys.stderr, flush=True)
        if directory is not None:
            print('fixture-e2e-product-free: evidence=' + str(directory), file=sys.stderr, flush=True)
        return 1
