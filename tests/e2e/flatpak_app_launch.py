"""Flatpak rules govern Jordan's access while Riley can use the same app."""
from functools import partial
from accessible_ui import FLATPAK_POLICY_APP
from installed_journey import JourneyPlan, record_installed_journey
from journey_blocks import app_policy_entry, desktop_entry, native_usable_app, prefixed_stages
from policy_edits import AppPolicyJourney
from flatpak_fixtures import fixture_actions
from ui_observations import SettingsObservation


JORDAN_ENTRY = prefixed_stages('jordan-entry', desktop_entry('other-child', source='gdm', entry='fresh'))
RILEY_ENTRY = prefixed_stages('riley-entry', desktop_entry('child', source='gdm', entry='fresh'))


def command_plan(*, limits=True, hard_blocked=False):
    rule = 'hard' if hard_blocked else 'allowed'
    access = 'permanent' if hard_blocked else 'allowed'
    setup = {
        **app_policy_entry(child='existing', initial_rows=False,
                           allowance='time-explanation-setup-thirty-read' if limits else None),
        rule + '-save': 'ui:access-flatpak-' + access,
        rule + '-row': 'ui:access-flatpak-row',
    }
    jordan = {
        'parent-logout': 'system:parent-logout', **JORDAN_ENTRY,
        **({'jordan-denied-command': 'ui:flatpak-allowed-command-blocked'} if hard_blocked else
           prefixed_stages('jordan-use', native_usable_app('command', kind='flatpak', role='A'))),
    }
    riley = {
        'jordan-logout': 'system:standard-logout', **RILEY_ENTRY,
        **prefixed_stages('riley-use', native_usable_app(
            'command', kind='flatpak', role='A', child='child')),
    }
    return JourneyPlan(
        prefix='flatpak-command-' + ('hard-blocked' if hard_blocked else 'allowed'),
        worker_mode='flatpak_command_' + ('hard_blocked' if hard_blocked else 'allowed')
                    + ('' if limits else '_disabled'),
        screen_tags={**setup, **jordan, **riley},
        phases={'ready': 'setup', 'setup-detached': 'setup',
                **{stage: 'step-1' for stage in setup}, 'installed-greeter': 'start',
                **{stage: 'step-2' for stage in jordan},
                **{stage: 'step-3' for stage in riley}},
        advance_after={'installed-greeter': 'step-1', rule + '-row': 'step-2',
                       ('jordan-denied-command' if hard_blocked else 'jordan-use-submitted'): 'step-3'},
        stage_actions={'desktop': 'native-verify'},
        child_bindings={**({'allowance-configured': 'existing'} if limits else {}),
                        rule + '-save': 'existing', rule + '-row': 'existing'},
        settings_checks={
            'parent-selected': SettingsObservation('existing-fixture-child', False, ('0 minutes',)),
            **({'saved-settings': SettingsObservation('existing-fixture-child', True, ('30 minutes',))}
               if limits else {})},
        balance_checks={'allowance-configured': 1800} if limits else {},
        access_checks={rule + '-row': (FLATPAK_POLICY_APP, access)},
        invocations=tuple(stage for stage in (*JORDAN_ENTRY, *RILEY_ENTRY)
                          if stage not in ('jordan-entry-entry-guard', 'riley-entry-entry-guard')),
        challenges={
            'jordan-entry': ('other-child', 'jordan-entry-standard-recipient-qualified',
                             'jordan-entry-standard-recipient-rechecked'),
            'riley-entry': ('child', 'riley-entry-child-recipient-qualified',
                            'riley-entry-child-recipient-rechecked')},
    )


PLAN = command_plan()
DISABLED_PLAN = command_plan(limits=False)
HARD_COMMAND_PLAN = command_plan(hard_blocked=True)


def execute(recorder, context, *, plan=PLAN):
    record_installed_journey(recorder, context, plan, timeout=1800,
                             actions=fixture_actions(include_refusal=False),
                             journey_type=AppPolicyJourney)


E2E_CASES = {'flatpak-command-allowed-enabled': execute,
             'flatpak-command-allowed-disabled': partial(execute, plan=DISABLED_PLAN),
             'flatpak-command-hard-blocked-enabled': partial(execute, plan=HARD_COMMAND_PLAN)}
