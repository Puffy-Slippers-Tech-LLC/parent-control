"""Installed LANG01 Parent slice with independent literal public expectations."""

import copy

from installed_journey import InstalledJourney, JourneyPlan
from journey_blocks import fresh_desktop, parent_reopen, language_selection
from private_artifacts import require

# Reviewed GTK oracles, deliberately independent of the running catalogues.
TEXTS = {
    'en': ('English', 'Choose your language', 'Save',
           'Save your language preference.', 'Screen time limit'),
    'de': ('Deutsch', 'Sprache wählen', 'Speichern',
           'Die Spracheinstellung speichern.', 'Bildschirmzeit begrenzen'),
    'zh-Hans': ('中文（简体）', '选择语言', '保存', '保存语言偏好设置。', '限制屏幕时间'),
    'he': ('עברית', 'בחירת השפה שלך', 'שמירה', 'שמירת העדפת השפה שלך.', 'מגבלת זמן מסך'),
}
# The visible row title and accessible switch name are distinct messages.
MANAGEMENT_TITLES = {
    'en': 'Screen Time Limit', 'de': 'Bildschirmzeit begrenzen',
    'zh-Hans': '限制屏幕时间', 'he': 'מגבלת זמן מסך',
}


def selection(prefix, language):
    """Reusable LANG01 stages; caller owns values, comparisons and response."""
    return language_selection(prefix, language, surface='parent')


SCREENS = {
    **fresh_desktop('parent'),
    'desktop': 'ui:parent-language-wrong-entry',
    'parent-command': 'ui:parent-command-launch',
    'initial-language': 'ui:parent-language-initial',
    'initial-save': 'ui:parent-language-save',
    'initial-state': 'ui:parent-language-state',
    **selection('german', 'de'), 'german-save': 'ui:parent-language-save',
    'german-state': 'ui:parent-language-state',
    **selection('cancel-chinese', 'zh-Hans'), 'cancel-response': 'ui:parent-language-cancel',
    'cancel-state': 'ui:parent-language-state',
    **selection('chinese', 'zh-Hans'), 'chinese-save': 'ui:parent-language-save',
    'chinese-state': 'ui:parent-language-state',
    **selection('hebrew', 'he'), 'hebrew-save': 'ui:parent-language-save',
    'hebrew-state': 'ui:parent-language-state',
    **selection('english', 'en'), 'english-save': 'ui:parent-language-save',
    'english-state': 'ui:parent-language-state',
    **parent_reopen(),
    'prior-window': 'ui:parent-language-state',
    'same-parent-window': 'ui:parent-language-state',
    'relaunched-state': 'ui:parent-language-state',
    'relaunched-open': 'ui:parent-language-open',
    'relaunched-cancel': 'ui:parent-language-cancel',
    'final-state': 'ui:parent-language-state',
}
PLAN = JourneyPlan(prefix='parent-language', worker_mode='parent_language', screen_tags=SCREENS,
    phases={'ready': 'setup', 'setup-detached': 'setup',
            **{stage: 'step-1' for stage in SCREENS}, 'installed-greeter': 'start'},
    invocations=tuple(SCREENS))


class ParentLanguageJourney(InstalledJourney):
    def __init__(self, context, progress, plan=PLAN, *, actions=None):
        super().__init__(context, progress, plan, actions=actions)
        self.committed = self.candidate = 'en'
        self.preservation = None
        self.language_captures = set()

    def check_settings(self, stage, observed):
        super().check_settings(stage, observed)
        operation = self.plan.screen_tags.get(stage, '')[3:]
        if operation not in ('parent-language-save', 'parent-language-cancel',
                             'parent-language-initial', 'parent-language-open',
                             'parent-language-read', 'parent-language-state') and not operation.startswith(
                                 'parent-language-choose-'):
            return
        require(stage not in self.language_captures, 'language:capture-replay')
        ui = observed['ui']
        if operation == 'parent-language-save':
            self.committed = self.candidate
        elif operation == 'parent-language-cancel':
            self.candidate = self.committed
        elif operation == 'parent-language-state':
            value = ui['language_state']
            require(value['management'] == TEXTS[self.committed][4]
                    and MANAGEMENT_TITLES[self.committed] in value['management_labels']
                    and value['chooser_absent'] is True, 'language:management-text')
            projection = {key: value[key] for key in
                          ('child', 'limit_enabled', 'allowance_minutes', 'rows')}
            if self.preservation is None:
                self.preservation = copy.deepcopy(projection)
            require(projection == self.preservation, 'language:policy-preservation')
        else:
            if operation.startswith('parent-language-choose-'):
                self.candidate = next(value for value in TEXTS if operation.endswith('-' + value.lower()))
            elif operation == 'parent-language-open':
                self.candidate = self.committed
            value = ui['language']
            expected = TEXTS[self.candidate]
            require(value == {
                'initial': operation == 'parent-language-initial',
                'checked': self.candidate.lower(),
                'choices': {language: texts[0] for language, texts in TEXTS.items()},
                'heading': expected[1], 'save': expected[2], 'save_label': expected[2],
                'save_description': expected[3]},
                'language:chooser-text-or-choice')
        self.language_captures.add(stage)
