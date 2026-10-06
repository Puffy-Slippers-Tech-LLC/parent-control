"""Case 255: one complete account, normal-entry and offline language history."""
from installed_journey import JourneyPlan, record_installed_journey
from journey_blocks import (fresh_desktop, parent_reopen, custom_child_selection,
    language_selection, station_entry, overlay_entry, prefixed_stages)
from language_composition import (language_journey, public_language_value,
    language_policy, offline_language_actions)

INITIAL = fresh_desktop('parent')
CHILD = prefixed_stages('child', fresh_desktop('child'))
RENEWED = prefixed_stages('renewed', fresh_desktop('child'))
RETURN = prefixed_stages('return', fresh_desktop('parent'))
SETUP = {
    **INITIAL, 'parent-command': 'ui:parent-command-launch',
    'initial-language': 'ui:parent-language-initial', 'initial-save': 'ui:parent-language-save',
    **custom_child_selection('riley-setup', 'child'),
    'riley-enabled': 'ui:parent-toggle-enabled', 'riley-saved': 'ui:parent-save-enabled',
    'riley-allowance': 'ui:parent-language-riley-allowance',
    'riley-before': 'ui:parent-language-riley-enabled-en',
    **custom_child_selection('jordan-setup', 'existing'),
    'jordan-enabled': 'ui:multiple-other-enable', 'jordan-saved': 'ui:multiple-other-saved',
    'jordan-allowance': 'ui:parent-language-jordan-allowance',
    'jordan-before': 'ui:parent-language-jordan-enabled-en',
}
PARENT = {'offline-enter': 'ui:parent-language-jordan-enabled-en',
    **language_selection('chinese', 'zh-Hans', surface='parent'),
    'chinese-save': 'ui:parent-language-save'}
for prefix, child, name in (('parent-riley', 'child', 'riley'), ('parent-jordan', 'existing', 'jordan'),
                           ('parent-riley-return', 'child', 'riley')):
    PARENT.update({**custom_child_selection(prefix, child),
        prefix + '-selected': 'ui:parent-language-' + name + '-selected',
        prefix + '-state': 'ui:parent-language-' + name + '-enabled-zh-hans',
        prefix + '-choice': 'ui:parent-language-open', prefix + '-close': 'ui:parent-language-cancel'})
PARENT.update({**parent_reopen(), 'prior-window': 'ui:parent-language-riley-enabled-zh-hans',
    'same-parent-window': 'ui:parent-language-jordan-enabled-zh-hans',
    'reopened-choice': 'ui:parent-language-open', 'reopened-close': 'ui:parent-language-cancel',
    **custom_child_selection('riley-session', 'child'),
    'riley-session-selected': 'ui:parent-language-riley-selected',
    'riley-session-before': 'ui:parent-language-riley-enabled-zh-hans',
    'parent-switch': 'system:parent-switch-user', 'parent-greeter': 'ui:gdm-returned'})
STATION = {**station_entry('initial-'),
    'station-initial-language': 'ui:kiosk-language-initial', 'station-initial-save': 'ui:kiosk-language-save',
    'jordan-jamie': 'ui:kiosk-language-jordan-jamie',
    'jordan-custom': 'ui:language-history-jordan-custom-open',
    **{f'jordan-text-{suffix}': 'ui:text-jordan-kiosk-fraction-' + suffix for suffix in ('focus', 'selected', 'read')},
    'jordan-soft': 'ui:language-history-jordan-soft', 'jordan-original': 'ui:language-history-jordan-en-jamie',
    **language_selection('german', 'de', surface='kiosk'), 'german-save': 'ui:kiosk-language-save',
    'jordan-german': 'ui:language-history-jordan-de-jamie',
    'riley-initial': 'ui:kiosk-language-riley-initial',
    'riley-custom': 'ui:language-history-riley-custom-open',
    **{f'riley-text-{suffix}': 'ui:text-kiosk-fraction-' + suffix for suffix in ('focus', 'selected', 'read')},
    'riley-soft': 'ui:language-history-riley-soft', 'riley-original': 'ui:language-history-riley-en-jamie',
    **language_selection('hebrew', 'he', surface='kiosk', child='child'),
    'hebrew-save': 'ui:kiosk-riley-language-save', 'riley-hebrew': 'ui:language-history-riley-he-jamie',
    **language_selection('cancel-german', 'de', surface='kiosk', child='child'),
    'cancel-german-response': 'ui:kiosk-riley-language-cancel',
    'cancel-retained': 'ui:kiosk-riley-language-open', 'cancel-close': 'ui:kiosk-riley-language-cancel',
    'riley-cancelled': 'ui:language-history-riley-he-jamie',
    'jordan-restored': 'ui:language-history-jordan-restored',
    'jordan-restored-form': 'ui:language-history-jordan-de-jamie',
    'jordan-choice': 'ui:kiosk-language-open', 'jordan-close': 'ui:kiosk-language-cancel',
    'jordan-casey-select': 'ui:language-history-jordan-casey-select',
    'jordan-casey': 'ui:language-history-jordan-de-casey',
    'jordan-casey-choice': 'ui:kiosk-language-open', 'jordan-casey-close': 'ui:kiosk-language-cancel',
    'jordan-jamie-select': 'ui:language-history-jordan-jamie-select',
    'riley-restored': 'ui:language-history-riley-restored', 'riley-restored-form': 'ui:language-history-riley-he-jamie',
    'riley-choice': 'ui:kiosk-riley-language-open', 'riley-close': 'ui:kiosk-riley-language-cancel',
    'riley-casey-select': 'ui:language-history-riley-casey-select', 'riley-casey': 'ui:language-history-riley-he-casey',
    'riley-casey-choice': 'ui:kiosk-riley-language-open', 'riley-casey-close': 'ui:kiosk-riley-language-cancel',
    'riley-jamie-select': 'ui:language-history-riley-jamie-select',
    'jordan-final': 'ui:language-history-jordan-restored',
    'station-cancel': 'ui:kiosk-request-cancel', 'station-returned': 'ui:gdm-station-returned',
    **station_entry('renewed-'),
    'jordan-reentered': 'ui:language-history-jordan-de-jamie',
    'jordan-reentered-choice': 'ui:kiosk-language-open', 'jordan-reentered-close': 'ui:kiosk-language-cancel',
    'riley-reentered-select': 'ui:language-history-riley-restored',
    'riley-reentered': 'ui:language-history-riley-he-jamie',
    'riley-reentered-choice': 'ui:kiosk-riley-language-open', 'riley-reentered-close': 'ui:kiosk-riley-language-cancel',
    'final-station-cancel': 'ui:kiosk-request-cancel', 'final-station-returned': 'ui:gdm-station-returned',
}
OVERLAY = {**CHILD, **overlay_entry('direct', 'command', form_operation='language-history-overlay-he-casey'),
    'overlay-choice': 'ui:overlay-language-open', 'overlay-close': 'ui:overlay-language-cancel',
    'overlay-cancel': 'ui:overlay-qualification-cancel', 'overlay-returned': 'ui:overlay-desktop',
    **overlay_entry('relaunched', 'command', form_operation='language-history-overlay-he-casey'),
    'relaunched-choice': 'ui:overlay-language-open', 'relaunched-close': 'ui:overlay-language-cancel',
    'relaunched-cancel': 'ui:overlay-qualification-cancel', 'relaunched-returned': 'ui:overlay-desktop',
    'child-logout': 'system:child-logout', **RENEWED,
    **overlay_entry('renewed-overlay', 'command', form_operation='language-history-overlay-he-casey'),
    'renewed-choice': 'ui:overlay-language-open', 'renewed-close': 'ui:overlay-language-cancel',
    'renewed-cancel': 'ui:overlay-qualification-cancel', 'renewed-returned': 'ui:overlay-desktop',
    'child-switch': 'system:child-switch-user', 'child-greeter': 'ui:gdm-returned',
}
FINAL = {**RETURN, 'return-parent-command': 'ui:parent-command-launch', 'return-parent-window': 'ui:switch-parent',
    **custom_child_selection('final-jordan', 'existing'),
    'final-jordan-selected': 'ui:parent-language-jordan-selected',
    'jordan-offline-final': 'ui:parent-language-jordan-enabled-zh-hans',
    **custom_child_selection('final-riley', 'child'),
    'final-riley-selected': 'ui:parent-language-riley-selected',
    'riley-offline-final': 'ui:parent-language-riley-enabled-zh-hans',
    'parent-final-choice': 'ui:parent-language-open', 'parent-final-close': 'ui:parent-language-cancel',
    'offline-restore': 'ui:parent-language-riley-enabled-zh-hans',
    'riley-online-final': 'ui:parent-language-riley-enabled-zh-hans',
    **custom_child_selection('online-jordan', 'existing'),
    'online-jordan-selected': 'ui:parent-language-jordan-selected',
    'jordan-online-final': 'ui:parent-language-jordan-enabled-zh-hans',
}
SCREENS = {**SETUP, **PARENT, **STATION, **OVERLAY, **FINAL}
ASSERTIONS = {'initial-language': 'initial-english-native-names', 'offline-enter': 'confirmed-offline',
    'riley-before': 'riley-policy-captured', 'jordan-before': 'jordan-policy-captured',
    'parent-riley-state': 'chinese-riley', 'parent-jordan-state': 'chinese-jordan', 'parent-riley-return-state': 'chinese-riley-return',
    'reopened-choice': 'parent-relaunch-choice', 'jordan-original': 'jordan-request-captured',
    'jordan-german': 'german-form', 'riley-original': 'riley-request-captured', 'riley-hebrew': 'hebrew-form',
    'cancel-retained': 'cancel-preserved-hebrew', 'jordan-casey-choice': 'jordan-approver-independent',
    'riley-casey-choice': 'riley-approver-independent', 'jordan-reentered': 'german-reentry',
    'riley-reentered': 'hebrew-reentry', 'direct-form': 'overlay-kiosk-sharing',
    'relaunched-form': 'overlay-relaunch', 'renewed-overlay-form': 'renewed-session-language',
    'jordan-offline-final': 'jordan-offline-policy', 'riley-offline-final': 'riley-offline-policy',
    'parent-final-choice': 'parent-child-independent', 'offline-restore': 'confirmed-online-recovery',
    'riley-online-final': 'riley-final-policy', 'jordan-online-final': 'jordan-final-policy'}
PLAN = JourneyPlan(prefix='language-persistence', worker_mode='language_persistence', screen_tags=SCREENS,
    phases={'ready': 'setup', 'setup-detached': 'setup',
        **{stage: 'step-1' for stage in SETUP}, 'installed-greeter': 'start',
        **{stage: 'step-2' for stage in PARENT}, **{stage: 'step-3' for stage in STATION},
        **{stage: 'step-4' for stage in OVERLAY}, **{stage: 'step-5' for stage in FINAL}},
    invocations=tuple(stage for stage in SCREENS if stage in (*INITIAL, *CHILD, *RENEWED, *RETURN,
        'direct-launch', 'direct-form', 'relaunched-launch', 'relaunched-form',
        'renewed-overlay-launch', 'renewed-overlay-form')),
    challenges={'parent-login': ('parent', 'recipient-qualified', 'recipient-rechecked'),
        'child': ('child', 'child-child-recipient-qualified', 'child-child-recipient-rechecked'),
        'renewed': ('child', 'renewed-child-recipient-qualified', 'renewed-child-recipient-rechecked'),
        'return': ('parent', 'return-recipient-qualified', 'return-recipient-rechecked')},
    stage_actions={'offline-enter': 'language-offline', 'offline-restore': 'language-online'},
    assertions_after=ASSERTIONS)

# Independent literal visible/accessibility oracles, including names and numbers.
TEXT = {'en': ('English', 'Choose your language', 'Save', 'Save your language preference.'),
    'de': ('Deutsch', 'Sprache wählen', 'Speichern', 'Die Spracheinstellung speichern.'),
    'zh-Hans': ('中文（简体）', '选择语言', '保存', '保存语言偏好设置。'),
    'he': ('עברית', 'בחירת השפה שלך', 'שמירה', 'שמירת העדפת השפה שלך.')}
CHOOSERS = {language: {'initial': False, 'checked': 'zh-hans' if language == 'zh-Hans' else language,
    'choices': {key: item[0] for key, item in TEXT.items()}, 'heading': text[1],
    'save': text[2], 'save_label': text[2], 'save_description': text[3]} for language, text in TEXT.items()}
CHOICE_LANGUAGES = {'initial-language': 'en', 'chinese-open': 'en', 'chinese-choose': 'zh-Hans',
    **{stage: 'zh-Hans' for stage in
        ('parent-riley-choice', 'parent-jordan-choice', 'parent-riley-return-choice', 'reopened-choice', 'parent-final-choice')},
    'station-initial-language': 'en', 'german-open': 'en', 'german-choose': 'de',
    'hebrew-open': 'en', 'hebrew-choose': 'he',
    'cancel-german-open': 'he', 'cancel-german-choose': 'de',
    'cancel-retained': 'he', 'jordan-choice': 'de', 'jordan-casey-choice': 'de',
    'riley-choice': 'he', 'riley-casey-choice': 'he', 'jordan-reentered-choice': 'de',
    'riley-reentered-choice': 'he', 'overlay-choice': 'he', 'relaunched-choice': 'he', 'renewed-choice': 'he'}
CHECKS = {stage: public_language_value('language', {**CHOOSERS[language],
    'initial': stage in ('initial-language', 'station-initial-language')})
    for stage, language in CHOICE_LANGUAGES.items()}
LABELS = {'en': ('Screen Time Limit', 'Daily Time Allowance', "Today's Remaining Time"),
    'zh-Hans': ('限制屏幕时间', '每日可用时间', '今日剩余时间')}
for stage, tag in SCREENS.items():
    if '-enabled-' in tag and tag[:19] == 'ui:parent-language-':
        name = 'riley' if '-riley-' in tag else 'jordan'
        language = 'en' if tag[-3:] == '-en' else 'zh-Hans'
        CHECKS[stage] = language_policy({'child': 'fixture-child' if name == 'riley' else 'existing-fixture-child',
            'account_name': 'Riley (Child)' if name == 'riley' else 'Jordan (Child)', 'limit_enabled': True,
            'allowance_minutes': 60, 'chooser_absent': True,
            'management': 'Screen time limit' if language == 'en' else '限制屏幕时间'},
            capture=name if stage == name + '-before' else None,
            same=None if stage == name + '-before' else name, max_elapsed_seconds=2400,
            labels=LABELS[language], absent_labels=LABELS['zh-Hans' if language == 'en' else 'en'])
FORM_TEXT = {'en': ('Child', 'Approver', '30 minutes', 'REQUEST', 'CANCEL'),
    'de': ('Kind', 'Genehmigung durch', '30 Minuten', 'ANFRAGEN', 'Abbrechen'),
    'he': ('ילד', 'מאשר', '30 דקות', 'בקשה', 'ביטול')}
# The reader's texts contain accessible names; labels contain visible captions.
# Preserve the descriptive button names established by kiosk_language.FORM.
FORM_NAMES = {'en': ('Request access', 'Cancel request'),
    'de': ('Zugriff anfragen', 'Anfrage abbrechen'),
    'he': ('בקשת גישה', 'ביטול הבקשה')}
FORM_IDS = ('kiosk-child-account-caption', 'kiosk-approver-account-caption', 'kiosk-duration-label-1800',
    'kiosk-request-submit', 'kiosk-request-cancel')
FORM_STAGES = {'jordan-original': ('jordan', 'en', 'jamie', False),
    'jordan-german': ('jordan', 'de', 'jamie', False), 'riley-original': ('riley', 'en', 'jamie', False),
    **{stage: ('riley', 'he', 'jamie', False) for stage in
        ('riley-hebrew', 'riley-cancelled', 'riley-restored-form', 'riley-reentered')},
    **{stage: ('jordan', 'de', 'jamie', False) for stage in ('jordan-restored-form', 'jordan-reentered')},
    'jordan-casey': ('jordan', 'de', 'casey', False), 'riley-casey': ('riley', 'he', 'casey', False),
    **{stage: ('riley', 'he', 'casey', True) for stage in ('direct-form', 'relaunched-form', 'renewed-overlay-form')}}
for stage, (child, language, approver, overlay) in FORM_STAGES.items():
    texts = FORM_TEXT[language]
    CHECKS[stage] = public_language_value('language_form', {
        'texts': dict(zip(FORM_IDS, (*texts[:3], *FORM_NAMES[language]))),
        'labels': {FORM_IDS[3]: texts[3], FORM_IDS[4]: texts[4]}, 'chooser_absent': True,
        'request': {'surface': 'child-overlay' if overlay else 'kiosk', 'form_count': 1,
            'child': 'fixture-child' if child == 'riley' else 'existing-fixture-child',
            'approver': 'fixture-parent' if approver == 'jamie' else 'other-fixture-parent',
            'duration_seconds': 75, 'custom_text': '1.25', 'allow_soft': True,
            'child_selector_enabled': not overlay, 'approver_selector_enabled': True,
            'duration_enabled': True, 'soft_choice_enabled': True, 'request_enabled': True,
            'cancel_enabled': True, 'message': '', 'mute': None}})


def execute(recorder, context):
    record_installed_journey(recorder, context, PLAN, timeout=2400,
        actions=offline_language_actions(), journey_type=language_journey(checks=CHECKS))


E2E_CASES = {'account-offline': execute}
