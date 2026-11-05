"""Native routes: saved policy, actual access and independent child use."""
from dataclasses import replace
from functools import partial
from installed_journey import JourneyPlan, record_installed_journey
from journey_blocks import (app_policy_entry, desktop_entry,
                            native_blocked_app, native_usable_app, prefixed_stages)
from native_fixtures import fixture_actions
from policy_edits import policy_edit, AppPolicyJourney
from accessible_ui import MATCH_APP
from match_rules import MATCH_RULES
from ui_observations import SettingsObservation


POLICY = policy_edit(MATCH_APP, 'match-precise', 'allowed', 'allowed')
SETUP = {
    **app_policy_entry(child='existing', allowance='time-explanation-setup-thirty-read',
                       initial_rows=False),
    **POLICY,
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

GRID_JORDAN = {
    'parent-logout': 'system:parent-logout', **JORDAN_ENTRY,
    **prefixed_stages('jordan-use', native_usable_app('grid', child='other-child')),
    'jordan-use-close': 'ui:native-close', 'jordan-use-closed': 'ui:native-closed',
    **prefixed_stages('jordan-command', native_usable_app('command', child='other-child')),
}
GRID_RILEY = {
    'jordan-logout': 'system:standard-logout', **RILEY_ENTRY,
    **prefixed_stages('riley-use', native_usable_app('grid', child='child')),
    'riley-use-close': 'ui:overlay-native-close',
    'riley-use-closed': 'ui:overlay-native-closed',
    **prefixed_stages('riley-command', native_usable_app('command', child='child')),
}
GRID_PLAN = replace(
    PLAN, prefix='native-grid-allowed', worker_mode='native_grid_allowed',
    screen_tags={**SETUP, **GRID_JORDAN, **GRID_RILEY},
    phases={**{stage: phase for stage, phase in PLAN.phases.items()
               if stage not in ('jordan-use-command', 'riley-use-command')},
            **{stage: 'step-2' for stage in GRID_JORDAN},
            **{stage: 'step-3' for stage in GRID_RILEY}},
    advance_after={'installed-greeter': 'step-1', 'allowed-final-match': 'step-2',
                   'jordan-command-submitted': 'step-3'},
)

def blocked_plan(rule, access, *, route='grid', control='enabled'):
    base = PLAN if control == 'enabled' else DISABLED_PLAN
    policy = policy_edit(MATCH_APP, 'match-precise', access, rule)
    setup = {stage: tag for stage, tag in base.screen_tags.items()
             if stage in SETUP and stage not in POLICY}
    setup.update(policy)
    jordan = {
        'parent-logout': 'system:parent-logout', **JORDAN_ENTRY,
        **prefixed_stages('jordan-denied', native_blocked_app('A', route=route)),
    }
    riley = {
        'jordan-logout': 'system:standard-logout', **RILEY_ENTRY,
        **prefixed_stages('riley-use', native_usable_app(route, child='child')),
    }
    return replace(
        base, prefix=f'native-{route}-{rule}-blocked',
        worker_mode=f'native_{route}_{rule}_blocked' + ('_disabled' if control == 'disabled' else ''),
        screen_tags={**setup, **jordan, **riley},
        phases={'ready': 'setup', 'setup-detached': 'setup',
                **{stage: 'step-1' for stage in setup}, 'installed-greeter': 'start',
                **{stage: 'step-2' for stage in jordan},
                **{stage: 'step-3' for stage in riley}},
        advance_after={'installed-greeter': 'step-1', f'{rule}-final-match': 'step-2',
                       'jordan-denied-' + ('denied' if route == 'grid' else 'command'): 'step-3'},
        child_bindings={**({'allowance-configured': 'existing'} if control == 'enabled' else {}), **{
            stage: 'existing' for stage in policy if stage != f'{rule}-found'}},
        match_checks={f'{rule}-{suffix}': MATCH_RULES[0] for suffix in
                      ('open', 'old', 'match', 'final-match')},
        access_checks={f'{rule}-access': access},
        # The family's combined visible-result requires Jordan's independent
        # denial and Riley's submitted draft in the ordered observations.
    )


HARD_GRID_PLAN = blocked_plan('hard', 'permanent')
SOFT_GRID_PLAN = blocked_plan('soft', 'conditional')
HARD_COMMAND_PLAN = blocked_plan('hard', 'permanent', route='command')
HARD_COMMAND_DISABLED_PLAN = blocked_plan('hard', 'permanent', route='command', control='disabled')
SOFT_COMMAND_PLAN = blocked_plan('soft', 'conditional', route='command')
SOFT_COMMAND_DISABLED_PLAN = blocked_plan('soft', 'conditional', route='command', control='disabled')


def execute(recorder, context, *, plan=PLAN):
    record_installed_journey(recorder, context, plan, timeout=1800,
                             actions=fixture_actions(include_refusal=False),
                             journey_type=AppPolicyJourney)


def execute_disabled(recorder, context):
    execute(recorder, context, plan=DISABLED_PLAN)


def execute_grid(recorder, context, *, plan=GRID_PLAN, case_id='native-grid-allowed-enabled'):
    from e2e_fixture_preparation import ACTIVITY_SUBSETS
    # Reuse the qualified union: setup verifies Riley's catalogue and shared
    # runtime; the stage action independently verifies Jordan's catalogue.
    context.fixture_subsets = ACTIVITY_SUBSETS
    context.fixture_caller = 'E2E-019/' + case_id
    execute(recorder, context, plan=plan)


E2E_CASES = {'native-command-allowed-enabled': execute,
             'native-command-allowed-disabled': execute_disabled,
             'native-grid-allowed-enabled': execute_grid,
             'native-grid-hard-blocked-enabled': partial(execute_grid,
                 plan=HARD_GRID_PLAN, case_id='native-grid-hard-blocked-enabled'),
             'native-grid-soft-blocked-enabled': partial(execute_grid,
                 plan=SOFT_GRID_PLAN, case_id='native-grid-soft-blocked-enabled'),
             'native-command-hard-blocked-enabled': partial(execute, plan=HARD_COMMAND_PLAN),
             'native-command-hard-blocked-disabled': partial(execute, plan=HARD_COMMAND_DISABLED_PLAN),
             'native-command-soft-blocked-enabled': partial(execute, plan=SOFT_COMMAND_PLAN),
             'native-command-soft-blocked-disabled': partial(execute, plan=SOFT_COMMAND_DISABLED_PLAN)}
