"""Preparation-only proof at the installed journey's real shared boundary."""
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
from installed_journey import prepare_installed_setup
from parent_setup_qualification import KioskEntryQualification
from provenance import VerifiedInputs
from execution import open_source
from suite_lease import Suite
from vm_transport import Transport
from asset_transfer import AssetTransfer
from observation_transport import ReadOnlyObservations
from qualification_storage import allocate, session
import system_runner as system
from tools import fixture_execution, fixture_provision
from tools.test_storage import authenticated_input
from tests.fixtures import native_assets


def selected_target():
    name = proof.prepare_vm.vm_config.selected().name
    system.require(name == 'onpc-Ubuntu26.04', 'fixture-e2e:target-not-qualified')
    return name


def refused_inputs(context, selection):
    wrong = deepcopy(selection.record())
    wrong['target'] = 'fedora'
    wrong['allocation'] = wrong['allocation'].replace('runtime-ubuntu-', 'runtime-fedora-')
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
    state = {}
    def observe(stage, context):
        vm, lease, directory = (context[key] for key in ('vm', 'lease', 'directory'))
        if stage == 'before':
            state['refusals'] = refused_inputs(context, selection)
            shared.wait_environment(vm, lease, directory)
            before = proof.audit(vm, manifest, preparation.SUBSETS)
            system.require(before['installed'] and not before['files']
                and not before['unselected_present'] and not before['staging'],
                'fixture-e2e:capture-not-clean')
            state['before'] = before
            return
        system.require(stage == 'ready' and 'before' in state, 'fixture-e2e:observer-order')
        controller, receipt = context['controller'], context['receipt']
        observed = proof.audit(vm, manifest, preparation.SUBSETS)
        members = proof.validate_readback(observed, manifest, preparation.SUBSETS,
                                         receipt.binding, installed=True)
        proof.unchanged_policy(state['before'], observed)
        witnesses = proof.runtime_witnesses(vm, members, observed['accounts'], selection.target,
                                           only=(native_assets.executable_path('A'),))
        before_repeat = proof.audit(vm, manifest, preparation.SUBSETS)
        edit = shared.source_edit_proof(source, selection, manifest)
        system.require(fixture_execution.verify(selection) == manifest,
                       'fixture-e2e:selected-input-changed')
        repeated = controller.provision(selection, preparation.SUBSETS,
                                         attempt_id=preparation.attempt_id(directory))
        controller.require_ready(repeated)
        system.require(repeated == receipt, 'fixture-e2e:version-switched')
        final = proof.audit(vm, manifest, preparation.SUBSETS)
        proof.verify_repeat(before_repeat, final)
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


def run_history(suite, directory, assets, selection, observe, mode):
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
        lease.start()
        hostname = system.address(suite.source)
        (directory / 'known-hosts').write_text(f'{hostname} {host_key}\n')
        vm = Transport({'directory': str(directory), 'hostname': hostname,
            'domain_uuid': suite.source.uuid, 'domain_id': lease.view.domain_id,
            'run': lease.state['run']}, suite.commands, guard=lambda _: lease.guard(), lease=lease)
        vm.probe_ready()
        context = SimpleNamespace(directory=directory, verified=verified, lease=lease,
                                  fixture_selection=selection.record(),
                                  asset_transfer=AssetTransfer(verified))
        prepare_installed_setup(context, vm, lease.guard, observer=observe)
        assets_receipt = context.asset_transfer.observe(ReadOnlyObservations(vm))
        verified.fixture_prepared['controller'].require_ready(verified.fixture_prepared['receipt'])
        return assets_receipt


def qualify_pinned(directory, assets, selection, manifest, source):
    suite = Suite(open_source)
    result = {'target': selected_target(), 'selection': selection.record(), 'attempts': []}
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
        for index, mode in enumerate(('online', 'online', 'offline', 'offline')):
            history = directory / ('history-' + str(index + 1) + '-' + mode)
            history.mkdir(mode=0o700)
            system.stage_assets(source_assets, history / 'assets', suite.commands, package_only=True)
            installed_setup.stage(history, history / 'assets', {},
                bundle=suite.input_bundle(ROOT), package_only=True)
            attempt = {'app_snapshot_mode': mode,
                       'restore_owner': 'Suite.prepare_case' if mode == 'online' else
                                        'KioskEntryQualification.attach_installed_snapshot'}
            attempt['assets'] = run_history(suite, history, history / 'input', selection,
                        observer(selection, manifest, attempt, previous, source), mode)
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
    selected_target()
    selection = fixture_execution.Selection.from_record(preparation.validate_input(selection))
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
        system.require(os.geteuid() == 0, 'fixture-e2e:root-required')
        selected_target()
        os.umask(0o077)
        with session():
            directory = Path(allocate(tempfile.mkdtemp, prefix='onpc-fixture-e2e-'))
            result = qualify(directory, assets, selection, source_selection)
            (directory / 'result.json').write_bytes(system.baseline.encode(result))
        print('fixture-e2e: passed; evidence=' + str(directory), flush=True)
        return 0
    except (Exception, KeyboardInterrupt) as error:
        if directory is not None:
            (directory / 'controller-error.txt').write_text(traceback.format_exc())
        print('fixture-e2e: ' + system.error_category(error), file=sys.stderr, flush=True)
        if directory is not None:
            print('fixture-e2e: evidence=' + str(directory), file=sys.stderr, flush=True)
        return 1
