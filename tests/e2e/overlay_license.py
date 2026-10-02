"""185oa: owned overlay About, license clickability and unchanged choices."""
from installed_journey import JourneyPlan
from journey_blocks import fresh_desktop, parent_management, overlay_entry, overlay_license_read
from request_flow import prepared_request
from request_composition import KioskRequestJourney


CHILD_SCREENS = {
    **{'fresh-' + stage: operation for stage, operation in fresh_desktop('child').items()},
    **overlay_entry('direct', 'command'),
    **prepared_request(prefix='open', entry='open', initial='default',
        child='fixture-child', approver='fixture-parent', duration_seconds=75,
        allow_soft=True, surface='overlay'),
    'missing-about-refused': 'ui:overlay-about-refused',
    **overlay_license_read(), **overlay_license_read('independent-'),
    'cancel': 'ui:overlay-request-cancel', 'returned': 'ui:overlay-desktop',
}
SCREENS = {
    **fresh_desktop('parent'), **parent_management(),
    'wrong-entry-refused': 'ui:parent-overlay-about-refused',
    'allowance-configured': 'ui:time-explanation-positive-read',
    'repeat-desktop': 'ui:desktop', 'switch-user': 'system:parent-switch-user',
    'gdm-switched': 'ui:gdm-returned', **CHILD_SCREENS,
}
PLAN = JourneyPlan(
    prefix='overlay-license', worker_mode='overlay_license', screen_tags=SCREENS,
    phases={'ready': 'setup', 'setup-detached': 'setup',
        **{stage: 'step-1' for stage in SCREENS}, 'installed-greeter': 'start',
        **{stage: 'step-2' for stage in CHILD_SCREENS}},
    advance_after={'gdm-switched': 'step-2'},
    invocations=(*fresh_desktop('parent'),
        *tuple('fresh-' + stage for stage in fresh_desktop('child')),
        'direct-launch', 'direct-form'),
    challenges={
        'parent-login': ('parent', 'recipient-qualified', 'recipient-rechecked'),
        'child-login': ('child', 'fresh-child-recipient-qualified', 'fresh-child-recipient-rechecked')},
    balance_checks={'allowance-configured': 900},
    request_checks={stage: ('open-estimate', 'overlay-about:changed-form', 'unchanged_form')
        for stage in ('form-returned', 'independent-form-returned')},
    assertions_after={'license-read': 'clickable-license',
        'form-returned': 'unchanged-form', 'independent-form-returned': 'independent-unchanged-form'},
)


class OverlayLicenseJourney(KioskRequestJourney):
    def __init__(self, context, progress, plan=PLAN, *, actions=None):
        super().__init__(context, progress, plan, actions=actions)
