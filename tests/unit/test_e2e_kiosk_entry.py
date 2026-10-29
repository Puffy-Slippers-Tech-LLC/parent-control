"""Public request-station entry and immutable form observation contracts."""
from tools.test_storage import named_input

import json
from dataclasses import FrozenInstanceError
from pathlib import Path

import pytest

from accessible_ui import EXTERNAL_PROVIDER_CONTRACTS, UiError
from private_artifacts import EvidenceError
from tests.support.accessible_ui import Node, ui_for
from tests.support.e2e_kiosk import request_form
from tests.support.paths import ROOT
from tests.support.perl import run_perl
from ui_observations import RequestObservation
from installed_journey import InstalledJourney


def activation_harness(monkeypatch, *, recipient=None, elapsed=0, enter_error=None,
                       boot='a' * 64):
    """Private in-memory controller boundary; never acquires or operates a VM."""
    from contextlib import contextmanager
    from types import SimpleNamespace
    from unittest.mock import Mock
    import kiosk_entry

    events = []
    active = []
    observer = SimpleNamespace(boot_guard=None, boot_proof=None)

    def observe(operation):
        assert active
        events.append(('observe', operation, observer.boot_guard))
        observer.boot_proof = boot
        if operation == 'gdm-station-focused' and recipient is not None:
            return recipient
        return {'operation': operation, 'outcome': 'passed',
                'interface': 'ApplicationUI+external-provider'}

    observer.observe = Mock(side_effect=observe)
    factory = Mock(return_value=observer)
    monkeypatch.setattr(kiosk_entry, 'UiObservations', factory)
    clock = iter((10, 10 + elapsed))
    monkeypatch.setattr(kiosk_entry.time, 'monotonic', lambda: next(clock))

    @contextmanager
    def operation(label):
        events.append(('intention', label))
        active.append(label)
        try:
            yield
        finally:
            active.pop()

    monkeypatch.setattr(kiosk_entry.watch_activity, 'operation', operation)

    def enter(*args):
        assert active[-1] == 'Entering the freshly focused request station'
        events.append(('enter', args))
        if enter_error is not None:
            raise enter_error

    def census(argv, *, timeout):
        assert active
        events.append(('census', argv, timeout))
        return json.dumps({'scope': 'session-identity-only',
                           'confinement_qualified': False}).encode()

    lease = SimpleNamespace(state={'run': 'b' * 32},
        guard=Mock(side_effect=lambda: events.append(('guard',))),
        source=SimpleNamespace(domain=SimpleNamespace(sendKey=Mock(side_effect=enter)),
                               api=SimpleNamespace(VIR_KEYCODE_SET_LINUX=0)))
    transport = SimpleNamespace(call=Mock(side_effect=census))
    return kiosk_entry, transport, lease, observer, factory, events


@pytest.mark.parametrize('phase, public_steps', [
    ('installed', ['station-initial-entry', 'restart-kiosk-read',
                   'restart-kiosk-close', 'restart-kiosk-closed', 'restart-kiosk-exit']),
    ('rebooted', ['station-default-entry', 'kiosk-request-form',
                  'restart-kiosk-missing-refused', 'kiosk-request-cancel']),
])
def test_real_activation_observes_each_phase_without_reset(monkeypatch, phase, public_steps):
    helper, transport, lease, ui, factory, events = activation_harness(monkeypatch)
    result = helper.observe_activation(transport, lease, phase)
    expected = ['gdm-station-list', 'gdm-station-focused', *public_steps, 'gdm-station-returned']
    assert [item['operation'] for item in result['public_observations']] == expected
    assert result['phase'] == phase and result['boot_sha256'] == 'a' * 64
    assert result['engineering_confinement'] == {
        'scope': 'session-identity-only', 'confinement_qualified': False}
    factory.assert_called_once_with(transport)
    lease.source.domain.sendKey.assert_called_once_with(0, 100, [28], 1, 0)
    transport.call.assert_called_once_with(['env', 'ONPC_EXPECTED_RUN=' + 'b' * 32,
        'PYTHONDONTWRITEBYTECODE=1', '/usr/bin/python3', '-B',
        helper.system.PAYLOAD + '/system_kiosk_confinement.py', 'census'], timeout=45)
    observations = [item for item in events if item[0] == 'observe']
    assert observations[0][2] == ''
    assert all(item[2] == 'a' * 64 for item in observations[1:])
    entry = next(index for index, item in enumerate(events) if item[0] == 'enter')
    assert events[entry - 1] == events[entry + 1] == ('guard',)
    census = next(index for index, item in enumerate(events) if item[0] == 'census')
    exit_step = 'restart-kiosk-close' if phase == 'installed' else 'kiosk-request-cancel'
    assert events[census - 1] == ('guard',)
    assert next(index for index, item in enumerate(events)
                if item[:2] == ('observe', public_steps[1])) < census
    assert next(index for index, item in enumerate(events)
                if item[:2] == ('observe', exit_step)) > census


@pytest.mark.parametrize('phase', ['', 'setup', 'postboot', None, 1])
def test_real_activation_invalid_phase_releases_no_input(monkeypatch, phase):
    helper, transport, lease, ui, factory, events = activation_harness(monkeypatch)
    with pytest.raises(EvidenceError, match='kiosk-activation:phase'):
        helper.observe_activation(transport, lease, phase)
    assert not events
    factory.assert_not_called()
    transport.call.assert_not_called()
    lease.source.domain.sendKey.assert_not_called()


@pytest.mark.parametrize('fault', ['wrong-recipient', 'failed-proof', 'stale', 'backward-clock', 'boot'])
def test_real_activation_refuses_bad_or_stale_recipient_without_retry(monkeypatch, fault):
    recipient = {'operation': 'gdm-station-focused', 'outcome': 'passed',
                 'interface': 'ApplicationUI+external-provider'}
    if fault == 'wrong-recipient':
        recipient['operation'] = 'gdm-focused'
    elif fault == 'failed-proof':
        recipient['outcome'] = 'failed'
    helper, transport, lease, ui, factory, events = activation_harness(monkeypatch,
        recipient=recipient, elapsed=30 if fault == 'stale' else -1 if fault == 'backward-clock' else 0,
        boot='private-invalid-boot' if fault == 'boot' else 'a' * 64)
    with pytest.raises(EvidenceError, match='kiosk-activation:(recipient|stale-recipient|boot-proof)'):
        helper.observe_activation(transport, lease, 'installed')
    assert [call.args[0] for call in ui.observe.call_args_list] == (
        ['gdm-station-list'] if fault == 'boot' else ['gdm-station-list', 'gdm-station-focused'])
    lease.source.domain.sendKey.assert_not_called()
    transport.call.assert_not_called()


def test_real_activation_uncertain_enter_is_guarded_and_never_replayed(monkeypatch):
    helper, transport, lease, ui, factory, events = activation_harness(
        monkeypatch, enter_error=RuntimeError('uncertain input'))
    with pytest.raises(RuntimeError, match='uncertain input'):
        helper.observe_activation(transport, lease, 'installed')
    lease.source.domain.sendKey.assert_called_once()
    assert events[-1] == ('guard',)
    assert ui.observe.call_count == 2
    transport.call.assert_not_called()


@pytest.mark.parametrize('uncertain', [False, True])
def test_entry_timing_brackets_input_before_post_guard_and_never_replays(monkeypatch, uncertain):
    from unittest.mock import Mock
    helper, _transport, lease, ui, _factory, events = activation_harness(
        monkeypatch, enter_error=RuntimeError('uncertain input') if uncertain else None)
    clock = iter((100, 200))
    monkeypatch.setattr(helper.time, 'monotonic_ns', lambda: next(clock))
    received = Mock()
    with helper.watch_activity.operation('Measuring guarded entry'):
        ui.boot_guard = ''
        if uncertain:
            with pytest.raises(RuntimeError, match='uncertain input'):
                helper.enter_station(lease, ui, ui.observe, on_input=received)
        else:
            assert helper.enter_station(lease, ui, ui.observe, on_input=received) == 100
    lease.source.domain.sendKey.assert_called_once()
    assert events[-1] == ('guard',)
    if uncertain:
        received.assert_not_called()
    else:
        received.assert_called_once_with(100, 200)


def station_greeter(*rows, recipient=None, field=None, list_showing=True):
    children = list(rows) if list_showing else []
    if recipient is not None:
        children.append(recipient)
    if field is not None:
        children.append(field)
    application = Node('GNOME Shell', 'application', children=children)
    return ui_for(Node(role='desktop frame', children=[application]))


@pytest.mark.parametrize('fallback', ['account-list', 'station-prompt'])
def test_station_refusal_reads_safe_fallback_without_a_password_or_message_oracle(fallback):
    if fallback == 'account-list':
        ui = station_greeter(Node('oh-no-parent-control', 'push button'))
    else:
        ui = station_greeter(recipient=Node('Oh No! Parent Control', 'label'),
                             field=Node('private password canary', 'password text'))
    assert ui.run('gdm-station-refused', '')['fallback'] == fallback


def test_station_refusal_waits_for_confirmed_transition_absence_only(monkeypatch):
    ui = station_greeter(Node('oh-no-parent-control', 'push button'))
    ui.timeout = 2
    actual = ui.station_refusal_snapshot
    snapshots = iter([None, None])
    def snapshot():
        try:
            return next(snapshots)
        except StopIteration:
            return actual()
    monkeypatch.setattr(ui, 'station_refusal_snapshot', snapshot)
    assert ui.run('gdm-station-refused', '')['fallback'] == 'account-list'


def test_station_refusal_unbound_transition_never_authorizes_input():
    assert station_greeter().station_refusal_snapshot() is None
    ui = station_greeter(field=Node('private canary', 'password text'))
    assert ui.station_refusal_snapshot() is None
    with pytest.raises(UiError, match='timeout:gdm-refused-fallback'):
        ui.run('gdm-station-refused', '')


def test_station_refusal_duplicate_station_labels_are_pending_until_the_list_returns(monkeypatch):
    ui = station_greeter(recipient=Node('Oh No! Parent Control', 'label'),
                         field=Node('oh-no-parent-control', 'label'))
    assert ui.station_refusal_snapshot() is None
    application = ui.api.get_desktop(0).children[0]
    actual = ui.station_refusal_snapshot
    def snapshot():
        result = actual()
        if result is None:
            application.children = [Node('oh-no-parent-control', 'push button')]
            application.children[0].parent = application
        return result
    monkeypatch.setattr(ui, 'station_refusal_snapshot', snapshot)
    ui.timeout = 2
    assert ui.run('gdm-station-refused', '')['fallback'] == 'account-list'


@pytest.mark.parametrize('fault', ['wrong-recipient', 'ambiguous-recipient', 'duplicate-field',
                                 'mixed-list', 'uncertain'])
def test_station_refusal_rejects_wrong_or_ambiguous_fallback(fault):
    recipient = Node('Jamie (Parent)' if fault == 'wrong-recipient' else
                     'Oh No! Parent Control', 'label')
    rows = [Node('Oh No! Parent Control', 'push button')] if fault == 'mixed-list' else []
    if fault == 'ambiguous-recipient':
        rows.append(Node('oh-no-parent-control', 'label'))
    if fault == 'duplicate-field':
        rows.append(Node('private canary 2', 'password text'))
    ui = station_greeter(*rows, recipient=recipient, field=Node('private canary', 'password text'))
    ui.input_uncertain = fault == 'uncertain'
    with pytest.raises(UiError):
        ui.run('gdm-station-refused', '')


def test_greeter_waits_for_public_owner_before_resolving_account(monkeypatch):
    import accessible_ui
    from unittest.mock import Mock

    parent = Node('Jamie (Parent)', 'push button')
    station = Node('oh-no-parent-control', 'push button')
    ui = station_greeter(parent, station)
    ready = ui.api.get_desktop(0)
    ui.api.get_desktop = Mock(side_effect=[Node(role='desktop frame'), ready])
    ui.timeout = 1
    monkeypatch.setattr(accessible_ui.time, 'sleep', lambda _: None)
    assert ui.gdm_semantic_owner() is ready.children[0]
    parent.action.do_action.assert_not_called()
    parent.component.grab_focus.assert_not_called()


def test_greeter_ambiguous_owner_never_retries_or_acts(monkeypatch):
    from unittest.mock import Mock
    import accessible_ui

    ui = ui_for(Node(role='desktop frame', children=[
        Node('GNOME Shell', 'application'), Node('GNOME Shell', 'application')]))
    sleep = Mock()
    monkeypatch.setattr(accessible_ui.time, 'sleep', sleep)
    with pytest.raises(UiError, match='ui:gdm-provider-owner'):
        ui.gdm_semantic_owner()
    sleep.assert_not_called()


def test_station_observer_does_not_wait_for_session_services(monkeypatch):
    from types import SimpleNamespace
    import accessible_ui

    def forbidden(*_args, **_kwargs):
        pytest.fail('station observation must wait for the public form')

    monkeypatch.setattr(accessible_ui, 'session_environment', forbidden)
    assert accessible_ui.observation_environment(
        SimpleNamespace(pw_uid=1234), 'kiosk-request-form') == {
            'XDG_RUNTIME_DIR': '/run/user/1234',
            'DBUS_SESSION_BUS_ADDRESS': 'unix:path=/run/user/1234/bus',
        }


@pytest.mark.parametrize('online', [False, True])
def test_kiosk_qualification_reuses_the_prepared_app_snapshot(tmp_path, online, monkeypatch):
    from contextlib import nullcontext
    from types import SimpleNamespace
    from unittest.mock import Mock, call

    import check_e2e_kiosk_entry as check
    import app_snapshot
    from guest_inputs import Bundle
    from parent_setup_qualification import KioskEntryQualification
    from tests.support.vm_runner import UUID, xml as domain_xml

    from tools.test_storage import named_input
    assert check.ASSETS == named_input(package_source=True)
    assert check.ASSETS == named_input()
    context = SimpleNamespace(directory=tmp_path)
    KioskEntryQualification.journey(context, lambda *_: None)
    version = json.loads((ROOT / 'data/app.json').read_bytes())['version']
    assert context.installed_snapshot == 'onpc-v' + version
    assert not hasattr(context, 'install_current_package')

    qualification = KioskEntryQualification.__new__(KioskEntryQualification)
    qualification.assets = tmp_path
    qualification.directory = tmp_path
    qualification.result = {}
    qualification.commands = Mock()
    qualification.commands.run.return_value = b'9.8.7+ppa1~ubuntu26.04.1\n'
    (tmp_path / 'package.deb').write_bytes(b'fixture')
    bundle = Mock()
    staged = Mock(return_value=bundle)
    monkeypatch.setattr(Bundle, 'from_staged', staged)
    identity = json.dumps({'schema_version': 2, 'package_sha256': 'b' * 64,
        'package_content_sha256': 'c' * 64, 'baseline_sha256': 'd' * 64,
        'recipe_sha256': 'e' * 64})
    expected_identity = Mock(return_value=identity)
    monkeypatch.setattr(app_snapshot, 'input_identity', expected_identity)
    monkeypatch.setattr(app_snapshot.time, 'time', lambda: 100000)
    # Snapshot validation includes both the SPICE console and private VNC
    # automation endpoint, plus the output-only observer.
    domain = app_snapshot.system.isolated_xml(domain_xml(), UUID, 'a' * 32, graphics_type='vnc')
    snap = Mock()
    snap.getXMLDesc.return_value = ('<domainsnapshot><description>' + identity +
        '</description><memory snapshot="' + ('internal' if online else 'no') +
        '"/><state>' + ('running' if online else 'shutoff') +
        '</state><creationTime>100000</creationTime>' + domain + '</domainsnapshot>')
    lease = Mock()
    lease.capture.state = {'guest': {'ubuntu_version': '26.04'}}
    lease.source.domain.snapshotLookupByName.return_value = snap
    lease.source.api.VIR_DOMAIN_SNAPSHOT_REVERT_FORCE = 4
    lease.state = {'run': 'a' * 32}
    # Offline reuse compares the saved domain with the lease's validated XML.
    lease.original_xml = domain
    lease.test_xml = '<domain/>'
    lease.snapshot_status.return_value = nullcontext()
    qualification.attach_installed_snapshot(lease)
    staged.assert_called_once_with(ROOT, tmp_path / 'input')
    expected_identity.assert_called_once_with(lease, tmp_path, bundle, qualification.commands)
    assert qualification.result['installed_snapshot']['inputs'] == json.loads(identity)
    # Offline reuse checks before metadata acceptance, again after restore
    # admission, and after restoring the isolated domain configuration.
    assert lease.guard.call_args_list == [call(off=True)] * (1 if online else 3)
    lease.source.domain.snapshotLookupByName.assert_called_once_with('onpc-v9.8.7', 0)
    if online:
        assert lease.online_pending is True and lease.installed_name == 'onpc-v9.8.7'
        assert lease.installed_xml == snap.getXMLDesc.return_value
        lease.source.domain.revertToSnapshot.assert_not_called()
        lease.source.connection.defineXML.assert_not_called()
        return
    lease.source.domain.revertToSnapshot.assert_called_once_with(snap, 4)
    lease.source.connection.defineXML.assert_called_once_with('<domain/>')


def test_kiosk_request_form_returns_only_the_fixed_public_projection():
    ui, durations = request_form()
    result = ui.run('kiosk-request-form', '')
    observation = RequestObservation.from_request(result['request'])
    assert observation == RequestObservation(
        surface='kiosk', form_count=1, child='existing-fixture-child',
        approver='other-fixture-parent', duration_seconds=1800, custom_text=None,
        allow_soft=False, child_selector_enabled=True, approver_selector_enabled=False,
        duration_enabled=False, soft_choice_enabled=False, request_enabled=False,
        cancel_enabled=True, message='screen-limit-disabled', mute=None)
    assert all(button.action.do_action.call_count == 0 for button in durations)


def test_kiosk_request_form_uses_two_complete_tree_reads_at_most(capsys):
    ui, _ = request_form()
    RequestObservation.from_request(ui.run('kiosk-request-form', '')['request'])
    records = [json.loads(line) for line in capsys.readouterr().out.splitlines()]
    passed = next(record for record in reversed(records) if record['status'] == 'passed')
    assert passed['tree'] == 'complete'
    assert passed['tree_reads'] <= 2
    assert passed['nodes_read'] <= 2 * len(list(ui.nodes(strict=True)))


def test_form_projection_reuses_complete_snapshot_ids(monkeypatch):
    from unittest.mock import Mock

    ui, _ = request_form()
    nodes = list(ui.nodes(strict=True))
    reads = []
    for node in nodes:
        read = Mock(wraps=node.get_attributes)
        monkeypatch.setattr(node, 'get_attributes', read)
        reads.append(read)
    RequestObservation.from_request(ui.run('kiosk-request-form', '')['request'])
    assert all(read.call_count == 1 for read in reads)


@pytest.mark.parametrize('completion', ['ready', 'missing', 'query-error'])
def test_form_checks_fresh_language_completion_before_outer_deadline(monkeypatch, completion):
    from unittest.mock import Mock

    ui, durations = request_form()
    window = ui.find_id('kiosk-request-window')
    ready = ui.find_id('kiosk-language-ready')
    window.children.remove(ready)
    reads = Mock(wraps=ui.read_snapshot)
    monkeypatch.setattr(ui, 'read_snapshot', reads)

    def complete():
        # Simulate the helper's input boundary and independent completion read.
        ui.invalidate_observation()
        if completion == 'query-error':
            raise LookupError('private language query')
        if completion == 'ready':
            window.children.append(ready)
        ui.read_snapshot()

    helper = Mock(side_effect=complete)
    ui.query_errors = (LookupError,)
    monkeypatch.setattr(ui, 'complete_request_language_setup', helper)
    # A completed predicate is allowed at the deadline; a pending one is not.
    assert ui.timeout == 0
    if completion == 'ready':
        RequestObservation.from_request(ui.run('kiosk-request-form', '')['request'])
    else:
        with pytest.raises(UiError, match='timeout:kiosk-request-form'):
            ui.run('kiosk-request-form', '')
    helper.assert_called_once_with()
    assert reads.call_count <= 4
    assert all(button.action.do_action.call_count == 0 for button in durations)


def test_station_positive_form_observation_permits_no_prompt_without_prompt_ids():
    ui, durations = request_form()
    ui.provider_contracts = EXTERNAL_PROVIDER_CONTRACTS
    result = ui.run('kiosk-request-form', '')
    RequestObservation.from_request(result['request'])
    assert ui.prompt_session == 'station'
    assert all(button.action.do_action.call_count == 0 for button in durations)


@pytest.mark.parametrize('identity', ['kiosk-child-selector', 'kiosk-approver-selector',
                                    'kiosk-request-submit', 'kiosk-screen-limit-notice',
                                    'kiosk-duration-1800'])
def test_station_never_borrows_a_control_from_another_surface(identity):
    ui, _ = request_form()
    form = ui.find_id('kiosk-request-form')
    target = next(node for node in form.children if node.identity == identity)
    form.children.remove(target)
    ui.api.get_desktop(0).children.append(Node(identity='unrelated-window', children=[target]))
    with pytest.raises(UiError, match='timeout:kiosk-request-form'):
        ui.kiosk_request_form()


def test_station_refuses_a_duplicate_owned_control():
    ui, _ = request_form()
    form = ui.find_id('kiosk-request-form')
    form.children.append(Node(identity='kiosk-child-selector'))
    with pytest.raises(UiError, match='ambiguous-automation-id'):
        ui.kiosk_request_form()


@pytest.mark.parametrize('owner_check', ['allowed-application', 'pid', 'application-owner'])
def test_station_refuses_the_form_under_a_wrong_runtime_owner(owner_check):
    ui, _ = request_form()
    if owner_check == 'allowed-application':
        ui.application_ids = lambda: ()
    elif owner_check == 'pid':
        ui.owner_pids = lambda: set()
    else:
        ui.application_owners = lambda: {}
    with pytest.raises(UiError, match='wrong-(?:application-)?owner'):
        ui.kiosk_request_form()


def test_station_refuses_incomplete_form_even_when_required_controls_exist():
    ui, _ = request_form()
    ui.find_id('kiosk-request-form').children.append(Node(states=('defunct',)))
    with pytest.raises(UiError, match='stale-request-form'):
        ui.kiosk_request_form()


@pytest.mark.parametrize('role', ['window', 'dialog'])
def test_station_form_accepts_public_window_roles_with_the_same_required_contents(role):
    ui, _ = request_form()
    ui.find_id('kiosk-request-form').role = role
    RequestObservation.from_request(ui.run('kiosk-request-form', '')['request'])


def test_station_form_targets_controls_only_by_public_id():
    ui, _ = request_form()
    for node in ui.find_id('kiosk-request-form').children:
        if node.identity and node.identity != 'kiosk-screen-limit-notice':
            node.name = 'Changed visual label'
            node.role = 'changed-role'
    observation = RequestObservation.from_request(
        ui.run('kiosk-request-form', '')['request'])
    assert observation.child == 'existing-fixture-child'
    assert observation.duration_seconds == 1800


@pytest.mark.parametrize('fault', ['missing', 'wrong-uid', 'non-scalar', 'wrong-description'])
@pytest.mark.parametrize('namespace', ['child', 'approver'])
def test_selected_account_requires_uid_identity_before_description(namespace, fault):
    ui, _ = request_form()
    selector = ui.find_id(f'kiosk-{namespace}-selector')
    if fault == 'missing':
        selector.value = None
    elif fault == 'wrong-uid':
        selector.value = '9000'
    elif fault == 'non-scalar':
        selector.value = [selector.value, selector.value]
    else:
        selector.description = 'Selected account: wrong person.'
    with pytest.raises(UiError):
        ui.kiosk_request_form()


def test_station_timeout_reports_only_registered_public_control_ids(capsys):
    ui = ui_for(Node('Unrelated private title', 'application', children=[
        Node('Unrelated private label', 'label')]))
    with pytest.raises(UiError, match='ui:timeout:kiosk-request-form'):
        ui.run('kiosk-request-form', '')
    output = capsys.readouterr().out
    assert 'Unrelated private' not in output
    diagnostic = json.loads(output.splitlines()[-1])
    assert diagnostic['status'] == 'failed'
    assert diagnostic['tree'] == 'complete'
    assert not any(diagnostic['public_ids'].values())


def test_station_deadline_interrupts_a_slow_predicate_and_retains_exact_phase(monkeypatch, capsys):
    import accessible_ui

    ui, _ = request_form()
    now = [0.0]
    monkeypatch.setattr(accessible_ui.time, 'monotonic', lambda: now[0])
    original = ui.showing

    def slow_showing(node):
        if node.identity == 'kiosk-child-selector':
            now[0] = 91.0
            ui.kiosk_diagnostic.check()
        return original(node)

    monkeypatch.setattr(ui, 'showing', slow_showing)
    with pytest.raises(UiError, match='timeout:kiosk-request-form'):
        ui.kiosk_request_form()
    records = [json.loads(line) for line in capsys.readouterr().out.splitlines()]
    assert records[-1]['phase'] == 'kiosk-child-selector'
    assert records[-1]['status'] == 'failed'
    assert records[-1]['tree'] == 'complete'
    assert records[-1]['public_ids']['kiosk-request-form'] == 1
    assert records[-1]['public_ids'][accessible_ui.KIOSK_APPLICATION] == 1
    assert records[-1]['tree_reads'] == 1
    assert ui.kiosk_diagnostic is None


@pytest.mark.parametrize('fault', ['null-child', 'query-error'])
def test_station_partial_public_read_never_proves_missing_ids(fault, capsys):
    ui, _ = request_form()
    root = ui.api.get_desktop(0)
    if fault == 'null-child':
        root.children.append(None)
    else:
        class QueryError(Exception):
            pass
        ui.query_errors = (QueryError,)
        def broken():
            raise QueryError('private provider error')
        root.get_attributes = broken
    with pytest.raises(UiError, match='timeout:kiosk-request-form'):
        ui.kiosk_request_form()
    output = capsys.readouterr().out
    assert 'private' not in output
    diagnostic = json.loads(output.splitlines()[-1])
    assert diagnostic['tree'] == 'incomplete'
    assert diagnostic['public_ids'] == {}
    assert diagnostic['incomplete_reads'] + diagnostic['query_errors'] == 1


@pytest.mark.parametrize('operation', ['kiosk-request-form', 'overlay-request-form'])
def test_station_diagnostic_survives_owned_transport_timeout(monkeypatch, tmp_path, capsys, operation):
    import os
    from types import SimpleNamespace
    from unittest.mock import Mock
    import accessible_ui
    import owned_commands
    import vm_transport
    from ui_observations import UiObservations

    accessible_ui.KioskDiagnostic().emit('public-tree')
    raw = capsys.readouterr().out.encode()
    commands = owned_commands.Commands()
    commands.directory = tmp_path
    previous = Mock()
    commands.progress = previous
    child = SimpleNamespace(pid=123, returncode=130, wait=Mock())
    child.communicate = Mock(side_effect=owned_commands.subprocess.TimeoutExpired('private argv', 120))
    def spawn(argv, **kwargs):
        kwargs['stdout'].write(raw)
        kwargs['stdout'].flush()
        kwargs['stderr'].write(b'private provider message\n')
        kwargs['stderr'].flush()
        return child
    monkeypatch.setattr(owned_commands.subprocess, 'Popen', spawn)
    monkeypatch.setattr(owned_commands.os, 'pidfd_open', lambda _: os.open('/dev/null', os.O_RDONLY))
    signal = Mock()
    monkeypatch.setattr(owned_commands.signal, 'pidfd_send_signal', signal)
    ticks = iter((0.0, 0.0, 121.0))
    monkeypatch.setattr(owned_commands.time, 'monotonic', lambda: next(ticks))
    monkeypatch.setattr(vm_transport.time, 'perf_counter', lambda: 0.0)
    transport = vm_transport.Transport({'directory': str(tmp_path), 'hostname': 'fixture.invalid',
        'run': 'a' * 32, 'domain_uuid': 'b' * 32}, commands, guard=Mock())
    with pytest.raises(owned_commands.subprocess.TimeoutExpired):
        UiObservations(transport).call(['fixed-program'], operation)
    # Failed exchanges also report fixed, sanitized transport timing fields.
    timing = (b'vm-transport-timing: operation=ssh-command sequence=1 state=failed '
              b'duration_seconds=0.000 guard_seconds=0.000 command_seconds=0.000\n')
    assert capsys.readouterr().err.encode() == raw + timing
    assert (tmp_path / 'command-0001.txt').read_bytes() == raw
    assert commands.progress is previous
    # Command-local parsing leaves the ordinary progress subscriber intact.
    previous.assert_called_once_with(raw)
    signal.assert_called_once()
    child.wait.assert_called_once()


@pytest.mark.parametrize('fault', ['phase', 'private-field', 'private-id', 'bool-count', 'incomplete-counts'])
def test_station_controller_rejects_untrusted_diagnostics_before_retaining(fault, capsys):
    import accessible_ui
    from ui_observations import UiObservations

    accessible_ui.KioskDiagnostic().emit()
    value = json.loads(capsys.readouterr().out)
    if fault == 'phase':
        value['phase'] = 'private text'
    elif fault == 'private-field':
        value['private'] = 'private text'
    elif fault == 'private-id':
        value['public_ids'] = {'private text': 1}
    elif fault == 'bool-count':
        value['tree_reads'] = True
    else:
        value['tree'] = 'complete'
    with pytest.raises(EvidenceError):
        UiObservations.retain_kiosk_diagnostic(value)
    assert not capsys.readouterr().err


@pytest.mark.parametrize('fault', [None, 'missing-result', 'partial', 'replay', 'late-diagnostic', 'flood'])
@pytest.mark.parametrize('operation', ['kiosk-request-form', 'overlay-request-form'])
def test_station_stream_requires_one_final_result_separate_from_diagnostics(fault, capsys, operation):
    from types import SimpleNamespace
    import accessible_ui
    from ui_observations import UiObservations

    accessible_ui.KioskDiagnostic().emit('public-tree')
    diagnostic = capsys.readouterr().out.encode()
    result = b'{"result": "fixture"}\n'
    raw = diagnostic + result
    if fault == 'missing-result':
        raw = diagnostic
    elif fault == 'partial':
        raw = diagnostic + result[:-1]
    elif fault == 'replay':
        raw += result
    elif fault == 'late-diagnostic':
        raw += diagnostic
    elif fault == 'flood':
        raw = diagnostic * 129 + result
    def call(*_args, on_output, **_kwargs):
        # Exercise arbitrary transport chunk boundaries, including JSON keys.
        for start in range(0, len(raw), 17):
            on_output(raw[start:start + 17])
        return raw
    transport = SimpleNamespace(call=call, commands=SimpleNamespace(progress=None))
    observer = UiObservations(transport)
    if fault:
        with pytest.raises(EvidenceError):
            observer.call(['fixed-program'], operation)
    else:
        assert observer.call(['fixed-program'], operation) == (result.rstrip(), [])
        assert capsys.readouterr().err.encode() == diagnostic
    assert transport.commands.progress is None


def test_station_observer_refreshes_an_empty_public_tree_after_session_entry():
    from unittest.mock import Mock

    ui, _ = request_form()
    ready = ui.api.get_desktop(0)
    ui.api.get_desktop = Mock(return_value=Node(role='desktop frame'))
    ui.reset_observer = Mock(side_effect=lambda: setattr(ui.api.get_desktop, 'return_value', ready))
    ui.timeout = 1
    result = ui.run('kiosk-request-form', '')
    RequestObservation.from_request(result['request'])
    ui.reset_observer.assert_called_once_with()


def test_station_observer_never_refreshes_away_a_visible_form_mismatch():
    from unittest.mock import Mock

    ui, _ = request_form(fault='wrong-duration')
    ui.reset_observer = Mock()
    with pytest.raises(UiError, match='ui:kiosk-duration-selection'):
        ui.run('kiosk-request-form', '')
    ui.reset_observer.assert_not_called()


def test_installed_journey_keeps_the_validated_request_observation_immutable(tmp_path):
    journey = InstalledJourney(type('Context', (), {'directory': tmp_path})(), lambda *_: None,
                               __import__('kiosk_entry').PLAN)
    value = request_form()[0].run('kiosk-request-form', '')['request']
    journey.check_request('request-form', {'ui': {'request': value}})
    assert isinstance(journey.request_observations['request-form'], RequestObservation)
    with pytest.raises(FrozenInstanceError):
        journey.request_observations['request-form'].request_enabled = True


@pytest.mark.parametrize('fault', [
    'wrong-duration', 'multiple-durations', 'checked-not-pressed', 'duration-enabled',
    'request-enabled', 'custom-visible', 'missing-message',
    'mute-present', 'duplicate-form',
])
def test_kiosk_request_form_refuses_changed_or_ambiguous_state(fault):
    ui, _ = request_form(fault=fault)
    ui.timeout = 0
    with pytest.raises((UiError, EvidenceError)):
        RequestObservation.from_request(ui.run('kiosk-request-form', '')['request'])


def test_station_greeter_navigation_and_wrong_entry_are_independent():
    station = Node('oh-no-parent-control', 'push button',
                   states=('showing', 'visible', 'sensitive'))
    parent = Node('Jamie (Parent)', 'push button')
    ui = station_greeter(parent, station)
    assert ui.run('gdm-station-list', '')['focused'] is True
    assert ui.run('gdm-station-focused', '')['outcome'] == 'passed'

    field = Node('Password', 'password text',
                 states=('showing', 'visible', 'sensitive', 'focused'))
    field.get_text_iface = lambda: (_ for _ in ()).throw(AssertionError('password read'))
    prompt = station_greeter(recipient=Node('Jamie (Parent)', 'label'), field=field,
                             list_showing=False)
    assert prompt.run('gdm-station-wrong-entry-refused', '')['outcome'] == 'passed'


def test_station_display_name_and_username_on_one_row_are_one_target():
    parent = Node('Jamie (Parent)', 'push button')
    station = Node('Oh No! Parent Control', 'push button',
                   states=('showing', 'visible', 'sensitive', 'focused'))
    ui = station_greeter(parent, station)
    assert ui.run('gdm-station-focused', '')['outcome'] == 'passed'


def test_station_entry_and_return_do_not_require_a_named_parent():
    station = Node('Oh No! Parent Control', 'push button')
    ui = station_greeter(station)
    assert ui.run('gdm-station-list', '')['focused'] is True
    assert ui.run('gdm-station-focused', '')['outcome'] == 'passed'
    assert ui.run('gdm-station-returned', '')['outcome'] == 'passed'


@pytest.mark.parametrize('fault', ['missing', 'duplicate', 'disabled', 'hidden', 'prompt'])
def test_station_only_greeter_still_rejects_unusable_entry(fault):
    station = Node('Oh No! Parent Control', 'push button')
    rows = [] if fault == 'missing' else [station]
    if fault == 'duplicate': rows.append(Node('Oh No! Parent Control', 'push button'))
    if fault == 'disabled': station.states.discard('sensitive')
    if fault == 'hidden': station.states.clear()
    if fault == 'prompt': rows.append(Node('Password', 'password text'))
    with pytest.raises(UiError):
        station_greeter(*rows).run('gdm-station-list', '')
    station.component.grab_focus.assert_not_called()


def test_unnamed_station_row_uses_exact_nested_labels_only_to_bind_its_button():
    parent = Node('Jamie (Parent)', 'push button')
    labels = [Node('Oh No! Parent Control', 'label'),
              Node('oh-no-parent-control', 'label')]
    station = Node('', 'push button', children=labels,
                   states=('showing', 'visible', 'sensitive', 'focused'))
    ui = station_greeter(parent, station)
    assert ui.run('gdm-station-focused', '')['outcome'] == 'passed'
    for label in labels:
        label.component.grab_focus.assert_not_called()
        label.action.do_action.assert_not_called()


RUN = r'''
use strict;
use warnings;
use JSON::PP;
our @events;
our $destination = shift // 'default-request-form';
our $failure = shift // '';
BEGIN { $INC{'testapi.pm'} = 1; }
package testapi;
sub current_console { 'sut' }
sub reset_consoles { push @main::events, ['reset'] }
sub select_console { push @main::events, ['console', $_[0]] }
sub record_info { push @main::events, ['stage', $_[0]] }
sub send_key { push @main::events, ['key', $_[0]] }
sub console { bless {}, 'Console' }
sub power { push @main::events, ['power', $_[0]] }
sub check_shutdown { 1 }
package Console;
sub disable { push @main::events, ['disable'] }
package main;
require onpc_kiosk_entry;
my $ok = eval {
    onpc_kiosk_entry::run(sub {
        my ($stage) = @_;
        push @events, ['exchange', $stage];
        die 'injected observation failure' if $stage eq $failure;
        return {ui_focused => 1} if $stage eq 'station-list';
        return {station_destination => $destination} if $stage eq 'station-branch';
        return {observed => $stage};
    });
    1;
};
print encode_json({ok => $ok ? 1 : 0, events => \@events});
'''


def test_station_worker_uses_only_the_intended_passwordless_route():
    result = json.loads(run_perl(RUN).stdout)
    assert result['ok']
    exchanges = [event[1] for event in result['events'] if event[0] == 'exchange']
    assert exchanges == [
        'station-list', 'station-focused', 'station-branch', 'request-form',
        'cancel', 'returned']
    keys = [event[1] for event in result['events'] if event[0] == 'key']
    assert keys == ['ret']
    assert not any(event[0] == 'secret' for event in result['events'])
    assert result['events'][-3:] == [
        ['disable'], ['power', 'off'], ['stage', 'shutdown']]


@pytest.mark.parametrize('failure', ['request-form', 'cancel', 'returned'])
def test_station_worker_requires_public_form_exit_and_return_before_finish(failure):
    result = json.loads(run_perl(RUN, 'default-request-form', failure).stdout)
    assert not result['ok']
    assert result['events'][-1] == ['exchange', failure]
    assert not any(event[0] == 'power' for event in result['events'])


@pytest.mark.parametrize('destination', ['greeter-controls', '', 'desktop'])
def test_station_worker_never_activates_an_unresolved_session_choice(destination):
    result = json.loads(run_perl(RUN, destination).stdout)
    assert not result['ok']
    assert [event[1] for event in result['events'] if event[0] == 'key'] == ['ret']
    assert result['events'][-1] == ['exchange', 'station-branch']


def test_station_default_branch_requires_owned_window_and_form_ids():
    ui, _ = request_form()
    ui.branch_owner = 'station'
    assert ui.run('station-entry-branch', '')['branch'] == {
        'destination': 'default-request-form', 'controls': []}
    ui.find_id('kiosk-request-form').identity = ''
    with pytest.raises(UiError, match='station-default-destination'):
        ui.run('station-entry-branch', '')


@pytest.mark.parametrize('fault', [
    None, 'wrong-session', 'duplicate-window', 'duplicate-form',
    'hidden-window', 'hidden-form', 'stale',
])
def test_station_default_entry_requires_one_fresh_owned_destination(fault):
    ui, _ = request_form()
    ui.branch_owner = 'greeter' if fault == 'wrong-session' else 'station'
    desktop = ui.api.get_desktop(0)
    window = ui.find_id('kiosk-request-window')
    form = ui.find_id('kiosk-request-form')
    if fault == 'duplicate-window':
        desktop.children.append(Node(identity='kiosk-request-window'))
    elif fault == 'duplicate-form':
        form.parent.children.append(Node(identity='kiosk-request-form'))
    elif fault == 'hidden-window':
        window.states.discard('showing')
    elif fault == 'hidden-form':
        form.states.discard('showing')
    elif fault == 'stale':
        form.states.add('defunct')
    if fault:
        with pytest.raises(UiError):
            ui.run('station-default-entry', '')
    else:
        assert ui.run('station-default-entry', '')['entry'] == {
            'destination': 'default-request-form'}


@pytest.mark.parametrize('destination', [
    'greeter-controls', 'desktop', '', None,
])
def test_station_default_entry_transport_rejects_every_unsupported_branch(destination):
    from types import SimpleNamespace
    from unittest.mock import Mock
    from ui_observations import UiObservations

    result = {'operation': 'station-default-entry', 'outcome': 'passed',
              'interface': 'ApplicationUI+external-provider', 'entry': {'destination': destination}}
    transport = SimpleNamespace(call=Mock(return_value=json.dumps(result).encode()))
    with pytest.raises(EvidenceError, match='ui:station-default-entry'):
        UiObservations(transport).observe('station-default-entry')


def test_station_default_entry_transport_accepts_only_the_bound_default():
    from types import SimpleNamespace
    from unittest.mock import Mock
    from ui_observations import UiObservations

    result = {'operation': 'station-default-entry', 'outcome': 'passed',
              'interface': 'ApplicationUI+external-provider',
              'entry': {'destination': 'default-request-form'}}
    transport = SimpleNamespace(call=Mock(return_value=json.dumps(result).encode()))
    assert UiObservations(transport).observe('station-default-entry') == result


@pytest.mark.parametrize('fault', [None, 'unknown-destination', 'extra', 'unresolved-default', 'private-label', 'invalid-state'])
def test_station_branch_transport_only_accepts_bounded_sanitized_evidence(fault):
    from types import SimpleNamespace
    from unittest.mock import Mock
    from ui_observations import UiObservations

    control = {'label': 'session-chooser', 'role': 'push button',
               'public_id_present': False, 'sensitive': True, 'focused': False}
    branch = {'destination': 'greeter-controls', 'controls': [control]}
    result = {'operation': 'station-entry-branch', 'outcome': 'passed',
              'interface': 'ApplicationUI+external-provider', 'branch': branch}
    if fault == 'unknown-destination':
        branch['destination'] = 'desktop'
    elif fault == 'extra':
        branch['extra'] = 'private'
    elif fault == 'unresolved-default':
        branch['destination'] = 'default-request-form'
    elif fault == 'private-label':
        control['label'] = 'Private unexpected label'
    elif fault == 'invalid-state':
        control['focused'] = 1
    transport = SimpleNamespace(call=Mock(return_value=json.dumps(result).encode()))
    if fault:
        with pytest.raises(EvidenceError):
            UiObservations(transport).observe('station-entry-branch')
    else:
        assert UiObservations(transport).observe('station-entry-branch') == result


@pytest.mark.parametrize('streamed', [True, False])
def test_large_standalone_observer_uses_guarded_stdin_not_one_exec_argument(tmp_path, monkeypatch, streamed):
    from types import SimpleNamespace
    from unittest.mock import Mock
    import ui_observations
    import vm_transport

    source = '# Standalone fixture source\n' + '# padded\n' * 40000
    reader = 'READER = "public-atspi"\n'
    e2e = tmp_path / 'tests/e2e'
    e2e.mkdir(parents=True)
    (e2e / 'accessible_ui.py').write_text(source)
    (e2e / 'session_control.py').write_text('SESSION_CONTROL = True\n')
    (e2e / 'public_atspi.py').write_text(reader)
    (e2e / 'block_semantics.py').write_text('SEMANTICS = True\n')
    (e2e / 'feedback_formats.py').write_text('FORMATS = True\n')
    (e2e / 'download_destination.py').write_text('DESTINATION = True\n')
    (e2e / 'fixture_ui.py').write_text('FIXTURE_UI = True\n')
    service = tmp_path / 'common/oh_no_parent_control_ui'
    service.mkdir(parents=True)
    (service / 'application_ui.py').write_text('SERVICE = True\n')
    (service / 'application_ui_client.py').write_text(
        'from .application_ui import SERVICE\nCLIENT = SERVICE\n')
    support = tmp_path / 'tests/support'
    support.mkdir()
    (support / 'application_ui.py').write_text(
        'from common.oh_no_parent_control_ui.application_ui_client import CLIENT\nSUPPORT = CLIENT\n')
    (e2e / 'application_ui.py').write_text(
        'from application_ui_support import SUPPORT\nADAPTER = SUPPORT\n')
    data = tmp_path / 'data'
    data.mkdir()
    (data / 'app.json').write_text('{"version": "9.8.7"}')
    monkeypatch.setattr(ui_observations.system, 'ROOT', tmp_path)
    result = {'operation': 'gdm-focused', 'outcome': 'passed', 'interface': 'ApplicationUI+external-provider'}
    raw = json.dumps(result).encode()
    def call(argv, **kwargs):
        import sys
        from unittest.mock import patch
        assert argv == ['/usr/bin/python3', '-I', '-', 'gdm-focused', '9.8.7']
        assert kwargs['input'].endswith(source.encode())
        assert len(kwargs['input']) > 128 * 1024
        # Execute only the supplied inert fixture modules. This checks package
        # and import ordering as well as inclusion of the shared API facade.
        with patch.dict(sys.modules):
            exec(compile(kwargs['input'], '<observer-fixture>', 'exec'), {})
            for name, marker in (
                    ('application_ui', 'ADAPTER'), ('application_ui_support', 'SUPPORT'),
                    ('session_control', 'SESSION_CONTROL'), ('block_semantics', 'SEMANTICS'),
                    ('feedback_formats', 'FORMATS'), ('download_destination', 'DESTINATION'),
                    ('fixture_ui', 'FIXTURE_UI')):
                assert getattr(sys.modules[name], marker) is True
            assert sys.modules['public_atspi'].READER == 'public-atspi'
        config = {'directory': str(tmp_path), 'run': 'a' * 32, 'domain_uuid': 'b' * 32}
        assert len(vm_transport.remote(config, argv).encode()) < 4096
        if streamed:
            kwargs['on_output'](raw + b'\n')
        return raw

    transport = SimpleNamespace(call=Mock(side_effect=call), commands=SimpleNamespace(progress=None))
    assert ui_observations.UiObservations(
        transport, system_prompt=Mock() if streamed else None).observe('gdm-focused') == result
    transport.call.assert_called_once()


@pytest.mark.parametrize('fault', [None, 'wrong-owner', 'duplicate', 'password', 'wrong-recipient', 'stale'])
def test_station_branch_observes_public_controls_without_action_or_private_labels(fault):
    chooser = Node('Select Session', 'push button')
    choice = Node('Oh No! Parent Control', 'radio menu item')
    private = Node('Private unexpected text', 'push button')
    recipient = Node('oh-no-parent-control', 'label')
    ui = station_greeter(chooser, choice, private, recipient)
    ui.branch_owner = 'greeter'
    app = ui.api.get_desktop(0).children[0]
    if fault == 'wrong-owner':
        app.name = 'Other application'
    elif fault == 'duplicate':
        app.children.append(Node('Select Session', 'push button'))
    elif fault == 'password':
        app.children.append(Node('Password', 'password text'))
    elif fault == 'wrong-recipient':
        recipient.name = 'Jamie (Parent)'
    elif fault == 'stale':
        choice.states.add('defunct')
    if fault:
        with pytest.raises(UiError):
            ui.run('station-entry-branch', '')
    else:
        branch = ui.run('station-entry-branch', '')['branch']
        assert branch['destination'] == 'greeter-controls'
        assert {control['label'] for control in branch['controls']} == {'session-chooser', 'station', 'unresolved'}
        assert 'Private' not in json.dumps(branch)
    for control in (chooser, choice, private):
        control.action.do_action.assert_not_called()
        control.component.grab_focus.assert_not_called()


@pytest.mark.parametrize('owner', ['greeter', 'station', 'other', 'duplicate'])
def test_station_branch_connection_rejects_wrong_or_ambiguous_active_owner(monkeypatch, owner):
    from types import SimpleNamespace
    import accessible_ui

    def call(argv, **_kwargs):
        if argv[1] == 'list-sessions':
            return SimpleNamespace(stdout='c1\nc2\n' if owner == 'duplicate' else 'c1\n')
        kind = 'greeter' if owner == 'greeter' else 'user'
        uid = 61234 if owner == 'greeter' else 1000 if owner == 'other' else 1234
        return SimpleNamespace(stdout=f'Class={kind}\nActive=yes\nRemote=no\nType=wayland\nSeat=seat0\nUser={uid}')
    monkeypatch.setattr(accessible_ui.subprocess, 'run', call)
    monkeypatch.setattr(accessible_ui.pwd, 'getpwnam', lambda _: SimpleNamespace(pw_uid=1234))
    monkeypatch.setattr(accessible_ui.pwd, 'getpwuid', lambda uid: SimpleNamespace(pw_uid=uid))
    if owner in ('other', 'duplicate'):
        with pytest.raises(UiError):
            accessible_ui.greeter_account(station_branch=True)
    else:
        account, observed = accessible_ui.greeter_account(station_branch=True)
        assert observed == owner
        assert account.pw_uid == (61234 if owner == 'greeter' else 1234)
