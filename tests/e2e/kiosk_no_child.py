"""FIX03 no-child station qualification; no complete scenario credit."""

from account_fixture import EmptyAccountFixture
from installed_journey import InstalledJourney, JourneyPlan
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


class KioskNoChildJourney(InstalledJourney):
    def __init__(self, context, progress):
        fixture = EmptyAccountFixture(context)

        def prepare(journey, guard):
            with watch_activity.operation('Preparing the fixed no-child station profile'):
                return fixture.prepare(journey, guard)

        super().__init__(context, progress, PLAN, actions={'prepare-empty': prepare})
