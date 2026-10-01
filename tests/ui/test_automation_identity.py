"""Qualify production IDs through the public accessibility connection."""

import pytest

from tests.e2e.accessible_ui import public_automation_id
from tests.support.automation_ids import audit_product_controls

pytestmark = pytest.mark.ui


@pytest.mark.parametrize('frontend', ['parent', 'kiosk'])
def test_language_chooser_previews_without_remapping_or_changing_owner(
        hermetic_ui_session, frontend):
    """Engineering check: live text changes preserve the mapped widget tree."""
    import subprocess
    import sys
    from tests.support.paths import ROOT

    script = '''
import gi
gi.require_version('Gtk', '4.0')
from gi.repository import Gio, GLib, Gtk
from common.oh_no_parent_control_ui import messages as m
from common.oh_no_parent_control_ui.translation_widgets import context_for, localized
from common.oh_no_parent_control_ui.languages import SUPPORTED_LANGUAGES
from common.oh_no_parent_control_ui.localization import load_translations
from FRONTEND.oh_no_parent_control_FRONTEND.language_dialog import LanguageDialog

Gtk.init()
application = Gtk.Application(application_id='com.puffyslippers.LanguageModalTest',
                              flags=Gio.ApplicationFlags.NON_UNIQUE)
application.register(None)
parent = Gtk.ApplicationWindow(application=application)
label = localized(Gtk.Label, label=m.CHOOSE_YOUR_LANGUAGE)
parent.set_child(label)
context_for(parent).apply('en')
parent.present()
if 'FRONTEND' == 'kiosk':
    parent.fullscreen()
saves, cancellations, events = [], [], []
options = {'account': (1001, 'Zoë', '')} if 'FRONTEND' == 'kiosk' else {}
dialog = LanguageDialog(parent, 'en', lambda *args: saves.append(args),
                        None, lambda: cancellations.append(True), **options)
dialog.connect('map', lambda *_: events.append('map'))
dialog.connect('unmap', lambda *_: events.append('unmap'))
dialog.present()
loop = GLib.MainContext.default()
def drain():
    while loop.pending():
        loop.iteration(False)
drain()
assert dialog.get_application() is application
assert dialog.get_transient_for() is parent and dialog.get_modal()
assert dialog.get_group() == parent.get_group()
assert dialog.get_surface().get_property('modal')
assert dialog.get_surface().get_property('transient-for') == parent.get_surface()

# Exercise the activation that an outside click requests from the compositor.
# This is an engineering focus/lifecycle check, not native pointer acceptance.
parent.present()
settled = GLib.MainLoop()
GLib.timeout_add(250, lambda: (settled.quit(), GLib.SOURCE_REMOVE)[1])
settled.run()
assert dialog.is_active(), 'parent activation stole modal focus'
dialog.close()
drain()
assert dialog.get_mapped() and events == ['map'], events
assert not saves and not cancellations

def controls(widget):
    result = {}
    identity = Gtk.Buildable.get_buildable_id(widget)
    if identity and identity.startswith('language-'):
        result[identity] = widget
    child = widget.get_first_child()
    while child is not None:
        result.update(controls(child))
        child = child.get_next_sibling()
    return result

original = controls(dialog)
dialog._failure(None)
for language, native_name in SUPPORTED_LANGUAGES:
    choice = original['language-choice-' + language.lower()]
    choice.set_active(True)
    drain()
    translations = load_translations(language)
    assert original['language-title'].get_label() == translations.gettext('Choose your language')
    assert 'language-description' not in controls(dialog)
    assert original['language-continue'].get_label() == translations.gettext('Save')
    assert original['language-cancel'].get_label() == translations.gettext('Cancel')
    assert original['language-error'].get_label() == translations.gettext('Your language could not be saved. Please try again.')
    assert choice.get_child().get_label() == native_name
    assert choice.get_active() and dialog._selected == language
    assert controls(dialog) == original, 'translation rebuilt controls'
    assert dialog.get_mapped() and events == ['map'], events
    assert label.get_label() == 'Choose your language', 'candidate escaped into owner'
    assert not saves and not cancellations
dialog._dismiss(None)
assert cancellations == [True] and not saves
assert label.get_label() == 'Choose your language'
parent.destroy()
'''.replace('FRONTEND', frontend)
    result = subprocess.run([sys.executable, '-c', script], cwd=ROOT,
                            capture_output=True, text=True, timeout=30)
    assert result.returncode == 0, result.stdout + result.stderr


def test_parent_language_chooser_unmaps_before_relabeling(hermetic_ui_session):
    """Engineering check: the outgoing native window never paints new text."""
    import subprocess
    import sys
    from tests.support.paths import ROOT

    script = '''
import gi
gi.require_version('Gtk', '4.0')
from gi.repository import GLib, Gtk
from common.oh_no_parent_control_ui import messages as m
from common.oh_no_parent_control_ui.translation_widgets import context_for, localized
from parent.oh_no_parent_control_parent.language_dialog import LanguageDialog

Gtk.init()
parent = Gtk.Window()
label = localized(Gtk.Label, label=m.CHOOSE_YOUR_LANGUAGE)
parent.set_child(label)
context = context_for(parent)
context.apply('en')
parent.present()
events = []

def saved(language):
    assert not dialog.get_mapped(), 'chooser is still visible during relabeling'
    events.append('applied')
    context.apply(language)

dialog = LanguageDialog(parent, 'en', None, saved, None)
dialog.connect('unmap', lambda *_: events.append('unmapped'))
dialog.present()
loop = GLib.MainContext.default()
while loop.pending():
    loop.iteration(False)
assert dialog.get_mapped()
dialog._success('de')
assert events == ['unmapped', 'applied'], events
assert parent.get_child() is label
assert label.get_label() == 'Sprache wählen'
parent.destroy()
'''
    result = subprocess.run([sys.executable, '-c', script], cwd=ROOT,
                            capture_output=True, text=True, timeout=30)
    assert result.returncode == 0, result.stdout + result.stderr


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
    ui.activate("kiosk-approver-selector")
    wait_for_accessible_state(
        lambda: ui.find("kiosk-approver-choice-1010") is not None,
        "approver choice is published",
    )
    ui.activate("kiosk-approver-choice-1010")
    wait_for_accessible_state(lambda: ui.showing("kiosk-approver-selected-1010"), "selected approver UID")
    ui.activate("kiosk-child-selector")
    wait_for_accessible_state(
        lambda: ui.find("kiosk-child-choice-1002") is not None,
        "child choice is published",
    )
    ui.activate("kiosk-child-choice-1002")
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
    import gi
    gi.require_version("Atspi", "2.0")
    from gi.repository import Atspi
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
    owners = [relation.get_target(index)
              for relation in ui.target("feedback-dialog").get_relation_set()
              if relation.get_relation_type() == Atspi.RelationType.CONTROLLED_BY
              for index in range(relation.get_n_targets())]
    assert owners == [ui.target("parent-window")]
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
        assert attributes["toolkit"] == "WebKitGTK"
        assert attributes["id"] == identity
        assert guest_reader.find_id(identity, root=ui.target("feedback-webview")) == node
    wait_for_accessible_state(lambda: audit_product_controls(ui, "feedback-dialog"),
                              "complete feedback ID inventory")
    ui.activate("feedback-close")
    wait_for_accessible_state(
        lambda: ui.absent("feedback-dialog", within="parent-window"),
        "feedback dialog closes",
    )
    assert not [relation.get_target(index)
                for relation in ui.target("parent-window").get_relation_set()
                if relation.get_relation_type() == Atspi.RelationType.CONTROLLER_FOR
                for index in range(relation.get_n_targets())
                if public_automation_id(relation.get_target(index)) == "feedback-dialog"]
    ui.activate("parent-menu-button", action_name="menu.popup")
    wait_for_accessible_state(lambda: ui.find("parent-menu-about") is not None,
                              "About menu item publishes its ID")
    ui.activate("parent-menu-about")
    wait_for_accessible_state(lambda: ui.find("about-dialog") is not None,
                              "About dialog publishes its ID")
    assert [relation.get_target(index)
            for relation in ui.target("about-dialog").get_relation_set()
            if relation.get_relation_type() == Atspi.RelationType.CONTROLLED_BY
            for index in range(relation.get_n_targets())] == [ui.target("parent-window")]
    for identity in ("about-version", "about-license-value",
                     "about-legal-notices-value", "about-integration-notice"):
        assert ui.target(identity).get_accessible_id() == identity
    wait_for_accessible_state(lambda: audit_product_controls(ui, "about-dialog"),
                              "complete About ID inventory")
