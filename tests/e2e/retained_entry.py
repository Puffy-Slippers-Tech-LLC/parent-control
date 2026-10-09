"""DESK09/FLOW15 finite retained-child visits, with explicit entry modes."""
from journey_blocks import (desktop_entry, fresh_desktop, native_activity_entry,
                            parent_management, prefixed_stages, rejected_gdm_return)
from retained_parent import RetainedParentJourney, retained_parent_entry
from installed_journey import JourneyPlan
from private_artifacts import require
from window_switch import window_switch_entry


ENTRIES = {
    'riley-fresh': ('child', 'gdm', 'fresh', 'success', None),
    'riley-same': ('child', 'desktop', 'same', 'success', None),
    'jordan-fresh': ('other-child', 'gdm', 'fresh', 'success', None),
    'jordan-same': ('other-child', 'desktop', 'same', 'success', None),
    'riley-return': ('child', 'desktop', 'retained', 'success', 'other-child'),
    'riley-unlock': ('child', 'locked', 'lock', 'success', None),
    'jordan-return': ('other-child', 'desktop', 'retained', 'success', 'child'),
    'riley-again': ('child', 'desktop', 'retained', 'success', 'other-child'),
    'riley-denied': ('child', 'gdm', 'retained', 'time-denied', None),
    'riley-restricted': ('child', 'locked', 'lock', 'time-denied', None),
}


def entry(prefix):
    account, source, mode, expected, source_account = ENTRIES[prefix]
    return prefixed_stages(prefix, desktop_entry(account, source=source, entry=mode,
                            expected=expected, source_account=source_account))


def resume(prefix, child):
    operation = 'overlay-native-' if child == 'child' else 'native-'
    return prefixed_stages(prefix, {key: 'ui:' + operation + value for key, value in (
        ('opened', 'activity'), ('submit', 'resubmit'), ('submitted', 'submitted'))})


SCREENS = {
    **fresh_desktop('parent'), **parent_management(),
    'allowance-configured': 'ui:time-explanation-positive-read',
    'before': 'ui:retained-parent-leave', 'session-before': 'system:parent-desktop-identity',
    'repeat-desktop': 'ui:desktop', 'switch-user': 'system:parent-switch-user',
    'gdm-switched': 'ui:gdm-returned',
    **entry('riley-fresh'), **native_activity_entry('riley-activity', child='child'),
    **entry('riley-same'), 'riley-wrong-mode-refused': 'system:child-entry-refusals',
    'riley-switch-ready': 'ui:fresh-child-desktop', 'riley-switch': 'system:child-switch-user',
    'riley-greeter': 'ui:gdm-returned',
    **entry('jordan-fresh'), **native_activity_entry('jordan-activity', child='other-child'),
    **entry('jordan-same'), 'jordan-wrong-mode-refused': 'system:standard-entry-refusals',
    **entry('riley-return'), 'riley-return-identity': 'system:child-entry-same',
    'riley-return-activity': 'ui:overlay-native-activity',
    'riley-lock-ready': 'ui:fresh-child-desktop', 'riley-lock': 'system:child-lock',
    **entry('riley-unlock'), 'riley-unlock-identity': 'system:child-entry-same',
    'riley-unlock-activity': 'ui:overlay-native-activity', **resume('riley-resume', 'child'),
    'riley-usable-activity': 'ui:overlay-native-activity',
    **entry('jordan-return'), 'jordan-return-identity': 'system:standard-entry-same',
    'jordan-return-activity': 'ui:native-activity', **resume('jordan-resume', 'other-child'),
    'jordan-usable-activity': 'ui:native-activity',
    **entry('riley-again'), 'riley-again-identity': 'system:child-entry-same',
    'riley-again-activity': 'ui:overlay-native-activity',
    **prefixed_stages('return', retained_parent_entry(source='child-desktop')),
    'session-returned': 'system:parent-desktop-identity', **window_switch_entry('focus-'),
    'zero-configured': 'ui:time-explanation-zero-read',
    'denial-switch-ready': 'ui:desktop', 'denial-switch': 'system:parent-switch-user',
    'denial-greeter': 'ui:gdm-returned', **entry('riley-denied'), **rejected_gdm_return(),
    'retained-before': 'system:child-retained-locked', 'enter-locked': 'system:child-enter-locked',
    **entry('riley-restricted'), 'return-greeter': 'system:child-return-greeter',
    'restricted-returned': 'ui:gdm-returned', 'retained-after': 'system:child-retained-locked',
}
LOGIN_ACCOUNTS = {'initial': 'parent', 'return': 'parent', **{
    prefix: binding[0] for prefix, binding in ENTRIES.items() if binding[2] in ('fresh', 'retained')}}
CHALLENGES = {prefix: (account,
    ('' if prefix == 'initial' else prefix + '-') +
        ('recipient-qualified' if account == 'parent' else
         'child-recipient-qualified' if account == 'child' else 'standard-recipient-qualified'),
    ('' if prefix == 'initial' else prefix + '-') +
        ('recipient-rechecked' if account == 'parent' else
         'child-recipient-rechecked' if account == 'child' else 'standard-recipient-rechecked'))
    for prefix, account in LOGIN_ACCOUNTS.items()}
LOGIN_STAGES = (set(fresh_desktop('parent')) | set(prefixed_stages('return', fresh_desktop('parent')))
                | set(rejected_gdm_return()))
for _prefix, _binding in ENTRIES.items():
    if _binding[2] in ('fresh', 'retained'):
        LOGIN_STAGES.update(prefixed_stages(_prefix, fresh_desktop(_binding[0], _binding[3])))
ACTIVITY_CHECKS = {stage: (('riley' if operation == 'ui:overlay-native-activity' else 'jordan')
                          + '-activity-capture', 'same')
    for stage, operation in SCREENS.items()
    if operation in ('ui:overlay-native-activity', 'ui:native-activity')
    and stage not in ('riley-activity-capture', 'jordan-activity-capture')}
PLAN = JourneyPlan(
    prefix='retained-entry', worker_mode='retained_entry', screen_tags=SCREENS,
    phases={'ready': 'setup', 'setup-detached': 'setup',
            **{stage: 'step-1' if list(SCREENS).index(stage) <= list(SCREENS).index('before')
               else 'step-2' for stage in SCREENS}, 'installed-greeter': 'start'},
    advance_after={'before': 'step-2'},
    invocations=tuple(stage for stage in SCREENS if stage in LOGIN_STAGES),
    challenges=CHALLENGES, activity_checks=ACTIVITY_CHECKS,
    assertions_after={'riley-wrong-mode-refused': 'riley-wrong-mode-refused-before-input',
        'jordan-wrong-mode-refused': 'jordan-wrong-mode-refused-before-input',
        'riley-return-activity': 'same-retained-riley-activity',
        'riley-unlock-activity': 'same-activity-after-lock-unlock',
        'riley-usable-activity': 'original-riley-window-usable',
        'jordan-return-activity': 'same-retained-jordan-activity',
        'jordan-usable-activity': 'original-jordan-window-usable',
        'riley-again-activity': 'independent-retained-child-return',
        'return-parent-retained': 'same-parent-window-child-page-settings',
        'session-returned': 'same-parent-desktop',
        'riley-denied-denied': 'retained-gdm-specific-time-denial',
        'riley-restricted-time-denied': 'lock-specific-restriction-without-secret',
        'retained-after': 'same-retained-locked-child-after-denials'},
)


class RetainedEntryJourney(RetainedParentJourney):
    def __init__(self, context, progress, plan=PLAN, *, actions=None):
        super().__init__(context, progress, plan, actions=actions)
        self.child_sessions = {}

    def check_settings(self, stage, observed):
        super().check_settings(stage, observed)
        value = observed.get('system', {})
        operation = value.get('operation', '')
        if '-entry-' in operation and value.get('entry') != 'fresh':
            role = operation.split('-', 1)[0]
            identity = value['session_sha256']
            if stage in ('riley-same-entry-guard', 'jordan-same-entry-guard'):
                require(role not in self.child_sessions, 'retained-entry:session-replay')
                self.child_sessions[role] = identity
            else:
                require(role in self.child_sessions and identity == self.child_sessions[role],
                        'retained-entry:child-desktop-replaced')
                observed['comparison'] = {'same_retained_child_desktop': True}
        if stage in ('retained-before', 'retained-after'):
            identity = value['session_sha256']
            require(identity == self.child_sessions.get('child'), 'retained-entry:denied-desktop-replaced')
            observed['comparison'] = {'same_retained_locked_child': True}
