"""Application UI identity and public language-control contracts."""

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
    # The Parent switch publishes an accessible label, not displayed child text.
    read_owner_text = ui.text if frontend == 'parent' else ui.getText
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
        assert read_owner_text(owner) == owner_text, 'candidate escaped into owner'
        assert not any(event['event'] == 'language-committed' for event in read_events(events))
    ui.activate('language-cancel')
    wait(lambda: ui.absent('language-dialog', within=(
        'parent-window' if frontend == 'parent' else 'kiosk-request-window')),
         'Cancel leaves the owner language unchanged')
    assert read_owner_text(owner) == owner_text




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
    from tests.e2e.accessible_ui import CHILD, EXISTING_CHILD, PARENT, OTHER_PARENT

    launch_ui("kiosk_preview", wait_for_application=False)
    ui = automation
    wait_for_accessible_state(lambda: ui.showing("kiosk-approver-selector"), "request ready")
    ui.setValue("kiosk-approver-selector", "1010")
    wait_for_accessible_state(lambda: ui.showing("kiosk-approver-selected-1010"), "selected approver UID")
    ui.setValue("kiosk-child-selector", "1002")
    wait_for_accessible_state(lambda: ui.showing("kiosk-child-selected-1002"), "selected child UID")
    wait_for_accessible_state(lambda: ui.showing("kiosk-screen-limit-notice"), "disabled child loaded")
    reader = ui.reader
    reader.fixture_uids = {CHILD: 1001, EXISTING_CHILD: 1002,
                          PARENT: 1000, OTHER_PARENT: 1010}
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
    # Host and installed operations share one owner-pinned catalog and scope.
    guest_reader = ui.reader
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
