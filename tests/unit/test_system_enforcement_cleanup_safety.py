"""No native launch before guest/credential checks; reuse owned command cleanup."""

from unittest.mock import Mock

import pytest

from test_system_enforcement import enforcement


@pytest.mark.parametrize('boundary', ['guard', 'identity'])
def test_refused_boundary_prevents_exec(monkeypatch, capsys, boundary):
    guard, identity, execute = Mock(), Mock(), Mock()
    (guard if boundary == 'guard' else identity).side_effect = enforcement.guest.GuestError('refused')
    monkeypatch.setattr(enforcement.guest, 'guard', guard)
    monkeypatch.setattr(enforcement, 'drop_identity', identity)
    monkeypatch.setattr(enforcement.os, 'execv', execute)
    with pytest.raises(enforcement.guest.GuestError, match='refused'):
        enforcement.launch_as(1001)
    execute.assert_not_called()
    assert capsys.readouterr().out == ''
    if boundary == 'guard':
        identity.assert_not_called()


def test_success_replaces_same_process_with_one_shot_target(monkeypatch, capsys):
    class Replaced(BaseException):
        pass

    events = []
    monkeypatch.setattr(enforcement.guest, 'guard', lambda: events.append('guard'))
    monkeypatch.setattr(enforcement, 'drop_identity', lambda uid: events.append(('identity', uid)))

    def execute(path, args):
        events.append(('exec', path, args))
        raise Replaced()

    monkeypatch.setattr(enforcement.os, 'execv', execute)
    with pytest.raises(Replaced):
        enforcement.launch_as(1001)
    assert events == ['guard', ('identity', 1001),
                      ('exec', str(enforcement.TARGET), [str(enforcement.TARGET)])]
    assert capsys.readouterr().out.encode() == enforcement.IDENTITY


def test_guest_refusal_prevents_fixture_files(monkeypatch, tmp_path):
    monkeypatch.setattr(enforcement, 'TARGET', tmp_path / 'native/fixture')
    monkeypatch.setattr(enforcement, 'DESKTOP', tmp_path / 'fixture.desktop')
    monkeypatch.setattr(enforcement.guest, 'guard', Mock(side_effect=enforcement.guest.GuestError('refused')))
    with pytest.raises(enforcement.guest.GuestError, match='refused'):
        enforcement.provision_native()
    assert list(tmp_path.iterdir()) == []
