"""Real public-controller qualification; no customer or stable-screen claims.

The existing serial smoke owns input and verifies the command's actual output.
This callback records its acknowledged stages before allowing the next input.
Raw captures/terminal output stay private; screen evidence is digest metadata.
"""

import json
from pathlib import Path
import sys

from asset_transfer import AssetTransfer
from private_artifacts import require
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'integration'))
from check_graphical_smoke import Smoke, SERIAL_STAGES, module_result
from graphical_serial import provision_getty
sys.path.pop(0)


def encoded(value):
    return (json.dumps(value, sort_keys=True) + '\n').encode()


def execute(recorder, context):
    def artifact(name, kind, value):
        return recorder.artifact(name, kind, encoded(value), reviewed=True)

    with recorder.step('setup'):
        credentials = context.credentials.provision(context.lease, context.verified,
            context.directory, context.guestfs, context.commands)
        provision_getty(context.lease, context.guestfs)
        transfer = AssetTransfer(context.verified)
        assets = transfer.provision(context.lease, context.guestfs)
        artifact('inputs', 'input-provenance', context.verified.inputs)
        artifact('provisioning', 'action-trace', {
            'fixture_credentials': credentials, 'assets': assets,
            'serial_getty': 'stock-password-authentication'})

    active = recorder.step('start')
    active.__enter__()
    boot = None
    trace = []

    def progress(stage, observed):
        nonlocal active, boot
        if observed is None:
            return
        current = smoke.vm.read('boot')['boot_sha256']
        require(boot is None or boot == current, 'qualification:boot-changed')
        boot = current
        recorder.continuity(boot=boot)
        # The fixed session probes establish presence/absence separately. This
        # case makes no cross-session continuity assertion or invented alias.
        trace.append({'stage': stage, 'boot_sha256': boot})
        if stage in ('gdm', 'selected', 'dismissed'):
            ref = artifact(stage, 'screen', observed)
            if stage == 'dismissed':
                recorder.assertion('screen-transition', artifact_ids=[ref])
        else:
            ref = artifact(stage, 'backend', observed)
            if stage == 'serial-command':
                require(observed.get('command_marker_verified') is True,
                        'qualification:command-not-observed')
                recorder.assertion('serial-command', artifact_ids=[ref])
            elif stage == 'serial-logout':
                require(observed.get('unexpected_user_session') is False,
                        'qualification:unexpected-session')
                ref = artifact('no-user-session', 'other-user', observed)
                recorder.assertion('session-isolation', artifact_ids=[ref])
        closing, active = active, None
        closing.__exit__(None, None, None)
        index = SERIAL_STAGES.index(stage) + 1
        next_step = SERIAL_STAGES[index] if index < len(SERIAL_STAGES) else 'end'
        active = recorder.step(next_step)
        active.__enter__()

    smoke = Smoke(context.directory, context.lease, context.commands, context.host_key,
                  progress=progress, transfer=transfer, authenticate=True, serial=True)

    def validate():
        require([s['stage'] for s in smoke.steps] == list(SERIAL_STAGES),
                'qualification:missing-stages')
        module_result(context.directory)

    try:
        worker = context.run_worker(observe=smoke.step, validate=validate,
                                    authenticate=True, serial=True, timeout=600)
        require(worker['shutdown_verified'] is True, 'qualification:shutdown-unverified')
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


E2E_CASES = {'serial-controller': execute}
