import json
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from oh_no_parent_control_kiosk.selection_store import SelectionStore
from oh_no_parent_control_kiosk.request_content import RequestContent
from oh_no_parent_control_kiosk.main import RequestWindow
from oh_no_parent_control_kiosk.model import RequestState
from common.oh_no_parent_control_ui.diagnostic_events import decode
from oh_no_parent_control.logs import DailyLogWriter
from tests.support.objects import bind_methods


@pytest.mark.parametrize('presets, expected', [
    ([14400, 300], 18000), ([82860], 82920), ([86350], 86350),
    ([86400], 86400), ([], 1800),
])
def test_new_preset_suggestion_uses_largest_and_bounded_fallback(presets, expected):
    from oh_no_parent_control_kiosk.preset_dialog import suggested_preset_seconds

    assert suggested_preset_seconds(presets) == expected


@pytest.mark.parametrize('text, expected', [
    ('1.25', '1.3'), ('0.09', '0.1'), ('24', '24.0'), ('6.', '6.0'),
    ('0.04', '0.0'), ('NaN', None), ('6e1000000', None),
])
def test_preset_fraction_rounding_uses_one_decimal_half_up(text, expected):
    from oh_no_parent_control_kiosk.preset_dialog import rounded_preset_value

    value = rounded_preset_value(text)
    assert (None if value is None else str(value)) == expected


@pytest.mark.parametrize('text, expected', [
    ('6.', '6'), ('6.0', '6.0'), ('.5', '0.5'), (' 6. ', '6'),
    ('', None), ('.', None), ('6..', None), ('NaN', None), ('Infinity', None),
    ('6e3', None), ('-1', None), ('６', None),
])
def test_duration_editors_share_decimal_syntax(text, expected):
    from oh_no_parent_control_kiosk.duration_controls import duration_number

    value = duration_number(text)
    assert (None if value is None else str(value)) == expected


@pytest.mark.parametrize('seconds, unit, display', [
    (7, 'minute', '0.1166666667'), (86350, 'minute', '1439.1666666667'),
    (18000, 'hour', '5'), (6, 'minute', '0.1'),
])
def test_backend_preset_initial_value_retains_whole_second_precision(seconds, unit, display):
    from oh_no_parent_control_kiosk.preset_dialog import PresetDialog, preset_display_value

    assert preset_display_value(seconds, unit) == display
    editor = SimpleNamespace(_initial_seconds=seconds)
    assert PresetDialog._seconds(editor) == seconds


def form_methods():
    """Exercise selector orchestration without constructing GTK or a desktop."""
    names = {"set_accounts", "_account_changed", "_approver_changed",
             "selected_approver_uid", "_restore_approver"}
    return bind_methods(SimpleNamespace(), RequestContent, names)


class Selector:
    def __init__(self, changed):
        self.index = 2**32 - 1
        self.changed = changed

    def set_items(self, _items, *, identities=()):
        self.index = 2**32 - 1

    def set_selected(self, index):
        self.index = index
        self.changed()

    def get_selected(self):
        return self.index

    def collapse(self):
        pass


@pytest.mark.parametrize("overlay", [False, True])
def test_form_restores_local_choices_and_keeps_child_identity(tmp_path, overlay):
    path = tmp_path / "selections.json"
    saved = SelectionStore(path)
    saved.remember("child_uid", 1002)
    saved.remember("approver_uid", 1004)
    form = form_methods()
    form._selection_store = SelectionStore(path, child_overlay=overlay)
    form._lock_child_selector = overlay
    form._update_ready = lambda: None
    loaded = []
    form._on_account_selected = loaded.append
    form._accounts = Selector(form._account_changed)
    users = [(1001, "Child", "")] if overlay else [(1003, "Child", ""), (1002, "Child", "")]
    form.set_accounts(users)
    assert loaded == [1001 if overlay else 1002]
    assert SelectionStore(path).preferred("child_uid") == 1002
    form._approvers_loaded = True
    form._approver_uids = [1005, 1004]
    form._pending_approver_uid = 1005
    form._emit_values_changed = lambda: None
    form._approvers = Selector(form._approver_changed)
    form._restore_approver()
    assert form.selected_approver_uid() == 1004
    form._approvers.set_selected(0)
    # A delayed broker preference must not undo a more recent local choice.
    form._pending_approver_uid = 1004
    form._restore_approver()
    assert form.selected_approver_uid() == 1005
    assert SelectionStore(path).preferred("approver_uid") == 1005
    form._approver_uids = [1006]
    form._approvers.set_items([])
    form._restore_approver()
    assert form.selected_approver_uid() == 1006


def test_kiosk_selections_survive_reopening(tmp_path):
    path = tmp_path / "state" / "selections.json"
    store = SelectionStore(path)
    store.remember("child_uid", 1002)
    store.remember("approver_uid", 1003)
    reopened = SelectionStore(path)
    assert reopened.preferred("child_uid") == 1002
    assert reopened.preferred("approver_uid") == 1003
    assert path.stat().st_mode & 0o777 == 0o600


def test_child_ignores_and_does_not_overwrite_kiosk_child(tmp_path):
    path = tmp_path / "selections.json"
    SelectionStore(path).remember("child_uid", 1002)
    child = SelectionStore(path, child_overlay=True)
    assert child.preferred("child_uid") == 0
    child.remember("child_uid", 1004)
    child.remember("approver_uid", 1003)
    reopened = SelectionStore(path, child_overlay=True)
    assert reopened.preferred("approver_uid") == 1003
    assert SelectionStore(path).preferred("child_uid") == 1002


@pytest.mark.parametrize("contents", ['{', '[]', '{"child_uid": true, "approver_uid": "1003"}'])
def test_invalid_local_state_falls_back(tmp_path, contents):
    path = tmp_path / "selections.json"
    path.write_text(contents)
    store = SelectionStore(path)
    assert store.preferred("child_uid") == 0
    assert store.preferred("approver_uid") == 0
    store.remember("approver_uid", 1003)
    assert json.loads(path.read_text())["approver_uid"] == 1003


def test_unwritable_state_is_nonfatal_and_logs_no_identity(tmp_path, caplog):
    path = tmp_path / "file"
    path.write_text("occupied")
    store = SelectionStore(path / "selections.json")
    store.remember("approver_uid", 1234567)
    assert "could not be saved" in caplog.text
    assert "1234567" not in caplog.text
    assert str(path) not in caplog.text


def diagnostic_window(overlay):
    return bind_methods(SimpleNamespace(
        _preview=False, _child_overlay=overlay, _applying_preferences=False,
        _request_content=Mock(), _state=RequestState(), _bus_call=Mock(),
        _queue_time_estimate=Mock(), _apply_mute=Mock(), _mute_surface=lambda: "kiosk",
        _show_error=Mock(), _set_request_controls=Mock(), _request_failed=Mock(),
        _preferences_save_done=Mock(), _preferences_saved=Mock(), _errors=Mock(),
    ), RequestWindow, (
        "_log_duration_selection", "_preferences_done", "_persist_form_values",
        "_request_access",
    ))


@pytest.mark.parametrize("overlay", (False, True))
def test_request_diagnostics_trace_restoration_edits_and_submission_without_identity(
        caplog, overlay):
    caplog.set_level("INFO")
    window = diagnostic_window(overlay)
    form = window._request_content
    secret = "private name /home/private private@example.test"
    form.selected.return_value = (1234567, secret, 7654321, 1800, False)
    form.selected_preferences.return_value = ("1800", 45.0, False)
    connection = SimpleNamespace(call_finish=lambda _: SimpleNamespace(unpack=lambda: ("{}",)))
    window._preferences_done(1234567, connection, object())
    form.selected.return_value = (1234567, secret, 7654321, 2700, False)
    form.selected_preferences.return_value = ("custom", 45.0, False)
    window._persist_form_values()
    window._request_access()
    payloads = [decode(record.onpc_payload) for record in caplog.records]
    selections = [item for item in payloads if item["event"] == "kiosk.duration-selection"]
    assert [item["fields"] for item in selections] == [
        {"stage": "restored", "kind": "preset", "duration_seconds": 1800, "overlay": overlay},
        {"stage": "edited", "kind": "custom", "duration_seconds": 2700, "overlay": overlay},
        {"stage": "submitted", "kind": "custom", "duration_seconds": 2700, "overlay": overlay},
    ]
    # The recorded submission must match the duration frozen for authentication.
    assert window._pending_request == (1234567, 7654321, 2700, False)
    for private in (secret, "1234567", "7654321"):
        assert private not in caplog.text
        assert private not in repr(payloads)
    window._show_error.assert_not_called()
    window._request_failed.assert_not_called()


def test_rapid_duration_reversions_survive_log_suppression(tmp_path, caplog):
    caplog.set_level("INFO")
    window = diagnostic_window(False)
    for seconds in (1800, 2700, 1800):
        window._request_content.selected.return_value = (1001, "Child", 1000, seconds, False)
        window._request_content.selected_preferences.return_value = ("custom", seconds / 60, False)
        window._log_duration_selection("edited")
    writer = DailyLogWriter(tmp_path, monotonic=lambda: 0)
    for record in caplog.records:
        writer.write("kiosk", "INFO", record.onpc_payload)
    saved = [json.loads(line) for path in (tmp_path / "kiosk").glob("*.events")
             for line in path.read_text().splitlines()]
    assert [item["fields"]["duration_seconds"] for item in saved] == [1800, 2700, 1800]
    assert writer.summary()["suppressed"] == 0


def test_duration_diagnostics_do_not_log_invalid_text_or_obsolete_preferences(caplog):
    caplog.set_level("INFO")
    window = diagnostic_window(False)
    window._request_content.selected.side_effect = ValueError("private custom text")
    window._log_duration_selection("edited")
    assert not caplog.records
    window._request_content.is_selected_account.return_value = False
    connection = SimpleNamespace(call_finish=lambda _: SimpleNamespace(unpack=lambda: ("{}",)))
    window._preferences_done(1001, connection, object())
    window._request_content.set_preferences.assert_not_called()
    assert not caplog.records


def test_rest_of_day_selection_is_not_reported_as_zero_length_fixed_grant(caplog):
    caplog.set_level("INFO")
    window = diagnostic_window(False)
    window._request_content.selected.return_value = (1001, "Child", 1000, 0, False)
    window._request_content.selected_preferences.return_value = ("0", 45.0, False)
    window._log_duration_selection("submitted")
    assert decode(caplog.records[-1].onpc_payload)["fields"]["kind"] == "rest-of-day"
