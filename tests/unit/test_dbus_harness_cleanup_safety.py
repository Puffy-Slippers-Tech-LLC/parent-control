"""Private-bus setup failures release only resources the harness acquired."""

from unittest.mock import Mock

import pytest
from tests.support import dbus


@pytest.mark.parametrize('failure', ['name', 'constructor', 'register', 'client', 'body', 'cleanup'])
def test_partial_setup_and_cleanup_close_every_acquired_resource(tmp_path, monkeypatch, failure):
    server = Mock(is_closed=Mock(return_value=False))
    client = Mock(is_closed=Mock(return_value=False))
    service = Mock()
    error = RuntimeError('fixture failure')
    opening = Mock(side_effect=[server, error if failure == 'client' else client])
    request_name = Mock(side_effect=error if failure == 'name' else None)
    release_name = Mock()
    factory = Mock(side_effect=error if failure == 'constructor' else None, return_value=service)
    monkeypatch.setattr(dbus, 'open_bus', opening)
    monkeypatch.setattr(dbus, 'request_name', request_name)
    monkeypatch.setattr(dbus, 'release_name', release_name)
    monkeypatch.setattr(dbus, 'Service', factory)
    if failure == 'register':
        service.register.side_effect = error
    if failure == 'cleanup':
        client.close_sync.side_effect = error
    with pytest.raises(RuntimeError, match='fixture failure'):
        with dbus.broker_service(Mock(address='private'), Mock(), tmp_path):
            if failure == 'body':
                raise error
    server.close_sync.assert_called_once_with(None)
    assert release_name.call_count == (failure != 'name')
    assert service.close.call_count == (failure not in {'name', 'constructor'})
    assert client.close_sync.call_count == (failure in {'body', 'cleanup'})
