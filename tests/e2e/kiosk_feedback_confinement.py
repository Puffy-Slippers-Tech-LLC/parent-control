"""Engineering-only installed kiosk error reporting and MAC qualification."""
from dataclasses import replace
import json

from installed_journey import InstalledJourney
from kiosk_eligible_choices import PLAN as CHOICES_PLAN
from private_artifacts import require
import system_runner as system

EXTRA = ('kiosk-diagnostic-error', 'kiosk-diagnostic-report', 'kiosk-diagnostic-editor')
PLAN = replace(CHOICES_PLAN, worker_mode='kiosk_feedback_confinement',
    screen_tags={**CHOICES_PLAN.screen_tags, **{stage: 'ui:' + stage for stage in EXTRA}},
    phases={**CHOICES_PLAN.phases, **{stage: 'step-2' for stage in EXTRA}})


class KioskFeedbackConfinementJourney(InstalledJourney):
    def __init__(self, context, progress):
        super().__init__(context, progress, PLAN)
        self.fault_pending = False
        self.scanner_pending = False

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

    def stop_scanner(self):
        if self.scanner_pending:
            value = self.engineering('scanner-finish')
            require(value.get('observation') in ('observed', 'not-observed', 'not-started', 'rejected') and
                    type(value.get('scanner_observed')) is bool,
                    'kiosk-feedback:scanner-response')
            self.scanner_pending = False
            return value

    def check_request(self, stage, observed):
        super().check_request(stage, observed)
        if stage == 'selections-read':
            # Set this before transport: an uncertain reply never licenses
            # replay of the mutation and must still attempt owned restoration.
            self.fault_pending = True
            observed['engineering_fault'] = self.engineering('begin')
            require(observed['engineering_fault'] == {
                'broker_unavailable': True, 'runtime_mask_owned': True},
                'kiosk-feedback:fault-response')
        elif stage == 'kiosk-diagnostic-error':
            observed['engineering_recovery'] = self.restore_fault()
            self.scanner_pending = True
            observed['engineering_scanner_start'] = self.engineering('scanner-start')
            require(observed['engineering_scanner_start'] == {'scanner_observer_started': True},
                    'kiosk-feedback:scanner-start-response')
        elif stage == 'kiosk-diagnostic-editor':
            observed['engineering_scanner'] = self.stop_scanner()
            require(observed['engineering_scanner']['observation'] != 'rejected',
                    'kiosk-feedback:scanner-confinement-rejected')
            observed['engineering_confinement'] = self.engineering('census')
