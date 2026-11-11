"""311c: Riley's current warning follows the saved fullscreen preference."""
from copy import deepcopy

from installed_journey import JourneyPlan
from journey_blocks import fresh_desktop, grant_only_time_profile, parent_management, prefixed_stages
from natural_reminder import NaturalReminderJourney
from native_fixtures import fixture_actions
from private_artifacts import require
from request_flow import prepared_request


SCREENS = {
    **grant_only_time_profile(source='gdm', entry='fresh', window='new',
        initial_enabled=False, revoke_first=False, duration_seconds=600,
        request_initial='default', balance_readback=False),
    'profile-balance': 'ui:revoke-balances',
    'policy-before': 'ui:overlay-language-policy',
    **prefixed_stages('fresh', fresh_desktop('child')),
    'natural-reminder': 'ui:child-countdown-present',
    'child-logout': 'system:child-logout', 'child-logged-out': 'ui:gdm-returned',
    **prefixed_stages('return', fresh_desktop('parent')),
    **prefixed_stages('return', parent_management()),
    'policy-after': 'ui:overlay-language-policy',
    'parent-switch': 'system:parent-switch-user', 'parent-gdm': 'ui:gdm-returned',
    **prepared_request(prefix='new', entry='new', initial='observed',
        child='fixture-child', approver='fixture-parent', duration_seconds=600, allow_soft=True),
    'saved-reminder-check': 'ui:kiosk-request-estimate',
    'cancel': 'ui:kiosk-request-cancel', 'returned': 'ui:gdm-station-returned',
}
LOGIN_STAGES = set(fresh_desktop('parent')) | {
    prefix + stage for prefix, role in (('fresh-', 'child'), ('return-', 'parent'))
    for stage in fresh_desktop(role)}
PLAN = JourneyPlan(prefix='natural-reminder', worker_mode='fullscreen_reminder', screen_tags=SCREENS,
    phases={'ready': 'setup', 'setup-detached': 'setup',
            **{stage: 'step-1' for stage in SCREENS}, 'installed-greeter': 'start'},
    invocations=tuple(stage for stage in SCREENS if stage in LOGIN_STAGES or stage == 'natural-reminder'),
    challenges={
        'parent-login': ('parent', 'recipient-qualified', 'recipient-rechecked'),
        'child-login': ('child', 'fresh-child-recipient-qualified', 'fresh-child-recipient-rechecked'),
        'return-parent': ('parent', 'return-recipient-qualified', 'return-recipient-rechecked')},
    kiosk_request=('child', 'parent', 600, True),
    stage_actions={'desktop': 'native-verify',
                   'profile-request-new-estimate': 'prepare-reminder',
                   'natural-reminder': 'observe-fullscreen-reminder',
                   'saved-reminder-check': 'verify-saved-reminder'},
    assertions_after={'profile-balance': 'real-ten-minute-grant',
                      'natural-reminder': 'owned-fullscreen-banner',
                      'policy-after': 'unchanged-policy',
                      'saved-reminder-check': 'unchanged-saved-reminder'},
)


class FullscreenReminderJourney(NaturalReminderJourney):
    def __init__(self, context, progress, *, fullscreen):
        super().__init__(context, progress, PLAN, fullscreen=fullscreen, actions={
            **fixture_actions(include_refusal=False, profile='game'),
            'prepare-reminder': self.prepare_reminder,
            'observe-fullscreen-reminder': self.observe_fullscreen_reminder,
            'verify-saved-reminder': self.verify_saved_reminder})
        self.policy_before = None

    def check_settings(self, stage, observed):
        super().check_settings(stage, observed)
        if stage not in ('policy-before', 'policy-after'):
            return
        policy = observed['ui']['language_policy']
        saved = {key: policy[key] for key in ('settings', 'rows')}
        require(saved['settings'] == {'child': 'fixture-child', 'limit_enabled': True,
                                     'allowance': ['0 minutes']}, 'fullscreen-reminder:daily-policy')
        require(policy['balances']['daily'] == 0
                and policy['balances']['total'] == policy['balances']['one_time'],
                'fullscreen-reminder:grant-only-policy')
        if stage == 'policy-before':
            self.policy_before = deepcopy(saved)
        else:
            require(self.policy_before == saved, 'fullscreen-reminder:changed-policy')

    @staticmethod
    def observe_fullscreen_reminder(journey, guard):
        guard()
        require(journey.saved_reminder is not None, 'fullscreen-reminder:missing-preparation')
        operation = ('child-fullscreen-reminder-visible' if journey.fullscreen_preference
                     else 'child-fullscreen-reminder-suppressed')
        result = journey.ui.observe(operation)['natural_reminder']
        guard()
        initial, emitted = result['initial'], result['emission']
        require(result['record'] == journey.saved_reminder and initial['seconds'] >= 300
                and emitted['body'] == journey.saved_reminder['text']
                and emitted['urgency'] == ('critical' if journey.fullscreen_preference else 'high')
                and result['visible'] is journey.fullscreen_preference
                and result['delivery_id'] == emitted['delivery_id']
                and result['game_usable_moves'] == 2,
                'fullscreen-reminder:independent-visibility')
        elapsed = [(emitted['read_bounds'][0] - initial['read_bounds'][1]) / 1e9,
                   (emitted['read_bounds'][1] - initial['read_bounds'][0]) / 1e9]
        crossing = initial['seconds'] - journey.saved_reminder['value']
        require(crossing - 2 <= elapsed[1] and elapsed[0] < crossing + 15,
                'fullscreen-reminder:natural-crossing')
        require(result['visibility_read_bounds'][1] <
                emitted['read_bounds'][0] + emitted['seconds'] * 1_000_000_000,
                'fullscreen-reminder:original-warning-lifetime')
        return result

    @staticmethod
    def verify_saved_reminder(journey, guard):
        guard()
        result = journey.ui.observe('binding-reminder-riley-open')['reminders']
        require({key: result[key] for key in journey.saved_preferences} == journey.saved_preferences,
                'fullscreen-reminder:changed-saved-preferences')
        journey.ui.observe('binding-reminder-riley-cancel')
        guard()
        return result
