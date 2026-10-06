"""Application UI identities and isolated translation-helper engineering contracts."""

import pytest

from tests.e2e.accessible_ui import public_automation_id
from tests.support.automation_ids import audit_product_controls

pytestmark = pytest.mark.ui


@pytest.mark.parametrize('frontend', ['parent', 'kiosk'])
def test_language_chooser_previews_keep_owner_language_until_commit(
        launch_ui, automation, wait_for_accessible_state, tmp_path, frontend):
    """Candidate translations leave the owning window's language unchanged."""
    from common.oh_no_parent_control_ui.languages import SUPPORTED_LANGUAGES
    from tests.support.events import read_events

    events = tmp_path / 'language-candidate-events.jsonl'
    launch_ui('parent_component_preview' if frontend == 'parent' else 'request_component_preview',
              environment_overrides={
                  'ONPC_LANGUAGE_INITIAL': 'en',
                  'ONPC_LANGUAGE_SAVE_FAILURES': '1',
                  'ONPC_PARENT_COMPONENT_EVENTS_PATH': str(events),
                  'ONPC_REQUEST_COMPONENT_EVENTS_PATH': str(events),
                  'LANGUAGE': 'en_US.UTF-8', 'LC_ALL': 'C.UTF-8',
              })
    ui, wait = automation, wait_for_accessible_state
    owner = 'parent-screen-limit-toggle' if frontend == 'parent' else 'kiosk-request-submit'
    owner_text = 'Screen time limit' if frontend == 'parent' else 'REQUEST'
    ui.reader.open_language_preferences(frontend)
    assert ui.target('language-dialog').surface_metadata['parent_id'] == (
        'parent-window' if frontend == 'parent' else 'kiosk-request-window')
    for query, expected in [
        ('GLI', {'en'}), ('PORT*BR', {'pt-BR'}), ('РУСС', {'ru'}),
        ('中文', {'zh-Hans', 'zh-Hant'}), ('SR-?ATN', {'sr-Latn'}),
        ('no such language', set())]:
        ui.setText('language-search', query)
        wait(lambda: {language for language, _name in SUPPORTED_LANGUAGES
                      if ui.showing('language-choice-' + language.lower())} == expected,
             'language search returns exactly the declared matches')
        assert ui.getValue('language-list') == 'en'
    ui.setText('language-search', '')
    assert set(ui.getChoices('language-list')) == {code for code, _name in SUPPORTED_LANGUAGES}
    ui.activate('language-continue')
    wait(lambda: ui.showing('language-error'), 'the ordinary save failure is reported')
    assert not any(event['event'] == 'language-committed' for event in read_events(events))
    for language, title, save, cancel in (
            ('en', 'Choose your language', 'Save', 'Cancel'),
            ('de', 'Sprache wählen', 'Speichern', 'Abbrechen'),
            ('he', 'בחירת השפה שלך', 'שמירה', 'ביטול'),
            ('ta', 'உங்கள் மொழியைத் தேர்ந்தெடுக்கவும்', 'சேமிக்கவும்', 'ரத்து')):
        ui.setValue('language-list', language)
        wait(lambda: ui.getText('language-title') == title, 'the candidate relabels its chooser')
        assert ui.getText('language-continue') == save
        assert ui.getText('language-cancel') == cancel
        assert ui.getValue('language-list') == language
        assert ui.text(owner) == owner_text, 'candidate escaped into owner'
        assert not any(event['event'] == 'language-committed' for event in read_events(events))
    ui.activate('language-cancel')
    wait(lambda: ui.absent('language-dialog', within=(
        'parent-window' if frontend == 'parent' else 'kiosk-request-window')),
         'Cancel leaves the owner language unchanged')
    assert ui.text(owner) == owner_text


def test_translation_bindings_follow_native_lifetime_and_reparenting(hermetic_ui_session):
    """Engineering lifecycle check on the existing private GTK display/bus."""
    import subprocess
    import sys
    from tests.support.paths import ROOT

    # The AT-SPI observer loads GTK 3. Isolate GTK 4 in one waited child on the
    # same private session; no separate compositor or desktop is started.
    script = '''
import gc
import gi
gi.require_version('Gtk', '4.0')
from gi.repository import Gtk
from common.oh_no_parent_control_ui import messages as m
from common.oh_no_parent_control_ui.translation_widgets import context_for, localized, register_retranslation

Gtk.init()
first, second = Gtk.Window(), Gtk.Window()
left, right = Gtk.Box(), Gtk.Box()
first.set_child(left)
second.set_child(right)
english, german = context_for(first), context_for(second)
german.apply('de')
label = localized(Gtk.Label, label=m.SAVE_LINK)
left.append(label)
native = label.weak_ref()
del label
gc.collect()
english.apply('ru')
assert left.get_first_child().get_label() == 'Сохранить ссылку'
label = left.get_first_child()
left.remove(label)
right.append(label)
assert label.get_label() == 'Link speichern'
english.apply('pl')
assert label.get_label() == 'Link speichern'
right.remove(label)
del label
gc.collect()
assert native() is None
assert not english.members and not german.members

class CallbackBox(Gtk.Box):
    def retranslate(self, translations):
        self.text = translations.gettext('Save link')

box = CallbackBox()
register_retranslation(box, box.retranslate)
left.append(box)
assert box.text == 'Zapisz łącze'
callback_native = box.weak_ref()
left.remove(box)
del box
gc.collect()
assert callback_native() is None
assert not english.members
first.destroy()
second.destroy()
'''
    result = subprocess.run([sys.executable, '-c', script], cwd=ROOT,
                            capture_output=True, text=True, timeout=30)
    assert result.returncode == 0, result.stdout + result.stderr


def test_language_is_private_reversible_and_inherited_by_shared_dialogs(
        hermetic_ui_session):
    """Engineering contract for synthetic widget contexts and native lifetime."""
    import subprocess
    import sys
    from tests.support.paths import ROOT

    script = '''
import gc
import gi
gi.require_version('Gtk', '4.0')
from gi.repository import GLib, Gtk
from common.oh_no_parent_control_ui import messages as m
from common.oh_no_parent_control_ui.translation_widgets import context_for, localized, fixed_direction

Gtk.init()
parent, other = Gtk.Window(), Gtk.Window()
box = Gtk.Box()
parent.set_child(box)
leading = localized(Gtk.Label, label=m.SAVE, xalign=0)
box.append(leading)
trailing = localized(Gtk.Label, label=m.CANCEL, xalign=1)
box.append(trailing)
native = Gtk.Label(label='English', xalign=0)
fixed_direction(native, Gtk.TextDirection.LTR)
box.append(native)
data_label = Gtk.Label(label='Zoë <&>', xalign=0)
box.append(data_label)
data_native = data_label.weak_ref()
del data_label
gc.collect()
dialog = Gtk.Window(transient_for=parent)
shared_box = Gtk.Box()
shared_label = localized(Gtk.Label, label=m.SAVE, xalign=0)
shared_box.append(shared_label)
dialog.set_child(shared_box)
other_label = localized(Gtk.Label, label=m.SAVE)
other.set_child(other_label)
context_for(other).apply('de')
context = context_for(parent)
loop = GLib.MainContext.default()
def drain():
    while loop.pending(): loop.iteration(False)
for language in ('ar', 'fa', 'he', 'ug', 'ur'):
    context.apply(language)
    drain()
    assert data_native().get_label() == 'Zoë <&>'
    assert other_label.get_label() == 'Speichern'
    # Late-created containers and labels use the active context once rooted.
    late_box = Gtk.Box()
    late_label = localized(Gtk.Label, label=m.SAVE, xalign=0)
    late_box.append(late_label)
    box.append(late_box)
    drain()
    assert late_label.get_label() == leading.get_label()
    box.remove(late_box)
    del late_box, late_label
    gc.collect()
    context.apply('en')
    drain()
    assert data_native().get_label() == 'Zoë <&>'
    assert shared_label.get_label() == 'Save'
for language in ('ta', 'th', 'zh-Hant', 'ko'):
    context.apply(language)
    assert other_label.get_label() == 'Speichern'
context.apply('en')
# Unparent while the interpreter and its signal callbacks are live; verify the
# native objects and their context registrations are released before shutdown.
other_context = context_for(other)
references = [item.weak_ref() for item in
              (box, leading, trailing, native, shared_box, shared_label, other_label)]
parent.set_child(None)
dialog.set_child(None)
other.set_child(None)
parent.destroy()
dialog.destroy()
other.destroy()
del box, leading, trailing, native, shared_box, shared_label, other_label
drain()
gc.collect()
assert all(reference() is None for reference in references)
assert data_native() is None
assert not context.members and not other_context.members
'''
    result = subprocess.run([sys.executable, '-X', 'faulthandler', '-c', script], cwd=ROOT,
                            capture_output=True, text=True, timeout=30)
    assert result.returncode == 0, result.stdout + result.stderr


def test_private_label_language_preserves_tamil_text_and_attributes(hermetic_ui_session):
    """Engineering Pango binding contract on synthetic labels and entries."""
    import subprocess
    import sys
    from tests.support.paths import ROOT

    script = '''
import gc
import time
import gi
gi.require_version('Gtk', '4.0')
gi.require_version('Gdk', '4.0')
from gi.repository import Gdk, GLib, Gtk, Pango
from common.oh_no_parent_control_ui import messages as m
from common.oh_no_parent_control_ui.translation_widgets import context_for, localized, fixed_direction

Gtk.init()
default_language = Pango.Language.get_default().to_string()
session_languages = tuple(GLib.get_language_names())
provider = Gtk.CssProvider()
provider.load_from_path('common/oh_no_parent_control_ui/feedback.css')
Gtk.StyleContext.add_provider_for_display(Gdk.Display.get_default(), provider,
                                        Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION + 1)
window = Gtk.Window(css_classes=['feedback-dialog'])
box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
window.set_child(box)
heading = localized(Gtk.Label, label=m.HELP_US_MAKE_THINGS_BETTER,
                    css_classes=['feedback-title'])
attributes = Pango.AttrList()
attributes.insert(Pango.attr_underline_new(Pango.Underline.SINGLE))
heading.set_attributes(attributes)
retained_attributes = attributes.to_string()
box.append(heading)
markup = '<b>உதவுங்கள்</b>'
marked = Gtk.Label(label=markup, use_markup=True)
box.append(marked)
native = Gtk.Label(label='English')
fixed_direction(native, Gtk.TextDirection.LTR, language='en')
box.append(native)
entry = Gtk.Entry(text='உதவுங்கள்', placeholder_text='அனுப்பவும்')
box.append(entry)
editable = entry.get_first_child()
assert isinstance(editable, Gtk.Text)
original_context_languages = [widget.get_pango_context().get_language()
                             for widget in (heading, marked, native)]
context = context_for(window)
window.present()
loop = GLib.MainContext.default()
def drain():
    while loop.pending(): loop.iteration(False)
drain()
context.apply('ta')
drain()
assert heading.get_label() == 'மேம்படுத்த எங்களுக்கு உதவுங்கள்'
assert retained_attributes in heading.get_attributes().to_string()
assert 'language ta' in heading.get_attributes().to_string()
assert 'language ta' in marked.get_attributes().to_string()
assert 'language en' in native.get_attributes().to_string()
assert 'language ta' in entry.get_attributes().to_string()
assert 'language ta' in editable.get_attributes().to_string()
assert entry.get_text() == 'உதவுங்கள்' and entry.get_placeholder_text() == 'அனுப்பவும்'
assert native.get_label() == 'English'
assert marked.get_label() == markup and marked.get_use_markup()
context.apply('en')
drain()
assert heading.get_label() == 'Help us make things better'
assert 'language en' in heading.get_attributes().to_string()
assert retained_attributes in heading.get_attributes().to_string()
assert marked.get_label() == markup
assert entry.get_text() == 'உதவுங்கள்' and entry.get_placeholder_text() == 'அனுப்பவும்'
assert 'language en' in entry.get_attributes().to_string()
assert [widget.get_pango_context().get_language() for widget in (heading, marked, native)] == original_context_languages
assert Pango.Language.get_default().to_string() == default_language
assert tuple(GLib.get_language_names()) == session_languages
references = [widget.weak_ref() for widget in (box, heading, marked, native, entry)]
window.set_focus(None)
window.set_child(None)
window.destroy()
del box, heading, marked, native, entry, editable, window
# A presented window can retain its final frame until the next main-loop turn.
# Release the diagnostic layouts too, then bound the native disposal wait.
deadline = time.monotonic() + 2
while time.monotonic() < deadline:
    drain()
    gc.collect()
    if all(reference() is None for reference in references):
        break
    time.sleep(0.01)
assert all(reference() is None for reference in references), [
    type(reference()).__name__ for reference in references if reference() is not None]
assert not context.members
'''
    result = subprocess.run([sys.executable, '-X', 'faulthandler', '-c', script], cwd=ROOT,
                            capture_output=True, text=True, timeout=30)
    assert result.returncode == 0, result.stdout + result.stderr


@pytest.mark.parametrize("launcher", ["kiosk_preview", "child_overlay_preview"])
def test_request_ids_are_public_and_unique(
        launch_ui, automation, wait_for_accessible_state, launcher):
    launch_ui(launcher, wait_for_application=False)
    ui = automation
    wait_for_accessible_state(lambda: ui.find("kiosk-request-window") is not None,
                              "request surface publishes its automation ID")
    for identity in ("kiosk-request-submit", "kiosk-request-cancel",
                     "kiosk-duration-0", "kiosk-duration-custom",
                     "kiosk-duration-300", "kiosk-menu-button",
                     "kiosk-request-status"):
        assert ui.target(identity).get_accessible_id() == identity
    wait_for_accessible_state(lambda: audit_product_controls(ui, "kiosk-request-window"),
                              "complete request ID inventory")


def test_station_selected_uids_drive_the_public_guest_projection(
        launch_ui, automation, wait_for_accessible_state):
    from gi.repository import Atspi, GLib
    from tests.e2e.accessible_ui import AccessibleUI, CHILD, EXISTING_CHILD, PARENT, OTHER_PARENT

    launch_ui("kiosk_preview", wait_for_application=False)
    ui = automation
    wait_for_accessible_state(lambda: ui.showing("kiosk-approver-selector"), "request ready")
    ui.setValue("kiosk-approver-selector", "1010")
    wait_for_accessible_state(lambda: ui.showing("kiosk-approver-selected-1010"), "selected approver UID")
    ui.setValue("kiosk-child-selector", "1002")
    wait_for_accessible_state(lambda: ui.showing("kiosk-child-selected-1002"), "selected child UID")
    wait_for_accessible_state(lambda: ui.showing("kiosk-screen-limit-notice"), "disabled child loaded")
    reader = AccessibleUI(Atspi, timeout=20, query_errors=(GLib.Error,),
                          dispatch=lambda: GLib.MainContext.default().iteration(False),
                          application_ids=launch_ui.application_ids,
                          application_owners=launch_ui.application_owners,
                          fixture_uids={CHILD: 1001, EXISTING_CHILD: 1002,
                                        PARENT: 1000, OTHER_PARENT: 1010})
    result = reader.kiosk_request_form()
    assert result['child'] == 'existing-fixture-child'
    assert result['approver'] == 'other-fixture-parent'
    assert result['duration_seconds'] == 1800
    assert result['request_enabled'] is False
    # REQUEST04 uses the same installed reader and public actions; each
    # selection validates the complete offered UID set before committing.
    result = reader.select_kiosk_account('child', CHILD, expected=(CHILD, EXISTING_CHILD))
    assert result['child'] == 'fixture-child'
    assert result['request_enabled'] is True
    result = reader.select_kiosk_account('approver', PARENT, expected=(PARENT, OTHER_PARENT))
    assert result['approver'] == 'fixture-parent'
    independent = reader.kiosk_request_form(enabled=True)
    assert independent == result


def test_parent_feedback_and_about_publish_public_ids(
        launch_ui, automation, wait_for_accessible_state):
    launch_ui("parent_component_preview", wait_for_application=False)
    ui = automation
    wait_for_accessible_state(lambda: ui.find("parent-feedback-button") is not None,
                              "parent controls publish IDs")
    for identity in ("parent-window", "parent-menu-button",
                     "parent-child-selector", "parent-screen-limit-toggle"):
        assert ui.target(identity).get_accessible_id() == identity
    wait_for_accessible_state(lambda: audit_product_controls(ui, "parent-window"),
                              "complete Parent ID inventory")
    ui.activate("parent-feedback-button")
    wait_for_accessible_state(lambda: ui.find("feedback-dialog") is not None,
                              "feedback dialog publishes its ID")
    assert ui.target("feedback-dialog").surface_metadata['parent_id'] == 'parent-window'
    for identity in ("feedback-dialog", "feedback-webview", "feedback-send",
                     "feedback-close", "feedback-toggle-logs", "feedback-content"):
        assert ui.target(identity).get_accessible_id() == identity
    wait_for_accessible_state(lambda: ui.find("feedback-editor-input") is not None,
                              "rich editor publishes its input ID")
    from tests.e2e.accessible_ui import AccessibleUI
    # Both facades share this private bus's node identities when passing an
    # explicit scope between them; independent connections own separate nodes.
    guest_reader = AccessibleUI(ui.api, application_ids=launch_ui.application_ids,
                                application_owners=launch_ui.application_owners)
    for identity in ("feedback-editor-input", "feedback-format-bold",
                     "feedback-format-style", "feedback-format-link"):
        node = ui.target(identity)
        attributes = node.get_attributes()
        assert attributes["toolkit"] == "ApplicationUI"
        assert attributes["id"] == identity
        assert guest_reader.find_id(identity, root=ui.target("feedback-webview")) == node
    wait_for_accessible_state(lambda: audit_product_controls(ui, "feedback-dialog"),
                              "complete feedback ID inventory")
    ui.activate("feedback-close")
    wait_for_accessible_state(
        lambda: ui.absent("feedback-dialog", within="parent-window"),
        "feedback dialog closes",
    )
    ui.setValue("parent-menu-button", "about")
    wait_for_accessible_state(lambda: ui.find("about-dialog") is not None,
                              "About dialog publishes its ID")
    assert ui.target("about-dialog").surface_metadata['parent_id'] == 'parent-window'
    for identity in ("about-version", "about-license-value",
                     "about-legal-notices-value", "about-integration-notice"):
        assert ui.target(identity).get_accessible_id() == identity
    wait_for_accessible_state(lambda: audit_product_controls(ui, "about-dialog"),
                              "complete About ID inventory")
