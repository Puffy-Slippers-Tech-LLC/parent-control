"""Preparation-only proof through standalone Qualification and Smoke's ready seam."""
from copy import deepcopy
import json
import os
from pathlib import Path
import sys
import tempfile
import traceback
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'tests/e2e'))
sys.path.insert(0, str(ROOT))

import check_graphical_smoke as smoke
import e2e_fixture_preparation as shared_preparation
import smoke_fixture_preparation as preparation
import fixture_system_qualification as shared
import fixture_provision_qualification as proof
from execution import open_source
from provenance import preflight_source
from suite_lease import Suite
from qualification_storage import allocate, session
import system_runner as system
from tools import fixture_execution, fixture_provision
from tools.test_storage import authenticated_input
from tests.fixtures import native_assets


def selected_target():
    name = proof.prepare_vm.vm_config.selected().name
    system.require(name == 'onpc-Ubuntu26.04', 'fixture-transfer:target-not-qualified')
    return name


def refused_inputs(context, selection):
    wrong = deepcopy(selection.record())
    wrong['target'] = 'fedora'
    wrong['allocation'] = wrong['allocation'].replace('runtime-ubuntu-', 'runtime-fedora-')
    result = {}
    for label, value, reason in (
            ('missing', None, 'fixtures:execution-selection-required'),
            ('incompatible', wrong, 'fixtures:transfer-target-not-qualified')):
        try:
            preparation.prepare(context['vm'], context['lease'], context['directory'], value)
        except ValueError as error:
            system.require(str(error) == reason, 'fixture-transfer:unexpected-refusal')
            result[label] = reason
        else:
            raise system.Error('fixture-transfer:invalid-input-released')
    system.require(not (context['directory'] / 'fixture-staging-intent.json').exists(),
                   'fixture-transfer:refusal-wrote-staging')
    return result


def observer(selection, manifest, result):
    state = {}

    def observe(stage, context):
        vm, lease, directory = (context[key] for key in ('vm', 'lease', 'directory'))
        if stage == 'before':
            for path in (system.PAYLOAD, '/var/lib/onpc-e2e-assets'):
                vm.call(['/usr/bin/test', '!', '-e', path], timeout=30, attempts=1)
            shared.wait_environment(vm, lease, directory)
            before = proof.audit(vm, manifest, shared_preparation.SUBSETS)
            system.require(not before['installed'] and not before['files']
                and not before['unselected_present'] and not before['staging']
                and before['preserved']['@attempt-trust'] is None,
                'fixture-transfer:capture-not-clean')
            state['refusals'] = refused_inputs(context, selection)
            proof.verify_repeat(before, proof.audit(vm, manifest, shared_preparation.SUBSETS))
            state['before'] = before
            return
        system.require(stage == 'ready' and 'before' in state,
                       'fixture-transfer:observer-order')
        controller, receipt = context['controller'], context['receipt']
        observed = proof.audit(vm, manifest, shared_preparation.SUBSETS)
        members = proof.validate_readback(observed, manifest, shared_preparation.SUBSETS,
                                         receipt.binding, installed=False)
        system.require(receipt.binding['attempt_id'] == shared_preparation.attempt_id(directory),
                       'fixture-transfer:unbound-readiness')
        proof.unchanged_policy(state['before'], observed)
        witnesses = proof.runtime_witnesses(vm, members, observed['accounts'], selection.target,
                                           only=(native_assets.executable_path('A'),))
        before_repeat = proof.audit(vm, manifest, shared_preparation.SUBSETS)
        system.require(fixture_execution.verify(selection) == manifest,
                       'fixture-transfer:selected-input-changed')
        repeated = controller.provision(selection, shared_preparation.SUBSETS,
                                       attempt_id=shared_preparation.attempt_id(directory))
        controller.require_ready(repeated)
        system.require(repeated == receipt, 'fixture-transfer:version-switched')
        final = proof.audit(vm, manifest, shared_preparation.SUBSETS)
        proof.verify_repeat(before_repeat, final)
        proof.unchanged_policy(state['before'], final)
        controller.require_ready(receipt)
        result.update(binding=receipt.binding, readback=final, refusals=state['refusals'],
            runtime_witnesses=witnesses, repeat_without_writes=True,
            selected_input_unchanged=True, no_preboot_payload=True, product_absent=True,
            worker_input_released=False, graphical_input_released=False,
            product_assertions_started=False, domain_id=lease.state['domain_id'],
            reused_proof='F03/F15 immutable input and readiness; F06 uncertain transfer/recovery')
    return observe


def preparation_backend(directory, lease, commands, host_key, ledger, expected_inputs, **options):
    """Run the actual ready request boundary, with no graphical worker or input."""
    lease.start()
    boundary = smoke.Smoke(directory, lease, commands, host_key,
        transfer=options['transfer'], fixture_selection=options['fixture_selection'],
        fixture_observer=options['fixture_observer'])
    (directory / 'ready.request.json').write_text(json.dumps({'stage': 'ready', 'screenshot': None}))
    boundary.step()
    system.require(len(boundary.steps) == 1 and boundary.steps[0]['stage'] == 'ready',
                   'fixture-transfer:preparation-not-complete')
    system.require((directory / 'ready.reply.json').is_file(), 'fixture-transfer:ready-reply-missing')
    return {'preparation_only': True}


class PreparationQualification(smoke.Qualification):
    """Retain finite checkpoint names without starting a graphical collector."""
    def checkpoint(self, event):
        self.result.setdefault('checkpoints', []).append(event)


def qualify_pinned(directory, assets, selection, manifest):
    suite = Suite(open_source)
    result = {'target': selected_target(), 'selection': selection.record(),
              'restore_owner': 'Qualification.execute / SuiteLease.prepare',
              'preparation_owner': 'Smoke ready / AssetTransfer.provision'}
    private = directory / 'private'
    private.mkdir(mode=0o700)
    suite.commands = system.EvidenceCommands(private)
    suite.commands.directory = private
    try:
        source_assets = system.artifact_source(assets)
        preflight_source(source_assets)
        smoke.stage_qualification_assets(source_assets, directory / 'assets', suite.commands,
                                         package_only=True)
        (directory / 'input').mkdir(mode=0o700)
        (directory / 'input/selected-inputs.json').write_bytes(system.baseline.encode(smoke.inputs()))
        ledger = system.RunLedger()
        suite.acquire(ledger)
        qualification = PreparationQualification(directory, suite.commands, ledger,
            None, {}, suite.host_before, assets=directory / 'assets')
        qualification.fixture_selection = selection.record()
        qualification.fixture_observer = observer(selection, manifest, result)
        with suite.lease:
            try:
                with patch.object(smoke, 'run_backend', preparation_backend):
                    qualification.execute(suite.lease, suite.guestfs)
            finally:
                suite.verified = qualification.verified
        system.require(suite.lease.state['phase'] == 'complete'
            and suite.lease.view.snapshot()[1] and suite.lease.view.domain_id is None,
            'fixture-transfer:attempt-cleanup-incomplete')
        result['qualification'] = qualification.result
    finally:
        suite.close()
    result.update(owned_baseline_restoration_verified=True, outcome='passed')
    return result


def qualify(directory, assets, selection):
    selected_target()
    selection = fixture_execution.Selection.from_record(preparation.validate_input(selection, target='ubuntu'))
    with authenticated_input(selection.record()):
        manifest = fixture_execution.verify(selection)
        fixture_provision.authenticated_bundle(selection)
        return qualify_pinned(directory, assets, selection, manifest)


def main(*, assets, selection):
    directory = None
    try:
        system.require(os.geteuid() == 0, 'fixture-transfer:root-required')
        selected_target()
        os.umask(0o077)
        with session():
            directory = Path(allocate(tempfile.mkdtemp, prefix='onpc-fixture-transfer-'))
            result = qualify(directory, assets, selection)
            (directory / 'result.json').write_bytes(system.baseline.encode(result))
        print('fixture-transfer: passed; evidence=' + str(directory), flush=True)
        return 0
    except (Exception, KeyboardInterrupt) as error:
        if directory is not None:
            (directory / 'controller-error.txt').write_text(traceback.format_exc())
        print('fixture-transfer: ' + system.error_category(error), file=sys.stderr, flush=True)
        if directory is not None:
            print('fixture-transfer: evidence=' + str(directory), file=sys.stderr, flush=True)
        return 1
