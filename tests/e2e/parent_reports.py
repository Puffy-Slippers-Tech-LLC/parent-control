"""Reusable Parent error-report declarations and public draft comparisons."""
import re
from match_rules import MatchRuleJourney
from feedback_composition import privacy_review, text_fragment
from private_artifacts import require
from ui_observations import FeedbackObservation


def report_review(prefix):
    """FEED15/05/UI18 from an already displayed automatic Parent report."""
    require(type(prefix) is str and re.fullmatch(r'[a-z][a-z0-9-]*', prefix),
            'report:invocation')
    return {
        prefix + '-report': 'ui:parent-report-read',
        **text_fragment('body-first', prefix + '-body'),
        **text_fragment('reply-first', prefix + '-reply'),
        prefix + '-actions': 'ui:parent-report-actions',
        **privacy_review(prefix=prefix + '-'),
        prefix + '-feedback-draft-reread': 'ui:feedback-draft-reread',
        prefix + '-feedback-draft-closed': 'ui:feedback-draft-closed',
    }


def report_close(prefix):
    """FEED15/UI18: read and close an untouched automatic Parent report."""
    require(type(prefix) is str and re.fullmatch(r'[a-z][a-z0-9-]*', prefix),
            'report:invocation')
    return {
        prefix + '-report': 'ui:parent-report-read',
        prefix + '-feedback-draft-closed': 'ui:feedback-draft-closed',
    }


class ParentReportJourney(MatchRuleJourney):
    """Match restoration and exact synthetic-draft preservation across Privacy."""
    def __init__(self, context, progress, plan, *, actions=None):
        super().__init__(context, progress, plan, actions=actions)
        self.report_draft = None

    def check_settings(self, stage, observed):
        super().check_settings(stage, observed)
        operation = self.plan.screen_tags.get(stage, '').removeprefix('ui:')
        if operation == 'parent-report-read':
            require(FeedbackObservation.from_value(observed['ui']['feedback']).draft
                    == 'parent-rule-error', 'report:automatic-draft')
            self.report_draft = None
        elif operation in ('parent-report-actions', 'feedback-privacy-returned',
                           'feedback-draft-reread'):
            current = FeedbackObservation.from_value(observed['ui']['feedback'])
            require(current.draft == 'synthetic-first', 'report:synthetic-draft')
            if operation == 'parent-report-actions':
                require(self.report_draft is None, 'report:draft-replay')
                self.report_draft = current
            else:
                require(self.report_draft is not None and current == self.report_draft,
                        'report:preserved-draft')
