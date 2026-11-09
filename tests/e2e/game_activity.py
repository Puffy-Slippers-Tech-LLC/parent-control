"""126a: a child opens the prepared offline level and retains recognizable play."""
from installed_journey import JourneyPlan
from policy_edits import AppPolicyJourney
from journey_blocks import app_policy_entry, desktop_entry, game_usable_app, prefixed_stages
from native_fixtures import fixture_actions
from ui_observations import SettingsObservation


SETUP = app_policy_entry(child='existing', allowance='time-explanation-setup-thirty-read',
                         initial_rows=False)
ENTRY = prefixed_stages('jordan-entry', desktop_entry('other-child', source='gdm', entry='fresh'))
PLAY = {**game_usable_app(level=1), 'capture': 'ui:game-activity',
        'reread': 'ui:game-activity', 'close': 'ui:game-close', 'closed': 'ui:game-closed'}
SCREENS = {**SETUP, 'parent-logout': 'system:parent-logout', **ENTRY,
           'wrong-window': 'ui:game-wrong-window',
           **prefixed_stages('first', PLAY),
           **prefixed_stages('independent', PLAY)}
PLAN = JourneyPlan(
    prefix='game-activity', worker_mode='game_activity', screen_tags=SCREENS,
    phases={'ready': 'setup', 'setup-detached': 'setup', 'installed-greeter': 'start',
            **{stage: 'step-1' for stage in SETUP if stage != 'installed-greeter'},
            **{stage: 'step-2' for stage in SCREENS if stage not in SETUP}},
    advance_after={'installed-greeter': 'step-1', 'apps-page': 'step-2'},
    stage_actions={'desktop': 'native-verify'},
    child_bindings={'allowance-configured': 'existing'},
    settings_checks={
        'parent-selected': SettingsObservation('existing-fixture-child', False, ('0 minutes',)),
        'saved-settings': SettingsObservation('existing-fixture-child', True, ('30 minutes',))},
    balance_checks={'allowance-configured': 1800},
    invocations=tuple(stage for stage in ENTRY if not stage.endswith('entry-guard')),
    challenges={'jordan-entry': ('other-child', 'jordan-entry-standard-recipient-qualified',
                                 'jordan-entry-standard-recipient-rechecked')},
    activity_checks={'first-reread': ('first-capture', 'same'),
                     'independent-capture': ('first-capture', 'replaced'),
                     'independent-reread': ('independent-capture', 'same')},
)


class GameActivityJourney(AppPolicyJourney):
    def __init__(self, context, progress):
        super().__init__(context, progress, PLAN,
                         actions=fixture_actions(include_refusal=False, profile='game'))
