import unittest
import inspect
import struct
from pathlib import Path
from unittest import mock
from types import SimpleNamespace

from common.oh_no_parent_control_ui.languages import selected_language, session_language, supported_language
from common.oh_no_parent_control_ui import messages as m

from parent.oh_no_parent_control_parent.main import (
    ACCOUNT_REFRESH_SECONDS, APPLICATION_ICON_NAME, APP_LIST_STATES, CATALOG_ROW_BATCH_SIZE, CUSTOM_DAILY_LIMIT_INDEX, DAILY_LIMIT_PRESETS, MATCH_RULES, MAX_TIME_STATUS_RETRIES, STATES, ParentAccountSelector, ParentWindow, _can_start, _daily_limit_label, _daily_limit_selection, _minutes_label,
    _time_status_subtitle,
    _daily_limit_keyboard_selection,
)
from parent.oh_no_parent_control_parent.preview_data import (
    PREVIEW_USERS, PreviewBrokerClient, PREVIEW_THUNDERBIRD_ICON,
)


class FakeDropDown:
    def __init__(self, owner):
        self.owner = owner
        self.blocked = False

    def set_users(self, _users, selected):
        self.owner.model_updates += 1
        self.owner.selected_index = selected if _users else None

    def get_selected(self):
        return self.owner.selected_index if self.owner.selected_index is not None else 0


class FakeSensitiveWidget:
    def __init__(self, active=False):
        self.active = active
        self.sensitive = None

    def get_active(self):
        return self.active

    def set_sensitive(self, sensitive):
        self.sensitive = sensitive


class FakeVisibleWidget:
    def __init__(self):
        self.visible = False

    def set_visible(self, visible):
        self.visible = visible


class FakeToggleButton:
    def __init__(self, active):
        self.active = active

    def get_active(self):
        return self.active


class ParentWindowHarness:
    _users_loaded = ParentWindow._users_loaded
    _account_changed = ParentWindow._account_changed
    _selected_uid = ParentWindow._selected_uid
    _try_auto_whats_new = mock.Mock()

    def __init__(self):
        self._users = []
        self._users_loaded_once = False
        self._users_loading = True
        self._account = FakeDropDown(self)
        self._no_users_message = FakeVisibleWidget()
        self.load_count = 0
        self.model_updates = 0
        self.selected_index = None
        self.apps_load_uids = []
        self.toasts = []

    def _ensure_apps_load(self, uid):
        self.apps_load_uids.append(uid)

    def _load_selected(self):
        self.load_count += 1

    def _toast(self, message):
        self.toasts.append(message)


class ParentWindowTests(unittest.TestCase):
    def release_window(self):
        window = SimpleNamespace(
            _closed=False, _fatal_discovery_error=False, _language_ready=True,
            _language_loading=False, _language_dialog=None, _own_language='de',
            _users_loaded_once=True, _whats_new_wait_id=0,
            _whats_new_auto_attempted=False, _whats_new_loaded_once=False,
            _whats_new_loading=True, _whats_new_record=None, _whats_new_dialog=None,
            _whats_new_menu_item=mock.Mock(), _language_shade=mock.Mock(),
            _whats_new_modal_blocked=mock.Mock(return_value=False),
            _client=mock.Mock(), _run=mock.Mock(), _load_policy_warnings=mock.Mock(),
            get_application=mock.Mock(return_value=SimpleNamespace(get_windows=lambda: [])),
            _toast=mock.Mock())
        for name in ('_try_auto_whats_new', '_show_whats_new', '_whats_new_closed',
                     '_whats_new_loaded', '_whats_new_failed'):
            setattr(window, name, lambda *args, _name=name:
                    getattr(ParentWindow, _name)(window, *args))
        return window

    @staticmethod
    def release_reply(auto=True):
        return {'product_version': '1.4', 'records': [{
            'ProductVersion': '1.4', 'record_id': '1.4:Parent',
            'Content': '## Changes\n- **Better** behavior', 'auto_show': auto}]}

    def test_release_waits_for_language_and_uses_the_final_preference(self):
        window = self.release_window()
        window._language_ready = False
        window._language_dialog = mock.Mock()
        with mock.patch('parent.oh_no_parent_control_parent.main.WhatsNewDialog') as dialog:
            window._whats_new_loaded(self.release_reply())
            dialog.assert_not_called()
            window._own_language = 'he'
            window._language_dialog = None
            window._language_ready = True
            window._try_auto_whats_new()
            self.assertEqual(dialog.call_args.args[0]._own_language, 'he')
            self.assertTrue(window._whats_new_auto_attempted)
            window._try_auto_whats_new()
            dialog.assert_called_once()
            window._run.assert_not_called()  # Query/presentation never persists seen state.

    def test_release_fresh_install_and_missing_or_wrong_audience_only_offer_valid_notes(self):
        for variant in ('fresh', 'missing', 'child', 'old'):
            window = self.release_window()
            reply = self.release_reply(auto=False)
            if variant == 'missing':
                reply['records'] = []
            elif variant == 'child':
                reply['records'][0]['record_id'] = '1.4:Child'
            elif variant == 'old':
                reply['records'][0]['ProductVersion'] = '1.3'
            with mock.patch('parent.oh_no_parent_control_parent.main.WhatsNewDialog') as dialog:
                window._whats_new_loaded(reply)
                dialog.assert_not_called()
                window._whats_new_menu_item.set_visible.assert_called_with(variant == 'fresh')

    def test_release_waits_for_other_modals_and_ignores_closed_or_fatal_parent(self):
        window = self.release_window()
        window._whats_new_record = self.release_reply()['records'][0]
        window._whats_new_modal_blocked.return_value = True
        with (mock.patch('parent.oh_no_parent_control_parent.main.GLib.timeout_add', return_value=7) as timer,
              mock.patch('parent.oh_no_parent_control_parent.main.WhatsNewDialog') as dialog):
            window._try_auto_whats_new()
            dialog.assert_not_called()
            self.assertEqual(window._whats_new_wait_id, 7)
            window._closed = True
            window._whats_new_loaded(self.release_reply())
            dialog.assert_not_called()
            window._closed = False
            window._fatal_discovery_error = True
            window._show_whats_new()
            dialog.assert_not_called()

    def test_release_modal_guard_includes_transient_windows_without_application_membership(self):
        window = mock.Mock()
        window.get_dialogs = lambda: SimpleNamespace(get_n_items=lambda: 0)
        intermediate = mock.Mock()
        intermediate.get_transient_for.return_value = window
        modal = mock.Mock()
        modal.get_transient_for.return_value = intermediate
        model = SimpleNamespace(get_n_items=lambda: 1, get_item=lambda index: modal)
        with mock.patch('parent.oh_no_parent_control_parent.main.Gtk.Window.get_toplevels', return_value=model):
            self.assertTrue(ParentWindow._whats_new_modal_blocked(window))
            modal.get_visible.return_value = False
            self.assertFalse(ParentWindow._whats_new_modal_blocked(window))

    def test_release_acknowledges_only_a_displayed_closed_record_and_keeps_failure_unseen(self):
        window = self.release_window()
        record = self.release_reply()['records'][0]
        window._whats_new_closed(record, False)
        window._run.assert_not_called()
        window._whats_new_closed(record, True)
        operation, success, failure = window._run.call_args.args
        operation()
        window._client.acknowledge_own_whats_new.assert_called_once_with('1.4')
        self.assertTrue(record['auto_show'])
        failure(RuntimeError('private data'))
        self.assertTrue(record['auto_show'])
        success(self.release_reply(auto=False))
        self.assertFalse(window._whats_new_record['auto_show'])

    def test_release_markdown_formats_content_and_never_interprets_html_or_unsafe_links(self):
        from parent.oh_no_parent_control_parent.release_markdown import inline_markup, markdown_blocks
        self.assertEqual(inline_markup('**Bold** & *italic* `x < y`'),
                         '<b>Bold</b> &amp; <i>italic</i> <tt>x &lt; y</tt>')
        self.assertIn('&lt;script&gt;', inline_markup('<script>alert(1)</script>'))
        self.assertNotIn('<a ', inline_markup('[bad](javascript:alert)'))
        self.assertNotIn('<a ', inline_markup('![remote](https://example.com/a.png)'))
        self.assertIn('<a href="https://example.com/?a=1&amp;b=2">',
                      inline_markup('[safe](https://example.com/?a=1&b=2)'))
        self.assertEqual([kind for kind, _markup in markdown_blocks(
            '## Heading\n\n- **Item**\n\n> Quote\n\n```\n<a>&\n```\n\n---\n\nEnd')],
            ['heading', 'list', 'quote', 'code', 'rule', 'paragraph'])
        self.assertEqual(markdown_blocks('Heading\n---'), [('heading', 'Heading')])

    def test_startup_presents_before_worker_and_coalesces_reactivation(self):
        from parent.oh_no_parent_control_parent.main import Application
        import parent.oh_no_parent_control_parent.main as main
        window = mock.Mock()
        app = SimpleNamespace(_startup_window=None, _client_factory=mock.Mock(),
                              _ensure_stylesheet=mock.Mock(),
                              _startup_closed=mock.Mock(), _startup_finished=mock.Mock())
        with (mock.patch.object(main.threading, 'Thread') as thread,
              mock.patch.object(main, 'ParentWindow', return_value=window) as parent,
              mock.patch.object(main, '_can_start') as check,
              mock.patch.object(main.GLib, 'idle_add') as idle):
            thread.return_value.start.side_effect = lambda: window.present.assert_called_once()
            Application._check_startup(app)
            Application._check_startup(app)
            parent.assert_called_once_with(app, client_factory=app._client_factory,
                                           defer_startup=True)
            thread.assert_called_once()
            check.assert_not_called()
            thread.call_args.kwargs['target']()
            check.assert_called_once()
            idle.assert_called_once_with(app._startup_finished, None)

    def test_startup_completion_respects_close_and_holds_during_window_transition(self):
        from parent.oh_no_parent_control_parent.main import Application
        for cancelled in (False, True):
            window = mock.Mock()
            app = SimpleNamespace(_startup_window=window, _startup_cancelled=cancelled,
                                  hold=mock.Mock(), release=mock.Mock(), do_activate=mock.Mock())
            error = RuntimeError('synthetic startup failure')
            Application._startup_finished(app, error)
            if cancelled:
                app.do_activate.assert_not_called()
                window.destroy.assert_not_called()
            else:
                self.assertTrue(app._startup_checked)
                self.assertIs(app._startup_error, error)
                app.hold.assert_called_once()
                app.release.assert_called_once()
                window.destroy.assert_called_once()
                window._close_requested.assert_called_once()
                app.do_activate.assert_called_once()

    def test_successful_startup_keeps_the_same_main_window(self):
        from parent.oh_no_parent_control_parent.main import Application
        window = mock.Mock()
        app = SimpleNamespace(_startup_window=window, _startup_cancelled=False,
                              do_activate=mock.Mock())
        Application._startup_finished(app, None)
        window._begin_startup.assert_called_once()
        window.destroy.assert_not_called()
        app.do_activate.assert_not_called()
        self.assertIsNone(app._startup_window)

    def test_closed_window_ignores_pending_client_initialization(self):
        window = SimpleNamespace(_closed=True, _client=None, _load_language=mock.Mock())
        ParentWindow._client_ready(window, mock.Mock())
        self.assertIsNone(window._client)
        window._load_language.assert_not_called()

    def test_screen_panel_waits_for_both_preferences_and_time(self):
        for preferences in (None, {"parent_control_enabled": True}):
            for time_ready in (False, True):
                for closed in (False, True):
                    with self.subTest(preferences=preferences, time_ready=time_ready, closed=closed):
                        panel = mock.Mock()
                        window = SimpleNamespace(_preferences=preferences,
                            _screen_time_ready=time_ready, _closed=closed,
                            _panels={"screen": panel})
                        ParentWindow._reveal_screen(window)
                        if closed:
                            panel.set_visible_child_name.assert_not_called()
                        else:
                            expected = "content" if preferences is not None and time_ready else "blank"
                            panel.set_visible_child_name.assert_called_once_with(expected)

    def setUp(self):
        from tests.support.objects import set_plain_text, plain_accessible_text
        for name, replacement in [('set_text', set_plain_text),
                                  ('accessible_text', plain_accessible_text)]:
            patch = mock.patch('parent.oh_no_parent_control_parent.main.' + name, replacement)
            patch.start()
            self.addCleanup(patch.stop)

    def test_session_language_collapses_variants_and_falls_back_to_english(self):
        for locale, expected in (
            ("en_GB.UTF-8", "en"), ("en-AU", "en"), ("de_DE@euro", "de"),
            ("es_MX", "es"), ("fr_CA", "fr"), ("pt_PT.UTF-8", "pt"),
            ("pt-BR", "pt-BR"), ("zh_TW.UTF-8", "zh-Hant"),
            ("zh-Hans-CN", "zh-Hans"), ("ru_RU", "ru"), ("it_IT", "it"),
            ("pl_PL", "pl"), ("ja_JP", "ja"), ("DE_de", "de"),
            ("ar_EG", "ar"), ("C.UTF-8", "en"), ("POSIX", "en"), ("", "en"),
        ):
            with self.subTest(locale=locale):
                self.assertEqual(supported_language(locale), expected)
        self.assertEqual(session_language(["nl_NL", "de_DE", "C"]), "nl")
        self.assertEqual(session_language(["zz_ZZ", "de_DE", "C"]), "en")
        self.assertEqual(session_language([]), "en")
        self.assertEqual(selected_language("", ["pt_PT.UTF-8"]), "pt")
        self.assertEqual(selected_language("fr-CA", ["de_DE"]), "fr")
        self.assertEqual(selected_language("", ["nl_NL", "fr_FR"]), "nl")

    def test_language_read_only_prompts_for_empty_or_requested_preferences(self):
        for language, requested, prompt in (("", False, True), ("de", False, False),
                                             ("xx-future", False, False), ("fr", True, True)):
            with self.subTest(language=language, requested=requested):
                window = SimpleNamespace(_closed=False, _language_requested=requested,
                    _fatal_discovery_error=False,
                    _language_readiness=object(), _open_language_dialog=mock.Mock(),
                    _apply_language=mock.Mock(return_value=True),
                    _finish_startup=mock.Mock(), _language_shade=mock.Mock(),
                    _try_auto_whats_new=mock.Mock())
                with mock.patch("parent.oh_no_parent_control_parent.main.set_automation_id") as identify:
                    ParentWindow._language_loaded(window, language)
                self.assertEqual(window._own_language, language)
                self.assertFalse(window._language_loading)
                window._apply_language.assert_called_once_with(language)
                self.assertEqual(window._open_language_dialog.called, prompt)
                self.assertEqual(window._finish_startup.called, not prompt)
                self.assertEqual(identify.called, not prompt)
                if not prompt:
                    window._language_shade.set_reveal_child.assert_called_once_with(False)
                    identify.assert_called_once_with(
                        window._language_readiness, "parent-language-ready")

    def custom_save_window(self):
        class Window:
            _clear_daily_limit_keyboard = ParentWindow._clear_daily_limit_keyboard
            _show_daily_limit_keyboard_choice = ParentWindow._show_daily_limit_keyboard_choice
            _custom_daily_limit_changed = ParentWindow._custom_daily_limit_changed
            _daily_limit_minutes = ParentWindow._daily_limit_minutes
            _save_parent_control = ParentWindow._save_parent_control
            _queue_save = ParentWindow._queue_save
            _start_save = ParentWindow._start_save
            _start_next_save = ParentWindow._start_next_save
            _save_succeeded = ParentWindow._save_succeeded
            _save_failed = ParentWindow._save_failed
            _set_apps_sensitive = ParentWindow._set_apps_sensitive

        window = Window()
        window._loading = False
        window._save_in_progress = False
        window._active_save = None
        window._pending_saves = []
        window._restore_preferences_uid = None
        window._selected_uid = lambda: 1001
        window._preferences = {
            "parent_control_enabled": True, "daily_time_limit_minutes": 15,
        }
        window._daily_limit_selected = CUSTOM_DAILY_LIMIT_INDEX
        window._update_daily_limit_choice_styles = mock.Mock()
        window._scroll_daily_limit_keyboard_choice = mock.Mock()
        for name in ("_account", "_revoke", "_daily_limit", "_apps_group",
                     "_custom_daily_limit"):
            setattr(window, name, mock.Mock())
        window._enabled = FakeSensitiveWidget(active=True)
        window._custom_daily_limit_entry = mock.Mock()
        window._custom_daily_limit_entry.get_text.return_value = "15"
        for name in ("_cancel_custom_daily_limit_save", "_start_parent_control_save",
                     "_start_app_policy_save", "_load_policy_warnings",
                     "_load_time_status", "_show_error", "_preferences_loaded"):
            setattr(window, name, mock.Mock())
        return window

    def test_unchanged_custom_focus_leave_does_not_start_save(self):
        window = self.custom_save_window()
        window._custom_daily_limit_changed()
        window._start_parent_control_save.assert_not_called()
        window._daily_limit.set_sensitive.assert_not_called()
        self.assertFalse(window._save_in_progress)

    def test_loading_saved_allowance_restores_editor_after_rejected_draft(self):
        for minutes in (0, 15, 73, 1439):
            for draft in ("", "abc", "-1", "0.5", "1440", "1441"):
                with self.subTest(minutes=minutes, draft=draft):
                    window = self.custom_save_window()
                    window._custom_daily_limit_entry.get_text.return_value = draft
                    window._custom_daily_limit_changed()
                    window._custom_daily_limit_entry.add_css_class.assert_called_with("error")
                    window._start_parent_control_save.assert_not_called()
                    window._update_daily_limit_choice_styles = mock.Mock()
                    window._loading = True
                    ParentWindow._set_daily_limit_value(window, minutes)
                    window._custom_daily_limit_entry.set_text.assert_called_once_with(str(minutes))
                    window._custom_daily_limit_entry.remove_css_class.assert_called_with("error")
                    self.assertEqual(
                        window._custom_daily_limit_entry.update_property.call_args.args[1],
                        ["Enter a whole number of minutes from zero through 1439."],
                    )
                    selected, is_custom = _daily_limit_selection(minutes)
                    self.assertEqual(window._daily_limit_selected, selected)
                    window._custom_daily_limit.set_visible.assert_called_with(is_custom)
                    window._start_parent_control_save.assert_not_called()

    def test_custom_typing_remains_editable_and_saves_in_order(self):
        window = self.custom_save_window()
        # Repeated commit signals must not repeat a write; returning to the
        # original saved value must still follow the outstanding newer values.
        for text in ("1", "1", "14", "14", "15", "15"):
            window._custom_daily_limit_entry.get_text.return_value = text
            window._custom_daily_limit_changed()
        window._start_parent_control_save.assert_called_once_with(1001, True, 1)
        self.assertEqual([save[2] for save in window._pending_saves],
                         [(True, 14), (True, 15)])
        window._custom_daily_limit.set_sensitive.assert_called_with(True)
        window._daily_limit.set_sensitive.assert_called_with(True)
        window._account.set_sensitive.assert_called_with(False)
        self.assertFalse(window._enabled.sensitive)
        for minutes in (1, 14, 15):
            window._save_succeeded(1001, {
                "parent_control_enabled": True, "daily_time_limit_minutes": minutes,
            })
            window._custom_daily_limit.set_sensitive.assert_called_with(True)
            window._custom_daily_limit_entry.set_text.assert_not_called()
        self.assertEqual(window._start_parent_control_save.call_args_list,
                         [mock.call(1001, True, value) for value in (1, 14, 15)])
        self.assertFalse(window._save_in_progress)
        self.assertIsNone(window._active_save)
        self.assertEqual(window._preferences["daily_time_limit_minutes"], 15)

    def test_preset_selected_during_custom_save_is_committed_after_it(self):
        window = self.custom_save_window()
        window._custom_daily_limit_entry.get_text.return_value = "30"
        window._custom_daily_limit_changed()
        window._daily_limit.set_sensitive.assert_called_with(True)
        window._update_daily_limit_choice_styles = mock.Mock()
        ParentWindow._daily_limit_changed(window, None, DAILY_LIMIT_PRESETS.index(45))
        self.assertEqual(window._pending_saves, [("parent-control", 1001, (True, 45))])
        window._save_succeeded(1001, {
            "parent_control_enabled": True, "daily_time_limit_minutes": 30,
        })
        window._start_parent_control_save.assert_called_with(1001, True, 45)
        window._save_succeeded(1001, {
            "parent_control_enabled": True, "daily_time_limit_minutes": 45,
        })
        self.assertEqual(window._preferences["daily_time_limit_minutes"], 45)
        self.assertFalse(window._save_in_progress)

    def test_invalid_draft_during_custom_save_is_not_queued_or_overwritten(self):
        window = self.custom_save_window()
        window._custom_daily_limit_entry.get_text.return_value = "1"
        window._custom_daily_limit_changed()
        for text in ("", "abc", "-1", "0.5", "1440", "1441"):
            window._custom_daily_limit_entry.get_text.return_value = text
            window._custom_daily_limit_changed()
        self.assertEqual(window._pending_saves, [])
        window._save_succeeded(1001, {
            "parent_control_enabled": True, "daily_time_limit_minutes": 1,
        })
        window._custom_daily_limit_entry.set_text.assert_not_called()
        window._custom_daily_limit_entry.add_css_class.assert_called_with("error")
        self.assertEqual(window._preferences["daily_time_limit_minutes"], 1)

    def test_custom_save_failure_drains_later_edits_before_restoring(self):
        window = self.custom_save_window()
        for text in ("1", "14"):
            window._custom_daily_limit_entry.get_text.return_value = text
            window._custom_daily_limit_changed()
        window._save_failed(1001, "screen-time settings", RuntimeError("failed"))
        window._show_error.assert_called_once()
        window._preferences_loaded.assert_not_called()
        window._start_parent_control_save.assert_called_with(1001, True, 14)
        preferences = {"parent_control_enabled": True, "daily_time_limit_minutes": 14}
        window._save_succeeded(1001, preferences)
        window._preferences_loaded.assert_called_once_with(preferences)
        self.assertFalse(window._save_in_progress)
        self.assertIsNone(window._active_save)

    def test_other_save_and_loading_states_keep_custom_editor_disabled(self):
        for kind in ("app-policy", "parent-control"):
            window = self.custom_save_window()
            window._start_save((kind, 1001, (True, 15)))
            window._custom_daily_limit.set_sensitive.assert_called_with(False)
            window._daily_limit.set_sensitive.assert_called_with(False)
        for loading, uid, enabled in ((True, 1001, True), (False, None, True),
                                      (False, 1001, False)):
            window = self.custom_save_window()
            window._loading = loading
            window._selected_uid = lambda: uid
            window._enabled.active = enabled
            window._active_save = ("custom-allowance", 1001, (True, 1))
            window._save_in_progress = True
            window._set_apps_sensitive(True)
            window._custom_daily_limit.set_sensitive.assert_called_with(False)
            window._daily_limit.set_sensitive.assert_called_with(False)

    def test_policy_warning_is_visible_without_repeated_dialogs_and_recovers(self):
        window = mock.Mock()
        window._language_dialog = None
        window._whats_new_dialog = None
        window._selected_uid.return_value = 1001
        window._policy_warnings_closed = False
        window._reported_policy_warnings = {}
        window._app_catalog = [{"id": "lunar.desktop", "name": "Lunar Client"}]
        for _ in range(3):
            ParentWindow._policy_warnings_loaded(window, 1001, ["lunar.desktop"])
        window._show_error.assert_called_once()
        self.assertIn("Lunar Client", window._policy_warning.set_label.call_args.args[0])
        self.assertNotIn("Lunar Client", window._show_error.call_args.args[1])
        window._policy_warning.set_visible.assert_called_with(True)
        window._set_apps_sensitive.assert_not_called()
        ParentWindow._policy_warnings_loaded(window, 1001, [])
        window._policy_warning.set_visible.assert_called_with(False)
        ParentWindow._policy_warnings_loaded(window, 1001, ["lunar.desktop"])
        self.assertEqual(window._show_error.call_count, 2)

    def test_stale_and_closed_warning_results_do_not_modify_current_surface(self):
        window = mock.Mock()
        window._policy_warnings_closed = False
        window._selected_uid.return_value = 1002
        ParentWindow._policy_warnings_loaded(window, 1001, ["lunar.desktop"])
        window._load_policy_warnings.assert_called_once()
        window._policy_warning.set_visible.assert_not_called()
        window._show_error.assert_not_called()
        window._policy_warnings_closed = True
        ParentWindow._policy_warnings_failed(window, 1002, RuntimeError("private"))
        window._show_error.assert_not_called()

    def test_warning_query_errors_and_discovery_outages_do_not_close_loaded_window(self):
        window = mock.Mock()
        window._language_dialog = None
        window._whats_new_dialog = None
        window._policy_warnings_closed = False
        window._policy_warning_query_failed = False
        window._selected_uid.return_value = 1001
        window._users_loaded_once = True
        window._user_discovery_error_reported = False
        error = RuntimeError("private")
        for _ in range(3):
            ParentWindow._policy_warnings_failed(window, 1001, error)
            ParentWindow._users_failed(window, error)
        self.assertEqual(window._show_error.call_count, 2)
        self.assertFalse(window._users_loading)
        window.get_content.assert_not_called()
        window.get_application.assert_not_called()

    def test_runtime_icon_matches_the_installed_parent_desktop_icon(self):
        root = Path(__file__).resolve().parents[2]
        desktop_entry = (
            root / "data/applications/com.puffyslippers.OhNoParentControl.Parent.desktop"
        ).read_text(encoding="utf-8")

        self.assertIn(f"Icon={APPLICATION_ICON_NAME}", desktop_entry)
        self.assertIn(
            "self.set_icon_name(APPLICATION_ICON_NAME)",
            inspect.getsource(ParentWindow.__init__),
        )

    def test_preview_client_uses_fixture_data_and_persists_ui_changes_in_memory(self):
        client = PreviewBrokerClient()

        self.assertEqual(client.list_users(), PREVIEW_USERS)
        preferences = client.get_preferences(1001)
        preferences["daily_time_limit_minutes"] = 120
        client.set_preferences(1001, preferences)

        self.assertEqual(client.get_preferences(1001)["daily_time_limit_minutes"], 120)

    def test_preview_shows_the_three_policy_and_match_rule_combinations(self):
        client = PreviewBrokerClient()
        applications = {app["id"]: app for app in client.list_apps(1001)}
        policies = client.get_preferences(1001)["apps"]

        self.assertEqual(
            [(app_id, policies[app_id]["state"], bool(policies[app_id]["patterns"]))
             for app_id in (
                 "thunderbird_thunderbird.desktop",
                 "lunarclient.desktop",
                 "com.mojang.Minecraft.desktop",
                 "steam.desktop",
             )],
            [
                ("thunderbird_thunderbird.desktop", "allowed", True),
                ("lunarclient.desktop", "permanent", True),
                ("com.mojang.Minecraft.desktop", "conditional", False),
                ("steam.desktop", "conditional", False),
            ],
        )
        self.assertEqual(
            applications["com.mojang.Minecraft.desktop"]["suggested_patterns"], [],
        )
        self.assertEqual(applications["steam.desktop"]["targets"], ["/usr/bin/steam"])

    def test_preview_uses_the_bundled_thunderbird_icon(self):
        client = PreviewBrokerClient()
        applications = {app["id"]: app for app in client.list_apps(1001)}

        self.assertEqual(
            applications["thunderbird_thunderbird.desktop"]["icon"],
            PREVIEW_THUNDERBIRD_ICON,
        )
        self.assertTrue(Path(PREVIEW_THUNDERBIRD_ICON).is_file())

    def test_loading_an_exact_match_policy_accepts_an_empty_pattern_list(self):
        class SettableToggle:
            def set_active(self, _active):
                pass

        class ExactMatchRow:
            app = {"id": "calculator.desktop", "targets": ["/usr/bin/gnome-calculator"]}
            policy_buttons = {"conditional": SettableToggle()}
            user_saved_match_rule = False
            match_rule = "not-yet-loaded"

        class ExactMatchHarness:
            _preferences_loaded = ParentWindow._preferences_loaded
            _apply_app_policies = ParentWindow._apply_app_policies
            _default_match_rule = ParentWindow._default_match_rule
            _update_match_rule_icon = lambda self, _row: None
            _load_time_status = lambda self: None

            def __init__(self):
                self._enabled = SettableToggle()
                self._set_daily_limit_value = lambda *_args: None
                self._rows = [ExactMatchRow()]
                self._selected_uid = lambda: 1001
                self._loading = False
                self._set_apps_sensitive = lambda _sensitive: None
                self._update_apps_loading_ui = lambda: None
                self._filter = lambda *_args: None

        harness = ExactMatchHarness()
        harness._preferences_loaded({
            "parent_control_enabled": True,
            "daily_time_limit_minutes": 90,
            "apps": {"calculator.desktop": {"state": "conditional", "patterns": []}},
        })

        self.assertIsNone(harness._rows[0].match_rule)

    def test_parent_app_only_starts_when_broker_authorizes_its_caller(self):
        class AuthorizedClient:
            def list_users(self):
                return []

        class DeniedClient:
            def list_users(self):
                raise RuntimeError("administrator access is required")

        self.assertTrue(_can_start(AuthorizedClient))
        self.assertFalse(_can_start(DeniedClient))

    def test_startup_logs_outcome_and_wait_without_exception_text(self):
        from gi.repository import Gio
        from common.oh_no_parent_control_ui.diagnostic_events import decode
        from parent.oh_no_parent_control_parent.client import BUS_NAME
        for name, outcome in ((None, 'ready'),
                (f'{BUS_NAME}.Error.RebootRequired', 'reboot-required'),
                (f'{BUS_NAME}.Error.AccessDenied', 'access-denied'),
                ('org.freedesktop.DBus.Error.TimedOut', 'unavailable')):
            client = mock.Mock()
            error = Gio.DBusError.new_for_dbus_error(name, 'private-account-detail') if name else None
            client.list_users.side_effect = error
            received = []
            with (mock.patch('parent.oh_no_parent_control_parent.main.time.monotonic',
                             side_effect=[100, 125]), self.assertLogs('onpc.parent', 'INFO') as logs):
                self.assertEqual(_can_start(lambda: client, received.append), name is None)
            records = [decode(record.onpc_payload) for record in logs.records]
            self.assertEqual([record['fields'] for record in records], [
                {'outcome': 'started', 'elapsed_ms': 0},
                {'outcome': outcome, 'elapsed_ms': 25000}])
            self.assertNotIn('private-account-detail', str(logs.output))
            self.assertEqual(received, [error] if name else [])

    def test_app_policy_states_keep_the_original_three_state_visuals(self):
        self.assertEqual(
            [(state["id"], state["icon"], state["css"]) for state in STATES],
            [
                ("allowed", "emblem-ok-symbolic", "policy-allowed"),
                ("permanent", "window-close-symbolic", "policy-hard-blocked"),
                ("conditional", "dialog-warning-symbolic", "policy-soft-blocked"),
            ],
        )

    def test_app_list_places_soft_block_before_hard_block(self):
        self.assertEqual(
            [state["id"] for state in APP_LIST_STATES],
            ["allowed", "conditional", "permanent"],
        )

    def test_parent_title_bar_uses_the_shared_product_logo(self):
        source = inspect.getsource(ParentWindow._build)
        stylesheet = (
            Path(__file__).resolve().parents[2]
            / "parent/oh_no_parent_control_parent/style.css"
        ).read_text(encoding="utf-8")

        self.assertIn('branding_asset_path("app_logo_titlebar.png")', source)
        self.assertIn("title_logo.set_pixel_size(48)", source)
        self.assertIn('css_classes=["parent-title-brand"]', source)
        self.assertIn(".parent-title-brand image {", stylesheet)

        logo = (
            Path(__file__).resolve().parents[2] / "data/app_logo_titlebar.png"
        )
        with logo.open("rb") as source_file:
            source_file.read(16)
            self.assertEqual(struct.unpack(">II", source_file.read(8)), (48, 48))

    def test_match_rule_states_use_the_new_rule_icons_and_selected_button_classes(self):
        self.assertEqual(
            [(rule["id"], rule["glyph"], rule["css"]) for rule in MATCH_RULES],
            [
                ("pattern", "***", "match-rule-pattern"),
                ("precise", "ABC", "match-rule-precise"),
            ],
        )
        stylesheet = (
            Path(__file__).resolve().parents[2]
            / "parent/oh_no_parent_control_parent/style.css"
        ).read_text(encoding="utf-8")
        self.assertIn(".match-rule-button.match-rule-pattern {", stylesheet)
        self.assertIn(".match-rule-button.match-rule-precise {", stylesheet)
        self.assertIn(".match-rule-icon {\n  font-size: 16px;", stylesheet)
        self.assertIn("padding: 2px 1px 0;", stylesheet)
        self.assertIn(".match-rule-icon.match-rule-pattern {\n  font-size: 20px;", stylesheet)
        self.assertIn("padding-top: 3px;", stylesheet)
        self.assertIn("min-width: 36px;", stylesheet)
        self.assertNotIn(".match-rule-button.match-rule-pattern:hover", stylesheet)

    def test_app_policy_headings_use_measurement_matched_control_slots(self):
        source = inspect.getsource(ParentWindow._build)

        self.assertIn('self._match_rule_slot()', source)
        self.assertIn('self._policy_selector_slot()', source)
        self.assertIn('self._policy_column_heading(', source)

    def test_match_and_access_rule_headings_are_multi_select_filters(self):
        source = inspect.getsource(ParentWindow._policy_column_heading)
        stylesheet = (
            Path(__file__).resolve().parents[2]
            / "parent/oh_no_parent_control_parent/style.css"
        ).read_text(encoding="utf-8")
        build = inspect.getsource(ParentWindow._build)

        self.assertIn("Gtk.Popover(", source)
        self.assertIn("localized(Gtk.CheckButton,", source)
        self.assertIn("trigger.set_popover(popover)", source)
        self.assertIn("icon_factory(item)", source)
        self.assertIn('css_classes=["app-policy-filter-item-label"]', source)
        self.assertIn("MATCH_RULES, self._match_rule_filters", build)
        self.assertIn("STATES, self._access_rule_filters", build)
        self.assertIn("self._match_rule_filter_icon", build)
        self.assertIn("self._access_rule_filter_icon", build)
        self.assertIn(".app-policy-filter > button {", stylesheet)
        self.assertIn(".app-policy-filter-item-label {", stylesheet)
        self.assertIn(
            ".match-rule-header .app-policy-filter {\n  margin-right: 41px;",
            stylesheet,
        )
        self.assertNotIn(
            ".match-rule-header .app-policy-column-header {",
            stylesheet,
        )

    def test_app_table_filters_rows_by_search_match_rule_and_access_rule(self):
        class FakeSearch:
            def get_text(self):
                return "calc"

        class VisibleRow:
            def __init__(self, search_text, match_rule, access):
                self.search_text = search_text
                self.match_rule = match_rule
                self.app = {
                    "targets": ["/usr/bin/gnome-calculator"],
                    "suggested_patterns": [],
                }
                self.policy_buttons = {
                    "allowed": FakeToggleButton(access == "allowed"),
                    "permanent": FakeToggleButton(access == "permanent"),
                    "conditional": FakeToggleButton(access == "conditional"),
                }
                self.visible = None

            def set_visible(self, visible):
                self.visible = visible

        shown = VisibleRow("calculator desktop", None, "conditional")
        hidden_search = VisibleRow("firefox desktop", None, "conditional")
        hidden_match = VisibleRow(
            "calc pattern", "/usr/lib/calc/calc-*.0", "conditional",
        )
        hidden_access = VisibleRow("calculator allowed", None, "allowed")
        window = type("WindowHarness", (), {})()
        window._search = FakeSearch()
        window._match_rule_filters = {"precise"}
        window._access_rule_filters = {"conditional"}
        window._rows = [shown, hidden_search, hidden_match, hidden_access]
        window._default_match_rule = lambda row: ParentWindow._default_match_rule(
            window, row,
        )
        window._is_pattern = ParentWindow._is_pattern
        window._row_match_rule_id = lambda row: ParentWindow._row_match_rule_id(
            window, row,
        )
        window._row_access_rule_id = ParentWindow._row_access_rule_id
        window._row_matches_filters = (
            lambda row, query: ParentWindow._row_matches_filters(window, row, query)
        )

        ParentWindow._filter(window)

        self.assertTrue(shown.visible)
        self.assertFalse(hidden_search.visible)
        self.assertFalse(hidden_match.visible)
        self.assertFalse(hidden_access.visible)

    def test_main_body_is_split_into_screen_and_app_limit_tabs(self):
        source = inspect.getsource(ParentWindow._build)

        account_picker = source.index("account_actions.append(self._account)")
        view_stack = source.index("pages = Adw.ViewStack")
        screen_tab = source.index(
            'screen_limits_page, "screen-limits", m.SCREEN_LIMITS, "alarm-symbolic"'
        )
        app_tab = source.index(
            'app_limits_page, "app-limits", m.APP_LIMITS, "view-grid-symbolic"'
        )

        self.assertLess(account_picker, view_stack)
        self.assertLess(view_stack, screen_tab)
        self.assertLess(screen_tab, app_tab)
        self.assertEqual(m.SCREEN_LIMITS.source, 'Screen Limits')
        self.assertEqual(m.APP_LIMITS.source, 'App Limits')
        self.assertIn("screen_limits_page.set_child(Adw.Clamp(", source)
        self.assertIn("screen_limits.append(screen_limit_rows)", source)
        self.assertIn("search_row.append(self._legend_button())", source)
        self.assertIn("app_limits.append(apps_section)", source)
        self.assertIn("app_limits_scroll.set_child(Adw.Clamp(", source)

    def test_screen_limits_use_reference_card_and_calculation_layout(self):
        source = inspect.getsource(ParentWindow._build)
        stylesheet = (
            Path(__file__).resolve().parents[2]
            / "parent/oh_no_parent_control_parent/style.css"
        ).read_text(encoding="utf-8")

        self.assertIn("ParentAccountSelector(self._account_changed)", source)
        selector = inspect.getsource(ParentAccountSelector)
        self.assertIn("Adw.Avatar(", selector)
        self.assertIn("Gdk.Texture.new_from_filename(icon_file)", selector)
        self.assertIn('automation_id=f"parent-child-choice-{uid}"', selector)
        self.assertNotIn("Gtk.DropDown", selector)
        self.assertNotIn("👦🏻", selector)
        self.assertIn('self._time_status = localized(Adw.ExpanderRow,', source)
        self.assertIn('self._time_status.add_suffix(self._time_status_value)', source)
        self.assertIn('self._time_status.add_row(self._time_calculation_panel())', source)
        self.assertEqual(source.count("maximum_size=CONTENT_MAX_WIDTH"), 4)
        self.assertIn(".account-picker {", stylesheet)
        self.assertIn('css_classes=["account-actions-separator"]', source)
        self.assertIn(".account-actions-separator {", stylesheet)
        self.assertIn("margin: 16px 28px;", stylesheet)
        self.assertIn(".revoke-grant-action {", stylesheet)
        self.assertIn(".revoke-grant-button:hover {", stylesheet)
        self.assertIn(".revoke-grant-button:active {", stylesheet)
        self.assertIn('gicon=revoke_gicon, pixel_size=40', source)
        self.assertIn("width_request=270, max_width_chars=36", source)
        self.assertIn("width_request=320", source)
        self.assertNotIn("revoke_icon.append", source)
        self.assertIn(".screen-limits-card-header {", stylesheet)
        self.assertIn(".screen-limit-switch:checked {", stylesheet)
        self.assertIn(".calculation-panel {", stylesheet)
        self.assertIn(".remaining-time-value {", stylesheet)

    def test_screen_limit_setting_icons_are_centered_in_their_tile(self):
        source = inspect.getsource(ParentWindow._setting_icon)

        self.assertIn("container = Gtk.CenterBox(", source)
        self.assertIn("container.set_center_widget(Gtk.Image(", source)

    def test_policy_selector_measurement_slot_is_fully_transparent(self):
        source = inspect.getsource(ParentWindow._policy_selector_slot)

        self.assertIn('opacity=0, css_classes=["policy-selector"]', source)

    def test_match_rule_control_is_centered_in_a_dedicated_cell(self):
        root = Path(__file__).resolve().parents[2]
        stylesheet = (
            root / "parent/oh_no_parent_control_parent/style.css"
        ).read_text(encoding="utf-8")
        source = inspect.getsource(ParentWindow._add_app_row)

        self.assertIn(".match-rule-cell {\n  min-width: 92px;", stylesheet)
        self.assertIn("width_request=92, halign=Gtk.Align.CENTER", source)

    def test_match_rule_button_uses_an_interactive_capsule(self):
        stylesheet = (
            Path(__file__).resolve().parents[2]
            / "parent/oh_no_parent_control_parent/style.css"
        ).read_text(encoding="utf-8")

        self.assertIn(".match-rule-button.policy-choice {", stylesheet)
        self.assertIn("min-height: 36px;", stylesheet)
        self.assertIn(".match-rule-button.policy-choice:hover {", stylesheet)
        self.assertIn("border-radius: 12px;", stylesheet)

    def test_app_limits_compact_layout_starts_with_legend(self):
        source = inspect.getsource(ParentWindow._build)
        initializer = inspect.getsource(ParentWindow.__init__)
        stylesheet = (
            Path(__file__).resolve().parents[2]
            / "parent/oh_no_parent_control_parent/style.css"
        ).read_text(encoding="utf-8")

        self.assertIn(
            "self.set_default_size(DEFAULT_WINDOW_WIDTH, 1168)", initializer,
        )
        self.assertIn('css_classes=["app-limits-card"]', source)
        self.assertNotIn('label=m.APP_LIMITS, xalign=0', source)
        self.assertIn('css_classes=["apps-section"]', source)
        self.assertIn('css_classes=["apps-panel"]', source)
        self.assertIn('css_classes=["apps-table-overlay"]', source)
        self.assertIn('css_classes=["apps-loading-mask"]', source)
        self.assertIn('label=m.LOADING_INSTALLED_APPS', source)
        self.assertEqual(m.LOADING_INSTALLED_APPS.source, 'Loading installed apps…')
        self.assertNotIn(".app-limits-card-header {", stylesheet)
        self.assertIn(".apps-section {\n  margin: 16px 29px 16px;", stylesheet)
        self.assertIn(".apps-loading-mask {", stylesheet)
        self.assertIn(".policy-choice {\n  min-width: 36px;", stylesheet)

    def test_match_rule_legend_uses_normal_visual_state(self):
        source = inspect.getsource(ParentWindow._legend_section)

        self.assertIn("icon = localized(Gtk.Button,", source)
        self.assertIn("can_focus=False, can_target=False", source)
        self.assertNotIn("sensitive=False", source)

    def test_legend_icons_use_the_same_dimensions_as_app_table_controls(self):
        stylesheet = (
            Path(__file__).resolve().parents[2]
            / "parent/oh_no_parent_control_parent/style.css"
        ).read_text(encoding="utf-8")
        source = inspect.getsource(ParentWindow._legend_section)

        self.assertNotIn(".policy-choice.policy-legend-icon {", stylesheet)
        self.assertNotIn(
            ".match-rule-button.policy-choice.policy-legend-icon {", stylesheet,
        )
        self.assertIn(".policy-choice {\n  min-width: 36px;\n  min-height: 36px;",
                      stylesheet)
        self.assertIn(
            ".match-rule-button.policy-choice {\n  min-width: 36px;\n"
            "  min-height: 36px;",
            stylesheet,
        )
        self.assertEqual(source.count("can_focus=False, can_target=False"), 2)

    def test_legend_is_one_initially_closed_floating_panel(self):
        source = inspect.getsource(ParentWindow._legend_button)
        toggled = inspect.getsource(ParentWindow._legend_toggled)
        stylesheet = (
            Path(__file__).resolve().parents[2]
            / "parent/oh_no_parent_control_parent/style.css"
        ).read_text(encoding="utf-8")

        self.assertIn('label=m.LEGEND', source)
        self.assertEqual(m.LEGEND.source, 'Legend')
        self.assertIn('active=False', source)
        self.assertIn('popover = Gtk.Popover(', source)
        self.assertIn('autohide=True', source)
        self.assertIn('automation_id="parent-legend-close"', source)
        self.assertIn(
            'set_automation_id(sections, "parent-legend-content")', source,
        )
        self.assertIn('m.APP_ACCESS_WHAT_HAPPENS, APP_LIST_STATES', source)
        self.assertIn('m.MATCH_RULE_HOW_APPS_ARE_MATCHED, MATCH_RULES', source)
        self.assertEqual(m.APP_ACCESS_WHAT_HAPPENS.source, 'App Access (What happens)')
        self.assertEqual(m.MATCH_RULE_HOW_APPS_ARE_MATCHED.source, 'Match Rule (How apps are matched)')
        self.assertIn('orientation=Gtk.Orientation.VERTICAL', source)
        self.assertIn('popover.popup()', toggled)
        self.assertIn('popover.popdown()', toggled)
        self.assertIn('.policy-legend-popover > contents {', stylesheet)

    def test_legend_book_icon_is_centered_in_its_tile(self):
        source = inspect.getsource(ParentWindow._legend_button)

        self.assertIn("book = Gtk.CenterBox(", source)
        self.assertIn("book.set_center_widget(Gtk.Image(", source)
        self.assertNotIn("hexpand=True, halign=Gtk.Align.CENTER", source)

    def test_daily_limit_labels_use_singular_only_for_one_minute(self):
        self.assertEqual(_minutes_label(0), "0 minutes")
        self.assertEqual(_minutes_label(1), "1 minute")
        self.assertEqual(_minutes_label(1440), "1440 minutes")

    def test_daily_limit_menu_has_requested_presets_and_custom_selection(self):
        self.assertEqual(DAILY_LIMIT_PRESETS[:4], (0, 15, 30, 45))
        self.assertEqual(DAILY_LIMIT_PRESETS[-1], 23 * 60 + 30)
        self.assertEqual(_daily_limit_label(90), "1.5 hours")
        self.assertEqual(_daily_limit_selection(30), (2, False))
        self.assertEqual(_daily_limit_selection(31), (CUSTOM_DAILY_LIMIT_INDEX, True))

    def test_keyboard_allowance_requires_units_and_an_exact_preset(self):
        for text, minutes in (("15m", 15), ("15h", 900), ("2.5h", 150),
                              ("0m", 0), ("23.5H", 1410)):
            self.assertEqual(_daily_limit_keyboard_selection(text), DAILY_LIMIT_PRESETS.index(minutes))
        for text in ("15", "2.5", "31m", "24h", "-15m", "1.001h", "m", "2..5h"):
            self.assertIsNone(_daily_limit_keyboard_selection(text))

    def test_keyboard_allowance_buffers_cancels_and_commits_without_early_save(self):
        from parent.oh_no_parent_control_parent.main import Gdk
        window = self.custom_save_window()
        window._daily_limit_key_pressed = ParentWindow._daily_limit_key_pressed.__get__(window)
        window._daily_limit_changed = ParentWindow._daily_limit_changed.__get__(window)
        window._update_daily_limit_choice_styles = mock.Mock()
        window._daily_limit_selected = DAILY_LIMIT_PRESETS.index(15)
        window._clear_daily_limit_keyboard()
        def key(value, modifiers=0):
            return window._daily_limit_key_pressed(None, value, 0, modifiers)
        for char in "2.5":
            self.assertTrue(key(ord(char)))
        self.assertEqual(window._daily_limit_selected, DAILY_LIMIT_PRESETS.index(15))
        window._start_parent_control_save.assert_not_called()
        key(Gdk.KEY_Escape)
        self.assertIsNone(window._daily_limit_keyboard_index)
        key(Gdk.KEY_Down)
        key(Gdk.KEY_Up)
        key(Gdk.KEY_Down)
        window._start_parent_control_save.assert_not_called()
        key(Gdk.KEY_Return)
        window._start_parent_control_save.assert_called_once_with(1001, True, 30)
        self.assertFalse(key(ord('c'), Gdk.ModifierType.CONTROL_MASK))
        key(ord('c'))
        window._custom_daily_limit_entry.grab_focus.assert_not_called()
        key(Gdk.KEY_Return)
        window._custom_daily_limit.set_visible.assert_called_with(True)
        window._custom_daily_limit_entry.grab_focus.assert_called_once()

    def test_keyboard_typing_buffers_until_enter_and_escape_discards_choice(self):
        from parent.oh_no_parent_control_parent.main import Gdk
        window = self.custom_save_window()
        window._daily_limit_key_pressed = ParentWindow._daily_limit_key_pressed.__get__(window)
        window._daily_limit_changed = ParentWindow._daily_limit_changed.__get__(window)
        window._update_daily_limit_choice_styles = mock.Mock()
        window._daily_limit_selected = DAILY_LIMIT_PRESETS.index(15)
        window._clear_daily_limit_keyboard()
        window._daily_limit.reset_mock()
        for char in "2.5":
            window._daily_limit_key_pressed(None, ord(char), 0, 0)
        window._daily_limit.set_label.assert_called_with("15 minutes")
        window._start_parent_control_save.assert_not_called()
        window._daily_limit_key_pressed(None, ord('h'), 0, 0)
        window._daily_limit.set_label.assert_called_with("2.5 hours")
        window._start_parent_control_save.assert_not_called()
        self.assertEqual(window._daily_limit_selected, DAILY_LIMIT_PRESETS.index(15))
        window._daily_limit_key_pressed(None, Gdk.KEY_Escape, 0, 0)
        window._daily_limit.popdown.assert_called_once()
        window._daily_limit.set_label.assert_called_with("15 minutes")
        window._start_parent_control_save.assert_not_called()
        for char in "2.5h":
            window._daily_limit_key_pressed(None, ord(char), 0, 0)
        window._daily_limit_key_pressed(None, Gdk.KEY_Return, 0, 0)
        window._start_parent_control_save.assert_called_once_with(1001, True, 150)
        self.assertEqual(window._daily_limit.popdown.call_count, 2)
        self.assertEqual(window._daily_limit_selected, DAILY_LIMIT_PRESETS.index(150))

    def test_keyboard_exact_match_resets_typing_for_another_pending_choice(self):
        from parent.oh_no_parent_control_parent.main import Gdk
        window = self.custom_save_window()
        window._daily_limit_key_pressed = ParentWindow._daily_limit_key_pressed.__get__(window)
        window._daily_limit_changed = ParentWindow._daily_limit_changed.__get__(window)
        committed = DAILY_LIMIT_PRESETS.index(15)
        window._daily_limit_selected = committed
        window._clear_daily_limit_keyboard()

        def type_choice(text, minutes):
            for char in text:
                window._daily_limit_key_pressed(None, ord(char), 0, 0)
            self.assertEqual(window._daily_limit_keyboard_text, "")
            self.assertEqual(window._daily_limit_keyboard_index, DAILY_LIMIT_PRESETS.index(minutes))
            self.assertEqual(window._daily_limit_selected, committed)
            window._start_parent_control_save.assert_not_called()

        type_choice("15h", 900)
        window._daily_limit.set_label.assert_called_with("15 hours")
        type_choice("0m", 0)
        window._daily_limit.set_label.assert_called_with("0 minutes")
        window._daily_limit_key_pressed(None, Gdk.KEY_Escape, 0, 0)
        self.assertEqual(window._daily_limit_selected, committed)
        self.assertIsNone(window._daily_limit_keyboard_index)
        window._start_parent_control_save.assert_not_called()
        window._daily_limit.popdown.assert_called_once()

        type_choice("15h", 900)
        type_choice("0m", 0)
        window._daily_limit_key_pressed(None, Gdk.KEY_Return, 0, 0)
        window._start_parent_control_save.assert_called_once_with(1001, True, 0)
        self.assertEqual(window._daily_limit_selected, DAILY_LIMIT_PRESETS.index(0))
        self.assertEqual(window._daily_limit.popdown.call_count, 2)

    def test_keyboard_pending_choice_styles_restore_on_escape(self):
        window = self.custom_save_window()
        window._daily_limit_selected = DAILY_LIMIT_PRESETS.index(15)
        pending = DAILY_LIMIT_PRESETS.index(120)
        committed_choice, committed_marker = mock.Mock(), mock.Mock()
        pending_choice, pending_marker = mock.Mock(), mock.Mock()
        window._daily_limit_choices = [
            (committed_choice, committed_marker, window._daily_limit_selected),
            (pending_choice, pending_marker, pending),
        ]
        window._update_daily_limit_choice_styles = (
            ParentWindow._update_daily_limit_choice_styles.__get__(window))
        window._daily_limit_keyboard_index = pending
        window._show_daily_limit_keyboard_choice()
        pending_choice.add_css_class.assert_called_with("selected")
        pending_marker.add_css_class.assert_called_with("selected")
        committed_choice.remove_css_class.assert_called_with("selected")
        window._clear_daily_limit_keyboard()
        committed_choice.add_css_class.assert_called_with("selected")
        pending_choice.remove_css_class.assert_called_with("selected")
        window._start_parent_control_save.assert_not_called()

    def test_keyboard_pending_preset_scrolls_into_view_without_moving_focus(self):
        choice = mock.Mock()
        viewport = mock.Mock()
        window = SimpleNamespace(
            _daily_limit_keyboard_index=DAILY_LIMIT_PRESETS.index(900),
            _daily_limit_choices=[(choice, mock.Mock(), DAILY_LIMIT_PRESETS.index(900))],
            _daily_limit_viewport=viewport,
        )
        viewport.get_mapped.return_value = True
        ParentWindow._scroll_daily_limit_keyboard_choice(window)
        viewport.scroll_to.assert_called_once_with(choice, None)
        choice.grab_focus.assert_not_called()
        viewport.reset_mock()
        window._daily_limit_keyboard_index = CUSTOM_DAILY_LIMIT_INDEX
        ParentWindow._scroll_daily_limit_keyboard_choice(window)
        viewport.scroll_to.assert_not_called()
        window._daily_limit_keyboard_index = DAILY_LIMIT_PRESETS.index(900)
        viewport.get_mapped.return_value = False
        ParentWindow._scroll_daily_limit_keyboard_choice(window)
        viewport.scroll_to.assert_not_called()

    def test_time_explanation_shows_both_amounts_and_remaining_time(self):
        status = {
            "daily_allowance_remaining_seconds": 0,
            "one_time_grant_remaining_seconds": 10 * 60,
            "additional_one_time_grant_seconds": 0,
            "calculated_active_extension_seconds": 10 * 60,
        }
        self.assertEqual(_time_status_subtitle(status), (
            "Daily allowance remaining: <b>0m</b>\nOne-time grant remaining: <b>10m</b>\n"
            "<b>Remaining time: 10m</b> — the larger of the two amounts."
        ))
        status["daily_allowance_remaining_seconds"] = 31 * 60
        status["calculated_active_extension_seconds"] = 31 * 60
        self.assertEqual(_time_status_subtitle(status), (
            "Daily allowance remaining: <b>31m</b>\nOne-time grant remaining: <b>10m</b>\n"
            "<b>Remaining time: 31m</b> — the larger of the two amounts."
        ))

    def test_revoke_confirmation_discloses_that_the_child_is_locked(self):
        source = inspect.getsource(ParentWindow._show_revoke_dialog)

        self.assertIn('m.THIS_WILL_REVOKE_ONE_TIME_SCREEN_TIME_AND_ACCESS_TO_SOFT_BLOCKED', source)
        warning = m.THIS_WILL_REVOKE_ONE_TIME_SCREEN_TIME_AND_ACCESS_TO_SOFT_BLOCKED.source
        self.assertIn("close their running blocked apps", warning)
        self.assertIn("lock their desktop when no time remains", warning)

    def test_language_change_reloads_the_shared_catalogue_and_supersedes_old_load(self):
        window = type("WindowHarness", (), {})()
        window._applied_language = "en"
        window._apps_loading = True
        window._app_catalog = None
        window._selected_uid = lambda: 1001
        window._ensure_apps_load = mock.Mock()
        with mock.patch("parent.oh_no_parent_control_parent.main.context_for") as context:
            self.assertTrue(ParentWindow._apply_language(window, "de"))
            context.return_value.apply.assert_called_once_with("de")
        self.assertFalse(window._apps_loading)
        window._ensure_apps_load.assert_called_once_with(1001)
        window._ensure_apps_load.reset_mock()
        with mock.patch("parent.oh_no_parent_control_parent.main.context_for") as context:
            self.assertTrue(ParentWindow._apply_language(window, "de"))
            context.assert_not_called()
        window._ensure_apps_load.assert_not_called()

    def test_revoke_confirmation_constrains_and_word_wraps_its_warning(self):
        source = inspect.getsource(ParentWindow._show_revoke_dialog)

        self.assertIn("wrap=True, max_width_chars=72", source)
        self.assertIn(
            "warning.set_natural_wrap_mode(Gtk.NaturalWrapMode.WORD)", source,
        )

    def test_running_app_reply_does_not_open_a_dialog_after_parent_closes(self):
        window = type("WindowHarness", (), {"_closed": True})()
        ParentWindow._show_revoke_dialog(window, 1001, ["soft.desktop"])

    def test_revoke_at_zero_time_tracks_running_soft_apps_and_idle_state(self):
        class Label:
            def set_label(self, _label):
                pass

        window = type("WindowHarness", (), {})()
        window._time_status_loading = True
        window._time_status_refresh_pending = False
        window._time_status_retry_id = 0
        window._time_status_retry_count = 0
        window._cancel_time_status_retry = lambda: None
        window._load_pending_time_status_refresh = lambda: None
        window._selected_uid = lambda: 1001
        window._time_status_value = Label()
        window._time_explanation = Label()
        window._preferences = {"daily_time_limit_minutes": 0}
        window._loading = False
        window._account = FakeSensitiveWidget()
        window._revoke = FakeSensitiveWidget()
        window._enabled = FakeSensitiveWidget(active=True)
        window._daily_limit = FakeSensitiveWidget()
        window._apps_group = FakeSensitiveWidget()
        window._set_apps_sensitive = lambda sensitive: ParentWindow._set_apps_sensitive(
            window, sensitive,
        )

        status = {
            "daily_allowance_remaining_seconds": 0,
            "one_time_grant_remaining_seconds": 0,
            "additional_one_time_grant_seconds": 0,
            "calculated_active_extension_seconds": 0,
        }
        ParentWindow._time_status_loaded(window, 1001, status)
        self.assertEqual(window._remaining_time_seconds, 0)
        self.assertFalse(window._revoke.sensitive)
        status["has_running_soft_blocked_apps"] = True
        ParentWindow._time_status_loaded(window, 1001, status)
        self.assertTrue(window._revoke.sensitive)
        for busy_field in ("_loading", "_save_in_progress"):
            setattr(window, busy_field, True)
            window._set_apps_sensitive(True)
            self.assertFalse(window._revoke.sensitive)
            setattr(window, busy_field, False)
        status["has_running_soft_blocked_apps"] = False
        ParentWindow._time_status_loaded(window, 1001, status)
        self.assertFalse(window._revoke.sensitive)
        status["calculated_active_extension_seconds"] = 60
        ParentWindow._time_status_loaded(window, 1001, status)
        self.assertTrue(window._revoke.sensitive)

    def test_transient_time_status_failure_retries_before_showing_unavailable(self):
        class Label:
            def __init__(self, label):
                self.label = label

            def set_label(self, label):
                self.label = label

        window = type("WindowHarness", (), {
            "_retry_time_status": ParentWindow._retry_time_status,
        })()
        window._time_status_loading = True
        window._time_status_refresh_pending = False
        window._time_status_retry_id = 0
        window._time_status_retry_count = 0
        window._selected_uid = lambda: 1001
        window._time_status_value = Label("59 minutes")
        window._time_explanation = Label("One-time grant remaining: 59m.")
        window._load_time_status = mock.Mock()

        with mock.patch(
            "parent.oh_no_parent_control_parent.main.GLib.timeout_add_seconds",
            return_value=73,
        ) as timeout_add:
            ParentWindow._time_status_failed(window, 1001, RuntimeError("busy"))

        self.assertEqual(window._time_status_value.label, "59 minutes")
        self.assertEqual(window._time_status_retry_id, 73)
        retry_callback = timeout_add.call_args.args[1]
        self.assertEqual(retry_callback(), 0)
        window._load_time_status.assert_called_once_with(retry=True)

    def test_time_status_failure_shows_unavailable_after_bounded_retries(self):
        class Label:
            def __init__(self):
                self.label = "value"

            def set_label(self, label):
                self.label = label

        window = type("WindowHarness", (), {})()
        window._time_status_loading = True
        window._time_status_refresh_pending = False
        window._time_status_retry_id = 0
        window._time_status_retry_count = MAX_TIME_STATUS_RETRIES
        window._show_error = mock.Mock()
        window._selected_uid = lambda: 1001
        window._time_status_value = Label()
        window._time_explanation = Label()

        ParentWindow._time_status_failed(window, 1001, RuntimeError("busy"))

        self.assertEqual(window._time_status_value.label, "Unavailable")
        self.assertEqual(window._time_explanation.label, "—")

    def test_overlapping_time_status_refresh_is_coalesced(self):
        window = type("WindowHarness", (), {})()
        window._time_status_loading = True
        window._time_status_refresh_pending = False
        window._selected_uid = lambda: 1001

        ParentWindow._load_time_status(window)

        self.assertTrue(window._time_status_refresh_pending)

    def test_loading_users_loads_initial_selection_once(self):
        window = ParentWindowHarness()

        window._users_loaded([(1001, "Child")])

        self.assertEqual(window.load_count, 1)
        self.assertEqual(window.apps_load_uids, [1001])
        self.assertFalse(window._users_loading)
        self.assertFalse(window._no_users_message.visible)

    def test_account_refresh_adds_user_without_reloading_selected_settings(self):
        window = ParentWindowHarness()
        window._users_loaded([(1001, "Existing child", "")])
        window.load_count = 0
        window.apps_load_uids.clear()

        window._users_loaded([
            (1001, "Existing child", ""), (1002, "New child", ""),
        ])

        self.assertEqual([user[0] for user in window._users], [1001, 1002])
        self.assertEqual(window.selected_index, 0)
        self.assertEqual(window.load_count, 0)
        self.assertEqual(window.apps_load_uids, [])
        self.assertFalse(window._no_users_message.visible)

    def test_unchanged_account_refresh_does_not_rebuild_picker(self):
        window = ParentWindowHarness()
        users = [(1001, "Existing child", "")]
        window._users_loaded(users)
        updates = window.model_updates

        window._users_loading = True
        window._users_loaded(users)

        self.assertEqual(window.model_updates, updates)
        self.assertFalse(window._users_loading)

    def test_account_refresh_moves_selection_when_selected_user_disappears(self):
        window = ParentWindowHarness()
        window._users_loaded([
            (1001, "Existing child", ""), (1002, "Other child", ""),
        ])
        window._users = [(1002, "Other child", ""), (1001, "Existing child", "")]
        window.selected_index = 0
        window.load_count = 0

        window._users_loaded([(1001, "Existing child", "")])

        self.assertEqual(window.selected_index, 0)
        self.assertEqual(window.load_count, 1)
        self.assertEqual(window.apps_load_uids[-1], 1001)

    def test_account_refresh_is_bounded_and_coalesces_overlapping_loads(self):
        window = type("WindowHarness", (), {})()
        window._users_loading = True
        window._client = mock.Mock()
        window._run = mock.Mock()

        self.assertGreater(ACCOUNT_REFRESH_SECONDS, 0)
        self.assertEqual(ParentWindow._load_users(window), 0)
        window._run.assert_not_called()

    def test_loading_no_users_does_not_load_preferences(self):
        window = ParentWindowHarness()

        window._users_loaded([])

        self.assertEqual(window.load_count, 0)
        self.assertEqual(window.apps_load_uids, [])
        self.assertTrue(window._no_users_message.visible)
        self.assertEqual(window.toasts, ["No interactive non-admin users were found"])

    def test_app_settings_stay_enabled_when_daily_limit_is_off(self):
        window = type("WindowHarness", (), {})()
        window._loading = False
        window._selected_uid = lambda: 1001
        window._account = FakeSensitiveWidget()
        window._revoke = FakeSensitiveWidget()
        window._enabled = FakeSensitiveWidget(active=False)
        window._daily_limit = FakeSensitiveWidget()
        window._apps_group = FakeSensitiveWidget()

        ParentWindow._set_apps_sensitive(window, True)

        self.assertTrue(window._apps_group.sensitive)
        self.assertFalse(window._daily_limit.sensitive)

    def test_selecting_an_app_policy_state_starts_an_auto_save(self):
        window = type("WindowHarness", (), {})()
        window._loading = False
        window.save_count = 0
        window._save_app_policy = lambda: setattr(
            window, "save_count", window.save_count + 1,
        )
        window._filter = lambda *_args: None

        ParentWindow._policy_changed(window, FakeToggleButton(active=True))

        self.assertEqual(window.save_count, 1)

    def test_filename_only_match_rule_uses_its_app_executable_directory(self):
        row = type("PolicyRow", (), {})()
        row.app = {"targets": ["/home/child/Applications/Lunar Client.AppImage"]}

        self.assertEqual(
            ParentWindow._canonical_match_rule(row, "*Lunar*Client*"),
            "/home/child/Applications/*Lunar*Client*",
        )

    def test_app_policy_uses_the_current_daily_limit(self):
        class FakePolicyButton:
            def get_active(self):
                return True

        row = type("PolicyRow", (), {})()
        row.app = {"id": "example.desktop", "targets": ["example"]}
        row.policy_buttons = {
            "allowed": FakePolicyButton(),
            "permanent": FakeToggleButton(active=False),
            "conditional": FakeToggleButton(active=False),
        }
        row.user_saved_match_rule = False
        row.match_rule = None
        window = type("WindowHarness", (), {})()
        window._preferences = {
            "daily_time_limit_minutes": 30,
            "apps": {},
        }
        window._daily_limit_minutes = lambda: 60
        window._rows = [row]

        value = ParentWindow._app_policy_value(window)

        self.assertEqual(value["daily_time_limit_minutes"], 60)

    def test_app_policy_preserves_unlisted_launchers(self):
        row = type("PolicyRow", (), {})()
        row.app = {"id": "visible.desktop", "targets": ["/usr/bin/visible"]}
        row.policy_buttons = {
            "allowed": FakeToggleButton(active=True),
            "permanent": FakeToggleButton(active=False),
            "conditional": FakeToggleButton(active=False),
        }
        row.user_saved_match_rule = False
        row.match_rule = None
        window = type("WindowHarness", (), {})()
        window._preferences = {
            "daily_time_limit_minutes": 30,
            "apps": {
                "gone.desktop": {
                    "state": "permanent", "targets": ["/opt/gone.AppImage"],
                },
            },
        }
        window._daily_limit_minutes = lambda: 30
        window._rows = [row]

        value = ParentWindow._app_policy_value(window)

        self.assertEqual(value["apps"], window._preferences["apps"])

    def test_updated_launcher_displays_and_saves_existing_wildcard_policy(self):
        for duplicate_default in (False, True):
            with self.subTest(duplicate_default=duplicate_default):
                self._assert_updated_launcher_policy(duplicate_default)

    def _assert_updated_launcher_policy(self, duplicate_default):
        from types import SimpleNamespace
        from tests.support.objects import plain_accessible_text

        match_images = {match['id']: mock.Mock() for match in MATCH_RULES}

        class Harness:
            _default_match_rule = ParentWindow._default_match_rule
            _is_pattern = staticmethod(ParentWindow._is_pattern)
            _match_rule_image = staticmethod(lambda match: match_images[match['id']])
            _update_match_rule_icon = ParentWindow._update_match_rule_icon

        row = SimpleNamespace(
            app={'id': 'new-lunar.desktop', 'name': 'Lunar Client',
                 'targets': ['/apps/Lunar Client-2.AppImage'],
                 'suggested_patterns': ['/apps/Lunar Client-*.AppImage']},
            policy_buttons={state: mock.Mock() for state in ('allowed', 'conditional', 'permanent')},
            match_rule_button=mock.Mock(),
        )
        for state, button in row.policy_buttons.items():
            button.get_active.return_value = state == 'conditional'
        window = Harness()
        window._preferences = {'daily_time_limit_minutes': 30, 'apps': {
            'old-lunar.desktop': {
                'state': 'conditional', 'targets': ['/apps/Lunar Client-1.AppImage'],
                'patterns': ['/apps/Lunar Client-*.AppImage'],
                'user_saved_match_rule': not duplicate_default,
            },
            'uninstalled.desktop': {'state': 'permanent', 'targets': ['/apps/missing']},
        }}
        if duplicate_default:
            window._preferences['apps']['new-lunar.desktop'] = {
                'state': 'conditional', 'targets': ['/usr/bin/AppImageLauncher'],
                'patterns': [], 'user_saved_match_rule': False,
            }
        window._app_catalog = [row.app]
        window._rows = [row]
        window._loading = False
        window._daily_limit_minutes = lambda: 30

        with mock.patch('parent.oh_no_parent_control_parent.main.set_automation_id') as set_automation_id, \
                mock.patch('common.oh_no_parent_control_ui.accessibility.accessible_text',
                           plain_accessible_text):
            ParentWindow._apply_app_policies(window)

        row.policy_buttons['conditional'].set_active.assert_called_once_with(True)
        row.match_rule_button.set_tooltip_text.assert_called_once_with('Pattern Match')
        row.match_rule_button.set_child.assert_called_once_with(match_images['pattern'])
        from gi.repository import Gtk
        row.match_rule_button.update_property.assert_called_once_with(
            [Gtk.AccessibleProperty.LABEL, Gtk.AccessibleProperty.DESCRIPTION],
            ['Lunar Client match rule', 'Current match rule: /apps/Lunar Client-*.AppImage'],
        )
        set_automation_id.assert_called_once_with(
            match_images['pattern'], 'parent-app-05aaf42b0b4804d4-match-pattern',
        )
        self.assertEqual(row.match_rule, '/apps/Lunar Client-*.AppImage')
        saved = ParentWindow._app_policy_value(window)
        self.assertNotIn('old-lunar.desktop', saved['apps'])
        self.assertIn('uninstalled.desktop', saved['apps'])
        self.assertEqual(saved['apps']['new-lunar.desktop'], {
            'state': 'conditional', 'targets': ['/apps/Lunar Client-2.AppImage'],
            'patterns': ['/apps/Lunar Client-*.AppImage'],
            'user_saved_match_rule': not duplicate_default,
        })
        # Allowing the visible replacement must remove its old saved block too.
        row.user_saved_match_rule = False
        row.policy_buttons['conditional'].get_active.return_value = False
        row.policy_buttons['allowed'].get_active.return_value = True
        allowed = ParentWindow._app_policy_value(window)
        self.assertEqual(set(allowed['apps']), {'uninstalled.desktop'})

    def test_completed_auto_save_does_not_reload_the_widgets(self):
        window = type("WindowHarness", (), {})()
        window._save_in_progress = True
        window._pending_saves = []
        window._selected_uid = lambda: 1001
        window._preferences_loaded = lambda _preferences: self.fail("unexpected reload")
        window._start_next_save = lambda: None
        window._load_policy_warnings = mock.Mock()

        preferences = {"apps": {"example.desktop": {"state": "conditional"}}}
        ParentWindow._save_succeeded(window, 1001, preferences)

        self.assertFalse(window._save_in_progress)
        self.assertEqual(window._preferences, preferences)

    def test_selected_account_loads_apps_independently_of_preferences(self):
        source = inspect.getsource(ParentWindow._load_selected)

        self.assertIn("self._ensure_apps_load(uid)", source)
        self.assertIn("self._client.get_preferences(uid)", source)
        self.assertNotIn("self._client.list_apps(uid)", source)
        self.assertLess(
            source.index("self._ensure_apps_load(uid)"),
            source.index("self._client.get_preferences(uid)"),
        )
        self.assertEqual(CATALOG_ROW_BATCH_SIZE, 8)

    def test_app_catalog_is_cached_until_the_app_limits_tab_is_shown(self):
        window = type("WindowHarness", (), {
            "_apps_loaded": ParentWindow._apps_loaded,
            "_apps_mask_should_show": ParentWindow._apps_mask_should_show,
            "_maybe_populate_app_table": ParentWindow._maybe_populate_app_table,
        })()
        window._apps_load_generation = 1
        window._selected_uid = lambda: 1001
        window._app_limits_visible = False
        window._apps_loading = True
        window._catalog_building = False
        window._apps_table_ready = False
        window._preferences = {"apps": {}}
        window._app_catalog = None
        window.catalog_sets = 0
        window.ui_updates = 0
        window._set_catalog = lambda _apps: setattr(
            window, "catalog_sets", window.catalog_sets + 1,
        )
        window._update_apps_loading_ui = lambda: setattr(
            window, "ui_updates", window.ui_updates + 1,
        )

        ParentWindow._apps_loaded(window, 1001, 1, [{"id": "one.desktop"}])

        self.assertFalse(window._apps_loading)
        self.assertEqual(window._app_catalog[0]["id"], "one.desktop")
        self.assertEqual(window.catalog_sets, 0)
        self.assertFalse(window._apps_mask_should_show())

        window._app_limits_visible = True
        self.assertTrue(window._apps_mask_should_show())
        ParentWindow._maybe_populate_app_table(window)
        self.assertEqual(window.catalog_sets, 1)

    def test_app_limits_tab_keeps_the_table_masked_until_rows_are_ready(self):
        window = type("WindowHarness", (), {
            "_apps_mask_should_show": ParentWindow._apps_mask_should_show,
            "_visible_page_changed": ParentWindow._visible_page_changed,
        })()
        window._pages = type("Pages", (), {
            "get_visible_child_name": lambda self: "app-limits",
        })()
        window._closed = False
        window._loading = False
        window._app_limits_visible = False
        window._apps_loading = True
        window._catalog_building = False
        window._apps_table_ready = False
        window._apps_table_painted = False
        window._apps_paint_wait = None
        window._preferences = None
        window._app_catalog = None
        window._maybe_populate_app_table = lambda: None
        window.mask_visible = None
        window.spinner_spinning = None
        window._apps_loading_mask = type("Mask", (), {
            "set_visible": lambda self, visible: setattr(window, "mask_visible", visible),
        })()
        window._apps_loading_spinner = type("Spinner", (), {
            "set_spinning": lambda self, spinning: setattr(
                window, "spinner_spinning", spinning,
            ),
        })()
        window._update_apps_loading_ui = lambda: ParentWindow._update_apps_loading_ui(
            window,
        )

        with mock.patch(
            "parent.oh_no_parent_control_parent.main.GLib.idle_add",
        ) as idle_add:
            ParentWindow._visible_page_changed(window)

        self.assertTrue(window._app_limits_visible)
        self.assertTrue(window._apps_mask_should_show())
        self.assertTrue(window.mask_visible)
        self.assertTrue(window.spinner_spinning)
        idle_add.assert_called_once_with(window._maybe_populate_app_table)

        window._apps_loading = False
        window._app_catalog = []
        window._catalog_building = False
        window._apps_table_ready = True
        window._apps_table_painted = True
        window._preferences = {"apps": {}}
        window._update_apps_loading_ui()
        self.assertFalse(window._apps_mask_should_show())
        self.assertFalse(window.mask_visible)
        self.assertFalse(window.spinner_spinning)

    def catalog_paint_window(self, applications, *, preferences=True, mapped=True):
        window = type("CatalogPaintHarness", (), {
            name: getattr(ParentWindow, name) for name in (
                "_append_catalog_batch", "_apps_mask_should_show",
                "_update_apps_loading_ui", "_cancel_apps_paint",
            )
        })()
        window._closed = False
        window._loading = False
        window._app_limits_visible = True
        window._apps_loading = False
        window._apps_table_ready = False
        window._apps_table_painted = False
        window._apps_paint_wait = None
        window._catalog_building = True
        window._catalog_build_generation = window._apps_load_generation = 1
        window._pending_catalog_apps = applications.copy()
        window._preferences = {"apps": {}} if preferences else None
        window._rows = []
        window._search = mock.Mock()
        window._add_app_row = window._rows.append
        window._apply_app_policies = mock.Mock()
        window._filter = mock.Mock()
        window._set_apps_sensitive = mock.Mock()
        window._apps_loading_mask = mock.Mock()
        window._apps_loading_spinner = mock.Mock()
        window._apps_loading_progress = mock.Mock()
        window._apps_group = mock.Mock()
        window._apps_group.get_mapped.return_value = mapped
        return window

    def test_complete_catalog_stays_masked_through_its_first_paint(self):
        for count in (0, CATALOG_ROW_BATCH_SIZE + 1):
            with self.subTest(count=count):
                apps = [{"id": f"app-{index}.desktop"} for index in range(count)]
                window = self.catalog_paint_window(apps)
                clock = window._apps_group.get_frame_clock.return_value
                window._apps_loading = True
                window._update_apps_loading_ui()
                window._apps_loading_progress.set_visible.assert_called_with(False)
                window._apps_loading = False
                window._update_apps_loading_ui()
                window._apps_loading_progress.set_label.assert_called_with(
                    "0%" if apps else "100%")
                while window._pending_catalog_apps:
                    window._append_catalog_batch()
                    if window._pending_catalog_apps:
                        clock.connect.assert_not_called()
                        window._apps_loading_progress.set_visible.assert_called_with(True)
                        window._apps_loading_progress.set_label.assert_called_with("88%")
                if not apps:
                    window._append_catalog_batch()
                self.assertEqual(window._rows, apps)
                window._apply_app_policies.assert_called_once_with()
                window._filter.assert_called_once_with(window._search)
                window._set_apps_sensitive.assert_called_once_with(True)
                self.assertTrue(window._apps_table_ready)
                window._apps_loading_progress.set_label.assert_called_with("100%")
                self.assertTrue(window._apps_mask_should_show())
                window._apps_loading_mask.set_visible.assert_called_with(True)
                # Repeated readiness updates must share one frame callback.
                window._update_apps_loading_ui()
                clock.connect.assert_called_once()
                signal, painted = clock.connect.call_args.args
                self.assertEqual(signal, "after-paint")
                painted(clock)
                clock.disconnect.assert_called_once_with(clock.connect.return_value)
                self.assertIsNone(window._apps_paint_wait)
                self.assertTrue(window._apps_table_painted)
                self.assertFalse(window._apps_mask_should_show())
                window._apps_loading_mask.set_visible.assert_called_with(False)
                window._apps_loading_spinner.set_spinning.assert_called_with(False)
                window._apps_loading_progress.set_visible.assert_called_with(False)

    def test_catalog_paint_waits_for_preferences_and_mapping(self):
        window = self.catalog_paint_window([], preferences=False, mapped=False)
        window._append_catalog_batch()
        window._apps_group.get_frame_clock.assert_not_called()
        self.assertTrue(window._apps_mask_should_show())
        window._preferences = {"apps": {}}
        # A previous child's preferences do not finish the current load.
        window._loading = True
        window._apps_group.get_mapped.return_value = True
        window._update_apps_loading_ui()
        window._apps_group.get_frame_clock.assert_not_called()
        window._loading = False
        window._apps_group.get_mapped.return_value = False
        window._update_apps_loading_ui()
        window._apps_group.get_frame_clock.assert_not_called()
        window._apps_group.get_mapped.return_value = True
        window._update_apps_loading_ui()
        clock = window._apps_group.get_frame_clock.return_value
        clock.connect.call_args.args[1](clock)
        self.assertFalse(window._apps_mask_should_show())

    def test_catalog_paint_cannot_reveal_a_stale_hidden_or_closed_table(self):
        for field, value in (("_apps_load_generation", 2),
                             ("_app_limits_visible", False), ("_closed", True)):
            with self.subTest(field=field):
                window = self.catalog_paint_window([])
                window._append_catalog_batch()
                clock = window._apps_group.get_frame_clock.return_value
                setattr(window, field, value)
                clock.connect.call_args.args[1](clock)
                self.assertFalse(window._apps_table_painted)
                self.assertIsNone(window._apps_paint_wait)

    def test_cancel_catalog_paint_disconnects_only_its_owned_handler(self):
        window = self.catalog_paint_window([])
        window._append_catalog_batch()
        clock = window._apps_group.get_frame_clock.return_value
        window._cancel_apps_paint()
        window._cancel_apps_paint()
        clock.disconnect.assert_called_once_with(clock.connect.return_value)
        self.assertIsNone(window._apps_paint_wait)
        self.assertFalse(window._apps_table_painted)

    def test_stale_app_catalog_results_are_ignored_after_account_change(self):
        window = type("WindowHarness", (), {
            "_apps_loaded": ParentWindow._apps_loaded,
            "_apps_failed": ParentWindow._apps_failed,
        })()
        window._apps_load_generation = 2
        window._selected_uid = lambda: 1002
        window._apps_loading = True
        window._app_catalog = None
        window._update_apps_loading_ui = lambda: None
        window._maybe_populate_app_table = lambda: None

        ParentWindow._apps_loaded(window, 1001, 1, [{"id": "stale.desktop"}])
        ParentWindow._apps_failed(window, 1001, 1, RuntimeError("gone"))

        self.assertTrue(window._apps_loading)
        self.assertIsNone(window._app_catalog)


if __name__ == "__main__":
    unittest.main()
