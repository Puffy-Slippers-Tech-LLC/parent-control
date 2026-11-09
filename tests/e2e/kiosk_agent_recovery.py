"""System obligation 144: lose the real agent, then approve one fresh request."""
from dataclasses import replace
import json

from desktop_session import run_attached
from kiosk_approval import KioskApprovalJourney
from kiosk_service_recovery import PLAN as RECOVERY
from private_artifacts import require
import system_runner as system


SCREENS = {}
for stage, operation in RECOVERY.screen_tags.items():
    SCREENS[stage] = operation
    if stage == 'selections-read':
        # The selected enabled form is already observed. Reuse only the
        # recovery history's duration/soft-choice inputs and final estimate.
        for name in ('new-duration', 'new-text-focus', 'new-text-selected',
                     'new-text-read', 'new-apps', 'new-estimate'):
            SCREENS['fault-' + name] = RECOVERY.screen_tags[name]
        SCREENS['agent-prompt-open'] = 'ui:kiosk-mate-open'
SCREENS['kiosk-diagnostic-error'] = 'ui:kiosk-agent-refused'
SCREENS['kiosk-diagnostic-exit'] = 'ui:kiosk-request-cancel'
PLAN = replace(RECOVERY, worker_mode='kiosk_agent_recovery', screen_tags=SCREENS,
    phases={**RECOVERY.phases, **{stage: 'step-1' for stage in SCREENS
                                 if stage not in RECOVERY.phases}},
    assertions_after={**RECOVERY.assertions_after,
        'agent-prompt-open': 'real-agent-stopped-before-any-password',
        'kiosk-diagnostic-error': 'agent-loss-denies-without-grant-and-station-remains-usable',
        'outage-returned': 'safe-station-exit-after-agent-restoration'})


def engineering(transport, action):
    transport.lease.guard()
    return json.loads(transport.call(['env',
        'ONPC_EXPECTED_RUN=' + transport.lease.state['run'],
        'PYTHONDONTWRITEBYTECODE=1', '/usr/bin/python3', '-B',
        system.PAYLOAD + '/system_kiosk_agent.py', action], timeout=180))


class KioskAgentRecoveryJourney(KioskApprovalJourney):
    def __init__(self, context, progress, plan=PLAN, *, actions=None, transport=None):
        super().__init__(context, progress, plan, actions=actions, transport=transport)

    def check_settings(self, stage, observed):
        super().check_settings(stage, observed)
        if stage in self.plan.balance_checks:
            require(observed['ui']['time_explanation']['one_time']['seconds'] == 0,
                    'kiosk-agent:unexpected-grant')

    def check_request(self, stage, observed):
        super().check_request(stage, observed)
        if stage == 'agent-prompt-open':
            observed['engineering_fault'] = engineering(self.transport, 'begin')
            require(observed['engineering_fault'] == {'actual_agent_stopped': True},
                    'kiosk-agent:fault-response')
        elif stage == 'kiosk-diagnostic-error':
            observed['engineering_no_grant'] = engineering(self.transport, 'no-grant')
            require(observed['engineering_no_grant'] == {
                'no_grant': True, 'other_accounts_unchanged': True}, 'kiosk-agent:grant-response')
            observed['engineering_recovery'] = engineering(self.transport, 'restore')
            require(observed['engineering_recovery'] == {'agent_restored': True},
                    'kiosk-agent:restore-response')


def run(directory, lease, transport, ledger, *, expected_inputs, progress, context):
    try:
        result = run_attached(directory, lease, transport, ledger, PLAN,
            expected_inputs=expected_inputs, progress=progress, context=context,
            journey_type=KioskAgentRecoveryJourney, timeout=2400)
        require(engineering(transport, 'complete') == {
            'fresh_approval': True, 'other_accounts_unchanged': True}, 'kiosk-agent:complete-response')
        return result
    finally:
        # The attached worker closes before fault recovery and VM cleanup.
        engineering(transport, 'restore')
