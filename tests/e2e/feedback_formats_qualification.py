"""Independent installed all-format entry, removal and refusal qualification."""
from installed_journey import InstalledJourney, JourneyPlan
from journey_blocks import fresh_desktop
from private_artifacts import require
from feedback_formats import STAGES, LINK_STAGES, OPERATIONS, expected
import block_semantics

SCREENS = {**fresh_desktop('parent'), 'parent-command': 'ui:parent-command-launch',
           **{stage: 'ui:' + stage for stage in (
               'parent-window', 'child-picker-opened', 'child-choice-highlighted',
               'parent-selected', *STAGES)}}
PLAN = JourneyPlan(prefix='formats', worker_mode='feedback_formats', screen_tags=SCREENS,
    phases={'ready': 'setup', 'setup-detached': 'setup', 'installed-greeter': 'start',
            **{stage: 'step-1' for stage in SCREENS if stage != 'installed-greeter'},
            **{stage: 'step-2' for stage in STAGES[STAGES.index('formats-kept-close'):]}},
    advance_after={'formats-link-read': 'step-2'})


class FeedbackFormatsJourney(InstalledJourney):
    def __init__(self, context, progress, plan=PLAN, *, actions=None):
        super().__init__(context, progress, plan, actions=actions)
        self.formatted = None
        self.cleared = None

    def check_settings(self, stage, observed):
        super().check_settings(stage, observed)
        if stage.startswith('block-') and stage.endswith('-read'):
            require(observed['ui']['blocks'] == block_semantics.expected(stage), 'formats:blocks')
        if stage not in OPERATIONS or not (stage.endswith(('-read', '-reopen')) or
                                           stage in ('formats-before', 'linked-before')):
            return
        result = observed['ui']['formats']
        require(result == expected(stage), 'formats:result')
        if stage in ('formats-link-read', 'linked-link-read'):
            require(self.formatted is None, 'formats:replay')
            self.formatted = result
        elif stage == 'formats-clear-read':
            require(self.cleared is None, 'formats:replay')
            self.cleared = result
        elif stage.endswith('-reopen'):
            require(result == (self.formatted if stage.endswith('-kept-reopen') else self.cleared),
                    'formats:independent-entry')


LINK_SCREENS = {**fresh_desktop('parent'), 'parent-command': 'ui:parent-command-launch',
                **{stage: 'ui:' + stage for stage in (
                    'parent-window', 'child-picker-opened', 'child-choice-highlighted',
                    'parent-selected', *LINK_STAGES)}}
LINK_PLAN = JourneyPlan(prefix='linked', worker_mode='feedback_link_semantics',
    screen_tags=LINK_SCREENS,
    phases={'ready': 'setup', 'setup-detached': 'setup', 'installed-greeter': 'start',
            **{stage: 'step-1' for stage in LINK_SCREENS if stage != 'installed-greeter'},
            **{stage: 'step-2' for stage in LINK_STAGES[-3:]}},
    advance_after={'linked-link-read': 'step-2'})


class FeedbackLinkJourney(FeedbackFormatsJourney):
    def __init__(self, context, progress, plan=LINK_PLAN, *, actions=None):
        super().__init__(context, progress, plan, actions=actions)
