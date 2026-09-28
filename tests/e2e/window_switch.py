"""DESK10 same-desktop existing-window qualification; no feedback submission."""
from installed_journey import InstalledJourney, JourneyPlan
from journey_blocks import fresh_desktop
from private_artifacts import require
import re


def window_switch_entry(prefix=''):
    """Launch the supporting viewer once and return to the observed Parent."""
    require(isinstance(prefix, str) and re.fullmatch(r'(?:[a-z][a-z0-9-]*-)?', prefix),
            'switch:invocation')
    return {prefix + stage: 'ui:' + stage for stage in (
        'switch-parent-before', 'switch-viewer-launch', 'switch-parent-ready', 'switch-parent')}

STAGES = (
    *window_switch_entry(), 'feedback-open',
    'text-body-first-focus', 'text-body-first-selected', 'text-body-first-read',
    'text-reply-first-anchor', 'text-reply-first-focus',
    'text-reply-first-selected', 'text-reply-first-read',
    'switch-draft-before', 'switch-viewer-ready', 'switch-viewer',
    'switch-feedback-ready', 'switch-feedback',
    'switch-viewer-again-ready', 'switch-viewer-again',
    'switch-feedback-again-ready', 'switch-feedback-again',
    'switch-viewer-close-ready', 'switch-viewer-close',
    'switch-viewer-absent',
)
SCREENS = {
    **fresh_desktop('parent'), 'parent-command': 'ui:parent-command-launch',
    **{stage: 'ui:' + stage for stage in (
        'parent-window', 'child-picker-opened', 'child-choice-highlighted',
        'parent-selected', *STAGES)},
}
PLAN = JourneyPlan(
    prefix='window-switch', worker_mode='window_switch', screen_tags=SCREENS,
    phases={'ready': 'setup', 'setup-detached': 'setup',
            **{stage: 'step-1' for stage in SCREENS}, 'installed-greeter': 'start',
            **{stage: 'step-2' for stage in STAGES[STAGES.index('switch-viewer-ready'):]}},
    advance_after={'switch-draft-before': 'step-2'},
)


class WindowSwitchJourney(InstalledJourney):
    def __init__(self, context, progress, plan=PLAN, *, actions=None):
        super().__init__(context, progress, plan, actions=actions)
        self.windows = {}

    def check_settings(self, stage, observed):
        super().check_settings(stage, observed)
        stage = self.plan.screen_tags.get(stage, '').removeprefix('ui:').removeprefix('draft-')
        if not stage.startswith('switch-'):
            return
        value = observed['ui']['window']
        binding = value['binding']
        entries = {'parent': 'switch-parent-before', 'viewer': 'switch-viewer-launch',
                   'feedback': 'switch-draft-before'}
        if stage == entries[binding]:
            require(binding not in self.windows, 'switch:replayed-entry')
            self.windows[binding] = value
        else:
            expected = self.windows.get(binding)
            if stage.endswith('-ready') and expected is not None:
                expected = {key: item for key, item in expected.items() if key != 'feedback'}
                expected['active'] = False
            require(expected is not None and value == expected,
                    'switch:window-or-draft-changed')
