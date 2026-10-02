"""Case 191: overlay information and unchanged choices after About closes."""

from installed_journey import JourneyPlan, record_installed_journey
from journey_blocks import fresh_desktop, parent_management, overlay_entry, overlay_license_read
from request_flow import prepared_request
from request_composition import KioskRequestJourney


INFORMATION = overlay_license_read(links='information')
SCREENS = {
    **fresh_desktop('parent'), **parent_management(),
    'allowance-configured': 'ui:time-explanation-setup-thirty-read',
    'switch-user': 'system:parent-switch-user',
    'gdm-switched': 'ui:gdm-returned',
    **{'fresh-' + stage: operation for stage, operation in fresh_desktop('child').items()},
    **overlay_entry('direct', 'command'),
    **prepared_request(prefix='open', entry='open', initial='default',
                       child='fixture-child', approver='fixture-parent',
                       duration_seconds=75, allow_soft=True, surface='overlay'),
    'captured-form': 'ui:overlay-valid-fraction-soft-read',
    **INFORMATION,
    'cancel': 'ui:overlay-request-cancel',
    'returned': 'ui:overlay-desktop',
}
PLAN = JourneyPlan(
    prefix='overlay-about', worker_mode='overlay_about', screen_tags=SCREENS,
    phases={'ready': 'setup', 'setup-detached': 'setup',
            **{stage: 'step-1' for stage in SCREENS}, 'installed-greeter': 'start',
            **{stage: 'step-2' for stage in INFORMATION},
            **{stage: 'step-3' for stage in ('about-close-ready', 'about-closed',
                                            'form-returned', 'cancel', 'returned')}},
    advance_after={'captured-form': 'step-2', 'legal-notices-read': 'step-3'},
    invocations=tuple('fresh-' + stage for stage in fresh_desktop('child'))
                + ('direct-launch', 'direct-form'),
    challenges={'child-login': ('child', 'fresh-child-recipient-qualified',
                                'fresh-child-recipient-rechecked')},
    balance_checks={'allowance-configured': 1800},
    request_checks={'form-returned': ('captured-form', 'overlay-about:changed-form', 'unchanged_form')},
)


def execute(recorder, context):
    record_installed_journey(recorder, context, PLAN, timeout=1800,
                             journey_type=KioskRequestJourney)


E2E_CASES = {'child-overlay': execute}
