"""Ordered recipient continuity cannot be repinned, replayed or exported."""

import json
from unittest.mock import Mock

import pytest

import guest_observations
from observation_transport import ReadOnlyObservations
from private_artifacts import EvidenceError


STAGES = ('vt6-getty-identity', 'vt6-password-identity', 'vt6-password-recheck')


def response(stage, *, boot='a' * 64, recipient='b' * 64):
    return (json.dumps({'probe': STAGES[min(stage, 1)], 'boot_sha256': boot,
                       'recipient_sha256': recipient}, sort_keys=True) + '\n').encode()


@pytest.fixture
def observer():
    transport = Mock(config={'run': 'a' * 32, 'domain_id': 7})
    reader = ReadOnlyObservations(transport)
    transport.call.return_value = b'a' * 64 + b'\n'
    reader.read('boot')
    transport.reset_mock()
    return reader, transport


def advance(reader, transport, count):
    for stage in range(count):
        transport.call.return_value = response(stage)
        result = reader.read(STAGES[stage])
        assert result == {'boot_sha256': 'a' * 64, 'active_vt6_verified': True, **(
            {'vt6_getty_verified': True} if stage == 0 else {
                'vt6_login_process_verified': True, 'terminal_echo_disabled': True,
                'vt6_recipient_continuity_verified': True})}
    transport.reset_mock()


def assert_latched(reader, transport, capsys):
    calls = list(transport.mock_calls)
    for name in (*STAGES, 'boot', 'vt6-getty', 'vt6-password', 'vt6-session'):
        with pytest.raises(EvidenceError, match='previous-failure'):
            reader.read(name)
    assert transport.mock_calls == calls
    output = capsys.readouterr()
    assert not output.out
    assert 'private-canary' not in output.err
    assert 'b' * 64 not in output.err


def test_vt6_recipient_uses_fresh_fixed_probes_and_only_returns_proofs(observer, capsys):
    reader, transport = observer
    for stage in range(3):
        transport.call.return_value = response(stage)
        result = reader.read(STAGES[stage])
        assert 'recipient_sha256' not in result
        assert 'vt6_password_input_authorized' not in result
        assert 'vt6_shell_ready_verified' not in result
        transport.call.assert_called_once_with(['/usr/bin/python3', '-c',
            guest_observations.VT6_GETTY_IDENTITY if stage == 0 else
            guest_observations.VT6_PASSWORD_IDENTITY], timeout=60 if stage == 0 else 30)
        assert transport.guard.call_count == 2
        transport.copy.assert_not_called()
        transport.reboot.assert_not_called()
        transport.reset_mock()
    with pytest.raises(EvidenceError, match='vt6-recipient-order'):
        reader.read(STAGES[2])
    transport.call.assert_not_called()
    assert_latched(reader, transport, capsys)


@pytest.mark.parametrize('completed,requested', [
    (0, 1), (0, 2), (1, 0), (1, 2), (2, 0), (2, 1), (3, 0), (3, 1), (3, 2)])
def test_vt6_recipient_refuses_skips_replays_and_repinning(observer, completed, requested, capsys):
    reader, transport = observer
    advance(reader, transport, completed)
    with pytest.raises(EvidenceError, match='vt6-recipient-order'):
        reader.read(STAGES[requested])
    transport.call.assert_not_called()
    assert_latched(reader, transport, capsys)


def test_vt6_recipient_requires_independent_boot_observation(observer, capsys):
    _, transport = observer
    reader = ReadOnlyObservations(transport)
    with pytest.raises(EvidenceError, match='vt6-recipient-order'):
        reader.read(STAGES[0])
    transport.call.assert_not_called()
    assert_latched(reader, transport, capsys)


@pytest.mark.parametrize('stage', [0, 1, 2])
@pytest.mark.parametrize('fault', ['boot', 'recipient', 'wrong-probe', 'extra', 'duplicate',
    'noncanonical', 'private', 'boolean-digest', 'uppercase', 'missing', 'oversize',
    'before-guard', 'after-guard', 'transport', 'configuration', 'interrupt'])
def test_vt6_recipient_refusal_is_private_and_permanent(observer, stage, fault, capsys):
    reader, transport = observer
    advance(reader, transport, stage)
    raw = response(stage)
    if fault == 'boot':
        raw = response(stage, boot='c' * 64)
    elif fault == 'recipient':
        # At the first observation no prior recipient exists to compare.
        raw = response(stage, recipient='c' * 64) if stage else response(stage, recipient='invalid')
    elif fault in ('wrong-probe', 'extra', 'boolean-digest', 'uppercase', 'missing'):
        data = json.loads(raw)
        if fault == 'wrong-probe':
            data['probe'] = STAGES[1 if stage == 0 else 0]
        elif fault == 'extra':
            data['private-canary'] = 'private-canary'
        elif fault == 'boolean-digest':
            data['recipient_sha256'] = True
        elif fault == 'uppercase':
            data['recipient_sha256'] = 'B' * 64
        else:
            del data['recipient_sha256']
        raw = (json.dumps(data, sort_keys=True) + '\n').encode()
    elif fault == 'duplicate':
        raw = raw.replace(b'{', b'{"boot_sha256": "' + b'a' * 64 + b'", ', 1)
    elif fault == 'noncanonical':
        raw += b'\n'
    elif fault == 'private':
        raw = b'private-canary'
    elif fault == 'oversize':
        raw = b'x' * 1025
    elif fault in ('before-guard', 'after-guard'):
        transport.guard.side_effect = ([RuntimeError('private-canary')] if fault == 'before-guard'
                                      else [None, RuntimeError('private-canary')])
    elif fault == 'transport':
        transport.call.side_effect = RuntimeError('private-canary')
    elif fault == 'configuration':
        transport.config['domain_id'] = 8
    elif fault == 'interrupt':
        transport.call.side_effect = KeyboardInterrupt('private-canary')
    transport.call.return_value = raw
    with pytest.raises(KeyboardInterrupt if fault == 'interrupt' else EvidenceError) as caught:
        reader.read(STAGES[stage])
    assert 'private-canary' not in str(caught.value)
    assert reader._vt6_recipient_stage == stage
    assert_latched(reader, transport, capsys)


def test_vt6_recipient_new_boot_read_cannot_repin_original_identity(observer, capsys):
    reader, transport = observer
    advance(reader, transport, 1)
    transport.call.return_value = b'c' * 64 + b'\n'
    reader.read('boot')
    transport.call.return_value = response(1, boot='c' * 64)
    with pytest.raises(EvidenceError, match='vt6-recipient-changed'):
        reader.read(STAGES[1])
    assert_latched(reader, transport, capsys)
