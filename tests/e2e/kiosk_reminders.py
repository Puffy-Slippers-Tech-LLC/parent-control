"""312b: selected-child reminder persistence across overlay and kiosk."""
from copy import deepcopy

from installed_journey import InstalledJourney, JourneyPlan
from journey_blocks import (fresh_desktop, parent_management, overlay_entry,
    station_entry, custom_child_selection, prefixed_stages)
from overlay_reminders import DEFAULTS, sorted_records
from private_artifacts import require


SCREENS = {
    **fresh_desktop('parent'), **parent_management(),
    'allowance-configured': 'ui:time-explanation-setup-thirty-read',
    'riley-policy-before': 'ui:overlay-language-policy',
    **custom_child_selection('jordan', 'existing'),
    'jordan-enabled': 'ui:multiple-other-enable', 'jordan-saved': 'ui:multiple-other-saved',
    'jordan-policy-before': 'ui:kiosk-language-policy',
    'parent-logout-ready': 'ui:desktop', 'parent-logout': 'system:parent-logout',
    'parent-logged-out': 'ui:gdm-returned',
    **prefixed_stages('fresh', fresh_desktop('child')),
    **overlay_entry('direct', 'command', form_operation='overlay-language-initial'),
    'initial-save': 'ui:overlay-language-save',
    'overlay-before': 'ui:overlay-language-form-en',
    'overlay-defaults': 'ui:binding-reminder-overlay-open',
    'overlay-created': 'ui:binding-reminder-overlay-create',
    'overlay-saved': 'ui:binding-reminder-overlay-save',
    'overlay-saved-form': 'ui:overlay-language-form-en',
    'overlay-exit': 'ui:overlay-qualification-cancel', 'overlay-returned': 'ui:overlay-desktop',
    'child-logout': 'system:child-logout', 'child-logged-out': 'ui:gdm-returned',
    **station_entry('initial-'),
    'jordan-language': 'ui:kiosk-language-initial', 'jordan-language-save': 'ui:kiosk-language-save',
    'jordan-jamie': 'ui:kiosk-language-jordan-jamie',
    'jordan-before': 'ui:kiosk-language-form-en',
    'jordan-reminders-before': 'ui:binding-reminder-jordan-open',
    'jordan-close': 'ui:binding-reminder-jordan-cancel',
    'riley-select': 'ui:binding-reminder-riley-select',
    'riley-saved-read': 'ui:binding-reminder-riley-open',
    'riley-edited': 'ui:binding-reminder-riley-edit',
    'riley-saved': 'ui:binding-reminder-riley-save',
    'riley-reopened': 'ui:binding-reminder-riley-open',
    'riley-close': 'ui:binding-reminder-riley-cancel',
    'riley-saved-form': 'ui:kiosk-riley-language-form-en',
    'approver-select': 'ui:binding-reminder-approver-select',
    'approver-reminders': 'ui:binding-reminder-riley-open',
    'approver-close': 'ui:binding-reminder-riley-cancel',
    'approver-form': 'ui:kiosk-riley-language-form-en-casey',
    'jordan-select': 'ui:binding-reminder-jordan-select',
    'jordan-reminders-after': 'ui:binding-reminder-jordan-open',
    'jordan-after-close': 'ui:binding-reminder-jordan-cancel',
    'jordan-after': 'ui:kiosk-language-form-en-casey',
    'riley-return-select': 'ui:binding-reminder-riley-select',
    'riley-return-read': 'ui:binding-reminder-riley-open',
    'riley-return-close': 'ui:binding-reminder-riley-cancel',
    'riley-return-form': 'ui:kiosk-riley-language-form-en-casey',
    'station-exit': 'ui:kiosk-request-cancel', 'station-returned': 'ui:gdm-station-returned',
    **prefixed_stages('renewed', fresh_desktop('child')),
    **overlay_entry('renewed', 'command', form_operation='overlay-request-form'),
    'overlay-final-before': 'ui:overlay-language-form-en',
    'overlay-final-read': 'ui:binding-reminder-overlay-open',
    'overlay-final-close': 'ui:binding-reminder-overlay-cancel',
    'overlay-final-form': 'ui:overlay-language-form-en',
    'overlay-final-exit': 'ui:overlay-qualification-cancel',
    'overlay-final-returned': 'ui:overlay-desktop',
    'final-child-logout': 'system:child-logout', 'final-child-logged-out': 'ui:gdm-returned',
    **prefixed_stages('return', fresh_desktop('parent')),
    **prefixed_stages('return', parent_management()),
    'riley-policy-after': 'ui:overlay-language-policy',
    **custom_child_selection('jordan-final', 'existing'),
    'jordan-policy-after': 'ui:kiosk-language-policy',
}
LOGIN_STAGES = set(fresh_desktop('parent')) | {
    prefix + stage for prefix, account in (('fresh-', 'child'), ('renewed-', 'child'), ('return-', 'parent'))
    for stage in fresh_desktop(account)}
PLAN = JourneyPlan(prefix='kiosk-reminders', worker_mode='kiosk_reminder_binding',
    screen_tags=SCREENS,
    phases={'ready': 'setup', 'setup-detached': 'setup',
        **{stage: 'step-1' for stage in SCREENS}, 'installed-greeter': 'start'},
    invocations=tuple(stage for stage in SCREENS if stage in LOGIN_STAGES
                      or stage.startswith(('direct-', 'renewed-launch', 'renewed-form'))),
    challenges={
        'parent-login': ('parent', 'recipient-qualified', 'recipient-rechecked'),
        'child-login': ('child', 'fresh-child-recipient-qualified', 'fresh-child-recipient-rechecked'),
        'renewed-child': ('child', 'renewed-child-recipient-qualified', 'renewed-child-recipient-rechecked'),
        'return-parent': ('parent', 'return-recipient-qualified', 'return-recipient-rechecked')},
    assertions_after={stage: stage + '-verified' for stage, tag in SCREENS.items()
        if tag.startswith('ui:binding-reminder-') or stage.endswith(('-before', '-after', '-form'))})


class KioskReminderJourney(InstalledJourney):
    """Finite public saved-value and child-isolation oracles before every reply."""
    def __init__(self, context, progress, plan=PLAN, *, actions=None):
        super().__init__(context, progress, plan, actions=actions)
        self.captures = set()
        self.custom_record = self.jordan_preferences = None
        self.policies, self.requests = {}, {}
        self.approver = 'fixture-parent'

    def check_form(self, request, *, child, overlay=False):
        require(request['child'] == child and request['surface'] == (
            'child-overlay' if overlay else 'kiosk') and request['form_count'] == 1
            and request['approver'] == ('other-fixture-parent' if overlay else self.approver)
            and request['duration_seconds'] == 1800 and request['custom_text'] is None
            and request['allow_soft'] is False, 'binding-reminders:declared-request')
        projection = {key: value for key, value in request.items()
                      if key not in ('surface', 'approver', 'child_selector_enabled')}
        if child not in self.requests:
            self.requests[child] = deepcopy(projection)
        require(projection == self.requests[child], 'binding-reminders:request-preservation')

    def check_policy(self, operation, policy):
        child = 'fixture-child' if operation == 'overlay-language-policy' else 'existing-fixture-child'
        require(policy['settings'] == {'child': child, 'limit_enabled': True,
            'allowance': ['30 minutes' if child == 'fixture-child' else '0 minutes']}
            and policy['balances']['one_time'] == 0
            and policy['balances']['total'] == policy['balances']['daily'],
            'binding-reminders:declared-policy')
        projection = {'settings': policy['settings'], 'rows': policy['rows']}
        daily, bounds = policy['balances']['daily'], self.ui.read_bounds
        if child not in self.policies:
            self.policies[child] = (deepcopy(projection), daily, bounds)
        before, initial, earlier = self.policies[child]
        elapsed = (bounds[1] - earlier[0]) / 1e9
        require(projection == before and initial - elapsed - 2 <= daily <= initial + 2
                and (child != 'existing-fixture-child' or daily == 0),
                'binding-reminders:policy-or-time-preservation')

    def check_settings(self, stage, observed):
        super().check_settings(stage, observed)
        operation = self.plan.screen_tags.get(stage, '')[3:]
        relevant = (operation.startswith('binding-reminder-') or '-language-form-' in operation
                    or operation in ('overlay-language-policy', 'kiosk-language-policy',
                                     'kiosk-language-jordan-jamie'))
        if not relevant:
            return
        require(stage not in self.captures, 'binding-reminders:capture-replay')
        value = observed['ui']
        if operation in ('overlay-language-policy', 'kiosk-language-policy'):
            self.check_policy(operation, value['language_policy'])
        elif '-language-form-' in operation:
            overlay = operation.startswith('overlay-')
            child = ('fixture-child' if overlay or operation.startswith('kiosk-riley-')
                     else 'existing-fixture-child')
            self.check_form(value['language_form']['request'], child=child, overlay=overlay)
        elif operation.endswith('-select') or operation == 'kiosk-language-jordan-jamie':
            if operation == 'binding-reminder-approver-select':
                self.approver = 'other-fixture-parent'
            child = ('existing-fixture-child' if operation in (
                'binding-reminder-jordan-select', 'kiosk-language-jordan-jamie') else 'fixture-child')
            self.check_form(value['request'], child=child)
        elif operation.endswith(('-save', '-cancel')):
            pass
        else:
            current = value['reminders']
            require(current['language'] == 'en' and current['show_in_fullscreen'] is True
                    and current['fullscreen_enabled'] is True, 'binding-reminders:preferences')
            records = current['records']
            if stage == 'overlay-defaults':
                expected = DEFAULTS
            elif stage == 'overlay-created':
                added = [row for row in records if row['id'] not in {item['id'] for item in DEFAULTS}]
                require(len(added) == 1 and added[0] == {'id': added[0]['id'],
                    'value': 90, 'unit': 'second', 'text': 'Save <work> & games!'},
                    'binding-reminders:created-record')
                self.custom_record = deepcopy(added[0])
                expected = sorted_records([*DEFAULTS, self.custom_record])
            elif operation.startswith('binding-reminder-jordan-'):
                preferences = {key: current[key] for key in (
                    'records', 'language', 'show_in_fullscreen', 'fullscreen_enabled')}
                if stage == 'jordan-reminders-before':
                    require(records == DEFAULTS, 'binding-reminders:jordan-defaults')
                    self.jordan_preferences = deepcopy(preferences)
                require(self.jordan_preferences is not None and preferences == self.jordan_preferences,
                        'binding-reminders:jordan-preservation')
                expected = self.jordan_preferences['records']
            else:
                require(self.custom_record is not None, 'binding-reminders:missing-record')
                if stage == 'riley-edited':
                    self.custom_record = {**self.custom_record, 'value': 75}
                expected = sorted_records([*DEFAULTS, self.custom_record])
            require(records == expected, 'binding-reminders:records-or-stored-id')
        self.captures.add(stage)
