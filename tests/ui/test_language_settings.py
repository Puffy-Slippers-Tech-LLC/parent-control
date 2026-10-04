"""Localization's chooser contract through real GTK and shared E2E actions."""

import pytest

from tests.support.events import read_events
from tests.support.feedback import feedback_editor
from tests.support.localization_review import public_label_names


pytestmark = pytest.mark.ui
SURFACES = ('parent', 'kiosk', 'overlay')
# Independent text oracles: do not load the same catalogue as the app to predict it.
LANGUAGES = {
    'en': ('en_US.UTF-8', 'English', 'Choose your language', 'Save',
           'Save your language preference.', 'Screen time limit', 'REQUEST',
           'Request unavailable'),
    'de': ('de_DE.UTF-8', 'Deutsch', 'Sprache wählen', 'Speichern',
           'Die Spracheinstellung speichern.', 'Bildschirmzeit begrenzen', 'ANFRAGEN',
           'Anfrage nicht verfügbar'),
    'zh-Hans': ('zh_CN.UTF-8', '中文（简体）', '选择语言', '保存',
                '保存语言偏好设置。', '限制屏幕时间', '提交请求', '暂时无法提交请求'),
}
# Literal meanings reviewed independently of the catalog author and runtime.
EXPANDED_LANGUAGES = {
    'ar': ('العربية', 'اختر لغتك', 'حفظ', 'احفظ تفضيل اللغة لديك.',
           'حد وقت استخدام الشاشة', 'طلب'),
    'fa': ('فارسی', 'زبان خود را انتخاب کنید', 'ذخیره', 'ترجیح زبان خود را ذخیره کنید.',
           'محدودیت زمان استفاده از صفحه', 'درخواست'),
    'he': ('עברית', 'בחירת השפה שלך', 'שמירה', 'שמירת העדפת השפה שלך.',
           'מגבלת זמן מסך', 'בקשה'),
    'pt': ('Português', 'Escolha a sua língua', 'Guardar', 'Guardar a sua preferência de língua.',
           'Limite de tempo de ecrã', 'SOLICITAR'),
    'zh-Hant': ('中文（繁體）', '選擇語言', '儲存', '儲存語言偏好設定。', '限制螢幕時間', '提交請求'),
    'bn': ('বাংলা', 'আপনার ভাষা বেছে নিন', 'সংরক্ষণ', 'আপনার ভাষার পছন্দ সংরক্ষণ করুন।',
           'স্ক্রিন সময়ের সীমা', 'অনুরোধ'),
    'hi': ('हिन्दी', 'अपनी भाषा चुनें', 'सहेजें', 'अपनी भाषा की प्राथमिकता सहेजें।',
           'स्क्रीन समय सीमा', 'अनुरोध'),
    'ug': ('ئۇيغۇرچە', 'تىلىڭىزنى تاللاڭ', 'ساقلاش', 'تىل مايىللىقىڭىزنى ساقلاڭ.',
           'ئېكران ۋاقىت چەكلىمىسى', 'تەلەپ'),
    'ur': ('اردو', 'اپنی زبان منتخب کریں', 'محفوظ کریں', 'اپنی زبان کی ترجیح محفوظ کریں۔',
           'اسکرین ٹائم کی حد', 'درخواست'),
    'fur': ('Furlan', 'Sielç la tô lenghe', 'Salve', 'Salve la tô preference di lenghe.',
            'Limit dal timp di schermi', 'DOMANDE'),
    'ta': ('தமிழ்', 'உங்கள் மொழியைத் தேர்ந்தெடுக்கவும்', 'சேமிக்கவும்',
           'உங்கள் மொழி விருப்பத்தைச் சேமிக்கவும்.', 'திரை நேர வரம்பு', 'கோரிக்கை'),
}


def launch_language(launch_ui, tmp_path, surface, *, language='', session='en',
                    save_failures=0, load_failures=0, release=None, scenario='normal',
                    child_desktop='', language_delay=0):
    path = tmp_path / 'language-events.jsonl'
    environment = {
        'ONPC_LANGUAGE_INITIAL': language,
        'ONPC_LANGUAGE_SAVE_FAILURES': str(save_failures),
        'ONPC_LANGUAGE_LOAD_FAILURES': str(load_failures),
        'ONPC_LANGUAGE_SAVE_RELEASE': str(release or ''),
        'LANGUAGE': LANGUAGES[session][0], 'LC_ALL': 'C.UTF-8', 'LANG': 'C.UTF-8',
        'ONPC_PARENT_COMPONENT_EVENTS_PATH': str(path),
        'ONPC_REQUEST_COMPONENT_EVENTS_PATH': str(path),
        'ONPC_REQUEST_COMPONENT_OVERLAY': '1' if surface == 'overlay' else '0',
        'ONPC_REQUEST_COMPONENT_SCENARIO': scenario,
        'ONPC_CHILD_1001_DESKTOP_LANGUAGE': child_desktop,
        'ONPC_CHILD_LANGUAGE_DELAY_MS': str(language_delay),
    }
    launch_ui('parent_component_preview' if surface == 'parent' else 'request_component_preview',
              complete_language_setup=False, environment_overrides=environment)
    return path


@pytest.mark.parametrize('scenario', ('normal', 'reboot-required'))
@pytest.mark.parametrize('language,saved,desktop', (
    ('zh-Hans', '', 'zh_CN.UTF-8'), ('de', '', 'de_DE.UTF-8'),
    ('de', 'de', 'zh_CN.UTF-8'),
))
def test_kiosk_initial_language_uses_child_account_in_english_station(
        launch_ui, automation, wait_for_accessible_state, tmp_path,
        scenario, language, saved, desktop):
    ui, wait = automation, wait_for_accessible_state
    path = launch_language(launch_ui, tmp_path, 'kiosk', language=saved,
                          child_desktop=desktop, scenario=scenario, language_delay=300)
    if scenario == 'reboot-required':
        wait(lambda: ui.showing('update-required-dialog'), 'localized update notice opens')
        expected = {
            'zh-Hans': ('请重启计算机，以使 Oh No! Parent Control 正常工作。', '立即重启', '需要重启'),
            'de': ('Starten Sie den Computer neu, damit Oh No! Parent Control ordnungsgemäß funktioniert.',
                   'Jetzt neu starten', 'Neustart erforderlich'),
        }[language]
        assert ui.text('update-required-message') == expected[0]
        assert ui.text('update-required-reboot') == expected[1]
        assert ui.text('kiosk-result-title') == expected[2]
        assert ui.absent('language-dialog', within='kiosk-request-window')
        assert not committed(path)
        assert not [event for event in read_events(path) if event['event'] == 'reboot-requested']
    else:
        if not saved:
            wait(lambda: ui.showing('language-dialog'), 'child-language chooser opens')
            assert ui.text('language-title') == LANGUAGES[language][2]
            assert ui.text('language-continue') == LANGUAGES[language][3]
            assert ui.state('language-choice-' + language.lower(), ui.api.StateType.CHECKED)
            ui.reader.cancel_language('kiosk')
            assert not committed(path)
        else:
            wait(lambda: ui.showing('kiosk-language-ready'), 'saved language is ready')
            assert ui.absent('language-dialog', within='kiosk-request-window')
        assert_surface_language(ui, wait, 'kiosk', language)
        ui.activate('kiosk-request-submit')
        wait(lambda: ui.showing('kiosk-result-title'), 'request completes after agent preparation')
        records = read_events(path)
        prepared = [event for event in records if event['event'] == 'agent-language-prepared']
        assert prepared == [{'event': 'agent-language-prepared', 'language': language,
                             'desktop_language': desktop}]
        preparation = records.index(prepared[0])
        approval = next(index for index, event in enumerate(records)
                        if event.get('method') == 'RequestAccess')
        assert preparation < approval


def frontend(surface):
    return 'parent' if surface == 'parent' else 'kiosk'


@pytest.mark.parametrize('scenario', ('normal', 'reboot-required'))
def test_chinese_initial_e2e_reader_uses_real_owned_controls(
        launch_ui, automation, wait_for_accessible_state, tmp_path, monkeypatch, scenario):
    from tests.e2e import accessible_ui as module
    from tests.e2e.chinese_kiosk_lifecycle import NOTICE, FORM, CHOOSER

    # The existing private preview owns its bus, display and process. Bind its
    # finite child UID to the installed reader's role, without changing owners.
    path = launch_language(launch_ui, tmp_path, 'kiosk',
                          child_desktop='zh_CN.UTF-8', scenario=scenario)
    reader = automation.reader
    monkeypatch.setattr(reader, 'fixture_uids', {module.EXISTING_CHILD: 1001})
    wait_for_accessible_state(
        lambda: automation.showing('update-required-dialog' if scenario == 'reboot-required'
                                  else 'language-dialog'), 'Chinese initial presentation')
    if scenario == 'reboot-required':
        first = reader.initial_kiosk_presentation('notice')
        assert first['texts'] == NOTICE
        assert reader.close_initial_notice() == first
        assert automation.showing('kiosk-result-action')
        assert not [event for event in read_events(path) if event['event'] == 'reboot-requested']
    else:
        first = reader.initial_kiosk_presentation('language')
        assert first['texts'] == {**FORM, **CHOOSER}
        assert first['default_chinese'] is True
        assert reader.cancel_initial_language() == first
        assert reader.initial_kiosk_presentation('form')['texts'] == FORM
    assert not committed(path)
    records = read_events(path)
    assert not [event for event in records if event.get('method') in (
        'RequestOwnAccess', 'RequestAccess', 'UpdateRequestPreferences', 'SetRequestMuted')]
    assert not [event for event in records if event['event'] in (
        'set_preferences', 'set_parent_control', 'revoke_one_time_grant', 'feedback',
        'logout', 'close_overlay', 'language-committed', 'reboot-requested')]


def committed(path):
    return [event['language'] for event in read_events(path)
            if event['event'] == 'language-committed']


def test_installed_parent_chooser_reader_observes_first_run_and_preferences(
        launch_ui, automation, wait_for_accessible_state, tmp_path):
    """The installed reader sees the real GTK chooser without automatic Save."""
    ui, wait = automation, wait_for_accessible_state
    path = launch_language(launch_ui, tmp_path, 'parent')
    wait(lambda: ui.showing('language-dialog'), 'untouched Parent chooser')
    first = ui.reader.read_parent_language(initial=True)
    assert first == {'initial': True, 'checked': 'en',
        'choices': {'en': 'English', 'de': 'Deutsch', 'zh-Hans': '中文（简体）', 'he': 'עברית'},
        'heading': 'Choose your language', 'save': 'Save', 'save_label': 'Save',
        'save_description': 'Save your language preference.'}
    assert committed(path) == []
    ui.reader.save_language('parent')
    ui.reader.open_language_preferences('parent')
    reopened = ui.reader.read_parent_language()
    assert reopened == {**first, 'initial': False}
    ui.reader.choose_language('parent', 'he')
    hebrew = ui.reader.read_parent_language()
    assert hebrew == {**reopened, 'checked': 'he', 'heading': 'בחירת השפה שלך',
                     'save': 'שמירה', 'save_label': 'שמירה', 'save_description': 'שמירת העדפת השפה שלך.'}
    ui.reader.cancel_language('parent')
    assert committed(path) == ['en']


@pytest.mark.parametrize('language,accessible,title', [
    ('en', 'Screen time limit', 'Screen Time Limit'),
    ('de', 'Bildschirmzeit begrenzen', 'Bildschirmzeit begrenzen'),
    ('zh-Hans', '限制屏幕时间', '限制屏幕时间'),
    ('he', 'מגבלת זמן מסך', 'מגבלת זמן מסך'),
])
def test_installed_parent_management_reader_keeps_visible_and_accessible_text_separate(
        launch_ui, automation, wait_for_accessible_state, tmp_path, language, accessible, title):
    ui, wait = automation, wait_for_accessible_state
    path = launch_language(launch_ui, tmp_path, 'parent', language='en')
    wait(lambda: ui.showing('parent-language-ready'), 'saved startup ready')
    ui.reader.open_language_preferences('parent')
    ui.reader.choose_language('parent', language)
    ui.reader.save_language('parent')
    value = ui.reader.parent_language_management()
    assert value['management'] == accessible
    assert title in value['management_labels']
    assert_no_policy_or_request_writes(path)


def assert_no_policy_or_request_writes(path, *, expected_results=0):
    records = read_events(path)
    assert not [event for event in records if event['event'] in (
        'set_preferences', 'set_parent_control', 'revoke_one_time_grant',
        'feedback', 'logout', 'close_overlay')]
    # Results are presentation events, not broker writes. Only the declared
    # startup-error scenario may produce one without submitting a request.
    assert len([event for event in records if event['event'] == 'result']) == expected_results
    assert not [event for event in records if event.get('method') in (
        'RequestOwnAccess', 'RequestAccess', 'UpdateRequestPreferences', 'SetRequestMuted')]


@pytest.mark.parametrize('language', ('en', 'de', 'zh-Hans', 'he'))
@pytest.mark.parametrize('surface', ('kiosk', 'overlay'))
def test_installed_kiosk_chooser_and_form_readers_through_real_gtk(
        launch_ui, automation, wait_for_accessible_state, tmp_path, monkeypatch, language, surface):
    from kiosk_language import CHOOSER, FORM, TEXT_IDS
    ui, wait = automation, wait_for_accessible_state
    path = launch_language(launch_ui, tmp_path, surface, scenario='installed-language')
    wait(lambda: ui.showing('language-dialog'), 'untouched kiosk chooser')
    # Preview UIDs differ from the installed fixture; only the account mapping
    # is supplied. The complete operation reads the actual selected public ID.
    ui.reader.fixture_uids = {'Jordan (Child)': 1001, 'Jamie (Parent)': 1000,
                             'Riley (Child)': 1002, 'Casey (Parent)': 1010}
    if surface == 'overlay':
        # Host preview has no installed Riley session. Only that transport guard
        # is doubled; all application ownership, public IDs and GTK reads are real.
        monkeypatch.setattr(ui.reader, 'require_child_overlay_session', lambda: None)
    operation = ui.reader.overlay_language_operation if surface == 'overlay' else ui.reader.kiosk_language_operation
    reader = ui.reader.read_overlay_language if surface == 'overlay' else ui.reader.read_kiosk_language
    initial = operation(surface + '-language-initial')['language']
    assert initial == {'initial': True, 'checked': 'en',
        'choices': {key: texts[0] for key, texts in CHOOSER.items()},
        'heading': 'Choose your language', 'save': 'Save', 'save_label': 'Save',
        'save_description': 'Save your language preference.'}
    assert committed(path) == []
    ui.reader.save_language(surface)
    ui.reader.open_language_preferences(surface)
    ui.reader.choose_language(surface, language)
    candidate = reader()
    text = CHOOSER[language]
    assert candidate == {**initial, 'initial': False, 'checked': language.lower(),
        'heading': text[1], 'save': text[2], 'save_label': text[2], 'save_description': text[3]}
    ui.reader.save_language(surface)
    value = ui.reader.kiosk_language_form(language, overlay=surface == 'overlay')
    text = FORM[language]
    assert value['texts'] == dict(zip(TEXT_IDS, (*text[:3], text[4], text[6])))
    assert value['labels'] == {TEXT_IDS[3]: text[3], TEXT_IDS[4]: text[5]}
    ui.reader.open_language_preferences(surface)
    assert reader() == candidate
    ui.reader.cancel_language(surface)
    assert committed(path) == ['en', language]
    assert_no_policy_or_request_writes(path)


def test_kiosk_shared_selector_restores_per_child_language_and_approver_independence(
        launch_ui, automation, wait_for_accessible_state, tmp_path):
    from accessible_ui import CHILD, EXISTING_CHILD, PARENT, OTHER_PARENT
    from kiosk_language import FORM, TEXT_IDS
    ui, wait = automation, wait_for_accessible_state
    path = launch_language(launch_ui, tmp_path, 'kiosk', scenario='installed-language')
    ui.reader.fixture_uids = {EXISTING_CHILD: 1001, CHILD: 1002, PARENT: 1000, OTHER_PARENT: 1010}
    wait(lambda: ui.showing('language-dialog'), 'initial Jordan language')
    ui.reader.kiosk_language_operation('kiosk-language-initial')
    ui.reader.kiosk_language_operation('kiosk-language-save')
    ui.reader.kiosk_language_operation('kiosk-language-open')
    ui.reader.kiosk_language_operation('kiosk-language-choose-de')
    ui.reader.kiosk_language_operation('kiosk-language-save')
    ui.reader.select_kiosk_account('child', CHILD, expected=(CHILD, EXISTING_CHILD),
        child=EXISTING_CHILD, language='de', result_language='en')
    ui.reader.kiosk_language_operation('kiosk-riley-language-open')
    ui.reader.kiosk_language_operation('kiosk-riley-language-choose-he')
    ui.reader.kiosk_language_operation('kiosk-riley-language-save')
    current, language = CHILD, 'he'
    baselines = {}
    for target, retained in ((EXISTING_CHILD, 'de'), (CHILD, 'he'), (EXISTING_CHILD, 'de')):
        selected = ui.reader.select_kiosk_account('child', target, expected=(CHILD, EXISTING_CHILD),
            child=current, language=language, result_language=retained)
        current, language = target, retained
        owner = 'kiosk' if target == EXISTING_CHILD else 'kiosk-riley'
        for approver in (PARENT, OTHER_PARENT, PARENT):
            selected = ui.reader.select_kiosk_account('approver', approver, expected=(PARENT, OTHER_PARENT),
                child=current, language=language)
            form = ui.reader.kiosk_language_form(language, child=current)
            text = FORM[language]
            assert form['texts'] == dict(zip(TEXT_IDS, (*text[:3], text[4], text[6])))
            assert form['labels'] == {TEXT_IDS[3]: text[3], TEXT_IDS[4]: text[5]}
            assert form['request'] == selected
            projection = {key: value for key, value in selected.items() if key != 'approver'}
            baselines.setdefault(current, projection)
            assert projection == baselines[current]
            checked = ui.reader.kiosk_language_operation(owner + '-language-open')['language']
            assert checked['checked'] == language and checked['initial'] is False
            ui.reader.kiosk_language_operation(owner + '-language-cancel')
    assert committed(path) == ['en', 'de', 'he']
    records = read_events(path)
    assert not [event for event in records if event['event'] in (
        'set_preferences', 'set_parent_control', 'revoke_one_time_grant',
        'feedback', 'logout', 'close_overlay', 'result')]
    assert not [event for event in records if event.get('method') in (
        'RequestOwnAccess', 'RequestAccess', 'SetRequestMuted')]
    # Public approver selection persists request choices. It must preserve the
    # default duration, hidden custom value and excluded soft apps for each child.
    updates = [event['values'] for event in records if event.get('method') == 'UpdateRequestPreferences']
    assert updates and {value[0] for value in updates} == {1001, 1002}
    assert all(value[1:4] == ['1800', 7.5, False] and value[4] in (1000, 1010) for value in updates)
    for uid in (1001, 1002):
        assert [value for value in updates if value[0] == uid][-1][4] == 1000


def assert_surface_language(ui, wait, surface, language):
    identity = 'parent-screen-limit-toggle' if surface == 'parent' else 'kiosk-request-submit'
    expected = LANGUAGES[language][5 if surface == 'parent' else 6]
    wait(lambda: ui.text(identity) == expected, 'surface uses the committed language')


@pytest.mark.parametrize('surface', SURFACES)
@pytest.mark.parametrize('dpi_scale', (1, 1.25))
def test_language_search_is_accessible_and_keyboard_operable(
        launch_ui, automation, wait_for_accessible_state, tmp_path, surface,
        request_display_scale, dpi_scale):
    from tests.support.automation_ids import audit_product_controls
    from tests.support.keyboard import press_key, type_text

    ui, wait = automation, wait_for_accessible_state
    path = launch_language(launch_ui, tmp_path, surface)
    wait(lambda: ui.showing('language-search'), 'search is publicly accessible')
    inventory = audit_product_controls(ui, 'language-dialog')
    assert inventory['language-list'].get_name() == 'Language'
    assert inventory['language-list'].get_description() == 'Choose your language'
    search = inventory['language-search']
    assert search.get_name() == 'Search languages'
    assert search.get_description() == 'Search languages'
    assert search.get_role_name() == 'entry'
    assert search.get_text_iface() is not None
    assert search.get_state_set().contains(ui.api.StateType.EDITABLE)
    ui.focus('language-search')
    type_text(ui, 'language-search', 'PORT*BR')
    wait(lambda: ui.content('language-search') == 'PORT*BR'
         and ui.showing('language-choice-pt-br')
         and ui.absent('language-choice-en', within='language-dialog'),
         'typing filters without Enter and removes hidden choices from accessibility')
    assert not committed(path)
    press_key(ui, 'language-search', 'Tab', state=ui.api.StateType.FOCUSED)
    wait(lambda: ui.state('language-list', ui.api.StateType.FOCUSED),
         'Tab reaches the scrollable language list')
    press_key(ui, 'language-list', 'Tab', state=ui.api.StateType.FOCUSED)
    wait(lambda: ui.state('language-choice-pt-br', ui.api.StateType.FOCUSED),
         'Tab from the list reaches the matching language')
    press_key(ui, 'language-choice-pt-br', 'space', state=ui.api.StateType.FOCUSED)
    wait(lambda: ui.state('language-choice-pt-br', ui.api.StateType.CHECKED),
         'Space selects the matching language')
    assert ui.text('language-search') == 'Pesquisar idiomas'
    assert ui.target('language-search').get_description() == 'Pesquisar idiomas'
    press_key(ui, 'language-choice-pt-br', 'Escape', state=ui.api.StateType.FOCUSED)
    wait(lambda: ui.content('language-search') == ''
         and ui.state('language-choice-pt-br', ui.api.StateType.FOCUSED),
         'Escape from a language row clears search and preserves focus')
    ui.focus('language-search')
    type_text(ui, 'language-search', 'PORT*BR')
    wait(lambda: ui.absent('language-choice-en', within='language-dialog'),
         'typing filters again')
    press_key(ui, 'language-search', 'Escape', state=ui.api.StateType.FOCUSED)
    wait(lambda: ui.content('language-search') == ''
         and ui.find('language-choice-fur') is not None,
         'Escape restores the complete accessible list')
    assert ui.showing('language-dialog')
    assert ui.state('language-search', ui.api.StateType.FOCUSED)
    assert ui.state('language-choice-pt-br', ui.api.StateType.CHECKED)
    ui.focus('language-choice-fur')
    assert ui.showing('language-choice-fur'), 'last language is keyboard reachable'
    ui.focus('language-search')
    type_text(ui, 'language-search', 'no such language')
    wait(lambda: ui.absent('language-choice-pt-br', within='language-dialog'),
         'empty search result removes the selected row from accessibility')
    assert ui.state('language-search', ui.api.StateType.FOCUSED)
    press_key(ui, 'language-search', 'Tab', state=ui.api.StateType.FOCUSED)
    wait(lambda: ui.state('language-cancel', ui.api.StateType.FOCUSED),
         'Tab skips hidden choices and reaches Cancel')
    ui.reader.cancel_language(frontend(surface))
    assert not committed(path)
    assert_no_policy_or_request_writes(path)


@pytest.mark.parametrize('surface', SURFACES)
@pytest.mark.parametrize('language', LANGUAGES)
def test_first_run_defaults_and_save_waits_for_commit(
        launch_ui, automation, wait_for_accessible_state, tmp_path, surface, language):
    ui, wait = automation, wait_for_accessible_state
    release = tmp_path / 'release-language-save'
    path = launch_language(launch_ui, tmp_path, surface, session=language, release=release)
    scope = frontend(surface)
    wait(lambda: ui.showing('language-dialog'), 'first-run chooser opens')
    choice = 'language-choice-' + language.lower()
    assert ui.state(choice, ui.api.StateType.CHECKED)
    assert ui.text(choice) == LANGUAGES[language][1]
    assert ui.text('language-title') == LANGUAGES[language][2]
    assert ui.text('language-continue') == LANGUAGES[language][3]
    assert ui.target('language-continue').get_description() == LANGUAGES[language][4]
    assert LANGUAGES[language][3] in public_label_names(ui, 'language-dialog')
    assert ui.showing('language-cancel')
    assert not committed(path)
    if surface != 'parent':
        account = {'en': 'For Alex Morgan', 'de': 'Für Alex Morgan',
                   'zh-Hans': '为 Alex Morgan'}[language]
        wait(lambda: ui.text('language-account') == account,
             'chooser identifies the child in the active language')
        assert not ui.state('kiosk-request-submit', ui.api.StateType.SENSITIVE)
    try:
        ui.activate('language-continue')
        wait(lambda: any(event['event'] == 'language-save-started'
                         for event in read_events(path)), 'save reaches the fixture')
        assert ui.showing('language-dialog')
        assert not committed(path)
        disabled = ('language-continue', choice, 'language-cancel', 'language-search')
        for identity in disabled:
            assert not ui.state(identity, ui.api.StateType.SENSITIVE)
    finally:
        # Release the owned worker even if a pre-commit assertion fails.
        release.touch()
    ui.reader.language_save_completed(scope)
    assert committed(path) == [language]
    assert_surface_language(ui, wait, surface, language)
    assert_no_policy_or_request_writes(path)
    ui.reader.open_language_preferences(scope)
    assert ui.state(choice, ui.api.StateType.CHECKED)
    assert ui.showing('language-cancel')
    ui.reader.cancel_language(scope)
    assert committed(path) == [language]


@pytest.mark.parametrize('snap_environment', (False, True), ids=('desktop', 'vscode-snap'))
def test_parent_development_preview_language_keyboard_input(
        launch_ui, automation, wait_for_accessible_state, snap_environment):
    from tests.support.keyboard import press_key, type_text

    ui, wait = automation, wait_for_accessible_state
    environment = {'LANGUAGE': 'en_US.UTF-8', 'LC_ALL': 'C.UTF-8'}
    if snap_environment:
        environment.update({'GDK_BACKEND': 'x11', 'GDK_BACKEND_VSCODE_SNAP_ORIG': '',
                            'GSETTINGS_SCHEMA_DIR': '/nonexistent/vscode-snap-schemas',
                            'GSETTINGS_SCHEMA_DIR_VSCODE_SNAP_ORIG': ''})
    launch_ui('parent_preview', complete_language_setup=False,
              environment_overrides=environment)
    wait(lambda: ui.showing('language-search'), 'development preview chooser opens')
    ui.focus('language-search')
    type_text(ui, 'language-search', 'PORT*BR')
    wait(lambda: ui.content('language-search') == 'PORT*BR'
         and ui.showing('language-choice-pt-br')
         and ui.absent('language-choice-en', within='language-dialog'),
         'native keyboard input filters the preview language list')
    press_key(ui, 'language-search', 'Escape', state=ui.api.StateType.FOCUSED)
    wait(lambda: ui.content('language-search') == '', 'Escape restores the full list')
    ui.focus('language-choice-fur')
    assert ui.showing('language-choice-fur'), 'the last language is reachable by scrolling'
    press_key(ui, 'language-choice-fur', 'space', state=ui.api.StateType.FOCUSED)
    wait(lambda: ui.state('language-choice-fur', ui.api.StateType.CHECKED),
         'the revealed language accepts native keyboard selection')
    ui.focus('language-cancel')
    press_key(ui, 'language-cancel', 'space', state=ui.api.StateType.FOCUSED)
    wait(lambda: ui.absent('language-dialog', within='parent-window'),
         'native Cancel closes the preview chooser')


def test_parent_first_run_shared_helper_saves_with_cancel_visible(
        launch_ui, automation, wait_for_accessible_state, tmp_path):
    ui, wait = automation, wait_for_accessible_state
    path = launch_language(launch_ui, tmp_path, 'parent')
    wait(lambda: ui.showing('language-dialog'), 'first-run chooser opens')
    assert ui.showing('language-cancel')
    ui.complete_parent_language_setup()
    assert committed(path) == ['en']
    assert_surface_language(ui, wait, 'parent', 'en')
    assert_no_policy_or_request_writes(path)


@pytest.mark.parametrize('language', ('ug', 'ur', 'ar', 'de'))
def test_parent_development_preview_translates_visible_labels(
        launch_ui, automation, wait_for_accessible_state, language):
    ui, wait = automation, wait_for_accessible_state
    launch_ui('parent_preview', complete_language_setup=False,
              environment_overrides={'LANGUAGE': 'en_US.UTF-8', 'LC_ALL': 'C.UTF-8'})
    wait(lambda: ui.showing('language-dialog'), 'development preview chooser opens')
    heading, save = (EXPANDED_LANGUAGES[language][1:3] if language in EXPANDED_LANGUAGES
                     else LANGUAGES[language][2:4])
    ui.reader.choose_language('parent', language)
    wait(lambda: ui.text('language-title') == heading, 'candidate translates the visible heading')
    assert save in public_label_names(ui, 'language-continue')
    ui.reader.save_language('parent')
    screen = EXPANDED_LANGUAGES[language][4] if language in EXPANDED_LANGUAGES else LANGUAGES[language][5]
    wait(lambda: ui.text('parent-screen-limit-toggle') == screen, 'preview uses saved language')
    translated_tab = {'ug': 'ئېكران چەكلىمىلىرى', 'ur': 'اسکرین کی حدود',
                      'ar': 'قيود الشاشة', 'de': 'Bildschirmzeit'}[language]
    assert translated_tab in public_label_names(ui, 'parent-page-screen-limits')
    ui.reader.open_language_preferences('parent')
    ui.reader.choose_language('parent', 'en')
    ui.reader.save_language('parent')
    wait(lambda: 'Screen Limits' in public_label_names(ui, 'parent-page-screen-limits'),
         'preview returns its visible labels to English')
    ui.reader.open_language_preferences('parent')
    ui.reader.choose_language('parent', language)
    ui.reader.save_language('parent')
    wait(lambda: translated_tab in public_label_names(ui, 'parent-page-screen-limits'),
         'saving from Preferences retranslates the existing main window')
    headings = {
        'ug': ('ئېكران ۋاقىت چەكلىمىسى', 'كۈندىلىك ۋاقىت مىقدارى', 'بۈگۈنكى قالغان ۋاقىت'),
        'ur': ('اسکرین ٹائم کی حد', 'روزانہ کا مختص وقت', 'آج کا باقی وقت'),
        'ar': ('حد وقت استخدام الشاشة', 'الحصة اليومية للوقت', 'الوقت المتبقي اليوم'),
        'de': ('Bildschirmzeit begrenzen', 'Tägliches Zeitkontingent', 'Heute verbleibende Zeit'),
    }[language]
    assert set(headings) <= set(public_label_names(ui, 'parent-screen-limits-page'))


@pytest.mark.parametrize('surface', SURFACES)
@pytest.mark.parametrize('language', EXPANDED_LANGUAGES)
def test_expanded_catalogue_choices_save_with_translated_text(
        launch_ui, automation, wait_for_accessible_state, tmp_path,
        surface, language):
    """Translated visible/accessibility labels and native names survive Save."""
    ui, wait = automation, wait_for_accessible_state
    native_name, heading, save, description, screen, request = EXPANDED_LANGUAGES[language]
    path = launch_language(launch_ui, tmp_path, surface, language='en')
    scope = frontend(surface)
    wait(lambda: ui.showing(scope + '-language-ready'), 'saved startup ready')
    ui.reader.open_language_preferences(scope)
    choice = 'language-choice-' + language.lower()
    assert ui.text(choice) == native_name
    ui.reader.choose_language(scope, language)
    assert ui.text('language-title') == heading
    assert ui.text('language-continue') == save
    assert ui.target('language-continue').get_description() == description
    ui.reader.save_language(scope)
    assert committed(path) == [language]
    identity = 'parent-screen-limit-toggle' if surface == 'parent' else 'kiosk-request-submit'
    wait(lambda: ui.text(identity) == (screen if surface == 'parent' else request),
         'surface uses independently verified translated text')
    ui.reader.open_language_preferences(scope)
    assert ui.state(choice, ui.api.StateType.CHECKED)
    assert ui.text(choice) == native_name
    ui.reader.cancel_language(scope)
    assert_no_policy_or_request_writes(path)


@pytest.mark.parametrize('surface', SURFACES)
def test_parent_first_run_cancel_leaves_language_unset(
        launch_ui, automation, wait_for_accessible_state, tmp_path, surface):
    ui, wait = automation, wait_for_accessible_state
    path = launch_language(launch_ui, tmp_path, surface)
    scope = frontend(surface)
    wait(lambda: ui.showing('language-dialog'), 'first-run chooser opens')
    ui.reader.choose_language(scope, 'de')
    ui.reader.cancel_language(scope)
    assert_surface_language(ui, wait, surface, 'en')
    assert not committed(path)
    ui.reader.open_language_preferences(scope)
    assert ui.state('language-choice-en', ui.api.StateType.CHECKED)
    ui.reader.cancel_language(scope)
    assert_no_policy_or_request_writes(path)


def test_kiosk_child_switch_restores_saved_language_and_reprompts_after_cancel(
        launch_ui, automation, wait_for_accessible_state, tmp_path):
    ui, wait = automation, wait_for_accessible_state
    path = launch_language(launch_ui, tmp_path, 'kiosk', scenario='language-switch')
    wait(lambda: ui.showing('language-dialog'), 'first child setup opens')
    assert ui.text('language-account') == 'For Alex Morgan'
    ui.reader.choose_language('kiosk', 'de')
    ui.reader.cancel_language('kiosk')
    assert not committed(path)
    ui.activate('kiosk-child-selector')
    wait(lambda: ui.find('kiosk-child-choice-1002') is not None, 'second child choice')
    ui.activate('kiosk-child-choice-1002')
    wait(lambda: ui.showing('language-dialog'), 'second child has no preference')
    assert ui.text('language-account') == 'For Sam Rivera'
    ui.reader.choose_language('kiosk', 'de')
    ui.reader.save_language('kiosk')
    assert_surface_language(ui, wait, 'kiosk', 'de')
    ui.activate('kiosk-child-selector')
    wait(lambda: ui.find('kiosk-child-choice-1001') is not None, 'first child choice')
    ui.activate('kiosk-child-choice-1001')
    wait(lambda: ui.showing('language-dialog'), 'cancelled child setup reopens')
    assert ui.text('language-account') == 'For Alex Morgan'
    assert ui.state('language-choice-en', ui.api.StateType.CHECKED)
    ui.reader.cancel_language('kiosk')
    assert_surface_language(ui, wait, 'kiosk', 'en')
    ui.activate('kiosk-child-selector')
    wait(lambda: ui.find('kiosk-child-choice-1002') is not None, 'saved child choice')
    ui.activate('kiosk-child-choice-1002')
    wait(lambda: ui.showing('kiosk-language-ready'), 'saved child language loaded')
    assert ui.absent('language-dialog', within='kiosk-request-window')
    assert_surface_language(ui, wait, 'kiosk', 'de')
    assert committed(path) == ['de']
    assert_no_policy_or_request_writes(path)


@pytest.mark.parametrize('surface', SURFACES)
@pytest.mark.parametrize('language', LANGUAGES)
def test_saved_language_bypasses_setup_and_cancel_discards_candidate(
        launch_ui, automation, wait_for_accessible_state, tmp_path, surface, language):
    ui, wait = automation, wait_for_accessible_state
    path = launch_language(launch_ui, tmp_path, surface, language=language)
    scope = frontend(surface)
    window = 'parent-window' if surface == 'parent' else 'kiosk-request-window'
    wait(lambda: ui.showing(scope + '-language-ready'), 'saved language startup is ready')
    assert ui.absent('language-dialog', within=window)
    assert_surface_language(ui, wait, surface, language)
    ui.reader.open_language_preferences(scope)
    assert ui.state('language-choice-' + language.lower(), ui.api.StateType.CHECKED)
    candidate = 'de' if language != 'de' else 'zh-Hans'
    ui.reader.choose_language(scope, candidate)
    wait(lambda: ui.text('language-title') == LANGUAGES[candidate][2],
         'candidate immediately translates the chooser')
    assert ui.text('language-continue') == LANGUAGES[candidate][3]
    assert ui.target('language-continue').get_description() == LANGUAGES[candidate][4]
    if surface != 'parent':
        account = {'de': 'Für Alex Morgan', 'zh-Hans': '为 Alex Morgan'}[candidate]
        assert ui.text('language-account') == account
    assert not committed(path)
    ui.reader.cancel_language(scope)
    assert_surface_language(ui, wait, surface, language)
    ui.reader.open_language_preferences(scope)
    assert ui.state('language-choice-' + language.lower(), ui.api.StateType.CHECKED)
    assert not committed(path)
    ui.reader.cancel_language(scope)
    assert_no_policy_or_request_writes(path)


@pytest.mark.parametrize('surface', SURFACES)
@pytest.mark.parametrize('first_run', (True, False), ids=('first-run', 'preferences'))
def test_failed_save_retains_candidate_and_active_language_then_retries(
        launch_ui, automation, wait_for_accessible_state, tmp_path, surface, first_run):
    ui, wait = automation, wait_for_accessible_state
    path = launch_language(launch_ui, tmp_path, surface,
                           language='' if first_run else 'en', save_failures=1)
    scope = frontend(surface)
    if first_run:
        wait(lambda: ui.showing('language-dialog'), 'setup opens')
    else:
        wait(lambda: ui.showing(scope + '-language-ready'), 'saved startup ready')
        ui.reader.open_language_preferences(scope)
    ui.reader.choose_language(scope, 'de')
    ui.activate('language-continue')
    wait(lambda: ui.showing('language-error'), 'save failure is visible')
    assert ui.text('language-error') == 'Die Sprache konnte nicht gespeichert werden. Bitte erneut versuchen.'
    assert ui.state('language-choice-de', ui.api.StateType.CHECKED)
    assert ui.state('language-choice-de', ui.api.StateType.SENSITIVE)
    assert ui.state('language-continue', ui.api.StateType.SENSITIVE)
    assert ui.state('language-search', ui.api.StateType.SENSITIVE)
    assert ui.text('language-title') == LANGUAGES['de'][2]
    assert not committed(path)
    assert ui.state('language-cancel', ui.api.StateType.SENSITIVE)
    ui.reader.save_language(scope)
    assert committed(path) == ['de']
    assert_surface_language(ui, wait, surface, 'de')
    assert_no_policy_or_request_writes(path)


@pytest.mark.parametrize('surface', SURFACES)
def test_failed_startup_read_is_reported_and_preferences_retries(
        launch_ui, automation, wait_for_accessible_state, tmp_path, surface):
    ui, wait = automation, wait_for_accessible_state
    path = launch_language(launch_ui, tmp_path, surface, language='de', load_failures=1)
    explanation = 'Your language preference could not be loaded. Open Preferences to try again.'
    if surface == 'parent':
        wait(lambda: ui.showing('feedback-dialog'), 'read failure opens the error report')
        editor = feedback_editor(ui, wait)
        # Error reports seed only fixed public text and closed categories;
        # caller-provided explanations must not enter the editable draft.
        wait(lambda: 'Error categories: RuntimeError' in ui.content(editor),
             'read failure report is populated')
        assert ui.content(editor).rstrip('\n') == (
            'Something went wrong\n'
            'The operation could not be completed. Please try again later.\n\n'
            'Error categories: RuntimeError')
        ui.activate('feedback-close')
        wait(lambda: ui.absent('feedback-dialog', within='parent-window'), 'error report closes')
    else:
        wait(lambda: ui.showing('kiosk-language-load-error'), 'read failure is distinct from setup')
        assert ui.text('kiosk-result-title') == LANGUAGES['en'][7]
        assert ui.text('kiosk-result-detail') == explanation
    window = 'parent-window' if surface == 'parent' else 'kiosk-request-window'
    assert ui.absent('language-dialog', within=window)
    assert not committed(path)
    ui.reader.open_language_preferences(frontend(surface))
    assert ui.state('language-choice-de', ui.api.StateType.CHECKED)
    ui.reader.save_language(frontend(surface))
    assert_surface_language(ui, wait, surface, 'de')
    assert_no_policy_or_request_writes(path, expected_results=0 if surface == 'parent' else 1)


@pytest.mark.parametrize('surface', ('kiosk', 'overlay'))
@pytest.mark.parametrize('language', LANGUAGES)
def test_request_error_result_uses_current_language(
        launch_ui, automation, wait_for_accessible_state, tmp_path, surface, language):
    ui, wait = automation, wait_for_accessible_state
    path = launch_language(launch_ui, tmp_path, surface, language='en', scenario='service-failure')
    wait(lambda: ui.showing('kiosk-language-ready'), 'request setup ready')
    ui.reader.open_language_preferences('kiosk')
    ui.reader.choose_language('kiosk', language)
    ui.reader.save_language('kiosk')
    wait(lambda: ui.state('kiosk-request-submit', ui.api.StateType.SENSITIVE), 'request ready')
    ui.activate('kiosk-request-submit')
    wait(lambda: ui.showing('kiosk-result-title')
         and ui.text('kiosk-result-title') == LANGUAGES[language][7],
         'late error data is rendered in the current language')
    assert 'org.example.Secret' not in ui.text('kiosk-result-detail')
    assert '/private/path' not in ui.text('kiosk-result-detail')
    assert committed(path) == [language]
