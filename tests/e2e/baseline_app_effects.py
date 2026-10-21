"""C04p's finite native grant/use/revocation history; no scenario completion."""
from accessible_ui import MATCH_APPS, MATCH_RULES, NAMED_CHILD_OPERATIONS
from feedback_composition import text_fragment
from installed_journey import JourneyPlan
from journey_blocks import (desktop_entry, fresh_desktop, native_usable_app,
                            parent_management, prefixed_stages, retained_parent_entry)
from kiosk_approved_flow import obtain_time
from native_fixtures import fixture_actions
from policy_edits import policy_edit
from request_composition import GrantAppEffectsJourney
from ui_observations import SettingsObservation


CHOICES = dict(child='fixture-child', approver='fixture-parent',
               duration_seconds=600, allow_soft=True)
EDITS = (
    ('A', 'match-precise', 'allowed', 'allowed'),
    ('H', 'match-hard-precise', 'permanent', 'hard'),
    ('S', 'match-soft-wildcard', 'conditional', 'soft'),
    ('H', 'match-hard-precise', 'allowed', 'restore-hard'),
    ('S', 'match-soft-wildcard', 'allowed', 'restore-soft'),
)
POLICIES = {prefix: policy_edit(MATCH_APPS[role], draft, access, prefix)
            for role, draft, access, prefix in EDITS}
RULES = {'A': MATCH_RULES[0], 'H': MATCH_RULES[3], 'S': MATCH_RULES[4]}
CHILD_ENTRY = prefixed_stages('child-entry', desktop_entry('child', source='gdm', entry='fresh'))
PARENT_RETURN = prefixed_stages('parent-return', desktop_entry('parent', source='gdm', entry='retained'))
RESTORE_RETURN = prefixed_stages('restore-return', desktop_entry('parent', source='gdm', entry='retained'))

SCREENS = {
    **fresh_desktop('parent'), **parent_management(),
    'allowance-configured': 'ui:time-explanation-setup-zero-read',
    'saved-settings': 'ui:parent-selected',
    'apps-page': 'ui:parent-apps-page',
    **POLICIES['allowed'], **POLICIES['hard'], **POLICIES['soft'],
    **text_fragment('catalogue-clear', 'setup-clear'),
    'saved-policy': 'ui:revoke-saved-balances',
    'switch-ready': 'ui:desktop', 'switch-user': 'system:parent-switch-user',
    'gdm-switched': 'ui:gdm-returned',
    **obtain_time(initial='default', **CHOICES, exit='automatic'),
    **CHILD_ENTRY,
    'child-countdown': 'ui:child-countdown-present',
    **prefixed_stages('allowed-use', native_usable_app('command', child='child', role='A')),
    **prefixed_stages('soft-use', native_usable_app('command', child='child', role='S')),
    'soft-close': 'ui:overlay-native-soft-close',
    'soft-closed': 'ui:overlay-native-soft-closed',
    'allowed-close': 'ui:overlay-native-allowed-close',
    'allowed-closed': 'ui:overlay-native-allowed-closed',
    'hard-denied': 'ui:overlay-native-hard-command-blocked',
    'remaining-countdown': 'ui:child-countdown-present',
    'child-switch-ready': 'ui:fresh-child-desktop',
    'child-switch': 'system:child-switch-user', 'child-greeter': 'ui:gdm-returned',
    **PARENT_RETURN,
    **prefixed_stages('supplied', retained_parent_entry(source='same-user')),
    'granted-policy': 'ui:revoke-saved-balances',
    'revoke-open': 'ui:revoke-open', 'revoke-warning': 'ui:revoke-warning',
    'revoke-confirm': 'ui:revoke-confirm',
    'revoked-policy': 'ui:revoke-cleared-balances',
    'parent-switch-ready': 'ui:desktop', 'parent-switch': 'system:parent-switch-user',
    'revoked-greeter': 'ui:gdm-returned',
    'enter-locked': 'system:child-enter-locked',
    'curtain': 'ui:child-lock-curtain', 'reveal-ready': 'ui:child-lock-reveal-ready',
    'time-denied': 'ui:child-lock-time-denied',
    'soft-denied': 'ui:overlay-native-soft-locked-command-blocked',
    'return-greeter': 'system:child-return-greeter', 'denied-returned': 'ui:gdm-returned',
    **RESTORE_RETURN,
    **prefixed_stages('restored', retained_parent_entry(source='same-user')),
    'restore-apps': 'ui:parent-apps-page',
    **POLICIES['restore-hard'], **POLICIES['restore-soft'],
    **text_fragment('catalogue-clear', 'restore-clear'),
    'restore-screen': 'ui:parent-screen-page',
    'restore-disabled': 'ui:parent-toggle-disabled',
    'restore-saved': 'ui:parent-save-disabled',
    'restore-settings': 'ui:parent-toggle-disabled-settings',
    'restore-balance': 'ui:time-explanation-reach-read',
}
_login = set(CHILD_ENTRY) | set(PARENT_RETURN) | set(RESTORE_RETURN)
_matches, _accesses = {}, {}
for role, _draft, access, prefix in EDITS:
    for suffix in ('open', 'old', 'match', 'final-match'):
        _matches[prefix + '-' + suffix] = (MATCH_APPS[role], RULES[role])
    _accesses[prefix + '-access'] = (MATCH_APPS[role], access)
PLAN = JourneyPlan(
    prefix='baseline-app-effects', worker_mode='baseline_app_effects', screen_tags=SCREENS,
    phases={'ready': 'setup', 'setup-detached': 'setup',
            **{stage: 'step-1' for stage in SCREENS}, 'installed-greeter': 'start'},
    stage_actions={'installed-greeter': 'native-refuse', 'desktop': 'native-verify'},
    child_bindings={stage: 'child' for stage, tag in SCREENS.items()
                    if tag.startswith('ui:') and tag[3:] in NAMED_CHILD_OPERATIONS},
    settings_checks={
        'parent-selected': SettingsObservation('fixture-child', False, ('0 minutes',)),
        'saved-settings': SettingsObservation('fixture-child', True, ('0 minutes',)),
        'restore-settings': SettingsObservation('fixture-child', False, ('0 minutes',))},
    balance_checks={'allowance-configured': 0, 'restore-balance': 0},
    match_checks=_matches, access_checks=_accesses,
    countdown_checks={stage: ('new-estimate', 600, 60, 180)
                      for stage in ('child-countdown', 'remaining-countdown')},
    invocations=tuple(stage for stage, tag in SCREENS.items()
                      if stage in _login and tag.startswith('ui:')),
    challenges={
        'child-entry': ('child', 'child-entry-child-recipient-qualified',
                        'child-entry-child-recipient-rechecked'),
        'parent-return': ('parent', 'parent-return-recipient-qualified',
                          'parent-return-recipient-rechecked'),
        'restore-return': ('parent', 'restore-return-recipient-qualified',
                           'restore-return-recipient-rechecked')},
    assertions_after={
        'saved-policy': 'zero-time-and-saved-native-policy',
        'remaining-countdown': 'positive-grant-allowed-soft-use-and-hard-denial',
        'granted-policy': 'independent-positive-grant-and-unchanged-rules',
        'revoked-policy': 'confirmed-zero-grant-and-unchanged-rules',
        'soft-denied': 'time-restriction-and-attributed-soft-execution-denial',
        'restore-balance': 'public-policy-and-time-restoration'},
)


class BaselineAppEffectsJourney(GrantAppEffectsJourney):
    def __init__(self, context, progress, plan=PLAN, *, actions=None):
        super().__init__(context, progress, plan,
            actions=fixture_actions() if actions is None else actions,
            settings={'child': 'fixture-child', 'limit_enabled': True, 'allowance': ['0 minutes']},
            app_rules={MATCH_APPS[role]: (access, RULES[role])
                       for role, access in (('A', 'allowed'), ('H', 'permanent'), ('S', 'conditional'))},
            approval_stage='new-estimate', policy_reads={
                'saved-policy': (None, 'zero'),
                'granted-policy': ('saved-policy', 'positive'),
                'revoked-policy': ('saved-policy', 'zero')})
