"""116: Parent blocks Flatpaks, closes captured work and preserves Allowed use."""
from accessible_ui import FLATPAK_POLICY_APPS, NAMED_CHILD_OPERATIONS
from flatpak_fixtures import fixture_actions
from installed_journey import JourneyPlan
from journey_blocks import app_policy_entry, desktop_entry, native_usable_app, prefixed_stages
from policy_edits import AppPolicyJourney
from ui_observations import SettingsObservation


SCREENS = app_policy_entry(child='existing', initial_rows=False,
                          allowance='time-explanation-setup-thirty-read')
ENTRIES = {}
for name, role, access in (('hard', 'H', 'permanent'), ('soft', 'S', 'conditional')):
    if name == 'soft':
        ENTRIES['next-parent'] = prefixed_stages('next-parent', desktop_entry(
            'parent', source='gdm', entry='retained'))
        SCREENS.update(ENTRIES['next-parent'])
    SCREENS.update(prefixed_stages(name + '-leave-parent', {
        'desktop': 'ui:desktop', 'switch': 'system:parent-switch-user', 'greeter': 'ui:gdm-returned'}))
    for suffix, account, source, entry, source_account in (
            ('fresh', 'other-child', 'gdm', 'fresh', None),
            ('parent', 'parent', 'desktop', 'retained', 'other-child'),
            ('return', 'other-child', 'desktop', 'retained', 'parent')):
        prefix = name + '-' + suffix
        ENTRIES[prefix] = prefixed_stages(prefix, desktop_entry(
            account, source=source, entry=entry, source_account=source_account))
    SCREENS.update({
        **ENTRIES[name + '-fresh'],
        **prefixed_stages(name + '-activity', native_usable_app('command', role=role, kind='flatpak')),
        name + '-capture': 'ui:flatpak-' + name + '-policy-activity',
        **ENTRIES[name + '-parent'], name + '-apps': 'ui:existing-apps',
        name + '-block-save': 'ui:access-flatpak-' + name + '-' + access,
        name + '-block-row': 'ui:access-flatpak-' + name + '-row',
        **ENTRIES[name + '-return'],
        name + '-closed': 'ui:flatpak-' + name + '-policy-closed',
        name + '-denied': 'ui:flatpak-' + name + '-command-blocked',
        **prefixed_stages(name + '-unaffected', {
            **native_usable_app('command', role='A', kind='flatpak'),
            'close': 'ui:flatpak-allowed-close', 'closed': 'ui:flatpak-allowed-closed'}),
        name + '-logout': 'system:standard-logout',
    })

LOGIN_STAGES = {stage for entry in ENTRIES.values() for stage in entry
                if not stage.endswith(('-source-desktop', '-source-greeter'))}
PLAN = JourneyPlan(
    prefix='flatpak-policy-closure', worker_mode='flatpak_policy_closure', screen_tags=SCREENS,
    phases={'ready': 'setup', 'setup-detached': 'setup',
            **{stage: 'step-1' for stage in SCREENS}, 'installed-greeter': 'start'},
    stage_actions={'desktop': 'native-verify'},
    child_bindings={stage: 'existing' for stage, tag in SCREENS.items()
                    if tag.startswith('ui:') and tag[3:] in NAMED_CHILD_OPERATIONS},
    settings_checks={
        'parent-selected': SettingsObservation('existing-fixture-child', False, ('0 minutes',)),
        'saved-settings': SettingsObservation('existing-fixture-child', True, ('30 minutes',))},
    balance_checks={'allowance-configured': 1800},
    access_checks={name + '-block-row': (FLATPAK_POLICY_APPS[role], access)
                   for name, role, access in (('hard', 'H', 'permanent'), ('soft', 'S', 'conditional'))},
    activity_checks={name + '-closed': (name + '-capture', 'closed') for name in ('hard', 'soft')},
    activity_entries={name + '-return-source-desktop': name + '-capture' for name in ('hard', 'soft')},
    invocations=tuple(stage for stage, tag in SCREENS.items()
                      if stage in LOGIN_STAGES and tag.startswith('ui:')),
    challenges={prefix: (account, prefix + '-' + recipient + '-qualified',
                         prefix + '-' + recipient + '-rechecked')
                for prefix, account, recipient in (
                    ('hard-fresh', 'other-child', 'standard-recipient'),
                    ('hard-parent', 'parent', 'recipient'),
                    ('hard-return', 'other-child', 'standard-recipient'),
                    ('next-parent', 'parent', 'recipient'),
                    ('soft-fresh', 'other-child', 'standard-recipient'),
                    ('soft-parent', 'parent', 'recipient'),
                    ('soft-return', 'other-child', 'standard-recipient'))},
    assertions_after={name + '-unaffected-closed': name + '-closed-denied-and-allowed-usable'
                      for name in ('hard', 'soft')},
)


class FlatpakPolicyClosureJourney(AppPolicyJourney):
    def __init__(self, context, progress):
        super().__init__(context, progress, PLAN, actions=fixture_actions(include_refusal=False))
