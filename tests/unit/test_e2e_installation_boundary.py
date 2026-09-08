"""Exercise install phases, provenance and terminal failure latching."""

from pathlib import Path
import sys
from unittest.mock import Mock

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'e2e'))
from installation_boundary import InstallationBoundary
from private_artifacts import EvidenceError
sys.path.pop(0)


@pytest.fixture
def boundary():
    observations = {
        'boot': {'boot_sha256': 'b'*64},
        'serial-session': {'active_local_serial_session': True},
        'package-absent': {'product_package_absent': True},
        'install-password': {'sudo_install_process_verified': True, 'terminal_echo_disabled': True},
        'package-installed': {'package_sha256': 'a'*64, 'installed_identity_verified': True,
                              'product_reboot_required': True},
    }
    observer = Mock(read=Mock(side_effect=lambda name: dict(observations[name])))
    verified = Mock(inputs={'package_sha256': 'a'*64})
    transfer = Mock(verified=verified)
    return InstallationBoundary(observer, verified, transfer), observations


def test_ordered_install_acknowledgements_bind_assets_and_package(boundary):
    instance, _ = boundary
    before = instance.observe('install-ready')
    assert before['installation_authorized'] and before['verified_assets']
    instance.transfer.observe.assert_called_once_with(instance.observer)
    assert instance.observe('install-password')['sudo_install_process_verified']
    after = instance.observe('install-complete')
    assert after['verified_package_digest'] and after['package_sha256'] == 'a'*64
    assert after['boot_sha256'] == before['boot_sha256']
    with pytest.raises(EvidenceError, match='install:phase'):
        instance.observe('install-complete')


@pytest.mark.parametrize('first,bad', [(0, 'install-password'), (0, 'install-complete'),
    (1, 'install-ready'), (1, 'install-complete'), (2, 'install-ready'), (2, 'install-password'),
    (0, 'arbitrary-command')])
def test_phase_refusal_is_terminal_before_any_observation(boundary, first, bad):
    instance, _ = boundary
    for stage in instance.STAGES[:first]:
        instance.observe(stage)
    instance.observer.reset_mock()
    with pytest.raises(EvidenceError, match='install:phase'):
        instance.observe(bad)
    with pytest.raises(EvidenceError, match='install:previous-failure'):
        instance.observe(instance.STAGES[first])
    instance.observer.read.assert_not_called()


@pytest.mark.parametrize('fault', ['transfer', 'absent', 'secret-proof', 'package',
    'changed-inputs', 'boot-before', 'boot-during', 'provenance-before', 'provenance-after', 'interrupt'])
def test_failed_install_observation_never_authorizes_next_input(boundary, fault, capsys):
    instance, observations = boundary
    stage = 'install-ready'
    private_error = RuntimeError('private-canary')
    if fault in ('secret-proof', 'package', 'boot-before', 'changed-inputs'):
        instance.observe(stage)
        stage = 'install-password'
    if fault == 'package':
        instance.observe(stage)
        stage = 'install-complete'
        observations['package-installed']['package_sha256'] = 'c'*64
    elif fault == 'transfer':
        instance.transfer.observe.side_effect = private_error
    elif fault in ('absent', 'secret-proof'):
        fail_probe = 'package-absent' if fault == 'absent' else 'install-password'
        def read(name):
            if name == fail_probe:
                raise private_error
            return dict(observations[name])
        instance.observer.read.side_effect = read
    elif fault == 'changed-inputs':
        instance.verified.inputs['package_sha256'] = 'c'*64
    elif fault == 'boot-before':
        observations['boot']['boot_sha256'] = 'c'*64
    elif fault == 'boot-during':
        instance.transfer.observe.side_effect = lambda _: observations['boot'].update(boot_sha256='c'*64)
    elif fault in ('provenance-before', 'provenance-after', 'interrupt'):
        instance.verified.recheck.side_effect = ([None, private_error] if fault == 'provenance-after'
            else KeyboardInterrupt('private-canary') if fault == 'interrupt' else private_error)
    with pytest.raises(KeyboardInterrupt if fault == 'interrupt' else EvidenceError) as caught:
        instance.observe(stage)
    assert 'private-canary' not in str(caught.value) + capsys.readouterr().err
    calls = instance.observer.read.call_count
    with pytest.raises(EvidenceError, match='previous-failure'):
        instance.observe(stage)
    assert instance.observer.read.call_count == calls
