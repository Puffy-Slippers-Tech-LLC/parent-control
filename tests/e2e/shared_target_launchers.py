"""229a: Jordan uses two distinct Allowed launchers for A's exact target."""
from accessible_ui import NAMED_CHILD_OPERATIONS
from installed_journey import JourneyPlan
from journey_blocks import (desktop_entry, fresh_desktop, native_usable_app,
                            parent_management, prefixed_stages)
from journey_checks import allowed_app_rows
from native_fixtures import check_catalogue, fixture_actions
from policy_edits import AppPolicyJourney
from ui_observations import SettingsObservation


SETUP = {
    **fresh_desktop('parent'), **parent_management(child='existing'),
    'parent-selected': 'ui:existing-returned',
    'allowance-configured': 'ui:time-explanation-setup-thirty-read',
    'saved-settings': 'ui:existing-returned', 'apps-page': 'ui:existing-apps',
    'initial-rows': 'ui:existing-parent-app-rows',
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


class SharedTargetLaunchersJourney(AppPolicyJourney):
    def __init__(self, context, progress, plan=PLAN, *, actions=None):
        super().__init__(context, progress, plan,
                         actions=fixture_actions(include_refusal=False) if actions is None else actions)

    def check_settings(self, stage, observed):
        super().check_settings(stage, observed)
        if stage == 'initial-rows':
            rows = allowed_app_rows(self, observed)
            observed['comparison'].update(check_catalogue(rows, alias=True))
