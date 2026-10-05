"""Case 154: attach declared files, review them and remove an unwanted file."""
from attachment_composition import AttachmentJourney, file_handoff, attachment_removal
from installed_journey import JourneyPlan, record_installed_journey
from journey_blocks import fresh_desktop, parent_management
from synthetic_files import fixture_actions

ENTRY = {
    **fresh_desktop('parent'), **parent_management(),
    'feedback-open': 'ui:feedback-open',
}
MATRIX = {
    **file_handoff(),
    'chooser-attachments': 'ui:chooser-attachments',
}
REVIEW = {'attachment-details': 'ui:attachment-details', **attachment_removal()}
SCREENS = {**ENTRY, **MATRIX, **REVIEW}
PLAN = JourneyPlan(prefix='feedback-attachments', worker_mode='feedback_attachments',
    screen_tags=SCREENS,
    phases={'ready': 'setup', 'setup-detached': 'setup',
            **{stage: 'step-1' for stage in (*ENTRY, *MATRIX)
               if stage != 'installed-greeter'},
            'installed-greeter': 'start',
            **{stage: 'step-2' for stage in REVIEW}},
    advance_after={'chooser-attachments': 'step-2'},
    stage_actions={'parent-selected': 'attachment-fixtures',
                   'attachment-remaining': 'attachment-cleanup'})


ACTIONS = fixture_actions(('standard',), stage='attachment-fixtures', cleanup='attachment-cleanup')


def execute(recorder, context):
    record_installed_journey(recorder, context, PLAN, actions=ACTIONS,
                             journey_type=AttachmentJourney)


E2E_CASES = {'attachments': execute}
