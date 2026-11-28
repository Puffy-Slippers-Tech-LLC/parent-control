"""Case 269: pause and reuse a running grant at the kiosk without losing seconds."""

from accessible_ui import NAMED_CHILD_OPERATIONS
from countdown import CountdownSample
from grant_only_profile import GrantOnlyProfileJourney
from installed_journey import JourneyPlan, record_installed_journey
from journey_blocks import (desktop_entry, desktop_return, fresh_desktop, grant_only_time_profile,
                            prefixed_stages, retained_parent_entry, station_entry)
from journey_checks import require_zero_grant
from kiosk_approved_flow import approved_request
from private_artifacts import require
from real_interval import interval_action
from saved_time_retained_unlock import SECONDS_MARGIN, TRANSFER_LEAD_SECONDS, elapsed_interval, elapsed_result


GRANT_SECONDS = 240
# Each pause must still find running time beyond the five-second transfer window.
MINIMUM_RUNNING_SECONDS = 15
STABLE_WAIT_SECONDS = 15
REST_OF_DAY = ('child', 'parent', 0, False)


def approved_time(prefix):
    """Fresh station entry, the bound child and its Approved time page."""
    return {**prefixed_stages(prefix, station_entry()),
            f'{prefix}-child': 'ui:kiosk-request-child',
            f'{prefix}-tab': 'ui:kiosk-saved-tab-approved',
            f'{prefix}-read': 'ui:kiosk-saved-read'}


def leave_child(prefix):
    """Switch User from the child's desktop and keep its locked session."""
    return {f'{prefix}-switch-ready': 'ui:fresh-child-desktop',
            f'{prefix}-switch': 'system:child-switch-user',
            f'{prefix}-greeter': 'ui:gdm-returned',
            f'{prefix}-retained-locked': 'system:child-retained-locked'}


FIRST_PAUSE = {
    **grant_only_time_profile(source='gdm', entry='fresh', window='new',
        initial_enabled=False, revoke_first=False, duration_seconds=GRANT_SECONDS,
        request_initial='default', balance_readback=False),
    **prefixed_stages('fresh', desktop_entry('child', source='gdm', entry='fresh')),
    **leave_child('first'),
    **approved_time('running'),
    'running-reread': 'ui:kiosk-saved-read',
    'pause-first': 'ui:kiosk-saved-pause',
    'paused-reread': 'ui:kiosk-saved-read',
    'paused-cancel': 'ui:kiosk-request-cancel',
    'paused-returned': 'ui:gdm-station-returned',
    'paused-retained-locked': 'system:child-retained-locked',
    **prefixed_stages('reuse', station_entry()),
    'other-before': 'ui:kiosk-saved-disabled',
    'reuse-child': 'ui:kiosk-request-child',
    'reuse-tab': 'ui:kiosk-saved-tab-approved',
    'reuse-read': 'ui:kiosk-saved-read',
}
TRANSFERS = {
    'use-first': 'ui:kiosk-saved-use',
    'use-first-returned': 'ui:gdm-station-returned',
    **prefixed_stages('retained', desktop_entry('child', source='gdm', entry='retained')),
    'first-countdown': 'ui:child-countdown-present',
    'first-identity': 'system:child-entry-same',
    **leave_child('again'),
    **approved_time('second'),
    'pause-second': 'ui:kiosk-saved-pause',
    'use-second': 'ui:kiosk-saved-use',
    'use-second-returned': 'ui:gdm-station-returned',
    **approved_time('third'),
    'pause-third': 'ui:kiosk-saved-pause',
}
REVOKE = {
    'third-cancel': 'ui:kiosk-request-cancel',
    'third-returned': 'ui:gdm-station-returned',
    **prefixed_stages('revoke-parent', desktop_entry('parent', source='gdm', entry='retained')),
    **prefixed_stages('revoke-entry', retained_parent_entry(source='same-user', desktop_observation=False)),
    'revoke-before': 'ui:revoke-balances',
    'revoke-open': 'ui:revoke-open',
    'revoke-confirm': 'ui:revoke-confirm',
    **desktop_return('revoke-leave', account='parent'),
    **prefixed_stages('revoked', station_entry()),
    'other-after': 'ui:kiosk-saved-disabled',
    'revoked-child': 'ui:kiosk-request-child',
    'revoked-tab': 'ui:kiosk-saved-tab-approved',
    'revoked-read': 'ui:kiosk-saved-read',
}
DEADLINE = {
    'final-request-tab': 'ui:kiosk-saved-tab-request',
    **prefixed_stages('final', {
        'new-choices': 'ui:kiosk-request-select', 'new-estimate': 'ui:kiosk-request-estimate',
        **approved_request(child='fixture-child', approver='fixture-parent', duration_seconds=0,
                           allow_soft=False, exit='automatic', explicit=True)}),
    **approved_time('deadline'),
    'deadline-cancel': 'ui:kiosk-request-cancel',
    'deadline-returned': 'ui:gdm-station-returned',
}
GROUPS = (FIRST_PAUSE, TRANSFERS, REVOKE, DEADLINE)
SCREENS = {stage: tag for screens in GROUPS for stage, tag in screens.items()}
LOGIN_STAGES = {*fresh_desktop('parent'), *prefixed_stages('fresh', fresh_desktop('child')),
                *prefixed_stages('retained', fresh_desktop('child')),
                *prefixed_stages('revoke-parent', fresh_desktop('parent'))}
PLAN = JourneyPlan(
    prefix='saved-time-kiosk-pause-reuse', worker_mode='saved_time_kiosk_pause_reuse',
    screen_tags=SCREENS,
    phases={'ready': 'setup', 'setup-detached': 'setup',
            **{stage: f'step-{index}' for index, screens in enumerate(GROUPS, 1) for stage in screens},
            'installed-greeter': 'start'},
    advance_after={'reuse-read': 'step-2', 'pause-third': 'step-3', 'revoked-read': 'step-4'},
    stage_actions={'running-read': 'real-interval', 'pause-first': 'saved-wait'},
    child_bindings={stage: 'child' for stage, tag in SCREENS.items()
                    if tag.removeprefix('ui:') in NAMED_CHILD_OPERATIONS},
    invocations=tuple(stage for stage in SCREENS if stage in LOGIN_STAGES),
    challenges={'parent-login': ('parent', 'recipient-qualified', 'recipient-rechecked'),
                'fresh': ('child', 'fresh-child-recipient-qualified', 'fresh-child-recipient-rechecked'),
                'retained': ('child', 'retained-child-recipient-qualified',
                             'retained-child-recipient-rechecked'),
                'revoke-parent': ('parent', 'revoke-parent-recipient-qualified',
                                  'revoke-parent-recipient-rechecked')},
    kiosk_request=REST_OF_DAY,
    # Rest of the day must end well after the journey, not at a nearby midnight.
    ordinary_daytime=True,
    assertions_after={'reuse-read': 'pause-saves-stable-balance',
                      'pause-third': 'transfers-conserve-granted-seconds',
                      'other-after': 'other-child-unchanged',
                      'revoked-read': 'revoked-saved-time-unavailable',
                      'deadline-read': 'deadline-grant-offers-no-pause'},
)
RUNNING_READS = ('running-read', 'running-reread', 'second-read', 'third-read')
PAUSES = ('pause-first', 'pause-second', 'pause-third')
SAVED_READS = ('paused-reread', 'reuse-read')
SESSION_STAGES = ('first-retained-locked', 'paused-retained-locked', 'retained-entry-guard',
                  'first-identity', 'again-retained-locked')


class SavedTimeKioskPauseReuseJourney(GrantOnlyProfileJourney):
    def __init__(self, context, progress, plan, *, actions=None):
        super().__init__(context, progress, plan, grant_seconds=GRANT_SECONDS, actions={
            'real-interval': interval_action(2),
            'saved-wait': interval_action(STABLE_WAIT_SECONDS),
        } if actions is None else actions)
        self.retained_session = None
        self.running = None
        self.saved = None
        self.redemption = None
        self.other = None
        self.transfers = []

    @staticmethod
    def check_balance(value, *, saved, running):
        """Exact saved/zero balances; a positive running value is checked by the caller."""
        require(value['child'] == 'fixture-child' and value['daily_seconds'] == 0
                and value['saved_seconds'] == saved
                and (value['running_seconds'] == running if running is not None
                     else type(value['running_seconds']) is int and value['running_seconds'] > 0)
                and value['state'] == ('ready' if saved or running is None else 'empty')
                and value['actions']['use_saved'] is bool(saved)
                and value['actions']['pause'] is (running is None and not saved),
                'saved-time:pause-reuse-balance')

    def redeemed(self, seconds, bounds):
        """Compare a later reading of a redeemed grant with its elapsed interval."""
        low, high = elapsed_interval(self.redemption, bounds, maximum_seconds=GRANT_SECONDS)
        deduction = self.saved - seconds
        require(0 < seconds and 0 < deduction
                and low - SECONDS_MARGIN <= deduction <= high + SECONDS_MARGIN,
                'saved-time:redeemed-interval')
        return {'deducted_seconds': deduction, 'elapsed_interval_seconds': elapsed_result(low, high)}

    def check_settings(self, stage, observed):
        super().check_settings(stage, observed)
        system = observed.get('system', {})
        if stage == 'first-retained-locked':
            self.retained_session = system['session_sha256']
        if stage in SESSION_STAGES:
            require(system['session_sha256'] == self.retained_session, 'saved-time:retained-session-replaced')

        ui = observed.get('ui', {})
        value = ui.get('saved_time')
        if stage in RUNNING_READS:
            self.check_balance(value, saved=0, running=None)
            seconds = value['running_seconds']
            require(MINIMUM_RUNNING_SECONDS <= seconds <= GRANT_SECONDS, 'saved-time:running-grant')
            if stage == 'running-reread':
                before, bounds = self.running
                low, high = elapsed_interval(bounds, self.ui.read_bounds)
                decrease = before - seconds
                require(0 < decrease and low - SECONDS_MARGIN <= decrease <= high + SECONDS_MARGIN,
                        'saved-time:running-decrease')
                observed['comparison'] = {'decrease_seconds': decrease,
                                          'elapsed_interval_seconds': elapsed_result(low, high)}
            elif stage != 'running-read':
                observed['comparison'] = self.redeemed(seconds, self.ui.read_bounds)
            self.running = (seconds, self.ui.read_bounds)
        elif stage in PAUSES:
            # No parent prompt is accepted while waiting; the page shows saved time only.
            after = value['time']
            saved = after['saved_seconds']
            self.check_balance(after, saved=saved, running=0)
            before, bounds = self.running
            low, high = elapsed_interval(bounds, self.ui.read_bounds)
            low += TRANSFER_LEAD_SECONDS
            high += TRANSFER_LEAD_SECONDS
            require(value['paused'] is True and 0 < saved
                    and before - high - SECONDS_MARGIN <= saved <= before - low + SECONDS_MARGIN,
                    'saved-time:pause-conservation')
            self.saved = saved
            self.transfers.append({'stage': stage, 'running_seconds': before, 'saved_seconds': saved})
            observed['comparison'] = {'saved_seconds': saved, 'running_before_seconds': before,
                                      'elapsed_interval_seconds': elapsed_result(low, high),
                                      **({'transfers': list(self.transfers)} if stage == 'pause-third' else {})}
        elif stage in SAVED_READS:
            self.check_balance(value, saved=self.saved, running=0)
        elif stage in ('use-first', 'use-second'):
            require(value['used'] is True and value['saved_seconds'] == self.saved,
                    'saved-time:wrong-redemption-balance')
            self.redemption = self.ui.read_bounds
        elif stage == 'first-countdown':
            current = CountdownSample.from_ui(ui, boot_sha256=observed['boot_sha256'])
            observed['comparison'] = self.redeemed(current.countdown.seconds, current.read_bounds)
        elif stage in ('other-before', 'other-after'):
            other = ui['saved_time']
            if stage == 'other-before':
                self.other = other
            else:
                require(other == self.other, 'saved-time:other-child-changed')
        elif stage == 'revoke-before':
            # Only saved time remains: no running grant and no daily time.
            balances = ui['revoke_cancel']['balances']
            require_zero_grant(balances)
            require(balances['daily']['seconds'] == 0, 'saved-time:revoke-daily')
        elif stage == 'revoked-read':
            self.check_balance(value, saved=0, running=0)
        elif stage == 'final-new-estimate':
            choice = ui['valid_choice']['request']
            require(choice['child'] == 'fixture-child' and choice['approver'] == 'fixture-parent'
                    and choice['duration_seconds'] == 0 and choice['allow_soft'] is False,
                    'saved-time:rest-of-day-request')
        elif stage == 'deadline-read':
            # Time until midnight runs, but a deadline grant cannot be paused.
            require(value['child'] == 'fixture-child' and value['state'] == 'ready'
                    and value['saved_seconds'] == 0 and type(value['running_seconds']) is int
                    and value['running_seconds'] > 0 and not value['actions']['pause']
                    and not value['actions']['use_saved'], 'saved-time:deadline-pause')


def execute(recorder, context):
    record_installed_journey(recorder, context, PLAN, timeout=2700,
                             journey_type=SavedTimeKioskPauseReuseJourney)


E2E_CASES = {'saved-time-kiosk-pause-reuse': execute}
