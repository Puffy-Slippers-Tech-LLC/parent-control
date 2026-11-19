"""An Allowed Snap rule leaves the app usable for both children."""
from functools import partial

from accessible_ui import SNAP_POLICY_APP
from app_launch import packaged_launch_plan
from installed_journey import record_installed_journey
from policy_edits import AppPolicyJourney
from snap_fixtures import fixture_actions


def execute(recorder, context, *, plan):
    record_installed_journey(recorder, context, plan, timeout=1800,
                             actions=fixture_actions(include_refusal=False),
                             journey_type=AppPolicyJourney)


GRID_PLAN = packaged_launch_plan('snap', SNAP_POLICY_APP, 'grid')


E2E_CASES = {
    'snap-grid-allowed-enabled': partial(
        execute, plan=GRID_PLAN),
    'snap-command-allowed-disabled': partial(
        execute, plan=packaged_launch_plan('snap', SNAP_POLICY_APP, limits=False)),
}
