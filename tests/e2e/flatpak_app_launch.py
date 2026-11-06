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


def launch_plan(route='command', *, limits=True, rule='allowed'):
    access = {'allowed': 'allowed', 'hard': 'permanent', 'soft': 'conditional'}[rule]
    policy = 'allowed' if rule == 'allowed' else rule + '-blocked'
    blocked = rule != 'allowed'
    setup = {
        **app_policy_entry(child='existing', initial_rows=False,
                           allowance='time-explanation-setup-thirty-read' if limits else None),
        rule + '-save': 'ui:access-flatpak-' + access,
        rule + '-row': 'ui:access-flatpak-row',
    }
    denied = {
        **(prefixed_stages('jordan-denied', {
            stage: tag for stage, tag in native_usable_app('grid', kind='flatpak', role='A').items()
            if stage in ('desktop', 'search-ready', 'search-focused', 'search-entered')})
           if route == 'grid' else {}),
        **({'jordan-denied-app-grid': 'ui:flatpak-allowed-grid-hidden'} if route == 'grid' else {}),
        'jordan-denied-command': 'ui:flatpak-allowed-command-blocked',
    }
    jordan = {
        'parent-logout': 'system:parent-logout', **JORDAN_ENTRY,
        **(denied if blocked else
           prefixed_stages('jordan-use', native_usable_app(route, kind='flatpak', role='A'))),
    }
    riley = {
        'jordan-logout': 'system:standard-logout', **RILEY_ENTRY,
        **prefixed_stages('riley-use', native_usable_app(
            route, kind='flatpak', role='A', child='child')),
    }
    return JourneyPlan(
        prefix='flatpak-' + route + '-' + policy,
        worker_mode='flatpak_' + route + '_' + policy.replace('-', '_')
                    + ('' if limits else '_disabled'),
        screen_tags={**setup, **jordan, **riley},
        phases={'ready': 'setup', 'setup-detached': 'setup',
                **{stage: 'step-1' for stage in setup}, 'installed-greeter': 'start',
                **{stage: 'step-2' for stage in jordan},
                **{stage: 'step-3' for stage in riley}},
        advance_after={'installed-greeter': 'step-1', rule + '-row': 'step-2',
                       ('jordan-denied-command' if blocked else 'jordan-use-submitted'): 'step-3'},
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


PLAN = launch_plan()
GRID_PLAN = launch_plan('grid')
HARD_GRID_PLAN = launch_plan('grid', rule='hard')
SOFT_GRID_PLAN = launch_plan('grid', rule='soft')
DISABLED_PLAN = launch_plan(limits=False)
HARD_COMMAND_PLAN = launch_plan(rule='hard')
HARD_COMMAND_DISABLED_PLAN = launch_plan(limits=False, rule='hard')
SOFT_COMMAND_PLAN = launch_plan(rule='soft')
SOFT_COMMAND_DISABLED_PLAN = launch_plan(limits=False, rule='soft')


def execute(recorder, context, *, plan=PLAN):
    record_installed_journey(recorder, context, plan, timeout=1800,
                             actions=fixture_actions(include_refusal=False),
                             journey_type=AppPolicyJourney)


E2E_CASES = {'flatpak-command-allowed-enabled': execute,
             'flatpak-grid-allowed-enabled': partial(execute, plan=GRID_PLAN),
             'flatpak-grid-hard-blocked-enabled': partial(execute, plan=HARD_GRID_PLAN),
             'flatpak-grid-soft-blocked-enabled': partial(execute, plan=SOFT_GRID_PLAN),
             'flatpak-command-allowed-disabled': partial(execute, plan=DISABLED_PLAN),
             'flatpak-command-hard-blocked-enabled': partial(execute, plan=HARD_COMMAND_PLAN),
             'flatpak-command-hard-blocked-disabled': partial(execute, plan=HARD_COMMAND_DISABLED_PLAN),
             'flatpak-command-soft-blocked-enabled': partial(execute, plan=SOFT_COMMAND_PLAN),
             'flatpak-command-soft-blocked-disabled': partial(execute, plan=SOFT_COMMAND_DISABLED_PLAN)}
