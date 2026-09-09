"""Runtime startup ordering on the established, independently owned private bus."""

import json
import time

import pytest
from gi.repository import Gio, GLib

from oh_no_parent_control.logs import DailyLogWriter
from oh_no_parent_control.service import Service
from tests.support.dbus import (
    RecordingAccounts, RecordingBroker, broker_service, call, close_connection, open_bus,
)


@pytest.mark.parametrize('fault', [None, 'policy', 'extensions', 'caps', 'registration', 'log'])
def test_startup_witness_tracks_real_publication_and_required_failures(
        dbusmock_system, dbusmock_session, tmp_path, monkeypatch, caplog, fault):
    monkeypatch.setenv('INVOCATION_ID', 'a' * 32)
    client = open_bus(dbusmock_system.address)
    intervals = {}
    original_register = Service.register

    def unpublished():
        with pytest.raises(GLib.Error) as caught:
            call(client, 'ListManagedUsers', None, '(a(uss))')
        assert Gio.dbus_error_get_remote_error(caught.value) == (
            'org.freedesktop.DBus.Error.UnknownMethod')

    def phase(name, result):
        def run(_self):
            start = time.monotonic_ns()
            unpublished()
            intervals[name] = (start, time.monotonic_ns())
            if fault == name:
                raise RuntimeError('private-startup-canary')
            return result
        return run

    def register(service):
        unpublished()
        intervals['registration'] = (time.monotonic_ns(),)
        original_register(service)
        intervals['registration'] += (time.monotonic_ns(),)

    monkeypatch.setattr(RecordingAccounts, 'sync_execution_policy', phase('policy', None))
    monkeypatch.setattr(RecordingBroker, 'refresh_enabled_extensions', phase('extensions', ()))
    monkeypatch.setattr(RecordingBroker, 'clear_live_session_runtime_caps', phase('caps', ()))
    monkeypatch.setattr(Service, 'register', register)
    if fault == 'registration':
        monkeypatch.setattr(Gio.DBusConnection, 'register_object_with_closures2',
                            lambda *_args: 0)
    if fault == 'log':
        def fail_write(*_args, **_kwargs):
            raise OSError('private-startup-canary')
        monkeypatch.setattr(DailyLogWriter, 'write', fail_write)
    try:
        if fault in ('policy', 'extensions', 'registration'):
            with pytest.raises(RuntimeError):
                with broker_service(dbusmock_system, dbusmock_session, tmp_path):
                    pytest.fail('failed startup became ready')
            assert not list((tmp_path / 'logs' / 'broker').iterdir())
            assert set(intervals) == {
                'policy': {'policy'}, 'extensions': {'policy', 'extensions'},
                'registration': {'policy', 'extensions', 'caps', 'registration'},
            }[fault]
        else:
            with broker_service(dbusmock_system, dbusmock_session, tmp_path) as harness:
                assert call(client, 'ListManagedUsers', None, '(a(uss))').unpack()[0]
                files = list((harness.writer.root / 'broker').iterdir())
                if fault == 'log':
                    assert not files
                    assert 'startup witness unavailable error_type=OSError' in caplog.text
                else:
                    assert len(files) == 1
                    line = files[0].read_text().splitlines()
                    assert len(line) == 1
                    witness = json.loads(line[0].split(' INFO startup-witness ', 1)[1])
                    assert witness['invocation_id'] == 'a' * 32
                    assert witness['bus_owner'] == harness.server.get_unique_name()
                    assert witness['pid'] > 0
                    times = [witness[key] for key in (
                        'started_ns', 'policy_ready_ns', 'extensions_ready_ns',
                        'caps_attempted_ns', 'register_started_ns', 'register_finished_ns')]
                    assert times == sorted(times)
                    assert times[0] <= intervals['policy'][0]
                    for name, index in (('policy', 1), ('extensions', 2), ('caps', 3)):
                        assert intervals[name][1] <= times[index]
                    assert intervals['registration'][0] <= times[4] <= times[5]
                    assert times[5] <= intervals['registration'][1]
                    assert 'private-startup-canary' not in line[0]
            if fault == 'caps':
                assert 'runtime caps error_type=RuntimeError' in caplog.text
            assert 'private-startup-canary' not in caplog.text
    finally:
        close_connection(client)


@pytest.mark.parametrize('invocation', ['', 'private-startup-canary'])
def test_startup_does_not_log_invalid_invocation_or_require_systemd(
        dbusmock_system, dbusmock_session, tmp_path, monkeypatch, invocation):
    monkeypatch.setenv('INVOCATION_ID', invocation)
    with broker_service(dbusmock_system, dbusmock_session, tmp_path) as harness:
        line = next((harness.writer.root / 'broker').iterdir()).read_text()
        witness = json.loads(line.split(' INFO startup-witness ', 1)[1])
        assert witness['invocation_id'] == ''
        assert 'private-startup-canary' not in line
