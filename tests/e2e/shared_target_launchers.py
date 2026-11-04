"""229a: Jordan uses two distinct Allowed launchers for A's exact target."""
from accessible_ui import NAMED_CHILD_OPERATIONS
from installed_journey import JourneyPlan
from journey_blocks import app_policy_entry, desktop_entry, native_usable_app, prefixed_stages
from policy_edits import NativePolicyJourney
from ui_observations import SettingsObservation


SETUP = {
    **app_policy_entry(child='existing', allowance='time-explanation-setup-thirty-read'),
    'parent-logout': 'system:parent-logout',
}
ENTRY = prefixed_stages('child-entry', desktop_entry('other-child', source='gdm', entry='fresh'))
SCREENS = {**SETUP, **ENTRY}
for name, role in (('original', None), ('alias', 'Alias')):
    SCREENS.update(prefixed_stages(name, {
        **native_usable_app('grid', role=role),
        'close': 'ui:native-close', 'closed': 'ui:native-closed'}))
SCREENS['child-logout'] = 'system:standard-logout'

PLAN = JourneyPlan(
    prefix='shared-target-launchers', worker_mode='shared_target_launchers', screen_tags=SCREENS,
    phases={'ready': 'setup', 'setup-detached': 'setup',
            **{stage: 'step-1' for stage in SCREENS}, 'installed-greeter': 'start'},
    stage_actions={'desktop': 'native-verify'},
    child_bindings={stage: 'existing' for stage, tag in SETUP.items()
                    if tag.startswith('ui:') and tag[3:] in NAMED_CHILD_OPERATIONS},
    settings_checks={
        'parent-selected': SettingsObservation('existing-fixture-child', False, ('0 minutes',)),
        'saved-settings': SettingsObservation('existing-fixture-child', True, ('30 minutes',))},
    balance_checks={'allowance-configured': 1800},
    invocations=tuple(stage for stage, tag in ENTRY.items() if tag.startswith('ui:')),
    challenges={'child-entry': ('other-child', 'child-entry-standard-recipient-qualified',
                                'child-entry-standard-recipient-rechecked')},
    assertions_after={'original-closed': 'original-launcher-usable',
                      'alias-closed': 'alias-launcher-usable'},
)


class SharedTargetLaunchersJourney(NativePolicyJourney):
    def __init__(self, context, progress, plan=PLAN, *, actions=None):
        super().__init__(context, progress, plan, actions=actions, alias=True)
