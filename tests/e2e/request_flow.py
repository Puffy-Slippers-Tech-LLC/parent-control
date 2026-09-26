"""FLOW04's finite kiosk composition and independent open/new qualification.

The enabled target and earlier public balance are supplied by the caller.
This flow neither changes policy nor submits a request.
"""
from installed_journey import JourneyPlan
from journey_blocks import fresh_desktop, parent_management, station_entry
from kiosk_valid_duration import KioskValidDurationJourney
from private_artifacts import require


def prepared_request(*, prefix, entry, initial, child, approver, duration_seconds, allow_soft):
    """Declare the qualified custom-duration binding with explicit entry state."""
    require(prefix in ('open', 'new'), 'request-flow:prefix')
    require(entry in ('open', 'new') and initial in ('default', 'selected'),
            'request-flow:entry')
    require(child == 'fixture-child' and approver == 'fixture-parent'
            and type(duration_seconds) is int and duration_seconds == 75
            and allow_soft is True, 'request-flow:choices')
    stages = station_entry('cancel-') if entry == 'new' else {}
    stages.update({
        prefix + '-form': 'ui:kiosk-request-form' if initial == 'default' else 'ui:kiosk-valid-fraction-soft-read',
        prefix + '-child': 'ui:kiosk-child-select' if initial == 'default' else 'ui:kiosk-flow-child-select',
        prefix + '-approver': 'ui:kiosk-approver-select' if initial == 'default' else 'ui:kiosk-flow-approver-select',
        prefix + '-selections': 'ui:kiosk-enabled-form' if initial == 'default' else 'ui:kiosk-valid-fraction-soft-read',
        prefix + '-duration': 'ui:kiosk-valid-custom-open',
        **{prefix + '-text-' + action: 'ui:text-kiosk-fraction-' + action
           for action in ('focus', 'selected', 'read')},
        prefix + '-duration-read': 'ui:kiosk-valid-fraction-read' if initial == 'default' else 'ui:kiosk-valid-fraction-soft-read',
        prefix + '-apps': 'ui:kiosk-valid-fraction-soft-select',
        prefix + '-estimate': 'ui:kiosk-valid-fraction-soft-read',
    })
    return stages


CHOICES = dict(child='fixture-child', approver='fixture-parent', duration_seconds=75, allow_soft=True)
SCREENS = {
    **fresh_desktop('parent'), **parent_management(),
    'wrong-entry': 'ui:parent-kiosk-refused',
    'valid-wrong-entry': 'ui:parent-kiosk-valid-refused',
    'limit-enabled': 'ui:parent-toggle-enabled',
    'save-enabled': 'ui:parent-save-enabled',
    'allowance-15-select': 'ui:allowance-15-select',
    'allowance-15-read': 'ui:allowance-15-read',
    'time-explanation-read': 'ui:time-explanation-read',
    'switch-user': 'system:parent-switch-user',
    'gdm-switched': 'ui:gdm-returned',
    **station_entry(),
    **prepared_request(prefix='open', entry='open', initial='default', **CHOICES),
    'open-cancel': 'ui:kiosk-request-cancel',
    'open-returned': 'ui:gdm-station-returned',
    **prepared_request(prefix='new', entry='new', initial='selected', **CHOICES),
    'new-cancel': 'ui:kiosk-request-cancel',
    'new-returned': 'ui:gdm-station-returned',
}
PLAN = JourneyPlan(
    prefix='request-flow', worker_mode='request_flow', screen_tags=SCREENS,
    phases={'ready': 'setup', 'setup-detached': 'setup',
            **{stage: 'step-1' for stage in SCREENS}, 'installed-greeter': 'start',
            **{stage: 'step-2' for stage in list(SCREENS)[list(SCREENS).index('switch-user'):]}},
    advance_after={'time-explanation-read': 'step-2'},
)


class RequestFlowJourney(KioskValidDurationJourney):
    def __init__(self, context, progress):
        super().__init__(context, progress, plan=PLAN)
        self.prepared = None

    def check_settings(self, stage, observed):
        super().check_settings(stage, observed)
        if stage == 'open-estimate':
            self.prepared = observed['ui']['valid_choice']['request']
        elif stage == 'new-estimate':
            require(self.prepared is not None and self.prepared ==
                    observed['ui']['valid_choice']['request'], 'request-flow:reproduced-choices')
            observed['comparison']['reproduced_choices'] = True
