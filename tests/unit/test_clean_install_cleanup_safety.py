"""Case 2 must stop before acknowledging any incomplete customer result."""

import json
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

import accessible_ui as ui_module
import clean_install as case
import package_journey
from private_artifacts import EvidenceError


@pytest.mark.parametrize('fault', ['', 'ignored-input'])
def test_restart_kiosk_public_selection_repairs_other_initial_approver_without_weakening_guard(fault):
    from tests.support.e2e_kiosk import accounts_form
    from ui_observations import UiObservations
    ui, approver, _choices, _expected = accounts_form('approver')
    commit = approver.setValue.side_effect
    commit('1010')  # Existing eligible parent selected before the public input.
    child = ui.find_id('kiosk-child-selector')
    child.value = '1002'
    child.description = f'Selected account: {ui_module.EXISTING_CHILD}.'
    child.children[0].identity = 'kiosk-child-selected-1002'
    child.children[0].name = ui_module.EXISTING_CHILD
    with pytest.raises(ui_module.UiError, match='kiosk-valid-selection'):
        ui.restart_usable('kiosk')
    approver.setValue.assert_not_called()
    if fault:
        approver.setValue.side_effect = lambda _uid: None
        with pytest.raises(ui_module.UiError, match='timeout:kiosk-selected-account'):
            ui.run('kiosk-language-jordan-jamie', '')
        assert ui.input_uncertain
        with pytest.raises(ui_module.UiError): ui.restart_usable('kiosk')
    else:
        result = ui.run('kiosk-language-jordan-jamie', '')
        observer = UiObservations(Mock())
        observer.call = Mock(return_value=(json.dumps(result).encode(), []))
        assert observer.observe('kiosk-language-jordan-jamie') == result
        ui.restart_usable('kiosk')
        result['request']['approver'] = 'other-fixture-parent'
        observer.call.return_value = (json.dumps(result).encode(), [])
        with pytest.raises(EvidenceError, match='ui:request'):
            observer.observe('kiosk-language-jordan-jamie')
    approver.setValue.assert_called_once_with('1000')


def journey(monkeypatch):
    transfer = Mock()
    transfer_factory = Mock(return_value=transfer)
    monkeypatch.setattr(package_journey, 'AssetTransfer', transfer_factory)
    context = SimpleNamespace(installed_snapshot=None, verified=Mock(), lease=Mock(), guestfs=Mock())
    result = package_journey.PackageJourney(context, Mock(), case.PLAN, checks=case.CHECKS)
    # Delivery belongs to the shared post-connection setup, not construction.
    transfer_factory.assert_called_once_with(context.verified)
    assert context.asset_transfer is transfer
    assert context.product_free is True
    return result


def test_installed_snapshot_refuses_before_transfer(monkeypatch):
    transfer = Mock()
    monkeypatch.setattr(package_journey, 'AssetTransfer', transfer)
    with pytest.raises(EvidenceError, match='product-free-required'):
        package_journey.PackageJourney(SimpleNamespace(installed_snapshot='onpc-v9.8.7'),
                                       Mock(), case.PLAN, checks=case.CHECKS)
    transfer.assert_not_called()


@pytest.mark.parametrize('fault', ['missing-result', 'unknown-stage', 'wrong-check', 'input-order'])
def test_invalid_package_composition_refuses_before_staging(monkeypatch, fault):
    from dataclasses import replace
    transfer = Mock()
    monkeypatch.setattr(package_journey, 'AssetTransfer', transfer)
    checks, plan = dict(case.CHECKS), case.PLAN
    if fault == 'missing-result':
        checks.pop('package-result')
    elif fault == 'unknown-stage':
        checks['nonexistent'] = checks['package-result']
    elif fault == 'wrong-check':
        checks['package-result'] = checks['app-rows']
    else:
        screens = dict(plan.screen_tags)
        screens['package-submitted'] = screens.pop('package-submitted')
        plan = replace(plan, screen_tags=screens)
    with pytest.raises(EvidenceError, match='package-plan'):
        package_journey.PackageJourney(SimpleNamespace(installed_snapshot=None),
                                       Mock(), plan, checks=checks)
    transfer.assert_not_called()


def test_package_envelope_accepts_an_independent_recipe_without_case_identity(monkeypatch):
    from dataclasses import replace
    transfer = Mock()
    monkeypatch.setattr(package_journey, 'AssetTransfer', Mock(return_value=transfer))
    plan = replace(case.PLAN, prefix='another-install', worker_mode='another_install')
    checks = dict(case.CHECKS)
    context = SimpleNamespace(installed_snapshot=None, verified=Mock(), lease=Mock(), guestfs=Mock())
    current = package_journey.PackageJourney(context, Mock(), plan, checks=checks)
    checks.clear()
    assert current.plan is plan and current.checks == case.CHECKS
    current.package = Mock()
    observed = {}
    current.check_settings('package-result', observed)
    assert observed['package'] == current.package.read_result.return_value


@pytest.mark.parametrize('stage', ['package-result', 'reboot-installed-greeter', 'app-rows'])
def test_failed_shared_check_latches_before_reply(tmp_path, monkeypatch, stage):
    current = journey(monkeypatch)
    current.context.directory = tmp_path
    current.steps = [{'stage': name} for name in case.PLAN.stages[:case.PLAN.stages.index(stage)]]
    current.vm = Mock()
    current.vm.read.return_value = {'boot_sha256': 'b' * 64}
    current.ui = Mock(boot_proof='b' * 64)
    current.ui.observe.return_value = {'operation': case.PLAN.screen_tags[stage][3:],
                                      'outcome': 'passed'}
    current.checks[stage] = Mock(side_effect=EvidenceError('required-result-missing'))
    current.reboot_submitted = True
    current.vm.wait_boot_change.return_value = {
        'previous_boot_sha256': None, 'boot_changed': True, 'boot_sha256': 'b' * 64}
    import installed_journey
    monkeypatch.setattr(installed_journey, 'UiObservations', Mock(return_value=current.ui))
    monkeypatch.setattr(installed_journey.session_control, 'observe', Mock(return_value={}))
    (tmp_path / (stage + '.request.json')).write_text(json.dumps({'stage': stage, 'screenshot': None}))
    with pytest.raises(EvidenceError, match='required-result-missing'):
        current.step(Mock())
    current.progress.assert_not_called()
    assert not (tmp_path / (stage + '.reply.json')).exists()
    with pytest.raises(EvidenceError, match='previous-failure'):
        current.step(Mock())
    current.checks[stage].assert_called_once()
