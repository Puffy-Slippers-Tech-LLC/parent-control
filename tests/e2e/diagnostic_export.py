"""FEED08 fixed qualification; complete case 155 remains separate."""
from installed_journey import JourneyPlan
from journey_blocks import fresh_desktop, parent_management
from attachment_composition import diagnostic_export, DiagnosticExportJourney
from feedback_composition import text_fragment
from synthetic_files import diagnostic_export_actions


SCREENS = {
    **fresh_desktop('parent'), **parent_management(),
    **{stage: operation for entry in ('first', 'second') for stage, operation in {
        entry + '-feedback': 'ui:' + ('feedback-open' if entry == 'first' else 'feedback-draft-reopen'),
        entry + '-collection': 'ui:feedback-collection-ready',
        **text_fragment('body-first', prefix=entry + '-text-body-first'),
        **text_fragment('reply-first', prefix=entry + '-text-reply-first'),
        entry + '-capture': 'ui:switch-draft-before',
        entry + '-refused': 'ui:export-save-chooser-wrong-entry',
        **diagnostic_export(entry),
        entry + '-feedback-draft-reread': 'ui:feedback-draft-reread',
        entry + '-feedback-draft-closed': 'ui:feedback-draft-closed',
    }.items()},
}
PLAN = JourneyPlan(
    prefix='diagnostic-export', worker_mode='diagnostic_export', screen_tags=SCREENS,
    phases={'ready': 'setup', 'setup-detached': 'setup', 'installed-greeter': 'start',
            **{stage: 'step-1' for stage in SCREENS}},
    stage_actions={stage: action for entry in ('first', 'second') for stage, action in {
        entry + '-refused': 'save-prepare', entry + '-result': 'save-read',
        entry + '-inspect': 'diagnostic-inspect', entry + '-feedback-draft-closed': 'save-cleanup',
    }.items()},
)


def journey(context, progress):
    return DiagnosticExportJourney(context, progress, PLAN,
                                   actions=diagnostic_export_actions())
