"""Named-child daily access bindings; the complete case 7 history is separate."""
from accessible_ui import NAMED_CHILD_OPERATIONS
from countdown import CountdownObservation, check_countdown_balance
from installed_journey import JourneyPlan
from journey_blocks import (desktop_entry, fresh_desktop, parent_management,
                            prefixed_stages, rejected_gdm_return, retained_parent_entry)
from journey_checks import RetainedDesktopJourney
from private_artifacts import require


ENTRIES = {
    'positive': desktop_entry('other-child', source='gdm', entry='fresh'),
    'return': desktop_entry('parent', source='gdm', entry='retained'),
    'denied': desktop_entry('other-child', source='gdm', entry='fresh', expected='time-denied'),
    # Supply the second valid prompt independently of FLOW15.
    'independent': fresh_desktop('other-child', 'time-denied'),
    'off-return': desktop_entry('parent', source='gdm', entry='retained'),
    'off': desktop_entry('other-child', source='gdm', entry='fresh'),
}
SCREENS = {
    **fresh_desktop('parent'), **parent_management(child='existing'),
    'allowance-configured': 'ui:time-explanation-positive-read',
    'before': 'ui:retained-parent-read', 'session-before': 'system:parent-desktop-identity',
    'repeat-desktop': 'ui:desktop', 'switch-user': 'system:parent-switch-user',
    'gdm-switched': 'ui:gdm-returned',
    **prefixed_stages('positive', ENTRIES['positive']),
    'countdown': 'ui:child-countdown-present',
    **prefixed_stages('logout', {'desktop': 'ui:standard-desktop',
        'logout': 'system:standard-logout', 'gdm-logged-out': 'ui:gdm-returned'}),
    **prefixed_stages('return', ENTRIES['return']),
    **prefixed_stages('supplied', retained_parent_entry(source='same-user', desktop_observation=False)),
    'session-returned': 'system:parent-desktop-identity',
    'zero-configured': 'ui:time-explanation-zero-read',
    'zero-before': 'ui:retained-parent-read',
    'zero-desktop': 'ui:desktop', 'zero-switch': 'system:parent-switch-user',
    'zero-greeter': 'ui:gdm-returned',
    **prefixed_stages('denied', ENTRIES['denied']),
    **prefixed_stages('first', rejected_gdm_return()),
    'independent-entry-guard': 'system:standard-entry-fresh',
    **prefixed_stages('independent', ENTRIES['independent']),
    **prefixed_stages('second', rejected_gdm_return()),
    **prefixed_stages('off-return', ENTRIES['off-return']),
    **prefixed_stages('off-supplied', retained_parent_entry(source='same-user', desktop_observation=False)),
    'limits-disabled': 'ui:time-explanation-off-read',
    'disabled-settings': 'ui:retained-parent-read',
    'off-parent-desktop': 'ui:desktop', 'off-switch': 'system:parent-switch-user',
    'off-greeter': 'ui:gdm-returned',
    **prefixed_stages('off', ENTRIES['off']),
    'absent-countdown': 'ui:child-countdown-absent',
}
LOGIN_STAGES = set(fresh_desktop('parent')) | {
    prefix + '-' + stage for prefix, screens in ENTRIES.items()
    for stage, tag in screens.items() if tag.startswith('ui:')}
RETURN_STAGES = {prefix + '-' + stage for prefix in ('first', 'second')
                 for stage in rejected_gdm_return()}
PLAN = JourneyPlan(
    prefix='jordan-daily-access', worker_mode='jordan_daily_access', screen_tags=SCREENS,
    phases={'ready': 'setup', 'setup-detached': 'setup',
            **{stage: 'step-1' for stage in SCREENS}, 'installed-greeter': 'start'},
    invocations=tuple(stage for stage in SCREENS if stage in LOGIN_STAGES | RETURN_STAGES),
    challenges={
        'initial': ('parent', 'recipient-qualified', 'recipient-rechecked'),
        **{prefix: ('parent' if prefix in ('return', 'off-return') else 'other-child',
            prefix + ('-recipient-qualified' if prefix in ('return', 'off-return')
                      else '-standard-recipient-qualified'),
            prefix + ('-recipient-rechecked' if prefix in ('return', 'off-return')
                      else '-standard-recipient-rechecked')) for prefix in ENTRIES},
    },
    child_bindings={stage: 'existing' for stage, tag in SCREENS.items()
                    if tag.startswith('ui:') and tag[3:] in NAMED_CHILD_OPERATIONS},
    balance_checks={'allowance-configured': 900, 'zero-configured': 0},
    assertions_after={'allowance-configured': 'jordan-positive-daily-no-grant',
        'countdown': 'jordan-countdown-matches-parent',
        'supplied-parent-retained': 'same-jordan-parent-window-settings',
        'session-returned': 'same-jamie-desktop',
        'zero-configured': 'jordan-zero-daily-no-grant',
        'denied-denied': 'jordan-fresh-time-denial',
        'first-denied-returned': 'jordan-normal-greeter-return',
        'independent-denied': 'jordan-independent-time-denial',
        'second-denied-returned': 'jordan-independent-greeter-return',
        'disabled-settings': 'jordan-limits-disabled',
        'off-desktop': 'jordan-limits-off-desktop',
        'absent-countdown': 'jordan-stable-countdown-absence'},
)


class JordanDailyAccessJourney(RetainedDesktopJourney):
    def __init__(self, context, progress, plan=PLAN, *, actions=None):
        super().__init__(context, progress, plan, actions=actions,
            parent_expected={stage: {'page': 'screen-limits', 'settings': {
                'child': 'existing-fixture-child', 'limit_enabled': enabled,
                'allowance': [str(minutes) + ' minutes']}}
                for stage, enabled, minutes in (('before', True, 15),
                    ('zero-before', True, 0), ('disabled-settings', False, 15))},
            parent_checks={'supplied-parent-retained': 'before',
                           'off-supplied-parent-retained': 'zero-before'},
            window_checks={}, session_checks={'session-returned': 'session-before'})
        self.balance = None

    def check_settings(self, stage, observed):
        super().check_settings(stage, observed)
        if stage == 'allowance-configured':
            self.balance = dict(observed['ui']['time_explanation'])
        if stage == 'countdown':
            require(self.balance is not None, 'countdown:missing-balance')
            value = CountdownObservation.from_value(observed['ui']['countdown'],
                present=True, child='existing-fixture-child')
            observed['comparison'] = check_countdown_balance(value,
                seconds=self.balance['total']['seconds'],
                precision_seconds=self.balance['total']['precision_seconds'],
                observed_monotonic_ns=self.balance['observed_monotonic_ns'],
                max_elapsed_seconds=300)
