"""FLOW13 daily-only qualification; fresh and independent same-user attempts."""

from installed_journey import JourneyPlan
from journey_blocks import daily_time_profile, fresh_desktop, parent_management
from journey_checks import DailyTimeProfileJourney
from ui_observations import SettingsObservation

FRESH_SCREENS = daily_time_profile(source='gdm', entry='fresh', window='new',
                                 initial_enabled=False, minutes=2)
SAME_SCREENS = {
    **fresh_desktop('parent'), **parent_management(),
    'wrong-child': 'ui:time-explanation-config-wrong-child',
    'wrong-window': 'ui:parent-new-window-refused',
    'close-ready': 'ui:parent-search-close-ready',
    'closed': 'ui:parent-search-closed',
    **daily_time_profile(source='desktop', entry='same-user', window='new',
                         initial_enabled=False, minutes=4),
}
PLAN = JourneyPlan(
    prefix='time-profiles-daily', worker_mode='time_profiles_daily', screen_tags=FRESH_SCREENS,
    phases={'ready': 'setup', 'setup-detached': 'setup', 'installed-greeter': 'start',
            **{stage: 'step-1' for stage in FRESH_SCREENS if stage != 'installed-greeter'}},
    settings_checks={'parent-selected': SettingsObservation('fixture-child', False, ('0 minutes',)),
                     'profile-settings': SettingsObservation('fixture-child', True, ('2 minutes',))},
    balance_checks={'profile-configured': 120},
)
SAME_PLAN = JourneyPlan(
    prefix='time-profiles-same', worker_mode='time_profiles_same', screen_tags=SAME_SCREENS,
    phases={'ready': 'setup', 'setup-detached': 'setup', 'installed-greeter': 'start',
            **{stage: 'step-1' for stage in SAME_SCREENS if stage != 'installed-greeter'}},
    settings_checks={'parent-selected': SettingsObservation('fixture-child', False, ('0 minutes',)),
                     'same-parent-selected': SettingsObservation('fixture-child', False, ('0 minutes',)),
                     'profile-settings': SettingsObservation('fixture-child', True, ('4 minutes',))},
    balance_checks={'profile-configured': 240},
)


def journey(context, progress, plan=PLAN, *, actions=None):
    return DailyTimeProfileJourney(context, progress, plan,
                                   no_grant_checks=('profile-before',), actions=actions)
