"""LIFE04 composition refuses replay and incomplete or non-durable results."""

import json
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

import check_e2e_package_command as check
import check_graphical_smoke as smoke
import package_install as install
import session_control
from owned_commands import CommandError
from private_artifacts import EvidenceError
from tests.support.package_command import boundary


def test_fixed_launcher(monkeypatch):
    launch = Mock(return_value=0)
    monkeypatch.setattr(check, 'smoke', launch)
    assert check.main() == 0
    launch.assert_called_once_with(assets=check.ASSETS, provision_credentials=True,
                                  package_install=True)


@pytest.mark.parametrize('extra', [{}, {'install': True}, {'product_free_entry': True},
    {'package_authority': True}, {'challenges': True}, {'fresh_desktop': 'parent'}])
def test_exclusive_empty_baseline_required(extra):
    kwargs = dict(assets=check.ASSETS, provision_credentials=True, **extra) if extra else {}
    with pytest.raises(CommandError):
        smoke.main(package_install=True, **kwargs)


@pytest.mark.parametrize('fault', ['', 'transport', 'guard'])
def test_composition_never_resubmits_after_uncertain_input(monkeypatch, fault):
    command = boundary(monkeypatch)
    monkeypatch.setattr(install, 'PackageCommand', Mock(return_value=command))
    journey = SimpleNamespace(package=None, transport=command.transport,
        context=SimpleNamespace(verified=command.verified))
    guard = Mock(side_effect=[None, EvidenceError('lost-owner')] if fault == 'guard' else None)
    if fault == 'transport': command.transport.call.side_effect = TimeoutError()
    if fault:
        with pytest.raises((TimeoutError, EvidenceError)):
            install.submit_install(journey, guard)
    else:
        assert install.submit_install(journey, guard) == {'submitted': True}
    with pytest.raises(EvidenceError, match='package-install:replay'):
        install.submit_install(journey, Mock())
    assert command.transport.call.call_count == 1


@pytest.mark.parametrize('fault', ['', 'missing', 'failed', 'notice', 'durability'])
def test_result_checkpoint_requires_public_success_before_durable_ack(tmp_path, monkeypatch, fault):
    command = boundary(monkeypatch)
    progress = Mock(side_effect=OSError('evidence unavailable') if fault == 'durability' else None)
    journey = install.PackageInstallJourney(SimpleNamespace(directory=tmp_path,
        product_free=True, asset_transfer=Mock(), verified=command.verified), progress)
    monkeypatch.setattr(install, 'PackageCommand', Mock(return_value=command))
    journey.transport = command.transport
    journey.vm = SimpleNamespace(read=Mock(return_value={'boot_sha256': 'b' * 64}))
    if fault != 'missing': install.submit_install(journey, Mock())
    if fault == 'failed': command.receipt = (command.receipt[0], 1)
    if fault == 'notice': command.receipt = (b'command submitted\n', 0)
    journey.steps = [{'stage': stage} for stage in install.PLAN.stages[:-1]]
    monkeypatch.setattr(session_control, 'observe', Mock(return_value={'outcome': 'passed'}))
    (tmp_path / 'package-result.request.json').write_text(json.dumps(
        {'stage': 'package-result', 'screenshot': None}))
    if fault:
        with pytest.raises((EvidenceError, OSError)): journey.step(Mock())
        assert not (tmp_path / 'package-result.reply.json').exists()
        with pytest.raises(EvidenceError, match='previous-failure'): journey.step(Mock())
    else:
        journey.step(Mock())
        assert (tmp_path / 'package-result.reply.json').exists()
        observed = progress.call_args.args[1]
        assert observed['package']['exit_status'] == 0
        assert observed['assertion']['id'] == 'install-completed-with-reboot-notice'


@pytest.mark.parametrize('extra', [{}, {'customer_reboot': True}, {'restart_notice': True},
    {'install': True}, {'kiosk_entry': True}])
def test_unrelated_selector_refuses_incompatible_modes(extra):
    kwargs = dict(assets=check.ASSETS, provision_credentials=True, **extra) if extra else {}
    with pytest.raises(CommandError): smoke.main(unrelated_reboot_request=True, **kwargs)




@pytest.mark.parametrize('fault', ['', 'transport', 'guard'])
def test_unrelated_shared_submission_retains_consumption_and_qualification_refusals(monkeypatch, fault):
    import package_command
    import unrelated_reboot
    command = boundary(monkeypatch)
    command.read_identity = Mock(return_value={'version': 'current'})
    command.package_identities = Mock(return_value={'current': {'version': 'current'}})
    command.read_unrelated = Mock()
    monkeypatch.setattr(install, 'PackageCommand', Mock(return_value=command))
    monkeypatch.setattr(unrelated_reboot, 'PackageCommand', Mock(return_value=command))
    journey = SimpleNamespace(unrelated_package=None, transport=command.transport,
        context=SimpleNamespace(verified=command.verified))
    guard = Mock(side_effect=[None, EvidenceError('lost-owner')] if fault == 'guard' else None)
    if fault == 'transport': command.transport.call.side_effect = TimeoutError()
    if fault:
        with pytest.raises((EvidenceError, TimeoutError)): unrelated_reboot.qualify_submission(journey, guard)
    else:
        value = unrelated_reboot.qualify_submission(journey, guard)
        assert value['refusals'] == ['unregistered', 'artifact', 'vm', 'attempt', 'replay']
    with pytest.raises(EvidenceError, match='replay'): install.submit_unrelated(journey, Mock())
    assert journey.unrelated_package is command and command.transport.call.call_count == 1
