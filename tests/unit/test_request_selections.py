import json
import ast
from pathlib import Path
from types import SimpleNamespace

import pytest

from oh_no_parent_control_kiosk.selection_store import SelectionStore


def form_methods():
    """Exercise selector orchestration without constructing GTK or a desktop."""
    source = Path(__file__).resolve().parents[2] / "kiosk/oh_no_parent_control_kiosk/request_content.py"
    tree = ast.parse(source.read_text())
    cls = next(node for node in tree.body if isinstance(node, ast.ClassDef)
               and node.name == "RequestContent")
    names = {"set_accounts", "_account_changed", "_approver_changed",
             "selected_approver_uid", "_restore_approver"}
    cls.bases = []
    cls.body = [node for node in cls.body if isinstance(node, ast.FunctionDef)
                and node.name in names]
    namespace = {"Gtk": SimpleNamespace(INVALID_LIST_POSITION=2**32 - 1),
                 "parse_listed_user": lambda user: user}
    exec(compile(ast.Module(body=[cls], type_ignores=[]), str(source), "exec"), namespace)
    return namespace["RequestContent"]()


class Selector:
    def __init__(self, changed):
        self.index = 2**32 - 1
        self.changed = changed

    def set_items(self, _items):
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
