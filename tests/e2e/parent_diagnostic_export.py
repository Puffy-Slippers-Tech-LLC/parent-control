"""Case 155: Cancel, failed save, recovery, exported contents and Privacy."""
from attachment_composition import (DiagnosticExportJourney, diagnostic_export,
                                    save_cancellation, save_handoff)
from feedback_composition import privacy_review, text_fragment
from installed_journey import JourneyPlan, record_installed_journey
from journey_blocks import fresh_desktop, parent_management
from synthetic_files import diagnostic_export_actions

ENTRY = {**fresh_desktop('parent'), **parent_management(),
         'collection': 'ui:feedback-collection-trace'}
EDIT = {**text_fragment('body-first'), **text_fragment('reply-first')}
CANCEL = {'cancel-capture': 'ui:switch-draft-before',
          **save_cancellation('cancel', draft='synthetic-first'),
          'cancel-return': 'ui:switch-feedback'}
DENIED = {'denied-capture': 'ui:switch-draft-before',
          **save_handoff('denied', draft='synthetic-first', destination='unwritable'),
          'denied-return': 'ui:switch-feedback'}
EXPORT = {'export-capture': 'ui:switch-draft-before', **diagnostic_export('export')}
PRIVACY = {'privacy-capture': 'ui:switch-draft-before', **privacy_review(),
           'privacy-return': 'ui:switch-feedback',
           'feedback-draft-reread': 'ui:feedback-draft-reread',
           'feedback-draft-closed': 'ui:feedback-draft-closed'}
SCREENS = {**ENTRY, **EDIT, **CANCEL, **DENIED, **EXPORT, **PRIVACY}
PLAN = JourneyPlan(prefix='parent-diagnostic-export', worker_mode='parent_diagnostic_export',
    screen_tags=SCREENS,
    phases={'ready': 'setup', 'setup-detached': 'setup',
            **{stage: 'step-1' for stage in (*ENTRY, *EDIT)}, 'installed-greeter': 'start',
            **{stage: 'step-2' for stage in (*CANCEL, *DENIED, *EXPORT, *PRIVACY)}},
    advance_after={'text-reply-first-read': 'step-2'},
    accessibility_inputs={'collection': ('feedback-collection-open', True, 'collection')},
    stage_actions={'parent-selected': 'save-prepare',
                   'cancel-preserved': 'save-cancel-preserved',
                   'denied-result': 'save-denied-preserved',
                   'export-result': 'save-read', 'export-inspect': 'diagnostic-inspect',
                   'feedback-draft-closed': 'save-cleanup'},
    invocations=tuple(stage for stage, operation in SCREENS.items() if operation != 'ui:' + stage))


def execute(recorder, context):
    record_installed_journey(recorder, context, PLAN,
        actions=diagnostic_export_actions(preservation=True), journey_type=DiagnosticExportJourney)


E2E_CASES = {'diagnostic-export': execute}
