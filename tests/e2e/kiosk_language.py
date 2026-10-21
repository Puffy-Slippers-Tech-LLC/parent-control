"""Finite installed Jordan kiosk LANG01 qualification; no approval or case credit."""
from copy import deepcopy

from installed_journey import InstalledJourney, JourneyPlan
from journey_blocks import fresh_desktop, parent_management, station_entry, language_selection
from private_artifacts import require
from real_interval import interval_action

# Independent literal oracles; never infer public IDs or results from catalogues.
CHOOSER = {
    'en': ('English', 'Choose your language', 'Save', 'Save your language preference.'),
    'de': ('Deutsch', 'Sprache wählen', 'Speichern', 'Die Spracheinstellung speichern.'),
    'zh-Hans': ('中文（简体）', '选择语言', '保存', '保存语言偏好设置。'),
    'he': ('עברית', 'בחירת השפה שלך', 'שמירה', 'שמירת העדפת השפה שלך.'),
}
# Captions, duration, then each button's visible caption and accessible name.
# Descriptive accessible names are intentional and checked separately.
FORM = {
    'en': ('Child', 'Approver', '30 minutes', 'REQUEST', 'Request access', 'CANCEL', 'Cancel request'),
    'de': ('Kind', 'Genehmigung durch', '30 Minuten', 'ANFRAGEN', 'Zugriff anfragen',
           'Abbrechen', 'Anfrage abbrechen'),
    'zh-Hans': ('孩子', '批准人', '30 分钟', '提交请求', '请求访问权限', '取消', '取消请求'),
    'he': ('ילד', 'מאשר', '30 דקות', 'בקשה', 'בקשת גישה', 'ביטול', 'ביטול הבקשה'),
}
TEXT_IDS = ('kiosk-child-account-caption', 'kiosk-approver-account-caption',
            'kiosk-duration-label-1800', 'kiosk-request-submit', 'kiosk-request-cancel')

SCREENS = {
    **fresh_desktop('parent'), **parent_management(),
    'wrong-entry': 'ui:kiosk-language-wrong-entry',
    'existing-child-picker-opened': 'ui:existing-child-picker-opened',
    'existing-child-choice-highlighted': 'ui:existing-child-choice-highlighted',
    'existing-returned': 'ui:discovery-ready',
    'other-enabled': 'ui:multiple-other-enable', 'other-saved': 'ui:multiple-other-saved',
    'policy-before': 'ui:kiosk-language-policy',
    'switch-user': 'system:parent-switch-user', 'gdm-switched': 'ui:gdm-returned',
    **station_entry('initial-'),
    'initial-language': 'ui:kiosk-language-initial-identity',
    'initial-retained': 'ui:kiosk-language-initial-identity', 'initial-save': 'ui:kiosk-language-save',
    'other-first-parent': 'ui:multiple-other-first-parent',
    'initial-form': 'ui:kiosk-language-form-en',
}
for prefix, language in (('german', 'de'), ('cancel-chinese', 'zh-Hans'),
                         ('chinese', 'zh-Hans'), ('hebrew', 'he'), ('english', 'en'), ('final-german', 'de')):
    SCREENS.update(language_selection(prefix, language, surface='kiosk'))
    response = 'cancel' if prefix == 'cancel-chinese' else 'save'
    retained = 'de' if response == 'cancel' else language
    SCREENS.update({prefix + '-response': 'ui:kiosk-language-' + response,
                    prefix + '-form': 'ui:kiosk-language-form-' + retained.lower(),
                    prefix + '-retained': 'ui:kiosk-language-open',
                    prefix + '-close': 'ui:kiosk-language-cancel'})
SCREENS.update({
    'cancel': 'ui:kiosk-request-cancel', 'returned': 'ui:gdm-station-returned',
    **station_entry('renewed-'),
    'reentered-form': 'ui:kiosk-language-form-de',
    'reentered-open': 'ui:kiosk-language-open', 'reentered-close': 'ui:kiosk-language-cancel',
    'final-form': 'ui:kiosk-language-form-de',
    **language_selection('restore-english', 'en', surface='kiosk'),
    'restore-english-save': 'ui:kiosk-language-save',
    'restore-english-form': 'ui:kiosk-language-form-en',
    'final-cancel': 'ui:kiosk-request-cancel', 'final-returned': 'ui:gdm-station-returned',
    'return-greeter': 'ui:gdm-list', 'return-focused': 'ui:gdm-focused',
    'return-qualified': 'ui:gdm-parent-recipient', 'return-rechecked': 'ui:gdm-parent-recipient-rechecked',
    'return-desktop': 'ui:desktop',
    'return-parent-command': 'ui:parent-command-launch',
    'return-parent-window': 'ui:switch-parent',
    'policy-after': 'ui:kiosk-language-policy',
    'restore-policy': 'ui:kiosk-language-policy-restored',
})
PLAN = JourneyPlan(prefix='kiosk-language', worker_mode='kiosk_language', screen_tags=SCREENS,
    phases={'ready': 'setup', 'setup-detached': 'setup',
            **{stage: 'step-1' for stage in SCREENS}, 'installed-greeter': 'start'},
    invocations=('return-greeter', 'return-focused', 'return-qualified', 'return-rechecked', 'return-desktop'),
    challenges={'return-parent': ('parent', 'return-qualified', 'return-rechecked')},
    stage_actions={'initial-language': 'real-interval'},
    assertions_after={stage: stage + '-verified' for stage in SCREENS
        if stage in ('wrong-entry', 'initial-language', 'initial-retained', 'policy-before', 'policy-after', 'restore-policy',
                     'returned', 'final-returned', 'reentered-open') or stage.endswith('-form')
        or stage.endswith('-candidate') or stage.endswith('-retained')})


class KioskLanguageJourney(InstalledJourney):
    def __init__(self, context, progress, plan=PLAN, *, actions=None):
        super().__init__(context, progress, plan, actions=(
            {'real-interval': interval_action(90)} if actions is None else actions))
        self.committed = self.candidate = 'en'
        self.language_captures = set()
        self.request_projection = self.policy_projection = None
        self.initial_chooser = None

    def check_settings(self, stage, observed):
        super().check_settings(stage, observed)
        operation = self.plan.screen_tags.get(stage, '')[3:]
        if operation == 'kiosk-language-initial-identity':
            operation = 'kiosk-language-initial'
        if not operation.startswith('kiosk-language-'):
            return
        require(stage not in self.language_captures, 'language:capture-replay')
        value = observed['ui']
        if operation == 'kiosk-language-policy-restored':
            policy = deepcopy(self.policy_projection)
            require(policy is not None, 'language:missing-policy')
            policy['settings']['limit_enabled'] = False
            require(value['language_policy'] == policy, 'language:policy-restoration')
        elif operation == 'kiosk-language-policy':
            policy = value['language_policy']
            require(policy['settings'] == {'child': 'existing-fixture-child', 'limit_enabled': True,
                    'allowance': ['0 minutes']} and policy['balances'] == {
                    'daily': 0, 'one_time': 0, 'total': 0}, 'language:declared-policy')
            if self.policy_projection is None:
                self.policy_projection = deepcopy(policy)
            require(policy == self.policy_projection, 'language:policy-preservation')
        elif operation.startswith('kiosk-language-form-'):
            require(operation == 'kiosk-language-form-' + self.committed.lower(), 'language:form-binding')
            form = value['language_form']
            text = FORM[self.committed]
            require(form['texts'] == dict(zip(TEXT_IDS, (*text[:3], text[4], text[6])))
                    and form['labels'] == {TEXT_IDS[3]: text[3], TEXT_IDS[4]: text[5]}
                    and form['chooser_absent'] is True, 'language:form-text')
            request = form['request']
            require(request['child'] == 'existing-fixture-child' and request['approver'] == 'fixture-parent'
                    and request['duration_seconds'] == 1800 and request['custom_text'] is None,
                    'language:declared-request')
            if self.request_projection is None:
                self.request_projection = deepcopy(request)
            require(request == self.request_projection, 'language:request-preservation')
        elif operation == 'kiosk-language-save':
            self.committed = self.candidate
        elif operation == 'kiosk-language-cancel':
            self.candidate = self.committed
        elif operation != 'kiosk-language-wrong-entry':
            if operation.startswith('kiosk-language-choose-'):
                self.candidate = next(key for key in CHOOSER if operation.endswith('-' + key.lower()))
            elif operation == 'kiosk-language-open':
                self.candidate = self.committed
            text = CHOOSER[self.candidate]
            chooser = deepcopy(value['language'])
            if stage in ('initial-language', 'initial-retained'):
                require('identity' in chooser, 'language:missing-chooser-identity')
                if stage == 'initial-language':
                    self.initial_chooser = deepcopy(chooser)
                require(self.initial_chooser is not None and chooser == self.initial_chooser,
                        'language:paused-chooser-replaced')
                chooser.pop('identity')
            require(chooser == {'initial': operation == 'kiosk-language-initial',
                'checked': self.candidate.lower(), 'choices': {key: texts[0] for key, texts in CHOOSER.items()},
                'heading': text[1], 'save': text[2], 'save_label': text[2], 'save_description': text[3]},
                'language:chooser-text-or-choice')
        self.language_captures.add(stage)
