"""Finite REQUEST04/LANG01 account isolation qualification; no request submission."""
from copy import deepcopy

from accessible_ui import (CHILD, EXISTING_CHILD, CHILD_IDENTITIES, APPROVER_IDENTITIES,
    KIOSK_LANGUAGE_BINDINGS, KIOSK_LANGUAGE_ACCOUNTS, KIOSK_LANGUAGE_POLICIES)
from installed_journey import InstalledJourney, JourneyPlan
from journey_blocks import (fresh_desktop, parent_management, station_entry,
    language_selection, custom_child_selection)
from kiosk_language import CHOOSER, FORM, TEXT_IDS
from private_artifacts import require


SCREENS = {
    **fresh_desktop('parent'), **parent_management(),
    'wrong-entry': 'ui:kiosk-language-wrong-entry',
    'limit-enabled': 'ui:parent-toggle-enabled', 'save-enabled': 'ui:parent-save-enabled',
    'riley-policy-before': 'ui:kiosk-riley-language-policy',
    **custom_child_selection('jordan', 'existing'),
    'other-enabled': 'ui:multiple-other-enable', 'other-saved': 'ui:multiple-other-saved',
    'jordan-policy-before': 'ui:kiosk-language-policy',
    'switch-user': 'system:parent-switch-user', 'gdm-switched': 'ui:gdm-returned',
    **station_entry('initial-'),
    'initial-language': 'ui:kiosk-language-initial', 'initial-save': 'ui:kiosk-language-save',
    'jordan-jamie': 'ui:kiosk-language-jordan-jamie',
    'jordan-original': 'ui:kiosk-language-form-en',
    **language_selection('german', 'de', surface='kiosk'),
    'german-save': 'ui:kiosk-language-save', 'german-form': 'ui:kiosk-language-form-de',
    'account-refusals': 'ui:kiosk-language-account-refusals',
    'riley-initial': 'ui:kiosk-language-riley-initial',
    'riley-original': 'ui:kiosk-riley-language-form-en',
    **language_selection('hebrew', 'he', surface='kiosk', child='child'),
    'hebrew-save': 'ui:kiosk-riley-language-save', 'hebrew-form': 'ui:kiosk-riley-language-form-he',
}


def retained(prefix, child, language, *, casey=False):
    owner = 'kiosk-riley' if child == 'child' else 'kiosk'
    return {prefix + '-form': f'ui:{owner}-language-form-{language}' + ('-casey' if casey else ''),
            prefix + '-open': f'ui:{owner}-language-open',
            prefix + '-close': f'ui:{owner}-language-cancel'}


for child, language in (('jordan', 'de'), ('riley', 'he')):
    SCREENS[child + '-restored'] = 'ui:kiosk-language-' + child + '-restored'
    SCREENS.update(retained(child + '-retained', 'existing' if child == 'jordan' else 'child', language))
    for approver, casey in (('casey', True), ('jamie-restored', False)):
        prefix = child + '-' + approver
        SCREENS[prefix] = 'ui:kiosk-language-' + prefix
        SCREENS.update(retained(prefix, 'existing' if child == 'jordan' else 'child', language, casey=casey))
SCREENS.update({
    'jordan-before-exit': 'ui:kiosk-language-jordan-restored',
    'cancel': 'ui:kiosk-request-cancel', 'returned': 'ui:gdm-station-returned',
    **station_entry('renewed-'),
    **retained('jordan-reentered', 'existing', 'de'),
    'riley-reentered': 'ui:kiosk-language-riley-restored',
    **retained('riley-reentered', 'child', 'he'),
    'jordan-final': 'ui:kiosk-language-jordan-restored',
    **retained('jordan-final', 'existing', 'de'),
    'final-cancel': 'ui:kiosk-request-cancel', 'final-returned': 'ui:gdm-station-returned',
    'return-greeter': 'ui:gdm-list', 'return-focused': 'ui:gdm-focused',
    'return-qualified': 'ui:gdm-parent-recipient', 'return-rechecked': 'ui:gdm-parent-recipient-rechecked',
    'return-desktop': 'ui:desktop',
    'return-parent-command': 'ui:parent-command-launch',
    'return-parent-window': 'ui:switch-parent',
    'jordan-policy-after': 'ui:kiosk-language-policy',
    **custom_child_selection('riley-final', 'child', route='keyboard'),
    'riley-policy-after': 'ui:kiosk-riley-language-policy',
    'parent-english-open': 'ui:parent-language-open', 'parent-english-close': 'ui:parent-language-cancel',
})
PLAN = JourneyPlan(prefix='kiosk-language-restoration', worker_mode='kiosk_language_restoration',
    screen_tags=SCREENS, phases={'ready': 'setup', 'setup-detached': 'setup',
        **{stage: 'step-1' for stage in SCREENS}, 'installed-greeter': 'start'},
    invocations=('return-greeter', 'return-focused', 'return-qualified', 'return-rechecked', 'return-desktop'),
    challenges={'return-parent': ('parent', 'return-qualified', 'return-rechecked')},
    assertions_after={stage: stage + '-verified' for stage in SCREENS
        if stage.endswith(('-form', '-open', '-original', '-before', '-after', '-candidate'))
        or stage in ('initial-language', 'account-refusals', 'wrong-entry', 'returned', 'final-returned')})


class KioskLanguageRestorationJourney(InstalledJourney):
    def __init__(self, context, progress, plan=PLAN, *, actions=None):
        super().__init__(context, progress, plan, actions=actions)
        self.child = EXISTING_CHILD
        self.approver = 'fixture-parent'
        self.committed = {CHILD: 'en', EXISTING_CHILD: 'en'}
        self.candidate = 'en'
        self.captures = set()
        self.requests, self.policies = {}, {}

    def check_request_preservation(self, request, child):
        require(request['child'] == CHILD_IDENTITIES[child] and request['approver'] == self.approver
                and request['duration_seconds'] == 1800 and request['custom_text'] is None
                and request['allow_soft'] is False, 'restoration:declared-request')
        projection = {key: value for key, value in request.items() if key != 'approver'}
        if child not in self.requests:
            self.requests[child] = deepcopy(projection)
        require(projection == self.requests[child], 'restoration:request-preservation')

    def check_settings(self, stage, observed):
        super().check_settings(stage, observed)
        operation = self.plan.screen_tags.get(stage, '')[3:]
        if operation not in (set(KIOSK_LANGUAGE_BINDINGS) | set(KIOSK_LANGUAGE_POLICIES)
                | set(KIOSK_LANGUAGE_ACCOUNTS) | {'parent-language-open', 'kiosk-language-account-refusals'}):
            return
        require(stage not in self.captures, 'restoration:capture-replay')
        value = observed['ui']
        if operation in KIOSK_LANGUAGE_POLICIES:
            child = KIOSK_LANGUAGE_POLICIES[operation]
            policy = value['language_policy']
            require(policy['settings'] == {'child': CHILD_IDENTITIES[child], 'limit_enabled': True,
                'allowance': ['0 minutes']} and policy['balances'] == {'daily': 0, 'one_time': 0, 'total': 0},
                'restoration:declared-policy')
            if child not in self.policies:
                self.policies[child] = deepcopy(policy)
            require(policy == self.policies[child], 'restoration:policy-preservation')
        elif operation in KIOSK_LANGUAGE_ACCOUNTS:
            field, name, owner, before, after = KIOSK_LANGUAGE_ACCOUNTS[operation]
            require(owner == self.child and self.committed[owner] == before, 'restoration:input-binding')
            if field == 'child':
                self.child = name
            else:
                self.approver = APPROVER_IDENTITIES[name]
            require(self.committed[self.child] == after, 'restoration:result-binding')
            self.check_request_preservation(value['request'], self.child)
        elif operation in ('kiosk-language-account-refusals', 'kiosk-language-wrong-entry'):
            require(value['refused'] is True, 'restoration:refusal')
        else:
            binding, child = KIOSK_LANGUAGE_BINDINGS.get(operation, (operation, None))
            require(child is None or child == self.child, 'restoration:chooser-child')
            if '-language-form-' in binding:
                language = self.committed[child]
                require(binding.endswith('-' + language.lower()), 'restoration:form-binding')
                form, text = value['language_form'], FORM[language]
                require(form['texts'] == dict(zip(TEXT_IDS, (*text[:3], text[4], text[6])))
                        and form['labels'] == {TEXT_IDS[3]: text[3], TEXT_IDS[4]: text[5]}
                        and form['chooser_absent'] is True, 'restoration:translated-form')
                self.check_request_preservation(form['request'], child)
            elif binding.endswith('-save'):
                self.committed[child] = self.candidate
            elif binding.endswith('-cancel'):
                self.candidate = self.committed[child]
            else:
                if '-choose-' in binding:
                    self.candidate = next(key for key in CHOOSER if binding.endswith('-' + key.lower()))
                elif binding.endswith('-open'):
                    self.candidate = self.committed[child] if child else 'en'
                text = CHOOSER[self.candidate]
                require(value['language'] == {'initial': binding.endswith('-initial'),
                    'checked': self.candidate.lower(), 'choices': {key: item[0] for key, item in CHOOSER.items()},
                    'heading': text[1], 'save': text[2], 'save_label': text[2], 'save_description': text[3]},
                    'restoration:checked-choice-or-text')
        self.captures.add(stage)
