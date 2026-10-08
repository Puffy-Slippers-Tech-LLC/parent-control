"""Case 2 must stop before acknowledging any incomplete customer result."""

import json
from types import SimpleNamespace
from unittest.mock import MagicMock, Mock

import pytest

import accessible_ui as ui_module
import clean_install as case
import package_journey
from private_artifacts import EvidenceError
from tests.support.accessible_ui import Node, ui_for
from tests.support.desktop_session import RUN_PROBE
from tests.support.perl import run_perl


@pytest.mark.parametrize('fault', ['', 'parent-notice', 'parent-close', 'parent-reentry',
                                  'reboot-requested', 'reboot-greeter', 'return-desktop', 'usable-parent'])
def test_parent_restart_actual_worker_order_titles_and_failure_stop(fault):
    import fresh_parent_restart as parent_case
    plan = parent_case.PLAN
    source = RUN_PROBE.replace('require onpc_desktop_session;', 'require onpc_customer_reboot;')
    source = source.replace('onpc_desktop_session::run', 'onpc_customer_reboot::run_parent_notice')
    declared = ','.join(repr(stage) for stage in plan.invocations)
    source = source.replace('}, $action);', '}, [' + declared + "], "
        "{'return' => ['parent', 'return-recipient-qualified', 'return-recipient-rechecked']});")
    source = source.replace('sub record_info { }', "sub record_info { push @main::events, ['title', $_[0]]; }")
    source = source.replace("push @events, ['stage', $_[0]];", """
        push @events, ['stage', $_[0]];
        die 'fixed refusal' if $_[0] eq $action;
        return {observed => $_[0], ui_focused => 1} if $_[0] =~ /(?:greeter|list)$/;
        return {observed => $_[0], challenge => {id => 'return', role => 'parent',
            surface => 'gdm', check => $_[0] =~ /rechecked$/ ? 'rechecked' : 'qualified'}}
            if $_[0] =~ /^return-recipient-/;
    """)
    result = json.loads(run_perl(source, fault).stdout)
    assert bool(result['ok']) == (not fault), result
    expected = list(plan.screen_tags)
    stages = [event[1] for event in result['events'] if event[0] == 'stage']
    assert stages == (expected[:expected.index(fault) + 1] if fault else expected)
    assert [event[1] for event in result['events'] if event[0] == 'title' and event[1] != 'shutdown'] == [
        plan.prefix + '-' + stage for stage in stages]
    assert not any(event[0] in ('pointer', 'click') for event in result['events'])
    if not fault:
        assert result['events'].count(['secret']) == 2
        assert [event for event in result['events'] if event[0] != 'title'][-1] == ['power', 'off']


@pytest.mark.parametrize('stage', ['parent-notice', 'parent-reentry', 'reboot-requested'])
@pytest.mark.parametrize('fault', ['', 'text', 'surface', 'modal', 'policy', 'missing'])
def test_parent_restart_literal_results_precede_reply_and_reboot(tmp_path, monkeypatch, stage, fault):
    import fresh_parent_restart as parent_case
    monkeypatch.setattr(package_journey, 'AssetTransfer', Mock())
    context = SimpleNamespace(directory=tmp_path, installed_snapshot=None,
        verified=Mock(), lease=Mock(), guestfs=Mock())
    current = package_journey.PackageJourney(context, Mock(), parent_case.PLAN, checks=parent_case.CHECKS)
    current.steps = [{'stage': name} for name in current.plan.stages[:current.plan.stages.index(stage)]]
    current.boot = 'a' * 64
    current.vm = Mock()
    current.vm.read.return_value = {'boot_sha256': current.boot}
    current.ui = Mock(boot_proof=current.boot)
    current.ui.submit_restart.return_value = {'surface': 'parent', 'status': 'acknowledged'}
    value = {'surface': 'parent', 'modal': True, 'policy_blocked': True, 'texts': {
        'update-required-message': 'Restart the computer for Oh No! Parent Control to work properly.',
        'update-required-close': 'Close', 'update-required-reboot': 'Reboot now'}}
    if fault == 'text': value['texts']['update-required-message'] = 'Update before opening the kiosk'
    if fault == 'surface': value['surface'] = 'kiosk'
    if fault == 'modal': value['modal'] = False
    if fault == 'policy': value['policy_blocked'] = False
    current.ui.observe.return_value = {} if fault == 'missing' else {'restart': value}
    (tmp_path / (stage + '.request.json')).write_text(json.dumps({'stage': stage, 'screenshot': None}))
    if fault:
        with pytest.raises(EvidenceError, match='installed-instructions'):
            current.step(Mock())
        assert not (tmp_path / (stage + '.reply.json')).exists()
        current.progress.assert_not_called()
        current.ui.submit_restart.assert_not_called()
        with pytest.raises(EvidenceError, match='previous-failure'): current.step(Mock())
    else:
        current.step(Mock())
        assert (tmp_path / (stage + '.reply.json')).is_file()
        assert current.ui.submit_restart.call_count == (stage == 'reboot-requested')
        if stage == 'reboot-requested':
            current.ui.submit_restart.assert_called_once_with('parent')
            assert json.loads((tmp_path / 'customer-reboot-intent.json').read_text())['surface'] == 'parent'


def test_parent_restart_real_recorder_constructs_package_envelope_before_worker(tmp_path, monkeypatch):
    import fresh_parent_restart as parent_case
    monkeypatch.setattr(package_journey, 'AssetTransfer', Mock())
    recorder = MagicMock()
    context = SimpleNamespace(directory=tmp_path, installed_snapshot=None, credentials=Mock(),
        verified=SimpleNamespace(inputs={}), lease=Mock(), guestfs=Mock(), commands=Mock())
    def worker(**options):
        current = options['guarded_observe'].__self__
        assert isinstance(current, package_journey.PackageJourney)
        assert current.plan is parent_case.PLAN and current.checks == parent_case.CHECKS
        assert set(current.actions) == {'install-package'}
        assert options['authenticate'] is True and options['timeout'] == 1800
        raise RuntimeError('synthetic-worker-start')
    context.run_worker = worker
    with pytest.raises(RuntimeError, match='synthetic-worker-start'):
        parent_case.execute(recorder, context)
    context.credentials.provision.assert_called_once()


def test_restart_instruction_oracle_is_immutable_and_validated():
    from journey_checks import restart_instructions
    texts = {'update-required-message': 'Install restart', 'update-required-close': 'Close',
             'update-required-reboot': 'Reboot now'}
    check = restart_instructions('parent', texts)
    texts['update-required-message'] = 'Changed oracle'
    observed = {'ui': {'restart': {'surface': 'parent', 'modal': True, 'policy_blocked': True,
        'texts': {**texts, 'update-required-message': 'Install restart'}}}}
    check(SimpleNamespace(plan=SimpleNamespace(prefix='another-recipe')), observed)
    for surface, value in (('wrong', texts), ('parent', {})):
        with pytest.raises(EvidenceError, match='comparison-plan'): restart_instructions(surface, value)


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
