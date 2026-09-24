"""FIX03 qualification and independent case 54 no-child station journey."""

from account_fixture import EmptyAccountFixture
from installed_journey import InstalledJourney, JourneyPlan, record_installed_journey
from journey_blocks import station_entry
import watch_activity


PLAN = JourneyPlan(
    prefix='kiosk-no-child', worker_mode='kiosk_no_child',
    screen_tags={
        'wrong-entry': 'ui:gdm-no-child-refused',
        **station_entry(),
        'empty-form': 'ui:kiosk-no-child-form',
        'empty-rechecked': 'ui:kiosk-no-child-form',
    },
    phases={
        'ready': 'setup', 'setup-detached': 'setup', 'wrong-entry': 'start',
        'station-list': 'step-1', 'station-focused': 'step-1',
        'station-branch': 'step-2', 'empty-form': 'step-2',
        'empty-rechecked': 'step-2',
    },
    advance_after={'station-focused': 'step-2'},
    stage_actions={'setup-detached': 'prepare-empty'},
)


CASE_PLAN = JourneyPlan(
    prefix='no-child', worker_mode='no_child',
    screen_tags={
        **station_entry(),
        'empty-form': 'ui:kiosk-no-child-form',
        'empty-rechecked': 'ui:kiosk-no-child-form',
        'cancel-action': 'ui:kiosk-request-cancel',
        'cancel-returned': 'ui:gdm-station-returned',
    },
    phases={
        'ready': 'setup', 'setup-detached': 'setup', 'station-list': 'start',
        'station-focused': 'step-1', 'station-branch': 'step-1',
        'empty-form': 'step-2', 'empty-rechecked': 'step-3',
        'cancel-action': 'step-3', 'cancel-returned': 'step-3',
    },
    advance_after={'station-list': 'step-1', 'station-branch': 'step-2',
                   'empty-form': 'step-3'},
    stage_actions={'setup-detached': 'prepare-empty'},
)


def fixture_actions(context):
    fixture = EmptyAccountFixture(context)

    def prepare(journey, guard):
        with watch_activity.operation('Preparing the fixed no-child station profile'):
            return fixture.prepare(journey, guard)

    return {'prepare-empty': prepare}


class KioskNoChildJourney(InstalledJourney):
    def __init__(self, context, progress):
        super().__init__(context, progress, PLAN, actions=fixture_actions(context))


def execute(recorder, context):
    record_installed_journey(recorder, context, CASE_PLAN, timeout=1800,
                             actions=fixture_actions(context))


E2E_CASES = {'no-child': execute}
