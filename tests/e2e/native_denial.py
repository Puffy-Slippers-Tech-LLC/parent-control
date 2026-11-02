"""079d: saved native rules, fresh execution denial and unaffected use."""
from accessible_ui import MATCH_APPS, MATCH_RULES, NAMED_CHILD_OPERATIONS
from installed_journey import JourneyPlan
from journey_blocks import (desktop_entry, fresh_desktop, native_blocked_app,
                            native_usable_app, parent_management, prefixed_stages)
from journey_checks import allowed_app_rows
from native_fixtures import check_catalogue, fixture_actions
from policy_edits import AppPolicyJourney, policy_edit
from ui_observations import SettingsObservation


EDITS = (('A', 'match-precise', 'allowed', 'allowed'),
         ('H', 'match-hard-precise', 'permanent', 'hard'),
         ('S', 'match-soft-wildcard', 'conditional', 'soft'))
POLICIES = {prefix: policy_edit(MATCH_APPS[role], draft, access, prefix)
            for role, draft, access, prefix in EDITS}
SETUP = {
    **fresh_desktop('parent'), **parent_management(),
    'child-picker-opened': 'ui:existing-child-picker-opened',
    'child-choice-highlighted': 'ui:existing-child-choice-highlighted',
    'parent-selected': 'ui:existing-returned',
    'allowance-configured': 'ui:time-explanation-setup-thirty-read',
    'saved-settings': 'ui:existing-returned', 'apps-page': 'ui:existing-apps',
    'initial-rows': 'ui:existing-parent-app-rows',
    **POLICIES['allowed'], **POLICIES['hard'], **POLICIES['soft'],
    'parent-logout': 'system:parent-logout',
}
ENTRIES = {name: prefixed_stages(name + '-entry', desktop_entry(
    'other-child', source='gdm', entry='fresh')) for name in ('first', 'independent')}
SCREENS = dict(SETUP)
for name, entry in ENTRIES.items():
    SCREENS.update({
        **entry,
        **prefixed_stages(name + '-hard', native_blocked_app('H')),
        **prefixed_stages(name + '-soft', native_blocked_app('S')),
        **prefixed_stages(name + '-allowed', {
            **native_usable_app('grid'), 'close': 'ui:native-close', 'closed': 'ui:native-closed'}),
        **prefixed_stages(name + '-nonmatching', {
            **native_usable_app('command', role='N'),
            'close': 'ui:native-nonmatching-close', 'closed': 'ui:native-nonmatching-closed'}),
        name + '-logout': 'system:standard-logout',
    })

RULES = {'A': MATCH_RULES[0], 'H': MATCH_RULES[3], 'S': MATCH_RULES[4]}
PLAN = JourneyPlan(
    prefix='native-denial', worker_mode='native_denial', screen_tags=SCREENS,
    phases={'ready': 'setup', 'setup-detached': 'setup',
            **{stage: 'step-1' for stage in SCREENS}, 'installed-greeter': 'start'},
    stage_actions={'desktop': 'native-verify'},
    child_bindings={stage: 'existing' for stage, tag in SETUP.items()
                    if tag.startswith('ui:') and tag[3:] in NAMED_CHILD_OPERATIONS},
    settings_checks={
        'parent-selected': SettingsObservation('existing-fixture-child', False, ('0 minutes',)),
        'saved-settings': SettingsObservation('existing-fixture-child', True, ('30 minutes',))},
    balance_checks={'allowance-configured': 1800},
    match_checks={prefix + '-' + suffix: (MATCH_APPS[role], RULES[role])
                  for role, _draft, _access, prefix in EDITS
                  for suffix in ('open', 'old', 'match', 'final-match')},
    access_checks={prefix + '-access': (MATCH_APPS[role], access)
                   for role, _draft, access, prefix in EDITS},
    invocations=tuple(stage for entry in ENTRIES.values() for stage, tag in entry.items()
                      if tag.startswith('ui:')),
    challenges={name + '-entry': ('other-child', name + '-entry-standard-recipient-qualified',
                                 name + '-entry-standard-recipient-rechecked')
                for name in ENTRIES},
    assertions_after={name + '-nonmatching-closed': name + '-native-denial-and-unaffected-use'
                      for name in ENTRIES},
)


class NativeDenialJourney(AppPolicyJourney):
    def __init__(self, context, progress, plan=PLAN, *, actions=None):
        super().__init__(context, progress, plan,
                         actions=fixture_actions(include_refusal=False) if actions is None else actions)

    def check_settings(self, stage, observed):
        super().check_settings(stage, observed)
        if stage == 'initial-rows':
            rows = allowed_app_rows(self, observed)
            observed['comparison'].update(check_catalogue(rows))
