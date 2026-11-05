"""A parent's Allowed Snap rule leaves the app usable for both children."""
from dataclasses import replace

from accessible_ui import SNAP_POLICY_APP
from app_launch import PLAN as NATIVE_PLAN, SETUP, POLICY, JORDAN_ENTRY, RILEY_ENTRY
from installed_journey import record_installed_journey
from journey_blocks import native_usable_app, prefixed_stages
from policy_edits import AppPolicyJourney
from snap_fixtures import fixture_actions


SETUP = {stage: tag for stage, tag in SETUP.items() if stage not in POLICY}
SETUP.update({'allowed-save': 'ui:access-snap-allowed',
              'allowed-row': 'ui:access-snap-row'})
JORDAN = {
    'parent-logout': 'system:parent-logout', **JORDAN_ENTRY,
    **prefixed_stages('jordan-use', native_usable_app('command', kind='snap', role='A')),
}
RILEY = {
    'jordan-logout': 'system:standard-logout', **RILEY_ENTRY,
    **prefixed_stages('riley-use', native_usable_app(
        'command', kind='snap', role='A', child='child')),
}
PLAN = replace(
    NATIVE_PLAN, prefix='snap-command-allowed', worker_mode='snap_command_allowed',
    screen_tags={**SETUP, **JORDAN, **RILEY},
    phases={'ready': 'setup', 'setup-detached': 'setup',
            **{stage: 'step-1' for stage in SETUP}, 'installed-greeter': 'start',
            **{stage: 'step-2' for stage in JORDAN},
            **{stage: 'step-3' for stage in RILEY}},
    advance_after={'installed-greeter': 'step-1', 'allowed-row': 'step-2',
                   'jordan-use-submitted': 'step-3'},
    child_bindings={'allowance-configured': 'existing',
                    'allowed-save': 'existing', 'allowed-row': 'existing'},
    match_checks={}, access_checks={'allowed-row': (SNAP_POLICY_APP, 'allowed')},
)


def execute(recorder, context):
    record_installed_journey(recorder, context, PLAN, timeout=1800,
                             actions=fixture_actions(include_refusal=False),
                             journey_type=AppPolicyJourney)


E2E_CASES = {'snap-command-allowed-enabled': execute}
