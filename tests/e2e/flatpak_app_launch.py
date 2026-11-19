"""Flatpak rules govern both children's access to the same installed app."""
from functools import partial

from accessible_ui import FLATPAK_POLICY_APP
from app_launch import packaged_launch_plan
from flatpak_fixtures import fixture_actions
from installed_journey import record_installed_journey
from policy_edits import AppPolicyJourney


def execute(recorder, context, *, plan):
    record_installed_journey(recorder, context, plan, timeout=1800,
                             actions=fixture_actions(include_refusal=False),
                             journey_type=AppPolicyJourney)


E2E_CASES = {
    f'flatpak-{route}-{policy}-{control}': partial(
        execute, plan=packaged_launch_plan('flatpak', FLATPAK_POLICY_APP, route,
                                          limits=control == 'enabled', rule=rule))
    for route, policy, control, rule in (
        ('grid', 'allowed', 'enabled', 'allowed'),
        ('grid', 'hard-blocked', 'enabled', 'hard'),
        ('grid', 'soft-blocked', 'enabled', 'soft'),
        ('command', 'allowed', 'disabled', 'allowed'),
        ('command', 'hard-blocked', 'disabled', 'hard'),
        ('command', 'soft-blocked', 'disabled', 'soft'),
    )
}
