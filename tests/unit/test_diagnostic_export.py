"""Diagnostic access is role-checked, bounded and independent of UI permissions."""

from io import BytesIO
import threading
from types import SimpleNamespace
from unittest.mock import Mock
from zipfile import ZipFile

import pytest
from gi.repository import Gio, GLib

from common.oh_no_parent_control_ui import diagnostics as client
from oh_no_parent_control import service
from oh_no_parent_control.core import AccessDenied
from tests.support.broker import Accounts, make_broker


@pytest.mark.parametrize("uid", (0, 991, 1001, 1002, 1003))
def test_product_roles_can_export_all_component_logs(uid):
    make_broker().authorize_diagnostic_export(uid)


@pytest.mark.parametrize("uid", (999, 1004, 1005, 12345))
def test_unrelated_callers_cannot_export(uid):
    with pytest.raises(AccessDenied):
        make_broker().authorize_diagnostic_export(uid)


def test_ui_gets_archive_bytes_via_fixed_broker_method(monkeypatch):
    data = b"PK\x03\x04\x00\xff\x80archive bytes"
    connection = Mock(call_sync=Mock(return_value=GLib.Variant("(ay)", (data,))))
    monkeypatch.setattr(Gio, "bus_get_sync", lambda *_: connection)
    assert client.collect_logs() == data
    assert connection.call_sync.call_args.args[:5] == (
        client.BUS_NAME, client.OBJECT_PATH, client.BUS_NAME, "ExportDiagnosticLogs", None,
    )


def test_ui_preserves_existing_collection_error_contract(monkeypatch):
    error = Gio.DBusError.new_for_dbus_error("org.freedesktop.DBus.Error.AccessDenied", "private")
    monkeypatch.setattr(Gio, "bus_get_sync", Mock(side_effect=error))
    with pytest.raises(OSError, match="Diagnostic export unavailable"):
        client.collect_logs()


def test_broker_worker_exports_all_four_components_and_releases_lock(tmp_path, monkeypatch):
    for component in ("broker", "parent", "child", "kiosk"):
        directory = tmp_path / component
        directory.mkdir()
        (directory / "2026-09-09.log").write_text(component)
    instance = SimpleNamespace(
        broker=make_broker(), log_writer=SimpleNamespace(root=tmp_path),
        _diagnostic_export_lock=threading.Lock(),
    )
    instance._export_logs_done = lambda *args: service.Service._export_logs_done(instance, *args)
    instance._diagnostic_export_lock.acquire()
    invocation = Mock()
    monkeypatch.setattr(GLib, "idle_add", lambda callback, *args: callback(*args))
    service.Service._export_logs_worker(instance, invocation, 991)
    response = invocation.return_value.call_args.args[0]
    with ZipFile(BytesIO(bytes(response.unpack()[0]))) as archive:
        assert set(archive.namelist()) == {
            f"{component}/2026-09-09.log" for component in ("broker", "parent", "child", "kiosk")
        }
    assert not instance._diagnostic_export_lock.locked()


def test_export_rechecks_role_before_delivery():
    accounts = Accounts()
    broker = make_broker(accounts=accounts)
    broker.authorize_diagnostic_export(1001)
    del accounts.users[1001]
    instance = SimpleNamespace(broker=broker, _diagnostic_export_lock=threading.Lock())
    instance._diagnostic_export_lock.acquire()
    invocation = Mock()
    service.Service._export_logs_done(instance, invocation, 1001, b"archive")
    invocation.return_value.assert_not_called()
    assert invocation.return_dbus_error.call_args.args[0] == AccessDenied.dbus_name
    assert not instance._diagnostic_export_lock.locked()


def test_busy_export_refuses_another_worker():
    instance = SimpleNamespace(
        broker=make_broker(), credentials=SimpleNamespace(uid=lambda _: 991),
        _diagnostic_export_lock=threading.Lock(), _export_logs_worker=Mock(),
    )
    instance._diagnostic_export_lock.acquire()
    invocation = Mock()
    service.Service._method_call(instance, None, ":1.2", None, None,
                                "ExportDiagnosticLogs", None, invocation)
    assert invocation.return_dbus_error.call_args.args[0].endswith(".Busy")
    instance._export_logs_worker.assert_not_called()
