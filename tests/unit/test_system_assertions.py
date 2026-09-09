"""Shared installed assertions preserve real-caller framing and private diagnostics."""

import json
from unittest.mock import Mock

import pytest
import system_assertions as assertions
import system_enforcement as enforcement


def test_batched_calls_preserve_order_identity_root_opt_in_and_private_streams(monkeypatch):
    replies = [{'result': [1]}, {'error': 'org.example.Denied'}]
    run = Mock(return_value=json.dumps({'uid': 0, 'replies': replies}).encode())
    monkeypatch.setattr(assertions.guest, 'commands', Mock(run=run))
    operations = [{'kind': 'call', 'method': 'First'}, {'kind': 'call', 'method': 'Second'}]
    assert assertions.batch(0, operations, allow_root=True) == replies
    assert json.loads(run.call_args.kwargs['input']) == {
        'uid': 0, 'operations': operations, 'allow_root': True}
    assert run.call_args.kwargs['timeout'] == 180
    assert run.call_args.kwargs['merge_stderr'] is False


@pytest.mark.parametrize('raw', [
    b'private-canary', b'\xff', b'[]', b'null',
    b'{"uid": true, "replies": [{}]}',
    b'{"uid": 1002, "replies": [{}]}',
    b'{"uid": 1001, "replies": []}',
    b'{"uid": 1001, "replies": ["private-canary"]}',
])
def test_malformed_or_wrong_caller_replies_fail_with_a_fixed_category(monkeypatch, raw, capsys):
    monkeypatch.setattr(assertions.guest, 'commands', Mock(run=Mock(return_value=raw)))
    with pytest.raises(assertions.guest.GuestError) as caught:
        assertions.call(1001, 'GetPreferences')
    assert str(caught.value) == 'caller:reply'
    assert capsys.readouterr() == ('', '')


@pytest.mark.parametrize('reply', [{'result': ['value']}, {'error': 'private-canary'}])
def test_enforcement_uses_shared_transport_and_retains_its_failure_category(monkeypatch, reply):
    run = Mock(return_value=json.dumps({'uid': 1001, 'replies': [reply]}).encode())
    monkeypatch.setattr(assertions.guest, 'commands', Mock(run=run))
    if 'result' in reply:
        assert enforcement.call(1001, 'GetPreferences', '(u)', (1002,)) == ['value']
    else:
        with pytest.raises(assertions.guest.GuestError) as caught:
            enforcement.call(1001, 'GetPreferences', '(u)', (1002,))
        assert str(caught.value) == 'enforcement:broker-call-failed'
    assert json.loads(run.call_args.kwargs['input']) == {
        'uid': 1001, 'allow_root': False, 'operations': [
            {'kind': 'call', 'method': 'GetPreferences', 'signature': '(u)', 'args': [1002]}]}


def test_success_assertion_does_not_echo_backend_error_details():
    with pytest.raises(assertions.guest.GuestError) as caught:
        assertions.accepted({'error': 'private-canary'})
    assert str(caught.value) == 'authorization:expected-success'
