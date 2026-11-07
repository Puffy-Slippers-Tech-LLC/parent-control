"""116a: grid use, hidden blocked entry, restoration and separate new work."""
from accessible_ui import FLATPAK_POLICY_APPS, NAMED_CHILD_OPERATIONS
from flatpak_fixtures import fixture_actions
from installed_journey import JourneyPlan
from journey_blocks import (app_policy_entry, desktop_entry, desktop_return,
                            flatpak_blocked_app, native_usable_app, prefixed_stages)
from policy_edits import AppPolicyJourney
from private_artifacts import require
from ui_observations import SettingsObservation


SCREENS = app_policy_entry(child='existing', initial_rows=False,
                          allowance='time-explanation-setup-thirty-read')
SCREENS.update(desktop_return('leave-parent', account='parent'))
ENTRIES = {}
for prefix, account, source, entry, source_account in (
        ('fresh', 'other-child', 'gdm', 'fresh', None),
        ('block-parent', 'parent', 'desktop', 'retained', 'other-child'),
        ('blocked-child', 'other-child', 'desktop', 'retained', 'parent'),
        ('restore-parent', 'parent', 'desktop', 'retained', 'other-child'),
        ('restored-child', 'other-child', 'desktop', 'retained', 'parent')):
    ENTRIES[prefix] = prefixed_stages(prefix, desktop_entry(
        account, source=source, entry=entry, source_account=source_account))
SCREENS.update(ENTRIES['fresh'])
for name, role in (('allowed', 'A'), ('hard', 'H'), ('soft', 'S')):
    SCREENS.update(prefixed_stages(name, native_usable_app('grid', role=role, kind='flatpak')))
    if name == 'allowed':
        SCREENS['allowed-capture'] = 'ui:flatpak-allowed-policy-activity'
    else:
        SCREENS.update({name + '-close': 'ui:flatpak-' + name + '-close',
                        name + '-closed': 'ui:flatpak-' + name + '-closed'})
SCREENS.update({
    **ENTRIES['block-parent'], 'block-apps': 'ui:existing-apps',
    'block-save': 'ui:access-flatpak-soft-conditional',
    'block-row': 'ui:access-flatpak-soft-row',
    **ENTRIES['blocked-child'],
    **flatpak_blocked_app('blocked', 'S', 'grid'),
    'allowed-after-block': 'ui:flatpak-allowed-policy-activity',
    **ENTRIES['restore-parent'], 'restore-apps': 'ui:existing-apps',
    'restore-save': 'ui:access-flatpak-soft-allowed',
    'restore-row': 'ui:access-flatpak-soft-row',
    **ENTRIES['restored-child'],
    **prefixed_stages('earlier', native_usable_app('command', role='S', kind='flatpak', instance='secondary')),
    'earlier-capture': 'ui:flatpak-soft-second-activity',
    **prefixed_stages('restored', native_usable_app('grid', role='S', kind='flatpak')),
    'restored-capture': 'ui:flatpak-soft-activity',
    'earlier-reread': 'ui:flatpak-soft-second-activity',
    'allowed-preserved': 'ui:flatpak-allowed-policy-activity',
    'restored-close': 'ui:flatpak-soft-close', 'restored-closed': 'ui:flatpak-soft-closed',
    'earlier-close': 'ui:flatpak-soft-second-close', 'earlier-closed': 'ui:flatpak-soft-second-closed',
    'allowed-close': 'ui:flatpak-allowed-close', 'allowed-closed': 'ui:flatpak-allowed-closed',
})
LOGIN_STAGES = {stage for entry in ENTRIES.values() for stage in entry
                if not stage.endswith(('-source-desktop', '-source-greeter'))}
PLAN = JourneyPlan(
    prefix='flatpak-grid', worker_mode='flatpak_grid', screen_tags=SCREENS,
    phases={'ready': 'setup', 'setup-detached': 'setup',
            **{stage: 'step-1' for stage in SCREENS}, 'installed-greeter': 'start'},
    stage_actions={'desktop': 'native-verify'},
    child_bindings={stage: 'existing' for stage, tag in SCREENS.items()
                    if tag.startswith('ui:') and tag[3:] in NAMED_CHILD_OPERATIONS},
    settings_checks={
        'parent-selected': SettingsObservation('existing-fixture-child', False, ('0 minutes',)),
        'saved-settings': SettingsObservation('existing-fixture-child', True, ('30 minutes',))},
    balance_checks={'allowance-configured': 1800},
    access_checks={'block-row': (FLATPAK_POLICY_APPS['S'], 'conditional'),
                   'restore-row': (FLATPAK_POLICY_APPS['S'], 'allowed')},
    activity_checks={'allowed-after-block': ('allowed-capture', 'same'),
                     'restored-capture': ('earlier-capture', 'separate'),
                     'earlier-reread': ('earlier-capture', 'same'),
                     'allowed-preserved': ('allowed-capture', 'same')},
    activity_entries={prefix + '-source-desktop': 'allowed-capture'
                      for prefix in ('block-parent', 'blocked-child', 'restore-parent', 'restored-child')},
    invocations=tuple(stage for stage, tag in SCREENS.items()
                      if stage in LOGIN_STAGES and tag.startswith('ui:')),
    challenges={prefix: (account, prefix + '-' + recipient + '-qualified',
                         prefix + '-' + recipient + '-rechecked')
                for prefix, account, recipient in (
                    ('fresh', 'other-child', 'standard-recipient'),
                    ('block-parent', 'parent', 'recipient'),
                    ('blocked-child', 'other-child', 'standard-recipient'),
                    ('restore-parent', 'parent', 'recipient'),
                    ('restored-child', 'other-child', 'standard-recipient'))},
    assertions_after={'allowed-closed': 'grid-hidden-denied-restored-with-original-work'},
)


class FlatpakGridJourney(AppPolicyJourney):
    def __init__(self, context, progress, plan=PLAN):
        require(plan is PLAN, 'flatpak-grid:plan')
        super().__init__(context, progress, plan, actions=fixture_actions(include_refusal=False))
