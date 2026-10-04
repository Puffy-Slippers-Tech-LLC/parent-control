"""Finite installed Riley overlay LANG01 history, independent of complete case 300."""
from copy import deepcopy

from installed_journey import InstalledJourney, JourneyPlan
from journey_blocks import fresh_desktop, parent_management, overlay_entry, language_selection
from private_artifacts import require

CHOOSER = {
    'en': ('English', 'Choose your language', 'Save', 'Save your language preference.'),
    'de': ('Deutsch', 'Sprache wählen', 'Speichern', 'Die Spracheinstellung speichern.'),
    'zh-Hans': ('中文（简体）', '选择语言', '保存', '保存语言偏好设置。'),
    'he': ('עברית', 'בחירת השפה שלך', 'שמירה', 'שמירת העדפת השפה שלך.'),
}
FORM = {
    'en': ('Child', 'Approver', '30 minutes', 'REQUEST', 'REQUEST', 'CANCEL', 'CANCEL'),
    'de': ('Kind', 'Genehmigung durch', '30 Minuten', 'ANFRAGEN', 'ANFRAGEN', 'Abbrechen', 'Abbrechen'),
    'zh-Hans': ('孩子', '批准人', '30 分钟', '提交请求', '提交请求', '取消', '取消'),
    'he': ('ילד', 'מאשר', '30 דקות', 'בקשה', 'בקשה', 'ביטול', 'ביטול'),
}
TEXT_IDS = ('kiosk-child-account-caption', 'kiosk-approver-account-caption',
            'kiosk-duration-label-1800', 'kiosk-request-submit', 'kiosk-request-cancel')

SCREENS = {
    **fresh_desktop('parent'), **parent_management(),
    'wrong-entry': 'ui:overlay-language-wrong-entry',
    'allowance-configured': 'ui:time-explanation-setup-thirty-read',
    'policy-before': 'ui:overlay-language-policy',
    'wrong-account-refused': 'ui:overlay-wrong-account-refused',
    'repeat-desktop': 'ui:desktop', 'switch-user': 'system:parent-switch-user',
    'gdm-switched': 'ui:gdm-returned',
    **{'fresh-' + stage: operation for stage, operation in fresh_desktop('child').items()},
    **overlay_entry('direct', 'command', form_operation='overlay-language-initial'),
    'initial-save': 'ui:overlay-language-save', 'initial-form': 'ui:overlay-language-form-en',
}
for prefix, language in (('german', 'de'), ('cancel-chinese', 'zh-Hans'),
                         ('chinese', 'zh-Hans'), ('hebrew', 'he'), ('english', 'en'), ('final-german', 'de')):
    SCREENS.update(language_selection(prefix, language, surface='overlay'))
    response = 'cancel' if prefix == 'cancel-chinese' else 'save'
    retained = 'de' if response == 'cancel' else language
    SCREENS.update({prefix + '-response': 'ui:overlay-language-' + response,
                    prefix + '-form': 'ui:overlay-language-form-' + retained.lower(),
                    prefix + '-retained': 'ui:overlay-language-open',
                    prefix + '-close': 'ui:overlay-language-cancel',
                    prefix + '-closed-form': 'ui:overlay-language-form-' + retained.lower()})
SCREENS.update({
    'cancel': 'ui:overlay-qualification-cancel', 'returned': 'ui:overlay-desktop',
    **overlay_entry('renewed', 'command', form_operation='overlay-language-form-de'),
    'reentered-open': 'ui:overlay-language-open', 'reentered-close': 'ui:overlay-language-cancel',
    'final-form': 'ui:overlay-language-form-de',
    'final-cancel': 'ui:overlay-qualification-cancel', 'final-returned': 'ui:overlay-desktop',
    'child-switch-user': 'system:child-switch-user', 'child-gdm-switched': 'ui:gdm-returned',
    'return-greeter': 'ui:gdm-list', 'return-focused': 'ui:gdm-focused',
    'return-qualified': 'ui:gdm-parent-recipient', 'return-rechecked': 'ui:gdm-parent-recipient-rechecked',
    'return-desktop': 'ui:desktop', 'policy-after': 'ui:overlay-language-policy',
})
PLAN = JourneyPlan(prefix='overlay-language', worker_mode='overlay_language', screen_tags=SCREENS,
    phases={'ready': 'setup', 'setup-detached': 'setup',
            **{stage: 'step-1' for stage in SCREENS}, 'installed-greeter': 'start'},
    invocations=tuple(stage for stage in SCREENS if stage in fresh_desktop('parent')
                      or stage.startswith(('fresh-', 'direct-', 'renewed-', 'return-'))),
    challenges={
        'parent-login': ('parent', 'recipient-qualified', 'recipient-rechecked'),
        'child-login': ('child', 'fresh-child-recipient-qualified', 'fresh-child-recipient-rechecked'),
        'return-parent': ('parent', 'return-qualified', 'return-rechecked')},
    assertions_after={stage: stage + '-verified' for stage in SCREENS
        if stage in ('wrong-entry', 'wrong-account-refused', 'initial-form', 'policy-before', 'policy-after',
                     'returned', 'final-returned', 'reentered-open') or stage.endswith('-form')
        or stage.endswith('-candidate') or stage.endswith('-retained')})


class OverlayLanguageJourney(InstalledJourney):
    def __init__(self, context, progress, plan=PLAN, *, actions=None):
        super().__init__(context, progress, plan, actions=actions)
        self.committed = self.candidate = 'en'
        self.language_captures = set()
        self.request_projection = self.policy_projection = None

    def check_settings(self, stage, observed):
        super().check_settings(stage, observed)
        operation = self.plan.screen_tags.get(stage, '')[3:]
        if not operation.startswith('overlay-language-'):
            return
        require(stage not in self.language_captures, 'language:capture-replay')
        value = observed['ui']
        if operation == 'overlay-language-policy':
            policy = value['language_policy']
            require(policy['settings'] == {'child': 'fixture-child', 'limit_enabled': True,
                    'allowance': ['30 minutes']} and policy['balances']['one_time'] == 0
                    and policy['balances']['total'] == policy['balances']['daily'], 'language:declared-policy')
            saved = {'settings': policy['settings'], 'rows': policy['rows']}
            if self.policy_projection is None:
                self.policy_projection = deepcopy(saved)
            require(saved == self.policy_projection, 'language:policy-preservation')
        elif operation.startswith('overlay-language-form-'):
            require(operation == 'overlay-language-form-' + self.committed.lower(), 'language:form-binding')
            form = value['language_form']
            text = FORM[self.committed]
            require(form['texts'] == dict(zip(TEXT_IDS, (*text[:3], text[4], text[6])))
                    and form['labels'] == {TEXT_IDS[3]: text[3], TEXT_IDS[4]: text[5]}
                    and form['chooser_absent'] is True, 'language:form-text')
            request = form['request']
            require(request['surface'] == 'child-overlay' and request['form_count'] == 1
                    and request['child'] == 'fixture-child' and request['approver'] == 'other-fixture-parent'
                    and request['duration_seconds'] == 1800 and request['custom_text'] is None
                    and request['allow_soft'] is False, 'language:declared-request')
            if self.request_projection is None:
                self.request_projection = deepcopy(request)
            require(request == self.request_projection, 'language:request-preservation')
        elif operation == 'overlay-language-save':
            self.committed = self.candidate
        elif operation == 'overlay-language-cancel':
            self.candidate = self.committed
        elif operation != 'overlay-language-wrong-entry':
            if operation.startswith('overlay-language-choose-'):
                self.candidate = next(key for key in CHOOSER if operation.endswith('-' + key.lower()))
            elif operation == 'overlay-language-open':
                self.candidate = self.committed
            text = CHOOSER[self.candidate]
            require(value['language'] == {'initial': operation == 'overlay-language-initial',
                'checked': self.candidate.lower(), 'choices': {key: texts[0] for key, texts in CHOOSER.items()},
                'heading': text[1], 'save': text[2], 'save_label': text[2], 'save_description': text[3]},
                'language:chooser-text-or-choice')
        self.language_captures.add(stage)
