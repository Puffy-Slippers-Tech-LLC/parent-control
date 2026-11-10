"""Saved kiosk preset edits and exact Hours choices; no complete-case credit."""

from installed_journey import JourneyPlan
from journey_blocks import fresh_desktop, parent_management, station_entry
from request_flow import prepared_request
from request_composition import KioskRequestJourney
from private_artifacts import require


SCREENS = {
    **fresh_desktop('parent'), **parent_management(),
    'allowance-configured': 'ui:time-explanation-setup-zero-read',
    'switch-user': 'system:parent-switch-user', 'gdm-switched': 'ui:gdm-returned',
    **station_entry(),
    **prepared_request(prefix='open', entry='open', initial='default',
                       child='fixture-child', approver='fixture-parent',
                       duration_seconds=75, allow_soft=True, compact=True),
    'presets-shipped': 'ui:kiosk-presets-shipped-read',
    'preset-added': 'ui:kiosk-presets-add-ten',
    'preset-reopened': 'ui:kiosk-presets-added-read',
    'preset-deleted': 'ui:kiosk-presets-delete-ten',
    'presets-restored': 'ui:kiosk-presets-restored-read',
    'hours-selected': 'ui:kiosk-custom-hours-select',
    'hours-read': 'ui:kiosk-custom-hours-read',
    'minutes-restored': 'ui:kiosk-custom-minutes-restore',
    'minutes-read': 'ui:kiosk-valid-fraction-soft-read',
    'cancel': 'ui:kiosk-request-cancel', 'returned': 'ui:gdm-station-returned',
}
PLAN = JourneyPlan(
    prefix='request-preset-controls', worker_mode='request_preset_controls', screen_tags=SCREENS,
    phases={'ready': 'setup', 'setup-detached': 'setup',
            **{stage: 'step-1' for stage in SCREENS}, 'installed-greeter': 'start',
            **{stage: 'step-2' for stage in tuple(SCREENS)[tuple(SCREENS).index('switch-user'):]}},
    advance_after={'allowance-configured': 'step-2'},
    balance_checks={'allowance-configured': 0},
)


class RequestPresetControlsJourney(KioskRequestJourney):
    def __init__(self, context, progress):
        super().__init__(context, progress, PLAN)
        self.shipped_presets = None

    def check_settings(self, stage, observed):
        super().check_settings(stage, observed)
        if stage == 'presets-shipped':
            self.shipped_presets = observed['ui']['presets']['values'][:]
            require(self.shipped_presets == [300, 900, 1800, 3600, 7200, 14400],
                    'request-presets:shipped-list')
        if stage in ('preset-reopened', 'presets-restored'):
            require(self.shipped_presets is not None, 'request-presets:missing-original')
            wanted = (sorted([*self.shipped_presets, 600]) if stage == 'preset-reopened'
                      else self.shipped_presets)
            require(observed['ui']['presets']['values'] == wanted,
                    'request-presets:saved-list')
            observed.setdefault('comparison', {})['saved_presets_and_request_choices'] = True
