"""FEED08 fixed qualification; complete case 155 remains separate."""
from installed_journey import JourneyPlan
from journey_blocks import fresh_desktop
from attachment_composition import diagnostic_export, DiagnosticExportJourney
from synthetic_files import diagnostic_export_actions


SCREENS = {
    **fresh_desktop('parent'), 'parent-command': 'ui:parent-command-launch',
    **{stage: 'ui:' + stage for stage in ('parent-window', 'child-picker-opened',
        'child-choice-highlighted', 'parent-selected')},
    **{stage: operation for entry in ('first', 'second') for stage, operation in {
        entry + '-feedback': 'ui:' + ('feedback-open' if entry == 'first' else 'feedback-draft-reopen'),
        entry + '-collection': 'ui:feedback-collection-ready',
        **{entry + '-text-' + binding + '-' + step: 'ui:text-' + binding + '-' + step
           for binding in ('body-first', 'reply-first')
           for step in (('anchor', 'focus', 'selected', 'read') if binding == 'reply-first'
                        else ('focus', 'selected', 'read'))},
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
