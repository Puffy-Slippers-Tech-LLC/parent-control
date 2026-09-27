"""UTF-16 boundary qualification; valid drafts never reach Send."""

from accessible_ui import (LENGTH_OBSERVATIONS, REJECTION_CASES, TEXT_REPETITIONS,
                           DUPLICATE_OPERATIONS)
from feedback_rejection import text_stages
from installed_journey import InstalledJourney, JourneyPlan
from journey_blocks import fresh_desktop
from private_artifacts import require
from ui_observations import FeedbackStateObservation


def input_stages(family, units):
    binding = f'body-{family}-{units}'
    source = binding + '-base' if family == 'mixed' else binding
    seed, *copies = TEXT_REPETITIONS[source]
    return (*text_stages(seed),
            *(stage for stage, (target, _) in DUPLICATE_OPERATIONS.items() if target in copies),
            *(f'text-suffix-{source}-{action}' for action in ('focus', 'caret', 'read')),
            *((f'text-scalar-{binding}-{action}' for action in ('focus', 'caret', 'read'))
              if family == 'mixed' else ()))


def length_boundary(family):
    """One FEED09 UTF-16 family, from empty reply to observed length rejection.

    The caller owns dialog return and independent-entry qualification. Valid
    input is observed and refused by the invalid-only Send guard, never sent.
    """
    require(family in ('ascii', 'mixed'), 'length:family')
    return {stage: 'ui:' + stage for stage in (
        *input_stages(family, 5000), f'length-{family}-valid', f'length-{family}-refusal',
        *input_stages(family, 5001), f'rejection-{family}-send', f'rejection-{family}-read')}


STAGES = ('feedback-open', *(stage for family in ('ascii', 'mixed') for stage in (
    *length_boundary(family),
    f'length-{family}-close', f'length-{family}-wrong-entry', f'length-{family}-reopen',
    f'rejection-{family}-reopened-send', f'rejection-{family}-reopened-read',
    *(('length-ascii-reset-close', 'length-ascii-reset-open') if family == 'ascii' else ()))))
SCREENS = {
    **fresh_desktop('parent'), 'parent-command': 'ui:parent-command-launch',
    **{stage: 'ui:' + stage for stage in (
        'parent-window', 'child-picker-opened', 'child-choice-highlighted',
        'parent-selected', *STAGES)},
    'length-ascii-reset-close': 'ui:length-ascii-close',
    'length-ascii-reset-open': 'ui:length-ascii-reopen',
}
PLAN = JourneyPlan(
    prefix='feedback-length', worker_mode='feedback_length', screen_tags=SCREENS,
    phases={'ready': 'setup', 'setup-detached': 'setup',
            **{stage: 'step-1' for stage in SCREENS}, 'installed-greeter': 'start',
            **{stage: 'step-2' for stage in STAGES
               if 'mixed' in stage or '-reset-' in stage}},
    advance_after={'rejection-ascii-reopened-read': 'step-2'},
    invocations=('length-ascii-reset-close', 'length-ascii-reset-open'),
)


class FeedbackLengthJourney(InstalledJourney):
    def __init__(self, context, progress):
        super().__init__(context, progress, PLAN)
        self.rejected = {}

    def check_settings(self, stage, observed):
        super().check_settings(stage, observed)
        if stage in LENGTH_OBSERVATIONS:
            state = FeedbackStateObservation.from_value(observed['ui']['feedback_state'])
            projection, validation = LENGTH_OBSERVATIONS[stage]
            require((state.draft, state.validation, state.send_enabled)
                    == (projection, validation, True), 'length:public-boundary')
            if stage.endswith('-reopen'):
                family = stage.split('-')[1]
                require(family in self.rejected and state.draft == self.rejected[family].draft,
                        'length:independent-entry')
        elif stage.startswith('rejection-') and stage.endswith('-read'):
            case = stage.removeprefix('rejection-').removesuffix('-read')
            state = FeedbackStateObservation.from_value(observed['ui']['feedback_state'])
            projection, validation = REJECTION_CASES[case]
            require((state.draft, state.validation, state.send_enabled)
                    == (projection, validation, True), 'length:public-rejection')
            if case.endswith('-reopened'):
                require(state == self.rejected.get(case.removesuffix('-reopened')),
                        'length:independent-rejection')
            else:
                require(case not in self.rejected, 'length:replay')
                self.rejected[case] = state
