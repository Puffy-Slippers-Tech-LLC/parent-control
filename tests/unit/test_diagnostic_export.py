"""Diagnostic access is role-checked, bounded and independent of UI permissions."""

from io import BytesIO
import threading
from types import SimpleNamespace
from unittest.mock import Mock
from zipfile import ZipFile

import pytest
from gi.repository import Gio, GLib

from common.oh_no_parent_control_ui import diagnostics as client
from common.oh_no_parent_control_ui.diagnostic_bundle import build_bundle, with_system_info
from common.oh_no_parent_control_ui.diagnostic_report import read_report
from tests.support.system_info import sample_info
from common.oh_no_parent_control_ui.diagnostic_events import encode, event
from oh_no_parent_control import service
from oh_no_parent_control.logs import DailyLogWriter
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
    data = build_bundle([])
    connection = Mock(call_sync=Mock(return_value=GLib.Variant("(ay)", (data,))))
    monkeypatch.setattr(Gio, "bus_get_sync", lambda *_: connection)
    monkeypatch.setattr(client, "collect_system_info", lambda bus: sample_info())
    assert client.collect_logs() == with_system_info(data, sample_info())
    assert connection.call_sync.call_args.args[:5] == (
        client.BUS_NAME, client.OBJECT_PATH, client.BUS_NAME, "ExportDiagnosticLogs", None,
    )


def test_ui_preserves_existing_collection_error_contract(monkeypatch):
    error = Gio.DBusError.new_for_dbus_error("org.freedesktop.DBus.Error.AccessDenied", "private")
    monkeypatch.setattr(Gio, "bus_get_sync", Mock(side_effect=error))
    with pytest.raises(OSError, match="Diagnostic export unavailable"):
        client.collect_logs()


def test_broker_worker_exports_all_four_components_and_releases_lock(tmp_path, monkeypatch):
    writer = DailyLogWriter(tmp_path)
    for component in ("broker", "parent", "child", "kiosk"):
        writer.write(component, "INFO", encode(event("diagnostic.rejected")))
    instance = SimpleNamespace(
        broker=make_broker(), log_writer=writer, _health_snapshot=lambda: {},
        _diagnostic_export_lock=threading.Lock(),
    )
    instance._export_logs_done = lambda *args: service.Service._export_logs_done(instance, *args)
    instance._diagnostic_export_lock.acquire()
    invocation = Mock()
    monkeypatch.setattr(GLib, "idle_add", lambda callback, *args: callback(*args))
    service.Service._export_logs_worker(instance, invocation, 991)
    response = invocation.return_value.call_args.args[0]
    with ZipFile(BytesIO(bytes(response.unpack()[0]))) as archive:
        logs, _ = read_report(archive)
        records = [record for rows in logs.values() for record in rows]
        assert {record["component"] for record in records} == {"broker", "parent", "child", "kiosk"}
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


def test_health_snapshot_reports_only_closed_states(tmp_path, monkeypatch, caplog):
    writer = DailyLogWriter(tmp_path)
    writer.write_failed()
    connection = Mock(call_sync=Mock(side_effect=[
        GLib.Variant("(b)", (True,)), GLib.Variant("(b)", (False,)),
        OSError("private host and path"), GLib.Variant("(b)", (True,)),
    ]))
    monkeypatch.setattr(service, "Path", lambda _: SimpleNamespace(exists=lambda: True))
    instance = SimpleNamespace(connection=connection, log_writer=writer)
    with caplog.at_level("INFO"):
        health = service.Service._health_snapshot(instance)
    assert health == {"accounts": "available", "timer": "inactive", "polkit": "unknown",
                      "systemd": "available", "migration": "incomplete", "storage": "unavailable"}
    assert "private" not in caplog.text
    assert all(call.args[6] == Gio.DBusCallFlags.NONE and call.args[7] == 1000
               for call in connection.call_sync.call_args_list)


def test_grant_signal_bursts_use_one_worker(monkeypatch):
    threads = []
    instance = SimpleNamespace(_grant_observation_lock=threading.Lock(), _observe_grants=Mock())
    instance._grant_observation_worker = lambda: service.Service._grant_observation_worker(instance)
    monkeypatch.setattr(service.threading, "Thread", lambda **kwargs: threads.append(kwargs) or Mock())
    for _ in range(50):
        service.Service._grant_changed(instance)
    assert len(threads) == 1
    threads[0]["target"]()
    instance._observe_grants.assert_called_once()
    assert not instance._grant_observation_lock.locked()
