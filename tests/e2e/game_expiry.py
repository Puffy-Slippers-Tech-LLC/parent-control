"""APP05/FLOW10: Jordan plays the windowed level, then time expires naturally."""
from countdown import CountdownSample
from installed_journey import JourneyPlan
from journey_blocks import (desktop_entry, fresh_desktop, game_usable_app,
                            parent_management, prefixed_stages)
from journey_checks import require_zero_grant
from kiosk_approved_flow import obtain_time
from native_fixtures import fixture_actions
from natural_expiry_observation import await_natural_expiry
from private_artifacts import require
from request_flow import RequestFlowJourney
from ui_observations import SettingsObservation


CHOICES = dict(child='existing-fixture-child', approver='fixture-parent',
               duration_seconds=600, allow_soft=True)
SETUP = {**fresh_desktop('parent'), **parent_management(child='existing'),
         'profile-before': 'ui:revoke-balances',
         'allowance-configured': 'ui:time-explanation-setup-zero-read',
         'saved-settings': 'ui:existing-returned', 'parent-logout': 'system:parent-logout'}
REQUEST = prefixed_stages('request', obtain_time(initial='observed', **CHOICES, exit='automatic'))
ENTRY = prefixed_stages('jordan-entry', desktop_entry('other-child', source='gdm', entry='fresh'))
PLAY = {**game_usable_app(level=1, mode='windowed'), 'capture': 'ui:game-activity'}
EXHAUSTION = {'natural-expiry': 'ui:game-activity',
              'lock-input-ready': 'ui:child-natural-expiry-lock-ready',
              'lock-result': 'ui:child-natural-expiry-lock-result'}
SCREENS = {**SETUP, **REQUEST, **ENTRY, 'initial-countdown': 'ui:child-countdown-present',
           **prefixed_stages('first', {**PLAY, 'close': 'ui:game-close', 'closed': 'ui:game-closed'}),
           **prefixed_stages('independent', PLAY), **EXHAUSTION}
PLAN = JourneyPlan(
    prefix='game-expiry', worker_mode='game_expiry', screen_tags=SCREENS,
    phases={'ready': 'setup', 'setup-detached': 'setup',
            **{stage: 'step-1' for stage in SETUP}, 'installed-greeter': 'start',
            **{stage: 'step-2' for stage in REQUEST},
            **{stage: 'step-3' for stage in SCREENS if stage not in SETUP and stage not in REQUEST}},
    advance_after={'parent-logout': 'step-2', 'request-new-returned': 'step-3'},
    stage_actions={'desktop': 'native-verify', 'natural-expiry': 'natural-expiry'},
    child_bindings={stage: 'existing' for stage in (
        'profile-before', 'allowance-configured', 'initial-countdown', 'lock-input-ready', 'lock-result')},
    settings_checks={'parent-selected': SettingsObservation('existing-fixture-child', False, ('0 minutes',)),
                     'saved-settings': SettingsObservation('existing-fixture-child', True, ('0 minutes',))},
    balance_checks={'allowance-configured': 0},
    countdown_checks={'initial-countdown': ('request-new-estimate', 600, 1, 300)},
    kiosk_request=('other-child', 'parent', 600, True),
    invocations=tuple(stage for stage in SCREENS if stage in fresh_desktop('parent')
                      or stage in ENTRY and not stage.endswith('entry-guard')
                      or stage in ('initial-countdown', *EXHAUSTION)),
    challenges={'parent-login': ('parent', 'recipient-qualified', 'recipient-rechecked'),
                'jordan-entry': ('other-child', 'jordan-entry-standard-recipient-qualified',
                                 'jordan-entry-standard-recipient-rechecked')},
    activity_entries={'natural-expiry': 'independent-capture'},
    activity_checks={'independent-capture': ('first-capture', 'replaced'),
                     'natural-expiry': ('independent-capture', 'same')},
)


class GameExpiryJourney(RequestFlowJourney):
    def __init__(self, context, progress, plan=PLAN, *, actions=None):
        super().__init__(context, progress, plan, actions=actions if actions is not None else {
            **fixture_actions(include_refusal=False, profile='game'),
            'natural-expiry': self.natural_expiry})
        self.initial_countdown = None
        self.natural_expiry_result = None

    def check_settings(self, stage, observed):
        super().check_settings(stage, observed)
        if stage == 'profile-before':
            require_zero_grant(observed['ui']['revoke_cancel']['balances'])
        if stage == 'initial-countdown':
            require(self.initial_countdown is None, 'game-expiry:countdown-replay')
            self.initial_countdown = CountdownSample.from_ui(observed['ui'],
                boot_sha256=observed['boot_sha256'], child='existing-fixture-child')

    @staticmethod
    def natural_expiry(journey, guard):
        require(journey.initial_countdown is not None and journey.natural_expiry_result is None,
                'game-expiry:missing-or-replayed-entry')
        result = await_natural_expiry(journey, guard, journey.initial_countdown,
            journey.activity_observations[journey.plan.activity_entries['natural-expiry']],
            maximum_seconds=600, child='existing')
        journey.natural_expiry_result = result
        return result
