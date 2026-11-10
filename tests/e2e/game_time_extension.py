"""E2E-024: extend the larger balance without losing the child's game."""
from copy import deepcopy
from dataclasses import replace

from accessible_ui import GAME_OPERATIONS
from countdown import CountdownSample
from grant_only_profile import GrantOnlyProfileJourney
from installed_journey import JourneyPlan, record_installed_journey
from journey_blocks import (daily_dominant_time_profile, desktop_entry, fresh_desktop,
                            game_usable_app, grant_only_time_profile, overlay_entry, prefixed_stages)
from native_fixtures import check_catalogue, fixture_actions
from natural_expiry_observation import await_natural_expiry
from private_artifacts import require
from request_composition import KioskRequestJourney
from request_flow import approval_and_return
from time_profiles_dominant import DailyDominantProfileJourney
from ui_observations import AppRowsObservation, SettingsObservation


PROFILE = {
    **daily_dominant_time_profile(grant_seconds=600, daily_minutes=20, finish='parent'),
    'game-apps': 'ui:parent-apps-page', 'game-policy': 'ui:parent-app-rows',
    'dominant-switch': 'system:parent-switch-user', 'dominant-gdm': 'ui:gdm-returned',
}
ENTRY = prefixed_stages('child-entry', desktop_entry('child', source='gdm', entry='fresh'))
PLAY = {**ENTRY, 'before-countdown': 'ui:child-countdown-present',
        **prefixed_stages('play', {**game_usable_app(level=1, mode='windowed'),
                                  'capture': 'ui:game-activity'})}
REQUEST = approval_and_return(prefix='new', entry='new', child='fixture-child',
    approver='fixture-parent', duration_seconds=75, allow_soft=False)
FINISH = {'returned-game': 'ui:game-activity', 'resume': 'ui:game-resume',
          'resumed': 'ui:game-resumed', 'resumed-capture': 'ui:game-resumed-activity',
          'natural-expiry': 'ui:game-resumed-activity',
          'lock-input-ready': 'ui:child-natural-expiry-lock-ready',
          'lock-result': 'ui:child-natural-expiry-lock-result'}
SCREENS = {**PROFILE, **PLAY, **REQUEST, **FINISH}
LOGINS = {'': ('parent', 'parent-login'), 'profile-return-': ('parent', 'profile-return'),
          'child-entry-': ('child', 'child-entry')}
LOGIN_STAGES = {prefix + stage for prefix, (role, _identity) in LOGINS.items()
                for stage in fresh_desktop(role)}
PLAN = JourneyPlan(
    prefix='game-time-extension', worker_mode='game_time_extension', screen_tags=SCREENS,
    phases={'ready': 'setup', 'setup-detached': 'setup',
            **{stage: phase for phase, screens in (
                ('step-1', {**PROFILE, **PLAY}), ('step-2', REQUEST), ('step-3', FINISH))
               for stage in screens}, 'installed-greeter': 'start'},
    advance_after={'play-capture': 'step-2', 'countdown': 'step-3'},
    invocations=tuple(stage for stage in SCREENS if stage in LOGIN_STAGES
                     or stage in ('natural-expiry', 'lock-input-ready', 'lock-result')),
    challenges={identity: (role, prefix + ('recipient-qualified' if role == 'parent'
                                          else 'child-recipient-qualified'),
                          prefix + ('recipient-rechecked' if role == 'parent'
                                    else 'child-recipient-rechecked'))
                for prefix, (role, identity) in LOGINS.items()},
    stage_actions={'desktop': 'native-verify', 'natural-expiry': 'natural-expiry'},
    child_bindings={stage: 'child' for stage, tag in SCREENS.items()
                    if tag.removeprefix('ui:') in GAME_OPERATIONS},
    settings_checks={'dominant-settings': SettingsObservation('fixture-child', True, ('20 minutes',))},
    overlay_request=('child', 'parent', 75, False),
    countdown_checks={'countdown': ('new-estimate', 'estimate', 1, 300)},
    activity_entries={'natural-expiry': 'resumed-capture'},
    activity_checks={'returned-game': ('play-capture', 'same'),
                     'natural-expiry': ('resumed-capture', 'same')},
    assertions_after={'lock-result': 'visible-result'},
)


class GameTimeExtensionChecks:
    def __init__(self, context, progress, plan, *, actions=None, **profile):
        super().__init__(context, progress, plan, actions=actions if actions is not None else {
            **fixture_actions(include_refusal=False, profile='game'),
            'natural-expiry': self.natural_expiry}, **profile)
        self.extended_countdown = None

    def check_estimate(self, observed):
        # The profile owns its zero-daily setup estimate; the later request
        # uses the independent dominance comparison below, rather than a stale
        # unused-child balance. Countdown capture/comparison remains shared.
        pass

    def check_settings(self, stage, observed):
        super().check_settings(stage, observed)
        if stage == 'game-policy':
            observed['comparison'] = check_catalogue(
                AppRowsObservation.from_rows(observed['ui']['apps']['rows']), profile='game')
        if stage == 'countdown':
            require(self.extended_countdown is None, 'game-time-extension:countdown-replay')
            self.extended_countdown = CountdownSample.from_ui(observed['ui'],
                boot_sha256=observed['boot_sha256'])

    def check_request(self, stage, observed):
        super().check_request(stage, observed)
        if stage == 'new-estimate':
            observed['comparison'] = self.check_request_time(
                observed['ui']['valid_choice'], tuple(self.ui.read_bounds), additional_seconds=75)

    @staticmethod
    def natural_expiry(journey, guard):
        require(journey.extended_countdown is not None, 'game-time-extension:missing-countdown')
        return await_natural_expiry(journey, guard, journey.extended_countdown,
            journey.activity_observations['resumed-capture'], maximum_seconds=1500)


class GameTimeExtensionJourney(GameTimeExtensionChecks, DailyDominantProfileJourney,
                               KioskRequestJourney):
    def __init__(self, context, progress, plan=PLAN, *, actions=None):
        super().__init__(context, progress, plan, actions=actions)


FULLSCREEN_PROFILE = {
    **{stage: operation for stage, operation in grant_only_time_profile(
        source='gdm', entry='fresh', window='new', initial_enabled=False, revoke_first=False,
        duration_seconds=600, request_initial='default', daily_minutes=10).items()
       if stage not in ('profile-final-switch', 'profile-final-gdm')},
    'game-apps': 'ui:parent-apps-page', 'game-policy': 'ui:parent-app-rows',
    'profile-final-switch': 'system:parent-switch-user', 'profile-final-gdm': 'ui:gdm-returned',
}
FULLSCREEN_PLAY = {**ENTRY, 'before-countdown': 'ui:child-countdown-present',
    **prefixed_stages('play', {**game_usable_app(level=1, mode='fullscreen'),
                              'capture': 'ui:game-fullscreen-activity'})}
FULLSCREEN_REQUEST = {**overlay_entry('new', 'panel', form_operation='overlay-grant-form'),
                      **{stage: operation for stage, operation in REQUEST.items()
                         if stage not in ('new-launch', 'new-form')},
                      # Fullscreen hides Shell's Activities control. Verify the
                      # child session here; returned-game independently proves
                      # overlay closure and the original fullscreen activity.
                      'returned': 'system:child-desktop-identity'}
FULLSCREEN_FINISH = {**FINISH, 'returned-game': 'ui:game-fullscreen-activity'}
FULLSCREEN_SCREENS = {**FULLSCREEN_PROFILE, **FULLSCREEN_PLAY,
                      **FULLSCREEN_REQUEST, **FULLSCREEN_FINISH}
FULLSCREEN_PLAN = replace(PLAN, worker_mode='game_time_extension_fullscreen',
    screen_tags=FULLSCREEN_SCREENS,
    phases={'ready': 'setup', 'setup-detached': 'setup',
        **{stage: phase for phase, screens in (
            ('step-1', {**FULLSCREEN_PROFILE, **FULLSCREEN_PLAY}),
            ('step-2', FULLSCREEN_REQUEST), ('step-3', FULLSCREEN_FINISH)) for stage in screens},
        'installed-greeter': 'start'},
    invocations=tuple(stage for stage in FULLSCREEN_SCREENS if stage in LOGIN_STAGES
        or stage in ('new-panel', 'new-launch', 'new-form',
                     'natural-expiry', 'lock-input-ready', 'lock-result')),
    settings_checks={},
    child_bindings={stage: 'child' for stage, tag in FULLSCREEN_SCREENS.items()
                    if tag.removeprefix('ui:') in GAME_OPERATIONS})


class GrantDominantGameTimeExtensionJourney(GameTimeExtensionChecks, GrantOnlyProfileJourney,
                                           KioskRequestJourney):
    def __init__(self, context, progress, plan=FULLSCREEN_PLAN, *, actions=None):
        super().__init__(context, progress, plan, actions=actions,
                         daily_minutes=10, grant_seconds=600)
        self.parent_balance = None

    def check_settings(self, stage, observed):
        super().check_settings(stage, observed)
        if stage == 'profile-balance':
            balance = observed['ui']['revoke_cancel']['balances']
            daily, grant = (balance[key]['seconds'] for key in ('daily', 'one_time'))
            precision = max(balance[key]['precision_seconds'] for key in ('daily', 'one_time'))
            require(daily - precision >= 300 and grant - daily - 2 * precision > 90,
                    'game-time-extension:grant-dominant-parent')
            self.parent_balance = (deepcopy(balance), tuple(self.ui.read_bounds))

    def check_request_time(self, choice, bounds, *, additional_seconds):
        require(self.parent_balance is not None, 'game-time-extension:missing-parent-balance')
        balance, earlier = self.parent_balance
        low, high = DailyDominantProfileJourney.elapsed(earlier, bounds)
        daily, grant = (balance[key]['seconds'] for key in ('daily', 'one_time'))
        precision = max(balance[key]['precision_seconds'] for key in ('daily', 'one_time')) + 2
        request = choice['request']
        require(request['child'] == balance['child']
                and request['duration_seconds'] == additional_seconds
                and choice['estimate']['kind'] == 'fixed',
                'game-time-extension:grant-dominant-request-binding')
        daily_low, grant_low = daily - high - precision, grant - high - precision
        daily_high, grant_high = daily + precision, grant - low + precision
        base = choice['estimate']['seconds'] - additional_seconds
        require(daily_low >= 300 and grant_low >= 300 and grant_low - daily_high > 90
                and grant_low <= base <= grant_high
                and base - choice['estimate']['precision_seconds'] - daily_high > 90,
                'game-time-extension:grant-dominant-request')
        return {'grant_dominant_at_request': True, 'elapsed_interval_seconds': [low, high],
                'original_daily_lower_seconds': daily_low,
                'original_grant_lower_seconds': grant_low,
                'original_grant_upper_seconds': grant_high, 'estimate_base_seconds': base}


def execute(recorder, context):
    from e2e_fixture_preparation import GAME_SUBSETS
    context.fixture_subsets = GAME_SUBSETS
    context.fixture_caller = 'E2E-024/daily-dominant-windowed'
    record_installed_journey(recorder, context, PLAN, timeout=3600,
                             journey_type=GameTimeExtensionJourney)


def execute_fullscreen(recorder, context):
    from e2e_fixture_preparation import GAME_SUBSETS
    context.fixture_subsets = GAME_SUBSETS
    context.fixture_caller = 'E2E-024/grant-dominant-fullscreen'
    record_installed_journey(recorder, context, FULLSCREEN_PLAN, timeout=3600,
                             journey_type=GrantDominantGameTimeExtensionJourney)


E2E_CASES = {'daily-dominant-windowed': execute, 'grant-dominant-fullscreen': execute_fullscreen}
