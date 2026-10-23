"""Shared input authorization, evidence identity and private-field safeguards."""

from types import SimpleNamespace
from unittest.mock import Mock
import json

import pytest
import accessible_ui
from private_artifacts import EvidenceError
from tests.support.accessible_ui import Node, ui_for


@pytest.mark.parametrize('fault', ['', 'wrong-stage', 'wrong-token', 'uncertain'])
def test_actual_exchange_releases_only_one_validated_keyboard_batch(tmp_path, fault):
    from tests.support.perl import run_perl
    from tests.support.paths import ROOT
    source = (ROOT / 'tests/integration/graphical_smoke/tests/smoke.pm').read_text()
    exchange = source[source.index('sub exchange {'):source.index('\nsub capture {')]
    proof = {'stage': 'other' if fault == 'wrong-stage' else 'renamed',
             'token': 'invalid' if fault == 'wrong-token' else 'a' * 32,
             'source': 'b' * 64, 'binding': 'overlay-approve', 'values': ['ret'], 'child': 'child'}
    (tmp_path / 'renamed.input.json').write_text(json.dumps(proof))
    result = json.loads(run_perl('use strict; use warnings; use JSON::PP; use Time::HiRes qw(time sleep);\n' + exchange + r'''
my ($directory, $fault) = @ARGV; chdir($directory) or die 'chdir';
my $count = 0;
my $ok = eval { exchange('renamed', undef, sub {
    $count++; die 'uncertain' if $fault eq 'uncertain';
    open(my $reply, '>', 'renamed.reply.json') or die 'reply';
    print {$reply} encode_json({observed => 'renamed'}); close($reply);
}); 1; };
print encode_json({ok => $ok ? 1 : 0, count => $count});
''', str(tmp_path), fault).stdout)
    assert result == {'ok': int(not fault), 'count': int(fault not in ('wrong-stage', 'wrong-token'))}
    assert (tmp_path / 'renamed.input-done.json').exists() is (not fault)


@pytest.mark.parametrize('fault', ['', 'no-ready', 'duplicate', 'foreign', 'boot',
                                  'storage', 'input', 'observer', 'cancel', 'oversize', 'order'])
def test_accessibility_trace_stream_brackets_one_input_and_latches(monkeypatch, fault):
    from ui_observations import UiObservations
    operations, retained = [], []
    transport = SimpleNamespace(commands=SimpleNamespace(progress=None))
    reader = UiObservations(transport)
    reader.boot_guard = 'b' * 64

    def call(argv, *, input, timeout, on_output=None):
        operation = argv[3]
        operations.append(operation)
        if operation == 'parent-toggle-enabled':
            assert retained and argv[-1] == 'c' * 64
            if fault == 'input':
                raise OSError('uncertain action')
            reply = json.dumps({'operation': operation, 'outcome': 'passed', 'interface': 'ApplicationUI+external-provider',
                               'boot_sha256': 'b' * 64,
                               'toggle': {'state': True, 'activated': True}}).encode()
            assert on_output is not None  # The nested call must own its parser.
            on_output(reply + b'\n')
            return reply
        assert operation == 'parent-checked-events'
        token = argv[-1]
        ready = {'event': 'accessibility-trace-ready', 'token': token, 'source': 'c' * 64,
                 'boot_sha256': 'b' * 64, 'checked': False}
        if fault == 'foreign': ready['token'] = 'd' * 32
        if fault == 'boot': ready['boot_sha256'] = 'd' * 64
        if fault != 'no-ready':
            encoded = json.dumps(ready).encode() + b'\n'
            on_output(encoded[:17])
            on_output(encoded[17:])
        if fault == 'duplicate': on_output(encoded)
        if fault == 'observer': raise OSError('observer lost')
        if fault == 'cancel': raise KeyboardInterrupt()
        samples = [{'elapsed_ms': i, 'checked': True, 'source': 'application-ui'} for i in range(32)]
        if fault == 'order': samples[-1]['elapsed_ms'] = 0
        if fault == 'oversize': samples.append(samples[-1])
        reply = {'operation': operation, 'outcome': 'passed', 'interface': 'ApplicationUI+external-provider',
                 'boot_sha256': 'b' * 64, 'trace': {'token': token, 'source': 'c' * 64,
                     'terminal': True, 'samples': samples}}
        on_output(json.dumps(reply).encode() + b'\n')
        return b''

    transport.call = call
    def retain(token, index, sample):
        if fault == 'storage': raise OSError('durable readiness failed')
        retained.append((token, index, sample))
    reader.trace_sink = retain
    if fault:
        with pytest.raises((EvidenceError, OSError, KeyboardInterrupt)):
            reader.observe_accessibility_input('parent-toggle-enabled', True)
        assert reader.trace_failed and reader.accessibility_trace is None
        with pytest.raises(EvidenceError):
            reader.observe_accessibility_input('parent-toggle-enabled', True)
        with pytest.raises(EvidenceError):
            reader.observe('parent-toggle-enabled')
        assert operations.count('parent-toggle-enabled') == (
            0 if fault in ('no-ready', 'foreign', 'boot', 'storage') else 1)
    else:
        result = reader.observe_accessibility_input('parent-toggle-enabled', True)
        assert result['operation'] == 'accessibility-input-trace'
        assert len(result['samples']) == 32 and len(retained) == 33
        assert operations == ['parent-checked-events', 'parent-toggle-enabled']
    assert transport.commands.progress is None


def test_transition_pump_runs_without_worker_checkpoint_and_storage_is_immutable(tmp_path):
    from installed_journey import InstalledJourney
    from trace_transition import PLAN as plan
    context = SimpleNamespace(directory=tmp_path)
    journey = InstalledJourney(context, Mock(), plan)
    journey.trace_token = 'a' * 32
    journey.ui = SimpleNamespace(poll_trace=Mock())
    guard = Mock()
    journey.step(guard)
    journey.ui.poll_trace.assert_called_once_with()
    journey.retain_trace_sample('a' * 32, 0, {'state': 'public'})
    with pytest.raises(FileExistsError):
        journey.retain_trace_sample('a' * 32, 0, {'state': 'replacement'})
    assert json.loads((tmp_path / ('trace-' + 'a' * 32 + '-000.json')).read_text()) == {'state': 'public'}
    journey.ui.poll_trace.side_effect = EvidenceError('ui:trace-terminal')
    with pytest.raises(EvidenceError, match='trace-terminal'):
        journey.step(guard)
    with pytest.raises(EvidenceError, match='previous-failure'):
        journey.step(guard)


def trace_reader(monkeypatch):
    import ui_observations
    ui, _, _, _ = feedback_ui()
    value = ui.feedback_snapshot(states=True)
    reply = {'operation': 'feedback-state-empty', 'outcome': 'passed', 'interface': 'ApplicationUI+external-provider',
             'feedback_state': value, 'boot_sha256': 'b' * 64}
    reader = ui_observations.UiObservations(Mock())
    reader.boot_guard = 'b' * 64
    reader.call = Mock(return_value=(json.dumps(reply).encode(), []))
    clock = Mock(side_effect=range(100))
    monkeypatch.setattr(reader, '_trace_clock', clock)
    return reader, reply, clock




@pytest.mark.parametrize('fault', ['duplicate', 'missing', 'foreign', 'stale', 'input', 'boot'])
def test_stable_trace_refuses_and_latches_without_replay(monkeypatch, fault):
    reader, reply, clock = trace_reader(monkeypatch)
    if fault == 'missing':
        with pytest.raises(EvidenceError, match='trace-token'):
            reader.finish_trace(None)
    else:
        ready = reader.start_trace()
        if fault == 'stale':
            clock.side_effect = None
            clock.return_value = 61
        if fault == 'boot':
            reply['boot_sha256'] = 'c' * 64
        reader.call.return_value = (json.dumps(reply).encode(), [])
        with pytest.raises(EvidenceError):
            if fault == 'duplicate':
                reader.start_trace()
            elif fault == 'input':
                reader.observe('feedback-close')
            else:
                reader.finish_trace('foreign' if fault == 'foreign' else ready['token'])
    calls = reader.call.call_count
    assert reader.trace_failed and reader.trace is None
    with pytest.raises(EvidenceError, match='trace-previous-failure'):
        reader.start_trace()
    assert reader.call.call_count == calls


def test_stable_trace_new_entry_cannot_consume_prior_token(monkeypatch):
    reader, _, _ = trace_reader(monkeypatch)
    old = reader.start_trace()['token']
    reader.finish_trace(old)
    new = reader.start_trace()['token']
    assert new != old
    with pytest.raises(EvidenceError, match='trace-token'):
        reader.finish_trace(old)
    assert reader.call.call_count == 4


def chooser_ui(*, portal=False):
    ui, parent, caller, controls = feedback_ui()
    ui.api.StateType.MULTISELECTABLE = 'multiselectable'
    names = accessible_ui.CHOOSER_FILES
    items = [Node(name + ('. File' if portal else ''), role='list item') for name in names]
    selected = []
    selection = SimpleNamespace()
    view = Node(role='list', children=items,
                states=('visible', 'showing', 'sensitive', 'multiselectable'))
    view.get_selection_iface = lambda: selection
    ui.api.Selection = SimpleNamespace(
        get_n_selected_children=lambda _: len(selected),
        get_selected_child=lambda _, index: selected[index],
        select_all=Mock(side_effect=lambda _: selected.__setitem__(slice(None), items) or True))
    accept = Node('Open', role='push button')
    cancel = Node('Cancel', role='push button')
    window = Node(role='file chooser', children=[view, accept, cancel],
                  states=('visible', 'showing', 'active', 'modal', 'sensitive'))
    window.relations = [SimpleNamespace(get_relation_type=lambda: 'controlled-by',
        get_n_targets=lambda: 1, get_target=lambda _: caller)]
    parent.children.append(window)
    window.parent = parent
    ui.prompt_enabled = True
    ui.prompt_session = 'desktop'
    if portal:
        window.relations = []  # Imported Wayland parents have no GTK relation.
        # Nautilus cancels through its window close control, not a Cancel button.
        cancel.name = 'Close'
        ui.chooser_portal_owner = Mock(side_effect=lambda caller, provider:
            accessible_ui.validate_chooser_portal_owner(portal_query(), caller, provider))
        parent.children.remove(window)
        accept.identity = 'accept_button'
        window.identity = 'NautilusFileChooser'
        window.role = 'dialog'
        application = Node('org.gnome.Nautilus', role='application', children=[window])
        for node in (application, window, view, *items, accept, window.children[-1]):
            node.get_process_id = lambda: 200
        window.get_application = lambda: application
        desktop = Node(role='desktop', children=[ui.root(), application])
        ui.api.get_desktop = lambda _: desktop
    return ui, window, view, items, selected, accept, caller




def save_ui():
    ui, window, _, _, _, accept, caller = chooser_ui(portal=True)
    accept.name = 'Save'
    field = Node(role='text', identity='filename_entry', states=(
        'visible', 'showing', 'sensitive', 'editable', 'focused'))
    field.get_process_id = lambda: 200
    field.value = 'diagnostic-logs.zip'
    field.get_text_iface = lambda: field
    field.get_editable_text_iface = lambda: field
    ui.api.Text = SimpleNamespace(get_character_count=lambda f: len(f.value),
                                 get_text=lambda f, a, b: f.value[a:b])
    ui.api.EditableText = SimpleNamespace(set_text_contents=Mock(
        side_effect=lambda f, value: setattr(f, 'value', value) or True))
    window.children.append(field)
    return ui, window, field, accept, caller


def collapse_save_name(ui, window, field):
    # Nautilus removes the transient editor from AT-SPI on focus loss.
    window.children.remove(field)
    label = Node(field.value, role='label', identity='filename_label')
    edit = Node(field.value, role='button', children=[label])
    reset = Node('Reset File Name', role='button', identity='filename_undo_button')
    for node in (label, edit, reset):
        node.get_process_id = lambda: 200
    ui.api.RelationType.LABELLED_BY = 'labelled-by'
    edit.relations = [SimpleNamespace(get_relation_type=lambda: 'labelled-by',
        get_n_targets=lambda: 1, get_target=lambda _: label)]
    window.children.extend([edit, reset])

    def reveal(_):
        window.children.remove(edit)
        window.children.append(field)
        field.states.add('focused')
        return True
    edit.action.do_action.side_effect = reveal
    return edit, label, reset


@pytest.mark.parametrize('fault', ['', 'directory', 'input-echo', 'name', 'uncertain'])
def test_save_checks_destination_then_restored_name_before_single_accept(fault):
    assert accessible_ui.SAVE_DIRECTORY == '/home/onpc-parent-jamie/Downloads'
    ui, window, field, accept, _ = save_ui()
    field.value = accessible_ui.SAVE_NAMES[0]
    edit, _, reset = collapse_save_name(ui, window, field)
    location = Node(role='text', identity='location_entry', states=(
        'visible', 'showing', 'sensitive', 'editable', 'focused'))
    location.get_process_id = lambda: 200
    location.get_text_iface = lambda: location
    location.value = accessible_ui.SAVE_DIRECTORY
    window.children.append(location)
    accept.action.do_action.side_effect = lambda _: window.states.clear() or True
    if fault == 'directory':
        location.value += '-wrong'
    elif fault == 'input-echo':
        location.value += '/'
    if fault in ('directory', 'input-echo'):
        with pytest.raises((accessible_ui.UiError, TimeoutError)):
            ui.save_chooser_operation('save-chooser-destination')
        accept.action.do_action.assert_not_called()
        return
    ui.save_chooser_operation('save-chooser-destination')
    location.states.remove('showing')
    if fault == 'name':
        field.value = 'Wrong.zip'
    elif fault == 'uncertain':
        accept.action.do_action.side_effect = TimeoutError
    if fault == 'name':
        with pytest.raises(accessible_ui.UiError):
            ui.save_chooser_operation('save-chooser-restored')
        accept.action.do_action.assert_not_called()
    else:
        ui.save_chooser_operation('save-chooser-restored')
        if fault == 'uncertain':
            with pytest.raises(TimeoutError):
                ui.save_chooser_operation('save-chooser-accept')
            with pytest.raises(accessible_ui.UiError, match='uncertain-input'):
                ui.save_chooser_operation('save-chooser-accept')
        else:
            ui.save_chooser_operation('save-chooser-accept')
        accept.action.do_action.assert_called_once()
        if not fault:
            assert ui.chooser_snapshot(mode='save', absent=True)
        edit.action.do_action.assert_called_once()
    reset.action.do_action.assert_not_called()


def portal_query():
    """Public introspection for one live delegated request, no host bus."""
    def query(bus, path, interface, method, signature, args):
        if method == 'GetNameOwner':
            return ':1.20'
        if method == 'GetConnectionUnixProcessID':
            return 200 if args == (':1.20',) else Node().get_process_id()
        if path.endswith('/request'):
            return '<node><node name="1_10"/></node>'
        if path.endswith('/1_10'):
            return '<node><node name="gtk123"/></node>'
        prefix = 'org.freedesktop.portal' if bus == 'org.freedesktop.portal.Desktop' else 'org.freedesktop.impl.portal'
        return '<node><interface name="' + prefix + '.Request"/></node>'
    return query


@pytest.mark.parametrize('fault', ['none', 'wrong-provider', 'wrong-caller', 'no-request',
    'other-request', 'two-tokens', 'path-injection', 'missing-frontend', 'missing-backend',
    'malformed', 'oversize', 'replaced'])
def test_portal_request_proves_live_provider_and_caller_or_refuses(fault):
    baseline = portal_query()
    calls = []
    def query(bus, path, interface, method, signature, args):
        calls.append((bus, path, method, args))
        if method == 'GetConnectionUnixProcessID':
            if fault == 'wrong-provider' and args == (':1.20',):
                return 999
            if fault == 'wrong-caller' and args == (':1.10',):
                return 999
        if method == 'GetNameOwner' and fault == 'replaced' and len(calls) > 1:
            return ':1.21'
        if method == 'Introspect':
            if fault == 'malformed':
                return '<node'
            if fault == 'oversize':
                return 'x' * 65537
            if path.endswith('/request'):
                if fault == 'no-request':
                    return '<node/>'
                if fault == 'other-request':
                    return '<node><node name="1_10"/><node name="1_11"/></node>'
            if path.endswith('/1_10'):
                if fault == 'two-tokens':
                    return '<node><node name="a"/><node name="b"/></node>'
                if fault == 'path-injection':
                    return '<node><node name="../other"/></node>'
            if path.endswith('/gtk123') and (
                    fault == 'missing-frontend' and bus == 'org.freedesktop.portal.Desktop'
                    or fault == 'missing-backend' and bus == ':1.20'):
                return '<node/>'
        return baseline(bus, path, interface, method, signature, args)
    if fault == 'none':
        accessible_ui.validate_chooser_portal_owner(query, Node().get_process_id(), 200)
        assert len(calls) == 9
    else:
        with pytest.raises(accessible_ui.UiError, match='chooser-'):
            accessible_ui.validate_chooser_portal_owner(query, Node().get_process_id(), 200)
    assert {call[2] for call in calls} <= {'GetNameOwner', 'GetConnectionUnixProcessID', 'Introspect'}


@pytest.mark.parametrize('failed', [False, True])
def test_portal_owner_reads_current_session_without_activation_and_closes(monkeypatch, failed):
    from gi.repository import Gio
    connection = Mock()
    baseline = portal_query()
    def reply(bus, path, interface, method, parameters, result_type, flags, timeout, cancellable):
        assert flags == Gio.DBusCallFlags.NO_AUTO_START
        assert timeout == 2000
        if failed:
            raise accessible_ui.UiError('ui:chooser-request-interface')
        args = parameters.unpack() if parameters is not None else ()
        return SimpleNamespace(unpack=lambda: (baseline(bus, path, interface, method, '', args),))
    connection.call_sync.side_effect = reply
    connect = Mock(return_value=connection)
    monkeypatch.setattr(Gio.DBusConnection, 'new_for_address_sync', connect)
    monkeypatch.setenv('DBUS_SESSION_BUS_ADDRESS', 'unix:path=/private-test-bus')
    ui, *_ = chooser_ui()
    if failed:
        with pytest.raises(accessible_ui.UiError, match='request-interface'):
            ui.chooser_portal_owner(Node().get_process_id(), 200)
    else:
        ui.chooser_portal_owner(Node().get_process_id(), 200)
    assert connect.call_args.args[0] == 'unix:path=/private-test-bus'
    connection.set_exit_on_close.assert_called_once_with(False)
    connection.close_sync.assert_called_once_with(None)


def test_portal_request_failure_prevents_selection_and_open():
    ui, _, _, _, _, accept, _ = chooser_ui(portal=True)
    ui.chooser_portal_owner.side_effect = accessible_ui.UiError('ui:chooser-request-caller')
    with pytest.raises(accessible_ui.UiError, match='request-caller'):
        ui.chooser_select_files()
    ui.api.Selection.select_all.assert_not_called()
    accept.action.do_action.assert_not_called()


@pytest.mark.parametrize('fault', ['wrong-caller', 'wrong-owner', 'secret',
                                  'authentication-title', 'other-modal', 'nested-modal'])
def test_portal_guard_rejects_unproven_or_additional_prompts(fault):
    ui, window, _, _, _, accept, _ = chooser_ui(portal=True)
    if fault == 'wrong-caller':
        window.relations = [SimpleNamespace(get_relation_type=lambda: 'controlled-by',
            get_n_targets=lambda: 1, get_target=lambda _: Node())]
    elif fault == 'wrong-owner':
        window.get_application().name = 'Unrelated application'
    elif fault == 'secret':
        window.children.append(Node(role='password text'))
    elif fault == 'authentication-title':
        window.name = 'Authentication Required'
    else:
        owner = window if fault == 'nested-modal' else window.get_application()
        owner.children.append(Node(role='dialog'))
    with pytest.raises(accessible_ui.UiError):
        ui.chooser_select_files()
    ui.api.Selection.select_all.assert_not_called()
    accept.action.do_action.assert_not_called()


def rejection_ui(case):
    ui, parent, dialog, controls = feedback_ui()
    projection, _ = accessible_ui.REJECTION_CASES[case]
    for binding in accessible_ui.FEEDBACK_PROJECTIONS[projection]:
        identity, value = accessible_ui.TEXT_VALUES[binding]
        controls[identity].text.count = len(value)
        controls[identity].text.value = value
    ui.api.Text.get_text = Mock(side_effect=lambda text, start, end: text.value[start:end])
    ui.api.Text.get_character_at_offset = Mock(side_effect=lambda text, offset: ord(text.value[offset]))
    ui.api.Text.get_attribute_run = Mock(side_effect=lambda text, offset, defaults: (
        ({'weight': '400', 'style': 'normal', 'underline': 'none', 'strikethrough': 'false'}
         if projection.startswith('length-') else
         {'weight': '700', 'style': 'italic', 'underline': 'single', 'strikethrough': 'true'}),
        offset, offset + 1))
    ui.activate_id = Mock()
    return ui, parent, dialog, controls


@pytest.mark.parametrize('fault', ['', 'body', 'reply', 'duplicate', 'owner', 'stale',
                                  'disabled', 'uncertain', 'wrong-entry'])
def test_invalid_only_send_requires_exact_fresh_owned_invalid_fixture(fault):
    case = 'complex'
    ui, parent, dialog, controls = rejection_ui(case)
    if fault == 'body':
        controls['feedback-editor-input'].text.count += 10
    elif fault == 'reply':
        controls['feedback-reply-email'].text.count += 1
    elif fault == 'duplicate':
        dialog.children.append(Node(identity='feedback-send'))
    elif fault == 'owner':
        ui.api.get_desktop(0).identity = 'other.app'
    elif fault == 'stale':
        controls['feedback-editor-input'].states.add('defunct')
    elif fault == 'disabled':
        controls['feedback-send'].states.discard('sensitive')
    elif fault == 'uncertain':
        ui.input_uncertain = True
    elif fault == 'wrong-entry':
        parent.children.clear()
    if fault:
        with pytest.raises(accessible_ui.UiError):
            ui.reject_invalid_feedback(case)
        ui.activate_id.assert_not_called()
    else:
        ui.reject_invalid_feedback(case)
        ui.activate_id.assert_called_once_with('feedback-send')


def test_rejection_refuses_valid_input_and_missing_format_at_last_line():
    ui, _, _, controls = rejection_ui('complex')
    with pytest.raises(accessible_ui.UiError, match='valid-refused'):
        ui.reject_invalid_feedback('valid')
    ui.api.Text.get_attribute_run.side_effect = lambda text, offset, defaults: (
        {'weight': '700', 'style': 'italic', 'underline': 'single',
         'strikethrough': 'false' if offset == len(accessible_ui.COMPLEX_BODY) - 1 else 'true'},
        offset, offset + 1)
    with pytest.raises(accessible_ui.UiError, match='format-proof'):
        ui.reject_invalid_feedback('complex')
    ui.activate_id.assert_not_called()
    ui, _, _, controls = rejection_ui('hidden')
    controls['feedback-editor-input'].text.value = 'a b'
    with pytest.raises(accessible_ui.UiError, match='nonempty-draft'):
        ui.reject_invalid_feedback('hidden')
    ui.activate_id.assert_not_called()


def test_rejection_values_stay_invalid_under_maintained_transport_limits():
    from common.oh_no_parent_control_ui import feedback_transport as transport
    assert accessible_ui.TEXT_VALUES['body-hidden'][1] == 'a\x01b'
    assert (transport.MAX_MESSAGE_UTF16, transport.MAX_HTML_UTF16) == (5000, 50000)
    html = '<p><strong><em><u><s>x</s></u></em></strong></p>' * accessible_ui.COMPLEX_LINES
    assert len(html) == 48 * accessible_ui.COMPLEX_LINES > transport.MAX_HTML_UTF16
    for case, (projection, explanation) in accessible_ui.REJECTION_CASES.items():
        body, reply = [accessible_ui.TEXT_VALUES[binding][1]
                       for binding in accessible_ui.FEEDBACK_PROJECTIONS[projection]]
        units = len(body.encode('utf-16-le')) // 2
        if explanation == 'length-invalid':
            assert units == transport.MAX_MESSAGE_UTF16 + 1
        else:
            assert units <= transport.MAX_MESSAGE_UTF16
        error = transport.validation_error(body, reply, '1.2', html if projection == 'rejection-complex' else '')
        assert accessible_ui.FEEDBACK_VALIDATION[error] == explanation


@pytest.mark.parametrize('family', ['ascii', 'mixed'])
def test_length_valid_boundary_cannot_reach_send_even_with_invalid_case_name(family):
    ui, _, _, controls = rejection_ui(family)
    value = accessible_ui.TEXT_VALUES[f'body-{family}-5000'][1]
    body = controls['feedback-editor-input'].text
    body.value, body.count = value, len(value)
    assert len(value.encode('utf-16-le')) // 2 == 5000
    ui.length_operation(f'length-{family}-refusal')
    ui.activate_id.assert_not_called()


def synthetic_feedback_ui():
    ui, parent, dialog, controls = feedback_ui()
    for binding in ('body-first', 'reply-first'):
        identity, value = accessible_ui.TEXT_VALUES[binding]
        controls[identity].text.count = len(value)
        controls[identity].text.value = value
    ui.api.Text.get_text = Mock(side_effect=lambda text, start, end: text.value[start:end])
    return ui, parent, dialog, controls


@pytest.mark.parametrize('missing', [False, True])
def test_privacy_reads_actual_disclosure_and_never_follows_external_link(missing):
    import ast
    # The shipped disclosure supplies the fixture; remove an essential promise
    # to prove a mere visible dialog cannot satisfy the observation.
    from tests.support.paths import ROOT
    tree = ast.parse((ROOT / 'common/oh_no_parent_control_ui/feedback.py').read_text())
    method = next(node for node in ast.walk(tree)
                  if isinstance(node, ast.FunctionDef) and node.name == '_show_log_privacy')
    from common.oh_no_parent_control_ui import messages
    suffix = getattr(messages, method.body[0].value.right.attr).source
    disclosure = ('Feedback, reply email addresses, attachments, and diagnostic logs are emailed '
                  'to support. Retention depends on our support mailbox and service providers, '
                  'including their backup policies. We do not currently guarantee deletion '
                  'within a fixed period.')
    ui, _, _, _ = synthetic_feedback_ui()
    ui.activate_id = Mock()
    ui.window_ready_to_close = Mock()
    root = Node(identity='feedback-privacy-dialog')
    text = Node(name=('' if missing else disclosure) + suffix, identity='feedback-privacy-text')
    ui.id_target = Mock(side_effect=[root, text])
    if missing:
        with pytest.raises(accessible_ui.UiError, match='ui:feedback-privacy-disclosure'):
            ui.feedback_privacy('synthetic-first')
    else:
        ui.feedback_privacy('synthetic-first')
    ui.activate_id.assert_called_once_with('feedback-privacy-link')


def feedback_ui():
    controls = {identity: Node(identity=identity) for identity in (
        'feedback-editor-input', 'feedback-reply-email', 'feedback-logs-row',
        'feedback-close', 'feedback-send', 'feedback-add-files',
        'feedback-download-logs', 'feedback-toggle-logs')}
    for identity in ('feedback-editor-input', 'feedback-reply-email'):
        node = controls[identity]
        node.states.add('editable')
        node.role = 'text'
        node.text = SimpleNamespace(count=0)
        node.get_text_iface = lambda node=node: node.text
    controls['feedback-logs-row'].name = 'diagnostic-logs.zip'
    dialog = Node(identity='feedback-dialog', children=list(controls.values()),
                  states=('showing', 'visible', 'sensitive', 'active'))
    parent = Node(identity='parent-window', children=[dialog])
    ui = ui_for(parent)
    ui.api.Text = SimpleNamespace(get_character_count=lambda text: text.count,
                                 get_text=Mock(side_effect=AssertionError('no raw text')))
    return ui, parent, dialog, controls
