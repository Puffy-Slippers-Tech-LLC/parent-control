"""Canonical E2E-001 graphical/serial runner smoke; no customer claims.

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
from check_graphical_smoke import Smoke, SERIAL_STAGES, module_result, screenshot
from graphical_serial import provision_getty
sys.path.pop(0)


def encoded(value):
    return (json.dumps(value, sort_keys=True) + '\n').encode()


def matched_screens(directory):
    """Reconcile public module results; export only fixed names and PNG hashes.

    In particular, an earlier account-list capture cannot prove graphical
    return. Require its match after the recorded real serial logout. Identical
    initial/return pixels are valid because serial leaves the greeter unchanged.
    """
    module_result(directory)
    details = json.loads((directory / 'testresults/result-smoke.json').read_text())['details']
    matches = [(i, d) for i, d in enumerate(details) if 'needle' in d]
    account, prompt = 'onpc-gdm-parent-account', 'onpc-gdm-parent-masked-password'
    require([d['needle'] for _, d in matches] == [account, account, account, prompt, account, account],
            'qualification:match-sequence')
    logout = [i for i, d in enumerate(details) if d.get('title') == 'serial-logout' and d.get('result') == 'ok']
    returned = [i for i, d in enumerate(details) if d.get('title') == 'gdm-return' and d.get('result') == 'ok']
    require(len(logout) == len(returned) == 1
            and matches[-2][0] < logout[0] < matches[-1][0] < returned[0],
            'qualification:return-order')
    result = []
    for (index, match), stage in zip(matches, ('initial', 'select-ready', 'click', 'prompt', 'dismissed', 'returned')):
        require(match.get('result') == 'ok' and match.get('area')
                and all(a.get('result') == 'ok' and a.get('similarity') == 100 for a in match['area']),
                'qualification:match-quality')
        result.append({'stage': stage, 'detail_index': index, 'needle': match['needle'],
                       **screenshot(directory, match.get('screenshot'))})
    return result


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
    current_step = 'start'
    command_ref = None

    def progress(stage, observed):
        nonlocal active, boot, current_step, command_ref
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
        next_step = ('step-1' if following in ('gdm', 'selected', 'dismissed') else
                     'step-2' if following and following.startswith('serial-') else 'step-3')
        if next_step != current_step:
            closing, active = active, None
            closing.__exit__(None, None, None)
            current_step = next_step
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
        ref = artifact('matched-screens', 'screen', matched_screens(context.directory))
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


E2E_CASES = {'gdm-observation': execute}
