"""Cases 7/8: Jordan's daily allowance across fresh or retained child visits."""
from copy import deepcopy
from dataclasses import replace

from accessible_ui import MATCH_APPS, MATCH_RULES, NAMED_CHILD_OPERATIONS
from countdown import CountdownObservation, check_countdown_balance
from installed_journey import JourneyPlan, record_installed_journey
from journey_blocks import (allowance_selection, custom_allowance, desktop_entry,
                            fresh_desktop, native_blocked_app, native_usable_app,
                            native_activity_entry, native_activity_resume,
                            parent_management, prefixed_stages, rejected_gdm_return,
                            retained_parent_entry)
from native_fixtures import fixture_actions
from journey_checks import RetainedDesktopJourney
from policy_edits import AppPolicyJourney, policy_edit
from private_artifacts import require
from ui_observations import SettingsObservation


EDITS = (('A', 'match-precise', 'allowed', 'allowed'),
         ('H', 'match-hard-precise', 'permanent', 'hard'))
SETUP = {
    **fresh_desktop('parent'), **parent_management(child='existing'),
    'initial-balance': 'ui:time-explanation-reach-read',
    'setup-enable': 'ui:parent-toggle-enabled',
    **custom_allowance('thirty', 30),
    'setup-settings': 'ui:retained-parent-read',
    'apps-page': 'ui:existing-apps',
    **{stage: tag for role, draft, access, prefix in EDITS
       for stage, tag in policy_edit(MATCH_APPS[role], draft, access, prefix).items()},
    'policy-screen': 'ui:discovery-ready',
    'setup-disable': 'ui:parent-toggle-disabled',
    'setup-off-settings': 'ui:retained-parent-read',
    'setup-off-balance': 'ui:time-explanation-reach-read',
}
TRANSITIONS = ('enabled', 'forty', 'zero', 'off', 'reenabled')
ENTRIES = {}
SCREENS = dict(SETUP)
PHASES = {stage: 'step-1' for stage in SETUP}
SAVED = {'setup-settings': (True, 30), 'setup-off-settings': (False, 30)}
for name in TRANSITIONS:
    phase = 'step-2' if name == 'enabled' else 'step-3' if name in ('forty', 'zero') else 'step-4'
    denied = name in ('zero', 'reenabled')
    edits = (custom_allowance('forty', 40) if name == 'forty' else
             allowance_selection('zero', (0,)) if name == 'zero' else
             {name + '-toggle': 'ui:parent-toggle-disabled' if name == 'off'
                               else 'ui:parent-toggle-enabled'})
    entry = desktop_entry('other-child', source='gdm', entry='fresh',
                          expected='time-denied' if denied else 'success')
    returned = desktop_entry('parent', source='gdm', entry='retained')
    ENTRIES[name + '-entry'] = entry
    ENTRIES[name + '-return'] = returned
    screens = {
        **edits,
        name + '-settings': 'ui:retained-parent-read',
        name + '-balance': 'ui:time-explanation-reach-read',
        **prefixed_stages(name + '-leave', {
            'desktop': 'ui:desktop', 'switch-user': 'system:parent-switch-user',
            'gdm-switched': 'ui:gdm-returned'}),
        **prefixed_stages(name + '-entry', entry),
    }
    if denied:
        screens.update(prefixed_stages(name + '-denial', rejected_gdm_return()))
    else:
        screens[name + '-countdown'] = 'ui:child-countdown-absent' if name == 'off' else 'ui:child-countdown-present'
        if name in ('enabled', 'off'):
            screens.update(prefixed_stages(name + '-hard', native_blocked_app('H')))
            screens.update(prefixed_stages(name + '-allowed', {
                **native_usable_app('grid'), 'close': 'ui:native-close', 'closed': 'ui:native-closed'}))
        screens.update(prefixed_stages(name + '-logout', {
            'desktop': 'ui:standard-desktop', 'logout': 'system:standard-logout',
            'gdm-logged-out': 'ui:gdm-returned'}))
    screens.update({
        **prefixed_stages(name + '-return', returned),
        **prefixed_stages(name + '-supplied', retained_parent_entry(
            source='same-user', desktop_observation=False)),
        name + '-returned-balance': 'ui:time-explanation-reach-read',
    })
    SCREENS.update(screens)
    PHASES.update({stage: phase for stage in screens})
    state = (name != 'off', 30 if name == 'enabled' else 40 if name == 'forty' else 0)
    SAVED[name + '-settings'] = state
    SAVED[name + '-supplied-parent-retained'] = state

LOGIN_STAGES = set(fresh_desktop('parent')) | {
    prefix + '-' + stage for prefix, screens in ENTRIES.items()
    for stage, tag in screens.items() if tag.startswith('ui:')}
DENIAL_STAGES = {name + '-denial-' + stage for name in ('zero', 'reenabled')
                 for stage in rejected_gdm_return()}
PLAN = JourneyPlan(
    prefix='daily-access-case', worker_mode='daily_access_case', screen_tags=SCREENS,
    phases={'ready': 'setup', 'setup-detached': 'setup', **PHASES, 'installed-greeter': 'start'},
    advance_after={'installed-greeter': 'step-1', 'setup-off-balance': 'step-2',
                   'enabled-returned-balance': 'step-3', 'zero-returned-balance': 'step-4'},
    stage_actions={'desktop': 'native-verify'},
    child_bindings={stage: 'existing' for stage, tag in SCREENS.items()
                    if tag.startswith('ui:') and tag[3:] in NAMED_CHILD_OPERATIONS},
    settings_checks={
        'parent-selected': SettingsObservation('existing-fixture-child', False, ('0 minutes',)),
        'policy-screen': SettingsObservation('existing-fixture-child', True, ('30 minutes',))},
    match_checks={prefix + '-' + suffix: (MATCH_APPS[role], MATCH_RULES[0 if role == 'A' else 3])
                  for role, _draft, _access, prefix in EDITS
                  for suffix in ('open', 'old', 'match', 'final-match')},
    access_checks={prefix + '-access': (MATCH_APPS[role], access)
                   for role, _draft, access, prefix in EDITS},
    invocations=tuple(stage for stage in SCREENS if stage in LOGIN_STAGES | DENIAL_STAGES),
    challenges={
        'initial': ('parent', 'recipient-qualified', 'recipient-rechecked'),
        **{prefix: ('parent' if prefix.endswith('-return') else 'other-child',
            prefix + ('-recipient-qualified' if prefix.endswith('-return') else '-standard-recipient-qualified'),
            prefix + ('-recipient-rechecked' if prefix.endswith('-return') else '-standard-recipient-rechecked'))
           for prefix in ENTRIES}},
)


# The retained binding shares the allowance history and public operations, but
# starts Jordan once, proves his original work survives enablement, and never
# logs him out. Close that work normally before testing new native launches.
RETAINED_PREPARATION = {
    **SETUP,
    **prefixed_stages('prepare-leave', {
        'desktop': 'ui:desktop', 'switch-user': 'system:parent-switch-user',
        'gdm-switched': 'ui:gdm-returned'}),
    **prefixed_stages('prepare-entry', desktop_entry('other-child', source='gdm', entry='fresh')),
    **native_activity_entry('original', route='grid', child='other-child'),
    'original-session': 'system:standard-entry-same',
    **prefixed_stages('prepare-child-leave', {
        'desktop': 'ui:standard-desktop', 'switch-user': 'system:standard-switch-user',
        'gdm-switched': 'ui:gdm-returned'}),
    **prefixed_stages('prepare-return', desktop_entry('parent', source='gdm', entry='retained')),
    'prepared-parent-retained': 'ui:retained-parent-read',
}
RETAINED_SCREENS = dict(RETAINED_PREPARATION)
RETAINED_PHASES = {stage: 'step-1' for stage in RETAINED_PREPARATION}
RETAINED_SAVED = {**SAVED, 'prepared-parent-retained': (False, 30)}
for name in TRANSITIONS:
    group = {stage: tag for stage, tag in SCREENS.items() if stage.startswith(name + '-')}
    if name == 'forty':
        # An allowance-only edit needs its saved value/balances, not another tour.
        group = {stage: tag for stage, tag in group.items()
                 if stage in custom_allowance('forty', 40) or stage in ('forty-settings', 'forty-balance')}
    else:
        group = {stage: tag for stage, tag in group.items()
                 if not stage.startswith((name + '-hard-', name + '-allowed-', name + '-logout-'))}
        group[name + '-entry-entry-guard'] = 'system:standard-entry-retained'
        if name in ('enabled', 'off'):
            return_start = name + '-return-entry-guard'
            before = list(group).index(return_start)
            items = list(group.items())
            apps = {
                **({**native_activity_resume('enabled-original', child='other-child'),
                    'enabled-original-close': 'ui:native-close',
                    'enabled-original-closed': 'ui:native-closed'} if name == 'enabled' else {}),
                **{stage: tag for stage, tag in SCREENS.items()
                   if stage.startswith(name + '-hard-')},
                **{stage: tag for stage, tag in SCREENS.items()
                   if stage.startswith(name + '-allowed-')},
            }
            leave = prefixed_stages(name + '-child-leave', {
                'desktop': 'ui:standard-desktop', 'switch-user': 'system:standard-switch-user',
                'gdm-switched': 'ui:gdm-returned'})
            group = dict(items[:before] + list(apps.items()) + list(leave.items()) + items[before:])
    RETAINED_SCREENS.update(group)
    RETAINED_PHASES.update({stage: PHASES.get(stage,
        'step-2' if name == 'enabled' else 'step-4') for stage in group})

RETAINED_LOGIN_PREFIXES = ('prepare-entry', 'prepare-return', *(
    prefix for name in ('enabled', 'zero', 'off', 'reenabled')
    for prefix in (name + '-entry', name + '-return')))
RETAINED_LOGIN_STAGES = set(fresh_desktop('parent')) | DENIAL_STAGES | {
    stage for prefix in RETAINED_LOGIN_PREFIXES for stage in prefixed_stages(
        prefix, fresh_desktop('parent' if prefix.endswith('-return') else 'other-child',
            'time-denied' if prefix in ('zero-entry', 'reenabled-entry') else 'success'))}
RETAINED_PLAN = replace(PLAN,
    prefix='daily-retained-access-case', worker_mode='daily_retained_access_case',
    screen_tags=RETAINED_SCREENS,
    phases={'ready': 'setup', 'setup-detached': 'setup', **RETAINED_PHASES, 'installed-greeter': 'start'},
    advance_after={'installed-greeter': 'step-1', 'prepared-parent-retained': 'step-2',
                   'enabled-returned-balance': 'step-3', 'zero-returned-balance': 'step-4'},
    child_bindings={stage: 'existing' for stage, tag in RETAINED_SCREENS.items()
                    if tag.startswith('ui:') and tag[3:] in NAMED_CHILD_OPERATIONS},
    invocations=tuple(stage for stage in RETAINED_SCREENS if stage in RETAINED_LOGIN_STAGES),
    challenges={'initial': PLAN.challenges['initial'], **{
        prefix: ('parent' if prefix.endswith('-return') else 'other-child',
            prefix + ('-recipient-qualified' if prefix.endswith('-return') else '-standard-recipient-qualified'),
            prefix + ('-recipient-rechecked' if prefix.endswith('-return') else '-standard-recipient-rechecked'))
        for prefix in RETAINED_LOGIN_PREFIXES}},
    activity_entries={'enabled-entry-entry-guard': 'original-capture'},
    activity_checks={'enabled-original-opened': ('original-capture', 'same')},
)


class DailyAccessJourney(AppPolicyJourney):
    def __init__(self, context, progress, plan=PLAN, *, actions=None):
        super().__init__(context, progress, plan,
            actions=fixture_actions(include_refusal=False) if actions is None else actions)
        self.parent_window = None
        self.saved = {}
        self.balances = {}

    def check_settings(self, stage, observed):
        super().check_settings(stage, observed)
        saved_states = RETAINED_SAVED if self.plan is RETAINED_PLAN else SAVED
        if stage in saved_states:
            enabled, minutes = saved_states[stage]
            value = observed['ui']['retained_parent']
            require(value['page'] == 'screen-limits' and value['settings'] == {
                'child': 'existing-fixture-child', 'limit_enabled': enabled,
                'allowance': [str(minutes) + ' minutes']}, 'daily-access:saved-settings')
            if self.parent_window is None:
                self.parent_window = deepcopy(value['window'])
            require(value['window'] == self.parent_window, 'daily-access:parent-window-replaced')
            if '-supplied-' in stage:
                name = stage.split('-supplied-')[0]
                require(value == self.saved[name + '-settings'], 'daily-access:retained-settings-changed')
            self.saved[stage] = deepcopy(value)
        value = observed.get('ui', {}).get('time_explanation')
        if value is not None:
            require(value['child'] == 'existing-fixture-child' and value['one_time']['seconds'] == 0,
                    'daily-access:unexpected-grant')
            require(value['daily']['seconds'] == value['total']['seconds'], 'daily-access:total-balance')
            if self.balances:
                require(value['observed_monotonic_ns'] > next(reversed(self.balances.values()))[
                    'observed_monotonic_ns'], 'daily-access:balance-order')
            if stage in ('initial-balance', 'setup-off-balance') or stage.startswith(('zero-', 'off-', 'reenabled-')):
                require(value['total']['seconds'] == 0, 'daily-access:expected-zero-time')
            elif stage == 'enabled-balance':
                require(0 < value['total']['seconds'] <= 1800 and
                        (self.plan is RETAINED_PLAN or
                         abs(value['total']['seconds'] - 1800) < value['total']['precision_seconds']),
                        'daily-access:initial-daily-balance')
            elif stage == 'forty-balance':
                before = self.balances['enabled-returned-balance']
                elapsed = (value['observed_monotonic_ns'] - before['observed_monotonic_ns']) / 1e9
                delta = value['daily']['seconds'] - before['daily']['seconds']
                tolerance = value['daily']['precision_seconds'] + before['daily']['precision_seconds']
                require(0 < elapsed <= 300 and 600 - elapsed - tolerance <= delta <= 600 + tolerance,
                        'daily-access:allowance-increase')
            else:
                require(value['daily']['seconds'] > 0, 'daily-access:positive-daily-time')
            self.balances[stage] = deepcopy(value)
        if stage in ('enabled-countdown', 'forty-countdown'):
            before = self.balances[stage.removesuffix('-countdown') + '-balance']
            countdown = CountdownObservation.from_value(observed['ui']['countdown'],
                present=True, child='existing-fixture-child')
            observed['comparison'] = check_countdown_balance(countdown,
                seconds=before['total']['seconds'], precision_seconds=before['total']['precision_seconds'],
                observed_monotonic_ns=before['observed_monotonic_ns'], max_elapsed_seconds=300)


def execute(recorder, context):
    record_installed_journey(recorder, context, PLAN, timeout=1800,
                             journey_type=DailyAccessJourney)


class RetainedDailyAccessJourney(RetainedDesktopJourney, DailyAccessJourney):
    def __init__(self, context, progress, plan=RETAINED_PLAN, *, actions=None):
        super().__init__(context, progress, plan, actions=actions,
            parent_expected={}, parent_checks={}, window_checks={},
            session_checks={name + '-entry-entry-guard': 'original-session'
                            for name in ('enabled', 'zero', 'off', 'reenabled')})


def execute_retained(recorder, context):
    record_installed_journey(recorder, context, RETAINED_PLAN, timeout=1800,
                             journey_type=RetainedDailyAccessJourney)


E2E_CASES = {'daily-only-new': execute, 'daily-only-retained': execute_retained}
