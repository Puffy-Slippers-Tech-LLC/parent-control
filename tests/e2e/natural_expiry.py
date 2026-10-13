"""TIME04: public daily-only preparation and actual use until natural lock."""

from countdown import CountdownSample, check_countdown_balance
from installed_journey import JourneyPlan
from journey_blocks import daily_time_profile, fresh_desktop, native_activity_entry, prefixed_stages
from journey_checks import DailyTimeProfileJourney
from native_fixtures import fixture_actions
from natural_expiry_observation import await_natural_expiry
from private_artifacts import require
from ui_observations import SettingsObservation


SCREENS = {
    **fresh_desktop('parent'),
    'wrong-account-refused': 'ui:child-natural-expiry-wrong-account-refused',
    **daily_time_profile(source='desktop', entry='same-user', window='new',
                         initial_enabled=False, minutes=2),
    **prefixed_stages('fresh', fresh_desktop('child')),
    **native_activity_entry('activity', child='child'),
    'natural-expiry': 'ui:child-countdown-present',
    'lock-input-ready': 'ui:child-natural-expiry-lock-ready',
    'lock-result': 'ui:child-natural-expiry-lock-result',
}
LOGIN_STAGES = set(fresh_desktop('parent')) | set(prefixed_stages('fresh', fresh_desktop('child')))
PLAN = JourneyPlan(
    prefix='natural-expiry', worker_mode='natural_expiry', screen_tags=SCREENS,
    phases={'ready': 'setup', 'setup-detached': 'setup',
            **{stage: 'step-1' for stage in SCREENS}, 'installed-greeter': 'start',
            **{stage: 'step-2' for stage in SCREENS
               if stage.startswith(('fresh-', 'activity-', 'lock-')) or stage == 'natural-expiry'}},
    advance_after={'gdm-switched': 'step-2'},
    invocations=tuple(stage for stage in SCREENS if stage in LOGIN_STAGES
                      or stage in ('wrong-account-refused', 'natural-expiry', 'lock-input-ready', 'lock-result')),
    challenges={
        'parent-login': ('parent', 'recipient-qualified', 'recipient-rechecked'),
        'child-login': ('child', 'fresh-child-recipient-qualified', 'fresh-child-recipient-rechecked'),
    },
    settings_checks={
        'same-parent-selected': SettingsObservation('fixture-child', False, ('0 minutes',)),
        'profile-settings': SettingsObservation('fixture-child', True, ('2 minutes',)),
    },
    balance_checks={'profile-configured': 120},
    stage_actions={'desktop': 'native-verify', 'natural-expiry': 'natural-expiry'},
    activity_entries={'natural-expiry': 'activity-capture'},
    assertions_after={'wrong-account-refused': 'wrong-account-refused',
                      'profile-configured': 'daily-only-time',
                      'fresh-desktop': 'usable-child-desktop',
                      'activity-capture': 'usable-native-activity',
                      'natural-expiry': 'natural-enforced-lock',
                      'lock-result': 'lock-owns-normal-input'},
)


class NaturalExpiryJourney(DailyTimeProfileJourney):
    """The fixed qualification owns its preparation and independent endpoints."""

    def __init__(self, context, progress, plan=PLAN, *, actions=None):
        if actions is None:
            actions = {**fixture_actions(include_refusal=False),
                       'natural-expiry': self.natural_expiry}
        super().__init__(context, progress, plan, no_grant_checks=('profile-before',),
                         actions=actions)
        self.balance = None
        self.initial_countdown = None
        self.natural_expiry_result = None

    def check_settings(self, stage, observed):
        super().check_settings(stage, observed)
        if stage == 'profile-configured':
            value = observed['ui']['time_explanation']
            self.balance = (value['total']['seconds'], value['total']['precision_seconds'],
                            value['observed_monotonic_ns'])
        if stage == 'natural-expiry':
            require(self.balance is not None and self.initial_countdown is None,
                    'natural-expiry:missing-or-replayed-entry')
            current = CountdownSample.from_ui(observed['ui'], boot_sha256=observed['boot_sha256'])
            observed['comparison'] = check_countdown_balance(current.countdown,
                seconds=self.balance[0], precision_seconds=self.balance[1],
                observed_monotonic_ns=self.balance[2])
            self.initial_countdown = current

    @staticmethod
    def natural_expiry(journey, guard):
        require(journey.initial_countdown is not None and journey.natural_expiry_result is None
                and 'activity-capture' in journey.activity_observations,
                'natural-expiry:missing-or-replayed-entry')
        result = await_natural_expiry(journey, guard, journey.initial_countdown,
                                     journey.activity_observations['activity-capture'])
        journey.natural_expiry_result = result
        return result
