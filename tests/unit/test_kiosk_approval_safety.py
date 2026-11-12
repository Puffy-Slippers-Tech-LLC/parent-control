"""Direct input guards for credentials and the bound child's applications."""
import json
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

import ui_observations
from private_artifacts import EvidenceError
from tests.support.perl import run_password_guard, run_perl


def test_management_parent_refuses_another_administrator(monkeypatch):
    module = ui_observations.accessible_ui
    lookup = Mock(return_value=SimpleNamespace(pw_uid=1234))
    monkeypatch.setattr(module.pwd, 'getpwnam', lookup)
    monkeypatch.setattr(module.os, 'getuid', lambda: 5678)
    with pytest.raises(module.UiError, match='ui:management-parent-owner'):
        module.require_management_owner('second-parent')
    lookup.assert_called_once_with('onpc-parent-casey')


def test_second_parent_challenge_requires_its_own_two_fresh_checks():
    ui = ui_observations.UiObservations(None)
    ui.observe = Mock(return_value={'recipient': True})
    challenge = {'id': 'sam-fresh', 'role': 'second-parent', 'surface': 'gdm', 'check': 'qualified'}
    ui.observe_challenge('gdm-second-parent-recipient', challenge)
    ui.observe_challenge('gdm-second-parent-recipient-rechecked', {**challenge, 'check': 'rechecked'})
    assert ui.observe.call_count == 2
    with pytest.raises(EvidenceError, match='ui:challenge-replay'):
        ui.observe_challenge('gdm-second-parent-recipient', challenge)
    assert ui.observe.call_count == 2


def test_second_parent_challenge_refuses_a_primary_parent_proof():
    ui = ui_observations.UiObservations(None)
    ui.observe = Mock(side_effect=AssertionError('wrong recipient reached guest'))
    with pytest.raises(EvidenceError, match='ui:challenge'):
        ui.observe_challenge('gdm-parent-recipient',
            {'id': 'sam-fresh', 'role': 'second-parent', 'surface': 'gdm', 'check': 'qualified'})
    ui.observe.assert_not_called()


@pytest.mark.parametrize('outside', ['product-modal', 'native-modal', 'product-focus'])
def test_lock_input_ignores_app_local_modality_but_refuses_competing_recipients(outside):
    import os
    module = ui_observations.accessible_ui

    class Node:
        def __init__(self, *, focused=False):
            self.focused = focused

        def get_process_id(self):
            return os.getpid()

        def get_parent(self):
            return root

    root, owner, window, hint = Node(), Node(), Node(focused=True), Node()
    other = Node(focused=outside == 'product-focus')
    if outside.startswith('product-'):
        other.ui_element = object()
    nodes = [root, owner, window, hint, other]
    edges = {root: [owner, other], owner: [window], window: [hint], hint: [], other: []}
    facts = {node: {'role': role, 'name': name, 'showing': True, 'modal': False}
             for node, role, name in (
                 (root, 'desktop', ''), (owner, 'application', 'gnome-shell'),
                 (window, 'window', ''),
                 (hint, 'label', 'Click or press a key to unlock'),
                 (other, 'window', ''))}
    facts[other]['modal'] = outside != 'product-focus'
    states = SimpleNamespace(DEFUNCT='defunct', FOCUSED='focused')
    ui = module.AccessibleUI(SimpleNamespace(StateType=states, get_desktop=lambda index: root))
    ui.require_lock_session = Mock(return_value='same-locked-session')
    ui.has_state = lambda node, state: state == 'focused' and node.focused
    observation = (nodes, edges, {}, facts)
    if outside == 'product-modal':
        assert ui.shell_lock_snapshot(os.getuid(), 'curtain', observation=observation)[:3] == (
            owner, window, None)
        assert ui.require_lock_session.call_count == 2
    else:
        with pytest.raises(module.UiError, match='ui:lock-other-surface'):
            ui.shell_lock_snapshot(os.getuid(), 'curtain', observation=observation)


@pytest.mark.parametrize('child', ['child', 'existing'])
def test_expiry_lock_binding_refuses_another_account_before_session_read(monkeypatch, child):
    module = ui_observations.accessible_ui
    child = module.CHILD if child == 'child' else module.EXISTING_CHILD
    ui = object.__new__(module.AccessibleUI)
    ui.lock_role, ui.lock_child = 'child', child
    monkeypatch.setattr(module.pwd, 'getpwnam', lambda name: SimpleNamespace(pw_uid=1234))
    monkeypatch.setattr(module.os, 'getuid', lambda: 5678)
    sessions = Mock(side_effect=AssertionError('wrong account reached session discovery'))
    monkeypatch.setattr(module.session_control, 'sessions', sessions)
    with pytest.raises(module.UiError, match='ui:lock-session'):
        ui.require_lock_session(5678)
    sessions.assert_not_called()


@pytest.mark.parametrize('fault', ['none', 'recipient', 'request'])
def test_german_native_prompt_still_binds_parent_and_request(fault):
    module = ui_observations.accessible_ui

    class Node:
        def get_process_id(self):
            return 123

        def get_text_iface(self):
            return self

    owner, dialog, field, recipient, message, cancel = [Node() for _ in range(6)]
    nodes = [owner, dialog, field, recipient, message, cancel]
    edges = {node: [] for node in nodes}
    edges[owner], edges[dialog] = [dialog], nodes[2:]
    # Independent native v1.26.1 German catalogue and product message inputs.
    facts = {node: {'role': role, 'name': name, 'showing': True}
             for node, role, name in (
                 (owner, 'application', 'mate-polkit'), (dialog, 'dialog', ''),
                 (field, 'password text', ''),
                 (recipient, 'label', 'Passwort für onpc-parent-jamie:'),
                 (message, 'label', 'Zugriff für Riley (Child) gewähren\nfür 4 Minuten\n\n'
                                   '✓ Vorübergehend freigebbare Apps erlaubt'),
                 (cancel, 'push button', 'Abbrechen'))}
    if fault == 'recipient':
        facts[recipient]['name'] = 'Passwort für onpc-parent-casey:'
    elif fault == 'request':
        facts[message]['name'] = facts[message]['name'].replace('4 Minuten', '10 Minuten')
    states = SimpleNamespace(DEFUNCT='defunct', SENSITIVE='sensitive', FOCUSED='focused')
    api = SimpleNamespace(StateType=states,
                          Text=SimpleNamespace(get_character_count=lambda node: 0))
    ui = module.AccessibleUI(api)
    ui.kiosk_request = ('child', 'parent', 240, True)
    ui.system_prompt_kind = Mock(return_value='mate-polkit')
    ui.mate_provider_metadata = Mock(return_value={'version': '1.26.1-4'})
    ui.has_state = lambda node, state: state in ('sensitive', 'focused')
    request = module.kiosk_request_facts(ui.kiosk_request)
    options = dict(observation=(nodes, edges, {}, facts), language='de', request=request)
    if fault == 'none':
        assert ui.mate_prompt(123, **options) == (owner, dialog, field, cancel)
    else:
        with pytest.raises(module.UiError, match='ui:mate-' + fault + '-context-missing'):
            ui.mate_prompt(123, **options)


@pytest.mark.parametrize('fault', ['none', 'fullscreen', 'saved-work', 'saved-work-recovery',
                                  'wrong-child', 'wrong-scope', 'replay',
                                  'reminder', 'reminder-wrong-child'])
def test_game_approval_secret_stays_bound_to_its_request(fault):
    result = run_password_guard(r'''
my $fault = shift @ARGV;
my $journey = bless {prefix => 'game-expiry-request', stage_prefix => 'request-',
    kiosk_request => ['other-child', 'parent', 600, 1], review => 0}, 'onpc_journey';
$journey->{prefix} = 'game-fullscreen-request' if $fault eq 'fullscreen';
if ($fault =~ /\Areminder/) {
    $journey->{prefix} = 'reminder-notifications-first';
    $journey->{stage_prefix} = 'first-';
    $journey->{kiosk_request} = [$fault eq 'reminder' ? 'child' : 'other-child', 'parent', 240, 1];
}
if ($fault eq 'saved-work' || $fault eq 'saved-work-recovery') {
    my $scope = $fault eq 'saved-work' ? 'request' : 'recovery';
    $journey->{prefix} = 'repeated-saved-work-' . $scope;
    $journey->{stage_prefix} = $scope . '-';
    $journey->{kiosk_request}[2] = 1200 if $scope eq 'recovery';
}
$journey->{kiosk_request}[0] = 'child' if $fault eq 'wrong-child';
$journey->{stage_prefix} = 'other-' if $fault eq 'wrong-scope';
my $ok = eval {
    onpc_password::enter_kiosk_mate_password($journey, 'bound-request');
    onpc_password::enter_kiosk_mate_password($journey, 'bound-request') if $fault eq 'replay';
    1;
};
print encode_json({ok => $ok ? 1 : 0, events => \@events});
''', fault)
    value = json.loads(result.stdout)
    assert value['ok'] == (fault in ('none', 'fullscreen', 'reminder', 'saved-work', 'saved-work-recovery'))
    scope = 'first' if fault == 'reminder' else 'recovery' if fault == 'saved-work-recovery' else 'request'
    expected = [] if fault in ('wrong-child', 'wrong-scope', 'reminder-wrong-child') else [
        ['proof', scope + '-approval-qualified'], ['proof', scope + '-approval-rechecked'],
        ['delivery', 'parent', scope + '-kiosk-mate-approval']]
    assert value['events'] == expected


@pytest.mark.parametrize('child', ['child', 'existing'])
def test_game_input_refuses_another_account_before_window_discovery(monkeypatch, child):
    module = ui_observations.accessible_ui
    ui = object.__new__(module.AccessibleUI)
    ui.native_app_snapshot = Mock(side_effect=AssertionError('wrong child reached window discovery'))
    monkeypatch.setattr(module.pwd, 'getpwnam', lambda name: SimpleNamespace(pw_uid=1234))
    monkeypatch.setattr(module.os, 'getuid', lambda: 5678)
    monkeypatch.setattr(module.os, 'geteuid', lambda: 5678)
    with pytest.raises(module.UiError, match='ui:game-account'):
        ui.game_operation('game-move', child=module.NAMED_CUSTOM_CHILDREN[child])
    ui.native_app_snapshot.assert_not_called()


@pytest.mark.parametrize(('surface', 'fault'), [
    ('kiosk', 'none'), ('overlay', 'none'), ('overlay', 'scope'),
    ('kiosk', 'request'), ('overlay', 'replay'), ('overlay', 'retained')])
def test_game_permission_secret_requires_exact_scope_and_single_use(surface, fault):
    result = run_password_guard(r'''
my ($surface, $fault) = @ARGV;
my $row = $fault eq 'retained' ? 'first' : $surface eq 'kiosk' ? 'included' : 'excluded';
my $scope = "fullscreen-$row-";
my $family = $fault eq 'retained' ? 'retained-game-denial' : 'game-permission';
my $journey = bless {prefix => "$family-fullscreen-$row", stage_prefix => $scope,
    review => 0}, 'onpc_journey';
$journey->{$surface eq 'kiosk' ? 'kiosk_request' : 'overlay_request'} =
    ['other-child', 'parent', 900, $surface eq 'kiosk' || $fault eq 'retained' ? 1 : 0];
$journey->{stage_prefix} = "windowed-$row-" if $fault eq 'scope';
$journey->{kiosk_request}[0] = 'child' if $fault eq 'request';
my $enter = sub {
    $surface eq 'kiosk' ? onpc_password::enter_kiosk_mate_password($journey, 'bound-request')
                       : onpc_password::enter_overlay_shell_password($journey);
};
my $ok = eval { $enter->(); $enter->() if $fault eq 'replay'; 1 };
print encode_json({ok => $ok ? 1 : 0, events => \@events});
''', surface, fault)
    value = json.loads(result.stdout)
    assert value['ok'] == (fault in ('none', 'retained'))
    scope = 'fullscreen-' + ('first-' if fault == 'retained' else
                              'included-' if surface == 'kiosk' else 'excluded-')
    assert value['events'] == ([] if fault in ('scope', 'request') else [
        ['proof', scope + 'approval-qualified'], ['proof', scope + 'approval-rechecked'],
        ['delivery', 'parent', scope + ('kiosk-mate-approval' if surface == 'kiosk'
                                       else 'overlay-shell-approval')]])


@pytest.mark.parametrize('surface,fault', [
    ('overlay', 'none'), ('kiosk', 'none'), ('kiosk', 'child'),
    ('overlay', 'scope'), ('kiosk', 'parent'), ('overlay', 'replay')])
def test_homework_approval_keeps_its_declared_recipient_and_scope(surface, fault):
    result = run_password_guard(r'''
my ($surface, $fault) = @ARGV;
my $row = $surface eq 'kiosk' ? 'recovery' : 'home';
my $scope = "cycle-2-$row-";
my $journey = bless {prefix => "homework-game-cycle-2-$row", stage_prefix => $scope,
    review => 0}, 'onpc_journey';
$journey->{$surface eq 'kiosk' ? 'kiosk_request' : 'overlay_request'} =
    ['other-child', $surface eq 'kiosk' ? 'parent' : 'other-parent',
     $surface eq 'kiosk' ? 1200 : 30, $surface eq 'kiosk' ? 1 : 0];
$journey->{kiosk_request}[0] = 'child' if $fault eq 'child';
$journey->{kiosk_request}[1] = 'other-parent' if $fault eq 'parent';
$journey->{stage_prefix} = 'cycle-1-home-' if $fault eq 'scope';
my $enter = sub {
    $surface eq 'kiosk' ? onpc_password::enter_kiosk_mate_password($journey, 'bound-request')
                       : onpc_password::enter_overlay_shell_password($journey);
};
my $ok = eval { $enter->(); $enter->() if $fault eq 'replay'; 1 };
print encode_json({ok => $ok ? 1 : 0, events => \@events});
''', surface, fault)
    value = json.loads(result.stdout)
    assert value['ok'] == (fault == 'none')
    scope = 'cycle-2-' + ('recovery-' if surface == 'kiosk' else 'home-')
    assert value['events'] == ([] if fault in ('child', 'parent', 'scope') else [
        ['proof', scope + 'approval-qualified'], ['proof', scope + 'approval-rechecked'],
        ['delivery', 'parent' if surface == 'kiosk' else 'other-parent',
         scope + ('kiosk-mate-approval' if surface == 'kiosk' else 'overlay-shell-approval')]])


@pytest.mark.parametrize('operation', ['reminder', 'panel-target', 'panel-launch', 'panel-form'])
def test_reminder_overlay_wrong_account_refuses_before_discovery(monkeypatch, operation):
    module = ui_observations.accessible_ui
    ui = object.__new__(module.AccessibleUI)
    ui.input_uncertain = False
    ui.read_snapshot = Mock(side_effect=AssertionError('UI read on another child account'))
    ui.id_target = Mock(side_effect=AssertionError('target discovery on another child account'))
    ui._invoke_target = Mock(side_effect=AssertionError('input on another child account'))
    monkeypatch.setattr(module.pwd, 'getpwnam', lambda name: SimpleNamespace(pw_uid=1002))
    monkeypatch.setattr(module.os, 'getuid', lambda: 1001)
    monkeypatch.setattr(module.os, 'geteuid', lambda: 1001)
    with pytest.raises(module.UiError, match='ui:overlay-account'):
        if operation == 'reminder':
            ui.overlay_reminder_open(child=module.EXISTING_CHILD)
        elif operation == 'panel-target':
            ui.overlay_panel_target(child=module.EXISTING_CHILD)
        elif operation == 'panel-launch':
            ui.overlay_panel_launch(child=module.EXISTING_CHILD)
        else:
            ui.overlay_panel_form_present(child=module.EXISTING_CHILD)
    ui.read_snapshot.assert_not_called()
    ui.id_target.assert_not_called()
    ui._invoke_target.assert_not_called()


@pytest.mark.parametrize('boundary', ['entry', 'child'])
def test_preset_input_refuses_wrong_entry_or_selected_child(boundary):
    module = ui_observations.accessible_ui
    ui = module.AccessibleUI(SimpleNamespace())
    ui.read_snapshot = Mock(return_value=([], {}, {}, {}))
    ui.request_surface = Mock(side_effect=module.UiError('ui:kiosk-valid-entry')
                              if boundary == 'entry' else None)
    ui.initial_kiosk_child = Mock(side_effect=module.UiError('ui:initial-child'))
    ui.open_language_preferences = Mock(side_effect=AssertionError('input after wrong entry'))
    with pytest.raises(module.UiError, match='ui:' + (
            'kiosk-valid-entry' if boundary == 'entry' else 'initial-child')):
        ui.kiosk_presets_open()
    ui.open_language_preferences.assert_not_called()
    assert ui.input_uncertain is True


def test_preset_replaced_dialog_cannot_release_input():
    module = ui_observations.accessible_ui
    ui = module.AccessibleUI(SimpleNamespace())
    ui._kiosk_preferences_state = Mock(side_effect=module.UiError('ui:preferences-replaced'))
    ui.activate_id = Mock(side_effect=AssertionError('input after replaced draft'))
    with pytest.raises(module.UiError, match='ui:preferences-replaced'):
        ui.kiosk_preset_change(instance='a' * 32, seconds=600)
    with pytest.raises(module.UiError, match='ui:uncertain-input'):
        ui.kiosk_presets_close(instance='a' * 32, save=True)
    ui.activate_id.assert_not_called()


def test_reminder_uncertain_deletion_cannot_release_another_input():
    module = ui_observations.accessible_ui
    ui = module.AccessibleUI(SimpleNamespace())
    ui._overlay_reminder_state = Mock(side_effect=module.UiError('ui:reminder-stale-draft'))
    ui._invoke_target = Mock(side_effect=AssertionError('input released after failed draft proof'))
    with pytest.raises(module.UiError, match='ui:reminder-stale-draft'):
        ui.overlay_reminder_delete('saved-record', expected_source='a' * 64, surface='kiosk')
    assert ui.input_uncertain is True
    with pytest.raises(module.UiError, match='ui:uncertain-input'):
        ui.overlay_reminder_commit(save=True, surface='kiosk')
    ui._overlay_reminder_state.assert_called_once_with(
        source='a' * 64, surface='kiosk', child=module.CHILD)
    ui._invoke_target.assert_not_called()


def test_reminder_mutation_requires_a_prior_draft_and_stops_after_refusal():
    ui = ui_observations.UiObservations(None)
    ui.call = Mock(side_effect=AssertionError('guest input without prior draft receipt'))
    with pytest.raises(EvidenceError, match='ui:reminder-source-required'):
        ui.observe('binding-reminder-riley-delete')
    with pytest.raises(EvidenceError, match='ui:language-previous-failure'):
        ui.observe('binding-reminder-riley-open')
    ui.call.assert_not_called()


@pytest.mark.parametrize('role,instance', [('H', 'primary'), ('A', 'hard')])
def test_flatpak_cross_app_instance_refuses_before_session_or_launch(monkeypatch, role, instance):
    module = ui_observations.accessible_ui
    ui = object.__new__(module.AccessibleUI)
    ui.input_uncertain = False
    session = Mock(side_effect=AssertionError('session read after conclusive binding refusal'))
    launch = Mock(side_effect=AssertionError('command released for another app identity'))
    monkeypatch.setattr(module, 'require_active_launch_session', session)
    monkeypatch.setattr(module.subprocess, 'run', launch)
    with pytest.raises(module.UiError, match='ui:native-binding'):
        ui.native_launch_command(instance, role=role, child=module.EXISTING_CHILD, kind='flatpak')
    session.assert_not_called()
    launch.assert_not_called()


def test_privileged_fixture_password_uses_authenticated_callers_private_file(tmp_path, monkeypatch):
    import test_account_password as password
    uid = tmp_path.stat().st_uid
    config = tmp_path / '.onpc-config'
    config.mkdir()
    source = config / '.envrc'
    source.write_text("TEST_ACCOUNT_PASSWORD='fixture-only-canary'\n")
    source.chmod(0o600)
    monkeypatch.setattr(password.os, 'getuid', lambda: 0)
    monkeypatch.setenv('PKEXEC_UID', str(uid))
    lookup = Mock(return_value=SimpleNamespace(pw_dir=str(tmp_path)))
    monkeypatch.setattr(password.pwd, 'getpwuid', lookup)
    assert password.read_password() == 'fixture-only-canary'
    lookup.assert_called_once_with(uid)
    monkeypatch.setenv('PKEXEC_UID', str(uid + 1))
    with pytest.raises(ValueError, match='caller-owned regular file'):
        password.read_password()


@pytest.mark.parametrize('caller', ['', '0', '-1', 'invalid'])
def test_privileged_fixture_password_refuses_missing_caller_before_open(monkeypatch, caller):
    import test_account_password as password
    monkeypatch.setattr(password.os, 'getuid', lambda: 0)
    monkeypatch.setenv('PKEXEC_UID', caller)
    opened = Mock(side_effect=AssertionError('credential opened without authenticated caller'))
    monkeypatch.setattr(password.os, 'open', opened)
    with pytest.raises(ValueError, match='caller-owned regular file'):
        password.read_password()
    opened.assert_not_called()


@pytest.mark.parametrize('operation,previous,last_child,error', [
    ('gdm-child-time-denied', 'gdm-child-recipient-rechecked', 'child', 'denial-order'),
    ('gdm-child-denied-return-ready', 'gdm-child-time-denied', 'child', 'denial-child-changed'),
])
def test_named_gdm_denial_cannot_authorize_return_for_another_child(
        operation, previous, last_child, error):
    ui = ui_observations.UiObservations(None)
    ui.last_operation = previous
    ui.last_child = last_child
    ui.call = Mock(side_effect=AssertionError('guest observation after conclusive refusal'))
    with pytest.raises(EvidenceError, match=error):
        ui._observe(operation, child='existing')
    ui.call.assert_not_called()


def test_bound_prompt_wait_and_repeat_still_require_fresh_recipient_proofs(monkeypatch):
    clock = [100.0]
    monkeypatch.setattr(ui_observations.time, 'monotonic', lambda: clock[0])
    ui = ui_observations.UiObservations(None)
    ui.kiosk_request = ('child', 'parent', 30, False)
    ui._observe = Mock(return_value={})
    order = ui_observations.accessible_ui.BOUND_MATE_ORDER
    ui.observe(order[0])
    clock[0] += 45
    ui.observe(order[1])
    clock[0] += 1
    ui.observe(order[2])
    ui.observe(order[3])
    ui.observe('kiosk-request-estimate')
    ui.observe(order[0])
    ui.observe(order[1])
    clock[0] += 31
    calls = ui._observe.call_count
    with pytest.raises(EvidenceError, match='mate-stale-proof'):
        ui.observe(order[2])
    assert ui._observe.call_count == calls
    with pytest.raises(EvidenceError, match='challenge-previous-failure'):
        ui.observe(order[2])
    assert ui._observe.call_count == calls


def test_bound_prompt_refuses_changed_request_before_another_recipient_read():
    ui = ui_observations.UiObservations(None)
    ui.kiosk_request = ('other-child', 'parent', 30, False)
    ui._observe = Mock(return_value={})
    order = ui_observations.accessible_ui.BOUND_MATE_ORDER
    ui.observe(order[0])
    ui.kiosk_request = ('other-child', 'other-parent', 30, True)
    with pytest.raises(EvidenceError, match='mate-request-replaced'):
        ui.observe(order[1])
    assert ui._observe.call_count == 1


def test_agent_loss_ends_only_an_unqualified_challenge_without_releasing_input():
    ui = ui_observations.UiObservations(None)
    ui._observe = Mock(return_value={})
    ui.challenges.add('lost-challenge')
    ui.observe('kiosk-mate-open')
    ui.observe('kiosk-agent-refused')
    assert ui.mate_approval_index == 0
    assert ui.mate_approval_identity is None
    assert ui.challenges == {'lost-challenge'}
    calls = ui._observe.call_count
    with pytest.raises(EvidenceError, match='mate-order'):
        ui.observe('kiosk-mate-qualified')
    assert ui._observe.call_count == calls

    ui = ui_observations.UiObservations(None)
    ui._observe = Mock(return_value={})
    ui.observe('kiosk-mate-open')
    ui.observe('kiosk-mate-qualified')
    with pytest.raises(EvidenceError, match='mate-agent-loss-order'):
        ui.observe('kiosk-agent-refused')
    assert ui._observe.call_count == 2
    with pytest.raises(EvidenceError, match='challenge-previous-failure'):
        ui.observe('kiosk-mate-rechecked')
    assert ui._observe.call_count == 2


@pytest.mark.parametrize('prefix,scope,seconds,soft,accepted', [
    ('daily-soft-profile-profile-request', 'profile-request-', 6, 1, True),
    ('daily-soft-profile-profile-request', 'request-', 6, 1, False),
    ('kiosk-fresh-return', '', 6, 1, False),
    ('ordinary-rest-of-day-request', 'request-', 0, 0, True),
    ('ordinary-rest-of-day-request', 'other-', 0, 0, False),
    ('ordinary-fixed-grant-request', 'request-', 1200, 0, True),
    ('ordinary-fixed-grant-request', 'other-', 1200, 0, False),
    ('ordinary-fixed-grant-request', 'request-', 0, 0, False),
    ('kiosk-fresh-return', '', 0, 0, False),
    ('spring-forward-paired-grants-riley-request', 'riley-request-', 600, 0, True),
    ('fall-back-paired-grants-jordan-request', 'jordan-request-', 0, 0, True),
    ('fall-back-paired-grants-riley-request', 'riley-request-', 600, 0, True),
    ('fall-back-paired-grants-jordan-request', 'riley-request-', 0, 0, False),
    ('fall-back-paired-grants-riley-request', 'riley-request-', 0, 0, False),
])
def test_short_and_calendar_approvals_keep_their_declared_secret_scope(prefix, scope, seconds, soft, accepted):
    result = run_password_guard(r'''
my ($prefix, $scope, $seconds, $soft) = @ARGV;
my $child = $prefix =~ /-jordan-request\z/ ? 'other-child' : 'child';
my $journey = bless {prefix => $prefix, stage_prefix => $scope, review => 0,
    kiosk_request => [$child, 'parent', $seconds, $soft]}, 'onpc_journey';
my $ok = eval { onpc_password::enter_kiosk_mate_password($journey, 'bound-request'); 1 };
print encode_json({ok => $ok ? 1 : 0, events => \@events});
''', prefix, scope, str(seconds), str(soft))
    value = json.loads(result.stdout)
    assert value['ok'] == accepted
    assert value['events'] == ([
        ['proof', scope + 'approval-qualified'],
        ['proof', scope + 'approval-rechecked'],
        ['delivery', 'parent', scope + 'kiosk-mate-approval'],
    ] if accepted else [])


@pytest.mark.parametrize('mode,surface,kind', [
    (mode, surface, 'flatpak') for surface in ('kiosk', 'overlay')
    for mode in ('sequence', 'wrong-scope', 'crossed-request', 'replay')
] + [('sequence', 'overlay', 'native-desktop'), ('wrong-duration', 'overlay', 'native'),
     ('sequence', 'kiosk', 'native'), ('wrong-duration', 'kiosk', 'native'),
     ('sequence', 'kiosk', 'native-command'), ('sequence', 'kiosk', 'native-files')])
def test_temporary_access_secret_binds_each_parent_and_requires_fresh_proofs(mode, surface, kind):
    # Exercise the password guard with finite request inputs. Importing the
    # complete customer case makes this safety test depend on unrelated plans.
    seconds = 30 if kind.startswith('native') else 300
    requests = {'first': ('other-child', 'parent', seconds, False),
                'included': ('other-child', 'other-parent', seconds, True),
                'replacement': ('other-child', 'parent', seconds, False)}
    prefix = (kind + '-kiosk-temporary-access' if kind in ('native-command', 'native-files') else
              'native-desktop-temporary-access' if kind == 'native-desktop' else
              'native-grid-kiosk-temporary-access' if (kind, surface) == ('native', 'kiosk') else
              kind + ('-temporary-access' if surface == 'kiosk' else '-grid-temporary-access'))
    result = run_password_guard(r'''
my ($mode, $prefix, $encoded, $surface) = @ARGV;
my $requests = decode_json($encoded);
my $binding_key = $surface eq 'kiosk' ? 'kiosk_request' : 'overlay_request';
my $enter = sub {
    $surface eq 'kiosk' ? onpc_password::enter_kiosk_mate_password($_[0], 'bound-request')
                       : onpc_password::enter_overlay_shell_password($_[0]);
};
my $ok = eval {
    for my $name ('first', 'included', 'replacement') {
        my $request = bless {prefix => "$prefix-$name", stage_prefix => "$name-",
            $binding_key => [@{$requests->{$name}}], review => 0}, 'onpc_journey';
        $request->{stage_prefix} = 'included-' if $mode eq 'wrong-scope';
        $request->{$binding_key} = $requests->{included} if $mode eq 'crossed-request';
        $request->{$binding_key}[2] = 300 if $mode eq 'wrong-duration';
        $enter->($request);
        $enter->($request) if $mode eq 'replay';
    }
    1;
};
print encode_json({ok => $ok ? 1 : 0, events => \@events});
''', mode, prefix, json.dumps({name: [*binding[:3], int(binding[3])]
                             for name, binding in requests.items()}), surface)
    value = json.loads(result.stdout)
    names = list(requests) if mode == 'sequence' else ['first'] if mode == 'replay' else []
    assert value['ok'] == (mode == 'sequence')
    assert value['events'] == [event for name in names for event in (
        ['proof', name + '-approval-qualified'], ['proof', name + '-approval-rechecked'],
        ['delivery', requests[name][1], name + ('-kiosk-mate-approval' if surface == 'kiosk'
                                               else '-overlay-shell-approval')])]


@pytest.mark.parametrize('action', ['cancel', 'lock', 'switch-user', 'close'])
def test_shell_interruption_proof_requires_the_bound_request_and_a_new_challenge(action):
    operation = 'overlay-shell-' + action + '-ready'
    proof = {'child': 'fixture-child', 'approver': 'fixture-parent',
             'duration_seconds': 30, 'allow_soft': False, action + '_ready': True,
             'same_challenge_rechecked': True,
             'rejected_proofs': list(ui_observations.accessible_ui.SHELL_PROMPT_REFUSALS),
             'provider': {'version': '50.0', 'locale': 'en_US.UTF-8',
                          'keyboard': [['xkb', 'us']]}, 'challenge_id': 'a' * 64}

    def observer(value):
        ui = ui_observations.UiObservations(None)
        ui.overlay_request = ('child', 'parent', 30, False)
        response = {'operation': operation, 'outcome': 'passed',
                    'interface': 'ApplicationUI+external-provider',
                    'boot_sha256': 'b' * 64, 'shell_prompt': value}
        ui.call = Mock(return_value=(json.dumps(response).encode(), []))
        return ui

    ui = observer(proof)
    assert ui.observe(operation)['shell_prompt'] == proof
    argv = ui.call.call_args.args[0]
    assert json.loads(argv[argv.index('--overlay-request') + 1]) == list(ui.overlay_request)
    with pytest.raises(EvidenceError, match='challenge-replay'):
        ui.observe(operation)

    wrong = observer({**proof, 'duration_seconds': 75, 'allow_soft': True})
    with pytest.raises(EvidenceError, match='shell-response'):
        wrong.observe(operation)
    calls = wrong.call.call_count
    with pytest.raises(EvidenceError, match='challenge-previous-failure'):
        wrong.observe(operation)
    assert wrong.call.call_count == calls


@pytest.mark.parametrize('action', ['lock', 'switch', 'signout', 'close'])
def test_pending_approval_refusal_prevents_session_input_and_replay(action):
    result = run_perl(r'''
use strict;
use warnings;
use JSON::PP;
our @events;
BEGIN { $INC{'testapi.pm'} = 1; }
package testapi;
sub record_info { }
sub send_key { die 'unexpected keyboard input'; }
package main;
require onpc_request_flow;
my $action = shift @ARGV;
my $interrupt = $action eq 'close' ? \&onpc_request_flow::overlay_close
               : $action eq 'lock' ? \&onpc_request_flow::overlay_lock
                                 : \&onpc_request_flow::overlay_switch;
my $journey = onpc_journey->new(prefix => 'pending-overlay-lock', review => 0,
    exchange => sub { push @events, $_[0]; die 'fixture:prompt-refused'; });
my @entry = $action eq 'signout' ? ('fresh') : ();
my $first = eval { $interrupt->($journey, 'interruption', @entry); 1; };
my $first_error = "$@";
my $second = eval { $interrupt->($journey, 'interruption', @entry); 1; };
print encode_json({first => $first ? 1 : 0, second => $second ? 1 : 0,
    first_error => $first_error, second_error => "$@", events => \@events});
''', action)
    value = json.loads(result.stdout)
    assert not value['first'] and not value['second']
    assert 'fixture:prompt-refused' in value['first_error']
    assert 'pending-' + ('switch' if action == 'signout' else action) + ':replay' in value['second_error']
    assert value['events'] == ['interruption-pending-approval']


@pytest.mark.parametrize('identity', ['a' * 64, 'b' * 64])
@pytest.mark.parametrize('provider', ['shell', 'mate'])
def test_pending_close_rechecks_the_same_prompt_before_the_owned_surface(monkeypatch, identity, provider):
    module = ui_observations.accessible_ui
    ui = module.AccessibleUI.__new__(module.AccessibleUI)
    ui.input_uncertain = False
    ui.overlay_bound_values = Mock(return_value=(module.CHILD, module.PARENT, 75, True))
    ui.require_child_overlay_session = Mock()
    ui.invalidate_observation = Mock()
    ui.read_snapshot = Mock(return_value=object())
    ui.shell_prompt_owner = Mock(return_value=SimpleNamespace(get_process_id=lambda: 123))
    ui.shell_prompt = Mock(return_value=object())
    ui.mate_agent_pid = Mock(return_value=123)
    ui.mate_prompt = Mock(return_value=object())
    monkeypatch.setattr(module.pwd, 'getpwnam', lambda name: SimpleNamespace(pw_uid=1234))
    monkeypatch.setattr(module.os, 'getuid', lambda: 1234)
    session = Mock()
    monkeypatch.setattr(module, 'require_active_launch_session', session)
    ui.mate_challenge_identity = Mock(return_value=identity)
    target = Mock()
    ui.snapshot_owned_target = Mock(return_value=target)
    ui.surface_available = Mock(return_value=True)
    binding = {f'pending_{provider}_challenge': 'a' * 64}
    if identity == 'a' * 64:
        ui.close_id('kiosk-request-window', **binding)
        target.close.assert_called_once_with()
        if provider == 'shell':
            ui.require_child_overlay_session.assert_called_once_with(module.CHILD)
        else:
            session.assert_called_once_with()
    else:
        with pytest.raises(module.UiError, match='pending-close-challenge'):
            ui.close_id('kiosk-request-window', **binding)
        ui.snapshot_owned_target.assert_not_called()
        target.close.assert_not_called()


@pytest.mark.parametrize('surface', ['overlay', 'kiosk'])
def test_pending_close_proof_is_consumed_before_an_uncertain_dispatch(surface):
    ui = ui_observations.UiObservations(None)
    if surface == 'overlay':
        ui.last_operation = 'overlay-shell-close-ready'
        ui.pending_close_challenge = 'a' * 64
    else:
        ui.last_operation = 'kiosk-mate-rechecked'
        ui.mate_approval_index = 3
        ui.mate_request_binding = ui.kiosk_request
        ui.mate_approval_identity = 'a' * 64
        ui.mate_approval_checked = ui_observations.time.monotonic()
    ui.boot_guard = 'b' * 64
    ui.call = Mock(side_effect=RuntimeError('fixture:lost-reply'))
    with pytest.raises(RuntimeError, match='lost-reply'):
        ui.observe(surface + '-pending-close')
    argv = ui.call.call_args.args[0]
    assert argv[-2:] == ['b' * 64, 'a' * 64]
    with pytest.raises(EvidenceError, match='pending-(?:station-)?close-order'):
        ui.observe(surface + '-pending-close')
    assert ui.call.call_count == 1


def test_pending_overlay_entry_refuses_another_account_before_observation():
    result = run_perl(r'''
use strict;
use warnings;
use JSON::PP;
our @events;
BEGIN { $INC{'testapi.pm'} = 1; }
package testapi;
sub record_info { }
package main;
require onpc_desktop_session;
my $journey = onpc_journey->new(prefix => 'pending-overlay-switch', review => 0,
    exchange => sub { push @events, $_[0]; die 'unexpected observation'; });
my $ok = eval {
    onpc_desktop_session::enter_desktop($journey, 'pending-overlay', 'other-child',
        'retained', 'success', 'interruption');
    1;
};
print encode_json({ok => $ok ? 1 : 0, error => "$@", events => \@events});
''')
    value = json.loads(result.stdout)
    assert not value['ok'] and 'desk:entry-binding' in value['error']
    assert value['events'] == []


@pytest.mark.parametrize('mode', ['sequence', 'wrong-scope', 'replay'])
def test_cross_surface_approval_keeps_separate_single_use_credentials(mode):
    # The mixed-surface owner is new; both providers must consume their own
    # fresh proofs. Exercise the real guard with no password or customer plan.
    result = run_password_guard(r'''
my $mode = shift @ARGV;
my $overlay = bless {prefix => 'offline-approvals-overlay', stage_prefix => 'overlay-',
    overlay_request => ['child', 'parent', 180, 1], review => 0}, 'onpc_journey';
my $station = bless {prefix => 'offline-approvals-station', stage_prefix => 'station-',
    kiosk_request => ['child', 'parent', 180, 1], review => 0}, 'onpc_journey';
$overlay->{stage_prefix} = 'station-' if $mode eq 'wrong-scope';
my $ok = eval {
    onpc_password::enter_overlay_shell_password($overlay);
    onpc_password::enter_overlay_shell_password($overlay) if $mode eq 'replay';
    onpc_password::enter_kiosk_mate_password($station, 'bound-request');
    1;
};
print encode_json({ok => $ok ? 1 : 0, events => \@events});
''', mode)
    value = json.loads(result.stdout)
    assert value['ok'] == (mode == 'sequence')
    scopes = [('overlay', 'overlay-shell')] if mode == 'replay' else (
        [('overlay', 'overlay-shell'), ('station', 'kiosk-mate')] if mode == 'sequence' else [])
    assert value['events'] == [event for scope, provider in scopes for event in (
        ['proof', scope + '-approval-qualified'], ['proof', scope + '-approval-rechecked'],
        ['delivery', 'parent', scope + '-' + provider + '-approval'])]


@pytest.mark.parametrize('mode,role', [
    ('excluded', 'parent'), ('included', 'other-parent'),
    ('wrong-choice', None), ('wrong-scope', None),
    ('lock-recovery', 'parent'), ('close-recovery', 'parent'), ('lock-wrong-scope', None),
    ('game-extension', 'parent'), ('game-wrong-choice', None),
])
def test_composed_overlay_secret_requires_fresh_proofs_and_cannot_be_replayed(mode, role):
    binding = ['child', 'parent', 30, False] if mode == 'excluded' else [
        'child', 'other-parent', 30, True]
    if mode == 'wrong-choice':
        binding[3] = False
    lock = mode.startswith(('lock-', 'close-'))
    if lock:
        binding = ['child', 'parent', 75, True]
    game = mode.startswith('game-')
    if game:
        binding = ['child', 'parent', 75, mode == 'game-wrong-choice']
    result = run_password_guard(r'''
my $journey = bless {prefix => shift @ARGV, stage_prefix => '',
    overlay_request => decode_json(shift @ARGV), review => 0}, 'onpc_journey';
$journey->{stage_prefix} = 'later-' if shift(@ARGV) eq 'wrong-scope';
my $first = eval { onpc_password::enter_overlay_shell_password($journey); 1; };
my $replay = eval { onpc_password::enter_overlay_shell_password($journey); 1; };
print encode_json({first => $first ? 1 : 0, replay => $replay ? 1 : 0, events => \@events});
''', 'game-time-extension' if game else 'overlay-close-case' if mode == 'close-recovery'
        else 'overlay-lock-case' if lock else 'panel-request-case', json.dumps(binding),
        'wrong-scope' if mode == 'lock-wrong-scope' else mode)
    if role is None:
        assert json.loads(result.stdout) == {'first': 0, 'replay': 0, 'events': []}
        return
    assert json.loads(result.stdout) == {'first': 1, 'replay': 0, 'events': [
        ['proof', 'approval-qualified'], ['proof', 'approval-rechecked'],
        ['delivery', role, 'overlay-shell-approval']]}


@pytest.mark.parametrize('fault', ['none', 'scope', 'child'])
def test_station_close_recovery_secret_stays_on_its_fresh_request(fault):
    result = run_password_guard(r'''
my $fault = shift @ARGV;
my $journey = bless {prefix => 'station-close-case', stage_prefix => '',
    kiosk_request => ['child', 'parent', 75, 1], review => 0}, 'onpc_journey';
$journey->{stage_prefix} = 'interruption-' if $fault eq 'scope';
$journey->{kiosk_request}[0] = 'other-child' if $fault eq 'child';
my $first = eval { onpc_password::enter_kiosk_mate_password($journey, 'bound-request'); 1; };
my $replay = eval { onpc_password::enter_kiosk_mate_password($journey, 'bound-request'); 1; };
print encode_json({first => $first ? 1 : 0, replay => $replay ? 1 : 0, events => \@events});
''', fault)
    assert json.loads(result.stdout) == {
        'first': int(fault == 'none'), 'replay': 0,
        'events': [['proof', 'approval-qualified'], ['proof', 'approval-rechecked'],
                   ['delivery', 'parent', 'kiosk-mate-approval']] if fault == 'none' else []}


@pytest.mark.parametrize('prefix,scope,binding,accepted', [
    ('suspend-wake-expired', 'profile-request-', 'long-request', True),
    ('suspend-wake-expired', 'first-', 'long-request', False),
    ('suspend-wake-expired', 'profile-request-', 'request-1200', False),
    ('natural-reminder', 'profile-request-', 'long-request', True),
])
def test_expired_suspend_approval_keeps_its_secret_scope(prefix, scope, binding, accepted):
    result = run_password_guard(r'''
my ($prefix, $scope, $request) = @ARGV;
my $journey = bless {prefix => $prefix . '-profile-request',
    stage_prefix => $scope, review => 0}, 'onpc_journey';
my $ok = eval { onpc_password::enter_kiosk_mate_password($journey, $request); 1 };
print encode_json({ok => $ok ? 1 : 0, events => \@events});
''', prefix, scope, binding)
    value = json.loads(result.stdout)
    assert bool(value['ok']) is accepted
    assert value['events'] == ([
        ['proof', 'profile-request-approval-qualified'],
        ['proof', 'profile-request-approval-rechecked'],
        ['delivery', 'parent', 'profile-request-kiosk-mate-long-request'],
    ] if accepted else [])


@pytest.mark.parametrize('mode', ['two-requests', 'replay', 'wrong-scope', 'wrong-child',
                                 'profile-setup', 'profile-wrong-scope', 'suspend-profile',
                                 'grant-request', 'grant-wrong-scope', 'grant-wrong-child',
                                 'transition-request', 'transition-wrong-duration', 'revocation-request',
                                 'work-recovery', 'expired-recovery', 'kiosk-recovery', 'kiosk-recovery-wrong-scope',
                                 'app-restart-request', 'sign-out-request', 'reboot-request', 'suspend-request',
                                 'process-update-request', 'process-update-wrong-soft', 'session-update-request',
                                 'reboot-update-request',
                                 'sign-out-expired-recovery', 'reboot-expired-recovery', 'suspend-expired-recovery',
                                 'daily-expired-recovery', 'daily-expired-wrong-scope',
                                 'daily-expired-included', 'daily-expired-included-wrong-scope',
                                 'expired-recovery-wrong-scope', 'idle-requests', 'idle-crossed-duration'])
def test_composed_kiosk_secret_scope_and_single_use(mode):
    # Execute the real password guard; replace only the secret delivery sink.
    # No password is supplied, and each isolated Perl process owns its latch.
    # These are independent guard inputs, not runnable customer plans. Loading
    # every journey here couples a focused refusal check to unrelated setup.
    transition = ['app-rule-changes-soft-opening', 'soft-opening-', ['other-child', 'parent', 75, True]]
    revocation = ['revocation-case-request', 'request-', ['other-child', 'parent', 1200, True]]
    recovery = ['grant-work-recovery', ['child', 'parent', 1200, True]]
    if mode in ('expired-recovery', 'sign-out-expired-recovery', 'reboot-expired-recovery',
                'suspend-expired-recovery',
                'expired-recovery-wrong-scope'):
        expired = ('app-restart-expired' if mode == 'expired-recovery' else
                   'reboot-expired' if mode == 'reboot-expired-recovery' else
                   'sign-out-in-expired' if mode == 'sign-out-expired-recovery' else 'suspend-wake-expired')
        recovery = [expired, ['child', 'parent', 1200, False]]
    if mode.startswith('daily-expired-'):
        recovery = ['expired-daily-replacement', ['child', 'parent', 1200, 'included' in mode]]
    restart = ('suspend-wake-active' if mode == 'suspend-request' else
               'reboot-active' if mode == 'reboot-request' else
               'sign-out-in-active' if mode == 'sign-out-request' else 'app-restart-active')
    result = run_password_guard(r'''
my $mode = shift @ARGV;
my $transition = decode_json(shift @ARGV);
my $revocation = decode_json(shift @ARGV);
my $recovery = decode_json(shift @ARGV);
my $panel_prefix = shift @ARGV;
my $kiosk_prefix = shift @ARGV;
my $restart = decode_json(shift @ARGV);
my $process_update = decode_json(shift @ARGV);
my $idle_bindings = decode_json(shift @ARGV);
my $first = bless {prefix => 'kiosk-delayed-approval-first', stage_prefix => 'first-',
    kiosk_request => ['child', 'parent', 30, 0], review => 0}, 'onpc_journey';
my $second = bless {%$first, prefix => 'kiosk-delayed-approval-second', stage_prefix => 'second-'}, 'onpc_journey';
$first->{stage_prefix} = 'second-' if $mode eq 'wrong-scope';
$first->{kiosk_request} = ['other-child', 'parent', 30, 0] if $mode eq 'wrong-child';
if ($mode =~ /^profile-/) {
    $first = bless {prefix => $panel_prefix . '-profile-request',
        stage_prefix => $mode eq 'profile-setup' ? 'profile-request-' : 'first-',
        review => 0}, 'onpc_journey';
}
if ($mode =~ /^grant-/) {
    $first = bless {prefix => 'grant-access-case-request',
        stage_prefix => $mode eq 'grant-wrong-scope' ? 'first-' : 'request-',
        kiosk_request => [$mode eq 'grant-wrong-child' ? 'child' : 'other-child', 'parent', 1200, 1],
        review => 0}, 'onpc_journey';
}
if ($mode =~ /^transition-/) {
    $transition->[2][2] = 1200 if $mode eq 'transition-wrong-duration';
    $first = bless {prefix => $transition->[0], stage_prefix => $transition->[1],
        kiosk_request => $transition->[2],
        review => 0}, 'onpc_journey';
}
if ($mode eq 'revocation-request') {
    $first = bless {prefix => $revocation->[0], stage_prefix => $revocation->[1],
        kiosk_request => $revocation->[2], review => 0}, 'onpc_journey';
}
if ($mode eq 'app-restart-request' || $mode eq 'sign-out-request' || $mode eq 'reboot-request' || $mode eq 'suspend-request') {
    $first = bless {prefix => $restart->[0] . '-request', stage_prefix => 'request-',
        kiosk_request => $restart->[1], review => 0}, 'onpc_journey';
}
if ($mode =~ /^(?:process|session|reboot)-update-/) {
    $process_update->[1][3] = 1 if $mode eq 'process-update-wrong-soft';
    $first = bless {prefix => $process_update->[0] . '-request', stage_prefix => 'request-',
        kiosk_request => $process_update->[1], review => 0}, 'onpc_journey';
}
if ($mode =~ /^kiosk-recovery/) {
    $first = bless {prefix => $kiosk_prefix . '-kiosk-final',
        stage_prefix => $mode eq 'kiosk-recovery' ? 'kiosk-final-' : 'kiosk-first-',
        review => 0}, 'onpc_journey';
}
my $ok = eval {
    if ($mode =~ /^idle-/) {
        for my $scope ('request', 'recovery') {
            my $idle = bless {prefix => 'idle-active-expired-' . $scope,
                stage_prefix => $scope . '-', review => 0,
                kiosk_request => $idle_bindings->{$scope}}, 'onpc_journey';
            $idle->{kiosk_request} = $idle_bindings->{recovery} if $mode eq 'idle-crossed-duration';
            onpc_password::enter_kiosk_mate_password($idle, 'bound-request');
        }
    } elsif ($mode =~ /^kiosk-recovery/) {
        onpc_password::enter_kiosk_mate_password($first, 'request-1200');
        onpc_password::enter_kiosk_mate_password($first, 'request-1200');
    } elsif ($mode eq 'work-recovery' || $mode eq 'expired-recovery'
            || $mode eq 'sign-out-expired-recovery' || $mode eq 'reboot-expired-recovery'
            || $mode eq 'suspend-expired-recovery'
            || $mode eq 'daily-expired-recovery' || $mode eq 'daily-expired-wrong-scope'
            || $mode eq 'daily-expired-included' || $mode eq 'daily-expired-included-wrong-scope'
            || $mode eq 'expired-recovery-wrong-scope') {
        my $setup = bless {prefix => $recovery->[0] . '-profile-request',
            stage_prefix => 'profile-request-', review => 0}, 'onpc_journey';
        onpc_password::enter_kiosk_mate_password($setup, 'long-request');
        my $return = bless {prefix => $recovery->[0],
            stage_prefix => ($mode eq 'expired-recovery-wrong-scope'
                || $mode eq 'daily-expired-wrong-scope'
                || $mode eq 'daily-expired-included-wrong-scope') ? 'profile-request-' : '',
            kiosk_request => $recovery->[1], review => 0}, 'onpc_journey';
        onpc_password::enter_kiosk_mate_password($return, 'bound-request');
    } elsif ($mode =~ /^profile-/) {
        onpc_password::enter_kiosk_mate_password($first, 'request-1200');
    } elsif ($mode =~ /^(?:grant|transition|revocation|app-restart|sign-out|reboot|suspend|process-update|session-update)-/) {
        onpc_password::enter_kiosk_mate_password($first, 'bound-request');
    } else {
        onpc_password::enter_kiosk_mate_password($first, 'bound-request');
        onpc_password::enter_kiosk_mate_password($mode eq 'replay' ? $first : $second, 'bound-request');
    }
    1;
};
print encode_json({ok => $ok ? 1 : 0, events => \@events});
''', 'profile-setup' if mode == 'suspend-profile' else mode,
        json.dumps(transition), json.dumps(revocation), json.dumps(recovery),
        'suspend-active-grant' if mode == 'suspend-profile' else 'panel-request-case', 'baseline-journey',
        json.dumps([restart, ['other-child', 'parent', 1200, True]]),
        json.dumps(['update-reboot-case' if mode == 'reboot-update-request' else
                    'update-session-case' if mode == 'session-update-request' else 'update-process-case',
                    ['other-child', 'parent', 1200, False]]),
        json.dumps({'request': ['other-child', 'parent', 600, True],
                    'recovery': ['other-child', 'parent', 1200, True]}))
    value = json.loads(result.stdout)
    deliveries = [event for event in value['events'] if event[0] == 'delivery']
    if mode.startswith('idle-'):
        assert value['ok'] == (mode == 'idle-requests')
        scopes = ('request', 'recovery') if mode == 'idle-requests' else ()
        assert deliveries == [['delivery', 'parent', scope + '-kiosk-mate-approval'] for scope in scopes]
        assert [event for event in value['events'] if event[0] == 'proof'] == [
            ['proof', scope + '-approval-' + proof]
            for scope in scopes for proof in ('qualified', 'rechecked')]
    elif mode == 'kiosk-recovery':
        assert value['ok'] == 0  # The second delivery is refused.
        assert deliveries == [['delivery', 'parent', 'kiosk-final-kiosk-mate-request-1200']]
        assert [event for event in value['events'] if event[0] == 'proof'] == [
            ['proof', 'kiosk-final-approval-' + proof] for proof in ('qualified', 'rechecked')]
    elif mode in ('work-recovery', 'expired-recovery', 'sign-out-expired-recovery',
                  'reboot-expired-recovery', 'suspend-expired-recovery',
                  'daily-expired-recovery', 'daily-expired-included'):
        assert value['ok'] == 1
        assert deliveries == [
            ['delivery', 'parent', 'profile-request-kiosk-mate-long-request'],
            ['delivery', 'parent', 'kiosk-mate-approval']]
        assert [event for event in value['events'] if event[0] == 'proof'] == [
            ['proof', prefix + 'approval-' + proof]
            for prefix in ('profile-request-', '') for proof in ('qualified', 'rechecked')]
    elif mode in ('expired-recovery-wrong-scope', 'daily-expired-wrong-scope',
                  'daily-expired-included-wrong-scope'):
        assert value['ok'] == 0
        assert deliveries == [['delivery', 'parent', 'profile-request-kiosk-mate-long-request']]
        assert [event for event in value['events'] if event[0] == 'proof'] == [
            ['proof', 'profile-request-approval-' + proof] for proof in ('qualified', 'rechecked')]
    elif mode == 'two-requests':
        assert value['ok'] == 1
        assert deliveries == [['delivery', 'parent', request + '-kiosk-mate-approval']
                               for request in ('first', 'second')]
        assert [event for event in value['events'] if event[0] == 'proof'] == [
            ['proof', request + '-approval-' + proof]
            for request in ('first', 'second') for proof in ('qualified', 'rechecked')]
    elif mode in ('grant-request', 'transition-request', 'revocation-request', 'app-restart-request',
                  'sign-out-request', 'reboot-request', 'suspend-request', 'process-update-request', 'session-update-request',
                  'reboot-update-request'):
        assert value['ok'] == 1
        scope = 'soft-opening' if mode == 'transition-request' else 'request'
        assert deliveries == [['delivery', 'parent', scope + '-kiosk-mate-approval']]
        assert [event for event in value['events'] if event[0] == 'proof'] == [
            ['proof', scope + '-approval-' + proof] for proof in ('qualified', 'rechecked')]
    elif mode in ('profile-setup', 'suspend-profile'):
        assert value['ok'] == 1
        assert deliveries == [['delivery', 'parent', 'profile-request-kiosk-mate-request-1200']]
        assert [event for event in value['events'] if event[0] == 'proof'] == [
            ['proof', 'profile-request-approval-' + proof]
            for proof in ('qualified', 'rechecked')]
    else:
        assert value['ok'] == 0
        assert len(deliveries) == (1 if mode == 'replay' else 0)
