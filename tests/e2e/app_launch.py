"""Cases 80–81: Allowed native command use and independent child access."""
from dataclasses import replace
from installed_journey import JourneyPlan, record_installed_journey
from journey_blocks import fresh_desktop, parent_management, desktop_entry, native_usable_app, prefixed_stages
from native_fixtures import fixture_actions
from policy_edits import policy_edit, AppPolicyJourney
from accessible_ui import MATCH_APP
from match_rules import MATCH_RULES
from ui_observations import SettingsObservation


POLICY = policy_edit(MATCH_APP, 'match-precise', 'allowed', 'allowed')
SETUP = {
    **fresh_desktop('parent'), **parent_management(),
    'child-picker-opened': 'ui:existing-child-picker-opened',
    'child-choice-highlighted': 'ui:existing-child-choice-highlighted',
    'parent-selected': 'ui:existing-returned',
    'allowance-configured': 'ui:time-explanation-setup-thirty-read',
    'saved-settings': 'ui:existing-returned',
    'apps-page': 'ui:existing-apps', **POLICY,
}
JORDAN_ENTRY = prefixed_stages('jordan-entry', desktop_entry('other-child', source='gdm', entry='fresh'))
RILEY_ENTRY = prefixed_stages('riley-entry', desktop_entry('child', source='gdm', entry='fresh'))
JORDAN = {
    'parent-logout': 'system:parent-logout',
    **JORDAN_ENTRY,
    **prefixed_stages('jordan-use', native_usable_app('command', child='other-child')),
}
RILEY = {
    'jordan-logout': 'system:standard-logout',
    **RILEY_ENTRY,
    **prefixed_stages('riley-use', native_usable_app('command', child='child')),
}
SCREENS = {**SETUP, **JORDAN, **RILEY}
PLAN = JourneyPlan(
    prefix='native-command-allowed', worker_mode='native_command_allowed', screen_tags=SCREENS,
    phases={'ready': 'setup', 'setup-detached': 'setup',
            **{stage: 'step-1' for stage in SETUP}, 'installed-greeter': 'start',
            **{stage: 'step-2' for stage in JORDAN},
            **{stage: 'step-3' for stage in RILEY}},
    advance_after={'installed-greeter': 'step-1', 'allowed-final-match': 'step-2',
                   'jordan-use-submitted': 'step-3'},
    stage_actions={'desktop': 'native-verify'},
    child_bindings={'allowance-configured': 'existing', **{
        stage: 'existing' for stage in POLICY if stage != 'allowed-found'}},
    settings_checks={
        'parent-selected': SettingsObservation('existing-fixture-child', False, ('0 minutes',)),
        'saved-settings': SettingsObservation('existing-fixture-child', True, ('30 minutes',))},
    balance_checks={'allowance-configured': 1800},
    match_checks={stage: MATCH_RULES[0] for stage in
                  ('allowed-open', 'allowed-old', 'allowed-match', 'allowed-final-match')},
    access_checks={'allowed-access': 'allowed'},
    invocations=tuple(stage for stage in (*JORDAN_ENTRY, *RILEY_ENTRY)
                      if stage not in ('jordan-entry-entry-guard', 'riley-entry-entry-guard')),
    challenges={
        'jordan-entry': ('other-child', 'jordan-entry-standard-recipient-qualified',
                         'jordan-entry-standard-recipient-rechecked'),
        'riley-entry': ('child', 'riley-entry-child-recipient-qualified',
                        'riley-entry-child-recipient-rechecked')},
)

DISABLED_PLAN = replace(
    PLAN, worker_mode='native_command_allowed_disabled',
    screen_tags={stage: tag for stage, tag in SCREENS.items()
                 if stage not in ('allowance-configured', 'saved-settings')},
    phases={stage: phase for stage, phase in PLAN.phases.items()
            if stage not in ('allowance-configured', 'saved-settings')},
    child_bindings={stage: child for stage, child in PLAN.child_bindings.items()
                    if stage != 'allowance-configured'},
    settings_checks={
        'parent-selected': SettingsObservation('existing-fixture-child', False, ('0 minutes',))},
    balance_checks={},
)


def execute(recorder, context):
    record_installed_journey(recorder, context, PLAN, timeout=1800,
                             actions=fixture_actions(include_refusal=False),
                             journey_type=AppPolicyJourney)


def execute_disabled(recorder, context):
    record_installed_journey(recorder, context, DISABLED_PLAN, timeout=1800,
                             actions=fixture_actions(include_refusal=False),
                             journey_type=AppPolicyJourney)


E2E_CASES = {'native-command-allowed-enabled': execute,
             'native-command-allowed-disabled': execute_disabled}
