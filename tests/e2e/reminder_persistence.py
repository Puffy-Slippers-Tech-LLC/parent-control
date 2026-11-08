"""Case 263: one child's saved empty reminder list survives a real reboot."""
from copy import deepcopy

from installed_journey import InstalledJourney, JourneyPlan, record_installed_journey
from journey_blocks import (fresh_desktop, parent_management, overlay_entry,
    station_entry, custom_child_selection, prefixed_stages)
from kiosk_reminders import KioskReminderJourney
from overlay_reminders import DEFAULTS, sorted_records
from private_artifacts import require


SETUP = {
    **fresh_desktop('parent'), **parent_management(),
    'allowance-configured': 'ui:time-explanation-setup-thirty-read',
    'riley-policy-before': 'ui:overlay-language-policy',
    **custom_child_selection('jordan', 'existing'),
    'jordan-allowance-configured': 'ui:time-explanation-setup-thirty-read',
    'jordan-policy-before': 'ui:kiosk-language-policy',
    'parent-logout-ready': 'ui:desktop', 'parent-logout': 'system:parent-logout',
    'parent-logged-out': 'ui:gdm-returned',
    **station_entry('initial-'),
    'jordan-language': 'ui:kiosk-language-initial',
    'jordan-language-save': 'ui:kiosk-language-save',
    'jordan-jamie': 'ui:kiosk-language-jordan-jamie',
    'jordan-before': 'ui:kiosk-language-form-en',
    'jordan-defaults': 'ui:binding-reminder-jordan-open',
    'jordan-defaults-close': 'ui:binding-reminder-jordan-cancel',
    'defaults-riley-select': 'ui:binding-reminder-riley-select',
    'riley-defaults': 'ui:binding-reminder-riley-open',
    'riley-defaults-close': 'ui:binding-reminder-riley-cancel',
    'defaults-jordan-select': 'ui:binding-reminder-jordan-select',
    'initial-station-exit': 'ui:kiosk-request-cancel',
    'initial-station-returned': 'ui:gdm-station-returned',
}
EDIT = {
    **prefixed_stages('fresh', fresh_desktop('child')),
    **overlay_entry('direct', 'command', form_operation='overlay-language-form-en'),
    'overlay-defaults': 'ui:overlay-reminder-defaults',
    'overlay-created': 'ui:overlay-reminder-create',
    'overlay-edited': 'ui:overlay-reminder-edit',
    'overlay-saved': 'ui:overlay-reminder-save',
    'overlay-saved-form': 'ui:overlay-language-form-en',
    'overlay-exit': 'ui:overlay-qualification-cancel', 'overlay-returned': 'ui:overlay-desktop',
    'child-logout': 'system:child-logout', 'child-logged-out': 'ui:gdm-returned',
}
CLEAR = {
    **station_entry('renewed-'),
    'riley-select': 'ui:binding-reminder-riley-select',
    'station-saved-read': 'ui:binding-reminder-riley-open',
    'station-delete-draft': 'ui:binding-reminder-riley-delete',
    'station-cancel': 'ui:binding-reminder-riley-cancel',
    'station-cancel-read': 'ui:binding-reminder-riley-open',
    'station-clear-draft': 'ui:binding-reminder-riley-delete-all',
    'station-empty-save': 'ui:binding-reminder-riley-save',
    'station-empty-read': 'ui:binding-reminder-riley-open',
    'station-empty-close': 'ui:binding-reminder-riley-cancel',
    'station-riley-form': 'ui:kiosk-riley-language-form-en',
    'station-exit': 'ui:kiosk-request-cancel', 'station-returned': 'ui:gdm-station-returned',
    **prefixed_stages('reboot-parent', fresh_desktop('parent')),
}
RETURN = {
    'reboot-requested': 'system:parent-desktop-identity', 'reboot-greeter': 'ui:gdm-list',
    **prefixed_stages('after', station_entry('initial-')),
    'after-jordan-select': 'ui:binding-reminder-jordan-select',
    'after-jordan-form': 'ui:kiosk-language-form-en',
    'after-jordan-station': 'ui:binding-reminder-jordan-open',
    'after-jordan-close': 'ui:binding-reminder-jordan-cancel',
    'after-riley-select': 'ui:binding-reminder-riley-select',
    'after-riley-station': 'ui:binding-reminder-riley-open',
    'after-riley-close': 'ui:binding-reminder-riley-cancel',
    'after-station-riley-form': 'ui:kiosk-riley-language-form-en',
    'after-station-exit': 'ui:kiosk-request-cancel',
    'after-station-returned': 'ui:gdm-station-returned',
    **prefixed_stages('after-riley', fresh_desktop('child')),
    **overlay_entry('after-riley', 'command', form_operation='overlay-language-form-en'),
    'after-riley-overlay': 'ui:overlay-reminder-empty',
    'after-riley-overlay-close': 'ui:overlay-reminder-cancel',
    'after-riley-exit': 'ui:overlay-qualification-cancel',
    'after-riley-returned': 'ui:overlay-desktop',
    'after-riley-logout': 'system:child-logout', 'after-riley-logged-out': 'ui:gdm-returned',
    **prefixed_stages('after-jordan', fresh_desktop('other-child')),
    'after-jordan-overlay-launch': 'ui:transfer-overlay-jordan-launch',
    'after-jordan-overlay-ready': 'ui:request-overlay-jordan-ready',
    'after-jordan-overlay': 'ui:binding-reminder-jordan-overlay-open',
    'after-jordan-overlay-close': 'ui:binding-reminder-jordan-overlay-cancel',
    'after-jordan-overlay-exit': 'ui:transfer-overlay-jordan-cancel',
    'after-jordan-overlay-returned': 'ui:transfer-overlay-jordan-returned',
    'after-jordan-logout': 'system:standard-logout', 'after-jordan-logged-out': 'ui:gdm-returned',
    **prefixed_stages('return', fresh_desktop('parent')),
    **prefixed_stages('return', parent_management()),
    'riley-policy-after': 'ui:overlay-language-policy',
    **custom_child_selection('jordan-final', 'existing'),
    'jordan-policy-after': 'ui:kiosk-language-policy',
}
SCREENS = {**SETUP, **EDIT, **CLEAR, **RETURN}
LOGINS = {'': ('parent', 'parent-login'), 'fresh': ('child', 'child-login'),
    'reboot-parent': ('parent', 'reboot-parent'), 'after-riley': ('child', 'after-riley'),
    'after-jordan': ('other-child', 'after-jordan'), 'return': ('parent', 'return-parent')}
LOGIN_STAGES = {('-'.join((prefix, stage)) if prefix else stage)
                for prefix, (role, _identity) in LOGINS.items() for stage in fresh_desktop(role)}
PLAN = JourneyPlan(prefix='reminder-persistence', worker_mode='reminder_persistence',
    screen_tags=SCREENS,
    phases={'ready': 'setup', 'setup-detached': 'setup',
        **{stage: 'step-1' for stage in SETUP}, 'installed-greeter': 'start',
        **{stage: 'step-2' for stage in EDIT}, **{stage: 'step-3' for stage in CLEAR},
        **{stage: 'step-4' for stage in RETURN}},
    advance_after={'initial-station-returned': 'step-2', 'child-logged-out': 'step-3',
                   'reboot-parent-desktop': 'step-4'},
    invocations=tuple(stage for stage in SCREENS if stage in LOGIN_STAGES
        or stage in ('direct-launch', 'direct-form', 'after-riley-launch', 'after-riley-form')),
    challenges={identity: (role, (prefix + '-' if prefix else '') +
        ('recipient-qualified' if role == 'parent' else 'child-recipient-qualified'
         if role == 'child' else 'standard-recipient-qualified'),
        (prefix + '-' if prefix else '') + ('recipient-rechecked' if role == 'parent'
         else 'child-recipient-rechecked' if role == 'child' else 'standard-recipient-rechecked'))
        for prefix, (role, identity) in LOGINS.items()},
    child_bindings={'jordan-allowance-configured': 'existing'},
    reboot_transition=('reboot-requested', 'reboot-greeter'),
    assertions_after={'riley-defaults': 'both-defaults', 'station-saved-read': 'saved-edited-record',
        'station-cancel-read': 'cancel-preserved', 'station-empty-read': 'saved-empty',
        'reboot-greeter': 'changed-boot', 'after-riley-overlay': 'empty-on-both-surfaces',
        'after-jordan-overlay': 'other-child-preserved', 'jordan-policy-after': 'policy-preserved'})


class ReminderPersistenceJourney(KioskReminderJourney):
    jordan_allowance = '30 minutes'

    def check_settings(self, stage, observed):
        InstalledJourney.check_settings(self, stage, observed)
        operation = self.plan.screen_tags.get(stage, '')[3:]
        value = observed.get('ui', {})
        if operation in ('overlay-language-policy', 'kiosk-language-policy'):
            self.check_policy(operation, value['language_policy'])
        elif '-language-form-' in operation:
            overlay = operation.startswith('overlay-')
            child = ('fixture-child' if overlay or operation.startswith('kiosk-riley-')
                     else 'existing-fixture-child')
            self.check_form(value['language_form']['request'], child=child, overlay=overlay)
        elif operation.endswith('-select') and operation.startswith('binding-reminder-'):
            self.check_form(value['request'], child=('fixture-child' if 'riley' in operation
                                                    else 'existing-fixture-child'))
        if 'reminders' not in value:
            return
        require(stage not in self.captures, 'reminder-persistence:capture-replay')
        current = value['reminders']
        records = current['records']
        preferences = {key: current[key] for key in (
            'records', 'language', 'show_in_fullscreen', 'fullscreen_enabled')}
        require(current['language'] == 'en' and current['show_in_fullscreen'] is True
                and current['fullscreen_enabled'] is bool(records),
                'reminder-persistence:preferences')
        if stage in ('jordan-defaults', 'riley-defaults', 'overlay-defaults'):
            require(records == DEFAULTS, 'reminder-persistence:untouched-defaults')
            if stage == 'jordan-defaults':
                self.jordan_preferences = deepcopy(preferences)
        elif stage == 'overlay-created':
            added = [row for row in records if row['id'] not in {row['id'] for row in DEFAULTS}]
            require(len(added) == 1 and added[0] == {'id': added[0]['id'],
                'value': 75, 'unit': 'second', 'text': 'Save <work>!'},
                'reminder-persistence:created-record')
            self.custom_record = deepcopy(added[0])
            require(records == sorted_records([*DEFAULTS, self.custom_record]),
                    'reminder-persistence:created-list')
        elif stage in ('overlay-edited', 'station-saved-read', 'station-cancel-read'):
            require(self.custom_record is not None, 'reminder-persistence:missing-created-record')
            if stage == 'overlay-edited':
                self.custom_record = {**self.custom_record, 'value': 90, 'text': 'Save <work> & games!'}
            require(records == sorted_records([*DEFAULTS, self.custom_record]),
                    'reminder-persistence:saved-id-text-trigger')
        elif stage == 'station-delete-draft':
            require(records == DEFAULTS, 'reminder-persistence:deleted-custom-draft')
        elif stage in ('station-clear-draft', 'station-empty-read', 'after-riley-station',
                       'after-riley-overlay'):
            require(records == [], 'reminder-persistence:durable-empty-list')
        else:
            require(stage in ('after-jordan-station', 'after-jordan-overlay')
                    and self.jordan_preferences is not None and preferences == self.jordan_preferences,
                    'reminder-persistence:other-child-preservation')
        self.captures.add(stage)


def execute(recorder, context):
    record_installed_journey(recorder, context, PLAN, timeout=3600,
                             journey_type=ReminderPersistenceJourney)


E2E_CASES = {'saved-empty-reboot': execute}
