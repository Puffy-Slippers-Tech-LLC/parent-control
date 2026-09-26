"""REQUEST09 invalid kiosk submission with the retained valid-choice regression."""

from dataclasses import replace
from accessible_ui import KIOSK_INVALID_VALUES
from kiosk_valid_duration import PLAN as VALID_PLAN, KioskValidDurationJourney

SCREENS = {}
for stage, operation in VALID_PLAN.screen_tags.items():
    if stage == 'kiosk-request-cancel':
        SCREENS['invalid-custom-open'] = 'ui:kiosk-valid-custom-open'
        for binding in KIOSK_INVALID_VALUES:
            for action in ('focus', 'selected', 'read'):
                name = f'text-kiosk-invalid-{binding}-{action}'
                SCREENS[name] = 'ui:' + name
            for action in ('ready', 'submit', 'read'):
                name = f'kiosk-invalid-{binding}-{action}'
                SCREENS[name] = 'ui:' + name
    SCREENS[stage] = operation
    if stage == 'valid-wrong-entry':
        SCREENS['invalid-wrong-entry'] = 'ui:parent-kiosk-invalid-refused'

PLAN = replace(
    VALID_PLAN, prefix='request-duration', worker_mode='request_duration', screen_tags=SCREENS,
    phases={**VALID_PLAN.phases, **{stage: 'step-2' for stage in SCREENS
                                   if stage not in VALID_PLAN.phases},
            'invalid-wrong-entry': 'step-1'},
)


class RequestDurationJourney(KioskValidDurationJourney):
    def __init__(self, context, progress):
        super().__init__(context, progress, plan=PLAN)
