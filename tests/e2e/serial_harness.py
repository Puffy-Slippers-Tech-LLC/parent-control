"""Product-free graphical/serial attempt envelope and HAR09/HAR10 checks.

The existing serial smoke owns input and verifies the command's actual output.
This callback records its acknowledged stages before allowing the next input.
Raw captures/terminal output stay private; screen evidence is semantic metadata.
"""

import json
from pathlib import Path
import sys

from asset_transfer import AssetTransfer
from private_artifacts import require
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'integration'))
from check_graphical_smoke import (Smoke, FUNCTIONAL_SERIAL_STAGES as SERIAL_STAGES,
                                   FUNCTIONAL_GDM_OPERATIONS, module_result,
                                   harness_observation)
from graphical_serial import provision_getty
sys.path.pop(0)
from installed_journey import JourneyPlan, matched_screens as reconcile_screens


PLAN = JourneyPlan(prefix='smokeui', worker_mode='functional_smoke', phases={},
                   screen_tags={stage: 'ui:' + operation
                                for stage, operation in FUNCTIONAL_GDM_OPERATIONS.items()})


def encoded(value):
    return (json.dumps(value, sort_keys=True) + '\n').encode()


def matched_screens(directory, observations):
    """Fresh semantic results and ordered worker markers, including real logout."""
    result = reconcile_screens(directory, PLAN, observations)
    details = json.loads((directory / 'testresults/result-smoke.json').read_text())['details']
    logout = [i for i, d in enumerate(details) if d.get('title') == 'serial-logout' and d.get('result') == 'ok']
    require(len(logout) == 1 and result[-2]['detail_index'] < logout[0] < result[-1]['detail_index'],
            'qualification:return-order')
    return result


def validate_stages(directory, observations):
    """HAR10's pre-shutdown callback: a zero worker exit cannot prove success."""
    require([s['stage'] for s in observations] == list(SERIAL_STAGES),
            'qualification:missing-stages')
    module_result(directory)


def validate_completion(directory, observations, worker):
    """HAR10 after normal owned shutdown, before any terminal assertions."""
    validate_stages(directory, observations)
    require(worker['shutdown_verified'] is True, 'qualification:shutdown-unverified')


def recorded_serial_case(case):
    """Only the recorded harness binding consumes this preparation envelope."""
    return case['executable'] == {
        'path': 'tests/e2e/controller_qualification.py', 'test_id': 'gdm-observation'}


def validate_fixture_input(value, target=None):
    """Recorded serial has its own target qualification, separate from Smoke."""
    from e2e_fixture_preparation import selection_record
    from smoke_fixture_preparation import validate_input
    record = selection_record(value, product_free=True)
    require(record['target'] in ('ubuntu', 'fedora')
            and target in (None, 'ubuntu', 'fedora')
            and (target is None or target == record['target']),
            'fixtures:recorded-serial-target-not-qualified')
    return validate_input(record, target=target)


def record_serial_journey(recorder, context):
    def artifact(name, kind, value):
        return recorder.artifact(name, kind, encoded(value), reviewed=True)

    from system_fixture_preparation import guest_target
    with recorder.step('setup'):
        selection = validate_fixture_input(context.fixture_selection,
            target=guest_target(context.lease.capture.state['guest']))
        credentials = context.credentials.provision(context.lease, context.verified,
            context.directory, context.guestfs, context.commands)
        provision_getty(context.lease, context.guestfs)
        transfer = AssetTransfer(context.verified)
        assets = transfer.provision(context.lease, context.guestfs, fixture_selection=selection)
        artifact('inputs', 'input-provenance', context.verified.inputs)
        fixture_ref = artifact('fixture-input', 'input-provenance', selection)
        artifact('provisioning', 'action-trace', {
            'fixture_credentials': credentials, 'assets': assets,
            'serial_getty': 'stock-password-authentication'})

    active = recorder.step('start')
    active.__enter__()
    boot = None
    trace = []
    current_step = 'start'
    command_ref = None

    def progress(stage, observed):
        nonlocal active, boot, current_step, command_ref
        if observed is None:
            return
        current = harness_observation(smoke.vm, 'boot')['boot_sha256']
        require(boot is None or boot == current, 'qualification:boot-changed')
        boot = current
        recorder.continuity(boot=boot)
        if stage == 'ready':
            prepared = smoke.fixture_prepared
            require(prepared is not None and prepared['lease'] is context.lease
                    and prepared['selection'] == selection
                    and prepared['receipt'].binding['boot_sha256'] == boot,
                    'qualification:fixture-readiness-unbound')
            prepared['controller'].require_ready(prepared['receipt'])
            artifact('fixture-readiness', 'input-provenance', {
                'input_artifact': fixture_ref,
                'source_sha256': context.verified.inputs['source_sha256'],
                'selection': selection, 'binding': prepared['receipt'].binding,
                'files': prepared['receipt'].files})
        # The fixed session probes establish presence/absence separately. This
        # case makes no cross-session continuity assertion or invented alias.
        trace.append({'stage': stage, 'boot_sha256': boot})
        if stage in ('gdm', 'focused', 'selected', 'dismissed'):
            ref = artifact(stage, 'screen', observed)
        else:
            ref = artifact(stage, 'backend', observed)
            if stage == 'serial-command':
                require(observed.get('command_marker_verified') is True,
                        'qualification:command-not-observed')
                command_ref = ref
            elif stage in ('serial-logout', 'gdm-return'):
                require(observed.get('unexpected_user_session') is False,
                        'qualification:unexpected-session')
                if stage == 'gdm-return':
                    ref = artifact('no-user-session', 'other-user', observed)
                    recorder.assertion('other-user-result', artifact_ids=[ref])
        # Several transport stages belong to one declared journey step. Keep
        # every observation durable before the worker receives its reply.
        recorder.checkpoint('observation')
        index = SERIAL_STAGES.index(stage) + 1
        following = SERIAL_STAGES[index] if index < len(SERIAL_STAGES) else None
        next_step = ('step-1' if following in ('gdm', 'focused', 'selected', 'dismissed') else
                     'step-2' if following and following.startswith('serial-') else 'step-3')
        if next_step != current_step:
            closing, active = active, None
            closing.__exit__(None, None, None)
            current_step = next_step
            active = recorder.step(next_step)
            active.__enter__()

    smoke = Smoke(context.directory, context.lease, context.commands, context.host_key,
                  progress=progress, transfer=transfer, authenticate=True, serial=True, functional=True,
                  fixture_selection=selection,
                  fixture_observer=getattr(context, 'fixture_observer', None))

    def validate():
        validate_stages(context.directory, smoke.steps)

    try:
        worker = context.run_worker(observe=smoke.step, validate=validate,
                                    authenticate=True, serial=True, timeout=600)
        validate_completion(context.directory, smoke.steps, worker)
        ref = artifact('matched-screens', 'screen', matched_screens(context.directory, smoke.steps))
        recorder.assertion('visible-result', artifact_ids=[ref])
        require(command_ref is not None, 'qualification:command-not-observed')
        ref = artifact('command-continuity', 'backend', {'command_artifact': command_ref,
            'command_marker_verified': True, 'boot_sha256': boot})
        recorder.assertion('backend-result', artifact_ids=[ref])
        closing, active = active, None
        closing.__exit__(None, None, None)
        active = recorder.step('end')
        active.__enter__()
        recorder.continuity(boot=boot)
        artifact('observed-stages', 'action-trace', trace)
        artifact('boot-continuity', 'continuity', {'boot_sha256': boot,
                                                'observations': len(trace)})
        artifact('worker-outcome', 'outcomes', {'outcome': worker['outcome']})
        artifact('worker-cleanup', 'cleanup', {name: worker[name] for name in
            ('worker_stopped', 'callback_closed', 'shutdown_verified')})
    finally:
        if active is not None:
            active.__exit__(*sys.exc_info())
