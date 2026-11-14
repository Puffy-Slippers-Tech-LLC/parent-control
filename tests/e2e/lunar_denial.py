"""Original Lunar command denial with independently usable allowed work."""
from accessible_ui import LUNAR_POLICY_APP, NAMED_CHILD_OPERATIONS
from installed_journey import JourneyPlan
from journey_blocks import (app_policy_entry, desktop_entry, native_usable_app,
                            prefixed_stages)
from ui_observations import SettingsObservation


SETUP = {
    **app_policy_entry(child='existing', allowance='time-explanation-setup-thirty-read',
                       initial_rows=False),
    **{'lunar-search-' + action: 'ui:text-catalogue-lunar-' + action
       for action in ('focus', 'selected', 'read')},
    'lunar-policy-save': 'ui:access-lunar-permanent',
    'lunar-policy-saved': 'ui:access-lunar-row',
    'parent-logout': 'system:parent-logout',
}
ENTRY = prefixed_stages('child-entry', desktop_entry(
    'other-child', source='gdm', entry='fresh'))
SCREENS = {
    **SETUP, **ENTRY,
    'observer-ready': 'ui:lunar-observer-ready',
    'lunar-before': 'ui:lunar-closed',
    'lunar-denied': 'ui:lunar-command-blocked',
    'lunar-absent': 'ui:lunar-closed',
    **prefixed_stages('allowed', {
        **native_usable_app('command', role='N'),
        'close': 'ui:native-nonmatching-close', 'closed': 'ui:native-nonmatching-closed'}),
    'child-logout': 'system:standard-logout',
}
PLAN = JourneyPlan(
    prefix='lunar-denial', worker_mode='lunar_denial', screen_tags=SCREENS,
    phases={'ready': 'setup', 'setup-detached': 'setup',
            **{stage: 'step-1' for stage in SCREENS}, 'installed-greeter': 'start'},
    stage_actions={'setup-detached': 'daytime-clock', 'desktop': 'native-verify'},
    child_bindings={stage: 'existing' for stage, tag in SETUP.items()
                    if tag.startswith('ui:') and tag[3:] in NAMED_CHILD_OPERATIONS},
    settings_checks={
        'parent-selected': SettingsObservation('existing-fixture-child', False, ('0 minutes',)),
        'saved-settings': SettingsObservation('existing-fixture-child', True, ('30 minutes',))},
    balance_checks={'allowance-configured': 1800},
    access_checks={'lunar-policy-saved': (LUNAR_POLICY_APP, 'permanent')},
    invocations=tuple(stage for stage in ENTRY if ENTRY[stage].startswith('ui:')),
    challenges={'child-entry': ('other-child', 'child-entry-standard-recipient-qualified',
                               'child-entry-standard-recipient-rechecked')},
)
