"""Read-only credential verification never mutates guest passwords or keyrings."""
import json
from unittest.mock import Mock
import pytest
import fixture_credentials as credentials
from private_artifacts import PrivateCollector
from tests.support.e2e_credentials import CANARY, HASH, attempt

def test_shared_password_verification_preserves_every_guest_byte(attempt, capsys):
    receipt = attempt.run()
    assert receipt == {'accounts': 4, 'passwords_verified': True,
                       'unrelated_accounts_preserved': True}
    assert attempt.guest.close.call_count == 1
    assert attempt.verified.recheck.call_count == 2
    assert attempt.fixture.worker_secrets(attempt.lease) is attempt.fixture.variables
    assert attempt.verifier.call_count == 4
    assert all(call.args == (CANARY, HASH) for call in attempt.verifier.call_args_list)
    assert attempt.files == attempt.original
    assert not list(attempt.directory.iterdir())
    attempt.commands.run.assert_not_called()
    attempt.guest.write.assert_not_called()
    attempt.guest.mv.assert_not_called()
    output = capsys.readouterr().err + json.dumps(receipt) + repr(attempt.fixture)
    assert CANARY not in output and HASH not in output
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
    'inputs', 'uid', 'shell', 'home', 'missing', 'duplicate', 'symlink', 'hardlink',
    'owner', 'interrupt', 'wrong-password', 'late-inputs', 'configuration'])
def test_failure_latches_without_changing_guest(attempt, fault, capsys, monkeypatch):
    if fault == 'phase': attempt.lease.state['phase'] = 'running'
    elif fault == 'running': attempt.lease.state['domain_id'] = 5
    elif fault == 'lease': attempt.verified.lease = Mock()
    elif fault == 'released': attempt.lease.fd = None
    elif fault == 'guard': attempt.lease.guard.side_effect = RuntimeError(CANARY)
    elif fault == 'inputs': attempt.verified.recheck.side_effect = RuntimeError(CANARY)
    elif fault == 'uid': attempt.files['/etc/passwd'] = attempt.files['/etc/passwd'].replace(b':1000:', b':9999:')
    elif fault == 'shell': attempt.files['/etc/passwd'] = attempt.files['/etc/passwd'].replace(b'/bin/bash', b'/bin/false')
    elif fault == 'home': attempt.files['/etc/passwd'] = attempt.files['/etc/passwd'].replace(b'/home/', b'/elsewhere/')
    elif fault == 'missing': attempt.files['/etc/shadow'] = b'root:!:20000:0:99999:7:::\n'
    elif fault == 'duplicate': attempt.files['/etc/shadow'] *= 2
    elif fault == 'symlink': attempt.guest.realpath.side_effect = lambda path: '/replaced'
    elif fault in ('hardlink', 'owner'):
        attempt.guest.lstatns.return_value['st_nlink' if fault == 'hardlink' else 'st_uid'] = 2
    elif fault == 'interrupt': attempt.verifier.side_effect = KeyboardInterrupt(CANARY)
    elif fault == 'wrong-password': attempt.verifier.side_effect = lambda *_: False
    elif fault == 'late-inputs': attempt.verified.recheck.side_effect = [None, RuntimeError(CANARY)]
    elif fault == 'configuration': monkeypatch.setattr(credentials, 'read_password', lambda: 'changed')
    before = dict(attempt.files)
    with pytest.raises(KeyboardInterrupt if fault == 'interrupt' else credentials.EvidenceError) as caught:
        attempt.run()
    assert CANARY not in str(caught.value)
    with pytest.raises(credentials.EvidenceError, match='provisioning-required'):
        attempt.fixture.worker_secrets(attempt.lease)
    with pytest.raises(credentials.EvidenceError, match='already-attempted'):
        attempt.run()
    assert attempt.files == before
    attempt.commands.run.assert_not_called()
    attempt.guest.write.assert_not_called()
    assert CANARY not in capsys.readouterr().err
    attempt.lease.stop.assert_not_called()
    attempt.lease.finish.assert_not_called()

def test_completed_credentials_refuse_replacement_or_started_lease(attempt):
    attempt.run()
    with pytest.raises(credentials.EvidenceError, match='provisioning-required'):
        attempt.fixture.worker_secrets(Mock())
    attempt.lease.state['domain_id'] = 42
    with pytest.raises(credentials.EvidenceError, match='provisioning-required'):
        attempt.fixture.worker_secrets(attempt.lease)
