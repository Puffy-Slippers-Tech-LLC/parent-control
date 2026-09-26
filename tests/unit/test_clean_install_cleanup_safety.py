"""Case 2 must stop before acknowledging any incomplete customer result."""

import json
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

import accessible_ui as ui_module
import clean_install as case
import package_journey
from private_artifacts import EvidenceError
from tests.support.accessible_ui import Node, ui_for
from tests.support.desktop_session import RUN_PROBE
from tests.support.perl import run_perl


def journey(monkeypatch):
    transfer = Mock()
    monkeypatch.setattr(package_journey, 'AssetTransfer', Mock(return_value=transfer))
    context = SimpleNamespace(installed_snapshot=None, verified=Mock(), lease=Mock(), guestfs=Mock())
    result = package_journey.PackageJourney(context, Mock(), case.PLAN, checks=case.CHECKS)
    transfer.provision.assert_called_once_with(context.lease, context.guestfs)
    assert context.product_free is True
    return result


def test_installed_snapshot_refuses_before_transfer(monkeypatch):
    transfer = Mock()
    monkeypatch.setattr(package_journey, 'AssetTransfer', transfer)
    with pytest.raises(EvidenceError, match='product-free-required'):
        package_journey.PackageJourney(SimpleNamespace(installed_snapshot='onpc-v1.1'),
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


@pytest.mark.parametrize('fault', ['enabled', 'allowance', 'child', 'empty-apps', 'blocked-app'])
def test_customer_defaults_are_asserted_not_accepted_from_current_state(monkeypatch, fault):
    current = journey(monkeypatch)
    settings = {'child': 'fixture-child', 'limit_enabled': False, 'allowance': ['0 minutes']}
    if fault == 'enabled': settings['limit_enabled'] = True
    if fault == 'allowance': settings['allowance'] = ['1 minute']
    if fault == 'child': settings['child'] = 'fixture-existing'
    if fault in ('empty-apps', 'blocked-app'):
        rows = [] if fault == 'empty-apps' else [['parent-app-0123456789abcdef', 'permanent', 'precise']]
        stage, observed = 'app-rows', {'ui': {'apps': {'rows': rows}}}
    else:
        stage, observed = 'parent-selected', {'ui': {'settings': settings}}
    with pytest.raises(EvidenceError):
        current.check_settings(stage, observed)


def test_install_notice_and_preserved_accounts_are_independent_required_reads(monkeypatch):
    current = journey(monkeypatch)
    current.package = Mock()
    current.package.read_result.side_effect = EvidenceError('missing-final-notice')
    with pytest.raises(EvidenceError, match='missing-final-notice'):
        current.check_settings('package-result', {})
    current.ui = Mock()
    current.ui.observe.side_effect = EvidenceError('missing-personal-account')
    with pytest.raises(EvidenceError, match='missing-personal-account'):
        current.check_settings('reboot-installed-greeter', {})
    current.ui.observe.assert_called_once_with('gdm-installed-accounts')


@pytest.mark.parametrize('fault', ['', 'missing', 'duplicate', 'disabled', 'password', 'wrong-owner', 'incomplete'])
def test_complete_public_account_set_refuses_partial_or_unusable_choices(fault):
    names = (ui_module.PARENT, ui_module.OTHER_PARENT, ui_module.EXISTING_CHILD,
             ui_module.CHILD, ui_module.KIOSK)
    rows = [Node(name, role='push button') for name in names]
    if fault == 'missing': rows.pop()
    if fault == 'duplicate': rows.append(Node(names[0], role='push button'))
    if fault == 'disabled': rows[0].states.remove('sensitive')
    if fault == 'password': rows.append(Node(role='password text'))
    owner = Node('unrelated' if fault == 'wrong-owner' else 'gnome-shell',
                 role='application', children=rows)
    ui = ui_for(owner)
    desktop = Node(role='desktop', children=[owner])
    ui.api.get_desktop = lambda _: desktop
    for row in rows:
        row.component.grab_focus = Mock(side_effect=row.component.grab_focus)
    if fault == 'incomplete': owner.get_child_count = Mock(side_effect=LookupError())
    if fault:
        with pytest.raises((ui_module.UiError, LookupError)):
            ui.gdm_semantic_rows(names)
    else:
        _, observed = ui.gdm_semantic_rows(names)
        assert set(observed) == set(names)
        for row in rows:
            row.action.do_action.assert_not_called()
            row.component.grab_focus.assert_not_called()


@pytest.mark.parametrize('fault', ['', 'package-result', 'reboot-installed-greeter',
                                  'reboot-recipient-rechecked', 'app-rows', 'cancel-returned'])
def test_real_worker_stops_at_refusal_and_consumes_fresh_reboot_desktop(fault):
    source = RUN_PROBE.replace('require onpc_desktop_session;', 'require onpc_clean_install;')
    source = source.replace('onpc_desktop_session::run', 'onpc_clean_install::run')
    source = source.replace('}, $action);', "}, [qw(reboot-installed-greeter reboot-parent-focused "
        "reboot-recipient-qualified reboot-recipient-rechecked reboot-desktop)], "
        "{'after-reboot' => ['parent', 'reboot-recipient-qualified', 'reboot-recipient-rechecked']});")
    source = source.replace("push @events, ['stage', $_[0]];", """
        push @events, ['stage', $_[0]];
        die 'fixed refusal' if $_[0] eq $action;
        return {observed => $_[0], ui_focused => 1}
            if $_[0] =~ /(?:greeter|list|opened)$/;
        return {observed => $_[0], station_destination => 'default-request-form'}
            if $_[0] eq 'cancel-station-branch';
        return {observed => $_[0], challenge => {id => 'after-reboot', role => 'parent',
            surface => 'gdm', check => $_[0] =~ /rechecked$/ ? 'rechecked' : 'qualified'}}
            if $_[0] =~ /^reboot-recipient-/;
    """)
    result = json.loads(run_perl(source, fault).stdout)
    assert bool(result['ok']) == (not fault), result
    expected = list(case.PLAN.screen_tags)
    stages = [event[1] for event in result['events'] if event[0] == 'stage']
    assert stages == (expected[:expected.index(fault) + 1] if fault else expected)
    if not fault:
        assert result['events'].count(['secret']) == 2
        assert result['events'][-1] == ['power', 'off']
    assert not any(event[0] in ('pointer', 'click') for event in result['events'])
