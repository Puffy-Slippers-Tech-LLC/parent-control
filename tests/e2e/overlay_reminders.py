"""312a: saved reminder editing through the shared request Preferences API."""
from copy import deepcopy

from installed_journey import InstalledJourney, JourneyPlan
from journey_blocks import fresh_desktop, parent_management, overlay_entry
from private_artifacts import require


DEFAULTS = [
    {'id': 'fifteen-seconds', 'value': 15, 'unit': 'second', 'text': ''},
    {'id': 'one-minute', 'value': 1, 'unit': 'minute', 'text': ''},
    {'id': 'five-minutes', 'value': 5, 'unit': 'minute', 'text': ''},
    {'id': 'ten-minutes', 'value': 10, 'unit': 'minute', 'text': ''},
]
REMINDER_STAGES = {
    'defaults-open': 'defaults', 'created': 'create', 'edited': 'edit',
    'saved': 'save', 'saved-read': 'read', 'deleted-draft': 'delete',
    'cancelled': 'cancel', 'cancel-read': 'read', 'cleared-draft': 'delete-all',
    'empty-saved': 'save', 'empty-read': 'empty', 'empty-close': 'cancel',
}
SCREENS = {
    **fresh_desktop('parent'), **parent_management(),
    'wrong-entry': 'ui:overlay-language-wrong-entry',
    'allowance-configured': 'ui:time-explanation-setup-thirty-read',
    'policy-before': 'ui:overlay-language-policy',
    'wrong-account-refused': 'ui:overlay-wrong-account-refused',
    'logout-ready': 'ui:desktop', 'logout': 'system:parent-logout',
    'gdm-logged-out': 'ui:gdm-returned',
    **{'fresh-' + stage: operation for stage, operation in fresh_desktop('child').items()},
    **overlay_entry('direct', 'command', form_operation='overlay-language-initial'),
    'initial-save': 'ui:overlay-language-save',
    'initial-form': 'ui:overlay-language-form-en',
    **{stage: 'ui:overlay-reminder-' + action for stage, action in REMINDER_STAGES.items()},
    'final-form': 'ui:overlay-language-form-en',
    'cancel': 'ui:overlay-qualification-cancel', 'returned': 'ui:overlay-desktop',
    'child-switch-user': 'system:child-switch-user', 'child-gdm-switched': 'ui:gdm-returned',
    'return-greeter': 'ui:gdm-list', 'return-focused': 'ui:gdm-focused',
    'return-qualified': 'ui:gdm-parent-recipient',
    'return-rechecked': 'ui:gdm-parent-recipient-rechecked', 'return-desktop': 'ui:desktop',
    'return-parent-command': 'ui:parent-command-launch', 'return-parent-window': 'ui:parent-window',
    'return-child-picker-opened': 'ui:child-picker-opened',
    'return-child-choice-highlighted': 'ui:child-choice-highlighted',
    'return-parent-selected': 'ui:parent-selected',
    'policy-after': 'ui:overlay-language-policy',
}
PLAN = JourneyPlan(prefix='overlay-reminders', worker_mode='overlay_reminder_editing',
    screen_tags=SCREENS,
    phases={'ready': 'setup', 'setup-detached': 'setup',
            **{stage: 'step-1' for stage in SCREENS}, 'installed-greeter': 'start'},
    invocations=tuple(stage for stage in SCREENS if stage in fresh_desktop('parent')
                      or stage.startswith(('fresh-', 'direct-'))
                      or stage in ('return-greeter', 'return-focused', 'return-qualified',
                                   'return-rechecked', 'return-desktop')),
    challenges={
        'parent-login': ('parent', 'recipient-qualified', 'recipient-rechecked'),
        'child-login': ('child', 'fresh-child-recipient-qualified', 'fresh-child-recipient-rechecked'),
        'return-parent': ('parent', 'return-qualified', 'return-rechecked')},
    assertions_after={stage: stage + '-verified' for stage in SCREENS
                      if stage in REMINDER_STAGES or stage in (
                          'wrong-entry', 'wrong-account-refused', 'initial-form',
                          'final-form', 'policy-before', 'policy-after', 'returned')})


def sorted_records(records):
    return sorted(deepcopy(records), key=lambda row: row['value'] * (
        60 if row['unit'] == 'minute' else 1))


class OverlayReminderJourney(InstalledJourney):
    """The caller owns finite values; shared UI operations own all input."""
    def __init__(self, context, progress, plan=PLAN, *, actions=None):
        super().__init__(context, progress, plan, actions=actions)
        self.reminder_captures = set()
        self.custom_record = self.saved_records = None
        self.policy_balance = None
        self.policy_projection = self.request_projection = None

    def check_settings(self, stage, observed):
        super().check_settings(stage, observed)
        operation = self.plan.screen_tags.get(stage, '')[3:]
        if operation == 'overlay-language-initial':
            require(observed['ui']['language']['checked'] == 'en', 'reminders:initial-language')
        if operation == 'overlay-language-form-en':
            form = observed['ui']['language_form']
            request = form['request']
            require(request['surface'] == 'child-overlay' and request['form_count'] == 1
                and request['child'] == 'fixture-child' and request['approver'] == 'other-fixture-parent'
                and request['duration_seconds'] == 1800 and request['custom_text'] is None
                and request['allow_soft'] is False, 'reminders:declared-request')
            if self.request_projection is None:
                self.request_projection = deepcopy(request)
            require(request == self.request_projection, 'reminders:request-preservation')
        if operation == 'overlay-language-policy':
            policy = observed['ui']['language_policy']
            balances = policy['balances']
            require(policy['settings'] == {'child': 'fixture-child', 'limit_enabled': True,
                'allowance': ['30 minutes']} and balances['one_time'] == 0
                and balances['total'] == balances['daily'], 'reminders:declared-policy')
            saved = {'settings': policy['settings'], 'rows': policy['rows']}
            if self.policy_projection is None:
                self.policy_projection = deepcopy(saved)
            require(saved == self.policy_projection, 'reminders:policy-preservation')
            daily = balances['daily']
            bounds = self.ui.read_bounds
            if self.policy_balance is None:
                self.policy_balance = (daily, bounds)
            else:
                before, earlier = self.policy_balance
                elapsed = (bounds[1] - earlier[0]) / 1e9
                require(before - elapsed - 2 <= daily <= before + 2,
                        'reminders:time-preservation')
        if not operation.startswith('overlay-reminder-'):
            return
        require(stage not in self.reminder_captures, 'reminders:capture-replay')
        action = operation.removeprefix('overlay-reminder-')
        if action in ('save', 'cancel'):
            self.reminder_captures.add(stage)
            return
        value = observed['ui']['reminders']
        records = value['records']
        require(value['language'] == 'en' and value['show_in_fullscreen'] is True
                and value['fullscreen_enabled'] is bool(records), 'reminders:preference-preservation')
        if action == 'defaults':
            expected = DEFAULTS
        elif action == 'create':
            added = [row for row in records if row['id'] not in {item['id'] for item in DEFAULTS}]
            require(len(added) == 1 and added[0] == {
                'id': added[0]['id'], 'value': 75, 'unit': 'second', 'text': 'Save <work>!'},
                'reminders:created-record')
            self.custom_record = deepcopy(added[0])
            expected = sorted_records([*DEFAULTS, self.custom_record])
        elif action == 'edit':
            require(self.custom_record is not None, 'reminders:missing-created-record')
            self.custom_record = {**self.custom_record, 'value': 90, 'text': 'Save <work> & games!'}
            expected = sorted_records([*DEFAULTS, self.custom_record])
            self.saved_records = deepcopy(expected)
        elif action == 'read':
            require(self.saved_records is not None, 'reminders:missing-saved-record')
            expected = self.saved_records
        elif action == 'delete':
            require(self.custom_record is not None, 'reminders:missing-created-record')
            expected = DEFAULTS
        else:
            require(action in ('delete-all', 'empty'), 'reminders:operation')
            expected = []
        require(records == expected, 'reminders:records-or-stored-id')
        self.reminder_captures.add(stage)
