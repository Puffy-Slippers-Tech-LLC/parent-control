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
from tests.support.desktop_session import RUN_PROBE
from tests.support.package_command import boundary
from tests.support.perl import run_perl


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


@pytest.mark.parametrize('fault', ['', 'wrong-entry', 'command-context',
                                   'package-submitted', 'package-result'])
def test_worker_stops_at_failed_checkpoint(fault):
    source = RUN_PROBE.replace('require onpc_desktop_session;', 'require onpc_package_install;')
    source = source.replace('onpc_desktop_session::run', 'onpc_package_install::run')
    source = source.replace('}, $action);', '});')
    source = source.replace("push @events, ['stage', $_[0]];",
        "push @events, ['stage', $_[0]]; die 'fixed failure' if $_[0] eq $action;")
    result = json.loads(run_perl(source, fault).stdout)
    assert bool(result['ok']) == (not fault)
    stages = [event[1] for event in result['events'] if event[0] == 'stage']
    expected = list(install.PLAN.screen_tags)
    assert stages == (expected[:expected.index(fault) + 1] if fault else expected)
    if not fault: assert result['events'][-1] == ['power', 'off']
