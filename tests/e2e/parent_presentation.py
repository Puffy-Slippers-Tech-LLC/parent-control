"""Case 256: complete Parent English → Hebrew → English policy/dialog history."""
from installed_journey import JourneyPlan, record_installed_journey
from journey_blocks import fresh_desktop, custom_child_selection, language_selection
from feedback_composition import text_fragment
from language_composition import language_journey, public_language_value, language_policy
from journey_checks import public_checks

ENTRY = fresh_desktop('parent')
SETUP = {
    **ENTRY, 'parent-command': 'ui:parent-command-launch',
    'initial-language': 'ui:parent-language-initial', 'initial-save': 'ui:parent-language-save',
    **custom_child_selection('riley-setup', 'child', route='keyboard'),
    'riley-enabled': 'ui:parent-toggle-enabled', 'riley-saved': 'ui:parent-save-enabled',
    'riley-allowance': 'ui:parent-language-riley-allowance',
    'policy-captured': 'ui:parent-language-riley-enabled-en',
    'feedback-empty': 'ui:parent-dialog-feedback-en-empty',
    **text_fragment('body-rtl'), **text_fragment('reply-rtl'),
    'draft-captured': 'ui:parent-dialog-feedback-en-read',
    'draft-close': 'ui:parent-dialog-feedback-en-close-ready',
    'draft-closed': 'ui:parent-dialog-feedback-en-closed',
}
SCREENS = dict(SETUP)
PHASES = {'ready': 'setup', 'setup-detached': 'setup',
          **{stage: 'step-1' for stage in SETUP}, 'installed-greeter': 'start'}
ASSERTIONS = {'initial-language': 'untouched-english-native-names',
              'policy-captured': 'immutable-english-policy', 'draft-captured': 'mixed-script-draft'}
ADVANCE = {'draft-closed': 'step-2', 'english-entry-final': 'step-3', 'hebrew-final': 'step-4'}
HISTORY = (('english-entry', 'en', 'step-2'), ('hebrew', 'he', 'step-3'),
           ('english-return', 'en', 'step-4'))
for prefix, selected, phase in HISTORY:
    section = {} if prefix == 'english-entry' else {
        **language_selection(prefix, selected, surface='parent'),
        prefix + '-save': 'ui:parent-language-save',
        prefix + '-state': 'ui:parent-language-riley-enabled-' + selected,
    }
    for surface in ('about', 'feedback'):
        section.update({prefix + '-' + surface + '-' + action:
                        'ui:parent-dialog-' + surface + '-' + selected + '-' +
                        ('close-ready' if action == 'close' else action)
                        for action in ('open', 'close', 'closed')})
        ASSERTIONS[prefix + '-' + surface + '-open'] = prefix + '-' + surface + '-inherited'
    section[prefix + '-final'] = 'ui:parent-language-riley-enabled-' + selected
    ASSERTIONS[prefix + '-final'] = prefix + '-policy-preserved'
    SCREENS.update(section)
    PHASES.update({stage: phase for stage in section})

PLAN = JourneyPlan(prefix='parent-presentation', worker_mode='parent_presentation',
    screen_tags=SCREENS, phases=PHASES, invocations=tuple(ENTRY),
    challenges={'parent-login': ('parent', 'recipient-qualified', 'recipient-rechecked')},
    assertions_after=ASSERTIONS, advance_after=ADVANCE)

# Independent literals; no product translation context or qualification recipe.
NATIVE = {'en': 'English', 'de': 'Deutsch', 'zh-Hans': '中文（简体）', 'he': 'עברית'}
TEXT = {'en': ('Choose your language', 'Save', 'Save your language preference.', 'Screen time limit'),
        'he': ('בחירת השפה שלך', 'שמירה', 'שמירת העדפת השפה שלך.', 'מגבלת זמן מסך')}
LABELS = {'en': ('Screen Time Limit', 'Daily Time Allowance', "Today's Remaining Time"),
          'he': ('מגבלת זמן מסך', 'מכסת זמן יומית', 'הזמן שנותר היום')}
DIALOG_LABELS = {
    'en': {'about': {'about-website-label': 'Website', 'about-privacy-label': 'Privacy',
                    'about-privacy-value': 'Privacy policy'},
           'feedback': {'feedback-close': 'Close', 'feedback-send': 'Send Feedback',
                        'feedback-reply-email': 'Reply email (optional)'}},
    'he': {'about': {'about-website-label': 'אתר', 'about-privacy-label': 'פרטיות',
                    'about-privacy-value': 'מדיניות פרטיות'},
           'feedback': {'feedback-close': 'סגירה', 'feedback-send': 'שליחת משוב',
                        'feedback-reply-email': 'דוא״ל לתשובה (לא חובה)'}},
}
DRAFT = {'draft': 'synthetic-rtl', 'attachments': ['diagnostic-logs.zip'],
         'collection': 'ready', 'validation': 'none', 'controls': 'ready'}
CHECKS = {'initial-language': public_language_value('language', {
    'initial': True, 'checked': 'en', 'choices': NATIVE, 'heading': TEXT['en'][0],
    'save': TEXT['en'][1], 'save_label': TEXT['en'][1], 'save_description': TEXT['en'][2]})}
POLICY_LANGUAGES = {'policy-captured': 'en'}
CHOICE_LANGUAGES = {}
for prefix, selected, _phase in HISTORY:
    previous = 'he' if prefix == 'english-return' else 'en'
    if prefix != 'english-entry':
        CHOICE_LANGUAGES.update({prefix + '-open': previous, prefix + '-choose': selected})
        POLICY_LANGUAGES[prefix + '-state'] = selected
    POLICY_LANGUAGES[prefix + '-final'] = selected
    for surface in ('about', 'feedback'):
        for action in ('open',):
            check = public_language_value('dialog_presentation', {
                'surface': surface, 'language': selected, 'labels': DIALOG_LABELS[selected][surface]})
            CHECKS[prefix + '-' + surface + '-' + action] = (
                public_checks(check, public_language_value('feedback', DRAFT, same='original-draft'))
                if surface == 'feedback' else check)
for stage, selected in CHOICE_LANGUAGES.items():
    CHECKS[stage] = public_language_value('language', {
        'initial': False, 'checked': selected, 'choices': NATIVE, 'heading': TEXT[selected][0],
        'save': TEXT[selected][1], 'save_label': TEXT[selected][1], 'save_description': TEXT[selected][2]})
for stage, selected in POLICY_LANGUAGES.items():
    CHECKS[stage] = language_policy({'child': 'fixture-child', 'account_name': 'Riley (Child)',
        'limit_enabled': True, 'allowance_minutes': 60, 'chooser_absent': True,
        'management': TEXT[selected][3]}, capture='original-policy' if stage == 'policy-captured' else None,
        same=None if stage == 'policy-captured' else 'original-policy', max_elapsed_seconds=600,
        labels=LABELS[selected], absent_labels=LABELS['he' if selected == 'en' else 'en'])
CHECKS['draft-captured'] = public_language_value('feedback', DRAFT, capture='original-draft')


def execute(recorder, context):
    return record_installed_journey(recorder, context, PLAN,
                                    journey_type=language_journey(checks=CHECKS))


E2E_CASES = {'parent-hebrew': execute}
