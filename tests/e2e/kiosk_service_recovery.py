"""One owned broker outage, safe exit and fresh genuine request after recovery."""
from installed_journey import JourneyPlan
from journey_blocks import (desktop_entry, fresh_desktop, parent_management,
                            prefixed_stages, retained_parent_entry, station_entry)
from kiosk_approval import KioskApprovalJourney
from kiosk_approved_flow import approved_request
from kiosk_feedback_confinement import BrokerOutage
from private_artifacts import require
from request_flow import CHOICES, daily_station_entry


ENTRIES = {prefix: prefixed_stages(prefix + '-parent', desktop_entry(
    'parent', source='gdm', entry='retained')) for prefix in ('outage', 'approved')}
SETUP = {**fresh_desktop('parent'), **parent_management()}
for stage, operation in daily_station_entry().items():
    if stage == 'switch-user':
        # Parent's independent polling/error dialogs are outside this kiosk
        # history. Reopen it only when an authoritative time read is needed.
        SETUP['setup-parent-closed'] = 'ui:parent-search-closed'
    SETUP[stage] = operation
SCREENS = {
    **SETUP,
    'request-form': 'ui:kiosk-request-form',
    'child-selected': 'ui:kiosk-child-select',
    'approver-selected': 'ui:kiosk-approver-select',
    'selections-read': 'ui:kiosk-enabled-form',
    'kiosk-diagnostic-error': 'ui:kiosk-diagnostic-error',
    'kiosk-diagnostic-exit': 'ui:kiosk-diagnostic-exit',
    'outage-returned': 'ui:gdm-station-returned',
    **ENTRIES['outage'],
    **prefixed_stages('outage-supplied', parent_management()),
    'outage-balance': 'ui:time-explanation-reach-read',
    'outage-switch': 'system:parent-switch-user', 'outage-greeter': 'ui:gdm-returned',
    **station_entry('cancel-'),
    'new-duration': 'ui:kiosk-valid-custom-open',
    **{'new-text-' + action: 'ui:text-kiosk-fraction-' + action
       for action in ('focus', 'selected', 'read')},
    'new-apps': 'ui:kiosk-valid-fraction-soft-select',
    'new-estimate': 'ui:kiosk-valid-fraction-soft-read',
    **approved_request(**CHOICES, exit='automatic'),
    **ENTRIES['approved'],
    **prefixed_stages('approved-supplied', retained_parent_entry(
        source='same-user', desktop_observation=False)),
    'approved-balance': 'ui:time-explanation-reach-read',
}
_entry_stages = {stage for fragment in ENTRIES.values() for stage in fragment}
PLAN = JourneyPlan(
    prefix='kiosk-service-recovery', worker_mode='kiosk_service_recovery', screen_tags=SCREENS,
    phases={'ready': 'setup', 'setup-detached': 'setup', 'installed-greeter': 'start',
            **{stage: 'step-1' for stage in SCREENS if stage != 'installed-greeter'}},
    invocations=tuple(stage for stage in SCREENS
                      if stage in _entry_stages and SCREENS[stage].startswith('ui:')),
    challenges={prefix + '-parent': ('parent', prefix + '-parent-recipient-qualified',
                                     prefix + '-parent-recipient-rechecked')
                for prefix in ENTRIES},
    balance_checks={'time-explanation-read': 900, 'outage-balance': 900},
    assertions_after={
        'kiosk-diagnostic-error': 'unavailable-request-grants-nothing',
        'outage-returned': 'safe-exit-and-owned-service-restoration',
        'outage-balance': 'restored-parent-confirms-no-grant',
        'approved-balance': 'fresh-approval-issues-exact-single-grant'},
)


class KioskServiceRecoveryJourney(BrokerOutage, KioskApprovalJourney):
    def __init__(self, context, progress):
        super().__init__(context, progress, plan=PLAN)
        self.fault_pending = False

    def check_settings(self, stage, observed):
        super().check_settings(stage, observed)
        if stage in self.plan.balance_checks:
            require(observed['ui']['time_explanation']['one_time']['seconds'] == 0,
                    'kiosk-service-recovery:unexpected-grant')

    def check_request(self, stage, observed):
        super().check_request(stage, observed)
        if stage == 'selections-read':
            # Rest of day avoids a periodic estimate request racing the single
            # intended submission. The public operation reads its midnight estimate.
            observed['outage_choices'] = self.ui.observe('kiosk-valid-rest-select')
            self.fault_pending = True
            observed['engineering_fault'] = self.engineering('begin')
            require(observed['engineering_fault'] == {
                'broker_unavailable': True, 'runtime_mask_owned': True},
                'kiosk-service-recovery:fault-response')
        elif stage == 'kiosk-diagnostic-error':
            observed['engineering_no_grant'] = self.engineering('no-grant')
            require(observed['engineering_no_grant'] == {
                'broker_unavailable': True, 'no_grant': True},
                'kiosk-service-recovery:grant-response')
        elif stage == 'outage-returned':
            observed['engineering_recovery'] = self.restore_fault()
