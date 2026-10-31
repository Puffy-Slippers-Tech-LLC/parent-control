"""FLOW20: station approval followed by the selected child's fresh desktop."""
from installed_journey import JourneyPlan
from journey_blocks import fresh_desktop, parent_management, station_entry
from request_flow import approval_and_return, kiosk_choices
from request_composition import KioskRequestJourney
from private_artifacts import require


def qualification_plan(*, entry, child, approver, seconds, soft):
    binding = kiosk_choices(child, approver, seconds, soft)
    flow = approval_and_return(prefix=entry, entry=entry, child=child, approver=approver,
        duration_seconds=seconds, allow_soft=soft, surface='kiosk', child_entry='fresh')
    parent = parent_management()
    if binding[0] == 'other-child':
        parent.update({'child-picker-opened': 'ui:existing-child-picker-opened',
                       'child-choice-highlighted': 'ui:existing-child-choice-highlighted',
                       'parent-selected': 'ui:discovery-ready'})
    screens = {
        **fresh_desktop('parent'), **parent,
        'allowance-configured': 'ui:time-explanation-setup-thirty-read',
        'repeat-desktop': 'ui:desktop', 'switch-user': 'system:parent-switch-user',
        'gdm-switched': 'ui:gdm-returned',
        **(station_entry() if entry == 'open' else {}), **flow,
    }
    recipient = 'child' if binding[0] == 'child' else 'standard'
    return JourneyPlan(
        prefix='kiosk-fresh-return', worker_mode='kiosk_fresh_return_' + entry,
        screen_tags=screens,
        phases={'ready': 'setup', 'setup-detached': 'setup',
                **{stage: 'step-1' for stage in screens}, 'installed-greeter': 'start'},
        invocations=(*fresh_desktop('parent'),
                     *('fresh-' + stage for stage in fresh_desktop(binding[0]))),
        challenges={'parent-login': ('parent', 'recipient-qualified', 'recipient-rechecked'),
                    'fresh': (binding[0], 'fresh-' + recipient + '-recipient-qualified',
                              'fresh-' + recipient + '-recipient-rechecked')},
        child_bindings={'allowance-configured': 'child' if binding[0] == 'child' else 'existing'},
        balance_checks={'allowance-configured': 1800},
        countdown_checks={'countdown': (entry + '-estimate', 'estimate', 1, 180)},
        kiosk_request=binding,
        assertions_after={'approval-success': 'explicit-selected-child-approval',
                          'new-returned': 'automatic-greeter-return',
                          'fresh-desktop': 'fresh-selected-child-desktop',
                          'countdown': 'elapsed-public-balance-increment'},
    )


NEW_PLAN = qualification_plan(entry='new', child='fixture-child', approver='fixture-parent',
                              seconds=30, soft=False)
OPEN_PLAN = qualification_plan(entry='open', child='existing-fixture-child',
                               approver='other-fixture-parent', seconds=75, soft=True)


class KioskFreshReturnJourney(KioskRequestJourney):
    def __init__(self, context, progress, plan=NEW_PLAN):
        super().__init__(context, progress, plan)

    def check_settings(self, stage, observed):
        super().check_settings(stage, observed)
        if stage == 'allowance-configured':
            require(self.balance['daily']['seconds'] >= 900, 'kiosk-fresh-return:daily-balance')
