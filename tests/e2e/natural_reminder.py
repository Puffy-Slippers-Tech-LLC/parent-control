"""311b: Riley receives the saved warning while using real approved time."""

from copy import deepcopy

from grant_only_profile import GrantOnlyProfileJourney
from installed_journey import JourneyPlan
from journey_blocks import fresh_desktop, grant_only_time_profile, native_activity_entry, prefixed_stages
from native_fixtures import fixture_actions
from private_artifacts import require


SCREENS = {
    **grant_only_time_profile(source='gdm', entry='fresh', window='new',
        initial_enabled=False, revoke_first=False, duration_seconds=600,
        request_initial='default', balance_readback=False),
    'profile-balance': 'ui:revoke-balances',
    **prefixed_stages('fresh', fresh_desktop('child')),
    **native_activity_entry('activity', child='child'),
    'natural-reminder': 'ui:child-countdown-present',
}
LOGIN_STAGES = set(fresh_desktop('parent')) | set(prefixed_stages('fresh', fresh_desktop('child')))
PLAN = JourneyPlan(
    prefix='natural-reminder', worker_mode='natural_reminder', screen_tags=SCREENS,
    phases={'ready': 'setup', 'setup-detached': 'setup',
            **{stage: 'step-1' for stage in SCREENS}, 'installed-greeter': 'start'},
    invocations=tuple(stage for stage in SCREENS if stage in LOGIN_STAGES or stage == 'natural-reminder'),
    challenges={
        'parent-login': ('parent', 'recipient-qualified', 'recipient-rechecked'),
        'child-login': ('child', 'fresh-child-recipient-qualified', 'fresh-child-recipient-rechecked')},
    stage_actions={'desktop': 'native-verify',
                   'profile-request-new-estimate': 'prepare-reminder',
                   'natural-reminder': 'observe-reminder'},
    assertions_after={'profile-balance': 'real-ten-minute-grant',
                      'activity-capture': 'usable-native-work',
                      'natural-reminder': 'natural-warning-and-removal'},
)


class NaturalReminderJourney(GrantOnlyProfileJourney):
    def __init__(self, context, progress, plan=PLAN, *, fullscreen=True, actions=None):
        super().__init__(context, progress, plan, grant_seconds=600,
                         actions=actions if actions is not None else {**fixture_actions(include_refusal=False),
                                  'prepare-reminder': self.prepare_reminder,
                                  'observe-reminder': self.observe_reminder})
        self.saved_reminder = None
        self.saved_preferences = None
        self.fullscreen_preference = fullscreen

    @staticmethod
    def prepare_reminder(journey, guard):
        guard()
        require(journey.saved_reminder is None, 'natural-reminder:preparation-replay')
        def observe(action):
            guard()
            result = journey.ui.observe('binding-reminder-riley-' + action)
            guard()
            return result.get('reminders')

        # Keep each public operation inside its own existing command budget;
        # the worker's single checkpoint deadline still bounds the composition.
        # No time grant is issued until independent saved-state readback finishes.
        observe('open')
        observe('delete-all')
        draft = observe('create-warning')
        require(draft['show_in_fullscreen'] is True, 'natural-reminder:fullscreen')
        if journey.fullscreen_preference is False:
            draft = observe('fullscreen-false')
        observe('save')
        value = observe('open')
        require(value['records'] == draft['records'] and value['language'] == draft['language'],
                'natural-reminder:saved-readback')
        require(len(value['records']) == 1 and value['show_in_fullscreen'] is journey.fullscreen_preference,
                'natural-reminder:saved-preferences')
        row = value['records'][0]
        require(row == {'id': row['id'], 'value': 30, 'unit': 'second',
                        'text': 'Save your game now'}, 'natural-reminder:saved-record')
        observe('cancel')
        journey.saved_reminder = deepcopy(row)
        journey.saved_preferences = {key: deepcopy(value[key])
                                     for key in ('records', 'language', 'show_in_fullscreen')}
        journey.ui.natural_reminder_record = deepcopy(row)
        guard()
        return value

    @staticmethod
    def observe_reminder(journey, guard):
        guard()
        require(journey.saved_reminder is not None and 'activity-capture' in journey.activity_observations,
                'natural-reminder:entry')
        result = journey.ui.observe('child-natural-reminder-wait')['natural_reminder']
        guard()
        initial, emitted = result['initial'], result['emission']
        require(result['record'] == journey.saved_reminder and initial['seconds'] >= 300
                and emitted['body'] == journey.saved_reminder['text']
                and emitted['urgency'] == 'critical'
                and 0 < emitted['seconds'] <= journey.saved_reminder['value'],
                'natural-reminder:content-and-live-balance')
        elapsed = [(emitted['read_bounds'][0] - initial['read_bounds'][1]) / 1e9,
                   (emitted['read_bounds'][1] - initial['read_bounds'][0]) / 1e9]
        crossing = initial['seconds'] - journey.saved_reminder['value']
        require(crossing - 2 <= elapsed[1] and elapsed[0] < crossing + 15,
                'natural-reminder:natural-crossing')
        lock_elapsed = [(result['lock_read_bounds'][0] - initial['read_bounds'][1]) / 1e9,
                        (result['lock_read_bounds'][1] - initial['read_bounds'][0]) / 1e9]
        require(initial['seconds'] - 2 <= lock_elapsed[1]
                and lock_elapsed[0] < initial['seconds'] + 15 and result['removed'] is True,
                'natural-reminder:natural-lock-removal')
        return result
