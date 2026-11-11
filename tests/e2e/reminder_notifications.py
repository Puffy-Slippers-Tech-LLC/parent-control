"""Case 266: independent saved warnings during play, renewal and reboot."""
from copy import deepcopy

from installed_journey import InstalledJourney, JourneyPlan, record_installed_journey
from journey_blocks import (fresh_desktop, parent_management, custom_child_selection,
                            desktop_entry, native_activity_entry, prefixed_stages)
from kiosk_approved_flow import obtain_time
from native_fixtures import fixture_actions
from overlay_reminders import DEFAULTS
from private_artifacts import require


SCREENS = {
    **fresh_desktop('parent'), **parent_management(),
    'riley-zero': 'ui:time-explanation-setup-zero-read',
    'riley-policy-before': 'ui:overlay-language-policy',
    **custom_child_selection('jordan', 'existing'),
    'jordan-zero': 'ui:time-explanation-setup-zero-read',
    'jordan-policy-before': 'ui:kiosk-language-policy',
    'parent-logout': 'system:parent-logout', 'parent-greeter': 'ui:gdm-returned',
}
LOGINS = {'': 'parent'}
ACTIONS = {'desktop': 'native-verify', 'first-new-estimate': 'prepare-defaults',
           'enabled-new-estimate': 'prepare-custom',
           'disabled-new-estimate': 'disable-fullscreen',
           'after-new-estimate': 'check-persistence',
           'persistence-new-estimate': 'save-final-preferences'}
for name, seconds, entry in (('first', 240, 'fresh'), ('enabled', 600, 'retained'),
                             ('disabled', 600, 'retained')):
    SCREENS.update(prefixed_stages(name, obtain_time(initial='observed',
        child='fixture-child', approver='fixture-parent', duration_seconds=seconds,
        allow_soft=True, exit='automatic')))
    prefix = name + '-child'
    LOGINS[prefix] = 'child'
    SCREENS.update(prefixed_stages(prefix, desktop_entry('child', source='gdm', entry=entry)))
    if name == 'first':
        SCREENS.update(native_activity_entry('activity', child='child'))
    SCREENS.update({name + '-warning': 'ui:child-countdown-present',
                    name + '-leave-lock': 'system:child-return-greeter',
                    name + '-greeter': 'ui:gdm-returned'})
    ACTIONS[name + '-warning'] = 'observe-' + name

# Save independent final choices before reboot, without another grant.
SCREENS.update(prefixed_stages('persistence', obtain_time(initial='observed',
    child='fixture-child', approver='fixture-parent', duration_seconds=600,
    allow_soft=True, exit='automatic')))
for stage in tuple(SCREENS):
    if stage.startswith('persistence-approval-') or stage == 'persistence-new-returned':
        del SCREENS[stage]
SCREENS.update({'persistence-cancel': 'ui:kiosk-request-cancel',
                'persistence-returned': 'ui:gdm-station-returned',
                **prefixed_stages('reboot-parent', fresh_desktop('parent')),
                'reboot-requested': 'system:parent-desktop-identity',
                'reboot-greeter': 'ui:gdm-list'})
LOGINS['reboot-parent'] = 'parent'
SCREENS.update(prefixed_stages('after', obtain_time(initial='observed',
    child='fixture-child', approver='fixture-parent', duration_seconds=600,
    allow_soft=True, exit='automatic')))
SCREENS.update({**prefixed_stages('after-child', desktop_entry('child', source='gdm', entry='fresh')),
    'after-warning': 'ui:child-countdown-present',
    'after-leave-lock': 'system:child-return-greeter', 'after-greeter': 'ui:gdm-returned',
    **prefixed_stages('return', fresh_desktop('parent')),
    **prefixed_stages('return', parent_management()),
    'riley-policy-after': 'ui:overlay-language-policy',
    **custom_child_selection('jordan-final', 'existing'),
    'jordan-policy-after': 'ui:kiosk-language-policy',
    'final-logout': 'system:parent-logout', 'final-greeter': 'ui:gdm-returned'})
LOGINS.update({'after-child': 'child', 'return': 'parent'})
ACTIONS['after-warning'] = 'observe-after'
LOGIN_STAGES = {(prefix + '-' if prefix else '') + stage
                for prefix, role in LOGINS.items() for stage in fresh_desktop(role)}
PLAN = JourneyPlan(prefix='reminder-notifications', worker_mode='reminder_notifications',
    screen_tags=SCREENS,
    phases={'ready': 'setup', 'setup-detached': 'setup',
            **{stage: 'step-1' for stage in SCREENS}, 'installed-greeter': 'start'},
    invocations=tuple(stage for stage in SCREENS if stage in LOGIN_STAGES),
    challenges={(prefix or 'parent-login'): (role,
        (prefix + '-' if prefix else '') + ('child-recipient-qualified' if role == 'child' else 'recipient-qualified'),
        (prefix + '-' if prefix else '') + ('child-recipient-rechecked' if role == 'child' else 'recipient-rechecked'))
        for prefix, role in LOGINS.items()},
    child_bindings={'jordan-zero': 'existing'},
    kiosk_request=('child', 'parent', 600, True),
    kiosk_requests={stage: ('child', 'parent', 240, True) for stage, tag in SCREENS.items()
                    if stage.startswith('first-') and tag[3:] in (
                        'kiosk-request-select', 'kiosk-request-estimate',
                        'kiosk-bound-mate-open', 'kiosk-bound-mate-qualified',
                        'kiosk-bound-mate-rechecked', 'kiosk-bound-mate-submit-success')},
    reboot_transition=('reboot-requested', 'reboot-greeter'), stage_actions=ACTIONS)


class ReminderNotificationsJourney(InstalledJourney):
    def __init__(self, context, progress, plan=PLAN, *, actions=None):
        super().__init__(context, progress, plan, actions={
            **fixture_actions(include_refusal=False, profile='game'),
            'prepare-defaults': self.prepare_defaults, 'prepare-custom': self.prepare_custom,
            'disable-fullscreen': self.disable_fullscreen,
            'save-final-preferences': self.save_final_preferences,
            'check-persistence': self.check_persistence,
            **{'observe-' + name: self.observer(name) for name in ('first', 'enabled', 'disabled', 'after')}})
        self.policies, self.deliveries = {}, set()
        self.custom = self.jordan_defaults = self.final_preferences = None

    def check_settings(self, stage, observed):
        super().check_settings(stage, observed)
        if '-policy-' in stage:
            value = observed['ui']['language_policy']
            saved = {key: deepcopy(value[key]) for key in ('settings', 'rows')}
            require(saved['settings']['limit_enabled'] is True
                    and saved['settings']['allowance'] == ['0 minutes']
                    and value['balances'] == {'daily': 0, 'one_time': 0, 'total': 0},
                    'reminder-notifications:independent-zero-policy')
            child = stage.split('-')[0]
            if stage.endswith('-before'):
                self.policies[child] = saved
            else:
                require(saved == self.policies[child], 'reminder-notifications:changed-policy')

    def reminder(self, guard, action, child='riley'):
        guard()
        value = self.ui.observe(f'binding-reminder-{child}-{action}').get('reminders')
        guard()
        return value

    def select(self, guard, child, seconds=600):
        guard()
        self.ui.kiosk_request = ('child' if child == 'riley' else 'other-child', 'parent', seconds, True)
        self.ui.observe('kiosk-request-select')
        guard()

    @staticmethod
    def preferences(value):
        return {key: deepcopy(value[key]) for key in ('records', 'language', 'show_in_fullscreen')}

    def saved(self, guard, *, child='riley'):
        value = self.reminder(guard, 'open', child)
        self.reminder(guard, 'cancel', child)
        return self.preferences(value)

    @staticmethod
    def prepare_defaults(journey, guard):
        before = journey.saved(guard)
        require(before == {'records': DEFAULTS, 'language': 'en', 'show_in_fullscreen': True},
                'reminder-notifications:untouched-riley-defaults')
        journey.select(guard, 'jordan', 1200)
        journey.jordan_defaults = journey.saved(guard, child='jordan')
        require(journey.jordan_defaults == before, 'reminder-notifications:untouched-jordan-defaults')
        journey.select(guard, 'riley', 240)
        journey.reminder(guard, 'open')
        journey.reminder(guard, 'language-de')
        journey.reminder(guard, 'save')
        require(journey.saved(guard) == {**before, 'language': 'de'},
                'reminder-notifications:saved-german-defaults')
        journey.ui.observe('kiosk-request-estimate')
        guard()
        return {'both_defaults': True, 'language': 'de'}

    @staticmethod
    def prepare_custom(journey, guard):
        journey.reminder(guard, 'open')
        journey.reminder(guard, 'delete-all')
        draft = journey.reminder(guard, 'create-final-warning')
        journey.reminder(guard, 'save')
        saved = journey.saved(guard)
        require(saved['records'] == draft['records'] and saved['language'] == 'de'
                and len(saved['records']) == 1, 'reminder-notifications:saved-custom-warning')
        journey.custom = deepcopy(saved['records'][0])
        require(journey.custom == {'id': journey.custom['id'], 'value': 15,
                    'unit': 'second', 'text': 'Save your game now'},
                'reminder-notifications:literal-custom-warning')
        for language in ('en', 'de'):
            journey.reminder(guard, 'open')
            journey.reminder(guard, 'language-' + language)
            journey.reminder(guard, 'save')
            require(journey.saved(guard) == {**saved, 'language': language},
                    'reminder-notifications:literal-across-language-switch')
        journey.select(guard, 'jordan', 1200)
        require(journey.saved(guard, child='jordan') == journey.jordan_defaults,
                'reminder-notifications:other-child-unchanged')
        journey.select(guard, 'riley')
        journey.ui.observe('kiosk-request-estimate')
        guard()
        return saved

    @staticmethod
    def disable_fullscreen(journey, guard):
        journey.reminder(guard, 'open')
        draft = journey.reminder(guard, 'fullscreen-false')
        journey.reminder(guard, 'save')
        saved = journey.saved(guard)
        require(saved == journey.preferences(draft) and saved['records'] == [journey.custom],
                'reminder-notifications:saved-fullscreen-disabled')
        journey.final_preferences = saved
        journey.ui.observe('kiosk-request-estimate')
        guard()
        return saved

    @staticmethod
    def save_final_preferences(journey, guard):
        require(journey.saved(guard) == journey.final_preferences,
                'reminder-notifications:custom-preserved')
        journey.select(guard, 'jordan', 1200)
        require(journey.saved(guard, child='jordan') == journey.jordan_defaults,
                'reminder-notifications:other-child-before-clear')
        journey.reminder(guard, 'open', 'jordan')
        journey.reminder(guard, 'delete-all', 'jordan')
        journey.reminder(guard, 'save', 'jordan')
        require(journey.saved(guard, child='jordan') == {**journey.jordan_defaults, 'records': []},
                'reminder-notifications:saved-empty')
        journey.select(guard, 'riley')
        return journey.final_preferences

    @staticmethod
    def check_persistence(journey, guard):
        require(journey.reboot_observed and journey.saved(guard) == journey.final_preferences,
                'reminder-notifications:reboot-custom-persistence')
        journey.select(guard, 'jordan', 1200)
        require(journey.saved(guard, child='jordan') == {**journey.jordan_defaults, 'records': []},
                'reminder-notifications:reboot-empty-persistence')
        journey.select(guard, 'riley')
        journey.ui.observe('kiosk-request-estimate')
        guard()
        return {'custom_and_empty_retained': True}

    @staticmethod
    def observer(name):
        def observe(journey, guard):
            guard()
            journey.ui.natural_reminder_record = {
                'records': [DEFAULTS[1], DEFAULTS[0]] if name == 'first' else [journey.custom],
                'language': 'de', 'fullscreen': None if name == 'first' else name == 'enabled'}
            result = journey.ui.observe('child-reminder-history-wait')['natural_reminder']
            guard()
            require(result['removed'] is True, 'reminder-notifications:lock-removal')
            initial = result['initial']
            for row, emission in zip(journey.ui.natural_reminder_record['records'], result['emissions'], strict=True):
                threshold = row['value'] * (60 if row['unit'] == 'minute' else 1)
                elapsed = [(emission['read_bounds'][0] - initial['read_bounds'][1]) / 1e9,
                           (emission['read_bounds'][1] - initial['read_bounds'][0]) / 1e9]
                require(initial['seconds'] - threshold - 2 <= elapsed[1]
                        and elapsed[0] < initial['seconds'] - threshold + 15
                        and emission['delivery_id'] not in journey.deliveries,
                        'reminder-notifications:natural-crossing-and-renewal')
                journey.deliveries.add(emission['delivery_id'])
            if name != 'first':
                require(result['visibility']['visible'] is (name == 'enabled')
                        and result['visibility']['game_usable_moves'] == 2,
                        'reminder-notifications:fullscreen-and-original-game')
            elapsed = [(result['lock_read_bounds'][0] - initial['read_bounds'][1]) / 1e9,
                       (result['lock_read_bounds'][1] - initial['read_bounds'][0]) / 1e9]
            require(initial['seconds'] - 2 <= elapsed[1] and elapsed[0] < initial['seconds'] + 15,
                    'reminder-notifications:original-natural-lock')
            return result
        return observe


def execute(recorder, context):
    from e2e_fixture_preparation import REMINDER_CALLER, REMINDER_SUBSETS
    context.fixture_subsets = REMINDER_SUBSETS
    context.fixture_caller = REMINDER_CALLER
    record_installed_journey(recorder, context, PLAN, timeout=7200,
                             journey_type=ReminderNotificationsJourney)


E2E_CASES = {'warnings-play-renewal-reboot': execute}
