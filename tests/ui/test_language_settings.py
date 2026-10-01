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


def launch_language(launch_ui, tmp_path, surface, *, language='', session='en',
                    save_failures=0, load_failures=0, release=None, scenario='normal'):
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
    }
    launch_ui('parent_component_preview' if surface == 'parent' else 'request_component_preview',
              complete_language_setup=False, environment_overrides=environment)
    return path


def frontend(surface):
    return 'parent' if surface == 'parent' else 'kiosk'


def committed(path):
    return [event['language'] for event in read_events(path)
            if event['event'] == 'language-committed']


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


def assert_surface_language(ui, wait, surface, language):
    identity = 'parent-screen-limit-toggle' if surface == 'parent' else 'kiosk-request-submit'
    expected = LANGUAGES[language][5 if surface == 'parent' else 6]
    wait(lambda: ui.text(identity) == expected, 'surface uses the committed language')


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
    if surface == 'parent':
        assert ui.showing('language-cancel')
    else:
        assert ui.absent('language-cancel', within='language-dialog')
    assert not committed(path)
    if surface != 'parent':
        assert not ui.state('kiosk-request-submit', ui.api.StateType.SENSITIVE)
    try:
        ui.activate('language-continue')
        wait(lambda: any(event['event'] == 'language-save-started'
                         for event in read_events(path)), 'save reaches the fixture')
        assert ui.showing('language-dialog')
        assert not committed(path)
        disabled = ('language-continue', choice)
        if surface == 'parent':
            disabled += ('language-cancel',)
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


def test_parent_first_run_cancel_leaves_language_unset(
        launch_ui, automation, wait_for_accessible_state, tmp_path):
    ui, wait = automation, wait_for_accessible_state
    path = launch_language(launch_ui, tmp_path, 'parent')
    wait(lambda: ui.showing('language-dialog'), 'first-run chooser opens')
    ui.reader.choose_language('parent', 'de')
    ui.reader.cancel_language('parent')
    assert_surface_language(ui, wait, 'parent', 'en')
    assert not committed(path)
    ui.reader.open_language_preferences('parent')
    assert ui.state('language-choice-en', ui.api.StateType.CHECKED)
    ui.reader.cancel_language('parent')
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
    assert ui.text('language-title') == LANGUAGES[language][2]
    assert ui.text('language-continue') == LANGUAGES[language][3]
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
    assert ui.text('language-error') == 'Your language could not be saved. Please try again.'
    assert ui.state('language-choice-de', ui.api.StateType.CHECKED)
    assert ui.state('language-choice-de', ui.api.StateType.SENSITIVE)
    assert ui.state('language-continue', ui.api.StateType.SENSITIVE)
    assert ui.text('language-title') == LANGUAGES['en'][2]
    assert not committed(path)
    if first_run and surface != 'parent':
        assert ui.absent('language-cancel', within='language-dialog')
    else:
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
