"""Offline credential ownership and failure tests; no commands or VM started."""

import json
from unittest.mock import Mock

import pytest

import fixture_credentials as credentials
from private_artifacts import PrivateCollector

from tests.support.e2e_credentials import CANARY, HASH, attempt


def test_fixed_fixture_passwords_verify_and_use_same_frozen_worker_registry(attempt, capsys):
    receipt = attempt.run()
    assert receipt == {'accounts': 4, 'passwords_verified': True,
                       'unrelated_accounts_preserved': True}
    assert attempt.guest.close.call_count == 2
    assert attempt.verified.recheck.call_count == 2
    assert attempt.fixture.worker_secrets(attempt.lease) is attempt.fixture.variables
    for call in attempt.hasher.run.call_args_list:
        assert call.args[0] == ['/usr/bin/openssl', 'passwd', '-6', '-salt', 'fixturesalt', '-stdin']
        assert call.kwargs['input'] == CANARY.encode() + b'\n'
    assert attempt.files['/etc/passwd'] == attempt.original['/etc/passwd']
    output = capsys.readouterr().err + json.dumps(receipt) + repr(attempt.fixture)
    assert CANARY not in output and HASH not in output
    assert not any(account.username in output for account in credentials.ACCOUNTS.values())
    with PrivateCollector(run_id='credential-test',
                          secrets=attempt.fixture.variables.registered_secrets,
                          parent=attempt.directory) as collector:
        with pytest.raises(credentials.EvidenceError, match='secret-detected'):
            collector.save_report('bad', {'private': CANARY})
        collector.save_report('good', receipt)
        collector.verify([])
    attempt.lease.stop.assert_not_called()
    attempt.lease.finish.assert_not_called()


@pytest.mark.parametrize('fault', ['phase', 'running', 'lease', 'released', 'guard',
    'inputs', 'uid', 'shell', 'missing', 'duplicate', 'symlink', 'hardlink', 'owner',
    'existing-directory', 'public-directory', 'command', 'interrupt', 'secret-file',
    'root', 'passwd', 'unchanged', 'wrong-password', 'aging', 'late-inputs'])
def test_failure_latches_before_worker_and_outer_owner_keeps_cleanup(attempt, fault, capsys):
    if fault == 'phase': attempt.lease.state['phase'] = 'running'
    elif fault == 'running': attempt.lease.state['domain_id'] = 5
    elif fault == 'lease': attempt.verified.lease = Mock()
    elif fault == 'released': attempt.lease.fd = None
    elif fault == 'guard': attempt.lease.guard.side_effect = RuntimeError(CANARY)
    elif fault == 'inputs': attempt.verified.recheck.side_effect = RuntimeError(CANARY)
    elif fault == 'uid': attempt.files['/etc/passwd'] = attempt.files['/etc/passwd'].replace(b':1000:', b':9999:')
    elif fault == 'shell': attempt.files['/etc/passwd'] = attempt.files['/etc/passwd'].replace(b'/bin/bash', b'/bin/false')
    elif fault == 'missing': attempt.files['/etc/shadow'] = b'root:!:20000:0:99999:7:::\n'
    elif fault == 'duplicate': attempt.files['/etc/shadow'] *= 2
    elif fault == 'symlink': attempt.guest.realpath.side_effect = lambda path: '/replaced'
    elif fault in ('hardlink', 'owner'):
        attempt.guest.lstatns.return_value['st_nlink' if fault == 'hardlink' else 'st_uid'] = 2
    elif fault == 'existing-directory': (attempt.directory / 'fixture-secrets').mkdir()
    elif fault == 'public-directory': attempt.directory.chmod(0o755)
    elif fault == 'command': attempt.commands.run.side_effect = RuntimeError(CANARY)
    elif fault == 'interrupt': attempt.commands.run.side_effect = KeyboardInterrupt(CANARY)
    elif fault == 'wrong-password': attempt.hasher.run.return_value = b'wrong-hash'
    elif fault == 'late-inputs': attempt.verified.recheck.side_effect = [None, RuntimeError(CANARY)]
    else:
        def corrupt(args, **kwargs):
            attempt.customize(args, **kwargs)
            if fault == 'secret-file':
                (attempt.directory / 'fixture-secrets/parent.password').write_text('replaced')
            elif fault == 'root':
                attempt.files['/etc/shadow'] = attempt.files['/etc/shadow'].replace(b'root:!', b'root:changed')
            elif fault == 'passwd': attempt.files['/etc/passwd'] += b'extra\n'
            elif fault == 'unchanged': attempt.files['/etc/shadow'] = attempt.original['/etc/shadow']
            elif fault == 'aging': attempt.files['/etc/shadow'] = attempt.files['/etc/shadow'].replace(b':20000:', b':20001:')
        attempt.commands.run.side_effect = corrupt
    with pytest.raises(KeyboardInterrupt if fault == 'interrupt' else credentials.EvidenceError) as caught:
        attempt.run()
    assert CANARY not in str(caught.value)
    with pytest.raises(credentials.EvidenceError, match='provisioning-required'):
        attempt.fixture.worker_secrets(attempt.lease)
    with pytest.raises(credentials.EvidenceError, match='already-attempted'):
        attempt.run()
    if fault in ('phase', 'running', 'lease', 'released', 'guard', 'inputs', 'uid',
                 'shell', 'missing', 'duplicate', 'symlink', 'hardlink', 'owner',
                 'existing-directory', 'public-directory'):
        attempt.commands.run.assert_not_called()
    assert CANARY not in capsys.readouterr().err
    attempt.lease.stop.assert_not_called()
    attempt.lease.finish.assert_not_called()


def test_completed_credentials_cannot_be_used_on_replacement_or_started_lease(attempt):
    attempt.run()
    with pytest.raises(credentials.EvidenceError, match='provisioning-required'):
        attempt.fixture.worker_secrets(Mock())
    attempt.lease.state['domain_id'] = 42
    with pytest.raises(credentials.EvidenceError, match='provisioning-required'):
        attempt.fixture.worker_secrets(attempt.lease)


def test_preflight_requires_pinned_password_verifier():
    commands = Mock()
    commands.run.return_value = b'3.5.5-1ubuntu3.5'
    credentials.preflight(commands)
    commands.run.return_value = b'other'
    with pytest.raises(credentials.EvidenceError, match='openssl-prerequisite'):
        credentials.preflight(commands)
