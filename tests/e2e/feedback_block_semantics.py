"""Independent installed entry/refusal qualification of public block meanings."""
from installed_journey import InstalledJourney, JourneyPlan
from journey_blocks import fresh_desktop
from private_artifacts import require
from block_semantics import FORMATS, expected

STAGES = ('feedback-open', 'text-body-blocks-focus', 'text-body-blocks-selected',
          'text-body-blocks-read', 'block-before',
          *(f'block-{kind}-{action}' for kind in FORMATS
            for action in ('focus', 'home', 'selected', 'read')),
          'block-close', 'block-wrong-entry', 'block-reopen')
SCREENS = {**fresh_desktop('parent'), 'parent-command': 'ui:parent-command-launch',
           **{stage: 'ui:' + stage for stage in (
               'parent-window', 'child-picker-opened', 'child-choice-highlighted',
               'parent-selected', *STAGES)}}
PLAN = JourneyPlan(
    prefix='blocks', worker_mode='feedback_block_semantics', screen_tags=SCREENS,
    phases={'ready': 'setup', 'setup-detached': 'setup',
            **{stage: 'step-1' for stage in SCREENS}, 'installed-greeter': 'start',
            **{stage: 'step-2' for stage in STAGES[-3:]}},
    advance_after={'block-code-read': 'step-2'})


class BlockSemanticsJourney(InstalledJourney):
    def __init__(self, context, progress, plan=PLAN, *, actions=None):
        super().__init__(context, progress, plan, actions=actions)
        self.formatted = None

    def check_settings(self, stage, observed):
        super().check_settings(stage, observed)
        if not (stage in ('block-before', 'block-reopen') or
                stage.startswith('block-') and stage.endswith('-read')):
            return
        result = observed['ui']['blocks']
        require(result == expected(stage), 'blocks:result')
        if stage == 'block-code-read':
            require(self.formatted is None, 'blocks:replay')
            self.formatted = result
        if stage == 'block-reopen':
            require(self.formatted is not None and self.formatted == result,
                    'blocks:independent-entry')
