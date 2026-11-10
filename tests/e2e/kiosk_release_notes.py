"""Case 265: Riley reads upgrade notes and resumes the same usable request."""
from installed_journey import JourneyPlan, record_installed_journey
from journey_blocks import fresh_desktop, parent_management, prefixed_stages, station_entry
from kiosk_whats_new import KioskWhatsNewJourney
from request_flow import prepared_request


SETUP = {
    **fresh_desktop('parent'), **parent_management(),
    'allowance-configured': 'ui:time-explanation-setup-zero-read',
    'policy-before': 'ui:overlay-language-policy',
    'switch-user': 'system:parent-switch-user', 'gdm-switched': 'ui:gdm-returned',
    **station_entry(),
    **prepared_request(prefix='open', entry='open', initial='default',
        child='fixture-child', approver='fixture-parent', duration_seconds=75,
        allow_soft=True, compact=True),
}
READ = {'notes-open': 'ui:kiosk-whats-new-open', 'notes-read': 'ui:kiosk-whats-new-read'}
RETURN = {
    'notes-close': 'ui:kiosk-whats-new-close',
    'form-returned': 'ui:kiosk-valid-fraction-soft-read',
    'cancel': 'ui:kiosk-request-cancel', 'returned': 'ui:gdm-station-returned',
    **prefixed_stages('verify', fresh_desktop('parent')),
    'policy-after': 'ui:overlay-language-policy',
    'balance-after': 'ui:time-explanation-read',
    'parent-logout': 'system:parent-logout', 'final-greeter': 'ui:gdm-returned',
}
SCREENS = {**SETUP, **READ, **RETURN}
PLAN = JourneyPlan(prefix='kiosk-release-notes', worker_mode='kiosk_release_notes',
    screen_tags=SCREENS,
    phases={'ready': 'setup', 'setup-detached': 'setup',
        **{stage: 'step-1' for stage in SETUP}, **{stage: 'step-2' for stage in READ},
        **{stage: 'step-3' for stage in RETURN}, 'installed-greeter': 'start'},
    advance_after={'open-estimate': 'step-2', 'notes-read': 'step-3'},
    balance_checks={'allowance-configured': 0, 'balance-after': 0},
    request_checks={'form-returned': ('open-estimate', 'kiosk-whats-new:changed-request',
                                    'unchanged_request')},
    invocations=tuple(prefixed_stages('verify', fresh_desktop('parent'))),
    challenges={'verify': ('parent', 'verify-recipient-qualified', 'verify-recipient-rechecked')},
    assertions_after={'notes-read': 'child-release-content', 'form-returned': 'unchanged-request',
                      'final-greeter': 'unchanged-policy-and-no-grant'})


class KioskReleaseNotesJourney(KioskWhatsNewJourney):
    def previous_version(self, current):
        # The declared installed preparation binds the real 1.2→2.0 package
        # history. Customer acceptance reads public content, never private state.
        return '1.2'


def execute(recorder, context):
    record_installed_journey(recorder, context, PLAN, timeout=1800,
                             journey_type=KioskReleaseNotesJourney)


E2E_CASES = {'kiosk': execute}
