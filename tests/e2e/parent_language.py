"""Installed LANG01 Parent slice with independent literal public expectations."""

import copy

from installed_journey import InstalledJourney, JourneyPlan
from journey_blocks import fresh_desktop, parent_reopen, language_selection, custom_child_selection
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


# One fixed prerequisite slice for the later account/offline history. Desktop
# languages stay English; no child login or temporary grant occurs here.
ISOLATION_SCREENS = {
    **fresh_desktop('parent'),
    'desktop': 'ui:parent-language-wrong-entry',
    'parent-command': 'ui:parent-command-launch',
    'initial-language': 'ui:parent-language-initial',
    'initial-save': 'ui:parent-language-save',
    **custom_child_selection('riley-setup', 'child', route='keyboard'),
    'riley-enabled': 'ui:parent-toggle-enabled', 'riley-saved': 'ui:parent-save-enabled',
    'riley-allowance': 'ui:parent-language-riley-allowance',
    'riley-before': 'ui:parent-language-riley-enabled-en',
    **custom_child_selection('jordan-setup', 'existing', route='keyboard'),
    'jordan-enabled': 'ui:multiple-other-enable', 'jordan-saved': 'ui:multiple-other-saved',
    'jordan-allowance': 'ui:parent-language-jordan-allowance',
    'jordan-before': 'ui:parent-language-jordan-enabled-en',
    **selection('chinese', 'zh-Hans'), 'chinese-save': 'ui:parent-language-save',
}
for prefix, child in (('riley', 'child'), ('jordan', 'existing'), ('riley-return', 'child')):
    name = 'jordan' if child == 'existing' else 'riley'
    ISOLATION_SCREENS.update({
        **custom_child_selection(prefix, child, route='keyboard'),
        prefix + '-selected': f'ui:parent-language-{name}-selected',
        prefix + '-state': f'ui:parent-language-{name}-enabled-zh-hans',
        prefix + '-choice': 'ui:parent-language-open',
        prefix + '-close': 'ui:parent-language-cancel',
    })
ISOLATION_SCREENS.update({
    **parent_reopen(), 'prior-window': 'ui:parent-language-riley-enabled-zh-hans',
    # A new Parent window starts with the first alphabetically listed child,
    # Jordan, rather than remembering Riley from the closed window. Read that
    # untouched entry before explicitly repeating Riley -> Jordan -> Riley.
    'same-parent-window': 'ui:parent-language-jordan-enabled-zh-hans',
})
for name, child in (('riley', 'child'), ('jordan', 'existing'), ('riley-return', 'child')):
    prefix = 'reopened-' + name
    account = 'jordan' if child == 'existing' else 'riley'
    ISOLATION_SCREENS.update({
        **custom_child_selection(prefix, child, route='keyboard'),
        prefix + '-selected': f'ui:parent-language-{account}-selected',
        prefix + '-state': f'ui:parent-language-{account}-enabled-zh-hans',
        prefix + '-choice': 'ui:parent-language-open',
        prefix + '-close': 'ui:parent-language-cancel',
    })
ISOLATION_PLAN = JourneyPlan(prefix='parent-language-isolation', worker_mode='parent_language_isolation',
    screen_tags=ISOLATION_SCREENS, phases={'ready': 'setup', 'setup-detached': 'setup',
        **{stage: 'step-1' for stage in ISOLATION_SCREENS}, 'installed-greeter': 'start'},
    invocations=tuple(ISOLATION_SCREENS))

# Independent visible management oracles, not derived from installed catalogues.
ENABLED_LABELS = {
    'en': {'Screen Time Limit', 'Daily Time Allowance', "Today's Remaining Time"},
    'zh-Hans': {'限制屏幕时间', '每日可用时间', '今日剩余时间'},
}


class ParentLanguageIsolationJourney(ParentLanguageJourney):
    def __init__(self, context, progress, plan=ISOLATION_PLAN, *, actions=None):
        super().__init__(context, progress, plan, actions=actions)
        self.policies = {}
        self.balance_captures = {}

    def check_settings(self, stage, observed):
        from accessible_ui import (PARENT_LANGUAGE_STATES, PARENT_LANGUAGE_SELECTIONS,
                                   NAMED_CUSTOM_CHILDREN, CHILD_IDENTITIES)
        operation = self.plan.screen_tags.get(stage, '')[3:]
        if operation in PARENT_LANGUAGE_SELECTIONS:
            InstalledJourney.check_settings(self, stage, observed)
            require(stage not in self.language_captures, 'language:capture-replay')
            account = NAMED_CUSTOM_CHILDREN[PARENT_LANGUAGE_SELECTIONS[operation]]
            require(observed['ui'].get('child_selection') == {
                'child': CHILD_IDENTITIES[account]}, 'language:selected-child')
            self.language_captures.add(stage)
            return
        if operation not in PARENT_LANGUAGE_STATES:
            return super().check_settings(stage, observed)
        # Call the recorder's inherited validation, then our fixed comparisons.
        InstalledJourney.check_settings(self, stage, observed)
        require(stage not in self.language_captures, 'language:capture-replay')
        child, language = PARENT_LANGUAGE_STATES[operation]
        value = observed['ui']['language_state']
        account = NAMED_CUSTOM_CHILDREN[child]
        require(language == self.committed and value['child'] == CHILD_IDENTITIES[account]
                and value['account_name'] == account and value['limit_enabled'] is True
                and value['allowance_minutes'] == 60 and value['chooser_absent'] is True,
                'language:enabled-account-state')
        labels = set(value['management_labels'])
        other = 'en' if language == 'zh-Hans' else 'zh-Hans'
        require(value['management'] == TEXTS[language][4]
                and ENABLED_LABELS[language] <= labels and not (ENABLED_LABELS[other] & labels),
                'language:enabled-management-text')
        policy = {key: value[key] for key in ('child', 'account_name', 'limit_enabled',
                                             'allowance_minutes', 'rows', 'app_names')}
        balances = value['balances']
        require(balances['child'] == value['child'] and balances['one_time']['seconds'] == 0
                and balances['daily']['seconds'] == balances['total']['seconds']
                and 0 < balances['daily']['seconds'] <= 3600,
                'language:zero-grant-and-daily')
        if child not in self.policies:
            require(stage == ('riley-before' if child == 'child' else 'jordan-before'),
                    'language:missing-english-baseline')
            self.policies[child] = copy.deepcopy(policy)
            self.balance_captures[child] = copy.deepcopy(balances)
        require(policy == self.policies[child], 'language:child-policy-preservation')
        baseline = self.balance_captures[child]
        elapsed = (balances['observed_monotonic_ns'] - baseline['observed_monotonic_ns']) / 10**9
        require(0 <= elapsed <= 600, 'language:elapsed-bound')
        # One-second formatter precision plus one normal public refresh tick.
        decrease = baseline['daily']['seconds'] - balances['daily']['seconds']
        require(-2 <= decrease <= elapsed + 2, 'language:balance-preservation')
        self.language_captures.add(stage)
