"""Shared ID-only interactions with the real feedback editor."""


EDITOR_ID = "feedback-editor-input"
DIALOG_CLOSE_IDS = {
    "feedback-privacy-dialog": "feedback-privacy-close",
    "feedback-success-dialog": "feedback-success-close",
}


def feedback_editor(ui, wait_for_accessible_state):
    wait_for_accessible_state(lambda: ui.find(EDITOR_ID) is not None,
                              "feedback editor publishes its public ID")
    return EDITOR_ID


def type_feedback(ui, value, wait_for_accessible_state):
    from tests.support.keyboard import type_text
    ui.focus(EDITOR_ID)
    type_text(ui, EDITOR_ID, value)
    wait_for_accessible_state(
        lambda: ui.content(EDITOR_ID).strip() == value,
        "rich feedback editor receives typed text",
    )


def dismiss_feedback_dialog(ui, wait_for_accessible_state, identity, *, within):
    """Close a known feedback modal through its stable public response ID."""
    wait_for_accessible_state(lambda: ui.showing(identity), identity + " opens")
    ui.activate(DIALOG_CLOSE_IDS[identity])
    wait_for_accessible_state(lambda: ui.absent(identity, within=within), identity + " closes")


def attachment_choices(directory, batches):
    """Declared OS-chooser inputs; the actual frontend loads and validates bytes."""
    import json
    from tests.e2e.accessible_ui import ATTACHMENT_INPUTS, BOUNDARY_FILES

    choices, paths = [], {}
    for batch in batches:
        inputs = ATTACHMENT_INPUTS if batch == 'standard' else BOUNDARY_FILES[batch]
        root = directory / batch
        root.mkdir()
        paths[batch] = []
        for name, data in inputs:
            path = root / name
            path.write_bytes(data)
            paths[batch].append(path)
        choices.append([str(path) for path in paths[batch]])
    # Re-add the same source after the test changes it; do not supply new bytes
    # directly to the app or read its private in-memory attachment snapshot.
    choices.append([str(path) for path in paths['single']])
    manifest = directory / 'chooser-inputs.json'
    manifest.write_text(json.dumps(choices), encoding='utf-8')
    return manifest, paths


def install_component_chooser(manifest, gtk, gio, glib):
    """Only the external chooser is a double; app callbacks and file I/O are real."""
    import json
    from pathlib import Path
    from types import SimpleNamespace
    from gi.repository import GObject

    manifest = Path(manifest)
    choices = iter(enumerate(json.loads(manifest.read_text(encoding='utf-8')), 1))
    delivery = manifest.with_suffix('.delivered')

    class Chooser(GObject.Object):
        title = GObject.Property(type=str)

        def __init__(self, *, title):
            assert title == 'Add feedback attachments'
            super().__init__(title=title)

        def open_multiple(self, parent, cancellable, callback):
            sequence, self.paths = next(choices)

            def deliver():
                callback(self, None)
                # Acknowledges only the external chooser handoff. The real
                # frontend worker and its public result still own completion.
                delivery.write_text(str(sequence), encoding='ascii')
                return glib.SOURCE_REMOVE

            glib.idle_add(deliver)

        def open_multiple_finish(self, result):
            files = [gio.File.new_for_path(path) for path in self.paths]
            return SimpleNamespace(get_n_items=lambda: len(files), get_item=files.__getitem__)

    gtk.FileDialog = Chooser


def add_component_attachments(ui, batch, manifest):
    """Use the same public before/result projections as the installed handoff."""
    delivery = manifest.with_suffix('.delivered')
    previous = int(delivery.read_text(encoding='ascii')) if delivery.exists() else 0
    ui.boundary_operation(f'boundary-{batch}-before')
    ui.activate_id('feedback-add-files')
    # Consecutive rejected selections can have identical rows and messages.
    # Do not let the previous public result satisfy this selection before the
    # asynchronous chooser double has even called the app's selection handler.
    try:
        ui.wait(lambda: delivery.exists()
                and delivery.read_text(encoding='ascii') == str(previous + 1),
                'component-chooser-delivered')
    except BaseException:
        ui.input_uncertain = True
        raise
    ui.boundary_operation(f'boundary-{batch}-result')
    return ui.boundary_operation(f'boundary-{batch}-preserved')
