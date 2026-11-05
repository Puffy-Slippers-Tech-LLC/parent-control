"""A parent's Allowed Snap rule leaves the app usable for both children."""
from dataclasses import replace
from functools import partial
from accessible_ui import SNAP_POLICY_APP
from installed_journey import JourneyPlan, record_installed_journey
from journey_blocks import app_policy_entry, desktop_entry, native_usable_app, prefixed_stages
from policy_edits import AppPolicyJourney
from snap_fixtures import fixture_actions
from ui_observations import SettingsObservation


SETUP = {
    **app_policy_entry(child='existing', allowance='time-explanation-setup-thirty-read',
                       initial_rows=False),
    'allowed-save': 'ui:access-snap-allowed', 'allowed-row': 'ui:access-snap-row',
}
JORDAN_ENTRY = prefixed_stages('jordan-entry', desktop_entry('other-child', source='gdm', entry='fresh'))
RILEY_ENTRY = prefixed_stages('riley-entry', desktop_entry('child', source='gdm', entry='fresh'))
def allowed_plan(route):
    jordan = {
        'parent-logout': 'system:parent-logout', **JORDAN_ENTRY,
        **prefixed_stages('jordan-use', native_usable_app(route, kind='snap', role='A')),
    }
    riley = {
        'jordan-logout': 'system:standard-logout', **RILEY_ENTRY,
        **prefixed_stages('riley-use', native_usable_app(
            route, kind='snap', role='A', child='child')),
    }
    return JourneyPlan(
        prefix=f'snap-{route}-allowed', worker_mode=f'snap_{route}_allowed',
        screen_tags={**SETUP, **jordan, **riley},
        phases={'ready': 'setup', 'setup-detached': 'setup',
                **{stage: 'step-1' for stage in SETUP}, 'installed-greeter': 'start',
                **{stage: 'step-2' for stage in jordan},
                **{stage: 'step-3' for stage in riley}},
        advance_after={'installed-greeter': 'step-1', 'allowed-row': 'step-2',
                       'jordan-use-submitted': 'step-3'},
        stage_actions={'desktop': 'native-verify'},
        child_bindings={'allowance-configured': 'existing',
                        'allowed-save': 'existing', 'allowed-row': 'existing'},
        settings_checks={
            'parent-selected': SettingsObservation('existing-fixture-child', False, ('0 minutes',)),
            'saved-settings': SettingsObservation('existing-fixture-child', True, ('30 minutes',))},
        balance_checks={'allowance-configured': 1800},
        access_checks={'allowed-row': (SNAP_POLICY_APP, 'allowed')},
        invocations=tuple(stage for stage in (*JORDAN_ENTRY, *RILEY_ENTRY)
                          if stage not in ('jordan-entry-entry-guard', 'riley-entry-entry-guard')),
        challenges={
            'jordan-entry': ('other-child', 'jordan-entry-standard-recipient-qualified',
                             'jordan-entry-standard-recipient-rechecked'),
            'riley-entry': ('child', 'riley-entry-child-recipient-qualified',
                            'riley-entry-child-recipient-rechecked')},
    )


PLAN = allowed_plan('command')
GRID_PLAN = allowed_plan('grid')

DISABLED_PLAN = replace(
    PLAN, worker_mode='snap_command_allowed_disabled',
    screen_tags={stage: tag for stage, tag in PLAN.screen_tags.items()
                 if stage not in ('allowance-configured', 'saved-settings')},
    phases={stage: phase for stage, phase in PLAN.phases.items()
            if stage not in ('allowance-configured', 'saved-settings')},
    child_bindings={stage: child for stage, child in PLAN.child_bindings.items()
                    if stage != 'allowance-configured'},
    settings_checks={
        'parent-selected': SettingsObservation('existing-fixture-child', False, ('0 minutes',))},
    balance_checks={},
)


def execute(recorder, context, *, plan=PLAN):
    record_installed_journey(recorder, context, plan, timeout=1800,
                             actions=fixture_actions(include_refusal=False),
                             journey_type=AppPolicyJourney)


E2E_CASES = {'snap-command-allowed-enabled': execute,
             'snap-command-allowed-disabled': partial(execute, plan=DISABLED_PLAN),
             'snap-grid-allowed-enabled': partial(execute, plan=GRID_PLAN)}
