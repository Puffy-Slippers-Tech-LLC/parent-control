"""User-manager cleanup refuses processes outside its owned invocation."""

from types import SimpleNamespace
from unittest.mock import Mock

import pytest

import system_kiosk_scope as scope


@pytest.mark.parametrize('fault', [None, 'failed-start', 'replaced', 'preexisting'])
def test_manager_cleanup_requires_its_new_invocation(monkeypatch, tmp_path, fault):
    old = dict(ActiveState='inactive', InvocationID='', MainPID='0')
    owned = dict(ActiveState='active', InvocationID='a' * 32, MainPID='4321')
    if fault == 'preexisting':
        old = owned
    current = dict(owned, InvocationID='b' * 32) if fault == 'replaced' else owned
    state = Mock(side_effect=[old, owned, current, old])
    monkeypatch.setattr(scope, 'manager', state)
    run = Mock()
    if fault == 'failed-start':
        run.side_effect = [RuntimeError('startup'), '']
    monkeypatch.setattr(scope.guest, 'run', run)
    monkeypatch.setattr(scope, 'PROC', tmp_path)
    if fault:
        expected = RuntimeError if fault == 'failed-start' else scope.guest.GuestError
        with pytest.raises(expected):
            with scope.owned_manager(SimpleNamespace(pw_uid=1001)):
                pass
    else:
        with scope.owned_manager(SimpleNamespace(pw_uid=1001)) as process:
            assert process == tmp_path / '4321'
    stopped = [call.args[0] for call in run.call_args_list if call.args[0][1] == 'stop']
    assert stopped == ([] if fault in ('preexisting', 'replaced') else
                       [['systemctl', 'stop', 'user@1001.service']])
