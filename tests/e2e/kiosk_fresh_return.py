"""FLOW20: station approval followed by the selected child's declared desktop."""
from installed_journey import JourneyPlan
from journey_blocks import (desktop_entry, fresh_desktop, native_activity_entry,
                            native_activity_resume, parent_management, prefixed_stages, station_entry)
from native_fixtures import fixture_actions
from request_flow import approval_and_return, kiosk_choices
from request_composition import KioskRequestJourney
from private_artifacts import require


def qualification_plan(*, entry, child, approver, seconds, soft, child_entry='fresh'):
    binding = kiosk_choices(child, approver, seconds, soft)
    flow = approval_and_return(prefix=entry, entry=entry, child=child, approver=approver,
        duration_seconds=seconds, allow_soft=soft, surface='kiosk', child_entry=child_entry)
    parent = parent_management(child='child' if binding[0] == 'child' else 'existing')
    retained = child_entry == 'retained'
    role = 'child' if binding[0] == 'child' else 'standard'
    initial_child = prefixed_stages('initial', desktop_entry(binding[0], source='gdm', entry='fresh'))
    balance_parent = prefixed_stages('balance', desktop_entry('parent', source='gdm', entry='retained'))
    activity = 'ui:' + ('overlay-native-' if binding[0] == 'child' else 'native-')
    retained_setup = {
        **initial_child, **native_activity_entry('activity', child=binding[0]),
        'child-switch-ready': fresh_desktop(binding[0])['desktop'],
        'child-switch': 'system:' + role + '-switch-user', 'child-greeter': 'ui:gdm-returned',
        **balance_parent, 'balance-read': 'ui:time-explanation-refresh-read',
        'station-desktop': 'ui:desktop', 'station-switch': 'system:parent-switch-user',
        'station-greeter': 'ui:gdm-returned',
    } if retained else {}
    screens = {
        **fresh_desktop('parent'), **parent,
        'allowance-configured': 'ui:time-explanation-setup-thirty-read',
        'repeat-desktop': 'ui:desktop', 'switch-user': 'system:parent-switch-user',
        'gdm-switched': 'ui:gdm-returned',
        **retained_setup,
        **(station_entry() if entry == 'open' else {}), **flow,
        **({**native_activity_resume('resume', child=binding[0]),
            'activity-returned': activity + 'activity',
            'activity-close': activity + 'close', 'activity-closed': activity + 'closed'} if retained else {}),
    }
    recipient = 'child' if binding[0] == 'child' else 'standard'
    return JourneyPlan(
        prefix='kiosk-' + child_entry + '-return', worker_mode='kiosk_' + child_entry + '_return_' + entry,
        screen_tags=screens,
        phases={'ready': 'setup', 'setup-detached': 'setup',
                **{stage: 'step-1' for stage in screens}, 'installed-greeter': 'start'},
        invocations=(*fresh_desktop('parent'),
                     *((stage for stage in initial_child if stage != 'initial-entry-guard') if retained else ()),
                     *((stage for stage in balance_parent if stage != 'balance-entry-guard') if retained else ()),
                     *(child_entry + '-' + stage for stage in fresh_desktop(binding[0]))),
        challenges={'parent-login': ('parent', 'recipient-qualified', 'recipient-rechecked'),
                    **({'initial': (binding[0], 'initial-' + recipient + '-recipient-qualified',
                                    'initial-' + recipient + '-recipient-rechecked'),
                        'balance': ('parent', 'balance-recipient-qualified', 'balance-recipient-rechecked')}
                       if retained else {}),
                    child_entry: (binding[0], child_entry + '-' + recipient + '-recipient-qualified',
                                  child_entry + '-' + recipient + '-recipient-rechecked')},
        stage_actions={'desktop': 'native-verify'} if retained else {},
        child_bindings={stage: 'child' if binding[0] == 'child' else 'existing'
                        for stage in (('allowance-configured', 'balance-read') if retained
                                      else ('allowance-configured',))},
        balance_checks={'allowance-configured': 1800},
        countdown_checks={'countdown': (entry + '-estimate', 'estimate', 1, 180)},
        activity_entries={'retained-entry-guard': 'activity-capture'} if retained else {},
        activity_checks={stage: ('activity-capture', 'same') for stage in
                         ('resume-opened', 'activity-returned')} if retained else {},
        kiosk_request=binding,
        assertions_after={'approval-success': 'explicit-selected-child-approval',
                          'new-returned': 'automatic-greeter-return',
                          child_entry + '-desktop': child_entry + '-selected-child-desktop',
                          'countdown': 'elapsed-public-balance-increment',
                          **({'activity-returned': 'same-usable-original-work'} if retained else {})},
    )


NEW_PLAN = qualification_plan(entry='new', child='fixture-child', approver='fixture-parent',
                              seconds=30, soft=False)
OPEN_PLAN = qualification_plan(entry='open', child='existing-fixture-child',
                               approver='other-fixture-parent', seconds=75, soft=True)
RETAINED_NEW_PLAN = qualification_plan(entry='new', child='fixture-child', approver='fixture-parent',
                                      seconds=30, soft=False, child_entry='retained')
RETAINED_OPEN_PLAN = qualification_plan(entry='open', child='existing-fixture-child',
    approver='other-fixture-parent', seconds=75, soft=True, child_entry='retained')


class KioskFreshReturnJourney(KioskRequestJourney):
    def __init__(self, context, progress, plan=NEW_PLAN):
        super().__init__(context, progress, plan,
            actions=fixture_actions(include_refusal=False, profile='activity') if plan.activity_checks else None)

    def check_settings(self, stage, observed):
        super().check_settings(stage, observed)
        if stage == 'allowance-configured':
            require(self.balance['daily']['seconds'] >= 900, 'kiosk-fresh-return:daily-balance')
        if stage == 'balance-read':
            require(self.balance['child'] == ('fixture-child' if self.plan.kiosk_request[0] == 'child'
                    else 'existing-fixture-child') and self.balance['daily']['seconds'] >= 900
                    and self.balance['one_time']['seconds'] == 0, 'kiosk-retained-return:daily-balance')
