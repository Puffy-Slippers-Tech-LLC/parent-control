"""Exercise the feedback dialog through stable Application UI IDs."""

import pytest
from tests.support.automation_ids import audit_product_controls
from tests.support.gui_blocks import run_block
from tests.support.feedback import (
    dismiss_feedback_dialog,
    feedback_editor,
    type_feedback,
)


pytestmark = pytest.mark.ui


# Draft preservation uses representative script changes; catalogue tests cover
# every translated message without repeating the whole editor journey.
@pytest.mark.parametrize('language', ['de', 'zh-Hans', 'he', 'ta'])
def test_language_switch_preserves_feedback_draft_reply_and_undo(
        launch_ui, automation, wait_for_accessible_state, language):
    from tests.support.keyboard import type_text, key_combo
    from tests.support.localization_review import switch_language, review_frame, public_label_names
    ui, wait = automation, wait_for_accessible_state
    editor, _log = open_feedback(launch_ui, ui, wait)
    type_feedback(ui, 'A retained draft', wait)
    ui.focus('feedback-reply-email')
    type_text(ui, 'feedback-reply-email', 'review@example.com')
    ui.activate('feedback-close')
    wait(lambda: ui.absent('feedback-dialog', within='parent-window'), 'draft closes')
    switch_language(ui, wait, 'parent', language)
    review_frame('parent-' + language)
    ui.activate('parent-feedback-button')
    wait(lambda: ui.showing('feedback-dialog'), 'draft reopens')
    feedback_editor(ui, wait)
    assert ui.content(editor).strip() == 'A retained draft'
    assert ui.content('feedback-reply-email') == 'review@example.com'
    expected = {'de': 'Fett', 'zh-Hans': '粗体', 'he': 'מודגש', 'ta': 'தடித்த'}
    wait(lambda: ui.text('feedback-format-bold') == expected[language], 'toolbar relabels')
    review_frame('feedback-' + language)
    ui.focus(editor)
    type_text(ui, editor, '!')
    wait(lambda: ui.content(editor).strip() == 'A retained draft!', 'draft remains editable')
    key_combo(ui, editor, '<Control>z', state=ui.api.StateType.FOCUSED)
    wait(lambda: ui.content(editor).strip() == 'A retained draft', 'undo survives switch')
    files = {'de': 'Dateien hinzufügen', 'zh-Hans': '添加文件',
             'he': 'הוספת קבצים', 'ta': 'கோப்புகளைச் சேர்க்கவும்'}
    assert ui.text('feedback-add-files') == files[language]
    headings = {'de': 'Die App gemeinsam verbessern', 'zh-Hans': '帮助我们改进应用',
                'he': 'עזרו לנו להשתפר', 'ta': 'மேம்படுத்த எங்களுக்கு உதவுங்கள்'}
    assert headings[language] in public_label_names(ui, 'feedback-content')


def block_semantic_tree(node):
    """Retain bounded public-tree diagnostics for the declared synthetic editor."""
    remaining = 128

    def describe(item, depth):
        nonlocal remaining
        remaining -= 1
        assert remaining >= 0 and depth < 12
        text = item.get_text_iface()
        length = text.get_character_count() if text else 0
        assert 0 <= length <= 128
        count = item.get_child_count()
        assert 0 <= count <= 32
        attrs = item.get_attributes()
        return {'role': item.get_role_name(),
                'attributes': {key: attrs[key] for key in ('level', 'xml-roles', 'roledescription')
                               if key in attrs},
                'text': text.get_text(0, length) if text else None,
                'children': [describe(item.get_child_at_index(i), depth + 1)
                             for i in range(count)]}

    return describe(node, 0)


def test_feedback_restored_block_semantics(launch_ui, automation, wait_for_accessible_state):
    from tests.e2e.block_semantics import FORMATS, projection
    open_feedback(launch_ui, automation, wait_for_accessible_state,
                  scenario='feedback-restored-blocks')
    wait_for_accessible_state(
        lambda: automation.reader.block_semantics() == projection(FORMATS),
        'restored delta exposes current public block meanings')
    print('BLOCK_SEMANTICS_RESTORED', block_semantic_tree(
        automation.target('feedback-editor-input')), flush=True)


def test_feedback_restored_link_semantics(launch_ui, automation, wait_for_accessible_state):
    from tests.e2e import feedback_formats as formats
    from tests.e2e.accessible_ui import require
    open_feedback(launch_ui, automation, wait_for_accessible_state,
                  scenario='feedback-restored-link')
    assert formats.read(automation.reader, require, 'linked-kept-reopen') == formats.expected('linked-kept-reopen')


def test_link_action_labels_follow_editing_mode_and_language(
        launch_ui, automation, wait_for_accessible_state):
    from tests.e2e import feedback_formats as formats
    from tests.e2e.accessible_ui import require
    from tests.support.keyboard import key_combo
    from tests.support.localization_review import switch_language
    ui, wait = automation, wait_for_accessible_state
    editor, _ = open_feedback(launch_ui, ui, wait, scenario='feedback-restored-link')
    # The public WebKit text projection may include Quill's final newline.
    original = ui.content(editor).rstrip('\n')
    ui.activate('feedback-close')
    wait(lambda: ui.absent('feedback-dialog', within='parent-window'), 'draft closes')
    switch_language(ui, wait, 'parent', 'de')
    ui.activate('parent-feedback-button')
    feedback_editor(ui, wait)
    ui.focus(editor)
    key_combo(ui, editor, '<Control>End', state=ui.api.StateType.FOCUSED)
    key_combo(ui, editor, 'Home', state=ui.api.StateType.FOCUSED)
    key_combo(ui, editor, 'Right', state=ui.api.StateType.FOCUSED)
    wait(lambda: ui.showing('feedback-link-save'), 'existing link action appears')
    assert ui.text('feedback-link-save') == 'Link bearbeiten'
    assert ui.content('feedback-link-save') == 'Link bearbeiten'
    assert ui.text('feedback-link-remove') == 'Link entfernen'
    assert ui.content('feedback-link-remove') == 'Link entfernen'
    ui.activate('feedback-link-save')
    wait(lambda: ui.showing('feedback-link-target'), 'link editor is available')
    assert ui.text('feedback-link-save') == 'Link speichern'
    assert ui.content('feedback-link-save') == 'Link speichern'
    ui.activate('feedback-link-save')
    # Saving closes Quill's tooltip; moving the caret back inside the existing
    # link opens its preview action again.
    ui.focus(editor)
    key_combo(ui, editor, '<Control>End', state=ui.api.StateType.FOCUSED)
    key_combo(ui, editor, 'Home', state=ui.api.StateType.FOCUSED)
    key_combo(ui, editor, 'Right', state=ui.api.StateType.FOCUSED)
    wait(lambda: ui.showing('feedback-link-save'), 'saved link preview opens')
    wait(lambda: ui.text('feedback-link-save') == 'Link bearbeiten', 'link preview returns')
    assert ui.content(editor).rstrip('\n') == original
    assert formats.read(ui.reader, require, 'linked-kept-reopen') == formats.expected('linked-kept-reopen')


def test_feedback_block_semantics(
        launch_ui, automation, wait_for_accessible_state):
    """Real product semantics, shared reader, independent reopen and removal."""
    from tests.e2e.block_semantics import BODY, FORMATS, RANGES, projection
    from tests.support.keyboard import key_combo
    ui = automation
    editor, _log = open_feedback(launch_ui, ui, wait_for_accessible_state)
    run_block(ui.reader, 'replace', 'body-blocks')
    assert ui.reader.block_operation('block-before') == []
    for kind in FORMATS:
        run_block(ui.reader, 'block', kind)
    assert ui.reader.block_semantics() == projection(FORMATS)
    ui.activate("feedback-close")
    wait_for_accessible_state(
        lambda: ui.absent("feedback-dialog", within="parent-window"), "feedback closed")
    ui.reader.block_operation('block-wrong-entry')
    ui.activate("parent-feedback-button")
    wait_for_accessible_state(lambda: ui.showing("feedback-dialog"), "feedback reopened")
    feedback_editor(ui, wait_for_accessible_state)
    assert ui.reader.block_semantics() == projection(FORMATS)
    print('BLOCK_SEMANTICS_REOPEN', block_semantic_tree(ui.target(editor)), flush=True)
    ui.focus(editor)
    key_combo(ui, editor, '<Control>a', state=ui.api.StateType.FOCUSED)
    ui.activate('feedback-format-clear')
    wait_for_accessible_state(lambda: ui.reader.block_semantics() == [], 'block roles removed')
    ui.focus(editor)
    key_combo(ui, editor, '<Control>z', state=ui.api.StateType.FOCUSED)
    wait_for_accessible_state(lambda: ui.reader.block_semantics() == projection(FORMATS),
                             'undo restores every meaning')
    key_combo(ui, editor, '<Control><Shift>z', state=ui.api.StateType.FOCUSED)
    wait_for_accessible_state(lambda: ui.reader.block_semantics() == [], 'redo removes every meaning')


# Attachment adapter coverage uses the existing private preview/display/bus and
# owned-process cleanup; it retains the reviewed Feedback scheduler bucket.
# Linked inline, restoration and undo/redo retain those same private resources.
@pytest.mark.parametrize('linked', [False, True], ids=['all-formats', 'linked-inline'])
def test_feedback_complete_format_sequence(launch_ui, automation, wait_for_accessible_state, linked):
    # Same private preview/display/bus and owned cleanup as block qualification.
    from tests.e2e import feedback_formats as formats
    from tests.support.keyboard import key_combo
    from tests.e2e.accessible_ui import UiError, require
    ui = automation
    editor, _log = open_feedback(launch_ui, ui, wait_for_accessible_state)
    run_block(ui.reader, 'replace', 'body-blocks')

    def operation(stage):
        if linked and not stage.startswith('formats-clear'):
            stage = stage.replace('formats-', 'linked-', 1)
        print('FORMAT_STAGE', stage, flush=True)
        return formats.operate(ui.reader, stage, require, UiError)

    operation('formats-before')
    if linked:
        for kind in (*formats.INLINE, 'link'):
            run_block(ui.reader, 'inline', kind, 'linked')
    else:
        run_block(ui.reader, 'formats')
    for action in ('close', 'wrong-entry', 'reopen'):
        operation('formats-kept-' + action)
    run_block(ui.reader, 'inline', 'clear')
    ui.focus(editor)
    key_combo(ui, editor, '<Control>z', state=ui.api.StateType.FOCUSED)
    formats.read(ui.reader, require, 'linked-kept-reopen' if linked else 'formats-kept-reopen')
    key_combo(ui, editor, '<Control><Shift>z', state=ui.api.StateType.FOCUSED)
    formats.read(ui.reader, require, 'formats-clear-read')
    for action in ('close', 'wrong-entry', 'reopen'):
        operation('formats-cleared-' + action)


def test_feedback_basic_installed_edit_sequence(
        launch_ui, automation, wait_for_accessible_state):
    """The same text, bold and emoji sample used by installed case 152."""
    open_feedback(launch_ui, automation, wait_for_accessible_state)
    reader = automation.reader
    run_block(reader, 'replace', 'body-first')
    run_block(reader, 'bold')
    run_block(reader, 'scalar', 'body-smoke')
    assert reader.basic_feedback_formatting() == {
        'blocks': [], 'inline': ['bold'], 'link': None,
        'normal_comparison': True, 'text_exact': True}


def test_feedback_unicode_and_hidden_character_validation(
        launch_ui, automation, wait_for_accessible_state):
    """Non-ASCII, combining marks and multi-scalar emoji remain exact in the GUI."""
    from tests.support.keyboard import key_combo, type_text
    editor, _ = open_feedback(launch_ui, automation, wait_for_accessible_state)
    ui = automation
    value = 'é' + 'e\u0301' + '漢' + '😀' + '👍🏽' + '👩\u200d💻'
    ui.setText(editor, value)
    wait_for_accessible_state(lambda: ui.content(editor).rstrip('\n') == value,
                              'all Unicode scalars remain exact')
    ui.activate('feedback-close')
    wait_for_accessible_state(lambda: ui.absent('feedback-dialog', within='parent-window'),
                              'Unicode draft closes')
    ui.activate('parent-feedback-button')
    feedback_editor(ui, wait_for_accessible_state)
    wait_for_accessible_state(lambda: ui.content(editor).rstrip('\n') == value,
                              'Unicode draft survives reopening')
    run_block(ui.reader, 'hidden')
    ui.reader.run('rejection-hidden-send', '')
    assert ui.reader.run('rejection-hidden-read', '')['feedback_state']['validation'] == 'hidden-invalid'


def test_attachment_items_adapter_reads_real_rows_and_removes_one(
        launch_ui, automation, wait_for_accessible_state):
    open_feedback(launch_ui, automation, wait_for_accessible_state,
                  scenario="attachment-items")
    wait_for_accessible_state(
        lambda: automation.text("feedback-logs-row") == "diagnostic-logs.zip",
        "diagnostics are ready")
    assert automation.reader.attachment_operation('attachment-details')['items'] == [
        ['Second note.txt', '33 bytes'], ['Synthetic note.txt', '26 bytes']]
    before = automation.reader.attachment_operation('attachment-details')['items']
    assert automation.reader.attachment_operation('attachment-preview') == {
        'checked': 'attachment-preview', 'items': before, 'preview': 'not-offered'}
    assert automation.reader.attachment_operation('attachment-preview-return')['items'] == before
    assert automation.reader.attachment_operation('attachment-remove')['items'] == [
        ['Synthetic note.txt', '26 bytes']]
    assert automation.reader.attachment_operation('attachment-remaining')['items'] == [
        ['Synthetic note.txt', '26 bytes']]


def open_feedback(launch_ui, ui, wait, *, scenario="normal", status=None,
                  collection_release=None, chooser_inputs=None):
    environment = {"ONPC_PARENT_COMPONENT_SCENARIO": scenario,
                   "GTK_IM_MODULE": "gtk-im-context-simple"}
    if status is not None:
        environment["ONPC_FEEDBACK_STATUS"] = str(status)
    if collection_release is not None:
        environment["ONPC_FEEDBACK_COLLECTION_RELEASE"] = str(collection_release)
    if chooser_inputs is not None:
        environment['ONPC_FEEDBACK_CHOOSER_INPUTS'] = str(chooser_inputs)
    _process, log = launch_ui(
        "parent_component_preview", environment_overrides=environment,
        wait_for_application=False,
    )
    wait(lambda: ui.find("parent-feedback-button") is not None,
         "Parent feedback action publishes its ID")
    ui.activate("parent-feedback-button")
    wait(lambda: ui.showing("feedback-dialog"), "feedback dialog opens")
    editor = feedback_editor(ui, wait)
    return editor, log


def test_attachment_validation_matrix_and_source_snapshot(
        launch_ui, automation, wait_for_accessible_state, tmp_path):
    """Full frontend matrix, real file reads, private declared chooser inputs."""
    from tests.support.feedback import attachment_choices, add_component_attachments
    from tests.e2e.accessible_ui import CHANGED_ATTACHMENT
    batches = ('standard', 'count', 'sixth', 'maximum', 'oversized', 'total',
               'overflow', 'name180', 'name181', 'hidden', 'mixed', 'single')
    manifest, paths = attachment_choices(tmp_path, batches)
    open_feedback(launch_ui, automation, wait_for_accessible_state, chooser_inputs=manifest)
    ui = automation.reader
    ui.feedback_snapshot()
    ui.activate_id('feedback-add-files')
    ui.chooser_operation('chooser-attachments')
    ui.attachment_operation('attachment-remove')
    ui.attachment_operation('attachment-remaining')
    ui.boundary_operation('boundary-clear-small')
    for batch in ('count', 'sixth'):
        add_component_attachments(ui, batch, manifest)
    ui.boundary_operation('boundary-clear-count')
    ui.boundary_operation('boundary-exclude-logs')
    for batch in ('maximum', 'oversized', 'total'):
        add_component_attachments(ui, batch, manifest)
    ui.boundary_operation('boundary-remove-total')
    add_component_attachments(ui, 'overflow', manifest)
    ui.boundary_operation('boundary-clear-maximum')
    for batch in ('name180', 'name181', 'hidden', 'mixed'):
        add_component_attachments(ui, batch, manifest)
    ui.boundary_operation('boundary-clear-name')
    add_component_attachments(ui, 'single', manifest)
    paths['single'][0].write_bytes(CHANGED_ATTACHMENT[0][1])
    ui.boundary_operation('boundary-source-unchanged')
    ui.boundary_operation('boundary-remove-single')
    assert add_component_attachments(ui, 'changed', manifest)['items'] == [
        ['Synthetic note.txt', '34 bytes']]


def test_feedback_draft_and_optional_attachment(
        launch_ui, automation, wait_for_accessible_state, collect_application_logs):
    ui = automation
    editor, log_path = open_feedback(launch_ui, ui, wait_for_accessible_state)
    type_feedback(ui, "Feedback draft must stay local.", wait_for_accessible_state)
    ui.activate("feedback-privacy-link")
    wait_for_accessible_state(lambda: ui.showing("feedback-privacy-dialog"),
                              "privacy dialog opens")
    assert audit_product_controls(ui, "feedback-privacy-dialog")
    assert ui.target("feedback-privacy-dialog").surface_metadata['parent_id'] == 'feedback-dialog'
    assert "Diagnostic logs do not collect account names" in ui.text("feedback-privacy-text")
    assert ui.reader.clickable_link("feedback-full-privacy-link")
    dismiss_feedback_dialog(ui, wait_for_accessible_state, "feedback-privacy-dialog",
                            within="feedback-dialog")
    wait_for_accessible_state(
        lambda: ui.state("feedback-download-logs", ui.api.StateType.SENSITIVE),
        "diagnostics are ready",
    )
    ui.activate("feedback-toggle-logs")
    wait_for_accessible_state(lambda: ui.text("feedback-logs-row") == "No logs attached",
                              "logs removed")
    ui.activate("feedback-toggle-logs")
    wait_for_accessible_state(lambda: ui.text("feedback-logs-row") == "diagnostic-logs.zip",
                              "logs restored")
    assert ui.content(editor).strip() == "Feedback draft must stay local."
    wait_for_accessible_state(lambda: ui.state("feedback-send", ui.api.StateType.SENSITIVE),
                              "feedback send is ready")
    ui.activate("feedback-close")
    wait_for_accessible_state(lambda: ui.absent("feedback-dialog", within="parent-window"),
                              "feedback dialog closed")
    ui.activate("parent-feedback-button")
    wait_for_accessible_state(lambda: ui.showing("feedback-dialog"),
                              "feedback dialog reopens")
    feedback_editor(ui, wait_for_accessible_state)
    assert ui.content(editor).strip() == "Feedback draft must stay local."
    log = collect_application_logs(log_path)
    assert "Feedback draft must stay local." not in log
    assert "Traceback" not in log
    assert "Theme parser error" not in log




def test_collection_observer_waits_for_finished_state(
        launch_ui, automation, wait_for_accessible_state, tmp_path):
    release = tmp_path / 'collection-release'
    launch_ui('parent_component_preview', environment_overrides={
        'ONPC_PARENT_COMPONENT_SCENARIO': 'feedback-collecting',
        'ONPC_FEEDBACK_COLLECTION_RELEASE': str(release),
    }, wait_for_application=False)
    wait_for_accessible_state(lambda: automation.find('parent-feedback-button') is not None,
                              'Parent feedback entry')
    automation.activate('parent-feedback-button')
    release.touch()
    try:
        result = automation.reader.wait_feedback_collection()
    finally:
        release.touch()
    assert result == {'collecting': False, 'download': True}


def test_collection_progress_disables_send_but_allows_editing(
        launch_ui, automation, wait_for_accessible_state, tmp_path):
    ui = automation
    release = tmp_path / "feedback-collection-release"
    editor, _log = open_feedback(
        launch_ui, ui, wait_for_accessible_state,
        scenario="feedback-collecting",
        collection_release=release,
    )
    try:
        wait_for_accessible_state(lambda: ui.showing("feedback-collection-status"),
                                  "collection progress is public")
        assert not ui.state("feedback-send", ui.api.StateType.SENSITIVE)
        assert ui.state("feedback-close", ui.api.StateType.SENSITIVE)
        assert ui.state(editor, ui.api.StateType.SENSITIVE)
        type_feedback(ui, "Draft during collection", wait_for_accessible_state)
    finally:
        release.touch()
    wait_for_accessible_state(lambda: ui.find("feedback-logs-row") is not None
                              and ui.text("feedback-logs-row") == "diagnostic-logs.zip",
                              "diagnostics collection completes")
    wait_for_accessible_state(lambda: ui.state("feedback-send", ui.api.StateType.SENSITIVE),
                              "collection enables sending")
    assert ui.content(editor).strip() == "Draft during collection"
    assert ui.absent("feedback-collection-status", within="feedback-dialog")


@pytest.mark.parametrize("status", [202, 409, 413, 422])
def test_feedback_submission_outcomes(
        launch_ui, automation, wait_for_accessible_state,
        collect_application_logs, status):
    from tests.support.keyboard import key_combo, type_text
    ui = automation
    editor, log_path = open_feedback(
        launch_ui, ui, wait_for_accessible_state, status=status,
    )
    type_feedback(ui, "A private feedback draft", wait_for_accessible_state)
    if status == 202:
        ui.setText("feedback-reply-email", "feedback@example.com")
    wait_for_accessible_state(lambda: ui.state("feedback-send", ui.api.StateType.SENSITIVE),
                              "feedback send is ready")
    ui.activate("feedback-send")
    if status == 409:
        wait_for_accessible_state(
            lambda: ui.text("feedback-send") == "Submit again (may duplicate)",
            "duplicate-safe retry offered",
        )
        assert ui.content(editor).strip() == "A private feedback draft"
        ui.activate("feedback-send")
    elif status == 413:
        wait_for_accessible_state(lambda: ui.showing("feedback-send-without-logs"),
                                  "send without logs offered")
        assert ui.content(editor).strip() == "A private feedback draft"
        ui.activate("feedback-send-without-logs")
    elif status == 422:
        expected = ("Feedback was not accepted. Your draft is preserved. Check your "
                    "feedback and reply address before sending again.")
        wait_for_accessible_state(lambda: ui.find("feedback-status") is not None
                                  and ui.text("feedback-status") == expected,
                                  "rejected feedback preserves draft")
        assert ui.content(editor).strip() == "A private feedback draft"
        assert ui.state(editor, ui.api.StateType.SENSITIVE)
        ui.activate("feedback-send")
    wait_for_accessible_state(lambda: ui.showing("feedback-success-dialog"),
                              "success confirmation opens")
    assert audit_product_controls(ui, "feedback-success-dialog")
    wait_for_accessible_state(lambda: ui.absent("feedback-dialog", within="parent-window"),
                              "feedback editor hides before confirmation dismissal")
    body = "Your feedback was sent successfully. We appreciate your help making the app better."
    if status == 202:
        body += ("\n\nWe may contact you at the email address you provided if we have "
                 "any follow-up questions.")
    assert ui.text("feedback-success-text") == body
    dismiss_feedback_dialog(ui, wait_for_accessible_state, "feedback-success-dialog",
                            within="parent-window")
    ui.activate("parent-feedback-button")
    wait_for_accessible_state(lambda: ui.showing("feedback-dialog"),
                              "feedback dialog reopens")
    feedback_editor(ui, wait_for_accessible_state)
    assert not ui.content(editor).strip()
    if status == 413:
        assert ui.text("feedback-logs-row") == "No logs attached"
    log = collect_application_logs(log_path)
    assert "A private feedback draft" not in log
    assert "Traceback" not in log
