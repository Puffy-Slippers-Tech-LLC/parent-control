"""ABOUT01 kiosk qualification; the complete information case remains separate."""
from installed_journey import JourneyPlan
from journey_blocks import fresh_desktop, parent_management, station_entry
from kiosk_valid_duration import KioskValidDurationJourney
from private_artifacts import require
from request_flow import prepared_request


SCREENS = {
    **fresh_desktop('parent'), **parent_management(),
    'wrong-entry': 'ui:parent-kiosk-about-refused',
    'limit-enabled': 'ui:parent-toggle-enabled',
    'save-enabled': 'ui:parent-save-enabled',
    'allowance-15-select': 'ui:allowance-15-select',
    'allowance-15-read': 'ui:allowance-15-read',
    'time-explanation-read': 'ui:time-explanation-read',
    'switch-user': 'system:parent-switch-user',
    'gdm-switched': 'ui:gdm-returned',
    **station_entry(),
    **prepared_request(prefix='open', entry='open', initial='default',
                       child='fixture-child', approver='fixture-parent',
                       duration_seconds=75, allow_soft=True),
    'about-open': 'ui:kiosk-about-open',
    'about-read': 'ui:kiosk-about-read',
    'about-close-ready': 'ui:kiosk-about-close-ready',
    'about-closed': 'ui:kiosk-about-closed',
    'form-returned': 'ui:kiosk-valid-fraction-soft-read',
    'cancel': 'ui:kiosk-request-cancel',
    'returned': 'ui:gdm-station-returned',
}
PLAN = JourneyPlan(
    prefix='restricted-station-about', worker_mode='restricted_station_about',
    screen_tags=SCREENS,
    phases={'ready': 'setup', 'setup-detached': 'setup',
            **{stage: 'step-1' for stage in SCREENS}, 'installed-greeter': 'start',
            **{stage: 'step-2' for stage in list(SCREENS)[list(SCREENS).index('switch-user'):]}},
    advance_after={'time-explanation-read': 'step-2'},
)


class RestrictedStationAboutJourney(KioskValidDurationJourney):
    def __init__(self, context, progress):
        super().__init__(context, progress, plan=PLAN)
        self.before_about = None

    def check_settings(self, stage, observed):
        super().check_settings(stage, observed)
        if stage == 'open-estimate':
            require(self.before_about is None, 'kiosk-about:capture-replay')
            self.before_about = dict(observed['ui']['valid_choice']['request'])
        elif stage == 'form-returned':
            require(self.before_about is not None and self.before_about ==
                    observed.get('ui', {}).get('valid_choice', {}).get('request'),
                    'kiosk-about:changed-form')
            observed['comparison']['unchanged_form'] = True
