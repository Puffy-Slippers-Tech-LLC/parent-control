"""116c: independent Flatpak work survives denial and another app's closure."""
from accessible_ui import FLATPAK_POLICY_APPS, NAMED_CHILD_OPERATIONS
from flatpak_fixtures import fixture_actions
from installed_journey import JourneyPlan
from journey_blocks import (app_policy_entry, desktop_entry, desktop_return,
                            native_usable_app, prefixed_stages)
from policy_edits import AppPolicyJourney
from ui_observations import SettingsObservation, compare_app_activity


SCREENS = app_policy_entry(child='existing', initial_rows=False,
                          allowance='time-explanation-setup-thirty-read')
ACCESS = {}
for name, role, access in (('allowed', 'A', 'allowed'), ('hard', 'H', 'permanent'),
                           ('soft', 'S', 'allowed')):
    operation = 'access-flatpak-' + (name + '-' if role != 'A' else '')
    SCREENS.update({name + '-save': 'ui:' + operation + access,
                    name + '-row': 'ui:' + operation + 'row'})
    ACCESS[name + '-row'] = (FLATPAK_POLICY_APPS[role], access)
SCREENS.update(desktop_return('leave-parent', account='parent'))
ENTRIES = {}
for prefix, account, source, entry, source_account in (
        ('fresh', 'other-child', 'gdm', 'fresh', None),
        ('parent-return', 'parent', 'desktop', 'retained', 'other-child'),
        ('child-return', 'other-child', 'desktop', 'retained', 'parent')):
    ENTRIES[prefix] = prefixed_stages(prefix, desktop_entry(
        account, source=source, entry=entry, source_account=source_account))
SCREENS.update(ENTRIES['fresh'])
for name, role in (('allowed', 'A'), ('soft', 'S')):
    SCREENS.update(prefixed_stages(name, native_usable_app('command', role=role, kind='flatpak')))
    SCREENS[name + '-capture'] = 'ui:flatpak-' + name + '-policy-activity'
SCREENS.update({
    'hard-denied': 'ui:flatpak-hard-command-blocked',
    'allowed-after-denial': 'ui:flatpak-allowed-policy-activity',
    'soft-after-denial': 'ui:flatpak-soft-policy-activity',
    **ENTRIES['parent-return'], 'return-apps': 'ui:existing-apps',
    'soft-block-save': 'ui:access-flatpak-soft-conditional',
    'soft-block-row': 'ui:access-flatpak-soft-row',
    **ENTRIES['child-return'],
    'soft-closed': 'ui:flatpak-soft-policy-closed',
    'soft-denied': 'ui:flatpak-soft-command-blocked',
    'allowed-preserved': 'ui:flatpak-allowed-policy-activity',
    'allowed-resubmit': 'ui:flatpak-allowed-resubmit',
    'allowed-submitted-again': 'ui:flatpak-allowed-submitted',
    'allowed-still-original': 'ui:flatpak-allowed-policy-activity',
    'allowed-close': 'ui:flatpak-allowed-close',
    'allowed-closed': 'ui:flatpak-allowed-closed',
})
ACCESS['soft-block-row'] = (FLATPAK_POLICY_APPS['S'], 'conditional')
LOGIN_STAGES = {stage for entry in ENTRIES.values() for stage in entry
                if not stage.endswith(('-source-desktop', '-source-greeter'))}
PLAN = JourneyPlan(
    prefix='flatpak-retained-work', worker_mode='flatpak_retained_work', screen_tags=SCREENS,
    phases={'ready': 'setup', 'setup-detached': 'setup',
            **{stage: 'step-1' for stage in SCREENS}, 'installed-greeter': 'start'},
    stage_actions={'desktop': 'native-verify'},
    child_bindings={stage: 'existing' for stage, tag in SCREENS.items()
                    if tag.startswith('ui:') and tag[3:] in NAMED_CHILD_OPERATIONS},
    settings_checks={
        'parent-selected': SettingsObservation('existing-fixture-child', False, ('0 minutes',)),
        'saved-settings': SettingsObservation('existing-fixture-child', True, ('30 minutes',))},
    balance_checks={'allowance-configured': 1800}, access_checks=ACCESS,
    activity_checks={
        'allowed-after-denial': ('allowed-capture', 'same'),
        'soft-after-denial': ('soft-capture', 'same'),
        'soft-closed': ('soft-capture', 'closed'),
        'allowed-preserved': ('allowed-capture', 'same'),
        'allowed-still-original': ('allowed-capture', 'same')},
    activity_entries={'parent-return-source-desktop': 'allowed-capture',
                      'child-return-source-desktop': 'soft-capture'},
    invocations=tuple(stage for stage, tag in SCREENS.items()
                      if stage in LOGIN_STAGES and tag.startswith('ui:')),
    challenges={prefix: (account, prefix + '-' + recipient + '-qualified',
                         prefix + '-' + recipient + '-rechecked')
                for prefix, account, recipient in (
                    ('fresh', 'other-child', 'standard-recipient'),
                    ('parent-return', 'parent', 'recipient'),
                    ('child-return', 'other-child', 'standard-recipient'))},
    assertions_after={'allowed-closed': 'independent-work-preserved-through-denial-and-closure'},
)


class FlatpakRetainedWorkJourney(AppPolicyJourney):
    def __init__(self, context, progress):
        super().__init__(context, progress, PLAN, actions=fixture_actions(include_refusal=False))

    def check_activity(self, stage, observed):
        super().check_activity(stage, observed)
        if stage == 'soft-capture':
            observed['comparison'] = compare_app_activity(
                self.activity_observations[stage], self.activity_observations['allowed-capture'],
                result='separate')
