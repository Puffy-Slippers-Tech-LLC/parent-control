"""Two independent fresh-child entries for TIME01's desktop binding."""

from dataclasses import replace

from accessible_ui import countdown_seconds
from countdown import (CountdownObservation, CountdownSample, await_countdown_progress,
                       check_countdown_balance, check_countdown_progress)
from installed_journey import InstalledJourney, JourneyPlan
from journey_blocks import daily_time_profile, fresh_desktop, parent_management
from journey_checks import DailyTimeProfileJourney, check_balances
from private_artifacts import require
from ui_observations import SettingsObservation


def plan(present):
    require(type(present) is bool, 'countdown:profile')
    screens = {
        **fresh_desktop('parent'), **parent_management(),
        'allowance-configured': 'ui:time-explanation-positive-read',
        **({} if present else {'limits-disabled': 'ui:time-explanation-off-read'}),
        'wrong-account-refused': 'ui:child-countdown-wrong-account-refused',
        'repeat-desktop': 'ui:desktop', 'switch-user': 'system:parent-switch-user',
        'gdm-switched': 'ui:gdm-returned',
        **{'fresh-' + stage: operation for stage, operation in fresh_desktop('child').items()},
        **{stage: 'ui:child-countdown-' + ('present' if present else 'absent')
           for stage in ('countdown', 'independent-countdown')},
    }
    return JourneyPlan(
        prefix='countdown-' + ('enabled' if present else 'off'),
        worker_mode='countdown_enabled' if present else 'countdown_off', screen_tags=screens,
        phases={'ready': 'setup', 'setup-detached': 'setup',
                **{stage: 'step-1' for stage in screens}, 'installed-greeter': 'start',
                **{stage: 'step-2' for stage in screens
                   if stage.startswith('fresh-') or 'countdown' in stage}},
        advance_after={'gdm-switched': 'step-2'},
        invocations=tuple(stage for stage in screens if stage in fresh_desktop('parent')
                          or stage.startswith('fresh-') or 'countdown' in stage),
        challenges={
            'parent-login': ('parent', 'recipient-qualified', 'recipient-rechecked'),
            'child-login': ('child', 'fresh-child-recipient-qualified', 'fresh-child-recipient-rechecked'),
        },
        assertions_after={'allowance-configured': 'positive-daily-time',
                          'wrong-account-refused': 'wrong-account-refused',
                          'fresh-desktop': 'usable-child-desktop',
                          'countdown': 'countdown-present' if present else 'countdown-absent',
                          'independent-countdown': 'independent-countdown'},
    )


PLAN = plan(True)
OFF_PLAN = plan(False)


def session_plan():
    """One positive-time child, explicit Lock, retained GDM entry and return."""
    screens = {
        **fresh_desktop('parent'), **parent_management(),
        'allowance-configured': 'ui:time-explanation-positive-read',
        'repeat-desktop': 'ui:desktop', 'switch-user': 'system:parent-switch-user',
        'gdm-switched': 'ui:gdm-returned',
        **{'fresh-' + stage: tag for stage, tag in fresh_desktop('child').items()},
        'countdown': 'ui:child-countdown-present',
        'panel-bound': 'ui:child-countdown-session-pin',
        'lock': 'system:child-lock',
        'locked-countdown': 'ui:child-countdown-session-locked',
        'return-greeter': 'system:child-return-greeter',
        'retained-greeter': 'ui:gdm-returned',
        'greeter-countdown': 'ui:child-countdown-session-greeter',
        'retained-list': 'ui:gdm-child-list', 'retained-focused': 'ui:gdm-child-focused',
        'retained-recipient-qualified': 'ui:gdm-child-recipient',
        'retained-recipient-rechecked': 'ui:gdm-child-recipient-rechecked',
        'unlock-desktop': 'ui:fresh-child-desktop',
        'panel-restored': 'ui:child-countdown-session-restored',
        'independent-countdown': 'ui:child-countdown-present',
    }
    return JourneyPlan(
        prefix='countdown-session', worker_mode='countdown_session', screen_tags=screens,
        phases={'ready': 'setup', 'setup-detached': 'setup', 'installed-greeter': 'start',
                **{stage: 'step-1' for stage in screens if stage != 'installed-greeter'}},
        invocations=tuple(stage for stage in screens if stage in fresh_desktop('parent')
            or stage.startswith('fresh-') or stage in ('countdown', 'panel-bound', 'locked-countdown',
                'greeter-countdown', 'retained-list', 'retained-focused',
                'retained-recipient-qualified', 'retained-recipient-rechecked', 'unlock-desktop',
                'panel-restored', 'independent-countdown')),
        challenges={**PLAN.challenges,
            'retained-login': ('child', 'retained-recipient-qualified', 'retained-recipient-rechecked')},
        assertions_after={'allowance-configured': 'positive-daily-time',
            'countdown': 'desktop-countdown-present', 'panel-bound': 'child-panel-bound',
            'locked-countdown': 'locked-countdown-unavailable',
            'greeter-countdown': 'greeter-countdown-unavailable',
            'panel-restored': 'same-child-panel-restored',
            'independent-countdown': 'positive-countdown-restored'},
    )


SESSION_PLAN = session_plan()


class CountdownJourney(InstalledJourney):
    def __init__(self, context, progress, plan=PLAN, *, actions=None):
        super().__init__(context, progress, plan, actions=actions)
        self.balance = None
        self.countdown = None

    def check_settings(self, stage, observed):
        super().check_settings(stage, observed)
        if stage == 'allowance-configured':
            check_balances(self, observed)
            value = observed['ui']['time_explanation']
            self.balance = (value['total']['seconds'], value['total']['precision_seconds'],
                            value['observed_monotonic_ns'])
        operation = self.plan.screen_tags.get(stage)
        if operation in ('ui:child-countdown-present', 'ui:child-countdown-absent'):
            value = CountdownObservation.from_value(observed['ui']['countdown'],
                present=operation == 'ui:child-countdown-present')
            if self.countdown is not None:
                require(value.observed_monotonic_ns > self.countdown.observed_monotonic_ns,
                        'countdown:stale-observation')
            if value.present:
                require(self.balance is not None, 'countdown:missing-balance')
                observed['comparison'] = check_countdown_balance(value, seconds=self.balance[0],
                    precision_seconds=self.balance[1], observed_monotonic_ns=self.balance[2])
            self.countdown = value


MINUTE_SCREENS = {
    **fresh_desktop('parent'),
    'wrong-account-refused': 'ui:child-countdown-wrong-account-refused',
    **daily_time_profile(source='desktop', entry='same-user', window='new',
                         initial_enabled=False, minutes=4),
    **{'fresh-' + stage: operation for stage, operation in fresh_desktop('child').items()},
    'minute-progression': 'ui:child-countdown-present',
    'independent-minute-progression': 'ui:child-countdown-present',
}
MINUTE_PLAN = JourneyPlan(
    prefix='countdown-minutes', worker_mode='countdown_minutes', screen_tags=MINUTE_SCREENS,
    phases={'ready': 'setup', 'setup-detached': 'setup',
            **{stage: 'step-1' for stage in MINUTE_SCREENS}, 'installed-greeter': 'start',
            **{stage: 'step-2' for stage in MINUTE_SCREENS if stage.startswith('fresh-')
               or stage.endswith('minute-progression')}},
    advance_after={'gdm-switched': 'step-2'},
    invocations=tuple(stage for stage in MINUTE_SCREENS
                      if stage in fresh_desktop('parent') or stage.startswith('fresh-')
                      or stage == 'wrong-account-refused' or stage.endswith('minute-progression')),
    challenges={
        'parent-login': ('parent', 'recipient-qualified', 'recipient-rechecked'),
        'child-login': ('child', 'fresh-child-recipient-qualified', 'fresh-child-recipient-rechecked'),
    },
    settings_checks={'same-parent-selected': SettingsObservation('fixture-child', False, ('0 minutes',)),
                     'profile-settings': SettingsObservation('fixture-child', True, ('4 minutes',))},
    balance_checks={'profile-configured': 240},
    stage_actions={stage: 'minute-progress' for stage in (
        'minute-progression', 'independent-minute-progression')},
    assertions_after={'wrong-account-refused': 'wrong-account-refused',
                      'profile-configured': 'daily-only-time',
                      'fresh-desktop': 'usable-child-desktop',
                      'minute-progression': 'minute-progression',
                      'independent-minute-progression': 'independent-minute-progression'},
)


class CountdownMinutesJourney(DailyTimeProfileJourney):
    """TIME02 minute slice with caller-supplied, independently read endpoints."""
    sample_precision_seconds = 60
    sample_bound_seconds = 90

    def __init__(self, context, progress, plan=MINUTE_PLAN, *, actions=None):
        super().__init__(context, progress, plan, no_grant_checks=('profile-before',),
                         actions=actions or {'minute-progress': self.minute_progress})
        self.balance = None
        self.current_countdown = None
        self.last_countdown = None

    def check_settings(self, stage, observed):
        super().check_settings(stage, observed)
        if stage == 'profile-configured':
            value = observed['ui']['time_explanation']
            self.balance = (value['total']['seconds'], value['total']['precision_seconds'],
                            value['observed_monotonic_ns'])
        if stage in self.plan.stage_actions:
            current = CountdownSample.from_ui(observed['ui'], boot_sha256=observed['boot_sha256'])
            if self.last_countdown is None:
                require(self.balance is not None, 'countdown:missing-balance')
                observed['comparison'] = check_countdown_balance(current.countdown,
                    seconds=self.balance[0], precision_seconds=self.balance[1],
                    observed_monotonic_ns=self.balance[2])
            else:
                current.elapsed_since(self.last_countdown,
                    max_elapsed_seconds=self.sample_bound_seconds)
                if current.countdown.text != self.last_countdown.countdown.text:
                    observed['comparison'] = check_countdown_progress(current, self.last_countdown,
                        precision_seconds=self.sample_precision_seconds, tolerance_seconds=2,
                        max_elapsed_seconds=self.sample_bound_seconds)
            self.check_progress_entry(current)
            self.current_countdown = current

    def check_progress_entry(self, current):
        pass

    @staticmethod
    def minute_progress(journey, guard):
        current, result = await_countdown_progress(journey, guard, journey.current_countdown,
            precision_seconds=60, tolerance_seconds=2, max_elapsed_seconds=90)
        journey.last_countdown = current
        return result


TICK_STAGES = ('final-second-transition', 'second-progression', 'independent-second-progression')
TICK_SCREENS = {
    **fresh_desktop('parent'),
    'wrong-account-refused': 'ui:child-countdown-wrong-account-refused',
    **daily_time_profile(source='desktop', entry='same-user', window='new',
                         initial_enabled=False, minutes=4),
    **{'fresh-' + stage: operation for stage, operation in fresh_desktop('child').items()},
    **{stage: 'ui:child-countdown-present' for stage in TICK_STAGES},
}
TICK_PLAN = replace(MINUTE_PLAN,
    prefix='countdown-ticks', worker_mode='countdown_ticks', screen_tags=TICK_SCREENS,
    phases={'ready': 'setup', 'setup-detached': 'setup',
            **{stage: 'step-1' for stage in TICK_SCREENS}, 'installed-greeter': 'start',
            **{stage: 'step-2' for stage in TICK_SCREENS
               if stage.startswith('fresh-') or stage in TICK_STAGES}},
    invocations=tuple(stage for stage in TICK_SCREENS
                      if stage in fresh_desktop('parent') or stage.startswith('fresh-')
                      or stage == 'wrong-account-refused' or stage in TICK_STAGES),
    settings_checks={'same-parent-selected': SettingsObservation('fixture-child', False, ('0 minutes',)),
                     'profile-settings': SettingsObservation('fixture-child', True, ('4 minutes',))},
    balance_checks={'profile-configured': 240},
    stage_actions={TICK_STAGES[0]: 'final-transition',
                   **{stage: 'second-progress' for stage in TICK_STAGES[1:]}},
    assertions_after={'wrong-account-refused': 'wrong-account-refused',
                      'profile-configured': 'daily-only-time',
                      'fresh-desktop': 'usable-child-desktop',
                      **{stage: stage for stage in TICK_STAGES}},
)


class CountdownTicksJourney(CountdownMinutesJourney):
    """Arm before the final minute, then observe its transition and two decreases.

    Initial stage reads never replace a completed endpoint or extend its bound.
    All reads and waits use TIME01/TIME03 and the same immutable TIME02 comparison.
    """
    sample_precision_seconds = 1
    sample_bound_seconds = 15

    def __init__(self, context, progress, plan=TICK_PLAN, *, actions=None):
        super().__init__(context, progress, plan, actions=actions or {
            'final-transition': self.final_transition, 'second-progress': self.second_progress})

    def check_progress_entry(self, current):
        if self.last_countdown is None:
            require(current.precision_seconds == 60, 'countdown:transition-window')
        else:
            require(current.precision_seconds == 1, 'countdown:seconds-required')
        require(countdown_seconds(current.countdown.text)[0] > 0,
                'countdown:final-window-missed')

    def await_tick(self, guard, *, transition):
        previous = self.current_countdown if transition else self.last_countdown
        minute_progressions = []
        if transition:
            # Fresh login need not land in one particular minute. Observe each
            # real minute edge before the final transition, with its own bound.
            while previous.countdown.text != '00:01':
                require(len(minute_progressions) < 3, 'countdown:minute-bound')
                previous, comparison = await_countdown_progress(self, guard, previous,
                    precision_seconds=60, tolerance_seconds=2, max_elapsed_seconds=90)
                minute_progressions.append(comparison)
        current, result = await_countdown_progress(self, guard, previous,
            precision_seconds=1, previous_precision_seconds=60 if transition else 1,
            tolerance_seconds=2, max_elapsed_seconds=90 if transition else 15,
            initial_sample=None if transition else self.current_countdown)
        require(countdown_seconds(current.countdown.text)[0] > 0,
                'countdown:final-window-missed')
        self.last_countdown = current
        if transition:
            result['minute_progressions'] = minute_progressions
        return result

    @staticmethod
    def final_transition(journey, guard):
        return journey.await_tick(guard, transition=True)

    @staticmethod
    def second_progress(journey, guard):
        return journey.await_tick(guard, transition=False)
