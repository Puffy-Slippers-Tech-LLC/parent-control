"""Host-only checks of the scenario read-only capability and output boundary."""

import json
from pathlib import Path
import sys
from unittest.mock import Mock

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'tests/e2e'))
import guest_observations
from observation_transport import ReadOnlyObservations
from private_artifacts import EvidenceError
sys.path.pop(0)


@pytest.fixture
def observer():
    transport = Mock(config={'run': 'a' * 32, 'domain_id': 7})
    return ReadOnlyObservations(transport), transport


@pytest.mark.parametrize('name,program,timeout,result,raw', [
    ('assets', guest_observations.ASSETS, 120, {'files': 3, 'sha256': 'a' * 64},
     (json.dumps({'files': 3, 'sha256': 'a' * 64}, sort_keys=True) + '\n').encode()),
    ('greeter', guest_observations.GREETER, 110,
     {'active_graphical_greeter': True, 'unexpected_user_session': False}, b'greeter-ready\n'),
])
def test_fixed_probe_checks_ownership_before_and_after_output(observer, name, program, timeout, result, raw):
    reader, transport = observer
    events = []
    transport.guard.side_effect = lambda _: events.append('guard')
    def call(*args, **kwargs):
        events.append('call')
        return raw
    transport.call.side_effect = call
    assert reader.read(name) == result
    assert events == ['guard', 'call', 'guard']
    transport.call.assert_called_once_with(['/usr/bin/python3', '-c', program], timeout=timeout)
    transport.reboot.assert_not_called()
    transport.copy.assert_not_called()


@pytest.mark.parametrize('probe', ['reboot', 'checkpoint', 'restore', 'set-grant', 'install',
                                    'sh -c touch /tmp/secret-canary', '/etc/shadow', '', None, [], {}])
def test_unknown_and_state_writing_requests_never_reach_transport(observer, probe, capsys):
    reader, transport = observer
    with pytest.raises(EvidenceError, match='unknown-probe'):
        reader.read(probe)
    transport.guard.assert_not_called()
    transport.call.assert_not_called()
    assert 'secret-canary' not in capsys.readouterr().err
    with pytest.raises(EvidenceError, match='previous-failure'):
        reader.read('greeter')
    transport.call.assert_not_called()


@pytest.mark.parametrize('method', ['call', 'copy', 'reboot', 'provision', 'reset'])
def test_scenario_capability_has_no_mutation_or_command_entrypoint(observer, method):
    assert not hasattr(observer[0], method)


@pytest.mark.parametrize('boundary', ['before', 'after', 'command', 'interrupt', 'config-before', 'config-after'])
def test_failure_and_identity_replacement_latch_without_exporting_raw_errors(observer, boundary, capsys):
    reader, transport = observer
    transport.call.return_value = b'greeter-ready\n'
    error = RuntimeError('private-secret-canary')
    if boundary in ('before', 'after'):
        transport.guard.side_effect = [error] if boundary == 'before' else [None, error]
    elif boundary == 'command':
        transport.call.side_effect = error
    elif boundary == 'interrupt':
        transport.call.side_effect = KeyboardInterrupt('private-secret-canary')
    elif boundary == 'config-before':
        transport.config['domain_id'] = 8
    else:
        def replaced(*args, **kwargs):
            transport.config['domain_id'] = 8
            return b'greeter-ready\n'
        transport.call.side_effect = replaced
    with pytest.raises(KeyboardInterrupt if boundary == 'interrupt' else EvidenceError) as caught:
        reader.read('greeter')
    assert 'private-secret-canary' not in str(caught.value)
    assert 'private-secret-canary' not in capsys.readouterr().err
    assert transport.call.call_count == (0 if boundary in ('before', 'config-before') else 1)
    count = transport.call.call_count
    with pytest.raises(EvidenceError, match='previous-failure'):
        reader.read('greeter')
    assert transport.call.call_count == count


@pytest.mark.parametrize('raw', [b'', b'private-secret-canary', b'{}', b'null', b'[]', b'\xff',
    b'a' * 1025, b'{"files": 1, "files": 2, "sha256": "' + b'a' * 64 + b'"}\n',
    *[(json.dumps(value, sort_keys=True) + '\n').encode() for value in [
        {'files': True, 'sha256': 'a' * 64}, {'files': 0, 'sha256': 'a' * 64},
        {'files': 100001, 'sha256': 'a' * 64}, {'files': 1, 'sha256': 'A' * 64},
        {'files': 1, 'sha256': 'a' * 64, 'user': 'private-secret-canary'},
    ]],
])
def test_malformed_or_private_asset_outputs_are_not_returned(observer, raw, capsys):
    reader, transport = observer
    transport.call.return_value = raw
    with pytest.raises(EvidenceError) as caught:
        reader.read('assets')
    assert 'private-secret-canary' not in str(caught.value)
    assert 'private-secret-canary' not in capsys.readouterr().err
    with pytest.raises(EvidenceError, match='previous-failure'):
        reader.read('assets')


@pytest.mark.parametrize('raw', [b'greeter-ready', b'greeter-ready\nprivate-secret-canary',
                               b'{"active_graphical_greeter": false}', 'greeter-ready\n'])
def test_greeter_requires_exact_safe_success(observer, raw):
    reader, transport = observer
    transport.call.return_value = raw
    with pytest.raises(EvidenceError, match='invalid-output'):
        reader.read('greeter')
