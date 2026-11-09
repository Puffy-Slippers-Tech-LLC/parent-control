"""Case 126: approved windowed play, natural expiry and the same game recovered."""
from accessible_ui import KIOSK_BOUND_OPERATIONS, NAMED_CHILD_OPERATIONS
from game_expiry import CHOICES, GameExpiryJourney
from installed_journey import JourneyPlan, record_installed_journey
from journey_blocks import (desktop_entry, fresh_desktop, game_usable_app,
                            parent_management, prefixed_stages, rejected_gdm_return)
from kiosk_approved_flow import obtain_time
from native_fixtures import check_catalogue
from private_artifacts import require
from request_flow import approval_and_return
from ui_observations import AppRowsObservation, SettingsObservation


SETUP = {**fresh_desktop('parent'), **parent_management(child='existing'),
         'profile-before': 'ui:revoke-balances',
         'allowance-configured': 'ui:time-explanation-setup-zero-read',
         'saved-settings': 'ui:existing-returned', 'apps-page': 'ui:existing-apps',
         'game-policy': 'ui:existing-parent-app-rows', 'parent-logout': 'system:parent-logout'}
DENIAL = {**prefixed_stages('denied', desktop_entry(
    'other-child', source='gdm', entry='fresh', expected='time-denied')),
    **prefixed_stages('initial', rejected_gdm_return())}
REQUEST = prefixed_stages('request', obtain_time(initial='observed', **CHOICES, exit='automatic'))
ENTRY = prefixed_stages('jordan-entry', desktop_entry('other-child', source='gdm', entry='fresh'))
PLAY = {**ENTRY, 'initial-countdown': 'ui:child-countdown-present',
        **prefixed_stages('play', {**game_usable_app(level=1, mode='windowed'),
                                  'capture': 'ui:game-activity'})}
EXHAUSTION = {'natural-expiry': 'ui:game-activity',
              'lock-input-ready': 'ui:child-natural-expiry-lock-ready',
              'lock-result': 'ui:child-natural-expiry-lock-result'}
RECOVERY_FLOW = prefixed_stages('recovery', approval_and_return(
    prefix='new', entry='new', **{**CHOICES, 'duration_seconds': 1200},
    surface='kiosk', child_entry='retained'))
RECOVERY = {'curtain': 'ui:child-lock-curtain', 'reveal-ready': 'ui:child-lock-reveal-ready',
            'time-denied': 'ui:child-lock-time-denied',
            'return-greeter': 'system:standard-return-greeter', 'denied-returned': 'ui:gdm-returned',
            **RECOVERY_FLOW, 'returned-game': 'ui:game-activity',
            'resume': 'ui:game-resume', 'resumed': 'ui:game-resumed'}
SCREENS = {**SETUP, **DENIAL, **REQUEST, **PLAY, **EXHAUSTION, **RECOVERY}
LOGIN_STAGES = {*fresh_desktop('parent'),
    *prefixed_stages('denied', fresh_desktop('other-child', 'time-denied')),
    *ENTRY, *prefixed_stages('recovery-retained', fresh_desktop('other-child'))}
PLAN = JourneyPlan(
    prefix='game-access', worker_mode='game_access', screen_tags=SCREENS,
    phases={'ready': 'setup', 'setup-detached': 'setup',
        **{stage: phase for phase, screens in (
            ('step-1', SETUP), ('step-2', DENIAL), ('step-3', REQUEST),
            ('step-4', PLAY), ('step-5', EXHAUSTION), ('step-6', RECOVERY)) for stage in screens},
        'installed-greeter': 'start'},
    advance_after={'parent-logout': 'step-2', 'initial-denied-returned': 'step-3',
                   'request-new-returned': 'step-4', 'play-capture': 'step-5', 'lock-result': 'step-6'},
    invocations=tuple(stage for stage in SCREENS if (stage in LOGIN_STAGES
        and not stage.endswith('entry-guard')) or stage in prefixed_stages('initial', rejected_gdm_return())
        or stage in ('initial-countdown', *EXHAUSTION)),
    challenges={'parent-login': ('parent', 'recipient-qualified', 'recipient-rechecked'),
        **{name: ('other-child', name + '-standard-recipient-qualified',
                  name + '-standard-recipient-rechecked')
           for name in ('denied', 'jordan-entry', 'recovery-retained')}},
    stage_actions={'desktop': 'native-verify', 'natural-expiry': 'natural-expiry'},
    child_bindings={stage: 'existing' for stage, tag in SCREENS.items()
                    if tag.startswith('ui:') and tag[3:] in NAMED_CHILD_OPERATIONS},
    settings_checks={'parent-selected': SettingsObservation('existing-fixture-child', False, ('0 minutes',)),
                     'saved-settings': SettingsObservation('existing-fixture-child', True, ('0 minutes',))},
    balance_checks={'allowance-configured': 0},
    countdown_checks={'initial-countdown': ('request-new-estimate', 600, 1, 300),
                      'recovery-countdown': ('recovery-new-estimate', 1200, 1, 300)},
    kiosk_request=('other-child', 'parent', 600, True),
    kiosk_requests={stage: ('other-child', 'parent', 1200, True)
                    for stage, tag in RECOVERY_FLOW.items() if tag[3:] in KIOSK_BOUND_OPERATIONS},
    activity_entries={'natural-expiry': 'play-capture',
                      'recovery-retained-entry-guard': 'play-capture'},
    activity_checks={stage: ('play-capture', 'same') for stage in ('natural-expiry', 'returned-game')},
    assertions_after={'resumed': 'visible-result'},
)


class GameAccessJourney(GameExpiryJourney):
    def __init__(self, context, progress, plan=PLAN, *, actions=None):
        super().__init__(context, progress, plan, actions=actions)

    def check_estimate(self, observed):
        choice = observed.get('ui', {}).get('valid_choice')
        if choice is None or choice['request']['duration_seconds'] != 1200:
            return super().check_estimate(observed)
        # The original zero-daily profile and independently observed natural
        # expiry establish exhausted time. Its old Parent balance is stale;
        # this fresh public request must offer exactly the replacement interval.
        require(self.natural_expiry_result is not None
                and choice['request']['child'] == 'existing-fixture-child'
                and choice['estimate']['kind'] == 'fixed' and choice['estimate']['seconds'] == 1200,
                'game-access:replacement-estimate')
        observed.setdefault('comparison', {})['replacement_time_after_natural_expiry'] = True

    def check_settings(self, stage, observed):
        super().check_settings(stage, observed)
        if stage == 'game-policy':
            observed['comparison'] = check_catalogue(
                AppRowsObservation.from_rows(observed['ui']['apps']['rows']), profile='game')
        if stage == 'time-denied':
            require(self.natural_expiry_result is not None
                    and observed['ui']['lock']['surface_id'] ==
                        self.natural_expiry_result['lock']['surface_id'], 'game-access:changed-expired-lock')


def execute(recorder, context):
    from e2e_fixture_preparation import GAME_SUBSETS
    context.fixture_subsets = GAME_SUBSETS
    context.fixture_caller = 'E2E-023/windowed'
    record_installed_journey(recorder, context, PLAN, timeout=3600, journey_type=GameAccessJourney)


E2E_CASES = {'windowed': execute}
