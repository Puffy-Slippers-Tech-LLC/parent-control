"""FIX03 no-approver qualification; complete case 55 remains separate."""

from account_fixture import NoApproverFixture
from installed_journey import InstalledJourney, JourneyPlan
from journey_blocks import station_entry
import watch_activity


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


def fixture_actions(context):
    fixture = NoApproverFixture(context)

    def prepare(journey, guard):
        with watch_activity.operation('Temporarily locking the observed approver accounts'):
            return fixture.prepare(journey, guard)

    return {'prepare-no-approver': prepare}


class KioskNoApproverJourney(InstalledJourney):
    def __init__(self, context, progress):
        super().__init__(context, progress, PLAN, actions=fixture_actions(context))
