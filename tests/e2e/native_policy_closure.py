"""079a: a Parent save closes the child's captured native activity."""
from dataclasses import replace

from accessible_ui import MATCH_APPS, MATCH_RULES, NAMED_CHILD_OPERATIONS
from installed_journey import JourneyPlan
from journey_blocks import (app_policy_entry, desktop_entry, native_blocked_app,
                            native_usable_app, prefixed_stages)
from policy_edits import NativePolicyJourney, policy_edit
from private_artifacts import EvidenceError, require
from ui_observations import AppActivityObservation, SettingsObservation, compare_app_activity


SETUP = app_policy_entry(child='existing', allowance='time-explanation-setup-thirty-read')
SCREENS = dict(SETUP)
ENTRIES, POLICIES = {}, {}
for name, route, access in (('hard', 'grid', 'permanent'), ('soft', 'command', 'conditional')):
    if name == 'soft':
        ENTRIES['restore-parent'] = prefixed_stages('restore-parent', desktop_entry(
            'parent', source='gdm', entry='retained'))
        POLICIES['restore'] = policy_edit(MATCH_APPS['A'], 'match-precise', 'allowed', 'restore')
        SCREENS.update({**ENTRIES['restore-parent'], 'restore-apps': 'ui:existing-apps',
                        **POLICIES['restore']})
    SCREENS.update(prefixed_stages(name + '-leave-parent', {
        'desktop': 'ui:desktop', 'switch': 'system:parent-switch-user', 'greeter': 'ui:gdm-returned'}))
    ENTRIES[name + '-fresh'] = prefixed_stages(name + '-fresh', desktop_entry(
        'other-child', source='gdm', entry='fresh'))
    ENTRIES[name + '-parent'] = prefixed_stages(name + '-parent', desktop_entry(
        'parent', source='desktop', entry='retained', source_account='other-child'))
    ENTRIES[name + '-return'] = prefixed_stages(name + '-return', desktop_entry(
        'other-child', source='desktop', entry='retained', source_account='parent'))
    POLICIES[name] = policy_edit(MATCH_APPS['A'], 'match-precise', access, name + '-block')
    SCREENS.update({
        **ENTRIES[name + '-fresh'],
        **prefixed_stages(name + '-activity', native_usable_app(route)),
        name + '-capture': 'ui:native-policy-activity',
        **ENTRIES[name + '-parent'], name + '-apps': 'ui:existing-apps',
        **POLICIES[name], **ENTRIES[name + '-return'],
        name + '-closed': 'ui:native-policy-closed',
        **prefixed_stages(name + '-denied', native_blocked_app('A')),
        **prefixed_stages(name + '-unaffected', {
            **native_usable_app('command', role='N'),
            'close': 'ui:native-nonmatching-close', 'closed': 'ui:native-nonmatching-closed'}),
        name + '-logout': 'system:standard-logout',
    })

# Source observations use seen(); only the subsequent sign-in uses invoke().
LOGIN_STAGES = {stage for entry in ENTRIES.values() for stage in entry
                if not stage.endswith(('-source-desktop', '-source-greeter'))}
PLAN = JourneyPlan(
    prefix='native-policy-closure', worker_mode='native_policy_closure', screen_tags=SCREENS,
    phases={'ready': 'setup', 'setup-detached': 'setup',
            **{stage: 'step-1' for stage in SCREENS}, 'installed-greeter': 'start'},
    stage_actions={'desktop': 'native-verify'},
    child_bindings={stage: 'existing' for stage, tag in SCREENS.items()
                    if tag.startswith('ui:') and tag[3:] in NAMED_CHILD_OPERATIONS},
    settings_checks={
        'parent-selected': SettingsObservation('existing-fixture-child', False, ('0 minutes',)),
        'saved-settings': SettingsObservation('existing-fixture-child', True, ('30 minutes',))},
    balance_checks={'allowance-configured': 1800},
    match_checks={prefix + '-' + suffix: (MATCH_APPS['A'], MATCH_RULES[0])
                  for prefix in ('hard-block', 'restore', 'soft-block')
                  for suffix in ('open', 'old', 'match', 'final-match')},
    access_checks={prefix + '-access': (MATCH_APPS['A'], access) for prefix, access in (
        ('hard-block', 'permanent'), ('restore', 'allowed'), ('soft-block', 'conditional'))},
    activity_checks={name + '-closed': (name + '-capture', 'closed') for name in ('hard', 'soft')},
    activity_entries={name + '-return-source-desktop': name + '-capture' for name in ('hard', 'soft')},
    invocations=tuple(stage for stage, tag in SCREENS.items()
                      if stage in LOGIN_STAGES and tag.startswith('ui:')),
    challenges={prefix: (account, prefix + '-' + role + '-qualified', prefix + '-' + role + '-rechecked')
                for prefix, account, role in (
                    ('hard-fresh', 'other-child', 'standard-recipient'),
                    ('hard-parent', 'parent', 'recipient'),
                    ('hard-return', 'other-child', 'standard-recipient'),
                    ('restore-parent', 'parent', 'recipient'),
                    ('soft-fresh', 'other-child', 'standard-recipient'),
                    ('soft-parent', 'parent', 'recipient'),
                    ('soft-return', 'other-child', 'standard-recipient'))},
    assertions_after={name + '-unaffected-closed': name + '-original-closed-denied-and-unaffected-usable'
                      for name in ('hard', 'soft')},
)


class NativePolicyClosureJourney(NativePolicyJourney):
    def __init__(self, context, progress, plan=PLAN, *, actions=None):
        super().__init__(context, progress, plan, actions=actions)

    def check_activity(self, stage, observed):
        if stage == 'hard-closed':
            # Qualify the new comparison's two distinct refusal boundaries once,
            # against a real complete observation. No additional input or replay.
            earlier = self.activity_observations['hard-capture']
            current = AppActivityObservation.from_value(observed['ui']['activity'], closed=True)
            for wrong in (replace(earlier, binding='native-secondary'),
                          replace(earlier, owner=(earlier.owner[0] + 1, earlier.owner[1]))):
                try:
                    compare_app_activity(current, wrong, result='closed')
                except EvidenceError as error:
                    require(str(error) == 'ui:app-closure-binding', 'ui:app-closure-wrong-refusal')
                else:
                    require(False, 'ui:app-closure-refusal-missing')
            observed['closure_refusals'] = {'wrong_activity': True, 'wrong_owner': True}
        super().check_activity(stage, observed)
