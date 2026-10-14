"""Engineering-only installed kiosk error reporting and MAC qualification."""
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


def scanner_proven(value):
    if not isinstance(value, dict) or set(value) != {
            'scanner_observed', 'observation', 'backend', 'scanner_thread_roles',
            'parent_thread_roles', 'pinned_executable', 'private_namespace_and_generation'}:
        return False
    backend = value['backend']
    if backend not in ('apparmor', 'selinux'):
        return False
    role = lambda name: ('onpc-kiosk-' + name if backend == 'apparmor'
                         else 'onpc_kiosk_' + name + '_t')
    scanner, parent = value['scanner_thread_roles'], value['parent_thread_roles']
    allowed = {role(name) for name in ('scanner', 'app', 'webkit', 'bwrap')}
    return (value['observation'] == 'observed' and value['scanner_observed'] is True and
        value['pinned_executable'] is True and value['private_namespace_and_generation'] is True and
        all(isinstance(counts, dict) and bool(counts) and set(counts) <= allowed and
            all(type(count) is int and count > 0 for count in counts.values())
            for counts in (scanner, parent)) and role('scanner') in scanner and
        bool(set(parent) & {role('app'), role('webkit')}))


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
        if stage == 'station-list':
            # Gst.init in the actual request window can scan before the
            # report exists. Observe before station login, including manager
            # startup, rather than accepting a cached/missed transient later.
            self.scanner_pending = True
            observed['engineering_scanner_start'] = self.engineering('scanner-start')
            require(observed['engineering_scanner_start'] == {'scanner_observer_started': True},
                    'kiosk-feedback:scanner-start-response')
        elif stage == 'selections-read':
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
            observed['engineering_scanner'] = self.stop_scanner()
            scanner = observed['engineering_scanner']
            require(scanner_proven(scanner), 'kiosk-feedback:scanner-confinement-unproven')
            observed['engineering_confinement'] = self.engineering('census')
            require(observed['engineering_confinement']['census']['backend'] == scanner['backend'],
                    'kiosk-feedback:scanner-census-backend')
