"""Feedback reads refuse private drafts, incomplete sets and wrong entry."""

from dataclasses import FrozenInstanceError
from types import SimpleNamespace
from unittest.mock import MagicMock, Mock
import json

import pytest
import accessible_ui
import check_e2e_feedback_read as check
import check_graphical_smoke as smoke
from feedback_read import FeedbackReadJourney, PLAN
from private_artifacts import EvidenceError
from owned_commands import CommandError
from tests.support.accessible_ui import Node, ui_for
from ui_observations import FeedbackObservation
import check_e2e_text
from text_qualification import PLAN as TEXT_PLAN
from feedback_privacy import FeedbackPrivacyJourney, PLAN as PRIVACY_PLAN
import check_e2e_feedback_privacy
import check_e2e_feedback_states
from feedback_states import FeedbackStatesJourney, PLAN as STATES_PLAN
from ui_observations import FeedbackStateObservation

# Added Privacy checks retain this module's reviewed isolation: in-memory UI
# doubles, pytest-owned paths and waited, private Perl subprocesses only.
# FEED09 additions use those same resources and require no scheduler change.
# UI24/FEED04 additions retain the same in-memory and private Perl resources.
# DESK10 uses the same isolated doubles and waited private Perl processes.
# Rejection checks retain these resources; no network, shared paths or new buses.
# UTF-16 checks retain the same in-memory doubles and waited private Perl children.
# Complete-case composition uses the same private values and waited Perl children;
# no added shared paths, VM resources, caches, buses or scheduler classification.
# FILE03 adds only in-memory provider doubles and waited private Perl children;
# it retains this module's reviewed unit scheduling and resource ownership.
# Attachment-item checks retain those same private resources and scheduling.


def attachment_ui():
    import hashlib
    ui, parent, dialog, controls = feedback_ui()
    ui.api.RelationType.DESCRIBED_BY = 'described-by'
    rows = []
    for name, data in accessible_ui.ATTACHMENT_INPUTS:
        key = hashlib.sha256(name.encode() + b'\0' + data).hexdigest()[:16]
        remove = Node(identity='feedback-remove-attachment-' + key)
        subtitle = Node(f'{len(data)} bytes', role='label')
        row = Node(name, identity='feedback-attachment-' + key, children=[remove, subtitle])
        row.relations = [SimpleNamespace(
            get_relation_type=lambda: 'described-by', get_n_targets=lambda: 1,
            get_target=lambda _, subtitle=subtitle: subtitle)]
        remove.action.do_action.side_effect = lambda _, row=row: (dialog.children.remove(row) or True)
        row.parent = dialog
        dialog.children.append(row)
        rows.append(row)
    dialog.children.append(Node('2 file attachments ready.', identity='feedback-status'))
    return ui, dialog, rows


@pytest.mark.parametrize('fault', ['', 'name', 'size', 'order', 'duplicate', 'stale', 'missing',
                                  'inactive', 'no-size', 'ambiguous-size', 'foreign-size', 'hidden-size'])
def test_attachment_items_public_metadata_and_refusals(fault):
    ui, dialog, rows = attachment_ui()
    if fault == 'name': rows[0].name = 'Unexpected.txt'
    if fault == 'size': rows[0].children[1].name = '999 bytes'
    if fault == 'no-size': rows[0].relations = []
    if fault == 'ambiguous-size': rows[0].relations *= 2
    if fault == 'foreign-size': rows[0].relations = rows[1].relations
    if fault == 'hidden-size': rows[0].children[1].states.remove('visible')
    if fault == 'order': dialog.children[-3:-1] = reversed(rows)
    if fault == 'duplicate': dialog.children.append(Node(identity=rows[0].identity))
    if fault == 'stale': rows[0].states.add('defunct')
    if fault == 'missing': dialog.children.remove(rows[0])
    if fault == 'inactive': dialog.states.remove('active')
    if fault:
        with pytest.raises(accessible_ui.UiError):
            ui.attachment_operation('attachment-remove')
        rows[0].children[0].action.do_action.assert_not_called()
    else:
        assert ui.attachment_operation('attachment-details')['items'] == [
            ['Second note.txt', '33 bytes'], ['Synthetic note.txt', '26 bytes']]
        assert ui.attachment_operation('attachment-remove')['items'] == [['Synthetic note.txt', '26 bytes']]
        assert ui.attachment_operation('attachment-remaining')['items'] == [['Synthetic note.txt', '26 bytes']]


def test_attachment_removal_refuses_stale_list_and_wrong_item_without_replay():
    for wrong in (False, True):
        ui, dialog, rows = attachment_ui()
        action = rows[0].children[0].action.do_action
        action.side_effect = (lambda _: (dialog.children.remove(rows[1]) or True)) if wrong else None
        with pytest.raises(accessible_ui.UiError):
            ui.attachment_operation('attachment-remove')
        assert ui.input_uncertain
        with pytest.raises(accessible_ui.UiError):
            ui.attachment_operation('attachment-remove')
        assert action.call_count == 1


def test_attachment_removal_waits_for_queued_action_without_replay(monkeypatch):
    ui, dialog, rows = attachment_ui()
    ui.timeout = 1
    action = rows[0].children[0].action.do_action
    action.side_effect = None
    dispatch = Mock(side_effect=lambda _: dialog.children.remove(rows[0]))
    monkeypatch.setattr(accessible_ui.time, 'sleep', dispatch)
    assert ui.attachment_operation('attachment-remove')['items'] == [['Synthetic note.txt', '26 bytes']]
    assert action.call_count == 1
    assert dispatch.call_count == 1


def test_attachment_wrong_entry_is_publicly_checked():
    ui, _, _, _ = feedback_ui()
    assert ui.attachment_operation('attachment-wrong-entry') == {'checked': 'attachment-wrong-entry'}


@pytest.mark.parametrize('operation', sorted(accessible_ui.ATTACHMENT_OPERATIONS))
def test_attachment_controller_decodes_exact_metadata_and_refuses_corruption(operation):
    from ui_observations import UiObservations
    ui, _, _ = attachment_ui()
    if operation == 'attachment-wrong-entry':
        ui, _, _, _ = feedback_ui()
    if operation == 'attachment-remaining':
        ui.attachment_operation('attachment-remove')
    value = ui.attachment_operation(operation)
    result = {'operation': operation, 'outcome': 'passed', 'interface': 'AT-SPI', 'attachment': value}
    controller = UiObservations(Mock())
    controller.call = Mock(return_value=(json.dumps(result).encode(), []))
    assert controller.observe(operation)['attachment'] == value
    value['items'] = [['Unexpected.txt', '0 bytes']]
    controller.call.return_value = (json.dumps(result).encode(), [])
    with pytest.raises(EvidenceError, match='attachment-response'):
        controller.observe(operation)


def chooser_ui(*, portal=False):
    ui, parent, caller, controls = feedback_ui()
    ui.api.StateType.MULTISELECTABLE = 'multiselectable'
    items = [Node(name + ('. File' if portal else ''), role='list item')
             for name in accessible_ui.CHOOSER_FILES]
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


@pytest.mark.parametrize('portal', [False, True])
def test_chooser_selects_prepared_files_in_one_api_call(portal):
    ui, _, _, items, selected, accept, _ = chooser_ui(portal=portal)
    ui.chooser_operation('chooser-files')
    assert selected == items
    accept.action.do_action.assert_not_called()
    assert ui.chooser_selection(accessible_ui.CHOOSER_FILES)[2] == list(accessible_ui.CHOOSER_FILES)
    ui.api.Selection.select_all.assert_called_once()


@pytest.mark.parametrize('fault', ['', 'single-selection', 'ambiguous', 'missing-interface'])
def test_nautilus_custom_selection_model_without_multiselectable_hint(fault):
    ui, window, view, items, selected, accept, _ = chooser_ui(portal=True)
    view.name = 'Content View'
    view.states.remove('multiselectable')
    if fault == 'single-selection':
        ui.api.Selection.select_all.side_effect = lambda _: selected.append(items[0]) or True
    elif fault == 'ambiguous':
        duplicate = Node('Content View', role='list')
        duplicate.get_selection_iface = view.get_selection_iface
        window.children.append(duplicate)
    elif fault == 'missing-interface':
        view.get_selection_iface = lambda: None
    if fault:
        with pytest.raises(accessible_ui.UiError):
            ui.chooser_select_files()
        accept.action.do_action.assert_not_called()
        if fault != 'single-selection':
            ui.api.Selection.select_all.assert_not_called()
    else:
        ui.chooser_select_files()
        assert selected == items


@pytest.mark.parametrize('suffix', ['', '. Folder', '. File. Starred', '. File extra'])
def test_nautilus_file_labels_require_exact_registered_file_role(suffix):
    ui, _, _, items, _, accept, _ = chooser_ui(portal=True)
    items[0].name = accessible_ui.CHOOSER_FILES[0] + suffix
    with pytest.raises(accessible_ui.UiError, match='file-set'):
        ui.chooser_select_files()
    ui.api.Selection.select_all.assert_not_called()
    accept.action.do_action.assert_not_called()


def location_ui(*, portal=False):
    ui, window, *_ = chooser_ui(portal=portal)
    field = Node(role='text', identity='entry', states=(
        'visible', 'showing', 'sensitive', 'editable', 'focused'))
    field.get_process_id = window.get_process_id
    field.value = 'old location'
    field.get_text_iface = field.get_editable_text_iface = lambda: field
    window.children.append(field)
    field.parent = window
    ui.api.Text = SimpleNamespace(get_character_count=lambda node: len(node.value),
                                 get_text=lambda node, start, end: node.value[start:end])
    ui.api.EditableText = SimpleNamespace(set_text_contents=Mock(
        side_effect=lambda node, value: setattr(node, 'value', value) or True))
    return ui, window, field


@pytest.mark.parametrize('portal', [False, True])
def test_chooser_location_uses_editable_api_and_fresh_readback(portal):
    ui, _, field = location_ui(portal=portal)
    snapshot = ui.chooser_snapshot
    ui.chooser_snapshot = Mock(side_effect=snapshot)
    ui.chooser_operation('chooser-location')
    ui.api.EditableText.set_text_contents.assert_called_once_with(
        field, accessible_ui.CHOOSER_DIRECTORY + '/')
    assert ui.chooser_snapshot.call_count == 2
    assert not ui.input_uncertain


@pytest.mark.parametrize('fault', ['wrong-owner', 'wrong-id', 'no-focus', 'hidden',
    'disabled', 'ambiguous', 'no-api', 'refused', 'timeout', 'wrong-text', 'lost-focus'])
def test_chooser_location_refuses_unsafe_target_and_uncertain_input(fault):
    ui, window, field = location_ui(portal=True)
    setter = ui.api.EditableText.set_text_contents
    after_input = fault in ('refused', 'timeout', 'wrong-text', 'lost-focus')
    if fault == 'wrong-owner':
        field.get_process_id = lambda: 999
    elif fault == 'wrong-id':
        field.identity = 'search_entry'
    elif fault in ('no-focus', 'hidden', 'disabled'):
        field.states.remove({'no-focus': 'focused', 'hidden': 'visible', 'disabled': 'sensitive'}[fault])
    elif fault == 'ambiguous':
        window.children.append(Node(role='text', identity='entry', states=field.states))
    elif fault == 'no-api':
        field.get_editable_text_iface = lambda: None
    elif fault == 'timeout':
        setter.side_effect = TimeoutError
    elif fault in ('refused', 'wrong-text'):
        setter.side_effect = None
        setter.return_value = fault != 'refused'
    else:
        setter.side_effect = lambda *_: field.states.remove('focused') or True
    with pytest.raises((accessible_ui.UiError, TimeoutError)):
        ui.chooser_operation('chooser-location')
    if after_input:
        with pytest.raises(accessible_ui.UiError, match='uncertain-input'):
            ui.chooser_operation('chooser-location')
        setter.assert_called_once()
    else:
        setter.assert_not_called()


def test_portal_is_expected_only_inside_fresh_chooser_validation():
    ui, window, _, _, _, _, _ = chooser_ui(portal=True)
    assert ui.system_prompt_kind() == 'unknown'
    assert ui.chooser_snapshot()[-1] == 'nautilus-portal'
    assert ui.chooser_snapshot(absent=True) is False
    # A successful chooser read must not exempt this provider in later work.
    with pytest.raises(accessible_ui.UiError, match='system-prompt-refused'):
        ui.handle_system_prompt()
    window.states.clear()
    assert ui.chooser_snapshot(absent=True) is True


@pytest.mark.parametrize('portal', [False, True])
@pytest.mark.parametrize('button_role', ['push button', 'button'])
def test_chooser_cancel_invokes_provider_control_once_and_observes_closure(portal, button_role):
    ui, window, _, items, selected, accept, _ = chooser_ui(portal=portal)
    # Cancel does not require browsing to or selecting a candidate file.
    cancel = window.children[-1]
    accept.role = cancel.role = button_role
    cancel.action.do_action.side_effect = lambda _: window.states.clear() or True
    ui.chooser_operation('chooser-cancel')
    cancel.action.do_action.assert_called_once()
    accept.action.do_action.assert_not_called()
    assert ui.chooser_snapshot(absent=True) is True


@pytest.mark.parametrize('fault', ['missing', 'ambiguous', 'wrong-owner', 'hidden', 'disabled', 'uncertain'])
@pytest.mark.parametrize('button_role', ['push button', 'button'])
def test_portal_cancel_refuses_invalid_control_and_never_replays(fault, button_role):
    ui, window, _, items, selected, accept, _ = chooser_ui(portal=True)
    selected.append(items[0])
    cancel = window.children[-1]
    accept.role = cancel.role = button_role
    if fault == 'missing':
        cancel.name = 'Cancel'
    elif fault == 'ambiguous':
        window.children.append(Node('Close', role=button_role))
    elif fault == 'wrong-owner':
        cancel.get_process_id = lambda: 999
    elif fault in ('hidden', 'disabled'):
        cancel.states.remove('visible' if fault == 'hidden' else 'sensitive')
    else:
        cancel.action.do_action.side_effect = TimeoutError
    with pytest.raises((accessible_ui.UiError, TimeoutError)):
        ui.chooser_operation('chooser-cancel')
    accept.action.do_action.assert_not_called()
    if fault == 'uncertain':
        with pytest.raises(accessible_ui.UiError, match='uncertain-input'):
            ui.chooser_operation('chooser-cancel')
        cancel.action.do_action.assert_called_once()
    else:
        cancel.action.do_action.assert_not_called()


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


def test_portal_open_wait_validates_chooser_before_generic_prompt_refusal():
    ui, window, _, _, _, _, _ = chooser_ui(portal=True)
    states = window.states.copy()
    window.states.clear()
    ui.activate_id = Mock(side_effect=lambda _: window.states.update(states))
    ui.chooser_metadata = Mock(return_value={'route': 'nautilus-portal'})
    assert ui.chooser_operation('chooser-open')['provider']['route'] == 'nautilus-portal'
    ui.activate_id.assert_called_once_with('feedback-add-files')


@pytest.mark.parametrize('fault', ['wrong-caller', 'mode', 'inactive', 'not-modal',
    'ambiguous', 'wrong-file', 'single-mode', 'incomplete', 'disabled', 'uncertain'])
def test_chooser_refuses_before_selection_or_open(fault):
    ui, window, view, items, selected, accept, caller = chooser_ui()
    if fault == 'wrong-caller':
        window.relations[0].get_target = lambda _: Node()
    elif fault == 'mode':
        accept.name = 'Save'
    elif fault == 'inactive':
        window.states.remove('active')
    elif fault == 'not-modal':
        window.states.remove('modal')
    elif fault == 'ambiguous':
        window.parent.children.append(Node(role='file chooser', children=[Node('Open', role='push button')]))
    elif fault == 'wrong-file':
        items[0].name = 'Unregistered.txt'
    elif fault == 'single-mode':
        view.states.remove('multiselectable')
    elif fault == 'incomplete':
        window.get_child_count = Mock(side_effect=LookupError())
    elif fault == 'disabled':
        view.states.remove('sensitive')
    elif fault == 'uncertain':
        ui.input_uncertain = True
    with pytest.raises((accessible_ui.UiError, LookupError)):
        ui.chooser_select_files()
    ui.api.Selection.select_all.assert_not_called()
    accept.action.do_action.assert_not_called()


def test_chooser_uncertain_selection_cannot_replay_or_open():
    ui, _, _, _, _, accept, _ = chooser_ui()
    ui.api.Selection.select_all.side_effect = TimeoutError
    with pytest.raises(TimeoutError):
        ui.chooser_select_files()
    with pytest.raises(accessible_ui.UiError, match='uncertain-input'):
        ui.chooser_operation('chooser-accept')
    assert ui.api.Selection.select_all.call_count == 1
    accept.action.do_action.assert_not_called()


def test_chooser_refuses_partial_selection_without_opening_or_replaying():
    ui, _, _, items, selected, accept, _ = chooser_ui()
    def replace(_):
        selected[:] = [items[0]]
        return True
    ui.api.Selection.select_all.side_effect = replace
    with pytest.raises(accessible_ui.UiError, match='partial-selection'):
        ui.chooser_select_files()
    with pytest.raises(accessible_ui.UiError, match='uncertain-input'):
        ui.chooser_select_files()
    assert ui.api.Selection.select_all.call_count == 1
    accept.action.do_action.assert_not_called()


def test_chooser_open_refuses_partial_selection_even_without_selection_action():
    ui, _, _, items, selected, accept, _ = chooser_ui()
    selected.append(items[0])
    with pytest.raises(accessible_ui.UiError, match='partial-selection'):
        ui.chooser_operation('chooser-accept')
    accept.action.do_action.assert_not_called()


def test_chooser_attachment_readback_uses_exact_ids_names_and_status():
    import hashlib
    from synthetic_files_guest import FILES
    ui, _, dialog, _ = feedback_ui()
    assert sorted(FILES) == list(accessible_ui.CHOOSER_FILES)
    for name, data in FILES.items():
        key = hashlib.sha256(name.encode() + b'\0' + data).hexdigest()[:16]
        dialog.children.append(Node(name, identity='feedback-attachment-' + key))
    dialog.children.append(Node('2 file attachments ready.', identity='feedback-status'))
    ui.feedback_snapshot(attachments=True)
    with pytest.raises(accessible_ui.UiError, match='attachment-set'):
        ui.feedback_snapshot()
    dialog.children[-2].name = 'Unexpected.txt'
    with pytest.raises(accessible_ui.UiError, match='attachment-name'):
        ui.feedback_snapshot(attachments=True)


@pytest.mark.parametrize('items', [False, True])
@pytest.mark.parametrize('fault', ['', 'chooser-open', 'chooser-location',
    'chooser-files', 'chooser-accept', 'chooser-cancel', 'chooser-preserved'])
def test_chooser_worker_matches_plan_and_stops_at_failed_proof(fault, items):
    from file_chooser import PLAN as chooser_plan
    if items:
        from attachment_items import PLAN as chooser_plan
    from tests.support.perl import run_perl
    result = json.loads(run_perl(r'''
use strict; use warnings; use JSON::PP;
our (@events, @stages); our $fault = shift @ARGV; our $items = shift @ARGV;
BEGIN { $INC{'testapi.pm'} = 1; }
package testapi;
sub record_info { }
sub send_key { push @main::events, $_[0]; }
sub type_string { push @main::events, 'type'; }
package main;
require onpc_feedback_read;
no warnings 'redefine';
*onpc_gdm::reattach_functional = sub { };
*onpc_parent::open_for_child = sub { return $_[0]->seen('parent-selected'); };
*onpc_journey::finish = sub { push @events, 'finish'; };
my $ok = eval { onpc_feedback_read::run_file_chooser(sub {
    push @events, $_[0]; push @stages, $_[0];
    die 'failed proof' if $_[0] eq $fault;
    return {observed => $_[0]};
}, ($items ? (1) : ())); 1; };
print encode_json({ok => $ok ? 1 : 0, events => \@events, stages => \@stages});
''', fault, str(int(items))).stdout)
    stages = list(chooser_plan.screen_tags)
    stages = stages[stages.index('parent-selected'):]
    assert result['stages'] == (stages[:stages.index(fault) + 1] if fault else stages)
    assert result['ok'] == (not fault)
    assert result['events'][-1] == (fault or 'finish')
    if not fault:
        assert [event for event in result['events'] if event in ('ctrl-l', 'ctrl-a', 'ret', 'type')] == ['ctrl-l', 'ret']


def test_chooser_selector_registration_and_prerequisites(monkeypatch):
    import check_e2e_file_chooser
    run = Mock(return_value=0)
    monkeypatch.setattr(check_e2e_file_chooser, 'smoke', run)
    assert check_e2e_file_chooser.main() == 0
    assert run.call_args.kwargs['file_chooser'] is True
    with pytest.raises(CommandError):
        smoke.main(file_chooser=True)
    with pytest.raises(CommandError, match='file-chooser-prerequisites'):
        smoke.main(file_chooser=True, feedback_read=True)


@pytest.mark.parametrize('fault', ['attachment-wrong-entry', 'attachment-details',
                                  'attachment-remove', 'attachment-remaining'])
def test_attachment_worker_stops_at_each_failed_proof(fault):
    test_chooser_worker_matches_plan_and_stops_at_failed_proof(fault, True)


def test_attachment_selector_registration_and_prerequisites(monkeypatch):
    import check_e2e_attachment_items
    run = Mock(return_value=0)
    monkeypatch.setattr(check_e2e_attachment_items, 'smoke', run)
    assert check_e2e_attachment_items.main() == 0
    assert run.call_args.kwargs['attachment_items'] is True
    with pytest.raises(CommandError, match='attachment-items-prerequisites'):
        smoke.main(attachment_items=True, file_chooser=True)


@pytest.mark.parametrize('operation', sorted(accessible_ui.CHOOSER_OPERATIONS))
def test_chooser_real_controller_decodes_closed_evidence(operation):
    from ui_observations import UiObservations
    value = {'checked': operation}
    if operation in ('chooser-open', 'chooser-reopen'):
        value['provider'] = {'route': 'nautilus-portal', 'version': '50.1-1',
                             'locale': 'en_US.UTF-8', 'keyboard': [['xkb', 'us']]}
    if operation in ('chooser-attachments', 'chooser-preserved'):
        value['attachments'] = ['diagnostic-logs.zip', *accessible_ui.CHOOSER_FILES]
    result = {'operation': operation, 'outcome': 'passed', 'interface': 'AT-SPI', 'chooser': value}
    controller = UiObservations(Mock())
    controller.call = Mock(return_value=(json.dumps(result).encode(), []))
    assert controller.observe(operation)['chooser'] == value
    assert controller.call.call_count == 1


def test_chooser_controller_rejects_partial_attachment_evidence():
    from ui_observations import UiObservations
    controller = UiObservations(Mock())
    result = {'operation': 'chooser-preserved', 'outcome': 'passed', 'interface': 'AT-SPI',
              'chooser': {'checked': 'chooser-preserved', 'attachments': ['diagnostic-logs.zip']}}
    controller.call = Mock(return_value=(json.dumps(result).encode(), []))
    with pytest.raises(EvidenceError, match='chooser-response'):
        controller.observe('chooser-preserved')


def test_validation_entry_reaches_worker_and_closes_recorder_on_failure(tmp_path):
    from parent_feedback_validation import PLAN, ValidationJourney, execute

    recorder = MagicMock(assertion=Mock())
    context = SimpleNamespace(directory=tmp_path, credentials=Mock(), lease=Mock(),
                              verified=SimpleNamespace(inputs={}), guestfs=Mock(),
                              commands=Mock(), recorder=recorder)

    def worker(**options):
        journey = options['guarded_observe'].__self__
        assert type(journey) is ValidationJourney
        assert journey.context is context and journey.plan is PLAN
        assert options['validate'].__self__ is journey
        assert options['authenticate'] is True and options['timeout'] == 1800
        assert journey.actions == {} and not journey.steps and not journey.states
        raise EvidenceError('synthetic-worker-stop')

    context.run_worker = Mock(side_effect=worker)
    with pytest.raises(EvidenceError, match='synthetic-worker-stop'):
        execute(recorder, context)
    context.credentials.provision.assert_called_once_with(
        context.lease, context.verified, tmp_path, context.guestfs, context.commands)
    context.run_worker.assert_called_once()
    recorder.step.assert_called_once_with('setup')
    assert recorder.step.return_value.__exit__.call_args.args[0] is EvidenceError
    recorder.assertion.assert_not_called()


@pytest.mark.parametrize('fault', ['', 'feedback-state-whitespace', 'length-ascii-valid',
                                  'rejection-mixed-read', 'rejection-hidden-input-read',
                                  'rejection-complex-read', 'review-reset-open',
                                  'switch-feedback-ready', 'feedback-privacy-returned',
                                  'feedback-draft-reopen'])
def test_complete_validation_worker_matches_plan_and_stops_at_failed_proof(fault):
    from parent_feedback_validation import PLAN
    from tests.support.perl import run_perl
    result = json.loads(run_perl(r'''
use strict; use warnings; use JSON::PP;
our (@events, @stages); our $fault = shift @ARGV;
BEGIN { $INC{'testapi.pm'} = 1; }
package testapi;
sub record_info { }
sub send_key { push @events, $_[0]; }
sub type_string { push @events, 'type:' . $_[0]; }
package main;
require onpc_feedback_privacy;
no warnings 'redefine';
*onpc_gdm::reattach_functional = sub { };
*onpc_parent::open_for_child = sub { return $_[0]->seen('parent-selected'); };
*onpc_journey::finish = sub { push @events, 'finish'; };
my $ok = eval {
    onpc_feedback_privacy::run(sub {
        push @events, $_[0]; push @stages, $_[0];
        die 'failed proof' if $_[0] eq $fault;
        return {observed => $_[0]};
    }, 'validation'); 1;
};
print encode_json({ok => $ok ? 1 : 0, events => \@events, stages => \@stages});
''', fault).stdout)
    stages = list(PLAN.screen_tags)
    stages = stages[stages.index('parent-selected'):]
    assert len(stages) == len(set(stages))
    assert result['stages'] == (stages[:stages.index(fault) + 1] if fault else stages)
    assert bool(result['ok']) is (not fault)
    assert result['events'][-1] == (fault or 'finish')
    if not fault:
        assert result['events'].count('ctrl-shift-v') == 20
        assert result['events'].count('alt-tab') == 3
        assert result['events'].count('ctrl-shift-u') == 3
        assert result['events'].count('alt-f4') == 2
        operations = [PLAN.screen_tags[stage] for stage in stages]
        assert {operation for operation in operations if operation.endswith('-send')} == {
            'ui:rejection-ascii-send', 'ui:rejection-mixed-send', 'ui:rejection-empty-send',
            'ui:rejection-malformed-send', 'ui:rejection-hidden-send',
            'ui:rejection-complex-send', 'ui:rejection-reopened-send'}
        assert operations.index('ui:feedback-state-whitespace') < operations.index('ui:rejection-empty-send')
        assert operations.index('ui:rejection-complex-read') < operations.index('ui:feedback-privacy-open')


@pytest.mark.parametrize('stage,projection,validation', [
    ('feedback-state-whitespace', 'states-whitespace', 'none'),
    ('feedback-state-no-reply', 'states-no-reply', 'none'),
    ('feedback-state-malformed', 'states-malformed', 'none'),
    ('length-ascii-valid', 'length-ascii-5000', 'none'),
    ('length-mixed-valid', 'length-mixed-5000', 'none'),
    ('rejection-ascii-read', 'length-ascii-5001', 'length-invalid'),
    ('rejection-mixed-read', 'length-mixed-5001', 'length-invalid'),
    ('rejection-empty-read', 'initial-empty', 'body-required'),
    ('rejection-malformed-read', 'states-malformed', 'reply-invalid'),
    ('rejection-hidden-read', 'rejection-hidden', 'hidden-invalid'),
    ('rejection-complex-read', 'rejection-complex', 'format-invalid'),
    ('review-valid', 'synthetic-first', 'none'),
])
@pytest.mark.parametrize('fault', ['', 'projection', 'explanation', 'disabled'])
def test_validation_matrix_requires_each_public_result(tmp_path, stage, projection, validation, fault):
    from parent_feedback_validation import ValidationJourney
    journey = ValidationJourney(SimpleNamespace(directory=tmp_path), Mock())
    value = dict(draft=projection, validation=validation, send_enabled=True,
                 attachments=['diagnostic-logs.zip'], collection='ready', controls='ready')
    if fault == 'projection':
        value['draft'] = 'synthetic-first' if projection != 'synthetic-first' else 'initial-empty'
    elif fault == 'explanation':
        value['validation'] = 'none' if validation != 'none' else 'body-required'
    elif fault == 'disabled':
        value['send_enabled'] = False
    if fault:
        with pytest.raises(EvidenceError, match='matrix-result'):
            journey.check_settings(stage, {'ui': {'feedback_state': value}})
    else:
        journey.check_settings(stage, {'ui': {'feedback_state': value}})
        with pytest.raises(EvidenceError, match='matrix-replay'):
            journey.check_settings(stage, {'ui': {'feedback_state': value}})


def test_validation_preservation_requires_earlier_evidence(tmp_path):
    from parent_feedback_validation import ValidationJourney
    journey = ValidationJourney(SimpleNamespace(directory=tmp_path), Mock())
    for stage in ('ready', 'setup-detached'):
        journey.check_settings(stage, {})
    assert not journey.states and not journey.windows and journey.draft is None
    value = dict(draft='rejection-complex', validation='none', send_enabled=True,
                 attachments=['diagnostic-logs.zip'], collection='ready', controls='ready')
    with pytest.raises(EvidenceError, match='matrix-preservation'):
        journey.check_settings('rejection-reopen', {'ui': {'feedback_state': value}})
    rejected = dict(value, validation='format-invalid')
    journey.check_settings('rejection-complex-read', {'ui': {'feedback_state': rejected}})
    journey.check_settings('rejection-reopen', {'ui': {'feedback_state': value}})
    journey.check_settings('rejection-reopened-read', {'ui': {'feedback_state': rejected}})
    draft = dict(draft='synthetic-first', validation='none', attachments=['diagnostic-logs.zip'],
                 collection='ready', controls='ready')
    with pytest.raises(EvidenceError, match='preserved-draft'):
        journey.check_settings('feedback-draft-reopen', {'ui': {'feedback': draft}})
    journey.check_settings('feedback-draft', {'ui': {'feedback': draft}})
    for stage in ('feedback-privacy-returned', 'feedback-draft-reread', 'feedback-draft-reopen'):
        journey.check_settings(stage, {'ui': {'feedback': draft}})


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


@pytest.mark.parametrize('case', accessible_ui.REJECTION_CASES)
@pytest.mark.parametrize('fault', ['', 'body', 'reply', 'duplicate', 'owner', 'stale',
                                  'disabled', 'uncertain', 'wrong-entry'])
def test_invalid_only_send_requires_exact_fresh_owned_invalid_fixture(case, fault):
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


@pytest.mark.parametrize('attribute', ['weight', 'style', 'underline', 'strikethrough'])
@pytest.mark.parametrize('offset', [0, 1200, 2398])
def test_rejection_reports_missing_format_without_exposing_text(attribute, offset):
    ui, _, _, _ = rejection_ui('complex')
    read = ui.api.Text.get_attribute_run.side_effect
    def missing(text, position, defaults):
        attributes, first, last = read(text, position, defaults)
        if position == offset:
            attributes.pop(attribute)
        return attributes, first, last
    ui.api.Text.get_attribute_run.side_effect = missing
    with pytest.raises(accessible_ui.UiError) as error:
        ui.reject_invalid_feedback('complex')
    assert str(error.value) == f'ui:rejection-format-proof:{attribute}:{offset}'
    ui.activate_id.assert_not_called()


@pytest.mark.parametrize('boundary', [1, 2, 1200, 2398, 2399])
def test_rejection_covers_public_runs_without_skipping_unproven_characters(boundary):
    ui, _, _, _ = rejection_ui('complex')
    read = ui.api.Text.get_attribute_run.side_effect
    def ranges(text, offset, defaults):
        attributes, _, _ = read(text, offset, defaults)
        if offset < boundary:
            return attributes, 0, boundary
        attributes['strikethrough'] = 'false'
        return attributes, boundary, len(accessible_ui.COMPLEX_BODY)
    ui.api.Text.get_attribute_run.side_effect = ranges
    if boundary == len(accessible_ui.COMPLEX_BODY):
        ui.reject_invalid_feedback('complex')
        ui.api.Text.get_attribute_run.assert_called_once()
        ui.activate_id.assert_called_once_with('feedback-send')
    else:
        with pytest.raises(accessible_ui.UiError, match='format-proof:strikethrough'):
            ui.reject_invalid_feedback('complex')
        assert ui.api.Text.get_attribute_run.call_args.args[1] == boundary + boundary % 2
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


def test_rejection_waits_for_the_independent_public_result_without_replaying_send():
    ui, _, _, _ = rejection_ui('empty')
    initial = ui.feedback_snapshot('initial-empty', states=True)
    rejected = {**initial, 'validation': 'body-required'}
    ui.feedback_snapshot = Mock(side_effect=[initial, rejected])
    ui.timeout = 1
    assert ui.rejection_operation('rejection-empty-read') == rejected
    assert ui.feedback_snapshot.call_count == 2
    ui.activate_id.assert_not_called()


@pytest.mark.parametrize('case', accessible_ui.REJECTION_CASES)
def test_rejection_requires_independent_explanation_and_decodes_closed_result(case):
    from ui_observations import UiObservations
    ui, _, dialog, _ = rejection_ui(case)
    with pytest.raises(accessible_ui.UiError, match='explanation'):
        ui.rejection_operation(f'rejection-{case}-read')
    projection, explanation = accessible_ui.REJECTION_CASES[case]
    label = next(text for text, name in accessible_ui.FEEDBACK_VALIDATION.items() if name == explanation)
    dialog.children.append(Node(label, identity='feedback-status'))
    state = ui.rejection_operation(f'rejection-{case}-read')
    reader = UiObservations(Mock())
    response = {'operation': f'rejection-{case}-read', 'outcome': 'passed', 'interface': 'AT-SPI',
                'feedback_state': state}
    reader.call = Mock(return_value=(json.dumps(response).encode(), []))
    assert reader.observe(response['operation']) == response
    state['validation'] = 'none'
    reader.call.return_value = (json.dumps(response).encode(), [])
    with pytest.raises(EvidenceError, match='rejection-response'):
        reader.observe(response['operation'])
    ui.activate_id.assert_not_called()


@pytest.mark.parametrize('fault', ['', 'rejection-empty-read', 'rejection-hidden-input-read',
                                  'text-duplicate-body-complex-150-select',
                                  'text-duplicate-body-complex-selected',
                                  'text-duplicate-body-complex-read',
                                  'rejection-format-strike-apply', 'rejection-complex-read'])
def test_rejection_worker_stops_without_replay_or_followup_input(fault):
    from feedback_rejection import PLAN, STAGES
    from tests.support.perl import run_perl
    result = json.loads(run_perl(r'''
use strict; use warnings; use JSON::PP;
our (@events, @stages); our $fault = shift @ARGV;
BEGIN { $INC{'testapi.pm'} = 1; }
package testapi;
sub record_info { }
sub send_key { push @events, $_[0]; }
sub type_string { push @events, 'type:' . $_[0]; }
package main;
require onpc_feedback_states;
no warnings 'redefine';
*onpc_gdm::reattach_functional = sub { };
*onpc_parent::open_for_child = sub { return $_[0]->seen('parent-selected'); };
*onpc_journey::finish = sub { push @events, 'finish'; };
my $ok = eval {
    onpc_feedback_states::run_rejection(sub {
        push @events, $_[0]; push @stages, $_[0];
        die 'failed proof' if $_[0] eq $fault;
        return {observed => $_[0]};
    }); 1;
};
print encode_json({ok => $ok ? 1 : 0, events => \@events, stages => \@stages});
''', fault).stdout)
    assert len(result['stages']) == len(set(result['stages']))
    assert set(result['stages']) <= set(PLAN.screen_tags)
    stages = ['parent-selected', *STAGES]
    assert result['stages'] == (stages[:stages.index(fault) + 1] if fault else stages)
    assert bool(result['ok']) is (not fault)
    assert result['events'][-1] == (fault or 'finish')
    if not fault:
        caret = result['events'].index('rejection-hidden-caret')
        assert result['events'][caret + 1:caret + 5] == [
            'ctrl-shift-u', 'type:0001', 'ret', 'rejection-hidden-input-read']
        assert result['events'].count('ctrl-shift-v') == 4
        assert result['events'].count('ctrl-c') == 4
        assert 'type:' + accessible_ui.COMPLEX_BODY not in result['events']
        for binding in (value for value in accessible_ui.TEXT_DUPLICATIONS
                        if value.startswith('body-complex')):
            selected = result['events'].index('text-duplicate-' + binding + '-selected')
            assert result['events'][selected + 1:selected + 6] == [
                'ctrl-c', 'ctrl-end', 'ret', 'ctrl-shift-v', 'text-duplicate-' + binding + '-read']


@pytest.mark.parametrize('fault', ['', 'unfocused', 'wrong-source', 'selection', 'refused', 'uncertain'])
@pytest.mark.parametrize('binding', ['body-complex-150', 'body-ascii-5000-double-1'])
def test_duplicate_source_and_exact_selection_guard_copy(fault, binding):
    ui, _, _, controls = feedback_ui()
    node = controls['feedback-editor-input']
    value = accessible_ui.TEXT_VALUES[accessible_ui.TEXT_DUPLICATIONS[binding]][1]
    prefix = 'text-duplicate-' + binding
    node.text.count = len(value) + 1
    node.states.add('focused')
    ui.api.Text.get_text = Mock(return_value=value + '\n')
    ui.api.Text.get_n_selections = Mock(return_value=1)
    ui.api.Text.set_selection = Mock(return_value=True)
    ui.api.Text.get_selection = Mock(return_value=SimpleNamespace(start_offset=0, end_offset=len(value)))
    if fault == 'unfocused':
        node.states.remove('focused')
    elif fault == 'wrong-source':
        ui.api.Text.get_text.return_value = 'y' * len(value) + '\n'
    elif fault == 'selection':
        ui.api.Text.get_n_selections.return_value = 0
    elif fault == 'refused':
        ui.api.Text.set_selection.return_value = False
    elif fault == 'uncertain':
        ui.input_uncertain = True
    if fault:
        with pytest.raises(accessible_ui.UiError):
            ui.duplicate_text_operation(prefix + '-select')
        assert ui.api.Text.set_selection.call_count == (1 if fault == 'refused' else 0)
    else:
        ui.duplicate_text_operation(prefix + '-select')
        ui.api.Text.set_selection.assert_called_once_with(node.text, 0, 0, len(value))
        ui.duplicate_text_operation(prefix + '-selected')
        ui.api.Text.get_selection.return_value.end_offset += 1
        with pytest.raises(accessible_ui.UiError, match='duplicate-selection'):
            ui.duplicate_text_operation(prefix + '-selected')


def test_rejection_selector_preserves_guarded_envelope(monkeypatch):
    import check_e2e_feedback_rejection
    run = Mock(return_value=0)
    monkeypatch.setattr(check_e2e_feedback_rejection, 'smoke', run)
    assert check_e2e_feedback_rejection.main() == 0
    assert run.call_args.kwargs['feedback_rejection'] is True
    with pytest.raises(CommandError, match='feedback-read-prerequisites'):
        smoke.main(feedback_rejection=True)
    with pytest.raises(CommandError, match='feedback-rejection-prerequisites'):
        smoke.main(feedback_rejection=True, feedback_states=True)


@pytest.mark.parametrize('family', ['ascii', 'mixed'])
def test_length_valid_boundary_cannot_reach_send_even_with_invalid_case_name(family):
    ui, _, _, controls = rejection_ui(family)
    value = accessible_ui.TEXT_VALUES[f'body-{family}-5000'][1]
    body = controls['feedback-editor-input'].text
    body.value, body.count = value, len(value)
    assert len(value.encode('utf-16-le')) // 2 == 5000
    ui.length_operation(f'length-{family}-refusal')
    ui.activate_id.assert_not_called()


@pytest.mark.parametrize('family', ['ascii', 'mixed'])
def test_length_wrong_entry_operation_refuses_without_input(family):
    ui, parent, _, _ = rejection_ui(family)
    parent.children.clear()
    assert ui.length_operation(f'length-{family}-wrong-entry') is None
    ui.activate_id.assert_not_called()


@pytest.mark.parametrize('family,fault', [
    (family, fault) for family in ('ascii', 'mixed')
    for fault in ('same-length', 'newline', 'formatted',
                  *(('utf16-offset',) if family == 'mixed' else ()))])
def test_length_invalid_guard_proves_all_scalars_and_normal_attributes(family, fault):
    ui, _, _, controls = rejection_ui(family)
    body = controls['feedback-editor-input'].text
    if fault == 'same-length':
        body.value = 'y' + body.value[1:]
    elif fault == 'newline':
        body.value += '\n\n'
        body.count += 2
    elif fault == 'utf16-offset':
        # Public offsets count Unicode scalars, never surrogate code units.
        body.count = len(body.value.encode('utf-16-le')) // 2 + 1
        body.value += '\nx'
    else:
        ui.api.Text.get_attribute_run.side_effect = lambda text, offset, defaults: (
            {'weight': '700', 'style': 'normal', 'underline': 'none', 'strikethrough': 'false'},
            0, body.count)
    with pytest.raises(accessible_ui.UiError):
        ui.reject_invalid_feedback(family)
    ui.activate_id.assert_not_called()


@pytest.mark.parametrize('family', ['ascii', 'mixed'])
def test_length_reopen_decoder_and_journey_require_independent_prior_result(tmp_path, family):
    from feedback_length import FeedbackLengthJourney
    from ui_observations import UiObservations
    ui, _, _, _ = rejection_ui(family)
    state = ui.feedback_snapshot(f'length-{family}-5001', states=True)
    response = {'operation': f'length-{family}-reopen', 'outcome': 'passed',
                'interface': 'AT-SPI', 'feedback_state': state}
    reader = UiObservations(Mock())
    reader.call = Mock(return_value=(json.dumps(response).encode(), []))
    assert reader.observe(response['operation']) == response
    frozen = FeedbackStateObservation.from_value(state)
    with pytest.raises(FrozenInstanceError):
        frozen.draft = 'other'
    journey = FeedbackLengthJourney(SimpleNamespace(directory=tmp_path), Mock())
    with pytest.raises(EvidenceError, match='independent-entry'):
        journey.check_settings(response['operation'], {'ui': response})
    rejected = {**response, 'feedback_state': {**state, 'validation': 'length-invalid'}}
    journey.check_settings(f'rejection-{family}-read', {'ui': rejected})
    journey.check_settings(response['operation'], {'ui': response})
    journey.check_settings(f'rejection-{family}-reopened-read', {'ui': rejected})
    state['send_enabled'] = False
    reader.call.return_value = (json.dumps(response).encode(), [])
    with pytest.raises(EvidenceError, match='length-response'):
        reader.observe(response['operation'])


@pytest.mark.parametrize('fault', ['', 'source', 'focus', 'caret', 'uncertain'])
@pytest.mark.parametrize('kind', ['scalar', 'suffix'])
def test_scalar_append_requires_exact_source_and_public_character_caret(fault, kind):
    ui, _, _, controls = rejection_ui('mixed')
    node = controls['feedback-editor-input']
    binding = 'body-mixed-5001' if kind == 'scalar' else 'body-mixed-5001-base'
    sources = accessible_ui.TEXT_SCALARS if kind == 'scalar' else accessible_ui.TEXT_SUFFIXES
    value = accessible_ui.TEXT_VALUES[sources[binding][0]][1]
    operation = getattr(ui, kind + '_text_operation')
    node.text.value, node.text.count = value, len(value)
    node.states.add('focused')
    ui.api.Text.get_caret_offset = Mock(return_value=len(value))
    if fault == 'source':
        node.text.value = 'y' * len(value)
    elif fault == 'focus':
        node.states.remove('focused')
    elif fault == 'caret':
        ui.api.Text.get_caret_offset.return_value -= 1
    elif fault == 'uncertain':
        ui.input_uncertain = True
    if fault:
        with pytest.raises(accessible_ui.UiError):
            operation(f'text-{kind}-{binding}-caret')
    else:
        operation(f'text-{kind}-{binding}-caret')
    ui.activate_id.assert_not_called()


@pytest.mark.parametrize('fault', ['', 'text-body-ascii-5000-seed-read',
    *(f'text-duplicate-body-ascii-5000-double-{step}-{action}'
      for step in range(1, 5) for action in ('select', 'selected', 'read')),
    'text-suffix-body-ascii-5000-caret', 'text-suffix-body-ascii-5000-read', 'length-ascii-refusal',
    'rejection-ascii-read', 'length-ascii-reopen', 'text-scalar-body-mixed-5000-caret',
    'text-scalar-body-mixed-5001-read', 'rejection-mixed-reopened-read'])
def test_length_worker_matches_controller_and_stops_at_failed_proof(fault):
    from feedback_length import STAGES, PLAN
    from tests.support.perl import run_perl
    result = json.loads(run_perl(r'''
use strict; use warnings; use JSON::PP;
our (@events, @stages); our $fault = shift @ARGV;
BEGIN { $INC{'testapi.pm'} = 1; }
package testapi;
sub record_info { }
sub send_key { push @events, $_[0]; }
sub type_string { push @events, 'type:' . $_[0]; }
package main;
require onpc_feedback_states;
no warnings 'redefine';
*onpc_gdm::reattach_functional = sub { };
*onpc_parent::open_for_child = sub { return $_[0]->seen('parent-selected'); };
*onpc_journey::finish = sub { push @events, 'finish'; };
my $ok = eval {
    onpc_feedback_states::run_length(sub {
        push @events, $_[0]; push @stages, $_[0];
        die 'failed proof' if $_[0] eq $fault;
        return {observed => $_[0]};
    }); 1;
};
print encode_json({ok => $ok ? 1 : 0, events => \@events, stages => \@stages});
''', fault).stdout)
    stages = ['parent-selected', *STAGES]
    assert len(stages) == len(set(stages))
    assert set(stages) <= set(PLAN.screen_tags)
    assert result['stages'] == (stages[:stages.index(fault) + 1] if fault else stages)
    assert bool(result['ok']) is (not fault)
    assert result['events'][-1] == (fault or 'finish')
    if not fault:
        assert result['events'].count('ctrl-c') == 16
        assert result['events'].count('ctrl-shift-v') == 16
        typed = [event.removeprefix('type:') for event in result['events'] if event.startswith('type:')]
        assert sum(value.count('x') for value in typed) == 1278
        assert max(map(len, typed)) == 312
        for binding, (seed, *copies) in accessible_ui.TEXT_REPETITIONS.items():
            assert 'type:' + accessible_ui.TEXT_VALUES[seed][1] in result['events']
            assert 'type:' + accessible_ui.TEXT_VALUES[binding][1] not in result['events']
            for target in copies:
                prefix = 'text-duplicate-' + target
                selected = result['events'].index(prefix + '-selected')
                assert result['events'][selected + 1:selected + 5] == [
                    'ctrl-c', 'ctrl-end', 'ctrl-shift-v', prefix + '-read']
            caret = result['events'].index(f'text-suffix-{binding}-caret')
            assert result['events'][caret + 1:caret + 3] == [
                'type:' + accessible_ui.TEXT_SUFFIXES[binding][1], f'text-suffix-{binding}-read']
        for units in (5000, 5001):
            caret = result['events'].index(f'text-scalar-body-mixed-{units}-caret')
            assert result['events'][caret + 1:caret + 5] == [
                'ctrl-shift-u', 'type:1f600', 'ret', f'text-scalar-body-mixed-{units}-read']


def test_length_selector_preserves_guarded_envelope(monkeypatch):
    import check_e2e_feedback_length
    run = Mock(return_value=0)
    monkeypatch.setattr(check_e2e_feedback_length, 'smoke', run)
    assert check_e2e_feedback_length.main() == 0
    assert run.call_args.kwargs['feedback_length'] is True
    with pytest.raises(CommandError, match='feedback-read-prerequisites'):
        smoke.main(feedback_length=True)
    with pytest.raises(CommandError, match='feedback-length-prerequisites'):
        smoke.main(feedback_length=True, feedback_rejection=True)


@pytest.mark.parametrize('fault', ['', 'absent', 'wrong-owner', 'duplicate', 'hidden',
                                  'disabled', 'already-active', 'focus-lost', 'uncertain'])
def test_existing_window_preparation_refuses_unsafe_or_uncertain_targets(fault):
    ui, parent, dialog, _ = synthetic_feedback_ui()
    dialog.states.discard('active')
    parent.states.add('active')
    dialog.bus, dialog.path = ':1.123', '/org/a11y/atspi/accessible/42'
    if fault == 'absent':
        parent.children.clear()
    elif fault == 'wrong-owner':
        ui.api.get_desktop(0).identity = 'unrelated.application'
    elif fault == 'duplicate':
        parent.children.append(Node(identity='feedback-dialog'))
    elif fault in ('hidden', 'disabled'):
        dialog.states.discard('showing' if fault == 'hidden' else 'sensitive')
    elif fault == 'already-active':
        dialog.states.add('active')
    elif fault == 'focus-lost':
        parent.states.discard('active')
    elif fault == 'uncertain':
        ui.input_uncertain = True
    if fault:
        with pytest.raises(accessible_ui.UiError):
            ui.window_switch_ready('feedback', 'parent')
    else:
        assert ui.window_switch_ready('feedback', 'parent')['active'] is False
        with pytest.raises(accessible_ui.UiError, match='switch-active'):
            ui.window_switch_proof('feedback')
    dialog.component.grab_focus.assert_not_called()


def test_window_switch_public_proof_decoder_and_retained_identity(tmp_path):
    import copy
    from window_switch import WindowSwitchJourney
    from ui_observations import UiObservations
    ui, _, dialog, controls = synthetic_feedback_ui()
    dialog.bus, dialog.path = ':1.123', '/org/a11y/atspi/accessible/42'
    value = ui.window_switch_proof('feedback')
    reader = UiObservations(Mock())
    reply = {'operation': 'switch-feedback', 'outcome': 'passed', 'interface': 'AT-SPI',
             'window': value}
    reader.call = Mock(return_value=(json.dumps(reply).encode(), []))
    assert reader.observe('switch-feedback') == reply
    journey = WindowSwitchJourney(SimpleNamespace(directory=tmp_path), Mock())
    with pytest.raises(EvidenceError, match='window-or-draft-changed'):
        journey.check_settings('switch-feedback', {'ui': reply})
    journey.check_settings('switch-draft-before', {'ui': copy.deepcopy(reply)})
    ready = copy.deepcopy(reply)
    ready['operation'] = 'switch-feedback-ready'
    ready['window'].pop('feedback')
    ready['window']['active'] = False
    reader.call.return_value = (json.dumps(ready).encode(), [])
    assert reader.observe('switch-feedback-ready') == ready
    journey.check_settings('switch-feedback-ready', {'ui': ready})
    journey.check_settings('switch-feedback', {'ui': reply})
    value['endpoint'][1] += '1'
    with pytest.raises(EvidenceError, match='window-or-draft-changed'):
        journey.check_settings('switch-feedback-again', {'ui': reply})
    value['active'] = False
    reader.call.return_value = (json.dumps(reply).encode(), [])
    with pytest.raises(EvidenceError, match='switch-response'):
        reader.observe('switch-feedback')
    controls['feedback-editor-input'].text.value = 'X' * controls['feedback-editor-input'].text.count
    with pytest.raises(accessible_ui.UiError, match='nonempty-draft'):
        ui.window_switch_proof('feedback')


def test_window_switch_absent_target_never_launches(monkeypatch):
    ui, _, dialog, _ = synthetic_feedback_ui()
    dialog.bus, dialog.path = ':1.123', '/org/a11y/atspi/accessible/42'
    ui.license_viewer_snapshot = Mock(return_value=(None, None, None))
    launch = Mock(side_effect=AssertionError('must not launch'))
    monkeypatch.setattr(accessible_ui.subprocess, 'run', launch)
    assert ui.window_switch_operation('switch-viewer-absent')['binding'] == 'feedback'
    launch.assert_not_called()


@pytest.mark.parametrize('fault', ['', 'wrong-owner', 'ambiguous', 'unrelated', 'hidden', 'wrong-pid'])
def test_window_switch_viewer_reacquires_inactive_public_document(fault):
    content = Node(identity='view', role='text')
    text = 'GNU GENERAL PUBLIC LICENSE\nVersion 3, 29 June 2007'
    content.get_text_iface = lambda: content
    window = Node(children=[content])
    owner = Node(identity='org.gnome.TextEditor', role='application', children=[window])
    ui = ui_for(Node(role='desktop frame', children=[owner]))
    ui.api.Text = SimpleNamespace(get_character_count=lambda _: len(text),
                                  get_text=lambda _, start, end: text[start:end])
    if fault == 'wrong-owner':
        owner.identity = 'unrelated'
    elif fault == 'ambiguous':
        owner.children.append(Node())
    elif fault == 'unrelated':
        text = 'Unrelated document'
    elif fault == 'hidden':
        content.states.discard('showing')
    elif fault == 'wrong-pid':
        content.get_process_id = lambda: 999
    if fault:
        with pytest.raises(accessible_ui.UiError):
            ui.existing_window('viewer')
        window.component.grab_focus.assert_not_called()
    else:
        with pytest.raises(accessible_ui.UiError, match='document-owner'):
            ui.read_document(content, 'gpl-heading', maximum=1024)
        assert ui.existing_window('viewer') is window
        assert ui.existing_window_active('viewer') is None
        window.states.add('active')
        assert ui.existing_window_active('viewer') is window
        window.component.grab_focus.assert_not_called()


@pytest.mark.parametrize('fault', ['', 'switch-viewer-launch', 'switch-parent',
                                  'switch-viewer-ready', 'switch-feedback-ready',
                                  'switch-viewer', 'switch-feedback', 'switch-viewer-absent'])
def test_window_switch_worker_preserves_order_and_stops_before_later_input(fault):
    from window_switch import STAGES
    from tests.support.perl import run_perl
    result = json.loads(run_perl(r'''
use strict; use warnings; use JSON::PP;
our (@events, @stages); our $fault = shift @ARGV;
BEGIN { $INC{'testapi.pm'} = 1; }
package testapi;
sub record_info { }
sub send_key { push @events, $_[0]; }
sub type_string { push @events, 'type'; }
package main;
require onpc_feedback_read;
no warnings 'redefine';
*onpc_gdm::reattach_functional = sub { };
*onpc_parent::open_for_child = sub { return $_[0]->seen('parent-selected'); };
*onpc_journey::finish = sub { push @events, 'finish'; };
my $ok = eval {
    onpc_feedback_read::run_window_switch(sub {
        push @events, $_[0]; push @stages, $_[0];
        die 'failed proof' if $_[0] eq $fault;
        return {observed => $_[0]};
    }); 1;
};
print encode_json({ok => $ok ? 1 : 0, events => \@events, stages => \@stages});
''', fault).stdout)
    stages = ['parent-selected', *STAGES]
    assert result['stages'] == (stages[:stages.index(fault) + 1] if fault else stages)
    assert bool(result['ok']) is (not fault)
    assert result['events'][-1] == (fault or 'finish')
    if not fault:
        assert result['events'].count('alt-tab') == 6
    elif fault.endswith('-ready'):
        assert result['events'][-1] != 'alt-tab'


def test_window_switch_selector_uses_guarded_envelope(monkeypatch):
    import check_e2e_window_switch
    run = Mock(return_value=0)
    monkeypatch.setattr(check_e2e_window_switch, 'smoke', run)
    assert check_e2e_window_switch.main() == 0
    assert run.call_args.kwargs['window_switch'] is True
    with pytest.raises(CommandError, match='feedback-read-prerequisites'):
        smoke.main(window_switch=True)
    with pytest.raises(CommandError, match='window-switch-prerequisites'):
        smoke.main(window_switch=True, format_qualification=True)


@pytest.mark.parametrize('fault', ['', 'missing', 'stalled', 'mixed', 'private', 'range'])
def test_format_range_public_runs_refuse_unavailable_or_invalid_attributes(fault):
    ui, _, _, controls = synthetic_feedback_ui()
    ui.api.Text.get_attribute_run = Mock(side_effect=lambda text, offset, defaults: (
        {'weight': '700' if offset < 9 else '400'}, 0 if offset < 9 else 9,
        9 if offset < 9 else 23))
    if fault == 'missing':
        ui.api.Text.get_attribute_run.return_value = ({}, 0, 23)
        ui.api.Text.get_attribute_run.side_effect = None
    elif fault == 'stalled':
        ui.api.Text.get_attribute_run.side_effect = lambda *args: ({'weight': '700'}, 0, 0)
    elif fault == 'private':
        controls['feedback-editor-input'].text.value = 'private'
    if fault:
        with pytest.raises(accessible_ui.UiError):
            ui.formatting_attributes(-1 if fault == 'range' else 0, 23 if fault == 'mixed' else 9)
    else:
        assert ui.formatting_attributes(0, 9) == {'start': 0, 'end': 9, 'weight': 'bold'}
        assert ui.formatting_attributes(9, 23) == {'start': 9, 'end': 23, 'weight': 'normal'}
        # No ambiguous boundary lookup; full public bounds still prove coverage.
        assert [call.args[1] for call in ui.api.Text.get_attribute_run.call_args_list] == [4, 16]


def test_format_decoder_and_independent_recorder(tmp_path):
    from format_qualification import FormatJourney
    from ui_observations import UiObservations
    value = [{'start': 0, 'end': 9, 'weight': 'bold'},
             {'start': 9, 'end': 23, 'weight': 'normal'}]
    reader = UiObservations(Mock())
    reply = {'operation': 'format-read', 'outcome': 'passed', 'interface': 'AT-SPI',
             'formatting': value}
    reader.call = Mock(return_value=(json.dumps(reply).encode(), []))
    assert reader.observe('format-read') == reply
    journey = FormatJourney(SimpleNamespace(directory=tmp_path), Mock())
    with pytest.raises(EvidenceError, match='format:independent-entry'):
        journey.check_settings('format-reopen', {'ui': reply})
    journey.check_settings('format-read', {'ui': reply})
    journey.check_settings('format-reopen', {'ui': reply})
    value[1]['weight'] = 'bold'
    reader.call.return_value = (json.dumps(reply).encode(), [])
    with pytest.raises(EvidenceError, match='ui:format-response'):
        reader.observe('format-read')


@pytest.mark.parametrize('fault', ['', 'format-home', 'format-selected', 'format-read', 'format-reopen'])
def test_format_worker_stops_on_refusal(fault):
    from format_qualification import STAGES
    from tests.support.perl import run_perl
    result = json.loads(run_perl(r'''
use strict; use warnings; use JSON::PP;
our (@events, @stages); our $fault = shift @ARGV;
BEGIN { $INC{'testapi.pm'} = 1; }
package testapi;
sub record_info { }
sub send_key { push @events, $_[0]; }
sub type_string { push @events, 'type'; }
package main;
require onpc_format;
no warnings 'redefine';
*onpc_gdm::reattach_functional = sub { };
*onpc_parent::open_for_child = sub { return $_[0]->seen('parent-selected'); };
*onpc_journey::finish = sub { push @events, 'finish'; };
my $ok = eval {
    onpc_format::run(sub {
        push @events, $_[0]; push @stages, $_[0];
        die 'failed proof' if $_[0] eq $fault;
        return {observed => $_[0]};
    }); 1;
};
print encode_json({ok => $ok ? 1 : 0, events => \@events, stages => \@stages});
''', fault).stdout)
    stages = ['parent-selected', *STAGES]
    assert result['stages'] == (stages[:stages.index(fault) + 1] if fault else stages)
    assert bool(result['ok']) is (not fault)
    assert result['events'][-1] == (fault or 'finish')


def test_format_selector_preserves_guarded_envelope(monkeypatch):
    import check_e2e_format
    run = Mock(return_value=0)
    monkeypatch.setattr(check_e2e_format, 'smoke', run)
    assert check_e2e_format.main() == 0
    assert run.call_args.kwargs['format_qualification'] is True
    with pytest.raises(CommandError, match='feedback-read-prerequisites'):
        smoke.main(format_qualification=True)
    with pytest.raises(CommandError, match='format-prerequisites'):
        smoke.main(format_qualification=True, feedback_states=True)


@pytest.mark.parametrize('projection', sorted(set(accessible_ui.FEEDBACK_STATE_PROJECTIONS.values())))
@pytest.mark.parametrize('enabled', [True, False])
@pytest.mark.parametrize('explanation', list(accessible_ui.FEEDBACK_VALIDATION))
def test_state_reads_public_send_and_validation_independently(projection, enabled, explanation):
    ui, _, dialog, controls = feedback_ui()
    for binding in accessible_ui.FEEDBACK_PROJECTIONS[projection]:
        identity, text = accessible_ui.TEXT_VALUES[binding]
        controls[identity].text.count = len(text)
        controls[identity].text.value = text
    ui.api.Text.get_text = Mock(side_effect=lambda text, start, end: text.value[start:end])
    if not enabled:
        controls['feedback-send'].states.remove('sensitive')
    if explanation:
        dialog.children.append(Node(explanation, identity='feedback-status'))
    state = FeedbackStateObservation.from_value(ui.feedback_snapshot(projection, states=True))
    assert state.send_enabled is enabled
    assert state.validation == accessible_ui.FEEDBACK_VALIDATION[explanation]
    for node in controls.values():
        node.action.do_action.assert_not_called()


@pytest.mark.parametrize('fault', ['private-status', 'private-body', 'missing-send',
                                  'duplicate-send', 'wrong-owner', 'inactive', 'wrong-entry'])
def test_state_refuses_unsafe_reads_without_input(fault):
    ui, parent, dialog, controls = synthetic_feedback_ui()
    if fault == 'private-status':
        dialog.children.append(Node('unregistered private text', identity='feedback-status'))
    elif fault == 'private-body':
        controls['feedback-editor-input'].text.count = 10000
    elif fault == 'missing-send':
        dialog.children.remove(controls['feedback-send'])
    elif fault == 'duplicate-send':
        dialog.children.append(Node(identity='feedback-send', states=()))
    elif fault == 'wrong-owner':
        ui.api.get_desktop(0).identity = 'unrelated.application'
    elif fault == 'inactive':
        dialog.states.remove('active')
    elif fault == 'wrong-entry':
        parent.children.clear()
        assert ui.feedback_state_operation('feedback-state-wrong-entry') is None
    with pytest.raises(accessible_ui.UiError):
        ui.feedback_snapshot('synthetic-first', states=True)
    for node in controls.values():
        node.action.do_action.assert_not_called()


@pytest.mark.parametrize('fault', ['', 'send', 'validation', 'projection', 'missing-prior'])
def test_state_controller_and_actual_decoder_reject_unexpected_results(tmp_path, fault):
    from ui_observations import UiObservations
    ui, _, _, controls = synthetic_feedback_ui()
    value = ui.feedback_snapshot('synthetic-first', states=True)
    reader = UiObservations(Mock())
    reply = {'operation': 'feedback-state-valid', 'outcome': 'passed', 'interface': 'AT-SPI',
             'feedback_state': value}
    reader.call = Mock(return_value=(json.dumps(reply).encode(), []))
    assert reader.observe('feedback-state-valid') == reply
    journey = FeedbackStatesJourney(SimpleNamespace(directory=tmp_path), Mock())
    if fault == 'send':
        value['send_enabled'] = False
    elif fault == 'validation':
        value['validation'] = 'reply-invalid'
    elif fault == 'projection':
        value['draft'] = 'initial-empty'
    if fault:
        with pytest.raises(EvidenceError):
            journey.check_settings('feedback-state-reopen' if fault == 'missing-prior'
                                   else 'feedback-state-valid', {'ui': reply})
    else:
        journey.check_settings('feedback-state-valid', {'ui': reply})
        journey.check_settings('feedback-state-reopen', {'ui': reply})
    value['send_enabled'] = 'true'
    reader.call.return_value = (json.dumps(reply).encode(), [])
    with pytest.raises(EvidenceError, match='ui:feedback-state-response'):
        reader.observe('feedback-state-valid')


def test_states_selector_preserves_existing_guarded_envelope(monkeypatch):
    run = Mock(return_value=0)
    monkeypatch.setattr(check_e2e_feedback_states, 'smoke', run)
    assert check_e2e_feedback_states.main() == 0
    assert run.call_args.kwargs['feedback_states'] is True
    with pytest.raises(CommandError, match='feedback-read-prerequisites'):
        smoke.main(feedback_states=True)
    with pytest.raises(CommandError, match='feedback-states-prerequisites'):
        smoke.main(feedback_states=True, feedback_privacy=True)


@pytest.mark.parametrize('fault', ['', 'feedback-state-whitespace', 'text-reply-malformed-selected',
                                  'feedback-state-valid', 'feedback-state-wrong-entry',
                                  'feedback-state-reopen'])
def test_states_worker_order_and_failure_stop_later_input(fault):
    from tests.support.perl import run_perl
    result = json.loads(run_perl(r'''
use strict; use warnings; use JSON::PP;
our (@events, @stages, @typed);
our $fault = shift @ARGV;
BEGIN { $INC{'testapi.pm'} = 1; }
package testapi;
sub record_info { }
sub send_key { push @events, $_[0]; }
sub type_string { push @events, 'type'; push @typed, $_[0]; }
package main;
require onpc_feedback_states;
no warnings 'redefine';
*onpc_gdm::reattach_functional = sub { };
*onpc_parent::open_for_child = sub { return $_[0]->seen('parent-selected'); };
*onpc_journey::finish = sub { push @events, 'finish'; };
my $ok = eval {
    onpc_feedback_states::run(sub {
        push @events, $_[0]; push @stages, $_[0];
        die 'failed proof' if $_[0] eq $fault;
        return {observed => $_[0]};
    }); 1;
};
print encode_json({ok => $ok ? 1 : 0, events => \@events, stages => \@stages, typed => \@typed});
''', fault).stdout)
    stages = list(STATES_PLAN.screen_tags)
    stages = stages[stages.index('parent-selected'):]
    assert result['stages'] == (stages[:stages.index(fault) + 1] if fault else stages)
    assert bool(result['ok']) is (not fault)
    if fault:
        assert result['events'][-1] == fault
    else:
        from feedback_states import EDITS
        assert result['typed'] == [accessible_ui.TEXT_VALUES[binding][1] for binding, _ in EDITS]
        assert result['events'][-1] == 'finish'


def synthetic_feedback_ui():
    ui, parent, dialog, controls = feedback_ui()
    for binding in ('body-first', 'reply-first'):
        identity, value = accessible_ui.TEXT_VALUES[binding]
        controls[identity].text.count = len(value)
        controls[identity].text.value = value
    ui.api.Text.get_text = Mock(side_effect=lambda text, start, end: text.value[start:end])
    return ui, parent, dialog, controls


@pytest.mark.parametrize('fault', ['', 'body', 'reply', 'controls', 'attachments'])
def test_nonempty_projection_compares_fields_and_controls_without_input(fault):
    ui, _, dialog, controls = synthetic_feedback_ui()
    if fault in ('body', 'reply'):
        identity = 'feedback-editor-input' if fault == 'body' else 'feedback-reply-email'
        controls[identity].text.value = 'X' * controls[identity].text.count
    elif fault == 'controls':
        controls['feedback-send'].states.remove('sensitive')
    elif fault == 'attachments':
        dialog.children.append(Node(identity='feedback-attachment-0123456789abcdef'))
    if fault:
        with pytest.raises(accessible_ui.UiError):
            ui.feedback_snapshot('synthetic-first')
    else:
        assert FeedbackObservation.from_value(ui.feedback_snapshot('synthetic-first')).draft == 'synthetic-first'
    for node in controls.values():
        node.action.do_action.assert_not_called()


def test_feedback_close_proof_refuses_wrong_window_without_input():
    ui, parent, dialog, controls = synthetic_feedback_ui()
    ui.window_ready_to_close('feedback')
    dialog.states.remove('active')
    with pytest.raises(accessible_ui.UiError, match='ui:feedback-entry'):
        ui.window_ready_to_close('feedback')
    parent.children.clear()
    assert ui.feedback_privacy_operation('feedback-close-refused') is None
    for node in controls.values():
        node.action.do_action.assert_not_called()


@pytest.mark.parametrize('missing', [False, True])
def test_privacy_reads_actual_disclosure_and_never_follows_external_link(missing):
    import ast
    # The shipped disclosure supplies the fixture; remove an essential promise
    # to prove a mere visible dialog cannot satisfy the observation.
    from tests.support.paths import ROOT
    tree = ast.parse((ROOT / 'common/oh_no_parent_control_ui/feedback.py').read_text())
    method = next(node for node in ast.walk(tree)
                  if isinstance(node, ast.FunctionDef) and node.name == '_show_log_privacy')
    suffix = method.body[0].value.right.value
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


def test_privacy_selector_and_controller_preserve_explicit_prior_draft(tmp_path, monkeypatch):
    run = Mock(return_value=0)
    monkeypatch.setattr(check_e2e_feedback_privacy, 'smoke', run)
    assert check_e2e_feedback_privacy.main() == 0
    assert run.call_args.kwargs['feedback_privacy'] is True
    with pytest.raises(CommandError, match='feedback-read-prerequisites'):
        smoke.main(feedback_privacy=True)
    with pytest.raises(CommandError, match='feedback-privacy-prerequisites'):
        smoke.main(feedback_privacy=True, feedback_read=True)
    journey = FeedbackPrivacyJourney(SimpleNamespace(directory=tmp_path), Mock())
    ui, _, _, _ = synthetic_feedback_ui()
    observed = {'ui': {'feedback': ui.feedback_snapshot('synthetic-first')}}
    with pytest.raises(EvidenceError, match='preserved-draft'):
        journey.check_settings('feedback-draft-reopen', observed)
    journey.check_settings('feedback-draft', observed)
    journey.check_settings('feedback-draft-reopen', observed)
    observed['ui']['feedback']['draft'] = 'initial-empty'
    with pytest.raises(EvidenceError, match='expected-draft'):
        journey.check_settings('feedback-draft-reopen', observed)


def test_nonempty_feedback_roundtrips_actual_controller_decoder():
    from ui_observations import UiObservations
    ui, _, _, _ = synthetic_feedback_ui()
    reader = UiObservations(Mock())
    reply = {'operation': 'feedback-draft-reopen', 'outcome': 'passed', 'interface': 'AT-SPI',
             'feedback': ui.feedback_snapshot('synthetic-first')}
    reader.call = Mock(return_value=(json.dumps(reply).encode(), []))
    assert reader.observe('feedback-draft-reopen') == reply
    reply['feedback']['draft'] = 'initial-empty'
    reader.call.return_value = (json.dumps(reply).encode(), [])
    with pytest.raises(EvidenceError, match='ui:feedback-response'):
        reader.observe('feedback-draft-reopen')


@pytest.mark.parametrize('fault', ['', 'feedback-privacy-open', 'feedback-draft-reread',
                                  'feedback-draft-reopen', 'privacy-independent'])
def test_privacy_worker_sequence_and_failed_proofs_stop_later_input(fault):
    from tests.support.perl import run_perl
    result = json.loads(run_perl(r'''
use strict; use warnings; use JSON::PP;
our (@events, @stages);
our $fault = shift @ARGV;
BEGIN { $INC{'testapi.pm'} = 1; }
package testapi;
sub record_info { }
sub send_key { push @events, $_[0]; }
sub type_string { push @events, 'type'; }
package main;
require onpc_feedback_privacy;
no warnings 'redefine';
*onpc_gdm::reattach_functional = sub { };
*onpc_parent::open_for_child = sub { return $_[0]->seen('parent-selected'); };
*onpc_journey::finish = sub { push @events, 'finish'; };
my $ok = eval {
    onpc_feedback_privacy::run(sub {
        push @events, $_[0]; push @stages, $_[0];
        die 'failed proof' if $_[0] eq $fault;
        return {observed => $_[0]};
    }); 1;
};
print encode_json({ok => $ok ? 1 : 0, events => \@events, stages => \@stages});
''', fault).stdout)
    stages = list(PRIVACY_PLAN.screen_tags)
    stages = stages[stages.index('parent-selected'):]
    assert result['stages'] == (stages[:stages.index(fault) + 1] if fault else stages)
    assert bool(result['ok']) is (not fault)
    if fault:
        assert result['events'][-1] == fault
    else:
        assert result['events'].count('alt-f4') == 3
        assert result['events'].count('type') == 2
        assert result['events'][-1] == 'finish'


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


def test_initial_draft_snapshot_is_bounded_and_immutable_without_input():
    ui, _, _, controls = feedback_ui()
    value = ui.feedback_snapshot()
    frozen = FeedbackObservation.from_value(value)
    value['attachments'].clear()
    assert frozen.attachments == ('diagnostic-logs.zip',)
    with pytest.raises(FrozenInstanceError):
        frozen.draft = 'private'
    ui.api.Text.get_text.assert_not_called()
    for node in controls.values():
        node.action.do_action.assert_not_called()


def test_feedback_ignores_reused_toolkit_ids_but_refuses_hidden_owned_duplicates():
    ui, _, dialog, _ = feedback_ui()
    dialog.children.extend(Node(identity=identity) for identity in ('box', 'box', 'title', 'title'))
    assert ui.feedback_snapshot()['draft'] == 'initial-empty'
    dialog.children.append(Node(identity='feedback-send', states=()))
    with pytest.raises(accessible_ui.UiError, match='ui:feedback-duplicate'):
        ui.feedback_snapshot()


@pytest.mark.parametrize('value,accepted', [('\n', True), ('x', False), (' ', False)])
def test_rich_editor_empty_paragraph_is_an_exact_bounded_comparison(value, accepted):
    ui, _, _, controls = feedback_ui()
    controls['feedback-editor-input'].text.count = 1
    ui.api.Text.get_text = Mock(return_value=value)
    if accepted:
        assert ui.feedback_snapshot()['draft'] == 'initial-empty'
    else:
        with pytest.raises(accessible_ui.UiError, match='ui:feedback-nonempty-draft'):
            ui.feedback_snapshot()
    ui.api.Text.get_text.assert_called_once_with(controls['feedback-editor-input'].text, 0, 1)


def test_reply_field_does_not_accept_the_rich_editor_empty_paragraph():
    ui, _, _, controls = feedback_ui()
    controls['feedback-reply-email'].text.count = 1
    with pytest.raises(accessible_ui.UiError, match='ui:feedback-nonempty-draft'):
        ui.feedback_snapshot()
    ui.api.Text.get_text.assert_not_called()


@pytest.mark.parametrize('fault', ['private', 'reply', 'duplicate', 'attachment',
    'missing', 'disabled', 'inactive', 'stale', 'incomplete', 'collecting',
    'validation', 'wrong-owner', 'projection', 'wrong-entry'])
def test_feedback_refuses_unsafe_or_unready_observations(fault):
    ui, parent, dialog, controls = feedback_ui()
    projection = 'initial-empty'
    if fault in ('private', 'reply'):
        controls['feedback-editor-input' if fault == 'private' else 'feedback-reply-email'].text.count = 5
    elif fault == 'duplicate':
        dialog.children.append(Node(identity='feedback-send'))
    elif fault == 'attachment':
        dialog.children.append(Node(identity='feedback-attachment-0123456789abcdef'))
    elif fault == 'missing':
        dialog.children.remove(controls['feedback-editor-input'])
    elif fault == 'disabled':
        controls['feedback-send'].states.remove('sensitive')
    elif fault == 'inactive':
        dialog.states.remove('active')
    elif fault == 'stale':
        controls['feedback-send'].states.add('defunct')
    elif fault == 'incomplete':
        dialog.get_child_count = Mock(side_effect=LookupError('incomplete'))
    elif fault == 'collecting':
        dialog.children.append(Node(identity='feedback-collection-status'))
    elif fault == 'validation':
        dialog.children.append(Node('Validation failed', identity='feedback-status'))
    elif fault == 'wrong-owner':
        ui.api.get_desktop(0).identity = 'unrelated.application'
    elif fault == 'projection':
        projection = 'arbitrary-private-text'
    elif fault == 'wrong-entry':
        parent.children.clear()
    with pytest.raises((accessible_ui.UiError, LookupError)):
        ui.feedback_snapshot(projection)
    ui.api.Text.get_text.assert_not_called()


def test_wrong_entry_live_operation_is_read_only():
    ui, parent, _, _ = feedback_ui()
    parent.children.clear()
    assert ui.feedback_read_operation('feedback-wrong-entry') is None


@pytest.mark.parametrize('binding', [binding for binding in accessible_ui.TEXT_VALUES
                                     if binding.startswith(('body-', 'reply-'))])
def test_synthetic_text_exact_bounded_readback(binding):
    ui, _, _, controls = feedback_ui()
    identity, value = accessible_ui.TEXT_VALUES[binding]
    controls[identity].text.count = len(value)
    ui.api.Text.get_text = Mock(return_value=value)
    ui.api.Text.get_character_at_offset = Mock(side_effect=lambda text, offset: ord(value[offset]))
    assert ui.read_synthetic_text(binding) == {
        'binding': binding, 'exact': True, 'length': len(value)}
    if binding == 'body-hidden':
        ui.api.Text.get_text.assert_not_called()
        assert ui.api.Text.get_character_at_offset.call_count == len(value)
    elif value:
        ui.api.Text.get_text.assert_called_once_with(controls[identity].text, 0, len(value))
    else:
        ui.api.Text.get_text.assert_not_called()


@pytest.mark.parametrize('fault', ['masked', 'disabled', 'wrong-owner', 'wrong-entry',
                                 'unfocused', 'uncertain', 'wrong-value', 'long-value'])
def test_text_refuses_before_input_or_private_projection(fault):
    ui, parent, _, controls = feedback_ui()
    node = controls['feedback-editor-input']
    component = SimpleNamespace(grab_focus=Mock())
    node.get_component_iface = Mock(return_value=component)
    value = accessible_ui.TEXT_VALUES['body-first'][1]
    node.text.count = len(value)
    ui.api.Text.get_text = Mock(return_value='x' * len(value))
    if fault == 'masked':
        node.role = 'password text'
    elif fault == 'disabled':
        node.states.remove('sensitive')
    elif fault == 'wrong-owner':
        ui.api.get_desktop(0).identity = 'unrelated.application'
    elif fault == 'wrong-entry':
        parent.children.clear()
    elif fault == 'uncertain':
        ui.input_uncertain = True
    elif fault == 'long-value':
        node.text.count = 10000
    with pytest.raises(accessible_ui.UiError):
        if fault in ('wrong-value', 'long-value'):
            ui.read_synthetic_text('body-first')
        else:
            ui.text_recipient('feedback-editor-input', focused=True)
    component.grab_focus.assert_not_called()
    if fault != 'wrong-value':
        ui.api.Text.get_text.assert_not_called()


def test_text_qualification_selector_and_gate(monkeypatch):
    run = Mock(return_value=0)
    monkeypatch.setattr(check_e2e_text, 'smoke', run)
    assert check_e2e_text.main() == 0
    assert run.call_args.kwargs['text_qualification'] is True
    with pytest.raises(CommandError, match='text-prerequisites'):
        smoke.main(text_qualification=True)
    with pytest.raises(CommandError, match='text-prerequisites'):
        smoke.main(assets=object(), provision_credentials=True,
                   text_qualification=True, feedback_read=True)
    assert TEXT_PLAN.worker_mode == 'text_qualification'


def test_text_focus_is_public_and_independently_verified_with_failure_latch():
    ui, _, _, controls = feedback_ui()
    node = controls['feedback-editor-input']
    ui.focus_text('feedback-editor-input')
    node.component.grab_focus.assert_called_once()
    assert ui.text_recipient('feedback-editor-input', focused=True) is node
    node.component.grab_focus.side_effect = None
    node.component.grab_focus.return_value = False
    with pytest.raises(accessible_ui.UiError, match='ui:text-focus-refused'):
        ui.focus_text('feedback-editor-input')
    assert ui.input_uncertain
    with pytest.raises(accessible_ui.UiError, match='ui:uncertain-input'):
        ui.focus_text('feedback-editor-input')
    assert node.component.grab_focus.call_count == 2


def test_live_text_refusals_perform_no_focus_or_text_read():
    ui, parent, _, controls = feedback_ui()
    parent.children.clear()
    disabled = Node(identity='parent-daily-limit-selector', states=('showing', 'visible'))
    parent.children.append(disabled)
    assert ui.text_operation('text-disabled') is None
    assert ui.text_operation('text-wrong-entry') is None
    disabled.component.grab_focus.assert_not_called()
    for node in controls.values():
        node.component.grab_focus.assert_not_called()
    ui.api.Text.get_text.assert_not_called()


def test_native_reply_focus_uses_verified_editor_anchor_without_native_grab():
    ui, _, _, controls = feedback_ui()
    editor = controls['feedback-editor-input']
    reply = controls['feedback-reply-email']
    reply.component.grab_focus.side_effect = AssertionError('GTK has no GrabFocus')
    ui.text_operation('text-reply-first-anchor')
    editor.component.grab_focus.assert_called_once()
    reply.states.add('focused')
    ui.text_operation('text-reply-first-focus')
    ui.text_operation('text-reply-first-selected')
    reply.component.grab_focus.assert_not_called()


def test_reply_anchor_refuses_disabled_destination_before_focusing_editor():
    ui, _, _, controls = feedback_ui()
    controls['feedback-reply-email'].states.remove('sensitive')
    with pytest.raises(accessible_ui.UiError, match='ui:text-disabled'):
        ui.text_operation('text-reply-first-anchor')
    controls['feedback-editor-input'].component.grab_focus.assert_not_called()


def test_text_controller_order_matches_actual_worker_exchange():
    from tests.support.perl import run_perl
    stages = json.loads(run_perl(r'''
use strict; use warnings; use JSON::PP;
our @stages;
BEGIN { $INC{'testapi.pm'} = 1; }
package testapi;
sub record_info { }
sub send_key { }
sub type_string { }
package main;
require onpc_text;
no warnings 'redefine';
*onpc_gdm::reattach_functional = sub { };
*onpc_parent::open_for_child = sub {
    return $_[0]->seen('parent-selected');
};
*onpc_journey::finish = sub { };
onpc_text::run(sub {
    push @stages, $_[0];
    return {observed => $_[0]};
});
print encode_json(\@stages);
''').stdout)
    planned = list(TEXT_PLAN.screen_tags)
    assert stages == planned[planned.index('parent-selected'):]


@pytest.mark.parametrize('binding,fault', [
    (binding, fault)
    for binding in ('body-first', 'body-clear', 'reply-second', 'reply-clear')
    for fault in ('', 'focus', 'selected', 'read', *(
        ('anchor',) if binding.startswith('reply-') else ()))
])
def test_text_worker_stops_at_failed_proof_without_replaying_input(binding, fault):
    from tests.support.perl import run_perl
    result = json.loads(run_perl(r'''
use strict; use warnings; use JSON::PP;
our @events;
our ($binding, $fault) = @ARGV;
BEGIN { $INC{'testapi.pm'} = 1; }
package testapi;
sub record_info { }
sub send_key { push @main::events, $_[0]; }
sub type_string {
    die 'pace' unless $_[1] eq 'max_interval' && $_[2] == 20;
    push @main::events, 'type';
}
package main;
require onpc_text;
no warnings 'redefine';
*onpc_journey::seen = sub {
    my ($self, $stage) = @_;
    push @events, $stage;
    die 'failed proof' if $fault && $stage eq "text-$binding-$fault";
    return {observed => $stage};
};
*onpc_journey::consume_observation = sub { };
my $ok = eval { onpc_text::replace_text(bless({}, 'onpc_journey'), $binding); 1; };
print encode_json({ok => $ok ? 1 : 0, events => \@events});
''', binding, fault).stdout)
    stages = [f'text-{binding}-focus', 'ctrl-a', f'text-{binding}-selected',
              'backspace' if binding.endswith('clear') else 'type', f'text-{binding}-read']
    if binding.startswith('reply-'):
        stages = [f'text-{binding}-anchor', 'ctrl-tab', *stages]
    assert result['events'] == (stages[:stages.index(f'text-{binding}-{fault}') + 1]
                                if fault else stages)
    assert bool(result['ok']) is (not fault)


def test_qualification_selector_and_gate(monkeypatch):
    run = Mock(return_value=0)
    monkeypatch.setattr(check, 'smoke', run)
    assert check.main() == 0
    assert run.call_args.kwargs['feedback_read'] is True
    with pytest.raises(CommandError, match='feedback-read-prerequisites'):
        smoke.main(feedback_read=True)
    with pytest.raises(CommandError, match='feedback-read-prerequisites'):
        smoke.main(assets=object(), provision_credentials=True,
                   feedback_read=True, parent_about=True)


def test_controller_requires_initial_evidence_before_independent_comparison(tmp_path):
    journey = FeedbackReadJourney(SimpleNamespace(directory=tmp_path), Mock())
    ui, _, _, _ = feedback_ui()
    observed = {'ui': {'feedback': ui.feedback_snapshot()}}
    with pytest.raises(EvidenceError, match='independent-read'):
        journey.check_settings('feedback-reread', observed)
    journey.check_settings('feedback-read', observed)
    journey.check_settings('feedback-reread', observed)
    with pytest.raises(EvidenceError, match='replay'):
        journey.check_settings('feedback-read', observed)
    assert PLAN.worker_mode == 'feedback_read'


@pytest.mark.parametrize('fault', ['', 'feedback-read', 'feedback-wrong-entry', 'feedback-reread'])
def test_real_worker_stops_before_further_input_on_failed_observation(fault):
    from tests.support.perl import run_perl
    result = json.loads(run_perl(r'''
use strict; use warnings; use JSON::PP;
our @events;
our $fault = shift @ARGV;
BEGIN { $INC{'testapi.pm'} = 1; }
package testapi;
sub record_info { }
package main;
require onpc_feedback_read;
no warnings 'redefine';
*onpc_gdm::reattach_functional = sub { };
*onpc_parent::open_for_child = sub {
    my ($journey, @args) = @_;
    die 'wrong entry' unless join(',', @args) eq 'gdm,fresh,new,child';
    return $journey->seen('parent-selected');
};
*onpc_journey::finish = sub { push @events, 'finish'; };
my $ok = eval {
    onpc_feedback_read::run(sub {
        push @events, $_[0];
        die 'failed observation' if $_[0] eq $fault;
        return {observed => $_[0]};
    });
    1;
};
print encode_json({ok => $ok ? 1 : 0, events => \@events});
''', fault).stdout)
    stages = ['parent-selected', 'feedback-open', 'feedback-read', 'feedback-close',
              'feedback-wrong-entry', 'feedback-reopen', 'feedback-reread',
              'feedback-finished', 'finish']
    assert result['events'] == (stages[:stages.index(fault) + 1] if fault else stages)
    assert bool(result['ok']) is (not fault)
