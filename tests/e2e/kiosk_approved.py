"""Case 49: Cancel, surface close and approved exit return to usable GDM."""

from installed_journey import JourneyPlan, record_installed_journey
from journey_blocks import fresh_desktop, parent_management, prefixed_stages
from request_composition import KioskRequestJourney
from request_flow import prepared_request, daily_station_entry
from kiosk_approved_flow import approved_request


CHILD_SCREENS = {'fresh-' + stage: operation
                 for stage, operation in fresh_desktop('child').items()}
EXIT_SCREENS = {}
for prefix, entry, initial, exit_stages in (
        ('cancel-exit', 'open', 'default', {'cancel-action': 'ui:kiosk-request-cancel',
                                          'cancel-returned': 'ui:gdm-station-returned'}),
        ('close-exit', 'new', 'selected', {'escape-ready': 'ui:kiosk-request-escape-ready',
                                         'escape-returned': 'ui:gdm-station-returned'})):
    EXIT_SCREENS.update(prefixed_stages(prefix, {
        **prepared_request(prefix='open', entry=entry, initial=initial,
                           child='fixture-child', approver='fixture-parent',
                           duration_seconds=75, allow_soft=True),
        **exit_stages,
    }))
SCREENS = {
    **fresh_desktop('parent'), **parent_management(),
    **daily_station_entry(),
    **EXIT_SCREENS,
    **prepared_request(prefix='open', entry='new', initial='selected',
                       child='fixture-child', approver='fixture-parent',
                       duration_seconds=75, allow_soft=True),
    **approved_request(child='fixture-child', approver='fixture-parent',
                       duration_seconds=75, allow_soft=True, exit='immediate'),
    **CHILD_SCREENS,
    'countdown': 'ui:child-countdown-present',
}
PLAN = JourneyPlan(
    prefix='kiosk-approval', worker_mode='kiosk_approved', screen_tags=SCREENS,
    phases={'ready': 'setup', 'setup-detached': 'setup',
            **{stage: 'step-1' for stage in SCREENS}, 'installed-greeter': 'start',
            **{stage: 'step-4' for stage in SCREENS
               if stage.startswith(('open-', 'cancel-station-', 'approval-'))
               or stage in ('new-returned', 'countdown') or stage in CHILD_SCREENS},
            **{stage: 'step-2' if stage.startswith('cancel-exit-') else 'step-3'
               for stage in EXIT_SCREENS}},
    advance_after={'station-branch': 'step-2',
                   'cancel-exit-cancel-returned': 'step-3',
                   'close-exit-escape-returned': 'step-4'},
    balance_checks={'time-explanation-read': 900},
    countdown_checks={'countdown': ('open-estimate', 975, 1, 180)},
    invocations=tuple(CHILD_SCREENS),
    challenges={'child-login': ('child', 'fresh-child-recipient-qualified',
                                'fresh-child-recipient-rechecked')},
    assertions_after={'cancel-exit-cancel-returned': 'cancel-result',
                      'close-exit-escape-returned': 'close-result',
                      'countdown': 'visible-result'},
)


def execute(recorder, context):
    record_installed_journey(recorder, context, PLAN, timeout=1800,
                             journey_type=KioskRequestJourney)


E2E_CASES = {'kiosk-approved': execute}
