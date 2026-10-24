"""C04j's finite confinement baseline; shared leaves own every mechanism."""
from accessible_ui import MATCH_APPS, MATCH_RULES, NAMED_CHILD_OPERATIONS
from approval_flow import rejected_request
from installed_journey import JourneyPlan
from journey_blocks import (desktop_entry, fresh_desktop, native_activity_entry,
                            native_usable_app, overlay_entry, parent_management,
                            prefixed_stages, rejected_gdm_return,
                            retained_parent_entry, station_entry)
from kiosk_approved_flow import approved_request
from native_fixtures import fixture_actions
from request_composition import GrantAppEffectsJourney
from request_flow import (CHOICES, continued_request, overlay_approved_request,
                          overlay_rejected_request, prepared_request)
from ui_observations import SettingsObservation


TIMEOUT = 1800
LONG_CHOICES = {**CHOICES, 'duration_seconds': 600}
EDITS = (('H', 'permanent', 'hard'), ('S', 'conditional', 'soft'),
         ('H', 'allowed', 'restore-hard'), ('S', 'allowed', 'restore-soft'))
RULES = {'A': MATCH_RULES[0], 'H': MATCH_RULES[3], 'S': MATCH_RULES[4]}
POLICIES = {prefix: {
    prefix + '-access-save': 'ui:access-' + name + '-' + access,
    prefix + '-access': 'ui:access-' + name + '-row',
    prefix + '-final-match': 'ui:match-' + name + '-row'}
    for role, access, prefix in EDITS for name in ({'H': 'hard', 'S': 'soft'}[role],)}
ENTRIES = {
    **{prefix: prefixed_stages(prefix, desktop_entry('parent', source='gdm', entry='retained'))
       for prefix in ('rejection-parent', 'cancel-parent',
                      'revoke-parent', 'restore-parent')},
    'zero-child': prefixed_stages('zero-child', desktop_entry(
        'child', source='gdm', entry='fresh', expected='time-denied')),
    'first-child': prefixed_stages('first-child', desktop_entry('child', source='gdm', entry='fresh')),
    'final-child': prefixed_stages('final-child', desktop_entry('child', source='gdm', entry='retained')),
}
OVERLAY_ENTRIES = {
    'overlay-rejection': prefixed_stages('overlay-rejection', overlay_entry(
        'entry', 'command', form_operation='overlay-long-approver-select')),
    **{prefix: prefixed_stages(prefix, overlay_entry(
        'entry', 'command', form_operation='overlay-valid-fraction-soft-read'))
       for prefix in ('overlay-cancel', 'overlay-approval')},
}

SCREENS = {
    **fresh_desktop('parent'), **parent_management(),
    'allowance-configured': 'ui:time-explanation-setup-zero-read',
    'saved-settings': 'ui:parent-selected', 'apps-page': 'ui:parent-apps-page',
    **POLICIES['hard'], **POLICIES['soft'],
    'saved-policy': 'ui:revoke-saved-balances',
    'setup-switch-ready': 'ui:desktop', 'setup-switch': 'system:parent-switch-user',
    'setup-greeter': 'ui:gdm-returned',
    **prefixed_stages('kiosk-rejection', {
        **prepared_request(prefix='open', entry='new', initial='default', compact=True, **CHOICES),
        **rejected_request(outcome='rejection', **CHOICES),
        'form-cancel': 'ui:kiosk-request-cancel', 'form-returned': 'ui:gdm-station-returned'}),
    **ENTRIES['rejection-parent'],
    **prefixed_stages('rejection-supplied', retained_parent_entry(source='same-user', desktop_observation=False)),
    'rejection-policy': 'ui:revoke-saved-balances',
    'rejection-switch': 'system:parent-switch-user', 'rejection-greeter': 'ui:gdm-returned',
    **prefixed_stages('kiosk-cancel', {
        **prepared_request(prefix='open', entry='new', initial='selected', compact=True, **CHOICES),
        **rejected_request(outcome='cancel', **CHOICES),
        'form-escape': 'ui:kiosk-request-escape-ready', 'form-returned': 'ui:gdm-station-returned'}),
    **ENTRIES['cancel-parent'],
    **prefixed_stages('cancel-supplied', retained_parent_entry(source='same-user', desktop_observation=False)),
    'cancel-policy': 'ui:revoke-saved-balances',
    'cancel-switch': 'system:parent-switch-user', 'cancel-greeter': 'ui:gdm-returned',
    **ENTRIES['zero-child'], **prefixed_stages('zero-child', rejected_gdm_return()),
    **prefixed_stages('kiosk-first', {
        **station_entry(),
        **continued_request(surface='kiosk', initial_seconds=75, duration_seconds=600),
        **approved_request(**LONG_CHOICES, exit='automatic')}),
    **ENTRIES['first-child'], 'first-countdown': 'ui:child-countdown-present',
    **prefixed_stages('allowed-use', native_usable_app('command', child='child', role='A', desktop_observation=False)),
    **prefixed_stages('soft-use', native_usable_app('command', child='child', role='S', desktop_observation=False)),
    'soft-close': 'ui:overlay-native-soft-close', 'soft-closed': 'ui:overlay-native-soft-closed',
    'allowed-close': 'ui:overlay-native-allowed-close', 'allowed-closed': 'ui:overlay-native-allowed-closed',
    'hard-denied': 'ui:overlay-native-hard-command-blocked',
    'remaining-countdown': 'ui:child-countdown-present',
    **native_activity_entry('activity', desktop_observation=False),
    **OVERLAY_ENTRIES['overlay-rejection'],
    **prefixed_stages('overlay-rejection', {
        **continued_request(surface='overlay', initial_seconds=600, duration_seconds=75),
        **overlay_rejected_request(outcome='rejection', fresh_estimate=True, **CHOICES),
        'form-cancel': 'ui:overlay-request-cancel', 'returned': 'ui:overlay-desktop'}),
    'rejection-activity': 'ui:overlay-native-activity',
    **OVERLAY_ENTRIES['overlay-cancel'],
    **prefixed_stages('overlay-cancel', {
        **overlay_rejected_request(outcome='cancel', fresh_estimate=True, **CHOICES),
        'form-cancel': 'ui:overlay-request-cancel', 'returned': 'ui:overlay-desktop'}),
    'cancel-activity': 'ui:overlay-native-activity',
    **OVERLAY_ENTRIES['overlay-approval'],
    'overlay-approval-open-estimate': 'ui:overlay-fraction-estimate-refresh',
    **prefixed_stages('overlay-approval', overlay_approved_request(**CHOICES, exit='immediate')),
    'approved-activity': 'ui:overlay-native-activity',
    'approved-activity-submit': 'ui:overlay-native-resubmit',
    'approved-activity-submitted': 'ui:overlay-native-submitted',
    'activity-close': 'ui:overlay-native-close', 'activity-closed': 'ui:overlay-native-closed',
    'overlay-countdown': 'ui:child-countdown-present',
    **prefixed_stages('overlay-soft-use', native_usable_app('command', child='child', role='S', desktop_observation=False)),
    'overlay-soft-close': 'ui:overlay-native-soft-close', 'overlay-soft-closed': 'ui:overlay-native-soft-closed',
    'overlay-hard-denied': 'ui:overlay-native-hard-command-blocked',
    'child-switch-ready': 'ui:fresh-child-desktop', 'child-switch': 'system:child-switch-user',
    'child-greeter': 'ui:gdm-returned',
    **ENTRIES['revoke-parent'],
    **prefixed_stages('revoke-supplied', retained_parent_entry(source='same-user', desktop_observation=False)),
    'overlay-policy': 'ui:revoke-saved-balances',
    'revoke-open': 'ui:revoke-open', 'revoke-warning': 'ui:revoke-warning',
    'revoke-confirm': 'ui:revoke-confirm', 'revoked-policy': 'ui:revoke-cleared-balances',
    'revoked-switch': 'system:parent-switch-user', 'revoked-greeter': 'ui:gdm-returned',
    'enter-locked': 'system:child-enter-locked', 'curtain': 'ui:child-lock-curtain',
    'reveal-ready': 'ui:child-lock-reveal-ready', 'time-denied': 'ui:child-lock-time-denied',
    'soft-denied': 'ui:overlay-native-soft-locked-command-blocked',
    'return-greeter': 'system:child-return-greeter', 'denied-returned': 'ui:gdm-returned',
    **prefixed_stages('kiosk-final', {
        **station_entry(),
        **continued_request(surface='kiosk', initial_seconds=75, duration_seconds=600),
        **approved_request(**LONG_CHOICES, exit='automatic')}),
    **ENTRIES['final-child'], 'final-countdown': 'ui:child-countdown-present',
    **prefixed_stages('final-soft-use', native_usable_app('command', child='child', role='S', desktop_observation=False)),
    'final-soft-close': 'ui:overlay-native-soft-close', 'final-soft-closed': 'ui:overlay-native-soft-closed',
    'final-hard-denied': 'ui:overlay-native-hard-command-blocked',
    'final-switch-ready': 'ui:fresh-child-desktop', 'final-switch': 'system:child-switch-user',
    'final-greeter': 'ui:gdm-returned',
    **ENTRIES['restore-parent'],
    **prefixed_stages('restore-supplied', retained_parent_entry(source='same-user', desktop_observation=False)),
    'final-policy': 'ui:revoke-saved-balances', 'restore-apps': 'ui:parent-apps-page',
    **POLICIES['restore-hard'], **POLICIES['restore-soft'],
    'restore-screen': 'ui:parent-screen-page', 'restore-disabled': 'ui:parent-toggle-disabled',
    'restore-saved': 'ui:parent-save-disabled', 'restore-settings': 'ui:parent-toggle-disabled-settings',
    'restore-balance': 'ui:time-explanation-reach-read',
}
_entry_stages = {stage for _prefix, fragment in ENTRIES.items() for stage in fragment}
_entry_stages.update(prefixed_stages('zero-child', rejected_gdm_return()))
_overlay_entry_stages = {stage for _prefix, fragment in OVERLAY_ENTRIES.items() for stage in fragment}
_matches, _accesses = {}, {}
for role, access, prefix in EDITS:
    _matches[prefix + '-final-match'] = (MATCH_APPS[role], RULES[role])
    _accesses[prefix + '-access'] = (MATCH_APPS[role], access)

PLAN = JourneyPlan(
    prefix='baseline-journey', worker_mode='baseline_journey', screen_tags=SCREENS,
    phases={'ready': 'setup', 'setup-detached': 'setup', 'installed-greeter': 'start',
            **{stage: 'step-1' for stage in SCREENS if stage != 'installed-greeter'}},
    stage_actions={'desktop': 'native-verify'},
    child_bindings={stage: 'child' for stage, tag in SCREENS.items()
                    if tag[:3] == 'ui:' and tag[3:] in NAMED_CHILD_OPERATIONS},
    invocations=tuple(stage for stage, tag in SCREENS.items() if tag[:3] == 'ui:'
                      and stage in _entry_stages | _overlay_entry_stages),
    challenges={prefix: (('child' if prefix[-5:] == 'child' else 'parent'),
                         prefix + ('-child-recipient-qualified' if prefix[-5:] == 'child'
                                   else '-recipient-qualified'),
                         prefix + ('-child-recipient-rechecked' if prefix[-5:] == 'child'
                                   else '-recipient-rechecked')) for prefix in ENTRIES},
    settings_checks={
        'parent-selected': SettingsObservation('fixture-child', False, ('0 minutes',)),
        'saved-settings': SettingsObservation('fixture-child', True, ('0 minutes',)),
        'restore-settings': SettingsObservation('fixture-child', False, ('0 minutes',))},
    balance_checks={'allowance-configured': 0, 'restore-balance': 0},
    match_checks=_matches, access_checks=_accesses,
    request_checks={
        **{prefix + '-flow-preserved': (prefix + '-flow-before',
            'baseline:changed-negative-choices', 'preserved_choices')
           for prefix in ('kiosk-rejection', 'kiosk-cancel', 'overlay-rejection', 'overlay-cancel')},
        'kiosk-cancel-open-estimate': ('kiosk-rejection-open-estimate',
            'baseline:changed-reentry-choices', 'remembered_choices'),
        },
    request_transfer_checks={'kiosk-final-new-form': 'overlay-approval-open-estimate'},
    activity_checks={stage: ('activity-capture', 'same') for stage in
                     ('rejection-activity', 'cancel-activity', 'approved-activity')},
    countdown_checks={
        'first-countdown': ('kiosk-first-new-estimate', 600, 60, 180),
        'remaining-countdown': ('kiosk-first-new-estimate', 600, 60, 180),
        'overlay-countdown': ('overlay-approval-open-estimate', 'estimate', 60, 180),
        'final-countdown': ('kiosk-final-new-estimate', 600, 60, 180)},
    assertions_after={
        'saved-policy': 'zero-daily-saved-app-policy',
        'kiosk-rejection-flow-preserved': 'explicit-rejection-and-preserved-form',
        'rejection-policy': 'rejection-zero-grant-and-unchanged-restrictions',
        'kiosk-cancel-flow-preserved': 'independent-authentication-cancel-and-preserved-form',
        'cancel-policy': 'cancel-zero-grant-and-unchanged-restrictions',
        'zero-child-denied': 'zero-time-child-entry-denied',
        'first-countdown': 'genuine-grant-only-approval',
        'remaining-countdown': 'usable-grant-allowed-soft-apps-and-hard-denial',
        'overlay-rejection-flow-preserved': 'overlay-rejection-no-additional-grant',
        'overlay-cancel-flow-preserved': 'overlay-cancel-no-additional-grant',
        'approved-activity-submitted': 'approved-overlay-preserves-usable-original-activity',
        'overlay-hard-denied': 'overlay-granted-soft-use-retains-hard-denial',
        'overlay-policy': 'overlay-positive-grant-and-unchanged-policy',
        'revoked-policy': 'public-confirmed-revocation-restores-zero-grant',
        'soft-denied': 'restored-time-and-soft-app-restrictions',
        'final-hard-denied': 'fresh-request-restores-usable-child-with-hard-denial',
        'final-policy': 'distinct-fresh-approval-positive-grant-and-saved-policy',
        'restore-balance': 'public-policy-and-time-restoration'},
)


class BaselineJourney(GrantAppEffectsJourney):
    def __init__(self, context, progress, plan=PLAN, *, actions=None):
        super().__init__(context, progress, plan,
            actions=fixture_actions(include_refusal=False) if actions is None else actions,
            settings={'child': 'fixture-child', 'limit_enabled': True, 'allowance': ['0 minutes']},
            app_rules={MATCH_APPS[role]: (access, RULES[role])
                       for role, access in (('A', 'allowed'), ('H', 'permanent'), ('S', 'conditional'))},
            approval_stage='kiosk-first-new-estimate', policy_reads={
                'saved-policy': (None, 'zero'), 'rejection-policy': ('saved-policy', 'zero'),
                'cancel-policy': ('saved-policy', 'zero'),
                'overlay-policy': ('saved-policy', 'positive'), 'revoked-policy': ('saved-policy', 'zero'),
                'final-policy': ('saved-policy', 'positive')},
            approval_stages={'overlay-policy': 'overlay-approval-open-estimate',
                             'final-policy': 'kiosk-final-new-estimate'},
            negative_estimates={prefix + '-flow-preserved': prefix + '-flow-before'
                                for prefix in ('overlay-rejection', 'overlay-cancel')},
            countdown_balances=('remaining-countdown',))
