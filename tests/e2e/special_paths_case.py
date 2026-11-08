"""Case 188: Hard and Soft rules deny special-path originals and copies."""
from accessible_ui import MATCH_APPS, NAMED_CHILD_OPERATIONS
from installed_journey import JourneyPlan, record_installed_journey
from journey_blocks import (app_policy_entry, desktop_entry, desktop_return, native_blocked_app,
                            native_usable_app, prefixed_stages, retained_parent_entry)
from native_fixtures import fixture_actions
from native_space_path import copy_actions
from policy_edits import NativePolicyJourney
from ui_observations import SettingsObservation


SCREENS = {
    **app_policy_entry(child='existing', allowance='time-explanation-setup-thirty-read'),
    'space-copy': 'ui:existing-apps', 'comma-copy': 'ui:existing-apps',
}
PHASES = {stage: 'step-1' for stage in SCREENS}
ACCESS_CHECKS = {}
ENTRIES = {}
for name, choice, phase in (('hard', 'permanent', 'step-2'),
                             ('soft', 'conditional', 'step-3')):
    group = {}
    for label, role in (('hard', 'H'), ('comma', 'C')):
        group.update({name + '-' + label + '-save': 'ui:access-' + label + '-' + choice,
                      name + '-' + label + '-row': 'ui:access-' + label + '-row'})
        ACCESS_CHECKS[name + '-' + label + '-row'] = (MATCH_APPS[role], choice)
    group.update(desktop_return(name + '-leave', account='parent'))
    for account, suffix in (('other-child', 'entry'), ('parent', 'return')):
        ENTRIES[name + '-' + suffix] = desktop_entry(account, source='gdm',
            entry='fresh' if account == 'other-child' else 'retained')
    group.update(prefixed_stages(name + '-entry', ENTRIES[name + '-entry']))
    for label, role in (('space-original', 'H'), ('space-copy', 'SpaceCopy'),
                        ('comma-original', 'C'), ('comma-copy', 'CommaCopy')):
        group.update(prefixed_stages(name + '-' + label, native_blocked_app(role)))
    group.update(prefixed_stages(name + '-allowed', {
        **native_usable_app('command', role='N'),
        'close': 'ui:native-nonmatching-close', 'closed': 'ui:native-nonmatching-closed'}))
    group.update({name + '-logout': 'system:standard-logout',
                  name + '-greeter': 'ui:gdm-returned'})
    group.update(prefixed_stages(name + '-return', ENTRIES[name + '-return']))
    group.update(prefixed_stages(name + '-supplied', retained_parent_entry(
        source='same-user', desktop_observation=False)))
    group[name + '-apps-page'] = 'ui:existing-apps'
    SCREENS.update(group)
    PHASES.update({stage: phase for stage in group})

# Both copies must be readable by their owner for identity-checked cleanup.
# Restore through Parent after both denial histories, before FILE05 cleanup.
for label, role in (('hard', 'H'), ('comma', 'C')):
    SCREENS.update({'restore-' + label + '-save': 'ui:access-' + label + '-allowed',
                    'restore-' + label + '-row': 'ui:access-' + label + '-row'})
    ACCESS_CHECKS['restore-' + label + '-row'] = (MATCH_APPS[role], 'allowed')
SCREENS.update({'space-cleanup': 'ui:existing-apps', 'comma-cleanup': 'ui:existing-apps',
                'parent-logout': 'system:parent-logout'})
LOGIN_STAGES = {prefix + '-' + stage for prefix, entry in ENTRIES.items()
                for stage, tag in entry.items() if tag.startswith('ui:')}
PLAN = JourneyPlan(
    prefix='special-paths-case', worker_mode='special_paths_case', screen_tags=SCREENS,
    phases={'ready': 'setup', 'setup-detached': 'setup',
            **{stage: PHASES.get(stage, 'step-3') for stage in SCREENS}, 'installed-greeter': 'start'},
    advance_after={'comma-copy': 'step-2', 'hard-apps-page': 'step-3'},
    stage_actions={'desktop': 'native-verify', 'space-copy': 'space-copy',
                   'comma-copy': 'comma-copy', 'space-cleanup': 'space-cleanup',
                   'comma-cleanup': 'comma-cleanup'},
    child_bindings={stage: 'existing' for stage, tag in SCREENS.items()
                    if tag.startswith('ui:') and tag[3:] in NAMED_CHILD_OPERATIONS},
    settings_checks={
        'parent-selected': SettingsObservation('existing-fixture-child', False, ('0 minutes',)),
        'saved-settings': SettingsObservation('existing-fixture-child', True, ('30 minutes',))},
    balance_checks={'allowance-configured': 1800}, access_checks=ACCESS_CHECKS,
    invocations=tuple(stage for stage in SCREENS if stage in LOGIN_STAGES),
    challenges={prefix: (
        'parent' if prefix.endswith('-return') else 'other-child',
        prefix + ('-recipient-qualified' if prefix.endswith('-return') else '-standard-recipient-qualified'),
        prefix + ('-recipient-rechecked' if prefix.endswith('-return') else '-standard-recipient-rechecked'))
        for prefix in ENTRIES},
)


class SpecialPathsJourney(NativePolicyJourney):
    def __init__(self, context, progress, plan=PLAN, *, actions=None):
        super().__init__(context, progress, plan, actions={
            **fixture_actions(include_refusal=False), **copy_actions('space'),
            **copy_actions('comma')} if actions is None else actions)


def execute(recorder, context):
    record_installed_journey(recorder, context, PLAN, timeout=1800,
                             journey_type=SpecialPathsJourney)


E2E_CASES = {'special-paths': execute}
