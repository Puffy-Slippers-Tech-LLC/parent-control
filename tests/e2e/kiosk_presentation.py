"""Case 261: Riley's request language stays independent of its approver."""
from copy import deepcopy
from functools import partial

from installed_journey import JourneyPlan, record_installed_journey
from journey_blocks import fresh_desktop, parent_management, station_entry, language_selection
from language_composition import PublicLanguageJourney, public_language_value
from private_artifacts import require
from request_flow import prepared_request


SETUP = {
    **fresh_desktop('parent'), **parent_management(),
    'limit-enabled': 'ui:parent-toggle-enabled', 'save-enabled': 'ui:parent-save-enabled',
    'switch-user': 'system:parent-switch-user', 'gdm-switched': 'ui:gdm-returned',
}
REQUEST = {
    **station_entry(),
    **prepared_request(prefix='open', entry='open', initial='default',
        child='fixture-child', approver='fixture-parent', duration_seconds=75,
        allow_soft=True, compact=True),
    'english-form': 'ui:language-history-riley-en-jamie',
    **language_selection('hebrew', 'he', surface='kiosk', child='child'),
    'hebrew-save': 'ui:kiosk-riley-language-save',
    'hebrew-form': 'ui:language-history-riley-he-jamie',
}
RESTORATION = {
    'casey-select': 'ui:language-history-riley-casey-select',
    'casey-form': 'ui:language-history-riley-he-casey',
    **language_selection('english', 'en', surface='kiosk', child='child'),
    'english-save': 'ui:kiosk-riley-language-save',
    'restored-form': 'ui:language-history-riley-en-casey-restricted',
    'cancel': 'ui:kiosk-request-cancel', 'returned': 'ui:gdm-station-returned',
}
SCREENS = {**SETUP, **REQUEST, **RESTORATION}
PLAN = JourneyPlan(prefix='kiosk-language-history', worker_mode='kiosk_language_history',
    screen_tags=SCREENS,
    phases={'ready': 'setup', 'setup-detached': 'setup',
        **{stage: phase for phase, screens in (
            ('step-1', SETUP), ('step-2', REQUEST), ('step-3', RESTORATION)) for stage in screens},
        'installed-greeter': 'start'},
    advance_after={'gdm-switched': 'step-2', 'hebrew-form': 'step-3'},
    invocations=tuple(fresh_desktop('parent')),
    challenges={'parent-login': ('parent', 'recipient-qualified', 'recipient-rechecked')},
    assertions_after={'english-form': 'original-english-request',
        'hebrew-form': 'hebrew-preserved-request', 'casey-form': 'approver-independent-language',
        'english-open': 'child-language-retained', 'restored-form': 'english-preserved-restricted-request',
        'returned': 'normal-station-exit'})

IDS = ('kiosk-child-account-caption', 'kiosk-approver-account-caption',
       'kiosk-duration-label-1800', 'kiosk-request-submit', 'kiosk-request-cancel')
REQUEST_VALUES = {'surface': 'kiosk', 'form_count': 1, 'child': 'fixture-child',
    'approver': 'fixture-parent', 'duration_seconds': 75, 'custom_text': '1.25', 'allow_soft': True,
    'child_selector_enabled': True, 'approver_selector_enabled': True, 'duration_enabled': True,
    'soft_choice_enabled': True, 'request_enabled': True, 'cancel_enabled': True, 'message': '', 'mute': None}
TEXT = {'en': ('Child', 'Approver', '30 minutes', 'Request access', 'Cancel request', 'REQUEST', 'CANCEL'),
        'he': ('ילד', 'מאשר', '30 דקות', 'בקשת גישה', 'ביטול הבקשה', 'בקשה', 'ביטול')}
CHECKS = {stage: public_language_value('language_form', {
    'request': {**REQUEST_VALUES, 'approver': approver},
    'texts': dict(zip(IDS, TEXT[language][:5])),
    'labels': dict(zip(IDS[3:], TEXT[language][5:])), 'chooser_absent': True})
    for stage, language, approver in (
        ('english-form', 'en', 'fixture-parent'), ('hebrew-form', 'he', 'fixture-parent'),
        ('casey-form', 'he', 'other-fixture-parent'), ('restored-form', 'en', 'other-fixture-parent'))}
CHECKS['english-open'] = public_language_value('language', {
    'initial': False, 'checked': 'he',
    'choices': {'en': 'English', 'de': 'Deutsch', 'zh-Hans': '中文（简体）', 'he': 'עברית'},
    'heading': 'בחירת השפה שלך', 'save': 'שמירה', 'save_label': 'שמירה',
    'save_description': 'שמירת העדפת השפה שלך.'})


class KioskLanguageHistoryJourney(PublicLanguageJourney):
    def check_settings(self, stage, observed):
        super().check_settings(stage, observed)
        if stage in ('english-form', 'hebrew-form', 'casey-form', 'restored-form'):
            form = deepcopy(observed['ui']['language_form'])
            # Only the declared approver changes during this history.
            del form['request']['approver']
            if stage == 'english-form':
                self.public_captures['original-request'] = deepcopy(form['request'])
                self.public_captures['english-form'] = deepcopy(form)
            else:
                require(form['request'] == self.public_captures['original-request'],
                        'kiosk-history:changed-request')
            if stage == 'hebrew-form':
                self.public_captures['hebrew-form'] = deepcopy(form)
            if stage in ('casey-form', 'restored-form'):
                language = 'hebrew-form' if stage == 'casey-form' else 'english-form'
                require(form == self.public_captures[language], 'kiosk-history:changed-language')


def execute(recorder, context):
    record_installed_journey(recorder, context, PLAN, timeout=900,
        journey_type=partial(KioskLanguageHistoryJourney, checks=CHECKS))


E2E_CASES = {'kiosk-hebrew': execute}
