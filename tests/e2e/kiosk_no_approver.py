"""FIX03 qualification and independent case 55 no-parent station journey."""

from account_fixture import station_fixture_actions
from installed_journey import InstalledJourney, JourneyPlan, record_installed_journey
from journey_blocks import station_entry


PLAN = JourneyPlan(
    prefix='kiosk-no-approver', worker_mode='kiosk_no_approver',
    screen_tags={
        'wrong-entry': 'ui:gdm-no-approver-refused',
        **station_entry(),
        'baseline-approvers': 'ui:kiosk-approver-baseline',
        'cancel-action': 'ui:kiosk-request-cancel',
        'cancel-returned': 'ui:gdm-station-returned',
        **station_entry('cancel-'),
        'empty-form': 'ui:kiosk-no-approver-form',
        'empty-rechecked': 'ui:kiosk-no-approver-form',
    },
    phases={
        'ready': 'setup', 'setup-detached': 'setup', 'wrong-entry': 'start',
        'station-list': 'step-1', 'station-focused': 'step-1',
        'station-branch': 'step-1', 'baseline-approvers': 'step-1',
        'cancel-action': 'step-1', 'cancel-returned': 'step-1',
        'cancel-station-list': 'step-1', 'cancel-station-focused': 'step-1',
        'cancel-station-branch': 'step-2', 'empty-form': 'step-2',
        'empty-rechecked': 'step-2',
    },
    advance_after={'cancel-station-focused': 'step-2'},
    stage_actions={'baseline-approvers': 'prepare-no-approver'},
)


CASE_PLAN = JourneyPlan(
    prefix='no-parent', worker_mode='no_parent',
    screen_tags={
        **station_entry(),
        'baseline-approvers': 'ui:kiosk-approver-baseline',
        'cancel-action': 'ui:kiosk-request-cancel',
        'cancel-returned': 'ui:gdm-station-returned',
        **station_entry('cancel-'),
        'empty-form': 'ui:kiosk-no-approver-form',
        'empty-rechecked': 'ui:kiosk-no-approver-form',
    },
    phases={
        'ready': 'setup', 'setup-detached': 'setup', 'station-list': 'start',
        'station-focused': 'step-1', 'station-branch': 'step-1',
        'baseline-approvers': 'step-1', 'cancel-action': 'step-1',
        'cancel-returned': 'step-1', 'cancel-station-list': 'step-1',
        'cancel-station-focused': 'step-1', 'cancel-station-branch': 'step-1',
        'empty-form': 'step-2', 'empty-rechecked': 'step-3',
    },
    advance_after={'station-list': 'step-1', 'cancel-station-branch': 'step-2',
                   'empty-form': 'step-3'},
    stage_actions={'baseline-approvers': 'prepare-no-approver'},
)


class KioskNoApproverJourney(InstalledJourney):
    def __init__(self, context, progress):
        super().__init__(context, progress, PLAN,
                         actions=station_fixture_actions(context, 'no-approver'))


def execute(recorder, context):
    record_installed_journey(recorder, context, CASE_PLAN, timeout=1800,
                             actions=station_fixture_actions(context, 'no-approver'))


E2E_CASES = {'no-parent': execute}
