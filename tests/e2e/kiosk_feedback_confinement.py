"""Engineering-only kiosk error reporting with session identity observations."""
from dataclasses import replace
import json

from calendar_fixture import preset_ordinary_daytime
from installed_journey import InstalledJourney
from journey_blocks import desktop_entry, fresh_desktop, prefixed_stages
from kiosk_eligible_choices import PLAN as CHOICES_PLAN
from private_artifacts import require
from request_flow import daily_station_entry
import system_runner as system

EXTRA = ('kiosk-diagnostic-error', 'kiosk-diagnostic-report', 'kiosk-diagnostic-editor',
         'kiosk-diagnostic-privacy')
CHILD_ENTRY = prefixed_stages('fixture-child', desktop_entry('child', source='gdm', entry='fresh'))
DAILY_SETUP = daily_station_entry()
SCREENS = {}
for stage, operation in CHOICES_PLAN.screen_tags.items():
    if stage == 'switch-user':
        SCREENS.update({key: DAILY_SETUP[key] for key in (
            'allowance-15-select', 'allowance-15-read', 'time-explanation-read')})
    if stage == 'station-list':
        SCREENS.update(CHILD_ENTRY)
        SCREENS.update({'child-countdown': 'ui:child-countdown-present',
                        'child-switch': 'system:child-switch-user',
                        'child-greeter': 'ui:gdm-returned'})
    SCREENS[stage] = operation
SCREENS.update({stage: 'ui:' + stage for stage in EXTRA})
PLAN = replace(CHOICES_PLAN, prefix='kiosk-feedback-confinement',
    worker_mode='kiosk_feedback_confinement',
    screen_tags=SCREENS,
    phases={**CHOICES_PLAN.phases, **{stage: (
        'step-1' if stage in ('allowance-15-select', 'allowance-15-read', 'time-explanation-read')
        else 'step-2') for stage in SCREENS if stage not in CHOICES_PLAN.phases}},
    advance_after={'time-explanation-read': 'step-2'},
    stage_actions={'setup-detached': 'daytime-window'},
    invocations=(*fresh_desktop('parent'),
                 *(stage for stage, tag in CHILD_ENTRY.items() if tag.startswith('ui:'))),
    challenges={'parent-login': ('parent', 'recipient-qualified', 'recipient-rechecked'),
                'fixture-child': ('child', 'fixture-child-child-recipient-qualified',
                                  'fixture-child-child-recipient-rechecked')})


class BrokerOutage:
    """Shared attempt-owned fault transport; callers own sequence and assertions."""
    outage_roles = ('kiosk',)

    def engineering(self, action, *arguments, timeout=90):
        self.context.lease.guard()
        result = self.transport.call(['env',
            'ONPC_EXPECTED_RUN=' + self.context.lease.state['run'],
            'PYTHONDONTWRITEBYTECODE=1', '/usr/bin/python3', '-B',
            system.PAYLOAD + '/system_kiosk_feedback.py', action, *arguments], timeout=timeout)
        return json.loads(result)

    def begin_fault(self):
        self._outage_boundary = None
        # Set this before transport: an uncertain reply never licenses replay.
        self.fault_pending = True
        value = self.engineering('begin')
        self._outage_boundary = value.pop('fault_time', None)
        return value

    def restore_fault(self):
        if self.fault_pending:
            value = self.engineering('restore')
            end = value.pop('fault_time', None)
            require(value == {'broker_restored': True}, 'kiosk-feedback:recovery-response')
            self.fault_pending = False
            observation = self.transport.product_failures
            if observation is not None:
                for role in self.outage_roles:
                    observation.add_allowance(role, 'dependency', self._outage_boundary, end)
            return value


class KioskFeedbackConfinementJourney(BrokerOutage, InstalledJourney):
    outage_roles = ('parent', 'child', 'kiosk')
    qualify_broker_signals = True

    def __init__(self, context, progress):
        super().__init__(context, progress, PLAN,
                         actions={'daytime-window': preset_ordinary_daytime})
        self.fault_pending = False
        self.healthy_start = None
        self.outage_start = None

    def check_request(self, stage, observed):
        super().check_request(stage, observed)
        if stage == 'installed-greeter':
            value = self.engineering('signal-start')
            require(value['settlement_exercised'] is True, 'kiosk-feedback:journal-settlement')
            self.healthy_start = value['boundary']
            observed['journal_settlement_exercised'] = True
        elif stage == 'selections-read':
            # Rest of day needs no periodic broker estimate. Keep the owned
            # outage from opening an unrelated estimate-error modal before
            # the single Request action. The shared operation independently
            # reads the selected duration and its midnight estimate.
            observed['diagnostic_preparation'] = self.ui.observe('kiosk-valid-rest-select')
            value = self.engineering('healthy-signals', json.dumps(self.healthy_start))
            require(value['failure_events'] == 0, 'kiosk-feedback:healthy-failure-signals')
            self.outage_start = value['boundary']
            observed['healthy_failure_events'] = 0
            observed['engineering_fault'] = self.begin_fault()
            require(observed['engineering_fault'] == {
                'broker_unavailable': True, 'runtime_mask_owned': True},
                'kiosk-feedback:fault-response')
        elif stage == 'kiosk-diagnostic-error':
            observed['engineering_outage_signals'] = self.engineering(
                'outage-signals', json.dumps(self.outage_start), timeout=150)
            observed['engineering_recovery'] = self.restore_fault()
        elif stage == 'kiosk-diagnostic-editor':
            observed['engineering_confinement'] = self.engineering('census')
        elif stage == 'kiosk-diagnostic-privacy' and self.qualify_broker_signals:
            result = self.engineering('broker-signals', timeout=150)
            start, end = result.pop('fault_allowance')
            for key in ('fault_start', 'fault_end'):
                result.pop(key)
            observation = self.transport.product_failures
            if observation is not None:
                for category in ('backend', 'operation'):
                    observation.add_allowance('broker', category, start, end)
            observed['engineering_broker_signals'] = result


class UnexpectedProductReportJourney(KioskFeedbackConfinementJourney):
    # Leave the kiosk's report-triggering fault for the standalone verdict.
    outage_roles = ('parent', 'child')
    qualify_broker_signals = False
