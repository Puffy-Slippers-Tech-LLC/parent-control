"""A parent's Allowed Flatpak rule leaves the app usable for both children."""
from accessible_ui import FLATPAK_POLICY_APP
from installed_journey import JourneyPlan, record_installed_journey
from journey_blocks import app_policy_entry, desktop_entry, native_usable_app, prefixed_stages
from policy_edits import AppPolicyJourney
from flatpak_fixtures import fixture_actions
from ui_observations import SettingsObservation


JORDAN_ENTRY = prefixed_stages('jordan-entry', desktop_entry('other-child', source='gdm', entry='fresh'))
RILEY_ENTRY = prefixed_stages('riley-entry', desktop_entry('child', source='gdm', entry='fresh'))
SETUP = {
    **app_policy_entry(child='existing', initial_rows=False,
                       allowance='time-explanation-setup-thirty-read'),
    'allowed-save': 'ui:access-flatpak-allowed', 'allowed-row': 'ui:access-flatpak-row',
}
JORDAN = {
    'parent-logout': 'system:parent-logout', **JORDAN_ENTRY,
    **prefixed_stages('jordan-use', native_usable_app('command', kind='flatpak', role='A')),
}
RILEY = {
    'jordan-logout': 'system:standard-logout', **RILEY_ENTRY,
    **prefixed_stages('riley-use', native_usable_app(
        'command', kind='flatpak', role='A', child='child')),
}
PLAN = JourneyPlan(
    prefix='flatpak-command-allowed', worker_mode='flatpak_command_allowed',
    screen_tags={**SETUP, **JORDAN, **RILEY},
    phases={'ready': 'setup', 'setup-detached': 'setup',
            **{stage: 'step-1' for stage in SETUP}, 'installed-greeter': 'start',
            **{stage: 'step-2' for stage in JORDAN},
            **{stage: 'step-3' for stage in RILEY}},
    advance_after={'installed-greeter': 'step-1', 'allowed-row': 'step-2',
                   'jordan-use-submitted': 'step-3'},
    stage_actions={'desktop': 'native-verify'},
    child_bindings={stage: 'existing' for stage in
                    ('allowance-configured', 'allowed-save', 'allowed-row')},
    settings_checks={
        'parent-selected': SettingsObservation('existing-fixture-child', False, ('0 minutes',)),
        'saved-settings': SettingsObservation('existing-fixture-child', True, ('30 minutes',))},
    balance_checks={'allowance-configured': 1800},
    access_checks={'allowed-row': (FLATPAK_POLICY_APP, 'allowed')},
    invocations=tuple(stage for stage in (*JORDAN_ENTRY, *RILEY_ENTRY)
                      if stage not in ('jordan-entry-entry-guard', 'riley-entry-entry-guard')),
    challenges={
        'jordan-entry': ('other-child', 'jordan-entry-standard-recipient-qualified',
                         'jordan-entry-standard-recipient-rechecked'),
        'riley-entry': ('child', 'riley-entry-child-recipient-qualified',
                        'riley-entry-child-recipient-rechecked')},
)


def execute(recorder, context):
    record_installed_journey(recorder, context, PLAN, timeout=1800,
                             actions=fixture_actions(include_refusal=False),
                             journey_type=AppPolicyJourney)


E2E_CASES = {'flatpak-command-allowed-enabled': execute}
