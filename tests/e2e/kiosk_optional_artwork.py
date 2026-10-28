"""One missing scenery image, genuine approval and restored usable reentry."""
from installed_journey import JourneyPlan
from journey_blocks import (desktop_entry, fresh_desktop, parent_management,
                            prefixed_stages, retained_parent_entry)
from kiosk_approval import KioskApprovalJourney
from kiosk_approved_flow import approved_request
from request_flow import CHOICES, daily_station_entry, prepared_request


ENTRY = prefixed_stages('approved-parent', desktop_entry(
    'parent', source='gdm', entry='retained'))
SCREENS = {
    **fresh_desktop('parent'), **parent_management(), **daily_station_entry(),
    **prepared_request(prefix='new', entry='open', initial='default', compact=True, **CHOICES),
    **approved_request(**CHOICES, exit='automatic'),
    **ENTRY,
    **prefixed_stages('approved-supplied', retained_parent_entry(
        source='same-user', desktop_observation=False)),
    'approved-balance': 'ui:time-explanation-reach-read',
    'approved-switch': 'system:parent-switch-user', 'approved-greeter': 'ui:gdm-returned',
    **prefixed_stages('reentry', prepared_request(
        prefix='open', entry='new', initial='selected', compact=True, **CHOICES)),
    'reentry-exit': 'ui:kiosk-request-cancel', 'reentry-returned': 'ui:gdm-station-returned',
}
PLAN = JourneyPlan(
    prefix='kiosk-optional-artwork', worker_mode='kiosk_optional_artwork', screen_tags=SCREENS,
    phases={'ready': 'setup', 'setup-detached': 'setup', 'installed-greeter': 'start',
            **{stage: 'step-1' for stage in SCREENS if stage != 'installed-greeter'}},
    invocations=tuple(stage for stage, operation in ENTRY.items() if operation.startswith('ui:')),
    challenges={'approved-parent': ('parent', 'approved-parent-recipient-qualified',
                                     'approved-parent-recipient-rechecked')},
    balance_checks={'time-explanation-read': 900},
    assertions_after={'new-estimate': 'missing-scenery-keeps-request-usable',
                      'approved-balance': 'genuine-approval-independent-time-access',
                      'reentry-open-estimate': 'normal-resources-usable-reentry'},
)


class KioskOptionalArtworkJourney(KioskApprovalJourney):
    def __init__(self, context, progress):
        super().__init__(context, progress, plan=PLAN)

    def check_settings(self, stage, observed):
        if stage == 'reentry-open-estimate':
            # REQUEST03/04 reads the complete usable form. The pre-approval
            # balance is no longer an operand for its post-approval estimate.
            # The independent grant comparison remains at approved-balance.
            observed.setdefault('comparison', {})['usable_reentry'] = True
            return
        super().check_settings(stage, observed)
