"""048c: two independently prepared Shell challenges and password-free Cancels."""
from installed_journey import JourneyPlan
from journey_blocks import fresh_desktop, parent_management, overlay_entry, prefixed_stages
from request_flow import prepared_request, overlay_authentication
from request_composition import KioskRequestJourney

REQUEST_SCREENS = {}
for prefix, initial in (('first', 'default'), ('second', 'selected')):
    REQUEST_SCREENS[prefix] = {
        **overlay_entry('direct', 'command', form_operation=(
            'overlay-request-form' if initial == 'default' else 'overlay-valid-fraction-soft-read')),
        'wrong-surface-refused': 'ui:overlay-valid-refusals',
        **prepared_request(prefix='open', entry='open', initial=initial,
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
    'gdm-switched': 'ui:gdm-returned',
    **prefixed_stages('fresh', fresh_desktop('child')),
    **prefixed_stages('first', REQUEST_SCREENS['first']),
    **prefixed_stages('second', REQUEST_SCREENS['second']),
}
PLAN = JourneyPlan(
    prefix='overlay-prompt', worker_mode='overlay_prompt', screen_tags=SCREENS,
    phases={'ready': 'setup', 'setup-detached': 'setup',
            **{stage: 'step-1' for stage in SCREENS},
            **{stage: 'step-2' for stage in prefixed_stages('first', REQUEST_SCREENS['first'])},
            **{stage: 'step-3' for stage in prefixed_stages('second', REQUEST_SCREENS['second'])},
            'installed-greeter': 'start'},
    advance_after={'fresh-desktop': 'step-2', 'first-returned': 'step-3'},
    invocations=(*fresh_desktop('parent'),
                 *tuple('fresh-' + stage for stage in fresh_desktop('child')),
                 'first-direct-launch', 'first-direct-form',
                 'second-direct-launch', 'second-direct-form'),
    challenges={
        'parent-login': ('parent', 'recipient-qualified', 'recipient-rechecked'),
        'child-login': ('child', 'fresh-child-recipient-qualified', 'fresh-child-recipient-rechecked'),
    },
    balance_checks={'allowance-configured': 900},
    request_checks={prefix + '-form-returned': (
        prefix + '-open-estimate', 'shell:form-changed', 'preserved_choices')
        for prefix in ('first', 'second')},
    assertions_after={stage: assertion
        for prefix in ('first', 'second')
        for stage, assertion in (
            (prefix + '-shell-cancel-ready', prefix + '-shell-recipient-and-refusals'),
            (prefix + '-form-returned', prefix + '-cancel-preserved-usable-no-error-form'))},
)


class OverlayPromptJourney(KioskRequestJourney):
    def __init__(self, context, progress, plan=PLAN, *, actions=None):
        super().__init__(context, progress, plan, actions=actions)
