"""Qualify the shared saved-time actions in two fixed installed slices.

Kiosk: disabled-control and Rest-of-the-day presentation, a deferred approval,
the saved balance and Use saved time with return to sign-in. Overlay: with
daily time and a running fixed grant, Cancel the lock confirmation, then Pause
and lock behind the native lock. Customer journeys belong to their own cases.
"""
from installed_journey import JourneyPlan
from journey_blocks import fresh_desktop, overlay_entry, parent_management, prefixed_stages, station_entry
from private_artifacts import require
from request_composition import KioskRequestJourney
from request_flow import approval_and_return, kiosk_choices

SECONDS = 600
CHOICES = dict(child='fixture-child', approver='fixture-parent', duration_seconds=SECONDS, allow_soft=False)
BINDING = kiosk_choices(*CHOICES.values())
OVERLAY_ENTRY = overlay_entry('direct', 'command', form_operation='request-overlay-riley-ready')
ENTRY = {
    **fresh_desktop('parent'), **parent_management(),
    'allowance-configured': 'ui:time-explanation-setup-thirty-read',
    'repeat-desktop': 'ui:desktop', 'switch-user': 'system:parent-switch-user',
    'gdm-switched': 'ui:gdm-returned',
}
KIOSK_SCREENS = {
    **ENTRY, **station_entry(),
    'disabled-read': 'ui:kiosk-saved-disabled',
    'child-selected': 'ui:kiosk-request-child',
    'request-tab': 'ui:kiosk-saved-tab-request',
    'rest-of-day': 'ui:kiosk-saved-rest-of-day',
    'new-choices': 'ui:kiosk-request-select',
    'new-estimate': 'ui:kiosk-request-estimate',
    **{'approval-' + stage: 'ui:kiosk-saved-mate-' + operation for stage, operation in (
        ('open', 'open'), ('qualified', 'qualified'), ('rechecked', 'rechecked'),
        ('success', 'submit-success'))},
    'saved-read': 'ui:kiosk-saved-read',
    'use-saved': 'ui:kiosk-saved-use',
    'use-returned': 'ui:gdm-station-returned',
    **prefixed_stages('after', station_entry()),
    'after-child': 'ui:kiosk-request-child',
    'after-tab': 'ui:kiosk-saved-tab-approved',
    'after-read': 'ui:kiosk-saved-read',
    'after-cancel': 'ui:kiosk-request-cancel',
    'after-returned': 'ui:gdm-station-returned',
}
OVERLAY_SCREENS = {
    **ENTRY,
    **approval_and_return(prefix='new', entry='new', surface='kiosk', child_entry='fresh', **CHOICES),
    **OVERLAY_ENTRY,
    'approved-tab': 'ui:overlay-saved-tab-approved',
    'running-read': 'ui:overlay-saved-read',
    'pause-open': 'ui:overlay-saved-pause',
    'pause-cancelled': 'ui:overlay-saved-lock-cancel',
    'pause-reopen': 'ui:overlay-saved-pause',
    'pause-confirmed': 'ui:overlay-saved-lock-confirm',
    'locked': 'ui:child-lock-curtain',
}


def plan(surface):
    require(surface in ('kiosk', 'overlay'), 'saved-time:surface')
    kiosk = surface == 'kiosk'
    screens = KIOSK_SCREENS if kiosk else OVERLAY_SCREENS
    child = () if kiosk else (*prefixed_stages('fresh', fresh_desktop('child')), *OVERLAY_ENTRY)
    return JourneyPlan(
        prefix='saved-time-' + surface, worker_mode='saved_time_' + surface, screen_tags=screens,
        phases={'ready': 'setup', 'setup-detached': 'setup',
                **{stage: 'step-1' for stage in screens}, 'installed-greeter': 'start'},
        invocations=(*fresh_desktop('parent'), *child),
        challenges={'parent-login': ('parent', 'recipient-qualified', 'recipient-rechecked'),
                    **({} if kiosk else {'fresh': (
                        'child', 'fresh-child-recipient-qualified', 'fresh-child-recipient-rechecked')})},
        child_bindings={'allowance-configured': 'child'},
        balance_checks={'allowance-configured': 1800},
        countdown_checks={} if kiosk else {'countdown': ('new-estimate', 'estimate', 1, 180)},
        kiosk_request=BINDING,
        assertions_after={
            'disabled-read': 'disabled-control-approved-time',
            'rest-of-day': 'rest-of-day-cannot-be-saved',
            'approval-success': 'deferred-approval-saved',
            'saved-read': 'saved-balance-without-running-time',
            'use-returned': 'saved-time-started-and-greeter-return',
            'after-read': 'saved-time-used-once',
        } if kiosk else {
            'new-returned': 'automatic-greeter-return',
            'fresh-desktop': 'fresh-selected-child-desktop',
            'running-read': 'running-grant-can-be-paused',
            'pause-cancelled': 'lock-cancel-keeps-grant-running',
            'locked': 'pause-and-lock-native-lock',
        },
    )


KIOSK_PLAN = plan('kiosk')
OVERLAY_PLAN = plan('overlay')


class SavedTimeControlsJourney(KioskRequestJourney):
    def __init__(self, context, progress, plan=KIOSK_PLAN):
        super().__init__(context, progress, plan)
        self.running = None

    def check_settings(self, stage, observed):
        super().check_settings(stage, observed)
        value = observed.get('ui', {}).get('saved_time')
        if stage == 'disabled-read':
            require(value['child'] == 'existing-fixture-child' and not any(value['actions'].values()),
                    'saved-time:disabled-control')
        elif stage == 'saved-read':
            require(value['state'] == 'ready' and value['saved_seconds'] == SECONDS
                    and value['running_seconds'] == 0
                    and value['daily_seconds'] == self.balance['daily']['seconds']
                    and value['actions']['use_saved']
                    and not value['actions']['pause'], 'saved-time:saved-balance')
        elif stage == 'use-saved':
            require(value['saved_seconds'] == SECONDS, 'saved-time:used-balance')
        elif stage == 'after-read':
            # The started grant runs beyond daily time; nothing remains saved.
            require(value['state'] == 'ready' and value['saved_seconds'] == 0
                    and 0 < value['running_seconds'] <= SECONDS and value['actions']['pause']
                    and value['daily_seconds'] == self.balance['daily']['seconds']
                    and not value['actions']['use_saved'], 'saved-time:used-once')
        elif stage == 'running-read':
            require(value['state'] == 'ready' and value['saved_seconds'] == 0
                    and 0 < value['running_seconds'] <= SECONDS and value['actions']['pause']
                    and 0 < value['daily_seconds'] <= self.balance['daily']['seconds']
                    and not value['actions']['use_saved'], 'saved-time:running-grant')
            self.running = value
        elif stage == 'pause-cancelled':
            # While daily time is used, the time beyond it stays constant.
            after = value['time']
            require(self.running is not None and after['state'] == 'ready'
                    and after['saved_seconds'] == 0 and after['actions']['pause']
                    and 0 < after['daily_seconds'] <= self.running['daily_seconds']
                    and abs(after['running_seconds'] - self.running['running_seconds']) <= 5,
                    'saved-time:cancel-kept-running')
