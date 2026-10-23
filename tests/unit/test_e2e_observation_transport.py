"""Read-only capability ownership and credential-purpose boundaries."""

from unittest.mock import Mock

import pytest

from observation_transport import ReadOnlyObservations
from private_artifacts import EvidenceError


@pytest.fixture
def observer():
    transport = Mock(config={'run': 'a' * 32, 'domain_id': 7})
    return ReadOnlyObservations(transport), transport


@pytest.mark.parametrize('raw', [b'install-password-safe\n',
    b'reboot-password-safe\nprivate-secret-canary', b'reboot-password-rejected:private-secret-canary\n',
    b'reboot-password-rejected:sudo-command\nreboot-password-safe\n'])
def test_reboot_proof_rejects_other_purpose_and_private_or_mixed_output(observer, raw, capsys):
    reader, transport = observer
    transport.call.return_value = raw
    with pytest.raises(EvidenceError, match='invalid-output'):
        reader.read('reboot-password')
    assert capsys.readouterr().err == 'e2e:observation-rejected\n'
    with pytest.raises(EvidenceError, match='previous-failure'):
        reader.read('reboot-password')


@pytest.mark.parametrize('probe', ['install', 'sh -c touch /tmp/secret-canary'])
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


@pytest.mark.parametrize('method', ['call', 'copy', 'reboot'])
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
