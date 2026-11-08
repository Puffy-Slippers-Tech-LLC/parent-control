"""312c: Jordan's own overlay and Riley's station deletion persistence."""
from copy import deepcopy

from installed_journey import InstalledJourney, JourneyPlan
from journey_blocks import (fresh_desktop, parent_management, overlay_entry,
    station_entry, custom_child_selection, prefixed_stages)
from kiosk_reminders import KioskReminderJourney
from overlay_reminders import DEFAULTS
from private_artifacts import require


SCREENS = {
    **fresh_desktop('parent'), **parent_management(),
    'allowance-configured': 'ui:time-explanation-setup-thirty-read',
    'riley-policy-before': 'ui:overlay-language-policy',
    **custom_child_selection('jordan', 'existing'),
    'jordan-allowance-configured': 'ui:time-explanation-setup-thirty-read',
    'jordan-policy-before': 'ui:kiosk-language-policy',
    'parent-logout-ready': 'ui:desktop', 'parent-logout': 'system:parent-logout',
    'parent-logged-out': 'ui:gdm-returned',
    **station_entry('initial-'),
    'jordan-language': 'ui:kiosk-language-initial',
    'jordan-language-save': 'ui:kiosk-language-save',
    'jordan-jamie': 'ui:kiosk-language-jordan-jamie',
    'jordan-before': 'ui:kiosk-language-form-en',
    'jordan-reminders-before': 'ui:binding-reminder-jordan-open',
    'jordan-close': 'ui:binding-reminder-jordan-cancel',
    'defaults-riley-select': 'ui:binding-reminder-riley-select',
    'riley-defaults-before': 'ui:binding-reminder-riley-open',
    'riley-defaults-close': 'ui:binding-reminder-riley-cancel',
    'defaults-jordan-select': 'ui:binding-reminder-jordan-select',
    'defaults-station-exit': 'ui:kiosk-request-cancel',
    'defaults-station-returned': 'ui:gdm-station-returned',
    **prefixed_stages('jordan', fresh_desktop('other-child')),
    'jordan-overlay-launch': 'ui:transfer-overlay-jordan-launch',
    'jordan-overlay-ready': 'ui:request-overlay-jordan-ready',
    'jordan-overlay-read': 'ui:binding-reminder-jordan-overlay-open',
    'jordan-overlay-close': 'ui:binding-reminder-jordan-overlay-cancel',
    'jordan-overlay-exit': 'ui:transfer-overlay-jordan-cancel',
    'jordan-overlay-returned': 'ui:transfer-overlay-jordan-returned',
    'jordan-logout': 'system:standard-logout', 'jordan-logged-out': 'ui:gdm-returned',
    **prefixed_stages('fresh', fresh_desktop('child')),
    **overlay_entry('direct', 'command', form_operation='overlay-language-form-en'),
    'overlay-defaults': 'ui:binding-reminder-overlay-open',
    'overlay-created': 'ui:binding-reminder-overlay-create',
    'overlay-saved': 'ui:binding-reminder-overlay-save',
    'overlay-saved-form': 'ui:overlay-language-form-en',
    'overlay-exit': 'ui:overlay-qualification-cancel', 'overlay-returned': 'ui:overlay-desktop',
    'child-logout': 'system:child-logout', 'child-logged-out': 'ui:gdm-returned',
    **station_entry('renewed-'),
    'riley-select': 'ui:binding-reminder-riley-select',
    'riley-saved-read': 'ui:binding-reminder-riley-open',
    'riley-delete-cancel-draft': 'ui:binding-reminder-riley-delete',
    'riley-delete-cancel': 'ui:binding-reminder-riley-cancel',
    'riley-cancel-read': 'ui:binding-reminder-riley-open',
    'riley-delete-save-draft': 'ui:binding-reminder-riley-delete',
    'riley-delete-save': 'ui:binding-reminder-riley-save',
    'riley-deleted-read': 'ui:binding-reminder-riley-open',
    'riley-close': 'ui:binding-reminder-riley-cancel',
    'riley-saved-form': 'ui:kiosk-riley-language-form-en',
    'jordan-select': 'ui:binding-reminder-jordan-select',
    'jordan-reminders-after': 'ui:binding-reminder-jordan-open',
    'jordan-after-close': 'ui:binding-reminder-jordan-cancel',
    'jordan-after': 'ui:kiosk-language-form-en',
    'station-exit': 'ui:kiosk-request-cancel', 'station-returned': 'ui:gdm-station-returned',
    **prefixed_stages('return', fresh_desktop('parent')),
    **prefixed_stages('return', parent_management()),
    'riley-policy-after': 'ui:overlay-language-policy',
    **custom_child_selection('jordan-final', 'existing'),
    'jordan-policy-after': 'ui:kiosk-language-policy',
}
LOGIN_STAGES = set(fresh_desktop('parent')) | {
    prefix + '-' + stage
    for prefix, account in (('jordan', 'other-child'), ('fresh', 'child'), ('return', 'parent'))
    for stage in fresh_desktop(account)}
PLAN = JourneyPlan(prefix='reminder-child-station', worker_mode='reminder_child_station_binding',
    screen_tags=SCREENS,
    phases={'ready': 'setup', 'setup-detached': 'setup',
            **{stage: 'step-1' for stage in SCREENS}, 'installed-greeter': 'start'},
    invocations=tuple(stage for stage in SCREENS if stage in LOGIN_STAGES
                      or stage.startswith('direct-')),
    challenges={
        'parent-login': ('parent', 'recipient-qualified', 'recipient-rechecked'),
        'jordan-login': ('other-child', 'jordan-standard-recipient-qualified',
                         'jordan-standard-recipient-rechecked'),
        'child-login': ('child', 'fresh-child-recipient-qualified', 'fresh-child-recipient-rechecked'),
        'return-parent': ('parent', 'return-recipient-qualified', 'return-recipient-rechecked')},
    child_bindings={'jordan-allowance-configured': 'existing'},
    assertions_after={stage: stage + '-verified' for stage, tag in SCREENS.items()
        if tag.startswith('ui:binding-reminder-') or stage.endswith(('-before', '-after', '-form'))})


class ReminderChildStationJourney(KioskReminderJourney):
    jordan_allowance = '30 minutes'

    def __init__(self, context, progress):
        super().__init__(context, progress, PLAN)
        self.station_riley_defaults = None

    def check_settings(self, stage, observed):
        if stage not in ('riley-defaults-before', 'jordan-overlay-read', 'jordan-overlay-close',
                         'riley-delete-cancel-draft', 'riley-delete-save-draft', 'riley-deleted-read'):
            return super().check_settings(stage, observed)
        InstalledJourney.check_settings(self, stage, observed)
        require(stage not in self.captures, 'binding-reminders:capture-replay')
        if stage == 'jordan-overlay-close':
            require('jordan-overlay-read' in self.captures, 'binding-reminders:jordan-overlay-order')
        else:
            current = observed['ui']['reminders']
            preferences = {key: current[key] for key in (
                'records', 'language', 'show_in_fullscreen', 'fullscreen_enabled')}
            if stage == 'riley-defaults-before':
                require(preferences == {'records': DEFAULTS, 'language': 'en',
                    'show_in_fullscreen': True, 'fullscreen_enabled': True},
                    'binding-reminders:riley-defaults')
                self.station_riley_defaults = deepcopy(preferences)
            elif stage == 'jordan-overlay-read':
                require(self.jordan_preferences is not None
                        and preferences == self.jordan_preferences,
                        'binding-reminders:jordan-overlay-preservation')
            else:
                require(self.custom_record is not None and self.custom_record['value'] == 90
                        and 'riley-saved-read' in self.captures
                        and self.station_riley_defaults is not None
                        and preferences == self.station_riley_defaults
                        and self.initial_reminders == self.station_riley_defaults,
                        'binding-reminders:deleted-id-and-defaults')
                if stage == 'riley-delete-save-draft':
                    require({'riley-delete-cancel', 'riley-cancel-read'} <= self.captures,
                            'binding-reminders:cancel-before-save')
                if stage == 'riley-deleted-read':
                    require({'riley-delete-save-draft', 'riley-delete-save'} <= self.captures,
                            'binding-reminders:deletion-before-save')
        self.captures.add(stage)
