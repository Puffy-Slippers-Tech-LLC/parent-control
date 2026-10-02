"""048c: one independently prepared Shell challenge and password-free Cancel."""
from installed_journey import JourneyPlan
from journey_blocks import fresh_desktop, parent_management, overlay_entry
from request_flow import prepared_request, overlay_authentication
from request_composition import KioskRequestJourney

CHILD_SCREENS = {
    **{'fresh-' + stage: operation for stage, operation in fresh_desktop('child').items()},
    **overlay_entry('direct', 'command'),
    'wrong-surface-refused': 'ui:overlay-valid-refusals',
    **prepared_request(prefix='open', entry='open', initial='default',
                       child='fixture-child', approver='fixture-parent', duration_seconds=75,
                       allow_soft=True, surface='overlay'),
    **overlay_authentication(result='cancel', prefix='shell'),
    'form-returned': 'ui:overlay-valid-fraction-soft-read',
    'cancel': 'ui:overlay-request-cancel', 'returned': 'ui:overlay-desktop',
}
SCREENS = {
    **fresh_desktop('parent'), **parent_management(),
    'allowance-configured': 'ui:time-explanation-positive-read',
    'wrong-account-refused': 'ui:overlay-wrong-account-refused',
    'repeat-desktop': 'ui:desktop', 'switch-user': 'system:parent-switch-user',
    'gdm-switched': 'ui:gdm-returned', **CHILD_SCREENS,
}
PLAN = JourneyPlan(
    prefix='overlay-prompt', worker_mode='overlay_prompt', screen_tags=SCREENS,
    phases={'ready': 'setup', 'setup-detached': 'setup',
            **{stage: 'step-1' for stage in SCREENS},
            **{stage: 'step-2' for stage in CHILD_SCREENS}, 'installed-greeter': 'start'},
    advance_after={'gdm-switched': 'step-2'},
    invocations=(*fresh_desktop('parent'),
                 *tuple('fresh-' + stage for stage in fresh_desktop('child')),
                 'direct-launch', 'direct-form'),
    challenges={
        'parent-login': ('parent', 'recipient-qualified', 'recipient-rechecked'),
        'child-login': ('child', 'fresh-child-recipient-qualified', 'fresh-child-recipient-rechecked'),
    },
    balance_checks={'allowance-configured': 900},
    request_checks={'form-returned': ('open-estimate', 'shell:form-changed', 'preserved_choices')},
    assertions_after={'shell-cancel-ready': 'shell-recipient-and-refusals',
                      'form-returned': 'cancel-preserved-usable-no-error-form'},
)


class OverlayPromptJourney(KioskRequestJourney):
    def __init__(self, context, progress, plan=PLAN, *, actions=None):
        super().__init__(context, progress, plan, actions=actions)
