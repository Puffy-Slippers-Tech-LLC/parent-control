"""Localization's chooser contract through real GTK and shared E2E actions."""

import pytest

from tests.support.events import read_events
from tests.support.feedback import feedback_editor
from tests.support.localization_review import public_label_names


pytestmark = pytest.mark.ui
SURFACES = ('parent', 'kiosk', 'overlay')


@pytest.mark.parametrize('text,unit,value,expected', [
    ('  Save <work> & play!  ', 'second', 15, '  Save &lt;work&gt; &amp; play!  '),
    ('   ', 'second', 15, '15 seconds left'),
    ('', 'minute', 1, '1 minute left'),
])
@pytest.mark.parametrize('overlay', [False, True])
def test_reminder_preview_sends_critical_literal_notification(text, unit, value, expected, overlay):
    """Isolate GTK 4 from the observer's GTK 3; no host notification is used."""
    import subprocess
    import sys
    from tests.support.paths import ROOT

    script = '''
import sys
import pytest
text, unit, value, expected, overlay = sys.argv[1:]
overlay = overlay == 'True'
value = int(value)
monkeypatch = pytest.MonkeyPatch()
import gettext
from types import SimpleNamespace
from kiosk.oh_no_parent_control_kiosk import preference_dialog as dialog

class State:
    def set_from_icon_name(self, value):
        self.icon = value

    def set_sensitive(self, value):
        self.sensitive = value

    def set_visible(self, value):
        self.visible = value

calls = []
pending = []

class Connection:
    defer = False

    def call(self, *args):
        calls.append(args)
        if self.defer and args[3] in ('PreviewLocalized', 'Notify'):
            pending.append(args[-1])
        else:
            args[-1](self, None)

    def call_finish(self, result):
        return dialog.GLib.Variant('(u)', (42,))

connection = Connection()
monkeypatch.setattr(dialog.Gio, 'bus_get', lambda bus, cancel, callback: callback(None, None))
monkeypatch.setattr(dialog.Gio, 'bus_get_finish', lambda result: connection)
monkeypatch.setattr(dialog, 'context_for', lambda widget:
                    SimpleNamespace(translations=gettext.NullTranslations(), language='en'))
monkeypatch.setattr(dialog, 'set_text', lambda widget, prop, value: setattr(widget, prop, value))
monkeypatch.setattr(dialog, 'describe_control', lambda *args, **kwargs: None)
editor = SimpleNamespace(
    _duration=lambda: value, _unit_token=lambda: unit,
    _text=SimpleNamespace(get_text=lambda: text),
    _preview_pending=False, _preview_id=0, _notified_closed=False,
    _preview_overlay=overlay, _preview_connection=None,
    _preview_button=State(), _preview_label=State(), _preview_icon=State(),
    _preview_hint_source=None, _error=State())
editor._restore_preview_label = lambda: dialog.ReminderDialog._restore_preview_label(editor)
editor._close_preview = lambda: dialog.ReminderDialog._close_preview(editor)
dialog.ReminderDialog._preview(editor)
payload = calls[0][4].unpack()
if overlay:
    assert calls[0][:4] == (dialog.SHELL_PREVIEW_NAME, dialog.SHELL_PREVIEW_PATH,
                           dialog.SHELL_PREVIEW_NAME, 'PreviewLocalized')
    assert payload == (text if text.strip() else expected, 0, value * (60 if unit == 'minute' else 1), 'en')
else:
    assert calls[0][:4] == ('org.freedesktop.Notifications', '/org/freedesktop/Notifications',
                           'org.freedesktop.Notifications', 'Notify')
    assert payload[3:5] == ('', expected)
    assert payload[6]['urgency'] == 2
    assert payload[6]['x-onpc-remaining-seconds'] == value * (60 if unit == 'minute' else 1)
    assert payload[6]['x-onpc-language'] == 'en'
    assert payload[2].endswith('app_logo.png')
assert editor._preview_id == 42
assert editor._preview_button.sensitive
dialog.ReminderDialog._preview(editor)
assert calls[1][4].unpack()[1] == 42
editor._close_preview()
assert calls[2][3] == ('Close' if overlay else 'CloseNotification')
assert calls[2][4].unpack() == (42,)
assert editor._preview_id == 0

# An editor may close while delivery is in flight. Close the returned ID,
# without enabling or touching controls on the disposed window.
connection.defer = True
dialog.ReminderDialog._preview(editor)
editor._notified_closed = True
pending.pop()(connection, None)
assert calls[-1][3] == ('Close' if overlay else 'CloseNotification')
assert calls[-1][4].unpack() == (42,)
assert editor._preview_id == 0
assert not editor._preview_pending
assert not editor._preview_button.sensitive

# If disposal wins before connecting, no notification should be sent.
editor._notified_closed = False
monkeypatch.setattr(dialog.Gio, 'bus_get', lambda bus, cancel, callback: pending.append(callback))
count = len(calls)
dialog.ReminderDialog._preview(editor)
editor._notified_closed = True
pending.pop()(None, None)
assert len(calls) == count
assert not editor._preview_pending
'''
    result = subprocess.run([sys.executable, '-c', script, text, unit, str(value), expected, str(overlay)],
                            cwd=ROOT, capture_output=True, text=True, timeout=30)
    assert result.returncode == 0, result.stdout + result.stderr


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
    'he': ('עברית', 'בחירת השפה שלך', 'שמירה', 'שמירת העדפת השפה שלך.',
           'מגבלת זמן מסך', 'בקשה'),
    'pt': ('Português', 'Escolha a sua língua', 'Guardar', 'Guardar a sua preferência de língua.',
           'Limite de tempo de ecrã', 'SOLICITAR'),
    'zh-Hant': ('中文（繁體）', '選擇語言', '儲存', '儲存語言偏好設定。', '限制螢幕時間', '提交請求'),
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
                    child_desktop='', language_delay=0, unicode_input=False,
                    notification_load_failures=0, notification_save_failures=0):
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
        'ONPC_NOTIFICATION_LOAD_FAILURES': str(notification_load_failures),
        'ONPC_NOTIFICATION_SAVE_FAILURES': str(notification_save_failures),
    }
    if unicode_input:
        # Bare Mutter has no desktop input-method daemon. Reuse the Unicode
        # fixture setting from test_parent_feedback's normal editor checks.
        environment['GTK_IM_MODULE'] = 'gtk-im-context-simple'
    launch_ui('parent_component_preview' if surface == 'parent' else 'request_component_preview',
              complete_language_setup=False, environment_overrides=environment)
    return path


def test_reminder_preview_real_session_provider_retains_unsaved_edit(
        launch_ui, automation, wait_for_accessible_state, tmp_path):
    from common.oh_no_parent_control_ui.application_ui_client import UIClientError

    process, _log = launch_ui('kiosk_notification_preview')
    clients = []

    def notification_ready():
        try:
            client = automation.reader.application_ui.client(
                'com.puffyslippers.OhNoParentControl.KioskNotifications')
            client.surface_id = 'kiosk-system-notification'
        except UIClientError:
            return False
        assert client.pid == process.pid
        clients.append(client)
        return True

    wait_for_accessible_state(notification_ready, 'private notification provider registered')
    client = clients[-1]
    def body_is(expected):
        # Notify is asynchronous: wait for its public surface before reading
        # the body. Mutations remain outside this read-only predicate.
        return (any(s['id'] == 'kiosk-system-notification' and s['visible']
                    for s in client.listSurfaces())
                and client.getText('kiosk-system-notification-message') == expected)
    ui, wait = automation, wait_for_accessible_state
    path = launch_language(launch_ui, tmp_path, 'kiosk', language='en')
    wait(lambda: ui.showing('kiosk-language-ready'), 'request ready')
    ui.reader.open_language_preferences('kiosk')
    ui.setValue('preferences-tabs', 'reminders')
    wait(lambda: ui.showing('reminder-fifteen-seconds-edit'), 'reminders loaded')
    ui.setValue('reminder-show-in-fullscreen', False)
    ui.activate('reminder-fifteen-seconds-edit')
    ui.setText('reminder-text', '  Save <games> & work!  ')
    ui.activate('reminder-editor-preview')
    wait(lambda: body_is('  Save <games> & work!  '),
         'literal real notification body')
    assert client.getValue('kiosk-system-notification-message') == 'critical'
    import time
    started = time.monotonic()
    wait(lambda: time.monotonic() - started >= 5.2 and body_is('  Save <games> & work!  '),
         'subminute preview remains visible beyond five seconds')
    client.activate('kiosk-system-notification-preferences')
    wait(lambda: not client.listSurfaces(), 'Preferences dismisses the banner')
    assert ui.getText('reminder-text') == '  Save <games> & work!  '
    ui.activate('reminder-editor-preview')
    wait(lambda: body_is('  Save <games> & work!  '), 'preview reopens with retained draft')
    client.activate('kiosk-system-notification-close')
    wait(lambda: not client.listSurfaces(), 'Dismiss closes the banner')
    ui.setText('reminder-value', '60')
    ui.setValue('reminder-unit', 'second')
    ui.setText('reminder-text', '   ')
    ui.activate('reminder-editor-preview')
    wait(lambda: body_is('60 seconds left'), 'minute boundary preview')
    assert client.getText('kiosk-system-notification-countdown') in ('5s', '4s')
    wait(lambda: not client.listSurfaces(), 'minute preview auto closes after five seconds')
    assert ui.getText('reminder-value') == '60'
    ui.setText('reminder-value', '15')
    ui.activate('reminder-editor-preview')
    wait(lambda: body_is('15 seconds left'),
         'default real notification body')
    assert client.getValue('kiosk-system-notification-message') == 'critical'
    ui.activate('reminder-editor-cancel')
    wait(lambda: not client.listSurfaces(), 'editor cancellation closes its preview')
    assert ui.getText('reminder-fifteen-seconds-text') == '15 seconds left'
    ui.activate('language-cancel')
    assert not [e for e in read_events(path) if e['event'] == 'notifications-committed']


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


@pytest.mark.parametrize('surface', ('kiosk', 'overlay'))
def test_child_preferences_reminders_sort_edit_save_cancel_and_empty_list(
        launch_ui, automation, wait_for_accessible_state, tmp_path, surface):
    ui, wait = automation, wait_for_accessible_state
    path = launch_language(launch_ui, tmp_path, surface, language='en')
    wait(lambda: ui.showing('kiosk-language-ready'), 'saved language ready')
    ui.reader.open_language_preferences('kiosk')
    assert ui.find('preferences-tabs').getChoices() == ['language', 'reminders']
    assert ui.getValue('preferences-tabs') == 'language'
    ui.setValue('preferences-tabs', 'reminders')
    assert ui.getValue('preferences-tabs') == 'reminders'
    wait(lambda: ui.find('reminder-list').getChoices() == [
        'fifteen-seconds', 'one-minute', 'five-minutes', 'ten-minutes'], 'backend defaults sorted')
    assert ui.getText('reminder-fifteen-seconds-text') == '15 seconds left'
    assert ui.getText('reminder-fifteen-seconds-trigger') == '15 seconds left'
    assert ui.getValue('reminder-show-in-fullscreen') is True
    ui.setValue('reminder-show-in-fullscreen', False)
    ui.activate('reminder-five-minutes-edit')
    ui.setText('reminder-value', '30')
    ui.setValue('reminder-unit', 'second')
    ui.setText('reminder-text', '  Save <work>!  ')
    ui.activate('reminder-editor-save')
    assert ui.getText('reminder-five-minutes-text') == '  Save <work>!  '
    assert ui.getText('reminder-five-minutes-trigger') == '30 seconds left'
    ui.activate('reminder-ten-minutes-delete')
    ui.activate('language-continue')
    wait(lambda: ui.absent('language-dialog', within='kiosk-request-window'), 'preferences saved')
    records = [e for e in read_events(path) if e['event'] == 'notifications-committed']
    assert len(records) == 1 and records[0]['uid'] == 1001
    assert records[0]['settings']['show_in_fullscreen'] is False
    assert records[0]['settings']['reminders'] == [
        {'id': 'fifteen-seconds', 'value': 15, 'unit': 'second', 'text': ''},
        {'id': 'five-minutes', 'value': 30, 'unit': 'second', 'text': '  Save <work>!  '},
        {'id': 'one-minute', 'value': 1, 'unit': 'minute', 'text': ''}]
    ui.reader.open_language_preferences('kiosk')
    ui.setValue('preferences-tabs', 'reminders')
    wait(lambda: ui.getText('reminder-five-minutes-text') == '  Save <work>!  ', 'saved reminder reloads')
    assert ui.getValue('reminder-show-in-fullscreen') is False
    ui.setValue('reminder-show-in-fullscreen', True)
    ui.activate('reminder-five-minutes-delete')
    ui.activate('language-cancel')
    ui.reader.open_language_preferences('kiosk')
    ui.setValue('preferences-tabs', 'reminders')
    wait(lambda: ui.showing('reminder-five-minutes-text'), 'Cancel retained saved reminder')
    assert ui.getValue('reminder-show-in-fullscreen') is False
    for identity in ('fifteen-seconds', 'five-minutes', 'one-minute'):
        ui.activate(f'reminder-{identity}-delete')
    assert not ui.state('reminder-show-in-fullscreen', ui.api.StateType.SENSITIVE)
    ui.activate('language-continue')
    wait(lambda: ui.absent('language-dialog', within='kiosk-request-window'), 'empty list saved')
    ui.reader.open_language_preferences('kiosk')
    ui.setValue('preferences-tabs', 'reminders')
    wait(lambda: ui.showing('reminder-add') and ui.state('reminder-add', ui.api.StateType.SENSITIVE), 'empty list loaded')
    assert ui.find('reminder-list').getChoices() == []
    assert not ui.state('reminder-show-in-fullscreen', ui.api.StateType.SENSITIVE)
    assert_no_policy_or_request_writes(path)


def test_reminder_creation_validation_and_candidate_translation(
        launch_ui, automation, wait_for_accessible_state, tmp_path):
    ui, wait = automation, wait_for_accessible_state
    path = launch_language(launch_ui, tmp_path, 'overlay', language='en')
    wait(lambda: ui.showing('kiosk-language-ready'), 'startup ready')
    ui.reader.open_language_preferences('kiosk')
    ui.setValue('preferences-tabs', 'reminders')
    wait(lambda: ui.state('reminder-add', ui.api.StateType.SENSITIVE), 'backend reminders loaded')
    ui.activate('reminder-add')
    assert ui.getText('reminder-value') == '20'
    assert ui.getValue('reminder-unit') == 'minute'
    assert ui.absent('reminder-duplicate-warning', within='reminder-editor-dialog')
    assert ui.state('reminder-editor-save', ui.api.StateType.SENSITIVE)
    ui.setText('reminder-value', '1')
    assert ui.showing('reminder-duplicate-warning')
    assert not ui.state('reminder-editor-save', ui.api.StateType.SENSITIVE)
    ui.setText('reminder-value', '60')
    ui.setValue('reminder-unit', 'second')
    assert ui.showing('reminder-duplicate-warning')
    assert not ui.state('reminder-editor-save', ui.api.StateType.SENSITIVE)
    ui.setValue('reminder-unit', 'minute')
    ui.setText('reminder-value', '1.5')
    ui.activate('reminder-editor-save')
    assert ui.showing('reminder-editor-error')
    ui.setText('reminder-value', '71582789')
    ui.activate('reminder-editor-save')
    assert ui.showing('reminder-editor-error')
    ui.setText('reminder-value', '2')
    assert ui.absent('reminder-duplicate-warning', within='reminder-editor-dialog')
    assert ui.state('reminder-editor-save', ui.api.StateType.SENSITIVE)
    ui.setText('reminder-text', 'x' * 51)
    assert ui.getText('reminder-text') == 'x' * 50
    assert ui.getText('reminder-text-count') == '50/50'
    ui.setText('reminder-text', '界' * 51)
    assert ui.getText('reminder-text') == '界' * 50
    ui.setText('reminder-text', '   ')
    ui.activate('reminder-editor-save')
    reminders = ui.find('reminder-list').getValue()
    added = next(r for r in reminders if r['id'].startswith('reminder-'))
    assert added == {**added, 'value': 2, 'unit': 'minute', 'text': ''}
    ui.setValue('preferences-tabs', 'language')
    ui.activate('language-choice-de')
    ui.setValue('preferences-tabs', 'reminders')
    assert ui.getText(f"reminder-{added['id']}-text") == 'Noch 2 Minuten'
    assert ui.getText(f"reminder-{added['id']}-trigger") == 'Noch 2 Minuten'
    assert ui.text('reminder-add') == 'Hinzufügen'
    ui.activate('language-cancel')
    assert not [e for e in read_events(path) if e['event'] == 'notifications-committed']
    assert not committed(path)


def test_reminder_load_and_save_failures_keep_draft_and_allow_retry(
        launch_ui, automation, wait_for_accessible_state, tmp_path):
    ui, wait = automation, wait_for_accessible_state
    path = launch_language(launch_ui, tmp_path, 'kiosk', language='en',
                          notification_load_failures=1, notification_save_failures=1)
    wait(lambda: ui.showing('kiosk-language-ready'), 'startup ready')
    ui.reader.open_language_preferences('kiosk')
    ui.setValue('preferences-tabs', 'reminders')
    wait(lambda: ui.showing('reminder-retry'), 'read failure offers retry')
    assert not ui.state('reminder-add', ui.api.StateType.SENSITIVE)
    assert not ui.state('reminder-show-in-fullscreen', ui.api.StateType.SENSITIVE)
    ui.activate('reminder-retry')
    wait(lambda: ui.showing('reminder-one-minute-delete'), 'retry loaded backend reminders')
    ui.setValue('reminder-show-in-fullscreen', False)
    ui.activate('reminder-one-minute-delete')
    ui.activate('language-continue')
    wait(lambda: ui.showing('language-error'), 'failed save retains preferences')
    assert 'one-minute' not in ui.find('reminder-list').getChoices()
    assert ui.getValue('reminder-show-in-fullscreen') is False
    assert not [e for e in read_events(path) if e['event'] == 'notifications-committed']
    ui.activate('language-continue')
    wait(lambda: ui.absent('language-dialog', within='kiosk-request-window'), 'retry saved preferences')
    assert len([e for e in read_events(path) if e['event'] == 'notifications-committed']) == 1
    assert next(e for e in read_events(path) if e['event'] == 'notifications-committed')[
        'settings']['show_in_fullscreen'] is False


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


def test_parent_hebrew_public_text_and_saved_selection(
        launch_ui, automation, wait_for_accessible_state, tmp_path):
    ui, wait = automation, wait_for_accessible_state
    path = launch_language(launch_ui, tmp_path, 'parent', language='en')
    wait(lambda: ui.showing('parent-language-ready'), 'saved startup ready')
    reader = ui.reader
    for language, heading in (('en', 'Choose your language'),
                              ('he', 'בחירת השפה שלך'), ('en', 'Choose your language')):
        reader.open_language_preferences('parent')
        reader.choose_language('parent', language)
        presented = reader.read_parent_language()
        assert {key: presented[key] for key in ('heading', 'choices', 'checked')} == {'heading': heading,
            'choices': {'en': 'English', 'de': 'Deutsch', 'zh-Hans': '中文（简体）', 'he': 'עברית'},
            'checked': language}
        reader.save_language('parent')
        reader.open_language_preferences('parent')
        assert reader.read_parent_language()['checked'] == language
        reader.cancel_language('parent')
    assert_no_policy_or_request_writes(path)


def test_parent_dialog_inherited_text_and_retained_hebrew_draft(
        launch_ui, automation, wait_for_accessible_state, tmp_path, capsys):
    import json
    from tests.support.paths import ROOT
    from tests.support.gui_blocks import run_block

    def checkpoint(stage):
        # Retain finite case stages even on success or interruption. Do not
        # record UI contents, exception text or private preview state.
        with capsys.disabled():
            print('ONPC_PARENT_DIALOG_DIAGNOSTIC ' + json.dumps({'stage': stage}),
                  flush=True)

    ui, wait = automation, wait_for_accessible_state
    checkpoint('startup-begin')
    path = launch_language(launch_ui, tmp_path, 'parent', language='en', unicode_input=True)
    wait(lambda: ui.showing('parent-language-ready'), 'saved startup ready')
    checkpoint('startup-ready')
    reader = ui.reader
    version = json.loads((ROOT / 'data/app.json').read_text())['version']
    reader.open_feedback()
    try:
        run_block(reader, 'replace', 'body-rtl')
    except Exception as error:
        # Bounded public diagnostic projects only the declared fixture alphabet;
        # unexpected text is represented by a closed marker, never returned.
        actual = ui.getText('feedback-editor-input')
        count = len(actual)
        if count <= 128:
            alphabet = 'שלום Alex 75\n'
            error.add_note('Synthetic input diagnostic: ' + json.dumps({
                'count': count, 'fixture_positions': [alphabet.index(character)
                    if character in alphabet else -1 for character in actual],
                'has_hebrew': 'שלום' in actual, 'has_ascii': ' Alex 75' in actual,
            }))
        raise
    run_block(reader, 'replace', 'reply-rtl')
    wait(lambda: reader.feedback_snapshot('synthetic-rtl'), 'seeded exact synthetic draft')
    ui.activate('feedback-close')
    wait(lambda: ui.absent('feedback-dialog', within='parent-window'), 'draft closes')
    checkpoint('synthetic-draft-checked-and-closed')
    for language in ('en', 'he', 'en'):
        checkpoint('language-' + language + '-begin')
        reader.open_language_preferences('parent')
        reader.choose_language('parent', language)
        reader.save_language('parent')
        checkpoint('language-' + language + '-saved')
        for surface in ('about', 'feedback'):
            operation = f'parent-dialog-{surface}-{language}-'
            checkpoint(operation + 'begin')
            opened = reader.parent_dialog_operation(operation + 'open', version)
            assert opened['dialog_presentation']['language'] == language
            reader.parent_dialog_operation(operation + 'read', version)
            reader.parent_dialog_operation(operation + 'close', version)
            ui.close(surface + '-dialog')
            reader.parent_dialog_operation(operation + 'closed', version)
            assert reader.parent_dialog_operation(operation + 'refused', version) == {'refused': True}
            checkpoint(operation + 'checked')
    assert committed(path) == ['en', 'he', 'en']
    assert_no_policy_or_request_writes(path)
    checkpoint('all-assertions-complete')


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


@pytest.mark.parametrize('selected_language', ['zh-Hans', 'he'])
def test_enabled_parent_language_reader_keeps_real_gtk_names_and_numeric_balances(
        launch_ui, automation, wait_for_accessible_state, tmp_path, selected_language):
    from tests.e2e.accessible_ui import CHILD, EXISTING_CHILD
    ui, wait = automation, wait_for_accessible_state
    path = launch_language(launch_ui, tmp_path, 'parent', language='en')
    wait(lambda: ui.showing('parent-language-ready'), 'saved startup ready')
    reader = ui.reader
    reader.fixture_uids = {CHILD: 1001, EXISTING_CHILD: 1002}
    reader.allowance_preset(CHILD, 60, action='select')
    original = reader.parent_language_state(child=CHILD, enabled=True, language='en')
    reader.open_language_preferences('parent')
    reader.choose_language('parent', selected_language)
    reader.save_language('parent')
    for account, uid, name in ((EXISTING_CHILD, 1002, 'jordan'), (CHILD, 1001, 'riley')):
        reader.open_child_picker(account)
        reader.child_highlighted(account)
        assert reader.run(f'parent-language-{name}-selected', '')['child_selection'] == {
            'child': 'fixture-child' if account == CHILD else 'existing-fixture-child'}
    translated = reader.parent_language_state(child=CHILD, enabled=True, language=selected_language)
    expected = {'zh-Hans': ('限制屏幕时间', {'限制屏幕时间', '每日可用时间', '今日剩余时间'}),
                'he': ('מגבלת זמן מסך', {'מגבלת זמן מסך', 'מכסת זמן יומית', 'הזמן שנותר היום'})}[selected_language]
    assert translated['management'] == expected[0]
    assert expected[1] <= set(translated['management_labels'])
    if selected_language == 'he':
        assert [translated['balances'][key]['text'] for key in ('daily', 'one_time', 'total')] == [
            '47דק׳', '15דק׳', '47דק׳']
    for key in ('child', 'account_name', 'limit_enabled', 'allowance_minutes', 'rows', 'app_names'):
        assert translated[key] == original[key]
    assert translated['account_name'] == CHILD and translated['allowance_minutes'] == 60
    assert translated['app_names']
    for value in (original, translated):
        assert [value['balances'][key]['seconds'] for key in ('daily', 'one_time', 'total')] == [2820, 900, 2820]
        assert value['chooser_absent'] is True
    reader.open_language_preferences('parent')
    reader.choose_language('parent', 'en')
    reader.save_language('parent')
    restored = reader.parent_language_state(child=CHILD, enabled=True, language='en')
    for key in ('child', 'account_name', 'limit_enabled', 'allowance_minutes', 'rows', 'app_names'):
        assert restored[key] == original[key]
    writes = [event for event in read_events(path) if event['event'] == 'set_parent_control']
    assert len(writes) == 1 and writes[0]['daily_limit_minutes'] == 60


@pytest.mark.parametrize('other_window', [False, True])
def test_parent_child_picker_after_language_policy_reads(
        launch_ui, automation, wait_for_accessible_state, tmp_path, other_window):
    from tests.e2e.accessible_ui import AccessibleUI, CHILD, EXISTING_CHILD

    ui, wait = automation, wait_for_accessible_state
    path = launch_language(launch_ui, tmp_path, 'parent', language='en')
    wait(lambda: ui.showing('parent-screen-limit-toggle')
         and ui.state('parent-screen-limit-toggle', ui.api.StateType.SENSITIVE),
         'Parent controls ready')
    def observer():
        return AccessibleUI(ui.api, timeout=20, query_errors=ui.query_errors,
            owner_pids=ui.owner_pids, application_ids=ui.application_ids,
            application_owners=ui.application_owners,
            application_owner_history=ui.application_owner_history,
            fixture_uids={CHILD: 1001, EXISTING_CHILD: 1002})
    reader = observer()
    original = reader.kiosk_language_policy(child=CHILD)
    assert reader.open_child_picker(EXISTING_CHILD)
    reader.child_highlighted(EXISTING_CHILD)
    reader.selected_child(EXISTING_CHILD)
    ui.activate('parent-screen-limit-toggle')
    reader.parent_save_snapshot(EXISTING_CHILD, True)
    if other_window:
        launch_ui('request_component_preview', environment_overrides={
            'ONPC_REQUEST_COMPONENT_OVERLAY': '1', 'ONPC_LANGUAGE_INITIAL': 'en'})
        wait(lambda: ui.showing('kiosk-request-window'), 'Other owned preview is available')
        ui.close('kiosk-request-window')
        wait(lambda: ui.showing('parent-window'), 'Parent remains available')
    reader.kiosk_language_policy(child=EXISTING_CHILD)
    ui.setValue('parent-child-selector', '1001')
    reader.selected_child(CHILD)
    assert reader.kiosk_language_policy(child=CHILD) == original
    assert [event['event'] for event in read_events(path)
            if event['event'] in ('set_preferences', 'set_parent_control',
                                  'revoke_one_time_grant')] == ['set_parent_control']


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
        launch_ui, automation, wait_for_accessible_state, tmp_path, monkeypatch):
    from accessible_ui import CHILD, EXISTING_CHILD, PARENT, OTHER_PARENT
    from kiosk_language import FORM, TEXT_IDS
    ui, wait = automation, wait_for_accessible_state
    path = launch_language(launch_ui, tmp_path, 'kiosk', scenario='installed-language')
    ui.reader.fixture_uids = {EXISTING_CHILD: 1001, CHILD: 1002, PARENT: 1000, OTHER_PARENT: 1010}
    # This preview declares synthetic approvers, not host OS accounts. Keep
    # the shared helper's exact eligibility check against that finite fixture.
    monkeypatch.setattr(ui.reader, 'interactive_approver_uids', lambda: {'1000', '1010'})
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


def test_language_history_nondefault_requests_restore_through_real_gtk(
        launch_ui, automation, wait_for_accessible_state, tmp_path, monkeypatch):
    from accessible_ui import CHILD, EXISTING_CHILD, PARENT, OTHER_PARENT
    from language_persistence import CHECKS
    from tests.support.gui_blocks import run_block

    ui, wait = automation, wait_for_accessible_state
    path = launch_language(launch_ui, tmp_path, 'kiosk', scenario='installed-language')
    reader = ui.reader
    reader.fixture_uids = {EXISTING_CHILD: 1001, CHILD: 1002, PARENT: 1000, OTHER_PARENT: 1010}
    # The preview's approvers are synthetic accounts. Keep the shared helper's
    # exact eligibility check against this fixture rather than the host OS.
    monkeypatch.setattr(reader, 'interactive_approver_uids', lambda: {'1000', '1010'})
    wait(lambda: ui.showing('language-dialog'), 'untouched Jordan setup')
    reader.kiosk_language_operation('kiosk-language-save')
    for child, name, language, binding, owner, stage in (
            (EXISTING_CHILD, 'jordan', 'de', 'jordan-kiosk-fraction', 'kiosk', 'jordan-german'),
            (CHILD, 'riley', 'he', 'kiosk-fraction', 'kiosk-riley', 'riley-hebrew')):
        if child == CHILD:
            reader.run('kiosk-language-riley-initial', '')
        reader.language_history_request('language-history-' + name + '-custom-open')
        run_block(reader, 'replace', binding)
        reader.language_history_request('language-history-' + name + '-soft')
        reader.kiosk_language_operation(owner + '-language-open')
        reader.kiosk_language_operation(owner + '-language-choose-' + language)
        reader.kiosk_language_operation(owner + '-language-save')
        value = reader.language_history_request('language-history-' + name + '-' + language + '-jamie')
        assert value['language_form'] == CHECKS[stage].keywords['expected']
    for name, language, stage in (('jordan', 'de', 'jordan-casey'), ('riley', 'he', 'riley-casey')):
        reader.language_history_request('language-history-' + name + '-restored')
        reader.language_history_request('language-history-' + name + '-casey-select')
        value = reader.language_history_request('language-history-' + name + '-' + language + '-casey')
        assert value['language_form'] == CHECKS[stage].keywords['expected']
        reader.language_history_request('language-history-' + name + '-jamie-select')
    # The maintained host fixture starts Riley with saved English; unlike the
    # clean installed journey, selecting Riley requires no first-run Save.
    assert committed(path) == ['en', 'de', 'he']
    records = read_events(path)
    assert not [event for event in records if event.get('method') in ('RequestAccess', 'RequestOwnAccess')]
    updates = [event['values'] for event in records if event.get('method') == 'UpdateRequestPreferences']
    for uid in (1001, 1002):
        assert [value for value in updates if value[0] == uid][-1][1:5] == ['custom', 1.25, True, 1000]


def assert_surface_language(ui, wait, surface, language):
    identity = 'parent-screen-limit-toggle' if surface == 'parent' else 'kiosk-request-submit'
    expected = LANGUAGES[language][5 if surface == 'parent' else 6]
    # The request button's displayed caption differs from its accessible name.
    # Parent's switch is checked by its accessible label, not button text.
    read_text = ui.text if surface == 'parent' else ui.getText
    wait(lambda: read_text(identity) == expected, 'surface uses the committed language')


@pytest.mark.parametrize('surface', SURFACES)
@pytest.mark.parametrize('dpi_scale', (1.25,))
def test_language_search_filters_choices_and_preserves_cancel(
        launch_ui, automation, wait_for_accessible_state, tmp_path, surface,
        request_display_scale, dpi_scale):
    from tests.support.automation_ids import audit_product_controls

    ui, wait = automation, wait_for_accessible_state
    path = launch_language(launch_ui, tmp_path, surface)
    wait(lambda: ui.showing('language-search'), 'search is publicly accessible')
    inventory = audit_product_controls(ui, 'language-dialog')
    assert inventory['language-list'].get_name() == 'Language'
    assert inventory['language-list'].get_description() == 'Choose your language'
    search = inventory['language-search']
    assert search.get_name() == 'Search languages'
    assert search.get_description() == 'Search languages'
    # Application UI exposes Gtk.SearchEntry's native role, not AT-SPI's entry role.
    assert search.element.snapshot()['role'] == 'search-box'
    assert {'getText', 'setText'} <= set(search.element.snapshot()['operations'])
    ui.setText('language-search', 'PORT*BR')
    wait(lambda: ui.content('language-search') == 'PORT*BR'
         and ui.showing('language-choice-pt-br')
         and ui.absent('language-choice-en', within='language-dialog'),
         'search changes filter the offered language choices')
    assert not committed(path)
    ui.activate('language-choice-pt-br')
    wait(lambda: ui.text('language-search') == 'Pesquisar idiomas',
         'selected language changes the chooser language')
    ui.setText('language-search', '')
    wait(lambda: ui.content('language-search') == ''
         and ui.find('language-choice-fur') is not None,
         'clearing restores the complete accessible list')
    assert ui.state('language-choice-pt-br', ui.api.StateType.CHECKED)
    ui.setText('language-search', 'no such language')
    wait(lambda: ui.absent('language-choice-pt-br', within='language-dialog'),
         'empty search result removes the selected row from accessibility')
    ui.reader.cancel_language(frontend(surface))
    assert not committed(path)
    assert_no_policy_or_request_writes(path)


@pytest.mark.parametrize('surface,language', (
    ('parent', 'en'), ('kiosk', 'de'), ('overlay', 'zh-Hans'),
))
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
    # A dialog's API text is its title; read the Save control's displayed label.
    assert public_label_names(ui, 'language-continue') == [LANGUAGES[language][3]]
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
def test_parent_development_preview_language_application_ui_input(
        launch_ui, automation, wait_for_accessible_state, snap_environment):
    ui, wait = automation, wait_for_accessible_state
    environment = {'LANGUAGE': 'en_US.UTF-8', 'LC_ALL': 'C.UTF-8'}
    if snap_environment:
        environment.update({'GDK_BACKEND': 'x11', 'GDK_BACKEND_VSCODE_SNAP_ORIG': '',
                            'GSETTINGS_SCHEMA_DIR': '/nonexistent/vscode-snap-schemas',
                            'GSETTINGS_SCHEMA_DIR_VSCODE_SNAP_ORIG': ''})
    launch_ui('parent_preview', complete_language_setup=False,
              environment_overrides=environment)
    wait(lambda: ui.showing('language-search'), 'development preview chooser opens')
    ui.setText('language-search', 'PORT*BR')
    wait(lambda: ui.content('language-search') == 'PORT*BR'
         and ui.showing('language-choice-pt-br')
         and ui.absent('language-choice-en', within='language-dialog'),
         'Application UI text filters the preview language list')
    ui.setText('language-search', '')
    wait(lambda: ui.content('language-search') == '', 'clearing search restores the full list')
    ui.setValue('language-list', 'fur')
    wait(lambda: ui.state('language-choice-fur', ui.api.StateType.CHECKED),
         'the language choice is selected')
    ui.activate('language-cancel')
    wait(lambda: ui.absent('language-dialog', within='parent-window'),
         'Cancel closes the preview chooser')


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


@pytest.mark.parametrize('surface,language', (
    ('parent', 'he'), ('kiosk', 'ta'), ('overlay', 'zh-Hant'),
    ('parent', 'pt'), ('kiosk', 'fur'),
))
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
    # Read request captions separately from their accessible action names,
    # as in assert_surface_language; Parent's switch uses its accessible label.
    read_text = ui.text if surface == 'parent' else ui.getText
    wait(lambda: read_text(identity) == (screen if surface == 'parent' else request),
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
    ui.setValue('kiosk-child-selector', '1002')
    wait(lambda: ui.showing('language-dialog'), 'second child has no preference')
    assert ui.text('language-account') == 'For Sam Rivera'
    ui.reader.choose_language('kiosk', 'de')
    ui.reader.save_language('kiosk')
    assert_surface_language(ui, wait, 'kiosk', 'de')
    ui.setValue('kiosk-child-selector', '1001')
    wait(lambda: ui.showing('language-dialog'), 'cancelled child setup reopens')
    assert ui.text('language-account') == 'For Alex Morgan'
    assert ui.state('language-choice-en', ui.api.StateType.CHECKED)
    ui.reader.cancel_language('kiosk')
    assert_surface_language(ui, wait, 'kiosk', 'en')
    ui.setValue('kiosk-child-selector', '1002')
    wait(lambda: ui.showing('kiosk-language-ready'), 'saved child language loaded')
    assert ui.absent('language-dialog', within='kiosk-request-window')
    assert_surface_language(ui, wait, 'kiosk', 'de')
    assert committed(path) == ['de']
    assert_no_policy_or_request_writes(path)


@pytest.mark.parametrize('surface,language', (
    ('parent', 'de'), ('kiosk', 'zh-Hans'), ('overlay', 'en'),
))
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


@pytest.mark.parametrize('surface,language', (
    ('kiosk', 'de'), ('overlay', 'zh-Hans'),
))
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
