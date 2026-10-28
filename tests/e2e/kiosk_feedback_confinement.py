"""Engineering-only kiosk error reporting with session identity observations."""
from dataclasses import replace
import json

from installed_journey import InstalledJourney
from kiosk_eligible_choices import PLAN as CHOICES_PLAN
from private_artifacts import require
import system_runner as system

EXTRA = ('kiosk-diagnostic-error', 'kiosk-diagnostic-report', 'kiosk-diagnostic-editor',
         'kiosk-diagnostic-privacy')
PLAN = replace(CHOICES_PLAN, worker_mode='kiosk_feedback_confinement',
    screen_tags={**CHOICES_PLAN.screen_tags, **{stage: 'ui:' + stage for stage in EXTRA}},
    phases={**CHOICES_PLAN.phases, **{stage: 'step-2' for stage in EXTRA}})


class BrokerOutage:
    """Shared attempt-owned fault transport; callers own sequence and assertions."""
    def engineering(self, action):
        self.context.lease.guard()
        result = self.transport.call(['env',
            'ONPC_EXPECTED_RUN=' + self.context.lease.state['run'],
            'PYTHONDONTWRITEBYTECODE=1', '/usr/bin/python3', '-B',
            system.PAYLOAD + '/system_kiosk_feedback.py', action], timeout=90)
        return json.loads(result)

    def restore_fault(self):
        if self.fault_pending:
            value = self.engineering('restore')
            require(value == {'broker_restored': True}, 'kiosk-feedback:recovery-response')
            self.fault_pending = False
            return value


class KioskFeedbackConfinementJourney(BrokerOutage, InstalledJourney):
    def __init__(self, context, progress):
        super().__init__(context, progress, PLAN)
        self.fault_pending = False

    def check_request(self, stage, observed):
        super().check_request(stage, observed)
        if stage == 'selections-read':
            # Rest of day needs no periodic broker estimate. Keep the owned
            # outage from opening an unrelated estimate-error modal before
            # the single Request action. The shared operation independently
            # reads the selected duration and its midnight estimate.
            observed['diagnostic_preparation'] = self.ui.observe('kiosk-valid-rest-select')
            # Set this before transport: an uncertain reply never licenses
            # replay of the mutation and must still attempt owned restoration.
            self.fault_pending = True
            observed['engineering_fault'] = self.engineering('begin')
            require(observed['engineering_fault'] == {
                'broker_unavailable': True, 'runtime_mask_owned': True},
                'kiosk-feedback:fault-response')
        elif stage == 'kiosk-diagnostic-error':
            observed['engineering_recovery'] = self.restore_fault()
        elif stage == 'kiosk-diagnostic-editor':
            observed['engineering_confinement'] = self.engineering('census')
