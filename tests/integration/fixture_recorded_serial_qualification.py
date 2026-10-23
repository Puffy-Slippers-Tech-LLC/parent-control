"""One real recorder/ScenarioContext preparation, stopped before worker input.

The selected scenario remains deliberately incomplete. Only the outer fixture
qualification can pass; its recorder must reject customer/HAR acceptance and
still finish the normal lease and recorder cleanup.
"""
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

import execution
import inventory
import serial_harness
import fixture_transfer_qualification as transfer
from qualification_storage import allocate, session
import system_runner as system
from tools import fixture_execution, fixture_provision
from tools.test_storage import authenticated_input


class PreparationComplete(BaseException):
    """Deliberately stop the actual callback without inventing stage success."""


def selected_target():
    name = transfer.selected_target()
    system.require(name == 'onpc-Ubuntu26.04',
                   'fixture-recorded-serial:target-not-qualified')
    return name


def recorded_binding(context, selection, prepared):
    """Read the exact durable artifact and observation saved before the reply."""
    collector, recorder = context.recorder.collector, context.recorder
    record = recorder.records[-1]
    artifacts = {item['artifact_id']: item for item in record['artifacts']}
    system.require('fixture-input' in artifacts and 'fixture-readiness' in artifacts,
                   'fixture-recorded-serial:binding-artifact-missing')
    collector.verify(record['artifacts'])
    input_record = json.loads((collector.path / artifacts['fixture-input']['path']).read_bytes())
    readiness = json.loads((collector.path / artifacts['fixture-readiness']['path']).read_bytes())
    system.require(input_record == selection.record()
        and readiness['input_artifact'] == 'fixture-input'
        and readiness['selection'] == input_record
        and readiness['binding'] == prepared['receipt'].binding
        and readiness['files'] == prepared['receipt'].files
        and readiness['source_sha256'] == context.verified.inputs['source_sha256'],
        'fixture-recorded-serial:recorder-input-mismatch')
    checkpoints = [json.loads((collector.path / name).read_bytes())
                   for name in collector._reports if name.startswith('event-')]
    observations = [item for item in checkpoints if item['event'] == 'observation']
    system.require(len(observations) == 1 and any(
        item['artifact_id'] == 'fixture-readiness'
        for item in observations[0]['record']['artifacts']),
        'fixture-recorded-serial:binding-not-checkpointed')
    return dict(input=input_record, readiness=readiness,
                checkpoint_sequence=observations[0]['sequence'],
                evidence_directory=str(collector.path))


def qualify_pinned(directory, assets, selection, manifest):
    document, digest = inventory.read_json(inventory.INVENTORY)
    plan = inventory.resolve_selection(document, 'E2E-001/gdm-observation', require_runnable=True)
    plan.update(artifacts=str(assets), inventory_sha256=digest,
                fixture_selection=selection.record())
    result = dict(target=selected_target(), selection=selection.record(),
        restore_owner='execution.attempt / Lease.prepare',
        preparation_owner='serial_harness.record_serial_journey / ScenarioContext / Smoke ready')
    held = {}
    observed = transfer.observer(selection, manifest, result)

    def stop_after_readiness(context, *, observe, validate, authenticate=False,
                             serial=False, timeout=600, **options):
        system.require(authenticate and serial and timeout == 600 and not options
            and not context._worker_started and context.worker is None,
            'fixture-recorded-serial:worker-boundary-changed')
        held['context'] = context
        boundary = observe.__self__
        boundary.fixture_observer = observed
        context.lease.start()
        request = context.directory / 'ready.request.json'
        request.write_bytes(system.baseline.encode({'stage': 'ready', 'screenshot': None}))
        original_checkpoint = context.recorder.checkpoint

        def checkpoint(event):
            if event == 'observation':
                system.require(not (context.directory / 'ready.reply.json').exists(),
                               'fixture-recorded-serial:reply-before-checkpoint')
            original_checkpoint(event)

        with patch.object(context.recorder, 'checkpoint', checkpoint):
            observe()
        system.require([step['stage'] for step in boundary.steps] == ['ready'],
                       'fixture-recorded-serial:unexpected-worker-stage')
        reply = json.loads((context.directory / 'ready.reply.json').read_bytes())
        system.require(reply.get('functional_smoke') is True and reply['serial'] is True
            and not reply['authenticate'] and not reply['install'] and not reply['install_refusal'],
            'fixture-recorded-serial:ready-reply-changed')
        result['recorder_binding'] = recorded_binding(context, selection, boundary.fixture_prepared)
        result['preboot_provisioning'] = json.loads(
            (context.recorder.collector.path / 'provisioning.evidence').read_bytes())
        system.require(result['preboot_provisioning']['fixture_credentials']['passwords_verified'] is True
            and result['preboot_provisioning']['serial_getty'] == 'stock-password-authentication',
            'fixture-recorded-serial:preboot-preparation-missing')
        # No worker was created. These closed-resource facts let the normal
        # recorder cleanup report the absence of an outstanding owned worker.
        context.worker = dict(worker_stopped=True, callback_closed=True,
                              shutdown_verified=True, preparation_only=True)
        held['stopped_at_readiness'] = True
        raise PreparationComplete()

    with patch.object(execution.ScenarioContext, 'run_worker', stop_after_readiness):
        attempt = execution.attempt(plan, plan['cases'][0])
    (directory / 'result.json').write_bytes(system.baseline.encode({
        'outcome': 'failed', 'attempt_report': attempt}))
    system.require(held.get('stopped_at_readiness') is True,
                   'fixture-recorded-serial:readiness-not-reached')
    context = held['context']
    record = context.recorder.records[-1]
    system.require(attempt['outcome'] == 'failed' and attempt['acceptance_candidate'] is None
        and attempt['lease_phase'] == 'complete'
        and attempt['outcomes']['cleanup']['outcome'] == 'passed'
        and attempt['outcomes']['collection']['category'] == 'scenario-evidence-missing'
        and attempt.get('evidence_capture') is not None
        and context.recorder._closed and context.recorder.collector._fd is None
        and record['cleanup']['lease_phase'] == 'complete'
        and all(value is True for key, value in record['cleanup'].items() if key != 'lease_phase')
        and record['steps'][-1]['step_id'] == 'cleanup'
        and not record['assertions'] and not context._worker_started
        and context.lease.fd is None and context.lease.view.domain_id is None,
        'fixture-recorded-serial:cleanup-or-incomplete-guard-failed')
    result.update(attempt_report=attempt, recorder_cleanup=record['cleanup'],
        recorder_steps=[step['step_id'] for step in record['steps']],
        deliberate_incomplete_scenario=True, scenario_acceptance_claimed=False,
        worker_started=False, serial_console_attached=False, serial_input_released=False,
        authentication_started=False, installation_started=False,
        recorder_closed=True, collector_closed=True, terminal_capture_complete=True,
        owned_baseline_restoration_verified=True, outcome='passed')
    return result


def qualify(directory, assets, selection):
    selected_target()
    selection = fixture_execution.Selection.from_record(
        serial_harness.validate_fixture_input(selection, target='ubuntu'))
    with authenticated_input(selection.record()):
        manifest = fixture_execution.verify(selection)
        fixture_provision.authenticated_bundle(selection)
        return qualify_pinned(directory, assets, selection, manifest)


def main(*, assets, selection):
    directory = None
    try:
        system.require(os.geteuid() == 0, 'fixture-recorded-serial:root-required')
        selected_target()
        os.umask(0o077)
        with session(check='check_fixture_recorded_serial', inputs={'fixture_selection': selection}):
            directory = Path(allocate(tempfile.mkdtemp, prefix='onpc-fixture-recorded-serial-'))
            result = qualify(directory, assets, selection)
            (directory / 'result.json').write_bytes(system.baseline.encode(result))
        print('fixture-recorded-serial: passed; evidence=' + str(directory), flush=True)
        return 0
    except (Exception, KeyboardInterrupt) as error:
        if directory is not None:
            (directory / 'controller-error.txt').write_text(traceback.format_exc())
        print('fixture-recorded-serial: ' + system.error_category(error), file=sys.stderr, flush=True)
        if directory is not None:
            print('fixture-recorded-serial: evidence=' + str(directory), file=sys.stderr, flush=True)
        return 1
