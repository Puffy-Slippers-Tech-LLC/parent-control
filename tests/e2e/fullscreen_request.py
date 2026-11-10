"""129a: open and cancel a panel request without losing fullscreen play."""
from accessible_ui import GAME_OPERATIONS
from installed_journey import JourneyPlan
from journey_blocks import app_policy_entry, desktop_entry, game_usable_app, overlay_entry, prefixed_stages
from native_fixtures import fixture_actions
from policy_edits import AppPolicyJourney
from ui_observations import SettingsObservation


SETUP = app_policy_entry(child='existing', allowance='time-explanation-setup-thirty-read',
                         initial_rows=False)
ENTRY = prefixed_stages('jordan-entry', desktop_entry('other-child', source='gdm', entry='fresh'))
PLAY = {**game_usable_app(level=1, mode='fullscreen'),
        'capture': 'ui:game-fullscreen-activity',
        **overlay_entry('request', 'panel'),
        'cancel': 'ui:overlay-request-cancel',
        'returned': 'system:standard-desktop-identity',
        'game': 'ui:game-fullscreen-activity',
        'resume': 'ui:game-resume', 'resumed': 'ui:game-resumed',
        'close': 'ui:game-resumed-close', 'closed': 'ui:game-closed'}
SCREENS = {**SETUP, 'parent-logout': 'system:parent-logout', **ENTRY,
           'wrong-window': 'ui:game-wrong-window',
           **prefixed_stages('first', PLAY), **prefixed_stages('independent', PLAY)}
PLAN = JourneyPlan(
    prefix='fullscreen-request', worker_mode='fullscreen_request', screen_tags=SCREENS,
    phases={'ready': 'setup', 'setup-detached': 'setup',
            **{stage: 'step-1' for stage in SETUP}, 'installed-greeter': 'start',
            **{stage: 'step-2' for stage in SCREENS if stage not in SETUP}},
    advance_after={'apps-page': 'step-2'},
    stage_actions={'desktop': 'native-verify'},
    child_bindings={stage: 'existing' for stage, operation in SCREENS.items()
                    if stage == 'allowance-configured' or operation.removeprefix('ui:') in GAME_OPERATIONS},
    settings_checks={
        'parent-selected': SettingsObservation('existing-fixture-child', False, ('0 minutes',)),
        'saved-settings': SettingsObservation('existing-fixture-child', True, ('30 minutes',))},
    balance_checks={'allowance-configured': 1800},
    overlay_request=('other-child', 'parent', 75, False),
    invocations=tuple(stage for stage in SCREENS if stage in ENTRY and not stage.endswith('entry-guard')
                      or stage.endswith(('request-panel', 'request-launch', 'request-form'))),
    challenges={'jordan-entry': ('other-child', 'jordan-entry-standard-recipient-qualified',
                                 'jordan-entry-standard-recipient-rechecked')},
    activity_checks={
        'first-game': ('first-capture', 'same'),
        'independent-capture': ('first-capture', 'replaced'),
        'independent-game': ('independent-capture', 'same')},
)


class FullscreenRequestJourney(AppPolicyJourney):
    def __init__(self, context, progress):
        super().__init__(context, progress, PLAN,
                         actions=fixture_actions(include_refusal=False, profile='game'))
