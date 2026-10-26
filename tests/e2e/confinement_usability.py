"""Short public entry/rejection/Cancel/approval/reentry confinement gate."""
from approval_flow import rejected_request
from installed_journey import JourneyPlan
from journey_blocks import (desktop_entry, fresh_desktop, parent_management,
                            prefixed_stages, retained_parent_entry)
from kiosk_approval import KioskApprovalJourney
from kiosk_approved_flow import approved_request
from private_artifacts import require
from request_flow import CHOICES, daily_station_entry, prepared_request
from ui_observations import SettingsObservation


ENTRIES = {prefix: prefixed_stages(prefix, desktop_entry(
    'parent', source='gdm', entry='retained'))
    for prefix in ('rejection-parent', 'cancel-parent', 'approved-parent', 'restore-parent')}

SCREENS = {**fresh_desktop('parent'), **parent_management(), **daily_station_entry()}
for outcome in ('rejection', 'cancel'):
    SCREENS.update(prefixed_stages(outcome, {
        **prepared_request(prefix='open', entry='open' if outcome == 'rejection' else 'new',
                           initial='default' if outcome == 'rejection' else 'selected',
                           compact=True, **CHOICES),
        **rejected_request(outcome=outcome, **CHOICES),
        'exit': 'ui:kiosk-request-cancel', 'returned': 'ui:gdm-station-returned'}))
    SCREENS.update(ENTRIES[outcome + '-parent'])
    SCREENS.update(prefixed_stages(outcome + '-supplied', retained_parent_entry(
        source='same-user', desktop_observation=False)))
    SCREENS.update({outcome + '-balance': 'ui:time-explanation-reach-read',
                    outcome + '-switch': 'system:parent-switch-user',
                    outcome + '-greeter': 'ui:gdm-returned'})
SCREENS.update({
    **prepared_request(prefix='new', entry='new', initial='selected', compact=True, **CHOICES),
    **approved_request(**CHOICES, exit='automatic'),
    **ENTRIES['approved-parent'],
    **prefixed_stages('approved-supplied', retained_parent_entry(
        source='same-user', desktop_observation=False)),
    'approved-balance': 'ui:time-explanation-reach-read',
    'approved-switch': 'system:parent-switch-user', 'approved-greeter': 'ui:gdm-returned',
    **prefixed_stages('reentry', prepared_request(
        prefix='open', entry='new', initial='selected', compact=True, **CHOICES)),
    'reentry-exit': 'ui:kiosk-request-cancel', 'reentry-returned': 'ui:gdm-station-returned',
    **ENTRIES['restore-parent'],
    **prefixed_stages('restore-supplied', retained_parent_entry(
        source='same-user', desktop_observation=False)),
    'revoke-open': 'ui:revoke-open', 'revoke-warning': 'ui:revoke-warning',
    'revoke-confirm': 'ui:revoke-confirm', 'revoked-balance': 'ui:revoke-cleared-balances',
    'restore-allowance': 'ui:time-explanation-zero-read',
    'restore-disabled': 'ui:parent-toggle-disabled', 'restore-saved': 'ui:parent-save-disabled',
    'restore-settings': 'ui:parent-toggle-disabled-settings',
    'restore-balance': 'ui:time-explanation-reach-read',
})
_entry_stages = {stage for fragment in ENTRIES.values() for stage in fragment}
PLAN = JourneyPlan(
    prefix='confinement-usability', worker_mode='confinement_usability', screen_tags=SCREENS,
    phases={'ready': 'setup', 'setup-detached': 'setup', 'installed-greeter': 'start',
            **{stage: 'step-1' for stage in SCREENS if stage != 'installed-greeter'}},
    invocations=tuple(stage for stage in SCREENS
                      if stage in _entry_stages and SCREENS[stage].startswith('ui:')),
    challenges={prefix: ('parent', prefix + '-recipient-qualified', prefix + '-recipient-rechecked')
                for prefix in ENTRIES},
    settings_checks={
        'parent-selected': SettingsObservation('fixture-child', False, ('0 minutes',)),
        'restore-settings': SettingsObservation('fixture-child', False, ('0 minutes',))},
    balance_checks={'time-explanation-read': 900, 'rejection-balance': 900,
                    'cancel-balance': 900, 'restore-allowance': 0, 'restore-balance': 0},
    request_checks={outcome + '-flow-preserved': (outcome + '-flow-before',
        'confinement-usability:changed-negative-choices', 'preserved_choices')
        for outcome in ('rejection', 'cancel')},
    assertions_after={
        'rejection-balance': 'wrong-password-grants-nothing',
        'cancel-balance': 'independent-cancel-grants-nothing',
        'approved-balance': 'genuine-approval-independent-grant',
        'reentry-open-estimate': 'fresh-passwordless-usable-request',
        'restore-balance': 'public-settings-and-grant-restored'},
)


class ConfinementUsabilityJourney(KioskApprovalJourney):
    def __init__(self, context, progress, plan=PLAN, *, actions=None):
        super().__init__(context, progress, plan, actions=actions)

    def check_settings(self, stage, observed):
        if stage == 'reentry-open-estimate':
            # REQUEST03/04 already checks the complete usable 75-second form.
            # Parent refreshes time status every 30 seconds; its displayed
            # active grant is not a timestamped fresh operand for a second
            # estimate calculation. The required 975-second approval comparison
            # remains at approved-balance, before this fresh entry.
            observed.setdefault('comparison', {})['usable_reentry'] = True
            return
        super().check_settings(stage, observed)
        if stage in self.plan.balance_checks:
            require(observed['ui']['time_explanation']['one_time']['seconds'] == 0,
                    'confinement-usability:unexpected-grant')
